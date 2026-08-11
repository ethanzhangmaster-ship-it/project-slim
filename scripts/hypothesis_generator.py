"""Growth Strategy Layer — HypothesisGenerator.

假设生成器：从诊断结果 + 历史经验生成可验证的增长假设。

数据流:
  DiagnosisResult
    + ExperienceStore.extract_patterns()   → 历史模式
    + ExperienceStore.query_by_mutation_type() → 变异历史
    + enricher_summary                     → 全局统计
      ↓
  GrowthHypothesis

不是 Agent，是 Engine。与 DiagnosticEngine 同级。
不新建 Memory，只消费已有 ExperienceStore。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceRecord,
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

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 根因 → 假设模板
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class HypothesisTemplate:
    """假设模板 — 每种根因对应的假设结构。"""

    hypothesis_format: str        # 假设陈述模板（含占位符）
    validation_method: str        # 验证方法
    success_condition: str        # 成功条件
    falsification_condition: str  # 证伪条件
    default_mutation_type: MutationType
    default_ratio: float          # 默认预算调整比例
    default_recovery: float       # 默认预期恢复幅度
    time_horizon_days: int        # 默认验证周期


HYPOTHESIS_TEMPLATES: dict[RootCause, HypothesisTemplate] = {
    RootCause.CREATIVE_FATIGUE: HypothesisTemplate(
        hypothesis_format="降低疲劳创意预算 {ratio:.0%}，ROAS 将在 {days} 天内停止下降",
        validation_method="budget_change",
        success_condition="ROAS 停止下降或恢复 > 5%",
        falsification_condition="ROAS 继续下降 > 10%",
        default_mutation_type=MutationType.REFRESH_HOOK,
        default_ratio=0.70,
        default_recovery=0.10,
        time_horizon_days=7,
    ),
    RootCause.AUDIENCE_SATURATION: HypothesisTemplate(
        hypothesis_format="降低预算 {ratio:.0%} 以缓解竞价压力，CPM 将下降 15%",
        validation_method="budget_change",
        success_condition="CPM 下降 > 10%",
        falsification_condition="CPM 继续上升 > 5%",
        default_mutation_type=MutationType.VISUAL_VARIATION,
        default_ratio=0.70,
        default_recovery=0.15,
        time_horizon_days=7,
    ),
    RootCause.HOOK_DECAY: HypothesisTemplate(
        hypothesis_format="变异 hook 基因后，CTR 将恢复 {recovery:.0%}",
        validation_method="creative_refresh",
        success_condition="CTR 恢复 > 15%",
        falsification_condition="CTR 无变化或继续下降",
        default_mutation_type=MutationType.REFRESH_HOOK,
        default_ratio=1.0,
        default_recovery=0.20,
        time_horizon_days=7,
    ),
    RootCause.AUDIENCE_QUALITY_DROP: HypothesisTemplate(
        hypothesis_format="降低预算 {ratio:.0%}，CPI 将回落至正常水平",
        validation_method="budget_change",
        success_condition="CPI 下降 > 10%",
        falsification_condition="CPI 继续上升",
        default_mutation_type=MutationType.OFFER_CHANGE,
        default_ratio=0.80,
        default_recovery=0.10,
        time_horizon_days=7,
    ),
    RootCause.SCALING_TOO_FAST: HypothesisTemplate(
        hypothesis_format="降低预算 {ratio:.0%}，ROAS 将在 {days} 天内恢复",
        validation_method="budget_change",
        success_condition="ROAS 恢复 > 10%",
        falsification_condition="ROAS 继续下降",
        default_mutation_type=MutationType.OFFER_CHANGE,
        default_ratio=0.80,
        default_recovery=0.10,
        time_horizon_days=7,
    ),
    RootCause.MONETIZATION_ISSUE: HypothesisTemplate(
        hypothesis_format="降低预算 {ratio:.0%} 观察效果，需人工排查商业化",
        validation_method="budget_change",
        success_condition="ROAS 停止下降",
        falsification_condition="ROAS 继续下降 > 10%",
        default_mutation_type=MutationType.OFFER_CHANGE,
        default_ratio=0.80,
        default_recovery=0.05,
        time_horizon_days=7,
    ),
    RootCause.CLICKBAIT_MISMATCH: HypothesisTemplate(
        hypothesis_format="暂停误导性创意，ROAS 将恢复",
        validation_method="creative_refresh",
        success_condition="ROAS 恢复 > 10%",
        falsification_condition="ROAS 无变化",
        default_mutation_type=MutationType.FULL_REBUILD,
        default_ratio=0.0,
        default_recovery=0.10,
        time_horizon_days=7,
    ),
    RootCause.UNDIAGNOSED: HypothesisTemplate(
        hypothesis_format="维持当前状态观察，收集更多数据",
        validation_method="monitoring",
        success_condition="指标稳定",
        falsification_condition="指标持续恶化",
        default_mutation_type=MutationType.REFRESH_HOOK,
        default_ratio=1.0,
        default_recovery=0.0,
        time_horizon_days=14,
    ),
}


# ──────────────────────────────────────────────
# GrowthHypothesis 数据模型
# ──────────────────────────────────────────────


@dataclass
class GrowthHypothesis:
    """增长假设 — 可验证的因果预测。

    领域无关，不限于 UA。描述"如果做 X，那么 Y 会发生"的可验证命题。
    """

    # ── 标识 ──
    hypothesis_id: str = ""
    diagnosis_id: str = ""
    creative_id: str = ""
    signal_id: str = ""

    # ── 核心内容 ──
    problem: str = ""              # 发生了什么问题？
    hypothesis: str = ""           # 我认为为什么发生？下一步验证什么？
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0        # [0, 1]
    expected_impact: dict[str, Any] = field(default_factory=dict)
    validation_plan: dict[str, Any] = field(default_factory=dict)

    # ── 元数据 ──
    basis: str = ""                # signal / pattern / historical / mixed
    pattern_ids: list[str] = field(default_factory=list)
    root_cause: str = ""
    recommended_strategy: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            self.hypothesis_id = f"hyp_{uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_actionable(self) -> bool:
        """假设是否可行动 — 置信度 ≥ 0.4 且有验证计划。"""
        return self.confidence >= 0.4 and bool(self.validation_plan)

    def to_dict(self) -> dict[str, Any]:
        """可序列化输出。"""
        return {
            "hypothesis_id": self.hypothesis_id,
            "diagnosis_id": self.diagnosis_id,
            "creative_id": self.creative_id,
            "signal_id": self.signal_id,
            "problem": self.problem,
            "hypothesis": self.hypothesis,
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "expected_impact": dict(self.expected_impact),
            "validation_plan": dict(self.validation_plan),
            "basis": self.basis,
            "pattern_ids": list(self.pattern_ids),
            "root_cause": self.root_cause,
            "recommended_strategy": self.recommended_strategy,
            "is_actionable": self.is_actionable,
            "created_at": self.created_at,
        }


# ──────────────────────────────────────────────
# HypothesisGenerator
# ──────────────────────────────────────────────


# 置信度权重
_W_DIAGNOSIS = 0.50
_W_PATTERN = 0.30
_W_GLOBAL = 0.20

# 数据不足时的降级置信度
_FALLBACK_PATTERN_CONF = 0.30
_FALLBACK_GLOBAL_CONF = 0.50


class HypothesisGenerator:
    """假设生成器 — 从诊断结果 + 历史经验生成可验证假设。

    使用方式:
        store = ExperienceStore()
        gen = HypothesisGenerator(store)
        hypothesis = gen.generate(diagnosis, enricher_summary)
    """

    def __init__(
        self,
        store: ExperienceStore | None = None,
    ) -> None:
        """初始化。

        Args:
            store: ExperienceStore 实例。为 None 时所有假设降级为 signal basis。
        """
        self._store = store

    def generate(
        self,
        diagnosis: DiagnosisResult,
        enricher_summary: dict[str, Any] | None = None,
    ) -> GrowthHypothesis:
        """从单个诊断结果生成假设。

        Args:
            diagnosis: DiagnosticEngine 的输出
            enricher_summary: MemoryEnricher.get_summary() 的输出（可选）

        Returns:
            GrowthHypothesis
        """
        enricher_summary = enricher_summary or {}

        # 若未显式传递 summary，使用 store 自身的聚合统计
        # （使 V2 Growth Loop 能利用历史成功率数据校准置信度）
        if not enricher_summary and self._store is not None:
            enricher_summary = self._store.get_stats().to_dict()

        template = HYPOTHESIS_TEMPLATES.get(
            diagnosis.root_cause,
            HYPOTHESIS_TEMPLATES[RootCause.UNDIAGNOSED],
        )

        # 查找历史相似模式
        patterns = self._find_similar_patterns(diagnosis, template)
        history_count = self._count_history(diagnosis, template)

        # 确定 basis
        basis = self._determine_basis(patterns, history_count)

        # 计算置信度
        confidence = self._compute_confidence(
            diagnosis, patterns, enricher_summary
        )

        # 构建 problem
        problem = self._build_problem(diagnosis)

        # 构建 hypothesis 陈述
        hypothesis_text = template.hypothesis_format.format(
            ratio=template.default_ratio,
            days=template.time_horizon_days,
            recovery=template.default_recovery,
        )

        # 构建 evidence
        evidence = self._build_evidence(diagnosis, patterns, history_count)

        # 构建 expected_impact
        expected_impact = self._build_expected_impact(
            diagnosis, template, patterns
        )

        # 构建 validation_plan
        validation_plan = self._build_validation_plan(diagnosis, template)

        return GrowthHypothesis(
            diagnosis_id=diagnosis.diagnosis_id,
            creative_id=diagnosis.creative_id,
            signal_id=diagnosis.signal_id,
            problem=problem,
            hypothesis=hypothesis_text,
            evidence=evidence,
            confidence=confidence,
            expected_impact=expected_impact,
            validation_plan=validation_plan,
            basis=basis,
            pattern_ids=[p.pattern_id for p in patterns if p.is_reliable],
            root_cause=diagnosis.root_cause.value,
            recommended_strategy=diagnosis.recommended_strategy_type.value,
        )

    def generate_batch(
        self,
        diagnoses: list[DiagnosisResult],
        enricher_summary: dict[str, Any] | None = None,
    ) -> list[GrowthHypothesis]:
        """批量生成假设。"""
        return [
            self.generate(d, enricher_summary) for d in diagnoses
        ]

    # ── 内部方法 ──

    def _find_similar_patterns(
        self,
        diagnosis: DiagnosisResult,
        template: HypothesisTemplate,
    ) -> list[ExperiencePattern]:
        """从 ExperienceStore 中查找与当前根因相关的历史模式。"""
        if not self._store:
            return []

        try:
            all_patterns = self._store.extract_patterns(min_sample=2)
        except Exception as exc:
            logger.warning("HypothesisGenerator: extract_patterns failed: %s", exc)
            return []

        # 筛选 mutation_pattern 类型且 mutation_type 匹配的模式
        target_mutation = template.default_mutation_type.value
        relevant: list[ExperiencePattern] = []
        for p in all_patterns:
            if p.pattern_type == "mutation_pattern" and target_mutation in p.description:
                relevant.append(p)
            elif p.pattern_type == "gene_pattern" and p.is_reliable:
                relevant.append(p)

        # 按置信度降序
        relevant.sort(key=lambda p: p.confidence, reverse=True)
        return relevant[:5]  # 最多取 5 个

    def _count_history(
        self,
        diagnosis: DiagnosisResult,
        template: HypothesisTemplate,
    ) -> int:
        """统计同类型变异的历史记录数。"""
        if not self._store:
            return 0

        try:
            records = self._store.query_by_mutation_type(
                template.default_mutation_type
            )
            return len(records)
        except Exception:
            return 0

    def _determine_basis(
        self,
        patterns: list[ExperiencePattern],
        history_count: int,
    ) -> str:
        """确定假设的依据类型。"""
        has_history = history_count >= 3
        has_reliable = any(p.is_reliable for p in patterns)

        if has_history and has_reliable:
            return "mixed"
        if has_history:
            return "historical"
        if has_reliable:
            return "pattern"
        return "signal"

    def _compute_confidence(
        self,
        diagnosis: DiagnosisResult,
        patterns: list[ExperiencePattern],
        summary: dict[str, Any],
    ) -> float:
        """三因子加权置信度 + 失败连 streak 惩罚。

        confidence = diagnosis.confidence × 0.5
                   + pattern_confidence × 0.3
                   + global_calibration × 0.2
                   - failure_streak_penalty

        当历史成功率 < 0.2 且记录数 >= 5 时，应用惩罚：
          惩罚力度与失败严重程度、历史记录量成正比。
          目的: 防止同一类策略在长期失败后仍被重复生成。
        """
        # 因子 1: 诊断置信度
        diag_conf = diagnosis.confidence

        # 因子 2: 历史模式置信度
        if patterns:
            best = max(patterns, key=lambda p: p.confidence)
            pattern_conf = best.confidence
        else:
            pattern_conf = _FALLBACK_PATTERN_CONF

        # 因子 3: 全局成功率校准
        total = summary.get("total_records", 0)
        if total >= 5:
            rate = summary.get("success_rate", 0.5)
            if rate > 0.6:
                global_conf = min(1.0, diag_conf + 0.10)
            elif rate < 0.3:
                global_conf = max(0.1, diag_conf - 0.15)
            else:
                global_conf = diag_conf
        else:
            global_conf = _FALLBACK_GLOBAL_CONF

        # 失败连 streak 惩罚（成功率 < 0.2 且记录数 >= 5）
        failure_penalty = 0.0
        if total >= 5:
            rate = summary.get("success_rate", 0.5)
            if rate < 0.2:
                severity = (0.2 - rate) / 0.2
                volume_factor = min(1.0, (total - 5) / 15)
                failure_penalty = 0.30 * severity * (0.5 + 0.5 * volume_factor)

        confidence = (
            diag_conf * _W_DIAGNOSIS
            + pattern_conf * _W_PATTERN
            + global_conf * _W_GLOBAL
            - failure_penalty
        )
        return round(max(0.10, min(0.95, confidence)), 4)

    def _build_problem(self, diagnosis: DiagnosisResult) -> str:
        """构建问题描述。"""
        evidence_str = "; ".join(diagnosis.evidence[:3]) if diagnosis.evidence else "未知"
        return (
            f"信号 {diagnosis.signal_type}（根因: {diagnosis.root_cause.value}）: "
            f"{evidence_str}"
        )

    def _build_evidence(
        self,
        diagnosis: DiagnosisResult,
        patterns: list[ExperiencePattern],
        history_count: int,
    ) -> list[str]:
        """构建证据列表。"""
        ev: list[str] = []

        # 诊断证据
        ev.extend(diagnosis.evidence[:3])

        # 历史记录
        if history_count > 0:
            ev.append(f"历史相似记录 {history_count} 条")

        # 模式证据
        for p in patterns:
            if p.is_reliable:
                ev.append(
                    f"可靠模式: {p.description} "
                    f"(成功率 {p.success_rate:.0%}, n={p.sample_size})"
                )

        return ev

    def _build_expected_impact(
        self,
        diagnosis: DiagnosisResult,
        template: HypothesisTemplate,
        patterns: list[ExperiencePattern],
    ) -> dict[str, Any]:
        """构建预期影响。"""
        # 从历史模式推导预期改善
        if patterns:
            best = max(patterns, key=lambda p: p.avg_improvement)
            estimated = best.avg_improvement
        else:
            estimated = template.default_recovery

        # 确定受影响的核心指标
        metric_map = {
            RootCause.CREATIVE_FATIGUE: "roas",
            RootCause.AUDIENCE_SATURATION: "cpm",
            RootCause.HOOK_DECAY: "ctr",
            RootCause.AUDIENCE_QUALITY_DROP: "cpi",
            RootCause.SCALING_TOO_FAST: "roas",
            RootCause.MONETIZATION_ISSUE: "roas",
            RootCause.CLICKBAIT_MISMATCH: "roas",
            RootCause.UNDIAGNOSED: "none",
        }
        metric = metric_map.get(diagnosis.root_cause, "unknown")

        return {
            "metric": metric,
            "direction": "positive" if template.default_recovery > 0 else "neutral",
            "estimated_change": round(estimated, 4),
            "time_horizon_days": template.time_horizon_days,
            "confidence_basis": "pattern" if patterns else "template_default",
        }

    def _build_validation_plan(
        self,
        diagnosis: DiagnosisResult,
        template: HypothesisTemplate,
    ) -> dict[str, Any]:
        """构建验证计划。"""
        return {
            "method": template.validation_method,
            "duration_days": template.time_horizon_days,
            "success_condition": template.success_condition,
            "falsification_condition": template.falsification_condition,
            "budget_ratio": template.default_ratio,
        }
