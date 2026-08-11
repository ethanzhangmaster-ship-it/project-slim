"""Test different approaches to download FB CDN thumbnails."""
import csv
from pathlib import Path

ROOT = Path(r"d:\project_slim\project_slim")
mapping_path = ROOT / "output" / "video_intelligence" / "p04" / "creative_mapping_v2.csv"

# Get first 5 thumbnail URLs
with open(mapping_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = [r for r in reader if r.get("thumbnail_url", "").strip()][:5]

urls = [r["thumbnail_url"].strip() for r in rows]
print("Testing 5 URLs...\n")

# Approach 1: urllib with minimal headers
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for i, url in enumerate(urls):
    print(f"[{i+1}] {url[:100]}...")
    
    # Try 1: urllib with Chrome UA
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
            print(f"  -> urllib OK: {len(data)} bytes, status={resp.status}")
    except Exception as e:
        print(f"  -> urllib FAIL: {e}")
    
    # Try 2: urllib with Facebook referer
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.facebook.com/",
        })
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
            print(f"  -> urllib+referer OK: {len(data)} bytes")
    except Exception as e:
        print(f"  -> urllib+referer FAIL: {e}")
    
    # Try 3: requests library
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.facebook.com/",
        }
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        ct = resp.headers.get("content-type", "?")
        print(f"  -> requests: status={resp.status_code}, content-type={ct}, size={len(resp.content)}")
    except Exception as e:
        print(f"  -> requests FAIL: {e}")
    
    print()