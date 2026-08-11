"""验证已创建广告的 creative 实际图片内容"""
import json, os, sys, requests
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Load env
if (ROOT / ".env").exists():
    with open(ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

token = os.getenv("META_ACCESS_TOKEN", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
BV = f"https://graph.facebook.com/{api_version}"

# 读取发布结果
result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_154336.json"
result = json.loads(result_file.read_text())

print("=" * 60)
print("  验证已创建广告的 creative 内容")
print("=" * 60)

for i, ad_id in enumerate(result["ad_ids"]):
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": token,
        "fields": "id,name,creative{id,image_url,thumbnail_url,image_hash,object_story_spec}",
    })
    d = r.json()
    cr = d.get("creative", {})
    img_url = cr.get("image_url", "")
    thumb_url = cr.get("thumbnail_url", "")
    img_hash = cr.get("image_hash", "")
    oss = cr.get("object_story_spec", {})
    
    print(f"\n[{i+1}] Ad {ad_id}")
    print(f"    name: {d.get('name','?')}")
    print(f"    creative_id: {cr.get('id','?')}")
    print(f"    image_hash: {img_hash[:20] if img_hash else 'N/A'}...")
    
    # 对比 image_hash 是否等于我们上传的
    our_hash = result["image_hashes"][i] if i < len(result["image_hashes"]) else ""
    print(f"    我们上传的 hash: {our_hash[:20]}...")
    print(f"    匹配: {'✅' if img_hash == our_hash else '❌ (用的是旧 creative 的图片)'}")
    
    # 显示 object_story_spec 类型
    if isinstance(oss, dict):
        if "video_data" in oss:
            print(f"    类型: VIDEO (视频广告)")
        elif "link_data" in oss:
            print(f"    类型: LINK_DATA (图片广告)")
        else:
            print(f"    类型: {list(oss.keys())}")

print(f"\n{'=' * 60}")
print(f"  结论")
print(f"{'=' * 60}")
print("""
如果 image_hash 不匹配 → 说明复用的是旧 creative，图片还是旧的
如果匹配 → 说明新图片成功用在了广告里
""")