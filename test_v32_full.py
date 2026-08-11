"""V3.2 集成测试"""
from creative_remix_engine.core.remix_engine import RemixEngine

print("=" * 70)
print("Creative Remix Engine V3.2 — Integration Test")
print("=" * 70)

engine = RemixEngine(game_code="P04")

# Step 1: Train models
print("\n[Step 1] Train ML Models...")
train_result = engine.train_models()
print(f"  Trained: {len(train_result)} models")
print(f"  Model ready: {engine.model_inference.is_ready()}")

# Step 2: Generate 50 variants
print("\n[Step 2] Generate 50 Creative Variants...")
result = engine.generate(
    template="bomb_15s",
    target_ratio="9X16",
    count=50,
    build_video=True,
    use_variants=True,
)

print(f"\n生成统计:")
print(f"  总生成: {result['total_generated']}")
print(f"  去重后: {result['after_dedup']}")
print(f"  组装视频: {result['assembled']}")
print(f"  ML模型可用: {result['ml_model_ready']}")

# TOP 10 预测
print(f"\n--- ML Prediction TOP 10 ---")
for i, pred in enumerate(result["predictions"][:10]):
    icon = "✅" if pred["recommendation"] == "TEST" else "⚠️" if "TEST" in pred["recommendation"] else "❌"
    print(f"  {icon} {i+1:2d}. {pred['creative_id']:<28} "
          f"eROAS={pred['expected_roas']:5.2f} "
          f"eCTR={pred['expected_ctr']:6.3f} "
          f"eCVR={pred['expected_cvr']:6.3f} "
          f"Score={pred['overall_score']:5.1f} "
          f"{pred['recommendation']}")

# 测试计划
if "test_plan" in result:
    tp = result["test_plan"]
    print(f"\n--- Auto Test Plan ---")
    for camp in tp.get("campaigns", []):
        print(f"  📢 {camp['name']} | 预算 ${camp['budget_per_day']:.0f}/天")
        print(f"     预期 ROAS: {camp['expected_roas_range']}")
        print(f"     Creatives: {', '.join(camp['creatives'][:3])}...")

print("\n" + "=" * 70)
print("V3.2 Integration Test PASSED")
print("=" * 70)
