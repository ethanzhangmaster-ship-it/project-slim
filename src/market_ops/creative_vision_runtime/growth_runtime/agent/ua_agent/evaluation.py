"""E14.3.1 Evaluation — 奖励函数与结果评估.

对 FeedbackCollector 采集的 UAActionOutcome 进行评估:
  1. RewardCalculator: 计算动作奖励值
  2. OutcomeEvaluator: 判定动作成功/失败

奖励函数设计:
  reward = ROAS_improvement × 0.5 + LTV_improvement × 0.3 - spend_risk × 0.2

  其中:
  - ROAS_improvement: ROAS 相对变化 (clamp to [-1, 1])
  - LTV_improvement: LTV 相对变化 (clamp to [-1, 1])
  - spend_risk: 花费风险 = spend_delta × risk_multiplier (clamp to [0, 1])

评估阈值:
  - reward >= 0.3  → SUCCESS (强正向)
  - reward >= 0.05 → PARTIAL (部分正向)
  - reward >= -0.05 → NEUTRAL (中性)
  - reward < -0.05 → FAILURE (负向)

设计原则:
  - 奖励函数可解释、可配置
  - ROAS 权重最高 (50%) 因为直接反映广告效率
  - LTV 权重次之 (30%) 反映长期价值
  - 花费风险惩罚 (20%) 防止无节制扩量
  - 所有评估结果可追溯
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .feedback import UAActionOutcome, FeedbackBatch
from .memory import DecisionOutcome


# ═══════════════════════════════════════════════════════════════
# Reward Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class RewardConfig:
    """奖励函数配置.

    Attributes:
        roas_weight: ROAS 改善权重 (默认 0.5)
        ltv_weight: LTV 改善权重 (默认 0.3)
        spend_risk_weight: 花费风险惩罚权重 (默认 0.2)
        spend_risk_multiplier: 花费风险乘数 (默认 2.0)
        success_threshold: 成功阈值 (默认 0.3)
        partial_threshold: 部分成功阈值 (默认 0.05)
        neutral_threshold: 中性阈值 (默认 -0.05)
    """
    roas_weight: float = 0.5
    ltv_weight: float = 0.3
    spend_risk_weight: float = 0.2
    spend_risk_multiplier: float = 2.0
    success_threshold: float = 0.3
    partial_threshold: float = 0.05
    neutral_threshold: float = -0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "roas_weight": self.roas_weight,
            "ltv_weight": self.ltv_weight,
            "spend_risk_weight": self.spend_risk_weight,
            "spend_risk_multiplier": self.spend_risk_multiplier,
            "success_threshold": self.success_threshold,
            "partial_threshold": self.partial_threshold,
            "neutral_threshold": self.neutral_threshold,
        }


# 默认配置
DEFAULT_REWARD_CONFIG = RewardConfig()


# ═══════════════════════════════════════════════════════════════
# Evaluation Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvaluationResult:
    """评估结果.

    Attributes:
        evaluation_id: 评估 ID
        outcome_id: 关联的结果 ID
        reward: 奖励值 (-1 ~ 1)
        decision_outcome: 决策结果 (SUCCESS/PARTIAL/FAILURE)
        roas_improvement: ROAS 改善项
        ltv_improvement: LTV 改善项
        spend_risk: 花费风险项
        confidence_adjustment: 置信度调整建议
        explanation: 评估解释
        created_at: 评估时间
    """
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcome_id: str = ""
    reward: float = 0.0
    decision_outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    roas_improvement: float = 0.0
    ltv_improvement: float = 0.0
    spend_risk: float = 0.0
    confidence_adjustment: float = 0.0
    explanation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "outcome_id": self.outcome_id,
            "reward": round(self.reward, 4),
            "decision_outcome": self.decision_outcome.value,
            "roas_improvement": round(self.roas_improvement, 4),
            "ltv_improvement": round(self.ltv_improvement, 4),
            "spend_risk": round(self.spend_risk, 4),
            "confidence_adjustment": round(self.confidence_adjustment, 4),
            "explanation": self.explanation,
            "created_at": self.created_at,
        }


@dataclass
class EvaluationBatch:
    """批量评估结果.

    Attributes:
        batch_id: 批次 ID
        results: 评估结果列表
        avg_reward: 平均奖励
        success_rate: 成功率
        created_at: 创建时间
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    results: list[EvaluationResult] = field(default_factory=list)
    avg_reward: float = 0.0
    success_rate: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "results": [r.to_dict() for r in self.results],
            "avg_reward": round(self.avg_reward, 4),
            "success_rate": round(self.success_rate, 4),
            "result_count": self.result_count,
            "created_at": self.created_at,
        }

    @property
    def result_count(self) -> int:
        return len(self.results)


