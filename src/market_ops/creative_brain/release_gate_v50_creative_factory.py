"""V5.0 Creative Factory Loop — Release Gate (16 tests).

Validates the Creative Factory Loop end-to-end:
  1. CreativePerformanceBuilder — data loading + normalization
  2. Winner extraction + ROAS calculation
  3. Platform filtering (iOS / Android)
  4. Confidence + decision logic
  5. CreativeFactoryLoop — daily loop execution
  6. Auto-detection of Lovart credentials
  7. Auto-detection of Facebook credentials
  8. Report generation

All tests must PASS before Phase 2 of Creative Factory.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_performance_builder import (
    CreativePerformanceBuilder,
    CreativePerformance,
    EFFECTIVE_SPEND,
    EFFECTIVE_INSTALLS,
)
from market_ops.creative_factory_loop import (
    CreativeFactoryLoop,
    FactoryLoopConfig,
)


# ═══════════════════════════════════════════════════════════
# 1. CreativePerformanceBuilder (6 tests)
# ═══════════════════════════════════════════════════════════

def test_builder_loads_merged_csv():
    """Builder: loads the merged CSV successfully"""
    builder = CreativePerformanceBuilder()
    all_ = builder.load()
    assert len(all_) > 1000, f"Expected >1000 creatives, got {len(all_)}"
    return True


def test_builder_calculates_roas():
    """Builder: ROAS = adjust_revenue / spend"""
    builder = CreativePerformanceBuilder()
    all_ = builder.load()
    for p in all_:
        if p.spend > 0 and p.revenue > 0:
            expected = round(p.revenue / p.spend, 4)
            assert abs(p.roas - expected) < 0.0001, f"ROAS mismatch: {p.roas} vs {expected}"
    return True


def test_builder_winners_roas_threshold():
    """Builder: winners have ROAS >= 1.0"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()
    for w in winners:
        assert w.roas >= 1.0, f"Winner with ROAS < 1.0: {w.roas}"
    return True


def test_builder_platform_detection():
    """Builder: correctly detects iOS / Android from ad_name"""
    builder = CreativePerformanceBuilder()
    all_ = builder.load()
    ios = [p for p in all_ if p.platform == "ios"]
    android = [p for p in all_ if p.platform == "android"]
    assert len(ios) > 0, "No iOS creatives found"
    assert len(android) > 0, "No Android creatives found"
    return True


def test_builder_confidence_levels():
    """Builder: confidence correctly assigned"""
    builder = CreativePerformanceBuilder()
    all_ = builder.load()
    for p in all_:
        assert p.confidence in ("high", "medium", "low"), f"Invalid confidence: {p.confidence}"
        if p.confidence == "high":
            assert p.spend >= 500 or p.revenue >= 100, f"High confidence but low spend/rev"
    return True


def test_builder_decision_assignment():
    """Builder: decision correctly assigned based on ROAS + spend"""
    builder = CreativePerformanceBuilder()
    all_ = builder.load()
    valid = [p for p in all_ if p.is_valid_sample]
    assert len(valid) > 0, "No valid samples found"
    for p in valid:
        assert p.decision in ("scale", "scale_candidate", "observe", "reduce", "stop"), f"Invalid decision: {p.decision}"
    return True


# ═══════════════════════════════════════════════════════════
# 2. CreativeFactoryLoop (4 tests)
# ═══════════════════════════════════════════════════════════

def _ensure_dry_run_env():
    """Temporarily clear Lovart env vars so tests run in dry_run mode."""
    import os
    for key in ("LOVART_ACCESS_KEY", "LOVART_SECRET_KEY"):
        if key in os.environ:
            del os.environ[key]


def test_loop_daily_run():
    """Loop: daily run executes without errors (dry run mode)"""
    _ensure_dry_run_env()
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="ios", daily_image_target=5, daily_video_target=2))
    result = loop.run_daily()
    assert result.creatives_loaded > 0
    assert result.errors == []
    assert result.generated_images > 0  # Real generator now
    return True


def test_loop_auto_detects_lovart_config():
    """Loop: _is_lovart_configured() detects env vars"""
    import os

    original_ak = os.environ.get("LOVART_ACCESS_KEY")
    original_sk = os.environ.get("LOVART_SECRET_KEY")
    try:
        # No env vars → not configured
        if "LOVART_ACCESS_KEY" in os.environ:
            del os.environ["LOVART_ACCESS_KEY"]
        if "LOVART_SECRET_KEY" in os.environ:
            del os.environ["LOVART_SECRET_KEY"]
        assert CreativeFactoryLoop._is_lovart_configured() is False

        # Set env vars → configured
        os.environ["LOVART_ACCESS_KEY"] = "test_ak"
        os.environ["LOVART_SECRET_KEY"] = "test_sk"
        assert CreativeFactoryLoop._is_lovart_configured() is True
    finally:
        if original_ak is not None:
            os.environ["LOVART_ACCESS_KEY"] = original_ak
        elif "LOVART_ACCESS_KEY" in os.environ:
            del os.environ["LOVART_ACCESS_KEY"]
        if original_sk is not None:
            os.environ["LOVART_SECRET_KEY"] = original_sk
        elif "LOVART_SECRET_KEY" in os.environ:
            del os.environ["LOVART_SECRET_KEY"]
    return True


