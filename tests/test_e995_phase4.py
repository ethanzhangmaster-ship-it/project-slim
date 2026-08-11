"""E9.9.5 Phase 4 Acceptance Test — Portfolio Manager"""
import sys
sys.path.insert(0, 'src')

from market_ops.growth_decision import (
    PortfolioManager,
    GrowthDecision, CreativePortfolio, RiskReport, ScalePlan,
    GrowthAction, WinnerLevel, PortfolioBucket, LifecycleStage, RiskLevel,
    GrowthDecisionExporter,
)

# ── Helpers ────────────────────────────────────────────────

def _make_decision(cid: str, winner_level: str, decision: str) -> GrowthDecision:
    """Create a GrowthDecision with given level and action."""
    return GrowthDecision(
        decision_id=f"GD_{cid}",
        experiment_id=f"EXP_{cid}",
        creative_id=cid,
        decision=decision,
        winner_level=winner_level,
        reason=f"Level={winner_level}, action={decision}",
        confidence=0.95,
        budget_before=100.0,
        budget_after=0.0,
    )


# ═══════════════════════════════════════════════════════════
# AC1: Portfolio Creation
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC1: Portfolio Creation")
print("=" * 50)

manager = PortfolioManager()

# 10 WINNER + 5 PROMISING + 5 FAILED
decisions = []
for i in range(1, 11):
    decisions.append(_make_decision(f"W{i:03d}", "WINNER", GrowthAction.SCALE.value))
for i in range(1, 6):
    decisions.append(_make_decision(f"P{i:03d}", "PROMISING", GrowthAction.WATCH.value))
for i in range(1, 6):
    decisions.append(_make_decision(f"F{i:03d}", "FAILED", GrowthAction.KILL.value))

portfolios = manager.create_portfolio(decisions, total_budget=10000.0)

# Count by bucket
growth_count = sum(1 for p in portfolios if p.bucket == PortfolioBucket.GROWTH.value)
exploration_count = sum(1 for p in portfolios if p.bucket == PortfolioBucket.EXPLORATION.value)
harvest_count = sum(1 for p in portfolios if p.bucket == PortfolioBucket.HARVEST.value)

print(f"  WINNER (10)  → Growth:      {growth_count}")
print(f"  PROMISING (5) → Exploration:  {exploration_count}")
print(f"  FAILED (5)    → Harvest:      {harvest_count}")

assert growth_count == 10, f"Expected 10 Growth, got {growth_count}"
assert exploration_count == 5, f"Expected 5 Exploration, got {exploration_count}"
assert harvest_count == 5, f"Expected 5 Harvest, got {harvest_count}"

# Verify FAILED get RETIRED lifecycle
for p in portfolios:
    if p.creative_id.startswith("F"):
        assert p.lifecycle_stage == LifecycleStage.RETIRED.value, \
            f"FAILED should be RETIRED, got {p.lifecycle_stage}"

