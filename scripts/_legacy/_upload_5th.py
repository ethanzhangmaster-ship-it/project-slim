"""补传第 5 张图并创建广告"""
import os, sys, json
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

if (ROOT / ".env").exists():
    with open(ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

_publish_dir = str(ROOT / "src" / "market_ops" / "creative_growth_loop" / "14_publish")
sys.path.insert(0, _publish_dir)
from facebook_publisher import FacebookPublisher
import time

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
adset_id = os.getenv("CLOSED_LOOP_ADSET_ID", "")

publisher = FacebookPublisher(
    access_token=token,
    ad_account_id=ad_account_id,
    api_version=api_version,
)

# 第 5 张图
img_path = ROOT / "output/creative_growth_loop/images/closed_loop_20260630_070327/variant_05_00.png"
run_id = "closed_loop_20260630_154336"

print(f"上传 {img_path.name}...")
hashes = publisher.upload_images([str(img_path)])
print(f"上传结果: {hashes}")

if hashes:
    existing = publisher.get_existing_creative_ids(limit=20)
    print(f"现有 creative: {len(existing)}")
    ad_id = publisher.create_ad_with_image_hash(
        image_hash=hashes[0],
        adset_id=adset_id,
        creative_ids=existing,
        ad_name=f"AI_{run_id}_04",
        status="PAUSED",
    )
    print(f"Ad created: {ad_id}")

    if ad_id:
        # 更新结果文件
        result_file = ROOT / "output/closed_loop/publish_results" / f"publish_{run_id}.json"
        if result_file.exists():
            result = json.loads(result_file.read_text(encoding="utf-8"))
            result["image_hashes"].append(hashes[0])
            result["ad_ids"].append(ad_id)
            result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"结果已更新: {len(result['ad_ids'])} 个广告")
else:
    print("上传失败, 跳过")