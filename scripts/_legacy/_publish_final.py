"""Facebook 广告发布脚本 — 使用更新后的 FacebookPublisher (支持回退方案)

完整链路:
  1. 读取 pipeline_directives.json 获取 winner 信息
  2. 使用已有生成的图片 (closed_loop_20260630_070327)
  3. 上传图片到 Facebook
  4. 创建广告创意 (App 开发模式 → 回退到复用 creative_id)
  5. 创建广告 (PAUSED 状态)

用法:
  python scripts/_publish_final.py
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
if (ROOT / ".env").exists():
    with open(ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

import requests

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
page_id = os.getenv("CLOSED_LOOP_PAGE_ID", "")
adset_id = os.getenv("CLOSED_LOOP_ADSET_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")

# 导入 FacebookPublisher
_publish_dir = str(ROOT / "src" / "market_ops" / "creative_growth_loop" / "14_publish")
sys.path.insert(0, _publish_dir)
from facebook_publisher import FacebookPublisher

print("=" * 60)
print("  Facebook 广告发布 (含回退方案)")
print("=" * 60)

# 配置
publisher = FacebookPublisher(
    access_token=token,
    ad_account_id=ad_account_id,
    api_version=api_version,
    page_id=page_id,
)

# 读取 winner 信息
directives_path = ROOT / "output" / "pipeline_directives.json"
winners = {}
if directives_path.exists():
    d = json.loads(directives_path.read_text(encoding="utf-8"))
    winners = d.get("directives", {})

game_w = winners.get("game", {}).get("target", "P04 Witch")
tone_w = winners.get("color_tone", {}).get("target", "cool")
layout_w = winners.get("layout", {}).get("target", "top_bottom")

print(f"\nWinner 特征: game={game_w}, color={tone_w}, layout={layout_w}")

# Step 1: 扫描图片
image_dir = ROOT / "output" / "creative_growth_loop" / "images" / "closed_loop_20260630_070327"
images = sorted(image_dir.glob("*.png"))
print(f"\nStep 1: 找到 {len(images)} 张图片")
for img in images:
    print(f"  {img.name} ({img.stat().st_size // 1024} KB)")

if not images:
    print("❌ 无图片可发布")
    sys.exit(1)

image_paths = [str(p) for p in images]

# Step 2: 上传图片
print(f"\nStep 2: 上传 {len(image_paths)} 张图片到 Facebook...")
image_hashes = publisher.upload_images(image_paths)
print(f"  ✅ 上传成功: {len(image_hashes)}/{len(image_paths)} 张")
if not image_hashes:
    print("❌ 上传全部失败")
    sys.exit(1)

# Step 3: 创建广告创意
print(f"\nStep 3: 创建广告创意...")
run_id = datetime.now().strftime("closed_loop_%Y%m%d_%H%M%S")

headlines = [f"{game_w} - {tone_w} {layout_w}"] * len(image_hashes)
primary_texts = [
    "Can you solve this? 🔮",
    "Merge & conquer! Try now 👇",
    "The most satisfying puzzle game!",
    "Test your skills - can you beat it?",
    "Addictive puzzle fun awaits!",
]

creative_ids = publisher.create_ad_creatives(
    image_hashes=image_hashes,
    headlines=headlines,
    primary_texts=primary_texts,
)

# Step 3 回退: 如果 creative 创建失败
if not creative_ids:
    print(f"\n  ⚠️ creative 创建失败 (App 开发模式)，启动回退方案...")
    print(f"  获取已有 creative_id...")
    existing_ids = publisher.get_existing_creative_ids(limit=20)
    print(f"  已有 creative: {len(existing_ids)} 个")
    if not existing_ids:
        print("❌ 无法获取现有 creative_id，发布失败")
        sys.exit(1)
    print(f"  回退方案: 使用现有 creative_id 创建 ad")

# Step 4: 创建广告
print(f"\nStep 4: 创建广告 (adset={adset_id})...")
status = "PAUSED"
ad_ids = []
names = [f"AI_{run_id}_{i:02d}" for i in range(len(image_hashes))]

if creative_ids:
    # 正常路径: 用新建 creative_id
    ad_ids = publisher.create_ads(
        creative_ids=creative_ids,
        adset_id=adset_id,
        names=names,
        status=status,
    )
else:
    # 回退路径: 用 upload_images 的 hash + 已有 creative_id
    for i, img_hash in enumerate(image_hashes):
        ad_id = publisher.create_ad_with_image_hash(
            image_hash=img_hash,
            adset_id=adset_id,
            creative_ids=existing_ids,
            ad_name=names[i],
            status=status,
        )
        if ad_id:
            ad_ids.append(ad_id)
        time.sleep(0.3)

print(f"\n  ✅ 广告创建: {len(ad_ids)}/{len(image_hashes)} 个, 状态={status}")

# Step 5: 保存结果
result = {
    "run_id": run_id,
    "ad_account_id": ad_account_id,
    "adset_id": adset_id,
    "status": status,
    "api_version": api_version,
    "winner": {"game": game_w, "color_tone": tone_w, "layout": layout_w},
    "image_hashes": image_hashes,
    "creative_ids": creative_ids,
    "ad_ids": ad_ids,
    "published_at": datetime.now(timezone.utc).isoformat(),
    "mode": "normal" if creative_ids else "fallback",
}

result_path = ROOT / "output" / "closed_loop" / "publish_results" / f"publish_{run_id}.json"
result_path.parent.mkdir(parents=True, exist_ok=True)
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"  发布完成!")
print(f"{'=' * 60}")
print(f"  图片上传: {len(image_hashes)} 张")
print(f"  Creative ID: {creative_ids if creative_ids else '(回退模式, 无新 creative)'}")
print(f"  广告: {len(ad_ids)} 个")
print(f"  状态: {status}")
print(f"  结果文件: {result_path}")

# 显示创建的 ad 链接
if ad_ids:
    print(f"\n  Facebook Ads Manager 链接:")
    for aid in ad_ids:
        print(f"    https://business.facebook.com/adsmanager/ads/?adservice=true&creative={aid}")