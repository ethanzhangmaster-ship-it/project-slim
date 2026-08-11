"""E1: Multi-modal Creative Analysis Engine — analyze URLs, images, text to extract genomes.

Upgrades HumanIdeaInbox with multi-modal input analysis:
  - Text → DNA extraction → Genome
  - URL → game analysis → Genome
  - Image/Video → visual analysis → genome hints (mock for MVP)
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any

from market_ops.creative_opportunity.schemas import HumanIdea, OpportunitySource
from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType
from market_ops.creative_genome_builder import CreativeGenomeBuilder


class CreativeAnalysisEngine:
    """Analyzes multi-modal inputs to extract creative genomes.

    Supports:
      - Text description → genome extraction
      - Google Play / App Store URLs → game analysis
      - Image/video → visual/style analysis (mock)
    """

    def __init__(self) -> None:
        self._genome_builder = CreativeGenomeBuilder()

    # ── Text Analysis ───────────────────────────────────────

    def analyze_text(self, text: str) -> dict[str, Any]:
        """Analyze a text description of a game idea.

        Returns genome hints + scoring.
        """
        text_lower = text.lower()
        genes = {
            "core_loop": self._detect_core_loop(text_lower),
            "theme": self._detect_theme(text_lower),
            "hook": self._detect_hook(text_lower),
            "reward": self._detect_reward(text_lower),
            "character": self._detect_character(text_lower),
            "visual": self._detect_visual(text_lower),
            "monetization": self._detect_monetization(text_lower),
        }

        # Remove None values
        genes = {k: v for k, v in genes.items() if v}

        confidence = self._estimate_confidence(text, genes)

        return {
            "idea_type": "gameplay",
            "category": genes.get("core_loop", "unknown"),
            "genes": genes,
            "missing_dimensions": self._find_missing(genes),
            "suggestions": self._generate_suggestions(genes, text_lower),
            "confidence": confidence,
        }

    # ── URL Analysis ────────────────────────────────────────

    def analyze_url(self, url: str) -> dict[str, Any]:
        """Analyze a game URL (Google Play, App Store, etc.).

        Returns game analysis + opportunity assessment.
        """
        url_type = self._detect_url_type(url)

        analysis = {
            "url": url,
            "url_type": url_type,
            "extracted_genome": {},
            "competitor_analysis": {},
            "opportunity_score": 0,
            "recommendation": "review",
        }

        if url_type == "google_play":
            analysis.update(self._analyze_google_play_url(url))
        elif url_type == "app_store":
            analysis.update(self._analyze_app_store_url(url))
        elif url_type == "youtube":
            analysis.update(self._analyze_youtube_url(url))
        elif url_type == "tiktok":
            analysis.update(self._analyze_tiktok_url(url))

        return analysis

    # ── Image/Video Analysis (mock) ─────────────────────────

    def analyze_media(self, media_type: str, description: str) -> dict[str, Any]:
        """Mock analysis of image/video content.

        Args:
            media_type: 'image' or 'video'
            description: Human-provided description of the media
        """
        tags = description.lower().split()
        return {
            "media_type": media_type,
            "hook": self._detect_hook(description),
            "character": self._detect_character(description),
            "reward": self._detect_reward(description),
            "structure": self._detect_video_structure(description, media_type),
            "ctr_prediction": "high" if any(t in tags for t in ["rescue", "cute", "baby"]) else "medium",
            "suggested_mutations": self._suggest_media_mutations(description),
            "confidence": 0.6,
        }

    # ── Full Pipeline: Any input → Genome ───────────────────

    def any_to_genome(self, idea: HumanIdea) -> Genome:
        """Convert any HumanIdea (text/URL/media) into a V5 Genome."""
        if idea.metadata.get("url"):
            analysis = self.analyze_url(idea.metadata["url"])
            genes_data = analysis.get("extracted_genome", {})
        elif idea.metadata.get("media_type"):
            analysis = self.analyze_media(
                idea.metadata.get("media_type", "image"),
                idea.description + " " + idea.title,
            )
            genes_data = analysis
        else:
            analysis = self.analyze_text(idea.title + ". " + idea.description)
            genes_data = analysis.get("genes", {})

        return self._genes_to_genome(idea, genes_data)

    # ── Internal: Detection ─────────────────────────────────

    @staticmethod
    def _detect_core_loop(text: str) -> str | None:
        loops = {
            "merge": ["merge", "合成"],
            "sort": ["sort", "排序", "分类"],
            "puzzle": ["puzzle", "解谜", "puzzle"],
            "simulation": ["simulation", "模拟", "经营"],
            "battle": ["battle", "战斗", "fight"],
            "decorate": ["decorate", "装修", "design"],
        }
        for loop, keywords in loops.items():
            if any(kw in text for kw in keywords):
                return loop
        return None

    @staticmethod
    def _detect_theme(text: str) -> str | None:
        themes = {
            "factory": ["factory", "工厂", "产业"],
            "home": ["home", "家", "房间", "装修"],
            "pet": ["pet", "宠物", "动物"],
            "dragon": ["dragon", "龙"],
            "fantasy": ["fantasy", "魔法", "witch"],
            "travel": ["travel", "旅行", "explore"],
        }
        for theme, keywords in themes.items():
            if any(kw in text for kw in keywords):
                return theme
        return None

    @staticmethod
    def _detect_hook(text: str) -> str | None:
        if any(w in text for w in ["rescue", "save", "help", "救援"]):
            return "rescue"
        if any(w in text for w in ["reward", "reward", "奖励", "bonus"]):
            return "reward"
        if any(w in text for w in ["mess", "clean", "混乱", "整理"]):
            return "mess_to_clean"
        if any(w in text for w in ["build", "建设", "progress"]):
            return "build_progress"
        if any(w in text for w in ["collection", "收集", "collect"]):
            return "collection"
        return None

    @staticmethod
    def _detect_reward(text: str) -> str | None:
        if any(w in text for w in ["evolution", "进化"]):
            return "evolution"
        if any(w in text for w in ["collection", "收集"]):
            return "collection"
        if any(w in text for w in ["growth", "成长", "升级"]):
            return "growth"
        if any(w in text for w in ["unlock", "解锁"]):
            return "unlock"
        return None

    @staticmethod
    def _detect_character(text: str) -> str | None:
        chars = ["dragon", "animal", "baby", "pet", "witch", "mermaid"]
        for c in chars:
            if c in text.lower():
                return c
        return None

    @staticmethod
    def _detect_visual(text: str) -> str | None:
        if "3d" in text:
            return "3d_cartoon"
        if any(w in text for w in ["bright", "colorful"]):
            return "bright"
        if any(w in text for w in ["cozy", "cozy", "温暖"]):
            return "cozy"
        return None

    @staticmethod
    def _detect_monetization(text: str) -> str | None:
        if "iaa" in text or "ad" in text:
            return "IAA"
        if "iap" in text or "purchase" in text:
            return "IAP"
        if "battle pass" in text or "battle_pass" in text:
            return "battle_pass"
        return "IAA + energy"

    @staticmethod
    def _detect_url_type(url: str) -> str:
        u = url.lower()
        if "play.google.com" in u:
            return "google_play"
        if "apps.apple.com" in u:
            return "app_store"
        if "youtube.com" in u or "youtu.be" in u:
            return "youtube"
        if "tiktok.com" in u:
            return "tiktok"
        if "reddit.com" in u:
            return "reddit"
        return "unknown"

    @staticmethod
    def _detect_video_structure(desc: str, media_type: str) -> dict[str, Any]:
        if media_type == "image":
            return {"type": "static", "elements": ["hero", "cta"]}
        return {
            "type": "video",
            "structure": "hook_body_cta",
            "estimated_duration": 15,
            "pace": "fast" if "fast" in desc.lower() else "medium",
        }

    @staticmethod
    def _suggest_media_mutations(desc: str) -> list[str]:
        suggestions = []
        if "rescue" in desc.lower():
            suggestions.append("add_collection_meta")
            suggestions.append("add_evolution_reward")
        if "merge" in desc.lower() or "sort" in desc.lower():
            suggestions.append("add_simulation_layer")
        return suggestions

    # ── Internal: Scoring ───────────────────────────────────

    def _estimate_confidence(self, text: str, genes: dict[str, str]) -> float:
        """Higher detail = higher confidence."""
        word_count = len(text.split())
        gene_count = len(genes)
        confidence = min(0.9, 0.3 + word_count * 0.01 + gene_count * 0.05)
        return round(confidence, 2)

    @staticmethod
    def _find_missing(genes: dict[str, str]) -> list[str]:
        all_dims = ["core_loop", "theme", "hook", "reward", "character", "visual", "monetization"]
        return [d for d in all_dims if d not in genes]

    @staticmethod
    def _generate_suggestions(genes: dict[str, str], text: str) -> list[str]:
        suggestions = []
        if "core_loop" not in genes:
            suggestions.append("Define the core gameplay loop")
        if "reward" not in genes:
            suggestions.append("Add a reward/collectable system")
        if "character" not in genes:
            suggestions.append("Consider adding a character/avatar")
        return suggestions

    # ── Mock URL Analyzers ──────────────────────────────────

    @staticmethod
    def _analyze_google_play_url(url: str) -> dict[str, Any]:
        # Mock: extract app ID and return analysis
        return {
            "extracted_genome": {
                "core": "sort_puzzle",
                "retention": "collection",
                "monetization": "IAA",
            },
            "competitor_analysis": {
                "weakness": "low depth",
                "opportunity": "add merge decoration layer",
            },
            "opportunity_score": 82,
            "recommendation": "build_prototype",
        }

    @staticmethod
    def _analyze_app_store_url(url: str) -> dict[str, Any]:
        return {
            "extracted_genome": {"core": "merge", "monetization": "IAP"},
            "opportunity_score": 75,
            "recommendation": "review",
        }

    @staticmethod
    def _analyze_youtube_url(url: str) -> dict[str, Any]:
        return {
            "extracted_genome": {"hook": "rescue", "pace": "fast"},
            "opportunity_score": 70,
            "recommendation": "monitor",
        }

    @staticmethod
    def _analyze_tiktok_url(url: str) -> dict[str, Any]:
        return {
            "extracted_genome": {"hook": "challenge", "pace": "fast"},
            "opportunity_score": 68,
            "recommendation": "watch",
        }

    # ── Genome Conversion ───────────────────────────────────

    def _genes_to_genome(self, idea: HumanIdea, genes_data: dict[str, Any]) -> Genome:
        """Convert extracted genes + idea metadata into V5 Genome."""
        gene_list: list[Gene] = []

        gene_mappings: list[tuple[str, GeneType]] = [
            ("core_loop", GeneType.GAMEPLAY),
            ("core", GeneType.GAMEPLAY),
            ("hook", GeneType.HOOK),
            ("theme", GeneType.VISUAL),
            ("visual", GeneType.VISUAL),
            ("reward", GeneType.REWARD),
            ("character", GeneType.CHARACTER),
            ("retention", GeneType.REWARD),
            ("monetization", GeneType.PLATFORM),
            ("pace", GeneType.PACING),
        ]

        seen_types = set()
        for key, gene_type in gene_mappings:
            if gene_type in seen_types:
                continue
            value = genes_data.get(key, "")
            if value:
                gene_list.append(Gene(
                    gene_type=gene_type,
                    value=str(value),
                    mutation_pool=[str(value)],
                    confidence=0.6,
                    source=f"creative_analysis:{key}",
                ))
                seen_types.add(gene_type)

        genome = Genome(
            name=idea.title or "analyzed_idea",
            generation=0,
            genes={g.gene_type.value: g for g in gene_list},
            metadata={
                "idea_id": idea.idea_id,
                "source": "creative_analysis_engine",
                "confidence": genes_data.get("confidence", 0.5),
            },
        )
        return genome
