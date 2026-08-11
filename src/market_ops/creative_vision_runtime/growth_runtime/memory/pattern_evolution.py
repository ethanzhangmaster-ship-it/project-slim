"""E13.6 Pattern Evolution Engine — 模式进化引擎.

让 PatternMemory 从静态记忆升级为动态演化模型，实现:
  - E13.6.1 Pattern Scoring: 多维度综合评分 (novelty + recency + quality)
  - E13.6.2 Pattern Decay: 时间衰减 + 市场条件敏感度
  - E13.6.3 Pattern Reinforcement: 贝叶斯更新 + 重复验证增强
  - E13.6.4 Pattern Conflict Resolver: 冲突检测 + 上下文分裂
  - E13.6.5 Adaptive Memory Controller: 进化编排 + 报告生成

与 E13.4.5 MemoryEvolution 的区别:
  - MemoryEvolution: 跨层进化 (Pattern + Strategy + Failure)
  - PatternEvolution: Pattern 专属精细演化 (评分/衰减/强化/冲突)
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import (
    PatternCondition,
    PatternMemory,
    PatternPerformance,
    PatternQuality,
)


# ═══════════════════════════════════════════════════════════════
# E13.6.1 Pattern Scoring
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternScore:
    """模式评分分解 — 多维度评分结果.

    Attributes:
        base_score: 基础评分 (sample × success_rate × reward)
        novelty_score: 新颖度评分 (最近发现 vs 很久以前)
        recency_score: 时效性评分 (最近验证 vs 长期未验证)
        quality_score: 质量评分 (样本质量 + 趋势一致性)
        stability_score: 稳定性评分 (标准差 + 趋势平稳度)
        composite_score: 综合评分 (加权组合)
        confidence: 置信度
        grade: 评分等级 (A/B/C/D/F)
    """
    base_score: float = 0.0
    novelty_score: float = 0.0
    recency_score: float = 0.0
    quality_score: float = 0.0
    stability_score: float = 0.0
    composite_score: float = 0.0
    confidence: float = 0.0
    grade: str = "F"

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_score": self.base_score,
            "novelty_score": self.novelty_score,
            "recency_score": self.recency_score,
            "quality_score": self.quality_score,
            "stability_score": self.stability_score,
            "composite_score": self.composite_score,
            "confidence": self.confidence,
            "grade": self.grade,
        }


class PatternScorer:
    """E13.6.1 Pattern Scoring — 多维度模式评分.

    评分维度:
      1. Base Score: 基础统计 (sample_factor × success_rate × avg_reward × confidence)
      2. Novelty Score: 新颖度 (最近发现 vs 很久以前)
      3. Recency Score: 时效性 (最近验证 vs 长期未验证)
      4. Quality Score: 质量 (样本量充足 + 趋势一致性)
      5. Stability Score: 稳定性 (标准差低 + 趋势平稳)

    综合评分 = 0.35×base + 0.15×novelty + 0.20×recency + 0.15×quality + 0.15×stability

    用法:
        scorer = PatternScorer()
        result = scorer.score(pattern)
        print(f"Grade: {result.grade}, Score: {result.composite_score}")
    """

    # 维度权重
    WEIGHTS = {
        "base": 0.35,
        "novelty": 0.15,
        "recency": 0.20,
        "quality": 0.15,
        "stability": 0.15,
    }

    # 评分等级阈值
    GRADE_THRESHOLDS = {
        "A": 0.80,
        "B": 0.60,
        "C": 0.40,
        "D": 0.20,
        "F": 0.0,
    }

    def __init__(self, now: datetime | None = None):
        self._now = now or datetime.now(timezone.utc)

    def score(self, pattern: PatternMemory) -> PatternScore:
        """计算模式的多维度评分.

        Args:
            pattern: PatternMemory 实例

        Returns:
            PatternScore: 多维度评分结果
        """
        perf = pattern.performance

        # 1. Base Score
        base = self._compute_base_score(perf)

        # 2. Novelty Score
        novelty = self._compute_novelty_score(pattern)

        # 3. Recency Score
        recency = self._compute_recency_score(perf)

        # 4. Quality Score
        quality = self._compute_quality_score(perf)

        # 5. Stability Score
        stability = self._compute_stability_score(perf)

        # 综合评分
        w = self.WEIGHTS
        composite = round(
            w["base"] * base
            + w["novelty"] * novelty
            + w["recency"] * recency
            + w["quality"] * quality
            + w["stability"] * stability,
            4,
        )

        # 置信度
        confidence = round(
            self._sample_factor(perf.samples) * perf.success_rate,
            4,
        )

        # 等级
        grade = self._assign_grade(composite)

        result = PatternScore(
            base_score=round(base, 4),
            novelty_score=round(novelty, 4),
            recency_score=round(recency, 4),
            quality_score=round(quality, 4),
            stability_score=round(stability, 4),
            composite_score=composite,
            confidence=confidence,
            grade=grade,
        )

        # 回写到 pattern
        pattern.score = composite
        pattern.confidence = confidence

        return result

    def _compute_base_score(self, perf: PatternPerformance) -> float:
        """基础评分: sample_factor × success_rate × avg_reward × confidence."""
        if perf.samples == 0:
            return 0.0
        sf = self._sample_factor(perf.samples)
        return round(sf * perf.success_rate * max(perf.avg_reward, 0.01) * (0.5 + 0.5 * perf.success_rate), 4)

    def _compute_novelty_score(self, pattern: PatternMemory) -> float:
        """新颖度评分: 首次发现时间越近，新颖度越高.

        使用指数衰减: score = exp(-days_since_first / 30)
        """
        if not pattern.performance.first_seen:
            # 使用 created_at 作为 fallback
            ts = pattern.created_at
        else:
            ts = pattern.performance.first_seen

        days = self._days_since(ts)
        if days is None:
            return 0.5  # 无法解析时间，默认中等
        return round(math.exp(-days / 60.0), 4)  # 60天半衰期

    def _compute_recency_score(self, perf: PatternPerformance) -> float:
        """时效性评分: 最近验证时间越近，时效性越高.

        使用指数衰减: score = exp(-days_since_last / 14)
        14天半衰期，强调近期验证
        """
        if not perf.last_seen:
            return 0.0
        days = self._days_since(perf.last_seen)
        if days is None:
            return 0.0
        return round(math.exp(-days / 14.0), 4)

    def _compute_quality_score(self, perf: PatternPerformance) -> float:
        """质量评分: 样本量充足 + 趋势一致性.

        样本量因子: 对数平滑
        趋势因子: 趋势越稳定，质量越高
        """
        sf = self._sample_factor(perf.samples)

        # 趋势一致性: 最近趋势的方差
        trend_factor = 1.0
        if perf.trend and len(perf.trend) >= 3:
            avg = sum(perf.trend) / len(perf.trend)
            variance = sum((t - avg) ** 2 for t in perf.trend) / len(perf.trend)
            trend_factor = max(0.2, 1.0 - math.sqrt(variance) * 2.0)

        return round(sf * trend_factor, 4)

    def _compute_stability_score(self, perf: PatternPerformance) -> float:
        """稳定性评分: 标准差低 + 趋势平稳.

        std_reward 越低 → 稳定性越高
        """
        if perf.std_reward == 0.0:
            # 单样本，默认中等稳定性
            return 0.5 if perf.samples <= 1 else 0.7

        # 标准差相对平均值
        if perf.avg_reward > 0:
            cv = perf.std_reward / perf.avg_reward  # 变异系数
            stability = max(0.1, 1.0 - cv)
        else:
            stability = 0.3

        return round(stability, 4)

    @staticmethod
    def _sample_factor(samples: int) -> float:
        """样本量因子: 对数平滑."""
        if samples == 0:
            return 0.0
        return min(1.0, math.log(samples + 1) / math.log(100))

    def _days_since(self, iso_str: str) -> float | None:
        """计算从 iso_str 到现在的天数."""
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return (self._now - ts).total_seconds() / 86400.0
        except (ValueError, AttributeError):
            return None

    def _assign_grade(self, score: float) -> str:
        """按阈值分配等级."""
        for grade, threshold in sorted(self.GRADE_THRESHOLDS.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return grade
        return "F"


# ═══════════════════════════════════════════════════════════════
# E13.6.2 Pattern Decay
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecayResult:
    """衰减结果.

    Attributes:
        pattern_id: 模式ID
        score_before: 衰减前评分
        score_after: 衰减后评分
        decay_factor: 衰减因子
        days_since_last: 距上次验证天数
        market_change_factor: 市场变化因子
        reason: 衰减原因
    """
    pattern_id: str = ""
    score_before: float = 0.0
    score_after: float = 0.0
    decay_factor: float = 0.0
    days_since_last: float = 0.0
    market_change_factor: float = 0.0
    reason: str = ""


class PatternDecayEngine:
    """E13.6.2 Pattern Decay — 时间衰减引擎.

    核心机制:
      1. 时间衰减: 距上次验证越久，评分越低
      2. 市场敏感度: 如果市场条件发生变化，加速衰减
      3. 衰减保护: 评分不会低于原始评分的 max_decay 比例

    衰减公式:
      decay_factor = time_decay × market_sensitivity
      new_score = original_score × (1 - decay_factor)
      new_score = max(new_score, original_score × (1 - max_decay))

    用法:
        engine = PatternDecayEngine()
        results = engine.apply_decay(patterns)
    """

    # 衰减参数
    DEFAULT_DECAY_RATE_PER_DAY = 0.005      # 每天 0.5%
    DEFAULT_GRACE_DAYS = 7                   # 宽限期: 7天内不衰减
    DEFAULT_MAX_DECAY = 0.50                 # 最大衰减: 评分不低于原始的 50%
    DEFAULT_MARKET_SENSITIVITY = 0.3         # 市场变化敏感度

    def __init__(
        self,
        decay_rate_per_day: float = DEFAULT_DECAY_RATE_PER_DAY,
        grace_days: int = DEFAULT_GRACE_DAYS,
        max_decay: float = DEFAULT_MAX_DECAY,
        market_sensitivity: float = DEFAULT_MARKET_SENSITIVITY,
        now: datetime | None = None,
    ):
        self._decay_rate = decay_rate_per_day
        self._grace_days = grace_days
        self._max_decay = max_decay
        self._market_sensitivity = market_sensitivity
        self._now = now or datetime.now(timezone.utc)

    def apply_decay(
        self,
        patterns: list[PatternMemory],
        market_conditions: dict[str, tuple[float, float]] | None = None,
    ) -> list[DecayResult]:
        """对所有模式应用时间衰减.

        Args:
            patterns: 模式列表
            market_conditions: 当前市场条件 (用于市场敏感度计算)

        Returns:
            list[DecayResult]: 衰减结果列表
        """
        results: list[DecayResult] = []
        for pattern in patterns:
            result = self._decay_one(pattern, market_conditions)
            if result is not None:
                results.append(result)
        return results

    def _decay_one(
        self,
        pattern: PatternMemory,
        market_conditions: dict[str, tuple[float, float]] | None,
    ) -> DecayResult | None:
        """对单个模式应用衰减."""
        if not pattern.performance.last_seen:
            return None

        days = self._days_since(pattern.performance.last_seen)
        if days is None or days <= self._grace_days:
            return None  # 宽限期内，不衰减

        effective_days = days - self._grace_days

        # 时间衰减
        time_decay = min(1.0, self._decay_rate * effective_days)

        # 市场敏感度: 如果当前市场条件与模式记录的市场条件差异大，加速衰减
        market_factor = 1.0
        if market_conditions and pattern.condition.market_conditions:
            market_factor = self._compute_market_divergence(
                market_conditions,
                pattern.condition.market_conditions,
            )

        # 综合衰减因子
        decay_factor = min(1.0, time_decay * (1.0 + self._market_sensitivity * (market_factor - 1.0)))

        # 计算新评分
        old_score = pattern.score if pattern.score > 0 else (pattern.performance.success_rate or 0.5)
        min_score = old_score * (1.0 - self._max_decay)
        new_score = round(max(min_score, old_score * (1.0 - decay_factor)), 4)

        # 更新 pattern
        score_before = pattern.score
        pattern.score = new_score

        return DecayResult(
            pattern_id=pattern.pattern_id,
            score_before=round(score_before, 4),
            score_after=new_score,
            decay_factor=round(decay_factor, 4),
            days_since_last=round(days, 1),
            market_change_factor=round(market_factor, 4),
            reason=self._build_decay_reason(days, decay_factor, market_factor),
        )

    def _compute_market_divergence(
        self,
        current: dict[str, tuple[float, float]],
        historical: dict[str, tuple[float, float]],
    ) -> float:
        """计算市场条件差异度 [1.0 = 完全一致, >1.0 = 有差异].

        差异越大，衰减越快。
        """
        common_keys = set(current.keys()) & set(historical.keys())
        if not common_keys:
            return 1.0  # 无可比较维度，无额外衰减

        divergences: list[float] = []
        for key in common_keys:
            cur_low, cur_high = current[key]
            hist_low, hist_high = historical[key]
            cur_mid = (cur_low + cur_high) / 2
            hist_mid = (hist_low + hist_high) / 2
            hist_range = (hist_high - hist_low) or 0.01
            # 归一化差异
            divergence = abs(cur_mid - hist_mid) / hist_range
            divergences.append(divergence)

        # 平均差异 + 1.0 作为倍增因子
        avg_div = sum(divergences) / len(divergences)
        return 1.0 + avg_div

    def _days_since(self, iso_str: str) -> float | None:
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return (self._now - ts).total_seconds() / 86400.0
        except (ValueError, AttributeError):
            return None

    def _build_decay_reason(self, days: float, decay_factor: float, market_factor: float) -> str:
        parts = [f"Decay after {days:.0f}d unused"]
        if market_factor > 1.1:
            parts.append(f"market divergence {market_factor:.2f}x")
        parts.append(f"decay={decay_factor:.2%}")
        return "; ".join(parts)


# ═══════════════════════════════════════════════════════════════
# E13.6.3 Pattern Reinforcement
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReinforcementResult:
    """强化结果.

    Attributes:
        pattern_id: 模式ID
        success_before: 强化前成功率
        success_after: 强化后成功率
        confidence_before: 强化前置信度
        confidence_after: 强化后置信度
        samples_added: 新增样本数
        success_added: 新增成功数
        boost_applied: 置信度提升值
        reinforcement_count: 累计强化次数
        reason: 强化原因
    """
    pattern_id: str = ""
    success_before: float = 0.0
    success_after: float = 0.0
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    samples_added: int = 0
    success_added: int = 0
    boost_applied: float = 0.0
    reinforcement_count: int = 0
    reason: str = ""


class PatternReinforcer:
    """E13.6.3 Pattern Reinforcement — 模式强化引擎.

    核心机制:
      1. 贝叶斯更新: 新证据通过贝叶斯方式更新成功率
      2. 重复验证增强: 同一模式被多次验证，置信度递增
      3. 趋势追踪: 维护最近N次验证的趋势

    贝叶斯更新公式:
      alpha' = alpha + new_successes
      beta' = beta + new_failures
      posterior_success_rate = alpha' / (alpha' + beta')

    重复验证增强:
      boost = min(MAX_BOOST, BASE_BOOST × reinforcement_count)
      confidence = min(1.0, base_confidence + boost)

    用法:
        reinforcer = PatternReinforcer()
        result = reinforcer.reinforce(pattern, new_successes=8, new_total=10)
    """

    # 贝叶斯先验参数
    DEFAULT_ALPHA_PRIOR = 2.0   # 先验成功 (等效2次成功)
    DEFAULT_BETA_PRIOR = 2.0    # 先验失败 (等效2次失败)

    # 强化参数
    BASE_BOOST = 0.05            # 每次验证基础提升
    MAX_BOOST = 0.30             # 最大总提升

    def __init__(
        self,
        alpha_prior: float = DEFAULT_ALPHA_PRIOR,
        beta_prior: float = DEFAULT_BETA_PRIOR,
        base_boost: float = BASE_BOOST,
        max_boost: float = MAX_BOOST,
    ):
        self._alpha_prior = alpha_prior
        self._beta_prior = beta_prior
        self._base_boost = base_boost
        self._max_boost = max_boost

    def reinforce(
        self,
        pattern: PatternMemory,
        new_successes: int,
        new_total: int,
    ) -> ReinforcementResult | None:
        """用新证据强化模式.

        Args:
            pattern: 要强化的模式
            new_successes: 新增成功数
            new_total: 新增总样本数

        Returns:
            ReinforcementResult | None: 强化结果
        """
        if new_total <= 0:
            return None

        new_failures = new_total - new_successes
        perf = pattern.performance

        # 保存强化前状态
        success_before = perf.success_rate
        conf_before = pattern.confidence

        # 贝叶斯更新
        prior_alpha = perf.success_count + self._alpha_prior
        prior_beta = (perf.samples - perf.success_count) + self._beta_prior

        posterior_alpha = prior_alpha + new_successes
        posterior_beta = prior_beta + new_failures
        posterior_rate = posterior_alpha / (posterior_alpha + posterior_beta)

        # 更新pattern
        perf.samples += new_total
        perf.success_count += new_successes
        perf.success_rate = round(posterior_rate, 4)
        perf.last_seen = datetime.now(timezone.utc).isoformat()

        # 更新趋势
        new_obs_rate = new_successes / new_total
        perf.trend.append(round(new_obs_rate, 4))
        if len(perf.trend) > 20:
            perf.trend = perf.trend[-20:]

        # 重复验证增强
        reinforcement_count = pattern.metadata.get("reinforcement_count", 0) + 1
        pattern.metadata["reinforcement_count"] = reinforcement_count
        pattern.metadata["last_reinforced_at"] = datetime.now(timezone.utc).isoformat()

        # 置信度提升
        boost = min(self._max_boost, self._base_boost * reinforcement_count)
        pattern.confidence = round(min(1.0, conf_before + boost), 4)

        # 更新评分
        pattern.compute_score()

        return ReinforcementResult(
            pattern_id=pattern.pattern_id,
            success_before=round(success_before, 4),
            success_after=round(posterior_rate, 4),
            confidence_before=round(conf_before, 4),
            confidence_after=round(pattern.confidence, 4),
            samples_added=new_total,
            success_added=new_successes,
            boost_applied=round(boost, 4),
            reinforcement_count=reinforcement_count,
            reason=f"Reinforced #{reinforcement_count}: {new_successes}/{new_total} successes, "
                    f"success_rate {success_before:.2%}→{posterior_rate:.2%}",
        )

    def contradict(
        self,
        pattern: PatternMemory,
        new_failures: int,
        new_total: int,
    ) -> ReinforcementResult:
        """用矛盾证据削弱模式 (失败的验证).

        与 reinforce 相同逻辑，但 boost 为负。
        """
        result = self.reinforce(pattern, new_total - new_failures, new_total)
        if result:
            result.boost_applied = round(-self._base_boost, 4)
            result.reason = result.reason.replace("Reinforced", "Contradicted")
        return result


# ═══════════════════════════════════════════════════════════════
# E13.6.4 Pattern Conflict Resolver
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConflictPair:
    """冲突对 — 两个矛盾的模式.

    Attributes:
        pattern_a: 模式A
        pattern_b: 模式B
        similarity: 条件相似度
        action_difference: 动作差异说明
        severity: 冲突严重程度 (high/medium/low)
    """
    pattern_a: PatternMemory = field(default_factory=PatternMemory)
    pattern_b: PatternMemory = field(default_factory=PatternMemory)
    similarity: float = 0.0
    action_difference: str = ""
    severity: str = "low"


@dataclass
class ConflictResolution:
    """冲突解决结果.

    Attributes:
        conflict: 冲突对
        resolution_type: 解决类型 (split/merge/keep_best/require_context)
        refined_patterns: 拆分后的细化子模式
        recommendation: 决策建议
        reason: 解决原因
    """
    conflict: ConflictPair = field(default_factory=ConflictPair)
    resolution_type: str = "keep_best"
    refined_patterns: list[PatternMemory] = field(default_factory=list)
    recommendation: str = ""
    reason: str = ""


class PatternConflictResolver:
    """E13.6.4 Pattern Conflict Resolver — 模式冲突解决器.

    核心机制:
      1. 冲突检测: 相同条件但不同动作的模式对
      2. 上下文分析: 找出区分两个模式的关键上下文维度
      3. 冲突解决策略:
         a. split: 按上下文维度拆分为子模式
         b. merge: 如果差异不大，合并为复合策略
         c. keep_best: 保留成功率更高的
         d. require_context: 标记需要更多上下文信息

    用法:
        resolver = PatternConflictResolver()
        conflicts = resolver.detect_conflicts(patterns)
        for conflict in conflicts:
            resolution = resolver.resolve(conflict)
    """

    # 冲突检测参数
    DEFAULT_SIMILARITY_THRESHOLD = 0.60   # 相似度阈值
    DEFAULT_MIN_SAMPLES = 5               # 最少样本数
    DEFAULT_MIN_SEVERITY_DIFF = 0.15      # 最小成功率差异

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        min_severity_diff: float = DEFAULT_MIN_SEVERITY_DIFF,
    ):
        self._similarity_threshold = similarity_threshold
        self._min_samples = min_samples
        self._min_severity_diff = min_severity_diff

    def detect_conflicts(
        self,
        patterns: list[PatternMemory],
    ) -> list[ConflictPair]:
        """检测所有冲突模式对.

        Args:
            patterns: 模式列表

        Returns:
            list[ConflictPair]: 冲突对列表
        """
        conflicts: list[ConflictPair] = []
        n = len(patterns)

        for i in range(n):
            for j in range(i + 1, n):
                pa = patterns[i]
                pb = patterns[j]

                # 跳过样本不足的
                if pa.performance.samples < self._min_samples:
                    continue
                if pb.performance.samples < self._min_samples:
                    continue

                # 条件相似度
                similarity = self._compute_condition_similarity(pa.condition, pb.condition)

                if similarity < self._similarity_threshold:
                    continue

                # 动作不同且有显著成功率差异
                if pa.action.action_type == pb.action.action_type:
                    continue

                success_diff = abs(pa.performance.success_rate - pb.performance.success_rate)
                if success_diff < self._min_severity_diff:
                    continue

                # 确定严重程度
                severity = "high" if similarity >= 0.80 else ("medium" if similarity >= 0.70 else "low")

                conflicts.append(ConflictPair(
                    pattern_a=pa,
                    pattern_b=pb,
                    similarity=round(similarity, 4),
                    action_difference=f"{pa.action.action_type} vs {pb.action.action_type}",
                    severity=severity,
                ))

        return conflicts

    def resolve(self, conflict: ConflictPair) -> ConflictResolution:
        """解决一对冲突模式.

        Args:
            conflict: 冲突对

        Returns:
            ConflictResolution: 解决结果
        """
        pa = conflict.pattern_a
        pb = conflict.pattern_b

        # 策略选择
        # 1. 如果两个模式的成功率差异很大 (>30%)，保留最好的
        if abs(pa.performance.success_rate - pb.performance.success_rate) > 0.30:
            return self._resolve_keep_best(conflict)

        # 2. 如果能找到上下文区分维度，拆分
        context_dim = self._find_context_differentiator(pa.condition, pb.condition)
        if context_dim:
            return self._resolve_split(conflict, context_dim)

        # 3. 如果样本量足够且相似度高，标记需要更多上下文
        return self._resolve_require_context(conflict)

    def _resolve_keep_best(self, conflict: ConflictPair) -> ConflictResolution:
        """保留成功率更高的模式."""
        pa = conflict.pattern_a
        pb = conflict.pattern_b
        better = pa if pa.performance.success_rate >= pb.performance.success_rate else pb
        worse = pb if better is pa else pa

        return ConflictResolution(
            conflict=conflict,
            resolution_type="keep_best",
            refined_patterns=[better],
            recommendation=f"Prefer {better.action.action_type} "
                           f"(success_rate={better.performance.success_rate:.2%} "
                           f"vs {worse.performance.success_rate:.2%})",
            reason=f"Success rate difference >30%: "
                   f"{better.action.action_type} significantly outperforms {worse.action.action_type}",
        )

    def _resolve_split(
        self,
        conflict: ConflictPair,
        context_dim: str,
    ) -> ConflictResolution:
        """按上下文维度拆分为子模式."""
        pa = conflict.pattern_a
        pb = conflict.pattern_b

        # 克隆两个模式，添加上下文区分
        refined_a = PatternMemory(
            pattern_id=f"{pa.pattern_id}_ctx_{context_dim}",
            dimension=pa.dimension,
            condition=pa.condition,
            action=pa.action,
            performance=pa.performance,
            score=pa.score,
            confidence=pa.confidence,
            metadata={**pa.metadata, "conflict_context": context_dim, "parent_pattern": pa.pattern_id},
        )
        refined_b = PatternMemory(
            pattern_id=f"{pb.pattern_id}_ctx_{context_dim}",
            dimension=pb.dimension,
            condition=pb.condition,
            action=pb.action,
            performance=pb.performance,
            score=pb.score,
            confidence=pb.confidence,
            metadata={**pb.metadata, "conflict_context": context_dim, "parent_pattern": pb.pattern_id},
        )

        return ConflictResolution(
            conflict=conflict,
            resolution_type="split",
            refined_patterns=[refined_a, refined_b],
            recommendation=f"Use {pa.action.action_type} when {context_dim} matches pattern A, "
                           f"use {pb.action.action_type} when {context_dim} matches pattern B",
            reason=f"Context dimension '{context_dim}' differentiates the two patterns",
        )

    def _resolve_require_context(self, conflict: ConflictPair) -> ConflictResolution:
        """标记需要更多上下文信息."""
        pa = conflict.pattern_a
        pb = conflict.pattern_b

        return ConflictResolution(
            conflict=conflict,
            resolution_type="require_context",
            refined_patterns=[pa, pb],
            recommendation=f"Need more context to decide between {pa.action.action_type} "
                           f"and {pb.action.action_type}. "
                           f"Consider LTV, payer_rate, or market conditions.",
            reason="Both patterns have similar success rates; additional context dimensions needed",
        )

    def _compute_condition_similarity(
        self,
        ca: PatternCondition,
        cb: PatternCondition,
    ) -> float:
        """计算两个条件的相似度."""
        score = 0.0
        total = 0.0

        checks = [
            ("opportunity_type", 0.3, ca.opportunity_type, cb.opportunity_type),
            ("category", 0.15, ca.category, cb.category),
            ("audience_segment", 0.20, ca.audience_segment, cb.audience_segment),
            ("product_category", 0.15, ca.product_category, cb.product_category),
            ("entity_type", 0.10, ca.entity_type, cb.entity_type),
        ]

        for name, weight, va, vb in checks:
            total += weight
            if va and vb and va == vb:
                score += weight

        # Signal types: Jaccard
        if ca.signal_types and cb.signal_types:
            total += 0.10
            set_a = set(ca.signal_types)
            set_b = set(cb.signal_types)
            jaccard = len(set_a & set_b) / len(set_a | set_b) if set_a | set_b else 0
            score += 0.10 * jaccard

        return round(score / total, 4) if total > 0 else 0.0

    def _find_context_differentiator(
        self,
        ca: PatternCondition,
        cb: PatternCondition,
    ) -> str | None:
        """找出能区分两个条件的上下文维度."""
        if ca.audience_segment and cb.audience_segment and ca.audience_segment != cb.audience_segment:
            return "audience_segment"
        if ca.product_category and cb.product_category and ca.product_category != cb.product_category:
            return "product_category"
        if ca.category and cb.category and ca.category != cb.category:
            return "category"
        if ca.signal_types and cb.signal_types:
            set_a = set(ca.signal_types)
            set_b = set(cb.signal_types)
            only_a = set_a - set_b
            only_b = set_b - set_a
            if only_a or only_b:
                return "signal_types"
        return None


# ═══════════════════════════════════════════════════════════════
# E13.6.5 Adaptive Memory Controller
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvolutionReport:
    """E13.6.5 进化周期报告.

    Attributes:
        cycle_id: 周期ID
        timestamp: 执行时间
        patterns_scored: 重新评分的模式数
        patterns_decayed: 衰减的模式数
        patterns_reinforced: 强化的模式数
        conflicts_detected: 检测到的冲突数
        conflicts_resolved: 解决的冲突数
        patterns_removed: 移除的模式数
        avg_score_before: 进化前平均评分
        avg_score_after: 进化后平均评分
        score_improvement: 评分变化
        grade_distribution: 评分等级分布
        decay_results: 衰减详情
        reinforcement_results: 强化详情
        conflict_resolutions: 冲突解决详情
        summary: 人类可读摘要
    """
    cycle_id: str = ""
    timestamp: str = ""
    patterns_scored: int = 0
    patterns_decayed: int = 0
    patterns_reinforced: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    patterns_removed: int = 0
    avg_score_before: float = 0.0
    avg_score_after: float = 0.0
    score_improvement: float = 0.0
    grade_distribution: dict[str, int] = field(default_factory=dict)
    decay_results: list[DecayResult] = field(default_factory=list)
    reinforcement_results: list[ReinforcementResult] = field(default_factory=list)
    conflict_resolutions: list[ConflictResolution] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "patterns_scored": self.patterns_scored,
            "patterns_decayed": self.patterns_decayed,
            "patterns_reinforced": self.patterns_reinforced,
            "conflicts_detected": self.conflicts_detected,
            "conflicts_resolved": self.conflicts_resolved,
            "patterns_removed": self.patterns_removed,
            "avg_score_before": self.avg_score_before,
            "avg_score_after": self.avg_score_after,
            "score_improvement": self.score_improvement,
            "grade_distribution": self.grade_distribution,
            "summary": self.summary,
        }

    def has_evolution(self) -> bool:
        return (self.patterns_decayed + self.patterns_reinforced
                + self.conflicts_resolved + self.patterns_removed) > 0


class AdaptiveMemoryController:
    """E13.6.5 Adaptive Memory Controller — 自适应记忆控制器.

    编排 E13.6.1-6.4 的所有演化操作，形成完整的进化周期。

    进化周期:
      1. Score: 对所有模式重新评分
      2. Decay: 对过期模式应用衰减
      3. Reinforce: 用新经验强化已有模式
      4. Resolve Conflicts: 检测并解决冲突
      5. Cleanup: 移除低于阈值的模式
      6. Report: 生成进化报告

    用法:
        store = PatternStore()
        controller = AdaptiveMemoryController(store)
        controller.evolve()                        # 运行完整进化周期
        report = controller.evolve(experiences)    # 带新经验的进化
        print(report.summary)
    """

    # 清理阈值
    MIN_SCORE_TO_KEEP = 0.05       # 低于此评分的模式会被移除
    MIN_SAMPLES_TO_KEEP = 1        # 低于此样本数的模式会被移除 (如果同时评分低)

    def __init__(
        self,
        store: Any,  # PatternStore
        scorer: PatternScorer | None = None,
        decay_engine: PatternDecayEngine | None = None,
        reinforcer: PatternReinforcer | None = None,
        conflict_resolver: PatternConflictResolver | None = None,
        now: datetime | None = None,
    ):
        self._store = store
        self._scorer = scorer or PatternScorer(now=now)
        self._decay_engine = decay_engine or PatternDecayEngine(now=now)
        self._reinforcer = reinforcer or PatternReinforcer()
        self._conflict_resolver = conflict_resolver or PatternConflictResolver()
        self._now = now or datetime.now(timezone.utc)

        # 进化历史
        self._reports: list[EvolutionReport] = []

    def evolve(
        self,
        new_experiences: list[Any] | None = None,
        market_conditions: dict[str, tuple[float, float]] | None = None,
    ) -> EvolutionReport:
        """运行完整进化周期.

        Args:
            new_experiences: 新经验列表 (用于强化)
            market_conditions: 当前市场条件 (用于衰减)

        Returns:
            EvolutionReport: 进化周期报告
        """
        report = EvolutionReport(
            cycle_id=str(uuid.uuid4())[:8],
            timestamp=self._now.isoformat(),
        )
        patterns = self._store.get_all()

        if not patterns:
            report.summary = "No patterns to evolve."
            return report

        # 记录进化前状态
        scores_before = [p.score for p in patterns if p.score > 0]
        report.avg_score_before = round(sum(scores_before) / len(scores_before), 4) if scores_before else 0.0

        # Step 1: Score — 重新评分
        for pattern in patterns:
            self._scorer.score(pattern)
        report.patterns_scored = len(patterns)

        # Step 2: Decay — 时间衰减
        decay_results = self._decay_engine.apply_decay(patterns, market_conditions)
        report.decay_results = decay_results
        report.patterns_decayed = len(decay_results)

        # Step 3: Reinforce — 新经验强化
        if new_experiences:
            reinforcement_results = self._apply_reinforcement(patterns, new_experiences)
            report.reinforcement_results = reinforcement_results
            report.patterns_reinforced = len(reinforcement_results)

        # Step 4: Resolve Conflicts — 冲突解决
        conflicts = self._conflict_resolver.detect_conflicts(patterns)
        report.conflicts_detected = len(conflicts)
        for conflict in conflicts:
            resolution = self._conflict_resolver.resolve(conflict)
            report.conflict_resolutions.append(resolution)
            # 将拆分后的子模式存入 store
            for refined in resolution.refined_patterns:
                if refined.pattern_id not in [p.pattern_id for p in self._store.get_all()]:
                    self._store.store(refined)

        report.conflicts_resolved = len(report.conflict_resolutions)

        # Step 5: Cleanup — 移除低质量模式
        removed = self._cleanup_low_quality(patterns)
        report.patterns_removed = len(removed)

        # 记录进化后状态
        remaining = self._store.get_all()
        scores_after = [p.score for p in remaining if p.score > 0]
        report.avg_score_after = round(sum(scores_after) / len(scores_after), 4) if scores_after else 0.0
        report.score_improvement = round(report.avg_score_after - report.avg_score_before, 4)

        # 等级分布
        grade_dist: dict[str, int] = {}
        for p in remaining:
            if p.score > 0:
                grade = self._scorer._assign_grade(p.score)
                grade_dist[grade] = grade_dist.get(grade, 0) + 1
        report.grade_distribution = grade_dist

        # 生成摘要
        report.summary = self._generate_summary(report)

        self._reports.append(report)
        return report

    def _apply_reinforcement(
        self,
        patterns: list[PatternMemory],
        experiences: list[Any],
    ) -> list[ReinforcementResult]:
        """用新经验强化已有模式."""
        results: list[ReinforcementResult] = []
        matched_experience_ids: set[str] = set()

        for pattern in patterns:
            matching = self._find_matching_experiences(pattern, experiences)
            # 排除已被其他模式匹配的经验
            matching = [e for e in matching
                        if getattr(e, "experience_id", id(e)) not in matched_experience_ids]

            if not matching:
                continue

            successes = sum(1 for e in matching if self._is_successful(e))
            result = self._reinforcer.reinforce(pattern, successes, len(matching))
            if result:
                results.append(result)
                for e in matching:
                    matched_experience_ids.add(getattr(e, "experience_id", id(e)))

        return results

    def _find_matching_experiences(
        self,
        pattern: PatternMemory,
        experiences: list[Any],
    ) -> list[Any]:
        """查找匹配模式的经验."""
        matching = []
        for exp in experiences:
            if hasattr(exp, "action_type") and exp.action_type != pattern.action.action_type:
                continue
            if (pattern.condition.opportunity_type
                    and hasattr(exp, "context")
                    and hasattr(exp.context, "opportunity_type")
                    and exp.context.opportunity_type != pattern.condition.opportunity_type):
                continue
            if (pattern.condition.audience_segment
                    and hasattr(exp, "context")
                    and hasattr(exp.context, "audience_segment")
                    and exp.context.audience_segment != pattern.condition.audience_segment):
                continue
            matching.append(exp)
        return matching

    @staticmethod
    def _is_successful(exp: Any) -> bool:
        """判断经验是否成功."""
        if hasattr(exp, "is_successful"):
            return exp.is_successful()
        if hasattr(exp, "outcome") and hasattr(exp.outcome, "success"):
            return exp.outcome.success
        if hasattr(exp, "reward"):
            return exp.reward >= 0.5
        return False

    def _cleanup_low_quality(self, patterns: list[PatternMemory]) -> list[PatternMemory]:
        """移除低质量模式."""
        removed: list[PatternMemory] = []
        to_keep: list[PatternMemory] = []

        for p in patterns:
            if (p.score < self.MIN_SCORE_TO_KEEP
                    and p.performance.samples < self.MIN_SAMPLES_TO_KEEP):
                removed.append(p)
            else:
                to_keep.append(p)

        # 更新 store
        if removed:
            # 直接操作内部列表
            self._store._patterns = to_keep

        return removed

    def _generate_summary(self, report: EvolutionReport) -> str:
        """生成人类可读的进化摘要."""
        lines = [
            "=" * 55,
            f"  E13.6 Pattern Evolution Report — {report.cycle_id}",
            "=" * 55,
            f"  Scored:       {report.patterns_scored:>4d} patterns",
            f"  Decayed:      {report.patterns_decayed:>4d} patterns",
            f"  Reinforced:   {report.patterns_reinforced:>4d} patterns",
            f"  Conflicts:    {report.conflicts_detected:>4d} detected, "
            f"{report.conflicts_resolved} resolved",
            f"  Removed:      {report.patterns_removed:>4d} patterns",
            "-" * 55,
            f"  Avg Score:    {report.avg_score_before:.4f} → "
            f"{report.avg_score_after:.4f} "
            f"({report.score_improvement:+.4f})",
            f"  Grades:       {report.grade_distribution}",
            "-" * 55,
        ]

        if report.decay_results:
            lines.append(f"  Top Decays:")
            for dr in sorted(report.decay_results, key=lambda x: -x.decay_factor)[:3]:
                lines.append(f"    {dr.pattern_id[:8]}: {dr.days_since_last:.0f}d, "
                             f"decay={dr.decay_factor:.2%}")

        if report.reinforcement_results:
            lines.append(f"  Top Reinforcements:")
            for rr in sorted(report.reinforcement_results, key=lambda x: -x.boost_applied)[:3]:
                lines.append(f"    {rr.pattern_id[:8]}: +{rr.samples_added} samples, "
                             f"boost={rr.boost_applied:+.2%}")

        if report.conflict_resolutions:
            lines.append(f"  Conflict Resolutions:")
            for cr in report.conflict_resolutions[:3]:
                lines.append(f"    {cr.resolution_type}: {cr.conflict.action_difference}")

        lines.append("=" * 55)
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # History
    # ═══════════════════════════════════════════════════════════

    def get_reports(self, limit: int = 10) -> list[EvolutionReport]:
        """获取最近的进化报告."""
        return self._reports[-limit:] if limit > 0 else self._reports

    def get_latest_report(self) -> EvolutionReport | None:
        """获取最新的进化报告."""
        return self._reports[-1] if self._reports else None

    @property
    def report_count(self) -> int:
        return len(self._reports)