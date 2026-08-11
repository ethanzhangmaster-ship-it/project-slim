"""P04 Winner DNA Golden Sample 单素材验证脚本 V6 (with UA Renderer)

验证目标：
  - 基于 Winner Ranking V2 选择最值得复制的商业 Winner
  - 通过 Creative Layout Planner 生成精确的 UA 广告结构蓝图
  - 通过 Creative Prompt Director 将 DNA + Layout 转换为 Performance Prompt
  - 通过 UA Native Creative Renderer V1 或 Composition Engine 生成买量素材
  - 只生成 1 张，验证出图质量能否达到 ≥8.0

用法:
  # UA Renderer V1 (default) — AI素材 + 广告渲染引擎
  python scripts/run_p04_golden_sample_verify.py --winner-type balanced --generation-mode composition --renderer-mode ua_renderer_v1

  # Composition Engine V1.1 — 分组件生成 + 合成
  python scripts/run_p04_golden_sample_verify.py --winner-type balanced --generation-mode composition --renderer-mode composition_v1.1

  # Prompt-only mode — 单次生成
  python scripts/run_p04_golden_sample_verify.py --winner-type balanced --generation-mode prompt_only

  # Dry run
  python scripts/run_p04_golden_sample_verify.py --winner-type scale --dry-run
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


def load_winner_ranking_v2() -> dict:
    """Load Winner Ranking V2 result."""
    path = ROOT / "output" / "creative_analysis" / "winner_ranking_v2.json"
    if not path.exists():
        print(f"[WARN] Winner Ranking V2 not found: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def select_winner_by_type(winners: list[dict], ranking: dict, winner_type: str) -> dict:
    """Select winner based on ranking type.

    winner_type: balanced | revenue | scale | hook | iap
    """
    type_key = f"{winner_type}_winner"
    if winner_type == "iap":
        type_key = "iap_intent_winner"

    ranked_winner = ranking.get(type_key, {})
    creative_id = ranked_winner.get("creative_id", "")

    if creative_id:
        for w in winners:
            if w["creative_id"] == creative_id:
                return w

    # Fallback: if ranking not found, fall back to old iap_score sort
    print(f"  [WARN] Ranking '{winner_type}' not found, falling back to iap_score sort")
    winners.sort(key=lambda w: w["iap_score"], reverse=True)
    return winners[0]


def main():
    parser = argparse.ArgumentParser(description="P04 Winner DNA Golden Sample 单素材验证 V5 (Composition Engine)")
    parser.add_argument("--winner-type", type=str, default="balanced",
                        choices=["balanced", "revenue", "scale", "hook", "iap"],
                        help="Winner 选择类型 (default: balanced)")
    parser.add_argument("--creative-mode", type=str, default="gameplay_transformation",
                        choices=["gameplay_transformation", "character_focus", "poster"],
                        help="Creative 模式 (default: gameplay_transformation)")
    parser.add_argument("--layout-mode", type=str, default="before_after_merge",
                        choices=["before_after_merge", "vertical_progression", "character_driven_merge", "split_screen_compare"],
                        help="Layout 模式 (default: before_after_merge)")
    parser.add_argument("--generation-mode", type=str, default="composition",
                        choices=["composition", "prompt_only"],
                        help="生成模式: composition=分组件合成, prompt_only=单次生成 (default: composition)")
    parser.add_argument("--composition-version", type=str, default="v1.1",
                        choices=["v1.0", "v1.1"],
                        help="Composition Engine 版本 (default: v1.1)")
    parser.add_argument("--renderer-mode", type=str, default="hybrid_renderer_v1.3.2",
                        choices=["composition_v1", "composition_v1.1", "ua_renderer_v1", "hybrid_renderer_v1", "hybrid_renderer_v1.1", "hybrid_renderer_v1.3.2"],
                        help="渲染器模式: composition_v1 | composition_v1.1 | ua_renderer_v1 | hybrid_renderer_v1 | hybrid_renderer_v1.1 | hybrid_renderer_v1.3.2 (default: hybrid_renderer_v1.3.2)")
    parser.add_argument("--threshold", type=float, default=6.0, help="评分通过阈值")
    parser.add_argument("--dry-run", action="store_true", help="只打印 prompt，不生成图片")
    args = parser.parse_args()

    project = "P04 Witch"
    run_id = datetime.now().strftime("p04_golden_verify_%Y%m%d_%H%M%S")
    run_dir = ROOT / "output" / "creative_intelligence" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  P04 Winner DNA Golden Sample 验证 V6 (UA Renderer)")
    print(f"  Run ID: {run_id}")
    print(f"  Winner Type        : {args.winner_type}")
    print(f"  Creative Mode      : {args.creative_mode}")
    print(f"  Layout Mode        : {args.layout_mode}")
    print(f"  Generation Mode    : {args.generation_mode}")
    print(f"  Renderer Mode      : {args.renderer_mode}")
    print(f"  策略: Layout → Director → {args.renderer_mode.upper()} | 阈值: {args.threshold}")
    print("=" * 70)

    # Phase 1: Load Winner DNA & Ranking V2
    print(f"\n{'─' * 70}")
    print("  Phase 1: 加载 Winner DNA + Ranking V2")
    print(f"{'─' * 70}")

    winners = load_winner_dna()
    if not winners:
        print("  ❌ 没有赢家DNA数据，终止")
        return 1

    ranking = load_winner_ranking_v2()
    if not ranking:
        print("  [WARN] Winner Ranking V2 未找到，将回退到 iap_score 排序")

    top_winner = select_winner_by_type(winners, ranking, args.winner_type)
    dna = top_winner["visual_dna"]

    # Get ranking info for display
    ranked_info = {}
    if ranking:
        type_key = f"{args.winner_type}_winner"
        if args.winner_type == "iap":
            type_key = "iap_intent_winner"
        ranked_info = ranking.get(type_key, {})

    print(f"\n  🏆 选中 Golden Sample Winner ({args.winner_type})")
    print(f"     Creative ID : {top_winner['creative_id']}")
    print(f"     Winner Score: {ranked_info.get('score', 'N/A (fallback)')}")
    print(f"     IAP Score   : {top_winner['iap_score']:.4f}")
    print(f"     Spend       : ${top_winner['spend']:.2f}")
    print(f"     Installs    : {top_winner['installs']}")
    print(f"     CTR         : {top_winner['ctr']:.4f}")
    print(f"     ROAS D7     : {top_winner['roas_d7']:.2f}")
    print(f"\n  📋 视觉 DNA 摘要")
    print(f"     Subject     : {dna['subject']}")
    print(f"     Composition : {dna['composition'][:80]}...")
    print(f"     Palette     : {dna['palette']}")
    print(f"     Overlay     : \"{dna['overlay_text']}\"")
    print(f"     Mood        : {dna['mood']}")
    print(f"     Hook        : {dna['hook_type']}")
    print(f"     Features    : {', '.join(str(s) for s in dna['standout_features'][:3])}")
    print(f"\n  🖼️  参考图 URL : {top_winner['cdn_url'][:80]}...")

    # Phase 2: Layout Planner — Winner DNA → Layout Blueprint
    print(f"\n{'─' * 70}")
    print("  Phase 2: Creative Layout Planner")
    print(f"         Winner DNA → UA Creative Layout Blueprint")
    print(f"{'─' * 70}")

    from market_ops.creative_intelligence.layout_planner import CreativeLayoutPlanner

    layout_planner = CreativeLayoutPlanner(project=project)
    layout_blueprint = layout_planner.plan(
        visual_dna=dna,
        product_type="merge_iap",
        creative_mode=args.creative_mode,
        layout_mode=args.layout_mode,
    )

    # Save Layout outputs
    layout_dir = ROOT / "output" / "creative_analysis" / "layout_planner"
    layout_outputs = layout_planner.save_blueprint(layout_blueprint, layout_dir)

    print(f"\n  📁 Layout Planner 输出已保存:")
    for name, path in layout_outputs.items():
        print(f"     • {name}: {path}")

    print(f"\n  📐 Layout Type: {layout_blueprint.layout_type}")
    print(f"\n  📐 Layout Visualization:")
    for line in layout_blueprint.layout_description.splitlines()[:12]:
        print(f"     {line}")
    print(f"\n  🎯 Regions ({len(layout_blueprint.regions)}):")
    for reg in layout_blueprint.regions:
        print(f"     • [{reg.position}] {reg.element} ({reg.size_hint})")
    print(f"\n  ✅ Must-Show ({len(layout_blueprint.must_show_elements)} 项):")
    for item in layout_blueprint.must_show_elements[:5]:
        print(f"     • {item}")

    # Phase 3: Prompt Director — DNA + Layout → Generation Prompt
    print(f"\n{'─' * 70}")
    print("  Phase 3: Creative Prompt Director V2")
    print(f"         DNA + Layout Blueprint → UA Performance Creative Strategy")
    print(f"{'─' * 70}")

    from market_ops.creative_intelligence.prompt_director import CreativePromptDirector

    director = CreativePromptDirector(project=project)
    strategy = director.direct(
        visual_dna=dna,
        winner_type=args.winner_type,
        creative_mode=args.creative_mode,
        layout_blueprint=layout_blueprint,
    )

    # Save Director outputs
    director_dir = ROOT / "output" / "creative_analysis" / "prompt_director"
    director_outputs = director.save_strategy(strategy, director_dir)

    print(f"\n  📁 Director 输出已保存:")
    for name, path in director_outputs.items():
        print(f"     • {name}: {path}")

    print(f"\n  🎯 Creative Type  : {strategy.creative_type}")
    print(f"  🎣 Hook Strategy  : {strategy.hook_strategy[:100]}...")
    print(f"  🎮 Gameplay Moment: {strategy.gameplay_moment[:100]}...")
    print(f"\n  ✅ Must-Have ({len(strategy.must_have_elements)} 项):")
    for item in strategy.must_have_elements[:5]:
        print(f"     • {item}")
    print(f"\n  ❌ Avoid ({len(strategy.avoid_elements)} 项):")
    for item in strategy.avoid_elements[:3]:
        print(f"     • {item}")

    prompt_text = strategy.generation_prompt
    negative_text = strategy.negative_prompt

    prompt_dict = {
        "prompt_id": "golden_001",
        "prompt_text": prompt_text,
        "hook_type": dna.get("hook_type", "collection"),
        "project": project,
        "negative_prompt": negative_text,
        "reference_image_url": top_winner["cdn_url"],
        "variation_axis": f"golden_sample:{args.winner_type}:{args.creative_mode}:{args.layout_mode}",
    }

    print(f"\n  Prompt 长度: {len(prompt_text)} 字符")
    print(f"  Negative 长度: {len(negative_text)} 字符")
    print(f"  参考图     : {top_winner['cdn_url'][:60]}...")
    print(f"\n  --- Generation Prompt 预览 (前 800 字符) ---")
    print(f"  {prompt_text[:800]}...")
    print(f"  --- End Preview ---")

    # Save prompt for audit
    plan_path = run_dir / "golden_prompt.json"
    plan_path.write_text(json.dumps(prompt_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Prompt 已保存: {plan_path}")

    if args.dry_run:
        print(f"\n{'=' * 70}")
        print("  [DRY RUN] 结束")
        print(f"{'=' * 70}")
        return 0

    # Phase 4: Generation
    img = None
    composition_result = None

    if args.generation_mode == "composition":
        if args.renderer_mode == "hybrid_renderer_v1.3.2":
            # ── Hybrid UA Creative Renderer V1.3.2 (UA Structure) ──
            print(f"\n{'─' * 70}")
            print("  Phase 4: Hybrid UA Creative Renderer V1.3.2")
            print(f"         UA结构控制 + 3候选Gameplay + Quality Gate + 严格UA布局")
            print(f"{'─' * 70}")

            from market_ops.creative_intelligence.hybrid_renderer.hybrid_creative_renderer_v132 import HybridCreativeRendererV132

            engine = HybridCreativeRendererV132(project=project, output_dir=run_dir / "hybrid_v132")
            composition_result = engine.render(
                strategy=strategy,
                layout_blueprint=layout_blueprint,
                winner_dna=dna,
                winner_cdn_url=top_winner["cdn_url"],
            )
        elif args.renderer_mode == "hybrid_renderer_v1.1":
            # ── Hybrid UA Creative Renderer V1.3.1 (Optimized) ──
            print(f"\n{'─' * 70}")
            print("  Phase 4: Hybrid UA Creative Renderer V1.3.1")
            print(f"         AI生成素材 + 布局约束 + 智能裁剪 + UA广告渲染")
            print(f"{'─' * 70}")

            from market_ops.creative_intelligence.hybrid_renderer.hybrid_creative_renderer import HybridCreativeRenderer

            engine = HybridCreativeRenderer(project=project, output_dir=run_dir / "hybrid_v131")
            composition_result = engine.render(
                strategy=strategy,
                layout_blueprint=layout_blueprint,
                winner_dna=dna,
                winner_cdn_url=top_winner["cdn_url"],
                hook_type=dna.get("hook_type", "collection"),
                custom_hook_text=dna.get("overlay_text", ""),
            )
        elif args.renderer_mode == "hybrid_renderer_v1":
            # ── Hybrid UA Creative Renderer V1 ──
            print(f"\n{'─' * 70}")
            print("  Phase 4: Hybrid UA Creative Renderer V1")
            print(f"         AI生成真实手游素材 + 广告渲染引擎")
            print(f"{'─' * 70}")

            from market_ops.creative_intelligence.hybrid_renderer.hybrid_creative_renderer import HybridCreativeRenderer

            engine = HybridCreativeRenderer(project=project, output_dir=run_dir / "hybrid_renderer")
            composition_result = engine.render(
                strategy=strategy,
                layout_blueprint=layout_blueprint,
                winner_dna=dna,
                winner_cdn_url=top_winner["cdn_url"],
                hook_type=dna.get("hook_type", "collection"),
                custom_hook_text=dna.get("overlay_text", ""),
            )
        elif args.renderer_mode == "ua_renderer_v1":
            # ── UA Native Creative Renderer V1 ──
            print(f"\n{'─' * 70}")
            print("  Phase 4: UA Native Creative Renderer V1")
            print(f"         AI素材 + 广告渲染引擎")
            print(f"{'─' * 70}")

            from market_ops.creative_intelligence.ua_renderer.creative_renderer import UACreativeRenderer

            engine = UACreativeRenderer(project=project, output_dir=run_dir / "ua_renderer")
            composition_result = engine.render(
                strategy=strategy,
                layout_blueprint=layout_blueprint,
                winner_dna=dna,
                winner_cdn_url=top_winner["cdn_url"],
                hook_type=dna.get("hook_type", "collection"),
                custom_hook_text=dna.get("overlay_text", ""),
            )
        else:
            # ── Composition Engine (V1.0 / V1.1) ──
            print(f"\n{'─' * 70}")
            print(f"  Phase 4: Composition Engine (分组件生成 + 合成)")
            print(f"{'─' * 70}")

            from market_ops.creative_intelligence.composition_engine import CreativeCompositionEngine

            engine = CreativeCompositionEngine(project=project, output_dir=run_dir / "composition")
            composition_result = engine.compose(
                strategy=strategy,
                layout_blueprint=layout_blueprint,
                winner_dna=dna,
                winner_cdn_url=top_winner["cdn_url"],
                hook_type=dna.get("hook_type", "collection"),
                custom_hook_text=dna.get("overlay_text", ""),
            )

        if not composition_result.final_image:
            print("  ❌ Composition Engine 失败，无最终图片")
            return 1

        # Create a synthetic GeneratedImage-like object for scoring
        from market_ops.creative_image_gen import GeneratedImage
        img = GeneratedImage(
            image_id=f"composition_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            prompt_id="golden_001",
            project=project,
            hook_type=dna.get("hook_type", "collection"),
            file_path=composition_result.final_image,
            prompt_used=strategy.generation_prompt if hasattr(strategy, "generation_prompt") else "",
            negative_prompt=strategy.negative_prompt if hasattr(strategy, "negative_prompt") else "",
            model="composition_engine",
            generation_ms=0,
            width=1024,
            height=1024,
            format="png",
            ready_for_review=True,
        )
        print(f"\n  ✓ Final creative: {composition_result.final_image}")

    else:
        # Prompt-only: single img2img generation
        print(f"\n{'─' * 70}")
        print("  Phase 4: 单张 img2img 生成 (Prompt Only)")
        print(f"{'─' * 70}")

        from market_ops.creative_image_gen import CreativeImageGenerator

        gen_dir = run_dir / "generated_images"
        gen = CreativeImageGenerator(output_dir=gen_dir)

        print(f"  后端 : {gen.active_backend}")
        print(f"  Lovart: {gen.is_lovart}")
        print(f"  输出 : {gen_dir}")

        gen_batch = gen.generate([prompt_dict], project=project, size="1024x1024")

        if not gen_batch.images:
            print("  ❌ 图片生成失败，无返回")
            return 1

        img = gen_batch.images[0]
        status = "✓" if img.ready_for_review else "✗"
        print(f"\n  {status} [{img.image_id}] model={img.model} ready={img.ready_for_review}")
        print(f"      路径: {img.file_path}")

        if not img.ready_for_review:
            print("  ❌ 图片未就绪，终止")
            return 1

    # Phase 5: Detailed Quality Scoring
    print(f"\n{'─' * 70}")
    print(f"  Phase 5: 详细质量评分 ({args.generation_mode.upper()})")
    print(f"{'─' * 70}")

    from market_ops.creative_image_scorer import CreativeImageScorer, print_score_report, save_score_report

    scorer = CreativeImageScorer(threshold=args.threshold)
    print(f"  后端   : {scorer.active_backend}")
    print(f"  阈值   : {args.threshold}")

    image_dict = {
        "file_path": img.file_path,
        "prompt_used": img.prompt_used,
        "model": img.model,
        "image_id": img.image_id,
        "hook_type": img.hook_type,
    }

    score_batch = scorer.score_batch([image_dict], project=project)
    print_score_report(score_batch)

    score_path = run_dir / "scores.json"
    save_score_report(score_batch, score_path)

    # Phase 6: Golden Sample Verdict
    print(f"\n{'=' * 70}")
    print("  Phase 6: Golden Sample 验证结论")
    print(f"{'=' * 70}")

    if score_batch.scores:
        s = score_batch.scores[0]
        print(f"\n  🎯 综合评分 : {s.overall:.1f} / 10")
        print(f"     视觉质量 : {s.visual_quality:.1f}")
        print(f"     品牌对齐 : {s.brand_alignment:.1f}")
        print(f"     Hook清晰 : {s.hook_clarity:.1f}")
        print(f"     广告适合 : {s.ad_suitability:.1f}")
        print(f"     原创性   : {s.originality:.1f}")
        print(f"\n  ✅ 通过阈值 : {s.passed} (阈值={args.threshold})")

        if s.strengths:
            print(f"\n  💪 优点")
            for st in s.strengths:
                print(f"     • {st}")
        if s.improvements:
            print(f"\n  🔧 改进建议")
            for imp in s.improvements:
                print(f"     • {imp}")

        # Verdict
        print(f"\n{'─' * 50}")
        if s.passed and s.overall >= 8.0:
            verdict = "🟢 EXCELLENT — 高度接近真实爆款质量，建议直接投放测试"
        elif s.passed:
            verdict = "🟡 GOOD — 达到投放标准，可测试，但仍有优化空间"
        else:
            verdict = "🔴 NEEDS WORK — 未达阈值，需检查 Winner DNA 继承或生成参数"
        print(f"  {verdict}")
        print(f"{'─' * 50}")

        # Version comparison
        print(f"\n  📊 版本对比")
        print(f"     V1 (iap_score)             : 6.0")
        print(f"     V2 (balanced)              : 7.0")
        print(f"     V3 (Prompt Director)       : 6.5")
        print(f"     V4 (Layout + Director)     : 7.0")
        print(f"     V5 (Composition Engine)    : 7.3")
        print(f"     V6 (UA Renderer V1)        : 6.7")
        print(f"     V7 (Hybrid Renderer V1)    : 6.9")
        print(f"     V8 (Hybrid V1.3.1)         : 6.0")
        print(f"     V9 (Hybrid V1.3.2)         : {s.overall:.1f}")
        print(f"\n  📊 与真实赢家对比")
        print(f"     真实赢家 Creative ID : {top_winner['creative_id']}")
        print(f"     真实赢家 IAP Score   : {top_winner['iap_score']:.4f}")
        print(f"     真实赢家 CTR         : {top_winner['ctr']:.4f}")
        print(f"     真实赢家 Spend       : ${top_winner['spend']:.2f}")
        print(f"\n  若 AI Score ≥ 8.0 且品牌对齐 ≥ 7.5，")
        print(f"  则该素材有较大概率继承赢家的付费转化能力。")
    else:
        print("  ⚠️  评分失败，无分数返回")

    # Save final report
    final_report = {
        "run_id": run_id,
        "project": project,
        "strategy": f"golden_sample_{args.renderer_mode}",
        "winner_type": args.winner_type,
        "creative_mode": args.creative_mode,
        "layout_mode": args.layout_mode,
        "generation_mode": args.generation_mode,
        "renderer_mode": args.renderer_mode,
        "threshold": args.threshold,
        "generated_at": datetime.now().isoformat(),
        "winner_anchor": {
            "creative_id": top_winner["creative_id"],
            "cdn_url": top_winner["cdn_url"],
            "iap_score": top_winner["iap_score"],
            "spend": top_winner["spend"],
            "ctr": top_winner["ctr"],
            "roas_d7": top_winner["roas_d7"],
        },
        "visual_dna_inherited": dna,
        "layout_blueprint": {
            "layout_type": layout_blueprint.layout_type,
            "regions": [{"position": r.position, "element": r.element, "size_hint": r.size_hint} for r in layout_blueprint.regions],
            "must_show_elements": layout_blueprint.must_show_elements,
        },
        "creative_strategy": {
            "creative_type": strategy.creative_type,
            "hook_strategy": strategy.hook_strategy,
            "gameplay_moment": strategy.gameplay_moment,
            "must_have_elements": strategy.must_have_elements,
            "avoid_elements": strategy.avoid_elements,
        },
        "generation": {
            "image_id": img.image_id,
            "file_path": img.file_path,
            "model": img.model,
            "ready": img.ready_for_review,
        },
        "score": {
            "overall": score_batch.scores[0].overall if score_batch.scores else 0,
            "visual_quality": score_batch.scores[0].visual_quality if score_batch.scores else 0,
            "brand_alignment": score_batch.scores[0].brand_alignment if score_batch.scores else 0,
            "hook_clarity": score_batch.scores[0].hook_clarity if score_batch.scores else 0,
            "ad_suitability": score_batch.scores[0].ad_suitability if score_batch.scores else 0,
            "originality": score_batch.scores[0].originality if score_batch.scores else 0,
            "passed": score_batch.scores[0].passed if score_batch.scores else False,
            "strengths": score_batch.scores[0].strengths if score_batch.scores else [],
            "improvements": score_batch.scores[0].improvements if score_batch.scores else [],
        } if score_batch.scores else {},
    }
    report_path = run_dir / "golden_sample_report.json"
    report_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  完整报告: {report_path}")
    print(f"  生成图片: {img.file_path}")
    print(f"\n{'=' * 70}")
    print(f"  ✅ Golden Sample V5 验证完成")
    print(f"{'=' * 70}")

    # Final status line
    if score_batch.scores:
        s = score_batch.scores[0]
        print(f"\n{'=' * 70}")
        print(f"  P04 Creative Composition Engine V1.3.2 Complete")
        print(f"{'=' * 70}")
        print(f"  Module       : hybrid_renderer_v132 (11-step UA pipeline + 5-candidate + Quality Gate)")
        print(f"  Winner       : {top_winner['creative_id']}")
        print(f"  Layout Mode  : {args.layout_mode}")
        print(f"  Creative Mode: {args.creative_mode}")
        print(f"  Renderer     : {args.renderer_mode}")
        print(f"  Generated    : {img.image_id}")
        print(f"  Score        : {s.overall:.1f}")
        print(f"  Hook Score   : {s.hook_clarity:.1f}")
        print(f"  Ad Fit Score : {s.ad_suitability:.1f}")
        print(f"  Status       : {'PASS' if s.passed else 'FAIL'}")
        print(f"{'=' * 70}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
