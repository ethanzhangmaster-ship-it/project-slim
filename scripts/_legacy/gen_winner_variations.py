#!/usr/bin/env python3
"""基于 IAP 赢家分析的智能出图

策略 (基于 270 张 P04 素材归因分析):
  ✅ 必须: 展示 merge 玩法 (merge board + 进化箭头 + 进度条)
  ✅ 必须: 1:1 方形 (1024x1024)
  ✅ 必须: 深紫 + 金色色调
  ✅ 必须: 底部 CTA 横幅
  ❌ 避免: 纯场景/角色图 (没有玩法展示)
  ❌ 避免: 直接用原图截图

参考: TOP 3 赢家图片做视觉参考 (img2img)
生成: 每张参考图 4 个变体 = 共 12 张新素材
"""
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


# TOP 3 赢家 (按 IAP 综合评分, spend≥$50, installs≥10)
WINNER_IMAGES = [
    r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\P4-IOS-US-图片2-0614_26995257276809682.png",
    r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\P4-IOS-T1-图片3-0614_1499507254711059.png",
    r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\P4-IOS-T1-图片6-0608_2681080065641777.png",
]

# 基于赢家DNA的变体prompt模板 — 保留赢家核心元素, 只做可控变体
VARIATION_STRATEGIES = [
    # 策略1: 换游戏场景但保留所有UI结构
    lambda dna: (
        f"Mobile game advertisement screenshot, {dna.get('subject','witch with merge gameplay')}, "
        f"keep the same composition and UI layout, "
        f"change the background to {dna.get('lighting','magical night')} with floating lanterns, "
        f"color palette: deep purple, violet, golden yellow, "
        f"merge board UI visible, progression arrows, CTA banner at bottom, "
        f"1:1 square format 1024x1024, high quality mobile game ad"
    ),
    # 策略2: 强化进化路径可视化
    lambda dna: (
        f"Mobile game ad, {dna.get('subject','witch')} showing clear merge evolution, "
        f"3-stage before/after transformation with arrows, "
        f"numbered badges (1,2,3) showing upgrade path, "
        f"merge board with input/output slots visible, "
        f"color palette: deep purple, magenta glow, gold accents, "
        f"CTA banner 'Play Now!' at bottom, "
        f"1:1 square 1024x1024, professional game ad creative"
    ),
    # 策略3: 增加收集/奖励可视化
    lambda dna: (
        f"Mobile game ad, {dna.get('subject','magical collection scene')}, "
        f"show collectible items floating with count numbers, "
        f"progress bar showing collection completion, "
        f"reward chest glowing with magical particles, "
        f"color palette: deep purple, teal glow, golden sparkles, "
        f"CTA 'Collect All!' at bottom, "
        f"1:1 square 1024x1024, eye-catching game ad"
    ),
    # 策略4: 更暗色调 + 霓虹高亮
    lambda dna: (
        f"Mobile game ad, {dna.get('subject','dark mystical witch')}, "
        f"darker moody version with dramatic neon purple highlights, "
        f"merge board glowing in center, progression arrows in bright gold, "
        f"color palette: midnight black, neon purple, electric gold, "
        f"CTA 'Merge Now!' in glowing banner at bottom, "
        f"1:1 square 1024x1024, premium game ad creative"
    ),
]


def main():
    print("=" * 70)
    print("  IAP 赢家策略出图")
    print(f"  参考图: {len(WINNER_IMAGES)} 张 TOP 赢家")
    print(f"  变体: {len(VARIATION_STRATEGIES)} 种策略/张")
    print(f"  预计产出: {len(WINNER_IMAGES) * len(VARIATION_STRATEGIES)} 张")
    print("=" * 70)

    client = LovartClient()
    output_dir = ROOT / "output" / "winner_variations" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    for ref_idx, ref_path in enumerate(WINNER_IMAGES):
        if not Path(ref_path).exists():
            print(f"\n  ⚠️  跳过不存在的文件: {ref_path}")
            continue

        print(f"\n{'─' * 70}")
        print(f"  参考图 {ref_idx+1}/{len(WINNER_IMAGES)}: {Path(ref_path).name[:50]}")
        print(f"{'─' * 70}")

        # 1. 分析参考图DNA
        print(f"  分析视觉DNA...")
        dna = client.describe_image(ref_path, project="P04 Witch")
        if "error" in dna:
            print(f"  ❌ 失败: {dna['error']}")
            continue
        print(f"  主题: {dna.get('subject','?')[:70]}")
        print(f"  色调: {dna.get('palette','?')[:50]}")

        # 2. 上传参考图
        cdn_url = dna.get("_cdn_url", "") or client.upload_file(ref_path)
        print(f"  参考CDN: {cdn_url[:60]}...")

        # 3. 生成变体
        for var_idx, strategy in enumerate(VARIATION_STRATEGIES):
            prompt = strategy(dna)
            print(f"\n  变体 {var_idx+1}: {prompt[:80]}...")

            try:
                result = client.generate_image(
                    prompt=prompt,
                    attachments=[cdn_url],
                )
                if result.image_urls:
                    img_url = result.image_urls[0]
                    dest = output_dir / f"w{ref_idx+1}_v{var_idx+1}.png"
                    download_image(img_url, dest)

                    # 评分
                    try:
                        score = client.evaluate_image(
                            image_path=str(dest),
                            prompt=prompt,
                            project="P04 Witch",
                            hook_type=dna.get("hook_type", "collection"),
                        )
                        dims = ["visual_quality", "brand_alignment", "hook_clarity", "ad_suitability", "originality"]
                        overall = sum(float(score.get(d, 0) or 0) for d in dims) / 5
                    except:
                        overall = 0

                    from PIL import Image
                    img = Image.open(dest)
                    all_results.append({
                        "path": str(dest),
                        "size": f"{img.size[0]}x{img.size[1]}",
                        "score": round(overall, 2),
                        "reference": ref_path,
                        "prompt": prompt,
                    })
                    print(f"    ✅ {dest.name}: {img.size[0]}x{img.size[1]}, score={overall:.1f}")
                else:
                    print(f"    ❌ 无图片输出")
            except Exception as e:
                print(f"    ❌ {e}")

    # 汇总
    print(f"\n{'=' * 70}")
    print(f"  生成完成!")
    print(f"{'=' * 70}")
    print(f"  总计: {len(all_results)} 张")
    if all_results:
        scores = [r["score"] for r in all_results]
        print(f"  评分: {min(scores):.1f} ~ {max(scores):.1f}, 均分 {sum(scores)/len(scores):.1f}")
        passed = [r for r in all_results if r["score"] >= 6.0]
        print(f"  通过 (≥6.0): {len(passed)}/{len(all_results)}")
    print(f"  输出: {output_dir}")

    # 保存
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
