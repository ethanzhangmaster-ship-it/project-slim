"""Get video source from FB creative via Graph API."""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
API_VERSION = os.environ.get("META_API_VERSION", "v19.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"

test_creative_id = "2405756773259457"

# Step 1: Get creative with video_id
print("=== Step 1: Get creative with video_id ===")
url = f"{BASE}/{test_creative_id}"
params = {
    "access_token": TOKEN,
    "fields": "id,name,title,image_url,thumbnail_url,video_id,object_story_spec{link_data,video_data}",
}
resp = requests.get(url, params=params, timeout=30)
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False)[:1500])

# Check for video_id
video_id = data.get("video_id")
if not video_id:
    # Try from object_story_spec
    oss = data.get("object_story_spec", {})
    video_data = oss.get("video_data", {})
    video_id = video_data.get("video_id")
    print(f"\nvideo_id from object_story_spec: {video_id}")

if video_id:
    print(f"\n=== Step 2: Get video source for {video_id} ===")
    url2 = f"{BASE}/{video_id}"
    params2 = {
        "access_token": TOKEN,
        "fields": "id,source,title,length,thumbnails{uri}",
    }
    resp2 = requests.get(url2, params=params2, timeout=30)
    data2 = resp2.json()
    print(json.dumps(data2, indent=2, ensure_ascii=False)[:2000])
    
    source = data2.get("source", "")
    if source:
        print(f"\nVideo source URL: {source[:150]}...")
    else:
        print("\nNo video source URL in response")
else:
    print("\nNo video_id found for this creative")
    print("This might be an image creative, not video")