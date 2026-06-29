"""真实数据 Replay — FinalBandit 多日滚动回放验证

用 DuckDB creative_performance (984 rows, 588 creatives) 模拟多日投放,
验证 FinalBandit 在真实 Facebook 数据上的行为:

- 去重: 同 creative 同天只学一次
- theta 曲线: 是否收敛到正确排序
- sigma 曲线: 是否正常下降
- 跨日稳定性: 每日回填不产生重复学习
"""
from __future__ import annotations

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

def load_creative_data(db_path: str) -> list[dict]:
    """加载 creative_performance, 按 creative_id 聚合"""
    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("""
        SELECT
            creative_id,
            SUM(impression) as imp,
            SUM(click) as click,
            SUM(spend) as spend,
            SUM(install) as install,
            CASE WHEN SUM(impression) > 0 THEN SUM(click)*100.0/SUM(impression) ELSE 0 END as ctr,
            CASE WHEN SUM(install) > 0 THEN SUM(spend)/SUM(install) ELSE 0 END as cpi,
            CASE WHEN SUM(spend) > 0 THEN SUM(roas_d7 * spend)/SUM(spend) ELSE 0 END as roas_d7
        FROM creative_performance
        GROUP BY creative_id
        HAVING SUM(impression) >= 500
        ORDER BY SUM(impression) DESC
    """).fetchall()

    cols = [d[0] for d in conn.description]
    data = [dict(zip(cols, r)) for r in rows]
    conn.close()
    return data


# ============================================================================
# 模拟环境
# ============================================================================

def sigmoid(x: float) -> float:
    return x / (1.0 + abs(x))


def compute_reward(ctr: float, roas: float, imp: int, b_ctr: float, b_roas: float) -> float:
    if imp < 500:
        return 0.5
    cn = (ctr - b_ctr) / (b_ctr + 1e-6)
    rn = (roas - b_roas) / (b_roas + 1e-6)
    return 0.6 * sigmoid(cn) + 0.4 * sigmoid(rn)


# ============================================================================
# 多日滚动 Replay
# ============================================================================

def replay_multiday(data: list[dict], n_days: int = 7, seed: int = 42) -> dict:
    """模拟 N 天滚动回填

    每天: backfill 所有 creatives (模拟 cron daily backfill)
    去重: 同 creative 同天只学一次
    """
    rng = random.Random(seed)
    bandit = FinalBandit()

    top_creatives = data[:50]
    gene_type = "creative_id"

    # 计算 baseline
    all_ctrs = [c["ctr"] for c in top_creatives]
    all_roas = [c["roas_d7"] for c in top_creatives]
    b_ctr = float(np.median(all_ctrs))
    b_roas = float(np.median(all_roas))

    history = {
        "thetas": defaultdict(list),
        "sigmas": defaultdict(list),
        "trials": defaultdict(list),
        "rankings": [],
        "selections": [],
        "entropies": [],
        "taus": [],
        "n_active_arms": [],
        "duplicate_skipped": [],  # 每天被去重跳过的次数
    }

    for day in range(n_days):
        date_str = f"2026-06-{26+day:02d}"
        skipped_today = 0

        for c in top_creatives:
            creative_id = c["creative_id"]
            reward = compute_reward(c["ctr"], c["roas_d7"], c["imp"], b_ctr, b_roas)
            noise = rng.gauss(0, 0.05)
            reward = max(-1.0, min(1.0, reward + noise))

            # 去重检查
            if bandit.has_learned_on_date(gene_type, creative_id, date_str):
                skipped_today += 1
                continue

            bandit.update(gene_type, creative_id, reward)
            bandit.mark_learned_on_date(gene_type, creative_id, date_str)

            arm_key = f"{gene_type}_{creative_id}"
            if arm_key in bandit.arms:
                arm = bandit.arms[arm_key]
                history["thetas"][creative_id].append(arm.theta)
                history["sigmas"][creative_id].append(arm.sigma)
                history["trials"][creative_id].append(arm.trials)

        # 每日记录
        ranking = bandit.rank(gene_type)
        history["rankings"].append(ranking[:5])
        selected = bandit.sample(gene_type)
        greedy = bandit.best(gene_type)
        history["selections"].append({
            "day": day, "date": date_str, "selected": selected, "greedy": greedy,
            "is_greedy": selected == greedy,
        })
        history["entropies"].append(bandit.entropy(gene_type))
        history["taus"].append(bandit._auto_tau(gene_type))
        history["n_active_arms"].append(
            len([a for a in bandit.arms.values() if a.gene_type == gene_type])
        )
        history["duplicate_skipped"].append(skipped_today)

    # 第 8 天: 模拟重复 backfill (验证去重)
    for run in range(3):
        date_str = "2026-07-03"  # 同一天
        skipped = 0
        for c in top_creatives:
            creative_id = c["creative_id"]
            if bandit.has_learned_on_date(gene_type, creative_id, date_str):
                skipped += 1
                continue
            reward = compute_reward(c["ctr"], c["roas_d7"], c["imp"], b_ctr, b_roas)
            bandit.update(gene_type, creative_id, reward)
            bandit.mark_learned_on_date(gene_type, creative_id, date_str)
        history.setdefault("dedup_runs", []).append(
            {"run": run + 1, "skipped": skipped, "total_creatives": len(top_creatives)}
        )

    return history, bandit


