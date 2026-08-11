"""FinalBandit 参数调优 — Grid Search

用真实 creative_performance 数据, 对 alpha/beta/tau/gamma 做 grid search。
评估指标: theta 收敛到正确排序的速度和稳定性。

不修改算法 — 只改变参数值。
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
    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("""
        SELECT creative_id, SUM(impression) as imp, SUM(click) as click,
               SUM(spend) as spend, SUM(install) as install,
               CASE WHEN SUM(impression)>0 THEN SUM(click)*100.0/SUM(impression) ELSE 0 END as ctr,
               CASE WHEN SUM(install)>0 THEN SUM(spend)/SUM(install) ELSE 0 END as cpi,
               CASE WHEN SUM(spend)>0 THEN SUM(roas_d7*spend)/SUM(spend) ELSE 0 END as roas_d7
        FROM creative_performance GROUP BY creative_id
        HAVING SUM(impression) >= 500 ORDER BY SUM(impression) DESC LIMIT 30
    """).fetchall()
    cols = [d[0] for d in conn.description]
    data = [dict(zip(cols, r)) for r in rows]
    conn.close()
    return data


def sigmoid(x: float) -> float:
    return x / (1.0 + abs(x))


def compute_reward(ctr, roas, imp, b_ctr, b_roas):
    if imp < 500:
        return 0.5
    cn = (ctr - b_ctr) / (b_ctr + 1e-6)
    rn = (roas - b_roas) / (b_roas + 1e-6)
    return 0.6 * sigmoid(cn) + 0.4 * sigmoid(rn)


# ============================================================================
# 模拟一次运行
# ============================================================================

def run_one(
    data: list[dict],
    alpha: float, beta: float, tau: float, gamma: float,
    n_days: int = 7, seed: int = 42,
) -> dict:
    """用指定参数运行 7 天模拟, 返回评估指标"""
    rng = random.Random(seed)
    bandit = FinalBandit()
    bandit.alpha = alpha
    bandit.beta = beta
    bandit.tau = tau
    bandit.gamma = gamma

    top = data[:20]
    gene_type = "creative_id"

    all_ctrs = [c["ctr"] for c in top]
    all_roas = [c["roas_d7"] for c in top]
    b_ctr = float(np.median(all_ctrs))
    b_roas = float(np.median(all_roas))

    # 真实 winner (按 ROAS)
    true_ranking = sorted(top, key=lambda x: x["roas_d7"], reverse=True)
    true_top3 = {c["creative_id"] for c in true_ranking[:3]}

    rankings: list[list[str]] = []
    entropies: list[float] = []
    sigmas: list[float] = []

    for day in range(n_days):
        date_str = f"2026-07-{1+day:02d}"
        for c in top:
            cid = c["creative_id"]
            if bandit.has_learned_on_date(gene_type, cid, date_str):
                continue
            reward = compute_reward(c["ctr"], c["roas_d7"], c["imp"], b_ctr, b_roas)
            reward = max(-1.0, min(1.0, reward + rng.gauss(0, 0.03)))
            bandit.update(gene_type, cid, reward)
            bandit.mark_learned_on_date(gene_type, cid, date_str)

        ranking = bandit.rank(gene_type)
        rankings.append(ranking)
        entropies.append(bandit.entropy(gene_type))

        # 平均 sigma
        arms_of_type = [a for a in bandit.arms.values() if a.gene_type == gene_type]
        if arms_of_type:
            sigmas.append(float(np.mean([a.sigma for a in arms_of_type])))

    # ===== 评估指标 =====

    # 1. Ranking 正确性: top 3 theta 中有几个在真实 top 3 ROAS 中
    final_ranking = rankings[-1]
    theta_top3 = set(final_ranking[:3])
    top3_recall = len(theta_top3 & true_top3) / 3

    # 2. Ranking 稳定性: flip rate
    flips = sum(1 for i in range(1, len(rankings)) if rankings[i] != rankings[i-1])
    flip_rate = flips / max(len(rankings) - 1, 1)

    # 3. Sigma 下降
    if len(sigmas) >= 2:
        sigma_decline = sigmas[-1] / max(sigmas[0], 1e-6)
    else:
        sigma_decline = 1.0

    # 4. Entropy 健康: 不崩塌
    if len(entropies) >= 2:
        entropy_collapse = entropies[-1] < entropies[0] * 0.2
    else:
        entropy_collapse = False

    # 5. Theta 区分度: max theta - min theta
    thetas = [a.theta for a in bandit.arms.values() if a.gene_type == gene_type]
    theta_spread = max(thetas) - min(thetas) if thetas else 0

    # 综合评分 (越高越好)
    score = (
        top3_recall * 0.35 +
        (1 - flip_rate) * 0.25 +
        (1 - min(sigma_decline, 1.0)) * 0.15 +
        (0 if entropy_collapse else 0.15) +
        min(theta_spread / 0.5, 1.0) * 0.10
    )

    return {
        "alpha": alpha, "beta": beta, "tau": tau, "gamma": gamma,
        "top3_recall": round(top3_recall, 3),
        "flip_rate": round(flip_rate, 3),
        "sigma_decline": round(sigma_decline, 3),
        "entropy_collapse": entropy_collapse,
        "theta_spread": round(theta_spread, 4),
        "score": round(score, 4),
    }


# ============================================================================
# Grid Search
# ============================================================================

GRID = {
    "alpha": [0.05, 0.10, 0.15, 0.20, 0.25],
    "beta":  [0.05, 0.10, 0.15, 0.20],
    "tau":   [0.10, 0.20, 0.30, 0.40],
    "gamma": [0.15, 0.30, 0.45, 0.60],
}


def main() -> int:
    print("=" * 78)
    print("  FinalBandit 参数调优 — Grid Search")
    print(f"  Grid: alpha={GRID['alpha']}, beta={GRID['beta']}, "
          f"tau={GRID['tau']}, gamma={GRID['gamma']}")
    print(f"  总组合: {len(GRID['alpha'])*len(GRID['beta'])*len(GRID['tau'])*len(GRID['gamma'])}")
    print("=" * 78)

    db_path = str(ROOT / "db" / "facebook_performance.duckdb")
    data = load_creative_data(db_path)
    print(f"\n  数据: {len(data)} creatives (imp >= 500)")

    # 当前默认参数
    default = run_one(data, 0.15, 0.10, 0.20, 0.30, n_days=7, seed=42)
    print(f"\n  默认参数 (alpha=0.15, beta=0.10, tau=0.20, gamma=0.30):")
    print(f"    top3_recall={default['top3_recall']}, flip_rate={default['flip_rate']}, "
          f"sigma_decline={default['sigma_decline']}, collapse={default['entropy_collapse']}, "
          f"score={default['score']}")

    # 跑 grid
    results = []
    total = len(GRID["alpha"]) * len(GRID["beta"]) * len(GRID["tau"]) * len(GRID["gamma"])
    done = 0
    for alpha in GRID["alpha"]:
        for beta in GRID["beta"]:
            for tau in GRID["tau"]:
                for gamma in GRID["gamma"]:
                    r = run_one(data, alpha, beta, tau, gamma, n_days=7, seed=42)
                    results.append(r)
                    done += 1
                    if done % 40 == 0:
                        print(f"  进度: {done}/{total}")

    # 排序
    results.sort(key=lambda x: x["score"], reverse=True)

    # 输出 top 10
    print(f"\n{'='*78}\n  Top 10 参数组合\n{'='*78}")
    print(f"  {'#':<3} {'alpha':<7} {'beta':<7} {'tau':<7} {'gamma':<7} "
          f"{'top3_rec':<9} {'flip':<7} {'sigma_dec':<10} {'collapse':<9} {'spread':<8} {'score':<8}")
    print(f"  {'-'*78}")

    for i, r in enumerate(results[:10]):
        marker = " ← DEFAULT" if (r["alpha"] == 0.15 and r["beta"] == 0.10 and
                                   r["tau"] == 0.20 and r["gamma"] == 0.30) else ""
        print(f"  {i+1:<3} {r['alpha']:<7} {r['beta']:<7} {r['tau']:<7} {r['gamma']:<7} "
              f"{r['top3_recall']:<9} {r['flip_rate']:<7} {r['sigma_decline']:<10} "
              f"{str(r['entropy_collapse']):<9} {r['theta_spread']:<8} {r['score']:<8}{marker}")

    # 最佳参数
    best = results[0]
    print(f"\n{'='*78}\n  最佳参数\n{'='*78}")
    print(f"  alpha={best['alpha']}, beta={best['beta']}, tau={best['tau']}, gamma={best['gamma']}")
    print(f"  score={best['score']} (默认: {default['score']})")
    print(f"  提升: {(best['score'] - default['score']) / max(default['score'], 1e-6) * 100:+.1f}%")

    # 参数重要性 (每个参数的最优值)
    print(f"\n{'='*78}\n  参数敏感性 (每个参数取最佳值的平均 score)\n{'='*78}")
    for param_name, param_values in GRID.items():
        best_for_param = {}
        for v in param_values:
            subset = [r for r in results if r[param_name] == v]
            avg_score = float(np.mean([r["score"] for r in subset]))
            best_for_param[v] = avg_score
        sorted_vals = sorted(best_for_param.items(), key=lambda x: x[1], reverse=True)
        print(f"  {param_name}: ", end="")
        for v, s in sorted_vals:
            marker = " ★" if v == sorted_vals[0][0] else ""
            print(f"{v}={s:.3f}{marker}  ", end="")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
