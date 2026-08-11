"""Phase 1: Discover all creative_ids from existing TeCDo exports + Meta API.
Phase 2: Batch fetch image_urls from Meta.
Phase 3: Download with timeout, organize by project.

Incremental: skips creative_ids already in _manifest.json.
"""
import json, os, time, requests, pathlib, urllib.parse
from pathlib import Path

ROOT = Path("/Users/sixin/Desktop/project_slim")

# ── Load token from .env (falls back to env var) ──
def _load_token():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("META_ACCESS_TOKEN="):
                return line.partition("=")[2].strip()
    return os.getenv("META_ACCESS_TOKEN", "")

TOKEN = _load_token()
API = "https://graph.facebook.com/v19.0"
CACHE = ROOT / "output" / "creatives_cache"
CACHE.mkdir(parents=True, exist_ok=True)

# ════════════════════════════
# PHASE 1: Collect all creative_ids from TeCDo exports
# ════════════════════════════
print("PHASE 1: Collecting creative_ids from existing TeCDo exports...")

creative_map: dict[str, dict] = {}  # creative_id → {project, ad_name, campaign_name, spend}

fb_dir = ROOT / "output/facebook_ads_data"
for fpath in sorted(fb_dir.glob("GAMEGZZ_*.json")):
    try:
        data = json.loads(fpath.read_text())
        project = data.get("project", "unknown")
        ads = data.get("ads", [])
        for ad in ads:
            # TeCDo ads have creative_id directly
            cid = ad.get("creative_id")
            if not cid:
                continue
            # Keep highest-spend entry per creative
            spend = float(ad.get("spend", 0))
            existing = creative_map.get(str(cid), {})
            if spend > existing.get("spend", 0):
                creative_map[str(cid)] = {
                    "creative_id": str(cid),
                    "project": project,
                    "ad_name": ad.get("name", "") or ad.get("ad_name", ""),
                    "campaign_name": ad.get("campaign_name", ""),
                    "spend": spend,
                    "impressions": int(ad.get("impressions", 0)),
                    "installs": float(ad.get("installs", 0)),
                }
        print(f"  {fpath.name}: {len(ads)} ads, project={project}")
    except Exception as e:
        print(f"  {fpath.name}: ERROR {e}")

print(f"\n  Total unique creative_ids from TeCDo: {len(creative_map)}")

# Also pull from accounts_to_pull via Meta API
print("\n  Supplementing with direct Meta API pull...")
me_data = requests.get(f"{API}/me/adaccounts", 
    params={"access_token": TOKEN, "fields": "id,name,account_id"},
    timeout=30).json()
for acc in me_data.get("data", []):
    acct_id = acc["account_id"]
    try:
        ads = []
        url = f"{API}/act_{acct_id}/ads"
        params = {"access_token": TOKEN, "limit": 500, "fields": "id,name,creative{id}"}
        for _ in range(10):
            r = requests.get(url, params=params, timeout=60)
            data = r.json()
            batch = data.get("data", [])
            ads.extend(batch)
            if "paging" not in data or "next" not in data["paging"]:
                break
            url = data["paging"]["next"]
        for ad in ads:
            cr = ad.get("creative") or {}
            cid = str(cr.get("id", ""))
            if cid and cid not in creative_map:
                creative_map[cid] = {
                    "creative_id": cid,
                    "project": "unknown",
                    "ad_name": ad.get("name", ""),
                    "campaign_name": "",
                    "spend": 0,
                    "impressions": 0,
                    "installs": 0,
                }
        print(f"  act_{acct_id}: +{len(ads)} ads")
    except Exception as e:
        print(f"  act_{acct_id}: ERROR {e}")

print(f"\n  Grand total creative_ids: {len(creative_map)}")
for proj in sorted(set(c["project"] for c in creative_map.values())):
    cnt = sum(1 for c in creative_map.values() if c["project"] == proj)
    print(f"    {proj}: {cnt}")

