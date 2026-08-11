"""
Daily monetization intelligence push — one command, full closed loop.

Usage:
    python daily_intel.py                 # all accounts, last 10 days
    python daily_intel.py ACCT_2          # one account
    python daily_intel.py ACCT_2 7        # one account, last 7 days

Per account: pull MAX Report API (day-by-day) -> analyze (6 rules)
-> daily report (md+json) -> reconcile action ledger (closed loop)
-> push Feishu card to the ops group.

Zero MAX writes (Phase 1 contract).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent
from operation.providers.live.max.accounts import load_accounts


def main() -> int:
    args = sys.argv[1:]
    only = args[0] if args else None
    days = int(args[1]) if len(args) > 1 else 10

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days - 1)).isoformat()

    accounts = load_accounts()
    targets = [only] if only else [k for k, v in accounts.items()
                                   if v.get("report_key")]
    agent = MonetizationIntelligenceAgent()
    failures = 0
    for acct in targets:
        try:
            out = agent.run_and_notify(acct, start, end, report_date=end)
            r = out["report"]
            loop = out["loop"]
            print(f"[OK] {acct}: ${r.revenue:,.2f} | "
                  f"H{r.health_score}/{r.health_grade} "
                  f"O{r.opportunity_score}/{r.opportunity_grade} "
                  f"R{r.risk_score}/{r.risk_grade} | "
                  f"actions {len(r.actions)} "
                  f"(safe {sum(1 for v in r.validated_actions if v['layer']=='safe')}/"
                  f"exp {sum(1 for v in r.validated_actions if v['layer']=='experiment')}/"
                  f"obs {sum(1 for v in r.validated_actions if v['layer']=='observe')}) | "
                  f"exp track {len(r.experiments)} | "
                  f"loop new={len(loop['new'])} open={len(loop['still_open'])} "
                  f"resolved={len(loop['resolved'])} | feishu pushed")
        except Exception as exc:                      # noqa: BLE001
            failures += 1
            print(f"[FAIL] {acct}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
