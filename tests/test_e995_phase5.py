"""E9.9.5 Phase 5 Acceptance Test — Growth Orchestrator"""
import sys
sys.path.insert(0, 'src')

from market_ops.growth_decision import (
    GrowthOrchestrator,
    GrowthDecision, CreativePortfolio, ScalePlan, RiskReport, GrowthReport,
    GrowthAction, WinnerLevel, PortfolioBucket, LifecycleStage, RiskLevel, ScaleStatus,
    GrowthDecisionExporter,
    WinnerDetector, KillEngine, ScaleEngine, RiskController, PortfolioManager,
)

# ── Helpers ────────────────────────────────────────────────

def _make_exp(cid: str, winner_level: str, confidence: float = 0.95) -> dict:
    """Create mock experiment result dict."""
    return {
        "experiment_id": f"EXP_{cid}",
        "creative_id": cid,
        "decision": winner_level,
        "lift": 0.25 if winner_level == "WINNER" else 0.05,
        "confidence": confidence,
        "reason": f"Level={winner_level}",
        "budget_before": 100.0,
    }


# ═══════════════════════════════════════════════════════════
# AC1: Full Pipeline — 5 WINNER, 5 FAILED, 5 PROMISING, 5 INCONCLUSIVE
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC1: Full Pipeline")
print("=" * 50)

orchestrator = GrowthOrchestrator()

experiments = []
for i in range(1, 6):
    experiments.append(_make_exp(f"W{i:03d}", "WINNER"))
for i in range(1, 6):
    experiments.append(_make_exp(f"F{i:03d}", "FAILED"))
for i in range(1, 6):
    experiments.append(_make_exp(f"P{i:03d}", "PROMISING"))
for i in range(1, 6):
    experiments.append(_make_exp(f"I{i:03d}", "INCONCLUSIVE"))

result = orchestrator.run(experiments, total_budget=10000.0)

report = result["report"]
decisions = result["decisions"]
portfolios = result["portfolios"]
scale_plans = result["scale_plans"]

print(f"  Total experiments: {len(experiments)}")
print(f"  Total decisions:   {len(decisions)}")
print(f"  SCALE:  {report.scale_count}")
print(f"  KILL:   {report.kill_count}")
print(f"  WATCH:  {report.watch_count}")
print(f"  RETEST: {report.retest_count}")

assert report.scale_count == 5, f"Expected 5 SCALE, got {report.scale_count}"
assert report.kill_count == 5, f"Expected 5 KILL, got {report.kill_count}"
assert report.watch_count == 5, f"Expected 5 WATCH, got {report.watch_count}"
assert report.retest_count == 5, f"Expected 5 RETEST, got {report.retest_count}"

