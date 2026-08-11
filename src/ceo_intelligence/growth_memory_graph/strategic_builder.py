"""
P3.6.2 — Strategic Summary Memory（战略规律归纳器，纯计算，只读）。

定位：**Retrieval → Understanding**。P3.6.1 给 CEO 找证据；P3.6.2 从大量证据中
总结规律（Strategic Insight）。第一阶段是**规则归纳器**，不是 LLM 自由发挥。

第一批 Insight 类型（确定性规则）：
1. **Strategy Insight**   —— 来自 MemoryItem(strategy_history)，按策略 key 聚类；
2. **Failure Insight**    —— 来自 MemoryItem(recovery_experience)，按故障聚类，
   common_causes 由 failure_type keyword 规则确定性派生；
3. **Action Pattern Insight** —— 来自 ceo_records（CEO_DECISION），按
   decision_payload.action 聚类，权重沿用 P3.5.2（realized=0.5 / simulated=0.2）；
4. **Lifecycle Insight**  —— 来自 ceo_records + lifecycle_map（E15.1.2 真实源注入，
   **不把 lifecycle 冗余复制进 Graph**），按 stage 聚类；无 lifecycle_map/ceo_records → 跳过。

纪律（用户 D1/D3 冻结 + 全库一致）：
- ❌ **StrategicInsight 不复用 DecisionKnowledgeRecord**（语义不同：一次具体决策反馈 vs
  从大量决策中总结的规律；CEO_DECISION → StrategicInsight 是派生关系，不是等价）；
- ❌ 本模块纯计算：**禁 add_node / add_edge / graph mutation / 写回任何源**；
- ❌ 不修改 StrategyLoop / Ranker、不产生 Action、不执行优化；
- ✅ 确定性：无 LLM、无随机性；`real_api_called` 恒 False；
- ✅ fail-open：lifecycle_map / ceo_records 可空，缺啥跳过啥，不中断。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import GraphNode, NodeType, node_id
from .controller import (
    SIMILAR_GAME,
    STRATEGY_HISTORY,
    RECOVERY_EXPERIENCE,
    MemoryItem,
)

# 置信常量（对齐全库 Laplace 语义）
_CONFIDENCE_K = 3.0
_MIN_SAMPLES = 3          # 样本不足过滤阈值（对齐 advisor _MIN_SAMPLES_FOR_RISK）
_SUCCESS_SR = 0.5         # 判定"成功模式"的成功率阈值

# P3.5.2 权重（外部事实=1.0；CEO 实际=0.5；模拟=0.2）
_W_EXTERNAL = 1.0
_W_CEO_REALIZED = 0.5
_W_CEO_SIMULATED = 0.2

# 生命周期 → 桶（说明性；实际按 lifecycle_map 的 stage 值聚类）
# 阶段来源：E15.1.2 stage_of(game_id) → launch / growth / maturity / decline
_LIFECYCLE_STAGES = ("launch", "growth", "maturity", "decline")

# failure_type → common_causes（确定性 keyword 规则）
_CAUSE_RULES: List[tuple] = [
    ("cpi", "CPI increase"),
    ("fatigue", "creative fatigue"),
    ("retention", "retention drop"),
    ("roas", "ROAS decline"),
    ("cvr", "store CVR drop"),
    ("crash", "technical crash"),
]

# action 关键字 → category（确定性映射，默认 portfolio）
_ACTION_CATEGORY_RULES: List[tuple] = [
    ("creative", "creative"),
    ("ua_", "ua"),
    ("budget", "portfolio"),
    ("scale", "portfolio"),
    ("monet", "monetization"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_insight_id() -> str:
    return f"ins_{uuid.uuid4().hex[:12]}"


def _common_causes(failure_type: str) -> List[str]:
    ft = str(failure_type or "").lower()
    return [label for kw, label in _CAUSE_RULES if kw in ft]


def _action_category(action: str) -> str:
    a = str(action or "").lower()
    for kw, cat in _ACTION_CATEGORY_RULES:
        if kw in a:
            return cat
    return "portfolio"


def _is_success(rec: Dict[str, Any]) -> Optional[bool]:
    """CEO_DECISION 记录的成败判定（对齐 quality 层）。"""
    oc = rec.get("outcome") or {}
    if oc.get("success") is not None:
        return bool(oc["success"])
    sr = oc.get("success_rate")
    if sr is None:
        return None
    return float(sr) >= _SUCCESS_SR


def _ceo_weight(rec: Dict[str, Any]) -> float:
    oc = rec.get("outcome") or {}
    return _W_CEO_SIMULATED if oc.get("simulated") else _W_CEO_REALIZED


@dataclass
class StrategicInsight:
    """从大量记忆中总结出的战略规律（用户冻结 schema）。

    **不是** DecisionKnowledgeRecord（那是一次具体决策反馈；这是跨决策的规律）。
    """

    insight_id: str = ""
    category: str = ""                    # lifecycle | ua | monetization | creative | portfolio
    statement: str = ""                   # 人可读规律（确定性模板）
    evidence_count: int = 0               # = len(supporting_memories)
    success_rate: float = 0.0
    confidence: float = 0.0               # eff/(eff+K)，eff=Σ(weight×quality)（样本×质量）
    supporting_memories: List[str] = field(default_factory=list)   # source_ref 列表
    counter_examples: List[str] = field(default_factory=list)      # 相反结果 source_ref
    created_at: str = ""
    last_validated_at: str = ""
    real_api_called: bool = False

    def __post_init__(self) -> None:
        if not self.insight_id:
            self.insight_id = _new_insight_id()
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.last_validated_at:
            self.last_validated_at = self.created_at

    # ------------------------------------------------------------------ #
    # 图节点互转（供 recorder.record_insight 写入）
    # ------------------------------------------------------------------ #
    def node_id(self) -> str:
        return node_id(NodeType.STRATEGIC_INSIGHT, self.insight_id)

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.STRATEGIC_INSIGHT,
            label=f"{self.category}:{self.statement[:40]}",
            payload={
                "insight_id": self.insight_id,
                "category": self.category,
                "statement": self.statement,
                "evidence_count": int(self.evidence_count),
                "success_rate": round(float(self.success_rate), 6),
                "confidence": round(float(self.confidence), 6),
                "supporting_memories": list(self.supporting_memories),
                "counter_examples": list(self.counter_examples),
                "created_at": self.created_at,
                "last_validated_at": self.last_validated_at,
                "real_api_called": False,
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "StrategicInsight":
        p = n.payload
        return cls(
            insight_id=str(p.get("insight_id", "")),
            category=str(p.get("category", "")),
            statement=str(p.get("statement", "")),
            evidence_count=int(p.get("evidence_count", 0)),
            success_rate=float(p.get("success_rate", 0.0)),
            confidence=float(p.get("confidence", 0.0)),
            supporting_memories=list(p.get("supporting_memories", [])),
            counter_examples=list(p.get("counter_examples", [])),
            created_at=str(p.get("created_at", "")),
            last_validated_at=str(p.get("last_validated_at", "")),
            real_api_called=bool(p.get("real_api_called", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "category": self.category,
            "statement": self.statement,
            "evidence_count": int(self.evidence_count),
            "success_rate": round(float(self.success_rate), 6),
            "confidence": round(float(self.confidence), 6),
            "supporting_memories": list(self.supporting_memories),
            "counter_examples": list(self.counter_examples),
            "created_at": self.created_at,
            "last_validated_at": self.last_validated_at,
            "real_api_called": bool(self.real_api_called),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategicInsight":
        return cls(
            insight_id=str(d.get("insight_id", "")),
            category=str(d.get("category", "")),
            statement=str(d.get("statement", "")),
            evidence_count=int(d.get("evidence_count", 0)),
            success_rate=float(d.get("success_rate", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            supporting_memories=list(d.get("supporting_memories", [])),
            counter_examples=list(d.get("counter_examples", [])),
            created_at=str(d.get("created_at", "")),
            last_validated_at=str(d.get("last_validated_at", "")),
            real_api_called=bool(d.get("real_api_called", False)),
        )


class StrategicMemoryBuilder:
    """规则归纳器：MemoryItem[] + ceo_records → StrategicInsight[]（纯计算）。"""

    def build(
        self,
        memories: List[MemoryItem],
        as_of: str = "",
        *,
        lifecycle_map: Optional[Dict[str, str]] = None,
        ceo_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[StrategicInsight]:
        """归纳战略规律（确定性；lifecycle_map / ceo_records 可空，缺啥跳过啥）。

        - ``lifecycle_map``：game_id → lifecycle_stage（来自 E15.1.2，注入不冗余复制）
        - ``ceo_records``：CEO_DECISION payload 列表（action 级规则 + 生命周期聚类的来源）
        """
        insights: List[StrategicInsight] = []
        insights += self._build_strategy(memories)
        insights += self._build_failure(memories)
        if ceo_records:
            insights += self._build_action_pattern(ceo_records)
            if lifecycle_map:
                insights += self._build_lifecycle(ceo_records, lifecycle_map)
        return insights

    # ------------------------------------------------------------------ #
    # 1) Strategy Insight（来自 strategy_history 记忆）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_strategy(memories: List[MemoryItem]) -> List[StrategicInsight]:
        groups: Dict[str, List[MemoryItem]] = {}
        for m in memories:
            if m.memory_type == STRATEGY_HISTORY:
                groups.setdefault(m.key, []).append(m)
        out: List[StrategicInsight] = []
        for key in sorted(groups):
            recs = groups[key]
            sr, eff, conf = _aggregate(recs)
            if len(recs) < _MIN_SAMPLES:
                continue
            category = _category_from_key(key)
            counter = [m.source_ref for m in recs
                       if (m.success_rate < _SUCCESS_SR) != (sr < _SUCCESS_SR)]
            out.append(StrategicInsight(
                category=category,
                statement=(
                    f"策略 {key} 历史成功率 {sr:.0%}（{len(recs)} 条证据）"
                    + ("，建议谨慎" if sr < _SUCCESS_SR else "，可维持/放量")
                ),
                evidence_count=len(recs),
                success_rate=sr,
                confidence=conf,
                supporting_memories=[m.source_ref for m in recs if m.source_ref],
                counter_examples=counter,
            ))
        return out

    # ------------------------------------------------------------------ #
    # 2) Failure Insight（来自 recovery_experience 记忆）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_failure(memories: List[MemoryItem]) -> List[StrategicInsight]:
        groups: Dict[str, List[MemoryItem]] = {}
        for m in memories:
            if m.memory_type == RECOVERY_EXPERIENCE:
                failure_type = str(m.key).split(":", 1)[0]
                groups.setdefault(failure_type, []).append(m)
        out: List[StrategicInsight] = []
        for ft in sorted(groups):
            recs = groups[ft]
            sr, eff, conf = _aggregate(recs)
            if len(recs) < _MIN_SAMPLES:
                continue
            causes = _common_causes(ft)
            cause_txt = f"；常见诱因：{'、'.join(causes)}" if causes else ""
            out.append(StrategicInsight(
                category=_category_from_key(ft),
                statement=(
                    f"故障 {ft} 恢复成功率 {sr:.0%}（{len(recs)} 条经验）"
                    f"{cause_txt}"
                ),
                evidence_count=len(recs),
                success_rate=sr,
                confidence=conf,
                supporting_memories=[m.source_ref for m in recs if m.source_ref],
                counter_examples=[],
            ))
        return out

    # ------------------------------------------------------------------ #
    # 3) Action Pattern Insight（来自 CEO_DECISION，P3.5.2 权重）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_action_pattern(
        ceo_records: List[Dict[str, Any]]
    ) -> List[StrategicInsight]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in ceo_records:
            dp = r.get("decision_payload") or {}
            action = str(dp.get("action", "") or "")
            if action:
                groups.setdefault(action, []).append(r)
        out: List[StrategicInsight] = []
        for action in sorted(groups):
            recs = groups[action]
            if len(recs) < _MIN_SAMPLES:
                continue
            wsum = sum(_ceo_weight(r) for r in recs)
            ssum = sum(
                float((r.get("outcome") or {}).get("success_rate", 0.0) or 0.0)
                * _ceo_weight(r) for r in recs
            )
            sr = (ssum / wsum) if wsum else 0.0
            eff = wsum
            conf = eff / (eff + _CONFIDENCE_K)
            successes = [r for r in recs if _is_success(r) is True]
            failures = [r for r in recs if _is_success(r) is False]
            counter = [r.get("record_id", "") or "" for r in successes] if sr < _SUCCESS_SR \
                else [r.get("record_id", "") or "" for r in failures]
            out.append(StrategicInsight(
                category=_action_category(action),
                statement=(
                    f"动作 {action} 历史成功率 {sr:.0%}（{len(recs)} 条决策）"
                    + ("，建议渐进/谨慎" if sr < _SUCCESS_SR else "，可继续")
                ),
                evidence_count=len(recs),
                success_rate=sr,
                confidence=conf,
                supporting_memories=[
                    f"ceo_decision:{r.get('record_id', '')}" for r in recs
                    if r.get("record_id")
                ],
                counter_examples=[c for c in counter if c],
            ))
        return out

    # ------------------------------------------------------------------ #
    # 4) Lifecycle Insight（ceo_records + lifecycle_map，E15.1.2 注入）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_lifecycle(
        ceo_records: List[Dict[str, Any]],
        lifecycle_map: Dict[str, str],
    ) -> List[StrategicInsight]:
        # stage → action → records
        buckets: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for r in ceo_records:
            stage = lifecycle_map.get(r.get("game_id", ""))
            if not stage:
                continue
            dp = r.get("decision_payload") or {}
            action = str(dp.get("action", "") or "")
            if not action:
                continue
            buckets.setdefault(stage, {}).setdefault(action, []).append(r)

        out: List[StrategicInsight] = []
        for stage in sorted(buckets):
            for action in sorted(buckets[stage]):
                recs = buckets[stage][action]
                if len(recs) < _MIN_SAMPLES:
                    continue
                wsum = sum(_ceo_weight(r) for r in recs)
                ssum = sum(
                    float((r.get("outcome") or {}).get("success_rate", 0.0) or 0.0)
                    * _ceo_weight(r) for r in recs
                )
                sr = (ssum / wsum) if wsum else 0.0
                eff = wsum
                conf = eff / (eff + _CONFIDENCE_K)
                out.append(StrategicInsight(
                    category="lifecycle",
                    statement=(
                        f"{stage} 生命周期：动作 {action} 成功率 {sr:.0%}"
                        f"（{len(recs)} 条决策）"
                    ),
                    evidence_count=len(recs),
                    success_rate=sr,
                    confidence=conf,
                    supporting_memories=[
                        f"ceo_decision:{r.get('record_id', '')}" for r in recs
                        if r.get("record_id")
                    ],
                    counter_examples=[],
                ))
        return out


def _aggregate(items: List[MemoryItem]) -> tuple:
    """加权成功率 / 加权有效样本 / Laplace 置信（样本×质量）。"""
    wsum = sum(m.weight * max(0.0, m.quality) for m in items)
    ssum = sum(m.success_rate * m.weight * max(0.0, m.quality) for m in items)
    sr = (ssum / wsum) if wsum else 0.0
    eff = wsum
    conf = eff / (eff + _CONFIDENCE_K) if eff > 0 else 0.0
    return sr, eff, conf


def _category_from_key(key: str) -> str:
    k = str(key or "").lower()
    if any(t in k for t in ("creative", "ctr", "fatigue")):
        return "creative"
    if any(t in k for t in ("monet", "revenue", "pricing")):
        return "monetization"
    if any(t in k for t in ("ua", "cpi", "roas", "install")):
        return "ua"
    return "portfolio"


__all__ = ["StrategicInsight", "StrategicMemoryBuilder", "_MIN_SAMPLES"]
