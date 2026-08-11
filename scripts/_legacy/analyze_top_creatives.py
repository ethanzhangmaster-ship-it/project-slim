#!/usr/bin/env python3
"""分析 facebook_fresh_data.json：按真实指标给创意排名，并关联本地图片。

用法:
  python scripts/analyze_top_creatives.py

输出:
  output/top_creatives_report.md      排名报告（含 Top CTR / Top installs）
  output/top_creatives.csv            全量创意指标 + 是否有本地图
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = ROOT / "output" / "facebook_fresh_data.json"
IMG_DIR = ROOT / "output" / "facebook_top_creatives"
REPORT = ROOT / "output" / "top_creatives_report.md"
CSV_OUT = ROOT / "output" / "top_creatives.csv"

MIN_IMP = 5000  # 排名所需最小曝光，保证统计置信度


def main() -> int:
    if not JSON_FILE.exists():
        print(f"❌ 找不到 {JSON_FILE}，请先运行 fetch_facebook_full.py")
        return 1

    raw = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    data = raw.get("data", [])
    print(f"加载 {len(data)} 条记录")

    # 1) 按 creative_id 聚合
    agg = defaultdict(lambda: {
        "imp": 0, "clk": 0, "spend": 0.0, "installs": 0,
        "name": "", "title": "", "n_ads": 0, "campaigns": set(),
        "first": "", "last": "", "image_url": "", "thumbnail_url": "",
    })
    for row in data:
        cid = str(row.get("creative_id", "")).strip()
        if not cid:
            continue
        a = agg[cid]
        a["imp"] += int(row.get("impressions", 0))
        a["clk"] += int(row.get("clicks", 0))
        a["spend"] += float(row.get("spend", 0))
        # installs
        for act in (row.get("actions") or []):
            if act.get("action_type") in ("mobile_app_install", "app_install", "omni_app_install"):
                try:
                    a["installs"] += int(float(act.get("value", 0)))
                except (ValueError, TypeError):
                    pass
        if not a["name"]:
            a["name"] = row.get("creative_name", "")
        if not a["title"]:
            a["title"] = row.get("title", "")
        if not a["image_url"]:
            a["image_url"] = row.get("image_url", "")
        if not a["thumbnail_url"]:
            a["thumbnail_url"] = row.get("thumbnail_url", "")
        a["n_ads"] += 1
        a["campaigns"].add(row.get("campaign_name", ""))
        ds = row.get("date_start", "")
        if ds:
            a["first"] = ds if not a["first"] or ds < a["first"] else a["first"]
            a["last"] = ds if not a["last"] or ds > a["last"] else a["last"]

    # 2) 关联本地图片：文件名尾号匹配 creative_id 末 6 位
    def has_local_image(cid: str) -> str:
        suffix = cid[-6:]
        for m in IMG_DIR.glob(f"*_{suffix}.*"):
            try:
                if m.stat().st_size >= 1500:  # 排除 <1KB 下载失败残留
                    return str(m)
            except OSError:
                continue
        return ""

    rows = []
    for cid, a in agg.items():
        imp = a["imp"]
        ctr = (a["clk"] / imp) if imp else 0.0
        cpi = (a["spend"] / a["installs"]) if a["installs"] else 0.0
        ipm = (a["installs"] / imp * 1000) if imp else 0.0
        local = has_local_image(cid)
        rows.append({
            "creative_id": cid,
            "name": a["name"],
            "title": a["title"],
            "impressions": imp,
            "clicks": a["clk"],
            "ctr_pct": round(ctr * 100, 4),
            "installs": a["installs"],
            "ipm": round(ipm, 3),
            "spend": round(a["spend"], 2),
            "cpi": round(cpi, 3),
            "n_ads": a["n_ads"],
            "campaigns": ";".join(sorted(c for c in a["campaigns"] if c)),
            "first": a["first"], "last": a["last"],
            "has_image": bool(local),
            "image_path": local,
        })

    # 3) 排名
    def by_ctr(r):
        return r["ctr_pct"] if r["impressions"] >= MIN_IMP else -1
    by_installs = sorted(rows, key=lambda r: r["installs"], reverse=True)
    by_ctr_sorted = sorted([r for r in rows if r["impressions"] >= MIN_IMP],
                           key=by_ctr, reverse=True)

    # 4) 写出 CSV
    cols = ["creative_id", "name", "title", "impressions", "clicks", "ctr_pct",
            "installs", "ipm", "spend", "cpi", "n_ads", "campaigns",
            "first", "last", "has_image", "image_path"]
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["impressions"], reverse=True):
            w.writerow(r)

    # 5) 报告
    total = len(rows)
    with_img = sum(1 for r in rows if r["has_image"])
    with_perf = sum(1 for r in rows if r["impressions"] >= MIN_IMP)
    with_perf_img = sum(1 for r in rows if r["impressions"] >= MIN_IMP and r["has_image"])

    md = []
    md.append("# Facebook 创意排名报告（真实投放数据）\n")
    md.append(f"- 数据窗口: {raw.get('date_range')}")
    md.append(f"- 总创意数（去重）: **{total}**")
    md.append(f"- 有本地图片的创意: **{with_img}** ({with_img/total*100:.1f}%)")
    md.append(f"- 达统计置信度（imp≥{MIN_IMP}）的创意: **{with_perf}**")
    md.append(f"-  其中「有本地图片」可对比的: **{with_perf_img}**\n")

    md.append("## 🏆 Top 25 按 CTR（imp≥%d，有图优先）\n" % MIN_IMP)
    md.append("| # | CTR% | Imp | Installs | CPI | 有图 | 创意名 | 标题 |")
    md.append("|---|------|-----|----------|-----|------|--------|------|")
    for i, r in enumerate(by_ctr_sorted[:25], 1):
        flag = "✅" if r["has_image"] else "—"
        md.append(f"| {i} | {r['ctr_pct']:.3f} | {r['impressions']:,} | "
                  f"{r['installs']:,} | {r['cpi']:.2f} | {flag} | "
                  f"{r['name'][:28]} | {r['title'][:24]} |")

    md.append("\n## 🔥 Top 25 按 Installs\n")
    md.append("| # | Installs | CTR% | Imp | CPI | 有图 | 创意名 |")
    md.append("|---|----------|------|-----|-----|------|--------|")
    for i, r in enumerate(by_installs[:25], 1):
        flag = "✅" if r["has_image"] else "—"
        md.append(f"| {i} | {r['installs']:,} | {r['ctr_pct']:.3f} | "
                  f"{r['impressions']:,} | {r['cpi']:.2f} | {flag} | {r['name'][:28]} |")

    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n✅ 报告: {REPORT}")
    print(f"✅ CSV:  {CSV_OUT}")
    print(f"\n总创意 {total} | 有图 {with_img} | 达置信度 {with_perf} | 可对比 {with_perf_img}")
    print("Top CTR #1:", by_ctr_sorted[0]["ctr_pct"], "%", by_ctr_sorted[0]["name"][:30]) if by_ctr_sorted else print("无达置信度创意")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
