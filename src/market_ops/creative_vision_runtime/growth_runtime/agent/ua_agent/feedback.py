"""E14.3.1 Feedback — 动作执行结果反馈采集.

UA Agent 执行动作后，从 Real World (Meta Ads, Adjust, MAX) 读取反馈数据，
形成 Action Outcome 记录，驱动后续的评估和学习循环。

核心循环:
  Decision → Execution → Observation → Feedback → Evaluation → Learning → Decision

输入: 执行前指标 (before_metrics) + 执行后指标 (after_metrics) + 观察周期
输出: UAActionOutcome (delta, reward, success)

设计原则:
  - 反馈数据来自真实广告平台 (Meta/Google/Adjust/MAX)
  - 观察周期可配置 (24h/48h/72h/7d)
  - 增量计算所有关键指标
  - 所有反馈可追溯
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .analyzer import UAMetrics


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class UAActionOutcome:
    """动作执行结果 — 连接执行与反馈.

    Attributes:
        outcome_id: 结果 ID
        action_id: 关联的动作 ID
        action_type: 动作类型
        target: 目标实体
        success: 是否成功
        before_metrics: 执行前指标
        after_metrics: 执行后指标
        spend_delta: 花费变化
        revenue_delta: 收入变化
        roas_delta: ROAS 变化
        ltv_delta: LTV 变化
        cpi_delta: CPI 变化
        ctr_delta: CTR 变化
        cvr_delta: CVR 变化
        payer_rate_delta: 付费率变化
        d7_retention_delta: D7 留存变化
        reward: 奖励值 (-1 ~ 1)
        observation_period_hours: 观察周期 (小时)
        confidence_adjustment: 置信度调整量
        learning: 学习总结
        observed_at: 观察时间
        metadata: 扩展元数据
    """
    outcome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: str = ""
    target: str = ""
    success: bool = False
    before_metrics: dict[str, Any] = field(default_factory=dict)
    after_metrics: dict[str, Any] = field(default_factory=dict)
    spend_delta: float = 0.0
    revenue_delta: float = 0.0
    roas_delta: float = 0.0
    ltv_delta: float = 0.0
    cpi_delta: float = 0.0
    ctr_delta: float = 0.0
    cvr_delta: float = 0.0
    payer_rate_delta: float = 0.0
    d7_retention_delta: float = 0.0
    reward: float = 0.0
    observation_period_hours: int = 24
    confidence_adjustment: float = 0.0
    learning: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "success": self.success,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "spend_delta": round(self.spend_delta, 4),
            "revenue_delta": round(self.revenue_delta, 4),
            "roas_delta": round(self.roas_delta, 4),
            "ltv_delta": round(self.ltv_delta, 4),
            "cpi_delta": round(self.cpi_delta, 4),
            "ctr_delta": round(self.ctr_delta, 4),
            "cvr_delta": round(self.cvr_delta, 4),
            "payer_rate_delta": round(self.payer_rate_delta, 4),
            "d7_retention_delta": round(self.d7_retention_delta, 4),
            "reward": round(self.reward, 4),
            "observation_period_hours": self.observation_period_hours,
            "confidence_adjustment": round(self.confidence_adjustment, 4),
            "learning": self.learning,
            "observed_at": self.observed_at,
            "metadata": self.metadata,
        }

    @property
    def is_positive(self) -> bool:
        """是否正向结果 (reward > 0)."""
        return self.reward > 0

    @property
    def is_strong_positive(self) -> bool:
        """是否强正向结果 (reward >= 0.5)."""
        return self.reward >= 0.5

    @property
    def is_negative(self) -> bool:
        """是否负向结果 (reward < 0)."""
        return self.reward < 0

    @property
    def summary(self) -> str:
        """生成结果摘要."""
        parts = [f"[{'✓' if self.success else '✗'}] {self.action_type}"]
        if self.roas_delta != 0:
            parts.append(f"ROAS {self.roas_delta:+.1%}")
        if self.ltv_delta != 0:
            parts.append(f"LTV {self.ltv_delta:+.1%}")
        parts.append(f"reward={self.reward:+.3f}")
        return " | ".join(parts)


@dataclass
class FeedbackBatch:
    """批量反馈结果.

    Attributes:
        batch_id: 批次 ID
        outcomes: 结果列表
        total_reward: 总奖励
        success_rate: 成功率
        created_at: 创建时间
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcomes: list[UAActionOutcome] = field(default_factory=list)
    total_reward: float = 0.0
    success_rate: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def outcome_count(self) -> int:
        return len(self.outcomes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "total_reward": round(self.total_reward, 4),
            "success_rate": round(self.success_rate, 4),
            "outcome_count": self.outcome_count,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Delta Computer
# ═══════════════════════════════════════════════════════════════

# 可跟踪的指标键列表
_TRACKED_METRICS = [
    ("spend", "spend_delta"),
    ("revenue", "revenue_delta"),
    ("roas", "roas_delta"),
    ("ltv", "ltv_delta"),
    ("cpi", "cpi_delta"),
    ("ctr", "ctr_delta"),
    ("cvr", "cvr_delta"),
    ("payer_rate", "payer_rate_delta"),
    ("d7_retention", "d7_retention_delta"),
]


def _compute_delta(before: float, after: float) -> float:
    """计算相对变化量."""
    if before == 0:
        return after if after != 0 else 0.0
    return (after - before) / before


def _safe_get(data: dict[str, Any], key: str, default: float = 0.0) -> float:
    """安全获取数值."""
    val = data.get(key, default)
    if val is None:
        return default
    return float(val)


# ═══════════════════════════════════════════════════════════════
# Feedback Collector
# ═══════════════════════════════════════════════════════════════


class FeedbackCollector:
    """反馈采集器 — 从 Real World 数据中提取动作结果.

    职责:
      1. 接收执行前/后指标
      2. 计算各维度增量
      3. 生成 UAActionOutcome

    用法:
        collector = FeedbackCollector()
        outcome = collector.collect(
            action_id="act_001",
            action_type="generate_variants",
            before_metrics={"roas": 1.3, "ltv": 4.5, "spend": 10000},
            after_metrics={"roas": 1.6, "ltv": 5.2, "spend": 10500},
            observation_hours=24,
        )
    """

    def collect(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        observation_hours: int = 24,
        metadata: dict[str, Any] | None = None,
    ) -> UAActionOutcome:
        """采集单个动作的结果.

        Args:
            action_id: 动作 ID
            action_type: 动作类型
            target: 目标实体
            before_metrics: 执行前指标
            after_metrics: 执行后指标
            observation_hours: 观察周期 (小时)
            metadata: 扩展元数据

        Returns:
            UAActionOutcome: 动作结果
        """
        outcome = UAActionOutcome(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=dict(before_metrics),
            after_metrics=dict(after_metrics),
            observation_period_hours=observation_hours,
            metadata=metadata or {},
        )

        # 计算每个指标的增量
        for metric_key, delta_attr in _TRACKED_METRICS:
            before_val = _safe_get(before_metrics, metric_key)
            after_val = _safe_get(after_metrics, metric_key)
            delta = _compute_delta(before_val, after_val)
            setattr(outcome, delta_attr, delta)

        return outcome

    def collect_from_metrics(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before: UAMetrics,
        after: UAMetrics,
        observation_hours: int = 24,
        metadata: dict[str, Any] | None = None,
    ) -> UAActionOutcome:
        """从 UAMetrics 对象采集结果.

        Args:
            action_id: 动作 ID
            action_type: 动作类型
            target: 目标实体
            before: 执行前指标
            after: 执行后指标
            observation_hours: 观察周期
            metadata: 扩展元数据

        Returns:
            UAActionOutcome
        """
        return self.collect(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=before.to_dict(),
            after_metrics=after.to_dict(),
            observation_hours=observation_hours,
            metadata=metadata,
        )

    def collect_batch(
        self,
        actions: list[dict[str, Any]],
        metrics_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
        observation_hours: int = 24,
    ) -> FeedbackBatch:
        """批量采集反馈.

        Args:
            actions: 动作信息列表 [{"action_id": ..., "action_type": ..., "target": ...}]
            metrics_pairs: 前后指标对 [(before, after), ...]
            observation_hours: 观察周期

        Returns:
            FeedbackBatch
        """
        outcomes = []
        for action, (before, after) in zip(actions, metrics_pairs):
            outcome = self.collect(
                action_id=action.get("action_id", ""),
                action_type=action.get("action_type", ""),
                target=action.get("target", ""),
                before_metrics=before,
                after_metrics=after,
                observation_hours=observation_hours,
                metadata=action.get("metadata", {}),
            )
            outcomes.append(outcome)

        total_reward = sum(o.reward for o in outcomes)
        success_count = sum(1 for o in outcomes if o.success)
        success_rate = success_count / len(outcomes) if outcomes else 0.0

        return FeedbackBatch(
            outcomes=outcomes,
            total_reward=total_reward,
            success_rate=success_rate,
        )

    def collect_from_resolutions(
        self,
        resolutions: list[dict[str, Any]],
    ) -> FeedbackBatch:
        """从决策结果记录中采集反馈.

        用于从 UAMemory 的 resolve_batch 结果中提取反馈.

        Args:
            resolutions: 决策结果列表，每个包含:
                - record_id, action_id, action_type, target
                - before_metrics, after_metrics

        Returns:
            FeedbackBatch
        """
        actions = []
        metrics_pairs = []
        for r in resolutions:
            actions.append({
                "action_id": r.get("action_id", r.get("record_id", "")),
                "action_type": r.get("action_type", ""),
                "target": r.get("target", ""),
                "metadata": r.get("metadata", {}),
            })
            metrics_pairs.append((
                r.get("before_metrics", {}),
                r.get("after_metrics", {}),
            ))
        return self.collect_batch(actions, metrics_pairs)

    # ── 查询 ──────────────────────────────────────────────────

    def get_delta_summary(self, outcome: UAActionOutcome) -> dict[str, float]:
        """获取 delta 摘要."""
        return {
            "spend_delta": outcome.spend_delta,
            "revenue_delta": outcome.revenue_delta,
            "roas_delta": outcome.roas_delta,
            "ltv_delta": outcome.ltv_delta,
            "cpi_delta": outcome.cpi_delta,
            "ctr_delta": outcome.ctr_delta,
            "cvr_delta": outcome.cvr_delta,
            "payer_rate_delta": outcome.payer_rate_delta,
            "d7_retention_delta": outcome.d7_retention_delta,
        }

    def get_delta_summary_batch(self, batch: FeedbackBatch) -> dict[str, float]:
        """获取批量 delta 均值摘要."""
        if not batch.outcomes:
            return {}
        n = len(batch.outcomes)
        summary: dict[str, float] = {}
        for key in ["spend_delta", "revenue_delta", "roas_delta", "ltv_delta",
                     "cpi_delta", "ctr_delta", "cvr_delta",
                     "payer_rate_delta", "d7_retention_delta"]:
            total = sum(getattr(o, key, 0) for o in batch.outcomes)
            summary[key] = total / n
        return summary


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_feedback_collector() -> FeedbackCollector:
    """创建默认反馈采集器."""
    return FeedbackCollector()