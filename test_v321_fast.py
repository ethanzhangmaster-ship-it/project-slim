"""V3.2.1 Fast Test — 不生成视频，只测预测逻辑"""
from creative_remix_engine.core.remix_engine import RemixEngine
from creative_remix_engine.predictor.model.dependency_checker import check_dependencies
from creative_remix_engine.predictor.calibration import PredictionCalibrator

print("=" * 70)
print("V3.2.1 Fast Acceptance Test")
print("=" * 70)

# Phase 1: Dependency Check
deps = check_dependencies()
print(f"\n[Deps] sklearn={deps['sklearn']}, xgboost={deps['xgboost']}, numpy={deps['numpy']}")

# Phase 2: Calibration Unit Test
print("\n[Calibration Unit Test]")
c = PredictionCalibrator()
print(f"  calibrate(eROAS=18.15) -> {c.calibrate({'expected_roas': 18.15})}")
print(f"  calibrate(eROAS=0.1)   -> {c.calibrate({'expected_roas': 0.1})}")
print(f"  calibrate(eROAS=5.0)   -> {c.calibrate({'expected_roas': 5.0})}")

# Phase 3: Full Pipeline (no video)
engine = RemixEngine(game_code="P04")
engine.train_models()

result = engine.generate(
    template="bomb_15s",
    target_ratio="9X16",
    count=100,
    build_video=False,  # 不生成视频，只测逻辑
    use_variants=True,
)

# Checks
print("\n" + "=" * 70)
print("ACCEPTANCE CHECK")
print("=" * 70)

preds = result["predictions"][:10]
eROAS_list = [p["expected_roas"] for p in preds]

print(f"\n[ML] Model Ready: {result['ml_model_ready']}")
print(f"[ML] Predictions Non-Zero: {all(p['expected_roas'] > 0 for p in preds)}")
print(f"[Calibration] eROAS in [0.2, 3.5]: {all(0.2 <= r <= 3.5 for r in eROAS_list)}")
print(f"[Calibration] eROAS values: {eROAS_list}")

print(f"\n[Diversity] {result['total_generated']} -> {result['after_dedup']} (target 50+)")
print(f"[Diversity] PASS: {result['after_dedup'] >= 50}")

print(f"\n[Ranking TOP5]")
for i, p in enumerate(preds[:5]):
    print(f"  {i+1}. {p['creative_id']:<28} eROAS={p['expected_roas']:.2f} eCTR={p['expected_ctr']:.3f} Score={p['overall_score']:.1f} {p['recommendation']}")

print(f"\n[Test Plan] Campaigns: {len(result.get('test_plan', {}).get('campaigns', []))}")

# Final
all_pass = (
    result['ml_model_ready'] and
    all(0.2 <= r <= 3.5 for r in eROAS_list) and
    result['after_dedup'] >= 50
)
print(f"\n{'✅ ALL CHECKS PASSED' if all_pass else '❌ SOME FAILED'} — V3.2.1")
print("=" * 70)
