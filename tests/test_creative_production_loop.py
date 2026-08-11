import json

from PIL import Image

from market_ops.product.creative_production_loop import ExactCopyRenderer, ReferenceGroundedPromptCompiler


def test_prompt_compiler_injects_product_truth_and_single_count(tmp_path):
    profile = json.loads(open("config/creative_product_profile_merge_witches.json", encoding="utf-8").read())
    winner = {"visual_dna_summary": {"mood": "magic payoff", "palette": "purple gold"}}
    prompt, negative = ReferenceGroundedPromptCompiler(profile, winner).compile("product first")
    assert "exactly THREE identical purple witch hats" in prompt
    assert "official Merge Witches screenshots" in prompt
    assert "render NO text" in prompt
    assert "generic dark gothic poster" in negative


def test_exact_copy_renderer_outputs_standard_vertical_asset(tmp_path):
    source = tmp_path / "source.png"
    destination = tmp_path / "final.png"
    Image.new("RGB", (768, 1344), (60, 20, 90)).save(source)
    ExactCopyRenderer().render(source, destination)
    with Image.open(destination) as image:
        assert image.size == (1080, 1920)
        assert image.format == "PNG"
