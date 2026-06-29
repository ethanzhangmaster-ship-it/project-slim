"""FinalBandit 特征维度 Replay 验证

用补全后的 variant 数据 (4 个 gene_type: color_tone, layout, saturation_level, brightness_level)
+ creative_performance, 模拟 7 天 backfill → FinalBandit 学习。

验证:
1. 每个 gene_type 下 FinalBandit theta 排序 vs 真实 ROAS 排序
2. theta 是否收敛到正确 winner
3. sigma 是否正常下降
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.final_bandit import FinalBandit


# ============================================================================
# 数据加载
# ============================================================================

def load_variant_data(db_path: str) -> dict[str, list[dict]]:
    """加载 variant 数据, 按 gene_type 分组"""
    conn = duckdb.connect(db_path, read_only=True)
    gene_types = ["color_tone", "layout", "saturation_level", "brightness_level"]

    result: dict[str, list[dict]] = {}
    for gt in gene_types:
        rows = conn.execute("""
            SELECT 
                v.variant_id,
                v.features,
                v.creative_id,
                COALESCE(SUM(cp.impression), 0) as total_imp,
                COALESCE(SUM(cp.click), 0) as total_click,
                COALESCE(SUM(cp.spend), 0) as total_spend,
                COALESCE(SUM(cp.install), 0) as total_install,
                CASE WHEN SUM(cp.impression) > 0 
                     THEN SUM(cp.click)*100.0/SUM(cp.impression) ELSE 0 END as ctr,
                CASE WHEN SUM(cp.spend) > 0 
                     THEN SUM(cp.roas_d7 * cp.spend)/SUM(cp.spend) ELSE 0 END as roas_d7
            FROM variant v
            LEFT JOIN creative_performance cp ON v.creative_id = cp.creative_id
            WHERE v.experiment_id = ?
            GROUP BY v.variant_id, v.features, v.creative_id
            HAVING SUM(cp.impression) >= 100
        """, [f"feat_{gt}"]).fetchall()

        cols = [d[0] for d in conn.description]
        data = [dict(zip(cols, r)) for r in rows]
        result[gt] = data

    conn.close()
    return result


def sigmoid(x: float) -> float:
    return x / (1.0 + abs(x))


# ============================================================================
# 模拟 7 天 backfill
# ============================================================================

def replay_gene_type(
    bandit: FinalBandit,
    gene_type: str,
    variants: list[dict],
    rng: random.Random,
    n_days: int = 7,
) -> dict:
    """对单个 gene_type 模拟 7 天 backfill"""
    # baseline
    all_ctrs = [v["ctr"] for v in variants if v["total_imp"] > 0]
    all_roas = [v["roas_d7"] for v in variants if v["total_imp"] > 0]
    b_ctr = float(np.median(all_ctrs)) if all_ctrs else 1.0
    b_roas = float(np.median(all_roas)) if all_roas else 0.3

    history = {
        "rankings": [],
        "entropies": [],
        "sigmas": [],
        "update_count": 0,
    }

    for day in range(n_days):
        date_str = f"2026-07-{1+day:02d}"
        for v in variants:
            # 提取 gene_value
            features = json.loads(v["features"])
            gene_value = features.get(gene_type, "unknown")
            imp = v["total_imp"]

            if bandit.has_learned_on_date(gene_type, gene_value, date_str):
                continue
            if imp < 100:
                continue

            ctr = v["ctr"]
            roas = v["roas_d7"]
            if imp < 500:
                reward = 0.5
            else:
                cn = (ctr - b_ctr) / (b_ctr + 1e-6)
                rn = (roas - b_roas) / (b_roas + 1e-6)
                reward = 0.6 * sigmoid(cn) + 0.4 * sigmoid(rn)

            reward = max(-1.0, min(1.0, reward + rng.gauss(0, 0.03)))
            bandit.update(gene_type, gene_value, reward)
            bandit.mark_learned_on_date(gene_type, gene_value, date_str)
            history["update_count"] += 1

        ranking = bandit.rank(gene_type)
        history["rankings"].append(ranking)
        history["entropies"].append(bandit.entropy(gene_type))

        arms_of_type = [a for a in bandit.arms.values() if a.gene_type == gene_type]
        if arms_of_type:
            history["sigmas"].append(float(np.mean([a.sigma for a in arms_of_type])))

    return history


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    print("=" * 78)
    print("  FinalBandit 特征维度 Replay 验证")
    print("  4 个 gene_type: color_tone, layout, saturation_level, brightness_level")
    print("=" * 78)

    db_path = str(ROOT / "db" / "facebook_performance.duckdb")
    all_data = load_variant_data(db_path)

    gene_types = ["color_tone", "layout", "saturation_level", "brightness_level"]
    rng = random.Random(42)

    for gt in gene_types:
        variants = all_data[gt]
        if not variants:
            print(f"\n  ⚠️  {gt}: 无数据, 跳过")
            continue

        # 真实 ROAS 排序
        true_ranking = sorted(variants, key=lambda x: x["roas_d7"], reverse=True)
        true_order = [v["features"] for v in true_ranking]

        print(f"\n{'='*78}")
        print(f"  📊 {gt} ({len(variants)} variants)")
        print(f"{'='*78}")

        # 真实数据
        print(f"  真实 ROAS 排序:")
        for i, v in enumerate(true_ranking):
            features = json.loads(v["features"])
            gv = features.get(gt, "?")
            print(f"    {i+1}. {gv:<12} ROAS={v['roas_d7']:.3f}  "
                  f"CTR={v['ctr']:.1f}%  imp={v['total_imp']:,}  n={v['total_spend']:.0f}")

        # Replay
        bandit = FinalBandit()
        history = replay_gene_type(bandit, gt, variants, rng)

        # 结果
        print(f"\n  FinalBandit theta 排序:")
        ranking = bandit.rank(gt)
        for i, gv in enumerate(ranking):
            arm_key = f"{gt}_{gv}"
            arm = bandit.arms.get(arm_key)
            if arm:
                print(f"    {i+1}. {gv:<12} theta={arm.theta:+.4f}  "
                      f"sigma={arm.sigma:.4f}  trials={arm.trials}")

        # 对比
        true_top = true_ranking[0]
        true_best_features = json.loads(true_top["features"])
        true_best_value = true_best_features.get(gt, "?")
        bandit_best = bandit.best(gt)
        match = "✅ MATCH" if bandit_best == true_best_value else "❌ MISMATCH"

        print(f"\n  真实 winner: {true_best_value} (ROAS={true_top['roas_d7']:.3f})")
        print(f"  Bandit best: {bandit_best}")
        print(f"  {match}")

        # 指标
        if len(history["sigmas"]) >= 2:
            sigma_dec = history["sigmas"][-1] / max(history["sigmas"][0], 1e-6)
            print(f"  sigma decline: {history['sigmas'][0]:.4f} → {history['sigmas'][-1]:.4f} "
                  f"(ratio={sigma_dec:.3f})")

        if len(history["entropies"]) >= 2:
            print(f"  entropy: {history['entropies'][0]:.4f} → {history['entropies'][-1]:.4f}")
            collapse = history["entropies"][-1] < history["entropies"][0] * 0.2
            print(f"  collapse: {collapse}")

        # 排名翻转
        rankings = history["rankings"]
        flips = sum(1 for i in range(1, len(rankings)) if rankings[i] != rankings[i-1])
        flip_rate = flips / max(len(rankings) - 1, 1)
        print(f"  flip_rate: {flip_rate:.3f} ({flips} flips / {len(rankings)-1} days)")

    # 汇总
    print(f"\n{'='*78}")
    print(f"  汇总")
    print(f"{'='*78}")
    all_pass = 0
    all_total = 0
    for gt in gene_types:
        variants = all_data[gt]
        if not variants:
            continue
        bandit = FinalBandit()
        replay_gene_type(bandit, gt, variants, rng)

        true_top = sorted(variants, key=lambda x: x["roas_d7"], reverse=True)[0]
        true_best = json.loads(true_top["features"]).get(gt, "?")
        bandit_best = bandit.best(gt)
        match = bandit_best == true_best
        all_total += 1
        if match:
            all_pass += 1
        status = "✅" if match else "❌"
        print(f"  {status} {gt}: true_best={true_best}, bandit_best={bandit_best}")

    print(f"\n  Winner 识别率: {all_pass}/{all_total}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
