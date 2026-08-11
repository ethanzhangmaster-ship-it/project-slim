"""P04 创意管线一键执行: Knowledge → Planner → Lovart生成 → 评分筛选

完整链路:
  1. 加载 CreativeKnowledgeBase (M5), 获取 P04 正向/负向规则
  2. CreativePlanner (M6) 基于规则生成 Prompt
  3. CreativeImageGenerator 调用 Lovart 生成图片
  4. CreativeImageScorer 5维评分 + 阈值筛选
  5. 输出最终可投放图片结果

用法:
  python scripts/run_p04_creative_pipeline.py
  python scripts/run_p04_creative_pipeline.py --count 3   # 只生成3张
  python scripts/run_p04_creative_pipeline.py --strategy exploit  # 全用winner变异
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = ROOT / ".env"

if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description="P04 创意管线: KB → Planner → Lovart → Scorer")
    parser.add_argument("--count", type=int, default=6, help="生成图片数量 (默认6)")
    parser.add_argument("--strategy", default="balanced", choices=["balanced", "exploit", "explore"])
    parser.add_argument("--threshold", type=float, default=6.0, help="评分通过阈值 (默认6.0)")
    parser.add_argument("--dry-run", action="store_true", help="只生成prompt,不实际出图")
    args = parser.parse_args()

    project = "P04"
    run_id = datetime.now().strftime("p04_pipeline_%Y%m%d_%H%M%S")
    output_root = ROOT / "output" / "creative_intelligence"
    run_dir = output_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"  P04 创意管线")
    print(f"  Run ID: {run_id}")
    print(f"  策略: {args.strategy} | 数量: {args.count} | 阈值: {args.threshold}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ========================================================================
    # Phase 1: 加载 Knowledge Base
    # ========================================================================
    print(f"\n{'─' * 70}")
    print("  Phase 1: 知识库加载 (M5)")
    print(f"{'─' * 70}")

    from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase

    kb = CreativeKnowledgeBase()
    positive_rules = kb.get_top_rules(project=project, effect="positive", limit=20)
    negative_rules = kb.get_avoid_rules(project=project, limit=10)

    print(f"  正向规则: {len(positive_rules)} 条")
    for r in positive_rules[:5]:
        print(f"    ✓ {r['pattern']:45s} {r['metric']:8s} lift={r['lift_pct']:+.1f}%  samples={r['sample_count']}")
    if len(positive_rules) > 5:
        print(f"    ... 还有 {len(positive_rules) - 5} 条")

    print(f"\n  负面规则: {len(negative_rules)} 条")
    for r in negative_rules:
        print(f"    ✗ {r['pattern']:45s} {r['metric']:8s} lift={r['lift_pct']:+.1f}%")

    # ========================================================================
    # Phase 2: Creative Planner 生成 Prompt
    # ========================================================================
    print(f"\n{'─' * 70}")
    print("  Phase 2: 创意规划 (M6)")
    print(f"{'─' * 70}")

    from market_ops.creative_intelligence.creative_planner import CreativePlanner

    planner = CreativePlanner()
    prompts = planner.plan(project=project, count=args.count, strategy=args.strategy)

    print(f"\n  生成 {len(prompts)} 个 Prompt:")
    for i, p in enumerate(prompts, 1):
        print(f"\n  [{i}] {p['prompt_id']} ({p['type']})")
        print(f"      Hook: {p['hook_type']}")
        print(f"      Prompt: {p['prompt_text'][:120]}...")
        if p.get("based_on_rules"):
            print(f"      Rules:  {p['based_on_rules']}")
        if p.get("predicted_features"):
            print(f"      Features: {p['predicted_features']}")

    # 保存 prompt 计划
    plan_path = run_dir / "plan.json"
    plan_path.write_text(json.dumps(prompts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Plan 已保存: {plan_path}")

    if args.dry_run:
        print(f"\n{'=' * 70}")
        print(f"  [DRY RUN] 跳过图片生成,管线结束")
        print(f"{'=' * 70}")
        return 0

    # ========================================================================
    # Phase 3: Lovart 生成图片
    # ========================================================================
    print(f"\n{'─' * 70}")
    print("  Phase 3: AI 图片生成 (Lovart)")
    print(f"{'─' * 70}")

    from market_ops.creative_image_gen import CreativeImageGenerator

    gen_dir = run_dir / "generated_images"
    gen = CreativeImageGenerator(output_dir=gen_dir)

    print(f"  后端: {gen.active_backend}")
    print(f"  Lovart: {gen.is_lovart}")
    print(f"  输出目录: {gen_dir}")

    batch = gen.generate(prompts, project=project)

    print(f"\n  生成结果: {batch.total_images} 张图片")
    success_count = sum(1 for img in batch.images if img.ready_for_review)
    print(f"  就绪: {success_count} | 失败: {batch.total_images - success_count}")

    if success_count == 0:
        print("\n  ❌ 没有图片生成成功, 终止")
        return 1

    # 打印每张图片信息
    for img in batch.images:
        status = "✓" if img.ready_for_review else "✗"
        print(f"  {status} [{img.image_id}] model={img.model} hook={img.hook_type}")

    # ========================================================================
    # Phase 4: 质量评分
    # ========================================================================
    print(f"\n{'─' * 70}")
    print("  Phase 4: 质量评分 (CreativeImageScorer)")
    print(f"{'─' * 70}")

    from market_ops.creative_image_scorer import CreativeImageScorer, print_score_report, save_score_report

    scorer = CreativeImageScorer(threshold=args.threshold)
    print(f"  评分后端: {scorer.active_backend}")
    print(f"  通过阈值: {args.threshold}")

    ready_images = [img for img in batch.images if img.ready_for_review]
    image_dicts = [
        {
            "file_path": img.file_path,
            "prompt_used": img.prompt_used,
            "model": img.model,
            "image_id": img.image_id,
            "hook_type": img.hook_type,
        }
        for img in ready_images
    ]

    score_batch = scorer.score_batch(image_dicts, project="P04 Witch")

    print_score_report(score_batch)

    score_path = run_dir / "scores.json"
    save_score_report(score_batch, score_path)
    print(f"  评分报告已保存: {score_path}")

    # ========================================================================
    # Phase 5: 最终结果汇总
    # ========================================================================
    print(f"\n{'=' * 70}")
    print("  Phase 5: 最终可投放结果")
    print(f"{'=' * 70}")

    passed = [s for s in score_batch.scores if s.passed]
    passed_sorted = sorted(passed, key=lambda s: s.overall, reverse=True)
    rejected = [s for s in score_batch.scores if not s.passed]

    print(f"\n  通过: {len(passed)}/{score_batch.total_scored} (阈值={args.threshold})")
    print(f"  淘汰: {len(rejected)}")

    if passed_sorted:
        print(f"\n  {'─' * 50}")
        print(f"  🏆 可投放图片 (按综合分排序)")
        print(f"  {'─' * 50}")
        for rank, s in enumerate(passed_sorted, 1):
            print(f"\n  #{rank} [{s.image_id}] 综合分={s.overall:.1f}")
            print(f"      视觉质量={s.visual_quality:.1f} | 品牌对齐={s.brand_alignment:.1f}")
            print(f"      Hook清晰={s.hook_clarity:.1f} | 广告适合={s.ad_suitability:.1f}")
            print(f"      原创性={s.originality:.1f}")
            print(f"      文件: {s.file_path}")
            if s.strengths:
                print(f"      优点: {', '.join(s.strengths[:3])}")
    else:
        print(f"\n  ⚠️  没有图片通过评分阈值 ({args.threshold})")
        if rejected:
            best_rejected = max(rejected, key=lambda s: s.overall)
            print(f"  最高分被淘汰: {best_rejected.image_id} (综合分={best_rejected.overall:.1f})")
            print(f"  淘汰原因: {best_rejected.reject_reason}")

    # 输出最终结果 JSON
    final_report = {
        "run_id": run_id,
        "project": project,
        "strategy": args.strategy,
        "threshold": args.threshold,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "prompts_generated": len(prompts),
            "images_generated": batch.total_images,
            "images_ready": success_count,
            "images_scored": score_batch.total_scored,
            "images_passed": len(passed),
            "images_rejected": len(rejected),
            "avg_score": score_batch.avg_overall,
        },
        "knowledge_base": {
            "positive_rules_count": len(positive_rules),
            "negative_rules_count": len(negative_rules),
        },
        "passed_images": [
            {
                "rank": i + 1,
                "image_id": s.image_id,
                "file_path": s.file_path,
                "overall": s.overall,
                "visual_quality": s.visual_quality,
                "brand_alignment": s.brand_alignment,
                "hook_clarity": s.hook_clarity,
                "ad_suitability": s.ad_suitability,
                "originality": s.originality,
                "strengths": s.strengths,
            }
            for i, s in enumerate(passed_sorted)
        ],
    }
    report_path = run_dir / "final_report.json"
    report_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  最终报告: {report_path}")

    print(f"\n{'=' * 70}")
    print(f"  ✅ 管线执行完成")
    print(f"  Run: {run_id}")
    if passed_sorted:
        print(f"  可投放图片: {len(passed_sorted)} 张")
        print(f"  最佳图片: {passed_sorted[0].file_path}")
        print(f"  综合分: {passed_sorted[0].overall:.1f}")
    print(f"{'=' * 70}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
