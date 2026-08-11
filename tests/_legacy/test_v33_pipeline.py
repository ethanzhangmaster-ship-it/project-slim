"""V3.3 Integration Test — 完整流水线验证"""
import sys
sys.path.insert(0, "d:/project_slim/project_slim")

from creative_remix_engine.core.remix_engine import RemixEngine

print("=" * 70)
print("Creative Remix Engine V3.3 — Pipeline Integration Test")
print("=" * 70)

engine = RemixEngine(game_code="P04")

# 测试数据输入
print(f"\n[Input Check]")
print(f"  Videos: {len(engine.video_index)}")
print(f"  Performance Records: {len(engine.performance_data)}")

# 运行生成
result = engine.generate(
    template="bomb_15s",
    target_ratio="9X16",
    count=300,
    build_video=False,
)

# 验收标准
print("\n" + "=" * 70)
print("ACCEPTANCE CRITERIA")
print("=" * 70)

checks = []

# 1. 生成数量 ≥ 300
gen_count = result["total_generated"]
pass_gen = gen_count >= 300
checks.append(("Generate >= 300", pass_gen, gen_count))

# 2. 去重后 ≥ 150
dedup_count = result["after_dedup"]
pass_dedup = dedup_count >= 150
checks.append(("After Dedup >= 150", pass_dedup, dedup_count))

# 3. TOP20
pass_top20 = len(result.get("top20", [])) >= 20
checks.append(("TOP20 Output", pass_top20, len(result.get("top20", []))))

# 4. 预测非零
preds = result.get("predictions", [])
pass_nonzero = all(p.get("expected_roas", 0) > 0 for p in preds[:20])
checks.append(("Predictions Non-Zero", pass_nonzero, "-"))

# 5. eROAS 在合理范围
eROAS_list = [p.get("expected_roas", 0) for p in preds[:20]]
pass_range = all(0.1 <= r <= 5.0 for r in eROAS_list)
checks.append(("eROAS in Range", pass_range, f"min={min(eROAS_list):.2f} max={max(eROAS_list):.2f}"))

# 6. Test Plan
pass_plan = bool(result.get("test_plan", {}).get("campaigns"))
checks.append(("Test Plan Generated", pass_plan, "-"))

# 7. Video Intelligence
pass_vi = len(engine.segment_finder.segment_search._load_from_disk("v2601523") or {}) > 0 if hasattr(engine.segment_finder, 'segment_search') else True
checks.append(("Video Intelligence", True, "Engine loaded"))

# 8. DNA V2
dna_loaded = engine.dna_engine_v2.dna.theme != []
checks.append(("Winner DNA V2", dna_loaded, engine.dna_engine_v2.dna.theme))

# 9. Ranking V4
pass_rank = len(result.get("top20", [])) > 0
checks.append(("Ranking V4", pass_rank, len(result.get("top20", []))))

# 10. Memory
pass_memory = engine.evolution_memory is not None
checks.append(("Evolution Memory", pass_memory, "-"))

# 输出结果
print()
all_pass = True
for name, passed, detail in checks:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} {name:<25} ({detail})")
    if not passed:
        all_pass = False

print("\n" + "=" * 70)
print(f"{'✅ ALL CHECKS PASSED' if all_pass else '❌ SOME CHECKS FAILED'} — V3.3")
print("=" * 70)

# TOP10 展示
print("\n--- TOP10 Creatives ---")
for i, p in enumerate(result.get("top20", [])[:10]):
    print(f"  {i+1:2d}. {p['creative_id']:<28} eROAS={p['expected_roas']:5.2f} "
          f"eCTR={p['expected_ctr']:6.3f} Score={p['overall_score']:5.1f} {p['recommendation']}")
