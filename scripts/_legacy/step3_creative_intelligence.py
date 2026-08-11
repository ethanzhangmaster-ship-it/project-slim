#!/usr/bin/env python3
"""Step 3: Creative Intelligence Analysis + Lovart Image Generation.

1. Load Top P04 Witch Winners from real DB
2. Run Phase 4.1 Creative Intelligence Analysis
3. Extract Creative DNA
4. Generate images via Lovart AI
5. Save results
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb

from market_ops.creative_intelligence.analysis_engine import AnalysisEngine, ANALYSIS_WEIGHTS
from market_ops.creative_intelligence.models import (
    HookType, VisualSubject, ColorStyle,
    Composition, ColorProfile, EmotionProfile, QualityProfile,
    ProgressionProfile, EconomyProfile, RetentionSignal,
    PurchaseTrigger,
    VisualFeatures, HookFeatures, GameplayFeatures, MonetizationFeatures,
    CreativeAnalysis,
)
from market_ops.creative_intelligence.creative_dna_extractor import CreativeDNAExtractor
from market_ops.creative_intelligence.validator import Validator
from market_ops.creative_repository import (
    CreativeEntity, CreativeIdentity, CreativePerformance,
    AcquisitionData, RevenueData, CreativeAnalysis as EntityAnalysis,
    CreativeType, CreativeAsset, CreativeSources,
)


# ── Load real winners ─────────────────────────────────────────────────
def load_top_winners(db_path: Path, limit: int = 10) -> list[dict]:
    conn = duckdb.connect(str(db_path), read_only=True)
    rows = conn.execute("""
        SELECT cp.creative_id, cp.project, SUM(cp.spend) as spend, SUM(cp.install) as installs,
               SUM(cp.impression) as imp, SUM(cp.click) as clicks,
               CASE WHEN SUM(cp.spend) > 0 THEN SUM(cp.roas_d7 * cp.spend)/SUM(cp.spend) ELSE 0 END as roas,
               cf.hook_type, cf.warm_cool, cf.center_layout, cf.left_right_layout,
               cf.subject_type, cf.primary_color, cf.secondary_color,
               cf.saturation, cf.brightness, cf.emotion_surprise, cf.emotion_reward,
               cf.game_has_merge, cf.game_has_reward, cf.game_has_progress, cf.game_has_collection
        FROM creative_performance cp
        LEFT JOIN creative_features cf ON cp.creative_id = cf.creative_id
        WHERE cp.project = 'P04 Witch'
        GROUP BY cp.creative_id, cp.project, cf.hook_type, cf.warm_cool, cf.center_layout,
                 cf.left_right_layout, cf.subject_type, cf.primary_color, cf.secondary_color,
                 cf.saturation, cf.brightness, cf.emotion_surprise, cf.emotion_reward,
                 cf.game_has_merge, cf.game_has_reward, cf.game_has_progress, cf.game_has_collection
        HAVING SUM(cp.spend) > 100 AND SUM(cp.install) > 10
        ORDER BY roas DESC
        LIMIT ?
    """, [limit]).fetchall()
    conn.close()

    cols = ["creative_id", "project", "spend", "installs", "imp", "clicks", "roas",
            "hook_type", "warm_cool", "center_layout", "left_right_layout",
            "subject_type", "primary_color", "secondary_color",
            "saturation", "brightness", "emotion_surprise", "emotion_reward",
            "game_has_merge", "game_has_reward", "game_has_progress", "game_has_collection"]
    return [dict(zip(cols, r)) for r in rows]


# ── Convert to CreativeEntity ─────────────────────────────────────────
def winner_to_entity(w: dict) -> CreativeEntity:
    """Convert a DB winner row to a CreativeEntity for analysis."""
    # Determine hook type
    hook_map = {
        "before_after": "BEFORE_AFTER",
        "collection": "COLLECTION",
        "reward": "REWARD_REVEAL",
        "progression": "PROGRESSION",
        "rare_item": "RARE_ITEM",
        "curiosity": "CURIOSITY",
        "impossible": "IMPOSSIBLE_RESULT",
    }
    raw_hook = (w.get("hook_type") or "").lower().strip()
    hook_type = hook_map.get(raw_hook, raw_hook)

    name = f"Winner_{w['creative_id'][:8]}"
    layout = "center" if w.get("center_layout") else ("left_right" if w.get("left_right_layout") else "top_bottom")
    style = w.get("warm_cool") or "cool"
    primary_color = w.get("primary_color") or "purple"

    return CreativeEntity(
        creative_asset_id=w["creative_id"],
        identity=CreativeIdentity(name=name, type=CreativeType.IMAGE),
        sources=CreativeSources(),
        performance=CreativePerformance(
            acquisition=AcquisitionData(
                spend=float(w.get("spend", 0)),
                impressions=int(w.get("imp", 0)),
                clicks=int(w.get("clicks", 0)),
                installs=int(w.get("installs", 0)),
            ),
            revenue=RevenueData(
                iap_d30=0,
                purchases=0,
                payer_count=0,
                payer_rate=0.0,
            ),
        ),
        asset=CreativeAsset(),
        analysis=EntityAnalysis(
            hook_type=hook_type,
            reward_type="collection" if w.get("game_has_collection") else "treasure",
            style=style,
            video_dna={
                "subject": w.get("subject_type") or "character",
                "character_focus": 70 if w.get("subject_type") else 30,
                "saturation": (float(w.get("saturation") or 0.5)) * 100,
                "contrast": (float(w.get("brightness") or 0.5)) * 100,
                "premium_feeling": 70 if style == "cool" else 50,
                "layout": layout,
                "primary_color": primary_color,
                "has_gameplay": bool(w.get("game_has_merge")),
                "has_reward": bool(w.get("game_has_reward")),
                "has_progression": bool(w.get("game_has_progress")),
            },
            image_dna={},
        ),
    )


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Step 3: Creative Intelligence 分析 + Lovart 生图")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    output_dir = ROOT / "output" / "creative_intelligence"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load Winners ───────────────────────────────────────────────
    print("\n[1] 加载 Top 10 P04 Witch Winners...")
    winners = load_top_winners(db_path, limit=10)
    print(f"    加载 {len(winners)} 个 Winner")

    if not winners:
        print("    ❌ 无数据，退出")
        return

    for i, w in enumerate(winners):
        layout = "center" if w.get("center_layout") else ("left_right" if w.get("left_right_layout") else "other")
        print(f"    {i+1}. {w['creative_id']} | ROAS={w['roas']:.3f} | "
              f"hook={w.get('hook_type','?')} | color={w.get('warm_cool','?')} | layout={layout}")

    # ── 2. Convert to CreativeEntity ──────────────────────────────────
    print("\n[2] 转换为 CreativeEntity...")
    entities = [winner_to_entity(w) for w in winners]
    print(f"    转换完成: {len(entities)} 个实体")

    # ── 3. Run Creative Intelligence Analysis ─────────────────────────
    print("\n[3] 运行 Phase 4.1 Creative Intelligence 分析...")
    engine = AnalysisEngine()
    print(f"    权重: monetization={ANALYSIS_WEIGHTS['monetization']:.0%} "
          f"hook={ANALYSIS_WEIGHTS['hook']:.0%} "
          f"gameplay={ANALYSIS_WEIGHTS['gameplay']:.0%} "
          f"visual={ANALYSIS_WEIGHTS['visual']:.0%}")

    report = engine.analyze_batch(entities)

    print(f"\n    分析结果:")
    print(f"    {'Creative':<20s} {'Score':>6s} {'Winner':>7s} {'IAP':>5s} {'Hook':>15s} {'Monetization':>13s} {'Insight'}")
    print(f"    {'-'*20} {'-'*6} {'-'*7} {'-'*5} {'-'*15} {'-'*13} {'-'*30}")

    for analysis in report.analyses:
        cid = getattr(analysis, 'creative_id', '')[:20]
        print(f"    {cid:<20s} {analysis.analysis_score:>6.1f} "
              f"{'✅' if analysis.is_winner else '  '}     "
              f"{'✅' if analysis.is_iap_quality else '  '}   "
              f"{analysis.hook_features.hook_type.value:>15s} "
              f"{analysis.monetization_features.monetization_score:>5.1f}/100   "
              f"{analysis.insight[:35]}")

    print(f"\n    Winner 率: {report.winner_count}/{len(report.analyses)} "
          f"({report.winner_count/len(report.analyses)*100:.0f}%)")
    print(f"    平均分: {report.avg_analysis_score:.1f}")

    # ── 4. Extract Creative DNA ───────────────────────────────────────
    print("\n[4] 提取 Creative DNA...")
    extractor = CreativeDNAExtractor()
    roas_map = {w["creative_id"]: w["roas"] for w in winners}
    dnas = extractor.extract_batch(report.analyses, roas_map)

    for i, dna in enumerate(dnas):
        cid = getattr(dna, 'creative_id', '')[:20]
        print(f"\n    DNA #{i+1}: {cid}")
        print(f"      hook: {dna.hook}")
        print(f"      scene: {dna.scene}")
        print(f"      emotion: {dna.emotion}")
        print(f"      monetization: {dna.monetization}")
        if dna.visual_rules:
            print(f"      visual_rules: {dna.visual_rules}")
        if dna.avoid_rules:
            print(f"      avoid_rules: {dna.avoid_rules}")

    # ── 5. Validate ───────────────────────────────────────────────────
    print("\n[5] 验证分析质量...")
    validator = Validator()
    winners_list = [a for a in report.analyses if a.is_winner]
    losers_list = [a for a in report.analyses if not a.is_winner]
    val_report = validator.validate(report.analyses)
    diff = validator.validate_winner_vs_loser(winners_list, losers_list) if losers_list else {}

    print(f"    Winner 率: {val_report.winner_rate:.0%}")
    print(f"    Clickbait 检测: {val_report.clickbait_count} 个")
    print(f"    Winner vs Loser 区分度:")
    if diff:
        for k, v in diff.items():
            print(f"      {k}: {v}")

    # ── 6. Generate Best DNA for Lovart ───────────────────────────────
    print("\n[6] 生成 Lovart 生图 Prompt...")
    # Pick the best analysis by score (not first)
    best_idx = max(range(len(report.analyses)), key=lambda i: report.analyses[i].analysis_score)
    best_analysis = report.analyses[best_idx]
    best_dna = dnas[best_idx] if best_idx < len(dnas) else None

    if best_dna and best_analysis:
        hf = best_analysis.hook_features
        vf = best_analysis.visual_features
        mf = best_analysis.monetization_features

        # Build Lovart prompt from Winner DNA
        prompts = []
        for i in range(5):
            variant = (
                f"P04 Witch merge game mobile ad, "
                f"magical witch character, "
                f"{best_dna.emotion} mood, "
                f"{best_dna.scene} scene, "
                f"cool purple-gold magical color palette, "
                f"center composition, "
                f"collection gameplay showing rare items, "
                f"high quality mobile game creative, "
                f"clear download CTA button, "
                f"Facebook ad format 1:1, "
                f"variant {i+1}"
            )
            prompts.append(variant)
            print(f"    Prompt {i+1}: {variant[:120]}...")

        # Save prompts
        prompt_data = {
            "generated_at": datetime.now().isoformat(),
            "winner_dna": {
                "hook": best_dna.hook,
                "scene": best_dna.scene,
                "emotion": best_dna.emotion,
                "monetization": best_dna.monetization,
                "visual_rules": best_dna.visual_rules,
                "avoid_rules": best_dna.avoid_rules,
            },
            "analysis_score": best_analysis.analysis_score,
            "prompts": prompts,
        }
        prompt_path = output_dir / "lovart_prompts.json"
        with open(prompt_path, "w", encoding="utf-8") as f:
            json.dump(prompt_data, f, indent=2, ensure_ascii=False)
        print(f"\n    Prompt 已保存: {prompt_path}")

    # ── 7. Save Full Analysis Report ──────────────────────────────────
    report_path = output_dir / "analysis_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "winner_count": report.winner_count,
            "avg_score": report.avg_analysis_score,
            "weights": ANALYSIS_WEIGHTS,
            "analyses": report.to_dict()["analyses"],
            "dna_list": [d.to_dict() for d in dnas],
            "validation": val_report.to_dict() if hasattr(val_report, 'to_dict') else {},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n    完整报告已保存: {report_path}")

    print(f"\n{'='*60}")
    print(f"  Step 3 完成!")
    print(f"  Winner DNA: {best_dna.hook if best_dna else 'N/A'}")
    print(f"  Lovart Prompts: {len(prompts) if best_dna else 0} 个")
    print(f"{'='*60}")

    return prompts if best_dna else []


if __name__ == "__main__":
    main()