"""E11.5.2 — Market Signal Processor (IAP) Test.

10 AC covering:
  1.  MarketSignal Schema
  2.  SignalType / SignalStrength
  3.  Acquisition Signal
  4.  Retention Signal
  5.  IAP Monetization Signal
  6.  LTV Signal
  7.  Creative DNA Mapping
  8.  Confidence Calculation
  9.  Serialization
  10. Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.market import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
    UAPerformanceAdapter,
    IAPPerformanceAdapter,
    AnalyticsPerformanceAdapter,
    SignalType,
    SignalStrength,
    MarketSignal,
    MarketSignalProcessor,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_ua(installs: int = 30000, spend: float = 10000.0) -> UAMetrics:
    return UAMetrics(
        impressions=100000,
        clicks=50000,
        installs=installs,
        spend=spend,
    )


def _make_eng(
    d1: float = 0.45,
    d7: float = 0.35,
    d30: float = 0.15,
    playtime: float = 42.0,
    level: float = 5.3,
) -> EngagementMetrics:
    return EngagementMetrics(
        d1_retention=d1,
        d7_retention=d7,
        d30_retention=d30,
        sessions=12.5,
        playtime=playtime,
        level_progress=level,
    )


def _make_iap(
    revenue: float = 50000.0,
    payers: int = 500,
    purchases: int = 1200,
    installs: int = 30000,
    d30_ltv: float = 8.0,
    d7_ltv: float = 1.2,
) -> IAPMetrics:
    return IAPMetrics(
        revenue=revenue,
        iap_revenue=48000.0,
        payer_count=payers,
        purchase_count=purchases,
        installs=installs,
        d7_ltv=d7_ltv,
        d30_ltv=d30_ltv,
        d90_ltv=15.0,
    )


def _make_full_feedback(creative_id: str = "creative_001") -> PerformanceFeedback:
    return PerformanceFeedback(
        creative_id=creative_id,
        campaign_id="campaign_001",
        source="facebook",
        period="2026-01-01_to_2026-01-07",
        ua_metrics=_make_ua(),
        engagement_metrics=_make_eng(),
        monetization_metrics=_make_iap(),
    )


def _make_processor() -> MarketSignalProcessor:
    return MarketSignalProcessor()


# ═══════════════════════════════════════════════════════════
# AC1 — MarketSignal Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_market_signal_create():
    """AC1a: MarketSignal creates with all fields."""
    signal = MarketSignal(
        creative_id="creative_001",
        genome_id="genome_001",
        quality_score=0.85,
        signals={"hook": 0.92, "visual": 0.75},
        signal_composition={"acquisition": "strong"},
        confidence=0.95,
    )

    assert signal.signal_id.startswith("sig_")
    assert signal.creative_id == "creative_001"
    assert signal.genome_id == "genome_001"
    assert signal.quality_score == 0.85
    assert signal.signals["hook"] == 0.92
    assert signal.confidence == 0.95


def test_ac1b_market_signal_has_genome_id():
    """AC1b: has_genome_id checks genome association."""
    sig = MarketSignal(genome_id="")
    assert sig.has_genome_id is False

    sig.genome_id = "genome_001"
    assert sig.has_genome_id is True


def test_ac1c_market_signal_is_reliable():
    """AC1c: is_reliable checks confidence >= 0.5."""
    assert MarketSignal(confidence=0.3).is_reliable is False
    assert MarketSignal(confidence=0.5).is_reliable is True
    assert MarketSignal(confidence=0.9).is_reliable is True


def test_ac1d_market_signal_is_high_confidence():
    """AC1d: is_high_confidence checks confidence >= 0.8."""
    assert MarketSignal(confidence=0.79).is_high_confidence is False
    assert MarketSignal(confidence=0.80).is_high_confidence is True


def test_ac1e_market_signal_best_signal():
    """AC1e: best_signal returns strongest gene."""
    signal = MarketSignal(signals={"hook": 0.92, "visual": 0.75, "reward": 0.88})
    best = signal.best_signal
    assert best is not None
    assert best[0] == "hook"
    assert best[1] == 0.92


def test_ac1f_market_signal_weakest_signal():
    """AC1f: weakest_signal returns weakest gene."""
    signal = MarketSignal(signals={"hook": 0.92, "visual": 0.75, "reward": 0.88})
    worst = signal.weakest_signal
    assert worst is not None
    assert worst[0] == "visual"
    assert worst[1] == 0.75


def test_ac1g_market_signal_get_signal_strength():
    """AC1g: get_signal_strength returns SignalStrength."""
    signal = MarketSignal(signals={"hook": 0.92, "visual": 0.35})

    assert signal.get_signal_strength("hook") == SignalStrength.VERY_STRONG
    assert signal.get_signal_strength("visual") == SignalStrength.WEAK
    assert signal.get_signal_strength("unknown") == SignalStrength.NONE


def test_ac1h_market_signal_get_signals_above():
    """AC1h: get_signals_above filters by threshold."""
    signal = MarketSignal(signals={"hook": 0.92, "visual": 0.75, "reward": 0.60})

    strong = signal.get_signals_above(0.80)
    assert len(strong) == 1
    assert "hook" in strong


# ═══════════════════════════════════════════════════════════
# AC2 — SignalType / SignalStrength
# ═══════════════════════════════════════════════════════════

def test_ac2_signal_type_enum():
    """AC2a: SignalType has 4 values."""
    assert SignalType.ACQUISITION.value == "acquisition"
    assert SignalType.ENGAGEMENT.value == "engagement"
    assert SignalType.MONETIZATION.value == "monetization"
    assert SignalType.CREATIVE.value == "creative"
    assert len(SignalType) == 4


def test_ac2b_signal_strength_from_score():
    """AC2b: SignalStrength.from_score maps correctly."""
    assert SignalStrength.from_score(0.95) == SignalStrength.VERY_STRONG
    assert SignalStrength.from_score(0.85) == SignalStrength.VERY_STRONG
    assert SignalStrength.from_score(0.75) == SignalStrength.STRONG
    assert SignalStrength.from_score(0.70) == SignalStrength.STRONG
    assert SignalStrength.from_score(0.50) == SignalStrength.MEDIUM
    assert SignalStrength.from_score(0.40) == SignalStrength.MEDIUM
    assert SignalStrength.from_score(0.10) == SignalStrength.WEAK
    assert SignalStrength.from_score(0.0) == SignalStrength.NONE


# ═══════════════════════════════════════════════════════════
# AC3 — Acquisition Signal
# ═══════════════════════════════════════════════════════════

def test_ac3_processor_creates_acquisition_signal():
    """AC3a: Processor creates acquisition signal from UA data."""
    fb = _make_full_feedback()
    processor = _make_processor()
    signal = processor.process(fb)

    assert "acquisition" in signal.signal_composition


def test_ac3b_good_cpi_produces_strong_acquisition():
    """AC3b: Low CPI → strong acquisition signal."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=30000, spend=15000.0)  # CPI=0.5
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["acquisition"] in ("strong", "very_strong")


