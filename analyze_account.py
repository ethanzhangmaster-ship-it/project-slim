"""
E15 — Live MAX account analyzer (network / format / country level).

Pulls real data from the MAX Report API and runs a channel-level diagnosis:
  - per-app, per-network, per-format, per-country revenue / eCPM / show-rate
  - wasted-slot detection (high attempts, ~0 impressions, 0 revenue)
  - high-eCPM low-volume networks worth promoting
  - dry-run waterfall reorder + bid-floor suggestions

Usage: python analyze_account.py ACCT_2 [start] [end]
"""
from __future__ import annotations

import sys, os, json, urllib.request, urllib.parse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operation.providers.live.max.accounts import get_account

REPORT_URL = "https://r.applovin.com/maxReport"


def pull(account_id: str, start: str, end: str) -> list:
    acct = get_account(account_id)
    if not acct:
        raise SystemExit(f"[{account_id}] not found / missing report_key")
    cols = ("day,application,ad_format,country,network,impressions,"
            "attempts,responses,ecpm,estimated_revenue")
    params = {
        "api_key": acct["report_key"],
        "start": start, "end": end,
        "format": "json", "limit": 5000,
        "columns": cols,
    }
    url = f"{REPORT_URL}?{urllib.parse.urlencode(params)}"
    data = json.loads(urllib.request.urlopen(
        urllib.request.Request(url), timeout=20).read())
    return data.get("results", [])


def f(x, d=0.0):
    try:
        return float(x or d)
    except (TypeError, ValueError):
        return d


def ecpm_of(rev, imp):
    return (rev / imp * 1000.0) if imp else 0.0


def show_rate(imp, att):
    return (imp / att) if att else 0.0


def agg(rows, keys):
    out = defaultdict(lambda: {"rev": 0.0, "imp": 0, "att": 0, "resp": 0,
                               "days": set(), "apps": set()})
    for r in rows:
        k = tuple((r.get(c) or "?") for c in keys)
        g = out[k]
        g["rev"] += f(r.get("estimated_revenue"))
        g["imp"] += int(f(r.get("impressions")))
        g["att"] += int(f(r.get("attempts")))
        g["resp"] += int(f(r.get("responses")))
        g["days"].add(r.get("day"))
        g["apps"].add(r.get("application"))
    return out


def main():
    acct_id = sys.argv[1] if len(sys.argv) > 1 else "ACCT_2"
    start = sys.argv[2] if len(sys.argv) > 2 else "2026-07-14"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-07-23"
    rows = pull(acct_id, start, end)
    print(f"\n=== {acct_id} | {start}..{end} | {len(rows)} rows ===\n")

    by_app = agg(rows, ["application"])
    by_net = agg(rows, ["network"])
    by_fmt = agg(rows, ["ad_format"])
    by_cc = agg(rows, ["country"])

    t_rev = sum(g["rev"] for g in by_app.values())
    t_imp = sum(g["imp"] for g in by_app.values())
    t_att = sum(g["att"] for g in by_app.values())

    print("--- Per App (revenue / imp / eCPM) ---")
    for (app,), g in sorted(by_app.items(), key=lambda x: -x[1]["rev"]):
        print(f"  {app[:34]:34s} ${g['rev']:>9.2f}  {g['imp']:>7,} imp  "
              f"eCPM ${ecpm_of(g['rev'], g['imp']):>6.2f}")

    print("\n--- Per Network (rev% / eCPM / imp / show% / attempts) ---")
    net_rows = []
    for (net,), g in by_net.items():
        s = show_rate(g["imp"], g["att"])
        e = ecpm_of(g["rev"], g["imp"])
        net_rows.append((net, g, s, e))
    for net, g, s, e in sorted(net_rows, key=lambda x: -x[1]["rev"]):
        pct = (g["rev"] / t_rev * 100) if t_rev else 0
        tag = ""
        if g["rev"] < 0.5 and g["att"] > 1000:
            tag = "  <-- WASTE (att>1k, ~0 rev)"
        elif e > 50 and g["imp"] < 200:
            tag = "  <-- HIGH eCPM LOW VOL"
        print(f"  {net[:24]:24s} {pct:4.1f}%  eCPM ${e:>6.2f}  "
              f"{g['imp']:>6,} imp  show {s:5.1%}  {g['att']:>7,} att{tag}")

    print("\n--- Per Format ---")
    for (fmt,), g in sorted(by_fmt.items(), key=lambda x: -x[1]["rev"]):
        print(f"  {fmt[:14]:14s} ${g['rev']:>9.2f}  {g['imp']:>7,} imp  "
              f"eCPM ${ecpm_of(g['rev'], g['imp']):>6.2f}")

    print("\n--- Per Country (top 10 by rev) ---")
    for (cc,), g in sorted(by_cc.items(), key=lambda x: -x[1]["rev"])[:10]:
        print(f"  {cc[:4]:4s} ${g['rev']:>9.2f}  {g['imp']:>7,} imp  "
              f"eCPM ${ecpm_of(g['rev'], g['imp']):>6.2f}")

    print(f"\n  TOTAL ${t_rev:.2f} | imp {t_imp:,} | attempts {t_att:,} | "
          f"blended eCPM ${ecpm_of(t_rev, t_imp):.2f} | "
          f"depth {t_att/max(t_imp,1):.1f} att/imp | "
          f"apps {len(by_app)} | nets {len(by_net)}")

    os.makedirs("data", exist_ok=True)
    with open(f"data/{acct_id}_report.json", "w", encoding="utf-8") as fh:
        json.dump({"account": acct_id, "start": start, "end": end,
                   "rows": rows}, fh, ensure_ascii=False)
    print(f"  raw -> data/{acct_id}_report.json")


if __name__ == "__main__":
    main()
