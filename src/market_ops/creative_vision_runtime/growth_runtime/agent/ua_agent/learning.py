"""E14.3.1 Learning — 反馈学习与策略改进.

从评估结果中学习，改进未来决策:
  1. LearningEngine: 从单个 outcome 中提取学习
  2. FeedbackLoop: 协调 Observe → Evaluate → Learn → Improve 完整闭环

核心流程:
  FeedbackLoop.run():
    1. Observe: 读取执行后指标 (after_metrics)
    2. Evaluate: 调用 RewardCalculator + OutcomeEvaluator
    3. Learn: 更新 UAMemory，记录结果
    4. Improve: 计算置信度调整，更新策略

学习规则:
  - 成功经验: 提升同类策略的置信度
  - 失败教训: 降低同类策略的置信度，记录失败原因
  - 样本积累: 达到 min_samples 后才触发学习

设计原则:
  - 学习结果写入 UAMemory (ExperienceEntry)
  - 置信度调整有上限 (+0.15 / -0.10)
  - 学习过程可追溯
  - 与 E14.2 Supervisor Memory 互补
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .feedback import UAActionOutcome, FeedbackBatch, FeedbackCollector
from .evaluation import (
    EvaluationResult,
    EvaluationBatch,
    RewardCalculator,
    OutcomeEvaluator,
    RewardConfig,
)
from .memory import UAMemory, UADecisionRecord, DecisionOutcome, ExperienceEntry
from .diagnosis import DiagnosisType
from .strategy import StrategyType


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningResult:
    """学习结果 — 一次完整的学习迭代输出.

    Attributes:
        learning_id: 学习 ID
        outcome: 动作结果
        evaluation: 评估结果
        confidence_adjustment: 置信度调整
        updated_experience: 更新后的经验条目
        learning_summary: 学习总结
        created_at: 学习时间
        metadata: 扩展元数据
    """
    learning_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcome: UAActionOutcome | None = None
    evaluation: EvaluationResult | None = None
    confidence_adjustment: float = 0.0
    updated_experience: ExperienceEntry | None = None
    learning_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "confidence_adjustment": round(self.confidence_adjustment, 4),
            "updated_experience": self.updated_experience.to_dict() if self.updated_experience else None,
            "learning_summary": self.learning_summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class FeedbackLoopResult:
    """反馈闭环结果 — FeedbackLoop.run() 的完整输出.

    Attributes:
        loop_id: 闭环 ID
        action_id: 关联的动作 ID
        outcome: 动作结果
        evaluation: 评估结果
        learning: 学习结果
        record: 更新后的决策记录
        improved: 是否成功改进
        recommendation: 后续建议
        created_at: 闭环时间
    """
    loop_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    outcome: UAActionOutcome | None = None
    evaluation: EvaluationResult | None = None
    learning: LearningResult | None = None
    record: UADecisionRecord | None = None
    improved: bool = False
    recommendation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "action_id": self.action_id,
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "learning": self.learning.to_dict() if self.learning else None,
            "record": self.record.to_dict() if self.record else None,
            "improved": self.improved,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class FeedbackLoopBatch:
    """批量反馈闭环结果.

    Attributes:
        batch_id: 批次 ID
        results: 闭环结果列表
        improved_count: 改进数量
        total_confidence_adjustment: 总置信度调整
        avg_reward: 平均奖励
        created_at: 创建时间
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    results: list[FeedbackLoopResult] = field(default_factory=list)
    improved_count: int = 0
    total_confidence_adjustment: float = 0.0
    avg_reward: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "results": [r.to_dict() for r in self.results],
            "improved_count": self.improved_count,
            "total_confidence_adjustment": round(self.total_confidence_adjustment, 4),
            "avg_reward": round(self.avg_reward, 4),
            "result_count": self.result_count,
            "created_at": self.created_at,
        }

    @property
    def result_count(self) -> int:
        return len(self.results)


# ═══════════════════════════════════════════════════════════════
# Learning Engine
# ═══════════════════════════════════════════════════════════════


