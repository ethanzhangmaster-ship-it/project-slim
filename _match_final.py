"""终极匹配：Facebook 视频 → Eagle P4 文件

方案：
1. 读取 Facebook 视频 (video_id + duration from video_objects)
2. 读取 Eagle P4 文件 (duration from ffprobe)
3. 按时长 ±0.5s 匹配
4. 按分辨率 (1X1/9X16/16X9) + 创建时间 + 文件名关键词 辅助验证
5. 输出匹配结果 CSV
"""
import json, re
from collections import defaultdict
from pathlib import Path
from difflib import SequenceMatcher

OUT = Path("output/video_intelligence/p04")

# ── 1. 加载 Facebook 视频数据 ──
fb_videos = json.loads((OUT / "facebook_video_objects_full.json").read_text(encoding="utf-8"))

# 构建 fb_duration_map: video_id → {duration, title, created_time, thumbnail, permalink_url}
fb_dur_map = {}
for vid, v in fb_videos.items():
    d = v.get("length")
    if d:
        fb_dur_map[vid] = {
            "fb_video_id": vid,
            "fb_duration": round(float(d), 2),
            "fb_title": v.get("title", ""),
            "fb_created": v.get("created_time", ""),
            "fb_thumbnail": v.get("picture", ""),
            "fb_permalink": v.get("permalink_url", ""),
        }

print(f"Facebook 视频（有时长信息）: {len(fb_dur_map)}")

# ── 2. 加载 Facebook creative ↔ video_id 映射 ──
fb_creative_video = {}
fb_raw = json.loads((OUT / "facebook_creatives_raw.json").read_text(encoding="utf-8"))
for cid, cr in fb_raw.items():
    vid = cr.get("video_id", "")
    if vid:
        fb_creative_video[cid] = vid

fb_full = json.loads((OUT / "facebook_creatives_full_export.json").read_text(encoding="utf-8"))
# Also get creative_name from the full export
creative_name_map = {}
creative_ad_map = {}
for f in fb_full:
    cid = f["creative_id"]
    creative_name_map[cid] = f.get("creative_name", "")
    creative_ad_map[cid] = f.get("ad_id", "")

# ── 3. 加载 Eagle P4 文件 ──
eagle = json.loads((OUT / "eagle_assets_full_scan.json").read_text(encoding="utf-8"))
p4_files = [e for e in eagle if e.get("metadata") and e["metadata"].get("name","").startswith("P4-")]

print(f"Eagle P4 视频文件: {len(p4_files)}")

# Build Eagle index by duration
eagle_by_dur = defaultdict(list)
for e in p4_files:
    dur = e.get("duration")
    if dur:
        rounded = round(float(dur), 1)
        eagle_by_dur[rounded].append(e)

# ── 4. 匹配：每个 Facebook video_id → 找最匹配的 Eagle 文件 ──
def parse_ratio(name):
    m = re.search(r'(1X1|9X16|16X9)', name)
    return m.group(1) if m else None

def parse_content_type(name):
    for t in ["wanfashipin","wanfazhanshi","kaitou","bianshen","fudan"]:
        if t in name: return t
    return "other"

def name_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

matches = []
unmatched = []

for vid, fb_v in fb_dur_map.items():
    fb_dur = fb_v["fb_duration"]
    fb_title = fb_v.get("fb_title", "").lower()
    fb_created = fb_v.get("fb_created", "")
    
    candidates = []
    
    # 找时长 ±0.5s 内的 Eagle 文件
    for eagle_dur, entries in eagle_by_dur.items():
        if abs(eagle_dur - fb_dur) <= 0.6:
            for e in entries:
                eagle_name = e["metadata"]["name"]
                ratio = parse_ratio(eagle_name)
                content_type = parse_content_type(eagle_name)
                
                # 计算综合匹配分数
                score = 0.0
                
                # 基础分数：时长匹配
                dur_diff = abs(eagle_dur - fb_dur)
                score = 1.0 - (dur_diff * 2)  # 0.1s diff → 0.8, 0.5s diff → 0
                
                # 加分：标题关键词匹配
                if "magic" in eagle_name and "magic" in fb_title: score += 0.1
                if "witch" in eagle_name and ("witch" in fb_title or "magic" in fb_title): score += 0.1
                if "merge" in eagle_name and "merge" in fb_title: score += 0.1
                
                # 加分：content type 匹配
                if "wanfashipin" in eagle_name and "game" in fb_title: score += 0.05
                if "kaitou" in eagle_name and ("level" in fb_title or "start" in fb_title): score += 0.05
                
                candidates.append({
                    "eagle_file": e["file_name"],
                    "eagle_name": eagle_name,
                    "eagle_duration": eagle_dur,
                    "ratio": ratio,
                    "content_type": content_type,
                    "score": round(score, 4),
                    "duration_diff": round(dur_diff, 2),
                })
    
    if candidates:
        # 按分数排序
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        best["fb_video_id"] = vid
        best["fb_duration"] = fb_dur
        best["fb_title"] = fb_v.get("fb_title", "")
        best["fb_created"] = fb_created
        best["candidate_count"] = len(candidates)
        matches.append(best)
    else:
        unmatched.append({"fb_video_id": vid, "fb_duration": fb_dur, "fb_title": fb_v.get("fb_title","")})

print(f"\n匹配结果:")
print(f"  找到匹配: {len(matches)}/{len(fb_dur_map)}")
print(f"  未匹配: {len(unmatched)}")

