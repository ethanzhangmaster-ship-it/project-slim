"""V5.0 Phase B+C: Video Generator + Facebook Publisher — Release Gate (18 tests).

Validates:
  Phase B — CreativeVideoGenerator:
    1. Story plan generation from winners
    2. Story archetype selection (DNA-based)
    3. Beat structure (5 beats: hook/problem/gameplay/reward/cta)
    4. DNA match scoring
    5. Manifest file save
    6. Integration with CreativeFactoryLoop

  Phase C — FacebookPublisher:
    7. Dry run publish (Level 0)
    8. Low budget publish (Level 1)
    9. Creative status tracking
    10. PublishResult structure
    11. Reads META_ prefixed env vars
    12. FB_ prefix takes priority over META_
    13. Manifest file save
    14. Integration with CreativeFactoryLoop
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_video_generator import (
    CreativeVideoGenerator,
    VideoGenerationResult,
    StoryPlan,
    StoryBeat,
    STORY_TEMPLATES,
    DNA_TO_STORY,
)
from market_ops.facebook_publisher import (
    FacebookPublisher,
    FacebookCreative,
    PublishResult,
    MAX_ADS_PER_LOOP,
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
# Phase B: CreativeVideoGenerator (8 tests)
# ═══════════════════════════════════════════════════════════

def test_video_generator_initializes():
    """Video: initializes with default config"""
    gen = CreativeVideoGenerator()
    assert gen.output_dir.exists()
    assert gen.target_duration == 15.0
    assert gen.target_ratio == "9:16"
    return True


def test_video_generates_plans_from_winners():
    """Video: generates story plans from winner list"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:3]

    gen = CreativeVideoGenerator()
    result = gen.generate_from_winners(winners, per_winner=2, max_total=6)
    assert result.total_plans == 6, f"Expected 6 plans, got {result.total_plans}"
    assert len(result.story_plans) == 6
    return True


def test_video_plan_has_5_beats():
    """Video: each story plan has exactly 5 beats (hook/problem/gameplay/reward/cta)"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeVideoGenerator()
    result = gen.generate_from_winners(winners, per_winner=1, max_total=1)

    for plan in result.story_plans:
        assert len(plan["beats"]) == 5, f"Expected 5 beats, got {len(plan['beats'])}"
        roles = [b["role"] for b in plan["beats"]]
        assert roles == ["hook", "problem", "gameplay", "reward", "cta"], f"Wrong beat order: {roles}"
    return True


def test_video_beat_duration_sum():
    """Video: beat durations sum to total_duration"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeVideoGenerator()
    result = gen.generate_from_winners(winners, per_winner=1, max_total=1)

    for plan in result.story_plans:
        beat_sum = sum(b["duration"] for b in plan["beats"])
        assert abs(beat_sum - plan["total_duration"]) < 0.01, \
            f"Beat sum {beat_sum} != total {plan['total_duration']}"
    return True


def test_video_story_type_selection():
    """Video: story type is selected based on DNA content"""
    gen = CreativeVideoGenerator()

    # Merge DNA → should select challenge or evolution
    merge_dna = {"gameplay": "merge puzzle", "reward": "dragon egg hatch", "character": "witch"}
    story = gen._select_story_type(merge_dna)
    assert story in STORY_TEMPLATES, f"Unknown story type: {story}"
    # merge → challenge or evolution
    assert story in ("challenge", "evolution"), f"Merge DNA got {story}, expected challenge/evolution"

    # Dragon DNA → should select evolution
    dragon_dna = {"gameplay": "merge puzzle", "reward": "dragon egg hatch", "character": "dragon"}
    story2 = gen._select_story_type(dragon_dna)
    assert story2 in ("evolution", "challenge"), f"Dragon DNA got {story2}"

    return True


def test_video_dna_match_scoring():
    """Video: DNA match score is between 0 and 1"""
    gen = CreativeVideoGenerator()
    score = gen._calc_dna_match({"gameplay": "merge puzzle", "reward": "dragon egg"}, "evolution")
    assert 0.0 <= score <= 1.0, f"Score out of range: {score}"
    assert score > 0, "Merge + dragon should match evolution"
    return True


def test_video_manifest_saved():
    """Video: manifest file is saved to output dir"""
    builder = CreativePerformanceBuilder()
    winners = builder.get_winners()[:1]

    gen = CreativeVideoGenerator(output_dir=Path("output/creative_factory/videos_test"))
    result = gen.generate_from_winners(winners, per_winner=1, max_total=1)

    from datetime import date
    today = date.today().isoformat().replace("-", "")
    manifest_path = gen.output_dir / f"video_manifest_{today}.json"
    assert manifest_path.exists(), f"Manifest not saved: {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["total_plans"] == 1
    return True


