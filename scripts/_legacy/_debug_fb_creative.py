"""Debug Facebook creative creation API call."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

import requests

token = os.getenv("META_ACCESS_TOKEN", "")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
page_id = os.getenv("CLOSED_LOOP_PAGE_ID", "")
api_version = os.getenv("META_API_VERSION", "v19.0")

# Use the image hash from the previous upload
image_hash = "0f8d1b7c9e2a3f4d5b6c7d8e9f0a1b2c"  # placeholder

# First, let's check what image hashes we have
# Actually, let's just upload one image and see the hash
image_dir = ROOT / "output" / "creative_growth_loop" / "images" / "closed_loop_20260630_070327"
images = sorted(image_dir.glob("*.png"))
print(f"Test image: {images[0].name}")

# Upload
url = f"https://graph.facebook.com/{api_version}/act_{ad_account_id}/adimages"
with open(images[0], "rb") as f:
    files = {"filename": (images[0].name, f, "image/png")}
    params = {"access_token": token}
    resp = requests.post(url, params=params, files=files, timeout=120)
    data = resp.json()
    print(f"Upload response: {json.dumps(data, indent=2)[:500]}")
    
    if "error" in data:
        print(f"Upload ERROR: {data['error']}")
        sys.exit(1)
    
    images_data = data.get("images", {})
    image_hash = list(images_data.values())[0].get("hash", "")
    print(f"Image hash: {image_hash}")

# Now try creative creation with different approaches
creative_url = f"https://graph.facebook.com/{api_version}/act_{ad_account_id}/adcreatives"

# Approach 1: Original object_story_spec
print("\n--- Approach 1: object_story_spec with link_data ---")
object_story_spec = {
    "page_id": page_id,
    "link_data": {
        "image_hash": image_hash,
        "link": "https://apps.apple.com/app/id000000000",
        "message": "Test ad creative",
        "name": "P04 Witch - Test",
        "call_to_action": {
            "type": "INSTALL_MOBILE_APP",
        },
    },
}
params = {
    "access_token": token,
    "object_story_spec": json.dumps(object_story_spec),
}
resp = requests.post(creative_url, data=params, timeout=60)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Approach 2: Without object_story_spec, use direct fields
print("\n--- Approach 2: direct fields ---")
params2 = {
    "access_token": token,
    "name": "Test Creative",
    "object_story_spec": json.dumps({
        "page_id": page_id,
        "link_data": {
            "image_hash": image_hash,
            "link": "https://apps.apple.com/app/id000000000",
            "message": "Test",
        },
    }),
}
resp2 = requests.post(creative_url, data=params2, timeout=60)
print(f"Status: {resp2.status_code}")
print(f"Response: {resp2.text[:500]}")

# Approach 3: Check if page_id is valid
print(f"\n--- Check page {page_id} ---")
page_url = f"https://graph.facebook.com/{api_version}/{page_id}"
resp3 = requests.get(page_url, params={"access_token": token, "fields": "id,name,access_token"})
print(f"Status: {resp3.status_code}")
print(f"Response: {resp3.text[:500]}")

# Approach 4: Try with the page's access token
print("\n--- Approach 4: with page access token ---")
page_data = resp3.json() if resp3.status_code == 200 else {}
page_token = page_data.get("access_token", "")

# Also check ad account capabilities
print(f"\n--- Check ad account {ad_account_id} ---")
acct_url = f"https://graph.facebook.com/{api_version}/act_{ad_account_id}"
resp4 = requests.get(acct_url, params={"access_token": token, "fields": "id,name,account_status,currency"})
print(f"Status: {resp4.status_code}")
print(f"Response: {resp4.text[:500]}")