"""Phase 3.0A: Golden Sample Pipeline — Validation.

Tests:
  1-3.   Winner DNA loading
  4-6.   Image Selector: top N, diversity, edge cases
  7-9.   Image Quality Gate: valid image, missing file, format check
  10-12. Image Exporter: prompt.txt, prompt.json, report.html
  13-15. Golden Sample Pipeline: plan-only, full pipeline, API check
  16-18. Pipeline Result: summary, error handling, data integrity
  19-20. Integration: DNA → Prompt → Plan → Export (no API needed)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_generation.models.prompt import Prompt, PromptScore
from market_ops.creative_generation.planner import CreativePromptPlanner

from market_ops.creative_image_pipeline.image_selector import ImageSelector
from market_ops.creative_image_pipeline.image_quality_gate import ImageQualityGate, QualityResult
from market_ops.creative_image_pipeline.image_exporter import ImageExporter
from market_ops.creative_image_pipeline.golden_sample_pipeline import (
    GoldenSamplePipeline, PipelineResult,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _create_test_png(path: str, w: int = 1080, h: int = 1080) -> str:
    """Create a minimal valid PNG file for testing (~3MB, >50KB threshold)."""
    import struct
    import zlib

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    # IDAT: fast noise via os.urandom, fix filter bytes to 0x00
    import os as _os
    row_size = 1 + w * 3
    raw = bytearray(_os.urandom(row_size * h))
    for y in range(h):
        raw[y * row_size] = 0  # filter byte = None
    compressed = zlib.compress(bytes(raw), level=1)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

    # IEND
    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    png_data = b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend
    with open(path, "wb") as f:
        f.write(png_data)
    return path


def _make_scored_prompts(count: int = 10) -> list[Prompt]:
    """Create a list of scored prompts for testing."""
    cameras = ["45_degree", "close_up", "top_down", "medium_shot"]
    lightings = ["warm", "dramatic", "magical_glow", "cinematic"]
    compositions = ["center", "triangle", "diagonal", "left_focus"]

    prompts = []
    for i in range(count):
        p = Prompt(
            positive_prompt=f"High-converting mobile game ad for Merge Witches. "
                           f"Cute witch with baby dragon, merge gameplay, "
                           f"high quality, clean composition. Variant {i}.",
            negative_prompt="low quality, blurry, watermark",
            camera=cameras[i % len(cameras)],
            lighting=lightings[i % len(lightings)],
            composition=compositions[i % len(compositions)],
            seed=100 + i,
            model="lovart",
        )
        p.score = PromptScore(
            gameplay=85 + i % 10,
            composition=80 + i % 15,
            hook=75 + i % 20,
            reward=88 + i % 8,
            brand=70 + i % 15,
            readability=90 + i % 5,
            novelty=65 + i % 25,
            diversity=80 + i % 10,
        )
        prompts.append(p)
    return prompts


# ═══════════════════════════════════════════════════════════
# 1-3. Winner DNA Loading
# ═══════════════════════════════════════════════════════════

def test_winner_dna_files_exist():
    dna_dir = Path("output/winner_dna")
    assert dna_dir.exists()
    files = list(dna_dir.glob("*.json"))
    assert len(files) >= 3
    return


def test_winner_dna_format():
    path = Path("output/winner_dna/winner_001.json")
    with open(path, "r") as f:
        data = json.load(f)
    assert "winner_id" in data
    assert "dna" in data
    dna = data["dna"]
    assert "character" in dna
    assert "reward" in dna
    assert "camera" in dna
    assert "lighting" in dna
    assert "gameplay" in dna
    return


def test_winner_dna_all_loadable():
    dna_dir = Path("output/winner_dna")
    for f in dna_dir.glob("*.json"):
        with open(f, "r") as fh:
            data = json.load(fh)
        assert "dna" in data
        assert len(data["dna"]) >= 5
    return


# ═══════════════════════════════════════════════════════════
# 4-6. Image Selector
# ═══════════════════════════════════════════════════════════

def test_selector_top_n():
    prompts = _make_scored_prompts(10)
    selector = ImageSelector(max_count=3, ensure_diversity=False)
    result = selector.select(prompts)
    assert len(result.selected) == 3
    assert result.total_available == 10
    return


def test_selector_diversity():
    prompts = _make_scored_prompts(20)
    selector = ImageSelector(max_count=3, ensure_diversity=True)
    result = selector.select(prompts)
    assert len(result.selected) == 3
    # Check that selected prompts have diverse combos
    combos = {f"{p.camera}|{p.lighting}|{p.composition}" for p in result.selected}
    assert len(combos) >= 2  # Should be somewhat diverse
    return


def test_selector_edge_cases():
    selector = ImageSelector(max_count=3)

    # Empty
    result = selector.select([])
    assert len(result.selected) == 0

    # Fewer than max
    prompts = _make_scored_prompts(2)
    result = selector.select(prompts)
    assert len(result.selected) == 2

    return


# ═══════════════════════════════════════════════════════════
# 7-9. Image Quality Gate
# ═══════════════════════════════════════════════════════════

def test_quality_gate_valid_image():
    gate = ImageQualityGate(strict=False)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    _create_test_png(path, 1080, 1080)

    try:
        result = gate.validate(path)
        assert result.passed, f"Quality gate failed: {[(c.name, c.passed, c.detail) for c in result.checks]}"
        assert len(result.checks) >= 5
        assert all(c.passed for c in result.checks)
    finally:
        os.unlink(path)
    return


def test_quality_gate_missing_file():
    gate = ImageQualityGate()
    result = gate.validate("nonexistent_file_xyz.png")
    assert not result.passed
    assert not result.checks[0].passed
    assert "not exist" in result.checks[0].detail.lower()
    return


def test_quality_gate_batch():
    gate = ImageQualityGate(strict=False)
    paths = []
    for i in range(3):
        fd, p = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        _create_test_png(p, 1080, 1080)
        paths.append(p)

    try:
        results = gate.validate_batch(paths)
        assert len(results) == 3
        assert all(r.passed for r in results), f"Results: {[(r.passed, r.score) for r in results]}"
    finally:
        for p in paths:
            os.unlink(p)
    return


# ═══════════════════════════════════════════════════════════
# 10-12. Image Exporter
# ═══════════════════════════════════════════════════════════

def test_exporter_prompt_txt():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ImageExporter(output_dir=Path(tmpdir))
        prompt = Prompt(
            positive_prompt="A cute witch with a baby dragon, merge gameplay",
            negative_prompt="low quality, blurry",
            camera="45_degree", lighting="warm", composition="center",
            seed=42, model="lovart",
        )
        prompt.score = PromptScore(
            gameplay=85, composition=90, hook=80, reward=88,
            brand=75, readability=92, novelty=70, diversity=82,
        )

        files = exporter.export(prompt, "", winner_id="winner_001")
        assert "txt" in files
        assert "json" in files
        assert "html" in files

        # Check prompt.txt content
        with open(files["txt"], "r") as f:
            content = f.read()
        assert "GOLDEN SAMPLE" in content
        assert "cute witch" in content.lower()
        assert "winner_001" in content

        # Check prompt.json content
        with open(files["json"], "r") as f:
            data = json.load(f)
        assert data["model"] == "lovart"
        assert data["camera"] == "45_degree"
        assert "score" in data
    return


def test_exporter_with_quality():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ImageExporter(output_dir=Path(tmpdir))
        prompt = Prompt(positive_prompt="test", negative_prompt="neg")
        quality = QualityResult(
            image_path="test.png",
            passed=True,
            score=100.0,
        )
        files = exporter.export(prompt, "", quality=quality)
        assert "quality" in files
        with open(files["quality"], "r") as f:
            data = json.load(f)
        assert data["passed"] is True
    return


def test_exporter_with_review():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = ImageExporter(output_dir=Path(tmpdir))
        prompt = Prompt(positive_prompt="test", negative_prompt="neg")
        review = {"hook": 8, "gameplay": 7, "reward": 9, "ctr": 8}
        files = exporter.export(prompt, "", review_scores=review)
        assert "review" in files
        with open(files["review"], "r") as f:
            data = json.load(f)
        assert data["scores"]["hook"] == 8
        assert data["average"] == 8.0
    return


# ═══════════════════════════════════════════════════════════
# 13-15. Golden Sample Pipeline
# ═══════════════════════════════════════════════════════════

def test_pipeline_plan_only():
    pipeline = GoldenSamplePipeline(strategy="balanced", model="lovart")
    prompts = pipeline.run_plan_only("output/winner_dna/winner_001.json")
    assert len(prompts) >= 10
    for p in prompts:
        assert p.positive_prompt
        assert p.model == "lovart"
        assert p.score is not None
    return


def test_pipeline_full_run():
    """Full pipeline without API (API unavailable)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GoldenSamplePipeline(
            strategy="aggressive",
            model="lovart",
            output_dir=Path(tmpdir),
            max_images=3,
        )
        result = pipeline.run("output/winner_dna/winner_001.json", prompt_count=20)

        assert result.winner_id == "winner_001"
        assert result.total_prompts >= 15
        assert result.selected_count == 3
        # API is unavailable, so generated_count should be 0
        # But the pipeline should still complete gracefully
        assert result.generated_count == 0
        assert result.elapsed_ms > 0
    return


