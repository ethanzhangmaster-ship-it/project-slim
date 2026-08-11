"""
E16.6.8 — ASO Creative Generator Agent.

Main pipeline: ASO Insight → Creative Brief → Generate → Vision Evaluate
→ Rank → Experiment → Learn

This is the bridge between ASO Intelligence and the E11 Creative Evolution
Engine — forming a unified "ads + store" Creative Intelligence Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.aso_intelligence.creative_generator.models import (
    ASOCreativeBrief,
    ASOCreativeGenome,
    CreativeCandidate,
    ASOCreativeReport,
    BriefObjective,
    StoreAssetType,
)
from src.aso_intelligence.creative_generator.brief_generator import (
    ASOBriefGenerator,
)
from src.aso_intelligence.creative_generator.asset_generator import (
    ASOAssetGenerator,
)
from src.aso_intelligence.creative_generator.vision_evaluator import (
    ASOVisionEvaluator,
)
from src.aso_intelligence.creative_generator.ranking import (
    CreativeRankingEngine,
)
from src.aso_intelligence.creative_generator.experiment_bridge import (
    CreativeExperimentBridge,
)
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperiment,
    ASOExperimentResult,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOCreativeGeneratorAgent:
    """AI ASO Creative Director — generates, evaluates, and experiments
    with store creative assets.

    Typical usage:

        agent = ASOCreativeGeneratorAgent.build(store)
        report = agent.run(
            game_id="merge_witch",
            source_insight="screenshot_hook_weak",
            source_data={"hook_score": 0.42},
            count=20,
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        brief_gen: Optional[ASOBriefGenerator] = None,
        asset_gen: Optional[ASOAssetGenerator] = None,
        vision: Optional[ASOVisionEvaluator] = None,
        ranking: Optional[CreativeRankingEngine] = None,
        bridge: Optional[CreativeExperimentBridge] = None,
        store: Optional[ASOExperimentStore] = None,
    ):
        self.brief_gen = brief_gen or ASOBriefGenerator()
        self.asset_gen = asset_gen or ASOAssetGenerator()
        self.vision = vision or ASOVisionEvaluator()
        self.ranking = ranking or CreativeRankingEngine()
        self.bridge = bridge or CreativeExperimentBridge(store)
        self.store = store

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOCreativeGeneratorAgent":
        return cls(
            bridge=CreativeExperimentBridge(store),
            store=store,
        )

    # ------------------------------------------------------------------ #
    def analyze_aso_insight(
        self,
        source_insight: str,
        source_data: dict = None,
    ) -> ASOCreativeBrief:
        """Step 1: Convert ASO insight → creative brief."""
        return self.brief_gen.generate(
            game_id="",
            source_insight=source_insight,
            source_data=source_data or {},
        )

    # ------------------------------------------------------------------ #
    def generate_brief(
        self,
        game_id: str,
        source_insight: str,
        source_data: dict = None,
        country: str = "US",
    ) -> Optional[ASOCreativeBrief]:
        """Step 1 (public): Generate a complete brief for a game."""
        return self.brief_gen.generate(
            game_id=game_id,
            source_insight=source_insight,
            source_data=source_data or {},
            country=country,
        )

    # ------------------------------------------------------------------ #
    def generate_assets(
        self,
        brief: ASOCreativeBrief,
        genome: ASOCreativeGenome,
        count: int = 5,
        dry_run: bool = True,
    ) -> List[CreativeCandidate]:
        """Step 2: Generate creative variants."""
        return self.asset_gen.generate_variants(
            brief, genome, count=count, dry_run=dry_run,
        )

    # ------------------------------------------------------------------ #
    def evaluate_vision(
        self, candidates: List[CreativeCandidate]
    ) -> List[CreativeCandidate]:
        """Step 3: Evaluate all candidates on vision + compliance."""
        return self.vision.evaluate_batch(candidates)

    # ------------------------------------------------------------------ #
    def rank_candidates(
        self,
        candidates: List[CreativeCandidate],
        revenue_quality: float = 1.0,
    ) -> List[CreativeCandidate]:
        """Step 4: Rank and select top candidate."""
        return self.ranking.select_top(
            candidates, k=1, revenue_quality=revenue_quality,
        )

    # ------------------------------------------------------------------ #
    def bridge_experiment(
        self,
        game_id: str,
        top_candidate: CreativeCandidate,
        category: str,
        condition: str,
    ) -> Optional[ASOExperiment]:
        """Step 5: Create experiment for top candidate."""
        return self.bridge.create_experiment(
            game_id=game_id,
            candidate=top_candidate,
            category=category,
            condition=condition,
        )

    # ------------------------------------------------------------------ #
    def learn(
        self,
        experiment: ASOExperiment,
        result: ASOExperimentResult,
        candidate: CreativeCandidate,
    ) -> None:
        """Step 6: Learn from experiment result."""
        self.bridge.learn_pattern(experiment, result, candidate)

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        source_insight: str,
        *,
        source_data: dict = None,
        genome: Optional[ASOCreativeGenome] = None,
        count: int = 5,
        dry_run: bool = True,
        country: str = "US",
        category: str = "unknown",
        revenue_quality: float = 1.0,
        # Optional: record experiment results
        experiment_result_data: dict = None,
    ) -> ASOCreativeReport:
        """Run the full creative generation cycle.

        1. Analyze ASO insight → Creative Brief
        2. Generate creative variants from brief + genome
        3. Evaluate vision quality + store compliance
        4. Rank candidates by composite score
        5. Bridge to experiment (if store configured)
        6. Learn from results (if result data provided)
        """
        # Step 1: Brief
        brief = self.generate_brief(
            game_id, source_insight, source_data, country,
        )
        if brief is None:
            return ASOCreativeReport(
                game_id=game_id, date=_today_iso(),
            )

        # Step 1b: Genome (default if not provided)
        if genome is None:
            genome = ASOCreativeGenome.merge_genome_default(category)

        # Step 2: Generate
        candidates = self.generate_assets(brief, genome, count, dry_run)

        # Step 3: Evaluate
        candidates = self.evaluate_vision(candidates)

        # Step 4: Rank
        top = self.rank_candidates(candidates, revenue_quality)

        # Step 5: Experiment
        experiments_created = 0
        if top and self.store:
            exp = self.bridge_experiment(
                game_id, top[0], category,
                condition=f"{brief.asset_type.value}_{source_insight}",
            )
            if exp:
                experiments_created = 1

        # Step 6: Learn (if result data provided)
        patterns_learned = 0
        if experiment_result_data and top and self.store:
            # Simulated learning: create a result from the data
            exp = ASOExperiment(
                experiment_id="simulated",
                game_id=game_id,
                platform="google_play",
                category=category,
                condition=f"{source_insight}_result",
                action_type=_asset_to_action(brief.asset_type),
                before_asset="current",
                after_asset=top[0].variant_label,
                start_date=_today_iso(),
            )
            result = ASOExperimentResult(
                experiment_id="simulated",
                before=experiment_result_data.get("before", {}),
                after=experiment_result_data.get("after", {}),
                confidence=experiment_result_data.get("confidence", 0.85),
            )
            pattern = self.bridge.learn_pattern(exp, result, top[0])
            if pattern:
                patterns_learned = 1

        # Report
        report = ASOCreativeReport(
            game_id=game_id,
            date=_today_iso(),
            brief=brief,
            candidates=candidates,
            top_candidate=top[0] if top else None,
            experiments_created=experiments_created,
            patterns_learned=patterns_learned,
        )
        return report


def _asset_to_action(asset_type: StoreAssetType):
    from src.aso_intelligence.experiment_memory.experiment_models import (
        ASOExperimentAction,
    )
    mapping = {
        StoreAssetType.ICON: ASOExperimentAction.UPDATE_ICON,
        StoreAssetType.SCREENSHOT: ASOExperimentAction.UPDATE_SCREENSHOT,
        StoreAssetType.FEATURE_GRAPHIC: ASOExperimentAction.UPDATE_SCREENSHOT,
    }
    return mapping.get(asset_type, ASOExperimentAction.UPDATE_SCREENSHOT)


__all__ = ["ASOCreativeGeneratorAgent"]
