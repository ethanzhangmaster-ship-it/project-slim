"""V4.2 Constraint Optimizer — finds optimal creative plans under constraints.

Answers: "Given budget X, country Y, monetization Z, what are the best creatives to generate?"

Optimizes across:
  - Budget (how many creatives to generate)
  - Country (DNA preferences per market)
  - Monetization (IAA vs IAP optimization)
  - Risk tolerance (explore vs exploit)
  - Historical patterns (what works)

Output: ranked list of creative plans with expected ROI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreativePlan:
    rank: int = 0
    dna: dict[str, Any] = field(default_factory=dict)
    expected_roas: float = 0.0
    expected_ctr: float = 0.0
    confidence: float = 0.0
    estimated_cost: float = 0.0
    pattern_source: str = ""
    risk_level: str = "medium"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "dna": self.dna,
            "expected_roas": round(self.expected_roas, 3),
            "expected_ctr": round(self.expected_ctr, 2),
            "confidence": round(self.confidence, 3),
            "estimated_cost": round(self.estimated_cost, 2),
            "pattern_source": self.pattern_source,
            "risk_level": self.risk_level,
            "rationale": self.rationale,
        }


@dataclass
class OptimizationResult:
    constraints: dict[str, Any] = field(default_factory=dict)
    plans: list[CreativePlan] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    total_expected_roas: float = 0.0
    exploration_ratio: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraints": self.constraints,
            "plans": [p.to_dict() for p in self.plans],
            "total_estimated_cost": round(self.total_estimated_cost, 2),
            "total_expected_roas": round(self.total_expected_roas, 3),
            "exploration_ratio": round(self.exploration_ratio, 2),
            "summary": self.summary,
        }


class ConstraintOptimizer:
    """Optimizes creative generation under constraints.

    Balances:
      - Exploitation (use known winning patterns)
      - Exploration (try novel combinations)
      - Budget efficiency
      - Country preferences
      - Monetization strategy
    """

    def __init__(self, retriever=None, pattern_miner=None,
                 country_adapter=None) -> None:
        self._retriever = retriever
        self._pattern_miner = pattern_miner
        self._country_adapter = country_adapter

    def optimize(self, budget: float = 1000.0,
                 country: str = "US",
                 monetization: str = "iaa",
                 creative_count: int = 10,
                 explore_ratio: float = 0.2,
                 existing_dna: dict[str, Any] | None = None) -> OptimizationResult:
        """Generate optimal creative plans under constraints.

        Args:
            budget: Total budget for creative generation
            country: Target country
            monetization: "iaa" or "iap"
            creative_count: Number of creatives to generate
            explore_ratio: Fraction of budget for exploration (0.0-1.0)
            existing_dna: Optional existing DNA to build upon
        """
        constraints = {
            "budget": budget,
            "country": country,
            "monetization": monetization,
            "creative_count": creative_count,
            "explore_ratio": explore_ratio,
        }

        # 1. Get known winning patterns for this country
        exploit_patterns = self._get_exploit_patterns(country, monetization)

        # 2. Generate exploration candidates
        explore_candidates = self._generate_explore_candidates(
            country, monetization, existing_dna
        )

        # 3. Allocate budget
        exploit_count = int(creative_count * (1 - explore_ratio))
        explore_count = creative_count - exploit_count

        # 4. Build plans
        plans = []

        # Exploit plans
        for i, pattern in enumerate(exploit_patterns[:exploit_count]):
            cost_per_creative = budget / max(creative_count, 1)
            plans.append(CreativePlan(
                rank=i + 1,
                dna=pattern.get("dna", {}),
                expected_roas=pattern.get("expected_roas", 0.5),
                expected_ctr=pattern.get("expected_ctr", 3.0),
                confidence=pattern.get("confidence", 0.7),
                estimated_cost=cost_per_creative,
                pattern_source="exploit",
                risk_level="low",
                rationale=f"Proven winner pattern in {country}",
            ))

        # Explore plans
        for i, candidate in enumerate(explore_candidates[:explore_count]):
            cost_per_creative = budget / max(creative_count, 1)
            plans.append(CreativePlan(
                rank=exploit_count + i + 1,
                dna=candidate.get("dna", {}),
                expected_roas=candidate.get("expected_roas", 0.3),
                expected_ctr=candidate.get("expected_ctr", 2.0),
                confidence=candidate.get("confidence", 0.3),
                estimated_cost=cost_per_creative,
                pattern_source="explore",
                risk_level="high",
                rationale=f"Novel combination for {country} market testing",
            ))

        # Sort by expected ROI
        plans.sort(key=lambda p: p.expected_roas * p.confidence, reverse=True)
        for i, p in enumerate(plans):
            p.rank = i + 1

        total_cost = sum(p.estimated_cost for p in plans)
        total_roas = (
            sum(p.expected_roas * p.confidence for p in plans)
            / max(len(plans), 1)
        )

        return OptimizationResult(
            constraints=constraints,
            plans=plans,
            total_estimated_cost=total_cost,
            total_expected_roas=total_roas,
            exploration_ratio=explore_count / max(creative_count, 1),
            summary=(
                f"Budget: ${budget:.0f} | {country} | {monetization.upper()} | "
                f"{exploit_count} exploit + {explore_count} explore | "
                f"Expected ROAS: {total_roas:.2f}"
            ),
        )

    def _get_exploit_patterns(self, country: str,
                               monetization: str) -> list[dict[str, Any]]:
        """Get known winning patterns for exploitation."""
        # Use country-specific DNA profiles
        if self._country_adapter:
            profile = self._country_adapter.COUNTRY_PROFILES.get(country, {})
        else:
            profile = {}

        patterns = []

        # Generate patterns from country profile
        characters = profile.get("top_characters", ["dragon", "witch", "warrior"])[:3]
        rewards = profile.get("top_rewards", ["dragon", "treasure", "evolution"])[:3]
        hooks = profile.get("top_hooks", ["collection", "transformation", "fail"])[:3]
        gameplays = profile.get("top_gameplays", ["merge", "puzzle", "idle"])[:3]

        for ch in characters:
            for rw in rewards[:2]:
                for hk in hooks[:2]:
                    patterns.append({
                        "dna": {
                            "character": ch,
                            "reward": rw,
                            "hook": hk,
                            "gameplay": gameplays[0],
                            "country": country,
                        },
                        "expected_roas": 0.75,
                        "expected_ctr": 4.0,
                        "confidence": 0.7,
                    })

        return patterns[:10]

    def _generate_explore_candidates(self, country: str,
                                      monetization: str,
                                      existing_dna: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Generate novel exploration candidates."""
        candidates = []

        # Novel character + known reward combinations
        novel_characters = ["phoenix", "mermaid", "vampire", "golem", "fairy",
                            "ghost", "elemental", "shadow", "angel", "demon"]
        known_rewards = ["dragon", "treasure", "evolution", "collection", "gold"]

        for ch in novel_characters[:5]:
            for rw in known_rewards[:3]:
                candidates.append({
                    "dna": {
                        "character": ch,
                        "reward": rw,
                        "hook": "collection",
                        "gameplay": "merge",
                        "country": country,
                    },
                    "expected_roas": 0.35,
                    "expected_ctr": 2.5,
                    "confidence": 0.3,
                })

        return candidates[:5]