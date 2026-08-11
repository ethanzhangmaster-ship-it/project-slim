"""验证广告状态"""
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

result_file = ROOT / "output/closed_loop/publish_results/publish_closed_loop_20260630_154336.json"
result = json.loads(result_file.read_text(encoding="utf-8"))

token = os.getenv("META_ACCESS_TOKEN", "")
api_version = os.getenv("META_API_VERSION", "v19.0")
BV = f"https://graph.facebook.com/{api_version}"

print(f"✅ 验证 {len(result['ad_ids'])} 个广告...")
all_ok = True
for ad_id in result["ad_ids"]:
    r = requests.get(f"{BV}/{ad_id}", params={
        "access_token": token,
        "fields": "id,name,status,effective_status"
    })
    if r.status_code == 200:
        d = r.json()
        st = d.get("effective_status") or d.get("status", "?")
        print(f"  ✅ {ad_id}: status={st}, name={d.get('name', '?')[:40]}")
    else:
        print(f"  ⚠️  {ad_id}: {r.status_code}")
        all_ok = False

print(f"\n{'✅' if all_ok else '⚠️ '} 广告已在 Facebook 后台")