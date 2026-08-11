"""
P3.5.3 — Memory Quality Governance（知识质量管理层，只读）。

定位：保证「记住的是正确的东西」，防止 Memory Drift（bad memory → bad advice →
bad decision → more bad memory）。在 P3.5.2 经验闭环之上加三道闸：

1. **KnowledgeScore**：给每条知识算质量分
   ``quality = success_rate × recency_factor × source_weight``
   - recency：1.0（今天）线性衰减到 0.2（一年前）：``max(0.2, 1 - 0.8*age/365)``
   - source_weight：realized=1.0 / simulated=0.5（模拟结果可信度减半）
   - 未验证（无 outcome）→ 0 分（不参与 Advisor）
2. **Contradiction Detection**：同键（decision_type:action）同时存在成功与失败结果 →
   产生 ``KnowledgeConflict``，**保留双记录不覆盖**（图本就 append-only，不做删除）。
3. **KnowledgeQualityFilter**：Advisor 只消费 ``quality >= min_quality`` 的经验。

纪律（与全库一致，只读）：

- ❌ 不写 Graph（禁 add_node/add_edge）、不写回 5 源、不调 consolidate；
- ❌ 不决策/不执行/不调 Provider / SafeExecutor / DecisionEngine；
- ✅ ``real_api_called`` 恒 False；
- ✅ fail-open：图不可用 / 解析异常 → 空结果，不中断主链。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import NodeType

# 质量分权重（P3.5.3 冻结）
_RECENCY_FLOOR = 0.2        # 一年前经验的最低衰减因子
_RECENCY_HALF_LIFE_DAYS = 365.0
_SW_REALIZED = 1.0          # 实际结果
_SW_SIMULATED = 0.5         # 模拟结果（可信度减半）
_SUCCESS_SR = 0.5           # 无显式 success 标志时，success_rate >= 0.5 视为成功


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _age_days(ts: Any, as_of: str) -> float:
    t = _parse_ts(ts)
    base = _parse_ts(as_of) or _parse_ts(_now_iso())
    if t is None or base is None:
        return 0.0
    return max(0.0, (base - t).total_seconds() / 86400.0)


def _recency_factor(age_days: float) -> float:
    """时间衰减：今天 1.0 → 一年前 0.2（线性）。"""
    return max(_RECENCY_FLOOR, 1.0 - 0.8 * age_days / _RECENCY_HALF_LIFE_DAYS)


def _record_ts(record: Dict[str, Any]) -> str:
    """取记录的时间戳：outcome.last_validated_at 优先，其次 record.created_at。"""
    oc = record.get("outcome") or {}
    ts = oc.get("last_validated_at") or record.get("created_at") or ""
    return str(ts)


def _record_sr(record: Dict[str, Any]) -> Optional[float]:
    oc = record.get("outcome") or {}
    sr = oc.get("success_rate")
    return float(sr) if sr is not None else None


def _record_is_success(record: Dict[str, Any]) -> Optional[bool]:
    """已验证记录的成功判定：显式 success 优先，否则 success_rate >= 0.5。"""
    oc = record.get("outcome") or {}
    if oc.get("success") is not None:
        return bool(oc["success"])
    sr = _record_sr(record)
    if sr is None:
        return None
    return sr >= _SUCCESS_SR


@dataclass
class KnowledgeScore:
    """一条知识（按 decision_type:action 聚合）的质量分。

    字段（与 P3.5.3 契约一致）：
    confidence / usage_count / success_count / failure_count / last_validated_at，
    另加派生字段 quality（= 各记录 quality 均值）与 success_rate。
    """

    key: str                                  # f"{decision_type}:{action}"
    confidence: float = 0.0                   # 命中记录 knowledge_signal.confidence 均值
    usage_count: int = 0                      # 命中记录数
    success_count: int = 0
    failure_count: int = 0
    last_validated_at: str = ""               # 最近一次结果时间
    quality: float = 0.0

    @property
    def validated_count(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.validated_count <= 0:
            return 0.0
        return self.success_count / self.validated_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "confidence": round(float(self.confidence), 6),
            "usage_count": int(self.usage_count),
            "success_count": int(self.success_count),
            "failure_count": int(self.failure_count),
            "last_validated_at": self.last_validated_at,
            "quality": round(float(self.quality), 6),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeScore":
        return cls(
            key=str(d.get("key", "")),
            confidence=float(d.get("confidence", 0.0)),
            usage_count=int(d.get("usage_count", 0)),
            success_count=int(d.get("success_count", 0)),
            failure_count=int(d.get("failure_count", 0)),
            last_validated_at=str(d.get("last_validated_at", "")),
            quality=float(d.get("quality", 0.0)),
        )


@dataclass
class KnowledgeConflict:
    """同键知识出现相反结果（保留双记录，不覆盖）。"""

    key: str                                  # f"{decision_type}:{action}"
    successes: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "successes": list(self.successes),
            "failures": list(self.failures),
            "evidence": list(self.evidence),
        }


class MemoryQualityGovernor:
    """知识质量管理器（只读，fail-open）。

    典型用法::

        gov = MemoryQualityGovernor(kg, as_of="2026-07-31T00:00:00+00:00")
        gov.filter_records(ceo_decision_records)   # 只留 quality >= min_quality
        gov.detect_conflicts()                     # 同键正反结果 → KnowledgeConflict
        gov.score_records(records)                 # 按 key 聚合 KnowledgeScore
    """

    def __init__(
        self,
        graph: Optional[Any] = None,
        as_of: Optional[str] = None,
        min_quality: float = 0.3,
    ) -> None:
        self.graph = graph
        self.as_of = as_of or _now_iso()
        self.min_quality = float(min_quality)

    @property
    def real_api_called(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # 单条质量分
    # ------------------------------------------------------------------ #
    def quality_of(self, record: Dict[str, Any]) -> float:
        """单条记录质量分 = success_rate × recency × source_weight。

        未验证（无 outcome.success_rate）→ 0.0。
        """
        sr = _record_sr(record)
        if sr is None:
            return 0.0
        age = _age_days(_record_ts(record), self.as_of)
        recency = _recency_factor(age)
        oc = record.get("outcome") or {}
        sw = _SW_SIMULATED if oc.get("simulated") else _SW_REALIZED
        return float(sr) * recency * sw

    # ------------------------------------------------------------------ #
    # 聚合评分 / 过滤
    # ------------------------------------------------------------------ #
    def score_records(self, records: List[Dict[str, Any]]) -> List[KnowledgeScore]:
        """按 key（decision_type:action）聚合 KnowledgeScore。"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            key = self._key_of(r)
            groups.setdefault(key, []).append(r)

        out: List[KnowledgeScore] = []
        for key, recs in sorted(groups.items()):
            successes = [r for r in recs if _record_is_success(r) is True]
            failures = [r for r in recs if _record_is_success(r) is False]
            confs = [
                float((r.get("knowledge_signal") or {}).get("confidence", 0.0) or 0.0)
                for r in recs
            ]
            ts_list = [_record_ts(r) for r in recs if _record_ts(r)]
            out.append(
                KnowledgeScore(
                    key=key,
                    confidence=(sum(confs) / len(confs)) if confs else 0.0,
                    usage_count=len(recs),
                    success_count=len(successes),
                    failure_count=len(failures),
                    last_validated_at=max(ts_list) if ts_list else "",
                    quality=(
                        sum(self.quality_of(r) for r in recs) / len(recs)
                        if recs else 0.0
                    ),
                )
            )
        return out

    def filter_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """只保留 quality >= min_quality 的记录（低质/未验证经验被过滤）。"""
        return [r for r in records if self.quality_of(r) >= self.min_quality]

    @staticmethod
    def _key_of(record: Dict[str, Any]) -> str:
        dp = record.get("decision_payload") or {}
        return f"{record.get('decision_type', '')}:{dp.get('action', '')}"

    # ------------------------------------------------------------------ #
    # 冲突检测（不覆盖）
    # ------------------------------------------------------------------ #
    def detect_conflicts(
        self, records: Optional[List[Dict[str, Any]]] = None
    ) -> List[KnowledgeConflict]:
        """同键同时存在成功与失败 → KnowledgeConflict（双记录保留）。"""
        recs = records if records is not None else self.ceo_decision_records()
        groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for r in recs:
            key = self._key_of(r)
            verdict = _record_is_success(r)
            if verdict is None:
                continue
            bucket = "successes" if verdict else "failures"
            groups.setdefault(key, {"successes": [], "failures": []})[bucket].append(r)

        out: List[KnowledgeConflict] = []
        for key, g in sorted(groups.items()):
            if g["successes"] and g["failures"]:
                ev = [
                    f"同一知识键 {key!r} 出现相反结果：成功 {len(g['successes'])} 条 vs "
                    f"失败 {len(g['failures'])} 条——双记录保留待仲裁，不覆盖。"
                ]
                out.append(
                    KnowledgeConflict(
                        key=key,
                        successes=list(g["successes"]),
                        failures=list(g["failures"]),
                        evidence=ev,
                    )
                )
        return out

    # ------------------------------------------------------------------ #
    # 从 Graph 读 CEO_DECISION 记录（只读，fail-open）
    # ------------------------------------------------------------------ #
    def ceo_decision_records(
        self, include_obsolete: bool = False, include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        if self.graph is None:
            return []
        try:
            store = self.graph.graph
            states: Dict[str, tuple] = {}
            for node in store.query(NodeType.GOVERNANCE_RECORD):
                payload = node.payload
                target = str(payload.get("target_node_id", ""))
                stamp = str(payload.get("created_at", ""))
                if target and (target not in states or stamp >= states[target][0]):
                    states[target] = (stamp, str(payload.get("new_state", "active")))
            out: List[Dict[str, Any]] = []
            for node in store.query(NodeType.CEO_DECISION):
                state = states.get(node.id, ("", "active"))[1]
                if state == "obsolete" and not include_obsolete:
                    continue
                if state == "archived" and not include_archived:
                    continue
                data = dict(node.payload)
                data["governance_state"] = state
                data["node_id"] = node.id
                out.append(data)
            return out
        except Exception:
            return []


# 公共别名（供测试/调用方直接使用衰减函数）
recency_factor = _recency_factor
age_days = _age_days


__all__ = [
    "KnowledgeScore",
    "KnowledgeConflict",
    "MemoryQualityGovernor",
    "recency_factor",
    "age_days",
]
