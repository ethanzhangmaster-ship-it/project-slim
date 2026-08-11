"""V3.1 集成测试"""
from creative_remix_engine.core.remix_engine import RemixEngine

print("=" * 70)
print("Creative Remix Engine V3.1 — Integration Test")
print("=" * 70)

engine = RemixEngine(game_code="P04")

# 测试1: 生成 20 个变体，只组装 TOP3
print("\n[测试] bomb_15s 模板, 20 variants, 组装 TOP3")
result = engine.generate(
    template="bomb_15s",
    target_ratio="9X16",
    count=20,
    build_video=True,
    use_variants=True,
)

print(f"\n生成总数: {result['total_generated']}")
print(f"组装数量: {result['assembled']}")

# TOP 5 预测结果
print("\n--- AI 预测 TOP 5 ---")
for i, pred in enumerate(result["predictions"][:5]):
    print(f"  {i+1}. {pred['creative_id']}")
    print(f"      eROAS: {pred['expected_roas']:.2f} | eCTR: {pred['expected_ctr']:.3f} | eCVR: {pred['expected_cvr']:.3f}")
    print(f"      Score: {pred['overall_score']:.1f} | Rec: {pred['recommendation']} | Conf: {pred['confidence']:.0%}")

# QA 结果
if result["qa_results"]:
    print(f"\n--- QA 结果 ---")
    for qa in result["qa_results"][:3]:
        status = "✅" if qa["ai_passed"] else "❌"
        print(f"  {status} {qa['creative_id']} | Quality: {qa['quality_score']} | Issues: {len(qa['issues'])}")

print("\n" + "=" * 70)
print("V3.1 集成测试完成!")
print("=" * 70)
