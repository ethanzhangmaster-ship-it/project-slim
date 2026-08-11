"""
E15.2.5+ — Action Ledger: closes the loop on recommendations.

Every daily run reconciles today's report actions against the ledger:

  NEW        action first seen today            -> record, notify as NEW
  STILL_OPEN action fired again (not applied)   -> age it, remind if stale
  RESOLVED   previously-open action no longer   -> the signal disappeared,
             fires in today's report               i.e. it was applied in the
                                                   MAX dashboard (or the
                                                   condition self-healed).
                                                   Mark resolved + notify.

State:   outputs/action_ledger/<account>.json      (current open/closed map)
History: outputs/action_ledger/<account>.events.jsonl (append-only audit)

Deterministic, no LLM, no MAX writes — pure bookkeeping.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date as _date
from typing import Dict, List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport

DEFAULT_DIR = os.path.join("outputs", "action_ledger")

# Rules whose disappearance genuinely means "applied / fixed".
# (geo_opportunity & revenue_concentration are standing advisories —
#  they resolve too, but we keep the same semantics for simplicity.)


def action_id(account: str, action: str, target: str) -> str:
    return hashlib.sha1(f"{account}|{action}|{target}".encode()).hexdigest()[:12]


class ActionLedger:
    def __init__(self, ledger_dir: str = DEFAULT_DIR) -> None:
        self.dir = ledger_dir

    # ------------------------------------------------------------------ #
    def reconcile(self, report: MonetizationDailyReport,
                  today: Optional[str] = None) -> Dict:
        """Compare today's actions vs open ledger items. Returns summary:
        {"new": [...], "still_open": [...], "resolved": [...]}"""
        today = today or report.date or _date.today().isoformat()
        state = self._load_state(report.account)

        current: Dict[str, Dict] = {}
        for a in report.actions:
            aid = action_id(report.account, a.action, a.target)
            current[aid] = {
                "action_id": aid, "priority": a.priority,
                "action": a.action, "target": a.target,
                "title": a.title, "source_rule": a.source_rule,
            }

        new, still_open, resolved = [], [], []

        # 1) previously open items
        for aid, rec in list(state.items()):
            if rec.get("status") != "open":
                continue
            age = self._age_days(rec.get("first_seen", today), today)
            if aid in current:
                rec["last_seen"] = today
                rec["age_days"] = age
                still_open.append({**rec})
            else:
                rec["status"] = "resolved"
                rec["resolved_at"] = today
                rec["age_days"] = age
                resolved.append({**rec})
                self._append_event(report.account,
                                   {"event": "resolved", "date": today, **rec})

        # 2) brand-new items
        for aid, cur in current.items():
            if aid not in state or state[aid].get("status") == "resolved":
                # re-firing after resolution == regression -> treat as new
                rec = {**cur, "status": "open", "first_seen": today,
                       "last_seen": today, "age_days": 0}
                state[aid] = rec
                new.append({**rec})
                self._append_event(report.account,
                                   {"event": "new", "date": today, **cur})

        self._save_state(report.account, state)
        return {"new": new, "still_open": still_open, "resolved": resolved,
                "open_total": sum(1 for r in state.values()
                                  if r.get("status") == "open")}

    # ------------------------------------------------------------------ #
    def open_items(self, account: str) -> List[Dict]:
        return [r for r in self._load_state(account).values()
                if r.get("status") == "open"]

    # ------------------------------------------------------------------ #
    def _state_path(self, account: str) -> str:
        return os.path.join(self.dir, f"{account}.json")

    def _events_path(self, account: str) -> str:
        return os.path.join(self.dir, f"{account}.events.jsonl")

    def _load_state(self, account: str) -> Dict[str, Dict]:
        p = self._state_path(account)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                return {}
        return {}

    def _save_state(self, account: str, state: Dict) -> None:
        os.makedirs(self.dir, exist_ok=True)
        with open(self._state_path(account), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)

    def _append_event(self, account: str, event: Dict) -> None:
        os.makedirs(self.dir, exist_ok=True)
        with open(self._events_path(account), "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    @staticmethod
    def _age_days(first_seen: str, today: str) -> int:
        try:
            from datetime import date
            f = date.fromisoformat(first_seen)
            t = date.fromisoformat(today)
            return max((t - f).days, 0)
        except ValueError:
            return 0
