"""E2/E3: Creative Scoring Engine — 5-component 100-point model.

Upgrades OpportunityRanker with the PRD's full 100-point scoring:

  Market Score:        30 pts — market heat, download trends, ad volume
  Creative Score:      25 pts — ad expressiveness, hook potential, CTR prediction
  Build Score:         20 pts — development cost, feasibility
  Monetization Score:  15 pts — IAA/IAP potential, revenue model fit
  Evolution Score:     10 pts — mutation space, combo potential
  ─────────────────────────────────
  TOTAL:              100 pts

Output: CreativeScore with component breakdown + recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class BuildAction(Enum):
    """What to do with a scored opportunity."""
    BUILD = "build"        # Score >= 80
    PROTOTYPE = "prototype"  # Score 60-79
    WATCH = "watch"        # Score 40-59
    IGNORE = "ignore"      # Score < 40


@dataclass
class CreativeScore:
    """Full 100-point creative opportunity score."""
    opportunity_name: str = ""
    total: float = 0.0
    # Components
    market_score: float = 0.0    # /30
    creative_score: float = 0.0  # /25
    build_score: float = 0.0     # /20
    monetization_score: float = 0.0  # /15
    evolution_score: float = 0.0  # /10
    # Meta
    confidence: float = 0.5
    action: BuildAction = BuildAction.WATCH
    justification: str = ""
    risks: list[str] = field(default_factory=list)
    advantages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_name": self.opportunity_name,
            "total": round(self.total, 1),
            "components": {
                "market_score": round(self.market_score, 1),
                "creative_score": round(self.creative_score, 1),
                "build_score": round(self.build_score, 1),
                "monetization_score": round(self.monetization_score, 1),
                "evolution_score": round(self.evolution_score, 1),
            },
            "confidence": round(self.confidence, 2),
            "action": self.action.value,
            "justification": self.justification,
            "risks": self.risks,
            "advantages": self.advantages,
        }


class CreativeScoringEngine:
    """Score any creative opportunity using the 5-component model.

    Usage:
        engine = CreativeScoringEngine()
        score = engine.score_from_text("Sort + Simulation + Collection")
        print(f"{score.total}/100 → {score.action.value}")
    """

    def __init__(self) -> None:
        pass

    # ── Scoring Methods ─────────────────────────────────────

    def score_from_analysis(self, analysis: dict[str, Any]) -> CreativeScore:
        """Score from a CreativeAnalysisEngine analysis result."""
        genes = analysis.get("genes", {})
        confidence = analysis.get("confidence", 0.5)
        name = analysis.get("idea_type", "") or analysis.get("category", "opportunity")

        market = self._score_market(genes)
        creative = self._score_creative(genes, analysis.get("url_type", ""))
        build = self._score_build(genes)
        monetization = self._score_monetization(genes)
        evolution = self._score_evolution(genes)

        total = market + creative + build + monetization + evolution
        action = self._decide(total)
        justification = self._justify(market, creative, build, monetization, evolution, genes)
        adv, risks = self._extract_adv_risks(genes)

        return CreativeScore(
            opportunity_name=name,
            total=total,
            market_score=market, creative_score=creative,
            build_score=build, monetization_score=monetization,
            evolution_score=evolution,
            confidence=confidence,
            action=action,
            justification=justification,
            advantages=adv,
            risks=risks,
        )

    def score_from_text(self, text: str) -> CreativeScore:
        """Quick score from free text description."""
        from market_ops.creative_brain_ui.creative_analysis_engine import CreativeAnalysisEngine

        engine = CreativeAnalysisEngine()
        analysis = engine.analyze_text(text)
        return self.score_from_analysis(analysis)

    def score_from_idea(self, idea: Any) -> CreativeScore:
        """Score from a HumanIdea."""
        return self.score_from_text(idea.title + ". " + idea.description)

    # ── Component Scorers ───────────────────────────────────

    @staticmethod
    def _score_market(genes: dict[str, str]) -> float:
        """Score 0-30: market heat."""
        score = 15.0  # baseline
        core = genes.get("core_loop", "")
        if core in ["merge", "sort"]:
            score += 8  # hot genres
        elif core in ["puzzle", "simulation"]:
            score += 5
        if genes.get("hook") in ["rescue", "reward"]:
            score += 4
        return min(30, score)

    @staticmethod
    def _score_creative(genes: dict[str, str], url_type: str = "") -> float:
        """Score 0-25: ad expressiveness."""
        score = 12.0
        if genes.get("hook") == "rescue":
            score += 5  # rescue hooks convert well
        elif genes.get("hook") == "mess_to_clean":
            score += 4
        if genes.get("visual") in ["3d_cartoon", "bright"]:
            score += 3
        if genes.get("character"):
            score += 3
        if url_type == "tiktok":
            score += 2  # trending on social
        return min(25, score)

    @staticmethod
    def _score_build(genes: dict[str, str]) -> float:
        """Score 0-20: development feasibility (higher = easier)."""
        score = 12.0
        core = genes.get("core_loop", "")
        if core in ["merge", "sort"]:
            score += 4  # well-understood mechanics
        if genes.get("monetization") == "IAA":
            score += 2  # simpler to implement
        if not genes.get("character"):
            score += 1  # no character = less art work
        return min(20, score)

    @staticmethod
    def _score_monetization(genes: dict[str, str]) -> float:
        """Score 0-15: IAA potential."""
        score = 8.0
        monet_type = genes.get("monetization", "IAA")
        if monet_type == "IAA":
            score += 3  # proven for casual
        elif monet_type == "battle_pass":
            score += 5  # high ARPU
        if genes.get("reward") in ["collection", "evolution"]:
            score += 2  # retention driver
        return min(15, score)

    @staticmethod
    def _score_evolution(genes: dict[str, str]) -> float:
        """Score 0-10: mutation/combo potential."""
        score = 5.0
        gene_count = len(genes)
        if gene_count >= 5:
            score += 3  # more genes = more mutation surface
        if genes.get("core_loop") in ["merge", "sort", "puzzle"]:
            score += 2  # well-understood mutation space
        return min(10, score)

    # ── Decision + Justification ────────────────────────────

    @staticmethod
    def _decide(total: float) -> BuildAction:
        if total >= 80:
            return BuildAction.BUILD
        elif total >= 60:
            return BuildAction.PROTOTYPE
        elif total >= 40:
            return BuildAction.WATCH
        return BuildAction.IGNORE

    @staticmethod
    def _justify(
        market: float, creative: float, build: float,
        monetization: float, evolution: float, genes: dict[str, str],
    ) -> str:
        parts = []
        max_comp = max(market, creative, build, monetization, evolution)
        if market == max_comp:
            parts.append("Strong market demand")
        if creative == max_comp:
            parts.append("High ad expressiveness")
        if build == max_comp:
            parts.append("Low development cost")
        if monetization == max_comp:
            parts.append("Strong monetization fit")
        if evolution == max_comp:
            parts.append("High mutation potential")
        return " + ".join(parts) if parts else "Balanced opportunity"

    @staticmethod
    def _extract_adv_risks(genes: dict[str, str]) -> tuple[list[str], list[str]]:
        advantages = []
        risks = []
        if genes.get("core_loop") in ["merge", "sort"]:
            advantages.append("Proven core loop with established UA channels")
        if genes.get("hook") == "rescue":
            advantages.append("Rescue hook has high CTR in current market")
        if not genes.get("reward"):
            risks.append("No clear reward loop → potential retention issue")
        if not genes.get("character"):
            risks.append("Missing character = weaker emotional engagement")
        return advantages, risks
