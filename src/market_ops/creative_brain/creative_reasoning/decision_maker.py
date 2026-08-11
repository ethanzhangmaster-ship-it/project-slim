"""V4.2 Decision Maker — final decision output with risk assessment.

Aggregates all reasoning modules into a single decision:
  - Winner analysis (why?)
  - Cross-country adaptation (where?)
  - Pattern classification (what pattern?)
  - Constraint optimization (what to generate?)

Produces:
  - Decision type (SCALE / TEST / ADAPT / AVOID)
  - Risk assessment
  - Actionable next steps
  - Explanation chain
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    SCALE = "scale"        # Proven winner, increase budget
    TEST = "test"          # Promising, test with budget
    ADAPT = "adapt"        # Adapt for new market
    AVOID = "avoid"        # Proven loser, don't invest
    EXPLORE = "explore"    # Novel, worth small test
    PAUSE = "pause"        # Needs more data


@dataclass
class Decision:
    decision_type: DecisionType = DecisionType.TEST
    creative_id: str = ""
    confidence: float = 0.0
    risk_level: str = "medium"
    expected_roas_range: tuple[float, float] = (0.0, 0.0)
    rationale: str = ""
    next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type.value,
            "creative_id": self.creative_id,
            "confidence": round(self.confidence, 3),
            "risk_level": self.risk_level,
            "expected_roas_range": [
                round(self.expected_roas_range[0], 3),
                round(self.expected_roas_range[1], 3),
            ],
            "rationale": self.rationale,
            "next_steps": self.next_steps,
            "warnings": self.warnings,
            "evidence": self.evidence,
        }


class DecisionMaker:
    """Makes the final creative decision by aggregating all reasoning.

    Decision logic:
      - Winner + high replicability → SCALE
      - Winner + low replicability → TEST
      - Pattern match + winner pattern → TEST
      - Novel + high confidence → EXPLORE
      - Loser pattern → AVOID
      - Cross-country + high transferability → ADAPT
    """

    def __init__(self) -> None:
        pass

    def decide(self, creative_id: str,
               winner_analysis=None,
               pattern_classification=None,
               cross_country_analysis=None,
               optimization_result=None) -> Decision:
        """Make a decision by aggregating all reasoning results."""
        evidence = {}
        rationale_parts = []
        next_steps = []
        warnings = []

        # 1. Evaluate winner analysis
        if winner_analysis:
            evidence["winner"] = {
                "is_winner": winner_analysis.is_winner,
                "replicability": winner_analysis.replicability_score,
                "key_factors": [f"{f.dimension}={f.value}" for f in winner_analysis.key_factors[:3]],
            }
            if winner_analysis.is_winner:
                rationale_parts.append("Creative is a proven winner")
                if winner_analysis.replicability_score > 0.6:
                    rationale_parts.append(
                        f"High replicability ({winner_analysis.replicability_score:.0%})"
                    )
                next_steps.extend(winner_analysis.recommendations[:2])

        # 2. Evaluate pattern classification
        if pattern_classification:
            evidence["pattern"] = {
                "best_match": pattern_classification.best_match.to_dict() if pattern_classification.best_match else None,
                "novelty": pattern_classification.novelty_score,
                "worth_trying": pattern_classification.worth_trying,
            }

        # 3. Evaluate cross-country
        if cross_country_analysis:
            evidence["cross_country"] = {
                "transferability": cross_country_analysis.transferability_score,
                "risk": cross_country_analysis.risk_level,
            }

        # 4. Determine decision type
        decision_type = self._determine_type(
            winner_analysis, pattern_classification, cross_country_analysis
        )

        # 5. Confidence
        confidence = self._compute_confidence(
            winner_analysis, pattern_classification
        )

        # 6. Risk level
        risk = self._compute_risk(decision_type, confidence)

        # 7. Expected ROAS range
        roas_range = self._estimate_roas_range(
            winner_analysis, pattern_classification
        )

        # 8. Build final next steps
        if decision_type == DecisionType.SCALE:
            next_steps.insert(0, "Increase budget by 50-100%")
            next_steps.append("Generate 10+ variants with same core DNA")
        elif decision_type == DecisionType.TEST:
            next_steps.insert(0, "Allocate test budget ($200-500)")
            next_steps.append("Generate 3-5 variants")
        elif decision_type == DecisionType.ADAPT:
            next_steps.insert(0, "Adapt DNA for target country")
            next_steps.append("Run small-budget test in new market")
        elif decision_type == DecisionType.EXPLORE:
            next_steps.insert(0, "Allocate small exploration budget ($100-200)")
            next_steps.append("Test 2-3 novel combinations")
        elif decision_type == DecisionType.AVOID:
            warnings.append("This pattern consistently underperforms")
            next_steps.append("Analyze failure reasons before retrying")

        return Decision(
            decision_type=decision_type,
            creative_id=creative_id,
            confidence=confidence,
            risk_level=risk,
            expected_roas_range=roas_range,
            rationale=". ".join(rationale_parts) if rationale_parts else "Insufficient data",
            next_steps=next_steps,
            warnings=warnings,
            evidence=evidence,
        )

    def _determine_type(self, winner_analysis,
                        pattern_classification,
                        cross_country_analysis) -> DecisionType:
        """Determine the decision type."""
        # Cross-country adaptation
        if cross_country_analysis and cross_country_analysis.transferability_score > 0.4:
            return DecisionType.ADAPT

        # Winner
        if winner_analysis and winner_analysis.is_winner:
            if winner_analysis.replicability_score > 0.6:
                return DecisionType.SCALE
            return DecisionType.TEST

        # Not a winner — check pattern
        if pattern_classification:
            if pattern_classification.worth_trying:
                if pattern_classification.novelty_score > 0.7:
                    return DecisionType.EXPLORE
                return DecisionType.TEST
            return DecisionType.AVOID

        # No data at all
        if winner_analysis and not winner_analysis.is_winner:
            return DecisionType.AVOID

        return DecisionType.TEST

    def _compute_confidence(self, winner_analysis,
                            pattern_classification) -> float:
        """Compute overall decision confidence."""
        confidences = []

        if winner_analysis:
            confidences.append(winner_analysis.replicability_score * 0.5 + 0.3)

        if pattern_classification and pattern_classification.best_match:
            confidences.append(pattern_classification.best_match.confidence)

        if not confidences:
            return 0.3

        return sum(confidences) / len(confidences)

    def _compute_risk(self, decision_type: DecisionType,
                      confidence: float) -> str:
        """Compute risk level."""
        if decision_type == DecisionType.SCALE and confidence > 0.7:
            return "low"
        if decision_type == DecisionType.AVOID:
            return "low"  # Avoiding risk is low risk
        if confidence < 0.4:
            return "high"
        return "medium"

    def _estimate_roas_range(self, winner_analysis,
                              pattern_classification) -> tuple[float, float]:
        """Estimate expected ROAS range."""
        if pattern_classification and pattern_classification.best_match:
            best = pattern_classification.best_match
            er = best.expected_range.get("roas_d7", (0.0, 0.0))
            return (er[0], er[1])

        if winner_analysis and winner_analysis.is_winner:
            return (0.6, 1.2)

        return (0.2, 0.5)