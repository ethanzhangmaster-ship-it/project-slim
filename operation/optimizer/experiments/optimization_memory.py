"""
E15.2.5+ — OptimizationMemory.

E15.2.1 OperationRecord remembers *what was done*.
OptimizationMemory remembers *what worked* — measured outcomes, so a new
game / geo showing the same structure can reference proven priors.

Storage: append-only JSONL at outputs/experiments/optimization_memory.jsonl
Row:
  {account, app, geo, ad_format, action, target, net_impact_pct,
   guardrail, decision, confidence, applied_at, decided_at}

Query: filter by (action, network-target, geo, format) with graceful
widening; returns matching rows + aggregate prior (mean impact, hit-rate,
pooled confidence).

Deterministic. Append-only. Zero MAX writes.
"""
from __future__ import annotations

import json
import os
from datetime import date as _date
from typing import Any, Dict, List, Optional

DEFAULT_PATH = os.path.join("outputs", "experiments",
                            "optimization_memory.jsonl")


class OptimizationMemory:
    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = path

    # ------------------------------------------------------------------ #
    def _load(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            return []
        return rows

    # ------------------------------------------------------------------ #
    def record(self, *, account: str, action: str, target: str,
               net_impact_pct: Optional[float], guardrail: str,
               decision: str, confidence: float,
               applied_at: Optional[str] = None,
               app: str = "", geo: str = "", ad_format: str = "",
               decided_at: Optional[str] = None) -> Dict[str, Any]:
        """Append one measured outcome. Dedup by (account, action, target,
        applied_at) — re-running the same day never duplicates."""
        row = {
            "account": account, "app": app, "geo": geo,
            "ad_format": ad_format, "action": action, "target": target,
            "net_impact_pct": net_impact_pct, "guardrail": guardrail,
            "decision": decision, "confidence": round(confidence, 2),
            "applied_at": applied_at,
            "decided_at": decided_at or _date.today().isoformat(),
        }
        key = (account, action, target, applied_at)
        for r in self._load():
            if (r.get("account"), r.get("action"),
                    r.get("target"), r.get("applied_at")) == key:
                return r          # already memorized
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    # ------------------------------------------------------------------ #
    def query(self, *, action: Optional[str] = None,
              target: Optional[str] = None, geo: Optional[str] = None,
              ad_format: Optional[str] = None) -> Dict[str, Any]:
        """Return matching precedents + aggregate prior. Filters are ANDed;
        None means don't filter on that axis."""
        rows = self._load()
        t = (target or "").upper()

        def ok(r: Dict[str, Any]) -> bool:
            if action and r.get("action") != action:
                return False
            if t and (r.get("target") or "").upper() != t:
                return False
            if geo and (r.get("geo") or "").lower() != geo.lower():
                return False
            if ad_format and r.get("ad_format") != ad_format:
                return False
            return True

        hits = [r for r in rows if ok(r)]
        measured = [r for r in hits
                    if isinstance(r.get("net_impact_pct"), (int, float))]
        if measured:
            impacts = [float(r["net_impact_pct"]) for r in measured]
            keeps = sum(1 for r in measured if r.get("decision") == "KEEP")
            prior = {
                "n": len(measured),
                "mean_impact_pct": round(sum(impacts) / len(impacts), 2),
                "hit_rate": round(keeps / len(measured), 2),
                "confidence": round(
                    min(0.95, sum(float(r.get("confidence", 0))
                                  for r in measured) / len(measured)), 2),
            }
        else:
            prior = {"n": 0, "mean_impact_pct": None,
                     "hit_rate": None, "confidence": 0.0}
        return {"precedents": hits, "prior": prior}

    # ------------------------------------------------------------------ #
    def prior_note(self, action: str, target: str) -> str:
        """One-line human-readable prior for report/hypothesis rendering."""
        q = self.query(action=action, target=target)
        p = q["prior"]
        if not p["n"]:
            return ""
        return (f"prior: {p['n']} precedent(s), mean impact "
                f"{p['mean_impact_pct']:+.1f}%/day, hit-rate "
                f"{p['hit_rate']:.0%}, confidence {p['confidence']:.2f}")
