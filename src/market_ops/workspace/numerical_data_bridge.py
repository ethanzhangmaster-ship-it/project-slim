"""Numerical Designer → Data Analyst 反向桥接层 — 订阅数值调优触发重新分析.

协同方向: Numerical Designer (tuning/modeling/ab_test broadcast) → Data Analyst (anomaly/retention/behavior)

设计原则 (与 DataNumericalBridge 对称):
  - 不修改现有 NumericalDesignerAgent 或 DataAnalystAgent (避免破坏已有逻辑)
  - 独立桥接层: 订阅 MessageBus → 转换数据 → 调用 DataAnalyst 方法 → JSONL 持久化
  - 双向闭环: 数值调优 → 重新检测异常 → 验证调优效果

触发策略 (按事件类型):
  - tuning_recommended:    → detect_anomalies (调优后重新检测异常, 验证调优效果)
  - numerical_modeled:     → predict_retention (基于新 LTV/CAC 模型重新预测留存)
  - ab_test_designed:      → analyze_behavior (A/B 测试设计后建立行为基线)

数据转换: TuningRecommendation/NumericalModel → BehaviorData
  - 从调优建议中提取 target_metric 和 current_value
  - 反向映射为 BehaviorData (用于 Data Analyst 的分析方法)
  - 保留原始调优建议作为上下文

与 DataNumericalBridge 的关系:
  - DataNumericalBridge: Data Analyst → Numerical (正向, 已存在)
  - NumericalDataBridge: Numerical → Data Analyst (反向, 本模块)
  - 两者独立运行, 互不干扰, 形成双向闭环:
    行为分析 → 数值建模 → 调优建议 → 重新检测异常 → (循环)

用法:
    bridge = NumericalDataBridge(
        data_dir="data",
        message_bus=bus,
        data_analyst_agent=data_analyst,
    )
    bridge.register()  # 注册到 MessageBus, 自动消费 numerical 事件

    # 也可直接调用 (测试或不依赖 MessageBus 的场景)
    result = bridge.process_tuning_recommendation(tuning_payload)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """UTC ISO 时间戳."""
    return datetime.now(timezone.utc).isoformat()


class NumericalDataBridge:
    """Numerical Designer → Data Analyst 反向桥接层.

    职责:
      1. 注册到 MessageBus, 订阅 Numerical Designer BROADCAST 消息
      2. 过滤 subject 前缀 == "numerical:" 的事件
      3. 按事件类型转换数据并调用 Data Analyst 对应方法
      4. 协同结果写入 data/collaboration/numerical_data.jsonl (append-only)
      5. 审计日志写入 data/collaboration/numerical_data_audit.jsonl

    不职责:
      - 不修改 NumericalDesignerAgent 或 DataAnalystAgent 的代码
      - 不替代 DataNumericalBridge 的正向链路
      - 不直接执行调优操作 (仅触发重新分析)
    """

    def __init__(
        self,
        data_dir: str = "data",
        message_bus: Any = None,
        agent_identity: Any = None,
        data_analyst_agent: Any = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._message_bus = message_bus
        self._agent_identity = agent_identity
        self._data_analyst_agent = data_analyst_agent
        self._collaboration_path = self.data_dir / "collaboration" / "numerical_data.jsonl"
        self._audit_path = self.data_dir / "collaboration" / "numerical_data_audit.jsonl"
        self._registered = False

    # ── MessageBus 订阅 ──────────────────────────────────────

    def register(self) -> bool:
        """注册到 MessageBus, 订阅 Numerical Designer BROADCAST 消息.

        Returns:
            True=注册成功; False=未注入 message_bus 或注册失败
        """
        if self._message_bus is None:
            logger.warning("NumericalDataBridge: message_bus not injected, skip register")
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
                "NumericalDataBridge: registered to MessageBus (agent_id=%s)",
                self._agent_id(),
            )
            return True
        except Exception as exc:
            logger.warning("NumericalDataBridge: register failed: %s", exc)
            return False

    def _agent_id(self) -> str:
        """获取 Data Analyst Agent ID (用于 MessageBus 注册)."""
        if self._agent_identity is not None:
            return getattr(self._agent_identity, "agent_id", "data_analyst_agent")
        return "numerical_data_bridge"

    def _handle_message(self, message: Any) -> Any:
        """MessageBus handler — 过滤 numerical 事件并路由处理."""
        subject = getattr(message, "subject", "")
        if not subject.startswith("numerical:"):
            return None

        event_type = subject.replace("numerical:", "")
        body = getattr(message, "body", {}) or {}

        try:
            handler = self._get_event_handler(event_type)
            if handler is not None:
                handler(body)
            else:
                logger.debug("NumericalDataBridge: no handler for event_type=%s", event_type)
        except Exception as exc:
            logger.warning(
                "NumericalDataBridge: handle %s failed: %s",
                event_type, exc,
            )
        return None

    def _get_event_handler(self, event_type: str):
        """按事件类型路由到对应处理方法."""
        handlers = {
            "tuning_recommended": self.process_tuning_recommendation,
            "numerical_modeled": self.process_numerical_modeling,
            "ab_test_designed": self.process_ab_test_design,
        }
        return handlers.get(event_type)

    # ── 核心逻辑: Numerical Designer 输出 → Data Analyst 输入 ───

    def process_tuning_recommendation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 tuning_recommended 事件 → 调用 data_analyst.detect_anomalies.

        反向协同核心: Numerical 调优建议 → Data Analyst 重新检测异常
        目的: 验证调优建议是否解决了已识别的指标偏差

        数据转换: TuningRecommendation → BehaviorData → AnomalyAlert 列表
        """
        game_id = payload.get("game_id", "unknown")
        behavior_data = self._tuning_to_behavior_data(payload)

        result = self._call_data_analyst(
            "detect_anomalies", game_id, behavior_data,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="tuning_recommended",
            trigger_source="numerical",
            target_method="detect_anomalies",
            target_agent="data_analyst",
            game_id=game_id,
            input_summary={
                "tuning_target_metric": payload.get("target_metric"),
                "tuning_parameter": payload.get("parameter"),
                "tuning_adjustment_pct": payload.get("adjustment_pct"),
                "tuning_priority": payload.get("priority"),
            },
            output=result,
            output_key="anomaly_alerts",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    def process_numerical_modeling(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 numerical_modeled 事件 → 调用 data_analyst.predict_retention.

        反向协同: Numerical 完成 LTV/CAC 建模 → Data Analyst 重新预测留存
        目的: 基于新的数值模型验证留存预测是否需要调整

        数据转换: NumericalModel → BehaviorData → RetentionPrediction
        """
        game_id = payload.get("game_id", "unknown")
        behavior_data = self._modeling_to_behavior_data(payload)

        result = self._call_data_analyst(
            "predict_retention", game_id, behavior_data,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="numerical_modeled",
            trigger_source="numerical",
            target_method="predict_retention",
            target_agent="data_analyst",
            game_id=game_id,
            input_summary={
                "model_ltv": payload.get("ltv"),
                "model_cac": payload.get("cac"),
                "model_roi": payload.get("roi"),
                "model_payback_days": payload.get("payback_days"),
            },
            output=result,
            output_key="retention_prediction",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    def process_ab_test_design(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 ab_test_designed 事件 → 调用 data_analyst.analyze_behavior.

        反向协同: Numerical 设计 A/B 测试 → Data Analyst 建立行为基线
        目的: 在 A/B 测试前建立行为基线, 用于后续效果对比

        数据转换: ABTestDesign → BehaviorData → BehaviorReport
        """
        game_id = payload.get("game_id", "unknown")
        behavior_data = self._ab_test_to_behavior_data(payload)

        result = self._call_data_analyst(
            "analyze_behavior", game_id, behavior_data,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="ab_test_designed",
            trigger_source="numerical",
            target_method="analyze_behavior",
            target_agent="data_analyst",
            game_id=game_id,
            input_summary={
                "test_id": payload.get("test_id"),
                "hypothesis": payload.get("hypothesis"),
                "target_metric": payload.get("target_metric"),
                "variants": payload.get("variants"),
            },
            output=result,
            output_key="behavior_baseline",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    # ── 反向闭环: 调优 → 重新分析 → 验证 ─────────────────────

    def run_reverse_closed_loop(
        self,
        game_id: str,
        tuning_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行反向闭环: 调优建议 → 异常检测 → 留存预测 → 行为基线.

        模拟 Numerical Designer 发布调优建议后, Data Analyst 完整的重新分析流程:
          Step 1: detect_anomalies (验证调优是否解决异常)
          Step 2: predict_retention (基于调优重新预测留存)
          Step 3: analyze_behavior (建立调优后行为基线)

        Args:
            game_id: 游戏 ID
            tuning_payload: 调优建议 payload (含 target_metric, parameter, adjustment_pct 等)

        Returns:
            闭环汇总: loop_id, game_id, steps, collaboration_count
        """
        loop_id = f"reverse-loop-{game_id}-{uuid.uuid4().hex[:8]}"
        steps: list[dict[str, Any]] = []

        # Step 1: 调优建议 → 异常检测
        logger.info("NumericalDataBridge: reverse loop step 1 - detect_anomalies (game=%s)", game_id)
        step1 = self.process_tuning_recommendation(tuning_payload)
        steps.append({"step": 1, "method": "detect_anomalies", "record": step1})

        # Step 2: 基于调优目标构建数值模型 payload → 留存预测
        logger.info("NumericalDataBridge: reverse loop step 2 - predict_retention (game=%s)", game_id)
        modeling_payload = self._build_modeling_payload_from_tuning(tuning_payload, game_id)
        step2 = self.process_numerical_modeling(modeling_payload)
        steps.append({"step": 2, "method": "predict_retention", "record": step2})

        # Step 3: 构建 A/B 测试 payload → 行为基线
        logger.info("NumericalDataBridge: reverse loop step 3 - analyze_behavior (game=%s)", game_id)
        ab_test_payload = self._build_ab_test_payload_from_tuning(tuning_payload, game_id)
        step3 = self.process_ab_test_design(ab_test_payload)
        steps.append({"step": 3, "method": "analyze_behavior", "record": step3})

        # 闭环审计记录
        audit_record = {
            "audit_type": "reverse_closed_loop",
            "loop_id": loop_id,
            "game_id": game_id,
            "collaboration_count": len(steps),
            "steps_summary": [
                {
                    "step": s["step"],
                    "method": s["method"],
                    "status": s["record"].get("status"),
                    "collaboration_id": s["record"].get("collaboration_id"),
                }
                for s in steps
            ],
            "created_at": _now_iso(),
        }
        self._persist_audit(audit_record)

        return {
            "loop_id": loop_id,
            "game_id": game_id,
            "direction": "numerical_to_data_analyst",
            "collaboration_count": len(steps),
            "steps": steps,
            "audit_record": audit_record,
        }

    # ── 数据转换: Numerical 输出 → BehaviorData 输入 ──────────

    def _tuning_to_behavior_data(self, payload: dict[str, Any]) -> Any:
        """将调优建议转换为 BehaviorData (用于 detect_anomalies).

        策略: 从调优建议中提取 current_value 和 target_value,
        构建模拟 BehaviorData 用于异常检测.
        """
        from .data_analyst_agent import BehaviorData

        # 从调优 payload 提取关键指标
        current_value = payload.get("current_value", 0.0)
        target_metric = payload.get("target_metric", "")

        # 根据 target_metric 反向映射到 BehaviorData 字段
        # retention_d1: 调优目标是留存 → 保留当前留存值
        # arpu: 调优目标是 ARPU → 保留当前 ARPU
        # first_pay_rate: 调优目标是首充率 → 保留当前付费率
        # payback_days: 调优目标是回本周期 → 保留当前回本天数

        # 使用调优建议中的值构建 BehaviorData (其他字段用默认值)
        return BehaviorData(
            game_id=payload.get("game_id", "unknown"),
            genre=payload.get("genre", "Merge"),
            dau=payload.get("dau", 10000),
            mau=payload.get("mau", 80000),
            retention_d1=current_value if target_metric == "retention_d1" else 0.42,
            retention_d7=payload.get("retention_d7", 0.18),
            retention_d30=payload.get("retention_d30", 0.10),
            revenue_total=payload.get("revenue_total", 5000.0),
            payer_count=payload.get("payer_count", 600),
        )

    def _modeling_to_behavior_data(self, payload: dict[str, Any]) -> Any:
        """将数值模型转换为 BehaviorData (用于 predict_retention)."""
        from .data_analyst_agent import BehaviorData

        return BehaviorData(
            game_id=payload.get("game_id", "unknown"),
            genre=payload.get("genre", "Merge"),
            dau=payload.get("dau", 10000),
            mau=payload.get("mau", 80000),
            retention_d1=payload.get("retention_d1", 0.42),
            retention_d7=payload.get("retention_d7", 0.18),
            retention_d30=payload.get("retention_d30", 0.10),
            revenue_total=payload.get("revenue_total", 5000.0),
            payer_count=payload.get("payer_count", 600),
        )

    def _ab_test_to_behavior_data(self, payload: dict[str, Any]) -> Any:
        """将 A/B 测试设计转换为 BehaviorData (用于 analyze_behavior)."""
        from .data_analyst_agent import BehaviorData

        return BehaviorData(
            game_id=payload.get("game_id", "unknown"),
            genre=payload.get("genre", "Merge"),
            dau=payload.get("dau", 10000),
            mau=payload.get("mau", 80000),
            retention_d1=payload.get("retention_d1", 0.42),
            retention_d7=payload.get("retention_d7", 0.18),
            retention_d30=payload.get("retention_d30", 0.10),
            revenue_total=payload.get("revenue_total", 5000.0),
            payer_count=payload.get("payer_count", 600),
        )

    def _build_modeling_payload_from_tuning(
        self, tuning_payload: dict[str, Any], game_id: str
    ) -> dict[str, Any]:
        """从调优建议构建数值模型 payload (用于 step 2)."""
        return {
            "game_id": game_id,
            "genre": tuning_payload.get("genre", "Merge"),
            "ltv": tuning_payload.get("target_value", 0.0),
            "cac": tuning_payload.get("cac", 5.0),
            "roi": tuning_payload.get("roi", 1.5),
            "payback_days": tuning_payload.get("payback_days", 30),
            "dau": tuning_payload.get("dau", 10000),
            "mau": tuning_payload.get("mau", 80000),
            "retention_d1": tuning_payload.get("current_value", 0.42),
            "retention_d7": tuning_payload.get("retention_d7", 0.18),
            "retention_d30": tuning_payload.get("retention_d30", 0.10),
            "revenue_total": tuning_payload.get("revenue_total", 5000.0),
            "payer_count": tuning_payload.get("payer_count", 600),
        }

    def _build_ab_test_payload_from_tuning(
        self, tuning_payload: dict[str, Any], game_id: str
    ) -> dict[str, Any]:
        """从调优建议构建 A/B 测试 payload (用于 step 3)."""
        return {
            "game_id": game_id,
            "genre": tuning_payload.get("genre", "Merge"),
            "test_id": f"test-{game_id}-{uuid.uuid4().hex[:8]}",
            "hypothesis": f"调优 {tuning_payload.get('parameter', 'unknown')} 改善 {tuning_payload.get('target_metric', 'unknown')}",
            "target_metric": tuning_payload.get("target_metric", "retention_d1"),
            "variants": ["control", "treatment"],
            "dau": tuning_payload.get("dau", 10000),
            "mau": tuning_payload.get("mau", 80000),
            "retention_d1": tuning_payload.get("current_value", 0.42),
            "retention_d7": tuning_payload.get("retention_d7", 0.18),
            "retention_d30": tuning_payload.get("retention_d30", 0.10),
            "revenue_total": tuning_payload.get("revenue_total", 5000.0),
            "payer_count": tuning_payload.get("payer_count", 600),
        }

    # ── 调用封装 ─────────────────────────────────────────────

    def _call_data_analyst(
        self, method_name: str, game_id: str, *args
    ) -> dict[str, Any] | list | None:
        """安全调用 Data Analyst Agent 方法.

        Returns:
            方法返回值的 dict/list 形式; None=agent 未注入或调用失败
        """
        if self._data_analyst_agent is None:
            logger.debug("NumericalDataBridge: data_analyst_agent not injected, skip %s", method_name)
            return None
        method = getattr(self._data_analyst_agent, method_name, None)
        if method is None:
            logger.warning("NumericalDataBridge: data_analyst has no method %s", method_name)
            return None
        try:
            result = method(game_id, *args)
            # 转换 dataclass → dict (支持单个对象和列表)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            if isinstance(result, list):
                return [item.to_dict() if hasattr(item, "to_dict") else item for item in result]
            return result
        except Exception as exc:
            logger.warning(
                "NumericalDataBridge: data_analyst.%s failed: %s",
                method_name, exc,
            )
            return None

    # ── 协同记录构建与持久化 ──────────────────────────────────

    def _extract_output_id(self, record: dict[str, Any]) -> str:
        """从协同记录中提取输出 ID (用于审计)."""
        output = record.get("analyst_output", {})
        output_key = record.get("output_key", "")
        target = output.get(output_key)

        if target is None:
            return ""
        if isinstance(target, list):
            if not target:
                return ""
            first = target[0]
            return (
                first.get("alert_id")
                or first.get("report_id")
                or first.get("prediction_id")
                or ""
                if isinstance(first, dict)
                else ""
            )
        if isinstance(target, dict):
            return (
                target.get("alert_id")
                or target.get("report_id")
                or target.get("prediction_id")
                or ""
            )
        return ""

    def _build_collaboration_record(
        self,
        trigger_event: str,
        trigger_source: str,
        target_method: str,
        target_agent: str,
        game_id: str,
        input_summary: dict[str, Any],
        output: dict[str, Any] | list | None,
        output_key: str,
    ) -> dict[str, Any]:
        """构建反向协同记录."""
        collaboration_id = f"rev-colab-{uuid.uuid4().hex[:12]}"
        record = {
            "collaboration_id": collaboration_id,
            "direction": "numerical_to_data_analyst",
            "trigger_event": trigger_event,
            "trigger_source": trigger_source,
            "target_method": target_method,
            "target_agent": target_agent,
            "game_id": game_id,
            "input_summary": input_summary,
            "analyst_output": {output_key: output} if output is not None else {},
            "output_key": output_key,
            "status": "success" if output is not None else "skipped_no_agent",
            "created_at": _now_iso(),
        }
        return record

    def _persist(self, record: dict[str, Any]) -> None:
        """追加写入协同记录到 JSONL."""
        self._collaboration_path.parent.mkdir(parents=True, exist_ok=True)
        with self._collaboration_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _persist_audit(self, record: dict[str, Any]) -> None:
        """追加写入审计日志到 JSONL."""
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write_ceo_memory(self, record: dict[str, Any]) -> None:
        """将反向协同结果回流到 CEO Memory."""
        ceo_memory_path = self.data_dir / "ceo" / "execution_memory.jsonl"
        ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_record = {
            "execution_id": record["collaboration_id"],
            "action_id": f"reverse_cross_agent_{record['target_method']}",
            "decision_id": record["game_id"],
            "game_id": record["game_id"],
            "strategy_type": "reverse_cross_agent_collaboration",
            "domain": "numerical_data_bridge",
            "action_type": record["target_method"],
            "status": record["status"],
            "success": record["status"] == "success",
            "real_api_called": False,
            "rolled_back": False,
            "detail": (
                f"Numerical {record['trigger_event']} → "
                f"Data Analyst {record['target_method']} "
                f"(game={record['game_id']}, status={record['status']})"
            ),
            "created_at": record["created_at"],
        }
        with ceo_memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(memory_record, ensure_ascii=False) + "\n")

    # ── 查询 API ─────────────────────────────────────────────

    def list_collaborations(
        self, game_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """查询反向协同记录列表."""
        if not self._collaboration_path.exists():
            return []
        try:
            text = self._collaboration_path.read_text(encoding="utf-8")
        except OSError:
            return []
        lines = [l for l in text.splitlines() if l.strip()]
        records = []
        for line in lines[-limit:]:
            try:
                rec = json.loads(line)
                if game_id is None or rec.get("game_id") == game_id:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
        return records

    def get_collaboration(self, collaboration_id: str) -> dict[str, Any] | None:
        """查询单条反向协同记录."""
        if not self._collaboration_path.exists():
            return None
        try:
            text = self._collaboration_path.read_text(encoding="utf-8")
        except OSError:
            return None
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if rec.get("collaboration_id") == collaboration_id:
                    return rec
            except json.JSONDecodeError:
                continue
        return None

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询反向闭环审计日志."""
        if not self._audit_path.exists():
            return []
        try:
            text = self._audit_path.read_text(encoding="utf-8")
        except OSError:
            return []
        lines = [l for l in text.splitlines() if l.strip()]
        records = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def get_stats(self) -> dict[str, Any]:
        """反向协同统计."""
        collaborations = self.list_collaborations(limit=10000)
        audit_logs = self.list_audit_logs(limit=10000)

        # 按事件类型统计
        event_counts: dict[str, int] = {}
        method_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for rec in collaborations:
            event = rec.get("trigger_event", "unknown")
            method = rec.get("target_method", "unknown")
            status = rec.get("status", "unknown")
            event_counts[event] = event_counts.get(event, 0) + 1
            method_counts[method] = method_counts.get(method, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1

        reverse_loops = [a for a in audit_logs if a.get("audit_type") == "reverse_closed_loop"]

        return {
            "direction": "numerical_to_data_analyst",
            "total_collaborations": len(collaborations),
            "total_reverse_loops": len(reverse_loops),
            "event_type_counts": event_counts,
            "method_counts": method_counts,
            "status_counts": status_counts,
            "last_collaboration_at": collaborations[-1]["created_at"] if collaborations else None,
            "last_loop_at": reverse_loops[-1]["created_at"] if reverse_loops else None,
        }
