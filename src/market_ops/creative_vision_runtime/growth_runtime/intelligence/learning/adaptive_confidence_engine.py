"""E13.7.7.3 Adaptive Confidence Engine — 自适应置信度引擎.

Day 7.7.3:
  将多个静态 confidence 统一升级为自适应 confidence，
  回答: "这个置信度本身有多可信？"

核心流程:
  base_confidence (from Enhancer/Predictor/DecisionEngine)
              |
              v
  AdaptiveConfidenceEngine.adjust(base_confidence, context)
              |
              +--> _compute_historical_accuracy()   → 历史预测准确率
              |
              +--> _compute_learning_effectiveness() → 学习系统有效性
              |
              +--> _compute_context_similarity()     → 上下文相似度
              |
              +--> _compute_freshness()              → 数据时效性
              |
              v
  adjusted_confidence = base_confidence
    × (historical_accuracy × w_ha
       + learning_effectiveness × w_le
       + context_similarity × w_cs
       + freshness × w_fr)

设计原则:
  - 包裹层 (Wrapper): 不修改上游 confidence 模块
  - 确定性: 纯函数式因子计算，可解释
  - 可追踪: 每次调整记录为 ConfidenceRecord
  - 可配置: 权重通过 LearningStrategyState 控制

用法:
  from growth_runtime.intelligence.learning.adaptive_confidence_engine import (
      AdaptiveConfidenceEngine,
  )

  engine = AdaptiveConfidenceEngine()
  result = engine.adjust(
      base_confidence=0.75,
      source="enhancer",
      context={"action_type": "increase_budget", "strategy": "scale_winning"},
      effectiveness=effectiveness_eval,
      data_timestamps=["2026-07-25", "2026-07-28"],
  )
"""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .evaluation.models import LearningEffectiveness
from .models.adaptive_confidence_models import (
    AdaptiveConfidenceResult,
    ConfidenceDimension,
    ConfidenceRecord,
)
from .models.learning_strategy_models import LearningStrategyState


# ═══════════════════════════════════════════════════════════════
# AdaptiveConfidenceEngine
# ═══════════════════════════════════════════════════════════════


