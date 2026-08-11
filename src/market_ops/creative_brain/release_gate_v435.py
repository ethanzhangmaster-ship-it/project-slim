"""V4.3.5 Knowledge Lifecycle Engine — Release Gate.

Per PRD v1.0, 45 tests:
  1. Pattern Promotion (5)
  2. Pattern Retirement (5)
  3. Graph Update (5)
  4. Embedding Refresh (5)
  5. Retriever Rebuild (5)
  6. Confidence Rebuild (5)
  7. Version Management (5)
  8. Lineage Tracking (5)
  9. Lifecycle Engine (5)

Total: 45 tests. All must PASS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.knowledge_lifecycle.pattern_promoter import PatternPromoter
from market_ops.creative_brain.knowledge_lifecycle.pattern_retirer import PatternRetirer
from market_ops.creative_brain.knowledge_lifecycle.graph_updater import GraphUpdater
from market_ops.creative_brain.knowledge_lifecycle.trend_updater import TrendUpdater
from market_ops.creative_brain.knowledge_lifecycle.embedding_refresher import EmbeddingRefresher
from market_ops.creative_brain.knowledge_lifecycle.retriever_rebuilder import RetrieverRebuilder
from market_ops.creative_brain.knowledge_lifecycle.confidence_rebuilder import ConfidenceRebuilder
from market_ops.creative_brain.knowledge_lifecycle.knowledge_version import KnowledgeVersion
from market_ops.creative_brain.knowledge_lifecycle.lineage_tracker import LineageTracker
from market_ops.creative_brain.knowledge_lifecycle.lifecycle_engine import LifecycleEngine
from market_ops.creative_brain.knowledge_lifecycle.schemas import (
    PatternLifecycle, PatternStatus, TrendDirection, GraphUpdate, LifecycleReport,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_pattern(pattern_id: str = "p_001", **overrides) -> PatternLifecycle:
    """Create a synthetic pattern."""
    defaults = {
        "pattern_id": pattern_id,
        "name": pattern_id,
        "status": PatternStatus.CANDIDATE,
        "dna_dimensions": {"character": "dragon", "reward": "dragon"},
        "current_roas": 0.9,
        "peak_roas": 1.2,
        "roas_lift": 0.40,
        "consecutive_winner_days": 25,
        "consecutive_decline_days": 0,
        "confidence": 0.90,
        "supporting_creatives": ["c_001", "c_002"],
        "evidence_count": 15,
        "validation_accuracy": 0.75,
    }
    defaults.update(overrides)
    return PatternLifecycle(**defaults)


# ═══════════════════════════════════════════════════════════
# 1. Pattern Promotion (5 tests)
# ═══════════════════════════════════════════════════════════

def test_promoter_evaluate_qualified():
    """Promoter: 满足条件的候选→通过"""
    promoter = PatternPromoter()
    pattern = _make_pattern("p_001")
    should_promote, reason = promoter.evaluate(pattern)
    assert should_promote
    assert "All criteria met" in reason
    return True


def test_promoter_evaluate_fails_winner_days():
    """Promoter: Winner天数不足→不通过"""
    promoter = PatternPromoter(min_winner_days=20)
    pattern = _make_pattern("p_002", consecutive_winner_days=5)
    should_promote, reason = promoter.evaluate(pattern)
    assert not should_promote
    assert "winner_days" in reason
    return True


def test_promoter_evaluate_fails_roas_lift():
    """Promoter: ROAS Lift不足→不通过"""
    promoter = PatternPromoter(min_roas_lift=0.35)
    pattern = _make_pattern("p_003", roas_lift=0.10)
    should_promote, reason = promoter.evaluate(pattern)
    assert not should_promote
    assert "roas_lift" in reason
    return True


def test_promoter_promote():
    """Promoter: 执行Promote→状态变为PROMOTED"""
    promoter = PatternPromoter()
    pattern = _make_pattern("p_004")
    result = promoter.promote(pattern)
    assert result.status == PatternStatus.PROMOTED
    assert result.promoted_at != ""
    return True


def test_promoter_batch():
    """Promoter: 批量评估"""
    promoter = PatternPromoter()
    patterns = [
        _make_pattern("p_010", consecutive_winner_days=25, roas_lift=0.40),
        _make_pattern("p_011", consecutive_winner_days=5, roas_lift=0.10),
        _make_pattern("p_012", status=PatternStatus.ACTIVE, consecutive_winner_days=30),
    ]
    results = promoter.evaluate_batch(patterns)
    assert len(results) == 3
    promoted = promoter.get_promoted(results)
    assert len(promoted) == 1
    return True


# ═══════════════════════════════════════════════════════════
# 2. Pattern Retirement (5 tests)
# ═══════════════════════════════════════════════════════════

def test_retirer_evaluate_still_healthy():
    """Retirer: 健康Pattern→不退休"""
    retirer = PatternRetirer()
    pattern = _make_pattern("p_005", status=PatternStatus.ACTIVE,
                            current_roas=0.9, peak_roas=1.0,
                            consecutive_decline_days=0)
    should_retire, reason = retirer.evaluate(pattern)
    assert not should_retire
    return True


def test_retirer_evaluate_roas_decline():
    """Retirer: ROAS大幅下降→退休"""
    retirer = PatternRetirer(roas_decline_threshold=0.5)
    pattern = _make_pattern("p_006", status=PatternStatus.ACTIVE,
                            current_roas=0.3, peak_roas=1.4,
                            consecutive_decline_days=95)
    should_retire, reason = retirer.evaluate(pattern)
    assert should_retire
    return True


def test_retirer_evaluate_peak_decline():
    """Retirer: Peak下降比例触发退休"""
    retirer = PatternRetirer(peak_decline_ratio=0.4)
    pattern = _make_pattern("p_007", status=PatternStatus.ACTIVE,
                            current_roas=0.4, peak_roas=1.5,
                            consecutive_decline_days=100)
    should_retire, reason = retirer.evaluate(pattern)
    assert should_retire
    assert "ratio" in reason.lower()
    return True


def test_retirer_retire():
    """Retirer: 退休后状态→DEPRECATED"""
    retirer = PatternRetirer()
    pattern = _make_pattern("p_008", status=PatternStatus.ACTIVE,
                            current_roas=0.3, peak_roas=1.4,
                            consecutive_decline_days=95)
    result = retirer.retire(pattern)
    assert result.status == PatternStatus.DEPRECATED
    assert result.deprecated_at != ""
    return True


def test_retirer_already_deprecated():
    """Retirer: 已退休→不重复退休"""
    retirer = PatternRetirer()
    pattern = _make_pattern("p_009", status=PatternStatus.DEPRECATED,
                            current_roas=0.3, consecutive_decline_days=95)
    should_retire, reason = retirer.evaluate(pattern)
    assert not should_retire
    return True


# ═══════════════════════════════════════════════════════════
# 3. Graph Update (5 tests)
# ═══════════════════════════════════════════════════════════

def test_graph_add_edge():
    """Graph: 添加新边"""
    graph = GraphUpdater()
    update = graph.add_edge("Dragon", "Merge", "character_uses", weight=0.6)
    assert update.action == "add"
    assert graph.get_node_count() == 2
    assert graph.get_edge_count() == 1
    return True


def test_graph_strengthen_edge():
    """Graph: 强化已有边"""
    graph = GraphUpdater()
    graph.add_edge("Dragon", "Merge", "character_uses", weight=0.5)
    update = graph.add_edge("Dragon", "Merge", "character_uses", weight=0.3)
    assert update.action == "strengthen"
    assert update.weight > 0.5
    return True


def test_graph_weaken_edge():
    """Graph: 弱化边"""
    graph = GraphUpdater()
    graph.add_edge("Dragon", "Merge", "character_uses", weight=0.5)
    update = graph.weaken_edge("Dragon", "Merge", "character_uses", decay=0.3)
    assert update is not None
    assert update.weight < 0.5
    return True


def test_graph_remove_edge():
    """Graph: 权重过低→删除边"""
    graph = GraphUpdater()
    graph.add_edge("Dragon", "Merge", "character_uses", weight=0.1)
    update = graph.weaken_edge("Dragon", "Merge", "character_uses", decay=0.2)
    assert update.action == "remove"
    return True


def test_graph_validation_update():
    """Graph: 基于Validation反馈更新"""
    graph = GraphUpdater()
    feedback = [
        {"source": "Dragon", "target": "Merge", "relation": "uses",
         "accuracy": 0.8, "should_strengthen": True},
        {"source": "Witch", "target": "Sort", "relation": "uses",
         "accuracy": 0.3, "should_strengthen": False},
    ]
    updates = graph.update_from_validation(feedback)
    assert len(updates) >= 2
    return True


# ═══════════════════════════════════════════════════════════
# 4. Embedding Refresh (5 tests)
# ═══════════════════════════════════════════════════════════

def test_embedding_add():
    """Embedding: 添加新Embedding"""
    ref = EmbeddingRefresher(vector_dim=64)
    update = ref.add("c_001", {"character": "dragon", "reward": "dragon"})
    assert update.action == "add"
    assert len(update.embedding_vector) == 64
    assert ref.embedding_count == 1
    return True


def test_embedding_update():
    """Embedding: 更新已有Embedding"""
    ref = EmbeddingRefresher(vector_dim=64)
    ref.add("c_001", {"character": "dragon", "reward": "dragon"})
    update = ref.update("c_001", {"character": "dragon", "reward": "treasure"})
    assert update.action == "update"
    return True


def test_embedding_remove():
    """Embedding: 删除Embedding"""
    ref = EmbeddingRefresher(vector_dim=64)
    ref.add("c_001", {"character": "dragon"})
    update = ref.remove("c_001")
    assert update is not None
    assert ref.embedding_count == 0
    return True


def test_embedding_deterministic():
    """Embedding: 相同DNA→相同向量"""
    ref = EmbeddingRefresher(vector_dim=64)
    v1 = ref._encode_dna({"character": "dragon", "reward": "dragon"})
    v2 = ref._encode_dna({"character": "dragon", "reward": "dragon"})
    assert v1 == v2
    return True


def test_embedding_batch():
    """Embedding: 批量刷新"""
    ref = EmbeddingRefresher(vector_dim=64)
    creatives = [
        {"creative_id": "c_001", "dna": {"character": "dragon"}},
        {"creative_id": "c_002", "dna": {"character": "witch"}},
        {"creative_id": "c_003", "dna": {"character": "knight"}},
    ]
    updates = ref.refresh_batch(creatives)
    assert len(updates) == 3
    assert ref.embedding_count == 3
    return True


# ═══════════════════════════════════════════════════════════
# 5. Retriever Rebuild (5 tests)
# ═══════════════════════════════════════════════════════════

def test_retriever_rebuild():
    """Retriever: 全量重建"""
    rb = RetrieverRebuilder()
    embeddings = {
        "c_001": [0.1] * 64,
        "c_002": [0.5] * 64,
        "c_003": [0.9] * 64,
    }
    summary = rb.rebuild(embeddings, new_version="idx_v2.0")
    assert summary["new_count"] == 3
    assert rb.index_version == "idx_v2.0"
    return True


def test_retriever_incremental_update():
    """Retriever: 增量更新"""
    rb = RetrieverRebuilder()
    rb.rebuild({"c_001": [0.1] * 64, "c_002": [0.5] * 64})
    summary = rb.incremental_update(
        added={"c_003": [0.9] * 64},
        removed=["c_001"],
    )
    assert summary["added"] == 1
    assert summary["removed"] == 1
    assert rb.index_size == 2
    return True


def test_retriever_search():
    """Retriever: 搜索相似向量"""
    rb = RetrieverRebuilder()
    rb.rebuild({
        "c_001": [0.1] * 64,
        "c_002": [0.5] * 64,
        "c_003": [0.9] * 64,
    })
    results = rb.search([0.1] * 64, top_k=2)
    assert len(results) == 2
    assert results[0]["creative_id"] == "c_001"  # Most similar
    return True


def test_retriever_search_similarity():
    """Retriever: 相似度计算正确"""
    rb = RetrieverRebuilder()
    sim = rb._cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert abs(sim - 1.0) < 0.001
    sim = rb._cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert abs(sim) < 0.001
    return True


def test_retriever_version_tracking():
    """Retriever: 版本追踪"""
    rb = RetrieverRebuilder()
    rb.rebuild({"c_001": [0.1] * 64}, new_version="idx_v2.0")
    rb.rebuild({"c_001": [0.1] * 64, "c_002": [0.5] * 64}, new_version="idx_v3.0")
    assert rb.rebuild_count == 2
    assert len(rb.get_rebuild_history()) == 2
    return True


# ═══════════════════════════════════════════════════════════
# 6. Confidence Rebuild (5 tests)
# ═══════════════════════════════════════════════════════════

def test_confidence_calibrate_overconfident():
    """Confidence: 过度自信→校准因子<1"""
    cr = ConfidenceRebuilder()
    cal = cr.calibrate("pattern", original_confidence=0.95, actual_accuracy=0.68)
    assert cal.adjustment_factor < 1.0
    assert cal.gap > 0.1
    return True


def test_confidence_calibrate_underconfident():
    """Confidence: 信心不足→校准因子>1"""
    cr = ConfidenceRebuilder()
    cal = cr.calibrate("retriever", original_confidence=0.60, actual_accuracy=0.80)
    assert cal.adjustment_factor > 1.0
    return True


def test_confidence_calibrate_perfect():
    """Confidence: 完美校准→因子≈1"""
    cr = ConfidenceRebuilder()
    cal = cr.calibrate("graph", original_confidence=0.80, actual_accuracy=0.80)
    assert abs(cal.adjustment_factor - 1.0) < 0.05
    return True


def test_confidence_calibrated_output():
    """Confidence: 校准后置信度"""
    cr = ConfidenceRebuilder()
    cr.calibrate("pattern", original_confidence=0.95, actual_accuracy=0.68)
    calibrated = cr.get_calibrated_confidence("pattern", 0.95)
    assert calibrated < 0.95
    return True


def test_confidence_batch():
    """Confidence: 批量校准"""
    cr = ConfidenceRebuilder()
    feedback = [
        {"source": "pattern", "confidence": 0.90, "accuracy": 0.70, "samples": 50},
        {"source": "retriever", "confidence": 0.80, "accuracy": 0.75, "samples": 50},
        {"source": "graph", "confidence": 0.70, "accuracy": 0.72, "samples": 50},
    ]
    cals = cr.calibrate_batch(feedback)
    assert len(cals) == 3
    assert len(cr.get_calibration_summary()) == 3
    return True


# ═══════════════════════════════════════════════════════════
# 7. Version Management (5 tests)
# ═══════════════════════════════════════════════════════════

def test_version_snapshot():
    """Version: 创建快照"""
    kv = KnowledgeVersion()
    snap = kv.snapshot(pattern_count=10, active_patterns=["p1", "p2"],
                       graph_node_count=5, graph_edge_count=8,
                       embedding_count=100, summary="Initial")
    assert snap.version == "knowledge_v1.0"
    assert snap.pattern_count == 10
    return True


def test_version_increment():
    """Version: 版本自动递增"""
    kv = KnowledgeVersion()
    kv.snapshot(pattern_count=5, summary="v1")
    kv.snapshot(pattern_count=10, summary="v2")
    kv.snapshot(pattern_count=15, summary="v3")
    assert kv.version_count == 3
    assert kv.latest.version == "knowledge_v3.0"
    return True


def test_version_rollback():
    """Version: 回滚到指定版本"""
    kv = KnowledgeVersion()
    kv.snapshot(pattern_count=5, summary="v1")
    kv.snapshot(pattern_count=10, summary="v2")
    kv.snapshot(pattern_count=15, summary="v3")
    restored = kv.rollback("knowledge_v2.0")
    assert restored is not None
    assert restored.pattern_count == 10
    assert kv.current.version == "knowledge_v2.0"
    return True


def test_version_compare():
    """Version: 版本比较"""
    kv = KnowledgeVersion()
    kv.snapshot(pattern_count=5, graph_node_count=3, graph_edge_count=5,
                embedding_count=50, summary="v1")
    kv.snapshot(pattern_count=10, graph_node_count=5, graph_edge_count=8,
                embedding_count=100, summary="v2")
    diff = kv.compare_versions("knowledge_v1.0", "knowledge_v2.0")
    assert diff["pattern_diff"] == 5
    assert diff["graph_node_diff"] == 2
    return True


def test_version_list():
    """Version: 版本列表"""
    kv = KnowledgeVersion()
    kv.snapshot(pattern_count=5, summary="v1")
    kv.snapshot(pattern_count=10, summary="v2")
    versions = kv.list_versions()
    assert len(versions) == 2
    assert versions[0]["version"] == "knowledge_v1.0"
    assert versions[-1]["is_current"]
    return True


# ═══════════════════════════════════════════════════════════
# 8. Lineage Tracking (5 tests)
# ═══════════════════════════════════════════════════════════

def test_lineage_record():
    """Lineage: 记录知识来源"""
    lt = LineageTracker()
    record = lt.record("p_001", "pattern", source="facebook",
                       source_creative_id="c_318", version_added="knowledge_v1.0")
    assert record.knowledge_type == "pattern"
    assert record.source == "facebook"
    assert len(record.full_lineage) == 1
    return True


def test_lineage_validation():
    """Lineage: 添加验证步骤"""
    lt = LineageTracker()
    lt.record("p_001", "pattern", source="facebook")
    record = lt.add_validation("p_001", "confirmed", "knowledge_v2.0")
    assert record is not None
    assert record.validation_result == "confirmed"
    assert len(record.full_lineage) == 2
    return True


def test_lineage_update():
    """Lineage: 添加更新步骤"""
    lt = LineageTracker()
    lt.record("p_001", "pattern", source="facebook")
    lt.add_update("p_001", "ROAS updated from 0.8 to 1.2")
    record = lt.get_lineage("p_001")
    assert len(record.full_lineage) == 2
    return True


def test_lineage_retirement():
    """Lineage: 添加退休步骤"""
    lt = LineageTracker()
    lt.record("p_001", "pattern", source="facebook")
    lt.add_retirement("p_001", "ROAS dropped below 0.5", "knowledge_v3.0")
    record = lt.get_lineage("p_001")
    assert record.version_retired == "knowledge_v3.0"
    assert len(record.full_lineage) == 2
    return True


def test_lineage_filter():
    """Lineage: 按类型/来源过滤"""
    lt = LineageTracker()
    lt.record("p_001", "pattern", source="facebook")
    lt.record("e_001", "embedding", source="creative")
    lt.record("g_001", "graph_edge", source="reasoning")

    patterns = lt.get_by_type("pattern")
    assert len(patterns) == 1

    fb_items = lt.get_by_source("facebook")
    assert len(fb_items) == 1

    unvalidated = lt.get_unvalidated()
    assert len(unvalidated) == 3
    return True


# ═══════════════════════════════════════════════════════════
# 9. Lifecycle Engine (5 tests)
# ═══════════════════════════════════════════════════════════

def test_lifecycle_run():
    """Lifecycle: 完整生命周期运行"""
    engine = LifecycleEngine()
    patterns = [
        _make_pattern("p_001", name="Dragon Merge", consecutive_winner_days=25,
                      roas_lift=0.40, confidence=0.90),
        _make_pattern("p_002", name="Witch Sort", status=PatternStatus.ACTIVE,
                      current_roas=0.3, peak_roas=1.4, consecutive_decline_days=95),
    ]
    report = engine.run(
        patterns=patterns,
        graph_updates=[
            {"source": "Dragon", "target": "Merge", "relation": "uses",
             "accuracy": 0.8, "should_strengthen": True},
        ],
        embedding_creatives=[
            {"creative_id": "c_new", "dna": {"character": "dragon"}},
        ],
        trend_updates=[
            {"trend_id": "dragon_merge", "roas": 0.9},
        ],
        confidence_feedback=[
            {"source": "pattern", "confidence": 0.90, "accuracy": 0.72, "samples": 50},
        ],
        summary="Daily lifecycle run",
    )
    assert isinstance(report, LifecycleReport)
    assert report.patterns_promoted >= 0
    assert report.graph_edges_updated >= 0
    return True


def test_lifecycle_promote_and_retire():
    """Lifecycle: 同时Promote和Retire"""
    engine = LifecycleEngine()
    patterns = [
        _make_pattern("p_win", name="Dragon Merge", consecutive_winner_days=25,
                      roas_lift=0.40),
        _make_pattern("p_lose", name="Witch Sort", status=PatternStatus.ACTIVE,
                      current_roas=0.3, peak_roas=1.4, consecutive_decline_days=95),
    ]
    report = engine.run(patterns=patterns, summary="Test")
    assert report.patterns_promoted == 1
    assert report.patterns_retired == 1
    return True


def test_lifecycle_version_created():
    """Lifecycle: 运行后创建版本"""
    engine = LifecycleEngine()
    patterns = [_make_pattern("p_001")]
    report = engine.run(patterns=patterns, summary="Test")
    assert engine.version.version_count == 1
    assert report.version_to == "knowledge_v1.0"
    return True


def test_lifecycle_rollback():
    """Lifecycle: 回滚到之前版本"""
    engine = LifecycleEngine()
    engine.run(patterns=[_make_pattern("p_001")], summary="v1")
    engine.run(patterns=[_make_pattern("p_001"), _make_pattern("p_002")], summary="v2")
    result = engine.rollback("knowledge_v1.0")
    assert result is not None
    assert result["rolled_back_to"] == "knowledge_v1.0"
    return True


def test_lifecycle_status():
    """Lifecycle: 状态查询"""
    engine = LifecycleEngine()
    patterns = [_make_pattern("p_001")]
    engine.run(
        patterns=patterns,
        embedding_creatives=[{"creative_id": "c_001", "dna": {"character": "dragon"}}],
        summary="Test",
    )
    status = engine.get_status()
    assert "patterns" in status
    assert "graph" in status
    assert "embeddings" in status
    assert "version" in status
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Pattern Promotion (5)
        ("Promoter: Qualified", test_promoter_evaluate_qualified),
        ("Promoter: Days Fail", test_promoter_evaluate_fails_winner_days),
        ("Promoter: ROAS Fail", test_promoter_evaluate_fails_roas_lift),
        ("Promoter: Status Change", test_promoter_promote),
        ("Promoter: Batch", test_promoter_batch),
        # 2. Pattern Retirement (5)
        ("Retirer: Healthy", test_retirer_evaluate_still_healthy),
        ("Retirer: ROAS Decline", test_retirer_evaluate_roas_decline),
        ("Retirer: Peak Ratio", test_retirer_evaluate_peak_decline),
        ("Retirer: Status Change", test_retirer_retire),
        ("Retirer: Already Deprecated", test_retirer_already_deprecated),
        # 3. Graph Update (5)
        ("Graph: Add Edge", test_graph_add_edge),
        ("Graph: Strengthen", test_graph_strengthen_edge),
        ("Graph: Weaken", test_graph_weaken_edge),
        ("Graph: Remove", test_graph_remove_edge),
        ("Graph: Validation", test_graph_validation_update),
        # 4. Embedding Refresh (5)
        ("Embedding: Add", test_embedding_add),
        ("Embedding: Update", test_embedding_update),
        ("Embedding: Remove", test_embedding_remove),
        ("Embedding: Deterministic", test_embedding_deterministic),
        ("Embedding: Batch", test_embedding_batch),
        # 5. Retriever Rebuild (5)
        ("Retriever: Rebuild", test_retriever_rebuild),
        ("Retriever: Incremental", test_retriever_incremental_update),
        ("Retriever: Search", test_retriever_search),
        ("Retriever: Similarity", test_retriever_search_similarity),
        ("Retriever: Version", test_retriever_version_tracking),
        # 6. Confidence Rebuild (5)
        ("Confidence: Overconfident", test_confidence_calibrate_overconfident),
        ("Confidence: Underconfident", test_confidence_calibrate_underconfident),
        ("Confidence: Perfect", test_confidence_calibrate_perfect),
        ("Confidence: Calibrated Output", test_confidence_calibrated_output),
        ("Confidence: Batch", test_confidence_batch),
        # 7. Version Management (5)
        ("Version: Snapshot", test_version_snapshot),
        ("Version: Increment", test_version_increment),
        ("Version: Rollback", test_version_rollback),
        ("Version: Compare", test_version_compare),
        ("Version: List", test_version_list),
        # 8. Lineage Tracking (5)
        ("Lineage: Record", test_lineage_record),
        ("Lineage: Validation", test_lineage_validation),
        ("Lineage: Update", test_lineage_update),
        ("Lineage: Retirement", test_lineage_retirement),
        ("Lineage: Filter", test_lineage_filter),
        # 9. Lifecycle Engine (5)
        ("Lifecycle: Run", test_lifecycle_run),
        ("Lifecycle: Promote+Retire", test_lifecycle_promote_and_retire),
        ("Lifecycle: Version", test_lifecycle_version_created),
        ("Lifecycle: Rollback", test_lifecycle_rollback),
        ("Lifecycle: Status", test_lifecycle_status),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.3.5 Knowledge Lifecycle Engine — Release Gate")
    print("  Per PRD v1.0: 45 tests")
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