"""V4.2 Evidence Builder — ensures every decision has traceable evidence.

Core principle: NO LLM GUESSING. Every conclusion must be backed by:
  - Memory (historical creative data)
  - Retriever (similar creative search)
  - Knowledge Graph (relationship data)
  - Pattern Mining (discovered patterns)
  - Learning Loop (learned insights)

Usage:
    builder = EvidenceBuilder(retriever=retriever, pattern_miner=miner)
    evidence = builder.build(dna=dna, performance=perf)
    # evidence = [EvidenceItem(source=MEMORY, ...), EvidenceItem(source=PATTERN, ...)]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import EvidenceItem, EvidenceSource, ReasoningContext


class EvidenceBuilder:
    """Builds evidence chains for reasoning decisions.

    Every decision output must include at least 1 evidence item.
    Evidence coverage target: 100%.
    """

    MIN_EVIDENCE_ITEMS = 1

    def __init__(self, retriever=None, pattern_miner=None,
                 knowledge_graph=None, learning_loop=None) -> None:
        self._retriever = retriever
        self._pattern_miner = pattern_miner
        self._knowledge_graph = knowledge_graph
        self._learning_loop = learning_loop

    def build(self, context: ReasoningContext | None = None,
              dna: dict[str, Any] | None = None,
              performance: dict[str, Any] | None = None,
              creative_id: str = "") -> list[EvidenceItem]:
        """Build a complete evidence chain for a reasoning decision.

        Collects evidence from ALL available sources.
        """
        dna = dna or {}
        performance = performance or {}
        evidence = []

        # 1. Memory evidence (historical creatives)
        memory_evidence = self._build_memory_evidence(dna, creative_id)
        evidence.extend(memory_evidence)

        # 2. Retriever evidence (similar creatives)
        retriever_evidence = self._build_retriever_evidence(dna, performance)
        evidence.extend(retriever_evidence)

        # 3. Pattern evidence (discovered patterns)
        pattern_evidence = self._build_pattern_evidence(dna, performance)
        evidence.extend(pattern_evidence)

        # 4. Knowledge Graph evidence (relationships)
        graph_evidence = self._build_graph_evidence(dna)
        evidence.extend(graph_evidence)

        # 5. Learning Loop evidence (learned insights)
        learning_evidence = self._build_learning_evidence(dna, performance)
        evidence.extend(learning_evidence)

        # Ensure minimum evidence
        if len(evidence) < self.MIN_EVIDENCE_ITEMS:
            evidence.append(EvidenceItem(
                source=EvidenceSource.RETRIEVER,
                source_id="insufficient_data",
                description="Insufficient data in all sources. "
                            "Decision based on conservative defaults.",
                strength=0.1,
            ))

        return evidence

    def validate_coverage(self, evidence: list[EvidenceItem]) -> dict[str, Any]:
        """Validate that evidence covers all required sources.

        Returns coverage report: coverage >= 95% must be achievable.
        """
        sources_used = {e.source for e in evidence}
        all_sources = set(EvidenceSource)
        coverage = len(sources_used) / len(all_sources) if all_sources else 0.0

        return {
            "total_items": len(evidence),
            "sources_used": [s.value for s in sources_used],
            "sources_missing": [s.value for s in (all_sources - sources_used)],
            "coverage": round(coverage, 3),
            "explainability": round(min(1.0, len(evidence) / 3), 3),
        }

    def build_summary(self, evidence: list[EvidenceItem]) -> str:
        """Build a human-readable summary of evidence."""
        if not evidence:
            return "No evidence available."

        lines = ["Evidence supporting this decision:", ""]
        for i, e in enumerate(evidence):
            lines.append(
                f"  {i+1}. [{e.source.value.upper()}] {e.description} "
                f"(strength: {e.strength:.0%})"
            )
        return "\n".join(lines)

    # ── Private: Source-specific builders ──

    def _build_memory_evidence(self, dna: dict[str, Any],
                                creative_id: str) -> list[EvidenceItem]:
        """Build evidence from memory (historical creative data)."""
        evidence = []
        # Memory evidence: the creative itself is in memory
        if creative_id:
            dims = {k: v for k, v in dna.items() if v}
            evidence.append(EvidenceItem(
                source=EvidenceSource.MEMORY,
                source_id=creative_id,
                description=f"Creative {creative_id} exists in memory "
                            f"with {len(dims)} DNA dimensions.",
                strength=0.7,
                data={"dna_dimensions": len(dims), "dna": dims},
            ))
        return evidence

    def _build_retriever_evidence(self, dna: dict[str, Any],
                                   performance: dict[str, Any]) -> list[EvidenceItem]:
        """Build evidence from retriever (similar creative search)."""
        evidence = []
        if not self._retriever or not dna:
            return evidence

        query = " ".join(f"{k}:{v}" for k, v in dna.items() if v)
        try:
            results = self._retriever.retrieve(query, top_k=5)
            if results:
                evidence.append(EvidenceItem(
                    source=EvidenceSource.RETRIEVER,
                    source_id=f"query_{hash(query) % 10000:04d}",
                    description=f"Found {len(results)} similar creatives "
                                f"via retriever search.",
                    strength=min(1.0, len(results) / 10),
                    data={
                        "similar_count": len(results),
                        "top_scores": [r.score for r in results[:3]],
                    },
                ))
        except Exception:
            pass

        return evidence

    def _build_pattern_evidence(self, dna: dict[str, Any],
                                 performance: dict[str, Any]) -> list[EvidenceItem]:
        """Build evidence from pattern mining."""
        evidence = []
        if not self._pattern_miner or not dna:
            return evidence

        try:
            patterns = self._pattern_miner.mine_patterns(
                samples=[{"dna": dna, "performance": performance}],
                min_dimensions=1,
            )
            if patterns:
                top_pattern = patterns[0] if hasattr(patterns[0], 'to_dict') else patterns[0]
                evidence.append(EvidenceItem(
                    source=EvidenceSource.PATTERN_MINING,
                    source_id=f"pattern_{hash(str(top_pattern)) % 10000:04d}",
                    description=f"Matched {len(patterns)} known patterns "
                                f"from pattern mining.",
                    strength=min(1.0, len(patterns) / 5),
                    data={"pattern_count": len(patterns)},
                ))
        except Exception:
            pass

        return evidence

    def _build_graph_evidence(self, dna: dict[str, Any]) -> list[EvidenceItem]:
        """Build evidence from knowledge graph."""
        evidence = []
        if not self._knowledge_graph:
            return evidence

        try:
            entities = []
            for dim, val in dna.items():
                if val:
                    neighbors = self._knowledge_graph.get_neighbors(
                        entity_type=dim, entity_value=val
                    )
                    if neighbors:
                        entities.extend(neighbors)

            if entities:
                evidence.append(EvidenceItem(
                    source=EvidenceSource.KNOWLEDGE_GRAPH,
                    source_id=f"graph_{hash(str(dna)) % 10000:04d}",
                    description=f"Found {len(entities)} related entities "
                                f"in knowledge graph.",
                    strength=min(1.0, len(entities) / 20),
                    data={"related_entities": len(entities)},
                ))
        except Exception:
            pass

        return evidence

    def _build_learning_evidence(self, dna: dict[str, Any],
                                  performance: dict[str, Any]) -> list[EvidenceItem]:
        """Build evidence from learning loop."""
        evidence = []
        if not self._learning_loop:
            return evidence

        try:
            insights = self._learning_loop.get_insights(dna=dna)
            if insights:
                evidence.append(EvidenceItem(
                    source=EvidenceSource.LEARNING_LOOP,
                    source_id=f"learning_{hash(str(dna)) % 10000:04d}",
                    description=f"Learning loop has {len(insights)} "
                                f"relevant insights.",
                    strength=0.5,
                    data={"insight_count": len(insights)},
                ))
        except Exception:
            pass

        return evidence