def test_pipeline_api_check():
    pipeline = GoldenSamplePipeline()
    # API may or may not be available, but the check should work
    assert isinstance(pipeline.api_available, bool)
    return


# ═══════════════════════════════════════════════════════════
# 16-18. Pipeline Result
# ═══════════════════════════════════════════════════════════

def test_pipeline_result_summary():
    result = PipelineResult(
        winner_id="winner_001",
        total_prompts=20,
        selected_count=3,
        generated_count=3,
        passed_quality=3,
        exported_files={"txt": "output/prompt.txt", "json": "output/prompt.json"},
        elapsed_ms=1500,
    )
    summary = result.summary()
    assert "winner_001" in summary
    assert "20" in summary
    assert "3" in summary
    assert "1500ms" in summary
    return


def test_pipeline_result_error():
    result = PipelineResult(
        winner_id="winner_001",
        error="Lovart API timeout",
        elapsed_ms=30000,
    )
    summary = result.summary()
    assert "ERROR" in summary
    assert "Lovart API timeout" in summary
    return


def test_pipeline_result_empty():
    result = PipelineResult()
    assert result.winner_id == ""
    assert result.total_prompts == 0
    return


# ═══════════════════════════════════════════════════════════
# 19-20. Integration
# ═══════════════════════════════════════════════════════════

