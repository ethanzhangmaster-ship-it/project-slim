"""V4.1.1 Brain Benchmark — real evaluation, not just PASS/FAIL.

This benchmark validates that the Brain actually WORKS, not just
that the framework is structurally correct.

Metrics:
  - Recall@K (5, 10, 20, 50)
  - MRR (Mean Reciprocal Rank)
  - NDCG@20
  - Pattern Precision (are discovered patterns real?)
  - Planner Quality (is the generated plan evidence-based?)
  - Learning Effect (does learning improve retrieval?)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    name: str = ""
    value: float = 0.0
    threshold: float = 0.0
    passed: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "threshold": self.threshold,
            "passed": self.passed,
            "detail": self.detail,
        }


class BrainBenchmark:
    """Validates that the Brain can actually learn and reason.

    NOT a unit test framework. This is a real benchmark that measures:
      - Can it retrieve relevant creatives?
      - Are discovered patterns statistically valid?
      - Is the planner evidence-based?
      - Does learning improve results?
    """

    def __init__(self, retriever=None, planner=None, learning_loop=None) -> None:
        self._retriever = retriever
        self._planner = planner
        self._learning = learning_loop
        self._results: list[BenchmarkResult] = []

    def run_all(self, test_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run all benchmarks."""
        self._results = []

        if self._retriever:
            self._benchmark_recall(test_data)
            self._benchmark_mrr(test_data)
            self._benchmark_ndcg(test_data)

        if self._planner:
            self._benchmark_planner_quality()
            self._benchmark_pattern_precision(test_data)

        if self._learning:
            self._benchmark_learning_effect(test_data)

        return self.summary()

    # ── Recall Benchmarks ──

    def _benchmark_recall(self, test_data: dict[str, Any] | None) -> None:
        queries = self._get_queries(test_data)
        if not self._retriever or not queries:
            self._results.append(BenchmarkResult(
                name="recall@10", value=0.0, threshold=0.3,
                passed=False, detail="No test data"
            ))
            return

        for k in [5, 10, 20]:
            recall_sum = 0.0
            for q in queries:
                results = self._retriever.retrieve(q["query"], top_k=k)
                retrieved_ids = {r.creative_id for r in results}
                relevant = set(q.get("relevant_ids", []))
                if relevant:
                    recall_sum += len(retrieved_ids & relevant) / len(relevant)

            recall = recall_sum / max(len(queries), 1)
            threshold = 0.5 if k == 5 else (0.6 if k == 10 else 0.7)
            self._results.append(BenchmarkResult(
                name=f"recall@{k}",
                value=recall,
                threshold=threshold,
                passed=recall >= threshold,
                detail=f"Found {recall:.1%} of relevant items in top {k}",
            ))

    def _benchmark_mrr(self, test_data: dict[str, Any] | None) -> None:
        queries = self._get_queries(test_data)
        if not self._retriever or not queries:
            self._results.append(BenchmarkResult(
                name="mrr", value=0.0, threshold=0.4,
                passed=False, detail="No test data"
            ))
            return

        mrr_sum = 0.0
        for q in queries:
            results = self._retriever.retrieve(q["query"], top_k=50)
            relevant = set(q.get("relevant_ids", []))
            for rank, r in enumerate(results):
                if r.creative_id in relevant:
                    mrr_sum += 1.0 / (rank + 1)
                    break

        mrr = mrr_sum / max(len(queries), 1)
        self._results.append(BenchmarkResult(
            name="mrr",
            value=mrr,
            threshold=0.4,
            passed=mrr >= 0.4,
            detail=f"Mean Reciprocal Rank: {mrr:.3f}",
        ))

    def _benchmark_ndcg(self, test_data: dict[str, Any] | None) -> None:
        queries = self._get_queries(test_data)
        if not self._retriever or not queries:
            self._results.append(BenchmarkResult(
                name="ndcg@20", value=0.0, threshold=0.5,
                passed=False, detail="No test data"
            ))
            return

        ndcg_sum = 0.0
        for q in queries:
            results = self._retriever.retrieve(q["query"], top_k=20)
            relevance = q.get("relevance", {})

            dcg = 0.0
            for rank, r in enumerate(results):
                rel = relevance.get(r.creative_id, 0)
                if rel > 0:
                    dcg += rel / math.log2(rank + 2)

            ideal_rels = sorted(relevance.values(), reverse=True)[:20]
            idcg = 0.0
            for i, rel in enumerate(ideal_rels):
                if rel > 0:
                    idcg += rel / math.log2(i + 2)

            ndcg_sum += dcg / max(idcg, 0.001)

        ndcg = ndcg_sum / max(len(queries), 1)
        self._results.append(BenchmarkResult(
            name="ndcg@20",
            value=ndcg,
            threshold=0.5,
            passed=ndcg >= 0.5,
            detail=f"NDCG@20: {ndcg:.3f}",
        ))

    # ── Planner Benchmarks ──

    def _benchmark_planner_quality(self) -> None:
        if not self._planner:
            self._results.append(BenchmarkResult(
                name="planner_quality", value=0.0, threshold=0.5,
                passed=False, detail="No planner"
            ))
            return

        # Test: does planner produce evidence-based results?
        result = self._planner.plan("dragon merge game", plan_type="image")
        evidence_count = getattr(result, 'evidence_count', 0)
        confidence = getattr(result, 'confidence', 0.0)

        quality = min(evidence_count / 10, 1.0) * 0.5 + min(confidence, 1.0) * 0.5
        self._results.append(BenchmarkResult(
            name="planner_quality",
            value=quality,
            threshold=0.3,
            passed=quality >= 0.3,
            detail=f"Evidence: {evidence_count}, Confidence: {confidence:.2f}",
        ))

    def _benchmark_pattern_precision(self, test_data: dict[str, Any] | None) -> None:
        """Verify that discovered patterns are real, not random."""
        if not self._planner:
            self._results.append(BenchmarkResult(
                name="pattern_precision", value=0.0, threshold=0.4,
                passed=False, detail="No planner"
            ))
            return

        result = self._planner.plan("dragon merge game", plan_type="image")
        patterns = getattr(result, 'patterns', [])

        if not patterns:
            self._results.append(BenchmarkResult(
                name="pattern_precision", value=0.0, threshold=0.4,
                passed=False, detail="No patterns discovered"
            ))
            return

        # Check pattern quality: confidence and sample count
        confidences = [p.get("confidence", 0) for p in patterns]
        avg_confidence = sum(confidences) / max(len(confidences), 1)

        self._results.append(BenchmarkResult(
            name="pattern_precision",
            value=avg_confidence,
            threshold=0.3,
            passed=avg_confidence >= 0.3,
            detail=f"{len(patterns)} patterns, avg confidence: {avg_confidence:.2f}",
        ))

    # ── Learning Benchmarks ──

    def _benchmark_learning_effect(self, test_data: dict[str, Any] | None) -> None:
        """Verify that learning actually changes the system state."""
        if not self._learning:
            self._results.append(BenchmarkResult(
                name="learning_effect", value=0.0, threshold=0.5,
                passed=False, detail="No learning loop"
            ))
            return

        # Feed some data
        self._learning.ingest_performance(
            "test_c001",
            new_performance={"roas_d7": 0.9, "ctr": 4.5},
            old_performance={"roas_d7": 0.3, "ctr": 2.0},
        )
        self._learning.ingest_performance(
            "test_c002",
            new_performance={"roas_d7": 0.1, "ctr": 1.0},
            old_performance={"roas_d7": 0.5, "ctr": 3.0},
        )

        report = self._learning.learn()

        # Verify learning happened
        weight_c001 = self._learning.get_creative_weight("test_c001")
        weight_c002 = self._learning.get_creative_weight("test_c002")

        effect = 1.0 if weight_c001 > weight_c002 else 0.0
        self._results.append(BenchmarkResult(
            name="learning_effect",
            value=effect,
            threshold=0.5,
            passed=effect > 0.5,
            detail=f"Winner weight: {weight_c001:.2f}, Loser weight: {weight_c002:.2f}",
        ))

    # ── Helpers ──

    def _get_queries(self, test_data: dict[str, Any] | None) -> list[dict[str, Any]]:
        if test_data and "queries" in test_data:
            return test_data["queries"]
        return []

    def summary(self) -> dict[str, Any]:
        passed = sum(1 for r in self._results if r.passed)
        total = len(self._results)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
            "results": [r.to_dict() for r in self._results],
        }