# ═══════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════


def _clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    """将值限制在 [lo, hi] 范围内."""
    return max(lo, min(hi, val))


# ═══════════════════════════════════════════════════════════════
# Reward Calculator
# ═══════════════════════════════════════════════════════════════


class RewardCalculator:
    """奖励计算器 — 计算动作执行的奖励值.

    奖励公式:
      reward = ROAS_improvement × roas_weight
             + LTV_improvement × ltv_weight
             - spend_risk × spend_risk_weight

    设计意图:
      - ROAS: 直接衡量广告效率，权重最高
      - LTV: 衡量长期价值，防止短视决策
      - spend_risk: 惩罚无节制扩量，控制风险

    用法:
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        # 或自定义配置
        calc = RewardCalculator(RewardConfig(roas_weight=0.6, ltv_weight=0.4))
    """

    def __init__(self, config: RewardConfig | None = None):
        self._config = config or DEFAULT_REWARD_CONFIG
        self._history: list[tuple[str, float]] = []  # (outcome_id, reward)

    @property
    def config(self) -> RewardConfig:
        return self._config

    def calculate(self, outcome: UAActionOutcome) -> float:
        """计算动作奖励.

        Args:
            outcome: 动作执行结果

        Returns:
            float: 奖励值 (-1 ~ 1)
        """
        # ROAS 改善: 将 delta 映射到 [-1, 1]
        # ROAS 上升 50% = +1.0, ROAS 下降 50% = -1.0
        roas_improvement = _clamp(outcome.roas_delta / 0.5)

        # LTV 改善: 将 delta 映射到 [-1, 1]
        # LTV 上升 30% = +1.0, LTV 下降 30% = -1.0
        ltv_improvement = _clamp(outcome.ltv_delta / 0.3)

        # 花费风险: spend_delta 越大风险越高
        # spend 上升 50% = 1.0, spend 不增 = 0
        spend_risk = _clamp(
            outcome.spend_delta * self._config.spend_risk_multiplier,
            lo=0.0,
            hi=1.0,
        )

        # 加权计算
        reward = (
            roas_improvement * self._config.roas_weight
            + ltv_improvement * self._config.ltv_weight
            - spend_risk * self._config.spend_risk_weight
        )

        reward = round(_clamp(reward), 4)
        self._history.append((outcome.outcome_id, reward))
        return reward

    def calculate_from_dicts(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> float:
        """从字典直接计算奖励.

        Args:
            before: 执行前指标
            after: 执行后指标

        Returns:
            float: 奖励值
        """
        # 构造临时 outcome 用于计算
        class _Temp:
            pass
        temp = _Temp()
        temp.outcome_id = "temp"
        temp.roas_delta = self._safe_delta(before, after, "roas")
        temp.ltv_delta = self._safe_delta(before, after, "ltv")
        temp.spend_delta = self._safe_delta(before, after, "spend")
        return self.calculate(temp)

    def calculate_batch(self, outcomes: list[UAActionOutcome]) -> list[float]:
        """批量计算奖励."""
        return [self.calculate(o) for o in outcomes]

    @staticmethod
    def _safe_delta(
        before: dict[str, Any],
        after: dict[str, Any],
        key: str,
    ) -> float:
        """安全计算单个指标的 delta."""
        b = float(before.get(key, 0) or 0)
        a = float(after.get(key, 0) or 0)
        if b == 0:
            return a if a != 0 else 0.0
        return (a - b) / b

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[tuple[str, float]]:
        return self._history[-n:]

    def get_avg_reward(self, n: int = 20) -> float:
        if not self._history:
            return 0.0
        recent = self._history[-n:]
        return sum(r for _, r in recent) / len(recent)

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Outcome Evaluator
# ═══════════════════════════════════════════════════════════════


class OutcomeEvaluator:
    """结果评估器 — 判定动作成功/失败并生成置信度调整建议.

    评估规则:
      - reward >= success_threshold  → SUCCESS
      - reward >= partial_threshold  → PARTIAL
      - reward >= neutral_threshold  → 不改变 (保持 PENDING)
      - reward < neutral_threshold   → FAILURE

    置信度调整:
      - reward >= 0.7  → +0.15
      - reward >= 0.3  → +0.10
      - reward >= 0.05 → +0.05
      - reward >= -0.05 → 0
      - reward >= -0.3  → -0.05
      - reward < -0.3   → -0.10

    用法:
        evaluator = OutcomeEvaluator()
        result = evaluator.evaluate(outcome, reward=0.45)
        print(result.decision_outcome)  # SUCCESS
        print(result.confidence_adjustment)  # 0.10
    """

    def __init__(self, config: RewardConfig | None = None):
        self._config = config or DEFAULT_REWARD_CONFIG
        self._history: list[EvaluationResult] = []

    def evaluate(
        self,
        outcome: UAActionOutcome,
        reward: float | None = None,
    ) -> EvaluationResult:
        """评估单个动作结果.

        Args:
            outcome: 动作执行结果
            reward: 奖励值 (如果已计算，否则将重新计算)

        Returns:
            EvaluationResult: 评估结果
        """
        if reward is None:
            calc = RewardCalculator(self._config)
            reward = calc.calculate(outcome)

        # 判定结果
        decision_outcome = self._classify(reward)

        # 信息项
        roas_improvement = _clamp(outcome.roas_delta / 0.5)
        ltv_improvement = _clamp(outcome.ltv_delta / 0.3)
        spend_risk = _clamp(
            outcome.spend_delta * self._config.spend_risk_multiplier,
            lo=0.0,
            hi=1.0,
        )

        # 置信度调整
        confidence_adjustment = self._compute_confidence_adjustment(reward)

        # 解释
        explanation = self._generate_explanation(
            outcome, reward, decision_outcome, roas_improvement, ltv_improvement, spend_risk,
        )

        result = EvaluationResult(
            outcome_id=outcome.outcome_id,
            reward=reward,
            decision_outcome=decision_outcome,
            roas_improvement=round(roas_improvement, 4),
            ltv_improvement=round(ltv_improvement, 4),
            spend_risk=round(spend_risk, 4),
            confidence_adjustment=confidence_adjustment,
            explanation=explanation,
        )

        self._history.append(result)
        return result

    def evaluate_batch(
        self,
        outcomes: list[UAActionOutcome],
        rewards: list[float] | None = None,
    ) -> EvaluationBatch:
        """批量评估.

        Args:
            outcomes: 动作结果列表
            rewards: 预计算的奖励值列表

        Returns:
            EvaluationBatch
        """
        if rewards is None:
            calc = RewardCalculator(self._config)
            rewards = calc.calculate_batch(outcomes)

        results = []
        for outcome, reward in zip(outcomes, rewards):
            result = self.evaluate(outcome, reward)
            results.append(result)

        avg_reward = sum(r.reward for r in results) / len(results) if results else 0.0
        success_count = sum(1 for r in results if r.decision_outcome == DecisionOutcome.SUCCESS)
        success_rate = success_count / len(results) if results else 0.0

        return EvaluationBatch(
            results=results,
            avg_reward=avg_reward,
            success_rate=success_rate,
        )

    def evaluate_from_feedback_batch(
        self,
        batch: FeedbackBatch,
    ) -> EvaluationBatch:
        """从 FeedbackBatch 评估."""
        return self.evaluate_batch(batch.outcomes)

    # ── 内部方法 ──────────────────────────────────────────────

    def _classify(self, reward: float) -> DecisionOutcome:
        """根据奖励值判定结果."""
        if reward >= self._config.success_threshold:
            return DecisionOutcome.SUCCESS
        elif reward >= self._config.partial_threshold:
            return DecisionOutcome.PARTIAL
        elif reward >= self._config.neutral_threshold:
            return DecisionOutcome.PENDING  # 中性，不判定
        else:
            return DecisionOutcome.FAILURE

    def _compute_confidence_adjustment(self, reward: float) -> float:
        """根据奖励值计算置信度调整."""
        if reward >= 0.7:
            return 0.15
        elif reward >= 0.3:
            return 0.10
        elif reward >= 0.05:
            return 0.05
        elif reward >= -0.05:
            return 0.0
        elif reward >= -0.3:
            return -0.05
        else:
            return -0.10

    def _generate_explanation(
        self,
        outcome: UAActionOutcome,
        reward: float,
        decision_outcome: DecisionOutcome,
        roas_improvement: float,
        ltv_improvement: float,
        spend_risk: float,
    ) -> str:
        """生成评估解释."""
        parts = []

        # 动作描述
        parts.append(f"动作[{outcome.action_type}]")

        # 结果判定
        label_map = {
            DecisionOutcome.SUCCESS: "成功",
            DecisionOutcome.PARTIAL: "部分成功",
            DecisionOutcome.FAILURE: "失败",
            DecisionOutcome.PENDING: "中性",
            DecisionOutcome.UNKNOWN: "未知",
        }
        parts.append(f"结果: {label_map.get(decision_outcome, '未知')}")

        # 奖励分解
        parts.append(
            f"reward={reward:+.3f} "
            f"(ROAS={roas_improvement:+.2f}×{self._config.roas_weight} "
            f"+ LTV={ltv_improvement:+.2f}×{self._config.ltv_weight} "
            f"- risk={spend_risk:.2f}×{self._config.spend_risk_weight})"
        )

        # 关键指标变化
        if outcome.roas_delta != 0:
            parts.append(f"ROAS {outcome.roas_delta:+.1%}")

        if outcome.ltv_delta != 0:
            parts.append(f"LTV {outcome.ltv_delta:+.1%}")

        return " | ".join(parts)

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[EvaluationResult]:
        return self._history[-n:]

    def get_success_rate(self, n: int = 20) -> float:
        if not self._history:
            return 0.0
        recent = self._history[-n:]
        successes = sum(1 for r in recent if r.decision_outcome == DecisionOutcome.SUCCESS)
        return successes / len(recent)

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total": 0, "success_rate": 0.0}

        success = sum(1 for r in self._history if r.decision_outcome == DecisionOutcome.SUCCESS)
        partial = sum(1 for r in self._history if r.decision_outcome == DecisionOutcome.PARTIAL)
        failure = sum(1 for r in self._history if r.decision_outcome == DecisionOutcome.FAILURE)
        avg_reward = sum(r.reward for r in self._history) / total

        return {
            "total": total,
            "success": success,
            "partial": partial,
            "failure": failure,
            "success_rate": round(success / total, 4),
            "avg_reward": round(avg_reward, 4),
        }

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_reward_calculator(
    roas_weight: float = 0.5,
    ltv_weight: float = 0.3,
    spend_risk_weight: float = 0.2,
) -> RewardCalculator:
    """创建奖励计算器."""
    config = RewardConfig(
        roas_weight=roas_weight,
        ltv_weight=ltv_weight,
        spend_risk_weight=spend_risk_weight,
    )
    return RewardCalculator(config)


def create_outcome_evaluator() -> OutcomeEvaluator:
    """创建默认结果评估器."""
    return OutcomeEvaluator()