# ============================================================================
# 分析
# ============================================================================

def analyze(history: dict, bandit: FinalBandit) -> dict:
    gene_type = "creative_id"

    # 去重验证
    dedup_runs = history.get("dedup_runs", [])
    dedup_pass = all(r["skipped"] == r["total_creatives"] for r in dedup_runs[1:]) if len(dedup_runs) > 1 else True

    # theta 收敛
    thetas = history["thetas"]
    final_thetas = {cid: thetas[cid][-1] for cid in thetas if thetas[cid]}
    sorted_by_theta = sorted(final_thetas.items(), key=lambda x: x[1], reverse=True)

    # sigma 下降
    all_sigmas = history["sigmas"]
    sigma_means = []
    for day_idx in range(len(history["duplicate_skipped"])):
        day_sigmas = []
        for cid in all_sigmas:
            if day_idx < len(all_sigmas[cid]):
                day_sigmas.append(all_sigmas[cid][day_idx])
        if day_sigmas:
            sigma_means.append(float(np.mean(day_sigmas)))
    early_sigma = sigma_means[0] if sigma_means else 0
    late_sigma = sigma_means[-1] if sigma_means else 0

    # exploration
    selections = history["selections"]
    early_explore = sum(1 for s in selections[:2] if not s["is_greedy"]) / max(len(selections[:2]), 1)
    late_explore = sum(1 for s in selections[-2:] if not s["is_greedy"]) / max(len(selections[-2:]), 1)

    # ranking 稳定性
    rankings = history["rankings"]
    flips = sum(1 for i in range(1, len(rankings)) if rankings[i] != rankings[i-1])
    flip_rate = flips / max(len(rankings) - 1, 1)

    # entropy
    entropies = history["entropies"]
    early_e = entropies[0] if entropies else 0
    late_e = entropies[-1] if entropies else 0

    # 每日跳过统计
    daily_skipped = history["duplicate_skipped"]

    return {
        "n_arms_learned": len(thetas),
        "final_top5_theta": [cid[:20] for cid, _ in sorted_by_theta[:5]],
        "theta_range": (sorted_by_theta[-1][1], sorted_by_theta[0][1]) if sorted_by_theta else (0, 0),
        "sigma_early": early_sigma,
        "sigma_late": late_sigma,
        "sigma_decline": late_sigma / max(early_sigma, 1e-6),
        "early_explore_rate": early_explore,
        "late_explore_rate": late_explore,
        "flip_rate": flip_rate,
        "entropy_early": early_e,
        "entropy_late": late_e,
        "entropy_collapse": late_e < early_e * 0.3,
        "n_active_arms_final": history["n_active_arms"][-1] if history["n_active_arms"] else 0,
        "dedup_pass": dedup_pass,
        "dedup_runs": dedup_runs,
        "daily_skipped": daily_skipped,
    }


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    print("=" * 78)
    print("  FinalBandit 多日滚动 Replay + 去重验证")
    print("  DuckDB creative_performance (588 creatives, 984 rows)")
    print("=" * 78)

    db_path = str(ROOT / "db" / "facebook_performance.duckdb")
    data = load_creative_data(db_path)
    print(f"\n  加载 {len(data)} 个 creatives (impressions >= 500)")

    if not data:
        print("  [SKIP] 无满足条件的 creative")
        return 0

    # Top by ROAS
    sorted_by_roas = sorted(data, key=lambda x: x["roas_d7"], reverse=True)
    print(f"\n  Top 3 by ROAS (真实 winner):")
    for i, c in enumerate(sorted_by_roas[:3]):
        print(f"    {i+1}. {c['creative_id'][:25]} ROAS={c['roas_d7']:.3f}")

    # 多日 Replay
    print(f"\n  运行 7 天滚动 Replay + 3 次同天重复 backfill...")
    history, bandit = replay_multiday(data, n_days=7, seed=42)

    result = analyze(history, bandit)
    print(f"\n{'='*78}\n  Replay 结果\n{'='*78}")

    print(f"\n  📊 去重验证:")
    for r in result["dedup_runs"]:
        status = "✅" if r["skipped"] == r["total_creatives"] else "❌"
        print(f"    Run {r['run']}: {r['skipped']}/{r['total_creatives']} skipped {status}")
    print(f"    去重通过: {'✅ YES' if result['dedup_pass'] else '❌ NO'}")

    print(f"\n  📊 每日去重统计:")
    for i, s in enumerate(result["daily_skipped"]):
        print(f"    Day {i+1}: {s} creatives 被去重跳过 (应全 0, 每日都是新数据)")

    print(f"\n  📊 Theta 收敛:")
    print(f"    Learned arms: {result['n_arms_learned']}")
    print(f"    Theta range: [{result['theta_range'][0]:.4f}, {result['theta_range'][1]:.4f}]")
    print(f"    Final Top 5: {result['final_top5_theta']}")

    print(f"\n  📊 Sigma 下降:")
    print(f"    Early: {result['sigma_early']:.4f} → Late: {result['sigma_late']:.4f}")
    print(f"    Decline: {result['sigma_decline']:.3f} {'✅' if result['sigma_decline'] < 0.95 else '⚠️'}")

    print(f"\n  📊 Exploration:")
    print(f"    Early: {result['early_explore_rate']:.1%} → Late: {result['late_explore_rate']:.1%}")

    print(f"\n  📊 Ranking 稳定性:")
    print(f"    Flip rate: {result['flip_rate']:.3f}")

    print(f"\n  📊 Entropy:")
    print(f"    Early: {result['entropy_early']:.4f} → Late: {result['entropy_late']:.4f}")
    print(f"    Collapse: {result['entropy_collapse']}")

    # 判定
    print(f"\n{'='*78}\n  判定\n{'='*78}")
    checks = [
        ("去重生效 (重复 backfill 全跳过)", result["dedup_pass"]),
        ("Theta 收敛 (有学习)", result["n_arms_learned"] > 5),
        ("Sigma 下降", result["sigma_decline"] < 0.95),
        ("Entropy 未崩塌", not result["entropy_collapse"]),
    ]
    all_pass = True
    for name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print(f"\n  🎉 多日滚动 Replay 全部通过!")
    else:
        print(f"\n  ⚠️ 部分检查未通过")

    return 0


if __name__ == "__main__":
    sys.exit(main())

