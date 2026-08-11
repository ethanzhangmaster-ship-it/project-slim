from creative_remix_engine.core.remix_engine import RemixEngine

engine = RemixEngine(game_code="P04")

print("\n" + "="*60)
print("测试1: bomb_15s 模板 (快节奏爆款)")
print("="*60)
result1 = engine.generate(template="bomb_15s", target_ratio="9X16", count=20, build_video=True)

print("\n--- TOP 10 ---")
for p in result1["predictions"][:10]:
    status = "✅" if p["recommendation"] == "TEST" else "⚠️"
    print(f"{status} {p['creative_id']:<25} | Score: {p['overall_score']:>5.1f} | "
          f"Hook: {p['hook_score']:>4.1f} | CTR: {p['ctr_score']:>4.1f} | "
          f"Purch: {p['purchase_score']:>4.1f} | {p['recommendation']}")

print("\n" + "="*60)
print("测试2: standard_30s 模板 (标准买量)")
print("="*60)
result2 = engine.generate(template="standard_30s", target_ratio="9X16", count=10, build_video=False)

print("\n--- TOP 5 ---")
for p in result2["predictions"][:5]:
    print(f"{p['creative_id']}: Score={p['overall_score']:.1f} Rec={p['recommendation']}")
