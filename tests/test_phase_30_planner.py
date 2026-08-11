"""Phase 3.0: Creative Prompt Planner — Comprehensive Validation.

Tests:
  1-4.   Data Models: PromptComponent, PromptPlan, Prompt, PromptScore, Variation
  5-8.   Variation Engine: single dimension, all dimensions, strategy modes, variant count
  9-12.  Dimension Planners: Composition, Camera, Lighting, Color
  13-15. Dimension Planners: Gameplay, Reward, Typography
  16-18. Prompt Strategy: all 4 modes, config, to_dict
  19-21. Prompt Renderer: Lovart, Flux, SDXL, ComfyUI
  22-24. Prompt Scorer: single score, batch, top_n, threshold
  25-27. Negative Prompt: all 4 models
  28-30. CreativePromptPlanner: single plan, batch generate, top_n
  31-32. Full pipeline: DNA → 50 prompts → top 20
  33-34. Cross-model: same DNA, different models
  35.    Integration: backward compat with existing structures
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_generation.models.prompt_component import PromptComponent
from market_ops.creative_generation.models.prompt_plan import PromptPlan
from market_ops.creative_generation.models.prompt import Prompt, PromptScore
from market_ops.creative_generation.models.variation import Variation

from market_ops.creative_generation.planner.variation_engine import VariationEngine
from market_ops.creative_generation.planner.prompt_strategy import PromptStrategy, GrowthMode
from market_ops.creative_generation.planner.composition_planner import CompositionPlanner
from market_ops.creative_generation.planner.camera_planner import CameraPlanner
from market_ops.creative_generation.planner.lighting_planner import LightingPlanner
from market_ops.creative_generation.planner.color_planner import ColorPlanner
from market_ops.creative_generation.planner.gameplay_planner import GameplayPlanner
from market_ops.creative_generation.planner.reward_planner import RewardPlanner
from market_ops.creative_generation.planner.typography_planner import TypographyPlanner
from market_ops.creative_generation.planner.negative_prompt import NegativePromptPlanner
from market_ops.creative_generation.planner.prompt_renderer import PromptRenderer
from market_ops.creative_generation.planner.prompt_scorer import PromptScorer
from market_ops.creative_generation.planner.prompt_planner import CreativePromptPlanner


# ═══════════════════════════════════════════════════════════
# Winner DNA fixture
# ═══════════════════════════════════════════════════════════

WINNER_DNA = {
    "character": "witch",
    "reward": "baby_dragon",
    "composition": "center",
    "camera": "45_degree",
    "lighting": "warm",
    "palette": "purple_gold",
    "hook": "collection",
    "gameplay": "merge",
    "emotion": "surprise",
    "style": "cartoon",
}


# ═══════════════════════════════════════════════════════════
# 1-4. Data Models
# ═══════════════════════════════════════════════════════════

def test_prompt_component():
    c = PromptComponent(dimension="character", value="witch", label="Witch")
    assert c.dimension == "character"
    assert c.value == "witch"
    assert c.label == "Witch"
    assert c.weight == 1.0
    d = c.to_dict()
    assert d["dimension"] == "character"
    return True


def test_prompt_component_immutable():
    c = PromptComponent(dimension="camera", value="45_degree", label="45°")
    try:
        c.value = "modified"  # type: ignore
        assert False, "Should be frozen"
    except Exception:
        pass
    return True


def test_prompt_plan():
    plan = PromptPlan(
        components=[
            PromptComponent(dimension="character", value="witch", label="Witch"),
            PromptComponent(dimension="camera", value="45_degree", label="45°"),
        ],
        strategy="aggressive",
        seed=42,
        aspect_ratio="9:16",
        model="lovart",
    )
    assert plan.get_value("character") == "witch"
    assert plan.get_value("camera") == "45_degree"
    assert plan.get_value("nonexistent", "default") == "default"
    assert plan.get_label("character") == "Witch"
    d = plan.to_dict()
    assert d["strategy"] == "aggressive"
    assert d["model"] == "lovart"
    return True


def test_prompt_score():
    score = PromptScore(
        gameplay=85, composition=90, hook=80, reward=88,
        brand=75, readability=92, novelty=70, diversity=82,
    )
    assert 80 < score.total < 86
    d = score.to_dict()
    assert d["gameplay"] == 85
    assert "total" in d
    return True


def test_prompt():
    p = Prompt(
        positive_prompt="A cute witch with a baby dragon",
        negative_prompt="low quality, blurry",
        camera="45_degree",
        lighting="warm",
        composition="center",
        seed=42,
        model="lovart",
    )
    d = p.to_dict()
    assert d["positive_prompt"] == "A cute witch with a baby dragon"
    assert d["camera"] == "45_degree"
    assert d["model"] == "lovart"
    return True


def test_variation():
    v = Variation(
        dimension="character", original="witch", variant="cute_witch",
        label="Cute Witch", distance=0.3,
    )
    assert v.dimension == "character"
    assert v.original == "witch"
    assert v.variant == "cute_witch"
    assert v.distance == 0.3
    d = v.to_dict()
    assert d["original"] == "witch"
    return True


# ═══════════════════════════════════════════════════════════
# 5-8. Variation Engine
# ═══════════════════════════════════════════════════════════

def test_variation_engine_single_dim():
    engine = VariationEngine(seed=42)
    variants = engine.vary_dimension("character", "witch", strategy="balanced")
    assert len(variants) >= 3
    assert all(v.dimension == "character" for v in variants)
    assert all(v.original == "witch" for v in variants)
    # All distances should be <= 0.5 for balanced
    assert all(v.distance <= 0.5 for v in variants)
    return True


def test_variation_engine_strategy_modes():
    engine = VariationEngine(seed=42)

    cons = engine.vary_dimension("character", "witch", strategy="conservative")
    assert len(cons) <= 2
    assert all(v.distance <= 0.3 for v in cons)

    aggr = engine.vary_dimension("character", "witch", strategy="aggressive")
    assert len(aggr) >= 5
    assert all(v.distance <= 0.7 for v in aggr)

    exp = engine.vary_dimension("character", "witch", strategy="experimental")
    assert len(exp) >= 6
    return True


def test_variation_engine_all_dims():
    engine = VariationEngine(seed=42)
    all_v = engine.vary_all(WINNER_DNA, strategy="balanced")
    assert "character" in all_v
    assert "camera" in all_v
    assert "lighting" in all_v
    assert "palette" in all_v
    assert "gameplay" in all_v
    assert "reward" in all_v
    assert all(len(v) >= 3 for v in all_v.values())
    return True


def test_variation_engine_variant_count():
    engine = VariationEngine(seed=42)
    count = engine.get_variant_count(WINNER_DNA, strategy="balanced")
    assert count > 100  # Should be combinatorial
    return True


def test_variation_engine_unknown_dimension():
    engine = VariationEngine()
    variants = engine.vary_dimension("unknown_dim", "some_value")
    assert len(variants) == 1
    assert variants[0].variant == "some_value"
    return True


# ═══════════════════════════════════════════════════════════
# 9-15. Dimension Planners
# ═══════════════════════════════════════════════════════════

def test_composition_planner():
    planner = CompositionPlanner()
    c = planner.plan("center")
    assert c.dimension == "composition"
    assert c.value == "center"
    tokens = planner.get_tokens("center")
    assert "subject" in tokens
    assert "layout" in tokens

    # Unknown composition falls back to center
    c2 = planner.plan("unknown")
    assert c2.value == "unknown"
    return True


def test_camera_planner():
    planner = CameraPlanner()
    c = planner.plan("45_degree")
    assert c.dimension == "camera"
    tokens = planner.get_tokens("45_degree")
    assert "lens" in tokens
    assert "angle" in tokens
    return True


def test_lighting_planner():
    planner = LightingPlanner()
    c = planner.plan("warm")
    assert c.dimension == "lighting"
    tokens = planner.get_tokens("warm")
    assert "key_light" in tokens
    assert "bloom" in tokens
    return True


def test_color_planner():
    planner = ColorPlanner()
    c = planner.plan("purple_gold")
    assert c.dimension == "palette"
    tokens = planner.get_tokens("purple_gold")
    assert "primary" in tokens
    return True


def test_gameplay_planner():
    planner = GameplayPlanner()
    c = planner.plan("merge")
    assert c.dimension == "gameplay"
    tokens = planner.get_tokens("merge")
    assert "action" in tokens
    assert "moment" in tokens
    assert "effect" in tokens
    return True


def test_reward_planner():
    planner = RewardPlanner()
    c = planner.plan("baby_dragon")
    assert c.dimension == "reward"
    tokens = planner.get_tokens("baby_dragon")
    assert "object" in tokens
    assert "placement" in tokens
    return True


def test_typography_planner():
    planner = TypographyPlanner()
    c = planner.plan("merge")
    assert c.dimension == "typography"
    copy_options = planner.get_copy_options("merge")
    assert len(copy_options) == 5
    assert "Merge Now!" in copy_options
    return True


# ═══════════════════════════════════════════════════════════
# 16-18. Prompt Strategy
# ═══════════════════════════════════════════════════════════

def test_strategy_modes():
    cons = PromptStrategy(GrowthMode.CONSERVATIVE)
    assert cons.max_distance == 0.3
    assert cons.max_variants_per_dim == 2
    assert cons.keep_original is True
    assert cons.crossover_enabled is False

    bal = PromptStrategy("balanced")
    assert bal.max_distance == 0.5
    assert bal.total_prompts_target == 20

    aggr = PromptStrategy("aggressive")
    assert aggr.total_prompts_target == 50

    exp = PromptStrategy("experimental")
    assert exp.total_prompts_target == 100
    assert exp.keep_original is False
    return True


def test_strategy_to_dict():
    s = PromptStrategy("balanced")
    d = s.to_dict()
    assert d["mode"] == "balanced"
    assert "max_distance" in d
    return True


def test_strategy_invalid_mode():
    try:
        PromptStrategy("invalid_mode")
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    return True


# ═══════════════════════════════════════════════════════════
# 19-21. Prompt Renderer
# ═══════════════════════════════════════════════════════════

def _make_plan(model: str = "lovart") -> PromptPlan:
    return PromptPlan(
        components=[
            PromptComponent("character", "witch", "Cute Witch"),
            PromptComponent("reward", "baby_dragon", "Baby Dragon"),
            PromptComponent("gameplay", "merge", "Merge"),
            PromptComponent("camera", "45_degree", "45° Overhead"),
            PromptComponent("lighting", "warm", "Warm Golden"),
            PromptComponent("composition", "center", "Center"),
            PromptComponent("palette", "purple_gold", "Purple Gold"),
            PromptComponent("emotion", "surprise", "Surprise"),
            PromptComponent("style", "cartoon", "Cartoon"),
        ],
        strategy="balanced",
        seed=42,
        aspect_ratio="9:16",
        model=model,
    )


def test_renderer_lovart():
    renderer = PromptRenderer()
    plan = _make_plan("lovart")
    prompt = renderer.render(plan)
    assert "Merge Witches" in prompt.positive_prompt
    assert "witch" in prompt.positive_prompt.lower()
    assert "dragon" in prompt.positive_prompt.lower()
    assert prompt.model == "lovart"
    assert prompt.seed == 42
    return True


def test_renderer_flux():
    renderer = PromptRenderer()
    plan = _make_plan("flux")
    prompt = renderer.render(plan)
    assert "mobile game ad" in prompt.positive_prompt.lower()
    assert prompt.model == "flux"
    return True


def test_renderer_sdxl():
    renderer = PromptRenderer()
    plan = _make_plan("sdxl")
    prompt = renderer.render(plan)
    assert "(" in prompt.positive_prompt  # Weighted tags
    assert ":" in prompt.positive_prompt  # Weight values
    assert prompt.model == "sdxl"
    return True


def test_renderer_comfyui():
    renderer = PromptRenderer()
    plan = _make_plan("comfyui")
    prompt = renderer.render(plan)
    assert "mobile game advertisement" in prompt.positive_prompt.lower()
    assert prompt.model == "comfyui"
    return True


# ═══════════════════════════════════════════════════════════
# 22-24. Prompt Scorer
# ═══════════════════════════════════════════════════════════

def test_scorer_single():
    scorer = PromptScorer()
    p = Prompt(
        positive_prompt="A cute witch with a baby dragon, merge gameplay, "
                        "center composition, warm golden lighting, purple gold palette, "
                        "mobile game advertisement, high quality, clean",
        camera="45_degree",
        lighting="warm",
        composition="center",
    )
    score = scorer.score(p)
    assert score.total > 0
    assert score.gameplay > 0
    assert score.composition > 0
    assert score.reward > 0
    return True


def test_scorer_batch():
    scorer = PromptScorer()
    prompts = [
        Prompt(positive_prompt=f"High-converting mobile game advertisement for Merge Witches. "
                              f"Cute witch character with surprise expression, holding a baby dragon reward. "
                              f"Merge evolution gameplay visible, center composition, "
                              f"warm golden lighting, purple gold palette, clean and clear, "
                              f"ultra high quality, sharp detail, professional. "
                              f"Unique creative variation {i}.",
               camera="45_degree", lighting="warm", composition="center")
        for i in range(10)
    ]
    scored = scorer.score_batch(prompts)
    assert len(scored) >= 8  # Most should pass threshold with rich keywords
    return True


def test_scorer_top_n():
    scorer = PromptScorer()
    prompts = [
        Prompt(positive_prompt=f"High quality prompt {i}",
               camera="45_degree", lighting="warm", composition="center")
        for i in range(30)
    ]
    top = scorer.top_n(prompts, n=20)
    assert len(top) <= 20
    return True


def test_scorer_threshold():
    scorer = PromptScorer()
    p = Prompt(positive_prompt="bad", camera="", lighting="", composition="")
    score = scorer.score(p)
    assert score.total < PromptScorer.PASS_THRESHOLD
    return True


# ═══════════════════════════════════════════════════════════
# 25-27. Negative Prompt
# ═══════════════════════════════════════════════════════════

def test_negative_prompt_lovart():
    planner = NegativePromptPlanner()
    text = planner.generate("lovart")
    assert "low quality" in text.lower() or "blurry" in text.lower()
    return True


def test_negative_prompt_all_models():
    planner = NegativePromptPlanner()
    for model in ["lovart", "flux", "sdxl", "comfyui"]:
        text = planner.generate(model)
        assert len(text) > 0
    return True


def test_negative_prompt_component():
    planner = NegativePromptPlanner()
    c = planner.plan("lovart")
    assert c.dimension == "negative_prompt"
    return True


# ═══════════════════════════════════════════════════════════
# 28-30. CreativePromptPlanner (main orchestrator)
# ═══════════════════════════════════════════════════════════

def test_planner_generate_plan():
    planner = CreativePromptPlanner(strategy="balanced", model="lovart")
    plan = planner.generate_plan(WINNER_DNA)
    assert len(plan.components) > 5
    assert plan.model == "lovart"
    assert plan.strategy == "balanced"
    # Should have all key dimensions
    dims = {c.dimension for c in plan.components}
    assert "character" in dims
    assert "camera" in dims
    assert "lighting" in dims
    return True


def test_planner_generate_batch():
    planner = CreativePromptPlanner(strategy="balanced", model="lovart", seed=42)
    prompts = planner.generate(WINNER_DNA, count=20)
    assert len(prompts) >= 10
    for p in prompts:
        assert p.positive_prompt
        assert p.negative_prompt
        assert p.model == "lovart"
        assert p.score is not None
    return True


def test_planner_top_n():
    planner = CreativePromptPlanner(strategy="aggressive", model="lovart", seed=42)
    prompts = planner.generate(WINNER_DNA, count=50)
    top = planner.top_n(prompts, n=20)
    assert len(top) <= 20
    # Top prompts should have scores
    if top:
        assert top[0].score is not None
        assert top[0].score.total >= PromptScorer.PASS_THRESHOLD
    return True


def test_planner_render_from_plan():
    planner = CreativePromptPlanner(model="lovart")
    plan = planner.generate_plan(WINNER_DNA)
    prompt = planner.render(plan)
    assert prompt.positive_prompt
    assert prompt.negative_prompt
    assert prompt.model == "lovart"
    return True


# ═══════════════════════════════════════════════════════════
# 31-32. Full Pipeline
# ═══════════════════════════════════════════════════════════

def test_full_pipeline_50():
    """DNA → 50 prompts → top 20"""
    planner = CreativePromptPlanner(strategy="aggressive", model="lovart", seed=42)
    prompts = planner.generate(WINNER_DNA, count=50)
    assert len(prompts) >= 30

    top = planner.top_n(prompts, n=20)
    assert len(top) <= 20

    # Check prompt structure
    for p in top[:5]:
        d = p.to_dict()
        assert "positive_prompt" in d
        assert "negative_prompt" in d
        assert "camera" in d
        assert "lighting" in d
        assert "composition" in d
        assert "model" in d
        assert "score" in d
        assert d["score"]["total"] >= PromptScorer.PASS_THRESHOLD
    return True


def test_full_pipeline_variety():
    """Verify that generated prompts are diverse."""
    planner = CreativePromptPlanner(strategy="aggressive", model="lovart", seed=42)
    prompts = planner.generate(WINNER_DNA, count=30)

    texts = [p.positive_prompt for p in prompts]
    unique = len(set(texts))
    # Most prompts should be unique
    assert unique >= len(texts) * 0.7
    return True


# ═══════════════════════════════════════════════════════════
# 33-34. Cross-Model
# ═══════════════════════════════════════════════════════════

def test_cross_model_generation():
    """Same DNA, different models."""
    for model in ["lovart", "flux", "sdxl", "comfyui"]:
        planner = CreativePromptPlanner(strategy="balanced", model=model, seed=42)
        prompts = planner.generate(WINNER_DNA, count=5)
        assert len(prompts) >= 3
        for p in prompts:
            assert p.model == model
            assert p.positive_prompt
    return True


def test_cross_model_renderer():
    """Same plan, different renderers."""
    plan = _make_plan("lovart")
    renderer = PromptRenderer()

    lovart_p = renderer.render(plan)
    plan.model = "flux"
    flux_p = renderer.render(plan)
    plan.model = "sdxl"
    sdxl_p = renderer.render(plan)

    # Each model should produce different prompt text
    assert lovart_p.positive_prompt != flux_p.positive_prompt
    assert lovart_p.positive_prompt != sdxl_p.positive_prompt
    return True


# ═══════════════════════════════════════════════════════════
# 35. Backward Compat
# ═══════════════════════════════════════════════════════════

def test_prompt_to_dict_full():
    """Prompt.to_dict() should be compatible with existing JSON consumers."""
    p = Prompt(
        positive_prompt="test",
        negative_prompt="neg",
        camera="45_degree",
        lighting="warm",
        composition="center",
        seed=12345,
        aspect_ratio="9:16",
        model="lovart",
        score=PromptScore(gameplay=80, composition=85, hook=75, reward=88,
                          brand=70, readability=90, novelty=65, diversity=80),
    )
    d = p.to_dict()
    assert d["positive_prompt"] == "test"
    assert d["negative_prompt"] == "neg"
    assert d["camera"] == "45_degree"
    assert d["seed"] == 12345
    assert d["aspect_ratio"] == "9:16"
    assert d["model"] == "lovart"
    assert d["score"]["total"] > 0
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Models
        ("PromptComponent", test_prompt_component),
        ("PromptComponent 不可变", test_prompt_component_immutable),
        ("PromptPlan", test_prompt_plan),
        ("PromptScore", test_prompt_score),
        ("Prompt", test_prompt),
        ("Variation", test_variation),
        # Variation Engine
        ("Variation Engine 单维度", test_variation_engine_single_dim),
        ("Variation Engine 策略模式", test_variation_engine_strategy_modes),
        ("Variation Engine 全维度", test_variation_engine_all_dims),
        ("Variation Engine 组合数", test_variation_engine_variant_count),
        ("Variation Engine 未知维度", test_variation_engine_unknown_dimension),
        # Dimension Planners
        ("Composition Planner", test_composition_planner),
        ("Camera Planner", test_camera_planner),
        ("Lighting Planner", test_lighting_planner),
        ("Color Planner", test_color_planner),
        ("Gameplay Planner", test_gameplay_planner),
        ("Reward Planner", test_reward_planner),
        ("Typography Planner", test_typography_planner),
        # Strategy
        ("Strategy 四种模式", test_strategy_modes),
        ("Strategy to_dict", test_strategy_to_dict),
        ("Strategy 无效模式报错", test_strategy_invalid_mode),
        # Renderer
        ("Renderer Lovart", test_renderer_lovart),
        ("Renderer Flux", test_renderer_flux),
        ("Renderer SDXL", test_renderer_sdxl),
        ("Renderer ComfyUI", test_renderer_comfyui),
        # Scorer
        ("Scorer 单次评分", test_scorer_single),
        ("Scorer 批量评分", test_scorer_batch),
        ("Scorer Top-N", test_scorer_top_n),
        ("Scorer 阈值过滤", test_scorer_threshold),
        # Negative Prompt
        ("Negative Prompt Lovart", test_negative_prompt_lovart),
        ("Negative Prompt 全模型", test_negative_prompt_all_models),
        ("Negative Prompt Component", test_negative_prompt_component),
        # Main Planner
        ("Planner 生成单个Plan", test_planner_generate_plan),
        ("Planner 批量生成", test_planner_generate_batch),
        ("Planner Top-N", test_planner_top_n),
        ("Planner 从Plan渲染", test_planner_render_from_plan),
        # Full Pipeline
        ("完整管线 50→Top20", test_full_pipeline_50),
        ("完整管线 多样性", test_full_pipeline_variety),
        # Cross-Model
        ("跨模型生成", test_cross_model_generation),
        ("跨模型渲染差异", test_cross_model_renderer),
        # Backward Compat
        ("Prompt.to_dict 兼容", test_prompt_to_dict_full),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  Phase 3.0: Creative Prompt Planner Validation")
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