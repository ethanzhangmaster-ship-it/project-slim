"""V4.2 Winner Analyzer — explains WHY a creative is a winner.

Not just "ROAS > 0.5 → winner". Analyzes:
  - Which DNA dimensions contributed most to success?
  - How does this creative compare to historical winners?
  - What is the replicability score (can this pattern be repeated)?
  - What are the key success factors ranked by impact?

Usage:
    analyzer = WinnerAnalyzer(retriever, pattern_miner)
    analysis = analyzer.analyze("c_0001")
    # analysis.key_factors = [
    #   {"dimension": "character", "value": "dragon", "contribution": 0.35},
    #   {"dimension": "hook", "value": "collection", "contribution": 0.28},
    # ]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactorContribution:
    dimension: str = ""
    value: str = ""
    contribution: float = 0.0  # [0, 1] normalized contribution
    baseline: float = 0.0
    with_factor: float = 0.0
    lift_pct: float = 0.0
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "contribution": round(self.contribution, 3),
            "baseline": round(self.baseline, 4),
            "with_factor": round(self.with_factor, 4),
            "lift_pct": round(self.lift_pct, 1),
            "evidence_count": self.evidence_count,
        }


@dataclass
class WinnerAnalysis:
    creative_id: str = ""
    is_winner: bool = False
    overall_score: float = 0.0
    key_factors: list[FactorContribution] = field(default_factory=list)
    similar_winners: list[dict[str, Any]] = field(default_factory=list)
    replicability_score: float = 0.0
    explanation: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "is_winner": self.is_winner,
            "overall_score": round(self.overall_score, 3),
            "key_factors": [f.to_dict() for f in self.key_factors],
            "similar_winners_count": len(self.similar_winners),
            "replicability_score": round(self.replicability_score, 3),
            "explanation": self.explanation,
            "recommendations": self.recommendations,
        }


class WinnerAnalyzer:
    """Analyzes WHY a creative is a winner.

    Uses:
      - Creative Retriever (find similar winners)
      - Combinatorial Pattern Miner (find contributing patterns)
      - Performance data (quantify impact)
    """

    # All DNA dimensions to analyze
    DNA_DIMENSIONS = [
        "character", "reward", "hook", "gameplay", "camera",
        "lighting", "palette", "style", "emotion", "brand",
        "composition", "typography", "background",
    ]

    def __init__(self, retriever=None, pattern_miner=None) -> None:
        self._retriever = retriever
        self._pattern_miner = pattern_miner

    def analyze(self, creative_id: str, creative_data: dict[str, Any] | None = None,
                dna_data: dict[str, Any] | None = None,
                performance: dict[str, Any] | None = None) -> WinnerAnalysis:
        """Analyze why a creative is a winner (or not)."""
        dna = dna_data or {}
        perf = performance or {}

        roas = perf.get("roas_d7", 0)
        ctr = perf.get("ctr", 0)
        is_winner = roas >= 0.5

        # 1. Find similar winners for comparison
        similar = self._find_similar_winners(dna) if self._retriever else []

        # 2. Analyze each DNA dimension's contribution
        key_factors = self._analyze_factors(dna, perf, similar)

        # 3. Compute replicability score
        replicability = self._compute_replicability(dna, similar, key_factors)

        # 4. Generate explanation
        explanation = self._generate_explanation(is_winner, key_factors, roas, ctr)

        # 5. Generate recommendations
        recommendations = self._generate_recommendations(is_winner, key_factors, dna)

        return WinnerAnalysis(
            creative_id=creative_id,
            is_winner=is_winner,
            overall_score=self._compute_overall_score(perf),
            key_factors=key_factors,
            similar_winners=similar[:5],
            replicability_score=replicability,
            explanation=explanation,
            recommendations=recommendations,
        )

    def _analyze_factors(self, dna: dict[str, Any], perf: dict[str, Any],
                         similar: list[dict[str, Any]]) -> list[FactorContribution]:
        """Analyze each DNA dimension's contribution to performance."""
        factors = []
        roas = perf.get("roas_d7", 0.5)

        for dim in self.DNA_DIMENSIONS:
            value = dna.get(dim, "")
            if not value:
                continue

            # Compute baseline: average ROAS of similar creatives WITHOUT this factor
            without_factor = [
                s for s in similar
                if s.get("dna", {}).get(dim) != value
            ]
            baseline = (
                sum(s.get("performance", {}).get("roas_d7", 0) for s in without_factor)
                / max(len(without_factor), 1)
            ) if without_factor else 0.5

            # Compute with-factor: average ROAS of creatives WITH this factor
            with_factor_creatives = [
                s for s in similar
                if s.get("dna", {}).get(dim) == value
            ]
            with_factor_avg = (
                sum(s.get("performance", {}).get("roas_d7", 0) for s in with_factor_creatives)
                / max(len(with_factor_creatives), 1)
            ) if with_factor_creatives else roas

            # Lift
            lift = ((with_factor_avg - baseline) / max(baseline, 0.001)) * 100

            # Contribution: how much this factor explains the performance
            contribution = abs(lift) / 100
            contribution = min(contribution, 1.0)

            factors.append(FactorContribution(
                dimension=dim,
                value=str(value),
                contribution=contribution,
                baseline=baseline,
                with_factor=with_factor_avg,
                lift_pct=lift,
                evidence_count=len(with_factor_creatives),
            ))

        # Sort by contribution (absolute lift)
        factors.sort(key=lambda f: abs(f.lift_pct), reverse=True)
        return factors[:10]

    def _find_similar_winners(self, dna: dict[str, Any]) -> list[dict[str, Any]]:
        """Find similar winning creatives."""
        if not self._retriever:
            return []
        query = " ".join(f"{k}:{v}" for k, v in dna.items() if v)
        results = self._retriever.retrieve(query, top_k=30, min_roas=0.5)
        return [
            {
                "creative_id": r.creative_id,
                "dna": r.dna,
                "performance": r.performance,
                "score": r.score,
            }
            for r in results
        ]

    def _compute_replicability(self, dna: dict[str, Any],
                                similar: list[dict[str, Any]],
                                factors: list[FactorContribution]) -> float:
        """Compute how replicable this winning pattern is.

        High replicability = many similar winners exist with the same DNA.
        """
        if not similar or not factors:
            return 0.0

        # Factor 1: How many similar winners exist?
        similarity_score = min(len(similar) / 10, 1.0)

        # Factor 2: How consistent are the top factors?
        top_factors = factors[:3]
        consistency = sum(f.evidence_count / max(len(similar), 1) for f in top_factors) / max(len(top_factors), 1)

        # Factor 3: How strong is the lift?
        lift_score = sum(min(abs(f.lift_pct) / 50, 1.0) for f in top_factors) / max(len(top_factors), 1)

        return (similarity_score * 0.3 + consistency * 0.4 + lift_score * 0.3)

    def _generate_explanation(self, is_winner: bool,
                               factors: list[FactorContribution],
                               roas: float, ctr: float) -> str:
        """Generate human-readable explanation."""
        if not factors:
            return "Insufficient data to analyze."

        top = factors[:3]

        if is_winner:
            lines = [
                f"This creative is a WINNER (ROAS: {roas:.2f}, CTR: {ctr:.1f}%).",
                "",
                "Key success factors:",
            ]
            for i, f in enumerate(top):
                lines.append(
                    f"  {i+1}. {f.dimension}={f.value} "
                    f"(lift: {f.lift_pct:+.1f}%, evidence: {f.evidence_count} creatives)"
                )

            if top[0].lift_pct > 20:
                lines.append(f"\n  The {top[0].dimension} '{top[0].value}' is the strongest driver.")
        else:
            lines = [
                f"This creative is NOT a winner (ROAS: {roas:.2f}, CTR: {ctr:.1f}%).",
                "",
                "Issues identified:",
            ]
            for i, f in enumerate(top):
                if f.lift_pct < 0:
                    lines.append(
                        f"  {i+1}. {f.dimension}={f.value} "
                        f"(negative impact: {f.lift_pct:+.1f}%)"
                    )

        return "\n".join(lines)

    def _generate_recommendations(self, is_winner: bool,
                                   factors: list[FactorContribution],
                                   dna: dict[str, Any]) -> list[str]:
        """Generate actionable recommendations."""
        recs = []

        if is_winner:
            top = factors[:3]
            recs.append(
                f"Scale this pattern: {', '.join(f'{f.dimension}={f.value}' for f in top)}"
            )
            recs.append("Generate variants with same core DNA, different camera/lighting")
            recs.append("Test this pattern in other countries with similar audience profiles")
        else:
            # Find negative factors
            negative = [f for f in factors if f.lift_pct < -5]
            for f in negative[:3]:
                recs.append(
                    f"Replace {f.dimension}='{f.value}' — "
                    f"negative impact of {f.lift_pct:+.1f}%"
                )

            if not negative:
                recs.append("No clear negative factors — consider testing different audience or platform")

        return recs

    def _compute_overall_score(self, perf: dict[str, Any]) -> float:
        """Compute overall performance score."""
        roas = perf.get("roas_d7", 0)
        ctr = perf.get("ctr", 0)
        ipm = perf.get("ipm", 0)

        roas_score = min(roas / 2.0, 1.0)
        ctr_score = min(ctr / 5.0, 1.0)
        ipm_score = min(ipm / 50.0, 1.0)

        return roas_score * 0.5 + ctr_score * 0.3 + ipm_score * 0.2