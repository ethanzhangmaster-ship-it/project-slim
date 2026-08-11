#!/usr/bin/env python3
"""基于原图参考的智能出图 — 分析原图视觉DNA → 参考原图生成匹配风格的1:1图片

用法:
  python scripts/gen_from_reference.py                          # 默认用第一张原图
  python scripts/gen_from_reference.py --image "D:\p4素材\新建文件夹 (3)\原图10.png"
  python scripts/gen_from_reference.py --all --count 5          # 分析所有原图, 每张生成5个变体
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# .env 加载
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    parser = argparse.ArgumentParser(description="基于原图参考的智能出图")
    parser.add_argument("--image", type=str, default=None,
                        help="单张原图路径 (默认: D:\\p4素材\\新建文件夹 (3)\\原图10.png)")
    parser.add_argument("--all", action="store_true",
                        help="分析所有原图")
    parser.add_argument("--count", type=int, default=8,
                        help="每张原图生成变体数 (默认 8)")
    parser.add_argument("--output", type=str, default="output/reference_gen",
                        help="输出目录")
    args = parser.parse_args()

    from market_ops.clients.lovart import LovartClient, download_image

    client = LovartClient()
    output_dir = ROOT / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # 收集原图
    source_dir = Path(r"D:\p4素材\新建文件夹 (3)")
    if args.image:
        ref_images = [Path(args.image)]
    elif args.all:
        ref_images = sorted(source_dir.glob("原图*.png"))
    else:
        ref_images = [source_dir / "原图10.png"]

    print("=" * 70)
    print(f"  基于原图参考的智能出图")
    print(f"  原图数: {len(ref_images)}")
    print(f"  每张变体数: {args.count}")
    print("=" * 70)

    all_results = []

    for ref_path in ref_images:
        if not ref_path.exists():
            print(f"\n  ⚠️  跳过不存在的文件: {ref_path}")
            continue

        print(f"\n{'─' * 70}")
        print(f"  原图: {ref_path.name}")
        print(f"{'─' * 70}")

        # Step 1: 分析原图视觉DNA
        print(f"  [1/4] 分析视觉DNA...")
        dna = client.describe_image(str(ref_path), project="P04 Witch")
        if "error" in dna:
            print(f"    ❌ 分析失败: {dna['error']}")
            continue

        cdn_url = dna.get("_cdn_url", "")
        print(f"    主题: {dna.get('subject', '?')}")
        print(f"    构图: {dna.get('composition', '?')}")
        print(f"    色调: {dna.get('palette', '?')}")
        print(f"    氛围: {dna.get('mood', '?')}")
        print(f"    参考图: {cdn_url[:60]}...")

        # Step 2: 上传原图作为参考
        print(f"  [2/4] 上传参考图...")
        if not cdn_url:
            cdn_url = client.upload_file(str(ref_path))
            print(f"    已上传: {cdn_url[:60]}...")
        else:
            print(f"    已缓存: {cdn_url[:60]}...")

        # Step 3: 生成变体 prompt
        print(f"  [3/4] 生成 {args.count} 个变体...")

        # 基于原图DNA构建精准prompt — 保留原图核心元素，只做变体
        subject = dna.get("subject", "witch character in magical scene")
        palette = dna.get("palette", "deep purple, mystical blue")
        mood = dna.get("mood", "mysterious")
        ui = ", ".join(dna.get("ui_elements", [])[:3])
        standout = ", ".join(dna.get("standout_features", [])[:3])

        base_prompt = (
            f"Mobile game advertisement screenshot, {subject}, "
            f"{dna.get('composition', 'centered composition')}, "
            f"game UI with {ui}, "
            f"color palette: {palette}, "
            f"{dna.get('lighting', 'magical glow')}, "
            f"{mood} mood, "
            f"standout features: {standout}, "
            f"CTA button at bottom, "
            f"high quality mobile game ad, "
            f"1:1 square aspect ratio"
        )

        variations = [
            # 变体1: 换背景
            f"{base_prompt}, different background: starry night sky with floating candles",
            # 变体2: 换角色姿态
            f"{base_prompt}, character standing and casting spell instead of seated",
            # 变体3: 换色调
            f"{base_prompt}, shift palette to emerald greens and gold accents",
            # 变体4: 增加动感
            f"{base_prompt}, add dramatic particle effects and motion blur on magic",
            # 变体5: 特写
            f"{base_prompt}, close-up view focusing on character face and crystal ball",
            # 变体6: 增加收集元素
            f"{base_prompt}, show more collectible items floating around the scene",
            # 变体7: 节日主题
            f"{base_prompt}, add festive decorations like floating lanterns and sparkles",
            # 变体8: 暗黑版
            f"{base_prompt}, darker moody version with dramatic shadows and moonlight",
        ]

        images = []
        for i, prompt in enumerate(variations[:args.count]):
            print(f"    生成变体 {i+1}/{args.count}...")
            try:
                result = client.generate_image(
                    prompt=prompt,
                    attachments=[cdn_url],  # 关键: 用原图做参考!
                )
                if result.image_urls:
                    img_url = result.image_urls[0]
                    safe_name = f"ref_{ref_path.stem}_v{i+1:02d}.png"
                    dest = output_dir / safe_name
                    download_image(img_url, dest)
                    images.append({
                        "path": str(dest),
                        "url": img_url,
                        "prompt": prompt,
                        "reference": str(ref_path),
                    })
                    print(f"      ✅ {safe_name}")
                else:
                    print(f"      ❌ 无图片: status={result.status}")
            except Exception as e:
                print(f"      ❌ 错误: {e}")

        # Step 4: 评分
        print(f"  [4/4] 评分...")
        scores = []
        for img_data in images:
            try:
                score = client.evaluate_image(
                    image_path=img_data["path"],
                    prompt=img_data["prompt"],
                    project="P04 Witch",
                    hook_type=dna.get("hook_type", "collection"),
                )
                if "error" not in score:
                    overall = sum(
                        float(score.get(d, 0) or 0)
                        for d in ["visual_quality", "brand_alignment", "hook_clarity", "ad_suitability", "originality"]
                    ) / 5
                    score["overall"] = round(overall, 2)
                scores.append(score)
                print(f"    {Path(img_data['path']).name}: {score.get('overall', '?')}")
            except Exception as e:
                print(f"    {Path(img_data['path']).name}: 评分失败 - {e}")

        all_results.append({
            "reference": str(ref_path),
            "dna": {k: v for k, v in dna.items() if not k.startswith("_")},
            "images": images,
            "scores": scores,
        })

    # 保存结果
    result_path = output_dir / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)

    total_images = sum(len(r["images"]) for r in all_results)
    print(f"\n{'=' * 70}")
    print(f"  完成! 生成 {total_images} 张图 → {output_dir}")
    print(f"  结果: {result_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