class LearningEngine:
    """学习引擎 — 从反馈中提取经验并更新记忆.

    职责:
      1. 从 outcome + evaluation 中提取学习
      2. 更新 UAMemory 中的经验
      3. 计算置信度调整
      4. 生成学习总结

    用法:
        engine = LearningEngine()
        result = engine.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
    """

    def __init__(self, min_samples: int = 3):
        self._min_samples = min_samples
        self._history: list[LearningResult] = []

    # ── 核心学习 ──────────────────────────────────────────────

    def learn(
        self,
        outcome: UAActionOutcome,
        evaluation: EvaluationResult,
        memory: UAMemory,
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        record_id: str = "",
    ) -> LearningResult:
        """从单个结果中学习.

        Args:
            outcome: 动作执行结果
            evaluation: 评估结果
            memory: UA 记忆系统
            diagnosis_type: 诊断类型
            strategy_type: 策略类型
            record_id: 关联的决策记录 ID

        Returns:
            LearningResult: 学习结果
        """
        # 1. 更新记忆中的决策记录
        if record_id and memory.get_record(record_id):
            memory.resolve(
                record_id=record_id,
                outcome=evaluation.decision_outcome,
                after_metrics=outcome.after_metrics,
                learning=self._generate_learning(outcome, evaluation),
            )
        elif not record_id:
            # 没有 record_id 时，创建新记录并直接 resolve 以触发经验更新
            record = memory.record_decision(
                diagnosis_type=diagnosis_type,
                strategy_type=strategy_type,
                action_type=outcome.action_type,
                action_target=outcome.target,
                confidence=outcome.confidence_adjustment,
                before_metrics=outcome.before_metrics,
            )
            memory.resolve(
                record_id=record.record_id,
                outcome=evaluation.decision_outcome,
                after_metrics=outcome.after_metrics,
                learning=self._generate_learning(outcome, evaluation),
            )

        # 2. 获取或创建经验条目
        # 先查找已有经验
        existing = self._find_experience(memory, diagnosis_type, strategy_type, outcome.action_type)

        # 3. 计算置信度调整
        confidence_adjustment = evaluation.confidence_adjustment
        if existing and existing.total_count < self._min_samples:
            # 样本不足时减少调整幅度
            confidence_adjustment *= (existing.total_count / self._min_samples)

        # 4. 生成学习总结
        learning_summary = self._generate_learning(outcome, evaluation)

        result = LearningResult(
            outcome=outcome,
            evaluation=evaluation,
            confidence_adjustment=confidence_adjustment,
            updated_experience=existing,
            learning_summary=learning_summary,
        )

        self._history.append(result)
        return result

    def learn_from_dicts(
        self,
        outcome_data: dict[str, Any],
        evaluation_data: dict[str, Any],
        memory: UAMemory,
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        record_id: str = "",
    ) -> LearningResult:
        """从字典数据学习."""
        outcome = UAActionOutcome(**{
            k: v for k, v in outcome_data.items()
            if k in UAActionOutcome.__dataclass_fields__
        })
        evaluation = EvaluationResult(**{
            k: v for k, v in evaluation_data.items()
            if k in EvaluationResult.__dataclass_fields__
        })
        return self.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            diagnosis_type=diagnosis_type,
            strategy_type=strategy_type,
            record_id=record_id,
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _find_experience(
        self,
        memory: UAMemory,
        diagnosis_type: DiagnosisType,
        strategy_type: StrategyType,
        action_type: str,
    ) -> ExperienceEntry | None:
        """查找已有经验."""
        for exp in memory.get_experiences(diagnosis_type=diagnosis_type):
            if exp.strategy_type == strategy_type and exp.action_type == action_type:
                return exp
        return None

    def _generate_learning(
        self,
        outcome: UAActionOutcome,
        evaluation: EvaluationResult,
    ) -> str:
        """生成学习总结."""
        parts = []

        # 动作 + 结果
        if evaluation.decision_outcome == DecisionOutcome.SUCCESS:
            parts.append(f"成功: {outcome.action_type} 产生了正向效果")
        elif evaluation.decision_outcome == DecisionOutcome.PARTIAL:
            parts.append(f"部分成功: {outcome.action_type} 有改善但未达预期")
        elif evaluation.decision_outcome == DecisionOutcome.FAILURE:
            parts.append(f"失败: {outcome.action_type} 未产生预期效果")
        else:
            parts.append(f"中性: {outcome.action_type} 效果不明显")

        # 关键指标变化
        if outcome.roas_delta > 0.05:
            parts.append(f"ROAS提升了{outcome.roas_delta:.0%}")
        elif outcome.roas_delta < -0.05:
            parts.append(f"ROAS下降了{outcome.roas_delta:.0%}")

        if outcome.ltv_delta > 0.03:
            parts.append(f"LTV提升了{outcome.ltv_delta:.0%}")
        elif outcome.ltv_delta < -0.03:
            parts.append(f"LTV下降了{outcome.ltv_delta:.0%}")

        # 置信度调整
        if evaluation.confidence_adjustment > 0:
            parts.append(f"建议提升置信度+{evaluation.confidence_adjustment:.0%}")
        elif evaluation.confidence_adjustment < 0:
            parts.append(f"建议降低置信度{evaluation.confidence_adjustment:.0%}")

        return " | ".join(parts)

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[LearningResult]:
        return self._history[-n:]

    def get_improved_count(self) -> int:
        return sum(1 for r in self._history if r.confidence_adjustment > 0)

    def get_degraded_count(self) -> int:
        return sum(1 for r in self._history if r.confidence_adjustment < 0)

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Feedback Loop
# ═══════════════════════════════════════════════════════════════


