"""V5.0 Phase A: Creative Image Generator — Release Gate (14 tests).

Validates the Creative Image Generator pipeline:
  1. CreativeImageGenerator — prompt generation from winners
  2. DNA building with platform-specific overrides
  3. Prompt quality (positive_prompt non-empty, ad structure)
  4. GenerationResult structure
  5. Manifest file save
  6. Integration with CreativeFactoryLoop

All tests run in dry_run mode (no Lovart API calls needed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_image_generator import (
    CreativeImageGenerator,
    GenerationResult,
    GeneratedImage,
    MERGE_WITCHES_DEFAULT_DNA,
    PLATFORM_DNA_OVERRIDES,
    create_default_generator,
)
from market_ops.creative_performance_builder import (
    CreativePerformanceBuilder,
    CreativePerformance,
)
from market_ops.creative_factory_loop import (
    CreativeFactoryLoop,
    FactoryLoopConfig,
)


# ═══════════════════════════════════════════════════════════
# 1. CreativeImageGenerator Core (6 tests)
# ═══════════════════════════════════════════════════════════

def test_generator_initializes():
    """Generator: initializes with default config"""
    gen = CreativeImageGenerator()
    assert gen.output_dir.exists()
    assert gen._model == "nano_banana"
    assert gen._aspect_ratio == "9:16"
    return True


def test_generate_prompts_from_winners():
    """Generator: generates prompts from winner list"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:3]
    assert len(winners) >= 1, "Need at least 1 winner"

    gen = CreativeImageGenerator()
    prompts = gen.generate_prompts_only(winners, per_winner=3)
    assert len(prompts) == 9, f"Expected 9 prompts, got {len(prompts)}"
    return True


def test_generate_prompts_has_required_fields():
    """Generator: each prompt dict has all required fields"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeImageGenerator()
    prompts = gen.generate_prompts_only(winners, per_winner=2)
    assert len(prompts) > 0

    required = ["winner_id", "winner_platform", "winner_roas", "prompt_id",
                 "positive_prompt", "negative_prompt", "score", "aspect_ratio", "seed"]
    for p in prompts:
        for key in required:
            assert key in p, f"Missing key: {key}"
    return True


def test_prompt_positive_text_is_ad_copy():
    """Generator: positive_prompt looks like ad copy (not empty, has context)"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeImageGenerator()
    prompts = gen.generate_prompts_only(winners, per_winner=3)

    for p in prompts:
        text = p["positive_prompt"]
        assert len(text) > 50, f"Prompt too short: {len(text)} chars"
        # Should contain game ad context
        assert "Merge Witches" in text or "advertisement" in text.lower() or "game" in text.lower(), \
            f"Prompt doesn't look like ad copy: {text[:80]}..."
    return True


def test_prompt_scores_are_reasonable():
    """Generator: prompt scores are in valid range (0-100)"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:2]

    gen = CreativeImageGenerator()
    prompts = gen.generate_prompts_only(winners, per_winner=5)

    for p in prompts:
        score = p["score"]
        assert 0 <= score <= 100, f"Score out of range: {score}"
    # At least some prompts should have non-zero scores
    non_zero = [p for p in prompts if p["score"] > 0]
    assert len(non_zero) > 0, "All prompts have zero score"
    return True


def test_generate_from_winners_dry_run():
    """Generator: dry_run mode returns correct counts"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:2]

    gen = CreativeImageGenerator()
    result = gen.generate_from_winners(winners, per_winner=3, max_total=6, dry_run=True)

    assert result.total_prompts == 6, f"Expected 6 prompts, got {result.total_prompts}"
    assert result.total_generated == 6
    assert result.total_downloaded == 6
    assert result.total_failed == 0
    assert result.success_rate == 1.0
    assert result.errors == []
    return True


# ═══════════════════════════════════════════════════════════
# 2. DNA Building (3 tests)
# ═══════════════════════════════════════════════════════════

def test_dna_build_platform_override():
    """DNA: iOS winner gets iOS-specific DNA overrides"""
    gen = CreativeImageGenerator()
    winner = CreativePerformance(
        creative_id="test_ios",
        creative_name="test-ios",
        platform="ios",
        roas=1.5,
        spend=1000,
    )
    dna = gen._build_dna_from_winner(winner)
    assert dna["style"] == "cartoon polished", f"iOS style override missing: {dna['style']}"
    assert dna["palette"] == "purple gold premium", f"iOS palette override missing: {dna['palette']}"
    return True


def test_dna_build_android_override():
    """DNA: Android winner gets Android-specific DNA overrides"""
    gen = CreativeImageGenerator()
    winner = CreativePerformance(
        creative_id="test_android",
        creative_name="test-android",
        platform="android",
        roas=1.5,
        spend=1000,
    )
    dna = gen._build_dna_from_winner(winner)
    assert dna["style"] == "cartoon vibrant", f"Android style override: {dna['style']}"
    assert dna["palette"] == "purple gold bright", f"Android palette override: {dna['palette']}"
    return True


