"""StrategySelector 单元测试。

覆盖:
  - 策略类型选择（8 种根因 → 5 种策略）
  - SUPPRESS 强度计算（置信度驱动 + 历史调整）
  - SCALE 强度计算
  - REFRESH / PAUSE / MAINTAIN 强度
  - 安全边界
  - 回滚条件
  - 推理链
  - 批量生成
  - end-to-end: Diagnosis → Hypothesis → Strategy
  - 序列化
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperimentDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceResult,
    MutationDetail,
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.diagnostic_engine import (
    DiagnosisCandidate,
    DiagnosisResult,
    DiagnosticEngine,
    RootCause,
    StrategyType,
)
from scripts.hypothesis_generator import (
    GrowthHypothesis,
    HypothesisGenerator,
)
from scripts.strategy_selector import (
    GrowthStrategy,
    ROOT_CAUSE_TO_STRATEGY,
    StrategySelector,
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
    return DiagnosisResult(
        signal_id="fs_test001",
        creative_id=creative_id,
        signal_type=signal_type,
        root_cause=root_cause,
        confidence=confidence,
        evidence=evidence or ["频次 6.0", "CTR -40%", "CPM 稳定"],
        recommended_strategy_type=strategy,
    )


def _make_hypothesis(
    confidence: float = 0.72,
    basis: str = "signal",
    creative_id: str = "c_001",
    root_cause: str = "creative_fatigue",
    diagnosis_id: str = "diag_test001",
    signal_id: str = "fs_test001",
    expected_impact: dict | None = None,
) -> GrowthHypothesis:
    return GrowthHypothesis(
        diagnosis_id=diagnosis_id,
        creative_id=creative_id,
        signal_id=signal_id,
        problem="test problem",
        hypothesis="test hypothesis",
        evidence=["evidence1"],
        confidence=confidence,
        expected_impact=expected_impact or {
            "metric": "roas",
            "direction": "positive",
            "estimated_change": 0.15,
            "time_horizon_days": 7,
        },
        validation_plan={"method": "budget_change", "duration_days": 7},
        basis=basis,
        root_cause=root_cause,
        recommended_strategy="suppress",
    )


def _make_experience_record(
    mutation_type: MutationType = MutationType.REFRESH_HOOK,
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    improvement: float = 0.20,
) -> ExperienceRecord:
    return ExperienceRecord(
        product_id="P01",
        creative_id="c_001",
        mutation=MutationDetail(mutation_type=mutation_type),
        experiment=ExperimentDetail(
            improvement=improvement, confidence=0.8
        ),
        context=ContextDetail(product_id="P01", platform="facebook"),
        result=ExperienceResult(
            outcome=outcome,
            success=(outcome == ExperienceOutcome.SUCCESS),
        ),
    )


def _build_store(
    count: int = 5,
    mutation_type: MutationType = MutationType.REFRESH_HOOK,
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    improvement: float = 0.20,
) -> ExperienceStore:
    store = ExperienceStore()
    for i in range(count):
        store.add(
            _make_experience_record(mutation_type, outcome, improvement)
        )
    return store


# ──────────────────────────────────────────────
# 数据模型测试
# ──────────────────────────────────────────────


class TestGrowthStrategyModel:
    def test_auto_id_and_timestamp(self):
        s = GrowthStrategy()
        assert s.strategy_id.startswith("strat_")
        assert s.created_at != ""

    def test_to_dict_serializable(self):
        s = GrowthStrategy(
            strategy_type=StrategyType.SUPPRESS,
            intensity=0.7,
            confidence=0.75,
        )
        d = s.to_dict()
        assert d["strategy_type"] == "suppress"
        assert d["intensity"] == 0.7
        assert d["confidence"] == 0.75
        assert "is_safe" in d
        assert "budget_change_ratio" in d
        assert "requires_execution" in d

    def test_is_safe_suppress(self):
        """SUPPRESS intensity >= 0.50 → safe。"""
        assert GrowthStrategy(
            strategy_type=StrategyType.SUPPRESS, intensity=0.50
        ).is_safe is True
        assert GrowthStrategy(
            strategy_type=StrategyType.SUPPRESS, intensity=0.49
        ).is_safe is False

    def test_is_safe_scale(self):
        """SCALE intensity <= 1.30 → safe。"""
        assert GrowthStrategy(
            strategy_type=StrategyType.SCALE, intensity=1.30
        ).is_safe is True
        assert GrowthStrategy(
            strategy_type=StrategyType.SCALE, intensity=1.31
        ).is_safe is False

    def test_budget_change_ratio(self):
        assert GrowthStrategy(
            strategy_type=StrategyType.SUPPRESS, intensity=0.7
        ).budget_change_ratio == 0.7
        assert GrowthStrategy(
            strategy_type=StrategyType.SCALE, intensity=1.2
        ).budget_change_ratio == 1.2
        assert GrowthStrategy(
            strategy_type=StrategyType.MAINTAIN, intensity=1.0
        ).budget_change_ratio == 1.0

    def test_requires_execution(self):
        assert GrowthStrategy(
            strategy_type=StrategyType.SUPPRESS
        ).requires_execution is True
        assert GrowthStrategy(
            strategy_type=StrategyType.MAINTAIN
        ).requires_execution is False


# ──────────────────────────────────────────────
# 策略类型选择测试
# ──────────────────────────────────────────────


class TestStrategyTypeSelection:
    @pytest.mark.parametrize("cause,expected", [
        (RootCause.CREATIVE_FATIGUE, StrategyType.SUPPRESS),
        (RootCause.AUDIENCE_SATURATION, StrategyType.SUPPRESS),
        (RootCause.HOOK_DECAY, StrategyType.REFRESH),
        (RootCause.AUDIENCE_QUALITY_DROP, StrategyType.SUPPRESS),
        (RootCause.SCALING_TOO_FAST, StrategyType.SUPPRESS),
        (RootCause.MONETIZATION_ISSUE, StrategyType.SUPPRESS),
        (RootCause.CLICKBAIT_MISMATCH, StrategyType.PAUSE),
        (RootCause.UNDIAGNOSED, StrategyType.MAINTAIN),
    ])
    def test_root_cause_maps_to_strategy(self, cause, expected):
        """每种根因映射到正确的策略类型。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=cause, strategy=expected
        )
        hyp = _make_hypothesis(root_cause=cause.value)
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == expected

    def test_fallback_to_mapping_when_maintain(self):
        """诊断推荐 MAINTAIN 但根因有映射 → 用映射表。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.CREATIVE_FATIGUE,
            strategy=StrategyType.MAINTAIN,  # 覆盖推荐
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        # MAINTAIN → fallback 到 ROOT_CAUSE_TO_STRATEGY
        assert strat.strategy_type == ROOT_CAUSE_TO_STRATEGY[RootCause.CREATIVE_FATIGUE]

    def test_scale_opportunity_uses_scale(self):
        """scale_opportunity 信号 → SCALE 策略。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.UNDIAGNOSED,
            signal_type="scale_opportunity",
            strategy=StrategyType.SCALE,
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == StrategyType.SCALE