def test_ac3c_high_cpi_produces_weak_acquisition():
    """AC3c: High CPI → weak acquisition signal."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=1000, spend=15000.0)  # CPI=15
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["acquisition"] in ("weak", "none")


def test_ac3d_no_ua_data_acquisition():
    """AC3d: No UA data → none acquisition."""
    fb = _make_full_feedback()
    fb.ua_metrics = None
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["acquisition"] == "none"


# ═══════════════════════════════════════════════════════════
# AC4 — Retention Signal
# ═══════════════════════════════════════════════════════════

def test_ac4_processor_creates_engagement_signal():
    """AC4a: Processor creates engagement signal from retention data."""
    fb = _make_full_feedback()
    processor = _make_processor()
    signal = processor.process(fb)

    assert "engagement" in signal.signal_composition


def test_ac4b_high_retention_strong_engagement():
    """AC4b: High D7 retention → strong engagement."""
    fb = _make_full_feedback()
    fb.engagement_metrics = _make_eng(d7=0.55)  # 55% D7
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["engagement"] in ("strong", "very_strong")


def test_ac4c_low_retention_weak_engagement():
    """AC4c: Low D7 retention → weak engagement."""
    fb = _make_full_feedback()
    fb.engagement_metrics = _make_eng(d7=0.10)  # 10% D7
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["engagement"] in ("weak", "none")


# ═══════════════════════════════════════════════════════════
# AC5 — IAP Monetization Signal
# ═══════════════════════════════════════════════════════════

def test_ac5_processor_creates_monetization_signal():
    """AC5a: Processor creates monetization signal from IAP data."""
    fb = _make_full_feedback()
    processor = _make_processor()
    signal = processor.process(fb)

    assert "monetization" in signal.signal_composition


def test_ac5b_high_pay_rate_strong_monetization():
    """AC5b: High pay rate → strong monetization."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(revenue=50000, payers=5000, installs=30000)  # 16.7% pay rate
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["monetization"] == "very_strong"


def test_ac5c_low_pay_rate_weak_monetization():
    """AC5c: Low pay rate → weak monetization."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(revenue=300, payers=30, installs=30000)  # 0.1% pay rate
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["monetization"] in ("weak", "none")


def test_ac5d_no_iap_data_monetization():
    """AC5d: No IAP data → none monetization."""
    fb = _make_full_feedback()
    fb.monetization_metrics = None
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signal_composition["monetization"] == "none"


# ═══════════════════════════════════════════════════════════
# AC6 — LTV Signal
# ═══════════════════════════════════════════════════════════

def test_ac6_high_ltv_strong_signal():
    """AC6a: High D30 LTV → high quality score."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(d30_ltv=12.0, d7_ltv=4.0)  # very high LTV
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.quality_score > 0.6


