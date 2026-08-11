"""E15.1.2 — BlueprintGenerator (ProductSpec -> GameBlueprint)."""
from operation.factory_brain import BlueprintGenerator, ProductSpec


def _spec(genre="merge", theme="vampire", monetization="hybrid",
          starter_pack=True, keywords=None):
    return ProductSpec(
        spec_id=f"spec_{genre}_{theme}_001",
        opportunity_id="o1", genre=genre, theme=theme,
        target_geos=["US", "JP"], monetization=monetization,
        starter_pack=starter_pack,
        aso_keywords=keywords or ["merge magic", "vampire merge"])


def test_build_returns_blueprint_ids():
    bp = BlueprintGenerator().build(_spec())
    assert bp.spec_id == "spec_merge_vampire_001"
    assert bp.blueprint_id == "bp_merge_vampire_001"


def test_core_loop_is_genre_specific():
    merge = BlueprintGenerator().build(_spec(genre="merge"))
    idle = BlueprintGenerator().build(_spec(genre="idle", theme="tycoon"))
    assert merge.core_loop == ["merge", "reward", "unlock"]
    assert idle.core_loop != merge.core_loop


def test_unknown_genre_gets_generic_loop():
    bp = BlueprintGenerator().build(_spec(genre="rhythm", theme="beat"))
    assert bp.core_loop == ["play", "reward", "progress"]


def test_hybrid_has_both_iaa_and_iap():
    bp = BlueprintGenerator().build(_spec(monetization="hybrid"))
    assert bp.iaa and bp.iap
    assert "rewarded_video" in bp.iaa


def test_pure_iaa_has_no_iap_but_adds_banner():
    bp = BlueprintGenerator().build(
        _spec(monetization="iaa", starter_pack=False))
    assert bp.iap == []
    assert "banner" in bp.iaa


def test_pure_iap_has_vip_and_no_iaa():
    bp = BlueprintGenerator().build(
        _spec(monetization="iap", starter_pack=False))
    assert bp.iaa == []
    assert "vip_subscription" in bp.iap


def test_starter_pack_flag_forces_bundle_first():
    bp = BlueprintGenerator().build(
        _spec(monetization="iaa", starter_pack=True))
    # iaa product normally has no iap; starter_pack flag injects it
    assert bp.iap and bp.iap[0] == "starter_pack"


def test_meta_weaves_theme():
    bp = BlueprintGenerator().build(_spec(genre="merge", theme="vampire"))
    assert "vampire" in bp.meta and "album" in bp.meta


def test_aso_keywords_passthrough():
    bp = BlueprintGenerator().build(_spec(keywords=["a", "b"]))
    assert bp.aso_keywords == ["a", "b"]


def test_build_batch_maps_all():
    specs = [_spec(theme="a"), _spec(theme="b")]
    bps = BlueprintGenerator().build_batch(specs)
    assert [b.theme for b in bps] == ["a", "b"]


def test_to_game_product_is_development_and_seeds_selling_points():
    bp = BlueprintGenerator().build(_spec())
    gp = BlueprintGenerator.to_game_product(bp, monetization="hybrid")
    assert gp.status == "development"
    assert gp.game_id == "g_merge_vampire_001"
    assert gp.package_name == "com.leanfactory.merge.vampire"
    assert gp.selling_points  # seeded from core loop
    assert "ja-JP" in gp.locales  # JP geo -> locale


def test_serialization_roundtrips_keys():
    bp = BlueprintGenerator().build(_spec())
    d = bp.to_dict()
    for k in ("core_loop", "iaa", "iap", "meta", "aso_keywords"):
        assert k in d
