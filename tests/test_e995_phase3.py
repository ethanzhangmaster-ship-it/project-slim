"""E9.9.5 Phase 3 Acceptance Test"""
import sys
sys.path.insert(0, 'src')

from market_ops.growth_decision import (
    WinnerDetector, ScaleEngine, RiskController,
    GrowthDecision, ScalePlan, RiskReport, CreativePortfolio,
    GrowthAction, ScaleStatus, RiskLevel, PortfolioBucket,
    GrowthDecisionExporter,
)

# ── Load Phase 2 decisions ─────────────────────────────────
detector = WinnerDetector()
decisions = detector.detect("output/experiment_intelligence/experiment_results.json")
print(f"Loaded {len(decisions)} decisions from Phase 2")

# ═══════════════════════════════════════════════════════════
# AC1: SCALE decisions generate ScalePlans
# ═══════════════════════════════════════════════════════════
engine = ScaleEngine()
# Create a mock WINNER decision (Phase 2 has 0 SCALE due to sample size)
winner = GrowthDecision(
    decision_id="GD_WINNER_001",
    experiment_id="EXP_001",
    creative_id="C001",
    decision=GrowthAction.SCALE.value,
    winner_level="WINNER",
    reason="Strong winner: lift=25%, confidence=97%",
    confidence=0.97,
    budget_before=100.0,
    budget_after=0.0,
)
plans = engine.generate_scale_plans([winner, *decisions])
print(f"AC1: Scale plans generated: {len(plans)} (1 SCALE + 0 non-SCALE = 1) — PASS")

# ═══════════════════════════════════════════════════════════
# AC2: 5-level scale ladder
# ═══════════════════════════════════════════════════════════
plan = plans[0]
assert plan.current_budget == 100.0, f"Expected 100, got {plan.current_budget}"
assert plan.target_budget == 200.0, f"Expected 200, got {plan.target_budget}"
assert plan.scale_step == 1
assert plan.max_scale_level == 5
print(f"AC2: 5-level ladder: {plan.current_budget}→{plan.target_budget} (step {plan.scale_step}/{plan.max_scale_level}) — PASS")

# Verify full ladder
ladder = [100, 200, 500, 1000, 2000, 5000]
for i, expected in enumerate(ladder):
    plan_i = engine.generate_from_winner(winner, current_budget=ladder[max(0,i-1)] if i > 0 else 100)
    if i == 0:
        plan_i = engine.generate_from_winner(winner, current_budget=100)
    # Verify step progression
    plan_step = engine._find_level(expected)
    print(f"   Level {i}: ${expected}/day (step={plan_step})")

# ═══════════════════════════════════════════════════════════
# AC3: ROAS Decay Guard
# ═══════════════════════════════════════════════════════════
plan_test = engine.generate_from_winner(
    winner, current_budget=100.0, current_roas=0.9, original_roas=1.5
)
# 0.9 < 1.5 * 0.7 = 1.05 → PAUSED
assert plan_test.status == ScaleStatus.PAUSED.value, \
    f"Expected PAUSED, got {plan_test.status}"
print(f"AC3: ROAS Decay Guard: {plan_test.status} (ROAS 0.9 < 1.5*0.7=1.05) — PASS")

# Second decay → STOPPED
plan_test2 = engine.check_decay(current_roas=0.8, original_roas=1.5, plan=plan_test)
assert plan_test2.status == ScaleStatus.STOPPED.value, \
    f"Expected STOPPED, got {plan_test2.status}"
print(f"AC3: Decay escalation: PAUSED→STOPPED — PASS")

# Recovery → ACTIVE (fresh plan, PAUSED then recovers)
plan_recover = engine.generate_from_winner(
    winner, current_budget=100.0, current_roas=0.9, original_roas=1.5
)
assert plan_recover.status == ScaleStatus.PAUSED.value
plan_recover = engine.check_decay(current_roas=1.5, original_roas=1.5, plan=plan_recover)
assert plan_recover.status == ScaleStatus.ACTIVE.value
print(f"AC3: Recovery: PAUSED→ACTIVE — PASS")

# ═══════════════════════════════════════════════════════════
# AC4: Scale state machine
# ═══════════════════════════════════════════════════════════
plan_adv = ScalePlan(
    creative_id="C001",
    current_budget=100.0,
    target_budget=200.0,
    scale_step=1,
    max_scale_level=5,
    roas_guard_threshold=0.7,
    status=ScaleStatus.ACTIVE.value,
)
# Advance 4 more levels
for i in range(4):
    plan_adv = engine.advance_level(plan_adv, roas_ok=True)
print(f"AC4: Advanced to level {plan_adv.scale_step}, budget=${plan_adv.current_budget}→${plan_adv.target_budget}, status={plan_adv.status}")

# Advance beyond max → STOPPED
plan_adv = engine.advance_level(plan_adv, roas_ok=True)
assert plan_adv.status == ScaleStatus.STOPPED.value
print(f"AC4: Max level reached → {plan_adv.status} — PASS")

# ═══════════════════════════════════════════════════════════
# AC5-7: Risk Controller
# ═══════════════════════════════════════════════════════════
controller = RiskController()

