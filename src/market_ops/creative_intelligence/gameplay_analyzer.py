"""E11 Phase 4.1 — Gameplay Analyzer（IAP 版）。

分析素材展示的玩法是否传递 IAP 价值：
  - progression:     level_growth / collection_growth / upgrade
  - economy:         rare_item / premium_currency / unlock
  - retention_signal: long_term_goal / character_attachment

IAP 与 IAA 最大区别：
  IAA 要"简单快速爽" → 看广告
  IAP 要"长期价值、成长、收集、付费点" → 付费
"""

from __future__ import annotations

from .models import (
    GameplayFeatures,
    ProgressionProfile,
    EconomyProfile,
    RetentionSignal,
    HookType,
)


class GameplayAnalyzer:
    """玩法分析器。

    分析素材展示的玩法维度。
    """

    # 进度关键词
    PROGRESSION_KEYWORDS = [
        "level", "progress", "upgrade", "evolve", "grow", "develop",
        "advance", "next", "stage", "complete", "finish",
    ]
    # 收集关键词
    COLLECTION_KEYWORDS = [
        "collect", "collection", "gather", "set", "all", "complete",
        "merge", "combine", "craft", "build",
    ]
    # 经济关键词
    ECONOMY_KEYWORDS = [
        "rare", "legendary", "epic", "special", "unique", "exclusive",
        "unlock", "discover", "find", "gem", "coin", "treasure",
    ]
    # 留存关键词
    RETENTION_KEYWORDS = [
        "long", "journey", "story", "adventure", "quest", "goal",
        "character", "dragon", "pet", "friend", "team",
    ]

    def analyze(self, entity) -> GameplayFeatures:
        analysis = getattr(entity, "analysis", None)
        identity = getattr(entity, "identity", None)

        name = getattr(identity, "name", "").lower() if identity else ""
        hook_type_str = getattr(analysis, "hook_type", "").lower() if analysis else ""
        video_dna = getattr(analysis, "video_dna", {}) or {} if analysis else {}

        # Progression
        progression = self._analyze_progression(video_dna, name, hook_type_str)

        # Economy
        economy = self._analyze_economy(video_dna, name, hook_type_str)

        # Retention Signal
        retention = self._analyze_retention(video_dna, name, hook_type_str)

        return GameplayFeatures(
            progression=progression,
            economy=economy,
            retention_signal=retention,
        )

    def analyze_batch(self, entities: list) -> list[GameplayFeatures]:
        return [self.analyze(e) for e in entities]

    # ── Progression ──────────────────────────────────────

    def _analyze_progression(self, dna_data: dict, name: str, hook_type: str) -> ProgressionProfile:
        level_growth = self._score_from_keywords(name, self.PROGRESSION_KEYWORDS, base=40)
        collection_growth = self._score_from_keywords(name, self.COLLECTION_KEYWORDS, base=30)
        upgrade = float(dna_data.get("upgrade", 0))

        if hook_type == "progression":
            level_growth = max(level_growth, 85)
            upgrade = max(upgrade, 70)
        if hook_type == "collection":
            collection_growth = max(collection_growth, 90)
        if "merge" in name:
            collection_growth = max(collection_growth, 70)
        if "upgrade" in name or "evolve" in name:
            upgrade = max(upgrade, 80)

        return ProgressionProfile(
            level_growth=level_growth,
            collection_growth=collection_growth,
            upgrade=upgrade,
        )

    # ── Economy ──────────────────────────────────────────

    def _analyze_economy(self, dna_data: dict, name: str, hook_type: str) -> EconomyProfile:
        rare_item = self._score_from_keywords(name, self.ECONOMY_KEYWORDS, base=20)
        premium_currency = float(dna_data.get("premium_currency", 0))
        unlock = float(dna_data.get("unlock", 0))

        if hook_type in ("rare_item", "reward_reveal"):
            rare_item = max(rare_item, 85)
        if "unlock" in name:
            unlock = max(unlock, 80)
        if "rare" in name or "legendary" in name:
            rare_item = max(rare_item, 90)
        if "buy" in name or "shop" in name or "store" in name:
            premium_currency = max(premium_currency, 70)

        return EconomyProfile(
            rare_item=rare_item,
            premium_currency=premium_currency,
            unlock=unlock,
        )

    # ── Retention Signal ─────────────────────────────────

    def _analyze_retention(self, dna_data: dict, name: str, hook_type: str) -> RetentionSignal:
        long_term_goal = self._score_from_keywords(name, self.RETENTION_KEYWORDS, base=30)
        character_attachment = float(dna_data.get("character_attachment", 0))

        if hook_type in ("collection", "rare_item"):
            long_term_goal = max(long_term_goal, 70)
        if "character" in name or "dragon" in name:
            character_attachment = max(character_attachment, 75)
        if "collect" in name:
            long_term_goal = max(long_term_goal, 75)

        return RetentionSignal(
            long_term_goal=long_term_goal,
            character_attachment=character_attachment,
        )

    # ── Helpers ──────────────────────────────────────────

    @staticmethod
    def _score_from_keywords(name: str, keywords: list[str], base: float = 30) -> float:
        matches = sum(1 for kw in keywords if kw in name)
        if matches >= 3:
            return 90
        if matches >= 2:
            return 75
        if matches >= 1:
            return 60
        return base