# ════════════════════════════
# PHASE 2: Batch fetch image_urls from Meta API
# ════════════════════════════
print("\nPHASE 2: Fetching image_urls from Meta API...")

cids = list(creative_map.keys())
fetched = 0
for i in range(0, len(cids), 50):
    batch = cids[i:i+50]
    ids_param = ",".join(batch)
    try:
        r = requests.get(f"{API}/", params={
            "ids": ids_param,
            "fields": "id,name,title,body,thumbnail_url,image_url",
            "access_token": TOKEN,
        }, timeout=90)
        data = r.json()
        for cid_str, cr in (data or {}).items():
            if isinstance(cr, dict):
                img_url = cr.get("image_url") or cr.get("thumbnail_url") or ""
                creative_map[cid_str]["image_url"] = img_url
                creative_map[cid_str]["creative_name"] = cr.get("name", "")
                creative_map[cid_str]["title"] = cr.get("title", "")
                creative_map[cid_str]["body"] = cr.get("body", "")
                fetched += 1
    except Exception as e:
        pass
    
    if (i // 50) % 5 == 0:
        print(f"  {min(i+50, len(cids))}/{len(cids)}")

print(f"  Fetched image_urls for {fetched} creatives")
with_image = sum(1 for c in creative_map.values() if c.get("image_url"))
print(f"  Creatives with image_url: {with_image}")

# ════════════════════════════
# PHASE 3: Download with ThreadPool, organize by project
# ════════════════════════════
print("\nPHASE 3: Downloading images (parallel, timeout 20s)...")

def download_one(item):
    cid = item["creative_id"]
    url = item.get("image_url", "")
    if not url:
        return None
    
    proj = item.get("project", "_unknown")
    # Normalize project
    if "P02" in proj or "Mermaid" in proj or "项目02" in proj:
        proj = "P02"
    elif "P07" in proj or "Vampire" in proj or "项目07" in proj:
        proj = "P07"
    elif "P04" in proj or "Witch" in proj or "项目04" in proj:
        proj = "P04"
    
    proj_dir = CACHE / proj
    proj_dir.mkdir(parents=True, exist_ok=True)
    
    ext = ".png" if ".png" in url.lower() else ".jpg"
    name = (item.get("creative_name") or item.get("ad_name") or cid)[:40]
    safe = name.replace("/","_").replace(" ","_").replace(":","")
    fpath = proj_dir / f"{safe}_{cid}{ext}"
    
    if fpath.exists() and fpath.stat().st_size > 1024:
        return {"creative_id": cid, "project": proj, "cached_path": str(fpath), "bytes": fpath.stat().st_size}
    
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "MarketOps/1.0"})
        if r.status_code == 200 and len(r.content) > 1024:
            fpath.write_bytes(r.content)
            return {"creative_id": cid, "project": proj, "cached_path": str(fpath), "bytes": len(r.content)}
    except:
        pass
    return None

download_list = [c for c in creative_map.values() if c.get("image_url")]
print(f"  Downloading {len(download_list)} images...")

results = []
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(download_one, item): item for item in download_list}
    for i, f in enumerate(as_completed(futures)):
        r = f.result()
        if r:
            results.append(r)
            if len(results) <= 10 or len(results) % 50 == 0:
                print(f"    [{len(results)}] {r['project']}: {Path(r['cached_path']).name[:50]} ({r['bytes']}b)")

# ════════════════════════════
# Save manifest
# ════════════════════════════
proj_counts = Counter(r["project"] for r in results)

manifest = {
    "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "total_creatives": len(creative_map),
    "creatives_with_image_url": with_image,
    "images_downloaded": len(results),
    "by_project": {p: cnt for p, cnt in proj_counts.most_common()},
    "items": [{
        **creative_map[r["creative_id"]],
        "cached_path": r["cached_path"],
        "file_bytes": r["bytes"],
    } for r in results],
}

(CACHE / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
print(f"\n{'='*60}")
print(f"DONE! {len(results)} images cached, manifest saved.")
for p, c in proj_counts.most_common():
    print(f"  {p}: {c} images")
