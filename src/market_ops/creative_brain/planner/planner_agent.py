"""V4.1 Planner Agent — the creative planning brain.

Pipeline:
  User Request → Retriever → Memory → Graph → Reasoning → Planning → Generator

Outputs:
  Image Plan, Video Plan, Prompt, Negative Prompt, Composition, Camera, Motion, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..memory.memory_center import MemoryCenter
from ..embedding.embedding_service import EmbeddingService
from ..vector_store.search_engine import SearchEngine
from ..knowledge_graph.graph_builder import GraphBuilder
from ..knowledge_graph.graph_reasoner import GraphReasoner
from ..pattern_mining.pattern_ranker import PatternRanker, WinnerPatternMiner, LoserPatternMiner
from .retrieval import Retriever
from .reasoning import Reasoner
from .planning import Planner


@dataclass
class PlanResult:
    request: str = ""
    plan_type: str = ""
    prompt: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    motion: dict[str, Any] = field(default_factory=dict)
    subtitle: dict[str, Any] = field(default_factory=dict)
    music: dict[str, Any] = field(default_factory=dict)
    retrieved: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    launch_ready: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "plan_type": self.plan_type,
            "prompt": self.prompt,
            "composition": self.composition,
            "camera": self.camera,
            "motion": self.motion,
            "subtitle": self.subtitle,
            "music": self.music,
            "retrieved_count": len(self.retrieved),
            "reasoning": self.reasoning,
            "launch_ready": self.launch_ready,
            "confidence": self.confidence,
        }


class PlannerAgent:
    """V4.1 Planner Agent — the creative planning brain.

    Usage:
        memory = MemoryCenter()
        agent = PlannerAgent(memory)
        result = agent.plan("Generate a dragon merge game ad for US market")
    """

    def __init__(self, memory: MemoryCenter | None = None,
                 embedder: EmbeddingService | None = None,
                 searcher: SearchEngine | None = None,
                 graph: GraphBuilder | None = None) -> None:
        self._memory = memory or MemoryCenter()
        self._embedder = embedder or EmbeddingService()
        self._searcher = searcher or SearchEngine()
        self._graph = graph or GraphBuilder()
        self._reasoner = GraphReasoner(self._graph)

        self._retriever = Retriever(self._memory, self._embedder, self._searcher)
        self._reasoning = Reasoner(self._graph, self._reasoner)
        self._planner = Planner()
        self._winner_miner = WinnerPatternMiner()
        self._loser_miner = LoserPatternMiner()

    def plan(self, request: str, plan_type: str = "image",
             **context) -> PlanResult:
        """Generate a creative plan from a user request."""
        # 1. Retrieve relevant memory
        retrieved = self._retriever.retrieve(request, top_k=5)

        # 2. Reason over graph
        reasoning = self._reasoning.reason(request, retrieved)

        # 3. Generate plan
        plan = self._planner.generate(request, plan_type, retrieved, reasoning, **context)

        return PlanResult(
            request=request,
            plan_type=plan_type,
            prompt=plan.get("prompt", {}),
            composition=plan.get("composition", {}),
            camera=plan.get("camera", {}),
            motion=plan.get("motion", {}),
            subtitle=plan.get("subtitle", {}),
            music=plan.get("music", {}),
            retrieved=[r.get("metadata", {}) for r in retrieved],
            reasoning=reasoning,
            launch_ready=plan.get("launch_ready", False),
            confidence=plan.get("confidence", 0.0),
        )

    def plan_image(self, request: str, **context) -> PlanResult:
        return self.plan(request, plan_type="image", **context)

    def plan_video(self, request: str, **context) -> PlanResult:
        return self.plan(request, plan_type="video", **context)

    def retrieve(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Retrieve relevant creative memory."""
        retrieved = self._retriever.retrieve(query, top_k=top_k)
        return [r.get("metadata", {}) for r in retrieved]

    def reason(self, query: str) -> str:
        """Reason about a creative query."""
        return self._reasoning.reason(query, [])

    def learn(self, creatives: list[dict[str, Any]]) -> dict[str, Any]:
        """Learn from creative performance data."""
        winners = self._winner_miner.mine(creatives)
        losers = self._loser_miner.mine(creatives)
        return {
            "winner_patterns": [w.to_dict() for w in winners],
            "loser_patterns": [l.to_dict() for l in losers],
            "total_creatives": len(creatives),
        }

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        return self.retrieve(query, top_k=top_k)

    def update(self, creative_id: str, **data) -> bool:
        return self._memory.creatives.update(creative_id, **data) is not None

    def graph(self) -> GraphBuilder:
        return self._graph

    def memory(self) -> MemoryCenter:
        return self._memory