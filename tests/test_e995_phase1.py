"""E9.9.5 Phase 1 Acceptance Test"""
import sys
sys.path.insert(0, 'src')

# 1. Package import
from market_ops.growth_decision import (
    GrowthDecision, CreativePortfolio, ScalePlan, RiskReport,
    GrowthAction, WinnerLevel, PortfolioBucket, LifecycleStage, ScaleStatus, RiskLevel,
    GrowthDecisionExporter,
)
print("1. Package import: PASS")

# 2. Enum validation
assert GrowthAction.SCALE.value == "SCALE"
assert WinnerLevel.WINNER.value == "WINNER"
assert WinnerLevel.PROMISING.value == "PROMISING"
assert WinnerLevel.FAILED.value == "FAILED"
assert WinnerLevel.INCONCLUSIVE.value == "INCONCLUSIVE"
assert PortfolioBucket.EXPLORATION.value == "EXPLORATION"
assert PortfolioBucket.GROWTH.value == "GROWTH"
assert PortfolioBucket.HARVEST.value == "HARVEST"
assert LifecycleStage.NEW.value == "NEW"
assert LifecycleStage.GROWING.value == "GROWING"
assert LifecycleStage.RETIRED.value == "RETIRED"
assert ScaleStatus.ACTIVE.value == "ACTIVE"
assert RiskLevel.SAFE.value == "SAFE"
assert RiskLevel.CRITICAL.value == "CRITICAL"
print("2. Enum validation: PASS")

# 3. Schema serialization
d = GrowthDecision(
    decision_id="GD001",
    experiment_id="EXP_001",
    creative_id="C001",
    decision=GrowthAction.SCALE.value,
    winner_level=WinnerLevel.WINNER.value,
    reason="ROAS +35%, confidence 97%",
    confidence=0.97,
    budget_before=100,
    budget_after=200,
)
d_dict = d.to_dict()
assert d_dict["decision"] == "SCALE"
assert d_dict["winner_level"] == "WINNER"
assert d_dict["confidence"] == 0.97

p = CreativePortfolio(
    creative_id="C001",
    bucket=PortfolioBucket.GROWTH.value,
    lifecycle_stage=LifecycleStage.GROWING.value,
    allocated_budget=500,
    roi=1.35,
    risk_score=0.2,
    archetype="collector",
)
p_dict = p.to_dict()
assert p_dict["bucket"] == "GROWTH"
assert p_dict["lifecycle_stage"] == "GROWING"

s = ScalePlan(
    creative_id="C001",
    current_budget=100,
    target_budget=200,
    scale_step=1,
    roas_guard_threshold=0.7,
    status=ScaleStatus.ACTIVE.value,
)
s_dict = s.to_dict()
assert s_dict["status"] == "ACTIVE"
assert s_dict["scale_step"] == 1

r = RiskReport(
    risk_id="R001",
    creative_id="C001",
    budget_risk=RiskLevel.SAFE.value,
    scale_risk=RiskLevel.SAFE.value,
    diversity_risk=RiskLevel.WARNING.value,
    hhi_score=0.35,
    blocking=False,
    reason="HHI within acceptable range",
)
r_dict = r.to_dict()
assert r_dict["blocking"] == False
assert r_dict["hhi_score"] == 0.35
print("3. Schema serialization: PASS")

# 4. JSON export
exporter = GrowthDecisionExporter()
paths = exporter.export_all(
    decisions=[d],
    portfolios=[p],
    scale_plans=[s],
    risk_reports=[r],
)
import os
for category, path in paths.items():
    assert os.path.exists(path), f"Missing: {path}"
    size_kb = round(os.path.getsize(path) / 1024, 1)
    print(f"   {category}: {size_kb}KB")
print("4. JSON export: PASS")

# 5. Architecture: no import from E9.8/E9.9
import pathlib
e995_dir = pathlib.Path('src/market_ops/growth_decision')
violations = []
for py_file in e995_dir.glob('*.py'):
    code = py_file.read_text(encoding='utf-8')
    if 'market_ops.creative_evolution' in code:
        violations.append(f'{py_file.name}: imports creative_evolution (E9.8)')
    if 'market_ops.experiment_intelligence' in code:
        violations.append(f'{py_file.name}: imports experiment_intelligence (E9.9)')
assert len(violations) == 0, f"Violations: {violations}"
print("5. Architecture constraints: PASS")

print(f"\n{'=' * 50}")
print("E9.9.5 Phase 1: 5/5 PASS")
print(f"{'=' * 50}")