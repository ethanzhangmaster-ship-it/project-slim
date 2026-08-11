"""
E15 End-to-End Demo: Publishing + Monetization Optimization

Run both pipelines with sample data and show real output.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monetization.providers.models import SandboxMode
from operation.publishing.providers.google_play.provider import GooglePlayProductionProvider
from operation.publishing.providers.app_store.provider import AppStoreProductionProvider
from operation.publishing.providers.models import PublishingChange
from operation.publishing.build.agent import BuildAgent, BuildArtifact
from operation.publishing.metadata.agent import MetadataAgent
from operation.publishing.orchestrator.agent import PublishingAgent
from operation.optimizer.planner.optimization_planner import OptimizationPlanner
from operation.optimizer.executor.optimization_executor import (
    OptimizationExecutor, OptimizationScheduler,
)
from operation.memory.agent import MemoryAgent
from operation.memory.store import OperationMemoryStore
from operation.safety.agent import SafetyAgent

# Suppress noisy __init__.py prints
import logging
logging.disable(logging.CRITICAL)

# =========================================================================== #
# Game Definition
# =========================================================================== #
GAME = {
    "game_id": "word_blast_01",
    "display_name": "Word Blast - Puzzle Master",
    "package_name": "com.fusion.wordblast",
    "bundle_id": "com.fusion.wordblast.ios",
    "platforms": ["android", "ios"],
    "category": "word",
    "genres": ["puzzle", "casual"],
    "version": "1.0.0",
    "build_number": 1,
}

print("=" * 60)
print(f"  LaunchForge E15 Demo — {GAME['display_name']}")
print(f"  Game ID: {GAME['game_id']}")
print("=" * 60)

# =========================================================================== #
# Pipeline 1: Publishing (Google Play + App Store)
# =========================================================================== #
print("\n─── Pipeline 1: Publishing ───")

# Mock API
def mock_api(method, path, body=None):
    return {"success": True, "status": "created", "_method": method, "_path": path}

# Google Play
gp = GooglePlayProductionProvider(sandbox=SandboxMode.SIMULATION)
gp.arm_real_client(mock_api)

# App Store
asc = AppStoreProductionProvider(sandbox=SandboxMode.SIMULATION)
asc.arm_real_client(mock_api)

# Build artifacts
android_build = BuildArtifact(
    game_id=GAME["game_id"], platform="android", version=GAME["version"],
    build_number=GAME["build_number"], file_path="builds/word_blast.aab",
    checksum="a1b2c3d4", size_bytes=45_000_000,
)
ios_build = BuildArtifact(
    game_id=GAME["game_id"], platform="ios", version=GAME["version"],
    build_number=GAME["build_number"], file_path="builds/word_blast.ipa",
    checksum="e5f6g7h8", size_bytes=52_000_000,
)

# Metadata
meta_agent = MetadataAgent()

# Google Play pipeline
print("\n[Google Play]")
pa_gp = PublishingAgent(gp, BuildAgent(), MetadataAgent())
gp_report = pa_gp.run(GAME["game_id"], "android", android_build, GAME)
print(f"  Status: {gp_report.final_status}")
steps = [f"{t.task_type} → {t.status}" for t in gp_report.tasks]
for i, s in enumerate(steps):
    print(f"  Step {i+1}: {s}")

# App Store pipeline
print("\n[App Store]")
pa_as = PublishingAgent(asc, BuildAgent(), MetadataAgent())
as_report = pa_as.run(GAME["game_id"], "ios", ios_build, GAME)
print(f"  Status: {as_report.final_status}")
steps = [f"{t.task_type} → {t.status}" for t in as_report.tasks]
for i, s in enumerate(steps):
    print(f"  Step {i+1}: {s}")

print(f"\n  Publishing: {'PASS' if gp_report.final_status == 'published' and as_report.final_status == 'published' else 'REVIEW'}")

# =========================================================================== #
# Pipeline 2: Monetization Optimization
# =========================================================================== #
print("\n─── Pipeline 2: Monetization Optimization ───")

# Sample metrics simulating 7 days of MAX data
METRICS = [
    {"format": "rewarded", "country": "US", "platform": "android",
     "ecpm": 18.0, "fill_rate": 0.92, "revenue_daily": 350.0, "bid_floor": 15.0,
     "networks": [
         {"network": "AppLovin", "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
         {"network": "Mintegral", "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
         {"network": "AdMob", "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
     ]},
    {"format": "interstitial", "country": "US", "platform": "android",
     "ecpm": 6.5, "fill_rate": 0.88, "revenue_daily": 120.0, "bid_floor": 8.0},
    {"format": "rewarded", "country": "JP", "platform": "android",
     "ecpm": 8.0, "fill_rate": 0.95, "revenue_daily": 200.0, "bid_floor": 7.0},
]

BASELINES = {
    "rewarded_US_ecpm": 24.0, "rewarded_US_fill": 0.95, "rewarded_US_revenue": 420.0,
    "interstitial_US_ecpm": 7.0, "interstitial_US_fill": 0.90, "interstitial_US_revenue": 130.0,
    "rewarded_JP_ecpm": 9.0, "rewarded_JP_fill": 0.93, "rewarded_JP_revenue": 220.0,
}

# Setup memory + safety
mem_store = OperationMemoryStore(base_dir="data/demo_memory")
memory = MemoryAgent(store=mem_store)
safety = SafetyAgent(memory_agent=memory)

# Planner
planner = OptimizationPlanner()
plan = planner.plan(
    GAME["game_id"], metrics=METRICS, baselines=BASELINES,
    network_data=[
        {"format": "rewarded", "country": "US", "network": "AppLovin",
         "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
        {"format": "rewarded", "country": "US", "network": "Mintegral",
         "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
        {"format": "rewarded", "country": "US", "network": "AdMob",
         "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
    ],
    current_order={"rewarded_US": ["Mintegral", "AdMob", "AppLovin"]},
    current_floors={"rewarded_US": 10.0, "interstitial_US": 8.0, "rewarded_JP": 7.0},
    current_frequencies={"rewarded": 60, "interstitial": 120},
)

print(f"\n  Signals detected: {plan.metadata.get('signals_detected', 0)}")
print(f"  Actions planned:  {plan.total_actions}")
print(f"  Critical signals: {plan.metadata.get('critical_signals', 0)}")

for a in plan.actions:
    severity = "CRIT" if a.priority == 0 else "HIGH" if a.priority == 1 else "MED" if a.priority == 2 else "LOW"
    pct = a.changes.get("change_pct", "—")
    print(f"  [{severity}] {a.action_type:25s} | {a.country:4s} {a.ad_format:14s} | Δ{pct}")

# Executor
executor = OptimizationExecutor(safety_agent=safety, memory_agent=memory, dry_run=True)
result = executor.execute(plan)

print(f"\n  Execution:")
print(f"    Executed: {result.actions_executed}")
print(f"    Blocked:  {result.actions_blocked}")
print(f"    Failed:   {result.actions_failed}")
print(f"    Rate:     {result.success_rate:.0%}")

# Scheduler
scheduler = OptimizationScheduler(planner=planner, executor=executor)
cycle = scheduler.run_cycle(GAME["game_id"], metrics=METRICS, baselines=BASELINES,
    network_data=[
        {"format": "rewarded", "country": "US", "network": "AppLovin",
         "ecpm_7d_avg": 19.0, "impressions_7d": 5000},
        {"format": "rewarded", "country": "US", "network": "Mintegral",
         "ecpm_7d_avg": 14.0, "impressions_7d": 3000},
        {"format": "rewarded", "country": "US", "network": "AdMob",
         "ecpm_7d_avg": 17.0, "impressions_7d": 4000},
    ],
    current_order={"rewarded_US": ["Mintegral", "AdMob", "AppLovin"]},
    current_floors={"rewarded_US": 10.0},
    dry_run=True,
)

print(f"\n  Cycle: {cycle['signals_detected']} signals → {cycle['actions_planned']} planned → {cycle['actions_executed']} executed")
print(f"  Elapsed: {cycle['elapsed_ms']}ms | Dry run: {cycle['dry_run']}")

# Memory summary
summary = memory.summary(GAME["game_id"])
print(f"\n  Memory: {summary['total_operations']} operations recorded, success rate {summary['success_rate']:.0%}")

# =========================================================================== #
# Final
# =========================================================================== #
print("\n" + "=" * 60)
print(f"  PUBLISHING:  {gp_report.final_status.upper()}")
print(f"  OPTIMIZATION: {plan.total_actions} actions planned, {result.actions_executed} executed")
print(f"  E15 PIPELINE DEMO COMPLETE")
print("=" * 60)
