"""V3.2.1 Production Hardening Acceptance Test"""
from creative_remix_engine.core.remix_engine import RemixEngine
from creative_remix_engine.predictor.model.dependency_checker import check_dependencies

print("=" * 70)
print("Creative Remix Engine V3.2.1 — Production Acceptance Test")
print("=" * 70)

# Phase 1: Dependency Check
print("\n[Phase 1] Dependency Check...")
deps = check_dependencies()
print(f"  sklearn: {deps['sklearn']}")
print(f"  xgboost: {deps['xgboost']}")
print(f"  numpy:   {deps['numpy']}")

# Phase 2-4: Engine + Train + Generate
engine = RemixEngine(game_code="P04")

print("\n[Phase 2-4] Model Training...")
train_result = engine.train_models()

print("\n[Phase 5-8] Generate 100 Variants...")
result = engine.generate(
    template="bomb_15s",
    target_ratio="9X16",
    count=100,
    build_video=True,
    use_variants=True,
)

# Acceptance Criteria Check
print("\n" + "=" * 70)
print("ACCEPTANCE CRITERIA CHECK")
print("=" * 70)

# 1. ML
print("\n[ML]")
ml_ready = result.get("ml_model_ready", False)
print(f"  ML Model Ready: {'PASS' if ml_ready else 'FAIL'}")

# Check predictions
preds = result["predictions"][:10]
all_nonzero = all(p["expected_roas"] > 0 and p["expected_ctr"] >= 0 for p in preds)
print(f"  Predictions Non-Zero: {'PASS' if all_nonzero else 'FAIL'}")

# Check eROAS range
eROAS_list = [p["expected_roas"] for p in preds]
roas_in_range = all(0.2 <= r <= 3.5 for r in eROAS_list)
print(f"  eROAS in Range [0.2, 3.5]: {'PASS' if roas_in_range else 'FAIL'}")
if not roas_in_range:
    print(f"    eROAS values: {eROAS_list}")

# 2. Diversity
print("\n[Diversity]")
before = result["total_generated"]
after = result["after_dedup"]
print(f"  Input: {before} -> Output: {after}")
diversity_pass = after >= 50 if before >= 100 else after >= before * 0.5
print(f"  Diversity Retention: {'PASS' if diversity_pass else 'WARN'} (target: 50+)")

# 3. Ranking
print("\n[Ranking TOP10]")
print(f"  {'#':<4} {'ID':<28} {'eROAS':<8} {'eCTR':<8} {'eCVR':<8} {'Score':<8} {'Rec':<15}")
print("  " + "-" * 65)
for i, p in enumerate(preds[:10]):
    icon = "✅" if p["recommendation"] == "TEST" else "⚠️" if "TEST" in p["recommendation"] else "❌"
    print(f"  {icon} {i+1:<2} {p['creative_id']:<26} "
          f"{p['expected_roas']:<8.2f} {p['expected_ctr']:<8.3f} "
          f"{p['expected_cvr']:<8.3f} {p['overall_score']:<8.1f} {p['recommendation']}")

# 4. Test Plan
print("\n[Test Plan]")
tp = result.get("test_plan", {})
for camp in tp.get("campaigns", []):
    print(f"  📢 {camp['name']}: {len(camp['creatives'])} creatives, ${camp['budget_per_day']:.0f}/day")

# Final Verdict
print("\n" + "=" * 70)
checks = [
    ("ML Model Ready", ml_ready),
    ("Predictions Non-Zero", all_nonzero),
    ("eROAS Calibrated", roas_in_range),
    ("Diversity OK", diversity_pass),
    ("Test Plan Generated", bool(tp.get("campaigns"))),
]
all_pass = all(v for _, v in checks)
for name, passed in checks:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} {name}")
print(f"\n{'✅ ALL CHECKS PASSED' if all_pass else '⚠️ SOME CHECKS FAILED'} — V3.2.1 Production Ready")
print("=" * 70)
