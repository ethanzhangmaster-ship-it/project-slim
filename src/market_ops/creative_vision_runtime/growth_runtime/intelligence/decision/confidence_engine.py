"""E13.7.1 DecisionConfidenceEngine — 决策置信度引擎.

Day 7.1 核心模块:
  让 DecisionEngine 不只是"根据历史找相似案例"，而是
  "根据历史预测未来动作价值并量化置信度"。

核心职责:
  1. 多维度置信度计算: pattern_quality × sample_size × recency × reward_consistency
  2. 备选方案对比: 多个策略的 EV (Expected Value) 排序
  3. 置信度等级判定: HIGH/MEDIUM/LOW/INSUFFICIENT

公式:
  confidence = pattern_quality × 0.35 + sample_size_factor × 0.25
             + recency_factor × 0.20 + reward_consistency × 0.20

与现有 ConfidenceEngine 的区别:
  - E12.2 ConfidenceEngine: 诊断置信度 (当前状态)
  - E12.3 PredictionConfidenceEngine: 预测置信度 (未来趋势)
  - E13.7.1 DecisionConfidenceEngine: 决策置信度 (动作价值)

用法:
    engine = DecisionConfidenceEngine(decision_sync=dsync, pattern_store=pstore)
    conf = engine.compute("S1", "creative_fatigue", "replace_creative")
    if conf.level == ConfidenceLevel.HIGH:
        execute()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# ConfidenceLevel
# ═══════════════════════════════════════════════════════════════


class ConfidenceLevel(str, Enum):
    """置信度等级.

    | Level         | Score Range | 含义               |
    |---------------|------------|--------------------|
    | HIGH          | >= 0.75    | 高度可信，可直接执行 |
    | MEDIUM        | >= 0.50    | 中等可信，建议测试   |
    | LOW           | >= 0.25    | 低可信，需更多数据   |
    | INSUFFICIENT  | < 0.25     | 数据不足，不可决策   |
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"

    @classmethod
    def from_score(cls, score: float) -> ConfidenceLevel:
        if score >= 0.75:
            return cls.HIGH
        elif score >= 0.50:
            return cls.MEDIUM
        elif score >= 0.25:
            return cls.LOW
        return cls.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════
# DecisionConfidence
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionConfidence:
    """决策置信度 — 对一个策略的多维度可信度评估.

    Attributes:
        strategy_id: 策略 ID
        strategy_name: 策略名称
        opportunity_type: 机会类型
        action_type: 动作类型
        confidence_score: 综合置信度 [0, 1]
        pattern_quality: 模式质量贡献 [0, 1]
        sample_size_factor: 样本量因子 [0, 1]
        recency_factor: 时效性因子 [0, 1]
        reward_consistency: 奖励一致性 [0, 1]
        historical_success_rate: 历史成功率
        avg_reward: 平均奖励
        total_samples: 总样本数
        recent_samples: 近期样本数 (7天内)
        level: 置信度等级
        supporting_patterns: 支撑模式数
        warnings: 警告信息
        components: 各维度详细分解
        computed_at: 计算时间
    """
    strategy_id: str = ""
    strategy_name: str = ""
    opportunity_type: str = ""
    action_type: str = ""
    confidence_score: float = 0.0
    pattern_quality: float = 0.0
    sample_size_factor: float = 0.0
    recency_factor: float = 0.0
    reward_consistency: float = 0.0
    historical_success_rate: float = 0.0
    avg_reward: float = 0.0
    total_samples: int = 0
    recent_samples: int = 0
    level: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT
    supporting_patterns: int = 0
    warnings: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "confidence_score": round(self.confidence_score, 4),
            "pattern_quality": round(self.pattern_quality, 4),
            "sample_size_factor": round(self.sample_size_factor, 4),
            "recency_factor": round(self.recency_factor, 4),
            "reward_consistency": round(self.reward_consistency, 4),
            "historical_success_rate": round(self.historical_success_rate, 4),
            "avg_reward": round(self.avg_reward, 4),
            "total_samples": self.total_samples,
            "recent_samples": self.recent_samples,
            "level": self.level.value,
            "supporting_patterns": self.supporting_patterns,
            "warnings": self.warnings,
            "components": self.components,
            "computed_at": self.computed_at,
        }

    @property
    def is_reliable(self) -> bool:
        """是否可靠 (HIGH 或 MEDIUM)."""
        return self.level in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM}

    @property
    def is_strong(self) -> bool:
        """是否强可信 (HIGH)."""
        return self.level == ConfidenceLevel.HIGH

    @property
    def has_insufficient_data(self) -> bool:
        """是否数据不足."""
        return self.level == ConfidenceLevel.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════
