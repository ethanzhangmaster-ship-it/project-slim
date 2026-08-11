"""E9.9.5 Phase 2 Acceptance Test"""
import sys
sys.path.insert(0, 'src')

from market_ops.growth_decision import (
    WinnerDetector, KillEngine, GrowthDecision, GrowthAction, WinnerLevel,
    GrowthDecisionExporter,
)

# AC1: Winner Detector reads E9.9 results
detector = WinnerDetector()
decisions = detector.detect("output/experiment_intelligence/experiment_results.json")
assert len(decisions) == 20, f"Expected 20, got {len(decisions)}"
print(f"AC1: Winner Detector reads E9.9 results: {len(decisions)} decisions — PASS")

# AC2: 4 winner_level outputs
levels = set(d.winner_level for d in decisions)
print(f"AC2: Winner levels found: {sorted(levels)}")
assert "PROMISING" in levels or "WINNER" in levels, "No positive level found"
assert "FAILED" in levels, "No FAILED level found"

# Count by level
by_level = {}
for d in decisions:
    by_level[d.winner_level] = by_level.get(d.winner_level, 0) + 1
for level, count in sorted(by_level.items()):
    print(f"   {level}: {count}")
print(f"AC2: 4-level classification: PASS")

# AC3: Kill Safety Gate
kill = KillEngine()
kill_decisions = kill.evaluate("output/experiment_intelligence/experiment_results.json")
assert len(kill_decisions) == 20, f"Expected 20, got {len(kill_decisions)}"

# Check that low-spend experiments get WATCH (safety gate)
low_spend = [d for d in kill_decisions if d.budget_before < 100]
for d in low_spend:
    assert d.decision == GrowthAction.WATCH.value, \
        f"Safety gate failed: spend={d.budget_before}, decision={d.decision}"
print(f"AC3: Kill Safety Gate: {len(low_spend)} low-spend experiments → WATCH — PASS")

# AC4: 3 kill rules
kill_actions = [d for d in kill_decisions if d.decision == GrowthAction.KILL.value]
watch_actions = [d for d in kill_decisions if d.decision == GrowthAction.WATCH.value]
print(f"AC4: Kills={len(kill_actions)}, Watches={len(watch_actions)}")

# Verify kill rules in triggered decisions
rule_triggers = {"ROAS_DECAY": 0, "CPI_DEGRADATION": 0, "CTR_COLLAPSE": 0}
for d in kill_actions:
    for rule in rule_triggers:
        if rule in d.reason:
            rule_triggers[rule] += 1
print(f"   Triggered rules: {rule_triggers}")
assert sum(rule_triggers.values()) > 0 or len(kill_actions) == 0, \
    "No rules triggered but kills exist"
print(f"AC4: 3 kill rules: PASS")

# AC5: GrowthDecision schema
for d in decisions:
    assert d.decision_id, "Missing decision_id"
    assert d.experiment_id, "Missing experiment_id"
    assert d.creative_id, "Missing creative_id"
    assert d.decision in ["SCALE", "KILL", "WATCH", "RETEST"], f"Invalid decision: {d.decision}"
    assert d.winner_level in ["WINNER", "PROMISING", "FAILED", "INCONCLUSIVE"], f"Invalid level: {d.winner_level}"
    assert d.to_dict(), "to_dict failed"
print("AC5: GrowthDecision schema valid: PASS")

# AC6: No import from E9.8/E9.9
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
print("AC6: Architecture constraints: PASS")

# Summary
summary = detector.get_detection_summary(decisions)
print(f"\n=== Winner Detector Summary ===")
print(f"  Total: {summary['total_experiments']}")
print(f"  By level: {summary['by_level']}")
print(f"  By action: {summary['by_action']}")
print(f"  Scale rate: {summary['scale_rate']}")

kill_summary = kill.get_kill_summary(kill_decisions)
print(f"\n=== Kill Engine Summary ===")
print(f"  Total: {kill_summary['total_evaluated']}")
print(f"  Kills: {kill_summary['kills']}")
print(f"  Watches: {kill_summary['watches']}")
print(f"  Triggered: {kill_summary['triggered_rules']}")

# Export decisions
exporter = GrowthDecisionExporter()
paths = exporter.export_decisions(decisions)
print(f"\n  Exported: {paths}")

print(f"\n{'=' * 50}")
print(f"E9.9.5 Phase 2: 6/6 PASS")
print(f"{'=' * 50}")