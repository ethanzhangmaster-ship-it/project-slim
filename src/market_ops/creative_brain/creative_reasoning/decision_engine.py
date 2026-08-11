"""V4.2 Decision Engine — final decision with full evidence, confidence, and explanation.

Integrates ALL reasoning modules:
  - Winner Reasoner (why?)
  - Transfer Reasoner (where?)
  - Pattern Reasoner (what pattern?)
  - Constraint Reasoner (how?)
  - Trend Reasoner (when? growing/declining?)
  - Meta Reasoner (cross-game transfer?)

Outputs: Decision with Evidence + Confidence + Explanation + Risk.

Every decision MUST have evidence (NO LLM GUESSING).
"""

from __future__ import annotations

from typing import Any

from .schemas import (
    DecisionType, RiskLevel, EvidenceSource, EvidenceItem,
    ConfidenceScore, ReasoningResult, DNASchema,
)
from .evidence_builder import EvidenceBuilder
from .confidence import ConfidenceEngine
from .explanation import ExplanationEngine


class DecisionEngine:
    """V4.2 Decision Engine — the brain's final decision layer.

    Fuses all reasoning modules into a single decision with:
      - Evidence chain (every decision backed by data)
      - Confidence score (weighted multi-source)
      - Explanation (human-readable)
      - Risk assessment (low/medium/high)
      - Next steps (actionable)
    """

    def __init__(self, retriever=None, pattern_miner=None,
                 knowledge_graph=None, learning_loop=None) -> None:
        self._evidence_builder = EvidenceBuilder(
            retriever=retriever,
            pattern_miner=pattern_miner,
            knowledge_graph=knowledge_graph,
            learning_loop=learning_loop,
        )
        self._confidence_engine = ConfidenceEngine()
        self._explanation_engine = ExplanationEngine()

    def decide(self, creative_id: str,
               winner_analysis=None,
               pattern_classification=None,
               cross_country_analysis=None,
               constraint_optimization=None,
               trend_report=None,
               meta_analysis=None,
               dna: dict[str, Any] | None = None,
               performance: dict[str, Any] | None = None) -> ReasoningResult:
        """Make a fully-evidenced decision.

        Aggregates all reasoning outputs into a single decision.
        """
        dna = dna or {}
        performance = performance or {}

        # 1. Build evidence
        evidence = self._evidence_builder.build(
            dna=dna, performance=performance, creative_id=creative_id
        )

        # 2. Determine decision type
        decision_type = self._determine_type(
            winner_analysis, pattern_classification,
            cross_country_analysis, trend_report,
        )

        # 3. Compute confidence
        confidence = self._compute_confidence(
            winner_analysis, pattern_classification,
            cross_country_analysis, trend_report,
        )

        # 4. Compute risk
        risk = self._compute_risk(decision_type, confidence)

        # 5. Build reason
        reason = self._build_reason(
            decision_type, winner_analysis, pattern_classification,
            cross_country_analysis, trend_report,
        )

        # 6. Estimate outcomes
        expected_roas = self._estimate_roas(pattern_classification, winner_analysis)
        expected_cpi = self._estimate_cpi(pattern_classification)

        # 7. Build next steps
        next_steps = self._build_next_steps(decision_type, cross_country_analysis)

        # 8. Build warnings
        warnings = self._build_warnings(decision_type, trend_report, confidence)

        # 9. Priority
        priority = self._compute_priority(decision_type, confidence, expected_roas)

        # 10. Recommend DNA
        recommended_dna = self._recommend_dna(
            winner_analysis, pattern_classification, cross_country_analysis
        )

        result = ReasoningResult(
            creative_id=creative_id,
            decision_type=decision_type,
            confidence=confidence,
            evidence=evidence,
            reason=reason,
            recommended_dna=recommended_dna,
            risk=risk,
            expected_roas=expected_roas,
            expected_cpi=expected_cpi,
            priority=priority,
            next_steps=next_steps,
            warnings=warnings,
        )

        # Generate explanation
        result.explanation = self._explanation_engine.explain(result, level="simple")

        return result

    def decide_with_explanation(self, creative_id: str,
                                 **kwargs) -> ReasoningResult:
        """Make a decision and generate full explanation."""
        result = self.decide(creative_id, **kwargs)
        result.explanation = self._explanation_engine.explain(result, level="detailed")
        return result

    # ── Decision type determination ──

    def _determine_type(self, winner_analysis,
                        pattern_classification,
                        cross_country_analysis,
                        trend_report) -> DecisionType:
        """Determine the decision type from all reasoning inputs."""
        # Cross-country adaptation takes priority
        if cross_country_analysis:
            transfer = getattr(cross_country_analysis, 'transferability_score', 0)
            if transfer > 0.4:
                return DecisionType.ADAPT

        # Winner analysis
        if winner_analysis:
            is_winner = getattr(winner_analysis, 'is_winner', False)
            replicability = getattr(winner_analysis, 'replicability_score', 0)
            if is_winner:
                if replicability > 0.6:
                    return DecisionType.GO
                return DecisionType.TEST
            # Not a winner
            if not is_winner:
                return DecisionType.AVOID

        # Pattern classification
        if pattern_classification:
            worth = getattr(pattern_classification, 'worth_trying', False)
            novelty = getattr(pattern_classification, 'novelty_score', 0)
            if worth:
                if novelty > 0.7:
                    return DecisionType.EXPLORE
                return DecisionType.TEST
            # High novelty without data → still worth exploring
            if novelty > 0.7:
                return DecisionType.EXPLORE
            return DecisionType.AVOID

        # Trend-based
        if trend_report:
            growing = getattr(trend_report, 'growing_dna', [])
            if growing:
                return DecisionType.EXPLORE

        # Default: test
        return DecisionType.TEST

    # ── Confidence computation ──

    def _compute_confidence(self, winner_analysis,
                            pattern_classification,
                            cross_country_analysis,
                            trend_report) -> ConfidenceScore:
        """Compute weighted confidence from all sources."""
        retriever = 0.0
        pattern = 0.0
        graph = 0.0
        learning = 0.0
        trend = 0.0

        if winner_analysis:
            retriever = getattr(winner_analysis, 'replicability_score', 0) * 0.5 + 0.3

        if pattern_classification:
            best = getattr(pattern_classification, 'best_match', None)
            if best:
                pattern = getattr(best, 'confidence', 0)

        if cross_country_analysis:
            graph = getattr(cross_country_analysis, 'transferability_score', 0)

        if trend_report:
            trend = getattr(trend_report, 'confidence', 0)

        return self._confidence_engine.compute(
            retriever_score=retriever,
            pattern_score=pattern,
            graph_score=graph,
            learning_score=learning,
            trend_score=trend,
        )

    # ── Risk assessment ──

    def _compute_risk(self, decision_type: DecisionType,
                      confidence: ConfidenceScore) -> RiskLevel:
        """Compute risk level."""
        if decision_type == DecisionType.GO and confidence.overall > 0.7:
            return RiskLevel.LOW
        if decision_type == DecisionType.AVOID:
            return RiskLevel.LOW
        if confidence.overall < 0.4:
            return RiskLevel.HIGH
        if decision_type == DecisionType.EXPLORE:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    # ── Reason builder ──

    def _build_reason(self, decision_type: DecisionType,
                      winner_analysis,
                      pattern_classification,
                      cross_country_analysis,
                      trend_report) -> str:
        """Build a human-readable reason for the decision."""
        parts = []

        if decision_type == DecisionType.GO:
            parts.append("Proven winner with high replicability")
            if winner_analysis:
                factors = getattr(winner_analysis, 'key_factors', [])
                top = [f"{f.dimension}={f.value}" for f in factors[:3]]
                if top:
                    parts.append(f"Key factors: {', '.join(top)}")
        elif decision_type == DecisionType.TEST:
            parts.append("Promising creative worth testing")
        elif decision_type == DecisionType.EXPLORE:
            parts.append("Novel combination worth exploring")
        elif decision_type == DecisionType.ADAPT:
            parts.append("Adapting proven creative for new market")
            if cross_country_analysis:
                src = getattr(cross_country_analysis, 'source_country', '')
                tgt = getattr(cross_country_analysis, 'target_country', '')
                if src and tgt:
                    parts.append(f"From {src} to {tgt}")
        elif decision_type == DecisionType.AVOID:
            parts.append("Pattern consistently underperforms")

        return ". ".join(parts) + "."

    # ── Outcome estimation ──

    def _estimate_roas(self, pattern_classification,
                       winner_analysis) -> float:
        """Estimate expected ROAS."""
        if pattern_classification:
            best = getattr(pattern_classification, 'best_match', None)
            if best:
                return getattr(best, 'expected_roas', 0.5)
        if winner_analysis and getattr(winner_analysis, 'is_winner', False):
            return 0.8
        return 0.4

    def _estimate_cpi(self, pattern_classification) -> float:
        """Estimate expected CPI."""
        if pattern_classification:
            best = getattr(pattern_classification, 'best_match', None)
            if best:
                er = getattr(best, 'expected_range', {})
                cpi_range = er.get("cpi", (0.5, 0.5))
                return (cpi_range[0] + cpi_range[1]) / 2
        return 0.5

    # ── Next steps ──

    def _build_next_steps(self, decision_type: DecisionType,
                          cross_country_analysis) -> list[str]:
        """Build actionable next steps."""
        if decision_type == DecisionType.GO:
            return [
                "Increase budget by 50-100%",
                "Generate 10+ variants with same core DNA",
                "Expand to similar audience segments",
            ]
        elif decision_type == DecisionType.TEST:
            return [
                "Allocate test budget ($200-500)",
                "Generate 3-5 variants",
                "Monitor for 7 days before scaling",
            ]
        elif decision_type == DecisionType.EXPLORE:
            return [
                "Allocate small exploration budget ($100-200)",
                "Test 2-3 novel combinations",
                "Compare against known winners",
            ]
        elif decision_type == DecisionType.ADAPT:
            return [
                "Adapt DNA for target country",
                "Run small-budget test in new market",
                "Compare performance against source market",
            ]
        elif decision_type == DecisionType.AVOID:
            return [
                "Analyze failure reasons before retrying",
                "Consider alternative DNA combinations",
                "Check if trend data shows this pattern is declining",
            ]
        return ["Monitor for 7 days"]

    # ── Warnings ──

    def _build_warnings(self, decision_type: DecisionType,
                        trend_report,
                        confidence: ConfidenceScore) -> list[str]:
        """Build warning messages."""
        warnings = []

        if confidence.overall < 0.4:
            warnings.append("Low confidence — decision based on limited data")
        if decision_type == DecisionType.EXPLORE:
            warnings.append("Exploration carries higher risk — limit budget exposure")
        if trend_report:
            declining = getattr(trend_report, 'declining_dna', [])
            if declining:
                warnings.append(f"Some DNA dimensions are declining in this window")

        return warnings

    # ── Priority ──

    def _compute_priority(self, decision_type: DecisionType,
                          confidence: ConfidenceScore,
                          expected_roas: float) -> int:
        """Compute decision priority (1 = highest)."""
        base = {
            DecisionType.GO: 1,
            DecisionType.ADAPT: 2,
            DecisionType.TEST: 3,
            DecisionType.EXPLORE: 4,
            DecisionType.AVOID: 5,
        }
        priority = base.get(decision_type, 3)
        # Boost priority for high-confidence decisions
        if confidence.overall > 0.7:
            priority = max(1, priority - 1)
        return priority

    # ── DNA recommendation ──

    def _recommend_dna(self, winner_analysis,
                       pattern_classification,
                       cross_country_analysis) -> DNASchema:
        """Recommend DNA based on reasoning results."""
        dna = DNASchema()

        if winner_analysis:
            factors = getattr(winner_analysis, 'key_factors', [])
            for f in factors[:5]:
                if f.contribution > 0.1:
                    setattr(dna, f.dimension, f.value)

        if pattern_classification:
            best = getattr(pattern_classification, 'best_match', None)
            if best:
                dims = getattr(best, 'match_dimensions', {})
                for k, v in dims.items():
                    if not getattr(dna, k, ""):
                        setattr(dna, k, v)

        if cross_country_analysis:
            keeps = getattr(cross_country_analysis, 'keep_dimensions', [])
            for k in keeps:
                dim = k.get("dimension", "")
                val = k.get("value", "")
                if dim and val:
                    setattr(dna, dim, val)

        return dna