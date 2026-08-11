"""E14.4.2.4 Creative Evaluator — 创意策略评估与反馈.

连接 E14.3.1 Feedback Loop，对创意策略执行结果进行评估:

  输入: CreativeStrategy + 执行前/后指标
  输出: CreativeStrategyOutcome (reward, success, learning)

核心能力:
  - 策略评估: 计算策略执行的 reward 和 success
  - 反馈学习: 更新 Creative Memory 中的经验
  - 策略迭代: 基于评估结果调整策略方向
  - 与 Feedback Loop 集成: 复用 E14.3.1 的 Reward 和 Confidence 机制

评估维度:
  - ROAS 变化: 执行前后 ROAS 比较
  - CTR 变化: 执行前后 CTR 比较
  - 疲劳度变化: 执行前后疲劳度比较
  - 综合 reward: ROAS * 0.5 + LTV * 0.3 - spend_risk * 0.2

设计原则:
  - 与 E14.3.1 Feedback Loop 兼容
  - 确定性评估，不依赖 AI
  - 评估结果可追溯
  - 支持批量评估
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .strategy import CreativeStrategy, CreativeStrategyType
from .opportunity import CreativeOpportunity, OpportunityPriority
from .memory import (
    CreativeMemory,
    CreativeDecisionOutcome,
    CreativeActionType,
    CreativeDecisionRecord,
)


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class StrategyOutcomeType(str, Enum):
    """策略结果类型."""
    SUCCESS = "success"          # 成功 — 达到预期
    PARTIAL = "partial"          # 部分成功 — 有改善但未达标
    FAILURE = "failure"          # 失败 — 未改善
    INCONCLUSIVE = "inconclusive" # 不确定 — 数据不足
    PENDING = "pending"          # 等待中


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeMetricsSnapshot:
    """创意指标快照.

    Attributes:
        creative_id: 创意 ID
        roas: ROAS
        ctr: 点击率
        cvr: 转化率
        fatigue: 疲劳度
        frequency: 频次
        spend: 花费
        revenue: 收入
        installs: 安装量
        payer_rate: 付费率
        ltv: D7 LTV
        timestamp: 时间
    """
    creative_id: str = ""
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    fatigue: float = 0.0
    frequency: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    installs: int = 0
    payer_rate: float = 0.0
    ltv: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeMetricsSnapshot:
        return cls(
            creative_id=data.get("creative_id", ""),
            roas=float(data.get("roas", 0)),
            ctr=float(data.get("ctr", 0)),
            cvr=float(data.get("cvr", 0)),
            fatigue=float(data.get("fatigue", 0)),
            frequency=float(data.get("frequency", 0)),
            spend=float(data.get("spend", 0)),
            revenue=float(data.get("revenue", 0)),
            installs=int(data.get("installs", 0)),
            payer_rate=float(data.get("payer_rate", 0)),
            ltv=float(data.get("ltv", 0)),
            timestamp=data.get("timestamp", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "fatigue": self.fatigue,
            "frequency": self.frequency,
            "spend": self.spend,
            "revenue": self.revenue,
            "installs": self.installs,
            "payer_rate": self.payer_rate,
            "ltv": self.ltv,
            "timestamp": self.timestamp,
        }


@dataclass
class StrategyEvaluation:
    """策略评估详情.

    Attributes:
        roas_change: ROAS 变化 (ratio)
        ctr_change: CTR 变化 (ratio)
        fatigue_change: 疲劳度变化 (绝对值)
        revenue_change: 收入变化 (ratio)
        payer_rate_change: 付费率变化
        ltv_change: LTV 变化
        reward: 综合奖励值
        confidence: 评估置信度
        sample_size: 样本量
        evaluation_details: 评估详情
    """
    roas_change: float = 0.0
    ctr_change: float = 0.0
    fatigue_change: float = 0.0
    revenue_change: float = 0.0
    payer_rate_change: float = 0.0
    ltv_change: float = 0.0
    reward: float = 0.0
    confidence: float = 0.0
    sample_size: int = 0
    evaluation_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "roas_change": round(self.roas_change, 4),
            "ctr_change": round(self.ctr_change, 4),
            "fatigue_change": round(self.fatigue_change, 4),
            "revenue_change": round(self.revenue_change, 4),
            "payer_rate_change": round(self.payer_rate_change, 4),
            "ltv_change": round(self.ltv_change, 4),
            "reward": round(self.reward, 4),
            "confidence": round(self.confidence, 4),
            "sample_size": self.sample_size,
            "evaluation_details": self.evaluation_details,
        }


@dataclass
class CreativeStrategyOutcome:
    """创意策略结果 — 完整的策略执行评估.

    Attributes:
        outcome_id: 结果 ID
        strategy_id: 关联策略 ID
        strategy_type: 策略类型
        creative_id: 创意 ID
        outcome_type: 结果类型
        before_metrics: 执行前指标
        after_metrics: 执行后指标
        evaluation: 评估详情
        reward: 奖励值
        success: 是否成功
        learning: 学习总结
        recommendation: 下一步建议
        created_at: 创建时间
        metadata: 扩展元数据
    """
    outcome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    strategy_type: CreativeStrategyType = CreativeStrategyType.UNKNOWN
    creative_id: str = ""
    outcome_type: StrategyOutcomeType = StrategyOutcomeType.PENDING
    before_metrics: CreativeMetricsSnapshot | None = None
    after_metrics: CreativeMetricsSnapshot | None = None
    evaluation: StrategyEvaluation | None = None
    reward: float = 0.0
    success: bool = False
    learning: str = ""
    recommendation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "creative_id": self.creative_id,
            "outcome_type": self.outcome_type.value,
            "before_metrics": self.before_metrics.to_dict() if self.before_metrics else None,
            "after_metrics": self.after_metrics.to_dict() if self.after_metrics else None,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "reward": self.reward,
            "success": self.success,
            "learning": self.learning,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def summary(self) -> str:
        status = "SUCCESS" if self.success else "FAILURE"
        parts = [f"[{status}] {self.strategy_type.value}"]
        if self.reward != 0:
            parts.append(f"reward={self.reward:.2f}")
        if self.learning:
            parts.append(self.learning)
        return " | ".join(parts)


@dataclass
class EvaluationReport:
    """评估报告 — 批量评估结果.

    Attributes:
        report_id: 报告 ID
        outcomes: 结果列表
        total_evaluated: 总评估数
        success_count: 成功数
        failure_count: 失败数
        avg_reward: 平均奖励
        best_strategy: 最佳策略类型
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcomes: list[CreativeStrategyOutcome] = field(default_factory=list)
    total_evaluated: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_reward: float = 0.0
    best_strategy: str = ""
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "total_evaluated": self.total_evaluated,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_reward": round(self.avg_reward, 4),
            "best_strategy": self.best_strategy,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def success_rate(self) -> float:
        if self.total_evaluated == 0:
            return 0.0
        return self.success_count / self.total_evaluated