# ──────────────────────────────────────────────
# SUPPRESS 强度测试
# ──────────────────────────────────────────────


class TestSuppressIntensity:
    def test_high_confidence_more_aggressive(self):
        """高置信度 → 降更多（intensity 更低）。"""
        selector = StrategySelector(None)

        diag_high = _make_diagnosis(confidence=0.95)
        hyp_high = _make_hypothesis(confidence=0.90)
        strat_high = selector.select(hyp_high, diag_high)

        diag_low = _make_diagnosis(confidence=0.30)
        hyp_low = _make_hypothesis(confidence=0.30)
        strat_low = selector.select(hyp_low, diag_low)

        assert strat_high.intensity < strat_low.intensity

    def test_intensity_bounded_50_to_90(self):
        """SUPPRESS intensity ∈ [0.50, 0.90]。

        置信度 < 0.4 时降级为 MAINTAIN（intensity=1.0）。
        """
        selector = StrategySelector(None)

        # 极端高置信度 → 正常 SUPPRESS
        diag = _make_diagnosis(confidence=1.0)
        hyp = _make_hypothesis(confidence=1.0)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.SUPPRESS
        assert 0.50 <= strat.intensity <= 0.90

        # 低置信度 → 降级 MAINTAIN
        diag = _make_diagnosis(confidence=0.0)
        hyp = _make_hypothesis(confidence=0.0)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.MAINTAIN
        assert strat.intensity == 1.0

    def test_low_history_success_makes_conservative(self):
        """历史成功率低 → 更保守（intensity 更高 = 降更少）。"""
        # 低成功率 store
        store_low = _build_store(
            5, outcome=ExperienceOutcome.FAILURE, improvement=-0.10
        )
        selector_low = StrategySelector(store_low)

        # 高成功率 store
        store_high = _build_store(
            5, outcome=ExperienceOutcome.SUCCESS, improvement=0.25
        )
        selector_high = StrategySelector(store_high)

        diag = _make_diagnosis(confidence=0.70)
        hyp = _make_hypothesis(confidence=0.70)

        strat_low = selector_low.select(hyp, diag)
        strat_high = selector_high.select(hyp, diag)

        # 低成功率 → intensity 更高（降更少）
        assert strat_low.intensity >= strat_high.intensity

    def test_high_history_success_more_aggressive(self):
        """历史成功率高 → 更激进（intensity 更低 = 降更多）。"""
        store = _build_store(
            5, outcome=ExperienceOutcome.SUCCESS, improvement=0.30
        )
        selector_with = StrategySelector(store)
        selector_none = StrategySelector(None)

        diag = _make_diagnosis(confidence=0.70)
        hyp = _make_hypothesis(confidence=0.70)

        strat_with = selector_with.select(hyp, diag)
        strat_none = selector_none.select(hyp, diag)

        assert strat_with.intensity <= strat_none.intensity

    def test_is_safe_always_true_for_suppress(self):
        """SUPPRESS 策略始终在安全边界内。"""
        selector = StrategySelector(None)
        for conf in [0.0, 0.3, 0.5, 0.7, 1.0]:
            diag = _make_diagnosis(confidence=conf)
            hyp = _make_hypothesis(confidence=conf)
            strat = selector.select(hyp, diag)
            assert strat.is_safe is True


