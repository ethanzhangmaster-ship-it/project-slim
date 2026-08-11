"""E17.7 Demo：E17.1 → E17.7 全链路 + 记忆图谱学习闭环（全 SIM）。

用法（从 launchforge/ 根目录）：
    python scripts/demo_e17_7_memory_graph.py
"""
import shutil
import tempfile
from pathlib import Path

from audit.trail import AuditTrail
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.registry import build_default_registry
from src.ceo_intelligence.execution_router.router import ApprovalOutbox, ExecutionRouter
from src.ceo_intelligence.growth_memory_graph.agent import (
    GrowthMemoryGraphAgent,
    run_pipeline,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="e17_7_demo_"))
    try:
        store = GrowthFeatureStore(root=str(tmp / "gr"))
        store.append(GrowthRealitySnapshot(
            "merge_witch", "d0",
            revenue=RevenueFact(5000, 50), creative=CreativeFact(0.03, 0.2, 80),
            confidence=1.0))
        store.append(GrowthRealitySnapshot(
            "merge_witch", "d1",
            revenue=RevenueFact(3500, 35), creative=CreativeFact(0.022, 0.85, 55),
            confidence=1.0))
        store.append(GrowthRealitySnapshot(
            "puzzle_island", "d0", aso=AsoFact(12, 0.05, 4.6, 4), confidence=1.0))
        store.append(GrowthRealitySnapshot(
            "puzzle_island", "d1", aso=AsoFact(12, 0.04, 4.6, 4), confidence=1.0))
        company = build_company_snapshot(
            [store.latest("merge_witch"), store.latest("puzzle_island")],
            "2026-07-29")

        graph = GrowthMemoryGraph(path=str(tmp / "memory_graph.jsonl"))
        router = ExecutionRouter(
            registry=build_default_registry(
                release_state_path=str(tmp / "release_state.json")),
            audit=AuditTrail(audit_dir=str(tmp / "audit")),
            memory=ExecutionMemory(str(tmp / "exec_mem.jsonl")),
            outbox=ApprovalOutbox(str(tmp / "outbox.jsonl")),
        )
        dec_report, portfolio, reports, graph_report = run_pipeline(
            company, graph=graph, store=store, execution_router=router,
            approval_queue_path=str(tmp / "q.jsonl"),
            audit_dir=str(tmp / "audit"), created_at="2026-07-29",
        )

        # 学习闭环：给 creative_refresh 链挂真实收入结果
        agent = GrowthMemoryGraphAgent(graph=graph)
        cr = next(r for r in reports if r.strategy_type == "creative_refresh")
        agent.record_outcome(cr.execution_id, 0.18, "创意刷新 7 日收入 +18%")

        print(agent.report().to_markdown())
        print()
        chain = agent.trace(cr.execution_id)
        print(f"链路回溯 {cr.execution_id}：")
        for nid in chain.node_ids:
            print(f"  {nid}")
        print()
        print(f"creative_refresh 置信度加成（回馈 E17.2 口径）："
              f"+{agent.confidence_boost_for('creative_refresh'):.4f}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
