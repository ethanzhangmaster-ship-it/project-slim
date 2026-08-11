"""Shared fixtures for E15.1.1 tests (no live data)."""
from operation.publishing_factory.catalog.product_profile import (
    GameProduct, GameStatus,
)


def game(game_id="merge_witch", genre="merge", status="ready", version="1.0.0",
         published_version="", monetization="iaa", display_name=None,
         keywords=None, locales=None, rejection_history=None, metrics=None,
         selling_points=None, platforms=None):
    return GameProduct(
        game_id=game_id,
        display_name=display_name or game_id.replace("_", " ").title(),
        package_name=f"com.lf.{game_id}",
        genre=genre, status=status, version=version,
        published_version=published_version, monetization=monetization,
        keywords=keywords or [], locales=locales or ["en-US"],
        rejection_history=rejection_history or [],
        metrics=metrics or {}, selling_points=selling_points or [],
        platforms=platforms or ["google_play"],
    )


def fleet(n=5):
    """A small diverse fleet for batch tests."""
    out = []
    specs = [
        ("merge_witch", "merge", "ready", "1.0.0", ""),
        ("hospital_fever", "casual", "published", "1.2.0", "1.1.0"),
        ("block_puzzle", "puzzle", "rejected", "1.0.0", ""),
        ("word_quest", "word", "published", "2.0.0", "2.0.0"),
        ("idle_miner", "idle", "development", "0.9.0", ""),
    ]
    for i, (gid, g, s, v, pv) in enumerate(specs[:n]):
        out.append(game(game_id=gid, genre=g, status=s, version=v,
                        published_version=pv))
    return out
