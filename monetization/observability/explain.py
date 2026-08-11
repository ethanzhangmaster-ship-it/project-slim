"""
E14.5.2 — Decision Explainability Log
======================================

Answers the operator's most important question for a 50-game fleet:

    "WHY did the system change MAX bid_floor / RemoteConfig frequency?"

Every consequential decision (execute / experiment / block) is turned into a
DecisionTrace with a human-readable `reason_chain`. The chain is derived
*only* from data the agent already produces (AgentAction fields + the
planner rationale) — no new signals, no LLM.

Output: append-only JSONL at <traces_dir>/<day_tag>.jsonl so each decision
is durably auditable and tail-able into a log backend later.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from monetization.agent.models import AgentAction
from monetization.observability.models import DecisionTrace

# only the consequential moves are worth a permanent audit trail
LOGGED_ACTIONS = ("execute", "experiment", "block")


class DecisionExplainabilityLog:
    """Collects + persists DecisionTraces as JSONL."""

    def __init__(self, traces_dir: str = "observability/decision_traces"):
        self.dir = Path(traces_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._buffer: List[DecisionTrace] = []

    # ------------------------------------------------------------------ #
    def build_trace(self, game_id: str, action: AgentAction) -> DecisionTrace:
        """Turn one AgentAction into an explainable DecisionTrace."""
        chain: List[str] = []
        if action.reason:
            chain.append(action.reason)
        chain.append(
            f"prior success {action.prior_mean:.0%} (n={action.prior_samples})")
        if action.simulation_revenue_delta:
            chain.append(
                f"simulation predicted revenue "
                f"{action.simulation_revenue_delta:+.1%}")
        if action.retention_delta:
            chain.append(f"retention delta {action.retention_delta:+.1%}")
        chain.append(f"confidence {action.confidence:.2f}, risk={action.risk}")
        chain.append(f"final_action={action.action} -> {action.result_status}")
        return DecisionTrace(
            game_id=game_id,
            decision=action.strategy_type,
            action=action.action,
            reason_chain=chain,
            final_action=action.result_status or action.action,
            confidence=action.confidence,
            risk=action.risk,
            priority=action.priority,
            day=action.day,
            opportunity_id=action.opportunity_id,
        )

    # ------------------------------------------------------------------ #
    def record_cycle(self, game_id: str,
                     actions: List[AgentAction]) -> List[DecisionTrace]:
        traces: List[DecisionTrace] = []
        for a in actions:
            if a.action in LOGGED_ACTIONS:
                t = self.build_trace(game_id, a)
                self._buffer.append(t)
                traces.append(t)
        return traces

    def all_traces(self) -> List[DecisionTrace]:
        return list(self._buffer)

    # ------------------------------------------------------------------ #
    def flush(self, day_tag: str = "") -> int:
        """Persist buffered traces to <day_tag>.jsonl. Returns count written."""
        path = self.dir / f"{day_tag or 'traces'}.jsonl"
        n = 0
        with path.open("a", encoding="utf-8") as fh:
            for t in self._buffer:
                fh.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
                n += 1
        self._buffer.clear()
        return n


__all__ = ["DecisionExplainabilityLog", "LOGGED_ACTIONS"]
