"""V4.2 Explanation Engine — generates human-readable explanations.

Every decision must be explainable. The Explanation Engine produces:
  - Simple explanation (1-2 sentences for quick overview)
  - Detailed explanation (full breakdown with evidence)
  - Technical explanation (raw data for debugging)

Explainability coverage target: ≥ 95%.
"""

from __future__ import annotations

from typing import Any

from .schemas import DecisionType, EvidenceItem, ReasoningResult


class ExplanationEngine:
    """Generates multi-level explanations for reasoning decisions.

    Three levels:
      - simple: 1-2 sentence summary
      - detailed: full breakdown with evidence
      - technical: raw data for debugging
    """

    def explain(self, result: ReasoningResult,
                level: str = "detailed") -> str:
        """Generate explanation at the requested level."""
        if level == "simple":
            return self._explain_simple(result)
        elif level == "technical":
            return self._explain_technical(result)
        else:
            return self._explain_detailed(result)

    def _explain_simple(self, result: ReasoningResult) -> str:
        """1-2 sentence summary."""
        decision = result.decision_type.value.upper()
        confidence = result.confidence.overall

        templates = {
            DecisionType.GO: (
                f"Decision: {decision}. This creative is a proven winner "
                f"with {confidence:.0%} confidence. Recommend scaling."
            ),
            DecisionType.TEST: (
                f"Decision: {decision}. This creative shows promise "
                f"with {confidence:.0%} confidence. Recommend testing."
            ),
            DecisionType.EXPLORE: (
                f"Decision: {decision}. This is a novel combination "
                f"with {confidence:.0%} confidence. Recommend small test."
            ),
            DecisionType.ADAPT: (
                f"Decision: {decision}. Adapt this creative for a new market "
                f"with {confidence:.0%} confidence."
            ),
            DecisionType.AVOID: (
                f"Decision: {decision}. This creative pattern underperforms "
                f"with {confidence:.0%} confidence. Recommend avoiding."
            ),
        }

        return templates.get(result.decision_type, f"Decision: {decision}.")

    def _explain_detailed(self, result: ReasoningResult) -> str:
        """Full breakdown with evidence."""
        lines = [
            "=" * 50,
            f"  REASONING REPORT: {result.creative_id}",
            "=" * 50,
            "",
            f"Decision: {result.decision_type.value.upper()}",
            f"Confidence: {result.confidence.overall:.0%}",
            f"Risk: {result.risk.value.upper()}",
            f"Expected ROAS: {result.expected_roas:.2f}",
            f"Expected CPI: ${result.expected_cpi:.2f}",
            f"Priority: {result.priority}",
            "",
            "─" * 50,
            "  REASON",
            "─" * 50,
            result.reason if result.reason else "No reason provided.",
            "",
            "─" * 50,
            "  EVIDENCE",
            "─" * 50,
        ]

        if result.evidence:
            for i, e in enumerate(result.evidence):
                lines.append(
                    f"  [{i+1}] {e.source.value.upper()}: {e.description} "
                    f"(strength: {e.strength:.0%})"
                )
        else:
            lines.append("  No evidence provided.")

        lines.extend([
            "",
            "─" * 50,
            "  NEXT STEPS",
            "─" * 50,
        ])

        if result.next_steps:
            for i, step in enumerate(result.next_steps):
                lines.append(f"  {i+1}. {step}")
        else:
            lines.append("  No next steps defined.")

        if result.warnings:
            lines.extend([
                "",
                "─" * 50,
                "  WARNINGS",
                "─" * 50,
            ])
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

        lines.extend([
            "",
            "─" * 50,
            "  RECOMMENDED DNA",
            "─" * 50,
        ])
        dna = result.recommended_dna.to_dict()
        if dna:
            for k, v in dna.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append("  No DNA recommendations.")

        return "\n".join(lines)

    def _explain_technical(self, result: ReasoningResult) -> str:
        """Raw data for debugging."""
        import json
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    def validate_explainability(self, result: ReasoningResult) -> dict[str, Any]:
        """Check if a result meets explainability requirements.

        Target: explainability coverage ≥ 95%.
        """
        checks = {
            "has_decision": result.decision_type is not None,
            "has_reason": bool(result.reason),
            "has_evidence": len(result.evidence) > 0,
            "has_confidence": result.confidence.overall > 0,
            "has_next_steps": len(result.next_steps) > 0,
        }

        coverage = sum(1 for v in checks.values() if v) / len(checks)
        return {
            "checks": checks,
            "coverage": round(coverage, 3),
            "passes": coverage >= 0.95,
        }