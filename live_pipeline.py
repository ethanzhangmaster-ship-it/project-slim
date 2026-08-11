"""
E15 Live Pipeline — Real MAX Report + Management API → Optimization

Pulls real data from both APIs and runs the full optimization loop.
"""
import urllib.request, urllib.parse, json, sys, os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from operation.optimizer.planner.optimization_planner import OptimizationPlanner
from operation.optimizer.executor.optimization_executor import OptimizationExecutor
from operation.memory.agent import MemoryAgent
from operation.memory.store import OperationMemoryStore
from operation.safety.agent import SafetyAgent

REPORT_KEY = "5To2N8G3aEu7TnwdIDMG0vq5QOKIyB0cSWhTOFbTog0TzDc5f63ONTVmFZetzbJia4DvKfift40oOeC-eqWlH5"
MGMT_KEY = "dTSu2On_1KEy_mbheNGy2phc37qD3ZThs_89mBf8EhpieXaUdLgd0KPAhpQOBUkB7xzkGfrEUicTzMztKoNaKE"

# ===================== Step 1: Real Revenue Data =====================
rev_url = "https://r.applovin.com/maxReport?" + urllib.parse.urlencode({
    "api_key": REPORT_KEY, "start": "2026-07-17", "end": "2026-07-24",
    "format": "json", "limit": 500,
    "columns": "day,application,ad_format,country,impressions,ecpm,estimated_revenue",
})
rev_data = json.loads(urllib.request.urlopen(
    urllib.request.Request(rev_url), timeout=15).read())

# ===================== Step 2: Real Ad Units (with floors) =====================
au_url = "https://o.applovin.com/mediation/v1/ad_units?limit=300&fields=bid_floors"
ad_units = json.loads(urllib.request.urlopen(
    urllib.request.Request(au_url, headers={"Api-Key": MGMT_KEY}), timeout=15).read())

# ===================== Step 3: Aggregate & match =====================
# Group revenue by (app, fmt, country)
rev_by = defaultdict(lambda: {"rev": 0.0, "imp": 0, "ecpm_sum": 0.0, "days": set()})
for r in rev_data["results"]:
    app = r.get("application", "?") or "?"
    fmt = (r.get("ad_format", "REWARD") or "REWARD").lower()
    fmt = fmt.replace("inter", "interstitial").replace("reward", "rewarded")
    cc = (r.get("country", "US") or "US").upper()
    rev_by[(app, fmt, cc)]["rev"] += float(r.get("estimated_revenue", 0) or 0)
    rev_by[(app, fmt, cc)]["imp"] += int(r.get("impressions", 0) or 0)
    rev_by[(app, fmt, cc)]["ecpm_sum"] += float(r.get("ecpm", 0) or 0)
    rev_by[(app, fmt, cc)]["days"].add(r.get("day"))

# Extract floors from ad units
floors = {}
for u in ad_units:
    name = (u.get("name", "") or "").lower()
    fmt = (u.get("ad_format", "") or "").lower()
    fmt = fmt.replace("inter", "interstitial").replace("reward", "rewarded")
    bid_floors = u.get("bid_floors", []) or []
    if bid_floors and isinstance(bid_floors, list):
        for bf in bid_floors:
            if isinstance(bf, dict) and "amount" in bf:
                floors[(name, fmt)] = float(bf["amount"])
                break

# ===================== Step 4: Build metrics =====================
# Baselines per (fmt, country)
bp = defaultdict(list)
for (app, fmt, cc), g in rev_by.items():
    if g["days"]:
        bp[(fmt, cc)].append(g["ecpm_sum"] / len(g["days"]))

baselines = {}
for (fmt, cc), vals in bp.items():
    if vals:
        baselines[f"{fmt}_{cc}_ecpm"] = round(sum(vals) / len(vals), 2)
        baselines[f"{fmt}_{cc}_revenue"] = round(sum(vals) / len(vals), 2)
        baselines[f"{fmt}_{cc}_fill"] = 0.90

metrics = []
for (app, fmt, cc), g in rev_by.items():
    if g["imp"] < 50:
        continue
    avg_ecpm = g["ecpm_sum"] / len(g["days"]) if g["days"] else 0
    # Try to match real floor
    floor_val = None
    for (au_name, au_fmt), floor in floors.items():
        if app.lower()[:10] in au_name and fmt == au_fmt:
            floor_val = floor
            break
    if floor_val is None:
        floor_val = round(avg_ecpm * 0.6, 2)  # fallback estimate

    metrics.append({
        "format": fmt,
        "country": cc,
        "platform": "android",
        "ecpm": round(avg_ecpm, 2),
        "revenue_daily": round(g["rev"] / 7, 2),
        "bid_floor": round(floor_val, 2),
        "fill_rate": 0.90,
    })

# ===================== Step 5: Run pipeline =====================
print("=" * 65)
print("  LaunchForge E15 — LIVE MAX Pipeline")
print(f"  Revenue: {len(rev_by)} segments  |  Ad Units: {len(ad_units)}")
print(f"  Metrics: {len(metrics)} (>50 imp) |  Floors: {len(floors)} ad units")
print("=" * 65)

planner = OptimizationPlanner()
plan = planner.plan("max_live", metrics=metrics, baselines=baselines)

print(f"\n  Signals: {plan.metadata.get('signals_detected', 0)}")
print(f"  Actions: {plan.total_actions}")
print()

for a in plan.actions:
    sev = "CRIT" if a.priority == 0 else "HIGH" if a.priority == 1 else "MED"
    old = a.changes.get("old_floor", 0) or 0
    new = a.changes.get("new_floor", 0) or 0
    src = a.source_signal
    descr = src.description[:55] if src else ""
    print(f"  [{sev}] {a.action_type:25s} {a.country:3s} {a.ad_format:12s} "
          f"| ${old:.2f}→${new:.2f} | {descr}")

mem = MemoryAgent(store=OperationMemoryStore(base_dir="data/live_memory"))
safety = SafetyAgent(memory_agent=mem)
executor = OptimizationExecutor(safety_agent=safety, memory_agent=mem, dry_run=True)
result = executor.execute(plan)

print(f"\n  Executed: {result.actions_executed}  Blocked: {result.actions_blocked}  "
      f"Failed: {result.actions_failed}  Rate: {result.success_rate:.0%}")

# Top earners
print(f"\n  Top earners (7d):")
for (app, fmt, cc), g in sorted(rev_by.items(), key=lambda x: -x[1]["rev"])[:5]:
    ecpm = g["ecpm_sum"] / len(g["days"]) if g["days"] else 0
    print(f"  {app[:30]:30s} {fmt:12s} {cc:3s} "
          f"${g['rev']:>7.2f}  {g['imp']:>5,} imp  eCPM ${ecpm:.2f}")

print()
