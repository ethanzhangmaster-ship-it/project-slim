"""E15.2 Play Decision Engine — 快照进, 决策出.

- 只消费 PlayRealitySnapshot, 不触碰任何 API (Reality/Decision 解耦)
- 规则按优先级短路评估, 全部未命中时兜底 HOLD_ROLLOUT
- package 级隔离: decide_many 单包异常不影响其他包
- 可选 feature_store: 决策历史落 JSONL 供审计/回溯
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .models import PlayAction, PlayDecision
from .rules import DEFAULT_RULES, DecisionRule

_DEFAULT_DECISION_LOG = Path("data") / "play_runtime" / "decisions.jsonl"


class PlayDecisionEngine:
    def __init__(
        self,
        rules: Optional[List[DecisionRule]] = None,
        *,
        decision_log: Optional[Path] = None,
        persist: bool = False,
    ) -> None:
        self.rules = rules if rules is not None else list(DEFAULT_RULES)
        self.decision_log = (
            Path(decision_log) if decision_log is not None else _DEFAULT_DECISION_LOG
        )
        self.persist = persist

    def decide(self, snapshot: Any) -> PlayDecision:
        """对单包快照做确定性决策."""
        decision: Optional[PlayDecision] = None
        for rule in self.rules:
            decision = rule.evaluate(snapshot)
            if decision is not None:
                break
        if decision is None:  # 理论上 observe 兜底不会到这, 双保险
            decision = PlayDecision(
                package_name=getattr(snapshot, "package_name", ""),
                action=PlayAction.HOLD_ROLLOUT,
                confidence=0.3,
                reason="no rule produced a decision; defaulting to hold",
                rule_name="fallback",
            )
        if self.persist:
            self._log(decision)
        return decision

    def decide_many(
        self, snapshots: Sequence[Any]
    ) -> Dict[str, Optional[PlayDecision]]:
        """逐包决策, package 级隔离."""
        results: Dict[str, Optional[PlayDecision]] = {}
        for snap in snapshots:
            pkg = getattr(snap, "package_name", "")
            try:
                results[pkg] = self.decide(snap)
            except Exception:
                results[pkg] = None
        return results

    def _log(self, decision: PlayDecision) -> None:
        try:
            self.decision_log.parent.mkdir(parents=True, exist_ok=True)
            entry = decision.to_dict()
            entry["logged_at"] = datetime.now(timezone.utc).isoformat()
            with self.decision_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 审计失败不阻断决策