# 按分数显示 Top 20
matches.sort(key=lambda x: x["score"], reverse=True)
print(f"\n{'='*100}")
print(f"Top 20 匹配 (按时长)")
print(f"{'='*100}")
print(f"{'FB视频ID':>18} | {'FB时长':>6} | {'FB标题':<35} | {'匹配度':>5} | {'Eagle文件':<50} | {'Eagle时长':>6}")
print(f"{'-'*18}-+-{'-'*6}-+-{'-'*35}-+-{'-'*5}-+-{'-'*50}-+-{'-'*6}")
for m in matches[:20]:
    print(f"{m['fb_video_id']:>18} | {m['fb_duration']:>5.1f} | {m['fb_title'][:35]:<35} | {m['score']:>5.2f} | {m['eagle_name'][:50]:<50} | {m['eagle_duration']:>5.1f}")

# ── 5. 现在用广告 Ad 名进一步缩小范围 ──
# 读取完整报告 CSV，获取 video_id → ad_name → campaign → 账号
import csv
rows = []
with open(OUT / "p4_videos_full_report.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader: rows.append(r)

# 构建: video_id → {platform, campaign, ad_name, spend}
video_ad_info = defaultdict(list)
for r in rows:
    vid = r.get("视频ID", "")
    if not vid: continue
    video_ad_info[vid].append({
        "platform": "Android" if "Android" in (r.get("账号","") or "") else "iOS",
        "account": r.get("账号",""),
        "campaign": r.get("Campaign",""),
        "ad_name": r.get("广告名",""),
        "ad_spend": float(r.get("该广告消费($)",0) or 0),
    })

# 标记匹配是否与平台一致
for m in matches:
    vid = m["fb_video_id"]
    ad_infos = video_ad_info.get(vid, [])
    platforms = set(a["platform"] for a in ad_infos)
    eagle_name = m["eagle_name"].lower()
    
    # 当前匹配的 Eagle file 没区分平台
    # 但我们可以看 Eagle 文件名中是否有 Android/iOS 相关信息
    # （Eagle 命名不含平台信息，所以这一步只做记录）
    
    m["platforms"] = ",".join(platforms) if platforms else "unknown"
    m["total_ad_spend"] = sum(a["ad_spend"] for a in ad_infos)

# ── 6. 输出完整匹配结果 ──
# 按消费排序，给出高质量匹配
print(f"\n{'='*100}")
print(f"Top 15 高质量匹配（消费 > $100 且匹配度 > 0.9）")
print(f"{'='*100}")

high_quality = [m for m in matches if m["score"] >= 0.9 and m.get("total_ad_spend",0) > 100]
high_quality.sort(key=lambda x: x["total_ad_spend"], reverse=True)

print(f"{'FB时长':>6} | {'匹配度':>5} | {'FB标题':<35} | {'Eagle文件':<55} | {'消费':>8} | {'平台':>10}")
print(f"{'-'*6}-+-{'-'*5}-+-{'-'*35}-+-{'-'*55}-+-{'-'*8}-+-{'-'*10}")
for m in high_quality[:15]:
    print(f"{m['fb_duration']:>5.1f} | {m['score']:>5.2f} | {m['fb_title'][:35]:<35} | {m['eagle_name'][:55]:<55} | ${m['total_ad_spend']:>6,.0f} | {m['platforms']:>10}")

# ── 7. 保存完整映射 ──
output = {
    "total_fb_videos": len(fb_dur_map),
    "total_eagle_p4": len(p4_files),
    "matched": len(matches),
    "unmatched": len(unmatched),
    "matches": matches,
    "unmatched_videos": unmatched,
}
(OUT / "fb_to_eagle_mapping.json").write_text(
    json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
)

# 保存 CSV 映射
with open(OUT / "fb_to_eagle_mapping.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["FB视频ID","FB时长","FB标题","FB创建时间","匹配度","时长差","Eagle名称","Eagle时长","比例","内容类型","候选数","平台","总消费"])
    for m in sorted(matches, key=lambda x: x["score"], reverse=True):
        w.writerow([m["fb_video_id"], m["fb_duration"], m["fb_title"], m["fb_created"],
                    m["score"], m["duration_diff"], m["eagle_name"], m["eagle_duration"],
                    m.get("ratio",""), m.get("content_type",""), m["candidate_count"],
                    m.get("platforms",""), m.get("total_ad_spend",0)])

print(f"\n✅ 已保存:")
print(f"  {OUT / 'fb_to_eagle_mapping.json'}")
print(f"  {OUT / 'fb_to_eagle_mapping.csv'}")

# ── 总结 ──
print(f"\n{'='*70}")
print(f"📊 匹配总结")
print(f"{'='*70}")
print(f"  总视频: {len(fb_dur_map)} FB vs {len(p4_files)} Eagle")
print(f"  时长匹配: {len(matches)}/{len(fb_dur_map)} ({len(matches)/max(len(fb_dur_map),1)*100:.0f}%)")
print(f"  未匹配: {len(unmatched)}")
print(f"  高质量匹配(>0.9): {len(high_quality)}")
print(f"\n  注意: 时长匹配只能找到候选，不能保证 1:1 正确")
print(f"  同一个时长的 Eagle 文件有多个候选时，需要人工确认")
print(f"  CSV 文件可以用 Excel 打开，按匹配度排序查看")