# ──────────────────────────────────────────────
# SCALE 强度测试
# ──────────────────────────────────────────────


class TestScaleIntensity:
    def test_high_confidence_scales_more(self):
        """高置信度 → 升更多。"""
        selector = StrategySelector(None)

        diag_high = _make_diagnosis(
            confidence=0.95, strategy=StrategyType.SCALE
        )
        hyp_high = _make_hypothesis(confidence=0.90)
        strat_high = selector.select(hyp_high, diag_high)

        diag_low = _make_diagnosis(
            confidence=0.30, strategy=StrategyType.SCALE
        )
        hyp_low = _make_hypothesis(confidence=0.30)
        strat_low = selector.select(hyp_low, diag_low)

        assert strat_high.intensity > strat_low.intensity

    def test_intensity_bounded_110_to_130(self):
        """SCALE intensity ∈ [1.10, 1.30]。

        置信度 < 0.4 时降级为 MAINTAIN（intensity=1.0）。
        """
        selector = StrategySelector(None)
        for conf in [0.5, 1.0]:
            diag = _make_diagnosis(
                confidence=conf, strategy=StrategyType.SCALE
            )
            hyp = _make_hypothesis(confidence=conf)
            strat = selector.select(hyp, diag)
            assert strat.strategy_type == StrategyType.SCALE
            assert 1.10 <= strat.intensity <= 1.30

        # 低置信度 → 降级 MAINTAIN
        diag = _make_diagnosis(
            confidence=0.0, strategy=StrategyType.SCALE
        )
        hyp = _make_hypothesis(confidence=0.0)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.MAINTAIN
        assert strat.intensity == 1.0

    def test_is_safe_always_true_for_scale(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            confidence=1.0, strategy=StrategyType.SCALE
        )
        hyp = _make_hypothesis(confidence=1.0)
        strat = selector.select(hyp, diag)
        assert strat.is_safe is True


# ──────────────────────────────────────────────
# REFRESH / PAUSE / MAINTAIN 测试
# ──────────────────────────────────────────────


