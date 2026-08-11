"""
E15.1.2 — Store Metadata Agent

Takes raw game information and produces a complete, store-ready
MetadataPackage for both Google Play and App Store.
"""
from __future__ import annotations

from typing import Dict, List

from operation.publishing.metadata.models import MetadataPackage, StoreMetadata

# Keyword seed by category (extensible)
_KEYWORD_SEED = {
    "puzzle": ["puzzle", "brain", "match", "logic", "solve"],
    "merge": ["merge", "combine", "discover", "craft", "evolve"],
    "casual": ["casual", "fun", "easy", "relax", "free"],
    "simulation": ["sim", "tycoon", "build", "manage", "grow"],
    "action": ["action", "battle", "fight", "hero", "epic"],
}


class MetadataAgent:
    """Produces store-ready metadata from game config + build info."""

    def build(self, game_config: dict,
              build_info: dict) -> MetadataPackage:
        game_id = game_config.get("game_id", "")
        platforms = game_config.get("platforms", ["android", "ios"])
        meta = {}
        for platform in platforms:
            meta[platform] = self._build_for(game_config, build_info, platform)
        return MetadataPackage(game_id=game_id, platforms=meta)

    def _build_for(self, game_config: dict, build_info: dict,
                   platform: str) -> StoreMetadata:
        name = game_config.get("display_name", game_config["game_id"])
        category = game_config.get("category", "casual")
        genre = game_config.get("genres", ["casual"])[0]
        keywords = self._gen_keywords(name, category, genre)

        return StoreMetadata(
            game_id=game_config["game_id"],
            platform=platform,
            title=name,
            short_description=game_config.get("short_description",
                                              f"{name} — a fun {genre} game!"),
            full_description=game_config.get("full_description",
                                             self._default_full(name, genre)),
            keywords=keywords,
            category=category,
            age_rating=game_config.get("age_rating", "Everyone"),
            privacy_url=game_config.get("privacy_url",
                                        f"https://{name.lower().replace(' ', '')}.com/privacy"),
            screenshots=game_config.get("screenshots", []),
            feature_graphic=game_config.get("feature_graphic", ""),
            icon=game_config.get("icon", f"assets/{game_config['game_id']}/icon.png"),
            app_preview=game_config.get("app_preview", ""),
            assets=game_config.get("assets", {}),
            version=build_info.get("version", "1.0.0"),
        )

    def _gen_keywords(self, name: str, category: str, genre: str) -> List[str]:
        base = _KEYWORD_SEED.get(genre, ["game", "fun", "free"])
        words = list(set(base + _KEYWORD_SEED.get(category, [])))
        words.extend([w.lower() for w in name.split() if len(w) > 2])
        return words[:8]

    def _default_full(self, name: str, genre: str) -> str:
        return (
            f"Discover the magic of {name}! "
            f"An exciting {genre} adventure awaits. "
            f"Play now for free."
        )


__all__ = ["MetadataAgent"]