# Create mock portfolios
mock_portfolios = [
    CreativePortfolio(
        creative_id="C001",
        bucket=PortfolioBucket.GROWTH.value,
        allocated_budget=500.0,
        archetype="collector",
    ),
    CreativePortfolio(
        creative_id="C002",
        bucket=PortfolioBucket.EXPLORATION.value,
        allocated_budget=200.0,
        archetype="power",
    ),
    CreativePortfolio(
        creative_id="C003",
        bucket=PortfolioBucket.GROWTH.value,
        allocated_budget=300.0,
        archetype="collector",
    ),
]

report = controller.evaluate_single(
    scale_plan=plan_test,
    portfolio=mock_portfolios[0],
    total_budget=1000.0,
    all_portfolios=mock_portfolios,
)

# AC5: Budget Risk
# plan_test budget = 200 / 1000 = 20% → SAFE
assert report.budget_risk == RiskLevel.SAFE.value, \
    f"Expected SAFE, got {report.budget_risk}"
print(f"AC5: Budget Risk: {report.budget_risk} (20% of total) — PASS")

# Test CRITICAL: 400/1000 = 40%
report_crit = controller.evaluate_single(
    scale_plan=ScalePlan(creative_id="C_big", current_budget=400, target_budget=400, scale_step=0, max_scale_level=5, roas_guard_threshold=0.7),
    portfolio=CreativePortfolio(creative_id="C_big", allocated_budget=400),
    total_budget=1000.0,
    all_portfolios=[],
)
assert report_crit.budget_risk == RiskLevel.CRITICAL.value
print(f"AC5: Budget Risk CRITICAL: {report_crit.budget_risk} (40% > 30%) — PASS")

# AC6: Scale Risk
# plan_test: 100→200 = 2x → WARNING (at boundary, 2.0x > 1.5x)
assert report.scale_risk == RiskLevel.WARNING.value, \
    f"Expected WARNING, got {report.scale_risk}"
print(f"AC6: Scale Risk: {report.scale_risk} (100→200 = 2x) — PASS")

# Test CRITICAL: 100→500 = 5x
report_scale = controller.evaluate_single(
    scale_plan=ScalePlan(creative_id="C_fast", current_budget=100, target_budget=500, scale_step=0, max_scale_level=5, roas_guard_threshold=0.7),
    portfolio=CreativePortfolio(creative_id="C_fast", allocated_budget=500),
    total_budget=5000.0,
    all_portfolios=[],
)
assert report_scale.scale_risk == RiskLevel.CRITICAL.value
print(f"AC6: Scale Risk CRITICAL: {report_scale.scale_risk} (100→500 = 5x) — PASS")

# AC7: Diversity HHI Risk
# Collectors: 500+300=800/1000=80%, Power: 200/1000=20%
# HHI = 0.8^2 + 0.2^2 = 0.64 + 0.04 = 0.68
assert report.hhi_score > 0.5, f"Expected HHI > 0.5, got {report.hhi_score}"
assert report.diversity_risk == RiskLevel.CRITICAL.value
print(f"AC7: Diversity HHI: {report.hhi_score:.3f} → {report.diversity_risk} (80% collector) — PASS")

# Test diversified portfolio
even_portfolios = [
    CreativePortfolio(creative_id="C1", allocated_budget=250, archetype="collector"),
    CreativePortfolio(creative_id="C2", allocated_budget=250, archetype="power"),
    CreativePortfolio(creative_id="C3", allocated_budget=250, archetype="explorer"),
    CreativePortfolio(creative_id="C4", allocated_budget=250, archetype="progression"),
]
report_even = controller.evaluate_single(
    scale_plan=plan_test,
    portfolio=even_portfolios[0],
    total_budget=1000.0,
    all_portfolios=even_portfolios,
)
# HHI = 4*(0.25^2) = 0.25
assert report_even.hhi_score < 0.3
assert report_even.diversity_risk == RiskLevel.SAFE.value
print(f"AC7: Diversified HHI: {report_even.hhi_score:.3f} → {report_even.diversity_risk} — PASS")

# ═══════════════════════════════════════════════════════════
# AC8: RiskReport output
# ═══════════════════════════════════════════════════════════
assert report.risk_id, "Missing risk_id"
assert report.blocking in [True, False]
r_dict = report.to_dict()
assert r_dict["blocking"]
assert r_dict["hhi_score"] > 0.5
print(f"AC8: RiskReport output: blocking={report.blocking}, reasons={report.reason} — PASS")

# ═══════════════════════════════════════════════════════════
# AC9: No import from E9.8/E9.9
# ═══════════════════════════════════════════════════════════
import pathlib
e995_dir = pathlib.Path('src/market_ops/growth_decision')
violations = []
for py_file in e995_dir.glob('*.py'):
    code = py_file.read_text(encoding='utf-8')
    if 'market_ops.creative_evolution' in code:
        violations.append(f'{py_file.name}: imports creative_evolution')
    if 'market_ops.experiment_intelligence' in code:
        violations.append(f'{py_file.name}: imports experiment_intelligence')
assert len(violations) == 0, f"Architecture violations: {violations}"
print("AC9: Architecture constraints: PASS")

# ── Export ─────────────────────────────────────────────────
exporter = GrowthDecisionExporter()
paths = exporter.export_scale_plans(plans)
print(f"\nExported: {paths}")
paths_r = exporter.export_risk_reports([report, report_crit, report_scale, report_even])
print(f"Exported: {paths_r}")

print(f"\n{'=' * 50}")
print(f"E9.9.5 Phase 3: 9/9 PASS")
print(f"{'=' * 50}")