"""
P3.5 — Growth Knowledge Graph：跨源 consolidated 查询 API（只读底座）。

在 E17.7 ``GrowthMemoryGraph`` 之上扩展统一 schema（P3.5.1），把 5 个分散的 memory 源
沉淀为一套可跨源查询的「经验型」知识图谱：

    源                               ->  高层节点
    ----------------------------------------------------------------
    E17.7 Graph (extract_patterns)  ->  CreativePattern / UAPattern / MonetizationPattern
    Strategy Memory (P3.3)          ->  StrategyResult
    Execution Memory (E17.6)        ->  ExecutionOutcome
    E16 Recovery Experience          ->  RecoveryHistory
    Portfolio Memory (P3.4.5 结果)  ->  PortfolioDecision

纪律红线（与 P3.4 一致，且更严——只读）：

- 不写回任何 5 个源（不调 strategy_memory.save / execution_memory.record /
  recovery_store.add / graph.record_outcome）；consolidate 只「读」源、往 E17.7 图里
  「加」高层节点（复用 E17.7 图存储，扩展 schema）。
- 不决策、不执行、不调 Provider；不重算 ROAS / revenue / LTV。
- real_api_called 恒 False。
- 幂等：重复 consolidate 不产生重复节点/边（E17.7 图键去重）。
"""
from __future__ import annotations

import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .knowledge_models import (
    ExecutionOutcome,
    GrowthPattern,
    PortfolioDecision,
    RecoveryHistory,
    StrategyResult,
    _PATTERN_EDGE,
    _PATTERN_NODE,
)
from .models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    node_id,
)
from .patterns import extract_patterns
from .store import GrowthMemoryGraph

# 默认 consolidated 图落盘路径（复用 E17.7 图存储机制；caller 可传隔离路径）
_DEFAULT_GRAPH_PATH = "data/ceo/knowledge_graph.jsonl"

# 生命周期 -> 策略维度（启发式；P3.5 后续里程碑可接入真实生命周期源）
_LIFECYCLE_DIMENSION = {
    "launch": "creative",
    "growth": "ua",
    "maturity": "monetization",
    "decline": "monetization",
}


def _temp_graph_path() -> str:
    """隔离的临时图路径（测试 / 一次性构建用，避免污染生产 store）。"""
    fd = tempfile.NamedTemporaryFile(prefix="kg_", suffix=".jsonl", delete=False)
    p = fd.name
    fd.close()
    return p


def _is_recovery_success(rec: Dict[str, Any]) -> bool:
    """恢复经验是否成功（兼容 ``success`` 布尔与 ``result`` 状态两种写法）。"""
    if rec.get("success") is True:
        return True
    return str(rec.get("result", "")).lower() in ("success", "recovered")


