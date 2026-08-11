"""DiagnosticEngine 单元测试。

覆盖:
  - 5 种根因诊断 (creative_fatigue / audience_saturation / hook_decay /
    audience_quality_drop / monetization_issue / scaling_too_fast / clickbait_mismatch)
  - 鉴别诊断
  - 边界情况 (空指标 / 零值 / 缺失上一周期)
  - SCALE_OPPORTUNITY 快速路径
  - 批量诊断
  - 推导指标 (cpm / frequency)
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

import pytest

# 确保能导入 scripts 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scripts.diagnostic_engine import (
    DiagnosisCandidate,
    DiagnosisResult,
    DiagnosticEngine,
    RootCause,
    StrategyType,
    ROOT_CAUSE_TO_STRATEGY,
    _pct_change,
    _safe_div,
    derive_cpm,
    derive_frequency,
    diagnose_signals,
)


# ──────────────────────────────────────────────
# 测试 fixtures
# ──────────────────────────────────────────────


class _FeedbackSignalType(str, Enum):
    """模拟 FeedbackSignalType。"""
    FATIGUE_WARNING = "fatigue_warning"
    ROAS_DECLINE = "roas_decline"
    SCALE_OPPORTUNITY = "scale_opportunity"
    CREATIVE_REPLACEMENT = "creative_replacement"
    DATA_COLLECTION = "data_collection"


@dataclass
class _MockSignal:
    """模拟 RealityFeedbackSignal。"""
    signal_id: str = "fs_test001"
    creative_id: str = "c_001"
    signal_type: _FeedbackSignalType = _FeedbackSignalType.ROAS_DECLINE
    severity: float = 0.8
    confidence: float = 0.8
    reason: list = None
    recommended_action: str = ""
    source_prediction_id: str = ""
    metadata: dict = None
    created_at: str = ""

    def __post_init__(self):
        if self.reason is None:
            self.reason = []
        if self.metadata is None:
            self.metadata = {}


def _metrics(
    spend=200.0,
    clicks=100.0,
    ctr=0.02,
    cpi=5.0,
    roas=0.5,
    impressions=None,
    installs=None,
    revenue=None,
):
    """快速构建指标 dict。"""
    if impressions is None:
        impressions = clicks / ctr if ctr > 0 else 0.0
    if installs is None:
        installs = spend / cpi if cpi > 0 else 0.0
    if revenue is None:
        revenue = spend * roas
    return {
        "spend": spend,
        "clicks": clicks,
        "ctr": ctr,
        "cpi": cpi,
        "roas": roas,
        "impressions": impressions,
        "installs": installs,
        "revenue": revenue,
    }


# ──────────────────────────────────────────────
# 工具函数测试
# ──────────────────────────────────────────────


class TestSafeDiv:
    def test_normal_division(self):
        assert _safe_div(10, 2) == 5.0

    def test_zero_denominator(self):
        assert _safe_div(10, 0) == 0.0

    def test_zero_denominator_with_default(self):
        assert _safe_div(10, 0, default=-1.0) == -1.0


class TestPctChange:
    def test_increase(self):
        assert _pct_change(100, 120) == pytest.approx(0.2)

    def test_decrease(self):
        assert _pct_change(100, 80) == pytest.approx(-0.2)

    def test_zero_old(self):
        assert _pct_change(0, 100) == 0.0

    def test_no_change(self):
        assert _pct_change(50, 50) == 0.0


class TestDeriveCpm:
    def test_normal(self):
        cpm = derive_cpm(100.0, 10000.0)
        assert cpm == pytest.approx(10.0)

    def test_zero_impressions(self):
        assert derive_cpm(100.0, 0.0) == 0.0


class TestDeriveFrequency:
    def test_normal(self):
        freq = derive_frequency(10000.0, 2000.0)
        assert freq == pytest.approx(5.0)

    def test_zero_installs(self):
        assert derive_frequency(10000.0, 0.0) == 0.0


# ──────────────────────────────────────────────
# 诊断决策树测试 — ROAS_DECLINE / CREATIVE_REPLACEMENT
# ──────────────────────────────────────────────


class TestDiagnoseDeclineCreativeFatigue:
    """CTR 下降 + 高频次 → creative_fatigue。"""

    def test_high_frequency_ctr_drop(self):
        """频次 > 5 + CTR 下降 > 15% → creative_fatigue (conf=0.90)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.015, cpi=5.0, roas=0.4, spend=200.0, clicks=60.0)
        # 制造高频率: impressions=12000, installs=2000 → freq=6.0
        current["impressions"] = 12000.0
        current["installs"] = 2000.0
        previous = _metrics(ctr=0.025, cpi=5.0, roas=0.6, spend=200.0, clicks=100.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.CREATIVE_FATIGUE
        assert result.confidence == pytest.approx(0.90)
        assert result.recommended_strategy_type == StrategyType.SUPPRESS
        assert len(result.evidence) == 3
        # 应有鉴别诊断
        assert len(result.differential) == 2
        assert result.differential[0].root_cause == RootCause.AUDIENCE_SATURATION

    def test_is_confident_property(self):
        """高置信度时 is_confident == True。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.010, roas=0.3)
        current["impressions"] = 15000.0
        current["installs"] = 2000.0  # freq=7.5
        previous = _metrics(ctr=0.030, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.is_confident is True


class TestDiagnoseDeclineAudienceSaturation:
    """CTR 下降 + CPM 上升 → audience_saturation。"""

    def test_cpm_increase_with_ctr_drop(self):
        """CPM 上升 > 20% + CTR 下降 → audience_saturation (conf=0.85)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        # current: spend=200, impressions=5000 → cpm=40
        current = _metrics(ctr=0.015, roas=0.4, spend=200.0, clicks=75.0)
        current["impressions"] = 5000.0
        current["installs"] = 2000.0  # freq=2.5（低于 SEVERE=5）

        # previous: spend=200, impressions=10000 → cpm=20
        previous = _metrics(ctr=0.025, roas=0.6, spend=200.0, clicks=100.0)
        previous["impressions"] = 10000.0
        previous["installs"] = 2000.0

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # cpm_change = (40-20)/20 = 100% > 20% → audience_saturation
        # 但频率 = 5000/2000 = 2.5 < SEVERE(5.0)，所以不进 fatigue 分支
        assert result.root_cause == RootCause.AUDIENCE_SATURATION
        assert result.confidence == pytest.approx(0.85)
        assert result.recommended_strategy_type == StrategyType.SUPPRESS
        assert len(result.differential) == 1


class TestDiagnoseDeclineHookDecay:
    """CTR 下降 + CPM 稳定 → hook_decay。"""

    def test_ctr_drop_cpm_stable(self):
        """CPM 变化 < 20% + CTR 下降 → hook_decay (conf=0.80)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        # current: spend=200, impressions=10000 → cpm=20
        current = _metrics(ctr=0.015, roas=0.4, spend=200.0, clicks=150.0)
        current["impressions"] = 10000.0
        current["installs"] = 5000.0  # freq=2.0

        # previous: spend=200, impressions=10500 → cpm≈19.05
        previous = _metrics(ctr=0.025, roas=0.6, spend=200.0, clicks=100.0)
        previous["impressions"] = 10500.0
        previous["installs"] = 5000.0

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # cpm_change = (20-19.05)/19.05 ≈ 5% < 20%，频率 2.0 < 5.0
        assert result.root_cause == RootCause.HOOK_DECAY
        assert result.confidence == pytest.approx(0.80)
        assert result.recommended_strategy_type == StrategyType.REFRESH


class TestDiagnoseDeclineAudienceQualityDrop:
    """CTR 稳定 + CPI 上升 → audience_quality_drop。"""

    def test_cpi_increase_ctr_stable(self):
        """CPI 上升 > 20% + CTR 稳定 → audience_quality_drop (conf=0.82)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.020, cpi=8.0, roas=0.4)  # cpi 8 vs prev 5 → +60%
        previous = _metrics(ctr=0.020, cpi=5.0, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # ctr_change = 0%, cpi_change = +60% > 20%
        assert result.root_cause == RootCause.AUDIENCE_QUALITY_DROP
        assert result.confidence == pytest.approx(0.82)
        assert result.recommended_strategy_type == StrategyType.SUPPRESS


class TestDiagnoseDeclineScalingTooFast:
    """CTR 稳定 + 花费大增 → scaling_too_fast。"""

    def test_spend_increase_over_50pct(self):
        """花费增加 > 50% + CTR/CPI 稳定 → scaling_too_fast (conf=0.80)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.020, cpi=5.0, roas=0.4, spend=400.0)
        previous = _metrics(ctr=0.020, cpi=5.0, roas=0.6, spend=200.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # ctr_change=0, cpi_change=0, spend_change=+100% > 50%
        assert result.root_cause == RootCause.SCALING_TOO_FAST
        assert result.confidence == pytest.approx(0.80)


class TestDiagnoseDeclineMonetizationIssue:
    """CTR/CPI/花费都稳定但 ROAS 下降 → monetization_issue。"""

    def test_all_stable_but_roas_drop(self):
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.020, cpi=5.0, roas=0.4, spend=200.0)
        previous = _metrics(ctr=0.020, cpi=5.0, roas=0.6, spend=200.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.MONETIZATION_ISSUE
        assert result.confidence == pytest.approx(0.65)
        assert len(result.differential) == 2


class TestDiagnoseDeclineClickbaitMismatch:
    """CTR 上升 + ROAS 下降 → clickbait_mismatch。"""

    def test_ctr_up_roas_down(self):
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.030, cpi=5.0, roas=0.3, spend=200.0)
        previous = _metrics(ctr=0.020, cpi=5.0, roas=0.6, spend=200.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # ctr_change = +50% > 15%
        assert result.root_cause == RootCause.CLICKBAIT_MISMATCH
        assert result.confidence == pytest.approx(0.78)
        assert result.recommended_strategy_type == StrategyType.PAUSE


# ──────────────────────────────────────────────
# 疲劳信号诊断测试
# ──────────────────────────────────────────────


class TestDiagnoseFatigue:
    def test_severe_frequency_confirms_fatigue(self):
        """频次 > 5 + CTR 下降 → creative_fatigue (conf=0.90)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.FATIGUE_WARNING)
        current = _metrics(ctr=0.015, roas=0.4)
        current["impressions"] = 12000.0
        current["installs"] = 2000.0  # freq=6.0
        previous = _metrics(ctr=0.025, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.CREATIVE_FATIGUE
        assert result.confidence == pytest.approx(0.90)

    def test_medium_frequency_possible_fatigue(self):
        """频次 3-5 + CTR 下降 → creative_fatigue (conf=0.70)。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.FATIGUE_WARNING)
        current = _metrics(ctr=0.015, roas=0.4)
        current["impressions"] = 10000.0
        current["installs"] = 2500.0  # freq=4.0
        previous = _metrics(ctr=0.025, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.CREATIVE_FATIGUE
        assert result.confidence == pytest.approx(0.70)
        assert len(result.differential) == 2

    def test_low_frequency_severe_ctr_drop_hook_decay(self):
        """频次低 + CTR 严重下降(>30%) → hook_decay。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.FATIGUE_WARNING)
        current = _metrics(ctr=0.010, roas=0.4)
        current["impressions"] = 5000.0
        current["installs"] = 2500.0  # freq=2.0
        previous = _metrics(ctr=0.025, roas=0.6)  # ctr_drop = -60%

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.HOOK_DECAY
        assert result.confidence == pytest.approx(0.75)

    def test_ambiguous_data_undiagnosed(self):
        """频次低 + CTR 变化小 → undiagnosed。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.FATIGUE_WARNING)
        current = _metrics(ctr=0.020, roas=0.5)
        current["impressions"] = 5000.0
        current["installs"] = 2500.0  # freq=2.0
        previous = _metrics(ctr=0.022, roas=0.5)  # ctr_drop ≈ -9%（不显著）

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.UNDIAGNOSED
        assert result.confidence == pytest.approx(0.35)
        assert len(result.differential) == 2


# ──────────────────────────────────────────────
# SCALE_OPPORTUNITY 诊断测试
# ──────────────────────────────────────────────


class TestDiagnoseScaleOpportunity:
    def test_scale_signal_returns_scale_strategy(self):
        """scale_opportunity 信号直接返回 SCALE 策略。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.SCALE_OPPORTUNITY)
        current = _metrics(roas=0.8, ctr=0.03)
        previous = _metrics(roas=0.7, ctr=0.025)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.recommended_strategy_type == StrategyType.SCALE
        assert result.confidence == pytest.approx(0.80)
        assert result.root_cause == RootCause.UNDIAGNOSED  # 不是问题

    def test_scale_without_previous_metrics(self):
        """无上一周期数据也能诊断 scale。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.SCALE_OPPORTUNITY)
        current = _metrics(roas=0.9, ctr=0.04)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current)

        assert result.recommended_strategy_type == StrategyType.SCALE


# ──────────────────────────────────────────────
# 边界情况
# ──────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_current_metrics(self):
        """空指标 → undiagnosed。"""
        signal = _MockSignal()
        engine = DiagnosticEngine()
        result = engine.diagnose(signal, {}, {})

        assert result.root_cause == RootCause.UNDIAGNOSED
        assert result.confidence == pytest.approx(0.20)

    def test_no_previous_metrics(self):
        """无上一周期 → ctr_change=0，走 CTR 稳定分支。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.02, cpi=5.0, roas=0.4, spend=200.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, {})

        # 无 prev → ctr_change=0, cpi_change=0, spend_change=0 → monetization_issue
        assert result.root_cause == RootCause.MONETIZATION_ISSUE

    def test_zero_ctr(self):
        """CTR=0 → 不崩溃，change=0。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.0, roas=0.3)
        previous = _metrics(ctr=0.0, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # ctr_change=0 → monetization_issue 分支
        assert result.root_cause in (RootCause.MONETIZATION_ISSUE, RootCause.UNDIAGNOSED)

    def test_zero_spend(self):
        """spend=0 → 不崩溃。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(spend=0.0, ctr=0.02, cpi=0.0, roas=0.0)
        previous = _metrics(spend=100.0, ctr=0.02, cpi=5.0, roas=0.5)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause in (
            RootCause.MONETIZATION_ISSUE,
            RootCause.AUDIENCE_QUALITY_DROP,
            RootCause.SCALING_TOO_FAST,
            RootCause.UNDIAGNOSED,
        )

    def test_unknown_signal_type(self):
        """未知信号类型 → undiagnosed。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.DATA_COLLECTION)
        current = _metrics()
        previous = _metrics()

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.root_cause == RootCause.UNDIAGNOSED
        assert result.confidence == pytest.approx(0.20)

    def test_dict_signal(self):
        """信号以 dict 形式传入也能正常工作。"""
        signal = {
            "signal_id": "fs_dict001",
            "creative_id": "c_dict",
            "signal_type": "roas_decline",
        }
        current = _metrics(ctr=0.015, roas=0.4)
        current["impressions"] = 12000.0
        current["installs"] = 2000.0  # freq=6.0
        previous = _metrics(ctr=0.025, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.creative_id == "c_dict"
        assert result.signal_id == "fs_dict001"
        assert result.root_cause == RootCause.CREATIVE_FATIGUE


# ──────────────────────────────────────────────
# 诊断结果属性测试
# ──────────────────────────────────────────────


class TestDiagnosisResultProperties:
    def test_auto_generated_ids(self):
        """diagnosis_id 和 created_at 自动生成。"""
        signal = _MockSignal()
        engine = DiagnosticEngine()
        result = engine.diagnose(signal, _metrics(), _metrics())

        assert result.diagnosis_id.startswith("diag_")
        assert len(result.diagnosis_id) == 17  # "diag_" + 12 hex
        assert result.created_at != ""

    def test_to_dict_serializable(self):
        """to_dict 输出可序列化。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.015, roas=0.4)
        current["impressions"] = 12000.0
        current["installs"] = 2000.0
        previous = _metrics(ctr=0.025, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)
        d = result.to_dict()

        assert "diagnosis_id" in d
        assert "root_cause" in d
        assert d["root_cause"] == "creative_fatigue"
        assert "differential" in d
        assert isinstance(d["differential"], list)
        assert "metrics_snapshot" in d
        assert "ctr_change" in d["metrics_snapshot"]

    def test_is_confident_threshold(self):
        """conf=0.55 → is_confident=False; conf=0.65 → True。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.ROAS_DECLINE)
        current = _metrics(ctr=0.020, cpi=5.0, roas=0.4, spend=200.0)
        previous = _metrics(ctr=0.020, cpi=5.0, roas=0.6, spend=200.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # monetization_issue conf=0.65 > 0.6 → confident
        assert result.confidence == pytest.approx(0.65)
        assert result.is_confident is True

    def test_candidate_to_dict(self):
        """DiagnosisCandidate.to_dict() 输出正确。"""
        c = DiagnosisCandidate(
            root_cause=RootCause.CREATIVE_FATIGUE,
            probability=0.85,
            evidence=["频次 5.0"],
        )
        d = c.to_dict()
        assert d["root_cause"] == "creative_fatigue"
        assert d["probability"] == pytest.approx(0.85)
        assert d["evidence"] == ["频次 5.0"]


# ──────────────────────────────────────────────
# 根因 → 策略映射测试
# ──────────────────────────────────────────────


class TestRootCauseToStrategy:
    def test_all_root_causes_mapped(self):
        """所有根因都有对应策略。"""
        for cause in RootCause:
            assert cause in ROOT_CAUSE_TO_STRATEGY

    def test_fatigue_maps_to_suppress(self):
        assert ROOT_CAUSE_TO_STRATEGY[RootCause.CREATIVE_FATIGUE] == StrategyType.SUPPRESS

    def test_hook_decay_maps_to_refresh(self):
        assert ROOT_CAUSE_TO_STRATEGY[RootCause.HOOK_DECAY] == StrategyType.REFRESH

    def test_clickbait_maps_to_pause(self):
        assert ROOT_CAUSE_TO_STRATEGY[RootCause.CLICKBAIT_MISMATCH] == StrategyType.PAUSE

    def test_undiagnosed_maps_to_maintain(self):
        assert ROOT_CAUSE_TO_STRATEGY[RootCause.UNDIAGNOSED] == StrategyType.MAINTAIN


# ──────────────────────────────────────────────
# 指标快照测试
# ──────────────────────────────────────────────


class TestMetricsSnapshot:
    def test_snapshot_contains_all_fields(self):
        """快照包含所有当前/历史/变化率字段。"""
        signal = _MockSignal()
        current = _metrics(ctr=0.02, cpi=5.0, roas=0.5, spend=200.0)
        previous = _metrics(ctr=0.025, cpi=4.0, roas=0.6, spend=150.0)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)
        snap = result.metrics_snapshot

        # 当前指标
        for key in ("spend", "clicks", "ctr", "cpi", "roas", "impressions",
                     "installs", "revenue", "cpm", "frequency"):
            assert key in snap, f"missing {key}"

        # 历史指标
        for key in ("prev_spend", "prev_ctr", "prev_cpi", "prev_roas",
                     "prev_cpm", "prev_impressions", "prev_installs"):
            assert key in snap, f"missing {key}"

        # 变化率
        for key in ("ctr_change", "cpm_change", "cpi_change", "spend_change", "roas_change"):
            assert key in snap, f"missing {key}"

    def test_derived_cpm_correct(self):
        """推导 CPM 计算正确。"""
        signal = _MockSignal()
        current = _metrics(spend=100.0, clicks=50.0, ctr=0.02)
        # impressions = 50/0.02 = 2500
        # cpm = 100/2500*1000 = 40
        previous = _metrics()

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.metrics_snapshot["cpm"] == pytest.approx(40.0, rel=0.01)

    def test_derived_frequency_correct(self):
        """推导频次计算正确。"""
        signal = _MockSignal()
        current = _metrics(spend=200.0, cpi=5.0, ctr=0.02, clicks=100.0)
        # impressions = 100/0.02 = 5000
        # installs = 200/5 = 40
        # frequency = 5000/40 = 125
        previous = _metrics()

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        assert result.metrics_snapshot["frequency"] == pytest.approx(125.0, rel=0.01)


# ──────────────────────────────────────────────
# 批量诊断测试
# ──────────────────────────────────────────────


class TestDiagnoseSignals:
    def test_batch_multiple_signals(self):
        """批量诊断多个信号。"""
        signals = [
            _MockSignal(signal_id="fs_1", creative_id="c_1",
                       signal_type=_FeedbackSignalType.ROAS_DECLINE),
            _MockSignal(signal_id="fs_2", creative_id="c_2",
                       signal_type=_FeedbackSignalType.SCALE_OPPORTUNITY),
            _MockSignal(signal_id="fs_3", creative_id="c_3",
                       signal_type=_FeedbackSignalType.FATIGUE_WARNING),
        ]
        current_metrics = {
            "c_1": _metrics(ctr=0.015, roas=0.4),
            "c_2": _metrics(ctr=0.03, roas=0.8),
            "c_3": _metrics(ctr=0.015, roas=0.4),
        }
        current_metrics["c_3"]["impressions"] = 12000.0
        current_metrics["c_3"]["installs"] = 2000.0

        previous_metrics = {
            "c_1": _metrics(ctr=0.025, roas=0.6),
            "c_2": _metrics(ctr=0.025, roas=0.7),
            "c_3": _metrics(ctr=0.025, roas=0.6),
        }

        results = diagnose_signals(signals, current_metrics, previous_metrics)

        assert len(results) == 3
        ids = {r.signal_id for r in results}
        assert ids == {"fs_1", "fs_2", "fs_3"}

    def test_batch_skips_missing_metrics(self):
        """缺少指标的 creative 被跳过。"""
        signals = [
            _MockSignal(signal_id="fs_1", creative_id="c_1"),
            _MockSignal(signal_id="fs_2", creative_id="c_missing"),
        ]
        current_metrics = {"c_1": _metrics()}
        previous_metrics = {}

        results = diagnose_signals(signals, current_metrics, previous_metrics)

        assert len(results) == 1
        assert results[0].signal_id == "fs_1"

    def test_batch_empty_signals(self):
        """空信号列表 → 空结果。"""
        results = diagnose_signals([], {}, {})
        assert results == []


# ──────────────────────────────────────────────
# CREATIVE_REPLACEMENT 信号测试（复用 decline 决策树）
# ──────────────────────────────────────────────


class TestCreativeReplacementSignal:
    def test_replacement_uses_decline_tree(self):
        """creative_replacement 信号复用 decline 决策树。"""
        signal = _MockSignal(signal_type=_FeedbackSignalType.CREATIVE_REPLACEMENT)
        current = _metrics(ctr=0.015, roas=0.2)
        current["impressions"] = 12000.0
        current["installs"] = 2000.0  # freq=6.0
        previous = _metrics(ctr=0.025, roas=0.6)

        engine = DiagnosticEngine()
        result = engine.diagnose(signal, current, previous)

        # 应走 decline 决策树 → creative_fatigue
        assert result.root_cause == RootCause.CREATIVE_FATIGUE
        assert result.confidence == pytest.approx(0.90)