def test_loop_auto_detects_fb_config():
    """Loop: _is_fb_configured() detects META_ prefixed env vars"""
    import os

    original_token = os.environ.get("META_ACCESS_TOKEN")
    original_account = os.environ.get("META_AD_ACCOUNT_ID")
    try:
        # No env vars → not configured
        if "META_ACCESS_TOKEN" in os.environ:
            del os.environ["META_ACCESS_TOKEN"]
        if "META_AD_ACCOUNT_ID" in os.environ:
            del os.environ["META_AD_ACCOUNT_ID"]
        assert CreativeFactoryLoop._is_fb_configured() is False

        # Set META_ env vars → configured
        os.environ["META_ACCESS_TOKEN"] = "test_token"
        os.environ["META_AD_ACCOUNT_ID"] = "test_account"
        assert CreativeFactoryLoop._is_fb_configured() is True
    finally:
        if original_token is not None:
            os.environ["META_ACCESS_TOKEN"] = original_token
        elif "META_ACCESS_TOKEN" in os.environ:
            del os.environ["META_ACCESS_TOKEN"]
        if original_account is not None:
            os.environ["META_AD_ACCOUNT_ID"] = original_account
        elif "META_AD_ACCOUNT_ID" in os.environ:
            del os.environ["META_AD_ACCOUNT_ID"]
    return True


def test_loop_winner_count():
    """Loop: finds and reports winners"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="both"))
    result = loop.run_daily()
    assert result.winners_found > 0, "No winners found"
    assert len(result.winners) > 0
    return True


def test_loop_generation_targets():
    """Loop: generation scales with winner count"""
    _ensure_dry_run_env()
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="ios", daily_image_target=10, daily_video_target=4))
    result = loop.run_daily()
    # 1 winner → 5 images, 2 videos (min of winner*5 and target)
    expected_images = min(result.winners_found * 5, 10)
    expected_videos = min(result.winners_found * 2, 4)
    assert result.generated_images == expected_images
    assert result.generated_videos == expected_videos
    return True


def test_loop_saves_report():
    """Loop: saves daily report to output dir"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="ios", daily_image_target=5, daily_video_target=2))
    result = loop.run_daily()
    path = loop.save_daily_report(result)
    assert path.exists(), f"Report not saved: {path}"
    return True


# ═══════════════════════════════════════════════════════════
# 3. Integration (4 tests)
# ═══════════════════════════════════════════════════════════

def test_platform_filter_ios():
    """Integration: iOS filter returns only iOS creatives"""
    builder = CreativePerformanceBuilder()
    ios = builder.get_by_platform("ios")
    android = builder.get_by_platform("android")
    assert len(ios) > len(android), "iOS should have more creatives than Android"
    for p in ios:
        assert p.platform == "ios"
    return True


def test_top_winners_report():
    """Integration: top winners report structure correct"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="both"))
    report = loop.get_top_winners_report()
    assert "summary" in report
    assert "winners" in report
    assert report["summary"]["winners"] > 0
    assert len(report["winners"]) > 0
    return True


def test_entities_from_performers():
    """Integration: converts CreativePerformance to CreativeEntity"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(platform="ios"))
    entities = loop.build_creative_entities_from_performers()
    assert len(entities) > 0
    for e in entities:
        assert e.creative_id != ""
        assert e.performance.spend is not None or e.performance.revenue is not None
    return True


def test_builder_summary_stats():
    """Integration: summary statistics are consistent"""
    builder = CreativePerformanceBuilder()
    summary = builder.summary()
    all_ = builder.load()
    winners = builder.get_winners()
    assert summary["total_creatives"] == len(all_)
    assert summary["winners"] == len(winners)
    assert summary["blend_roas"] == round(summary["total_revenue"] / summary["total_spend"], 4)
    assert summary["ios_creatives"] == len([p for p in all_ if p.platform == "ios"])
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. CreativePerformanceBuilder (6)
        ("Builder: loads merged CSV", test_builder_loads_merged_csv),
        ("Builder: calculates ROAS", test_builder_calculates_roas),
        ("Builder: winners ROAS threshold", test_builder_winners_roas_threshold),
        ("Builder: platform detection", test_builder_platform_detection),
        ("Builder: confidence levels", test_builder_confidence_levels),
        ("Builder: decision assignment", test_builder_decision_assignment),
        # 2. CreativeFactoryLoop (6)
        ("Loop: daily run", test_loop_daily_run),
        ("Loop: auto-detects Lovart config", test_loop_auto_detects_lovart_config),
        ("Loop: auto-detects FB config", test_loop_auto_detects_fb_config),
        ("Loop: winner count", test_loop_winner_count),
        ("Loop: generation targets", test_loop_generation_targets),
        ("Loop: saves report", test_loop_saves_report),
        # 3. Integration (4)
        ("Platform filter iOS", test_platform_filter_ios),
        ("Top winners report", test_top_winners_report),
        ("Entities from performers", test_entities_from_performers),
        ("Builder summary stats", test_builder_summary_stats),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Creative Factory Loop — Release Gate")
    print("  16 tests")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
