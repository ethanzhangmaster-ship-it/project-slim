"""E13.6 Pattern Feedback Loop — 模式反馈回路.

将执行结果反馈回 PatternMemory，实现自学习闭环:
  - PatternEvaluator:       评估模式是否继续有效 (基于最近执行结果)
  - PatternRewardUpdater:   执行结果→奖励信号→更新模式性能
  - PatternLifecycleManager: 生命周期管理 (ACTIVE → DECAYING → ARCHIVED)

与 pattern_evolution.py 的区别:
  - pattern_evolution.py: 模式内部进化 (评分/衰减/强化/冲突)，周期性运行
  - pattern_feedback.py:  执行结果反馈回路，每次执行后触发

架构:
  ExecutionResult
       │
       ▼
  PatternEvaluator ──→ 评估模式有效性
       │
       ▼
  PatternRewardUpdater ──→ 更新奖励/性能
       │
       ▼
  PatternLifecycleManager ──→ 生命周期迁移
       │
       ▼
  PatternMemory (更新后)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .models import (
    GrowthExperience,
    PatternMemory,
    PatternPerformance,
    PatternQuality,
)


# ═══════════════════════════════════════════════════════════════
# E13.6.1 PatternEvaluator — 模式有效性评估
# ═══════════════════════════════════════════════════════════════


class PatternEffectiveness(str, Enum):
    """模式有效性等级."""
    STRONG = "strong"           # 最近表现依然优秀
    MAINTAINING = "maintaining" # 维持历史水平
    WEAKENING = "weakening"     # 表现下降
    FAILING = "failing"         # 最近表现差
    EXPIRED = "expired"         # 不再有效


@dataclass
class EvaluationResult:
    """模式评估结果.

    Attributes:
        pattern_id: 模式ID
        effectiveness: 有效性等级
        historical_success_rate: 历史成功率
        recent_success_rate: 最近成功率
        recent_samples: 最近样本数
        success_rate_delta: 成功率变化
        confidence_adjustment: 置信度调整值
        should_update: 是否需要更新模式
        reason: 评估原因
    """
    pattern_id: str = ""
    effectiveness: PatternEffectiveness = PatternEffectiveness.MAINTAINING
    historical_success_rate: float = 0.0
    recent_success_rate: float = 0.0
    recent_samples: int = 0
    success_rate_delta: float = 0.0
    confidence_adjustment: float = 0.0
    should_update: bool = False
    reason: str = ""


class PatternEvaluator:
    """E13.6 PatternEvaluator — 评估历史模式是否继续有效.

    核心机制:
      1. 收集该模式最近N次执行结果
      2. 计算最近成功率 vs 历史成功率
      3. 判定有效性等级
      4. 输出置信度调整建议

    评估逻辑:
      - 最近成功率 >= 历史成功率 × 0.9 → STRONG
      - 最近成功率 >= 历史成功率 × 0.7 → MAINTAINING
      - 最近成功率 >= 历史成功率 × 0.5 → WEAKENING
      - 最近成功率 < 历史成功率 × 0.5  → FAILING
      - 最近样本=0 且长时间未验证       → EXPIRED

    用法:
        evaluator = PatternEvaluator()
        result = evaluator.evaluate(pattern, recent_experiences)
        if result.should_update:
            pattern.confidence += result.confidence_adjustment
    """

    # 评估参数
    DEFAULT_RECENT_WINDOW = 20          # 最近N次经验
    DEFAULT_MIN_RECENT_SAMPLES = 5      # 最少最近样本数
    DEFAULT_EXPIRY_DAYS = 90            # 超过此天数未验证视为过期

    # 有效性阈值
    STRONG_RATIO = 0.90      # 最近/历史 >= 0.9
    MAINTAINING_RATIO = 0.70 # 最近/历史 >= 0.7
    WEAKENING_RATIO = 0.50   # 最近/历史 >= 0.5

    # 置信度调整
    STRONG_BOOST = +0.05
    MAINTAINING_BOOST = 0.0
    WEAKENING_PENALTY = -0.10
    FAILING_PENALTY = -0.20
    EXPIRED_PENALTY = -0.30

    def __init__(
        self,
        recent_window: int = DEFAULT_RECENT_WINDOW,
        min_recent_samples: int = DEFAULT_MIN_RECENT_SAMPLES,
        expiry_days: int = DEFAULT_EXPIRY_DAYS,
        now: datetime | None = None,
    ):
        self._recent_window = recent_window
        self._min_recent_samples = min_recent_samples
        self._expiry_days = expiry_days
        self._now = now or datetime.now(timezone.utc)

    def evaluate(
        self,
        pattern: PatternMemory,
        recent_experiences: list[GrowthExperience],
    ) -> EvaluationResult:
        """评估模式有效性.

        Args:
            pattern: 要评估的模式
            recent_experiences: 最近与该模式相关的执行经验

        Returns:
            EvaluationResult: 评估结果
        """
        perf = pattern.performance
        historical_rate = perf.success_rate

        # 筛选匹配的经验
        matching = self._filter_matching(pattern, recent_experiences)
        recent = matching[-self._recent_window:] if len(matching) > self._recent_window else matching

        result = EvaluationResult(
            pattern_id=pattern.pattern_id,
            historical_success_rate=round(historical_rate, 4),
            recent_samples=len(recent),
        )

        # 没有最近样本
        if len(recent) < self._min_recent_samples:
            # 检查是否已过期
            days_since = self._days_since_last_seen(perf)
            if days_since is not None and days_since > self._expiry_days:
                result.effectiveness = PatternEffectiveness.EXPIRED
                result.confidence_adjustment = self.EXPIRED_PENALTY
                result.should_update = True
                result.reason = f"Expired: {days_since:.0f}d since last seen, no recent validation"
            else:
                result.effectiveness = PatternEffectiveness.MAINTAINING
                result.reason = f"Insufficient recent samples ({len(recent)} < {self._min_recent_samples})"
            return result

        # 计算最近成功率
        recent_successes = sum(1 for e in recent if e.is_successful())
        recent_rate = recent_successes / len(recent)
        result.recent_success_rate = round(recent_rate, 4)
        result.success_rate_delta = round(recent_rate - historical_rate, 4)

        # 判定有效性
        ratio = recent_rate / max(historical_rate, 0.01)
        if ratio >= self.STRONG_RATIO:
            result.effectiveness = PatternEffectiveness.STRONG
            result.confidence_adjustment = self.STRONG_BOOST
            result.reason = f"Strong: recent {recent_rate:.2%} vs historical {historical_rate:.2%} (ratio={ratio:.2f})"
        elif ratio >= self.MAINTAINING_RATIO:
            result.effectiveness = PatternEffectiveness.MAINTAINING
            result.confidence_adjustment = self.MAINTAINING_BOOST
            result.reason = f"Maintaining: recent {recent_rate:.2%} vs historical {historical_rate:.2%} (ratio={ratio:.2f})"
        elif ratio >= self.WEAKENING_RATIO:
            result.effectiveness = PatternEffectiveness.WEAKENING
            result.confidence_adjustment = self.WEAKENING_PENALTY
            result.should_update = True
            result.reason = f"Weakening: recent {recent_rate:.2%} vs historical {historical_rate:.2%} (ratio={ratio:.2f})"
        else:
            result.effectiveness = PatternEffectiveness.FAILING
            result.confidence_adjustment = self.FAILING_PENALTY
            result.should_update = True
            result.reason = f"Failing: recent {recent_rate:.2%} vs historical {historical_rate:.2%} (ratio={ratio:.2f})"

        return result

    def apply_evaluation(
        self,
        pattern: PatternMemory,
        result: EvaluationResult,
    ) -> PatternMemory:
        """将评估结果应用到模式上.

        Args:
            pattern: 模式
            result: 评估结果

        Returns:
            PatternMemory: 更新后的模式
        """
        if not result.should_update:
            return pattern

        # 更新置信度
        pattern.confidence = round(
            max(0.0, min(1.0, pattern.confidence + result.confidence_adjustment)),
            4,
        )

        # 更新成功率 (如果最近有足够样本)
        if result.recent_samples >= self._min_recent_samples:
            perf = pattern.performance
            # 合并最近结果到历史
            perf.success_rate = round(
                perf.success_rate * 0.7 + result.recent_success_rate * 0.3,
                4,
            )
            perf.last_seen = self._now.isoformat()

        # 标记评估结果
        pattern.metadata["last_evaluation"] = {
            "effectiveness": result.effectiveness.value,
            "timestamp": self._now.isoformat(),
            "reason": result.reason,
        }

        return pattern

    def _filter_matching(
        self,
        pattern: PatternMemory,
        experiences: list[GrowthExperience],
    ) -> list[GrowthExperience]:
        """筛选与模式匹配的经验."""
        matching = []
        for exp in experiences:
            # 动作类型匹配
            if exp.action_type != pattern.action.action_type:
                continue
            # 机会类型匹配 (如果模式有条件)
            if (pattern.condition.opportunity_type
                    and exp.context.opportunity_type != pattern.condition.opportunity_type):
                continue
            # 受众匹配
            if (pattern.condition.audience_segment
                    and exp.context.audience_segment != pattern.condition.audience_segment):
                continue
            matching.append(exp)
        return matching

    def _days_since_last_seen(self, perf: PatternPerformance) -> float | None:
        """计算距上次验证的天数."""
        if not perf.last_seen:
            return None
        try:
            ts = datetime.fromisoformat(perf.last_seen.replace("Z", "+00:00"))
            return (self._now - ts).total_seconds() / 86400.0
        except (ValueError, AttributeError):
            return None


# ═══════════════════════════════════════════════════════════════
# E13.6.2 PatternRewardUpdater — 执行结果奖励更新
# ═══════════════════════════════════════════════════════════════


@dataclass
class RewardSignal:
    """奖励信号 — 从执行结果计算出的奖励.

    Attributes:
        roas_reward: ROAS变化奖励
        ctr_reward: CTR变化奖励
        spend_reward: 花费稳定性奖励
        cvr_reward: CVR变化奖励
        payer_reward: 付费率变化奖励
        total_reward: 综合奖励 [-1, 1]
        normalized_reward: 归一化奖励 [0, 1]
    """
    roas_reward: float = 0.0
    ctr_reward: float = 0.0
    spend_reward: float = 0.0
    cvr_reward: float = 0.0
    payer_reward: float = 0.0
    total_reward: float = 0.0
    normalized_reward: float = 0.0


@dataclass
class RewardUpdateResult:
    """奖励更新结果.

    Attributes:
        pattern_id: 模式ID
        reward_before: 更新前平均奖励
        reward_after: 更新后平均奖励
        signal: 奖励信号
        samples_added: 新增样本数
        reason: 更新原因
    """
    pattern_id: str = ""
    reward_before: float = 0.0
    reward_after: float = 0.0
    signal: RewardSignal = field(default_factory=RewardSignal)
    samples_added: int = 0
    reason: str = ""


class PatternRewardUpdater:
    """E13.6 PatternRewardUpdater — 执行结果→奖励信号→更新模式性能.

    核心机制:
      1. 从执行结果中提取指标变化
      2. 计算多维度奖励信号
      3. 更新模式的 avg_reward 和 performance

    奖励计算 (类似强化学习):
      ROAS提升:    +1.0
      CTR提升:     +0.5
      CVR提升:     +0.3
      Spend稳定:   +0.3
      Payer提升:   +0.4
      失败:        -1.0

    综合奖励 = w1×roas + w2×ctr + w3×cvr + w4×spend + w5×payer
    归一化: sigmoid 映射到 [0, 1]

    用法:
        updater = PatternRewardUpdater()
        result = updater.update(pattern, execution_results)
        print(f"Reward: {result.reward_before:.2f} → {result.reward_after:.2f}")
    """

    # 奖励权重
    REWARD_WEIGHTS = {
        "roas": 0.30,
        "ctr": 0.15,
        "cvr": 0.15,
        "spend": 0.10,
        "payer": 0.30,
    }

    # 基值奖励
    BASE_ROAS_REWARD = 1.0
    BASE_CTR_REWARD = 0.5
    BASE_CVR_REWARD = 0.3
    BASE_SPEND_REWARD = 0.3
    BASE_PAYER_REWARD = 0.4
    BASE_FAILURE_PENALTY = -1.0

    # 指标变化阈值 (相对变化超过此值才视为有变化)
    MIN_DELTA_THRESHOLD = 0.02  # 2%

    # 更新衰减因子 (EMA)
    EMA_ALPHA = 0.3  # 新奖励权重

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        ema_alpha: float = EMA_ALPHA,
        now: datetime | None = None,
    ):
        self._weights = weights or dict(self.REWARD_WEIGHTS)
        self._ema_alpha = ema_alpha
        self._now = now or datetime.now(timezone.utc)

    def compute_reward(self, outcome: Any) -> RewardSignal:
        """从执行结果计算奖励信号.

        Args:
            outcome: ExperienceOutcome 或带 metrics_delta 的对象

        Returns:
            RewardSignal: 奖励信号
        """
        # 提取指标变化
        delta = self._extract_metrics_delta(outcome)

        # 如果执行失败，直接返回惩罚
        if self._is_failure(outcome):
            return RewardSignal(
                total_reward=self.BASE_FAILURE_PENALTY,
                normalized_reward=0.0,
            )

        # 计算各维度奖励
        roas = self._compute_metric_reward(delta.get("roas", 0.0), self.BASE_ROAS_REWARD)
        ctr = self._compute_metric_reward(delta.get("ctr", 0.0), self.BASE_CTR_REWARD)
        cvr = self._compute_metric_reward(delta.get("cvr", 0.0), self.BASE_CVR_REWARD)
        spend = self._compute_spend_reward(delta.get("spend", 0.0))
        payer = self._compute_metric_reward(delta.get("payer_rate", 0.0), self.BASE_PAYER_REWARD)

        # 加权综合
        total = (
            self._weights["roas"] * roas
            + self._weights["ctr"] * ctr
            + self._weights["cvr"] * cvr
            + self._weights["spend"] * spend
            + self._weights["payer"] * payer
        )
        total = round(max(-1.0, min(1.0, total)), 4)

        # 归一化到 [0, 1]
        normalized = round((total + 1.0) / 2.0, 4)

        return RewardSignal(
            roas_reward=round(roas, 4),
            ctr_reward=round(ctr, 4),
            spend_reward=round(spend, 4),
            cvr_reward=round(cvr, 4),
            payer_reward=round(payer, 4),
            total_reward=total,
            normalized_reward=normalized,
        )

    def update(
        self,
        pattern: PatternMemory,
        outcomes: list[Any],
    ) -> RewardUpdateResult | None:
        """用执行结果更新模式奖励.

        Args:
            pattern: 要更新的模式
            outcomes: 执行结果列表 (ExperienceOutcome 或类似对象)

        Returns:
            RewardUpdateResult | None: 更新结果
        """
        if not outcomes:
            return None

        reward_before = pattern.performance.avg_reward
        signals = [self.compute_reward(o) for o in outcomes]

        # 计算平均奖励
        avg_total = round(sum(s.total_reward for s in signals) / len(signals), 4)
        avg_normalized = round(sum(s.normalized_reward for s in signals) / len(signals), 4)

        # 计算平均各维度
        avg_roas = round(sum(s.roas_reward for s in signals) / len(signals), 4)
        avg_ctr = round(sum(s.ctr_reward for s in signals) / len(signals), 4)
        avg_cvr = round(sum(s.cvr_reward for s in signals) / len(signals), 4)
        avg_spend = round(sum(s.spend_reward for s in signals) / len(signals), 4)
        avg_payer = round(sum(s.payer_reward for s in signals) / len(signals), 4)

        avg_signal = RewardSignal(
            roas_reward=avg_roas,
            ctr_reward=avg_ctr,
            cvr_reward=avg_cvr,
            spend_reward=avg_spend,
            payer_reward=avg_payer,
            total_reward=avg_total,
            normalized_reward=avg_normalized,
        )

        # EMA 更新
        perf = pattern.performance
        new_reward = round(
            reward_before * (1 - self._ema_alpha) + avg_total * self._ema_alpha,
            4,
        )
        perf.avg_reward = new_reward
        perf.last_seen = self._now.isoformat()

        # 更新趋势
        perf.trend.append(avg_normalized)
        if len(perf.trend) > 20:
            perf.trend = perf.trend[-20:]

        # 更新元数据
        pattern.metadata["last_reward_update"] = {
            "timestamp": self._now.isoformat(),
            "samples": len(outcomes),
            "avg_total_reward": avg_total,
            "avg_normalized_reward": avg_normalized,
        }

        # 重新计算评分
        pattern.compute_score()

        return RewardUpdateResult(
            pattern_id=pattern.pattern_id,
            reward_before=round(reward_before, 4),
            reward_after=new_reward,
            signal=avg_signal,
            samples_added=len(outcomes),
            reason=f"Updated reward: {reward_before:.3f} → {new_reward:.3f} "
                   f"({len(outcomes)} outcomes, avg_total={avg_total:.3f})",
        )

    def _compute_metric_reward(self, delta: float, base_reward: float) -> float:
        """计算指标变化奖励.

        delta > 0 → 正奖励
        delta < 0 → 负奖励
        使用 sigmoid 平滑
        """
        if abs(delta) < self.MIN_DELTA_THRESHOLD:
            return 0.0
        # sigmoid: 2 / (1 + e^(-5x)) - 1, 映射到 [-1, 1]
        return base_reward * (2.0 / (1.0 + math.exp(-5.0 * delta)) - 1.0)

    def _compute_spend_reward(self, delta: float) -> float:
        """计算花费稳定性奖励.

        spend 小幅变化 (正负) 都算稳定，大幅变化给负奖励。
        """
        abs_delta = abs(delta)
        if abs_delta < self.MIN_DELTA_THRESHOLD:
            return 0.0
        if abs_delta < 0.10:  # 10% 以内 → 稳定
            return self.BASE_SPEND_REWARD
        if abs_delta < 0.30:  # 30% 以内 → 轻微不稳定
            return self.BASE_SPEND_REWARD * 0.5
        return -self.BASE_SPEND_REWARD * 0.5  # 大幅波动 → 负奖励

    @staticmethod
    def _extract_metrics_delta(outcome: Any) -> dict[str, float]:
        """从 outcome 提取指标变化."""
        if hasattr(outcome, "metrics_delta") and isinstance(outcome.metrics_delta, dict):
            return outcome.metrics_delta
        if hasattr(outcome, "to_dict"):
            d = outcome.to_dict()
            return d.get("metrics_delta", {})
        return {}

    @staticmethod
    def _is_failure(outcome: Any) -> bool:
        """判断执行结果是否失败."""
        if hasattr(outcome, "success"):
            return not outcome.success
        if hasattr(outcome, "outcome_level"):
            level = outcome.outcome_level
            if hasattr(level, "value"):
                return level.value in ("failure", "strong_failure")
        return False


# ═══════════════════════════════════════════════════════════════
# E13.6.3 PatternLifecycleManager — 生命周期管理
# ═══════════════════════════════════════════════════════════════


class PatternLifecycleState(str, Enum):
    """模式生命周期状态."""
    ACTIVE = "active"           # 活跃: 近期验证有效
    DECAYING = "decaying"       # 衰减中: 长期未验证或表现下降
    ARCHIVED = "archived"       # 已归档: 不再参与决策
    DEPRECATED = "deprecated"   # 已弃用: 环境变化导致不再适用


@dataclass
class LifecycleTransition:
    """生命周期迁移记录.

    Attributes:
        pattern_id: 模式ID
        from_state: 迁移前状态
        to_state: 迁移后状态
        trigger: 触发原因
        timestamp: 迁移时间
        metadata: 附加信息
    """
    pattern_id: str = ""
    from_state: PatternLifecycleState = PatternLifecycleState.ACTIVE
    to_state: PatternLifecycleState = PatternLifecycleState.ACTIVE
    trigger: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleReport:
    """生命周期管理报告.

    Attributes:
        timestamp: 执行时间
        patterns_checked: 检查的模式数
        transitions: 迁移记录
        active_count: 活跃模式数
        decaying_count: 衰减中模式数
        archived_count: 已归档模式数
        deprecated_count: 已弃用模式数
        summary: 摘要
    """
    timestamp: str = ""
    patterns_checked: int = 0
    transitions: list[LifecycleTransition] = field(default_factory=list)
    active_count: int = 0
    decaying_count: int = 0
    archived_count: int = 0
    deprecated_count: int = 0
    summary: str = ""


class PatternLifecycleManager:
    """E13.6 PatternLifecycleManager — 模式生命周期管理.

    核心机制:
      1. 状态机: ACTIVE → DECAYING → ARCHIVED
      2. 迁移条件基于: 时间、最近验证、成功率、衰减程度
      3. 被归档的模式不再参与决策

    状态迁移规则:
      ACTIVE → DECAYING:
        - 超过 30 天未验证
        - 或 最近成功率 < 历史成功率 × 0.5
        - 或 评分衰减至原始评分的 60% 以下

      DECAYING → ACTIVE:
        - 最近被重新验证且成功率 >= 历史成功率 × 0.7

      DECAYING → ARCHIVED:
        - 超过 60 天未验证
        - 或 评分衰减至原始评分的 30% 以下

      ACTIVE → DEPRECATED:
        - 市场条件发生根本性变化 (如 SKAN → 新框架)

    用法:
        manager = PatternLifecycleManager()
        transitions = manager.check_patterns(patterns)
        report = manager.get_lifecycle_report()
    """

    # 状态迁移阈值
    ACTIVE_TO_DECAYING_DAYS = 30        # 30天未验证 → DECAYING
    ACTIVE_TO_DECAYING_RATIO = 0.50     # 最近成功率 < 50% 历史 → DECAYING
    ACTIVE_TO_DECAYING_SCORE_RATIO = 0.60  # 评分衰减至 60% → DECAYING

    DECAYING_TO_ACTIVE_RATIO = 0.70     # 重新验证成功率 >= 70% → 恢复 ACTIVE

    DECAYING_TO_ARCHIVED_DAYS = 60      # 60天未验证 → ARCHIVED
    DECAYING_TO_ARCHIVED_SCORE_RATIO = 0.30  # 评分衰减至 30% → ARCHIVED

    def __init__(
        self,
        now: datetime | None = None,
        store: Any = None,  # PatternStore for state persistence
    ):
        self._now = now or datetime.now(timezone.utc)
        self._store = store
        self._transitions: list[LifecycleTransition] = []
        self._state_map: dict[str, PatternLifecycleState] = {}

    def check_pattern(
        self,
        pattern: PatternMemory,
        evaluation: EvaluationResult | None = None,
    ) -> LifecycleTransition | None:
        """检查单个模式的生命周期状态.

        Args:
            pattern: 要检查的模式
            evaluation: 可选的评估结果 (来自 PatternEvaluator)

        Returns:
            LifecycleTransition | None: 如果发生状态迁移则返回记录
        """
        current_state = self._get_state(pattern)
        transition = self._determine_transition(pattern, current_state, evaluation)

        if transition is None:
            return None

        # 记录迁移
        self._state_map[pattern.pattern_id] = transition.to_state
        self._transitions.append(transition)

        # 更新 pattern metadata
        pattern.metadata["lifecycle_state"] = transition.to_state.value
        pattern.metadata["lifecycle_transition"] = {
            "from": transition.from_state.value,
            "to": transition.to_state.value,
            "trigger": transition.trigger,
            "timestamp": transition.timestamp,
        }

        return transition

    def check_patterns(
        self,
        patterns: list[PatternMemory],
        evaluations: dict[str, EvaluationResult] | None = None,
    ) -> list[LifecycleTransition]:
        """批量检查模式生命周期.

        Args:
            patterns: 模式列表
            evaluations: pattern_id → EvaluationResult 映射

        Returns:
            list[LifecycleTransition]: 迁移记录列表
        """
        evals = evaluations or {}
        transitions = []
        for pattern in patterns:
            t = self.check_pattern(pattern, evals.get(pattern.pattern_id))
            if t is not None:
                transitions.append(t)
        return transitions

    def get_active_patterns(self, patterns: list[PatternMemory]) -> list[PatternMemory]:
        """获取所有活跃模式 (排除 ARCHIVED 和 DEPRECATED)."""
        return [
            p for p in patterns
            if self._get_state(p) not in (PatternLifecycleState.ARCHIVED, PatternLifecycleState.DEPRECATED)
        ]

    def get_lifecycle_report(self) -> LifecycleReport:
        """获取生命周期报告."""
        states: dict[str, int] = {}
        for state in self._state_map.values():
            states[state.value] = states.get(state.value, 0) + 1

        return LifecycleReport(
            timestamp=self._now.isoformat(),
            patterns_checked=len(self._state_map),
            transitions=list(self._transitions),
            active_count=states.get("active", 0),
            decaying_count=states.get("decaying", 0),
            archived_count=states.get("archived", 0),
            deprecated_count=states.get("deprecated", 0),
            summary=self._generate_summary(),
        )

    def _get_state(self, pattern: PatternMemory) -> PatternLifecycleState:
        """获取模式当前生命周期状态."""
        # 优先从 metadata 读取
        if pattern.pattern_id in self._state_map:
            return self._state_map[pattern.pattern_id]

        state_str = pattern.metadata.get("lifecycle_state", "active")
        try:
            return PatternLifecycleState(state_str)
        except ValueError:
            return PatternLifecycleState.ACTIVE

    def _determine_transition(
        self,
        pattern: PatternMemory,
        current_state: PatternLifecycleState,
        evaluation: EvaluationResult | None,
    ) -> LifecycleTransition | None:
        """判断是否需要状态迁移."""
        perf = pattern.performance
        days_since = self._days_since(perf.last_seen) if perf.last_seen else None

        # 计算评分衰减比例
        initial_score = pattern.metadata.get("initial_score", pattern.score or 0.5)
        score_ratio = pattern.score / max(initial_score, 0.01) if initial_score > 0 else 1.0

        if current_state == PatternLifecycleState.ACTIVE:
            # ACTIVE → DECAYING
            if days_since is not None and days_since > self.ACTIVE_TO_DECAYING_DAYS:
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.DECAYING,
                    trigger=f"Unused for {days_since:.0f}d",
                    timestamp=self._now.isoformat(),
                    metadata={"days_since": days_since},
                )

            if score_ratio < self.ACTIVE_TO_DECAYING_SCORE_RATIO:
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.DECAYING,
                    trigger=f"Score decayed to {score_ratio:.1%} of initial",
                    timestamp=self._now.isoformat(),
                    metadata={"score_ratio": score_ratio},
                )

            if evaluation and evaluation.effectiveness in (
                PatternEffectiveness.FAILING,
                PatternEffectiveness.EXPIRED,
            ):
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.DECAYING,
                    trigger=f"Evaluation: {evaluation.effectiveness.value}",
                    timestamp=self._now.isoformat(),
                    metadata={"evaluation": evaluation.reason},
                )

        elif current_state == PatternLifecycleState.DECAYING:
            # DECAYING → ACTIVE (恢复)
            if evaluation and evaluation.effectiveness in (
                PatternEffectiveness.STRONG,
                PatternEffectiveness.MAINTAINING,
            ):
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.ACTIVE,
                    trigger=f"Re-validated: {evaluation.effectiveness.value}",
                    timestamp=self._now.isoformat(),
                    metadata={"evaluation": evaluation.reason},
                )

            # DECAYING → ARCHIVED
            if days_since is not None and days_since > self.DECAYING_TO_ARCHIVED_DAYS:
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.ARCHIVED,
                    trigger=f"Unused for {days_since:.0f}d",
                    timestamp=self._now.isoformat(),
                    metadata={"days_since": days_since},
                )

            if score_ratio < self.DECAYING_TO_ARCHIVED_SCORE_RATIO:
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.ARCHIVED,
                    trigger=f"Score decayed to {score_ratio:.1%} of initial",
                    timestamp=self._now.isoformat(),
                    metadata={"score_ratio": score_ratio},
                )

        elif current_state == PatternLifecycleState.ARCHIVED:
            # ARCHIVED → ACTIVE (需要强证据)
            if evaluation and evaluation.effectiveness == PatternEffectiveness.STRONG:
                return LifecycleTransition(
                    pattern_id=pattern.pattern_id,
                    from_state=current_state,
                    to_state=PatternLifecycleState.ACTIVE,
                    trigger=f"Strong re-validation from archived",
                    timestamp=self._now.isoformat(),
                    metadata={"evaluation": evaluation.reason},
                )

        return None

    def _days_since(self, iso_str: str) -> float | None:
        """计算从 iso_str 到现在的天数."""
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return (self._now - ts).total_seconds() / 86400.0
        except (ValueError, AttributeError):
            return None

    def _generate_summary(self) -> str:
        """生成摘要."""
        states: dict[str, int] = {}
        for state in self._state_map.values():
            states[state.value] = states.get(state.value, 0) + 1

        lines = [
            "-" * 45,
            f"  Pattern Lifecycle Report — {self._now.isoformat()[:19]}",
            "-" * 45,
            f"  Active:     {states.get('active', 0):>4d}",
            f"  Decaying:   {states.get('decaying', 0):>4d}",
            f"  Archived:   {states.get('archived', 0):>4d}",
            f"  Deprecated: {states.get('deprecated', 0):>4d}",
            "-" * 45,
        ]

        if self._transitions:
            recent = self._transitions[-5:]
            lines.append(f"  Recent Transitions:")
            for t in recent:
                lines.append(f"    {t.pattern_id[:8]}: {t.from_state.value} → {t.to_state.value} "
                             f"({t.trigger})")

        lines.append("-" * 45)
        return "\n".join(lines)