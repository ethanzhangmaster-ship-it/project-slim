"""E17.8 Growth Simulation Engine — demo（SIM，确定性，无真实 API）。

演示三级执行门中的 Simulation 门：
1) 无记忆 → 全放行，组合 p10/p50/p90
2) 图谱里 creative_refresh 亏损记忆 → 先验拉负 → 闸门 BLOCK，计划不进 E17.6

跑法（launchforge/ 根目录）：
  python scripts/demo_e17_8_simulation_engine.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ceo_intelligence.growth_memory_graph.models import (  # noqa: E402
    GraphNode, NodeType, node_id,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph  # noqa: E402
from src.ceo_intelligence.simulation_engine.agent import run_pipeline  # noqa: E402
from src.growth_reality.feature_store import GrowthFeatureStore  # noqa: E402
from src.growth_reality.models import (  # noqa: E402
    AsoFact, CreativeFact, GrowthRealitySnapshot, RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot  # noqa: E402


def build_company(root: Path):
    store = GrowthFeatureStore(root=str(root / "gr"))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d0",
        revenue=RevenueFact(5000, 50), creative=CreativeFact(0.03, 0.2, 80),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d1",
        revenue=RevenueFact(3500, 35), creative=CreativeFact(0.022, 0.85, 55),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d0", aso=AsoFact(12, 0.05, 4.6, 4), confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d1", aso=AsoFact(12, 0.04, 4.6, 4), confidence=1.0,
    ))
    company = build_company_snapshot(
        [store.latest("merge_witch"), store.latest("puzzle_island")], "2026-07-29"
    )
    return store, company


def poisoned_graph(root: Path) -> GrowthMemoryGraph:
    g = GrowthMemoryGraph(path=str(root / "graph.jsonl"))
    g.add_node(GraphNode(
        id=node_id(NodeType.EXECUTION, "e1"), type=NodeType.EXECUTION,
        label="exec e1", payload={"execution_id": "e1", "revenue_delta": -0.60},
    ))
    for i in range(2):
        g.add_node(GraphNode(
            id=node_id(NodeType.RESULT, f"r{i}"), type=NodeType.RESULT,
            label=f"result {i}",
            payload={
                "strategy_type": "creative_refresh", "domain": "creative",
                "action_type": "SAFE", "success": False, "execution_id": "e1",
            },
        ))
    return g


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        print("=" * 68)
        print("场景 1：无记忆先验（纯静态基线）")
        print("=" * 68)
        store, company = build_company(root / "a")
        _, portfolio, sim_report, exec_reports = run_pipeline(
            company, store=store,
            approval_queue_path=str(root / "a/q.jsonl"),
            audit_dir=str(root / "a/audit"),
            created_at="2026-07-29",
        )
        print(sim_report.to_markdown())
        print(f"\n执行报告：{len(exec_reports)} 条（计划 {len(portfolio.plans)} 条）")

        print()
        print("=" * 68)
        print("场景 2：记忆图谱有 creative_refresh 亏损史（-60%）→ 闸门 BLOCK")
        print("=" * 68)
        store, company = build_company(root / "b")
        graph = poisoned_graph(root / "b")
        _, portfolio, sim_report, exec_reports = run_pipeline(
            company, store=store, memory_graph=graph,
            approval_queue_path=str(root / "b/q.jsonl"),
            audit_dir=str(root / "b/audit"),
            created_at="2026-07-29",
        )
        print(sim_report.to_markdown())
        print(f"\n被阻断决策：{sim_report.blocked_decision_ids()}")
        print(f"执行报告：{len(exec_reports)} 条（计划 {len(portfolio.plans)} 条，"
              f"BLOCK 的计划未进入执行层）")
        assert sim_report.summary["real_api_called"] is False
        print("\nSIM 纪律：real_api_called=False ✔")


if __name__ == "__main__":
    main()