def test_dna_build_high_roas_enhancement():
    """DNA: high ROAS winner gets enhanced emotion/hook DNA"""
    gen = CreativeImageGenerator()
    winner = CreativePerformance(
        creative_id="test_high_roas",
        creative_name="test-high-roas",
        platform="ios",
        roas=3.5,
        spend=6000,
    )
    dna = gen._build_dna_from_winner(winner)
    assert "excitement" in dna["emotion"], f"ROAS enhancement missing in emotion: {dna['emotion']}"
    assert "win moment" in dna["hook"], f"ROAS enhancement missing in hook: {dna['hook']}"
    assert "proven winner" in dna["style"], f"High spend enhancement missing: {dna['style']}"
    return True


# ═══════════════════════════════════════════════════════════
# 3. GenerationResult (2 tests)
# ═══════════════════════════════════════════════════════════

def test_result_manifest_saved():
    """Result: manifest file is saved to output dir"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeImageGenerator(output_dir=Path("output/creative_factory/images_test"))
    result = gen.generate_from_winners(winners, per_winner=2, max_total=2, dry_run=True)

    # Check manifest exists
    from datetime import date
    today = date.today().isoformat().replace("-", "")
    manifest_path = gen.output_dir / f"generation_manifest_{today}.json"
    assert manifest_path.exists(), f"Manifest not saved: {manifest_path}"

    # Check manifest content
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["total_prompts"] == 2
    assert data["success_rate"] == 1.0
    return True


def test_result_to_dict_structure():
    """Result: to_dict() produces valid JSON-serializable structure"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeImageGenerator()
    result = gen.generate_from_winners(winners, per_winner=2, max_total=2, dry_run=True)

    d = result.to_dict()
    assert "date" in d
    assert "total_prompts" in d
    assert "total_generated" in d
    assert "total_downloaded" in d
    assert "total_failed" in d
    assert "errors" in d
    assert "elapsed_sec" in d
    # Should be JSON serializable
    json.dumps(d)
    return True


# ═══════════════════════════════════════════════════════════
# 4. Integration with CreativeFactoryLoop (3 tests)
# ═══════════════════════════════════════════════════════════

def _ensure_dry_run_env():
    """Temporarily clear Lovart env vars so tests run in dry_run mode."""
    import os
    for key in ("LOVART_ACCESS_KEY", "LOVART_SECRET_KEY"):
        if key in os.environ:
            del os.environ[key]


def test_loop_generates_images_via_generator():
    """Integration: loop._generate_images() uses CreativeImageGenerator"""
    _ensure_dry_run_env()
    loop = CreativeFactoryLoop(FactoryLoopConfig(
        platform="ios",
        daily_image_target=10,
        daily_video_target=2,
    ))
    # Force dry_run by ensuring no Lovart env vars are set
    images = loop._generate_images(n_winners=2)
    assert images > 0, f"Expected >0 images, got {images}"
    assert images <= 10, f"Expected <=10 images, got {images}"
    return True


def test_loop_generate_images_real_returns_result():
    """Integration: _generate_images_real() returns GenerationResult (even if Lovart not configured)"""
    _ensure_dry_run_env()
    loop = CreativeFactoryLoop(FactoryLoopConfig(
        platform="ios",
        daily_image_target=5,
        daily_video_target=2,
    ))
    result = loop._generate_images_real()
    assert isinstance(result, GenerationResult)
    # When Lovart is not configured, result may have errors
    # but the method should not crash
    assert result.date != ""
    return True


def test_loop_daily_run_with_real_generator():
    """Integration: daily run uses real prompt generator (not placeholder)"""
    _ensure_dry_run_env()
    loop = CreativeFactoryLoop(FactoryLoopConfig(
        platform="ios",
        daily_image_target=10,
        daily_video_target=2,
    ))
    result = loop.run_daily()
    assert result.generated_images > 0
    assert result.generated_images <= 10
    assert result.errors == []
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Core (6)
        ("Generator: initializes", test_generator_initializes),
        ("Generator: prompts from winners", test_generate_prompts_from_winners),
        ("Generator: prompt required fields", test_generate_prompts_has_required_fields),
        ("Generator: prompt is ad copy", test_prompt_positive_text_is_ad_copy),
        ("Generator: prompt scores valid", test_prompt_scores_are_reasonable),
        ("Generator: dry_run counts correct", test_generate_from_winners_dry_run),
        # 2. DNA Building (3)
        ("DNA: iOS platform override", test_dna_build_platform_override),
        ("DNA: Android platform override", test_dna_build_android_override),
        ("DNA: high ROAS enhancement", test_dna_build_high_roas_enhancement),
        # 3. GenerationResult (2)
        ("Result: manifest saved", test_result_manifest_saved),
        ("Result: to_dict structure", test_result_to_dict_structure),
        # 4. Integration (3)
        ("Integration: loop generates via generator", test_loop_generates_images_via_generator),
        ("Integration: generate_images_real result", test_loop_generate_images_real_returns_result),
        ("Integration: daily run with real generator", test_loop_daily_run_with_real_generator),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase A: Creative Image Generator — Release Gate")
    print("  14 tests")
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