class FeedbackLoop:
    """反馈闭环 — 协调 Observe → Evaluate → Learn → Improve 完整流程.

    职责:
      1. Observe: 接收执行后指标
      2. Evaluate: 计算奖励并评估结果
      3. Learn: 更新记忆并提取经验
      4. Improve: 返回改进建议

    这是 UA Agent 实现 Autonomous Growth 的核心闭环:
      Decision → Execution → Observation → Feedback → Evaluation → Learning → Decision

    用法:
        loop = FeedbackLoop()
        result = loop.run(
            action_id="act_001",
            action_type="generate_variants",
            before_metrics={"roas": 1.3, "ltv": 4.5},
            after_metrics={"roas": 1.6, "ltv": 5.2},
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        print(f"Improved: {result.improved}, Reward: {result.evaluation.reward}")
    """

    def __init__(
        self,
        reward_config: RewardConfig | None = None,
        min_samples: int = 3,
    ):
        self._collector = FeedbackCollector()
        self._reward_calc = RewardCalculator(reward_config)
        self._evaluator = OutcomeEvaluator(reward_config)
        self._learner = LearningEngine(min_samples=min_samples)
        self._history: list[FeedbackLoopResult] = []

    # ── 核心闭环 ──────────────────────────────────────────────

    def run(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        memory: UAMemory,
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        observation_hours: int = 24,
        record_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackLoopResult:
        """运行完整反馈闭环.

        Args:
            action_id: 动作 ID
            action_type: 动作类型
            target: 目标实体
            before_metrics: 执行前指标
            after_metrics: 执行后指标
            memory: UA 记忆系统
            diagnosis_type: 诊断类型
            strategy_type: 策略类型
            observation_hours: 观察周期
            record_id: 关联的决策记录 ID
            metadata: 扩展元数据

        Returns:
            FeedbackLoopResult: 闭环结果
        """
        # Phase 1: Observe — 采集反馈
        outcome = self._collector.collect(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            observation_hours=observation_hours,
            metadata=metadata,
        )

        # Phase 2: Evaluate — 计算奖励 + 评估
        reward = self._reward_calc.calculate(outcome)
        outcome.reward = reward
        outcome.success = reward >= self._reward_calc.config.success_threshold
        evaluation = self._evaluator.evaluate(outcome, reward)

        # Phase 3: Learn — 更新记忆
        learning = self._learner.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            diagnosis_type=diagnosis_type,
            strategy_type=strategy_type,
            record_id=record_id,
        )

        # Phase 4: Improve — 更新 outcome 的置信度调整
        outcome.confidence_adjustment = learning.confidence_adjustment
        outcome.learning = learning.learning_summary

        # 查找关联的决策记录
        record = memory.get_record(record_id) if record_id else None

        # 生成建议
        recommendation = self._generate_recommendation(outcome, evaluation, learning)

        loop_result = FeedbackLoopResult(
            action_id=action_id,
            outcome=outcome,
            evaluation=evaluation,
            learning=learning,
            record=record,
            improved=learning.confidence_adjustment > 0,
            recommendation=recommendation,
            metadata=metadata or {},
        )

        self._history.append(loop_result)
        return loop_result

    def run_batch(
        self,
        actions: list[dict[str, Any]],
        metrics_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
        memory: UAMemory,
        diagnosis_types: list[DiagnosisType] | None = None,
        strategy_types: list[StrategyType] | None = None,
        observation_hours: int = 24,
    ) -> FeedbackLoopBatch:
        """批量运行反馈闭环.

        Args:
            actions: 动作信息列表
            metrics_pairs: 前后指标对
            memory: UA 记忆系统
            diagnosis_types: 诊断类型列表
            strategy_types: 策略类型列表
            observation_hours: 观察周期

        Returns:
            FeedbackLoopBatch
        """
        results = []
        for i, (action, (before, after)) in enumerate(zip(actions, metrics_pairs)):
            dt = (diagnosis_types or [DiagnosisType.HEALTHY])[i % len(diagnosis_types or [DiagnosisType.HEALTHY])]
            st = (strategy_types or [StrategyType.MONITOR_ONLY])[i % len(strategy_types or [StrategyType.MONITOR_ONLY])]

            result = self.run(
                action_id=action.get("action_id", ""),
                action_type=action.get("action_type", ""),
                target=action.get("target", ""),
                before_metrics=before,
                after_metrics=after,
                memory=memory,
                diagnosis_type=dt,
                strategy_type=st,
                observation_hours=observation_hours,
                record_id=action.get("record_id", ""),
                metadata=action.get("metadata", {}),
            )
            results.append(result)

        improved_count = sum(1 for r in results if r.improved)
        total_adj = sum(r.learning.confidence_adjustment for r in results if r.learning)
        avg_reward = sum(r.evaluation.reward for r in results if r.evaluation) / len(results) if results else 0.0

        return FeedbackLoopBatch(
            results=results,
            improved_count=improved_count,
            total_confidence_adjustment=total_adj,
            avg_reward=avg_reward,
        )

    def run_from_resolutions(
        self,
        resolutions: list[dict[str, Any]],
        memory: UAMemory,
        observation_hours: int = 24,
    ) -> FeedbackLoopBatch:
        """从决策结果记录批量运行闭环."""
        actions = []
        metrics_pairs = []
        diagnosis_types = []
        strategy_types = []

        for r in resolutions:
            actions.append({
                "action_id": r.get("action_id", r.get("record_id", "")),
                "action_type": r.get("action_type", ""),
                "target": r.get("action_target", r.get("target", "")),
                "record_id": r.get("record_id", ""),
                "metadata": r.get("metadata", {}),
            })
            metrics_pairs.append((
                r.get("before_metrics", {}),
                r.get("after_metrics", {}),
            ))
            diagnosis_types.append(
                DiagnosisType(r.get("diagnosis_type", "healthy"))
            )
            strategy_types.append(
                StrategyType(r.get("strategy_type", "monitor_only"))
            )

        return self.run_batch(
            actions=actions,
            metrics_pairs=metrics_pairs,
            memory=memory,
            diagnosis_types=diagnosis_types,
            strategy_types=strategy_types,
            observation_hours=observation_hours,
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _generate_recommendation(
        self,
        outcome: UAActionOutcome,
        evaluation: EvaluationResult,
        learning: LearningResult,
    ) -> str:
        """生成后续建议."""
        if evaluation.decision_outcome == DecisionOutcome.SUCCESS:
            if outcome.roas_delta > 0.1:
                return f"策略成功: 建议扩大 {outcome.action_type} 的应用范围"
            else:
                return f"策略成功: 继续使用 {outcome.action_type}"
        elif evaluation.decision_outcome == DecisionOutcome.PARTIAL:
            return f"部分成功: 建议调整 {outcome.action_type} 的参数后重试"
        elif evaluation.decision_outcome == DecisionOutcome.FAILURE:
            return f"策略失败: 建议切换到替代策略，避免使用 {outcome.action_type}"
        else:
            return f"效果中性: 建议继续观察 {outcome.action_type} 的长期效果"

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[FeedbackLoopResult]:
        return self._history[-n:]

    def get_improvement_rate(self, n: int = 20) -> float:
        if not self._history:
            return 0.0
        recent = self._history[-n:]
        return sum(1 for r in recent if r.improved) / len(recent)

    def get_avg_reward(self, n: int = 20) -> float:
        if not self._history:
            return 0.0
        recent = self._history[-n:]
        rewards = [r.evaluation.reward for r in recent if r.evaluation]
        return sum(rewards) / len(rewards) if rewards else 0.0

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total_loops": 0, "improvement_rate": 0.0}

        improved = sum(1 for r in self._history if r.improved)
        avg_reward = self.get_avg_reward(len(self._history))
        learner_improved = self._learner.get_improved_count()
        learner_degraded = self._learner.get_degraded_count()

        return {
            "total_loops": total,
            "improved": improved,
            "improvement_rate": round(improved / total, 4),
            "avg_reward": round(avg_reward, 4),
            "learner_improved": learner_improved,
            "learner_degraded": learner_degraded,
            "reward_calc_history": len(self._reward_calc.get_history()),
            "evaluator_history": len(self._evaluator.get_history()),
        }

    def reset(self) -> None:
        self._history.clear()
        self._reward_calc.reset()
        self._evaluator.reset()
        self._learner.reset()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_feedback_loop(
    roas_weight: float = 0.5,
    ltv_weight: float = 0.3,
    spend_risk_weight: float = 0.2,
    min_samples: int = 3,
) -> FeedbackLoop:
    """创建默认反馈闭环."""
    config = RewardConfig(
        roas_weight=roas_weight,
        ltv_weight=ltv_weight,
        spend_risk_weight=spend_risk_weight,
    )
    return FeedbackLoop(reward_config=config, min_samples=min_samples)