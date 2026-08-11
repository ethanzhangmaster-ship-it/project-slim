"""V4.2 Creative Reasoning Engine — unified reasoning entry point.

The reasoning layer that integrates ALL V4.2 modules into a single interface.

This is the DECISION LAYER that:
  - Explains WHY (WinnerAnalyzer)
  - Adapts WHERE (CrossCountryAdapter)
  - Classifies WHAT (PatternClassifier)
  - Optimizes HOW (ConstraintOptimizer)
  - Tracks WHEN (TrendReasoner)
  - Transfers ACROSS games (MetaReasoner)
  - Builds EVIDENCE (EvidenceBuilder)
  - Computes CONFIDENCE (ConfidenceEngine)
  - Generates EXPLANATION (ExplanationEngine)
  - Decides NEXT (DecisionEngine)

Usage:
    engine = ReasoningEngine(retriever=retriever)

    # Analyze a winner
    analysis = engine.analyze_winner("c_0001", dna, performance)

    # Adapt for a new country
    adaptation = engine.adapt_country("c_0001", "US", "JP", dna)

    # Classify a new creative
    classification = engine.classify_creative("c_new", dna)

    # Optimize under constraints
    plan = engine.optimize_generation(budget=1000, country="US")

    # Analyze trends
    trends = engine.analyze_trends(window_days=7)

    # Cross-game knowledge transfer
    transfer = engine.transfer_knowledge("merge", "puzzle")

    # Make a fully-evidenced decision
    result = engine.reason(creative_id="c_0001", dna=dna, performance=perf)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .winner_analyzer import WinnerAnalyzer, WinnerAnalysis, FactorContribution
from .cross_country_adapter import CrossCountryAdapter, CrossCountryAnalysis, AdaptationRecommendation
from .pattern_classifier import PatternClassifier, ClassificationResult, PatternMatch
from .constraint_optimizer import ConstraintOptimizer, OptimizationResult, CreativePlan
from .trend_reasoner import TrendReasoner, TrendReport
from .meta_reasoner import MetaReasoner, MetaAnalysis
from .decision_engine import DecisionEngine
from .decision_maker import DecisionMaker, Decision, DecisionType as LegacyDecisionType
from .evidence_builder import EvidenceBuilder
from .confidence import ConfidenceEngine
from .explanation import ExplanationEngine
from .schemas import DecisionType, ReasoningResult, ConfidenceScore, EvidenceItem, RiskLevel
from .models import KnowledgeTransferModel


@dataclass
class ReasoningReport:
    """Complete reasoning report with all analysis results."""
    creative_id: str = ""
    winner_analysis: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    country_adaptation: dict[str, Any] | None = None
    optimization: dict[str, Any] | None = None
    trend_report: dict[str, Any] | None = None
    meta_analysis: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: dict[str, Any] | None = None
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "winner_analysis": self.winner_analysis,
            "classification": self.classification,
            "country_adaptation": self.country_adaptation,
            "optimization": self.optimization,
            "trend_report": self.trend_report,
            "meta_analysis": self.meta_analysis,
            "decision": self.decision,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }


class ReasoningEngine:
    """V4.2 Creative Reasoning Engine — the brain's complete decision layer.

    Integrates ALL reasoning modules:
      - Core reasoners: Winner, Transfer, Pattern, Constraint
      - New reasoners: Trend, Meta
      - Decision engines: DecisionEngine, DecisionMaker (legacy)
      - Support: Evidence, Confidence, Explanation
    """

    def __init__(self, retriever=None, pattern_miner=None,
                 knowledge_graph=None, learning_loop=None) -> None:
        # Core reasoners
        self._winner_analyzer = WinnerAnalyzer(
            retriever=retriever, pattern_miner=pattern_miner
        )
        self._country_adapter = CrossCountryAdapter(retriever=retriever)
        self._pattern_classifier = PatternClassifier(
            retriever=retriever, pattern_miner=pattern_miner
        )
        self._constraint_optimizer = ConstraintOptimizer(
            retriever=retriever, pattern_miner=pattern_miner,
            country_adapter=self._country_adapter,
        )
        # New reasoners
        self._trend_reasoner = TrendReasoner(
            retriever=retriever, pattern_miner=pattern_miner
        )
        self._meta_reasoner = MetaReasoner()
        # Decision engines
        self._decision_engine = DecisionEngine(
            retriever=retriever,
            pattern_miner=pattern_miner,
            knowledge_graph=knowledge_graph,
            learning_loop=learning_loop,
        )
        self._decision_maker = DecisionMaker()
        # Support
        self._evidence_builder = EvidenceBuilder(
            retriever=retriever,
            pattern_miner=pattern_miner,
            knowledge_graph=knowledge_graph,
            learning_loop=learning_loop,
        )
        self._confidence_engine = ConfidenceEngine()
        self._explanation_engine = ExplanationEngine()

    # ── Public API: Core Reasoners ──

    def analyze_winner(self, creative_id: str,
                       dna: dict[str, Any] | None = None,
                       performance: dict[str, Any] | None = None) -> WinnerAnalysis:
        """Analyze WHY a creative is a winner (or not)."""
        return self._winner_analyzer.analyze(
            creative_id=creative_id,
            dna_data=dna,
            performance=performance,
        )

    def adapt_country(self, creative_id: str,
                      source_country: str, target_country: str,
                      dna: dict[str, Any] | None = None) -> CrossCountryAnalysis:
        """Adapt a creative from one country to another."""
        return self._country_adapter.adapt(
            creative_id=creative_id,
            source_country=source_country,
            target_country=target_country,
            dna=dna,
        )

    def classify_creative(self, creative_id: str,
                          dna: dict[str, Any],
                          performance: dict[str, Any] | None = None) -> ClassificationResult:
        """Classify a creative into known patterns."""
        return self._pattern_classifier.classify(
            creative_id=creative_id,
            dna=dna,
            performance=performance,
        )

    def optimize_generation(self, budget: float = 1000.0,
                            country: str = "US",
                            monetization: str = "iaa",
                            creative_count: int = 10,
                            explore_ratio: float = 0.2) -> OptimizationResult:
        """Optimize creative generation under constraints."""
        return self._constraint_optimizer.optimize(
            budget=budget,
            country=country,
            monetization=monetization,
            creative_count=creative_count,
            explore_ratio=explore_ratio,
        )

    # ── Public API: New Reasoners ──

    def analyze_trends(self, window_days: int = 7,
                       platform: str = "facebook") -> TrendReport:
        """Analyze DNA trends over time windows."""
        return self._trend_reasoner.analyze(
            window_days=window_days, platform=platform
        )

    def analyze_why_game_works(self, game_type: str) -> MetaAnalysis:
        """Analyze WHY a game type works (psychology, mechanics, hooks)."""
        return self._meta_reasoner.analyze_why(game_type)

    def transfer_knowledge(self, source_game: str,
                           target_game: str) -> KnowledgeTransferModel:
        """Generate cross-game knowledge transfer plan."""
        return self._meta_reasoner.transfer_to(source_game, target_game)

    # ── Public API: Evidence & Confidence ──

    def build_evidence(self, dna: dict[str, Any] | None = None,
                       performance: dict[str, Any] | None = None,
                       creative_id: str = "") -> list[EvidenceItem]:
        """Build evidence chain for a decision."""
        return self._evidence_builder.build(
            dna=dna, performance=performance, creative_id=creative_id
        )

    def compute_confidence(self, retriever_score: float = 0.0,
                           pattern_score: float = 0.0,
                           graph_score: float = 0.0,
                           learning_score: float = 0.0,
                           trend_score: float = 0.0) -> ConfidenceScore:
        """Compute weighted confidence score."""
        return self._confidence_engine.compute(
            retriever_score=retriever_score,
            pattern_score=pattern_score,
            graph_score=graph_score,
            learning_score=learning_score,
            trend_score=trend_score,
        )

    # ── Public API: Decision ──

    def decide(self, creative_id: str,
               dna: dict[str, Any] | None = None,
               performance: dict[str, Any] | None = None) -> Decision:
        """Legacy decision maker (backward compatible)."""
        winner = self.analyze_winner(creative_id, dna, performance)
        classification = self.classify_creative(creative_id, dna or {}, performance)
        return self._decision_maker.decide(
            creative_id=creative_id,
            winner_analysis=winner,
            pattern_classification=classification,
        )

    def reason(self, creative_id: str,
               dna: dict[str, Any] | None = None,
               performance: dict[str, Any] | None = None,
               source_country: str = "",
               target_country: str = "") -> ReasoningResult:
        """Full reasoning pipeline — returns complete ReasoningResult.

        This is the main V4.2 entry point. Runs ALL reasoning modules
        and returns a fully-evidenced decision.
        """
        dna = dna or {}
        performance = performance or {}

        # Run all analyses
        winner = self.analyze_winner(creative_id, dna, performance)
        classification = self.classify_creative(creative_id, dna, performance)
        country_adapt = (
            self.adapt_country(creative_id, source_country, target_country, dna)
            if source_country and target_country else None
        )
        trends = self.analyze_trends(window_days=7)

        # Make decision with full evidence
        result = self._decision_engine.decide(
            creative_id=creative_id,
            winner_analysis=winner,
            pattern_classification=classification,
            cross_country_analysis=country_adapt,
            trend_report=trends,
            dna=dna,
            performance=performance,
        )

        # Generate full explanation
        result.explanation = self._explanation_engine.explain(result, level="detailed")

        return result

    def full_report(self, creative_id: str,
                    dna: dict[str, Any] | None = None,
                    performance: dict[str, Any] | None = None,
                    source_country: str = "",
                    target_country: str = "") -> ReasoningReport:
        """Generate a comprehensive reasoning report with ALL modules."""
        dna = dna or {}
        performance = performance or {}

        winner = self.analyze_winner(creative_id, dna, performance)
        classification = self.classify_creative(creative_id, dna, performance)
        decision = self._decision_maker.decide(
            creative_id=creative_id,
            winner_analysis=winner,
            pattern_classification=classification,
        )

        country_adapt = None
        if source_country and target_country:
            country_adapt = self.adapt_country(
                creative_id, source_country, target_country, dna
            )

        trends = self.analyze_trends(window_days=7)

        evidence = self._evidence_builder.build(
            dna=dna, performance=performance, creative_id=creative_id
        )
        confidence = self._confidence_engine.compute_from_evidence(evidence)

        return ReasoningReport(
            creative_id=creative_id,
            winner_analysis=winner.to_dict(),
            classification=classification.to_dict(),
            country_adaptation=country_adapt.to_dict() if country_adapt else None,
            decision=decision.to_dict(),
            trend_report=trends.to_dict(),
            evidence=[e.to_dict() for e in evidence],
            confidence=confidence.to_dict(),
            explanation=self._explanation_engine.explain(
                ReasoningResult(
                    creative_id=creative_id,
                    decision_type=DecisionType(decision.decision_type.value),
                    confidence=confidence,
                    evidence=evidence,
                    reason=decision.rationale,
                ),
                level="simple",
            ),
        )

    # ── Accessors ──

    @property
    def winner_analyzer(self) -> WinnerAnalyzer:
        return self._winner_analyzer

    @property
    def country_adapter(self) -> CrossCountryAdapter:
        return self._country_adapter

    @property
    def pattern_classifier(self) -> PatternClassifier:
        return self._pattern_classifier

    @property
    def constraint_optimizer(self) -> ConstraintOptimizer:
        return self._constraint_optimizer

    @property
    def trend_reasoner(self) -> TrendReasoner:
        return self._trend_reasoner

    @property
    def meta_reasoner(self) -> MetaReasoner:
        return self._meta_reasoner

    @property
    def decision_engine(self) -> DecisionEngine:
        return self._decision_engine

    @property
    def decision_maker(self) -> DecisionMaker:
        return self._decision_maker

    @property
    def evidence_builder(self) -> EvidenceBuilder:
        return self._evidence_builder

    @property
    def confidence_engine(self) -> ConfidenceEngine:
        return self._confidence_engine

    @property
    def explanation_engine(self) -> ExplanationEngine:
        return self._explanation_engine