def test_ac6b_low_ltv_weak_signal():
    """AC6b: Low D30 LTV → low quality score."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(d30_ltv=0.5, d7_ltv=0.1)  # very low LTV
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.quality_score < 0.4


# ═══════════════════════════════════════════════════════════
# AC7 — Creative DNA Mapping
# ═══════════════════════════════════════════════════════════

def test_ac7_signals_contain_all_five_genes():
    """AC7a: signals dict contains all 5 gene slots."""
    fb = _make_full_feedback()
    processor = _make_processor()
    signal = processor.process(fb)

    assert "hook" in signal.signals
    assert "visual" in signal.signals
    assert "reward" in signal.signals
    assert "emotion" in signal.signals
    assert "gameplay" in signal.signals


def test_ac7b_high_pay_rate_boosts_reward():
    """AC7b: High pay rate → high reward gene signal."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(revenue=50000, payers=5000, installs=30000)
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signals["reward"] > 0.7


def test_ac7c_high_retention_boosts_emotion():
    """AC7c: High retention → high emotion gene signal."""
    fb = _make_full_feedback()
    fb.engagement_metrics = _make_eng(d7=0.55, playtime=55.0)
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signals["emotion"] > 0.6


def test_ac7d_strong_ua_boosts_hook():
    """AC7d: Good UA metrics → high hook gene signal."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=30000, spend=15000.0)  # CPI=0.5
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.signals["hook"] > 0.5


# ═══════════════════════════════════════════════════════════
# AC8 — Confidence Calculation
# ═══════════════════════════════════════════════════════════

def test_ac8_large_sample_high_confidence():
    """AC8a: Large sample → high confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=50000, spend=10000.0)
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.confidence > 0.8
    assert signal.sample_size == 50000


def test_ac8b_small_sample_low_confidence():
    """AC8b: Small sample → low confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=100, spend=100.0)
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.confidence < 0.5


def test_ac8c_partial_data_lower_confidence():
    """AC8c: Missing data sources → lower confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=50000)
    fb.engagement_metrics = None
    fb.monetization_metrics = None
    processor = _make_processor()
    signal = processor.process(fb)

    # Only UA data, so confidence should be lower than full data
    assert signal.confidence < 0.9


def test_ac8d_sample_size_zero():
    """AC8d: Zero sample → zero or near-zero confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = None
    processor = _make_processor()
    signal = processor.process(fb)

    assert signal.sample_size == 0
    assert signal.confidence < 0.5


# ═══════════════════════════════════════════════════════════
# AC9 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac9_market_signal_serialization():
    """AC9a: MarketSignal to_dict/from_dict roundtrip."""
    signal = MarketSignal(
        creative_id="creative_001",
        genome_id="genome_001",
        quality_score=0.85,
        signals={"hook": 0.92, "visual": 0.75, "reward": 0.88},
        signal_composition={
            "acquisition": "strong",
            "engagement": "medium",
            "monetization": "very_strong",
        },
        confidence=0.95,
        sample_size=30000,
    )

    d = signal.to_dict()
    restored = MarketSignal.from_dict(d)

    assert restored.signal_id == signal.signal_id
    assert restored.creative_id == signal.creative_id
    assert restored.genome_id == signal.genome_id
    assert restored.quality_score == signal.quality_score
    assert restored.signals == signal.signals
    assert restored.signal_composition == signal.signal_composition
    assert restored.confidence == signal.confidence
    assert restored.sample_size == signal.sample_size


def test_ac9b_empty_signal_serialization():
    """AC9b: Empty MarketSignal roundtrip."""
    signal = MarketSignal()
    d = signal.to_dict()
    restored = MarketSignal.from_dict(d)

    assert restored.quality_score == 0.0
    assert restored.signals == {}
    assert restored.confidence == 0.0


# ═══════════════════════════════════════════════════════════
# AC10 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac10_deterministic_processor():
    """AC10a: Same feedback → same signal."""
    fb1 = _make_full_feedback()
    fb2 = _make_full_feedback()

    processor1 = _make_processor()
    processor2 = _make_processor()

    s1 = processor1.process(fb1)
    s2 = processor2.process(fb2)

    assert s1.quality_score == s2.quality_score
    assert s1.signals == s2.signals
    assert s1.confidence == s2.confidence
    assert s1.signal_composition == s2.signal_composition


def test_ac10b_deterministic_signal_strength():
    """AC10b: SignalStrength.from_score is deterministic."""
    assert SignalStrength.from_score(0.85) == SignalStrength.VERY_STRONG
    assert SignalStrength.from_score(0.85) == SignalStrength.VERY_STRONG
    assert SignalStrength.from_score(0.70) == SignalStrength.STRONG
    assert SignalStrength.from_score(0.70) == SignalStrength.STRONG


def test_ac10c_deterministic_batch():
    """AC10c: Batch processing produces consistent results."""
    feedbacks = [_make_full_feedback(f"c_{i}") for i in range(3)]
    processor = _make_processor()
    signals = processor.process_batch(feedbacks)

    assert len(signals) == 3
    # All should have same quality since same data
    scores = [s.quality_score for s in signals]
    assert len(set(scores)) == 1