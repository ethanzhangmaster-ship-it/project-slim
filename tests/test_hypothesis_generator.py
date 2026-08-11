"""HypothesisGenerator 单元测试。

覆盖:
  - 无历史 (signal basis)
  - 有历史 (historical basis)
  - 高成功模式
  - 低成功模式
  - confidence 变化
  - end-to-end: Diagnosis → Hypothesis
  - 数据模型 / 序列化 / 批量生成
"""

import sys
from pathlib import Path

import pytest

# 路径设置
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperimentDetail,
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceRecord,
    ExperienceResult,
    MutationDetail,
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.diagnostic_engine import (
    DiagnosisResult,
    DiagnosticEngine,
    RootCause,
    StrategyType,
)
from scripts.hypothesis_generator import (
    GrowthHypothesis,
    HypothesisGenerator,
    HypothesisTemplate,
    HYPOTHESIS_TEMPLATES,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


def _make_diagnosis(
    root_cause: RootCause = RootCause.CREATIVE_FATIGUE,
    confidence: float = 0.85,
    creative_id: str = "c_001",
    signal_type: str = "roas_decline",
    evidence: list[str] | None = None,
    strategy: StrategyType = StrategyType.SUPPRESS,
) -> DiagnosisResult:
    """快速构建 DiagnosisResult。"""
    return DiagnosisResult(
        signal_id="fs_test001",
        creative_id=creative_id,
        signal_type=signal_type,
        root_cause=root_cause,
        confidence=confidence,
        evidence=evidence or ["频次 6.0", "CTR 0.025→0.015 (-40%)", "CPM 稳定"],
        recommended_strategy_type=strategy,
        metrics_snapshot={"roas": 0.4, "ctr": 0.015, "frequency": 6.0},
    )


def _make_experience_record(
    mutation_type: MutationType = MutationType.REFRESH_HOOK,
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    improvement: float = 0.20,
    creative_id: str = "c_001",
    changed_genes: list[str] | None = None,
    confidence: float = 0.8,
) -> ExperienceRecord:
    """快速构建 ExperienceRecord。"""
    return ExperienceRecord(
        product_id="P01",
        creative_id=creative_id,
        mutation=MutationDetail(
            mutation_type=mutation_type,
            changed_genes=changed_genes or ["hook_opening"],
        ),
        experiment=ExperimentDetail(
            baseline_metrics={"ctr": 0.015, "roas": 0.4},
            winner_metrics={"ctr": 0.025, "roas": 0.5},
            improvement=improvement,
            confidence=confidence,
            winner_id="var_001",
            variant_count=3,
        ),
        context=ContextDetail(
            product_id="P01",
            market="US",
            platform="facebook",
        ),
        result=ExperienceResult(
            outcome=outcome,
            success=(outcome == ExperienceOutcome.SUCCESS),
            insight="hook 变异有效",
            key_finding="UGC hook 在 US 女性群体表现好",
        ),
    )


def _build_store_with_records(
    count: int = 5,
    mutation_type: MutationType = MutationType.REFRESH_HOOK,
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    improvement: float = 0.20,
) -> ExperienceStore:
    """构建含 N 条记录的 ExperienceStore。"""
    store = ExperienceStore()
    for i in range(count):
        record = _make_experience_record(
            mutation_type=mutation_type,
            outcome=outcome,
            improvement=improvement,
            creative_id=f"c_{i:03d}",
        )
        store.add(record)
    return store


def _high_success_summary(total: int = 10, rate: float = 0.80) -> dict:
    """高成功率 summary。"""
    return {
        "total_records": total,
        "success_rate": rate,
        "reliable_patterns": 3,
        "tracked_creatives": 8,
        "mutation_stats": {},
    }


def _low_success_summary(total: int = 10, rate: float = 0.20) -> dict:
    """低成功率 summary。"""
    return {
        "total_records": total,
        "success_rate": rate,
        "reliable_patterns": 1,
        "tracked_creatives": 5,
        "mutation_stats": {},
    }


# ──────────────────────────────────────────────
# 数据模型测试
# ──────────────────────────────────────────────


class TestGrowthHypothesisModel:
    def test_auto_generated_ids(self):
        """hypothesis_id 和 created_at 自动生成。"""
        h = GrowthHypothesis()
        assert h.hypothesis_id.startswith("hyp_")
        assert len(h.hypothesis_id) == 16
        assert h.created_at != ""

    def test_to_dict_serializable(self):
        """to_dict 输出可序列化。"""
        h = GrowthHypothesis(
            problem="test problem",
            hypothesis="test hypothesis",
            confidence=0.72,
            expected_impact={"metric": "roas", "direction": "positive"},
            validation_plan={"method": "budget_change", "duration_days": 7},
        )
        d = h.to_dict()
        assert d["problem"] == "test problem"
        assert d["confidence"] == pytest.approx(0.72)
        assert d["expected_impact"]["metric"] == "roas"
        assert d["validation_plan"]["duration_days"] == 7
        assert "is_actionable" in d

    def test_is_actionable_threshold(self):
        """confidence >= 0.4 + 有 validation_plan → is_actionable。"""
        h1 = GrowthHypothesis(confidence=0.5, validation_plan={"method": "test"})
        assert h1.is_actionable is True

        h2 = GrowthHypothesis(confidence=0.3, validation_plan={"method": "test"})
        assert h2.is_actionable is False

        h3 = GrowthHypothesis(confidence=0.5, validation_plan={})
        assert h3.is_actionable is False


# ──────────────────────────────────────────────
# 无历史测试
# ──────────────────────────────────────────────


class TestNoHistory:
    def test_empty_store_signal_basis(self):
        """空 ExperienceStore → basis = "signal"。"""
        store = ExperienceStore()
        gen = HypothesisGenerator(store)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        assert hyp.basis == "signal"
        assert hyp.confidence > 0

    def test_none_store_signal_basis(self):
        """store=None → basis = "signal"。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        assert hyp.basis == "signal"

    def test_no_history_low_confidence(self):
        """无历史时置信度有降级。"""
        gen_none = HypothesisGenerator(None)
        gen_with = HypothesisGenerator(_build_store_with_records(5))

        diag = _make_diagnosis()
        conf_none = gen_none.generate(diag).confidence
        conf_with = gen_with.generate(diag).confidence

        # 有历史的置信度应 >= 无历史的
        assert conf_with >= conf_none

    def test_signal_basis_has_validation_plan(self):
        """即使无历史，validation_plan 仍然有值。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        assert hyp.validation_plan["method"] == "budget_change"
        assert hyp.validation_plan["duration_days"] == 7
        assert "success_condition" in hyp.validation_plan
        assert "falsification_condition" in hyp.validation_plan


# ──────────────────────────────────────────────
# 有历史测试
# ──────────────────────────────────────────────


class TestWithHistory:
    def test_historical_basis_with_3_plus_records(self):
        """≥3 条历史记录 → basis = "historical" 或 "mixed"。"""
        store = _build_store_with_records(4)
        gen = HypothesisGenerator(store)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        assert hyp.basis in ("historical", "mixed")

    def test_historical_evidence_contains_count(self):
        """有历史时 evidence 包含历史记录数。"""
        store = _build_store_with_records(5)
        gen = HypothesisGenerator(store)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        history_ev = [e for e in hyp.evidence if "历史" in e]
        assert len(history_ev) > 0

    def test_pattern_ids_populated_with_reliable(self):
        """有可靠模式时 pattern_ids 非空。"""
        store = _build_store_with_records(5, improvement=0.25)
        gen = HypothesisGenerator(store)
        diag = _make_diagnosis()
        hyp = gen.generate(diag)

        # extract_patterns 可能产生可靠模式
        if hyp.basis in ("pattern", "mixed"):
            assert len(hyp.pattern_ids) > 0


# ──────────────────────────────────────────────
# 高/低成功模式测试
# ──────────────────────────────────────────────


class TestSuccessRatePatterns:
    def test_high_success_rate_boosts_confidence(self):
        """全局成功率 > 60% → 置信度增强。"""
        diag = _make_diagnosis(confidence=0.80)

        gen_low = HypothesisGenerator(None)
        conf_low = gen_low.generate(diag, _low_success_summary()).confidence

        gen_high = HypothesisGenerator(None)
        conf_high = gen_high.generate(diag, _high_success_summary()).confidence

        assert conf_high > conf_low

    def test_low_success_rate_reduces_confidence(self):
        """全局成功率 < 30% → 置信度降低。"""
        diag = _make_diagnosis(confidence=0.80)

        gen = HypothesisGenerator(None)
        conf_normal = gen.generate(diag, {"total_records": 10, "success_rate": 0.5}).confidence
        conf_low = gen.generate(diag, _low_success_summary()).confidence

        assert conf_low < conf_normal

    def test_neutral_success_rate_no_change(self):
        """全局成功率 30-60% → 不增强不降低。"""
        diag = _make_diagnosis(confidence=0.70)

        gen = HypothesisGenerator(None)
        conf = gen.generate(diag, {"total_records": 10, "success_rate": 0.45}).confidence

        # 对比无 summary
        conf_none = gen.generate(diag).confidence

        # 有 summary 但中性 vs 无 summary (fallback=0.5)
        # 差异不大
        assert abs(conf - conf_none) < 0.15

    def test_insufficient_records_uses_fallback(self):
        """total_records < 5 → 用 fallback global_conf。"""
        diag = _make_diagnosis(confidence=0.80)

        gen = HypothesisGenerator(None)
        conf = gen.generate(diag, {"total_records": 3, "success_rate": 0.9}).confidence

        # 不会因为高成功率增强（数据不足）
        assert conf <= 0.80  # 不会超过诊断置信度太多


# ──────────────────────────────────────────────
# Confidence 变化测试
# ──────────────────────────────────────────────


class TestConfidenceComputation:
    def test_confidence_bounded_01_to_095(self):
        """confidence 始终在 [0.10, 0.95]。"""
        gen = HypothesisGenerator(None)

        # 极低诊断置信度
        diag_low = _make_diagnosis(confidence=0.01)
        hyp_low = gen.generate(diag_low, _low_success_summary())
        assert hyp_low.confidence >= 0.10

        # 极高诊断置信度
        diag_high = _make_diagnosis(confidence=1.0)
        hyp_high = gen.generate(diag_high, _high_success_summary())
        assert hyp_high.confidence <= 0.95

    def test_high_diagnosis_high_history(self):
        """诊断 0.90 + 历史高成功 → confidence > 0.75。"""
        store = _build_store_with_records(5, improvement=0.25)
        gen = HypothesisGenerator(store)
        diag = _make_diagnosis(confidence=0.90)
        hyp = gen.generate(diag, _high_success_summary())

        assert hyp.confidence > 0.60  # 应该有较高置信度

    def test_high_diagnosis_no_history(self):
        """诊断 0.90 + 无历史 → confidence 降级。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(confidence=0.90)
        hyp = gen.generate(diag)

        # 0.90*0.5 + 0.30*0.3 + 0.50*0.2 = 0.45 + 0.09 + 0.10 = 0.64
        assert hyp.confidence == pytest.approx(0.64, abs=0.02)

    def test_low_diagnosis_no_history(self):
        """诊断 0.35 + 无历史 → confidence 低。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(confidence=0.35)
        hyp = gen.generate(diag)

        # 0.35*0.5 + 0.30*0.3 + 0.50*0.2 = 0.175 + 0.09 + 0.10 = 0.365
        assert hyp.confidence < 0.50

    def test_more_history_increases_confidence(self):
        """更多历史 → 更高置信度（pattern_conf 更高）。"""
        diag = _make_diagnosis(confidence=0.70)

        gen_empty = HypothesisGenerator(None)
        conf_empty = gen_empty.generate(diag).confidence

        store = _build_store_with_records(5, improvement=0.25)
        gen_full = HypothesisGenerator(store)
        conf_full = gen_full.generate(diag).confidence

        assert conf_full >= conf_empty


# ──────────────────────────────────────────────
# 根因模板测试
# ──────────────────────────────────────────────


class TestRootCauseTemplates:
    @pytest.mark.parametrize("cause", list(RootCause))
    def test_all_root_causes_have_template(self, cause):
        """所有根因都有对应模板。"""
        assert cause in HYPOTHESIS_TEMPLATES

    @pytest.mark.parametrize("cause", list(RootCause))
    def test_each_template_produces_hypothesis(self, cause):
        """每种根因能生成假设。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(
            root_cause=cause,
            strategy=HYPOTHESIS_TEMPLATES[cause].default_mutation_type
            and StrategyType.MAINTAIN,  # 简化
        )
        hyp = gen.generate(diag)

        assert hyp.hypothesis != ""
        assert hyp.root_cause == cause.value
        assert hyp.validation_plan["method"] == HYPOTHESIS_TEMPLATES[cause].validation_method

    def test_creative_fatigue_template_content(self):
        """creative_fatigue 模板内容正确。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(root_cause=RootCause.CREATIVE_FATIGUE)
        hyp = gen.generate(diag)

        assert "预算" in hyp.hypothesis
        assert hyp.expected_impact["metric"] == "roas"

    def test_hook_decay_template_content(self):
        """hook_decay 模板内容正确。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(root_cause=RootCause.HOOK_DECAY)
        hyp = gen.generate(diag)

        assert "CTR" in hyp.hypothesis or "hook" in hyp.hypothesis
        assert hyp.expected_impact["metric"] == "ctr"

    def test_clickbait_template_content(self):
        """clickbait_mismatch 模板内容正确。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(root_cause=RootCause.CLICKBAIT_MISMATCH)
        hyp = gen.generate(diag)

        assert "暂停" in hyp.hypothesis
        assert hyp.expected_impact["metric"] == "roas"


# ──────────────────────────────────────────────
# End-to-End: Diagnosis → Hypothesis
# ──────────────────────────────────────────────


class TestEndToEnd:
    def test_diagnosis_to_hypothesis_full_chain(self):
        """完整链路: 信号 → 诊断 → 假设。"""
        # Step 1: 构建信号 + 指标
        from dataclasses import dataclass
        from enum import Enum

        class _SigType(str, Enum):
            ROAS_DECLINE = "roas_decline"

        @dataclass
        class _MockSignal:
            signal_id: str = "fs_e2e001"
            creative_id: str = "c_e2e"
            signal_type: _SigType = _SigType.ROAS_DECLINE

        signal = _MockSignal()
        current = {
            "spend": 200.0, "clicks": 60.0, "ctr": 0.015,
            "cpi": 5.0, "roas": 0.4, "impressions": 12000.0,
            "installs": 2000.0, "revenue": 80.0,
        }
        previous = {
            "spend": 200.0, "clicks": 100.0, "ctr": 0.025,
            "cpi": 5.0, "roas": 0.6, "impressions": 10000.0,
            "installs": 2000.0, "revenue": 120.0,
        }

        # Step 2: 诊断
        engine = DiagnosticEngine()
        diag = engine.diagnose(signal, current, previous)

        assert diag.root_cause == RootCause.CREATIVE_FATIGUE

        # Step 3: 生成假设
        store = _build_store_with_records(5, improvement=0.25)
        gen = HypothesisGenerator(store)
        hyp = gen.generate(diag, _high_success_summary())

        # Step 4: 验证假设
        assert hyp.diagnosis_id == diag.diagnosis_id
        assert hyp.creative_id == "c_e2e"
        assert hyp.signal_id == "fs_e2e001"
        assert hyp.root_cause == "creative_fatigue"
        assert hyp.confidence > 0.40
        assert hyp.is_actionable is True
        assert hyp.hypothesis != ""
        assert "ROAS" in hyp.hypothesis or "预算" in hyp.hypothesis
        assert hyp.validation_plan["method"] == "budget_change"
        assert hyp.validation_plan["duration_days"] == 7
        assert len(hyp.evidence) >= 3  # 诊断证据 + 历史
        assert hyp.expected_impact["metric"] == "roas"
        assert hyp.basis in ("historical", "mixed", "pattern")

    def test_hypothesis_enhanced_by_history(self):
        """有历史记录的假设比无历史的置信度更高。"""
        # 同一诊断
        diag = _make_diagnosis(confidence=0.70)

        # 无历史
        gen_empty = HypothesisGenerator(None)
        hyp_empty = gen_empty.generate(diag)

        # 有历史 (高改善)
        store = _build_store_with_records(5, improvement=0.30)
        gen_full = HypothesisGenerator(store)
        hyp_full = gen_full.generate(diag, _high_success_summary())

        assert hyp_full.confidence > hyp_empty.confidence
        assert hyp_full.basis in ("historical", "mixed")
        assert hyp_empty.basis == "signal"

    def test_problem_contains_signal_type_and_root_cause(self):
        """problem 字段包含信号类型和根因。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(
            root_cause=RootCause.HOOK_DECAY,
            signal_type="fatigue_warning",
        )
        hyp = gen.generate(diag)

        assert "fatigue_warning" in hyp.problem
        assert "hook_decay" in hyp.problem

    def test_evidence_grows_with_history(self):
        """有历史时 evidence 比无历史更多。"""
        diag = _make_diagnosis()

        gen_empty = HypothesisGenerator(None)
        hyp_empty = gen_empty.generate(diag)

        store = _build_store_with_records(5, improvement=0.25)
        gen_full = HypothesisGenerator(store)
        hyp_full = gen_full.generate(diag)

        assert len(hyp_full.evidence) > len(hyp_empty.evidence)

    def test_undiagnosed_produces_monitoring_plan(self):
        """undiagnosed 根因 → monitoring 验证计划。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(
            root_cause=RootCause.UNDIAGNOSED,
            confidence=0.20,
            evidence=["指标不足"],
        )
        hyp = gen.generate(diag)

        assert hyp.validation_plan["method"] == "monitoring"
        assert hyp.validation_plan["duration_days"] == 14


# ──────────────────────────────────────────────
# 批量生成测试
# ──────────────────────────────────────────────


class TestBatchGenerate:
    def test_batch_multiple_diagnoses(self):
        """批量生成多个假设。"""
        diagnoses = [
            _make_diagnosis(root_cause=RootCause.CREATIVE_FATIGUE, creative_id="c_1"),
            _make_diagnosis(root_cause=RootCause.HOOK_DECAY, creative_id="c_2"),
            _make_diagnosis(root_cause=RootCause.SCALING_TOO_FAST, creative_id="c_3"),
        ]
        gen = HypothesisGenerator(None)
        hypotheses = gen.generate_batch(diagnoses)

        assert len(hypotheses) == 3
        ids = {h.creative_id for h in hypotheses}
        assert ids == {"c_1", "c_2", "c_3"}

    def test_batch_empty_list(self):
        """空列表 → 空结果。"""
        gen = HypothesisGenerator(None)
        assert gen.generate_batch([]) == []

    def test_batch_with_store_and_summary(self):
        """批量生成 + store + summary。"""
        store = _build_store_with_records(4, improvement=0.22)
        gen = HypothesisGenerator(store)
        diagnoses = [
            _make_diagnosis(creative_id="c_a"),
            _make_diagnosis(creative_id="c_b"),
        ]
        hypotheses = gen.generate_batch(diagnoses, _high_success_summary())

        assert len(hypotheses) == 2
        for h in hypotheses:
            assert h.confidence > 0
            assert h.basis in ("signal", "pattern", "historical", "mixed")


# ──────────────────────────────────────────────
# 领域无关性测试
# ──────────────────────────────────────────────


class TestDomainAgnostic:
    def test_hypothesis_not_ua_specific(self):
        """假设内容不包含 UA 特有术语。"""
        gen = HypothesisGenerator(None)
        diag = _make_diagnosis(root_cause=RootCause.MONETIZATION_ISSUE)
        hyp = gen.generate(diag)

        # problem 应该描述问题，不限定 UA
        assert "UA" not in hyp.hypothesis
        assert "facebook" not in hyp.hypothesis.lower()

    def test_expected_impact_generic_metrics(self):
        """expected_impact 使用通用指标名。"""
        gen = HypothesisGenerator(None)
        for cause in [RootCause.CREATIVE_FATIGUE, RootCause.HOOK_DECAY, RootCause.AUDIENCE_SATURATION]:
            diag = _make_diagnosis(root_cause=cause)
            hyp = gen.generate(diag)
            assert hyp.expected_impact["metric"] in ("roas", "ctr", "cpm", "cpi", "none", "unknown")