class TestOtherStrategies:
    def test_refresh_intensity_is_1(self):
        """REFRESH intensity = 1.0。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.HOOK_DECAY,
            strategy=StrategyType.REFRESH,
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == StrategyType.REFRESH
        assert strat.intensity == 1.0

    def test_pause_intensity_is_1(self):
        """PAUSE intensity = 1.0。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.CLICKBAIT_MISMATCH,
            strategy=StrategyType.PAUSE,
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == StrategyType.PAUSE
        assert strat.intensity == 1.0

    def test_maintain_intensity_is_1(self):
        """MAINTAIN intensity = 1.0, requires_execution=False。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.UNDIAGNOSED,
            strategy=StrategyType.MAINTAIN,
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == StrategyType.MAINTAIN
        assert strat.intensity == 1.0
        assert strat.requires_execution is False


# ──────────────────────────────────────────────
# 回滚条件测试
# ──────────────────────────────────────────────


class TestRollbackCondition:
    def test_creative_fatigue_rollback(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(root_cause=RootCause.CREATIVE_FATIGUE)
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "ROAS" in strat.rollback_condition or "下降" in strat.rollback_condition

    def test_undiagnosed_rollback(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(
            root_cause=RootCause.UNDIAGNOSED,
            strategy=StrategyType.MAINTAIN,
        )
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "恶化" in strat.rollback_condition

    @pytest.mark.parametrize("cause", list(RootCause))
    def test_all_causes_have_rollback(self, cause):
        """所有根因的策略都有回滚条件。"""
        selector = StrategySelector(None)
        strategy_type = ROOT_CAUSE_TO_STRATEGY.get(cause, StrategyType.MAINTAIN)
        diag = _make_diagnosis(root_cause=cause, strategy=strategy_type)
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert strat.rollback_condition != ""


# ──────────────────────────────────────────────
# 推理链测试
# ──────────────────────────────────────────────


class TestReasoning:
    def test_reasoning_contains_signal_and_diagnosis(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(signal_type="roas_decline")
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "roas_decline" in strat.reasoning
        assert "creative_fatigue" in strat.reasoning

    def test_reasoning_contains_hypothesis(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis()
        hyp = _make_hypothesis()
        hyp.hypothesis = "test hypothesis text"
        strat = selector.select(hyp, diag)

        assert "test hypothesis text" in strat.reasoning

    def test_reasoning_contains_strategy(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(strategy=StrategyType.SUPPRESS)
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "SUPPRESS" in strat.reasoning
        assert "降预算" in strat.reasoning

    def test_reasoning_contains_confidence(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis(confidence=0.85)
        hyp = _make_hypothesis(confidence=0.72)
        strat = selector.select(hyp, diag)

        assert "0.85" in strat.reasoning or "0.85" in strat.reasoning
        assert "0.72" in strat.reasoning or "0.72" in strat.reasoning


# ──────────────────────────────────────────────
# 预期影响测试
# ──────────────────────────────────────────────


class TestExpectedImpact:
    def test_contains_metric_and_intensity(self):
        selector = StrategySelector(None)
        diag = _make_diagnosis()
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "metric" in strat.expected_impact
        assert "intensity" in strat.expected_impact
        assert "strategy_type" in strat.expected_impact

    def test_historical_success_rate_included(self):
        """有历史数据时 expected_impact 包含 historical_success_rate。"""
        store = _build_store(5, outcome=ExperienceOutcome.SUCCESS)
        selector = StrategySelector(store)
        diag = _make_diagnosis()
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "historical_success_rate" in strat.expected_impact
        assert strat.expected_impact["historical_success_rate"] > 0

    def test_no_historical_success_rate_without_store(self):
        """无 store 时 expected_impact 不含 historical_success_rate。"""
        selector = StrategySelector(None)
        diag = _make_diagnosis()
        hyp = _make_hypothesis()
        strat = selector.select(hyp, diag)

        assert "historical_success_rate" not in strat.expected_impact


# ──────────────────────────────────────────────
# 批量生成测试
# ──────────────────────────────────────────────


class TestBatchSelect:
    def test_batch_multiple(self):
        selector = StrategySelector(None)
        pairs = [
            (_make_hypothesis(creative_id="c_1"), _make_diagnosis(creative_id="c_1")),
            (_make_hypothesis(creative_id="c_2"), _make_diagnosis(creative_id="c_2")),
            (_make_hypothesis(creative_id="c_3"), _make_diagnosis(creative_id="c_3")),
        ]
        strategies = selector.select_batch(pairs)

        assert len(strategies) == 3
        assert {s.target_creative_id for s in strategies} == {"c_1", "c_2", "c_3"}

    def test_batch_empty(self):
        selector = StrategySelector(None)
        assert selector.select_batch([]) == []


# ──────────────────────────────────────────────
# End-to-End: Diagnosis → Hypothesis → Strategy
# ──────────────────────────────────────────────


class TestEndToEnd:
    def test_full_chain_creative_fatigue(self):
        """完整链路: 信号 → 诊断 → 假设 → 策略。"""
        from dataclasses import dataclass
        from enum import Enum

        class _SigType(str, Enum):
            ROAS_DECLINE = "roas_decline"

        @dataclass
        class _MockSignal:
            signal_id: str = "fs_e2e"
            creative_id: str = "c_e2e"
            signal_type: _SigType = _SigType.ROAS_DECLINE

        # Step 1: 诊断
        engine = DiagnosticEngine()
        diag = engine.diagnose(
            _MockSignal(),
            {"spend": 200, "clicks": 60, "ctr": 0.015, "cpi": 5.0,
             "roas": 0.4, "impressions": 12000, "installs": 2000, "revenue": 80},
            {"spend": 200, "clicks": 100, "ctr": 0.025, "cpi": 5.0,
             "roas": 0.6, "impressions": 10000, "installs": 2000, "revenue": 120},
        )
        assert diag.root_cause == RootCause.CREATIVE_FATIGUE

        # Step 2: 假设
        store = _build_store(5, improvement=0.25)
        hyp_gen = HypothesisGenerator(store)
        hyp = hyp_gen.generate(diag, {"total_records": 10, "success_rate": 0.7})
        assert hyp.confidence > 0

        # Step 3: 策略
        selector = StrategySelector(store)
        strat = selector.select(hyp, diag)

        # 验证策略
        assert strat.strategy_type == StrategyType.SUPPRESS
        assert 0.50 <= strat.intensity <= 0.90
        assert strat.is_safe is True
        assert strat.requires_execution is True
        assert strat.root_cause == "creative_fatigue"
        assert strat.target_creative_id == "c_e2e"
        assert strat.rollback_condition != ""
        assert strat.reasoning != ""
        assert "信号" in strat.reasoning
        assert "诊断" in strat.reasoning
        assert "假设" in strat.reasoning
        assert "策略" in strat.reasoning

        # 全链路追溯
        assert strat.signal_id == diag.signal_id
        assert strat.diagnosis_id == diag.diagnosis_id
        assert strat.hypothesis_id == hyp.hypothesis_id

    def test_high_confidence_produces_aggressive_suppress(self):
        """高置信度链路 → 更激进的 SUPPRESS。"""
        # 诊断 + 假设都高置信度
        diag = _make_diagnosis(confidence=0.95)
        hyp = _make_hypothesis(confidence=0.90, basis="mixed")

        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)

        # combined_conf = (0.95 + 0.90) / 2 = 0.925
        # base = 0.90 - 0.925*0.40 = 0.53
        assert strat.intensity <= 0.60  # 应该降很多

    def test_low_confidence_produces_conservative_suppress(self):
        """低置信度链路 → 保守的 SUPPRESS。"""
        diag = _make_diagnosis(confidence=0.30)
        hyp = _make_hypothesis(confidence=0.30, basis="signal")

        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)

        # combined_conf = 0.30, base = 0.90 - 0.12 = 0.78
        assert strat.intensity >= 0.70  # 降更少

    def test_undiagnosed_produces_maintain(self):
        """undiagnosed → MAINTAIN, 不执行。"""
        diag = _make_diagnosis(
            root_cause=RootCause.UNDIAGNOSED,
            confidence=0.20,
            strategy=StrategyType.MAINTAIN,
        )
        hyp = _make_hypothesis(confidence=0.20, basis="signal")

        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)

        assert strat.strategy_type == StrategyType.MAINTAIN
        assert strat.requires_execution is False
        assert strat.intensity == 1.0

    def test_strategy_to_dict_full_chain(self):
        """策略 to_dict 包含全链路 ID。"""
        diag = _make_diagnosis()
        hyp = _make_hypothesis()
        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)

        d = strat.to_dict()
        assert d["diagnosis_id"] == diag.diagnosis_id
        assert d["hypothesis_id"] == hyp.hypothesis_id
        assert d["signal_id"] == diag.signal_id
        assert d["root_cause"] == "creative_fatigue"
        assert d["strategy_type"] == "suppress"
        assert d["is_safe"] is True
