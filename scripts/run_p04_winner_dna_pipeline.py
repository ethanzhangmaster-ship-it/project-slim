"""P04 Winner DNA 管线: 真实赢家视觉DNA → Fission变异 → Lovart img2img → 评分

与之前 CreativePlanner(M6) 的本质区别:
  - 不是用 boolean feature map 填空模板
  - 而是用 CreativePromptForge.forge_from_winner_dna()
  - 每一张 prompt 锚定一张真实赢家图片做 img2img 参考
  - 保持赢家的核心视觉DNA, 只变异副轴(hook文案/构图/场景/生物/光影)

用法:
  python scripts/run_p04_winner_dna_pipeline.py
  python scripts/run_p04_winner_dna_pipeline.py --count 6 --threshold 6.0
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


def load_winner_dna() -> list[dict]:
    dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "winners_dna.json"
    if not dna_path.exists():
        print(f"[ERROR] Winner DNA 文件不存在: {dna_path}")
        return []

    raw = json.loads(dna_path.read_text(encoding="utf-8"))
    items = []
    for entry in raw:
        cdn_url = entry.get("_cdn_url", "").strip()
        if not cdn_url:
            continue
        items.append({
            "creative_id": entry.get("creative_id", ""),
            "cdn_url": cdn_url,
            "visual_dna": {
                "subject": entry.get("subject", ""),
                "composition": entry.get("composition", ""),
                "palette": entry.get("palette", ""),
                "lighting": entry.get("lighting", ""),
                "overlay_text": entry.get("overlay_text", ""),
                "character_pose": entry.get("character_pose", ""),
                "mood": entry.get("mood", ""),
                "hook_type": entry.get("hook_type", "collection"),
                "standout_features": entry.get("standout_features", []),
                "overall_summary": entry.get("overall_summary", ""),
            },
            "iap_score": entry.get("iap_score", 0),
            "spend": entry.get("spend", 0),
            "installs": entry.get("installs", 0),
            "ctr": entry.get("ctr", 0),
            "roas_d7": entry.get("roas_d7", 0),
        })
    return items


def build_winning_prompt_from_dna(dna: dict, axis_name: str, variation: str) -> str:
    """直接从赢家DNA构建prompt — 比forge_from_winner_dna更直接可控"""

    subject = dna.get("subject", "a witch character in a magical setting")
    palette = dna.get("palette", "deep purple, violet, gold accents")
    mood = dna.get("mood", "enchanting, mysterious, magical")
    composition = dna.get("composition", "centered hero shot")
    overlay_text = dna.get("overlay_text", "Merge & Watch the Magic")
    character_pose = dna.get("character_pose", "witch casting spell with hands extended")
    standout = dna.get("standout_features", [])
    lighting = dna.get("lighting", "magical glowing effects, dark moody background")

    style_brief = (
        f"Art style: high-quality fantasy game art, 3D cartoon rendering. "
        f"Color palette: {palette}. "
        f"Lighting: {lighting}. "
        f"Mood: {mood}. "
        f"Brand: P04 Witch merge puzzle game ad. "
        f"The winning ad used overlay text like: \"{overlay_text}\". "
    )

    styled_features = "; ".join(str(s) for s in standout[:3]) if standout else ""

    prompt = (
        f"Create a Facebook mobile game ad for P04 Witch, a dark fantasy merge puzzle game. "
        f"1:1 square aspect ratio, 1080x1080. Professional Facebook ad quality.\n\n"
        f"STYLE INHERITED FROM WINNER:\n"
        f"{style_brief}\n"
        f"Winner subject: {subject}. "
        f"Character pose reference: {character_pose}. "
        f"Notable features: {styled_features}.\n\n"
        f"CREATIVE DIRECTION FOR THIS VARIATION:\n"
        f"{variation}\n\n"
        f"REQUIREMENTS:\n"
        f"- MUST include a witch character as the focal point\n"
        f"- MUST show merge/evolution gameplay elements (merge board, upgrade arrows, before→after progression)\n"
        f"- Overlay text in bold gothic fantasy typography (like \"Build Your Dark Empire!\" or \"Merge & Watch the Magic\")\n"
        f"- Rich purple + gold color palette with magical glow effects\n"
        f"- Enchanting, aspirational mood — not scary, not too cute, not too dark\n"
        f"- 3D cartoon art style, polished AAA mobile game ad quality\n"
        f"- No watermarks, no realistic photos, no unrelated UI"
    )

    return prompt


def main():
    parser = argparse.ArgumentParser(description="P04 Winner DNA 管线: 真实赢家DNA → Fission → img2img")
    parser.add_argument("--count", type=int, default=6, help="生成图片数量")
    parser.add_argument("--threshold", type=float, default=6.0, help="评分通过阈值")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = "P04 Witch"
    run_id = datetime.now().strftime("p04_winner_dna_%Y%m%d_%H%M%S")
    run_dir = ROOT / "output" / "creative_intelligence" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"  P04 Winner DNA 管线 (img2img)")
    print(f"  Run ID: {run_id}")
    print(f"  策略: Winner DNA Fission | 数量: {args.count} | 阈值: {args.threshold}")
    print("=" * 70)

    # Phase 1: Load Winner DNA
    print(f"\n{'─' * 70}")
    print("  Phase 1: 加载真实赢家视觉DNA")
    print(f"{'─' * 70}")

    winners = load_winner_dna()
    if not winners:
        print("  ❌ 没有赢家DNA数据, 终止")
        return 1

    # Sort by iap_score descending, pick top ones
    winners.sort(key=lambda w: w["iap_score"], reverse=True)
    top_winners = winners[:min(4, len(winners))]  # Use top 4 as anchors

    print(f"  加载 {len(winners)} 个赢家, 选择 top {len(top_winners)} 作为锚点:")
    for i, w in enumerate(top_winners):
        dna = w["visual_dna"]
        print(f"\n  🏆 Anchor #{i+1} (IAP={w['iap_score']:.3f} | spend=${w['spend']:.0f} | installs={w['installs']})")
        print(f"     subject: {dna['subject'][:80]}...")
        print(f"     palette: {dna['palette'][:60]}...")
        print(f"     overlay: \"{dna['overlay_text'][:60]}\"")
        print(f"     mood: {dna['mood']}")
        print(f"     hook: {dna['hook_type']}")

    # Phase 2: Generate Fission Prompts
    print(f"\n{'─' * 70}")
    print("  Phase 2: Winner DNA Fission (Prompt生成)")
    print(f"{'─' * 70}")

    # Use CreativePromptForge for proper fission
    from market_ops.creative_prompt_forge import CreativePromptForge

    forge = CreativePromptForge(game=project)
    batch = forge.forge_from_winner_dna(top_winners, max_prompts=args.count)

    print(f"\n  生成 {len(batch.prompts)} 个 Fission Prompt:")
    prompts_for_gen = []
    for i, p in enumerate(batch.prompts, 1):
        has_ref = "✓ ref" if p.reference_image_url else "✗ no ref"
        print(f"\n  [{i}] {p.prompt_id} | {p.variation_axis}")
        print(f"      Hook: {p.hook_type} | Emotion: {p.emotion} | {has_ref}")
        print(f"      Prompt: {p.prompt_text[:150]}...")
        prompts_for_gen.append({
            "prompt_id": p.prompt_id,
            "prompt_text": p.prompt_text,
            "hook_type": p.hook_type,
            "project": p.project,
            "negative_prompt": p.negative_prompt,
            "reference_image_url": p.reference_image_url,
            "variation_axis": p.variation_axis,
        })

    plan_path = run_dir / "plan.json"
    plan_path.write_text(json.dumps([
        {k: v for k, v in p.items() if k != "prompt_text"} | {"prompt_text": p["prompt_text"]}
        for p in prompts_for_gen
    ], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Plan: {plan_path}")

    if args.dry_run:
        print(f"\n{'=' * 70}")
        print("  [DRY RUN] 结束")
        print(f"{'=' * 70}")
        return 0

    # Phase 3: img2img Generation via Lovart
    print(f"\n{'─' * 70}")
    print("  Phase 3: img2img 生成 (Lovart + 赢家参考图)")
    print(f"{'─' * 70}")

    from market_ops.creative_image_gen import CreativeImageGenerator

    gen_dir = run_dir / "generated_images"
    gen = CreativeImageGenerator(output_dir=gen_dir)

    print(f"  后端: {gen.active_backend} | Lovart: {gen.is_lovart}")
    print(f"  输出: {gen_dir}")

    gen_batch = gen.generate(prompts_for_gen, project=project)

    print(f"\n  生成结果: {gen_batch.total_images} 张")
    success_count = sum(1 for img in gen_batch.images if img.ready_for_review)
    print(f"  就绪: {success_count} | 失败: {gen_batch.total_images - success_count}")

    for img in gen_batch.images:
        status = "✓" if img.ready_for_review else "✗"
        # Find the corresponding prompt to show variation_axis
        axis = ""
        for pf in prompts_for_gen:
            if pf["prompt_id"] == img.prompt_id:
                axis = pf.get("variation_axis", "")
                break
        print(f"  {status} [{img.image_id}] hook={img.hook_type} axis={axis[:60]}")

    if success_count == 0:
        print("\n  ❌ 无图片生成成功")
        return 1

    # Phase 4: Quality Scoring
    print(f"\n{'─' * 70}")
    print("  Phase 4: 质量评分")
    print(f"{'─' * 70}")

    from market_ops.creative_image_scorer import CreativeImageScorer, print_score_report, save_score_report

    scorer = CreativeImageScorer(threshold=args.threshold)
    print(f"  后端: {scorer.active_backend} | 阈值: {args.threshold}")

    ready = [img for img in gen_batch.images if img.ready_for_review]
    image_dicts = [
        {"file_path": img.file_path, "prompt_used": img.prompt_used,
         "model": img.model, "image_id": img.image_id, "hook_type": img.hook_type}
        for img in ready
    ]

    score_batch = scorer.score_batch(image_dicts, project=project)
    print_score_report(score_batch)

    score_path = run_dir / "scores.json"
    save_score_report(score_batch, score_path)

    # Phase 5: Results
    print(f"\n{'=' * 70}")
    print("  Phase 5: 最终可投放结果")
    print(f"{'=' * 70}")

    passed = sorted([s for s in score_batch.scores if s.passed], key=lambda s: s.overall, reverse=True)
    rejected = [s for s in score_batch.scores if not s.passed]

    print(f"\n  通过: {len(passed)}/{score_batch.total_scored} (阈值={args.threshold})")
    print(f"  淘汰: {len(rejected)}")

    if passed:
        print(f"\n  {'─' * 50}")
        print(f"  🏆 可投放图片")
        print(f"  {'─' * 50}")
        for rank, s in enumerate(passed, 1):
            print(f"\n  #{rank} [{s.image_id}] 综合分={s.overall:.1f}")
            print(f"      VQ={s.visual_quality:.1f} BA={s.brand_alignment:.1f} HC={s.hook_clarity:.1f} AS={s.ad_suitability:.1f} OR={s.originality:.1f}")
            print(f"      文件: {s.file_path}")
            if s.strengths:
                print(f"      优点: {', '.join(s.strengths[:3])}")
    else:
        print(f"\n  ⚠️  无图片通过阈值")
        if rejected:
            best = max(rejected, key=lambda s: s.overall)
            print(f"  最高分: {best.image_id} ({best.overall:.1f})")
            print(f"  原因: {best.reject_reason}")

    # Save final report
    final_report = {
        "run_id": run_id, "project": project, "strategy": "winner_dna_fission",
        "threshold": args.threshold, "generated_at": datetime.now().isoformat(),
        "summary": {
            "winner_anchors": len(top_winners),
            "prompts_generated": len(batch.prompts),
            "images_generated": gen_batch.total_images,
            "images_ready": success_count,
            "images_scored": score_batch.total_scored,
            "images_passed": len(passed),
            "images_rejected": len(rejected),
            "avg_score": score_batch.avg_overall,
        },
        "passed_images": [{
            "rank": i + 1, "image_id": s.image_id, "file_path": s.file_path,
            "overall": s.overall, "visual_quality": s.visual_quality,
            "brand_alignment": s.brand_alignment, "hook_clarity": s.hook_clarity,
            "ad_suitability": s.ad_suitability, "originality": s.originality,
            "strengths": s.strengths,
        } for i, s in enumerate(passed)],
    }
    report_path = run_dir / "final_report.json"
    report_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  最终报告: {report_path}")
    print(f"\n{'=' * 70}")
    print(f"  ✅ 管线完成")
    print(f"  可投放: {len(passed)} 张")
    if passed:
        print(f"  最佳: {passed[0].file_path}")
        print(f"  综合分: {passed[0].overall:.1f}")
    print(f"{'=' * 70}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
