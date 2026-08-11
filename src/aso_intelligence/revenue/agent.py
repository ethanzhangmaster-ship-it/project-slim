"""
E16.6.6 — ASO Revenue Attribution Agent.

The main orchestrator that runs the full revenue attribution pipeline:

    collect_aso_events()
        → join_adjust_revenue()
            → calculate_quality()
                → update_memory()
                    → generate_insights()
                        → ASORevenueReport
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.revenue.models import (
    ASOAcquisitionEvent,
    ASORevenueAttribution,
    ASOActionReward,
    KeywordValueScore,
    CountryRevenueAttribution,
    ASORevenueReport,
)
from src.aso_intelligence.revenue.attribution import ASORevenueAttributor
from src.aso_intelligence.revenue.quality import ASOUserQualityAnalyzer
from src.aso_intelligence.revenue.analyzer import ASORevenueAnalyzer
from src.aso_intelligence.revenue.reward import ASOActionRewarder
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASORevenueAgent:
    """Full revenue attribution pipeline for ASO.

    Typical usage:

        agent = ASORevenueAgent(store)
        report = agent.run(
            game_id="merge_witch",
            events=[...],
            keyword_data=[...],
            revenue_map={"US": 15000.0, "JP": 8000.0},
            payer_map={"US": 500, "JP": 200},
            experiment_results=[...],    # optional
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        store: Optional[ASOExperimentStore] = None,
        attributor: Optional[ASORevenueAttributor] = None,
        quality: Optional[ASOUserQualityAnalyzer] = None,
        analyzer: Optional[ASORevenueAnalyzer] = None,
        rewarder: Optional[ASOActionRewarder] = None,
    ):
        self.store = store
        self.attributor = attributor or ASORevenueAttributor()
        self.quality = quality or ASOUserQualityAnalyzer()
        self.analyzer = analyzer or ASORevenueAnalyzer(
            attributor=self.attributor, quality=self.quality
        )
        self.rewarder = rewarder

    # ------------------------------------------------------------------ #
    # Pipeline steps
    # ------------------------------------------------------------------ #
    def collect_aso_events(
        self,
        events: List[ASOAcquisitionEvent],
    ) -> List[ASOAcquisitionEvent]:
        """Step 1: Receive/source ASO acquisition events.

        Currently a pass-through; in production this would load from
        data/aso/acquisition.jsonl or an API connector.
        """
        return events

    def join_adjust_revenue(
        self,
        events: List[ASOAcquisitionEvent],
        revenue_map: Dict[str, float],
        payer_map: Dict[str, int],
    ) -> List[ASORevenueAttribution]:
        """Step 2: Join ASO events with Adjust revenue data.

        Returns per-country attributions.
        """
        return self.attributor.attribute_by_country(
            events, revenue_map, payer_map
        )

    def calculate_quality(
        self,
        attributions: List[ASORevenueAttribution],
    ) -> List[ASORevenueAttribution]:
        """Step 3: Tag each attribution with quality labels."""
        for attr in attributions:
            report = self.quality.evaluate(attr)
            # Quality label is available via report for external use
        # Return ranked by quality
        return self.quality.rank_by_quality(attributions)

    def update_memory(
        self,
        experiment_id: str,
        game_id: str,
        category: str,
        condition: str,
        action: str,
        before: ASORevenueAttribution,
        after: ASORevenueAttribution,
    ) -> Optional[ASOActionReward]:
        """Step 4: Evaluate experiment + persist revenue-adjusted pattern.

        Only runs if a ``rewarder`` (with ``store``) was provided.
        """
        if self.rewarder is None:
            return None
        return self.rewarder.evaluate_and_learn(
            experiment_id, game_id, category, condition,
            action, before, after,
        )

    def generate_insights(
        self,
        game_id: str,
        keyword_data: Optional[List[Dict[str, Any]]] = None,
        events: Optional[List[ASOAcquisitionEvent]] = None,
        revenue_map: Optional[Dict[str, float]] = None,
        payer_map: Optional[Dict[str, int]] = None,
        action_rewards: Optional[List[ASOActionReward]] = None,
    ) -> ASORevenueReport:
        """Step 5: Generate the full revenue attribution report."""
        keyword_scores: List[KeywordValueScore] = []
        if keyword_data:
            keyword_scores = self.analyzer.analyze_keywords(game_id, keyword_data)

        country_attributions: List[CountryRevenueAttribution] = []
        if events and revenue_map and payer_map:
            raw_attributions = self.attributor.attribute_by_country(
                events, revenue_map, payer_map
            )
            country_attributions = self.analyzer.analyze_countries(
                game_id, events, revenue_map, payer_map
            )

        report = self.analyzer.generate_report(
            game_id=game_id,
            date=_today_iso(),
            keyword_scores=keyword_scores,
            country_attributions=country_attributions,
            action_rewards=action_rewards or [],
        )
        return report

    # ------------------------------------------------------------------ #
    # Main run
    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        events: List[ASOAcquisitionEvent],
        keyword_data: Optional[List[Dict[str, Any]]] = None,
        revenue_map: Optional[Dict[str, float]] = None,
        payer_map: Optional[Dict[str, int]] = None,
        # Optional: evaluate one experiment
        experiment_id: str = "",
        category: str = "",
        condition: str = "",
        action: str = "",
        attribution_before: Optional[ASORevenueAttribution] = None,
        attribution_after: Optional[ASORevenueAttribution] = None,
    ) -> ASORevenueReport:
        """Run the full attribution pipeline for one game.

        1. Collect ASO events
        2. Join with Adjust revenue
        3. Calculate user quality
        4. (Optional) Evaluate experiment → persist revenue-adjusted pattern
        5. Generate revenue insights report
        """
        # Step 1
        events = self.collect_aso_events(events)

        # Step 2
        revenue_map = revenue_map or {}
        payer_map = payer_map or {}
        attributions = self.join_adjust_revenue(events, revenue_map, payer_map)

        # Step 3
        attributions = self.calculate_quality(attributions)

        # Step 4 (optional experiment evaluation)
        action_rewards: List[ASOActionReward] = []
        if (experiment_id and attribution_before and attribution_after
                and category and condition and action):
            reward = self.update_memory(
                experiment_id, game_id, category, condition,
                action, attribution_before, attribution_after,
            )
            if reward:
                action_rewards.append(reward)

        # Step 5
        report = self.generate_insights(
            game_id=game_id,
            keyword_data=keyword_data,
            events=events,
            revenue_map=revenue_map,
            payer_map=payer_map,
            action_rewards=action_rewards,
        )
        return report


__all__ = ["ASORevenueAgent"]