class AdaptiveConfidenceEngine:
    """自适应置信度引擎 — 根据历史准确率和学习状态调整置信度.

    用法:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(
            base_confidence=0.75,
            source="enhancer",
            context={"action_type": "increase_budget"},
        )
        # 稍后记录实际结果
        engine.record_outcome(result.result_id, actual_outcome="success")
    """

    # ── 默认权重 (可通过 LearningStrategyState 覆盖) ──────────────

    DEFAULT_WEIGHT_HISTORICAL_ACCURACY = 0.30
    DEFAULT_WEIGHT_LEARNING_EFFECTIVENESS = 0.20
    DEFAULT_WEIGHT_CONTEXT_SIMILARITY = 0.25
    DEFAULT_WEIGHT_FRESHNESS = 0.25

    # ── 历史窗口 ─────────────────────────────────────────────────

    DEFAULT_MAX_HISTORY = 200

    # ── 默认阈值 ─────────────────────────────────────────────────

    DEFAULT_MIN_SAMPLES_FOR_ACCURACY = 5
    DEFAULT_FRESHNESS_DAYS_RECENT = 7
    DEFAULT_FRESHNESS_DAYS_STALE = 30

    def __init__(
        self,
        max_history: int = DEFAULT_MAX_HISTORY,
        min_samples_for_accuracy: int = DEFAULT_MIN_SAMPLES_FOR_ACCURACY,
        freshness_days_recent: int = DEFAULT_FRESHNESS_DAYS_RECENT,
        freshness_days_stale: int = DEFAULT_FRESHNESS_DAYS_STALE,
        strategy_state: LearningStrategyState | None = None,
    ) -> None:
        """初始化引擎.

        Args:
            max_history: 最大历史记录数
            min_samples_for_accuracy: 计算准确率的最小样本数
            freshness_days_recent: "近期"天数阈值
            freshness_days_stale: "过期"天数阈值
            strategy_state: 学习策略状态 (用于权重配置)
        """
        self._max_history = max_history
        self._min_samples = min_samples_for_accuracy
        self._freshness_recent = freshness_days_recent
        self._freshness_stale = freshness_days_stale
        self._strategy_state = strategy_state

        # 预测历史
        self._history: deque[ConfidenceRecord] = deque(maxlen=max_history)

        # 待确认的预测 (result_id → record)
        self._pending: dict[str, ConfidenceRecord] = {}

        # 统计
        self._adjustment_count: int = 0

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def adjustment_count(self) -> int:
        return self._adjustment_count

    # ═══════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════

    def adjust(
        self,
        base_confidence: float,
        source: str = "",
        context: dict[str, Any] | None = None,
        effectiveness: LearningEffectiveness | None = None,
        data_timestamps: list[str] | None = None,
        context_key: str = "",
    ) -> AdaptiveConfidenceResult:
        """对上游 confidence 进行自适应调整.

        Args:
            base_confidence: 原始置信度 [0, 1]
            source: 置信度来源 (enhancer/predictor/confidence_engine)
            context: 当前上下文 (用于相似度比较)
            effectiveness: 学习有效性评估 (可选)
            data_timestamps: 支撑数据的时间戳列表 (用于 freshness)
            context_key: 上下文标识键

        Returns:
            AdaptiveConfidenceResult: 自适应置信度结果
        """
        self._adjustment_count += 1
        ctx = context or {}

        # 1. 计算各维度因子
        ha = self._compute_historical_accuracy(source)
        le = self._compute_learning_effectiveness(effectiveness)
        cs = self._compute_context_similarity(ctx, source)
        fr = self._compute_freshness(data_timestamps)

        # 2. 获取权重
        weights = self._get_weights()

        # 3. 加权合成调整因子
        adjustment_factor = (
            ha * weights["historical_accuracy"]
            + le * weights["learning_effectiveness"]
            + cs * weights["context_similarity"]
            + fr * weights["freshness"]
        )

        # 4. 计算调整后置信度
        adjusted = round(base_confidence * adjustment_factor, 4)
        adjusted = max(0.0, min(1.0, adjusted))

        # 5. 生成调整说明
        adjustments_text = self._generate_adjustments(ha, le, cs, fr, base_confidence, adjusted)

        # 6. 生成警告
        warnings = self._generate_warnings(ha, le, cs, fr, adjusted)

        # 7. 判定等级
        level = self._determine_level(adjusted)

        # 8. 构建结果
        result = AdaptiveConfidenceResult(
            base_confidence=round(base_confidence, 4),
            adjusted_confidence=adjusted,
            adjustment_factor=round(adjustment_factor, 4),
            dimensions={
                ConfidenceDimension.BASE_CONFIDENCE.value: round(base_confidence, 4),
                ConfidenceDimension.HISTORICAL_ACCURACY.value: round(ha, 4),
                ConfidenceDimension.LEARNING_EFFECTIVENESS.value: round(le, 4),
                ConfidenceDimension.CONTEXT_SIMILARITY.value: round(cs, 4),
                ConfidenceDimension.FRESHNESS.value: round(fr, 4),
            },
            dimension_weights=weights,
            adjustments=adjustments_text,
            confidence_level=level,
            warnings=warnings,
            metadata={
                "source": source,
                "context_key": context_key or self._make_context_key(ctx),
            },
        )

        # 9. 记录到 pending
        record = ConfidenceRecord(
            source=source,
            context_key=context_key or self._make_context_key(ctx),
            base_confidence=round(base_confidence, 4),
            adjusted_confidence=adjusted,
            dimensions=result.dimensions,
            metadata={"result_id": result.result_id},
        )
        self._pending[result.result_id] = record

        return result

    def record_outcome(
        self,
        result_id: str,
        actual_outcome: str,
    ) -> ConfidenceRecord | None:
        """记录一次置信度预测的实际结果.

        Args:
            result_id: adjust() 返回的 result_id
            actual_outcome: 实际结果 (success/failure/partial)

        Returns:
            ConfidenceRecord 或 None (未找到)
        """
        record = self._pending.pop(result_id, None)
        if record is None:
            return None

        record.actual_outcome = actual_outcome
        record.is_accurate = self._judge_accuracy(record.adjusted_confidence, actual_outcome)
        self._history.append(record)
        return record

    def reset(self) -> None:
        """重置引擎状态."""
        self._history.clear()
        self._pending.clear()
        self._adjustment_count = 0

    # ═══════════════════════════════════════════════════════════
    # Dimension 1: Historical Accuracy
    # ═══════════════════════════════════════════════════════════

    def _compute_historical_accuracy(self, source: str = "") -> float:
        """计算历史预测准确率.

        基于已记录的 ConfidenceRecord 计算:
          - 有足够样本 → 返回实际准确率
          - 样本不足 → 返回中性值 (1.0, 不调整)
          - 无历史 → 返回 1.0 (不调整)

        准确率定义:
          - 高置信度预测成功 → 正确
          - 高置信度预测失败 → 错误
          - 低置信度预测正确 → 不计入 (保守预测)
        """
        resolved = [r for r in self._history if r.is_resolved]
        if source:
            resolved = [r for r in resolved if r.source == source]

        if len(resolved) < self._min_samples:
            return 1.0  # 样本不足，不调整

        accurate = sum(1 for r in resolved if r.is_accurate)
        total = len(resolved)

        # 只统计高置信度 (>= 0.50) 的预测，低置信度不计入
        decisive = [r for r in resolved if r.adjusted_confidence >= 0.50]
        if len(decisive) >= self._min_samples:
            accurate_d = sum(1 for r in decisive if r.is_accurate)
            return round(accurate_d / len(decisive), 4)
        if len(decisive) == 0:
            return 1.0  # 无 decisive 样本 → 不调整

        return round(accurate / total, 4)

    def _judge_accuracy(self, confidence: float, outcome: str) -> bool:
        """判断一次预测是否准确.

        规则:
          - 高置信度 (>= 0.70) + success → 正确
          - 高置信度 (>= 0.70) + failure → 错误
          - 中等置信度 (0.50-0.70) + success → 正确
          - 中等置信度 (0.50-0.70) + failure → 中性 (不计入)
          - 低置信度 (< 0.50) + success → 中性
          - 低置信度 (< 0.50) + failure → 正确
        """
        is_success = outcome == "success"
        is_failure = outcome == "failure"

        if confidence >= 0.70:
            return is_success
        elif confidence >= 0.50:
            if is_success:
                return True
            if is_failure:
                return False  # 中等置信度失败 → 算错误
            return False
        else:
            # 低置信度 → 失败=正确 (预测对了), 成功=中性
            return is_failure

    # ═══════════════════════════════════════════════════════════
    # Dimension 2: Learning Effectiveness
    # ═══════════════════════════════════════════════════════════

    def _compute_learning_effectiveness(
        self,
        effectiveness: LearningEffectiveness | None,
    ) -> float:
        """计算学习有效性因子.

        映射 effectiveness_score → 因子:
          - score >= 0.70: 学习有效 → 1.0 (不降级)
          - score >= 0.50: 学习一般 → 0.95
          - score >= 0.30: 学习偏低 → 0.85
          - score < 0.30:  学习无效 → 0.70
          - None:          无评估 → 1.0 (不调整)
        """
        if effectiveness is None:
            return 1.0

        score = effectiveness.effectiveness_score
        if score >= 0.70:
            return 1.0
        elif score >= 0.50:
            return 0.95
        elif score >= 0.30:
            return 0.85
        else:
            return 0.70

    # ═══════════════════════════════════════════════════════════
    # Dimension 3: Context Similarity
    # ═══════════════════════════════════════════════════════════

    def _compute_context_similarity(
        self,
        context: dict[str, Any],
        source: str = "",
    ) -> float:
        """计算上下文相似度.

        比较当前上下文与历史记录的上下文:
          - 有相似历史 → 1.0 (可信)
          - 无相似历史 → 0.80 (陌生上下文，降级)
          - 无历史 → 1.0 (不调整)
          - 空上下文 → 1.0 (不调整)
        """
        if not context:
            return 1.0

        resolved = [r for r in self._history if r.is_resolved]
        if source:
            resolved = [r for r in resolved if r.source == source]

        if not resolved:
            return 1.0

        # 比较上下文相似度
        current_key = self._make_context_key(context)
        if not current_key:
            return 1.0

        similarities = []
        for r in resolved:
            if r.context_key:
                sim = self._key_similarity(current_key, r.context_key)
                if r.is_accurate:
                    similarities.append(sim)
                else:
                    # 不准确的预测降低相似度权重
                    similarities.append(sim * 0.5)

        if not similarities:
            return 0.80  # 无比对数据 → 陌生上下文

        max_sim = max(similarities)
        # 映射: 0.0 → 0.80, 1.0 → 1.0
        return round(0.80 + max_sim * 0.20, 4)

    def _make_context_key(self, context: dict[str, Any]) -> str:
        """从上下文生成标准化键."""
        parts = []
        for key in sorted(context.keys()):
            val = str(context[key]).lower().strip()
            if val:
                parts.append(f"{key}:{val}")
        return "|".join(parts)

    def _key_similarity(self, key1: str, key2: str) -> float:
        """计算两个上下文键的相似度."""
        if not key1 or not key2:
            return 0.0
        if key1 == key2:
            return 1.0

        parts1 = set(key1.split("|"))
        parts2 = set(key2.split("|"))
        if not parts1 or not parts2:
            return 0.0

        intersection = parts1 & parts2
        union = parts1 | parts2
        return len(intersection) / len(union)

    # ═══════════════════════════════════════════════════════════
    # Dimension 4: Freshness
    # ═══════════════════════════════════════════════════════════

    def _compute_freshness(
        self,
        timestamps: list[str] | None,
    ) -> float:
        """计算数据时效性因子.

        基于支撑数据的时间戳:
          - 全部近期 (<= 7天) → 1.0
          - 混合 → 0.90
          - 全部过期 (> 30天) → 0.70
          - 无时间戳 → 1.0 (不调整)
        """
        if not timestamps:
            return 1.0

        now = datetime.now(timezone.utc)
        ages_days: list[float] = []

        for ts in timestamps:
            try:
                dt = datetime.fromisoformat(ts)
                days = (now - dt).total_seconds() / 86400
                ages_days.append(days)
            except (ValueError, TypeError):
                continue

        if not ages_days:
            return 0.85

        avg_age = sum(ages_days) / len(ages_days)

        if avg_age <= self._freshness_recent:
            return 1.0
        elif avg_age <= self._freshness_stale:
            # 线性衰减: recent → stale 从 1.0 → 0.70
            ratio = (avg_age - self._freshness_recent) / (self._freshness_stale - self._freshness_recent)
            return round(1.0 - ratio * 0.30, 4)
        else:
            return 0.70

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    def _get_weights(self) -> dict[str, float]:
        """获取维度权重.

        优先从 LearningStrategyState 读取，否则使用默认值。
        """
        if self._strategy_state is not None:
            return {
                "historical_accuracy": self._strategy_state.pattern_weight,
                "learning_effectiveness": self._strategy_state.memory_weight,
                "context_similarity": 0.25,
                "freshness": 0.25,
            }
        return {
            "historical_accuracy": self.DEFAULT_WEIGHT_HISTORICAL_ACCURACY,
            "learning_effectiveness": self.DEFAULT_WEIGHT_LEARNING_EFFECTIVENESS,
            "context_similarity": self.DEFAULT_WEIGHT_CONTEXT_SIMILARITY,
            "freshness": self.DEFAULT_WEIGHT_FRESHNESS,
        }

    def _generate_adjustments(
        self,
        ha: float,
        le: float,
        cs: float,
        fr: float,
        base: float,
        adjusted: float,
    ) -> list[str]:
        """生成调整说明."""
        adjustments: list[str] = []

        if ha < 0.90:
            adjustments.append(
                f"Historical accuracy low ({ha:.0%}) — confidence downgraded"
            )
        if le < 0.90:
            adjustments.append(
                f"Learning effectiveness reduced ({le:.0%}) — confidence adjusted"
            )
        if cs < 0.90:
            adjustments.append(
                f"Context similarity low ({cs:.0%}) — unfamiliar context"
            )
        if fr < 0.90:
            adjustments.append(
                f"Data freshness reduced ({fr:.0%}) — stale supporting data"
            )

        if not adjustments:
            adjustments.append("All dimensions nominal — confidence unchanged")

        if adjusted > base + 0.01:
            adjustments.append(f"Confidence upgraded: {base:.2f} → {adjusted:.2f}")
        elif adjusted < base - 0.01:
            adjustments.append(f"Confidence downgraded: {base:.2f} → {adjusted:.2f}")

        return adjustments

    def _generate_warnings(
        self,
        ha: float,
        le: float,
        cs: float,
        fr: float,
        adjusted: float,
    ) -> list[str]:
        """生成警告信息."""
        warnings: list[str] = []

        if ha < 0.50:
            warnings.append(f"CRITICAL: Historical accuracy very low ({ha:.0%})")
        if le < 0.80:
            warnings.append(f"Learning system underperforming ({le:.0%})")
        if cs < 0.85:
            warnings.append("Limited historical data for this context")
        if fr < 0.80:
            warnings.append("Supporting data is stale — consider refreshing")
        if adjusted < 0.50:
            warnings.append("Adjusted confidence below decision threshold")

        return warnings

    def _determine_level(self, score: float) -> str:
        """判定置信度等级."""
        if score >= 0.75:
            return "high"
        elif score >= 0.50:
            return "medium"
        elif score >= 0.25:
            return "low"
        return "insufficient"

    def get_accuracy_stats(self, source: str = "") -> dict[str, Any]:
        """获取历史准确率统计."""
        resolved = [r for r in self._history if r.is_resolved]
        if source:
            resolved = [r for r in resolved if r.source == source]

        if not resolved:
            return {"total": 0, "accuracy": 0.0, "samples": 0}

        total = len(resolved)
        accurate = sum(1 for r in resolved if r.is_accurate)
        accuracy = accurate / total if total > 0 else 0.0

        # 按置信度分段统计
        high_conf = [r for r in resolved if r.base_confidence >= 0.70]
        med_conf = [r for r in resolved if 0.50 <= r.base_confidence < 0.70]
        low_conf = [r for r in resolved if r.base_confidence < 0.50]

        return {
            "total": total,
            "accuracy": round(accuracy, 4),
            "samples": total,
            "high_confidence_accuracy": round(
                sum(1 for r in high_conf if r.is_accurate) / max(len(high_conf), 1), 4
            ),
            "medium_confidence_accuracy": round(
                sum(1 for r in med_conf if r.is_accurate) / max(len(med_conf), 1), 4
            ),
            "low_confidence_accuracy": round(
                sum(1 for r in low_conf if r.is_accurate) / max(len(low_conf), 1), 4
            ),
        }

    def __repr__(self) -> str:
        return (
            f"AdaptiveConfidenceEngine("
            f"history={len(self._history)}, "
            f"pending={len(self._pending)})"
        )


__all__ = [
    "AdaptiveConfidenceEngine",
]