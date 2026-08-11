#!/usr/bin/env python3
"""🎬 V3.5.2 Production Run — Character Reveal Scaling (48h).

生成 5 个变体的完整制作交付包：
  - Direction Card (锁定的结构 + 变体视觉风格)
  - Execution Script (JSON + Markdown)
  - AI Prompt 集 (所有画面 Prompt)
  - 验证占位文件

用法:
  python run_production.py              # 全部 5 个变体
  python run_production.py --variant v1_dark_fantasy  # 单个变体
"""
import json, sys
from pathlib import Path
from datetime import datetime

from engine.pattern_lock import generate_locked_card, validate_variant, list_variants, LOCKED_CARD
from engine.execution_bridge import card_to_script, script_to_markdown

OUT = Path(__file__).resolve().parent / "output" / "character_reveal"
VARIANT_DIR = OUT / "variants"
SCRIPTS_DIR = OUT / "execution_scripts"


def generate_variant(variant_key: str) -> dict:
    """Generate complete production package for one variant."""
    # ── 1. Generate locked Direction Card ──
    card = generate_locked_card(variant_key)
    style = card["variant_style"]

    # ── 2. Validate against locked structure ──
    violations = validate_variant(card)
    has_critical = any(v["severity"] == "critical" for v in violations)
    if has_critical:
        print(f"  ⚠️  CRITICAL violations for {variant_key}:")
        for v in violations:
            if v["severity"] == "critical":
                print(f"     ❌ {v['message']}")

    # ── 3. Generate Execution Script ──
    execution = card_to_script(card)
    markdown = script_to_markdown(execution)

    # ── 4. Extract all AI prompts ──
    ai_prompts = [seg["ai_generation_prompt"] for seg in execution["script_segments"]]

    # ── 5. Build production package ──
    package = {
        "variant": variant_key,
        "style": style,
        "generated_at": datetime.now().isoformat(),
        "direction_card": card,
        "execution_script": execution,
        "execution_markdown": markdown,
        "ai_prompts": ai_prompts,
        "validation_violations": violations,
        "validation_placeholder": {
            "variant": variant_key,
            "spend": None,
            "revenue": None,
            "impressions": None,
            "clicks": None,
            "installs": None,
            "roas": None,
            "ctr": None,
            "cvr": None,
            "verdict": None,
            "notes": "",
        },
    }

    return package


def save_variant(pkg: dict):
    """Save variant package to output directory."""
    v = pkg["variant"]
    variant_dir = VARIANT_DIR / v
    variant_dir.mkdir(parents=True, exist_ok=True)

    (variant_dir / "direction_card.json").write_text(
        json.dumps(pkg["direction_card"], ensure_ascii=False, indent=2), encoding="utf-8")
    (variant_dir / "execution_script.json").write_text(
        json.dumps(pkg["execution_script"], ensure_ascii=False, indent=2), encoding="utf-8")
    (variant_dir / "execution_script.md").write_text(
        pkg["execution_markdown"], encoding="utf-8")
    (variant_dir / "ai_prompts.json").write_text(
        json.dumps(pkg["ai_prompts"], ensure_ascii=False, indent=2), encoding="utf-8")
    (variant_dir / "validation.json").write_text(
        json.dumps(pkg["validation_placeholder"], ensure_ascii=False, indent=2), encoding="utf-8")

    # Also save flat scripts directory
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (SCRIPTS_DIR / f"{v}.md").write_text(pkg["execution_markdown"], encoding="utf-8")

    return variant_dir


def print_report(pkgs: list[dict]):
    """Print production run summary."""
    print(f"\n{'='*70}")
    print("🎬 CHARACTER REVEAL — 48h SCALABILITY RUN")
    print(f"{'='*70}")
    print(f"  Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Variants: {len(pkgs)}/5")
    print()

    for pkg in pkgs:
        violations = pkg["validation_violations"]
        crits = [v for v in violations if v["severity"] == "critical"]
        warns = [v for v in violations if v["severity"] == "warning"]
        status = "✅ LOCKED" if not crits else "⚠️ VIOLATION"
        
        card = pkg["direction_card"]
        style = card.get("variant_styling", {})
        es = pkg["execution_script"]

        print(f"  {'='*50}")
        print(f"  {status} | {pkg['variant']}")
        print(f"  Style: {pkg['style']}")
        print(f"  Mood:  {style.get('mood','')}")
        print(f"  Palette: {style.get('color_palette','')}")
        print(f"  Duration: {es['total_duration']}")
        print(f"  Hook: {es['hook_type']} | Trigger: {es['cognitive_trigger']}")
        print(f"  Shots: {len(es['script_segments'])} | AE tasks: {len(es['ae_tasks'])} | AI prompts: {len(pkg['ai_prompts'])}")
        if warns:
            print(f"  ⚠️ Warnings: {len(warns)}")
        print(f"  📁 {pkg['output_dir']}")

    print(f"\n{'='*70}")
    print("📋 STRUCTURE LOCK VERIFICATION")
    print(f"{'='*70}")
    all_crits = [v for pkg in pkgs for v in pkg["validation_violations"] if v["severity"] == "critical"]
    all_warns = [v for pkg in pkgs for v in pkg["validation_violations"] if v["severity"] == "warning"]
    print(f"  Critical violations: {len(all_crits)} {'✅ All clean' if not all_crits else '❌ Check above'}")
    print(f"  Warnings: {len(all_warns)}")
    print()

    print(f"{'='*70}")
    print("🚀 NEXT STEPS")
    print(f"{'='*70}")
    print(f"  1. AE picks up scripts from:")
    print(f"     {OUT / 'execution_scripts' / '*'}")
    print(f"  2. AI art team generates hero frames from:")
    print(f"     {VARIANT_DIR / '{variant}' / 'ai_prompts.json'}")
    print(f"  3. Launch 5 videos: same budget, same audience")
    print(f"  4. After 48h, update validation.json for each variant")
    print(f"  5. Run scaling_tracker to get verdict")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Character Reveal Production Run")
    parser.add_argument("--variant", default=None,
                        help="Single variant key (default: all 5)")
    args = parser.parse_args()

    variants = list_variants()
    if args.variant:
        variants = [v for v in variants if v["key"] == args.variant]
        if not variants:
            print(f"Unknown variant: {args.variant}")
            sys.exit(1)

    # Generate variants
    pkgs = []
    for vinfo in variants:
        vkey = vinfo["key"]
        print(f"\nGenerating {vkey} ({vinfo['style']})...")
        pkg = generate_variant(vkey)
        pkg["output_dir"] = str(save_variant(pkg))
        pkgs.append(pkg)
        print(f"  ✅ {vkey}: {len(pkg['ai_prompts'])} AI prompts, "
              f"{len(pkg['execution_script']['ae_tasks'])} AE tasks")

    # Sort by output dir time for consistent ordering
    pkgs.sort(key=lambda p: p["variant"])

    # Save base card
    (OUT / "base_card.json").write_text(
        json.dumps(LOCKED_CARD, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save summary index
    index = {
        "generated_at": datetime.now().isoformat(),
        "total_variants": len(pkgs),
        "archetype": "Character Reveal",
        "structure_locked": True,
        "variants": [
            {
                "key": p["variant"],
                "style": p["style"],
                "dir": p["output_dir"],
                "has_critical_violations": any(
                    v["severity"] == "critical" for v in p["validation_violations"]),
            }
            for p in pkgs
        ],
    }
    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print_report(pkgs)


if __name__ == "__main__":
    main()