def test_integration_prompt_plan_export():
    """DNA → Prompt Planner → Top Prompts → Export (no API)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Load DNA
        with open("output/winner_dna/winner_001.json", "r") as f:
            dna_data = json.load(f)

        # Generate prompts
        planner = CreativePromptPlanner(strategy="aggressive", model="lovart")
        prompts = planner.generate(dna_data["dna"], count=20)
        top = planner.top_n(prompts, n=20)

        assert len(top) >= 15

        # Select top 3
        selector = ImageSelector(max_count=3)
        selection = selector.select(top)
        assert len(selection.selected) == 3

        # Export (no image)
        exporter = ImageExporter(output_dir=Path(tmpdir))
        top_prompt = selection.selected[0]
        files = exporter.export(
            top_prompt, "",
            winner_id=dna_data["winner_id"],
        )
        assert "txt" in files
        assert "json" in files
        assert "html" in files

        assert Path(files["txt"]).exists()
        assert Path(files["json"]).exists()
        assert Path(files["html"]).exists()
    return


def test_integration_all_winners():
    """All 3 winner DNAs should produce valid prompts."""
    dna_dir = Path("output/winner_dna")
    planner = CreativePromptPlanner(strategy="balanced", model="lovart")

    for dna_file in sorted(dna_dir.glob("*.json")):
        with open(dna_file, "r") as f:
            dna_data = json.load(f)

        prompts = planner.generate(dna_data["dna"], count=10)
        top = planner.top_n(prompts, n=5)
        assert len(top) >= 3
        for p in top:
            assert p.positive_prompt
            assert p.score is not None
            assert p.score.total >= 70  # Should be decent quality
    return


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Winner DNA
        ("Winner DNA 文件存在", test_winner_dna_files_exist),
        ("Winner DNA 格式正确", test_winner_dna_format),
        ("Winner DNA 全部可加载", test_winner_dna_all_loadable),
        # Image Selector
        ("Image Selector Top-N", test_selector_top_n),
        ("Image Selector 多样性", test_selector_diversity),
        ("Image Selector 边界情况", test_selector_edge_cases),
        # Quality Gate
        ("Quality Gate 有效图片", test_quality_gate_valid_image),
        ("Quality Gate 缺失文件", test_quality_gate_missing_file),
        ("Quality Gate 批量验证", test_quality_gate_batch),
        # Exporter
        ("Exporter prompt.txt", test_exporter_prompt_txt),
        ("Exporter quality.json", test_exporter_with_quality),
        ("Exporter review.json", test_exporter_with_review),
        # Pipeline
        ("Pipeline Plan Only", test_pipeline_plan_only),
        ("Pipeline Full Run", test_pipeline_full_run),
        ("Pipeline API Check", test_pipeline_api_check),
        # Pipeline Result
        ("Pipeline Result Summary", test_pipeline_result_summary),
        ("Pipeline Result Error", test_pipeline_result_error),
        ("Pipeline Result Empty", test_pipeline_result_empty),
        # Integration
        ("Integration DNA→Prompt→Export", test_integration_prompt_plan_export),
        ("Integration 全部3个Winner", test_integration_all_winners),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  Phase 3.0A: Golden Sample Pipeline Validation")
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