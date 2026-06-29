#!/usr/bin/env python3
"""FinalBandit Production Pipeline — 一键执行

完整流程:
  Step 1: 数据导入 (creative_library + creative_features)
  Step 2: 特征构建 → variant 表
  Step 3: FinalBandit 学习 (7 天模拟 backfill)
  Step 4: 投放策略输出
  Step 5: Monitor 快照 → Dashboard 数据

用法:
  python3 scripts/run_pipeline.py
  python3 scripts/run_pipeline.py --days 14
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.final_bandit import FinalBandit
from market_ops.creative_intelligence.monitor import FinalBanditMonitor


# ============================================================================
# Step 1: 数据导入
# ============================================================================

def step1_import_data(db_path: Path) -> dict:
    """导入所有可用数据源"""
    print("━" * 60)
    print("  Step 1: 数据导入")
    print("━" * 60)

    result = {"creative_performance_rows": 0, "creative_features_rows": 0}

    conn = duckdb.connect(str(db_path), read_only=True)
    result["creative_performance_rows"] = conn.execute(
        "SELECT COUNT(*) FROM creative_performance"
    ).fetchone()[0]
    result["creative_features_rows"] = conn.execute(
        "SELECT COUNT(*) FROM creative_features"
    ).fetchone()[0]
    result["unique_dates"] = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM creative_performance"
    ).fetchone()[0]
    result["unique_creatives"] = conn.execute(
        "SELECT COUNT(DISTINCT creative_id) FROM creative_performance"
    ).fetchone()[0]
    result["total_spend"] = conn.execute(
        "SELECT SUM(spend) FROM creative_performance"
    ).fetchone()[0] or 0
    result["total_installs"] = conn.execute(
        "SELECT SUM(install) FROM creative_performance"
    ).fetchone()[0] or 0
    conn.close()

    print(f"  creative_performance: {result['creative_performance_rows']} 行, "
          f"{result['unique_dates']} 天, {result['unique_creatives']} creatives")
    print(f"  总 spend: \${result['total_spend']:,.0f}, "
          f"总 installs: {result['total_installs']:,}")
    return result


# ============================================================================
# Step 2: 特征构建
# ============================================================================

def step2_build_features(db_path: Path) -> dict:
    """构建特征 variant, 写入 DB"""
    print("\n" + "━" * 60)
    print("  Step 2: 特征构建")
    print("━" * 60)

    conn = duckdb.connect(str(db_path), read_only=False)

    # 清空 pipeline 生成的旧数据
    conn.execute("DELETE FROM variant WHERE experiment_id LIKE 'pipe_%'")
    conn.execute("DELETE FROM experiment WHERE experiment_id LIKE 'pipe_%'")

    # 从 creative_library 导入的特征维度
    gene_types = {}
    gene_types["game"] = {
        "sql": """SELECT DISTINCT project as gene_value FROM creative_performance
                  WHERE project IS NOT NULL AND project != ''""",
        "feature_sql": """
            SELECT v.creative_id, cp.project as gene_value
            FROM creative_performance cp
            JOIN (SELECT DISTINCT creative_id FROM creative_performance WHERE creative_id != '') v
              ON cp.creative_id = v.creative_id
            WHERE cp.project IS NOT NULL AND cp.project != ''
        """,
    }

    # channel 维度
    gene_types["channel"] = {
        "feature_sql": """
            SELECT DISTINCT creative_id, 'Facebook' as gene_value
            FROM creative_performance WHERE creative_id != ''
        """,
    }

    # 从 creative_features 导入
    gene_types["color_tone"] = {
        "feature_sql": """
            SELECT cf.creative_id, cf.warm_cool as gene_value
            FROM creative_features cf
            WHERE cf.warm_cool IS NOT NULL AND cf.warm_cool != ''
        """,
    }
    gene_types["layout"] = {
        "feature_sql": """
            SELECT cf.creative_id,
                   CASE WHEN cf.left_right_layout THEN 'left_right'
                        WHEN cf.center_layout THEN 'center'
                        ELSE 'top_bottom' END as gene_value
            FROM creative_features cf
        """,
    }

    stats = {}
    total_variants = 0
    ts = datetime.now().isoformat()

    for gene_type, config in gene_types.items():
        exp_id = f"pipe_{gene_type}"

        # 创建 experiment
        conn.execute("""
            INSERT OR REPLACE INTO experiment (experiment_id, project, type, status, hypothesis, created_at)
            VALUES (?, 'PIPELINE', 'CREATIVE', 'RUNNING', ?, ?)
        """, [exp_id, f"FinalBandit 学习 {gene_type}", ts])

        # 拉取 creative → gene_value 映射
        rows = conn.execute(config["feature_sql"]).fetchall()
        if not rows:
            stats[gene_type] = {"variants": 0, "arms": 0}
            continue

        value_counts: dict[str, int] = defaultdict(int)
        for cid, gv in rows:
            if not cid or not gv:
                continue
            value_counts[gv] += 1
            variant_id = f"pipe_{gene_type}_{cid}"
            features = {gene_type: gv}
            conn.execute("""
                INSERT OR REPLACE INTO variant (variant_id, experiment_id, features, weight, creative_id, ad_id)
                VALUES (?, ?, ?, 1.0, ?, '')
            """, [variant_id, exp_id, json.dumps(features, ensure_ascii=False), cid])
            total_variants += 1

        stats[gene_type] = {"variants": len(rows), "arms": len(value_counts),
                            "distribution": dict(value_counts)}

    conn.commit()
    conn.close()

    print(f"  构建 {total_variants} 条 variant, {len(gene_types)} 个 experiment")
    for gt, s in stats.items():
        print(f"    {gt}: {s['variants']} variants, {s['arms']} arms "
              f"({', '.join(f'{k}={v}' for k,v in sorted(s['distribution'].items()))})")

    return stats


# ============================================================================
# Step 3: FinalBandit 学习
# ============================================================================

def step3_learn(db_path: Path, n_days: int = 7, seed: int = 42, project: str | None = None) -> dict:
    """FinalBandit 模拟 N 天 backfill 学习

    project: 限定项目 (如 'P04'), None = 全量
    """
    print("\n" + "━" * 60)
    proj_str = f" ({project} only)" if project else ""
    print(f"  Step 3: FinalBandit 学习 ({n_days} 天){proj_str}")
    print("━" * 60)

    rng = random.Random(seed)
    bandit = FinalBandit()
    monitor = FinalBanditMonitor(bandit, log_dir=ROOT / "output" / "monitor")

    conn = duckdb.connect(str(db_path), read_only=True)
    gene_types = conn.execute(
        "SELECT DISTINCT REPLACE(experiment_id, 'pipe_', '') FROM experiment WHERE experiment_id LIKE 'pipe_%'"
    ).fetchall()
    gene_types = [r[0] for r in gene_types]

    results = {}

    for gt in gene_types:
        exp_id = f"pipe_{gt}"

        # 加载 variant + performance 聚合
        proj_filter = ""
        proj_params: list = [exp_id]
        if project:
            proj_filter = "AND cp.project IN (?, ?)"
            proj_params.extend([project, f"{project} Witch"])

        rows = conn.execute(f"""
            SELECT v.features,
                   COALESCE(SUM(cp.spend), 0) as spend,
                   COALESCE(SUM(cp.install), 0) as installs,
                   COALESCE(SUM(cp.impression), 0) as imp,
                   CASE WHEN SUM(cp.impression) > 0 THEN SUM(cp.click)*100.0/SUM(cp.impression) ELSE 0 END as ctr,
                   CASE WHEN SUM(cp.spend) > 0 THEN SUM(cp.roas_d7 * cp.spend)/SUM(cp.spend) ELSE 0 END as roas
            FROM variant v
            LEFT JOIN creative_performance cp ON v.creative_id = cp.creative_id
            WHERE v.experiment_id = ? {proj_filter}
            GROUP BY v.features
            HAVING SUM(cp.impression) >= 100
        """, proj_params).fetchall()

        if not rows:
            results[gt] = {"status": "no_data", "arms": 0}
            continue

        # 按 gene_value 聚合
        arm_data: dict[str, dict] = defaultdict(lambda: {"spend": 0, "installs": 0, "imp": 0, "ctr_sum": 0.0, "count": 0, "roas_sum": 0.0, "roas_w": 0.0})
        for features_json, spend, installs, imp, ctr, roas in rows:
            features = json.loads(features_json)
            gv = features.get(gt, "unknown")
            ad = arm_data[gv]
            ad["spend"] += float(spend)
            ad["installs"] += int(installs)
            ad["imp"] += int(imp)
            ad["ctr_sum"] += float(ctr)
            ad["count"] += 1
            if float(spend) > 0:
                ad["roas_sum"] += float(roas) * float(spend)
                ad["roas_w"] += float(spend)

        # 计算每个 arm 的指标
        arms = []
        for gv, ad in arm_data.items():
            cpi = ad["spend"] / ad["installs"] if ad["installs"] > 0 else 999
            avg_ctr = ad["ctr_sum"] / ad["count"] if ad["count"] > 0 else 0
            roas = ad["roas_sum"] / ad["roas_w"] if ad["roas_w"] > 0 else 0
            arms.append({"gene_value": gv, "cpi": cpi, "roas": roas,
                         "spend": ad["spend"], "installs": ad["installs"],
                         "imp": ad["imp"], "ctr": avg_ctr})

        if len(arms) < 2:
            results[gt] = {"status": "too_few_arms", "arms": len(arms)}
            continue

        # baseline
        all_cpis = [a["cpi"] for a in arms if a["cpi"] < 999]
        all_roas = [a.get("roas", 0) for a in arms]
        b_cpi = float(np.median(all_cpis)) if all_cpis else 10
        b_roas = float(np.median(all_roas)) if all_roas else 0.1

        # N 天 backfill
        def sigmoid(x): return x / (1 + abs(x))

        for day in range(n_days):
            date_str = f"2026-07-{1+day:02d}"
            for arm in arms:
                gv = arm["gene_value"]
                if monitor.has_learned_on_date(gt, gv, date_str):
                    monitor.log_duplicate_reject(gt, gv, date_str)
                    continue
                if arm["installs"] < 1:
                    continue

                # 内购产品 reward: ROAS 权重 0.6 + CPI 权重 0.4
                # ROAS 越高越好, CPI 越低越好
                roas = arm.get("roas", 0)
                cpi = arm["cpi"]
                roas_score = sigmoid((roas - b_roas) / max(b_roas, 1e-6))
                cpi_score = sigmoid((b_cpi - cpi) / max(b_cpi, 1e-6))
                reward = 0.6 * roas_score + 0.4 * cpi_score
                reward = max(-1.0, min(1.0, reward + rng.gauss(0, 0.03)))
                monitor.update(gt, gv, reward)
                monitor.mark_learned_on_date(gt, gv, date_str)

        # 记录结果
        ranking = bandit.rank(gt)
        # 按 ROAS 排序作为真实 winner (内购产品)
        true_ranking = sorted(arms, key=lambda x: x["roas"], reverse=True)
        best_arm = bandit.best(gt)
        true_best = true_ranking[0]["gene_value"]

        arm_details = []
        for gv in ranking:
            arm_key = f"{gt}_{gv}"
            a = bandit.arms.get(arm_key)
            if a:
                orig = next((x for x in arms if x["gene_value"] == gv), None)
                arm_details.append({
                    "gene_value": gv,
                    "theta": round(a.theta, 4),
                    "sigma": round(a.sigma, 4),
                    "trials": a.trials,
                    "cpi": round(orig["cpi"], 2) if orig else 0,
                    "roas": round(orig["roas"], 4) if orig else 0,
                    "installs": orig["installs"] if orig else 0,
                    "spend": round(orig["spend"], 0) if orig else 0,
                })

        results[gt] = {
            "status": "ok",
            "arms": len(arms),
            "best_arm": best_arm,
            "true_best": true_best,
            "match": best_arm == true_best,
            "entropy": round(bandit.entropy(gt), 4),
            "ranking": arm_details,
        }

        match_str = "✅" if best_arm == true_best else "❌"
        print(f"  {match_str} {gt}: best={best_arm}, true={true_best}, "
              f"arms={len(arms)}, entropy={bandit.entropy(gt):.4f}")

    conn.close()

    # 最终快照
    monitor.take_snapshot()
    dashboard_data = monitor.export_dashboard_data()
    dashboard_path = ROOT / "output" / "monitor" / "current_state.json"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Monitor 快照已保存: {dashboard_path}")

    return results


# ============================================================================
# Step 4: 投放策略输出
# ============================================================================

def step4_strategy(results: dict, data_info: dict) -> str:
    """基于学习结果输出投放策略"""
    print("\n" + "━" * 60)
    print("  Step 4: 投放策略")
    print("━" * 60)

    lines = []
    lines.append("# FinalBandit 投放策略报告")
    lines.append(f"## 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"## 数据基础: {data_info['creative_performance_rows']} 行, "
                 f"{data_info['unique_creatives']} creatives, "
                 f"\${data_info['total_spend']:,.0f} spend\n")

    # 汇总
    matches = sum(1 for r in results.values() if r.get("match"))
    total = sum(1 for r in results.values() if r.get("status") == "ok")
    lines.append(f"## Winner 识别率: {matches}/{total}\n")

    lines.append("---\n")
    lines.append("## 各维度 Winner/Loser\n")

    for gt, r in sorted(results.items()):
        if r.get("status") != "ok":
            continue
        lines.append(f"### {gt}")
        lines.append(f"- **Winner**: `{r['best_arm']}` (theta={r['ranking'][0]['theta'] if r['ranking'] else '?'})")
        lines.append(f"- 真实最佳: `{r['true_best']}`")
        lines.append(f"- 匹配: {'✅' if r['match'] else '❌'}")
        lines.append(f"- Arms: {r['arms']}, Entropy: {r['entropy']}\n")

        if r["ranking"]:
            lines.append("| # | Arm | theta | sigma | trials | ROAS | CPI | Installs | Spend |")
            lines.append("|---|-----|-------|-------|--------|------|-----|----------|-------|")
            for i, a in enumerate(r["ranking"]):
                marker = "⭐" if a["gene_value"] == r["best_arm"] else ""
                lines.append(f"| {i+1} | {marker} {a['gene_value']} | "
                            f"{a['theta']:+.4f} | {a['sigma']:.4f} | {a['trials']} | "
                            f"{a.get('roas', 0):.3f} | \${a['cpi']:.2f} | "
                            f"{a['installs']:,} | \${a['spend']:,.0f} |")
            lines.append("")

    # 投放建议
    lines.append("---\n")
    lines.append("## 投放建议\n")

    for gt, r in sorted(results.items()):
        if r.get("status") != "ok" or not r["ranking"]:
            continue
        winner = r["ranking"][0]
        loser = r["ranking"][-1] if len(r["ranking"]) > 1 else None
        lines.append(f"### {gt}")
        lines.append(f"- ✅ **多投**: `{winner['gene_value']}` "
                    f"(theta={winner['theta']:+.4f}, ROAS={winner.get('roas', 0):.3f}, CPI=\${winner['cpi']:.2f})")
        if loser and loser["gene_value"] != winner["gene_value"]:
            roas_diff = winner.get("roas", 0) - loser.get("roas", 0)
            cpi_save = (loser["cpi"] - winner["cpi"]) / max(loser["cpi"], 1) * 100
            lines.append(f"- ❌ **少投**: `{loser['gene_value']}` "
                        f"(theta={loser['theta']:+.4f}, ROAS={loser.get('roas', 0):.3f}, CPI=\${loser['cpi']:.2f}, "
                        f"ROAS差 {roas_diff:+.3f}, CPI高 {cpi_save:+.0f}%)")
        lines.append("")

    report = "\n".join(lines)
    print(report)

    # 保存
    report_path = ROOT / "output" / "pipeline_strategy.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  策略报告已保存: {report_path}")

    return report


# ============================================================================
# Step 5: 创意 Prompt 生成
# ============================================================================

def step5_generate_prompts(results: dict) -> str:
    """基于 winner 特征组合, 生成下一轮裂变图片 prompt"""
    print("\n" + "━" * 60)
    print("  Step 5: AI 裂变 Prompt 生成")
    print("━" * 60)

    # 收集所有 winner
    winners = {}
    for gt, r in results.items():
        if r.get("status") == "ok" and r.get("match") and r.get("ranking"):
            winners[gt] = r["ranking"][0]["gene_value"]

    if not winners:
        print("  ⚠️ 无可用 winner, 跳过 prompt 生成")
        return ""

    lines = []
    lines.append("# AI 裂变图片 Prompt 批次")
    lines.append(f"## 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"## 基于 FinalBandit 学习结果\n")

    lines.append("## Winner 特征组合\n")
    for gt, gv in winners.items():
        lines.append(f"- **{gt}**: `{gv}`")
    lines.append("")

    # 生成 prompt
    game = winners.get("game", "P04 Witch")
    color = winners.get("color_tone", "cool")
    layout = winners.get("layout", "center")

    lines.append("---\n")
    lines.append("## 推荐 Prompt (5 个变体)\n")

    prompts = [
        f"{game} mobile game ad, {color} color tone, {layout} layout, "
        f"show exciting merge gameplay, bright gems and magical effects, "
        f"clear CTA button, high CTR mobile game creative",

        f"{game} puzzle game screenshot, {color} palette, {layout} composition, "
        f"dramatic before-after moment, witch character casting spell, "
        f"bold text overlay 'Can You Solve This?', viral game ad style",

        f"{game} casual game ad creative, {color} tones, {layout} structure, "
        f"progress bar showing level completion, reward chest opening, "
        f"satisfying game moment, high conversion mobile ad",

        f"{game} merge game scene, {color} aesthetic, {layout} design, "
        f"multiple items merging with particle effects, coin shower reward, "
        f"engaging hook in first 3 seconds, Facebook ad format 1:1",

        f"{game} fantasy game ad, {color} mood, {layout} visual flow, "
        f"character close-up with emotional expression, urgent situation, "
        f"simple UI overlay with download button, optimized for mobile feed",
    ]

    for i, prompt in enumerate(prompts):
        lines.append(f"### Variant {i+1}")
        lines.append(f"```\n{prompt}\n```\n")
        lines.append(f"- 目标特征: game={game}, color={color}, layout={layout}")
        lines.append(f"- 预期效果: 延续 winner 特征, 测试 {game} 在 {color}+{layout} 下的表现\n")

    lines.append("---\n")
    lines.append("## 投放建议\n")
    lines.append(f"- Campaign: {game} Auto-Bandit Test")
    lines.append(f"- 每个 variant 生成 2-3 张图")
    lines.append(f"- 每日 budget: \$20-50")
    lines.append(f"- 投放 7 天后回收数据, 更新 FinalBandit")

    report = "\n".join(lines)
    print(report[:500] + "...")

    prompt_path = ROOT / "output" / "pipeline_prompts.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Prompt 已保存: {prompt_path}")

    return report


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="FinalBandit Production Pipeline")
    parser.add_argument("--days", type=int, default=7, help="模拟学习天数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--project", type=str, default=None, help="限定项目 (如 P04)")
    args = parser.parse_args()

    print("=" * 60)
    print("  FinalBandit Production Pipeline")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    t0 = time.time()

    # Step 1
    data_info = step1_import_data(db_path)

    # Step 2
    feature_stats = step2_build_features(db_path)

    # Step 3
    results = step3_learn(db_path, n_days=args.days, seed=args.seed, project=args.project)

    # Step 4
    step4_strategy(results, data_info)

    # Step 5
    step5_generate_prompts(results)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Pipeline 完成! 耗时 {elapsed:.1f}s")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
