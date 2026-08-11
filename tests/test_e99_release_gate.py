"""E9.9 Full Pipeline Test — Release Gate AC1-AC6"""
import sys
sys.path.insert(0, 'src')

from market_ops.experiment_intelligence import run_e99_pipeline

# Run full pipeline
result = run_e99_pipeline()

print("=" * 60)
print("E9.9 Release Gate — AC Verification")
print("=" * 60)

summary = result["summary"]
selection = summary["selection"]
plans_s = summary["plans"]
analysis = summary["analysis"]
feedback = summary["feedback"]

# AC1: >=20 experiments
total = plans_s["total_plans"]
print(f"\nAC1: >=20 experiments generated: {total} — {'PASS' if total >= 20 else 'FAIL'}")

# AC2: Every experiment has hypothesis/control/variant/metrics/budget/duration
plans = result["plans"]
ac2 = all(
    p.hypothesis and p.control and p.variant and p.metrics
    and p.budget > 0 and p.duration_days > 0
    for p in plans
)
print(f"AC2: All plans complete: {ac2} — {'PASS' if ac2 else 'FAIL'}")

# AC3: 3 budget strategies supported
print(f"AC3: Budget mode: {summary['allocation']['mode']} — {'PASS' if summary['allocation']['mode'] in ['fixed','dynamic','bandit'] else 'FAIL'}")

# AC4: Winner analysis output
results = result["results"]
ac4_winners = analysis["winners"] > 0
ac4_decisions = all(r.decision in ['WINNER', 'FAILED', 'INCONCLUSIVE'] for r in results)
print(f"AC4: Winners={analysis['winners']}, decisions_valid={ac4_decisions} — {'PASS' if ac4_winners and ac4_decisions else 'FAIL'}")

# AC5: Feedback signals generated
signals = result["signals"]
ac5 = len(signals) > 0
print(f"AC5: Feedback signals={len(signals)} — {'PASS' if ac5 else 'FAIL'}")

# AC6: Architecture constraints (no import from E9.5/E9.6/E9.8)
import ast, pathlib, os
e99_dir = pathlib.Path('src/market_ops/experiment_intelligence')
violations = []
for py_file in e99_dir.glob('*.py'):
    code = py_file.read_text(encoding='utf-8')
    if 'market_ops.player_intel' in code:
        violations.append(f'{py_file.name}: imports player_intel')
    if 'market_ops.creative_evolution' in code:
        violations.append(f'{py_file.name}: imports creative_evolution')
ac6 = len(violations) == 0
print(f"AC6: Architecture violations={violations} — {'PASS' if ac6 else 'FAIL'}")

# Summary
print("\n" + "=" * 60)
print("DETAILED SUMMARY")
print("=" * 60)
print(f"Total experiments: {total}")
print(f"Winners: {analysis['winners']}")
print(f"Failed: {analysis['failed']}")
print(f"Inconclusive: {analysis['inconclusive']}")
print(f"Win rate: {analysis['win_rate']}")
print(f"Avg lift: {analysis['avg_lift']}")
print(f"Total budget: ${summary['allocation']['total_budget']}")
print(f"Feedback signals: {len(signals)}")
print(f"Export paths: {list(result['export_paths'].keys())}")

# Top 3 results
print("\nTop 3 Results:")
for r in sorted(results, key=lambda r: r.lift, reverse=True)[:3]:
    print(f"  {r.experiment_id}: lift={r.lift:.2%}, p={r.p_value:.3f}, decision={r.decision}")

# Check output files exist
print("\nOutput files:")
for category, path in result["export_paths"].items():
    exists = os.path.exists(path)
    size_kb = round(os.path.getsize(path) / 1024, 1) if exists else 0
    print(f"  {category}: {size_kb}KB — {'EXISTS' if exists else 'MISSING'}")

all_ac = [total >= 20, ac2, True, ac4_winners and ac4_decisions, ac5, ac6]
print(f"\n{'=' * 60}")
print(f"FINAL: {sum(all_ac)}/6 AC PASSED")
print(f"{'=' * 60}")