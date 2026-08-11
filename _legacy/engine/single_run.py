"""Single Run — 单条创意闭环验证入口。

流程：
  1. 输入: FB creative_id (或手动构造的 Direction Card)
  2. 方向: direction_engine → Direction Card
  3. 脚本: execution_bridge → Execution Script
  4. 输出: single_run/{run_id}/

用法:
  python -m engine.single_run --arch "Character Reveal"
  python -m engine.single_run --arch "Narrative" --output-dir ./output

验证目标:
  一个 Direction Card 是否能让 AE 做出"结构一致的视频"
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

from engine.direction_engine import generate_direction_card
from engine.execution_bridge import card_to_script, script_to_markdown, generate_single_run_output
from engine.pattern_mining import PATTERN_KEYWORDS


# ── Sample patterns for demo runs ──
SAMPLE_PATTERNS = {
    "Character Reveal": {
        "pattern": "Character Reveal", "roas": 1.01,
        "total_spend": 3360, "total_revenue": 3382,
        "mean_duration": 31, "duration_range": "15s-45s",
        "eagle_asset_count": 126, "fb_video_count": 32,
        "examples": ["P4-v2601xxx-char-reveal-30s-9X16"],
    },
    "Narrative": {
        "pattern": "Narrative", "roas": 0.49,
        "total_spend": 38069, "total_revenue": 18550,
        "mean_duration": 41, "duration_range": "18s-51s",
        "eagle_asset_count": 65, "fb_video_count": 576,
        "examples": ["P4-v2601xxx-story-40s-9X16"],
    },
    "Gameplay Loop": {
        "pattern": "Gameplay Loop", "roas": 0.57,
        "total_spend": 30042, "total_revenue": 17269,
        "mean_duration": 45, "duration_range": "15s-51s",
        "eagle_asset_count": 44, "fb_video_count": 307,
        "examples": ["P4-v2601xxx-gameplay-45s-9X16"],
    },
    "Hook Opener": {
        "pattern": "Hook Opener", "roas": 0.44,
        "total_spend": 1200, "total_revenue": 528,
        "mean_duration": 20, "duration_range": "10s-30s",
        "eagle_asset_count": 19, "fb_video_count": 12,
        "examples": ["P4-v2601xxx-hook-20s-9X16"],
    },
    "Text Scroll": {
        "pattern": "Text Scroll", "roas": 0.44,
        "total_spend": 3802, "total_revenue": 1683,
        "mean_duration": 35, "duration_range": "18s-51s",
        "eagle_asset_count": 61, "fb_video_count": 10,
        "examples": ["P4-v2601xxx-text-35s-1X1"],
    },
}


def run(archetype: str = "Character Reveal", creative_id: str = "demo",
        output_dir: str = None) -> dict:
    """Execute single creative run.

    Args:
        archetype: 创意 Archetype 名称
        creative_id: FB creative ID (任意标识)
        output_dir: 输出目录，默认 output/single_run/{run_id}/

    Returns:
        result dict (同时保存到文件)
    """
    # ── Step 1: Get pattern info ──
    pinfo = SAMPLE_PATTERNS.get(archetype)
    if not pinfo:
        available = list(SAMPLE_PATTERNS.keys())
        raise ValueError(f"Unknown archetype '{archetype}'. Available: {available}")

    # ── Step 2: Generate Direction Card ──
    cid = next((k for k, v in SAMPLE_PATTERNS.items() if v == pinfo), "C00")
    card = generate_direction_card(cid, pinfo)

    # ── Step 3: Generate Execution Script ──
    full = generate_single_run_output(creative_id, card)

    # ── Step 4: Save output ──
    if output_dir is None:
        run_id = full["run_id"]
        output_dir = Path(__file__).resolve().parent.parent / "output" / "single_run" / run_id
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "direction_card.json").write_text(
        json.dumps(full["direction_card"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "execution_script.json").write_text(
        json.dumps(full["execution_script"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "execution_script.md").write_text(
        full["execution_markdown"], encoding="utf-8")
    (output_dir / "validation.json").write_text(
        json.dumps(full["validation"], ensure_ascii=False, indent=2), encoding="utf-8")

    full["output_dir"] = str(output_dir)
    return full


def print_summary(result: dict) -> None:
    """Print readable summary."""
    es = result["execution_script"]
    card = result["direction_card"]
    print(f"\n{'='*60}")
    print(f"🎬 SINGLE RUN: {result['run_id']}")
    print(f"{'='*60}")
    print(f"  Creative ID: {result['fb_creative_id']}")
    print(f"  Archetype:   {result['archetype']} (Cluster {result['cluster_id']})")
    print(f"  Duration:    {es['total_duration']}")
    print(f"  Hook:        {es['hook_type']}")
    print(f"  Narrative:   {es['narrative_type']}")
    print(f"  Trigger:     {es['cognitive_trigger']}")
    print(f"")
    print(f"  🎯 {card['winning_direction']}")
    print(f"")
    print(f"  Shot segments: {len(es['script_segments'])}")
    print(f"  AE tasks:      {len(es['ae_tasks'])}")
    print(f"  AI tasks:      {len(es['ai_tasks'])}")
    print(f"  Constraints:   {len(es['constraints'])}")
    print(f"")
    print(f"  📁 Output: {result['output_dir']}")
    print(f"    ├── direction_card.json")
    print(f"    ├── execution_script.json")
    print(f"    ├── execution_script.md")
    print(f"    └── validation.json")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V3.5 Single Creative Run")
    parser.add_argument("--arch", default="Character Reveal",
                        choices=list(SAMPLE_PATTERNS.keys()),
                        help="Creative archetype to generate script for")
    parser.add_argument("--creative-id", default="demo",
                        help="FB creative identifier")
    parser.add_argument("--output-dir", default=None,
                        help="Custom output directory")
    args = parser.parse_args()

    result = run(args.arch, args.creative_id, args.output_dir)
    print_summary(result)
