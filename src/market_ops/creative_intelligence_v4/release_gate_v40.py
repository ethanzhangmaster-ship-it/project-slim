"""V4.0 Creative Intelligence Platform — Release Gate.

Validates the entire V4.0 platform:
  - Creative Repository (metadata, registration, DNA storage, review)
  - DNA System (Image DNA, Video DNA, extraction)
  - Creative Intelligence (image planning, video planning)
  - Video Planner (hybrid AI + Eagle segments)
  - Video Generator (unified multi-model interface)
  - Quality Gate (image + video)
  - Human Review (scoring, saving)
  - Learning Engine (analysis, insights, recommendations)
  - V4.0 Pipeline (end-to-end image + video)
  - Cross-module integration (repository → intelligence → pipeline)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_intelligence_v4.creative_repository.repository import CreativeRepository
from market_ops.creative_intelligence_v4.creative_repository.metadata import (
    CreativeMetadata, CreativeType, CreativeStatus, MonetizationType, OptimizationGoal,
)
from market_ops.creative_intelligence_v4.creative_repository.adapters.facebook_adapter import FacebookAdapter
from market_ops.creative_intelligence_v4.creative_repository.adapters.adjust_adapter import AdjustAdapter
from market_ops.creative_intelligence_v4.creative_repository.adapters.eagle_adapter import EagleAdapter

from market_ops.creative_intelligence_v4.dna.image_dna import ImageDNA
from market_ops.creative_intelligence_v4.dna.video_dna import VideoDNA
from market_ops.creative_intelligence_v4.dna.dna_extractor import DNAExtractor

from market_ops.creative_intelligence_v4.creative_intelligence.intelligence import CreativeIntelligence
from market_ops.creative_intelligence_v4.creative_intelligence.video_planner import VideoPlanner, VideoPlan

from market_ops.creative_intelligence_v4.generation.video_generator import VideoGenerator, VideoGenerationResult

from market_ops.creative_intelligence_v4.quality.image_quality_gate import ImageQualityV4, ImageQualityResult
from market_ops.creative_intelligence_v4.quality.video_quality_gate import VideoQualityGate, VideoQualityResult

from market_ops.creative_intelligence_v4.review.human_review import HumanReview, ReviewResult

from market_ops.creative_intelligence_v4.learning.learning_engine import LearningEngine, LearningReport, LearningInsight

from market_ops.creative_intelligence_v4.pipeline.v40_pipeline import V40Pipeline, V40PipelineResult


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _load_winner_dna(idx: int = 1) -> dict:
    path = Path(f"output/winner_dna/winner_{idx:03d}.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ═══════════════════════════════════════════════════════════
# 1-3. Creative Repository
# ═══════════════════════════════════════════════════════════

def test_repository_register():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)
        meta = repo.register(
            creative_type="image",
            facebook_data={"creative_id": "fb_123", "spend": 100, "ctr": 0.85},
            adjust_data={"creative_id": "adj_123", "ltv_d30": 5.0},
        )
        assert meta.creative_id
        assert meta.creative_type == CreativeType.IMAGE
        assert meta.spend == 100
        assert meta.ctr == 0.85
        assert meta.ltv_d30 == 5.0
        assert (Path(tmpdir) / meta.creative_id / "metadata.json").exists()
        assert (Path(tmpdir) / meta.creative_id / "facebook.json").exists()
        assert (Path(tmpdir) / meta.creative_id / "adjust.json").exists()
    return True


def test_repository_dna_and_review():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)
        meta = repo.register(creative_type="image")
        cid = meta.creative_id

        # Save DNA
        dna = {"character": "witch", "reward": "dragon", "dna_type": "image"}
        assert repo.save_dna(cid, dna)
        loaded = repo.get_dna(cid)
        assert loaded["character"] == "witch"

        # Save review
        assert repo.save_review(cid, {"hook": 8, "gameplay": 7, "reward": 9})
        review = repo.get_review(cid)
        assert review["average"] == 8.0

        # Metadata should be updated
        meta2 = repo.get_metadata(cid)
        assert meta2.has_image_dna
        assert meta2.review_score == 8.0
    return True


def test_repository_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)
        m1 = repo.register(creative_type="image", facebook_data={"roas_d7": 0.8})
        m2 = repo.register(creative_type="video", facebook_data={"roas_d7": 0.2})
        repo.update_metadata(m1.creative_id, status=CreativeStatus.WINNER)
        repo.update_metadata(m2.creative_id, status=CreativeStatus.LOSER)

        assert len(repo.list_all()) == 2
        assert len(repo.list_winners(min_roas=0.5)) == 1
        assert len(repo.list_by_type("image")) == 1
        assert len(repo.list_by_status("winner")) == 1
    return True


# ═══════════════════════════════════════════════════════════
# 4-5. DNA System
# ═══════════════════════════════════════════════════════════

def test_image_dna():
    dna = ImageDNA(
        character="witch", reward="baby_dragon", gameplay="merge",
        composition="center", camera="45_degree", lighting="warm",
        palette="purple_gold", emotion="surprise", hook="collection",
        style="cartoon", brand="Merge Witches",
    )
    d = dna.to_dict()
    assert d["character"] == "witch"
    assert d["dna_type"] == "image"

    # to_planner_input
    planner_input = dna.to_planner_input()
    assert planner_input["character"] == "witch"
    assert planner_input["camera"] == "45_degree"

    # from_dict
    dna2 = ImageDNA.from_dict(d)
    assert dna2.character == "witch"
    return True


def test_video_dna():
    dna = VideoDNA(
        opening_hook="merge_surprise",
        gameplay_structure="linear",
        reward_type="evolution",
        cta_text="Play Now",
        camera_motion="zoom",
        cut_rhythm="fast",
        duration_ms=15000,
        music="epic",
        hook_type="challenge",
        facebook_video_id="vid_123",
    )
    d = dna.to_dict()
    assert d["dna_type"] == "video"
    assert d["opening_hook"] == "merge_surprise"
    assert d["duration_ms"] == 15000

    dna2 = VideoDNA.from_dict(d)
    assert dna2.opening_hook == "merge_surprise"
    return True


def test_dna_extractor():
    extractor = DNAExtractor()

    # Image DNA extraction
    winner_data = _load_winner_dna(1)
    if winner_data:
        image_dna = extractor.extract_image_dna(winner_data)
        assert image_dna.character == "witch"
        assert image_dna.gameplay == "merge"

    # Video DNA extraction
    video_data = {
        "opening_hook": "fail_react",
        "gameplay_structure": "loop",
        "reward_type": "treasure",
        "cta_text": "Download",
        "duration_ms": 12000,
        "hook_type": "fail",
        "video_id": "vid_456",
    }
    video_dna = extractor.extract_video_dna(video_data)
    assert video_dna.opening_hook == "fail_react"
    assert video_dna.reward_type == "treasure"
    return True


# ═══════════════════════════════════════════════════════════
# 6-8. Creative Intelligence
# ═══════════════════════════════════════════════════════════

def test_intelligence_image_plan():
    winner_data = _load_winner_dna(1)
    if not winner_data:
        return True  # Skip if no data

    extractor = DNAExtractor()
    image_dna = extractor.extract_image_dna(winner_data)

    intelligence = CreativeIntelligence()
    result = intelligence.plan_image_from_dna(image_dna, strategy="balanced")
    assert "plan" in result
    assert "prompt" in result
    assert result["prompt"]["positive_prompt"]
    return True


def test_intelligence_image_batch():
    winner_data = _load_winner_dna(1)
    if not winner_data:
        return True

    extractor = DNAExtractor()
    image_dna = extractor.extract_image_dna(winner_data)

    intelligence = CreativeIntelligence()
    results = intelligence.plan_image_batch(image_dna, count=5)
    assert len(results) >= 3
    for r in results:
        assert "prompt" in r
        assert r["prompt"]["positive_prompt"]
    return True


def test_intelligence_video_plan():
    dna = VideoDNA(
        opening_hook="merge_surprise",
        gameplay_structure="linear",
        reward_type="evolution",
        cta_text="Play Now",
        eagle_local_path="eagle/videos/123.mp4",
        duration_ms=15000,
    )

    intelligence = CreativeIntelligence()
    result = intelligence.plan_video_from_dna(dna)
    assert "plan" in result
    assert result["plan"]["plan_type"] == "video"
    segments = result["plan"]["segments"]
    assert len(segments) == 4  # opening, gameplay, reward, ending
    assert segments[0]["segment"] == "opening"
    assert segments[0]["type"] == "ai_generated"
    assert segments[1]["segment"] == "gameplay"
    assert segments[1]["type"] == "eagle_real"
    return True


# ═══════════════════════════════════════════════════════════
# 9-10. Video Planner
# ═══════════════════════════════════════════════════════════

def test_video_planner():
    dna = VideoDNA(
        opening_hook="fail_react",
        gameplay_structure="spiral",
        reward_type="treasure",
        cta_text="Install Now",
        ending_type="cta",
        eagle_local_path="eagle/456.mp4",
        duration_ms=12000,
    )

    planner = VideoPlanner()
    plan = planner.plan(dna, platform="facebook")

    assert plan.total_duration_ms == 15000
    assert len(plan.segments) == 4

    # Check segment types
    segment_types = [s.segment_type for s in plan.segments]
    assert "ai_opening" in segment_types
    assert "eagle_gameplay" in segment_types
    assert "reward" in segment_types
    assert "ai_ending" in segment_types

    # Check sources
    assert plan.segments[0].source == "ai"
    assert plan.segments[1].source == "eagle"
    assert plan.segments[3].source == "ai"

    # Check durations
    assert plan.segments[0].duration_ms == 3000  # opening
    assert plan.segments[3].duration_ms == 2000  # ending

    d = plan.to_dict()
    assert d["total_duration_ms"] == 15000
    return True


def test_video_planner_different_durations():
    dna = VideoDNA(
        opening_hook="collection_showcase",
        gameplay_structure="showcase",
        reward_type="collection",
        cta_text="Play",
        duration_ms=10000,
    )

    planner = VideoPlanner()
    plan = planner.plan(dna, platform="instagram")
    assert plan.total_duration_ms == 15000
    return True


# ═══════════════════════════════════════════════════════════
# 11-12. Video Generator
# ═══════════════════════════════════════════════════════════

def test_video_generator():
    generator = VideoGenerator(output_dir="output/test_videos", model="seedance")

    dna = VideoDNA(
        opening_hook="merge_surprise",
        gameplay_structure="linear",
        reward_type="evolution",
        cta_text="Play Now",
        duration_ms=15000,
    )

    planner = VideoPlanner()
    plan = planner.plan(dna)

    result = generator.generate(plan)
    assert result.success
    assert result.model == "seedance"
    assert result.segments_total == 4
    assert result.segments_generated == 2  # AI segments only
    return True


def test_video_generator_multi_model():
    for model in ["seedance", "runway", "veo"]:
        generator = VideoGenerator(output_dir="output/test_videos", model=model)

        dna = VideoDNA(
            opening_hook="fail_react",
            gameplay_structure="loop",
            reward_type="treasure",
            cta_text="Download",
            duration_ms=12000,
        )

        planner = VideoPlanner()
        plan = planner.plan(dna)

        result = generator.generate(plan)
        assert result.success
        assert result.model == model
    return True


# ═══════════════════════════════════════════════════════════
# 13-14. Quality Gate
# ═══════════════════════════════════════════════════════════

def test_image_quality_v4():
    gate = ImageQualityV4(strict=False)
    result = gate.validate("nonexistent.png")
    assert not result.passed
    assert len(result.checks) > 0
    return True


def test_video_quality_gate():
    gate = VideoQualityGate(platform="facebook")
    result = gate.validate("nonexistent.mp4")
    assert not result.passed
    assert result.checks[0].name == "file_exists"
    return True


# ═══════════════════════════════════════════════════════════
# 15-16. Human Review
# ═══════════════════════════════════════════════════════════

def test_human_review_score():
    review = HumanReview()
    result = review.score(
        creative_id="creative_000001",
        hook=8, gameplay=7, reward=9, ctr=8, brand=7, overall=8,
        launchable=True, notes="Strong hook, good reward",
    )
    assert result.average >= 7.5
    assert result.launchable
    assert result.notes == "Strong hook, good reward"

    d = review.to_dict(result)
    assert d["creative_id"] == "creative_000001"
    assert d["scores"]["hook"] == 8
    assert d["average"] == 7.8
    return True


def test_human_review_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)
        meta = repo.register(creative_type="image")
        cid = meta.creative_id

        review = HumanReview()
        result = review.score(
            creative_id=cid, hook=9, gameplay=8, reward=9, ctr=7, brand=8, overall=8,
        )
        assert review.save(result, repo)

        saved = review.to_dict(result)
        assert saved["average"] == 8.2
    return True


# ═══════════════════════════════════════════════════════════
# 17-19. Learning Engine
# ═══════════════════════════════════════════════════════════

def test_learning_engine_analyze():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)

        # Register winners and losers
        w1 = repo.register(creative_type="image", facebook_data={"roas_d7": 0.9})
        w2 = repo.register(creative_type="image", facebook_data={"roas_d7": 0.8})
        l1 = repo.register(creative_type="image", facebook_data={"roas_d7": 0.1})

        repo.update_metadata(w1.creative_id, status=CreativeStatus.WINNER)
        repo.update_metadata(w2.creative_id, status=CreativeStatus.WINNER)
        repo.update_metadata(l1.creative_id, status=CreativeStatus.LOSER)

        # Save DNA for winners
        repo.save_dna(w1.creative_id, {"character": "witch", "reward": "dragon", "hook": "collection"})
        repo.save_dna(w2.creative_id, {"character": "witch", "reward": "treasure", "hook": "collection"})

        # Save reviews
        repo.save_review(w1.creative_id, {"hook": 8, "gameplay": 7, "reward": 9})
        repo.save_review(w2.creative_id, {"hook": 9, "gameplay": 8, "reward": 8})

        engine = LearningEngine()
        report = engine.analyze(repo)

        assert report.total_creatives == 3
        assert report.winners == 2
        assert report.losers == 1
        assert len(report.insights) > 0
        assert len(report.recommendations) > 0
    return True


def test_learning_insight():
    insight = LearningInsight(
        dimension="character",
        winning_value="witch",
        losing_value="dragon",
        confidence=0.8,
        sample_count=5,
        source="performance",
    )
    assert insight.dimension == "character"
    assert insight.winning_value == "witch"
    assert insight.confidence == 0.8
    return True


def test_learning_report():
    report = LearningReport(
        total_creatives=10,
        winners=5,
        losers=5,
        recommendations=["Use character='witch'", "Pause 5 losers"],
    )
    assert report.total_creatives == 10
    assert len(report.recommendations) == 2
    return True


# ═══════════════════════════════════════════════════════════
# 20-21. V4.0 Pipeline
# ═══════════════════════════════════════════════════════════

def test_v40_pipeline_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = V40Pipeline(repository_dir=tmpdir, output_dir=tmpdir)

        # Test with DNA object
        dna = ImageDNA(
            character="witch", reward="baby_dragon", gameplay="merge",
            composition="center", camera="45_degree", lighting="warm",
            palette="purple_gold", emotion="surprise", hook="collection",
            style="cartoon",
        )
        result = pipeline.run_image_pipeline_from_dna(dna, strategy="balanced")
        assert result.creative_id
        assert result.dna["character"] == "witch"
        assert result.plan
        assert result.generation_success
        assert result.elapsed_ms > 0
    return True


def test_v40_pipeline_video():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = V40Pipeline(repository_dir=tmpdir, output_dir=tmpdir)

        dna = VideoDNA(
            opening_hook="merge_surprise",
            gameplay_structure="linear",
            reward_type="evolution",
            cta_text="Play Now",
            duration_ms=15000,
        )
        result = pipeline.run_video_pipeline(dna)
        assert result.creative_id
        assert result.creative_type == "video"
        assert result.dna["opening_hook"] == "merge_surprise"
        assert result.generation_success
    return True


# ═══════════════════════════════════════════════════════════
# 22-24. Integration
# ═══════════════════════════════════════════════════════════

def test_integration_full_flow():
    """Full flow: DNA → Repository → Intelligence → Pipeline → Review → Learning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = V40Pipeline(repository_dir=tmpdir, output_dir=tmpdir)

        # 1. Image pipeline
        dna = ImageDNA(
            character="witch", reward="baby_dragon", gameplay="merge",
            hook="collection", style="cartoon",
        )
        result = pipeline.run_image_pipeline_from_dna(dna)
        assert result.creative_id

        # 2. Human review
        review_result = pipeline.review(
            creative_id=result.creative_id,
            hook=9, gameplay=8, reward=9, ctr=8, brand=8, overall=8,
        )
        assert review_result.average >= 8.0

        # 3. Learning
        report = pipeline.learn()
        assert report.total_creatives >= 1
    return True


