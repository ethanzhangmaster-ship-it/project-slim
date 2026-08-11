#!/usr/bin/env python3
"""Step 4: Lovart AI Image Generation.

Uses Winner DNA prompts from Step 3 to generate 5 ad creatives
via Lovart AI, then downloads and saves them locally.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.clients.lovart import LovartClient, download_image


def main():
    print("=" * 70)
    print("  Step 4: Lovart AI 生图")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    output_dir = ROOT / "output" / "creative_intelligence"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load prompts from Step 3 ───────────────────────────────────
    prompt_path = output_dir / "lovart_prompts.json"
    if not prompt_path.exists():
        print("  ❌ 未找到 lovart_prompts.json，请先运行 Step 3")
        return

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_data = json.load(f)

    prompts = prompt_data.get("prompts", [])
    dna = prompt_data.get("winner_dna", {})
    print(f"\n  加载 {len(prompts)} 个 Prompt")
    print(f"  Winner DNA: {dna.get('hook')} | {dna.get('emotion')} | {dna.get('monetization')}")

    # ── 2. Initialize Lovart client ───────────────────────────────────
    print("\n[1] 初始化 Lovart Client...")
    try:
        client = LovartClient()
        print("  ✅ Lovart AK/SK 已配置")
    except ValueError as e:
        print(f"  ❌ {e}")
        return

    # ── 3. Generate images ────────────────────────────────────────────
    print(f"\n[2] 开始生成 {len(prompts)} 张图片 (nano_banana)...")
    print(f"    预计耗时: {len(prompts) * 2}~{len(prompts) * 5} 分钟")
    print()

    results = []
    for i, prompt in enumerate(prompts):
        print(f"  [{i+1}/{len(prompts)}] 生成中...")
        print(f"      Prompt: {prompt[:100]}...")

        try:
            result = client.generate_image(
                prompt=prompt,
                model="generate_image_nano_banana",
            )

            elapsed = result.elapsed_sec
            status = result.status
            url_count = len(result.image_urls)

            print(f"      状态: {status} | 耗时: {elapsed:.0f}s | 图片: {url_count} 张")

            if status == "done" and url_count > 0:
                # Download images
                for j, url in enumerate(result.image_urls):
                    dest = images_dir / f"gen_{i+1:02d}_{j+1:02d}.png"
                    try:
                        download_image(url, dest)
                        print(f"      ✅ 已保存: {dest.name}")
                    except Exception as e:
                        print(f"      ⚠️ 下载失败: {e}")
            else:
                print(f"      ⚠️ 生成未完成: {result.assistant_text[:200]}")

            results.append(result)

        except Exception as e:
            print(f"      ❌ 生成失败: {e}")
            continue

        # Small delay between requests
        if i < len(prompts) - 1:
            time.sleep(2)

    # ── 4. Summary ────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Step 4 完成!")
    successful = [r for r in results if r.status == "done" and r.image_urls]
    print(f"  成功: {len(successful)}/{len(prompts)} | 失败: {len(prompts) - len(successful)}")

    # List generated files
    generated_files = sorted(images_dir.glob("gen_*.png"))
    print(f"\n  本地图片 ({len(generated_files)} 张):")
    for f in generated_files:
        size_kb = f.stat().st_size / 1024
        print(f"    {f.name}  ({size_kb:.0f} KB)")

    # Save results
    results_path = output_dir / "lovart_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_attempts": len(prompts),
            "successful": len(successful),
            "results": [
                {
                    "thread_id": r.thread_id,
                    "status": r.status,
                    "elapsed_sec": r.elapsed_sec,
                    "image_count": len(r.image_urls),
                }
                for r in results
            ],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已保存: {results_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()