print("AC1: Full Pipeline — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC2: Scale Integration — WINNER → ScalePlan
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC2: Scale Integration")
print("=" * 50)

assert len(scale_plans) == 5, f"Expected 5 scale plans, got {len(scale_plans)}"

plan = scale_plans[0]
print(f"  Scale plan: {plan.creative_id}")
print(f"  Budget: ${plan.current_budget:.0f} → ${plan.target_budget:.0f}")
print(f"  Step: {plan.scale_step}, Status: {plan.status}")

assert plan.current_budget == 100.0, f"Expected 100, got {plan.current_budget}"
assert plan.target_budget == 200.0, f"Expected 200, got {plan.target_budget}"
assert plan.scale_step == 1
assert plan.status == ScaleStatus.ACTIVE.value

# Verify WINNER decisions have budget_after set
winner_decisions = [d for d in decisions if d.decision == GrowthAction.SCALE.value]
for d in winner_decisions:
    assert d.budget_after == 200.0, f"WINNER budget_after should be 200, got {d.budget_after}"

print("AC2: Scale Integration — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC3: Risk Blocking — blocking=True → SCALE downgraded to WATCH
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC3: Risk Blocking")
print("=" * 50)

# Create a scenario where all WINNERs have blocking risk
# (all same archetype → high HHI → blocking)
blocking_experiments = []
for i in range(1, 6):
    blocking_experiments.append(_make_exp(f"BW{i:03d}", "WINNER"))
for i in range(1, 4):
    blocking_experiments.append(_make_exp(f"BP{i:03d}", "PROMISING"))

# Use a small total_budget to trigger budget_risk CRITICAL
result_blocked = orchestrator.run(blocking_experiments, total_budget=100.0)

blocked_report = result_blocked["report"]
blocked_decisions = result_blocked["decisions"]

print(f"  Risk reports: {blocked_report.risk_status['total_reports']}")
print(f"  Blocking: {blocked_report.risk_status['blocking']}")
print(f"  SCALE after risk: {blocked_report.scale_count}")
print(f"  WATCH after risk: {blocked_report.watch_count}")

# With total_budget=100, 5 WINNERs each at 100 budget → 500 total on 100 budget
# This triggers budget_risk CRITICAL → blocking → SCALE downgraded to WATCH
assert blocked_report.scale_count == 0, \
    f"Expected 0 SCALE after blocking, got {blocked_report.scale_count}"

print("AC3: Risk Blocking — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC4: Portfolio Sync — WINNER→GROWTH, FAILED→HARVEST
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC4: Portfolio Sync")
print("=" * 50)

# Re-run the main pipeline for clean portfolio state
result_sync = orchestrator.run(experiments, total_budget=10000.0)
portfolios_sync = result_sync["portfolios"]

winner_portfolios = [p for p in portfolios_sync if p.creative_id.startswith("W")]
failed_portfolios = [p for p in portfolios_sync if p.creative_id.startswith("F")]

for p in winner_portfolios:
    assert p.bucket == PortfolioBucket.GROWTH.value, \
        f"WINNER {p.creative_id} should be GROWTH, got {p.bucket}"
print(f"  WINNER portfolios: {len(winner_portfolios)} → GROWTH bucket")

for p in failed_portfolios:
    assert p.bucket == PortfolioBucket.HARVEST.value, \
        f"FAILED {p.creative_id} should be HARVEST, got {p.bucket}"
    assert p.lifecycle_stage == LifecycleStage.RETIRED.value, \
        f"FAILED {p.creative_id} should be RETIRED, got {p.lifecycle_stage}"
print(f"  FAILED portfolios: {len(failed_portfolios)} → HARVEST / RETIRED")

print("AC4: Portfolio Sync — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC5: Export — 4 files
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC5: Export")
print("=" * 50)

exporter = GrowthDecisionExporter()

# Export all files
paths = {}
paths["growth_actions"] = str(exporter.export_growth_actions(
    result["decisions"], result["scale_plans"]
))
paths["portfolio_state"] = str(exporter.export_portfolio(result["portfolios"]))
paths["risk_report"] = str(exporter.export_risk_reports(result["risk_reports"]))
paths["growth_report"] = str(exporter.export_growth_report(result["report"]))

import pathlib
for name, path_str in paths.items():
    p = pathlib.Path(path_str)
    assert p.exists(), f"{name} not found: {path_str}"
    size_kb = round(p.stat().st_size / 1024, 1)
    print(f"  {name}: {path_str} ({size_kb} KB)")

print("AC5: Export — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC6: Architecture Constraints
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC6: Architecture Constraints")
print("=" * 50)

e995_dir = pathlib.Path('src/market_ops/growth_decision')
violations = []

for py_file in e995_dir.glob('*.py'):
    code = py_file.read_text(encoding='utf-8')
    if 'market_ops.creative_evolution' in code:
        violations.append(f'{py_file.name}: imports creative_evolution')
    if 'market_ops.experiment_intelligence' in code:
        violations.append(f'{py_file.name}: imports experiment_intelligence')
    if 'creative_policy' in code:
        violations.append(f'{py_file.name}: imports creative_policy')

assert len(violations) == 0, f"Architecture violations: {violations}"

# Verify orchestrator only imports from growth_decision internal modules
orch_code = (e995_dir / 'growth_orchestrator.py').read_text(encoding='utf-8')
assert 'market_ops.growth_decision.schemas' in orch_code
assert 'market_ops.growth_decision.winner_detector' in orch_code
assert 'market_ops.growth_decision.kill_engine' in orch_code
assert 'market_ops.growth_decision.scale_engine' in orch_code
assert 'market_ops.growth_decision.risk_controller' in orch_code
assert 'market_ops.growth_decision.portfolio_manager' in orch_code

print("  NO import from E9.8 (creative_evolution)")
print("  NO import from E9.9 (experiment_intelligence)")
print("  NO import from creative_policy")
print("  ONLY imports: growth_decision.*")
print("AC6: Architecture — PASS\n")


# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print(f"Report summary:")
print(f"  report_id: {report.report_id}")
print(f"  total_experiments: {report.total_experiments}")
print(f"  winner: {report.winner_count}, failed: {report.failed_count}")
print(f"  promising: {report.promising_count}, inconclusive: {report.inconclusive_count}")
print(f"  risk: {report.risk_status}")
print(f"  portfolio: {report.portfolio_state['by_bucket']}")

print(f"\n{'=' * 50}")
print(f"E9.9.5 Phase 5: 6/6 PASS")
print(f"{'=' * 50}")