class GrowthKnowledgeGraph:
    """跨源 consolidated 知识图谱（只读底座）。

    典型用法::

        kg = GrowthKnowledgeGraph()                       # 复用 E17.7 图存储
        kg.consolidate(                                    # 只读吃 5 源
            strategy_memory=adapter,
            execution_memory=exec_mem,
            recovery_store=recovery_store,
            portfolio_results=[optimization_result],
        )
        kg.why_game_succeeded("game_002")                  # 为什么这个游戏成功
        kg.similar_games("game_002")                        # 类似情况以前怎么处理
        kg.strategy_results_by_success()                   # 哪些策略有效
    """

    def __init__(
        self,
        graph: Optional[GrowthMemoryGraph] = None,
        graph_path: Optional[str] = None,
    ) -> None:
        if graph is not None:
            self.graph = graph
        else:
            self.graph = GrowthMemoryGraph(path=graph_path or _DEFAULT_GRAPH_PATH)
        self._consolidated = False

    # ------------------------------------------------------------------ #
    # 纪律：real_api_called 锁死 False（纯分析层）
    # ------------------------------------------------------------------ #
    @property
    def real_api_called(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # 源适配：接受实例或路径（惰性导入，避免 import 期耦合）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_strategy_memory(x):
        if x is None:
            return None
        from ...operator.strategy.memory import StrategyMemoryAdapter

        if isinstance(x, StrategyMemoryAdapter):
            return x
        if isinstance(x, str):
            return StrategyMemoryAdapter(store_path=x)
        return StrategyMemoryAdapter()

    @staticmethod
    def _coerce_execution_memory(x):
        if x is None:
            return None
        from ..execution_router.memory import ExecutionMemory

        if isinstance(x, ExecutionMemory):
            return x
        if isinstance(x, str):
            return ExecutionMemory(path=x)
        return ExecutionMemory()

    @staticmethod
    def _coerce_recovery_store(x):
        if x is None:
            return None
        from ...execution.recovery import JsonlRecoveryExperienceStore

        if isinstance(x, JsonlRecoveryExperienceStore):
            return x
        if isinstance(x, str):
            return JsonlRecoveryExperienceStore(path=x)
        return JsonlRecoveryExperienceStore()

    # ------------------------------------------------------------------ #
    # 主入口：consolidate（只读吃 5 源 -> 写 E17.7 高层节点）
    # ------------------------------------------------------------------ #
    def consolidate(
        self,
        *,
        strategy_memory: Any = None,
        execution_memory: Any = None,
        recovery_store: Any = None,
        portfolio_results: Optional[List[Any]] = None,
        include_patterns: bool = True,
    ) -> Dict[str, int]:
        """从 5 个 memory 源构建 consolidated 高层图谱（幂等）。

        返回 {"nodes_added": int, "edges_added": int}。
        """
        counts: Dict[str, int] = {"nodes_added": 0, "edges_added": 0}

        if include_patterns:
            counts = self._consolidate_patterns(counts)

        sm = self._coerce_strategy_memory(strategy_memory)
        if sm is not None:
            counts = self._consolidate_strategy(sm, counts)

        em = self._coerce_execution_memory(execution_memory)
        if em is not None:
            counts = self._consolidate_execution(em, counts)

        rs = self._coerce_recovery_store(recovery_store)
        if rs is not None:
            counts = self._consolidate_recovery(rs, counts)

        if portfolio_results:
            counts = self._consolidate_portfolio(portfolio_results, counts)

        self._consolidated = True
        return counts

    # ------------------------------------------------------------------ #
    # 各源 consolidation（均只「读」源）
    # ------------------------------------------------------------------ #
    def _consolidate_patterns(self, counts: Dict[str, int]) -> Dict[str, int]:
        patterns = extract_patterns(self.graph)
        by_strategy: Dict[str, List[GraphNode]] = {}
        for p in patterns:
            if p.domain not in _PATTERN_NODE:
                continue
            games = sorted(
                {
                    n.payload.get("game_id", "")
                    for n in self.graph.query(
                        NodeType.RESULT,
                        strategy_type=p.strategy_type,
                        domain=p.domain,
                        action_type=p.action_type,
                    )
                    if n.payload.get("game_id")
                }
            )
            gp = GrowthPattern(
                kind=p.domain,
                key=f"{p.strategy_type}::{p.action_type}",
                strategy_type=p.strategy_type,
                action_type=p.action_type,
                success_rate=p.success_rate,
                samples=p.samples,
                avg_reward=p.avg_revenue_delta,
                games=games,
            )
            node = gp.to_node()
            if self.graph.add_node(node):
                counts["nodes_added"] += 1
            for gid in games:
                edge = GraphEdge(
                    src=node_id(NodeType.GAME, gid),
                    tgt=node.id,
                    type=_PATTERN_EDGE[gp.kind],
                )
                if self.graph.add_edge(edge):
                    counts["edges_added"] += 1
            by_strategy.setdefault(p.strategy_type, []).append(node)

        # PATTERN_SIMILAR_TO：共享 strategy_type 的模式互连（跨动作/跨游戏学习）
        for nodes in by_strategy.values():
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    edge = GraphEdge(
                        src=nodes[i].id,
                        tgt=nodes[j].id,
                        type=EdgeType.PATTERN_SIMILAR_TO,
                        payload={
                            "shared_strategy": nodes[i].payload.get("strategy_type", "")
                        },
                    )
                    if self.graph.add_edge(edge):
                        counts["edges_added"] += 1
        return counts

    def _consolidate_strategy(self, sm: Any, counts: Dict[str, int]) -> Dict[str, int]:
        insights = sm.build_insights(self.graph)
        states = sm.all_states()
        for ins in insights:
            st = states.get(ins.strategy_id)
            confidence = float(st.confidence) if st else 0.0
            status = st.status.value if st else "active"
            games = sorted(
                {
                    n.payload.get("game_id", "")
                    for n in self.graph.query(
                        NodeType.RESULT, strategy_type=ins.strategy_id
                    )
                    if n.payload.get("game_id")
                }
            )
            sr = StrategyResult(
                strategy_id=ins.strategy_id,
                dimension=ins.dimension,
                success_rate=ins.historical_success_rate,
                samples=ins.samples,
                avg_reward=ins.avg_reward,
                confidence=confidence,
                status=status,
                recommendation=ins.recommendation,
                rationale=ins.rationale,
                games=games,
            )
            node = sr.to_node()
            if self.graph.add_node(node):
                counts["nodes_added"] += 1
            for gid in games:
                edge = GraphEdge(
                    src=node_id(NodeType.GAME, gid),
                    tgt=node.id,
                    type=EdgeType.HAS_STRATEGY_RESULT,
                )
                if self.graph.add_edge(edge):
                    counts["edges_added"] += 1
        return counts

    def _consolidate_execution(self, em: Any, counts: Dict[str, int]) -> Dict[str, int]:
        rows = em.all()
        groups: Dict[Tuple[str, str], List[Any]] = {}
        for e in rows:
            groups.setdefault((e.game_id, e.domain), []).append(e)
        for (gid, dom), exps in groups.items():
            n = len(exps)
            succ = sum(1 for e in exps if getattr(e, "success", False))
            rb = sum(1 for e in exps if getattr(e, "rolled_back", False))
            eo = ExecutionOutcome(
                game_id=gid,
                domain=dom,
                success_rate=(succ / n) if n else 0.0,
                samples=n,
                rolled_back_rate=(rb / n) if n else 0.0,
            )
            node = eo.to_node()
            if self.graph.add_node(node):
                counts["nodes_added"] += 1
            edge = GraphEdge(
                src=node_id(NodeType.GAME, gid),
                tgt=node.id,
                type=EdgeType.HAS_EXECUTION_OUTCOME,
            )
            if self.graph.add_edge(edge):
                counts["edges_added"] += 1
        return counts

    def _consolidate_recovery(self, store: Any, counts: Dict[str, int]) -> Dict[str, int]:
        rows = store.all()
        # execution_id -> game_id（从 E17.7 图解析，用于把恢复经验挂到具体游戏）
        exec_game: Dict[str, str] = {}
        for n in self.graph.query(NodeType.EXECUTION):
            eid = n.payload.get("execution_id", n.id.split(":", 1)[1])
            gid = n.payload.get("game_id", "")
            if gid:
                exec_game[eid] = gid

        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(
                (str(r.get("failure", "")), str(r.get("recovery", ""))), []
            ).append(r)
        for (failure, recovery), recs in groups.items():
            n = len(recs)
            succ = sum(1 for r in recs if _is_recovery_success(r))
            avg_reward = (
                sum(float(r.get("reward", 0.0)) for r in recs) / n if n else 0.0
            )
            games = sorted(
                {
                    exec_game.get(r.get("metadata", {}).get("execution_id", ""), "")
                    for r in recs
                    if r.get("metadata", {}).get("execution_id", "") in exec_game
                }
                - {""}
            )
            rh = RecoveryHistory(
                failure_type=failure,
                recovery_strategy=recovery,
                success_rate=(succ / n) if n else 0.0,
                n=n,
                avg_reward=avg_reward,
                game_id=games[0] if len(games) == 1 else "",
                games=games,
            )
            node = rh.to_node()
            if self.graph.add_node(node):
                counts["nodes_added"] += 1
            for gid in games:
                edge = GraphEdge(
                    src=node_id(NodeType.GAME, gid),
                    tgt=node.id,
                    type=EdgeType.HAS_RECOVERY_HISTORY,
                )
                if self.graph.add_edge(edge):
                    counts["edges_added"] += 1
        return counts

    def _consolidate_portfolio(
        self, results: List[Any], counts: Dict[str, int]
    ) -> Dict[str, int]:
        if not isinstance(results, list):
            results = [results]
        for res in results:
            if res is None:
                continue
            prop = getattr(res, "proposal", None)
            if prop is None:
                continue
            status_val = getattr(res, "status", None)
            status_str = status_val.value if status_val is not None else ""
            opt_id = getattr(res, "optimization_id", "") or ""
            for it in prop.items:
                pd = PortfolioDecision(
                    game_id=it.game_id,
                    recommendation=it.recommended_action.value,
                    confidence=it.confidence,
                    priority=it.priority,
                    guard=it.action_state.value,
                    status=status_str,
                    optimization_id=opt_id,
                    rank=it.rank,
                )
                node = pd.to_node()
                if self.graph.add_node(node):
                    counts["nodes_added"] += 1
                edge = GraphEdge(
                    src=node_id(NodeType.GAME, it.game_id),
                    tgt=node.id,
                    type=EdgeType.HAS_PORTFOLIO_DECISION,
                )
                if self.graph.add_edge(edge):
                    counts["edges_added"] += 1
        return counts

    # ------------------------------------------------------------------ #
    # 查询 API（只读，回答 P3.5 三个核心问题）
    # ------------------------------------------------------------------ #
    def _patterns_of(self, game_id: str) -> List[GrowthPattern]:
        out: List[GrowthPattern] = []
        for nt in (
            NodeType.CREATIVE_PATTERN,
            NodeType.UA_PATTERN,
            NodeType.MONETIZATION_PATTERN,
        ):
            for n in self.graph.query(nt):
                if game_id in (n.payload.get("games") or []):
                    out.append(GrowthPattern.from_node(n))
        return out

    def why_game_succeeded(self, game_id: str) -> Dict[str, Any]:
        """问题 1：为什么这个游戏过去成功？

        汇聚该游戏在 5 个高层节点上的全部经验证据，给出可解释摘要。
        """
        gid = str(game_id)
        strat = [
            StrategyResult.from_node(n)
            for n in self.graph.query(NodeType.STRATEGY_RESULT)
            if gid in (n.payload.get("games") or [])
        ]
        pats = self._patterns_of(gid)
        execs = [
            ExecutionOutcome.from_node(n)
            for n in self.graph.query(NodeType.EXECUTION_OUTCOME)
            if n.payload.get("game_id") == gid
        ]
        recs = [
            RecoveryHistory.from_node(n)
            for n in self.graph.query(NodeType.RECOVERY_HISTORY)
            if (n.payload.get("game_id") == gid)
            or (gid in (n.payload.get("games") or []))
        ]
        pds = [
            PortfolioDecision.from_node(n)
            for n in self.graph.query(NodeType.PORTFOLIO_DECISION)
            if n.payload.get("game_id") == gid
        ]
        ceo_decisions = [
            n.payload
            for n in self.graph.query(NodeType.CEO_DECISION)
            if n.payload.get("game_id") == gid
        ]
        summary = self._build_why_summary(gid, strat, pats, execs, recs, pds)
        return {
            "game_id": gid,
            "strategy_results": [s.to_dict() for s in strat],
            "patterns": [p.to_dict() for p in pats],
            "execution_outcomes": [e.to_dict() for e in execs],
            "recovery_history": [r.to_dict() for r in recs],
            "portfolio_decisions": [p.to_dict() for p in pds],
            "ceo_decisions": ceo_decisions,   # P3.5.2：本游戏的历史 CEO 决策（决策+知识+结果）
            "summary": summary,
        }

    def _build_why_summary(self, gid, strat, pats, execs, recs, pds) -> str:
        parts: List[str] = [f"游戏 {gid} 经验画像："]
        if strat:
            best = max(strat, key=lambda s: s.success_rate)
            parts.append(
                f"策略层：{best.strategy_id} 历史成功率 {best.success_rate:.0%}"
                f"（样本 {best.samples}），建议 {best.recommendation}"
            )
        if pats:
            top = max(pats, key=lambda p: p.success_rate)
            parts.append(
                f"模式层：{top.kind} 模式 {top.key} 成功率 {top.success_rate:.0%}"
            )
        if execs:
            avg_exec = sum(e.success_rate for e in execs) / len(execs)
            parts.append(f"执行层：平均动作成功率 {avg_exec:.0%}")
        if recs:
            avg_rec = sum(r.success_rate for r in recs) / len(recs)
            parts.append(f"恢复层：历史恢复成功率 {avg_rec:.0%}")
        if pds:
            acts = [p.recommendation for p in pds]
            parts.append(f"组合层：最新建议 {', '.join(acts)}")
        if len(parts) == 1:
            parts.append("暂无 consolidated 经验（需先 consolidate 且源中有数据）")
        return "；".join(parts) + "。"

    def similar_games(self, game_id: str) -> List[Dict[str, Any]]:
        """问题 2：类似情况以前怎么处理？

        基于「游戏 -> 经验信号」重叠度找相似游戏，按重叠数降序。
        """
        signals = self._game_signals()
        target = signals.get(str(game_id), set())
        if not target:
            return []
        out: List[Dict[str, Any]] = []
        for gid, sig in signals.items():
            if gid == str(game_id):
                continue
            shared = target & sig
            if shared:
                out.append(
                    {
                        "game_id": gid,
                        "shared_signals": sorted(shared),
                        "shared_count": len(shared),
                    }
                )
        out.sort(key=lambda d: (-d["shared_count"], d["game_id"]))
        return out

    def _game_signals(self) -> Dict[str, set]:
        signals: Dict[str, set] = {}
        for nt, kind in (
            (NodeType.STRATEGY_RESULT, "strategy"),
            (NodeType.CREATIVE_PATTERN, "creative"),
            (NodeType.UA_PATTERN, "ua"),
            (NodeType.MONETIZATION_PATTERN, "monetization"),
            (NodeType.EXECUTION_OUTCOME, "exec"),
            (NodeType.RECOVERY_HISTORY, "recovery"),
            (NodeType.PORTFOLIO_DECISION, "portfolio"),
        ):
            for n in self.graph.query(nt):
                p = n.payload
                for gid in (p.get("games") or []):
                    if gid:
                        signals.setdefault(gid, set()).add(f"{kind}:{n.label}")
                if p.get("game_id"):
                    signals.setdefault(p["game_id"], set()).add(f"{kind}:{n.label}")
        return signals

    def strategy_results_by_success(self, descending: bool = True) -> List[StrategyResult]:
        """问题 3（基础）：哪些策略有效？按历史成功率排序。"""
        rows = [
            StrategyResult.from_node(n)
            for n in self.graph.query(NodeType.STRATEGY_RESULT)
        ]
        rows.sort(key=lambda s: s.success_rate, reverse=descending)
        return rows

    def strategy_for_lifecycle(self, lifecycle_stage: str) -> List[StrategyResult]:
        """问题 3（进阶）：哪个策略在什么生命周期有效？

        当前用「生命周期 -> 策略维度」启发式映射（launch->creative / growth->ua /
        maturity,decline->monetization）筛选策略维度，再按成功率排序。
        真实生命周期源接入是 P3.5 后续里程碑的扩展点。
        """
        dim = _LIFECYCLE_DIMENSION.get(str(lifecycle_stage).lower())
        rows = self.strategy_results_by_success(descending=True)
        if dim is None:
            return rows
        return [r for r in rows if (r.dimension or "") == dim]

    def portfolio_decisions(
        self, game_id: Optional[str] = None
    ) -> List[PortfolioDecision]:
        out = [
            PortfolioDecision.from_node(n)
            for n in self.graph.query(NodeType.PORTFOLIO_DECISION)
        ]
        if game_id is not None:
            out = [d for d in out if d.game_id == str(game_id)]
        return out

    def recovery_history(
        self, game_id: Optional[str] = None
    ) -> List[RecoveryHistory]:
        out = [
            RecoveryHistory.from_node(n)
            for n in self.graph.query(NodeType.RECOVERY_HISTORY)
        ]
        if game_id is not None:
            out = [
                r
                for r in out
                if r.game_id == str(game_id)
                or str(game_id) in (r.games or [])
            ]
        return out

    def creative_patterns(self) -> List[GrowthPattern]:
        return [
            GrowthPattern.from_node(n)
            for n in self.graph.query(NodeType.CREATIVE_PATTERN)
        ]

    def ua_patterns(self) -> List[GrowthPattern]:
        return [
            GrowthPattern.from_node(n)
            for n in self.graph.query(NodeType.UA_PATTERN)
        ]

    def monetization_patterns(self) -> List[GrowthPattern]:
        return [
            GrowthPattern.from_node(n)
            for n in self.graph.query(NodeType.MONETIZATION_PATTERN)
        ]

    def game_knowledge(self, game_id: str) -> Dict[str, Any]:
        """某游戏的完整 consolidated 知识快照（跨 5 类节点）。"""
        return self.why_game_succeeded(game_id)

    # ------------------------------------------------------------------ #
    # 报告 / 汇总
    # ------------------------------------------------------------------ #
    def summary(self) -> Dict[str, Any]:
        stats = self.graph.stats()
        return {
            "consolidated": self._consolidated,
            "real_api_called": self.real_api_called,
            "nodes": stats.get("nodes", 0),
            "edges": stats.get("edges", 0),
            "by_type": {
                k.removeprefix("nodes_"): v
                for k, v in stats.items()
                if k.startswith("nodes_")
            },
        }

    def to_markdown(self) -> str:
        s = self.summary()
        lines = ["# Growth Knowledge Graph（跨游戏经验知识图谱）", ""]
        lines.append(
            f"- 节点 **{s['nodes']}** ｜ 边 **{s['edges']}** ｜ "
            f"真实 API：{'是' if s['real_api_called'] else '否（SIM）'}"
        )
        bt = self.strategy_results_by_success()[:8]
        if bt:
            lines.append("")
            lines.append("## 有效策略（按历史成功率）")
            lines.append("")
            lines.append("| 策略 | 维度 | 成功率 | 样本 | 建议 |")
            lines.append("|---|---|---|---|---|")
            for r in bt:
                lines.append(
                    f"| {r.strategy_id} | {r.dimension} | "
                    f"{r.success_rate:.0%} | {r.samples} | {r.recommendation} |"
                )
        pd = self.portfolio_decisions()
        if pd:
            lines.append("")
            lines.append("## 最新组合建议")
            for d in pd:
                lines.append(
                    f"- {d.game_id}: {d.recommendation.upper()} "
                    f"（{d.guard.upper()}, 优先级 {d.priority:.0f}）"
                )
        return "\n".join(lines)


__all__ = ["GrowthKnowledgeGraph"]
