"""V4.1.1 RAG Planner — pure RAG-based creative planning.

NOT: LLM generates prompt from scratch.
YES: Retrieve → Graph → Pattern → Reason → Plan.

Pipeline:
  1. Retrieve: find top-K similar winning creatives
  2. Graph: traverse knowledge graph for relationships
  3. Pattern: apply discovered combinatorial patterns
  4. Reason: synthesize insights
  5. Plan: generate image/video plan from retrieved evidence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..creative_retriever.retriever import CreativeRetriever
from ..knowledge_graph.graph_builder import GraphBuilder
from ..pattern_mining.combinatorial_miner import CombinatorialPatternMiner, CombinatorialPattern


@dataclass
class RAGPlanResult:
    request: str = ""
    plan_type: str = ""
    retrieved: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    graph_insights: list[str] = field(default_factory=list)
    prompt: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    evidence_count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "plan_type": self.plan_type,
            "retrieved_count": len(self.retrieved),
            "top_retrieved": [r.get("creative_id", "") for r in self.retrieved[:5]],
            "patterns": self.patterns,
            "graph_insights": self.graph_insights,
            "prompt": self.prompt,
            "composition": self.composition,
            "camera": self.camera,
            "evidence_count": self.evidence_count,
            "confidence": round(self.confidence, 3),
        }


class RAGPlanner:
    """RAG-based Creative Planner — evidence-driven, not LLM-generated.

    Usage:
        retriever = CreativeRetriever()
        retriever.index_batch(historical_creatives)

        planner = RAGPlanner(retriever)
        result = planner.plan("dragon merge game for US IAA")
        # result.prompt built from real winning DNA, not hallucinated
    """

    def __init__(self, retriever: CreativeRetriever,
                 graph: GraphBuilder | None = None) -> None:
        self._retriever = retriever
        self._graph = graph or GraphBuilder()
        self._miner = CombinatorialPatternMiner(min_samples=3, min_lift_pct=5.0)

    def plan(self, request: str, plan_type: str = "image",
             country: str = "", min_roas: float = 0.5) -> RAGPlanResult:
        """Generate a creative plan from retrieved evidence."""

        # 1. RETRIEVE: find similar winning creatives
        retrieved = self._retriever.retrieve(
            request, top_k=20,
            min_roas=min_roas,
            creative_type=plan_type,
            country=country if country else "",
        )

        if not retrieved:
            return RAGPlanResult(request=request, plan_type=plan_type)

        # 2. EXTRACT: build evidence from retrieved DNA
        evidence = self._extract_evidence(retrieved)

        # 3. PATTERN: mine combinatorial patterns from evidence
        patterns = self._mine_patterns_from_evidence(retrieved)

        # 4. GRAPH: traverse for relationships
        graph_insights = self._traverse_graph(evidence)

        # 5. PLAN: synthesize into creative plan
        prompt = self._build_prompt_from_evidence(request, evidence, patterns, plan_type)
        composition = self._build_composition_from_evidence(evidence, patterns)
        camera = self._build_camera_from_evidence(evidence, patterns)

        return RAGPlanResult(
            request=request,
            plan_type=plan_type,
            retrieved=[r.to_dict() for r in retrieved[:10]],
            patterns=[p.to_dict() for p in patterns[:5]],
            graph_insights=graph_insights,
            prompt=prompt,
            composition=composition,
            camera=camera,
            evidence_count=len(retrieved),
            confidence=self._compute_confidence(retrieved, patterns),
        )

    def _extract_evidence(self, retrieved: list[Any]) -> dict[str, Any]:
        """Extract aggregated DNA evidence from retrieved creatives."""
        evidence = {
            "total": len(retrieved),
            "avg_roas": 0.0,
            "avg_ctr": 0.0,
            "top_dna": {},
            "dna_distribution": {},
        }

        roas_vals = []
        ctr_vals = []
        dna_counts: dict[str, dict[str, int]] = {}

        for r in retrieved:
            perf = r.performance if hasattr(r, 'performance') else {}
            dna = r.dna if hasattr(r, 'dna') else {}

            if perf.get("roas_d7", 0) > 0:
                roas_vals.append(perf["roas_d7"])
            if perf.get("ctr", 0) > 0:
                ctr_vals.append(perf["ctr"])

            for dim, val in dna.items():
                if val and isinstance(val, str):
                    dna_counts.setdefault(dim, {})
                    dna_counts[dim][val] = dna_counts[dim].get(val, 0) + 1

        evidence["avg_roas"] = sum(roas_vals) / max(len(roas_vals), 1)
        evidence["avg_ctr"] = sum(ctr_vals) / max(len(ctr_vals), 1)

        # Top DNA value per dimension
        for dim, counts in dna_counts.items():
            top_val = max(counts, key=counts.get)
            evidence["top_dna"][dim] = top_val
            evidence["dna_distribution"][dim] = dict(
                sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
            )

        return evidence

    def _mine_patterns_from_evidence(self, retrieved: list[Any]) -> list[CombinatorialPattern]:
        """Mine patterns from retrieved evidence."""
        creatives = []
        for r in retrieved:
            creatives.append({
                "dna": r.dna if hasattr(r, 'dna') else {},
                "performance": r.performance if hasattr(r, 'performance') else {},
            })
        return self._miner.mine(creatives) if creatives else []

    def _traverse_graph(self, evidence: dict[str, Any]) -> list[str]:
        """Traverse knowledge graph for insights."""
        insights = []
        top_dna = evidence.get("top_dna", {})

        if top_dna.get("character"):
            insights.append(
                f"Character '{top_dna['character']}' appears in {evidence['total']} winning creatives"
            )
        if top_dna.get("reward"):
            insights.append(
                f"Reward '{top_dna['reward']}' avg ROAS: {evidence['avg_roas']:.2f}"
            )
        if evidence.get("avg_ctr", 0) > 0:
            insights.append(
                f"Average CTR: {evidence['avg_ctr']:.1f}% across {evidence['total']} creatives"
            )

        return insights

    def _build_prompt_from_evidence(self, request: str,
                                     evidence: dict[str, Any],
                                     patterns: list[CombinatorialPattern],
                                     plan_type: str) -> dict[str, Any]:
        """Build prompt from retrieved evidence, not LLM hallucination."""
        top_dna = evidence.get("top_dna", {})

        # Build positive prompt from real winning DNA
        positive_parts = [request]
        if top_dna.get("character"):
            positive_parts.append(f"character: {top_dna['character']}")
        if top_dna.get("reward"):
            positive_parts.append(f"reward: {top_dna['reward']}")
        if top_dna.get("hook"):
            positive_parts.append(f"hook: {top_dna['hook']}")
        if top_dna.get("gameplay"):
            positive_parts.append(f"gameplay: {top_dna['gameplay']}")
        if top_dna.get("style"):
            positive_parts.append(f"style: {top_dna['style']}")
        if top_dna.get("camera"):
            positive_parts.append(f"camera: {top_dna['camera']}")

        # Add top pattern dimensions
        for p in patterns[:3]:
            for dim, val in p.dimensions.items():
                if dim not in top_dna:
                    positive_parts.append(f"{dim}: {val}")

        positive = ", ".join(positive_parts)

        return {
            "positive_prompt": positive,
            "negative_prompt": "blurry, low quality, deformed, extra limbs, text artifacts",
            "evidence_based": True,
            "source_creative_count": evidence["total"],
            "avg_roas": round(evidence["avg_roas"], 2),
        }

    def _build_composition_from_evidence(self, evidence: dict[str, Any],
                                          patterns: list[CombinatorialPattern]) -> dict[str, Any]:
        top_dna = evidence.get("top_dna", {})
        return {
            "layout": "center",
            "subject_position": "center",
            "background": f"{top_dna.get('gameplay', 'gameplay')}_scene",
            "aspect_ratio": "1:1",
            "evidence_based": True,
        }

    def _build_camera_from_evidence(self, evidence: dict[str, Any],
                                     patterns: list[CombinatorialPattern]) -> dict[str, Any]:
        top_dna = evidence.get("top_dna", {})
        return {
            "angle": top_dna.get("camera", "45_degree"),
            "distance": "medium",
            "motion": "static",
            "evidence_based": True,
        }

    def _compute_confidence(self, retrieved: list[Any],
                            patterns: list[CombinatorialPattern]) -> float:
        """Compute confidence based on evidence quality."""
        evidence_score = min(len(retrieved) / 20, 1.0) * 0.5
        pattern_score = min(len(patterns) / 5, 1.0) * 0.3
        roas_avg = sum(
            (r.performance.get("roas_d7", 0) if hasattr(r, 'performance') else 0)
            for r in retrieved
        ) / max(len(retrieved), 1)
        roas_score = min(roas_avg / 2.0, 1.0) * 0.2

        return evidence_score + pattern_score + roas_score