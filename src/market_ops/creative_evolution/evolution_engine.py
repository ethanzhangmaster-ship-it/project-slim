"""E9.8: Evolution Engine — Orchestrates the full Creative Mutation pipeline.

Pipeline:
  1. Load winner DNA (from creative_dna_master + performance data)
  2. Load failure DNA (low performers)
  3. Generate mutation strategies (winner_emulation, failure_avoidance, exploration)
  4. Detect market opportunities
  5. Mutate winner DNA → new CreativeGenome candidates
  6. Predict archetype + LTV (via E9.6)
  7. Rank candidates
  8. Export results

Outputs:
  - mutation_candidates.json (all candidates)
  - top_mutations.json (top 20)
  - evolution_report.json (summary)
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_evolution.schemas import (
    CreativeGenome, MutationRecord, MutationCandidate,
    WinnerPattern, FailureAnalysis, EvolutionReport,
)
from market_ops.creative_evolution.winner_dna_analyzer import WinnerDNAAnalyzer
from market_ops.creative_evolution.failure_pattern_analyzer import FailurePatternAnalyzer
from market_ops.creative_evolution.mutation_strategy import MutationStrategyEngine
from market_ops.creative_evolution.opportunity_detector import OpportunityDetector
from market_ops.creative_evolution.creative_genome_mutator import CreativeGenomeMutator
from market_ops.creative_evolution.mutation_ranker import MutationRanker


class EvolutionEngine:
    """Orchestrates the full Creative Evolution pipeline.

    Usage:
        engine = EvolutionEngine()
        report = engine.run()
    """

    def __init__(self) -> None:
        # Components
        self._winner_analyzer = WinnerDNAAnalyzer(ltv_threshold_percentile=80)
        self._failure_analyzer = FailurePatternAnalyzer(ltv_threshold_percentile=20)
        self._strategy_engine = MutationStrategyEngine()
        self._opportunity_detector = OpportunityDetector()
        self._mutator = CreativeGenomeMutator()
        self._ranker = MutationRanker()

        # Data
        self._dna_list: list[dict[str, Any]] = []
        self._performance_map: dict[str, dict[str, Any]] = {}
        self._winner_dnas: list[dict[str, Any]] = []
        self._winner_pattern: WinnerPattern | None = None
        self._failure_analysis: FailureAnalysis | None = None
        self._strategies: list = []
        self._opportunities: list = []
        self._candidates_raw: list[tuple[CreativeGenome, list[MutationRecord]]] = []
        self._ranked_candidates: list[MutationCandidate] = []
        self._report: EvolutionReport | None = None

        # Paths
        self._dna_path = Path("output/active/creative_dna_master.json")
        self._perf_path = Path("output/creative_learning/actual_performance.json")
        self._weight_path = Path("output/creative_learning/dna_weight_config.json")
        self._output_dir = Path("output/creative_evolution")

    # ── Step 1: Load Data ─────────────────────────────────

    def load_data(
        self,
        dna_path: str | Path | None = None,
        perf_path: str | Path | None = None,
    ) -> tuple[int, int]:
        """Load DNA and performance data."""
        # Load DNA
        dp = Path(dna_path) if dna_path else self._dna_path
        if dp.exists():
            with open(dp, 'r', encoding='utf-8') as f:
                self._dna_list = json.load(f)

        # Load performance
        pp = Path(perf_path) if perf_path else self._perf_path
        if pp.exists():
            with open(pp, 'r', encoding='utf-8') as f:
                perf_list = json.load(f)
            self._performance_map = {
                p["creative_id"]: p for p in perf_list
            }

        return len(self._dna_list), len(self._performance_map)

    # ── Step 2: Analyze Winners ────────────────────────────

    def analyze_winners(self) -> WinnerPattern:
        """Analyze winner DNA patterns."""
        self._winner_pattern = self._winner_analyzer.analyze(
            self._dna_list, self._performance_map,
        )
        self._winner_dnas = self._winner_analyzer.extract_winner_dna(
            self._dna_list, self._performance_map,
        )
        return self._winner_pattern

    # ── Step 3: Analyze Failures ───────────────────────────

    def analyze_failures(self) -> FailureAnalysis:
        """Analyze failure DNA patterns."""
        self._failure_analysis = self._failure_analyzer.analyze(
            self._dna_list, self._performance_map,
        )
        return self._failure_analysis

    # ── Step 4: Generate Strategies ────────────────────────

    def generate_strategies(self) -> list:
        """Generate mutation strategies."""
        if not self._winner_pattern or not self._failure_analysis:
            return []

        # Collect existing DNA values for exploration
        existing_values = self._collect_existing_values()

        self._strategies = self._strategy_engine.generate(
            self._winner_pattern,
            self._failure_analysis,
            existing_values,
        )
        return self._strategies

    # ── Step 5: Detect Opportunities ───────────────────────

    def detect_opportunities(self) -> list:
        """Detect market opportunities."""
        if not self._winner_pattern:
            return []

        self._opportunities = self._opportunity_detector.detect(
            self._dna_list, self._winner_pattern,
        )
        return self._opportunities

    # ── Step 6: Mutate ────────────────────────────────────

    def mutate(self, max_candidates: int = 2000) -> int:
        """Generate mutation candidates."""
        if not self._strategies or not self._failure_analysis:
            return 0

        self._candidates_raw = self._mutator.mutate(
            self._winner_dnas,
            self._strategies,
            self._failure_analysis,
            max_candidates,
        )
        return len(self._candidates_raw)

    # ── Step 7: Predict & Rank ─────────────────────────────

    def predict_and_rank(self) -> list[MutationCandidate]:
        """Predict LTV/archetype and rank candidates."""
        if not self._candidates_raw:
            return []

        # Build LTV predictions using E9.6 (if available)
        predicted_ltv_map = self._predict_with_e96()

        # Rank
        self._ranked_candidates = self._ranker.rank(
            self._candidates_raw,
            self._winner_pattern,
            self._opportunities,
            self._dna_list,
            predicted_ltv_map,
        )
        return self._ranked_candidates

    # ── Step 8: Build Report ───────────────────────────────

    def build_report(self) -> EvolutionReport:
        """Build evolution summary report."""
        now = datetime.now(timezone.utc).isoformat()

        # Mutation stats
        by_type: dict[str, int] = defaultdict(int)
        by_dim: dict[str, int] = defaultdict(int)
        for genome, mutations in self._candidates_raw:
            for m in mutations:
                by_type[m.mutation_type] += 1
                by_dim[m.dimension] += 1

        # Archetype coverage
        arch_coverage: dict[str, int] = defaultdict(int)
        for c in self._ranked_candidates:
            if c.predicted_archetypes:
                top_arch = max(c.predicted_archetypes, key=c.predicted_archetypes.get)
                arch_coverage[top_arch] += 1

        # Avg metrics
        avg_ltv = (
            sum(c.predicted_ltv for c in self._ranked_candidates) /
            len(self._ranked_candidates)
            if self._ranked_candidates else 0.0
        )
        avg_conf = (
            sum(c.confidence for c in self._ranked_candidates) /
            len(self._ranked_candidates)
            if self._ranked_candidates else 0.0
        )

        self._report = EvolutionReport(
            report_time=now,
            evolution_round=1,
            winner_count=self._winner_pattern.winner_count if self._winner_pattern else 0,
            loser_count=self._failure_analysis.loser_count if self._failure_analysis else 0,
            total_dna_analyzed=len(self._dna_list),
            winner_pattern=self._winner_pattern,
            failure_analysis=self._failure_analysis,
            total_strategies=len(self._strategies),
            total_candidates=len(self._candidates_raw),
            mutations_by_type=dict(by_type),
            mutations_by_dimension=dict(by_dim),
            top_candidates=self._ranked_candidates[:20],
            avg_predicted_ltv=avg_ltv,
            avg_confidence=avg_conf,
            archetype_coverage=dict(arch_coverage),
        )
        return self._report

    # ── Export ─────────────────────────────────────────────

    def export_all(self) -> dict[str, str]:
        """Export all output files via standalone EvolutionExporter."""
        from market_ops.creative_evolution.export import EvolutionExporter

        exporter = EvolutionExporter(str(self._output_dir))
        return exporter.export_all(self._ranked_candidates, self._report)

    # ── Full Pipeline ──────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Run the complete Creative Evolution pipeline."""
        # Step 1: Load
        n_dna, n_perf = self.load_data()
        if n_dna == 0:
            return {"status": "error", "message": "No DNA data loaded"}

        # Step 2: Analyze winners
        self.analyze_winners()

        # Step 3: Analyze failures
        self.analyze_failures()

        # Step 4: Generate strategies
        self.generate_strategies()

        # Step 5: Detect opportunities
        self.detect_opportunities()

        # Step 6: Mutate
        n_candidates = self.mutate()

        # Step 7: Predict & Rank
        self.predict_and_rank()

        # Step 8: Build report
        self.build_report()

        # Step 9: Export
        export_paths = self.export_all()

        return {
            "status": "success",
            "summary": {
                "dna_loaded": n_dna,
                "performances_loaded": n_perf,
                "winner_count": self._winner_pattern.winner_count if self._winner_pattern else 0,
                "loser_count": self._failure_analysis.loser_count if self._failure_analysis else 0,
                "strategies": len(self._strategies),
                "opportunities": len(self._opportunities),
                "candidates": n_candidates,
                "ranked": len(self._ranked_candidates),
                "top_20_avg_ltv": round(
                    sum(c.predicted_ltv for c in self._ranked_candidates[:20]) / 20, 1
                ) if len(self._ranked_candidates) >= 20 else 0,
            },
            "export_paths": export_paths,
        }

    # ── Helpers ────────────────────────────────────────────

    def _collect_existing_values(self) -> dict[str, set[str]]:
        """Collect existing DNA values for each dimension."""
        existing: dict[str, set[str]] = defaultdict(set)
        for d in self._dna_list:
            h = (d.get("hook", {}) or {}).get("type", "")
            if h and h != "unknown":
                existing["hook"].add(h)
            r = (d.get("reward", {}) or {}).get("type", "")
            if r and r != "unknown":
                existing["reward"].add(r)
            v = (d.get("visual", {}) or {}).get("style", "")
            if v and v != "unknown":
                existing["visual"].add(v)
            for f in (d.get("fantasy", {}) or {}).get("drives", []) or []:
                existing["fantasy"].add(f)
        return dict(existing)

    def _predict_with_e96(self) -> dict[str, dict[str, Any]]:
        """Use E9.6 to predict LTV and archetypes for generated genomes."""
        predicted: dict[str, dict[str, Any]] = {}
        try:
            from market_ops.creative_matching.dna_feature_encoder import DNAFeatureEncoder
            from market_ops.creative_matching.creative_archetype_profile import CreativeArchetypeProfileDB
            from market_ops.creative_matching.archetype_predictor import ArchetypePredictor

            encoder = DNAFeatureEncoder()
            profile_db = CreativeArchetypeProfileDB()
            profile_db.load()

            predictor = ArchetypePredictor(profile_db)

            # Apply E9.7 learned weights if available
            if self._weight_path.exists():
                with open(self._weight_path, 'r', encoding='utf-8') as f:
                    weight_config = json.load(f)
                weights = weight_config.get("weights", {})
                if weights:
                    predictor.set_weights(weights)

            for genome, _ in self._candidates_raw:
                # Build minimal DNA dict for E9.6 encoder
                dna_dict = {
                    "creative_id": genome.genome_id,
                    "hook": {"type": genome.hook, "confidence": 0.8},
                    "reward": {"type": genome.reward, "confidence": 0.8},
                    "visual": {"style": genome.visual_style, "confidence": 0.8},
                    "fantasy": {"drives": [genome.fantasy] if genome.fantasy else []},
                    "mechanism": {"type": genome.mechanism or "merge"},
                }

                fv = encoder.encode(dna_dict)
                pred = predictor.predict(fv)

                arch_dist = {}
                for arch, detail in pred.archetype_distribution.items():
                    arch_dist[arch] = detail.adjusted_probability

                predicted[genome.genome_id] = {
                    "ltv": pred.expected_metrics.get("ltv", 0),
                    "archetypes": arch_dist,
                    "payer_rate": pred.expected_metrics.get("payer_rate", 0),
                    "d30": pred.expected_metrics.get("d30", 0),
                    "confidence": pred.overall_confidence,
                }

        except Exception:
            pass  # Fall back to winner pattern estimates

        return predicted


# ═══════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════

def run_e98_pipeline(
    dna_path: str | Path | None = None,
    perf_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete E9.8 Creative Evolution pipeline."""
    engine = EvolutionEngine()

    if dna_path:
        engine._dna_path = Path(dna_path)
    if perf_path:
        engine._perf_path = Path(perf_path)
    if output_dir:
        engine._output_dir = Path(output_dir)

    return engine.run()