# DecisionConfidenceEngine
# ═══════════════════════════════════════════════════════════════


class DecisionConfidenceEngine:
    """E13.7.1 DecisionConfidenceEngine — 决策置信度引擎.

    对每个策略计算多维度置信度，综合评估:
      1. Pattern Quality: 模式质量 (样本量 × 成功率 × 奖励)
      2. Sample Size: 样本量 (对数平滑)
      3. Recency: 时效性 (时间衰减)
      4. Reward Consistency: 奖励一致性 (1 - std/mean)

    公式:
      confidence = pattern_quality × 0.35 + sample_size  × 0.25
                 + recency_factor   × 0.20 + consistency  × 0.20

    Attributes:
        _decision_sync: DecisionMemorySync 实例
        _pattern_store: PatternStore 实例
        _weights: 各维度权重
    """

    # ── 权重配置 ──────────────────────────────────────────────

    WEIGHT_PATTERN_QUALITY = 0.35
    WEIGHT_SAMPLE_SIZE = 0.25
    WEIGHT_RECENCY = 0.20
    WEIGHT_CONSISTENCY = 0.20

    # ── 样本量阈值 ────────────────────────────────────────────

    MIN_SAMPLES_RELIABLE = 20   # 高可靠样本数
    MIN_SAMPLES_DECENT = 10     # 中等样本数
    MIN_SAMPLES_MINIMAL = 3     # 最低样本数

    # ── 时效性阈值 ────────────────────────────────────────────

    RECENCY_DAYS_FRESH = 3      # 新鲜数据 (3天内)
    RECENCY_DAYS_RECENT = 7     # 近期数据 (7天内)
    RECENCY_DAYS_STALE = 30     # 过期数据 (30天外)

    # ── 一致性阈值 ────────────────────────────────────────────

    CONSISTENCY_STD_THRESHOLD = 0.3  # std/mean 超过此值视为不一致

    def __init__(
        self,
        decision_sync: Any = None,  # DecisionMemorySync
        decision_memory: Any = None,  # DecisionMemory (fallback)
        pattern_store: Any = None,  # PatternStore
        weights: dict[str, float] | None = None,
    ):
        """初始化置信度引擎.

        Args:
            decision_sync: DecisionMemorySync 实例 (优先)
            decision_memory: DecisionMemory 实例 (fallback)
            pattern_store: PatternStore 实例
            weights: 自定义权重
        """
        self._decision_sync = decision_sync
        self._decision_memory = decision_memory
        self._pattern_store = pattern_store

        if weights:
            self._weights = weights
        else:
            self._weights = {
                "pattern_quality": self.WEIGHT_PATTERN_QUALITY,
                "sample_size": self.WEIGHT_SAMPLE_SIZE,
                "recency": self.WEIGHT_RECENCY,
                "consistency": self.WEIGHT_CONSISTENCY,
            }

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def compute(
        self,
        strategy_id: str = "",
        strategy_name: str = "",
        opportunity_type: str = "",
        action_type: str = "",
    ) -> DecisionConfidence:
        """计算单个策略的决策置信度.

        Args:
            strategy_id: 策略 ID
            strategy_name: 策略名称
            opportunity_type: 机会类型
            action_type: 动作类型

        Returns:
            DecisionConfidence: 置信度评估结果
        """
        conf = DecisionConfidence(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            opportunity_type=opportunity_type,
            action_type=action_type,
        )

        # 1. 从 DecisionMemorySync 获取历史数据
        records = self._get_historical_records(
            strategy_id=strategy_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
        )

        if not records:
            conf.warnings.append("No historical decision data found.")
            conf.level = ConfidenceLevel.INSUFFICIENT
            return conf

        conf.total_samples = len(records)

        # 样本不足时直接返回 INSUFFICIENT
        if conf.total_samples < self.MIN_SAMPLES_MINIMAL:
            conf.warnings.append(
                f"Only {conf.total_samples} samples available (min {self.MIN_SAMPLES_MINIMAL} required)."
            )
            conf.level = ConfidenceLevel.INSUFFICIENT
            return conf

        # 2. 计算各维度
        conf.historical_success_rate = self._compute_success_rate(records)
        conf.avg_reward = self._compute_avg_reward(records)

        conf.pattern_quality = self._compute_pattern_quality(
            opportunity_type, action_type,
        )
        conf.sample_size_factor = self._compute_sample_size_factor(conf.total_samples)
        conf.recency_factor = self._compute_recency_factor(records)
        conf.reward_consistency = self._compute_reward_consistency(records)
        conf.recent_samples = self._count_recent(records)

        # 3. 加权合成
        conf.confidence_score = self._synthesize(conf)

        # 4. 判定等级
        conf.level = ConfidenceLevel.from_score(conf.confidence_score)

        # 5. 生成警告
        self._generate_warnings(conf)

        # 6. 记录组件分解
        conf.components = {
            "pattern_quality": round(conf.pattern_quality, 4),
            "sample_size": round(conf.sample_size_factor, 4),
            "recency": round(conf.recency_factor, 4),
            "consistency": round(conf.reward_consistency, 4),
        }

        return conf

    def compare_alternatives(
        self,
        strategies: list[dict[str, str]],
        opportunity_type: str = "",
    ) -> list[DecisionConfidence]:
        """比较多个备选策略，按置信度排序.

        Args:
            strategies: 策略列表 [{"strategy_id": "S1", "strategy_name": "...", "action_type": "..."}]
            opportunity_type: 机会类型

        Returns:
            list[DecisionConfidence]: 按 confidence_score 降序排列
        """
        results: list[DecisionConfidence] = []
        for s in strategies:
            sid = s.get("strategy_id", "")
            sname = s.get("strategy_name", "")
            atype = s.get("action_type", "")
            conf = self.compute(
                strategy_id=sid,
                strategy_name=sname,
                opportunity_type=opportunity_type,
                action_type=atype,
            )
            results.append(conf)

        results.sort(key=lambda c: c.confidence_score, reverse=True)
        return results

    def is_confident(
        self,
        confidence: DecisionConfidence,
        threshold: float = 0.5,
    ) -> bool:
        """判断置信度是否达到阈值.

        Args:
            confidence: 置信度评估
            threshold: 阈值 (默认 0.5)

        Returns:
            bool: 是否可信
        """
        return confidence.confidence_score >= threshold

    # ═══════════════════════════════════════════════════════════
    # 维度计算
    # ═══════════════════════════════════════════════════════════

    def _compute_pattern_quality(
        self,
        opportunity_type: str,
        action_type: str,
    ) -> float:
        """从 PatternMemory 计算模式质量.

        查询匹配的 Pattern，取最高评分作为质量因子。
        """
        if self._pattern_store is None:
            return 0.0

        try:
            patterns = self._query_patterns(opportunity_type, action_type)
            if not patterns:
                return 0.0

            # 取最高评分模式的 quality
            best = max(patterns, key=lambda p: getattr(p, "score", 0))
            quality = self._pattern_to_quality(best)
            return min(1.0, quality)

        except Exception:
            return 0.0

    def _compute_sample_size_factor(self, total_samples: int) -> float:
        """计算样本量因子.

        使用对数平滑，避免大样本过度主导:
          - 3 samples  → ~0.30
          - 10 samples → ~0.55
          - 20 samples → ~0.70
          - 50 samples → ~0.85
          - 100 samples → ~0.95
        """
        if total_samples < self.MIN_SAMPLES_MINIMAL:
            return 0.0
        factor = math.log(total_samples + 1) / math.log(100)
        return round(min(1.0, factor), 4)

    def _compute_recency_factor(
        self,
        records: list[Any],
    ) -> float:
        """计算时效性因子.

        基于最近数据的比例:
          - 全部新鲜 → 1.0
          - 一半新鲜 → 0.5
          - 全部过期 → 0.0
        """
        if not records:
            return 0.0

        now = datetime.now(timezone.utc)
        weights = []

        for r in records:
            created_at = getattr(r, "created_at", "")
            if not created_at:
                weights.append(0.3)  # 无时间戳 → 中等权重
                continue

            try:
                dt = datetime.fromisoformat(created_at)
                days_ago = (now - dt).total_seconds() / 86400

                if days_ago <= self.RECENCY_DAYS_FRESH:
                    weights.append(1.0)
                elif days_ago <= self.RECENCY_DAYS_RECENT:
                    weights.append(0.8)
                elif days_ago <= self.RECENCY_DAYS_STALE:
                    weights.append(0.5)
                else:
                    weights.append(0.1)
            except (ValueError, TypeError):
                weights.append(0.3)

        if not weights:
            return 0.0

        return round(sum(weights) / len(weights), 4)

    def _compute_reward_consistency(
        self,
        records: list[Any],
    ) -> float:
        """计算奖励一致性.

        使用 (1 - CV) 来衡量:
          - CV = 0 (完全一致) → 1.0
          - CV > 1.0 (高度分散) → 0.0

        额外惩罚:
          - 平均奖励为负 → 一致性 × 0.3 (全部失败虽一致但不可信)
          - 平均奖励接近 0 → 一致性 × 0.5
        """
        rewards = []
        for r in records:
            reward = getattr(r, "reward", None)
            if reward is not None and isinstance(reward, (int, float)):
                rewards.append(reward)

        if len(rewards) < 2:
            return 0.5  # 单样本 → 中性

        mean = sum(rewards) / len(rewards)
        if abs(mean) < 0.001:
            return 0.0  # 均值接近0 → 低一致性

        variance = sum((x - mean) ** 2 for x in rewards) / len(rewards)
        std = math.sqrt(variance)
        cv = std / abs(mean)

        # 1 - CV, clip to [0, 1]
        consistency = max(0.0, min(1.0, 1.0 - cv))

        # 平均奖励为负 → 惩罚
        if mean < 0:
            consistency *= 0.3
        elif mean < 0.1:
            consistency *= 0.5

        return round(consistency, 4)

    def _compute_success_rate(self, records: list[Any]) -> float:
        """计算历史成功率."""
        if not records:
            return 0.0
        success_count = sum(1 for r in records if getattr(r, "success", False))
        return round(success_count / len(records), 4)

    def _compute_avg_reward(self, records: list[Any]) -> float:
        """计算平均奖励."""
        rewards = [
            r.reward for r in records
            if getattr(r, "reward", None) is not None
        ]
        if not rewards:
            return 0.0
        return round(sum(rewards) / len(rewards), 4)

    def _count_recent(self, records: list[Any]) -> int:
        """统计近期 (7天内) 样本数."""
        now = datetime.now(timezone.utc)
        count = 0
        for r in records:
            created_at = getattr(r, "created_at", "")
            if not created_at:
                continue
            try:
                dt = datetime.fromisoformat(created_at)
                days_ago = (now - dt).total_seconds() / 86400
                if days_ago <= self.RECENCY_DAYS_RECENT:
                    count += 1
            except (ValueError, TypeError):
                pass
        return count

    def _synthesize(self, conf: DecisionConfidence) -> float:
        """加权合成最终置信度.

        当 pattern_quality 为 0 (无 PatternStore) 时，
        将其权重按比例重新分配给其他三个维度。

        额外惩罚:
          - 历史成功率 0% → 最终得分 × 0.7 (不可信)
        """
        w_pq = self._weights.get("pattern_quality", 0.35)
        w_ss = self._weights.get("sample_size", 0.25)
        w_rc = self._weights.get("recency", 0.20)
        w_co = self._weights.get("consistency", 0.20)

        if conf.pattern_quality == 0.0:
            # 无模式数据 → 重新分配权重
            total_remaining = w_ss + w_rc + w_co
            if total_remaining > 0:
                w_ss = w_ss + w_pq * (w_ss / total_remaining)
                w_rc = w_rc + w_pq * (w_rc / total_remaining)
                w_co = w_co + w_pq * (w_co / total_remaining)

        score = (
            conf.pattern_quality * w_pq
            + conf.sample_size_factor * w_ss
            + conf.recency_factor * w_rc
            + conf.reward_consistency * w_co
        )

        # 历史成功率 0% → 严重惩罚
        if conf.historical_success_rate == 0.0 and conf.total_samples >= self.MIN_SAMPLES_MINIMAL:
            score *= 0.65

        return round(max(0.0, min(1.0, score)), 4)

    # ═══════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════

    def _get_historical_records(
        self,
        strategy_id: str = "",
        opportunity_type: str = "",
        action_type: str = "",
    ) -> list[Any]:
        """从 DecisionMemorySync 或 DecisionMemory 获取历史记录.

        优先使用 DecisionMemorySync (含完整生命周期数据)，
        fallback 到 DecisionMemory。
        """
        records: list[Any] = []

        # 优先: DecisionMemorySync
        if self._decision_sync is not None:
            completed = self._decision_sync.get_completed_decisions(
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
            if strategy_id:
                completed = [
                    r for r in completed
                    if getattr(r, "strategy_id", "") == strategy_id
                ]
            records = completed

        # Fallback: DecisionMemory
        if not records and self._decision_memory is not None:
            experiences = self._decision_memory.find_similar(
                opportunity_type=opportunity_type,
                strategy_id=strategy_id,
            )
            resolved = [e for e in experiences if e.is_resolved]
            # 转换为简化记录
            class _SimpleRecord:
                def __init__(self, exp):
                    self.success = exp.is_success
                    self.reward = self._compute_reward(exp)
                    self.created_at = exp.created_at
                    self.strategy_id = exp.strategy_id

                @staticmethod
                def _compute_reward(exp):
                    if exp.is_success:
                        return 0.8
                    if exp.is_failure:
                        return -1.0
                    return 0.0

            records = [_SimpleRecord(e) for e in resolved]

        return records

    def _query_patterns(
        self,
        opportunity_type: str,
        action_type: str,
    ) -> list[Any]:
        """从 PatternStore 查询匹配的 Pattern."""
        if self._pattern_store is None:
            return []

        try:
            # 尝试 query 方法
            if hasattr(self._pattern_store, "query"):
                from ...memory.models import PatternQuery
                query = PatternQuery(
                    opportunity_types=[opportunity_type] if opportunity_type else [],
                    action_types=[action_type] if action_type else [],
                    limit=10,
                )
                return self._pattern_store.query(query)

            # 尝试 get_all + 过滤
            if hasattr(self._pattern_store, "get_all"):
                all_patterns = self._pattern_store.get_all()
                matched = []
                for p in all_patterns:
                    cond = getattr(p, "condition", None)
                    if cond is None:
                        continue
                    if opportunity_type and getattr(cond, "opportunity_type", "") != opportunity_type:
                        continue
                    if action_type and getattr(cond, "action_type", "") != action_type:
                        continue
                    matched.append(p)
                return matched

        except Exception:
            pass

        return []

    def _pattern_to_quality(self, pattern: Any) -> float:
        """将 Pattern 转换为质量分数."""
        perf = getattr(pattern, "performance", None)
        if perf is None:
            return 0.0

        samples = getattr(perf, "samples", 0)
        success_rate = getattr(perf, "success_rate", 0.0)
        avg_reward = getattr(perf, "avg_reward", 0.0)

        if samples == 0:
            return 0.0

        # 质量 = 样本因子 × 成功率 × 奖励
        sample_factor = math.log(samples + 1) / math.log(100)
        return round(sample_factor * success_rate * max(avg_reward, 0.01), 4)

    # ═══════════════════════════════════════════════════════════
    # 警告生成
    # ═══════════════════════════════════════════════════════════

    def _generate_warnings(self, conf: DecisionConfidence) -> None:
        """生成置信度警告."""
        if conf.total_samples < self.MIN_SAMPLES_MINIMAL:
            conf.warnings.append(
                f"Only {conf.total_samples} samples available (min {self.MIN_SAMPLES_MINIMAL} required)."
            )
        if conf.recent_samples == 0 and conf.total_samples > 0:
            conf.warnings.append("No recent samples (last 7 days) — data may be stale.")
        if conf.reward_consistency < 0.3:
            conf.warnings.append(
                f"Low reward consistency ({conf.reward_consistency:.2f}) — "
                f"outcomes vary widely."
            )
        if conf.pattern_quality < 0.2 and conf.total_samples > 0:
            conf.warnings.append("No strong supporting patterns found.")
        if conf.historical_success_rate < 0.3 and conf.total_samples >= self.MIN_SAMPLES_MINIMAL:
            conf.warnings.append(
                f"Low historical success rate ({conf.historical_success_rate:.0%}) — "
                f"this strategy has a poor track record."
            )

    def __repr__(self) -> str:
        return (
            f"DecisionConfidenceEngine("
            f"sync={'yes' if self._decision_sync else 'no'}, "
            f"patterns={'yes' if self._pattern_store else 'no'})"
        )


__all__ = [
    "ConfidenceLevel",
    "DecisionConfidence",
    "DecisionConfidenceEngine",
]