"""下载 Winner 图片用于视觉分析"""
import json, os, requests

dna_path = r"c:\Users\ethan\Downloads\project_slim\output\creative_analysis\dna_cache\winners_dna.json"
output_dir = r"c:\Users\ethan\Downloads\project_slim\output\creative_analysis\winner_images"
os.makedirs(output_dir, exist_ok=True)

with open(dna_path, 'r', encoding='utf-8') as f:
    winners = json.load(f)

print(f"下载 {len(winners)} 张 Winner 图片...")
for i, w in enumerate(winners):
    url = w.get("_cdn_url", "")
    creative_id = w.get("creative_id", f"unknown_{i}")
    if not url:
        continue
    
    filepath = os.path.join(output_dir, f"winner_{i+1}_{creative_id}.png")
    if os.path.exists(filepath):
        print(f"  已存在: {filepath}")
        continue
    
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            print(f"  ✅ 下载: {filepath}")
        else:
            print(f"  ❌ 失败: {url} status={r.status_code}")
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n完成！")
