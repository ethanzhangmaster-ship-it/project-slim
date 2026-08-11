"""Test FB token and download real creative images via Graph API."""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
AD_ACCOUNT = os.environ.get("META_AD_ACCOUNT_ID", "")
API_VERSION = os.environ.get("META_API_VERSION", "v19.0")

print(f"Token found: {bool(TOKEN)}")
print(f"Token length: {len(TOKEN)}")
print(f"Token prefix: {TOKEN[:20]}...")
print(f"Ad Account: {AD_ACCOUNT}")
print(f"API Version: {API_VERSION}")

if not TOKEN:
    print("ERROR: No token found!")
    exit(1)

BASE = f"https://graph.facebook.com/{API_VERSION}"

# Test: get a specific creative by ID (top winner from Creative Mapping V2)
# Top 1: 2405756773259457 (iOS, spend=$10,290, revenue=$7,607)
test_creative_id = "2405756773259457"

print(f"\n=== Testing Graph API: creative/{test_creative_id} ===")
url = f"{BASE}/{test_creative_id}"
params = {
    "access_token": TOKEN,
    "fields": "id,name,title,body,image_url,thumbnail_url,object_story_spec,asset_feed_spec",
}
try:
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    print(f"Status: {resp.status_code}")
    if "error" in data:
        print(f"ERROR: {json.dumps(data['error'], indent=2)}")
    else:
        print(f"Creative ID: {data.get('id')}")
        print(f"Name: {data.get('name', 'N/A')[:80]}")
        print(f"Title: {data.get('title', 'N/A')[:80]}")
        image_url = data.get("image_url", "")
        thumbnail_url = data.get("thumbnail_url", "")
        print(f"image_url: {image_url[:100]}...")
        print(f"thumbnail_url: {thumbnail_url[:100]}...")
        
        # Try to download the image
        if image_url:
            print("\n=== Downloading image ===")
            img_resp = requests.get(image_url, timeout=30)
            print(f"Download status: {img_resp.status_code}")
            print(f"Content-Type: {img_resp.headers.get('content-type')}")
            print(f"Size: {len(img_resp.content)} bytes")
            if img_resp.status_code == 200:
                out_dir = Path(r"d:\project_slim\project_slim\output\creative_analysis\real_assets")
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"fb_api_{test_creative_id}.jpg"
                out_path.write_bytes(img_resp.content)
                print(f"SAVED: {out_path}")
        elif thumbnail_url:
            print("\n=== Downloading thumbnail ===")
            img_resp = requests.get(thumbnail_url, timeout=30)
            print(f"Download status: {img_resp.status_code}")
            print(f"Content-Type: {img_resp.headers.get('content-type')}")
            print(f"Size: {len(img_resp.content)} bytes")
            if img_resp.status_code == 200:
                out_dir = Path(r"d:\project_slim\project_slim\output\creative_analysis\real_assets")
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"fb_api_{test_creative_id}.jpg"
                out_path.write_bytes(img_resp.content)
                print(f"SAVED: {out_path}")
except Exception as e:
    print(f"Exception: {e}")