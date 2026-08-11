#!/usr/bin/env python3
"""补完赢家出图 — 参考图 2, 3 的剩余变体"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from market_ops.clients.lovart import LovartClient, download_image

# 参考图 2, 3 (TOP 赢家 #2, #3)
REFS = [
    r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\P4-IOS-T1-图片3-0614_1499507254711059.png",
    r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\P4-IOS-T1-图片6-0608_2681080065641777.png",
]

# 简化策略 — 只保留验证过能出图的
STRATEGIES = [
    ("进化路径", lambda d: (
        f"Mobile game ad screenshot, {d.get('subject','witch with merge game')}, "
        f"show clear merge evolution stages with progression arrows, "
        f"merge board UI visible, numbered level badges, "
        f"color palette: deep purple, gold accents, magenta glow, "
        f"CTA banner at bottom, 1:1 square, high quality"
    )),
    ("收集奖励", lambda d: (
        f"Mobile game ad, {d.get('subject','magical collection')}, "
        f"show collectible items with count numbers, reward chest glowing, "
        f"progress bar visible, magical sparkles and particles, "
        f"color palette: deep purple, teal glow, golden highlights, "
        f"CTA 'Collect All!' at bottom, 1:1 square 1024x1024"
    )),
    ("暗黑霓虹", lambda d: (
        f"Mobile game ad, {d.get('subject','dark mystical witch')}, "
        f"darker version with neon purple highlights and dramatic shadows, "
        f"merge board glowing in center, progression arrows in bright gold, "
        f"color palette: midnight black, neon purple, electric gold, "
        f"CTA at bottom, 1:1 square 1024x1024"
    )),
]


def main():
    client = LovartClient()
    output_dir = ROOT / "output" / "winner_variations" / "20260629_194352"

    for ref_idx, ref_path in enumerate(REFS, start=2):
        if not Path(ref_path).exists():
            print(f"跳过: {ref_path}")
            continue

        print(f"\n── 参考图 {ref_idx}/3: {Path(ref_path).name[:40]}")

        # 分析
        dna = client.describe_image(ref_path, project="P04 Witch")
        if "error" in dna:
            print(f"  ❌ {dna['error']}")
            continue
        print(f"  主题: {str(dna.get('subject','?'))[:60]}")
        cdn = dna.get("_cdn_url", "") or client.upload_file(ref_path)

        for sname, strategy in STRATEGIES:
            prompt = strategy(dna)
            print(f"  [{sname}] {prompt[:60]}...")
            try:
                result = client.generate_image(prompt=prompt, attachments=[cdn])
                if result.image_urls:
                    dest = output_dir / f"w{ref_idx}_{sname}.png"
                    download_image(result.image_urls[0], dest)
                    from PIL import Image
                    sz = Image.open(dest).size
                    print(f"    ✅ {dest.name}: {sz[0]}x{sz[1]}")
                else:
                    print(f"    ❌ 无输出")
            except Exception as e:
                print(f"    ❌ {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
