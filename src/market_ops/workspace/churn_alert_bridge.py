"""LiveOps → Growth 桥接层 — 订阅 churn_alert 自动生成 Growth 响应动作.

协同方向: LiveOps (churn_alert broadcast) → Growth (响应动作建议)

设计原则:
  - 不修改现有 SignalType 枚举和决策引擎 (避免破坏 Growth 主链稳定性)
  - 独立桥接层: 订阅 MessageBus → 生成 GrowthResponse → JSONL 持久化
  - 响应动作是"建议" (suggested), 不直接执行, 等人工或后续阶段审批

响应策略 (按 high_value_at_risk 分级):
  - >= 10 (high):   暂停拉新 + 60% 预算转向召回受众
  - 3-9  (medium):  削减 30% UA 预算 + 30% 转向召回受众
  - 1-2  (low):     持续观察 (仅建议, 不调整预算)
  - 0:              不响应 (LiveOps 不会广播 high_value=0 的事件)

用法:
    bridge = ChurnAlertBridge(data_dir="data", message_bus=bus)
    bridge.register()  # 注册到 MessageBus, 自动消费 churn_alert

    # 也可直接调用 (测试或不依赖 MessageBus 的场景)
    response = bridge.process_churn_alert(alert_payload)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 响应动作分级阈值 ──────────────────────────────────────────
HIGH_SEVERITY_THRESHOLD = 10      # high_value >= 10 → 暂停拉新
MEDIUM_SEVERITY_THRESHOLD = 3     # high_value >= 3 → 削减预算


class ChurnAlertBridge:
    """LiveOps → Growth 桥接层 — 消费 churn_alert 生成 Growth 响应动作.

    职责:
      1. 注册到 MessageBus, 订阅 LiveOps BROADCAST 消息
      2. 过滤 subject == "liveops:churn_alert" 的事件
      3. 按 high_value_at_risk 分级生成 Growth 响应动作 (pause/reallocate/reduce/monitor)
      4. 响应写入 data/growth/churn_responses.jsonl (append-only)
      5. 提供 list_responses / get_response API 供 Dashboard 查询

    不职责:
      - 不直接执行 Growth 动作 (只生成建议)
      - 不修改 GrowthSignalEngine / SignalType 枚举
      - 不替代 GrowthLoop 的主决策链
    """

    def __init__(
        self,
        data_dir: str = "data",
        message_bus: Any = None,
        agent_identity: Any = None,
        auto_execute: bool = True,
        dry_run: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._message_bus = message_bus
        self._agent_identity = agent_identity
        self._responses_path = self.data_dir / "growth" / "churn_responses.jsonl"
        self._audit_path = self.data_dir / "growth" / "churn_response_audit.jsonl"
        self._registered = False
        # 自动执行配置: auto_execute=True → 生成响应后立即执行所有动作
        # dry_run=True → 模拟执行 (无真实 Meta Ads API 调用); False → 真实执行
        self.auto_execute = auto_execute
        self.dry_run = dry_run

    # ── MessageBus 订阅 ──────────────────────────────────────

    def register(self) -> bool:
        """注册到 MessageBus, 订阅 LiveOps BROADCAST 消息.

        Returns:
            True=注册成功; False=未注入 message_bus 或注册失败
        """
        if self._message_bus is None:
            logger.warning("ChurnAlertBridge: message_bus not injected, skip register")
            return False

        try:
            from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                MessageType,
            )
            self._message_bus.register_handler_fn(
                agent_id=self._agent_id(),
                handler_fn=self._handle_message,
                message_types=[MessageType.BROADCAST],
            )
            self._registered = True
            logger.info(
                "ChurnAlertBridge: registered to MessageBus (agent_id=%s)",
                self._agent_id(),
            )
            return True
        except Exception as exc:
            logger.warning("ChurnAlertBridge: register failed: %s", exc)
            return False

    def _agent_id(self) -> str:
        """获取 Growth Agent ID (用于 MessageBus 注册)."""
        if self._agent_identity is not None:
            return getattr(self._agent_identity, "agent_id", "growth_agent")
        return "growth_agent"

    def _handle_message(self, message: Any) -> Any:
        """MessageBus handler — 过滤 churn_alert 并处理.

        MessageBus 的 BROADCAST 会投递到所有注册 handler 的 Agent,
        此处按 subject 过滤, 只处理 liveops:churn_alert.
        """
        if getattr(message, "subject", "") != "liveops:churn_alert":
            return None  # 非 churn_alert, 忽略
        try:
            self.process_churn_alert(message.body)
        except Exception as exc:
            logger.warning("ChurnAlertBridge: handle churn_alert failed: %s", exc)
        return None  # 不返回响应消息 (单向消费)

    # ── 核心逻辑: churn_alert → GrowthResponse ────────────────

    def process_churn_alert(self, alert_payload: dict[str, Any]) -> dict[str, Any]:
        """处理 churn_alert 事件, 生成 Growth 响应动作.

        Args:
            alert_payload: churn_alert 的 body (含 game_id, high_value_at_risk 等)

        Returns:
            GrowthResponse dict (含 response_id, actions, severity 等)
        """
        game_id = alert_payload.get("game_id", "unknown")
        high_value = int(alert_payload.get("high_value_at_risk", 0))

        severity = self._classify_severity(high_value)
        actions = self._generate_actions(game_id, high_value, severity, alert_payload)

        response = {
            "response_id": f"gr-{game_id}-{uuid.uuid4().hex[:8]}",
            "alert_campaign_id": alert_payload.get("campaign_id", ""),
            "alert_timestamp": alert_payload.get("timestamp", ""),
            "game_id": game_id,
            "high_value_at_risk": high_value,
            "target_segment": alert_payload.get("target_segment", ""),
            "rewards_pool": alert_payload.get("rewards_pool", 0.0),
            "severity": severity,
            "actions": actions,
            "action_count": len(actions),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "suggested",  # 初始状态, auto_execute=True 时会被覆盖
            "source": "churn_alert_bridge",
        }

        # 自动执行: 生成响应后立即执行所有动作
        if self.auto_execute:
            response = self._execute_response(response)

        self._persist_response(response)
        logger.info(
            "ChurnAlertBridge: generated response %s (game=%s, severity=%s, status=%s, actions=%d)",
            response["response_id"], game_id, severity, response["status"], len(actions),
        )
        return response

    # ── 自动执行 ─────────────────────────────────────────────

    def _execute_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """执行响应中的所有动作 — 自动执行核心方法.

        执行流程:
          1. 遍历 response["actions"], 逐个调用 _execute_action
          2. 每个动作写入 execution_result 字段
          3. 根据全部执行结果更新 response["status"]
          4. 写入审计日志

        执行状态:
          - dry_run=True:  status="executed" (模拟执行)
          - dry_run=False: status="executed" (真实执行)
          - 部分失败:      status="partial_executed"
        """
        for action in response["actions"]:
            action["execution_result"] = self._execute_action(action, response)

        all_success = all(
            a.get("execution_result", {}).get("success", False)
            for a in response["actions"]
        )
        response["status"] = "executed" if all_success else "partial_executed"
        response["executed_at"] = datetime.now(timezone.utc).isoformat()
        response["dry_run"] = self.dry_run

        # 审计日志
        self._persist_audit({
            "audit_type": "execute",
            "response_id": response["response_id"],
            "game_id": response["game_id"],
            "severity": response["severity"],
            "executed_at": response["executed_at"],
            "dry_run": self.dry_run,
            "action_count": len(response["actions"]),
            "all_success": all_success,
        })

        logger.info(
            "ChurnAlertBridge: executed response %s (dry_run=%s, all_success=%s)",
            response["response_id"], self.dry_run, all_success,
        )
        return response

    def _execute_action(self, action: dict, response: dict) -> dict[str, Any]:
        """执行单个动作 (模拟 / 真实).

        Args:
            action: 动作 dict (含 action_type, target, reason 等)
            response: 所属响应 dict (含 game_id 等)

        Returns:
            execution_result dict (含 success, status, message, executed_at)
        """
        action_type = action.get("action_type", "unknown")
        game_id = response["game_id"]

        # 模拟执行 (未来对接 Meta Ads API 时替换为真实执行)
        result = {
            "success": True,
            "status": "simulated" if self.dry_run else "executed",
            "message": self._execution_message(action_type, game_id, action),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
        }
        return result

    def _execution_message(self, action_type: str, game_id: str, action: dict) -> str:
        """生成执行消息."""
        suffix = " (模拟)" if self.dry_run else ""
        if action_type == "pause_campaign":
            return f"已暂停 {game_id} 的 UA 拉新活动{suffix}"
        if action_type == "reallocate_budget":
            ratio = action.get("ratio", 0)
            return f"已将 {game_id} 的 {int(ratio*100)}% UA 预算转向召回受众{suffix}"
        if action_type == "reduce_budget":
            ratio = action.get("ratio", 0)
            return f"已削减 {game_id} 的 {int(ratio*100)}% UA 预算{suffix}"
        if action_type == "monitor":
            return f"持续观察 {game_id} 的流失情况{suffix}"
        return f"已执行 {action_type}{suffix}"

    # ── 回滚 ─────────────────────────────────────────────────

    def rollback_response(self, response_id: str) -> dict[str, Any] | None:
        """回滚已执行的响应 — 恢复 UA 状态.

        Args:
            response_id: 响应 ID

        Returns:
            更新后的 response (status="rolled_back"); None=未找到
        """
        response = self.get_response(response_id)
        if response is None:
            return None

        if response.get("status") not in ("executed", "partial_executed"):
            return response  # 未执行, 无需回滚

        # 模拟回滚每个动作
        for action in response.get("actions", []):
            action["rollback_result"] = {
                "success": True,
                "status": "rolled_back",
                "message": self._rollback_message(action, response["game_id"]),
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            }

        response["status"] = "rolled_back"
        response["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

        # 追加新记录 (覆盖旧记录)
        self._persist_response(response)

        # 审计日志
        self._persist_audit({
            "audit_type": "rollback",
            "response_id": response_id,
            "game_id": response["game_id"],
            "rolled_back_at": response["rolled_back_at"],
            "action_count": len(response.get("actions", [])),
        })

        logger.info(
            "ChurnAlertBridge: rolled back response %s (game=%s)",
            response_id, response["game_id"],
        )
        return response

    def _rollback_message(self, action: dict, game_id: str) -> str:
        """生成回滚消息."""
        action_type = action.get("action_type", "unknown")
        if action_type == "pause_campaign":
            return f"已恢复 {game_id} 的 UA 拉新活动"
        if action_type == "reallocate_budget":
            return f"已恢复 {game_id} 的预算分配"
        if action_type == "reduce_budget":
            return f"已恢复 {game_id} 的 UA 预算"
        if action_type == "monitor":
            return f"停止观察 {game_id}"
        return f"已回滚 {action_type}"

    def _persist_audit(self, audit_record: dict[str, Any]) -> None:
        """追加写入审计日志 (append-only)."""
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询审计日志."""
        if not self._audit_path.exists():
            return []
        try:
            text = self._audit_path.read_text(encoding="utf-8")
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        records.reverse()
        return records[:limit]

    def _classify_severity(self, high_value: int) -> str:
        """按 high_value_at_risk 分级."""
        if high_value >= HIGH_SEVERITY_THRESHOLD:
            return "high"
        if high_value >= MEDIUM_SEVERITY_THRESHOLD:
            return "medium"
        return "low"

    def _generate_actions(
        self,
        game_id: str,
        high_value: int,
        severity: str,
        alert_payload: dict,
    ) -> list[dict[str, Any]]:
        """根据严重度生成 Growth 响应动作建议."""
        actions: list[dict[str, Any]] = []

        if severity == "high":
            # 高严重度: 暂停拉新 + 60% 预算转向召回
            actions.append({
                "action_type": "pause_campaign",
                "target": f"{game_id}:ua_campaigns",
                "reason": f"高价值流失 {high_value} 人, 暂停拉新避免加剧流失",
                "priority": "high",
                "expected_effect": "停止引入新用户, 聚焦留存",
            })
            actions.append({
                "action_type": "reallocate_budget",
                "from_target": f"{game_id}:ua_budget",
                "to_target": f"{game_id}:retention_audience",
                "ratio": 0.6,
                "reason": "将 60% UA 预算转向召回受众",
                "priority": "medium",
                "expected_effect": "提升回流触达, 对冲流失",
            })

        elif severity == "medium":
            # 中严重度: 削减 30% UA 预算 + 30% 转向召回
            actions.append({
                "action_type": "reduce_budget",
                "target": f"{game_id}:ua_campaigns",
                "ratio": 0.3,
                "reason": f"高价值流失 {high_value} 人, 削减 30% UA 预算",
                "priority": "medium",
                "expected_effect": "降低拉新速度, 给留存留出窗口",
            })
            actions.append({
                "action_type": "reallocate_budget",
                "from_target": f"{game_id}:ua_budget",
                "to_target": f"{game_id}:retention_audience",
                "ratio": 0.3,
                "reason": "将 30% UA 预算转向召回受众",
                "priority": "low",
                "expected_effect": "小幅加码召回, 测试效果",
            })

        else:
            # 低严重度: 仅建议观察
            actions.append({
                "action_type": "monitor",
                "target": game_id,
                "reason": f"高价值流失 {high_value} 人, 持续观察不调整预算",
                "priority": "low",
                "expected_effect": "积累数据, 等待下次分析",
            })

        return actions

    # ── 持久化 ───────────────────────────────────────────────

    def _persist_response(self, response: dict[str, Any]) -> None:
        """追加写入 churn_responses.jsonl (append-only)."""
        self._responses_path.parent.mkdir(parents=True, exist_ok=True)
        with self._responses_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(response, ensure_ascii=False) + "\n")

    # ── 查询 API ─────────────────────────────────────────────

    def list_responses(
        self,
        game_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询 Growth 响应记录.

        Args:
            game_id: 过滤指定游戏 (None=全部)
            limit: 返回最近 N 条 (倒序)

        Returns:
            响应记录列表 (最新的在前)
        """
        if not self._responses_path.exists():
            return []
        try:
            text = self._responses_path.read_text(encoding="utf-8")
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if game_id and rec.get("game_id") != game_id:
                continue
            records.append(rec)
        # 倒序: 最新在前
        records.reverse()
        return records[:limit]

    def get_response(self, response_id: str) -> dict[str, Any] | None:
        """按 response_id 查询单条响应记录."""
        if not self._responses_path.exists():
            return None
        try:
            text = self._responses_path.read_text(encoding="utf-8")
        except OSError:
            return None
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("response_id") == response_id:
                return rec
        return None

    def get_stats(self) -> dict[str, Any]:
        """聚合统计 — 供 Dashboard 概览."""
        responses = self.list_responses(limit=10000)
        if not responses:
            return self._empty_stats()

        severity_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        status_counts: dict[str, int] = {}
        action_type_counts: dict[str, int] = {}
        by_game: dict[str, int] = {}

        for r in responses:
            sev = r.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            status = r.get("status", "suggested")
            status_counts[status] = status_counts.get(status, 0) + 1
            gid = r.get("game_id", "unknown")
            by_game[gid] = by_game.get(gid, 0) + 1
            for action in r.get("actions", []):
                at = action.get("action_type", "unknown")
                action_type_counts[at] = action_type_counts.get(at, 0) + 1

        return {
            "total_responses": len(responses),
            "severity_distribution": severity_counts,
            "status_distribution": status_counts,
            "action_type_distribution": action_type_counts,
            "by_game": by_game,
            "recent_responses": responses[:5],
        }

    def _empty_stats(self) -> dict[str, Any]:
        return {
            "total_responses": 0,
            "severity_distribution": {"high": 0, "medium": 0, "low": 0},
            "status_distribution": {},
            "action_type_distribution": {},
            "by_game": {},
            "recent_responses": [],
        }