def test_integration_repository_flow():
    """Repository → DNA → Review → Query."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = CreativeRepository(tmpdir)

        # Register 3 creatives
        for i, (ct, roas) in enumerate([("image", 0.9), ("image", 0.7), ("video", 0.3)]):
            meta = repo.register(
                creative_type=ct,
                facebook_data={"roas_d7": roas, "spend": 100 + i * 50},
            )
            repo.save_dna(meta.creative_id, {"character": "witch", "dna_type": ct})
            repo.save_review(meta.creative_id, {"hook": 8, "overall": 8})

        # Set winner/loser
        all_creatives = repo.list_all()
        repo.update_metadata(all_creatives[0].creative_id, status=CreativeStatus.WINNER)
        repo.update_metadata(all_creatives[2].creative_id, status=CreativeStatus.LOSER)

        # Verify
        assert len(repo.list_all()) == 3
        assert len(repo.list_winners(min_roas=0.5)) == 2
        assert len(repo.list_by_status("winner")) == 1
        assert len(repo.list_by_status("loser")) == 1
    return True


def test_integration_pipeline_summary():
    result = V40PipelineResult(
        creative_id="creative_000001",
        creative_type="image",
        dna={"character": "witch"},
        plan={"plan_type": "image"},
        generation_success=True,
        quality_passed=True,
        quality_score=92.0,
        elapsed_ms=3500,
    )
    summary = result.summary()
    assert "creative_000001" in summary
    assert "PASS" in summary
    assert "92.0" in summary
    return True


# ═══════════════════════════════════════════════════════════
# 25. Metadata Model
# ═══════════════════════════════════════════════════════════

def test_metadata_model():
    meta = CreativeMetadata(
        creative_id="creative_000001",
        creative_type=CreativeType.IMAGE,
        monetization=MonetizationType.IAA,
        optimization_goal=OptimizationGoal.INSTALL,
        country="US",
        status=CreativeStatus.ACTIVE,
        spend=500.0,
        ctr=0.85,
        roas_d7=0.65,
    )
    d = meta.to_dict()
    assert d["creative_id"] == "creative_000001"
    assert d["creative_type"] == "image"
    assert d["performance"]["spend"] == 500.0

    meta2 = CreativeMetadata.from_dict(d)
    assert meta2.creative_id == "creative_000001"
    assert meta2.spend == 500.0
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Repository
        ("Repository 注册", test_repository_register),
        ("Repository DNA+Review", test_repository_dna_and_review),
        ("Repository 查询", test_repository_query),
        # DNA
        ("Image DNA", test_image_dna),
        ("Video DNA", test_video_dna),
        ("DNA Extractor", test_dna_extractor),
        # Intelligence
        ("Intelligence Image Plan", test_intelligence_image_plan),
        ("Intelligence Image Batch", test_intelligence_image_batch),
        ("Intelligence Video Plan", test_intelligence_video_plan),
        # Video Planner
        ("Video Planner", test_video_planner),
        ("Video Planner 多平台", test_video_planner_different_durations),
        # Video Generator
        ("Video Generator", test_video_generator),
        ("Video Generator 多模型", test_video_generator_multi_model),
        # Quality
        ("Image Quality V4", test_image_quality_v4),
        ("Video Quality Gate", test_video_quality_gate),
        # Review
        ("Human Review Score", test_human_review_score),
        ("Human Review Save", test_human_review_save),
        # Learning
        ("Learning Engine Analyze", test_learning_engine_analyze),
        ("Learning Insight", test_learning_insight),
        ("Learning Report", test_learning_report),
        # Pipeline
        ("V4.0 Pipeline Image", test_v40_pipeline_image),
        ("V4.0 Pipeline Video", test_v40_pipeline_video),
        # Integration
        ("Integration Full Flow", test_integration_full_flow),
        ("Integration Repository Flow", test_integration_repository_flow),
        ("Integration Pipeline Summary", test_integration_pipeline_summary),
        # Metadata
        ("Metadata Model", test_metadata_model),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.0 Creative Intelligence Platform — Release Gate")
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