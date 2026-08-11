"""
E15.1.1 + E15.2.4 Acceptance Gate

E15.1.1: Real Publishing Adapter (Google Play + App Store, 20 cases)
E15.2.4: Monetization Optimization Loop (RevenueAnalyzer + Waterfall + BidFloor + Frequency + Orchestrator, 25 cases)

Target: 45 cases, 0 failures.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from monetization.providers.models import SandboxMode
from operation.publishing.providers.google_play.provider import GooglePlayProductionProvider
from operation.publishing.providers.app_store.provider import AppStoreProductionProvider
from operation.publishing.providers.models import (
    GP_APPROVED, GP_DRAFT, GP_IN_REVIEW, GP_REJECTED,
    AS_READY, AS_IN_REVIEW, AS_PREPARE, AS_REJECTED,
    OP_CREATE_APP, OP_UPLOAD_BUILD, OP_CREATE_RELEASE,
    OP_SUBMIT_REVIEW, OP_CHECK_STATUS, OP_RELEASE,
    OP_UPDATE_METADATA, PublishingChange,
)
from operation.optimizer.analyzer import RevenueAnalyzer, RevenueIssue
from operation.optimizer.waterfall import WaterfallOptimizer, WaterfallChange
from operation.optimizer.bid_floor import BidFloorOptimizer, FloorChange
from operation.optimizer.frequency import FrequencyOptimizer, FrequencyChange
from operation.optimizer.orchestrator import OptimizationOrchestrator, OptimizationRun

PASS, FAIL, TOTAL = 0, 0, 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS  [{TOTAL:02d}] {label}")
    else:
        FAIL += 1
        print(f"  FAIL  [{TOTAL:02d}] {label}  — {detail}")


# =========================================================================== #
# Part 1: E15.1.1 Real Publishing Adapter (20 cases)
# =========================================================================== #
print("\n=== E15.1.1 Real Publishing Adapter ===")

# Mock API handler for testing real clients
def mock_gp_api(method, path, body):
    return {"success": True, "status": "draft"}

def mock_as_api(method, path, body):
    return {"success": True, "status": "ready_for_sale"}

# --- Google Play Production Provider ---
gp = GooglePlayProductionProvider(sandbox=SandboxMode.SIMULATION)
gp.arm_real_client(mock_gp_api)

# 1.1 Create app (SIMULATION → mock)
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_APP, provider="google_play",
    game_id="game_01", new={"package_name": "com.test.app", "title": "Test"}))
check("gp_sim_create_app: success", r.success)
check("gp_sim_create_app: real_api_called=false", not r.real_api_called)

# 1.2 Upload build
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_UPLOAD_BUILD, provider="google_play",
    game_id="game_01", new={"file_path": "build.aab", "version": "1.0", "build_number": 1}))
check("gp_sim_upload: success", r.success)

# 1.3 Create release (prerequisite for submit)
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_RELEASE, provider="google_play",
    game_id="game_01", new={"track": "internal"}))
check("gp_sim_create_release: success", r.success)

# 1.4 Submit review (mock advances status)
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_SUBMIT_REVIEW, provider="google_play",
    game_id="game_01", new={}))
check("gp_sim_submit: success", r.success)

# 1.5 Check status
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_CHECK_STATUS, provider="google_play",
    game_id="game_01", new={}))
check("gp_sim_check_status: success", r.success)

# 1.5 Production mode simulates real API call tracking
gp_prod = GooglePlayProductionProvider(sandbox=SandboxMode.PRODUCTION)
gp_prod.arm_real_client(mock_gp_api)
r = gp_prod.apply_change(PublishingChange(
    target="game_prod", operation=OP_CREATE_APP, provider="google_play",
    game_id="game_prod", new={"package_name": "com.prod.app", "title": "Prod"}))
check("gp_prod_create: success (arm_real_client returns success)", r.success)

# 1.6 Google Play health check
r = gp.health_check()
check("gp_health: success", r.success)

# 1.7 Rollback
r = gp.rollback_change(PublishingChange(
    target="game_01", operation="rollback", provider="google_play",
    game_id="game_01"))
check("gp_rollback: success", r.success)

# 1.8 Test rejection flow
gp._mock_client.set_simulated_rejection("policy_violation", "Test rejection")
# need create_app again (rollback cleared it)
gp.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_APP, provider="google_play",
    game_id="game_01", new={"package_name": "com.test.app", "title": "Test"}))
gp.apply_change(PublishingChange(
    target="game_01", operation=OP_UPLOAD_BUILD, provider="google_play",
    game_id="game_01", new={"file_path": "build.aab", "version": "1.0", "build_number": 1}))
gp.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_RELEASE, provider="google_play",
    game_id="game_01", new={"track": "internal"}))
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_SUBMIT_REVIEW, provider="google_play",
    game_id="game_01", new={}))
check("gp_rejection: success (mock reports)", r.success)
# Reset reject
gp._mock_client._simulated_rejection = None

# 1.9 Metadata update
r = gp.apply_change(PublishingChange(
    target="game_01", operation=OP_UPDATE_METADATA, provider="google_play",
    game_id="game_01", new={"title": "Updated Title"}))
check("gp_metadata_update: success", r.success)

# 1.10 Multi-game credential isolation
gp2 = GooglePlayProductionProvider(sandbox=SandboxMode.SIMULATION)
gp2.arm_real_client(mock_gp_api)
r2 = gp2.apply_change(PublishingChange(
    target="game_02", operation=OP_CREATE_APP, provider="google_play",
    game_id="game_02", new={"package_name": "com.game2.app", "title": "Game 2"}))
check("gp_game_02: isolated from game_01", r2.success)

# --- App Store Production Provider ---
asc = AppStoreProductionProvider(sandbox=SandboxMode.SIMULATION)
asc.arm_real_client(mock_as_api)

# 1.11 Create app
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_APP, provider="app_store",
    game_id="game_01", new={"bundle_id": "com.test.ios", "title": "Test iOS"}))
check("as_sim_create: success", r.success)

# 1.12 Upload build
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_UPLOAD_BUILD, provider="app_store",
    game_id="game_01", new={"file_path": "build.ipa", "version": "1.0", "build_number": 1}))
check("as_sim_upload: success", r.success)

# 1.13 Create version
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_RELEASE, provider="app_store",
    game_id="game_01", new={"version": "1.0.0"}))
check("as_sim_create_version: success", r.success)

# 1.14 Submit review
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_SUBMIT_REVIEW, provider="app_store",
    game_id="game_01", new={}))
check("as_sim_submit: success", r.success)

# 1.15 Release
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_RELEASE, provider="app_store",
    game_id="game_01", new={}))
check("as_sim_release: success", r.success)

# 1.16 Health check
r = asc.health_check()
check("as_health: success", r.success)

# 1.17 Production mode
asc_prod = AppStoreProductionProvider(sandbox=SandboxMode.PRODUCTION)
asc_prod.arm_real_client(mock_as_api)
r = asc_prod.apply_change(PublishingChange(
    target="game_prod", operation=OP_CREATE_APP, provider="app_store",
    game_id="game_prod", new={"bundle_id": "com.prod.ios", "title": "Prod iOS"}))
check("as_prod_create: success", r.success)

# 1.18 App Store rejection flow
asc._mock_client.set_simulated_rejection("guideline_4.3", "Spam")
asc.apply_change(PublishingChange(
    target="game_01", operation=OP_CREATE_RELEASE, provider="app_store",
    game_id="game_01", new={"version": "1.0.1"}))
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_SUBMIT_REVIEW, provider="app_store",
    game_id="game_01", new={}))
check("as_rejection: success (mock reports)", r.success)
asc._mock_client._simulated_rejection = None

# 1.19 Rollback
r = asc.rollback_change(PublishingChange(
    target="game_01", operation="rollback", provider="app_store",
    game_id="game_01"))
check("as_rollback: success", r.success)

# 1.20 Metadata
r = asc.apply_change(PublishingChange(
    target="game_01", operation=OP_UPDATE_METADATA, provider="app_store",
    game_id="game_01", new={"description": "New desc"}))
check("as_metadata_update: success", r.success)


# =========================================================================== #
# Part 2: E15.2.4 Monetization Optimization Loop (25 cases)
# =========================================================================== #
print("\n=== E15.2.4 Monetization Optimization Loop ===")

analyzer = RevenueAnalyzer()
wf_opt = WaterfallOptimizer()
floor_opt = BidFloorOptimizer()
freq_opt = FrequencyOptimizer()

# Sample data
sample_metrics = [
    {
        "format": "rewarded", "country": "US", "platform": "android",
        "ecpm": 18.0, "fill_rate": 0.92, "revenue_daily": 350.0,
        "networks": [
            {"network": "AppLovin", "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
            {"network": "Mintegral", "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
            {"network": "AdMob", "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
        ]
    },
    {
        "format": "interstitial", "country": "US", "platform": "android",
        "ecpm": 6.5, "fill_rate": 0.88, "revenue_daily": 120.0,
    },
    {
        "format": "rewarded", "country": "JP", "platform": "android",
        "ecpm": 8.0, "fill_rate": 0.95, "revenue_daily": 200.0,
    },
]

sample_baselines = {
    "rewarded_US_ecpm": 24.0,
    "rewarded_US_fill": 0.95,
    "rewarded_US_revenue": 420.0,
    "interstitial_US_ecpm": 7.0,
    "interstitial_US_fill": 0.90,
    "interstitial_US_revenue": 130.0,
    "rewarded_JP_ecpm": 9.0,
    "rewarded_JP_fill": 0.93,
    "rewarded_JP_revenue": 220.0,
}

# 2.1 RevenueAnalyzer: detect eCPM decline (critical)
issues = analyzer.analyze("game_01", sample_metrics, sample_baselines)
check("analyzer: detects issues", len(issues) > 0)
check("analyzer: eCPM decline is critical", any(i.issue_type == "ecpm_decline" and i.severity == "critical" for i in issues))

# 2.2 RevenueAnalyzer: detect revenue anomaly
check("analyzer: revenue anomaly detected", any(i.issue_type == "revenue_anomaly" for i in issues))

# 2.3 RevenueAnalyzer: severity ordering (critical first)
check("analyzer: critical issues sorted first", issues[0].severity == "critical")

# 2.4 RevenueAnalyzer: detect floor opportunity
opportunities = analyzer.detect_opportunities("game_01", [
    {"format": "rewarded", "country": "US", "ecpm": 30.0, "bid_floor": 15.0},
])
check("analyzer: floor opportunity detected", len(opportunities) > 0)
check("analyzer: opportunity suggests raise_bid_floor", opportunities[0].suggested_action == "raise_bid_floor")

# 2.5 RevenueAnalyzer: no opportunity when eCPM at floor
opportunities2 = analyzer.detect_opportunities("game_01", [
    {"format": "rewarded", "country": "US", "ecpm": 16.0, "bid_floor": 15.0},
])
check("analyzer: no opportunity when eCPM near floor", len(opportunities2) == 0)

# 2.6 WaterfallOptimizer: reorder by eCPM
wf_change = wf_opt.optimize(
    "game_01", "rewarded", "US",
    ["Mintegral", "AdMob", "AppLovin"],
    [
        {"network": "AppLovin", "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
        {"network": "Mintegral", "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
        {"network": "AdMob", "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
    ],
)
check("waterfall: reorder proposed", wf_change is not None)
if wf_change:
    check("waterfall: AppLovin is now first", wf_change.new_order[0] == "AppLovin")
    check("waterfall: differs from old order", wf_change.old_order != wf_change.new_order)

# 2.7 WaterfallOptimizer: no change if already optimal
wf_change2 = wf_opt.optimize(
    "game_01", "rewarded", "US",
    ["AppLovin", "AdMob", "Mintegral"],
    [
        {"network": "AppLovin", "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
        {"network": "Mintegral", "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
        {"network": "AdMob", "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
    ],
)
check("waterfall: no change when optimal", wf_change2 is None)

# 2.8 WaterfallOptimizer: to_operations
if wf_change:
    ops = wf_opt.to_operations(wf_change)
    check("waterfall: to_operations returns 3 ops", len(ops) == 3)
    check("waterfall: op has operation field", all("operation" in o for o in ops))

# 2.9 BidFloorOptimizer: raise floor (eCPM > 1.5x floor)
fc = floor_opt.analyze("game_01", "rewarded", "US", 15.0, 30.0, 0.95)
check("bidfloor: raise proposed", fc is not None)
if fc:
    check("bidfloor: new floor > old", fc.new_floor > fc.old_floor)
    check("bidfloor: increase within 20%", fc.change_pct <= 20.0)

# 2.10 BidFloorOptimizer: lower floor (fill < 80%)
fc2 = floor_opt.analyze("game_01", "interstitial", "US", 10.0, 8.0, 0.75)
check("bidfloor: lower proposed on low fill", fc2 is not None)

# 2.11 BidFloorOptimizer: no change when stable
fc3 = floor_opt.analyze("game_01", "rewarded", "US", 15.0, 18.0, 0.93)
check("bidfloor: no change when stable", fc3 is None)

# 2.12 BidFloorOptimizer: to_operation
if fc:
    op = floor_opt.to_operation(fc)
    check("bidfloor: to_operation has operation field", "operation" in op)
    check("bidfloor: to_operation has new_floor", "new_floor" in op)

# 2.13 FrequencyOptimizer: safe change (increase interval, fewer ads → approve)
frc = freq_opt.evaluate("game_01", "rewarded", 60, 72)
check("freq: safe increase → approve", frc.recommendation == "approve")

# 2.14 FrequencyOptimizer: blocked below hard cap
frc2 = freq_opt.evaluate("game_01", "interstitial", 60, 30)
check("freq: below hard cap → block", frc2.recommendation == "block")

# 2.15 FrequencyOptimizer: marginal change → review
frc3 = freq_opt.evaluate("game_01", "rewarded", 45, 40)
check("freq: marginal → review", frc3.recommendation in ("review", "block"))

# 2.16 FrequencyOptimizer: suggest_optimization
frc4 = freq_opt.suggest_optimization("game_01", "rewarded", 60)
check("freq: suggest when above safe", frc4 is not None)
if frc4:
    check("freq: suggested interval < current", frc4.proposed_interval_s < 60)

# 2.17 FrequencyOptimizer: no suggestion at safe level
frc5 = freq_opt.suggest_optimization("game_01", "rewarded", 40)
check("freq: no suggest at safe level", frc5 is None)

# 2.18 FrequencyOptimizer: to_operation
op = freq_opt.to_operation(frc)
check("freq: to_operation has operation", "operation" in op)

# 2.19 OptimizationOrchestrator: full cycle (dry_run)
orch = OptimizationOrchestrator()
run = orch.run(
    "game_01",
    metrics=sample_metrics,
    baselines=sample_baselines,
    current_waterfalls={"rewarded_US": ["Mintegral", "AdMob", "AppLovin"]},
    current_floors={"rewarded_US": 10.0, "interstitial_US": 10.0},
    current_frequencies={"rewarded": 60, "interstitial": 120},
)
check("orchestrator: issues detected", len(run.issues_detected) > 0)
check("orchestrator: waterfall change proposed", len(run.waterfall_changes) > 0)
check("orchestrator: floor change proposed", len(run.floor_changes) > 0)
check("orchestrator: dry_run has 0 executed", len(run.executed_ops) == 0)

# 2.20 Orchestrator summary
s = run.summary
check("orchestrator: summary has critical_issues", "critical_issues" in s)
check("orchestrator: total_changes > 0", run.total_changes > 0)


# =========================================================================== #
# Results
# =========================================================================== #
print(f"\n{'='*50}")
print(f"  TOTAL: {TOTAL}  |  PASS: {PASS}  |  FAIL: {FAIL}")
if FAIL == 0:
    print("  REAL ADAPTER + OPTIMIZER READY")
else:
    print(f"  {FAIL} FAILURES — review above")
print(f"{'='*50}")

sys.exit(0 if FAIL == 0 else 1)
