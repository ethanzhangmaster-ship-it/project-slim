"""
P3.6.1 — Memory Retrieval Intelligence（Memory Brain 检索编排层，只读）。

把 P3.5 三层（Storage / Understanding / Evolution）+ 质量门统一成
「Context → Retrieval → KnowledgeBundle → Consumer」的 Memory Intelligence Layer，
让 Memory 正式进入生产决策路径（G1 闭环）。

定位（用户冻结）：
- MemoryController **不替代** GrowthKnowledgeAdvisor / MemoryQualityGovernor /
  PortfolioRanker / StrategyLoop；它只回答「过去发生过什么，以及可信程度是多少」；
- ❌ 不决策、不推荐动作、不修改 proposal / rank score / strategy weight；
- 确定性 Graph Retrieval（第一版**不做** embedding/vector DB/LLM）；
- 五路召回：Similar Game / Strategy History / Execution Outcome / Recovery Experience /
  Portfolio Decision + Contradiction（复用 QualityGovernor.detect_conflicts）。

纪律（与全库一致，只读）：
- ❌ 不写 Graph（禁 add_node/add_edge）、不写回 5 源、不调 consolidate；
- ❌ 不 import feedback（不借 recorder 之外写路径）；
- ❌ 不决策/不执行/不调 Provider / SafeExecutor / DecisionEngine；
- ✅ ``real_api_called`` 恒 False；✅ fail-open（图异常 → 空 bundle，不中断主链）；
- ✅ 零回归：controller 是新增可选层，advisor/ranker/loop 原样保留。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .knowledge import GrowthKnowledgeGraph
from .models import NodeType
from .quality import KnowledgeConflict, MemoryQualityGovernor
from .signals import KnowledgeSignal

# 生命周期 → 策略维度（与 knowledge.py 启发式一致，确定性映射）
_LIFECYCLE_DIMENSION = {
    "launch": "creative",
    "growth": "ua",
    "maturity": "monetization",
    "decline": "monetization",
}
_CONFIDENCE_K = 3  # Laplace 式置信：eff / (eff + K)

# 记忆类型（五路）
SIMILAR_GAME = "similar_game"
STRATEGY_HISTORY = "strategy_history"
EXECUTION_OUTCOME = "execution_outcome"
RECOVERY_EXPERIENCE = "recovery_experience"
PORTFOLIO_DECISION = "portfolio_decision"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryContext:
    """检索请求：AI CEO 的决策上下文（统一入口，替代各入口散落传参）。"""

    query_reason: str = "report_explain"
    # "similar_game" | "strategy_effectiveness" | "failure_reason"
    # | "execution_outcome" | "portfolio_context" | "contradiction"
    # | "strategic"（P3.6.2 战略规律）| "report_explain"(全部)
    game_id: str = ""
    lifecycle: str = ""               # launch / growth / maturity / decline
    decision_type: str = ""           # "portfolio" | "strategy"
    required_confidence: float = 0.3  # 对齐 MemoryQualityGovernor.min_quality
    as_of: str = ""                   # decay 时间基准（默认 now）


@dataclass
class MemoryItem:
    """一条结构化召回记忆（可追溯、可评分）。"""

    memory_type: str                 # SIMILAR_GAME / STRATEGY_HISTORY / ...
    key: str                         # 稳定键（game_id / strategy_id / failure_type:strategy）
    success_rate: float = 0.0
    weight: float = 1.0              # 外部事实 1.0（五路均为 consolidated 外部事实）
    quality: float = 0.0             # P3.5.3 质量分（decay 后）
    evidence: List[str] = field(default_factory=list)
    source_ref: str = ""             # 可追溯：graph node id
    validated_at: str = ""           # 最近验证/结果时间（供"最新验证"与 P3.6.3 复盘）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_type": self.memory_type,
            "key": self.key,
            "success_rate": round(float(self.success_rate), 6),
            "weight": round(float(self.weight), 6),
            "quality": round(float(self.quality), 6),
            "evidence": list(self.evidence),
            "source_ref": self.source_ref,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryItem":
        return cls(
            memory_type=str(d.get("memory_type", "")),
            key=str(d.get("key", "")),
            success_rate=float(d.get("success_rate", 0.0)),
            weight=float(d.get("weight", 1.0)),
            quality=float(d.get("quality", 0.0)),
            evidence=list(d.get("evidence", [])),
            source_ref=str(d.get("source_ref", "")),
            validated_at=str(d.get("validated_at", "")),
        )


@dataclass
class RetrievalTrace:
    """本次检索看了什么（供 P3.6.3 Reflection 复盘：AI 当时看过什么）。"""

    query: str = ""                  # f"{query_reason}:{game_id}"
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"query": self.query, "sources": list(self.sources)}


@dataclass
class KnowledgeBundle:
    """检索结果（用户冻结形状 + retrieval_trace + strategic_insights）。"""

    memories: List[MemoryItem] = field(default_factory=list)
    confidence: float = 0.0          # 加权有效样本 Laplace：eff/(eff+3)
    explanation: str = ""            # 人可读理由（喂报告）
    source_chain: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)   # 冲突 evidence 行
    retrieval_trace: RetrievalTrace = field(default_factory=RetrievalTrace)
    strategic_insights: List[Dict[str, Any]] = field(default_factory=list)  # P3.6.2
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memories": [m.to_dict() for m in self.memories],
            "confidence": round(float(self.confidence), 6),
            "explanation": self.explanation,
            "source_chain": list(self.source_chain),
            "conflicts": list(self.conflicts),
            "retrieval_trace": self.retrieval_trace.to_dict(),
            "strategic_insights": list(self.strategic_insights),
            "real_api_called": bool(self.real_api_called),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeBundle":
        rt = d.get("retrieval_trace") or {}
        return cls(
            memories=[MemoryItem.from_dict(m) for m in d.get("memories", [])],
            confidence=float(d.get("confidence", 0.0)),
            explanation=str(d.get("explanation", "")),
            source_chain=list(d.get("source_chain", [])),
            conflicts=list(d.get("conflicts", [])),
            retrieval_trace=RetrievalTrace(
                query=str(rt.get("query", "")),
                sources=list(rt.get("sources", [])),
            ),
            strategic_insights=list(d.get("strategic_insights", [])),
            real_api_called=bool(d.get("real_api_called", False)),
        )


class MemoryController:
    """Memory Brain 检索编排层（只读，fail-open）。

    组装既有部件（不重写 Advisor 的聚合逻辑）：
      GrowthKnowledgeGraph（底层查询）+ MemoryQualityGovernor（质量过滤/评分/冲突）。
    """

    def __init__(
        self,
        graph: Optional[GrowthKnowledgeGraph] = None,
        quality: Optional[MemoryQualityGovernor] = None,
        as_of: Optional[str] = None,
    ) -> None:
        self.graph = graph
        self.quality = quality
        self.as_of = as_of or _now_iso()
        if self.quality is None and graph is not None:
            self.quality = MemoryQualityGovernor(graph, as_of=self.as_of)

    # ------------------------------------------------------------------ #
    # 纪律：real_api_called 锁死 False（纯检索）
    # ------------------------------------------------------------------ #
    @property
    def real_api_called(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # 主入口：Context → Retrieval → KnowledgeBundle
    # ------------------------------------------------------------------ #
    def retrieve(self, context: MemoryContext) -> KnowledgeBundle:
        if self.graph is None:
            return self._empty_bundle(context)
        try:
            return self._retrieve(context)
        except Exception:
            return self._empty_bundle(context)

    def _retrieve(self, context: MemoryContext) -> KnowledgeBundle:
        items, conflicts = self._route(context)

        # 质量门：只保留 quality >= required_confidence 的记忆
        gate = float(context.required_confidence)
        kept = [m for m in items if m.quality >= gate]
        kept.sort(key=lambda m: (m.memory_type, m.key))

        # 加权置信：有效样本 = Σ weight（Laplace）
        eff = sum(m.weight for m in kept)
        confidence = eff / (eff + _CONFIDENCE_K) if eff > 0 else 0.0

        source_chain = [m.source_ref for m in kept if m.source_ref]
        conflict_lines = [c.evidence[0] if c.evidence else f"conflict:{c.key}"
                          for c in conflicts]

        # P3.6.2：strategic 路由召回战略规律（STRATEGIC_INSIGHT 节点）
        strategic_insights: List[Dict[str, Any]] = []
        if context.query_reason == "strategic":
            strategic_insights = self._route_strategic()
            if strategic_insights:
                source_chain += [f"strategic_insight:{s.get('insight_id', '')}"
                                 for s in strategic_insights]

        trace = RetrievalTrace(
            query=f"{context.query_reason}:{context.game_id}",
            sources=list(source_chain),
        )

        return KnowledgeBundle(
            memories=kept,
            confidence=confidence,
            explanation=self._explain(kept, conflicts, strategic_insights),
            source_chain=source_chain,
            conflicts=conflict_lines,
            retrieval_trace=trace,
            strategic_insights=strategic_insights,
            real_api_called=False,
        )

    # ------------------------------------------------------------------ #
    # P3.6.2：战略规律召回（STRATEGIC_INSIGHT 节点，只读）
    # ------------------------------------------------------------------ #
    def _route_strategic(self) -> List[Dict[str, Any]]:
        try:
            store = self.graph.graph
            states: Dict[str, tuple] = {}
            for governance in store.query(NodeType.GOVERNANCE_RECORD):
                data = governance.payload
                target = str(data.get("target_node_id", ""))
                stamp = str(data.get("created_at", ""))
                if target and (target not in states or stamp >= states[target][0]):
                    states[target] = (stamp, str(data.get("new_state", "active")))
            nodes = store.query(NodeType.STRATEGIC_INSIGHT)
            return [
                n.payload for n in nodes
                if states.get(n.id, ("", "active"))[1] not in ("obsolete", "archived")
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # P3.6.3：Reflection 输入收集（只读，fail-open）
    # ------------------------------------------------------------------ #
    def reflection_inputs(self, period: str) -> Dict[str, Any]:
        """给 P3.6.3 ``MemoryReflectionBuilder`` 准备输入（只读，不计算）。

        返回 ``{ceo_records（窗口内）, strategic_insights（全量）, conflicts（窗口内）}``；
        图不可用 / 异常 → 全空（fail-open，不中断主链）。
        窗口过滤语义与 builder 一致：``created_at.startswith(period)``（UTC 日）。
        """
        empty: Dict[str, Any] = {
            "ceo_records": [],
            "strategic_insights": [],
            "conflicts": [],
        }
        if self.graph is None:
            return empty
        try:
            recs = self.quality.ceo_decision_records() if self.quality else []
            recs = [
                r for r in recs
                if period and str(r.get("created_at", "")).startswith(str(period))
            ]
            insights = self._route_strategic()
            conflicts = self.quality.detect_conflicts(recs) if self.quality else []
            return {
                "ceo_records": recs,
                "strategic_insights": insights,
                "conflicts": conflicts,
            }
        except Exception:
            return empty

    # ------------------------------------------------------------------ #
    # P3.6.4：Governance 输入收集（只读，fail-open）
    # ------------------------------------------------------------------ #
    def governance_inputs(self, as_of: str) -> Dict[str, Any]:
        empty = {
            "ceo_records": [], "strategic_insights": [], "conflicts": [],
            "states": {}, "qualities": {}, "state_changed_at": {},
        }
        if self.graph is None:
            return empty
        try:
            store = self.graph.graph
            records = (
                self.quality.ceo_decision_records(True, True) if self.quality else []
            )
            insights = []
            for node in store.query(NodeType.STRATEGIC_INSIGHT):
                data = dict(node.payload)
                data["node_id"] = node.id
                insights.append(data)
            states: Dict[str, str] = {}
            changed: Dict[str, str] = {}
            for node in store.query(NodeType.GOVERNANCE_RECORD):
                data = node.payload
                target = str(data.get("target_node_id", ""))
                stamp = str(data.get("created_at", ""))
                if target and stamp >= changed.get(target, ""):
                    states[target] = str(data.get("new_state", "active"))
                    changed[target] = stamp
            qualities: Dict[str, float] = {}
            for record in records:
                target = str(record.get("node_id", ""))
                qualities[target] = self.quality.quality_of(record) if self.quality else 0.0
            for insight in insights:
                qualities[str(insight.get("node_id", ""))] = float(
                    insight.get("confidence", insight.get("quality", 1.0)) or 0.0
                )
            active_records = [
                record for record in records
                if states.get(str(record.get("node_id", "")), "active") not in ("obsolete", "archived")
            ]
            conflicts = self.quality.detect_conflicts(active_records) if self.quality else []
            return {
                "ceo_records": records, "strategic_insights": insights,
                "conflicts": conflicts, "states": states, "qualities": qualities,
                "state_changed_at": changed,
            }
        except Exception:
            return empty

    # ------------------------------------------------------------------ #
    # 五路召回路由（确定性 Graph Retrieval）
    # ------------------------------------------------------------------ #
    def _route(
        self, ctx: MemoryContext
    ) -> Tuple[List[MemoryItem], List[KnowledgeConflict]]:
        reason = ctx.query_reason
        items: List[MemoryItem] = []
        conflicts: List[KnowledgeConflict] = []

        if reason in ("similar_game", "report_explain"):
            items += self._route_similar_game(ctx)
        if reason in ("strategy_effectiveness", "report_explain"):
            items += self._route_strategy(ctx)
        if reason in ("failure_reason", "report_explain"):
            items += self._route_recovery(ctx)
        if reason in ("execution_outcome", "report_explain"):
            items += self._route_execution(ctx)
        if reason in ("portfolio_context", "report_explain"):
            items += self._route_portfolio(ctx)
        if reason == "contradiction" or reason == "report_explain":
            conflicts = self._detect_conflicts(ctx)
        return items, conflicts

    def _quality_of(
        self, *, success_rate: float, created_at: str = "", simulated: bool = False
    ) -> float:
        if self.quality is None:
            return 0.0
        rec = {
            "outcome": {
                "success_rate": float(success_rate),
                "simulated": bool(simulated),
            },
            "created_at": created_at,
        }
        return self.quality.quality_of(rec)

    def _route_similar_game(self, ctx: MemoryContext) -> List[MemoryItem]:
        if not ctx.game_id:
            return []
        out: List[MemoryItem] = []
        for s in self.graph.similar_games(ctx.game_id):
            gid = s["game_id"]
            info = self.graph.why_game_succeeded(gid)
            srs = [float(st.get("success_rate", 0.0))
                   for st in info.get("strategy_results", [])]
            srs += [float(ex.get("success_rate", 0.0))
                    for ex in info.get("execution_outcomes", [])]
            sr = (sum(srs) / len(srs)) if srs else 0.0
            # 相似游戏是结构性参考，不做时间衰减（recency=1.0）
            q = self._quality_of(success_rate=sr)
            out += [MemoryItem(
                memory_type=SIMILAR_GAME,
                key=gid,
                success_rate=sr,
                weight=1.0,
                quality=q,
                evidence=[f"与 {ctx.game_id} 共享 {s['shared_count']} 个经验信号"],
                source_ref=f"GAME:{gid}",
                validated_at="",   # 相似游戏是结构性参考，无单一验证时间戳
            )]
        return out

    def _route_strategy(self, ctx: MemoryContext) -> List[MemoryItem]:
        dim = _LIFECYCLE_DIMENSION.get(str(ctx.lifecycle).lower()) if ctx.lifecycle else None
        out: List[MemoryItem] = []
        for n in self.graph.graph.query(NodeType.STRATEGY_RESULT):
            if dim and (n.payload.get("dimension") or "") != dim:
                continue
            sr = float(n.payload.get("success_rate", 0.0) or 0.0)
            sid = str(n.payload.get("strategy_id", ""))
            out += [MemoryItem(
                memory_type=STRATEGY_HISTORY,
                key=sid,
                success_rate=sr,
                weight=1.0,
                quality=self._quality_of(success_rate=sr, created_at=n.created_at),
                evidence=[f"{sid}（{n.payload.get('dimension', '')}）历史成功率 "
                          f"{sr:.0%}，样本 {n.payload.get('samples', 0)}"],
                source_ref=n.id,
                validated_at=n.created_at,
            )]
        return out

    def _route_execution(self, ctx: MemoryContext) -> List[MemoryItem]:
        out: List[MemoryItem] = []
        for n in self.graph.graph.query(NodeType.EXECUTION_OUTCOME):
            gid = str(n.payload.get("game_id", ""))
            if ctx.game_id and gid != ctx.game_id:
                continue
            sr = float(n.payload.get("success_rate", 0.0) or 0.0)
            out += [MemoryItem(
                memory_type=EXECUTION_OUTCOME,
                key=f"{gid}:{n.payload.get('domain', '')}",
                success_rate=sr,
                weight=1.0,
                quality=self._quality_of(success_rate=sr, created_at=n.created_at),
                evidence=[f"{gid} {n.payload.get('domain', '')} 执行成功率 {sr:.0%}"],
                source_ref=n.id,
                validated_at=n.created_at,
            )]
        return out

    def _route_recovery(self, ctx: MemoryContext) -> List[MemoryItem]:
        out: List[MemoryItem] = []
        for n in self.graph.graph.query(NodeType.RECOVERY_HISTORY):
            gid = str(n.payload.get("game_id", ""))
            if ctx.game_id and gid and gid != ctx.game_id:
                continue
            sr = float(n.payload.get("success_rate", 0.0) or 0.0)
            key = f"{n.payload.get('failure_type', '')}:{n.payload.get('recovery_strategy', '')}"
            out += [MemoryItem(
                memory_type=RECOVERY_EXPERIENCE,
                key=key,
                success_rate=sr,
                weight=1.0,
                quality=self._quality_of(success_rate=sr, created_at=n.created_at),
                evidence=[f"故障 {n.payload.get('failure_type', '')} 恢复成功率 {sr:.0%}"],
                source_ref=n.id,
                validated_at=n.created_at,
            )]
        return out

    def _route_portfolio(self, ctx: MemoryContext) -> List[MemoryItem]:
        out: List[MemoryItem] = []
        for n in self.graph.graph.query(NodeType.PORTFOLIO_DECISION):
            gid = str(n.payload.get("game_id", ""))
            if ctx.game_id and gid != ctx.game_id:
                continue
            conf = float(n.payload.get("confidence", 0.0) or 0.0)
            out += [MemoryItem(
                memory_type=PORTFOLIO_DECISION,
                key=gid,
                success_rate=conf,   # 推荐置信作成功率代理（仅组合上下文，文档注明）
                weight=1.0,
                quality=self._quality_of(success_rate=conf, created_at=n.created_at),
                evidence=[f"{gid} 组合建议 {n.payload.get('recommendation', '')} "
                          f"（guard={n.payload.get('guard', '')}）"],
                source_ref=n.id,
                validated_at=n.created_at,
            )]
        return out

    def _detect_conflicts(self, ctx: MemoryContext) -> List[KnowledgeConflict]:
        if self.quality is None:
            return []
        if ctx.game_id:
            recs = [r for r in self.quality.ceo_decision_records()
                    if r.get("game_id") == ctx.game_id]
            return self.quality.detect_conflicts(recs)
        return self.quality.detect_conflicts()

    # ------------------------------------------------------------------ #
    # 可解释输出
    # ------------------------------------------------------------------ #
    @staticmethod
    def _explain(
        items: List[MemoryItem],
        conflicts: List[KnowledgeConflict],
        strategic_insights: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        if not items and not conflicts and not strategic_insights:
            return "无可召回记忆（图为空或质量门过滤）。"
        lines: List[str] = [f"召回 {len(items)} 条记忆"]
        sims = [m.key for m in items if m.memory_type == SIMILAR_GAME]
        if sims:
            lines += [f"相似游戏：{', '.join(sims[:5])}"]
        validated = [m for m in items if m.quality > 0 and m.success_rate >= 0]
        if validated:
            sr = sum(m.success_rate for m in validated) / len(validated)
            lines += [f"历史成功率：{sr:.0%}（{len(validated)} 条已验证）"]
        ts = [m.validated_at for m in items if m.validated_at]
        if ts:
            lines += [f"最近验证：{max(ts)}"]
        if conflicts:
            keys = "、".join(sorted({c.key for c in conflicts}))
            lines += [f"冲突：{len(conflicts)} 组（{keys}）"]
        else:
            lines += ["冲突：无"]
        if strategic_insights:
            lines += [f"战略规律：{len(strategic_insights)} 条"]
        return "；".join(lines) + "。"

    def _empty_bundle(self, context: MemoryContext) -> KnowledgeBundle:
        return KnowledgeBundle(
            memories=[],
            confidence=0.0,
            explanation="无可召回记忆（图不可用）。",
            source_chain=[],
            conflicts=[],
            retrieval_trace=RetrievalTrace(
                query=f"{context.query_reason}:{context.game_id}", sources=[]
            ),
            strategic_insights=[],
            real_api_called=False,
        )


# ---------------------------------------------------------------------- #
# 薄映射：bundle -> KnowledgeSignal（供既有消费者 P3.4 Ranker / P3.3 Loop）
# ---------------------------------------------------------------------- #
def bundle_to_signal(bundle: KnowledgeBundle) -> KnowledgeSignal:
    """把检索结果映射回 P3.5.1 ``KnowledgeSignal``（只读搬运，不做新决策）。"""
    memories = bundle.memories
    validated = [m for m in memories if m.quality > 0]
    sr = (
        sum(m.success_rate * m.weight for m in validated)
        / sum(m.weight for m in validated)
        if validated else 0.0
    )
    risk_flags: List[str] = []
    if bundle.conflicts:
        risk_flags += ["knowledge_conflict"]
    ev = bundle.explanation.splitlines() or [bundle.explanation]
    return KnowledgeSignal(
        confidence=bundle.confidence,
        historical_success_rate=sr,
        similar_case_count=len(memories),
        risk_flags=risk_flags,
        evidence=[e for e in ev if e],
    )


class MemoryControllerAdvisor:
    """把 MemoryController 接到 P3.5.1 既有 advisor 注入点（生产 pipeline 用）。

    不新增任何构造参数：Optimizer/Loop 看到的仍是同一 ``KnowledgeSignal`` 接口，
    内部由 controller 召回 + bundle_to_signal 映射（G1 读侧闭环）。
    """

    def __init__(self, controller: MemoryController, role: str = "portfolio") -> None:
        self.controller = controller
        self.role = role

    @property
    def real_api_called(self) -> bool:
        return False

    def advise_portfolio(self, game: Any) -> KnowledgeSignal:
        gid = getattr(game, "game_id", None) or str(game)
        bundle = self.controller.retrieve(
            MemoryContext(query_reason="report_explain", game_id=str(gid))
        )
        return bundle_to_signal(bundle)

    def advise_strategy(self, proposal: Any) -> KnowledgeSignal:
        bundle = self.controller.retrieve(
            MemoryContext(query_reason="strategy_effectiveness")
        )
        return bundle_to_signal(bundle)


__all__ = [
    "MemoryContext",
    "MemoryItem",
    "RetrievalTrace",
    "KnowledgeBundle",
    "MemoryController",
    "MemoryControllerAdvisor",
    "bundle_to_signal",
    "SIMILAR_GAME",
    "STRATEGY_HISTORY",
    "EXECUTION_OUTCOME",
    "RECOVERY_EXPERIENCE",
    "PORTFOLIO_DECISION",
]