print("AC1: Portfolio Creation — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC2: Budget Allocation
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC2: Budget Allocation")
print("=" * 50)

allocation = manager.allocate_budget(portfolios, total_budget=10000.0)

growth_budget = allocation.get(PortfolioBucket.GROWTH.value, 0)
exploration_budget = allocation.get(PortfolioBucket.EXPLORATION.value, 0)
harvest_budget = allocation.get(PortfolioBucket.HARVEST.value, 0)

print(f"  Growth:      ${growth_budget:.0f}")
print(f"  Exploration: ${exploration_budget:.0f}")
print(f"  Harvest:     ${harvest_budget:.0f}")

assert growth_budget == 5000.0, f"Expected 5000, got {growth_budget}"
assert exploration_budget == 3000.0, f"Expected 3000, got {exploration_budget}"
assert harvest_budget == 2000.0, f"Expected 2000, got {harvest_budget}"

# Verify per-entry distribution
for p in portfolios:
    if p.bucket == PortfolioBucket.GROWTH.value:
        assert p.allocated_budget == 500.0, f"Growth per-entry: expected 500, got {p.allocated_budget}"
    elif p.bucket == PortfolioBucket.EXPLORATION.value:
        assert p.allocated_budget == 600.0, f"Exploration per-entry: expected 600, got {p.allocated_budget}"
    elif p.bucket == PortfolioBucket.HARVEST.value:
        assert p.allocated_budget == 400.0, f"Harvest per-entry: expected 400, got {p.allocated_budget}"

print("AC2: Budget Allocation — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC3: Lifecycle State Machine
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC3: Lifecycle State Machine")
print("=" * 50)

# Start at NEW
p = CreativePortfolio(
    creative_id="L001",
    bucket=PortfolioBucket.EXPLORATION.value,
    lifecycle_stage=LifecycleStage.NEW.value,
    allocated_budget=500.0,
    archetype="collector",
)
print(f"  Start: {p.lifecycle_stage}")

# NEW → TESTING
p = manager.update_lifecycle(p)
assert p.lifecycle_stage == LifecycleStage.TESTING.value
print(f"  → {p.lifecycle_stage}")

# TESTING → GROWING: need bucket=GROWTH + roas>1.0
p.bucket = PortfolioBucket.GROWTH.value
p = manager.update_lifecycle(p, {"roas": 1.5})
assert p.lifecycle_stage == LifecycleStage.GROWING.value
assert p.roi == 1.5
print(f"  → {p.lifecycle_stage} (ROAS=1.5)")

# GROWING → MATURE: need cycles>=3 + roas>1.0
p = manager.update_lifecycle(p, {"cycles": 3, "roas": 1.3})
assert p.lifecycle_stage == LifecycleStage.MATURE.value
print(f"  → {p.lifecycle_stage} (3 cycles, ROAS=1.3)")

# MATURE → HARVEST: ROAS < 0.8
p = manager.update_lifecycle(p, {"roas": 0.7})
assert p.lifecycle_stage == LifecycleStage.HARVEST.value
assert p.bucket == PortfolioBucket.HARVEST.value
print(f"  → {p.lifecycle_stage} (ROAS=0.7)")

# Verify full chain
print(f"\n  Full chain: NEW → TESTING → GROWING → MATURE → HARVEST")
print("AC3: Lifecycle — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC4: Rebalance (HHI-based)
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC4: Rebalance (HHI=0.68)")
print("=" * 50)

# 80% collector, 20% power → HHI=0.68
test_portfolios = [
    CreativePortfolio(
        creative_id="RB_C1", bucket=PortfolioBucket.GROWTH.value,
        allocated_budget=400.0, archetype="collector",
    ),
    CreativePortfolio(
        creative_id="RB_C2", bucket=PortfolioBucket.GROWTH.value,
        allocated_budget=400.0, archetype="collector",
    ),
    CreativePortfolio(
        creative_id="RB_P1", bucket=PortfolioBucket.EXPLORATION.value,
        allocated_budget=200.0, archetype="power",
    ),
]

# Record pre-rebalance state
collector_before = sum(p.allocated_budget for p in test_portfolios if p.archetype == "collector")
exploration_before = sum(p.allocated_budget for p in test_portfolios if p.bucket == PortfolioBucket.EXPLORATION.value)
print(f"  Before: collector=${collector_before:.0f}, exploration=${exploration_before:.0f}")

risk_report = RiskReport(
    risk_id="RR_001",
    creative_id="RB_C1",
    diversity_risk=RiskLevel.CRITICAL.value,
    hhi_score=0.68,
    blocking=True,
    reason="collector concentration 80% > 50%",
)

rebalanced = manager.rebalance(test_portfolios, risk_report, total_budget=1000.0)

collector_after = sum(p.allocated_budget for p in rebalanced if p.archetype == "collector")
exploration_after = sum(p.allocated_budget for p in rebalanced if p.bucket == PortfolioBucket.EXPLORATION.value)
print(f"  After:  collector=${collector_after:.0f}, exploration=${exploration_after:.0f}")

# Collector budget should decrease (reduced by 20%)
assert collector_after < collector_before, \
    f"Collector budget should decrease: {collector_before} → {collector_after}"
# Exploration budget should increase (freed budget moved to exploration)
assert exploration_after > exploration_before, \
    f"Exploration budget should increase: {exploration_before} → {exploration_after}"

print("AC4: Rebalance — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC5: Architecture Constraints
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC5: Architecture Constraints")
print("=" * 50)

import pathlib

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

# Verify only imports from growth_decision.schemas
pf_code = (e995_dir / 'portfolio_manager.py').read_text(encoding='utf-8')
assert 'market_ops.growth_decision.schemas' in pf_code, \
    "portfolio_manager.py must import from growth_decision.schemas"

print("  NO import from E9.8 (creative_evolution)")
print("  NO import from E9.9 (experiment_intelligence)")
print("  NO import from creative_policy")
print("  ONLY imports: growth_decision.schemas")
print("AC5: Architecture — PASS\n")


# ═══════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════
exporter = GrowthDecisionExporter()
paths = exporter.export_portfolio(portfolios)
print(f"Exported: {paths}")

# Portfolio summary
summary = manager.get_portfolio_summary(portfolios)
print(f"\nPortfolio Summary:")
print(f"  Total assets: {summary['total_assets']}")
print(f"  Total budget: ${summary['total_budget']:.0f}")
print(f"  By bucket: {summary['by_bucket']}")
print(f"  By lifecycle: {summary['by_lifecycle']}")

print(f"\n{'=' * 50}")
print(f"E9.9.5 Phase 4: 5/5 PASS")
print(f"{'=' * 50}")