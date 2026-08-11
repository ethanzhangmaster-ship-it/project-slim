"""
P3.6.3 — Memory Reflection Loop（认知复盘归纳器，纯计算，只读）。

定位：**Understanding → Self-Correction**。P3.6.1 给 CEO 找证据、P3.6.2 总结规律；
P3.6.3 让 AI CEO **修改自己的认知模型**——每天对昨日决策复盘：

    Yesterday Decisions
        ↓
    What was right?   → wins（ReflectionItem，verdict=True）
    What was wrong?   → mistakes（ReflectionItem，verdict=False）
    What changed?     → changed_beliefs（BeliefChange：窗口证据 vs 既有规律方向冲突
                        + 同键正反结果冲突）
    What should we believe now? → new_rules（NewRule：失败 action → caution /
                        全胜 action → reinforce；认知声明，不改消费端权重）

全部**确定性规则**（无 LLM/embedding/随机）。输出 `CEOReflection` 供
CEO 报告"十、Memory Reflection"展示，并可经 `KnowledgeFeedbackRecorder.record_reflection()`
写图（append-only 审计链，幂等键 = reflection:{period}）。

纪律（与全库一致，纯计算）：
- ❌ 本模块**禁 add_node / add_edge / graph mutation / 写回任何源**；
- ❌ 不修改 StrategyLoop / Ranker / Optimizer（new_rules 只进报告）；
- ❌ 不产生 Action、不执行优化、不调 Provider / SafeExecutor / DecisionEngine；
- ✅ 确定性：同输入同输出（generated_at 由 as_of 注入）；
- ✅ fail-open：空窗口 / 缺输入 → 空 Reflection 对象，不中断主链；
- ✅ ``real_api_called`` 恒 False。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .quality import KnowledgeConflict

# 判定阈值（对齐全库语义）
_SUCCESS_SR = 0.5             # success_rate >= 0.5 视为成功
# P3.5.2 权重（CEO 自生成证据：realized=0.5 / simulated=0.2）
_W_CEO_REALIZED = 0.5
_W_CEO_SIMULATED = 0.2
# new_rules 样本阈值
_RULE_MIN_FAILURES = 2        # 失败 >= 2 → caution 规则
_RULE_MIN_WINS = 3            # 成功 >= 3 且失败 0 → reinforce 规则


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_verdict(rec: Dict[str, Any]) -> Optional[bool]:
    """已验证记录的成败判定（对齐 quality 层）：显式 success 优先，否则 sr>=0.5。"""
    oc = rec.get("outcome") or {}
    if oc.get("success") is not None:
        return bool(oc["success"])
    sr = oc.get("success_rate")
    if sr is None:
        return None
    return float(sr) >= _SUCCESS_SR


def _record_sr(rec: Dict[str, Any]) -> float:
    oc = rec.get("outcome") or {}
    return float(oc.get("success_rate", 0.0) or 0.0)


def _ceo_weight(rec: Dict[str, Any]) -> float:
    oc = rec.get("outcome") or {}
    return _W_CEO_SIMULATED if oc.get("simulated") else _W_CEO_REALIZED


def _record_action(rec: Dict[str, Any]) -> str:
    dp = rec.get("decision_payload") or {}
    return str(dp.get("action", "") or "")


def _in_window(period: str, created_at: str) -> bool:
    """period = ISO 日期（"2026-07-31"，UTC 日语义）；startswith 确定性过滤。

    空 created_at 不属任何窗口。
    """
    if not period or not created_at:
        return False
    return str(created_at).startswith(str(period))


def _weighted_sr(recs: List[Dict[str, Any]]) -> float:
    """窗口内记录加权成功率（P3.5.2 CEO 权重）。"""
    wsum = sum(_ceo_weight(r) for r in recs)
    if wsum <= 0:
        return 0.0
    ssum = sum(_record_sr(r) * _ceo_weight(r) for r in recs)
    return ssum / wsum


# ---------------------------------------------------------------------- #
# 数据契约（用户冻结：wins / mistakes / changed_beliefs / new_rules）
# ---------------------------------------------------------------------- #
@dataclass
class ReflectionItem:
    """wins / mistakes 的单条复盘（证据链完整：当时看了什么 + 结果）。"""

    record_id: str = ""
    game_id: str = ""
    decision_type: str = ""
    action: str = ""
    verdict: bool = True              # True=win / False=mistake
    success_rate: float = 0.0
    knowledge_signal: Dict[str, Any] = field(default_factory=dict)  # 当时看了什么
    source_ref: str = ""              # ceo_decision:{record_id}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "game_id": self.game_id,
            "decision_type": self.decision_type,
            "action": self.action,
            "verdict": bool(self.verdict),
            "success_rate": round(float(self.success_rate), 6),
            "knowledge_signal": dict(self.knowledge_signal),
            "source_ref": self.source_ref,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReflectionItem":
        return cls(
            record_id=str(d.get("record_id", "")),
            game_id=str(d.get("game_id", "")),
            decision_type=str(d.get("decision_type", "")),
            action=str(d.get("action", "")),
            verdict=bool(d.get("verdict", True)),
            success_rate=float(d.get("success_rate", 0.0)),
            knowledge_signal=dict(d.get("knowledge_signal", {}) or {}),
            source_ref=str(d.get("source_ref", "")),
        )


@dataclass
class BeliefChange:
    """changed_beliefs 条目：一条既有信念被窗口证据修正。"""

    belief_id: str = ""               # insight_id 或 conflict:{key}
    belief: str = ""                  # 人可读（insight.statement 或 conflict key）
    previous_success_rate: float = 0.0
    window_success_rate: float = 0.0
    reason: str = ""
    evidence: List[str] = field(default_factory=list)   # record_id 列表

    def to_dict(self) -> Dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "belief": self.belief,
            "previous_success_rate": round(float(self.previous_success_rate), 6),
            "window_success_rate": round(float(self.window_success_rate), 6),
            "reason": self.reason,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BeliefChange":
        return cls(
            belief_id=str(d.get("belief_id", "")),
            belief=str(d.get("belief", "")),
            previous_success_rate=float(d.get("previous_success_rate", 0.0)),
            window_success_rate=float(d.get("window_success_rate", 0.0)),
            reason=str(d.get("reason", "")),
            evidence=list(d.get("evidence", [])),
        )


@dataclass
class NewRule:
    """new_rules 条目：从窗口结果归纳的认知规则（只进报告，不改消费端）。"""

    rule_id: str = ""                 # rule:{action}
    action: str = ""
    rule_type: str = ""               # "caution" | "reinforce"
    failures: int = 0
    successes: int = 0
    statement: str = ""
    evidence: List[str] = field(default_factory=list)   # record_id 列表

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action": self.action,
            "rule_type": self.rule_type,
            "failures": int(self.failures),
            "successes": int(self.successes),
            "statement": self.statement,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NewRule":
        return cls(
            rule_id=str(d.get("rule_id", "")),
            action=str(d.get("action", "")),
            rule_type=str(d.get("rule_type", "")),
            failures=int(d.get("failures", 0)),
            successes=int(d.get("successes", 0)),
            statement=str(d.get("statement", "")),
            evidence=list(d.get("evidence", [])),
        )


@dataclass
class CEOReflection:
    """一次 CEO 认知复盘（用户冻结四段 + 审计字段）。

    **不是** DecisionKnowledgeRecord / StrategicInsight（那是决策反馈与规律；
    这是对一段时期的认知修正声明，写图幂等键 = reflection:{period}）。
    """

    period: str = ""
    wins: List[ReflectionItem] = field(default_factory=list)
    mistakes: List[ReflectionItem] = field(default_factory=list)
    unresolved_count: int = 0
    changed_beliefs: List[BeliefChange] = field(default_factory=list)
    new_rules: List[NewRule] = field(default_factory=list)
    evidence_count: int = 0
    generated_at: str = ""
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "wins": [w.to_dict() for w in self.wins],
            "mistakes": [m.to_dict() for m in self.mistakes],
            "unresolved_count": int(self.unresolved_count),
            "changed_beliefs": [b.to_dict() for b in self.changed_beliefs],
            "new_rules": [r.to_dict() for r in self.new_rules],
            "evidence_count": int(self.evidence_count),
            "generated_at": self.generated_at,
            "real_api_called": bool(self.real_api_called),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CEOReflection":
        return cls(
            period=str(d.get("period", "")),
            wins=[ReflectionItem.from_dict(w) for w in d.get("wins", [])],
            mistakes=[ReflectionItem.from_dict(m) for m in d.get("mistakes", [])],
            unresolved_count=int(d.get("unresolved_count", 0)),
            changed_beliefs=[
                BeliefChange.from_dict(b) for b in d.get("changed_beliefs", [])
            ],
            new_rules=[NewRule.from_dict(r) for r in d.get("new_rules", [])],
            evidence_count=int(d.get("evidence_count", 0)),
            generated_at=str(d.get("generated_at", "")),
            real_api_called=bool(d.get("real_api_called", False)),
        )


class MemoryReflectionBuilder:
    """认知复盘归纳器：窗口 CEO 记录 → CEOReflection（纯计算，确定性）。"""

    def build(
        self,
        period: str,
        ceo_records: List[Dict[str, Any]],
        strategic_insights: Optional[List[Dict[str, Any]]] = None,
        conflicts: Optional[List[KnowledgeConflict]] = None,
        as_of: str = "",
    ) -> CEOReflection:
        """归纳一次复盘（fail-open：空窗口 → 空 Reflection 对象）。

        - ``ceo_records``：CEO_DECISION payload 列表（**可传全量**，内部按 period 过滤）
        - ``strategic_insights``：STRATEGIC_INSIGHT payload 列表（changed_beliefs 对比基准）
        - ``conflicts``：窗口内 KnowledgeConflict 列表（并入 changed_beliefs）
        - ``as_of``：generated_at（幂等测试须注入固定值；默认 now）
        """
        window = [r for r in (ceo_records or []) if _in_window(period, r.get("created_at", ""))]
        window_ids = {str(r.get("record_id", "")) for r in window if r.get("record_id")}

        wins: List[ReflectionItem] = []
        mistakes: List[ReflectionItem] = []
        unresolved = 0
        for r in window:
            verdict = _record_verdict(r)
            item = ReflectionItem(
                record_id=str(r.get("record_id", "")),
                game_id=str(r.get("game_id", "")),
                decision_type=str(r.get("decision_type", "")),
                action=_record_action(r),
                verdict=bool(verdict) if verdict is not None else True,
                success_rate=_record_sr(r),
                knowledge_signal=dict(r.get("knowledge_signal", {}) or {}),
                source_ref=f"ceo_decision:{r.get('record_id', '')}",
            )
            if verdict is True:
                wins += [item]
            elif verdict is False:
                mistakes += [item]
            else:
                unresolved += 1

        wins.sort(key=lambda i: i.record_id)
        mistakes.sort(key=lambda i: i.record_id)

        beliefs = self._changed_beliefs(
            window, window_ids, strategic_insights or [], conflicts or []
        )
        rules = self._new_rules(window)

        evidence_count = len(wins) + len(mistakes)
        return CEOReflection(
            period=period,
            wins=wins,
            mistakes=mistakes,
            unresolved_count=unresolved,
            changed_beliefs=beliefs,
            new_rules=rules,
            evidence_count=evidence_count,
            generated_at=as_of or _now_iso(),
            real_api_called=False,
        )

    # ------------------------------------------------------------------ #
    # changed_beliefs：窗口证据 vs 既有规律方向冲突 + conflicts 并入
    # ------------------------------------------------------------------ #
    @staticmethod
    def _changed_beliefs(
        window: List[Dict[str, Any]],
        window_ids: set,
        insights: List[Dict[str, Any]],
        conflicts: List[KnowledgeConflict],
    ) -> List[BeliefChange]:
        out: List[BeliefChange] = []

        # ① insight 关联窗口记录（supporting_memories 中 ceo_decision:{id} ∩ 窗口）
        for ins in insights:
            sid = str(ins.get("insight_id", ""))
            prev_sr = float(ins.get("success_rate", 0.0) or 0.0)
            linked = [
                r for r in window
                if f"ceo_decision:{r.get('record_id', '')}" in (ins.get("supporting_memories") or [])
            ]
            if not linked:
                continue
            win_sr = _weighted_sr(linked)
            prev_dir = prev_sr >= _SUCCESS_SR
            win_dir = win_sr >= _SUCCESS_SR
            if prev_dir == win_dir:
                continue   # 方向一致 = 规律被验证，不算信念改变
            out.append(BeliefChange(
                belief_id=sid,
                belief=str(ins.get("statement", "")),
                previous_success_rate=prev_sr,
                window_success_rate=win_sr,
                reason=(
                    f"窗口证据与既有规律方向相反（规律 sr={prev_sr:.0%} vs "
                    f"窗口 sr={win_sr:.0%}）"
                ),
                evidence=[r.get("record_id", "") for r in linked if r.get("record_id")],
            ))

        # ② conflicts 并入（同键正反结果并存 = 认知冲突）
        for c in conflicts or []:
            out.append(BeliefChange(
                belief_id=f"conflict:{c.key}",
                belief=str(c.key),
                previous_success_rate=0.0,     # 无单一先前信念
                window_success_rate=0.0,
                reason=(
                    f"同一知识键 {c.key!r} 出现相反结果"
                    f"（成功 {len(c.successes)} vs 失败 {len(c.failures)}）"
                ),
                evidence=[
                    str(r.get("record_id", "")) for r in (c.successes + c.failures)
                    if r.get("record_id")
                ],
            ))

        out.sort(key=lambda b: b.belief_id)
        return out

    # ------------------------------------------------------------------ #
    # new_rules：按 action 聚类（失败 → caution / 全胜 → reinforce）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _new_rules(window: List[Dict[str, Any]]) -> List[NewRule]:
        groups: Dict[str, Dict[str, Any]] = {}
        for r in window:
            action = _record_action(r)
            if not action:
                continue
            g = groups.setdefault(action, {"failures": 0, "successes": 0, "evidence": []})
            verdict = _record_verdict(r)
            if verdict is True:
                g["successes"] += 1
            elif verdict is False:
                g["failures"] += 1
            if r.get("record_id"):
                g["evidence"] += [str(r["record_id"])]

        out: List[NewRule] = []
        for action in sorted(groups):
            g = groups[action]
            fails, wins = g["failures"], g["successes"]
            if fails >= _RULE_MIN_FAILURES:
                out.append(NewRule(
                    rule_id=f"rule:{action}",
                    action=action,
                    rule_type="caution",
                    failures=fails,
                    successes=wins,
                    statement=(
                        f"动作 {action} 本周期失败 {fails} 次（成功 {wins}）"
                        f"→ 未来同类决策建议强制审批/降权"
                    ),
                    evidence=list(g["evidence"]),
                ))
            elif wins >= _RULE_MIN_WINS and fails == 0:
                out.append(NewRule(
                    rule_id=f"rule:{action}",
                    action=action,
                    rule_type="reinforce",
                    failures=0,
                    successes=wins,
                    statement=(
                        f"动作 {action} 本周期全胜 {wins} 次 → 可维持当前置信"
                    ),
                    evidence=list(g["evidence"]),
                ))
        out.sort(key=lambda r: r.rule_id)
        return out


__all__ = [
    "CEOReflection",
    "ReflectionItem",
    "BeliefChange",
    "NewRule",
    "MemoryReflectionBuilder",
    "_RULE_MIN_FAILURES",
    "_RULE_MIN_WINS",
]
