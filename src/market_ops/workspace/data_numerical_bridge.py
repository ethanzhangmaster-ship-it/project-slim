"""Data Analyst → Numerical Designer 桥接层 — 订阅行为分析自动触发数值建模.

协同方向: Data Analyst (behavior/funnel/retention/anomaly broadcast) → Numerical Designer (LTV/CAC/留存/调优)

设计原则:
  - 不修改现有 DataAnalystAgent 或 NumericalDesignerAgent (避免破坏已有逻辑)
  - 独立桥接层: 订阅 MessageBus → 转换数据 → 调用 Numerical 方法 → JSONL 持久化
  - 分析闭环: 行为洞察 → 数值建模 → 调优建议 → CEO Memory 回流

触发策略 (按事件类型):
  - behavior_analyzed:       → model_numerical (LTV/CAC 建模)
  - retention_predicted:     → model_retention (留存曲线建模)
  - players_segmented:       → analyze_pay_conversion (付费转化分析)
  - anomalies_detected:      → recommend_tuning (数值调优建议)
  - anomalies_detected (critical): → design_ab_test (A/B 测试方案)

数据转换: BehaviorData → GameMetrics
  - arpu = revenue_total / dau
  - arppu = revenue_total / max(payer_count, 1)
  - payer_rate = payer_count / dau
  - total_users = mau
  - spend = revenue_total * 0.6 (估算)

用法:
    bridge = DataNumericalBridge(
        data_dir="data",
        message_bus=bus,
        numerical_agent=numerical_agent,
    )
    bridge.register()  # 注册到 MessageBus, 自动消费 data_analyst 事件

    # 也可直接调用 (测试或不依赖 MessageBus 的场景)
    result = bridge.process_behavior_analysis(analysis_payload)
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


class DataNumericalBridge:
    """Data Analyst → Numerical Designer 桥接层 — 消费行为分析触发数值建模.

    职责:
      1. 注册到 MessageBus, 订阅 Data Analyst BROADCAST 消息
      2. 过滤 subject 前缀 == "data_analyst:" 的事件
      3. 按事件类型转换数据并调用 Numerical Designer 对应方法
      4. 协同结果写入 data/collaboration/data_numerical.jsonl (append-only)
      5. 审计日志写入 data/collaboration/data_numerical_audit.jsonl

    不职责:
      - 不修改 DataAnalystAgent 或 NumericalDesignerAgent 的代码
      - 不替代 GrowthLoop 的主决策链
      - 不直接执行 Meta Ads 操作
    """

    def __init__(
        self,
        data_dir: str = "data",
        message_bus: Any = None,
        agent_identity: Any = None,
        numerical_agent: Any = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._message_bus = message_bus
        self._agent_identity = agent_identity
        self._numerical_agent = numerical_agent
        self._collaboration_path = self.data_dir / "collaboration" / "data_numerical.jsonl"
        self._audit_path = self.data_dir / "collaboration" / "data_numerical_audit.jsonl"
        self._registered = False

    # ── MessageBus 订阅 ──────────────────────────────────────

    def register(self) -> bool:
        """注册到 MessageBus, 订阅 Data Analyst BROADCAST 消息.

        Returns:
            True=注册成功; False=未注入 message_bus 或注册失败
        """
        if self._message_bus is None:
            logger.warning("DataNumericalBridge: message_bus not injected, skip register")
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
                "DataNumericalBridge: registered to MessageBus (agent_id=%s)",
                self._agent_id(),
            )
            return True
        except Exception as exc:
            logger.warning("DataNumericalBridge: register failed: %s", exc)
            return False

    def _agent_id(self) -> str:
        """获取 Numerical Agent ID (用于 MessageBus 注册)."""
        if self._agent_identity is not None:
            return getattr(self._agent_identity, "agent_id", "numerical_agent")
        return "numerical_bridge"

    def _handle_message(self, message: Any) -> Any:
        """MessageBus handler — 过滤 data_analyst 事件并路由处理."""
        subject = getattr(message, "subject", "")
        if not subject.startswith("data_analyst:"):
            return None

        event_type = subject.replace("data_analyst:", "")
        body = getattr(message, "body", {}) or {}

        try:
            handler = self._get_event_handler(event_type)
            if handler is not None:
                handler(body)
            else:
                logger.debug("DataNumericalBridge: no handler for event_type=%s", event_type)
        except Exception as exc:
            logger.warning(
                "DataNumericalBridge: handle %s failed: %s",
                event_type, exc,
            )
        return None

    def _get_event_handler(self, event_type: str):
        """按事件类型路由到对应处理方法."""
        handlers = {
            "behavior_analyzed": self.process_behavior_analysis,
            "retention_predicted": self.process_retention_prediction,
            "players_segmented": self.process_player_segmentation,
            "anomalies_detected": self.process_anomaly_alerts,
        }
        return handlers.get(event_type)

    # ── 核心逻辑: Data Analyst 输出 → Numerical Designer 输入 ───

    def process_behavior_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 behavior_analyzed 事件 → 调用 numerical.model_numerical.

        数据转换: BehaviorReport → GameMetrics → NumericalModel
        """
        game_id = payload.get("game_id", "unknown")
        metrics = self._behavior_to_game_metrics(payload)

        result = self._call_numerical(
            "model_numerical", game_id, metrics,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="behavior_analyzed",
            trigger_source="data_analyst",
            target_method="model_numerical",
            target_agent="numerical",
            game_id=game_id,
            input_summary={
                "dau": metrics.get("dau"),
                "arpu": round(metrics.get("arpu", 0), 4),
                "arppu": round(metrics.get("arppu", 0), 2),
                "payer_rate": round(metrics.get("payer_rate", 0), 4),
            },
            output=result,
            output_key="numerical_model",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    def process_retention_prediction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 retention_predicted 事件 → 调用 numerical.model_retention.

        数据转换: RetentionPrediction → GameMetrics → RetentionCurveModel
        """
        game_id = payload.get("game_id", "unknown")
        metrics = self._behavior_to_game_metrics(payload)

        result = self._call_numerical(
            "model_retention", game_id, metrics,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="retention_predicted",
            trigger_source="data_analyst",
            target_method="model_retention",
            target_agent="numerical",
            game_id=game_id,
            input_summary={
                "historical_d1": payload.get("historical_d1"),
                "historical_d7": payload.get("historical_d7"),
                "historical_d30": payload.get("historical_d30"),
                "predicted_d60": payload.get("predicted_d60"),
                "predicted_d90": payload.get("predicted_d90"),
            },
            output=result,
            output_key="retention_curve",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    def process_player_segmentation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 players_segmented 事件 → 调用 numerical.analyze_pay_conversion.

        数据转换: PlayerSegmentation → GameMetrics → PayConversionFunnel
        """
        game_id = payload.get("game_id", "unknown")
        metrics = self._behavior_to_game_metrics(payload)

        result = self._call_numerical(
            "analyze_pay_conversion", game_id, metrics,
        )

        collaboration = self._build_collaboration_record(
            trigger_event="players_segmented",
            trigger_source="data_analyst",
            target_method="analyze_pay_conversion",
            target_agent="numerical",
            game_id=game_id,
            input_summary={
                "total_users": payload.get("total_users"),
                "segmentation_method": payload.get("segmentation_method"),
                "key_insight": payload.get("key_insight", "")[:80],
            },
            output=result,
            output_key="pay_conversion",
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    def process_anomaly_alerts(self, payload: dict[str, Any]) -> dict[str, Any]:
        """消费 anomalies_detected 事件 → 调用 numerical.recommend_tuning.

        当存在 critical 异常时, 额外触发 design_ab_test.
        """
        game_id = payload.get("game_id", "unknown")
        metrics = self._behavior_to_game_metrics(payload)

        tuning_result = self._call_numerical(
            "recommend_tuning", game_id, metrics,
        )

        # 检查是否有 critical 异常 → 触发 A/B 测试设计
        ab_test_result = None
        anomalies = payload.get("anomalies", [])
        has_critical = any(
            a.get("severity") == "critical" for a in anomalies
        ) if isinstance(anomalies, list) else False

        if has_critical:
            ab_test_result = self._call_numerical(
                "design_ab_test", game_id,
                f"修复异常指标: {[a.get('metric_name','') for a in anomalies if a.get('severity')=='critical']}",
                metrics,
                "retention_d7",
            )

        collaboration = self._build_collaboration_record(
            trigger_event="anomalies_detected",
            trigger_source="data_analyst",
            target_method="recommend_tuning" + ("+design_ab_test" if has_critical else ""),
            target_agent="numerical",
            game_id=game_id,
            input_summary={
                "anomaly_count": len(anomalies) if isinstance(anomalies, list) else 0,
                "has_critical": has_critical,
                "metrics": [a.get("metric_name", "") for a in anomalies[:3]] if isinstance(anomalies, list) else [],
            },
            output=tuning_result,
            output_key="tuning_recommendations",
            extra_output={"ab_test": ab_test_result} if ab_test_result else None,
        )
        self._persist(collaboration)
        self._write_ceo_memory(collaboration)
        return collaboration

    # ── 完整分析闭环: 一键触发 ─────────────────────────────────

    def run_analysis_closed_loop(
        self,
        game_id: str,
        behavior_data: dict[str, Any],
    ) -> dict[str, Any]:
        """完整分析闭环: Data Analyst 全套分析 → Numerical Designer 全套建模.

        这是端到端的协同方法, 不依赖 MessageBus, 直接顺序调用:
          1. behavior_analyzed → model_numerical
          2. retention_predicted → model_retention
          3. players_segmented → analyze_pay_conversion
          4. anomalies_detected → recommend_tuning (+design_ab_test if critical)

        Args:
            game_id: 游戏 ID
            behavior_data: BehaviorData dict (含 dau, mau, retention_d1/d7/d30,
                           revenue_total, payer_count, genre 等)

        Returns:
            闭环结果 dict (含 4 个协同记录 + 总结)
        """
        loop_id = f"loop-{game_id}-{uuid.uuid4().hex[:8]}"
        results: list[dict[str, Any]] = []

        # 1. 行为分析 → LTV/CAC 建模
        behavior_payload = {**behavior_data, "game_id": game_id}
        r1 = self.process_behavior_analysis(behavior_payload)
        results.append(r1)

        # 2. 留存预测 → 留存曲线建模
        retention_payload = {
            "game_id": game_id,
            "historical_d1": behavior_data.get("retention_d1", 0.42),
            "historical_d7": behavior_data.get("retention_d7", 0.18),
            "historical_d30": behavior_data.get("retention_d30", 0.10),
            "predicted_d60": behavior_data.get("predicted_d60", 0.07),
            "predicted_d90": behavior_data.get("predicted_d90", 0.05),
        }
        r2 = self.process_retention_prediction(retention_payload)
        results.append(r2)

        # 3. 玩家分群 → 付费转化分析
        segmentation_payload = {
            "game_id": game_id,
            "total_users": behavior_data.get("mau", 80000),
            "segmentation_method": "rfm",
            "key_insight": "行为数据驱动分群",
        }
        r3 = self.process_player_segmentation(segmentation_payload)
        results.append(r3)

        # 4. 异常检测 → 数值调优 (+A/B 测试)
        anomaly_payload = {
            "game_id": game_id,
            "anomalies": behavior_data.get("anomalies", []),
        }
        r4 = self.process_anomaly_alerts(anomaly_payload)
        results.append(r4)

        # 汇总闭环结果
        loop_summary = {
            "loop_id": loop_id,
            "game_id": game_id,
            "trigger_source": "data_analyst",
            "target_agent": "numerical",
            "collaboration_count": len(results),
            "steps": [
                {
                    "step": i + 1,
                    "trigger_event": r["trigger_event"],
                    "target_method": r["target_method"],
                    "status": r["status"],
                    "numerical_output_id": self._extract_output_id(r),
                }
                for i, r in enumerate(results)
            ],
            "created_at": _now_iso(),
        }

        self._persist_audit({
            "audit_type": "closed_loop",
            "loop_id": loop_id,
            "game_id": game_id,
            "collaboration_count": len(results),
            "created_at": loop_summary["created_at"],
        })

        return loop_summary

    # ── 数据转换: BehaviorData → GameMetrics ──────────────────

    def _behavior_to_game_metrics(self, payload: dict[str, Any]) -> dict[str, Any]:
        """将 Data Analyst 的行为数据转换为 Numerical Designer 的 GameMetrics.

        转换逻辑:
          - arpu = revenue_total / dau
          - arppu = revenue_total / max(payer_count, 1)
          - payer_rate = payer_count / max(dau, 1)
          - total_users = mau
          - spend = revenue_total * 0.6 (估算, UA 花费约占收入 60%)
          - first_pay_rate = payer_rate * 0.8 (估算)
        """
        dau = int(payload.get("dau", 10000))
        mau = int(payload.get("mau", dau * 8))
        revenue = float(payload.get("revenue_total", 5000.0))
        payer_count = int(payload.get("payer_count", 600))

        arpu = revenue / max(dau, 1)
        arppu = revenue / max(payer_count, 1)
        payer_rate = payer_count / max(dau, 1)
        first_pay_rate = payer_rate * 0.8

        return {
            "game_id": payload.get("game_id", "unknown"),
            "genre": payload.get("genre", "Merge"),
            "dau": dau,
            "total_users": mau,
            "revenue_total": revenue,
            "spend": revenue * 0.6,
            "arpu": round(arpu, 4),
            "arppu": round(arppu, 2),
            "retention_d1": float(payload.get("retention_d1", payload.get("historical_d1", 0.42))),
            "retention_d7": float(payload.get("retention_d7", payload.get("historical_d7", 0.18))),
            "retention_d30": float(payload.get("retention_d30", payload.get("historical_d30", 0.10))),
            "payer_rate": round(payer_rate, 4),
            "first_pay_rate": round(first_pay_rate, 4),
            "avg_first_pay_days": 3.5,
            "avg_first_pay_amount": 4.99,
        }

    # ── Numerical Agent 调用封装 ──────────────────────────────

    def _call_numerical(self, method_name: str, game_id: str, *args) -> dict[str, Any] | None:
        """调用 Numerical Designer Agent 的方法, 返回 to_dict() 结果."""
        if self._numerical_agent is None:
            logger.warning(
                "DataNumericalBridge: numerical_agent not injected, skip %s",
                method_name,
            )
            return None

        method = getattr(self._numerical_agent, method_name, None)
        if method is None:
            logger.warning(
                "DataNumericalBridge: numerical_agent has no method %s",
                method_name,
            )
            return None

        try:
            # GameMetrics 是 dataclass, 需要从 dict 构造
            if method_name in ("model_numerical", "model_retention", "analyze_pay_conversion"):
                from .numerical_designer_agent import GameMetrics
                metrics = GameMetrics(**args[0]) if isinstance(args[0], dict) else args[0]
                result = method(game_id, metrics)
            elif method_name == "recommend_tuning":
                from .numerical_designer_agent import GameMetrics
                metrics = GameMetrics(**args[0]) if isinstance(args[0], dict) else args[0]
                result = method(game_id, metrics)
            elif method_name == "design_ab_test":
                from .numerical_designer_agent import GameMetrics
                metrics = GameMetrics(**args[1]) if isinstance(args[1], dict) else args[1]
                result = method(game_id, args[0], metrics, args[2] if len(args) > 2 else "retention_d7")
            else:
                result = method(game_id, *args)

            # 统一转 dict
            if hasattr(result, "to_dict"):
                return result.to_dict()
            if isinstance(result, list):
                return [r.to_dict() if hasattr(r, "to_dict") else r for r in result]
            return result
        except Exception as exc:
            logger.warning(
                "DataNumericalBridge: numerical.%s failed: %s",
                method_name, exc,
            )
            return None

    # ── 协同记录构建与持久化 ──────────────────────────────────

    def _extract_output_id(self, record: dict[str, Any]) -> str:
        """从协同记录中提取 numerical_output 的唯一 ID.

        处理 dict 和 list 两种输出类型:
          - NumericalModel/RetentionCurve/PayConversion → dict (含 model_id/curve_id/funnel_id)
          - TuningRecommendation → list[dict] (取首个 recommendation_id)
        """
        output = record.get("numerical_output", {})
        output_key = record.get("output_key", "")
        target = output.get(output_key)

        if target is None:
            return ""
        if isinstance(target, list):
            # 列表输出: 取第一条记录的 ID
            if not target:
                return ""
            first = target[0]
            return (
                first.get("recommendation_id")
                or first.get("model_id")
                or first.get("test_id")
                or ""
                if isinstance(first, dict)
                else ""
            )
        if isinstance(target, dict):
            return (
                target.get("model_id")
                or target.get("curve_id")
                or target.get("funnel_id")
                or target.get("recommendation_id")
                or target.get("test_id")
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
        extra_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建协同记录."""
        collaboration_id = f"colab-{uuid.uuid4().hex[:12]}"
        record = {
            "collaboration_id": collaboration_id,
            "trigger_event": trigger_event,
            "trigger_source": trigger_source,
            "target_method": target_method,
            "target_agent": target_agent,
            "game_id": game_id,
            "input_summary": input_summary,
            "numerical_output": {output_key: output} if output is not None else {},
            "output_key": output_key,
            "status": "success" if output is not None else "skipped_no_agent",
            "created_at": _now_iso(),
        }
        if extra_output:
            record["numerical_output"].update(extra_output)
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
        """将协同结果回流到 CEO Memory."""
        ceo_memory_path = self.data_dir / "ceo" / "execution_memory.jsonl"
        ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_record = {
            "execution_id": record["collaboration_id"],
            "action_id": f"cross_agent_{record['target_method']}",
            "decision_id": record["game_id"],
            "game_id": record["game_id"],
            "strategy_type": "cross_agent_collaboration",
            "domain": "data_numerical_bridge",
            "action_type": record["target_method"],
            "status": record["status"],
            "success": record["status"] == "success",
            "real_api_called": False,
            "rolled_back": False,
            "detail": (
                f"Data Analyst {record['trigger_event']} → "
                f"Numerical {record['target_method']} "
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
        """查询协同记录列表."""
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
        """查询单条协同记录."""
        records = self.list_collaborations(limit=500)
        for rec in records:
            if rec.get("collaboration_id") == collaboration_id:
                return rec
        return None

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询审计日志."""
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
        """协同统计."""
        all_records = self.list_collaborations(limit=10000)
        by_trigger: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_game: dict[str, int] = {}
        for rec in all_records:
            trigger = rec.get("trigger_event", "unknown")
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1
            status = rec.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            game = rec.get("game_id", "unknown")
            by_game[game] = by_game.get(game, 0) + 1
        return {
            "total_collaborations": len(all_records),
            "by_trigger_event": by_trigger,
            "by_status": by_status,
            "by_game": by_game,
            "bridge_registered": self._registered,
        }