# ═══════════════════════════════════════════════════════════════
# Metrics → ActionType Mapping
# ═══════════════════════════════════════════════════════════════

STRATEGY_TO_ACTION: dict[CreativeStrategyType, CreativeActionType] = {
    CreativeStrategyType.REFRESH_HOOK: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_VISUAL_STYLE: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_EMOTION: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.COPY_WINNER_DNA: CreativeActionType.CLONE_DNA,
    CreativeStrategyType.EXPLORE_NEW_DNA: CreativeActionType.MUTATE_DNA,
    CreativeStrategyType.OPTIMIZE_OPENING: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.SCALE_WINNER: CreativeActionType.SCALE_CREATIVE,
    CreativeStrategyType.EXPLORE_NEW_AUDIENCE: CreativeActionType.GENERATE_VARIANTS,
    CreativeStrategyType.TEST_NEW_CONCEPT: CreativeActionType.MUTATE_DNA,
    CreativeStrategyType.REFRESH_CREATIVE: CreativeActionType.REPLACE_CREATIVE,
}


# ═══════════════════════════════════════════════════════════════
# Creative Evaluator
# ═══════════════════════════════════════════════════════════════


class CreativeEvaluator:
    """创意评估器 — 连接 E14.3.1 Feedback Loop.

    职责:
      1. 策略评估: 计算策略执行的 reward 和 success
      2. 反馈学习: 更新 Creative Memory 中的经验
      3. 策略迭代: 基于评估结果调整策略方向
      4. 批量评估: 支持多策略同步评估

    评估公式:
      reward = ROAS_delta * 0.5 + LTV_delta * 0.3 - fatigue_delta * 0.2
      success = reward > 0.1 AND roas_improved

    用法:
        evaluator = CreativeEvaluator(memory=creative_memory)
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics)
    """

    def __init__(self, memory: CreativeMemory | None = None):
        self._memory = memory or CreativeMemory()
        self._outcomes: dict[str, CreativeStrategyOutcome] = {}
        self._history: list[CreativeStrategyOutcome] = []

    # ── 核心评估 ──────────────────────────────────────────────

    def evaluate(
        self,
        strategy: CreativeStrategy,
        before_metrics: CreativeMetricsSnapshot | dict[str, Any],
        after_metrics: CreativeMetricsSnapshot | dict[str, Any],
    ) -> CreativeStrategyOutcome:
        """评估策略执行结果.

        Args:
            strategy: 创意策略
            before_metrics: 执行前指标
            after_metrics: 执行后指标

        Returns:
            CreativeStrategyOutcome: 策略结果
        """
        if isinstance(before_metrics, dict):
            before_metrics = CreativeMetricsSnapshot.from_dict(before_metrics)
        if isinstance(after_metrics, dict):
            after_metrics = CreativeMetricsSnapshot.from_dict(after_metrics)

        # 1. 计算指标变化
        evaluation = self._calculate_evaluation(before_metrics, after_metrics)

        # 2. 计算 reward
        reward = self._calculate_reward(before_metrics, after_metrics)
        evaluation.reward = reward

        # 3. 判断成功
        success = self._determine_success(evaluation)
        outcome_type = self._determine_outcome_type(evaluation, success)

        # 4. 生成学习
        learning = self._generate_learning(strategy, evaluation, success)

        # 5. 生成建议
        recommendation = self._generate_recommendation(strategy, evaluation, success)

        outcome = CreativeStrategyOutcome(
            strategy_id=strategy.strategy_id,
            strategy_type=strategy.strategy_type,
            creative_id=strategy.target_creative_id,
            outcome_type=outcome_type,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            evaluation=evaluation,
            reward=reward,
            success=success,
            learning=learning,
            recommendation=recommendation,
        )

        # 6. 更新 Memory
        self._update_memory(strategy, outcome)

        self._outcomes[outcome.outcome_id] = outcome
        self._history.append(outcome)
        return outcome

    def evaluate_batch(
        self,
        strategy_metrics: list[tuple[CreativeStrategy, dict[str, Any], dict[str, Any]]],
    ) -> EvaluationReport:
        """批量评估.

        Args:
            strategy_metrics: [(strategy, before_metrics, after_metrics), ...]

        Returns:
            EvaluationReport: 评估报告
        """
        outcomes = []
        for strategy, before, after in strategy_metrics:
            outcome = self.evaluate(strategy, before, after)
            outcomes.append(outcome)

        successes = [o for o in outcomes if o.success]
        failures = [o for o in outcomes if not o.success and o.outcome_type != StrategyOutcomeType.PENDING]

        avg_reward = (
            sum(o.reward for o in outcomes) / len(outcomes)
            if outcomes else 0.0
        )

        # 最佳策略类型
        strategy_rewards: dict[str, list[float]] = {}
        for o in outcomes:
            t = o.strategy_type.value
            if t not in strategy_rewards:
                strategy_rewards[t] = []
            strategy_rewards[t].append(o.reward)
        best_strategy = ""
        best_avg = -float('inf')
        for stype, rewards in strategy_rewards.items():
            avg = sum(rewards) / len(rewards)
            if avg > best_avg:
                best_avg = avg
                best_strategy = stype

        summary_parts = []
        if successes:
            summary_parts.append(f"{len(successes)} 个成功策略")
        if failures:
            summary_parts.append(f"{len(failures)} 个失败策略")
        if best_strategy:
            summary_parts.append(f"最佳策略: {best_strategy}")

        return EvaluationReport(
            outcomes=outcomes,
            total_evaluated=len(outcomes),
            success_count=len(successes),
            failure_count=len(failures),
            avg_reward=avg_reward,
            best_strategy=best_strategy,
            summary=" | ".join(summary_parts) if summary_parts else "无评估结果",
        )

    # ── 内部计算 ──────────────────────────────────────────────

    def _calculate_evaluation(
        self,
        before: CreativeMetricsSnapshot,
        after: CreativeMetricsSnapshot,
    ) -> StrategyEvaluation:
        """计算指标变化."""
        details = []

        def safe_ratio(new_val: float, old_val: float) -> float:
            if old_val == 0:
                return 0.0
            return (new_val - old_val) / abs(old_val)

        def safe_diff(new_val: float, old_val: float) -> float:
            return new_val - old_val

        roas_change = safe_ratio(after.roas, before.roas)
        ctr_change = safe_ratio(after.ctr, before.ctr)
        fatigue_change = safe_diff(after.fatigue, before.fatigue)
        revenue_change = safe_ratio(after.revenue, before.revenue)
        payer_rate_change = safe_diff(after.payer_rate, before.payer_rate)
        ltv_change = safe_ratio(after.ltv, before.ltv)

        if after.roas > before.roas:
            details.append(f"ROAS 提升 {roas_change:.0%}")
        elif after.roas < before.roas:
            details.append(f"ROAS 下降 {roas_change:.0%}")

        if after.ctr > before.ctr:
            details.append(f"CTR 提升 {ctr_change:.0%}")
        elif after.ctr < before.ctr:
            details.append(f"CTR 下降 {ctr_change:.0%}")

        if fatigue_change < 0:
            details.append(f"疲劳度降低 {abs(fatigue_change):.0%}")
        elif fatigue_change > 0:
            details.append(f"疲劳度升高 {fatigue_change:.0%}")

        if after.payer_rate > before.payer_rate:
            details.append(f"付费率提升 {payer_rate_change:.1%}pp")

        if after.ltv > before.ltv:
            details.append(f"LTV 提升 {ltv_change:.0%}")

        confidence = 0.5
        if after.installs > 1000:
            confidence = 0.7
        if after.installs > 5000:
            confidence = 0.85
        if after.installs > 10000:
            confidence = 0.95

        return StrategyEvaluation(
            roas_change=roas_change,
            ctr_change=ctr_change,
            fatigue_change=fatigue_change,
            revenue_change=revenue_change,
            payer_rate_change=payer_rate_change,
            ltv_change=ltv_change,
            confidence=confidence,
            sample_size=after.installs,
            evaluation_details=details,
        )

    def _calculate_reward(
        self,
        before: CreativeMetricsSnapshot,
        after: CreativeMetricsSnapshot,
    ) -> float:
        """计算综合奖励.

        公式: ROAS_delta * 0.5 + LTV_delta * 0.3 - fatigue_delta * 0.2
        """
        def safe_ratio(new_val: float, old_val: float) -> float:
            if old_val == 0:
                return 0.0
            return (new_val - old_val) / abs(old_val)

        roas_delta = safe_ratio(after.roas, before.roas)
        ltv_delta = safe_ratio(after.ltv, before.ltv)
        fatigue_delta = after.fatigue - before.fatigue

        reward = roas_delta * 0.5 + ltv_delta * 0.3 - fatigue_delta * 0.2
        return round(reward, 4)

    def _determine_success(self, evaluation: StrategyEvaluation) -> bool:
        """判断策略是否成功."""
        # reward > 0.05 且 ROAS 有改善
        return evaluation.reward > 0.05 and evaluation.roas_change > 0

    def _determine_outcome_type(
        self,
        evaluation: StrategyEvaluation,
        success: bool,
    ) -> StrategyOutcomeType:
        """确定结果类型."""
        if success:
            if evaluation.reward > 0.3:
                return StrategyOutcomeType.SUCCESS
            return StrategyOutcomeType.PARTIAL
        if evaluation.sample_size < 500:
            return StrategyOutcomeType.INCONCLUSIVE
        return StrategyOutcomeType.FAILURE

    def _generate_learning(
        self,
        strategy: CreativeStrategy,
        evaluation: StrategyEvaluation,
        success: bool,
    ) -> str:
        """生成学习总结."""
        if success:
            if strategy.strategy_type == CreativeStrategyType.REFRESH_HOOK:
                return f"更换Hook策略有效，ROAS提升{evaluation.roas_change:.0%}"
            elif strategy.strategy_type == CreativeStrategyType.COPY_WINNER_DNA:
                return f"复制赢家DNA成功，ROAS提升{evaluation.roas_change:.0%}"
            elif strategy.strategy_type == CreativeStrategyType.CHANGE_VISUAL_STYLE:
                return f"视觉更新有效，CTR提升{evaluation.ctr_change:.0%}"
            elif strategy.strategy_type == CreativeStrategyType.CHANGE_EMOTION:
                return f"情绪调整有效，付费率提升{evaluation.payer_rate_change:.1%}pp"
            else:
                return f"策略有效，reward={evaluation.reward:.2f}"
        else:
            if evaluation.roas_change < 0:
                return f"策略未达预期，ROAS下降{abs(evaluation.roas_change):.0%}，建议调整方向"
            elif evaluation.ctr_change < 0:
                return f"策略未达预期，CTR下降{abs(evaluation.ctr_change):.0%}，建议更换Hook"
            else:
                return "策略效果不明显，建议继续观察或调整方向"

    def _generate_recommendation(
        self,
        strategy: CreativeStrategy,
        evaluation: StrategyEvaluation,
        success: bool,
    ) -> str:
        """生成下一步建议."""
        if success:
            if strategy.strategy_type == CreativeStrategyType.SCALE_WINNER:
                return "继续扩大投放，监控疲劳度"
            return "可将成功策略应用到其他素材"
        else:
            if evaluation.fatigue_change > 0.1:
                return "疲劳度上升，建议更换策略方向"
            if evaluation.roas_change < -0.2:
                return "ROAS严重下降，建议暂停并重新分析"
            return "继续观察或尝试其他策略方向"

    def _update_memory(
        self,
        strategy: CreativeStrategy,
        outcome: CreativeStrategyOutcome,
    ) -> None:
        """更新创意记忆."""
        action = STRATEGY_TO_ACTION.get(strategy.strategy_type, CreativeActionType.UNKNOWN)

        decision_outcome = CreativeDecisionOutcome.SUCCESS if outcome.success else CreativeDecisionOutcome.FAILURE
        if outcome.outcome_type == StrategyOutcomeType.PARTIAL:
            decision_outcome = CreativeDecisionOutcome.PARTIAL
        elif outcome.outcome_type == StrategyOutcomeType.INCONCLUSIVE:
            decision_outcome = CreativeDecisionOutcome.PENDING

        record = self._memory.record_decision(
            creative_id=strategy.target_creative_id,
            action_type=action,
            confidence=strategy.confidence,
            before_metrics=outcome.before_metrics.to_dict() if outcome.before_metrics else {},
        )

        self._memory.resolve(
            record_id=record.record_id,
            outcome=decision_outcome,
            after_metrics=outcome.after_metrics.to_dict() if outcome.after_metrics else {},
            reward=outcome.reward,
            learning=outcome.learning,
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_outcome(self, outcome_id: str) -> CreativeStrategyOutcome | None:
        return self._outcomes.get(outcome_id)

    def get_strategy_outcomes(
        self,
        strategy_id: str,
    ) -> list[CreativeStrategyOutcome]:
        return [o for o in self._outcomes.values() if o.strategy_id == strategy_id]

    def get_successful_strategies(self) -> list[CreativeStrategyOutcome]:
        return [o for o in self._outcomes.values() if o.success]

    def get_failed_strategies(self) -> list[CreativeStrategyOutcome]:
        return [o for o in self._outcomes.values() if not o.success and o.outcome_type != StrategyOutcomeType.PENDING]

    def get_best_strategy_type(self) -> str:
        """获取最佳策略类型."""
        strategy_rewards: dict[str, list[float]] = {}
        for o in self._outcomes.values():
            t = o.strategy_type.value
            if t not in strategy_rewards:
                strategy_rewards[t] = []
            strategy_rewards[t].append(o.reward)

        best = ""
        best_avg = -float('inf')
        for stype, rewards in strategy_rewards.items():
            if len(rewards) >= 2:
                avg = sum(rewards) / len(rewards)
                if avg > best_avg:
                    best_avg = avg
                    best = stype
        return best

    def get_history(self, n: int = 20) -> list[CreativeStrategyOutcome]:
        return self._history[-n:]

    def stats(self) -> dict[str, Any]:
        total = len(self._outcomes)
        if total == 0:
            return {"total": 0}
        return {
            "total": total,
            "success_rate": round(
                len(self.get_successful_strategies()) / total, 4
            ),
            "avg_reward": round(
                sum(o.reward for o in self._outcomes.values()) / total, 4
            ),
            "best_strategy": self.get_best_strategy_type(),
        }

    def reset(self) -> None:
        self._outcomes.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_evaluator(
    memory: CreativeMemory | None = None,
) -> CreativeEvaluator:
    """创建默认评估器."""
    return CreativeEvaluator(memory=memory)