def test_video_loop_integration():
    """Video: CreativeFactoryLoop._generate_videos() uses real generator"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(
        platform="ios",
        daily_image_target=10,
        daily_video_target=4,
    ))
    videos = loop._generate_videos(n_winners=2)
    assert videos > 0, f"Expected >0 videos, got {videos}"
    assert videos <= 4, f"Expected <=4 videos, got {videos}"
    return True


# ═══════════════════════════════════════════════════════════
# Phase C: FacebookPublisher (8 tests)
# ═══════════════════════════════════════════════════════════

def test_publisher_dry_run():
    """Publisher: Level 0 dry run returns mock drafts"""
    pub = FacebookPublisher(approval_level=0)
    result = pub.publish_creatives(
        image_paths=["test1.png", "test2.png"],
        names=["v1", "v2"],
        platform="ios",
    )
    assert result.total_attempted == 2
    assert result.total_uploaded == 2
    assert result.total_active == 0  # Level 0 = draft only
    for c in result.creatives:
        assert c.status == "draft"
        assert c.ad_id.startswith("mock_ad_")
    return True


def test_publisher_level_1_active():
    """Publisher: Level 1 dry run returns active status"""
    pub = FacebookPublisher(approval_level=1)
    result = pub.publish_creatives(
        image_paths=["test1.png"],
        names=["v1"],
        platform="ios",
    )
    assert result.total_active == 1
    assert result.creatives[0].status == "active"
    return True


def test_publisher_safety_limit():
    """Publisher: max 5 ads per loop (safety limit)"""
    pub = FacebookPublisher(approval_level=0)
    paths = [f"test_{i}.png" for i in range(10)]
    result = pub.publish_creatives(image_paths=paths, platform="ios")
    assert result.total_attempted <= MAX_ADS_PER_LOOP, \
        f"Exceeded safety limit: {result.total_attempted}"
    return True


def test_publisher_creative_fields():
    """Publisher: FacebookCreative has all required fields"""
    pub = FacebookPublisher(approval_level=1)
    result = pub.publish_creatives(
        image_paths=["test1.png"],
        names=["variant_001"],
        platform="ios",
    )
    c = result.creatives[0]
    assert c.name == "variant_001"
    assert c.platform == "ios"
    assert c.budget_daily == 50.0
    assert c.creative_id != ""
    assert c.ad_creative_id != ""
    assert c.campaign_id != ""
    assert c.ad_set_id != ""
    assert c.ad_id != ""
    assert c.published_at != ""
    return True


def test_publisher_result_structure():
    """Publisher: PublishResult.to_dict() is JSON serializable"""
    pub = FacebookPublisher(approval_level=0)
    result = pub.publish_creatives(
        image_paths=["test1.png", "test2.png"],
        names=["v1", "v2"],
        platform="ios",
    )
    d = result.to_dict()
    assert "date" in d
    assert "total_attempted" in d
    assert "total_active" in d
    assert "creatives" in d
    assert "approval_level" in d
    # JSON serializable
    json.dumps(d)
    return True


def test_publisher_is_dry_run():
    """Publisher: is_dry_run when no credentials"""
    pub = FacebookPublisher(approval_level=0)
    assert pub.is_dry_run is True
    assert pub.is_configured is False
    return True


def test_publisher_reads_meta_env_vars():
    """Publisher: reads META_ACCESS_TOKEN / META_AD_ACCOUNT_ID / CLOSED_LOOP_PAGE_ID"""
    import os

    # Temporarily set META_ prefixed env vars
    original_token = os.environ.get("META_ACCESS_TOKEN")
    original_account = os.environ.get("META_AD_ACCOUNT_ID")
    original_page = os.environ.get("CLOSED_LOOP_PAGE_ID")
    try:
        os.environ["META_ACCESS_TOKEN"] = "test_meta_token_123"
        os.environ["META_AD_ACCOUNT_ID"] = "test_meta_account_456"
        os.environ["CLOSED_LOOP_PAGE_ID"] = "test_page_789"

        pub = FacebookPublisher()
        assert pub.is_configured is True
        assert pub._access_token == "test_meta_token_123"
        assert pub._ad_account_id == "test_meta_account_456"
        assert pub._page_id == "test_page_789"
        # approval_level defaults to 0 → dry_run even when configured
        assert pub.is_dry_run is True
        # Level 1 would be non-dry_run
        pub_level1 = FacebookPublisher(approval_level=1)
        assert pub_level1.is_dry_run is False
    finally:
        # Restore
        if original_token is not None:
            os.environ["META_ACCESS_TOKEN"] = original_token
        elif "META_ACCESS_TOKEN" in os.environ:
            del os.environ["META_ACCESS_TOKEN"]
        if original_account is not None:
            os.environ["META_AD_ACCOUNT_ID"] = original_account
        elif "META_AD_ACCOUNT_ID" in os.environ:
            del os.environ["META_AD_ACCOUNT_ID"]
        if original_page is not None:
            os.environ["CLOSED_LOOP_PAGE_ID"] = original_page
        elif "CLOSED_LOOP_PAGE_ID" in os.environ:
            del os.environ["CLOSED_LOOP_PAGE_ID"]
    return True


def test_publisher_fb_prefix_fallback():
    """Publisher: FB_xxx env vars take priority over META_xxx"""
    import os

    original_fb_token = os.environ.get("FB_ACCESS_TOKEN")
    original_meta_token = os.environ.get("META_ACCESS_TOKEN")
    try:
        os.environ["FB_ACCESS_TOKEN"] = "fb_token_priority"
        os.environ["META_ACCESS_TOKEN"] = "meta_token_fallback"

        pub = FacebookPublisher()
        assert pub._access_token == "fb_token_priority"
    finally:
        if original_fb_token is not None:
            os.environ["FB_ACCESS_TOKEN"] = original_fb_token
        elif "FB_ACCESS_TOKEN" in os.environ:
            del os.environ["FB_ACCESS_TOKEN"]
        if original_meta_token is not None:
            os.environ["META_ACCESS_TOKEN"] = original_meta_token
        elif "META_ACCESS_TOKEN" in os.environ:
            del os.environ["META_ACCESS_TOKEN"]
    return True


def test_publisher_manifest_saved():
    """Publisher: manifest file is saved to output dir"""
    pub = FacebookPublisher(
        approval_level=0,
        output_dir=Path("output/creative_factory/facebook_test"),
    )
    result = pub.publish_creatives(
        image_paths=["test1.png"],
        names=["v1"],
        platform="ios",
    )

    from datetime import date
    today = date.today().isoformat().replace("-", "")
    manifest_path = pub.output_dir / f"publish_manifest_{today}.json"
    assert manifest_path.exists(), f"Manifest not saved: {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["total_attempted"] == 1
    return True


def test_publisher_loop_integration():
    """Publisher: CreativeFactoryLoop daily run includes publisher step"""
    loop = CreativeFactoryLoop(FactoryLoopConfig(
        platform="ios",
        daily_image_target=5,
        daily_video_target=2,
    ))
    result = loop.run_daily()
    # Publisher step runs (dry run) without errors
    assert result.errors == []
    assert result.uploaded_to_facebook >= 0
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Phase B: Video Generator (8)
        ("Video: initializes", test_video_generator_initializes),
        ("Video: plans from winners", test_video_generates_plans_from_winners),
        ("Video: 5 beats per plan", test_video_plan_has_5_beats),
        ("Video: beat duration sum", test_video_beat_duration_sum),
        ("Video: story type selection", test_video_story_type_selection),
        ("Video: DNA match scoring", test_video_dna_match_scoring),
        ("Video: manifest saved", test_video_manifest_saved),
        ("Video: loop integration", test_video_loop_integration),
        # Phase C: Facebook Publisher (8)
        ("Publisher: dry run drafts", test_publisher_dry_run),
        ("Publisher: level 1 active", test_publisher_level_1_active),
        ("Publisher: safety limit", test_publisher_safety_limit),
        ("Publisher: creative fields", test_publisher_creative_fields),
        ("Publisher: result structure", test_publisher_result_structure),
        ("Publisher: is_dry_run", test_publisher_is_dry_run),
        ("Publisher: reads META_ env vars", test_publisher_reads_meta_env_vars),
        ("Publisher: FB_ prefix fallback", test_publisher_fb_prefix_fallback),
        ("Publisher: manifest saved", test_publisher_manifest_saved),
        ("Publisher: loop integration", test_publisher_loop_integration),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase B+C: Video Generator + Facebook Publisher")
    print("  18 tests")
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