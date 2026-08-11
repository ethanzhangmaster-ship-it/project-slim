"""E17.10 Portfolio Dashboard — demo（SIM，确定性，无真实 API）。

四场景：
  1) 12 游戏舰队 → 一键端到端（E17.9 pipeline → 聚合 → Markdown/HTML/JSON 落盘）
  2) 记忆图谱接入：成功模式 → learned_patterns + memory_summary 出现在仪表盘
  3) 毒图谱：creative 域连败 → 闸门 BLOCK → 风险旗标 + 决策队列「已阻断」
  4) 确定性：同输入两次聚合 → to_dict 完全一致

运行（从 launchforge/ 根目录）：
  python scripts/demo_e17_10_portfolio_dashboard.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ceo_intelligence.daily_operator.agent import DailyGrowthOperatorAgent
from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
from src.ceo_intelligence.daily_operator.pipeline import DailyGrowthPipeline
from src.ceo_intelligence.growth_memory_graph.models import (
    GraphNode,
    NodeType,
    node_id,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.ceo_intelligence.portfolio_dashboard.agent import PortfolioDashboardAgent
from src.ceo_intelligence.portfolio_dashboard.notifier import FileNotifier
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AcquisitionFact,
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    ProductFact,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot

DATE = "2026-07-29"


# --------------------------------------------------------------------------- #
# 数据构造（复用 E17.9 demo 思路）
# --------------------------------------------------------------------------- #
def _snapshots(gid: str, i: int):
    rev, dau, roas, spend = 1000.0, 3000 + i, 2.0, 100.0
    conf = 0.6 + (i % 3) * 0.1
    d0 = GrowthRealitySnapshot(
        gid, "d0",
        revenue=RevenueFact(daily_revenue=rev, payer_count=10),
        acquisition=AcquisitionFact(spend=spend, installs=1000, cpi=0.1, roas=roas),
        creative=CreativeFact(ctr=0.05, fatigue_score=0.30, creative_score=0.60),
        aso=AsoFact(ranking=10, store_cvr=0.10, rating=3.5, review_velocity=4.0),
        product=ProductFact(dau=dau, retention=0.3, conversion=0.02),
        confidence=conf, sources=["sim"],
    )
    rev1, roas1, spend1, ctr1, fatigue1, cvr1, rating1 = (
        rev, roas, spend, 0.05, 0.30, 0.10, 3.5,
    )
    p = i % 4
    if p == 0:
        rev1 = rev * (1 - (0.20 + (i % 5) * 0.04))
    elif p == 1:
        roas1 = roas * (1 - (0.15 + (i % 5) * 0.04))
        spend1 = spend * (1 + (0.20 + (i % 5) * 0.04))
    elif p == 2:
        ctr1 = 0.05 * (1 - (0.20 + (i % 5) * 0.04))
        fatigue1 = min(0.95, 0.70 + (i % 5) * 0.05)
    else:
        cvr1 = 0.10 * (1 - (0.15 + (i % 5) * 0.04))
        rating1 = 4.5
    d1 = GrowthRealitySnapshot(
        gid, "d1",
        revenue=RevenueFact(daily_revenue=rev1, payer_count=10),
        acquisition=AcquisitionFact(spend=spend1, installs=1000, cpi=0.1, roas=roas1),
        creative=CreativeFact(ctr=ctr1, fatigue_score=fatigue1, creative_score=0.60),
        aso=AsoFact(ranking=10, store_cvr=cvr1, rating=rating1, review_velocity=4.0),
        product=ProductFact(dau=dau, retention=0.3, conversion=0.02),
        confidence=conf, sources=["sim"],
    )
    return d0, d1


def _make_store(root: Path, n: int):
    store = GrowthFeatureStore(root=str(root / "gr"))
    gids = [f"game_{i:03d}" for i in range(n)]
    for i, gid in enumerate(gids):
        d0, d1 = _snapshots(gid, i)
        store.append(d0)
        store.append(d1)
    latest = [store.latest(g) for g in gids]
    return store, build_company_snapshot(latest, DATE)


def _success_graph(root: Path) -> GrowthMemoryGraph:
    """成功记忆：creative_refresh 连胜 → 沉淀高成功率模式。"""
    g = GrowthMemoryGraph(path=str(root / "graph_success.jsonl"))
    for j in range(3):
        eid = f"win{j}"
        g.add_node(GraphNode(
            id=node_id(NodeType.EXECUTION, eid), type=NodeType.EXECUTION,
            label=f"exec {eid}",
            payload={"execution_id": eid, "revenue_delta": 0.25},
        ))
        g.add_node(GraphNode(
            id=node_id(NodeType.RESULT, f"r{j}"), type=NodeType.RESULT,
            label=f"result {j}",
            payload={
                "strategy_type": "creative_refresh", "domain": "creative",
                "action_type": "SAFE", "success": True, "execution_id": eid,
            },
        ))
    return g


def _poisoned_graph(root: Path) -> GrowthMemoryGraph:
    """毒记忆：creative 域连败 → E17.8 闸门应 BLOCK。"""
    g = GrowthMemoryGraph(path=str(root / "graph_poison.jsonl"))
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


def _make_operator(root: Path, store, memory_graph=None):
    return DailyGrowthOperatorAgent(
        pipeline=DailyGrowthPipeline(
            store=store,
            memory_graph=memory_graph,
            approval_queue_path=str(root / "q.jsonl"),
            audit_dir=str(root / "audit"),
        ),
        operator_memory=JsonlOperatorMemory(path=str(root / "op_memory.jsonl")),
    )


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="e17_10_demo_"))
    out_dir = Path("reports/portfolio_demo")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    print("=" * 70)
    print("E17.10 Portfolio Dashboard demo（SIM · 确定性 · 无真实 API）")
    print("=" * 70)

    # -------- 场景 1：12 游戏舰队一键端到端 -------------------------------- #
    store, company = _make_store(root, 12)
    agent = PortfolioDashboardAgent(notifier=FileNotifier(out_dir))
    dash, paths = agent.run(
        company, DATE, operator=_make_operator(root / "s1", store)
    )
    k = dash.kpi
    print("\n[场景1] 12 游戏舰队 → 端到端落盘")
    print(f"  公司状态: {dash.company_status} | 游戏: {k.total_games}"
          f"（🟢{k.healthy_games}/🟡{k.attention_games}/🔴{k.critical_games}）")
    print(f"  日收入: ${k.total_daily_revenue:,.2f} | DAU: {k.total_dau:,}"
          f" | 平均置信: {k.avg_confidence:.0%}")
    print(f"  行动: AUTO {k.auto_actions} / APPROVAL {k.approval_actions}"
          f" / BLOCK {k.blocked_actions}"
          f" | 自动预期影响: {k.expected_revenue_impact:+.1%}")
    if k.portfolio_sim_p50 is not None:
        print(f"  组合模拟 p50: {k.portfolio_sim_p50:+.1%}")
    for p in paths:
        print(f"  落盘: {p}")

    # -------- 场景 2：成功记忆 → learned_patterns ------------------------- #
    store2, company2 = _make_store(root / "s2", 6)
    graph_ok = _success_graph(root)
    dash2, _ = agent.run(
        company2, DATE, memory_graph=graph_ok,
        operator=_make_operator(root / "s2", store2, memory_graph=graph_ok),
        notify=False,
    )
    print("\n[场景2] 成功记忆图谱接入")
    print(f"  memory_summary: {dash2.memory_summary}")
    for p in dash2.learned_patterns:
        print(f"  模式: {p.strategy_type}/{p.domain}/{p.action_type}"
              f" 样本{p.samples} 成功率{p.success_rate:.0%}"
              f" 收入增量{p.avg_revenue_delta:+.1%}")

    # -------- 场景 3：毒记忆 → BLOCK 旗标 --------------------------------- #
    store3, company3 = _make_store(root / "s3", 8)
    graph_bad = _poisoned_graph(root)
    dash3, _ = agent.run(
        company3, DATE, memory_graph=graph_bad,
        operator=_make_operator(root / "s3", store3, memory_graph=graph_bad),
        notify=False,
    )
    blocked_q = dash3.queue_by_kind("block")
    sim_flags = [f for f in dash3.risk_flags if f.domain == "simulation"]
    print("\n[场景3] 毒记忆图谱（creative 连败）")
    print(f"  决策队列 ⛔ 阻断: {len(blocked_q)} 条 | 模拟风险旗标: {len(sim_flags)} 条")
    for f in sim_flags[:3]:
        print(f"  旗标: [{f.level.value}] {f.game_id} — {f.reason}")

    # -------- 场景 4：确定性 ---------------------------------------------- #
    op4 = _make_operator(root / "s4", store)
    result = op4.run_daily_for_company(company, DATE, force=True)
    d_a = agent.from_daily_run(company, result)
    d_b = agent.from_daily_run(company, result)
    same = json.dumps(d_a.to_dict(), sort_keys=True) == json.dumps(
        d_b.to_dict(), sort_keys=True
    )
    print("\n[场景4] 确定性：同输入两次聚合 to_dict 一致 →", same)
    assert same, "determinism violated"

    print("\n全部场景完成 ✅（real_api_called 恒 False，未触任何真实 API）")


if __name__ == "__main__":
    main()
