"""Try different approaches to get high-res images from FB API."""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
API_VERSION = os.environ.get("META_API_VERSION", "v19.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"
OUT_DIR = Path(r"d:\project_slim\project_slim\output\creative_analysis\real_assets")
OUT_DIR.mkdir(parents=True, exist_ok=True)

test_creative_id = "2405756773259457"

# Get creative data
url = f"{BASE}/{test_creative_id}"
params = {
    "access_token": TOKEN,
    "fields": "id,name,thumbnail_url,image_url,object_story_spec{link_data,video_data{image_url,image_hash}}",
}
resp = requests.get(url, params=params, timeout=30)
data = resp.json()

# Approach 1: Try object_story_spec.video_data.image_url (ads/image)
oss_image = data.get("object_story_spec", {}).get("video_data", {}).get("image_url", "")
if oss_image:
    print(f"=== Approach 1: ads/image URL ===")
    print(f"URL: {oss_image[:120]}...")
    try:
        img_resp = requests.get(oss_image, timeout=30)
        print(f"Status: {img_resp.status_code}, Size: {len(img_resp.content)} bytes")
        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
            out_path = OUT_DIR / f"fb_hires_{test_creative_id}.jpg"
            out_path.write_bytes(img_resp.content)
            from PIL import Image
            img = Image.open(out_path)
            print(f"SAVED: {img.size}, {img.mode}")
    except Exception as e:
        print(f"FAIL: {e}")

# Approach 2: Try modifying thumbnail URL to get larger size
thumbnail_url = data.get("thumbnail_url", "")
if thumbnail_url:
    print(f"\n=== Approach 2: Modify thumbnail URL ===")
    # Try different sizes
    for size_replace in [
        ("p64x64", "p720x720"),
        ("p64x64", "p1080x1080"),
        ("p64x64", ""),
        ("stp=c0.5000x0.5000f_dst-emg0_p64x64_q75_tt6", "stp=dst-emg0_p720x720_q90_tt6"),
    ]:
        modified_url = thumbnail_url.replace(size_replace[0], size_replace[1])
        try:
            img_resp = requests.get(modified_url, timeout=15)
            if img_resp.status_code == 200 and len(img_resp.content) > 3000:
                print(f"  {size_replace[0]} -> {size_replace[1]}: {len(img_resp.content)} bytes OK")
                from PIL import Image
                from io import BytesIO
                img = Image.open(BytesIO(img_resp.content))
                print(f"    Size: {img.size}")
            else:
                print(f"  {size_replace[0]} -> {size_replace[1]}: {img_resp.status_code} ({len(img_resp.content)} bytes)")
        except Exception as e:
            print(f"  {size_replace[0]} -> {size_replace[1]}: ERROR {e}")

# Approach 3: Try creative previews endpoint
print(f"\n=== Approach 3: Creative previews ===")
url3 = f"{BASE}/{test_creative_id}/previews"
params3 = {
    "access_token": TOKEN,
    "ad_format": "DESKTOP_FEED_STANDARD",
}
try:
    resp3 = requests.get(url3, params=params3, timeout=30)
    data3 = resp3.json()
    print(f"Status: {resp3.status_code}")
    if "data" in data3:
        for item in data3["data"][:2]:
            print(f"  body: {str(item.get('body',''))[:100]}...")
    else:
        print(f"  Response: {json.dumps(data3, indent=2)[:500]}")
except Exception as e:
    print(f"FAIL: {e}")