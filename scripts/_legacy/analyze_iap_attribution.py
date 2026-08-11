#!/usr/bin/env python3
"""真正的 IAP 素材归因分析 — 赢家 vs 输家 视觉DNA 对比

数据源:
  - 本地图片: D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04\ (270张)
  - 投放数据: DuckDB creative_performance (228张可关联)
  - 视觉分析: Lovart describe_image()

流程:
  1. 加载所有本地图片, 关联 DuckDB IAP 数据
  2. 按 IAP 综合评分排序 (CPI 35% + IPM 20% + CTR 15% + ROAS 20% + 规模 10%)
  3. 选出 TOP 10 赢家 + BOTTOM 10 输家
  4. 用 Lovart 分析每张图的视觉DNA
  5. 交叉对比: 赢家共同特征 vs 输家共同特征
  6. 输出归因报告 + 下一代素材生成建议
"""
from __future__ import annotations

import json, os, re, sys, time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.clients.lovart import LovartClient


def load_and_score_images():
    """加载本地图片 + DuckDB 数据, 返回按 IAP 评分排序的列表"""
    img_dir = Path(r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04")
    conn = duckdb.connect(str(ROOT / "db" / "facebook_performance.duckdb"), read_only=True)

    # 收集本地图片
    local_images = {}
    for f in img_dir.rglob("*.png"):
        match = re.search(r"_(\d{10,25})\.png$", f.name)
        if match:
            local_images[match.group(1)] = str(f)

    print(f"本地图片: {len(local_images)} 张")

    # 关联 DuckDB
    results = []
    for cid, path in local_images.items():
        r = conn.execute("""
            SELECT SUM(spend), SUM(install), SUM(impression), SUM(click),
                   CASE WHEN SUM(impression)>0 THEN SUM(click)*100.0/SUM(impression) ELSE 0 END as ctr,
                   CASE WHEN SUM(spend)>0 THEN SUM(install)/SUM(spend) ELSE 0 END as cpi_rate,
                   CASE WHEN SUM(impression)>0 THEN SUM(install)*1000.0/SUM(impression) ELSE 0 END as ipm,
                   CASE WHEN SUM(spend)>0 THEN SUM(roas_d7*spend)/NULLIF(SUM(spend),0) ELSE 0 END as roas_d7
            FROM creative_performance WHERE creative_id = ?
        """, [cid]).fetchone()

        if not r or not r[0] or r[0] < 50:  # spend ≥ $50
            continue

        results.append({
            "creative_id": cid,
            "image_path": path,
            "spend": r[0], "installs": r[1], "impression": r[2], "click": r[3],
            "ctr": r[4] or 0, "cpi_rate": r[5] or 0, "ipm": r[6] or 0, "roas_d7": r[7] or 0,
        })

    conn.close()

    # 计算中位数用于归一化
    all_cpi = [d["cpi_rate"] for d in results if d["cpi_rate"] > 0]
    all_ipm = [d["ipm"] for d in results if d["ipm"] > 0]
    all_ctr = [d["ctr"] for d in results if d["ctr"] > 0]
    all_roas = [d["roas_d7"] for d in results if d["roas_d7"] > 0]
    all_inst = [d["installs"] for d in results]

    def med(vals):
        s = sorted(vals)
        return s[len(s)//2] if s else 0

    cpi_med, ipm_med, ctr_med, roas_med, inst_med = med(all_cpi), med(all_ipm), med(all_ctr), med(all_roas) or 0.05, med(all_inst)

    # IAP 综合评分
    for d in results:
        cpi_s = min(1.0, cpi_med / max(d["cpi_rate"], 1e-6)) if d["cpi_rate"] > 0 else 0.5
        ipm_s = min(1.0, d["ipm"] / max(ipm_med, 1e-6)) if ipm_med > 0 else 0.5
        ctr_s = min(1.0, d["ctr"] / max(ctr_med, 1e-6)) if ctr_med > 0 else 0.5
        roas_s = min(1.0, d["roas_d7"] / max(roas_med, 1e-6)) if d["roas_d7"] > 0 else 0.3
        inst_s = min(1.0, d["installs"] / max(inst_med, 1e-6)) if inst_med > 0 else 0.5
        d["iap_score"] = cpi_s * 0.35 + ipm_s * 0.20 + ctr_s * 0.15 + roas_s * 0.20 + inst_s * 0.10

    results.sort(key=lambda x: x["iap_score"], reverse=True)
    print(f"可关联且 spend≥$50: {len(results)} 张")
    print(f"CPI 中位数: ${1/cpi_med:.1f}" if cpi_med > 0 else "CPI 中位数: N/A")
    print(f"ROAS D7 中位数: {roas_med:.4f}")

    return results


def analyze_with_lovart(images, label, client, cache_file):
    """用 Lovart 分析一组图片的视觉DNA, 支持缓存"""
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if len(cached) == len(images):
            print(f"  [{label}] 从缓存加载 {len(cached)} 条分析")
            return cached

    results = []
    for i, img in enumerate(images):
        print(f"  [{label}] {i+1}/{len(images)}: {Path(img['image_path']).name[:50]}...")
        try:
            dna = client.describe_image(img["image_path"], project="P04 Witch")
            dna["creative_id"] = img["creative_id"]
            dna["iap_score"] = img["iap_score"]
            dna["spend"] = img["spend"]
            dna["roas_d7"] = img["roas_d7"]
            dna["cpi_rate"] = img["cpi_rate"]
            dna["ctr"] = img["ctr"]
            dna["installs"] = img["installs"]
            results.append(dna)
            time.sleep(0.5)  # 避免 rate limit
        except Exception as e:
            print(f"    ❌ 失败: {e}")
            results.append({"error": str(e), "creative_id": img["creative_id"]})

    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    return results


def compare_dna(winners_dna, losers_dna):
    """对比赢家和输家的视觉DNA, 找出关键差异"""
    print("\n" + "=" * 70)
    print("  赢家 vs 输家 视觉DNA 对比")
    print("=" * 70)

    # 提取有效分析
    def valid(dna_list):
        return [d for d in dna_list if "error" not in d]

    w = valid(winners_dna)
    l = valid(losers_dna)

    # 字符串特征对比
    str_features = ["subject", "composition", "palette", "lighting", "mood", "hook_type", "overall_summary"]
    
    for feat in str_features:
        w_vals = Counter(d.get(feat, "(无)") for d in w)
        l_vals = Counter(d.get(feat, "(无)") for d in l)
        print(f"\n  [{feat}]")
        print(f"    赢家 TOP3: {w_vals.most_common(3)}")
        print(f"    输家 TOP3: {l_vals.most_common(3)}")

    # 列表特征对比
    list_features = ["ui_elements", "standout_features"]
    for feat in list_features:
        w_all = []
        l_all = []
        for d in w:
            w_all.extend(d.get(feat, []))
        for d in l:
            l_all.extend(d.get(feat, []))
        w_counter = Counter(w_all)
        l_counter = Counter(l_all)
        print(f"\n  [{feat}]")
        print(f"    赢家 TOP5: {w_counter.most_common(5)}")
        print(f"    输家 TOP5: {l_counter.most_common(5)}")

    # 生成洞察
    insights = []
    
    # 赢家独有的高频特征
    w_set = set(w_counter.keys())
    l_set = set(l_counter.keys())
    winner_only = w_set - l_set
    loser_only = l_set - w_set

    if winner_only:
        print(f"\n  🟢 赢家独有元素: {winner_only}")
    if loser_only:
        print(f"\n  🔴 输家独有元素: {loser_only}")

    # mood 差异
    w_moods = Counter(d.get("mood", "") for d in w)
    l_moods = Counter(d.get("mood", "") for d in l)
    for mood, cnt in w_moods.most_common(3):
        l_cnt = l_moods.get(mood, 0)
        if cnt > l_cnt * 2:
            insights.append(f"赢家氛围倾向 '{mood}' ({cnt} vs {l_cnt})")

    return insights


def main():
    print("=" * 70)
    print("  IAP 素材归因分析 — 赢家 vs 输家 视觉DNA")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Step 1: 加载 + 评分
    scored = load_and_score_images()
    if not scored:
        print("❌ 无可分析数据")
        return

    top_n = min(10, len(scored) // 5)
    bottom_n = min(10, len(scored) // 5)

    winners = scored[:top_n]
    losers = scored[-bottom_n:]

    print(f"\n🏆 赢家 (TOP {top_n}):")
    for d in winners:
        cpi_str = f"${1/d['cpi_rate']:.1f}" if d['cpi_rate'] > 0 else "?"
        print(f"  {d['iap_score']:.3f} | spend=${d['spend']:,.0f} | CPI={cpi_str} | ROAS={d['roas_d7']:.3f} | {Path(d['image_path']).name[:50]}")

    print(f"\n💀 输家 (BOTTOM {bottom_n}):")
    for d in losers:
        cpi_str = f"${1/d['cpi_rate']:.1f}" if d['cpi_rate'] > 0 else "?"
        print(f"  {d['iap_score']:.3f} | spend=${d['spend']:,.0f} | CPI={cpi_str} | ROAS={d['roas_d7']:.3f} | {Path(d['image_path']).name[:50]}")

    # Step 2: Lovart 视觉分析
    print(f"\n{'='*70}")
    print(f"  Lovart 视觉DNA 分析")
    print(f"{'='*70}")

    client = LovartClient()
    cache_dir = ROOT / "output" / "creative_analysis" / "dna_cache"

    winners_dna = analyze_with_lovart(winners, "赢家", client, str(cache_dir / "winners_dna.json"))
    losers_dna = analyze_with_lovart(losers, "输家", client, str(cache_dir / "losers_dna.json"))

    # Step 3: 对比分析
    insights = compare_dna(winners_dna, losers_dna)

    # Step 4: 生成建议
    print("\n" + "=" * 70)
    print("  📝 下一代素材生成建议")
    print("=" * 70)

    valid_w = [d for d in winners_dna if "error" not in d]
    if valid_w:
        # 赢家共性
        common_subject = Counter(d.get("subject", "") for d in valid_w).most_common(1)[0][0] if valid_w else ""
        common_palette = Counter(d.get("palette", "") for d in valid_w).most_common(1)[0][0] if valid_w else ""
        common_mood = Counter(d.get("mood", "") for d in valid_w).most_common(1)[0][0] if valid_w else ""
        common_composition = Counter(d.get("composition", "") for d in valid_w).most_common(1)[0][0] if valid_w else ""

        print(f"\n  赢家DNA 共性:")
        print(f"    主题方向: {common_subject[:100]}")
        print(f"    色调: {common_palette}")
        print(f"    氛围: {common_mood}")
        print(f"    构图: {common_composition}")

        # 基于赢家DNA的 prompt 建议
        print(f"\n  推荐 prompt 模板:")
        print(f"    \"Mobile game ad, {common_subject[:80]}, {common_composition[:80]}, ")
        print(f"     {common_palette}, {common_mood} mood, 1:1 square\"")

    print(f"\n  关键洞察:")
    for ins in insights:
        print(f"    • {ins}")

    # 保存完整报告
    report_path = ROOT / "output" / "creative_analysis" / f"iap_attribution_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "winners": [{k: v for k, v in d.items() if k != "image_path"} for d in winners],
        "losers": [{k: v for k, v in d.items() if k != "image_path"} for d in losers],
        "winners_dna": winners_dna,
        "losers_dna": losers_dna,
        "insights": insights,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  完整报告: {report_path}")


if __name__ == "__main__":
    main()
