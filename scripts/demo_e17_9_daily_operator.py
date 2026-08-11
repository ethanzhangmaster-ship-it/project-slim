"""E17.9 Daily Growth Operator — demo（SIM，确定性，无真实 API）。

把 E17.1→E17.8 全链路变成「每日 Operating Loop」：
  Reality → Opportunity → Decision → Strategy → Simulation 闸门 → Execution
  → Priority Top10 → 晨报三版本（CEO/UA/Product）→ 记忆落盘（跨日环比）

演示四种情形（覆盖安全铁律的全部出口）：
  场景 1：57 款游戏全舰队每日 Operating Loop（晨报三版本 + 跨日环比）
  场景 2：纯素材疲劳舰队 → 全部 EXECUTE+PASS → 自动执行（AUTO）
  场景 3：投毒记忆图谱 → creative_refresh 被模拟闸门阻断（BLOCK）
  场景 4：跨日记忆读取（昨天 vs 今天环比）

跑法（launchforge/ 根目录）：
  python scripts/demo_e17_9_daily_operator.py

产物：
  - reports/daily/YYYY-MM-DD.md 等（FileNotifier 真实落盘，第一阶段）
  - outputs/e17_9_daily/e17_9_daily_operator_demo.md（合并演示稿）
"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ceo_intelligence.daily_operator.agent import DailyGrowthOperatorAgent
from src.ceo_intelligence.daily_operator.models import ActionKind
from src.ceo_intelligence.daily_operator.notifier import FileNotifier
from src.ceo_intelligence.daily_operator.pipeline import DailyGrowthPipeline
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

# poison 场景需要
from src.ceo_intelligence.growth_memory_graph.models import (
    GraphNode,
    NodeType,
    node_id,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph


# --------------------------------------------------------------------------- #
# 数据构造
# --------------------------------------------------------------------------- #
def _snapshots(gid: str, i: int):
    """单游戏两条时序快照（d0 基线、d1 施加变化），按 i%4 触发不同规则。"""
    rev = 1000.0
    dau = 3000 + i
    roas = 2.0
    spend = 100.0
    installs = 1000
    cpi = 0.1
    ctr = 0.05
    fatigue = 0.30
    creative_score = 0.60
    ranking = 10
    store_cvr = 0.10
    rating = 3.5
    conf = 0.6 + (i % 3) * 0.1

    d0 = GrowthRealitySnapshot(
        gid, "d0",
        revenue=RevenueFact(daily_revenue=rev, payer_count=10),
        acquisition=AcquisitionFact(spend=spend, installs=installs, cpi=cpi, roas=roas),
        creative=CreativeFact(ctr=ctr, fatigue_score=fatigue, creative_score=creative_score),
        aso=AsoFact(ranking=ranking, store_cvr=store_cvr, rating=rating, review_velocity=4.0),
        product=ProductFact(dau=dau, retention=0.3, conversion=0.02),
        confidence=conf,
        sources=["sim"],
    )

    rev1, roas1, spend1, ctr1, fatigue1, store_cvr1, rating1 = (
        rev, roas, spend, ctr, fatigue, store_cvr, rating,
    )
    pattern = i % 4
    if pattern == 0:
        drop = 0.20 + (i % 5) * 0.04
        rev1 = rev * (1 - drop)
    elif pattern == 1:
        roas_drop = 0.15 + (i % 5) * 0.04
        spend_inc = 0.20 + (i % 5) * 0.04
        roas1 = roas * (1 - roas_drop)
        spend1 = spend * (1 + spend_inc)
    elif pattern == 2:
        ctr_drop = 0.20 + (i % 5) * 0.04
        ctr1 = ctr * (1 - ctr_drop)
        fatigue1 = min(0.95, 0.70 + (i % 5) * 0.05)
    elif pattern == 3:
        cvr_drop = 0.15 + (i % 5) * 0.04
        store_cvr1 = store_cvr * (1 - cvr_drop)
        rating1 = 4.5

    d1 = GrowthRealitySnapshot(
        gid, "d1",
        revenue=RevenueFact(daily_revenue=rev1, payer_count=10),
        acquisition=AcquisitionFact(spend=spend1, installs=installs, cpi=cpi, roas=roas1),
        creative=CreativeFact(ctr=ctr1, fatigue_score=fatigue1, creative_score=creative_score),
        aso=AsoFact(ranking=ranking, store_cvr=store_cvr1, rating=rating1, review_velocity=4.0),
        product=ProductFact(dau=dau, retention=0.3, conversion=0.02),
        confidence=conf,
        sources=["sim"],
    )
    return d0, d1


def build_company(root: Path, n: int):
    store = GrowthFeatureStore(root=str(root / "gr"))
    gids = [f"game_{i:03d}" for i in range(n)]
    for i, gid in enumerate(gids):
        d0, d1 = _snapshots(gid, i)
        store.append(d0)
        store.append(d1)
    latest = [store.latest(g) for g in gids]
    return build_company_snapshot(latest, date.today().isoformat())


def build_creative_only(root: Path, n: int):
    """纯素材疲劳舰队：全部触发 creative_refresh → EXECUTE+PASS → AUTO。"""
    store = GrowthFeatureStore(root=str(root / "gr"))
    gids = [f"creative_{i:03d}" for i in range(n)]
    for i, gid in enumerate(gids):
        fatigue = min(0.95, 0.75 + (i % 4) * 0.05)
        d0 = GrowthRealitySnapshot(
            gid, "d0",
            revenue=RevenueFact(daily_revenue=2000.0, payer_count=20),
            creative=CreativeFact(ctr=0.06, fatigue_score=0.30, creative_score=0.70),
            product=ProductFact(dau=5000, retention=0.35, conversion=0.03),
            confidence=0.85,
            sources=["sim"],
        )
        d1 = GrowthRealitySnapshot(
            gid, "d1",
            revenue=RevenueFact(daily_revenue=2000.0, payer_count=20),
            creative=CreativeFact(ctr=0.035, fatigue_score=fatigue, creative_score=0.70),
            product=ProductFact(dau=5000, retention=0.35, conversion=0.03),
            confidence=0.85,
            sources=["sim"],
        )
        store.append(d0)
        store.append(d1)
    latest = [store.latest(g) for g in gids]
    return build_company_snapshot(latest, date.today().isoformat())


def build_poison_company(root: Path):
    """复刻 E17.8 demo：merge_witch（creative+revenue）、puzzle_island（aso）。"""
    store = GrowthFeatureStore(root=str(root / "gr"))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d0",
        revenue=RevenueFact(5000, 50),
        creative=CreativeFact(0.03, 0.2, 80),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d1",
        revenue=RevenueFact(3500, 35),
        creative=CreativeFact(0.022, 0.85, 55),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d0",
        aso=AsoFact(12, 0.05, 4.6, 4),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d1",
        aso=AsoFact(12, 0.04, 4.6, 4),
        confidence=1.0,
    ))
    return build_company_snapshot(
        [store.latest("merge_witch"), store.latest("puzzle_island")],
        date.today().isoformat(),
    )


def poisoned_graph(root: Path):
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


# --------------------------------------------------------------------------- #
# 运行 + 汇总
# --------------------------------------------------------------------------- #
def _run(agent, company, day: str):
    return agent.run_daily_for_company(company, day, force=True)


def _agent(root: Path, store=None, memory_graph=None):
    pipeline = DailyGrowthPipeline(
        store=store,
        memory_graph=memory_graph,
        approval_queue_path=str(root / "q.jsonl"),
        audit_dir=str(root / "audit"),
    )
    return DailyGrowthOperatorAgent(
        pipeline=pipeline,
        notifier=FileNotifier(report_dir=str(Path("reports") / "daily")),
    )


def _summarize(result, label: str) -> str:
    s = result.summary
    lines = [f"### {label}", ""]
    lines.append(f"- 公司状态：{s['company_status']}")
    lines.append(f"- 决策数：{s['decisions']} ｜ 自动执行 AUTO：{s['auto']} ｜ "
                 f"待审批 APPROVAL：{s['approval']} ｜ 阻断 BLOCK：{s['blocked']} ｜ "
                 f"仅观察 OBSERVE：{s['observed']}")
    lines.append(f"- 自动执行预期收入影响合计：{s['revenue_impact']:+.4%}")
    lines.append(f"- real_api_called：{s['real_api_called']}（SIM 纪律）")
    lines.append("")
    lines.append("**Top 10 优先级：**")
    lines.append("")
    lines.append("| # | 游戏 | 行动 | 优先级 | 闸门 | 类型 |")
    lines.append("|---|---|---|---|---|---|")
    for p in result.priorities:
        gate = p.gate.upper() if p.gate else "—"
        lines.append(
            f"| {p.rank} | {p.game_id} | {p.action} | "
            f"{p.priority_score_value:.4f} | {gate} | {p.opportunity_type} |"
        )
    lines.append("")
    for kind in (ActionKind.AUTO, ActionKind.APPROVAL, ActionKind.BLOCK):
        group = [a for a in result.actions if a.kind == kind]
        if not group:
            continue
        title = {
            ActionKind.AUTO: "✅ 已自动执行（AUTO）",
            ActionKind.APPROVAL: "🖐 等你审批（APPROVAL）",
            ActionKind.BLOCK: "⛔ 模拟闸门阻断（BLOCK）",
        }[kind]
        lines.append(f"**{title}（{len(group)}）**")
        for a in group:
            lines.append(f"- {a.game_id} — {a.action}（{a.detail}）")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    out_root = Path("outputs") / "e17_9_daily"
    out_root.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    md = ["# E17.9 Daily Growth Operator 演示稿", ""]
    md.append(f"> 生成日期：{today} ｜ 全 SIM，无真实 API 调用")
    md.append("")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 场景 1：57 游戏全舰队
        print("=" * 72)
        print("场景 1 · 57 款游戏每日 Operating Loop（晨报三版本）")
        print("=" * 72)
        company = build_company(root / "main", 57)
        store = GrowthFeatureStore(root=str(root / "main/gr"))
        agent = _agent(root / "main", store=store)
        r1 = _run(agent, company, today)
        md.append("## 场景 1 · 57 款游戏全舰队每日 Operating Loop")
        md.append("")
        md.append(r1.reports["ceo"])
        md.append("")
        md.append("---")
        md.append("")
        md.append("### UA Manager 视角")
        md.append("")
        md.append(r1.reports["ua"])
        md.append("")
        md.append("---")
        md.append("")
        md.append("### Product 视角")
        md.append("")
        md.append(r1.reports["product"])
        md.append("")
        md.append("---")
        md.append("")
        md.append(_summarize(r1, "场景 1 运行摘要"))
        print(_summarize(r1, "场景 1"))

        # 场景 2：纯素材疲劳 → AUTO
        print()
        print("=" * 72)
        print("场景 2 · 纯素材疲劳舰队 → 自动执行（AUTO 展示）")
        print("=" * 72)
        creative_co = build_creative_only(root / "creative", 6)
        cstore = GrowthFeatureStore(root=str(root / "creative/gr"))
        agent2 = _agent(root / "creative", store=cstore)
        r2 = _run(agent2, creative_co, today)
        md.append("## 场景 2 · 纯素材疲劳舰队 → 自动执行（AUTO）")
        md.append("")
        md.append(_summarize(r2, "场景 2 · 6 款素材疲劳游戏"))
        print(_summarize(r2, "场景 2"))

        # 场景 3：投毒记忆 → BLOCK
        print()
        print("=" * 72)
        print("场景 3 · 投毒记忆图谱 → 模拟闸门阻断（BLOCK 展示）")
        print("=" * 72)
        poison_co = build_poison_company(root / "poison")
        pstore = GrowthFeatureStore(root=str(root / "poison/gr"))
        pgraph = poisoned_graph(root / "poison")
        agent3 = _agent(root / "poison", store=pstore, memory_graph=pgraph)
        r3 = _run(agent3, poison_co, today)
        md.append("## 场景 3 · 投毒记忆图谱 → 模拟闸门阻断（BLOCK）")
        md.append("")
        md.append(_summarize(r3, "场景 3 · creative_refresh 被 BLOCK"))
        print(_summarize(r3, "场景 3"))

        # 场景 4：跨日记忆
        print()
        print("=" * 72)
        print("场景 4 · 跨日记忆（昨天 vs 今天环比）")
        print("=" * 72)
        agent4 = _agent(root / "mem", store=store)
        _run(agent4, company, yesterday)
        r4 = _run(agent4, company, today)
        md.append("## 场景 4 · 跨日记忆（昨天 vs 今天环比）")
        md.append("")
        y = r4.summary["yesterday"]
        md.append(f"- 昨天记录日期：{y['date'] if y else None}")
        md.append(f"- 今天 CEO 晨报含环比段落：{'昨天 vs 今天' in r4.reports['ceo']}")
        md.append("")
        md.append("> 跨日记忆让 Operator 每天能读昨天的结果，形成「昨天 vs 今天」的"
                  "经营闭环，无需人工搬运。")
        print(f"昨天：{y['date'] if y else None} ｜ 今天含环比："
              f"{'昨天 vs 今天' in r4.reports['ceo']}")

    demo_path = out_root / "e17_9_daily_operator_demo.md"
    demo_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n合并演示稿已写入：{demo_path}")
    print(f"晨报三版本已落盘：{Path('reports') / 'daily'}/")


if __name__ == "__main__":
    main()
