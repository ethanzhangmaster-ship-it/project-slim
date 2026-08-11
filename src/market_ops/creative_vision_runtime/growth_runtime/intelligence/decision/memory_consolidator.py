"""E13.7.3 DecisionMemoryConsolidator — 决策记忆整合引擎.

Day 7.3 核心模块:
  解决 Decision Memory 中长期堆积导致旧经验污染新决策的问题。
  实现类似人脑的记忆机制: 短期记忆 → 评估 → 分类 → 衰减 → 长期记忆/遗忘。

核心组件:
  1. MemoryCategory: 记忆分类 (CORE_PATTERN / TEMPORARY_PATTERN / NOISE / FAILED)
  2. MemoryClassifier: 基于多维指标对记忆进行分类
  3. MemoryDecayCalculator: 时间衰减计算 (e^(-λ × days))
  4. MemoryConsolidator: 整合 Pipeline (评估 → 分类 → 衰减 → 归档/遗忘)

记忆价值公式:
  memory_value = reward_score × confidence × recurrence × freshness

  例如:
    经验 A: reward=0.8, confidence=0.9, recurrence=20次, freshness=0.95  → 0.684 → 保留
    经验 B: reward=0.9, confidence=0.3, recurrence=1次,  freshness=0.1  → 0.003 → 遗忘

与现有模块的关系:
  - DecisionMemorySync: 提供原始记忆数据
  - DecisionEngine: 集成 Consolidator 过滤过期记忆
  - PatternStore: 归档 Core Pattern 记忆

用法:
    consolidator = MemoryConsolidator(decision_sync=sync)
    result = consolidator.consolidate()
    print(f"Kept: {result.kept}, Archived: {result.archived}, Forgotten: {result.forgotten}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# MemoryCategory
# ═══════════════════════════════════════════════════════════════


class MemoryCategory(str, Enum):
    """记忆分类 — 决定记忆的保留策略.

    | 类别               | 说明               | 保留策略         |
    |-------------------|-------------------|-----------------|
    | CORE_PATTERN      | 长期有效规律        | 永久保留          |
    | TEMPORARY_PATTERN | 阶段性有效          | 保留至过期        |
    | NOISE             | 偶然成功/失败       | 标记为低权重       |
    | FAILED            | 已确认失败的负经验    | 归档后降权        |
    """
    CORE_PATTERN = "core_pattern"
    TEMPORARY_PATTERN = "temporary_pattern"
    NOISE = "noise"
    FAILED = "failed"

    @property
    def is_retainable(self) -> bool:
        """是否应保留."""
        return self in {MemoryCategory.CORE_PATTERN, MemoryCategory.TEMPORARY_PATTERN}

    @property
    def is_disposable(self) -> bool:
        """是否可丢弃."""
        return self in {MemoryCategory.NOISE, MemoryCategory.FAILED}


# ═══════════════════════════════════════════════════════════════
# MemoryValueScore
# ═══════════════════════════════════════════════════════════════


@dataclass
class MemoryValueScore:
    """记忆价值评分 — 评估一条记忆的长期保留价值.

    公式:
      memory_value = reward_score × confidence × recurrence × freshness

    Attributes:
        decision_id: 决策 ID
        strategy_id: 策略 ID
        reward_score: 奖励分数 [0, 1]
        confidence: 综合置信度 [0, 1]
        recurrence: 重现因子 (基于出现次数)
        freshness: 新鲜度因子 (基于时间衰减)
        memory_value: 综合记忆价值 [0, 1]
        category: 记忆分类
        decay_factor: 衰减因子
        days_since_last: 距上次出现天数
        access_count: 被访问次数
        should_keep: 是否应保留
        should_archive: 是否应归档
        should_forget: 是否应遗忘
    """
    decision_id: str = ""
    strategy_id: str = ""
    reward_score: float = 0.0
    confidence: float = 0.0
    recurrence: float = 0.0
    freshness: float = 0.0
    memory_value: float = 0.0
    category: MemoryCategory = MemoryCategory.NOISE
    decay_factor: float = 1.0
    days_since_last: float = 0.0
    access_count: int = 0
    should_keep: bool = False
    should_archive: bool = False
    should_forget: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "reward_score": round(self.reward_score, 4),
            "confidence": round(self.confidence, 4),
            "recurrence": round(self.recurrence, 4),
            "freshness": round(self.freshness, 4),
            "memory_value": round(self.memory_value, 4),
            "category": self.category.value,
            "decay_factor": round(self.decay_factor, 4),
            "days_since_last": round(self.days_since_last, 1),
            "access_count": self.access_count,
            "should_keep": self.should_keep,
            "should_archive": self.should_archive,
            "should_forget": self.should_forget,
        }


# ═══════════════════════════════════════════════════════════════
# MemoryClassifier
# ═══════════════════════════════════════════════════════════════


class MemoryClassifier:
    """E13.7.3.1 MemoryClassifier — 记忆分类器.

    基于多维指标对每条记忆进行分类，决定保留策略。

    分类规则:
      CORE_PATTERN:
        - memory_value >= 0.5
        - recurrence >= 10 (出现 10 次以上)
        - freshness >= 0.5

      TEMPORARY_PATTERN:
        - memory_value >= 0.3
        - recurrence >= 3
        - freshness >= 0.3

      FAILED:
        - reward_score < 0 (负奖励)
        - 或 success=False 且 recurrence >= 3

      NOISE:
        - 其余情况
    """

    # ── 阈值配置 (recurrence 为归一化值 [0,1]) ─────────────────

    # log(10+1)/log(100) ≈ 0.52 → Core 需要约 10 次同类记忆
    CORE_MEMORY_VALUE_MIN = 0.5
    CORE_RECURRENCE_MIN = 0.5
    CORE_FRESHNESS_MIN = 0.5

    # log(3+1)/log(100) ≈ 0.30 → Temp 需要约 3 次同类记忆
    TEMP_MEMORY_VALUE_MIN = 0.3
    TEMP_RECURRENCE_MIN = 0.3
    TEMP_FRESHNESS_MIN = 0.3

    # 确认失败需要至少 3 次出现
    FAILED_RECURRENCE_MIN = 0.3

    def classify(self, score: MemoryValueScore) -> MemoryCategory:
        """对记忆进行分类.

        Args:
            score: 记忆价值评分

        Returns:
            MemoryCategory: 记忆分类
        """
        # 负奖励 + 多次出现 → 确认失败
        if score.reward_score < 0 and score.recurrence >= self.FAILED_RECURRENCE_MIN:
            return MemoryCategory.FAILED

        # 多次失败 → 确认失败
        if score.reward_score <= 0.1 and score.recurrence >= self.FAILED_RECURRENCE_MIN:
            return MemoryCategory.FAILED

        # Core Pattern: 高价值 + 高重现 + 高新鲜度
        if (
            score.memory_value >= self.CORE_MEMORY_VALUE_MIN
            and score.recurrence >= self.CORE_RECURRENCE_MIN
            and score.freshness >= self.CORE_FRESHNESS_MIN
        ):
            return MemoryCategory.CORE_PATTERN

        # Temporary Pattern: 中等价值
        if (
            score.memory_value >= self.TEMP_MEMORY_VALUE_MIN
            and score.recurrence >= self.TEMP_RECURRENCE_MIN
            and score.freshness >= self.TEMP_FRESHNESS_MIN
        ):
            return MemoryCategory.TEMPORARY_PATTERN

        # 单次失败 → Noise
        if score.reward_score < 0:
            return MemoryCategory.NOISE

        # 其余 → Noise
        return MemoryCategory.NOISE

    def classify_batch(
        self,
        scores: list[MemoryValueScore],
    ) -> list[MemoryValueScore]:
        """批量分类.

        Args:
            scores: 记忆价值评分列表

        Returns:
            list[MemoryValueScore]: 已分类的评分列表
        """
        for score in scores:
            score.category = self.classify(score)
        return scores


# ═══════════════════════════════════════════════════════════════
# MemoryDecayCalculator
# ═══════════════════════════════════════════════════════════════


class MemoryDecayCalculator:
    """E13.7.3.2 MemoryDecayCalculator — 记忆衰减计算器.

    公式:
      decay_factor = e^(-λ × days_since_last_seen)

    衰减速率:
      30 天  → 0.74
      90 天  → 0.41
      180 天 → 0.17
      365 天 → 0.03

    Attributes:
        lambda_decay: 衰减速率系数 (默认 0.01, 即每天衰减约 1%)
    """

    # 默认衰减系数: 每天衰减约 1%
    DEFAULT_LAMBDA = 0.01

    # 新鲜度阈值 (超过此天数视为过期)
    FRESHNESS_HALF_LIFE_DAYS = 69.0  # ln(2) / 0.01 ≈ 69 天半衰期

    def __init__(self, lambda_decay: float = 0.01):
        """初始化衰减计算器.

        Args:
            lambda_decay: 衰减速率系数
        """
        self._lambda = lambda_decay

    def compute_decay(self, days_since_last: float) -> float:
        """计算衰减因子.

        Args:
            days_since_last: 距上次出现天数

        Returns:
            float: 衰减因子 [0, 1]
        """
        if days_since_last <= 0:
            return 1.0
        decay = math.exp(-self._lambda * days_since_last)
        return round(max(0.0, min(1.0, decay)), 4)

    def compute_freshness(self, days_since_last: float) -> float:
        """计算新鲜度因子.

        freshness = decay_factor，但增加近期加权。

        Args:
            days_since_last: 距上次出现天数

        Returns:
            float: 新鲜度 [0, 1]
        """
        return self.compute_decay(days_since_last)

    def compute_days_since(
        self,
        iso_timestamp: str,
        reference: datetime | None = None,
    ) -> float:
        """计算距今天数.

        Args:
            iso_timestamp: ISO 格式时间戳
            reference: 参考时间 (默认当前时间)

        Returns:
            float: 天数
        """
        if not iso_timestamp:
            return 365.0  # 无时间戳 → 视为很久以前

        ref = reference or datetime.now(timezone.utc)
        try:
            ts = datetime.fromisoformat(iso_timestamp)
            # 处理 naive datetime
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = (ref - ts).total_seconds()
            return max(0.0, delta / 86400.0)
        except (ValueError, TypeError):
            return 365.0

    def compute_batch_decay(
        self,
        timestamps: list[str],
        reference: datetime | None = None,
    ) -> list[float]:
        """批量计算衰减因子.

        Args:
            timestamps: ISO 格式时间戳列表
            reference: 参考时间

        Returns:
            list[float]: 衰减因子列表
        """
        ref = reference or datetime.now(timezone.utc)
        return [
            self.compute_decay(self.compute_days_since(ts, ref))
            for ts in timestamps
        ]


# ═══════════════════════════════════════════════════════════════
# ConsolidationResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConsolidationResult:
    """整合结果 — 一次 Consolidation 的完整输出.

    Attributes:
        total_evaluated: 评估总数
        kept: 保留数
        archived: 归档数
        forgotten: 遗忘数
        core_patterns: Core Pattern 数
        temporary_patterns: Temporary Pattern 数
        noise_count: Noise 数
        failed_count: Failed 数
        avg_memory_value: 平均记忆价值
        scores: 详细评分列表
        timestamp: 整合时间
    """
    total_evaluated: int = 0
    kept: int = 0
    archived: int = 0
    forgotten: int = 0
    core_patterns: int = 0
    temporary_patterns: int = 0
    noise_count: int = 0
    failed_count: int = 0
    avg_memory_value: float = 0.0
    scores: list[MemoryValueScore] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "kept": self.kept,
            "archived": self.archived,
            "forgotten": self.forgotten,
            "core_patterns": self.core_patterns,
            "temporary_patterns": self.temporary_patterns,
            "noise_count": self.noise_count,
            "failed_count": self.failed_count,
            "avg_memory_value": round(self.avg_memory_value, 4),
            "scores": [s.to_dict() for s in self.scores[:20]],  # 只返回前 20 条
            "timestamp": self.timestamp,
        }

    @property
    def retention_rate(self) -> float:
        """保留率."""
        if self.total_evaluated == 0:
            return 0.0
        return round(self.kept / self.total_evaluated, 4)

    @property
    def cleanup_rate(self) -> float:
        """清理率 (遗忘 + 归档)."""
        if self.total_evaluated == 0:
            return 0.0
        return round((self.archived + self.forgotten) / self.total_evaluated, 4)


# ═══════════════════════════════════════════════════════════════
# MemoryConsolidator
# ═══════════════════════════════════════════════════════════════


class MemoryConsolidator:
    """E13.7.3 MemoryConsolidator — 决策记忆整合引擎.

    整合 Pipeline:
      1. 获取所有记忆 (from DecisionMemorySync)
      2. 计算记忆价值 (reward × confidence × recurrence × freshness)
      3. 分类 (Core / Temporary / Noise / Failed)
      4. 计算衰减因子
      5. 决定保留/归档/遗忘
      6. 执行清理

    决策规则:
      - CORE_PATTERN     → keep (永久保留)
      - TEMPORARY_PATTERN → keep (保留至过期)
      - NOISE + 低价值    → forget (遗忘)
      - NOISE + 中等价值  → archive (归档)
      - FAILED            → archive (归档供参考)

    Attributes:
        _decision_sync: DecisionMemorySync 实例
        _classifier: MemoryClassifier 实例
        _decay_calc: MemoryDecayCalculator 实例
        _archive: 归档存储
    """

    # ── 价值评分权重 ──────────────────────────────────────────

    WEIGHT_REWARD = 0.35
    WEIGHT_CONFIDENCE = 0.25
    WEIGHT_RECURRENCE = 0.25
    WEIGHT_FRESHNESS = 0.15

    # ── 阈值 ──────────────────────────────────────────────────

    FORGET_VALUE_THRESHOLD = 0.1    # 低于此值 → 遗忘
    ARCHIVE_VALUE_THRESHOLD = 0.25  # 低于此值 → 归档
    KEEP_VALUE_THRESHOLD = 0.3      # 高于此值 → 保留

    def __init__(
        self,
        decision_sync: Any = None,  # DecisionMemorySync
        lambda_decay: float = 0.01,
    ):
        """初始化整合引擎.

        Args:
            decision_sync: DecisionMemorySync 实例
            lambda_decay: 衰减速率系数
        """
        self._decision_sync = decision_sync
        self._classifier = MemoryClassifier()
        self._decay_calc = MemoryDecayCalculator(lambda_decay=lambda_decay)
        self._archive: dict[str, MemoryValueScore] = {}

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def consolidate(
        self,
        reference_time: datetime | None = None,
    ) -> ConsolidationResult:
        """执行一次完整的记忆整合.

        Args:
            reference_time: 参考时间 (默认当前时间)

        Returns:
            ConsolidationResult: 整合结果
        """
        ref = reference_time or datetime.now(timezone.utc)

        # 1. 获取所有记忆
        records = self._get_all_records()
        if not records:
            return ConsolidationResult()

        # 2. 计算记忆价值
        scores = self._evaluate_all(records, ref)

        # 3. 分类
        scores = self._classifier.classify_batch(scores)

        # 4. 决定去留
        self._decide_actions(scores)

        # 5. 执行清理
        result = self._apply_consolidation(scores)

        return result

    def evaluate_single(
        self,
        record: Any,
        reference_time: datetime | None = None,
    ) -> MemoryValueScore:
        """评估单条记忆.

        Args:
            record: DecisionMemoryRecord 实例
            reference_time: 参考时间

        Returns:
            MemoryValueScore: 记忆价值评分
        """
        ref = reference_time or datetime.now(timezone.utc)
        return self._evaluate_record(record, ref)

    # ═══════════════════════════════════════════════════════════
    # 评估逻辑
    # ═══════════════════════════════════════════════════════════

    def _evaluate_all(
        self,
        records: list[Any],
        reference: datetime,
    ) -> list[MemoryValueScore]:
        """评估所有记忆."""
        scores: list[MemoryValueScore] = []
        for record in records:
            score = self._evaluate_record(record, reference)
            scores.append(score)
        return scores

    def _evaluate_record(
        self,
        record: Any,
        reference: datetime,
    ) -> MemoryValueScore:
        """评估单条记忆记录.

        计算四维因子:
          - reward_score: 从 record.reward 归一化
          - confidence: 从 record.confidence 或默认
          - recurrence: 基于同类记忆出现次数
          - freshness: 基于时间衰减
        """
        score = MemoryValueScore(
            decision_id=getattr(record, "decision_id", ""),
            strategy_id=getattr(record, "strategy_id", ""),
        )

        # 1. 奖励分数 (归一化到 [0, 1])
        reward = getattr(record, "reward", None)
        if reward is not None:
            score.reward_score = round(self._normalize_reward(reward), 4)
        else:
            success = getattr(record, "success", None)
            score.reward_score = 0.8 if success else 0.2

        # 2. 置信度
        score.confidence = round(getattr(record, "confidence", 0.5), 4)

        # 3. 重现因子 (从同类记忆中统计)
        score.recurrence = self._compute_recurrence(record)

        # 4. 新鲜度
        last_seen = (
            getattr(record, "completed_at", "")
            or getattr(record, "created_at", "")
        )
        score.days_since_last = self._decay_calc.compute_days_since(last_seen, reference)
        score.freshness = self._decay_calc.compute_freshness(score.days_since_last)
        score.decay_factor = score.freshness

        # 5. 访问次数
        score.access_count = getattr(record, "access_count", 0)

        # 6. 综合记忆价值
        score.memory_value = self._compute_memory_value(score)

        return score

    def _compute_memory_value(self, score: MemoryValueScore) -> float:
        """计算综合记忆价值.

        memory_value = reward × 0.35 + confidence × 0.25 + recurrence × 0.25 + freshness × 0.15
        """
        value = (
            score.reward_score * self.WEIGHT_REWARD
            + score.confidence * self.WEIGHT_CONFIDENCE
            + score.recurrence * self.WEIGHT_RECURRENCE
            + score.freshness * self.WEIGHT_FRESHNESS
        )
        return round(max(0.0, min(1.0, value)), 4)

    def _compute_recurrence(self, record: Any) -> float:
        """计算重现因子 — 基于同类记忆的出现次数.

        使用对数平滑:
          1 次   → 0.1
          3 次   → 0.3
          10 次  → 0.5
          50 次  → 0.7
          100 次 → 0.8
        """
        if self._decision_sync is None:
            return 0.1

        try:
            # 统计同类记忆 (同 opportunity_type + action_type)
            opportunity_type = getattr(record, "opportunity_type", "")
            action_type = getattr(record, "action_type", "")

            completed = self._decision_sync.get_completed_decisions(
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
            count = len(completed)
            if count <= 1:
                return 0.1

            # 对数平滑: log(count) / log(100)
            recurrence = min(1.0, math.log(count + 1) / math.log(100))
            return round(recurrence, 4)
        except Exception:
            return 0.1

    @staticmethod
    def _normalize_reward(reward: float) -> float:
        """归一化奖励到 [0, 1].

        reward ∈ [-1, 1] → normalized ∈ [0, 1]
        """
        return (reward + 1.0) / 2.0

    # ═══════════════════════════════════════════════════════════
    # 决策逻辑
    # ═══════════════════════════════════════════════════════════

    def _decide_actions(self, scores: list[MemoryValueScore]) -> None:
        """基于分类和记忆价值决定去留.

        规则:
          - CORE_PATTERN     → keep
          - TEMPORARY_PATTERN → keep
          - FAILED           → archive
          - NOISE:
            - memory_value < FORGET_THRESHOLD  → forget
            - memory_value < ARCHIVE_THRESHOLD → archive
            - 其他                              → keep
        """
        for score in scores:
            if score.category == MemoryCategory.CORE_PATTERN:
                score.should_keep = True
            elif score.category == MemoryCategory.TEMPORARY_PATTERN:
                score.should_keep = True
            elif score.category == MemoryCategory.FAILED:
                score.should_archive = True
            elif score.category == MemoryCategory.NOISE:
                if score.memory_value < self.FORGET_VALUE_THRESHOLD:
                    score.should_forget = True
                elif score.memory_value < self.ARCHIVE_VALUE_THRESHOLD:
                    score.should_archive = True
                else:
                    score.should_keep = True

    def _apply_consolidation(
        self,
        scores: list[MemoryValueScore],
    ) -> ConsolidationResult:
        """执行整合动作.

        执行:
          - keep: 保留在 DecisionMemorySync 中
          - archive: 移入归档存储
          - forget: 从 DecisionMemorySync 中移除
        """
        result = ConsolidationResult(total_evaluated=len(scores))
        result.scores = scores

        for score in scores:
            if score.should_keep:
                result.kept += 1
            elif score.should_archive:
                result.archived += 1
                self._archive[score.decision_id] = score
            elif score.should_forget:
                result.forgotten += 1

            # 统计分类
            if score.category == MemoryCategory.CORE_PATTERN:
                result.core_patterns += 1
            elif score.category == MemoryCategory.TEMPORARY_PATTERN:
                result.temporary_patterns += 1
            elif score.category == MemoryCategory.NOISE:
                result.noise_count += 1
            elif score.category == MemoryCategory.FAILED:
                result.failed_count += 1

        # 平均记忆价值
        if result.total_evaluated > 0:
            result.avg_memory_value = round(
                sum(s.memory_value for s in scores) / result.total_evaluated, 4,
            )

        return result

    # ═══════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════

    def _get_all_records(self) -> list[Any]:
        """获取所有已完成记忆记录."""
        if self._decision_sync is None:
            return []

        try:
            return self._decision_sync.get_completed_decisions()
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════════════════════

    def get_archive(self) -> dict[str, MemoryValueScore]:
        """获取归档存储."""
        return dict(self._archive)

    def get_core_memories(
        self,
        scores: list[MemoryValueScore] | None = None,
    ) -> list[MemoryValueScore]:
        """获取 Core Pattern 记忆."""
        if scores is None:
            return [
                s for s in self._archive.values()
                if s.category == MemoryCategory.CORE_PATTERN
            ]
        return [s for s in scores if s.category == MemoryCategory.CORE_PATTERN]

    def get_high_value_memories(
        self,
        scores: list[MemoryValueScore],
        min_value: float = 0.5,
    ) -> list[MemoryValueScore]:
        """获取高价值记忆."""
        return [s for s in scores if s.memory_value >= min_value]

    def get_decayed_memories(
        self,
        scores: list[MemoryValueScore],
        min_decay: float = 0.5,
    ) -> list[MemoryValueScore]:
        """获取已衰减的记忆."""
        return [s for s in scores if s.decay_factor <= min_decay]

    # ═══════════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════════

    def stats(self) -> dict[str, Any]:
        """获取整合统计."""
        archive_count = len(self._archive)
        core_count = sum(
            1 for s in self._archive.values()
            if s.category == MemoryCategory.CORE_PATTERN
        )
        return {
            "archive_size": archive_count,
            "core_patterns": core_count,
            "lambda_decay": self._decay_calc._lambda,
        }

    def clear(self) -> None:
        """清空归档存储."""
        self._archive.clear()

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"MemoryConsolidator("
            f"archive={s['archive_size']}, "
            f"core={s['core_patterns']}, "
            f"lambda={s['lambda_decay']})"
        )


__all__ = [
    "MemoryCategory",
    "MemoryValueScore",
    "MemoryClassifier",
    "MemoryDecayCalculator",
    "MemoryConsolidator",
    "ConsolidationResult",
]