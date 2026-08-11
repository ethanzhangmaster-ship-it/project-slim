"""
E15.1.2 — Blueprint Generator (Game Blueprint Generator)
=========================================================

ProductSpec  ->  GameBlueprint  ->  (hand to Unity Operation Agent, E15.4)

Turns a production order into a concrete product design:

    input:   Merge + Vampire + Female US   (a ProductSpec)
    output:
        core_loop:  merge -> reward -> unlock
        iaa:        rewarded_video, interstitial
        iap:        starter_pack, remove_ads
        meta:       fantasy collection
        aso:        vampire merge, magic merge

Deterministic: core loops, ad formats, IAP bundles and meta layers come
from fixed per-genre tables. Monetization flavour (iaa / iap / hybrid)
decides which IAA/IAP lists apply. No LLM.
"""
from __future__ import annotations

from typing import Dict, List

from operation.publishing_factory.catalog.product_profile import GameProduct

from .models import GameBlueprint, ProductSpec

# per-genre core gameplay loop (deterministic)
_CORE_LOOP: Dict[str, List[str]] = {
    "merge": ["merge", "reward", "unlock"],
    "puzzle": ["match", "clear", "progress"],
    "idle": ["collect", "upgrade", "prestige"],
    "word": ["spell", "score", "advance"],
    "casual": ["tap", "score", "beat_level"],
    "simulation": ["build", "serve", "expand"],
    "action": ["fight", "loot", "power_up"],
}

# per-genre meta / collection layer
_META: Dict[str, str] = {
    "merge": "collection album",
    "puzzle": "level map",
    "idle": "empire expansion",
    "word": "world journey",
    "casual": "sticker book",
    "simulation": "city / venue growth",
    "action": "hero roster",
}

# ad formats offered when a game runs IAA
_IAA_FORMATS: List[str] = ["rewarded_video", "interstitial"]
_IAA_BANNER = "banner"          # only for pure-iaa (more aggressive)

# IAP bundles offered when a game runs IAP
_IAP_BUNDLES: List[str] = ["starter_pack", "remove_ads", "coin_pack"]
_IAP_VIP = "vip_subscription"   # only for iap-led products


class BlueprintGenerator:
    """ProductSpec -> full GameBlueprint (deterministic)."""

    def build(self, spec: ProductSpec) -> GameBlueprint:
        genre = spec.genre
        core = list(_CORE_LOOP.get(genre, ["play", "reward", "progress"]))
        meta_base = _META.get(genre, "collection")
        # weave the theme into the meta layer for flavour
        meta = f"{spec.theme} {meta_base}".strip() if spec.theme else meta_base

        iaa: List[str] = []
        iap: List[str] = []
        mon = spec.monetization
        if mon in ("iaa", "hybrid"):
            iaa = list(_IAA_FORMATS)
            if mon == "iaa":
                iaa.append(_IAA_BANNER)     # pure-IAA can afford banners
        if mon in ("iap", "hybrid"):
            iap = list(_IAP_BUNDLES)
            if mon == "iap":
                iap.append(_IAP_VIP)
        if spec.starter_pack and "starter_pack" not in iap:
            iap.insert(0, "starter_pack")

        return GameBlueprint(
            blueprint_id=spec.spec_id.replace("spec_", "bp_"),
            spec_id=spec.spec_id,
            genre=genre,
            theme=spec.theme,
            core_loop=core,
            iaa=iaa,
            iap=iap,
            meta=meta,
            aso_keywords=list(spec.aso_keywords),
            target_geos=list(spec.target_geos),
        )

    def build_batch(self, specs: List[ProductSpec]) -> List[GameBlueprint]:
        return [self.build(s) for s in specs]

    # ------------------------------------------------------------------ #
    @staticmethod
    def to_game_product(bp: GameBlueprint,
                        monetization: str = "hybrid") -> GameProduct:
        """Blueprint -> fleet-ready GameProduct (status=development).

        Selling points are seeded from the core loop so the Publishing
        Factory's ASO generator has real hooks to work with.
        """
        game_id = bp.blueprint_id.replace("bp_", "g_")
        return GameProduct(
            game_id=game_id,
            package_name=f"com.leanfactory.{bp.genre}.{bp.theme}",
            display_name=f"{bp.genre.title()} {bp.theme.title()}".strip(),
            platforms=["google_play", "app_store"],
            genre=bp.genre,
            monetization=monetization,
            status="development",
            selling_points=[s.replace("_", " ").title()
                            for s in bp.core_loop],
            keywords=list(bp.aso_keywords),
            locales=["en-US"] + (["ja-JP"] if "JP" in bp.target_geos else []),
        )


__all__ = ["BlueprintGenerator"]
