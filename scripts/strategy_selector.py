"""Growth Strategy Layer — StrategySelector.

策略选择器：将增长假设转化为具体的策略类型和执行强度。

数据流:
  GrowthHypothesis
    + DiagnosisResult (根因 + 严重度)
    + ExperienceStore (变异历史成功率)
      ↓
  GrowthStrategy (策略类型 + 强度 + 预期影响 + 回滚条件)

不是 Agent，是 Engine。与 DiagnosticEngine / HypothesisGenerator 同级。
不新建 Memory，只消费已有 ExperienceStore。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)

from scripts.diagnostic_engine import (
    DiagnosisResult,
    RootCause,
    StrategyType,
)
from scripts.hypothesis_generator import (
    GrowthHypothesis,
    HYPOTHESIS_TEMPLATES,
    HypothesisTemplate,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

# 强度边界
_MIN_INTENSITY = 0.10
_MAX_INTENSITY = 2.00

# 降预算安全边界：最多降 50%
_MAX_REDUCTION = 0.50  # intensity 下限 = 0.50

# 升预算安全边界：最多升 30%
_MAX_INCREASE = 1.30  # intensity 上限 = 1.30

# 置信度阈值
_HIGH_CONFIDENCE = 0.70
_LOW_CONFIDENCE = 0.40

# 经验样本量阈值
_MIN_SAMPLES_FOR_BOOST = 3
_HIGH_SUCCESS_RATE = 0.60
_LOW_SUCCESS_RATE = 0.30


# ──────────────────────────────────────────────
# 根因 → 策略映射
# ──────────────────────────────────────────────


ROOT_CAUSE_TO_STRATEGY: dict[RootCause, StrategyType] = {
    RootCause.CREATIVE_FATIGUE: StrategyType.SUPPRESS,
    RootCause.AUDIENCE_SATURATION: StrategyType.SUPPRESS,
    RootCause.HOOK_DECAY: StrategyType.REFRESH,
    RootCause.AUDIENCE_QUALITY_DROP: StrategyType.SUPPRESS,
    RootCause.SCALING_TOO_FAST: StrategyType.SUPPRESS,
    RootCause.MONETIZATION_ISSUE: StrategyType.SUPPRESS,
    RootCause.CLICKBAIT_MISMATCH: StrategyType.PAUSE,
    RootCause.UNDIAGNOSED: StrategyType.MAINTAIN,
}


# ──────────────────────────────────────────────
# GrowthStrategy 数据模型
# ──────────────────────────────────────────────


@dataclass
class GrowthStrategy:
    """增长策略 — 假设转化为可执行的策略指令。

    领域无关，不限于 UA。描述"做什么、做多重、预期什么、何时回滚"。
    """

    # ── 标识 ──
    strategy_id: str = ""
    hypothesis_id: str = ""
    diagnosis_id: str = ""
    signal_id: str = ""

    # ── 策略核心 ──
    strategy_type: StrategyType = StrategyType.MAINTAIN
    target_creative_id: str = ""
    intensity: float = 1.0  # SUPPRESS: 0.5-0.9（降预算比例）; SCALE: 1.1-1.3; REFRESH/PAUSE: 1.0

    # ── 预期与回滚 ──
    expected_impact: dict[str, Any] = field(default_factory=dict)
    rollback_condition: str = ""
    time_horizon_days: int = 7

    # ── 置信度与推理 ──
    confidence: float = 0.0
    reasoning: str = ""

    # ── 元数据 ──
    root_cause: str = ""
    basis: str = ""  # 来自 hypothesis 的 basis
    mutation_type: str = ""  # 关联的变异类型
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.strategy_id:
            self.strategy_id = f"strat_{uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_safe(self) -> bool:
        """策略是否在安全边界内。"""
        if self.strategy_type == StrategyType.SUPPRESS:
            return self.intensity >= _MAX_REDUCTION
        if self.strategy_type == StrategyType.SCALE:
            return self.intensity <= _MAX_INCREASE
        return True

    @property
    def budget_change_ratio(self) -> float:
        """预算变化比例（1.0 = 不变, 0.7 = 降 30%, 1.2 = 升 20%）。"""
        if self.strategy_type == StrategyType.SUPPRESS:
            return self.intensity
        if self.strategy_type == StrategyType.SCALE:
            return self.intensity
        return 1.0

    @property
    def requires_execution(self) -> bool:
        """是否需要真实执行（MAINTAIN 不需要）。"""
        return self.strategy_type != StrategyType.MAINTAIN

    def to_dict(self) -> dict[str, Any]:
        """可序列化输出。"""
        return {
            "strategy_id": self.strategy_id,
            "hypothesis_id": self.hypothesis_id,
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal_id,
            "strategy_type": self.strategy_type.value,
            "target_creative_id": self.target_creative_id,
            "intensity": round(self.intensity, 4),
            "expected_impact": dict(self.expected_impact),
            "rollback_condition": self.rollback_condition,
            "time_horizon_days": self.time_horizon_days,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "root_cause": self.root_cause,
            "basis": self.basis,
            "mutation_type": self.mutation_type,
            "is_safe": self.is_safe,
            "budget_change_ratio": round(self.budget_change_ratio, 4),
            "requires_execution": self.requires_execution,
            "created_at": self.created_at,
        }


# ──────────────────────────────────────────────
# StrategySelector
# ──────────────────────────────────────────────


class StrategySelector:
    """策略选择器 — 从假设 + 诊断生成具体策略。

    使用方式:
        store = ExperienceStore()
        selector = StrategySelector(store)
        strategy = selector.select(hypothesis, diagnosis)
    """

    def __init__(
        self,
        store: ExperienceStore | None = None,
    ) -> None:
        """初始化。

        Args:
            store: ExperienceStore 实例。为 None 时不参考历史成功率。
        """
        self._store = store

    def select(
        self,
        hypothesis: GrowthHypothesis,
        diagnosis: DiagnosisResult,
    ) -> GrowthStrategy:
        """从假设 + 诊断生成策略。

        Args:
            hypothesis: HypothesisGenerator 的输出
            diagnosis: DiagnosticEngine 的输出（同一信号的）

        Returns:
            GrowthStrategy
        """
        # 0. 假设不可行动 → 直接降级为 MAINTAIN
        if not hypothesis.is_actionable:
            logger.info(
                "StrategySelector: hypothesis not actionable (confidence=%.4f), "
                "downgrading to MAINTAIN",
                hypothesis.confidence,
            )
            return GrowthStrategy(
                hypothesis_id=hypothesis.hypothesis_id,
                diagnosis_id=diagnosis.diagnosis_id,
                signal_id=diagnosis.signal_id,
                strategy_type=StrategyType.MAINTAIN,
                target_creative_id=diagnosis.creative_id,
                intensity=1.0,
                expected_impact={"metric": "none", "direction": "neutral"},
                rollback_condition="",
                time_horizon_days=7,
                confidence=hypothesis.confidence,
                reasoning=["假设置信度不足，降级为 MAINTAIN"],
                root_cause=diagnosis.root_cause.value,
                basis=hypothesis.basis,
                mutation_type="",
            )

        # 1. 确定策略类型
        strategy_type = self._select_strategy_type(diagnosis)

        # 2. 计算强度
        intensity = self._compute_intensity(
            strategy_type, hypothesis, diagnosis
        )

        # 3. 获取模板（回滚条件等）
        template = HYPOTHESIS_TEMPLATES.get(
            diagnosis.root_cause,
            HYPOTHESIS_TEMPLATES[RootCause.UNDIAGNOSED],
        )

        # 4. 构建推理链
        reasoning = self._build_reasoning(
            hypothesis, diagnosis, strategy_type, intensity
        )

        # 5. 查历史成功率
        hist_success_rate = self._get_historical_success_rate(template)

        # 6. 构建预期影响
        expected_impact = self._build_expected_impact(
            hypothesis, strategy_type, intensity, hist_success_rate
        )

        return GrowthStrategy(
            hypothesis_id=hypothesis.hypothesis_id,
            diagnosis_id=diagnosis.diagnosis_id,
            signal_id=diagnosis.signal_id,
            strategy_type=strategy_type,
            target_creative_id=diagnosis.creative_id,
            intensity=intensity,
            expected_impact=expected_impact,
            rollback_condition=template.falsification_condition,
            time_horizon_days=template.time_horizon_days,
            confidence=hypothesis.confidence,
            reasoning=reasoning,
            root_cause=diagnosis.root_cause.value,
            basis=hypothesis.basis,
            mutation_type=template.default_mutation_type.value,
        )

    def select_batch(
        self,
        pairs: list[tuple[GrowthHypothesis, DiagnosisResult]],
    ) -> list[GrowthStrategy]:
        """批量生成策略。

        Args:
            pairs: (hypothesis, diagnosis) 元组列表

        Returns:
            list[GrowthStrategy]
        """
        return [self.select(h, d) for h, d in pairs]

    # ── 内部方法 ──

    def _select_strategy_type(
        self, diagnosis: DiagnosisResult
    ) -> StrategyType:
        """根据诊断根因确定策略类型。

        优先使用诊断推荐的策略类型（已由 DiagnosticEngine 设置），
        fallback 到 ROOT_CAUSE_TO_STRATEGY 映射表。
        """
        # 诊断引擎已经设置了 recommended_strategy_type
        if diagnosis.recommended_strategy_type != StrategyType.MAINTAIN:
            return diagnosis.recommended_strategy_type

        # fallback: 从映射表查找
        return ROOT_CAUSE_TO_STRATEGY.get(
            diagnosis.root_cause, StrategyType.MAINTAIN
        )

    def _compute_intensity(
        self,
        strategy_type: StrategyType,
        hypothesis: GrowthHypothesis,
        diagnosis: DiagnosisResult,
    ) -> float:
        """计算策略强度。

        SUPPRESS: intensity ∈ [0.50, 0.90]（降 10%-50%）
            - 诊断置信度高 + 假设置信度高 → 降更多 (0.50)
            - 置信度低 → 降更少 (0.90)
            - 历史成功率低 → 保守 (加 0.10)

        SCALE: intensity ∈ [1.10, 1.30]（升 10%-30%）
            - 置信度高 → 升更多 (1.30)
            - 置信度低 → 升更少 (1.10)

        REFRESH / PAUSE: intensity = 1.0（不涉及预算比例）

        MAINTAIN: intensity = 1.0
        """
        diag_conf = diagnosis.confidence
        hyp_conf = hypothesis.confidence
        combined_conf = (diag_conf + hyp_conf) / 2.0

        if strategy_type == StrategyType.SUPPRESS:
            # 基础强度: 置信度越高降越多
            # combined_conf=1.0 → intensity=0.50（降 50%）
            # combined_conf=0.5 → intensity=0.75（降 25%）
            # combined_conf=0.0 → intensity=0.90（降 10%）
            base = 0.90 - (combined_conf * 0.40)

            # 历史成功率调整
            hist_rate = self._get_historical_success_rate(
                HYPOTHESIS_TEMPLATES.get(
                    diagnosis.root_cause,
                    HYPOTHESIS_TEMPLATES[RootCause.UNDIAGNOSED],
                )
            )
            if hist_rate is not None:
                if hist_rate < _LOW_SUCCESS_RATE:
                    # 历史成功率低 → 更保守（少降一点）
                    base = min(0.90, base + 0.10)
                elif hist_rate > _HIGH_SUCCESS_RATE:
                    # 历史成功率高 → 更激进（多降一点）
                    base = max(0.50, base - 0.05)

            # 安全边界
            return round(max(_MAX_REDUCTION, min(0.90, base)), 4)

        if strategy_type == StrategyType.SCALE:
            # 基础强度: 置信度越高升越多
            # combined_conf=1.0 → intensity=1.30（升 30%）
            # combined_conf=0.5 → intensity=1.15（升 15%）
            # combined_conf=0.0 → intensity=1.10（升 10%）
            base = 1.10 + (combined_conf * 0.20)

            # 历史成功率调整
            hist_rate = self._get_historical_success_rate(
                HYPOTHESIS_TEMPLATES.get(
                    diagnosis.root_cause,
                    HYPOTHESIS_TEMPLATES[RootCause.UNDIAGNOSED],
                )
            )
            if hist_rate is not None:
                if hist_rate < _LOW_SUCCESS_RATE:
                    base = max(1.10, base - 0.05)
                elif hist_rate > _HIGH_SUCCESS_RATE:
                    base = min(_MAX_INCREASE, base + 0.05)

            # 安全边界
            return round(max(1.10, min(_MAX_INCREASE, base)), 4)

        # REFRESH / PAUSE / MAINTAIN / EXPLORE
        return 1.0

    def _get_historical_success_rate(
        self, template: HypothesisTemplate
    ) -> float | None:
        """查询某种变异类型的历史成功率。

        Returns:
            成功率 [0, 1]，无数据时返回 None。
        """
        if not self._store:
            return None

        try:
            records = self._store.query_by_mutation_type(
                template.default_mutation_type
            )
            if len(records) < _MIN_SAMPLES_FOR_BOOST:
                return None
            successes = sum(1 for r in records if r.is_success)
            return successes / len(records)
        except Exception:
            return None

    def _build_reasoning(
        self,
        hypothesis: GrowthHypothesis,
        diagnosis: DiagnosisResult,
        strategy_type: StrategyType,
        intensity: float,
    ) -> str:
        """构建完整推理链（人类可读）。"""
        parts: list[str] = []

        # 信号 → 诊断
        parts.append(
            f"信号 {diagnosis.signal_type}"
            f" → 诊断 {diagnosis.root_cause.value}"
            f" (置信度 {diagnosis.confidence:.2f})"
        )

        # 诊断证据
        if diagnosis.evidence:
            parts.append(f"  证据: {'; '.join(diagnosis.evidence[:2])}")

        # 诊断 → 假设
        parts.append(
            f"  → 假设: {hypothesis.hypothesis}"
            f" (置信度 {hypothesis.confidence:.2f}, 依据: {hypothesis.basis})"
        )

        # 假设 → 策略
        if strategy_type == StrategyType.SUPPRESS:
            pct = round((1.0 - intensity) * 100)
            parts.append(f"  → 策略: SUPPRESS (降预算 {pct}%)")
        elif strategy_type == StrategyType.SCALE:
            pct = round((intensity - 1.0) * 100)
            parts.append(f"  → 策略: SCALE (升预算 {pct}%)")
        elif strategy_type == StrategyType.REFRESH:
            parts.append("  → 策略: REFRESH (暂停并变异)")
        elif strategy_type == StrategyType.PAUSE:
            parts.append("  → 策略: PAUSE (完全暂停)")
        elif strategy_type == StrategyType.MAINTAIN:
            parts.append("  → 策略: MAINTAIN (观察不动)")
        else:
            parts.append(f"  → 策略: {strategy_type.value}")

        return "\n".join(parts)

    def _build_expected_impact(
        self,
        hypothesis: GrowthHypothesis,
        strategy_type: StrategyType,
        intensity: float,
        hist_success_rate: float | None,
    ) -> dict[str, Any]:
        """构建预期影响。"""
        # 从假设继承基础预期
        base_impact = dict(hypothesis.expected_impact)

        # 补充策略特定信息
        result: dict[str, Any] = {
            "metric": base_impact.get("metric", "unknown"),
            "direction": base_impact.get("direction", "neutral"),
            "estimated_change": base_impact.get("estimated_change", 0.0),
            "time_horizon_days": base_impact.get(
                "time_horizon_days", 7
            ),
            "intensity": round(intensity, 4),
            "strategy_type": strategy_type.value,
        }

        # 历史成功率
        if hist_success_rate is not None:
            result["historical_success_rate"] = round(hist_success_rate, 4)
            result["historical_samples"] = (
                f"≥{_MIN_SAMPLES_FOR_BOOST}"
            )

        # 置信度基础
        result["confidence_basis"] = hypothesis.basis

        return result
