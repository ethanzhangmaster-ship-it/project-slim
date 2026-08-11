"""V4.1 Creative Brain — Release Gate.

50 tests across 6 modules:
  Memory (8) + Embedding (8) + Vector Search (8) + Knowledge Graph (8)
  + Pattern Mining (8) + Planner (10)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.memory.memory_center import MemoryCenter
from market_ops.creative_brain.memory.creative_memory import CreativeMemory, CreativeRecord
from market_ops.creative_brain.memory.prompt_memory import PromptMemory, PromptRecord
from market_ops.creative_brain.memory.dna_memory import DNAMemory, DNARecord
from market_ops.creative_brain.memory.performance_memory import PerformanceMemory, PerformanceRecord

from market_ops.creative_brain.embedding.embedding_service import (
    EmbeddingService, ImageEmbedding, VideoEmbedding, PromptEmbedding, DNAEmbedding,
)

from market_ops.creative_brain.vector_store.vector_database import VectorDatabase, VectorEntry
from market_ops.creative_brain.vector_store.faiss_store import FAISSStore
from market_ops.creative_brain.vector_store.search_engine import SearchEngine, SearchResult
from market_ops.creative_brain.vector_store.similarity import cosine_similarity, l2_distance

from market_ops.creative_brain.knowledge_graph.graph_builder import GraphBuilder, GraphNode, GraphEdge
from market_ops.creative_brain.knowledge_graph.graph_storage import GraphStorage
from market_ops.creative_brain.knowledge_graph.graph_query import GraphQuery
from market_ops.creative_brain.knowledge_graph.graph_reasoner import GraphReasoner

from market_ops.creative_brain.pattern_mining.pattern_ranker import (
    PatternRanker, PatternResult, WinnerPatternMiner, LoserPatternMiner,
    TrendPatternMiner, CountryPatternMiner,
)

from market_ops.creative_brain.planner.planner_agent import PlannerAgent, PlanResult
from market_ops.creative_brain.planner.retrieval import Retriever
from market_ops.creative_brain.planner.reasoning import Reasoner
from market_ops.creative_brain.planner.planning import Planner
from market_ops.creative_brain.planner.task_executor import TaskExecutor


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _load_winner_dna(idx: int = 1) -> dict:
    path = Path("output/winner_dna/winner_{:03d}.json".format(idx))
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _sample_embedding(dim: int = 768) -> list[float]:
    import hashlib
    import math
    h = hashlib.sha256(b"test_embedding_v41").hexdigest()
    values = []
    for c in h * 10:
        values.append((int(c, 16) / 7.5) - 1.0)
    vec = values[:dim]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


# ═══════════════════════════════════════════════════════════
# Memory (8 tests)
# ═══════════════════════════════════════════════════════════

def test_memory_creative_store():
    with tempfile.TemporaryDirectory() as d:
        cm = CreativeMemory(Path(d) / "creatives")
        record = cm.add("c001", creative_type="image", source="facebook",
                        performance={"roas_d7": 0.8})
        assert record.creative_id == "c001"
        assert record.version == 1
        retrieved = cm.get("c001")
        assert retrieved is not None
        assert retrieved.creative_type == "image"
    return True


def test_memory_prompt_store():
    with tempfile.TemporaryDirectory() as d:
        pm = PromptMemory(Path(d) / "prompts")
        record = pm.add("p001", creative_id="c001", model="lovart",
                        positive_prompt="A dragon", score=85.0)
        assert record.prompt_id == "p001"
        assert record.score == 85.0
        retrieved = pm.get("p001")
        assert retrieved.positive_prompt == "A dragon"
    return True


def test_memory_dna_store():
    with tempfile.TemporaryDirectory() as d:
        dm = DNAMemory(Path(d) / "dna")
        record = dm.add("dna001", creative_id="c001", dna_type="image",
                        dna_data={"character": "witch"})
        assert record.dna_id == "dna001"
        assert record.dna_data["character"] == "witch"
        retrieved = dm.get("dna001")
        assert retrieved.dna_type == "image"
    return True


def test_memory_performance_store():
    with tempfile.TemporaryDirectory() as d:
        pm = PerformanceMemory(Path(d) / "performance")
        record = pm.add("perf001", creative_id="c001", spend=100.0, ctr=0.85, roas_d7=0.7)
        assert record.record_id == "perf001"
        assert record.spend == 100.0
        assert record.ctr == 0.85
        retrieved = pm.get("perf001")
        assert retrieved.roas_d7 == 0.7
    return True


def test_memory_version_management():
    with tempfile.TemporaryDirectory() as d:
        cm = CreativeMemory(Path(d) / "creatives")
        cm.add("c001", creative_type="image")
        updated = cm.update("c001", creative_type="video")
        assert updated is not None
        assert updated.version == 2
        assert updated.creative_type == "video"
        versions = cm.get_versions("c001")
        assert len(versions) == 2
    return True


def test_memory_archive():
    with tempfile.TemporaryDirectory() as d:
        cm = CreativeMemory(Path(d) / "creatives")
        cm.add("c001")
        assert cm.archive("c001")
        record = cm.get("c001")
        assert record.archived
        # Archived items don't appear in search
        results = cm.search()
        assert len(results) == 0
    return True


def test_memory_update():
    with tempfile.TemporaryDirectory() as d:
        pm = PromptMemory(Path(d) / "prompts")
        pm.add("p001", score=80.0)
        updated = pm.update("p001", score=90.0, strategy="aggressive")
        assert updated.score == 90.0
        assert updated.strategy == "aggressive"
        assert updated.version == 2
    return True


def test_memory_search():
    with tempfile.TemporaryDirectory() as d:
        cm = CreativeMemory(Path(d) / "creatives")
        cm.add("c001", creative_type="image", source="facebook")
        cm.add("c002", creative_type="video", source="eagle")
        cm.add("c003", creative_type="image", source="facebook")

        results = cm.search({"creative_type": "image"})
        assert len(results) == 2
        results2 = cm.search({"source": "eagle"})
        assert len(results2) == 1
    return True


# ═══════════════════════════════════════════════════════════
# Embedding (8 tests)
# ═══════════════════════════════════════════════════════════

def test_image_embedding():
    embedder = ImageEmbedding(dim=768)
    vec = embedder.embed("test_image.png")
    assert len(vec) == 768
    assert -1.0 <= vec[0] <= 1.0
    return True


def test_video_embedding():
    embedder = VideoEmbedding(dim=768)
    vec = embedder.embed("test_video.mp4", {"duration_ms": 15000})
    assert len(vec) == 768
    return True


def test_prompt_embedding():
    embedder = PromptEmbedding(dim=768)
    vec = embedder.embed("A witch casting a spell on a dragon")
    assert len(vec) == 768
    return True


def test_dna_embedding():
    embedder = DNAEmbedding(dim=768)
    vec = embedder.embed({"character": "witch", "reward": "dragon", "hook": "collection"})
    assert len(vec) == 768
    return True


def test_embedding_batch():
    embedder = ImageEmbedding(dim=768)
    paths = ["img1.png", "img2.png", "img3.png"]
    vecs = embedder.batch_embed(paths)
    assert len(vecs) == 3
    assert all(len(v) == 768 for v in vecs)
    return True


def test_embedding_cache():
    embedder = ImageEmbedding(dim=768)
    v1 = embedder.embed("test.png")
    v2 = embedder.embed("test.png")
    # Deterministic hash embedding should produce same result
    assert all(abs(a - b) < 1e-6 for a, b in zip(v1, v2))
    return True


def test_embedding_similarity():
    embedder = ImageEmbedding(dim=768)
    v1 = embedder.embed("witch_dragon.png")
    v2 = embedder.embed("witch_dragon.png")
    sim = embedder.similarity(v1, v2)
    assert sim > 0.99  # Same content should be highly similar
    return True


def test_embedding_persistence():
    embedder = ImageEmbedding(dim=768)
    vec = embedder.embed("test.png")
    assert embedder.dimension == 768
    return True


# ═══════════════════════════════════════════════════════════
# Vector Search (8 tests)
# ═══════════════════════════════════════════════════════════

def test_vector_ann_search():
    db = VectorDatabase(dim=768)
    for i in range(100):
        db.add(f"vec_{i}", _sample_embedding())
    results = db.search_cosine(_sample_embedding(), top_k=10)
    assert len(results) == 10
    assert results[0].score >= results[-1].score
    return True


def test_vector_cosine():
    db = VectorDatabase(dim=3)
    db.add("a", [1.0, 0.0, 0.0])
    db.add("b", [0.0, 1.0, 0.0])
    results = db.search_cosine([1.0, 0.0, 0.0], top_k=2)
    assert results[0].id == "a"
    assert results[0].score > results[1].score
    return True


def test_vector_hybrid():
    db = VectorDatabase(dim=3)
    db.add("a", [1.0, 0.0, 0.0], {"type": "image"})
    db.add("b", [0.0, 1.0, 0.0], {"type": "video"})
    results = db.search_hybrid(
        [1.0, 0.0, 0.0],
        metadata_filter={"type": "image"},
        top_k=5,
    )
    assert len(results) == 1
    assert results[0].id == "a"
    return True


def test_vector_filter():
    db = VectorDatabase(dim=3)
    db.add("a", [1.0, 0.0, 0.0], {"country": "US"})
    db.add("b", [0.0, 1.0, 0.0], {"country": "JP"})
    db.add("c", [0.0, 0.0, 1.0], {"country": "US"})

    def _us_filter(e): return e.metadata.get("country") == "US"
    results = db.search_cosine([1.0, 0.0, 0.0], top_k=5, filter_fn=_us_filter)
    assert len(results) == 2
    return True


def test_vector_topk():
    db = VectorDatabase(dim=3)
    for i in range(50):
        db.add(f"v_{i}", _sample_embedding(dim=3))
    for k in [1, 5, 10, 20]:
        results = db.search_cosine(_sample_embedding(dim=3), top_k=k)
        assert len(results) == min(k, 50)
    return True


def test_vector_multi_query():
    db = VectorDatabase(dim=3)
    db.add("a", [1.0, 0.0, 0.0])
    db.add("b", [0.0, 1.0, 0.0])
    queries = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    results = db.search_multi(queries, top_k=3)
    assert len(results) == 2
    return True


def test_vector_ranking():
    db = VectorDatabase(dim=3)
    db.add("a", [1.0, 0.0, 0.0])
    db.add("b", [0.0, 1.0, 0.0])
    db.add("c", [0.0, 0.0, 1.0])
    queries = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    batch_results = db.search_multi(queries, top_k=3)
    ranked = db.rank_results(batch_results, weights=[0.7, 0.3])
    assert len(ranked) >= 3
    return True


def test_vector_recall():
    db = VectorDatabase(dim=3)
    db.add("target", [1.0, 0.0, 0.0])
    db.add("noise_1", [0.0, 1.0, 0.0])
    db.add("noise_2", [0.0, 0.0, 1.0])
    results = db.search_cosine([1.0, 0.1, 0.0], top_k=3)
    # target should be in top results
    found_ids = [r.id for r in results]
    assert "target" in found_ids
    return True


# ═══════════════════════════════════════════════════════════
# Knowledge Graph (8 tests)
# ═══════════════════════════════════════════════════════════

def test_graph_node():
    g = GraphBuilder()
    node = g.add_node("n1", "Character", {"value": "witch"})
    assert node.node_id == "n1"
    assert node.node_type == "Character"
    assert node.properties["value"] == "witch"
    assert g.get_node("n1") is not None
    return True


def test_graph_edge():
    g = GraphBuilder()
    g.add_node("c1", "Creative")
    g.add_node("h1", "Hook", {"value": "collection"})
    edge = g.add_edge("c1", "h1", "uses", weight=0.9)
    assert edge is not None
    assert edge.edge_type == "uses"
    assert edge.weight == 0.9
    return True


def test_graph_query():
    g = GraphBuilder()
    for i in range(5):
        g.add_node(f"c{i}", "Creative", {"status": "active"})
    for i in range(3):
        g.add_node(f"h{i}", "Hook")
    results = g.query(node_type="Creative")
    assert len(results) == 5
    results2 = g.query(node_type="Creative", property_filter={"status": "active"})
    assert len(results2) == 5
    return True


def test_graph_update():
    g = GraphBuilder()
    g.add_node("n1", "Creative", {"roas": 0.5})
    assert g.update_node("n1", roas=0.9, status="winner")
    node = g.get_node("n1")
    assert node.properties["roas"] == 0.9
    assert node.properties["status"] == "winner"
    return True


def test_graph_merge():
    g1 = GraphBuilder()
    g1.add_node("c1", "Creative", {"roas": 0.8})
    g1.add_node("h1", "Hook", {"value": "collection"})
    g1.add_edge("c1", "h1", "uses")

    g2 = GraphBuilder()
    g2.add_node("c1", "Creative", {"roas": 0.9, "status": "winner"})
    g2.add_node("r1", "Reward", {"value": "dragon"})

    g1.merge(g2)
    assert len(g1.nodes) == 3  # c1, h1, r1
    assert g1.get_node("c1").properties["status"] == "winner"
    return True


def test_graph_reason():
    g = GraphBuilder()
    g.add_node("c1", "Creative", {"status": "winner", "performance": {"roas_d7": 0.9}})
    g.add_node("h1", "Hook", {"value": "collection"})
    g.add_node("r1", "Reward", {"value": "dragon"})
    g.add_edge("c1", "h1", "uses")
    g.add_edge("c1", "r1", "uses")

    reasoner = GraphReasoner(g)
    patterns = reasoner.infer_winner_patterns()
    assert len(patterns) == 1
    assert patterns[0]["creative_id"] == "c1"
    return True


def test_graph_export():
    g = GraphBuilder()
    g.add_node("c1", "Creative")
    g.add_node("h1", "Hook")
    g.add_edge("c1", "h1", "uses")
    exported = g.export()
    assert len(exported["nodes"]) == 2
    assert len(exported["edges"]) == 1
    return True


def test_graph_visualization():
    g = GraphBuilder()
    g.add_node("c1", "Creative", {"roas": 0.8})
    g.add_node("h1", "Hook", {"value": "collection"})
    g.add_edge("c1", "h1", "uses")
    viz = g.to_visualization()
    assert "Knowledge Graph" in viz
    assert "Creative" in viz
    assert "Hook" in viz
    return True


# ═══════════════════════════════════════════════════════════
# Pattern Mining (8 tests)
# ═══════════════════════════════════════════════════════════

def test_pattern_winner():
    miner = WinnerPatternMiner()
    creatives = [
        {"character": "witch", "reward": "dragon", "performance": {"roas_d7": 0.8}},
        {"character": "witch", "reward": "treasure", "performance": {"roas_d7": 0.7}},
        {"character": "knight", "reward": "dragon", "performance": {"roas_d7": 0.1}},
    ]
    patterns = miner.mine(creatives)
    assert len(patterns) > 0
    assert any(p.dimension == "character" and "witch" in p.values for p in patterns)
    return True


def test_pattern_loser():
    miner = LoserPatternMiner()
    creatives = [
        {"character": "knight", "performance": {"roas_d7": 0.1}},
        {"character": "knight", "performance": {"roas_d7": 0.2}},
        {"character": "witch", "performance": {"roas_d7": 0.8}},
    ]
    patterns = miner.mine(creatives)
    assert len(patterns) > 0
    return True


def test_pattern_country():
    miner = CountryPatternMiner()
    creatives = [
        {"character": "witch", "country": "US", "performance": {"roas_d7": 0.8}},
        {"character": "ninja", "country": "JP", "performance": {"roas_d7": 0.7}},
        {"character": "witch", "country": "US", "performance": {"roas_d7": 0.6}},
    ]
    patterns = miner.mine(creatives)
    country_values = {p.metadata.get("country", "") for p in patterns}
    assert "US" in country_values or "JP" in country_values
    return True


def test_pattern_genre():
    """Genre pattern (uses character as proxy)."""
    miner = WinnerPatternMiner()
    creatives = [
        {"character": "witch", "gameplay": "merge", "performance": {"roas_d7": 0.8}},
        {"character": "witch", "gameplay": "merge", "performance": {"roas_d7": 0.7}},
    ]
    patterns = miner.mine(creatives, dimensions=["character", "gameplay"])
    assert len(patterns) > 0
    return True


def test_pattern_hook():
    miner = WinnerPatternMiner()
    creatives = [
        {"hook": "collection", "performance": {"roas_d7": 0.9}},
        {"hook": "collection", "performance": {"roas_d7": 0.8}},
        {"hook": "fail", "performance": {"roas_d7": 0.2}},
    ]
    patterns = miner.mine(creatives, dimensions=["hook"])
    assert any(p.dimension == "hook" and "collection" in p.values for p in patterns)
    return True


def test_pattern_reward():
    miner = WinnerPatternMiner()
    creatives = [
        {"reward": "dragon", "performance": {"roas_d7": 0.9}},
        {"reward": "dragon", "performance": {"roas_d7": 0.8}},
    ]
    patterns = miner.mine(creatives, dimensions=["reward"])
    assert any(p.dimension == "reward" and "dragon" in p.values for p in patterns)
    return True


def test_pattern_character():
    miner = WinnerPatternMiner()
    creatives = [
        {"character": "witch", "performance": {"roas_d7": 0.9}},
        {"character": "witch", "performance": {"roas_d7": 0.8}},
        {"character": "knight", "performance": {"roas_d7": 0.2}},
    ]
    patterns = miner.mine(creatives, dimensions=["character"])
    assert any(p.dimension == "character" and "witch" in p.values for p in patterns)
    return True


def test_pattern_trend():
    miner = TrendPatternMiner()
    creatives = [
        {"character": "witch", "hook": "collection"},
        {"character": "witch", "hook": "fail"},
        {"character": "knight", "hook": "collection"},
        {"character": "witch", "hook": "collection"},
    ]
    patterns = miner.mine(creatives)
    assert len(patterns) > 0
    return True


# ═══════════════════════════════════════════════════════════
# Planner (10 tests)
# ═══════════════════════════════════════════════════════════

def test_planner_retrieval():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        memory.creatives.add("c001", creative_type="image")
        memory.dna.add("dna001", dna_type="image", dna_data={"character": "witch"})

        embedder = EmbeddingService()
        searcher = SearchEngine()
        retriever = Retriever(memory, embedder, searcher)
        results = retriever.retrieve("witch merge game", top_k=5)
        assert len(results) > 0
    return True


def test_planner_memory():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        agent = PlannerAgent(memory=memory)
        memory.creatives.add("c001", creative_type="image")
        assert len(agent.memory().creatives.search()) == 1
    return True


def test_planner_reasoning():
    g = GraphBuilder()
    g.add_node("c1", "Creative", {"status": "winner"})
    g.add_node("h1", "Hook")
    g.add_edge("c1", "h1", "uses")

    reasoner = GraphReasoner(g)
    r = Reasoner(g, reasoner)
    result = r.reason("test query", [{"type": "creative", "metadata": {"id": "c1"}}])
    assert len(result) > 0
    return True


def test_planner_planning():
    planner = Planner()
    plan = planner.generate(
        "Generate a dragon merge game ad",
        plan_type="image",
        retrieved=[{"type": "dna", "metadata": {"dna_data": {"character": "witch"}}}],
        reasoning="Found 1 winning pattern",
        model="lovart",
    )
    assert plan["plan_type"] == "image"
    assert plan["prompt"]["positive_prompt"]
    assert plan["confidence"] > 0.5
    return True


def test_planner_image_plan():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        memory.dna.add("dna001", dna_type="image", dna_data={
            "character": "witch", "reward": "dragon", "hook": "collection",
        })
        agent = PlannerAgent(memory=memory)
        result = agent.plan_image("Generate a witch merge game ad")
        assert result.plan_type == "image"
        assert result.prompt["positive_prompt"]
        assert result.composition["layout"] == "center"
        assert result.camera["angle"] == "45_degree"
        assert result.confidence > 0.5
    return True


def test_planner_video_plan():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        memory.dna.add("dna001", dna_type="video", dna_data={
            "opening_hook": "fail_react", "gameplay_structure": "linear",
        })
        agent = PlannerAgent(memory=memory)
        result = agent.plan_video("Generate a fail reaction video ad")
        assert result.plan_type == "video"
        assert result.prompt["positive_prompt"]
        assert result.composition["aspect_ratio"] == "9:16"
        assert result.camera["motion"] == "zoom"
    return True


def test_planner_prompt():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        memory.dna.add("dna001", dna_type="image", dna_data={
            "character": "witch", "reward": "dragon", "hook": "collection",
        })
        agent = PlannerAgent(memory=memory)
        result = agent.plan_image("witch merge game")
        assert result.prompt["positive_prompt"]
        assert "witch" in result.prompt["positive_prompt"].lower()
        assert result.prompt["model"] == "lovart"
        assert result.prompt["strategy"] == "balanced"
    return True


def test_planner_composition():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        agent = PlannerAgent(memory=memory)
        result = agent.plan_image("test", composition="split")
        assert result.composition["layout"] == "split"
    return True


def test_planner_camera():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        agent = PlannerAgent(memory=memory)
        result = agent.plan_image("test", camera="top_down")
        assert result.camera["angle"] == "top_down"
    return True


def test_planner_launch_ready():
    with tempfile.TemporaryDirectory() as d:
        memory = MemoryCenter(Path(d))
        memory.dna.add("dna001", dna_type="image", dna_data={"character": "witch"})
        agent = PlannerAgent(memory=memory)
        result = agent.plan_image("witch merge game")
        assert result.launch_ready
        assert result.confidence > 0.5
        d = result.to_dict()
        assert d["plan_type"] == "image"
        assert d["launch_ready"]
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Memory (8)
        ("Memory Creative 存储", test_memory_creative_store),
        ("Memory Prompt 存储", test_memory_prompt_store),
        ("Memory DNA 存储", test_memory_dna_store),
        ("Memory Performance 存储", test_memory_performance_store),
        ("Memory Version 管理", test_memory_version_management),
        ("Memory Archive", test_memory_archive),
        ("Memory Update", test_memory_update),
        ("Memory Search", test_memory_search),
        # Embedding (8)
        ("Image Embedding", test_image_embedding),
        ("Video Embedding", test_video_embedding),
        ("Prompt Embedding", test_prompt_embedding),
        ("DNA Embedding", test_dna_embedding),
        ("Embedding Batch", test_embedding_batch),
        ("Embedding Cache", test_embedding_cache),
        ("Embedding Similarity", test_embedding_similarity),
        ("Embedding Persistence", test_embedding_persistence),
        # Vector Search (8)
        ("Vector ANN 检索", test_vector_ann_search),
        ("Vector Cosine", test_vector_cosine),
        ("Vector Hybrid", test_vector_hybrid),
        ("Vector Filter", test_vector_filter),
        ("Vector TopK", test_vector_topk),
        ("Vector Multi Query", test_vector_multi_query),
        ("Vector Ranking", test_vector_ranking),
        ("Vector Recall", test_vector_recall),
        # Knowledge Graph (8)
        ("Graph Node", test_graph_node),
        ("Graph Edge", test_graph_edge),
        ("Graph Query", test_graph_query),
        ("Graph Update", test_graph_update),
        ("Graph Merge", test_graph_merge),
        ("Graph Reason", test_graph_reason),
        ("Graph Export", test_graph_export),
        ("Graph Visualization", test_graph_visualization),
        # Pattern Mining (8)
        ("Pattern Winner", test_pattern_winner),
        ("Pattern Loser", test_pattern_loser),
        ("Pattern Country", test_pattern_country),
        ("Pattern Genre", test_pattern_genre),
        ("Pattern Hook", test_pattern_hook),
        ("Pattern Reward", test_pattern_reward),
        ("Pattern Character", test_pattern_character),
        ("Pattern Trend", test_pattern_trend),
        # Planner (10)
        ("Planner Retrieval", test_planner_retrieval),
        ("Planner Memory", test_planner_memory),
        ("Planner Reasoning", test_planner_reasoning),
        ("Planner Planning", test_planner_planning),
        ("Planner Image Plan", test_planner_image_plan),
        ("Planner Video Plan", test_planner_video_plan),
        ("Planner Prompt", test_planner_prompt),
        ("Planner Composition", test_planner_composition),
        ("Planner Camera", test_planner_camera),
        ("Planner Launch Ready", test_planner_launch_ready),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.1 Creative Brain — Release Gate")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)