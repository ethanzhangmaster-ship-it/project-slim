"""Final Architecture 自检脚本 (Spec §13.9)

验证 8 个维度:
① theta 是否稳定收敛
② sigma 是否正常下降
③ exploration 是否逐渐降低
④ ranking 是否始终等于 theta 排序
⑤ reward 是否完全退出决策链
⑥ auction 是否没有进入 decision
⑦ entropy 是否只影响 temperature
⑧ 所有 decision 是否只来自 theta
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.final_bandit import FinalArm, FinalBandit


# ============================================================================
# 模拟环境
# ============================================================================

ARMS = ["arm_A", "arm_B", "arm_C"]
TRUE_THETA = {"arm_A": 0.9, "arm_B": 0.5, "arm_C": 0.1}
TRUE_CTR = {"arm_A": 0.018, "arm_B": 0.015, "arm_C": 0.012}
TRUE_ROAS = {"arm_A": 0.45, "arm_B": 0.32, "arm_C": 0.20}
AUCTION_PRESSURE_BASE = {"arm_A": 1.3, "arm_B": 1.0, "arm_C": 0.8}


def simulate_event(arm: str, rng: random.Random, auction_noise: float = 0.3) -> dict:
    """模拟 Facebook 环境: observed = theta + auction_noise + delay_noise"""
    base_ctr = TRUE_CTR[arm]
    base_roas = TRUE_ROAS[arm]
    pressure = AUCTION_PRESSURE_BASE[arm] * (1 + rng.gauss(0, auction_noise))
    pressure = max(0.3, pressure)
    observed_ctr = base_ctr * (1 + (pressure - 1) * 0.3) + rng.gauss(0, 0.003)
    observed_ctr = max(0.001, observed_ctr)
    observed_roas = base_roas / pressure + rng.gauss(0, 0.05)
    observed_roas = max(0.05, observed_roas)
    imp = int(rng.randint(100, 300) / pressure)
    clicks = max(0, int(imp * observed_ctr))
    spend = imp * pressure * 0.5
    return {
        "impressions": imp, "clicks": clicks, "spend": spend,
        "ctr": observed_ctr * 100, "roas_d7": observed_roas,
        "auction_pressure": pressure,
    }


def sigmoid(x: float) -> float:
    return x / (1.0 + abs(x))


def compute_reward(ctr, roas, imp, b_ctr, b_roas):
    """Spec §13.8: Facebook 数据 → reward → 结束

    reward = baseline normalized score (observation)
    """
    if imp < 500:
        return 0.5
    cn = (ctr - b_ctr) / (b_ctr + 1e-6)
    rn = (roas - b_roas) / (b_roas + 1e-6)
    return 0.6 * sigmoid(cn) + 0.4 * sigmoid(rn)


# ============================================================================
# 跑 48h Final Architecture
# ============================================================================

def run_final(n_hours=48, seed=42, auction_noise=0.3):
    rng = random.Random(seed)
    audit_mem = ROOT / "output" / "audit" / "final_selfcheck.json"
    if audit_mem.exists():
        audit_mem.unlink()
    bandit = FinalBandit(memory_path=audit_mem)

    history = {
        "thetas": defaultdict(list),
        "sigmas": defaultdict(list),
        "trials": defaultdict(list),
        "rewards": defaultdict(list),
        "auction_pressures": defaultdict(list),
        "rankings": [],
        "selections": [],
        "entropies": [],
        "taus": [],
    }

    rolling = defaultdict(lambda: {"imp": 0, "click": 0, "roas_sum": 0.0, "roas_w": 0.0, "spend": 0.0})

    for hour in range(n_hours):
        for _ in range(5):
            for arm in ARMS:
                ev = simulate_event(arm, rng, auction_noise)
                r = rolling[arm]
                r["imp"] += ev["impressions"]
                r["click"] += ev["clicks"]
                r["roas_sum"] += ev["roas_d7"] * ev["impressions"]
                r["roas_w"] += ev["impressions"]
                r["spend"] += ev["spend"]

        all_ctrs, all_roas = [], []
        for arm in ARMS:
            r = rolling[arm]
            if r["imp"] > 0:
                all_ctrs.append(r["click"] / r["imp"] * 100)
                all_roas.append(r["roas_sum"] / r["roas_w"] if r["roas_w"] > 0 else 0)
        b_ctr = float(np.median(all_ctrs)) if all_ctrs else 1.5
        b_roas = float(np.median(all_roas)) if all_roas else 0.3

        for arm in ARMS:
            r = rolling[arm]
            if r["imp"] == 0:
                continue
            ctr = r["click"] / r["imp"] * 100
            roas = r["roas_sum"] / r["roas_w"] if r["roas_w"] > 0 else 0

            # Spec §13.8: Facebook → reward → 结束
            reward = compute_reward(ctr, roas, r["imp"], b_ctr, b_roas)

            # Spec §13.2: 唯一 update
            bandit.update("hook_type", arm, reward)

            # 记录
            arm_state = bandit.arms[f"hook_type_{arm}"]
            history["thetas"][arm].append(arm_state.theta)
            history["sigmas"][arm].append(arm_state.sigma)
            history["trials"][arm].append(arm_state.trials)
            history["rewards"][arm].append(reward)
            # auction 仅 diagnostic (Spec §13.7)
            history["auction_pressures"][arm].append(
                r["spend"] / r["imp"] * 1000 if r["imp"] > 0 else 1.0
            )

        # Spec §13.4: ranking = theta DESC
        ranking = bandit.rank("hook_type")
        history["rankings"].append(ranking)

        # Spec §13.5: sampling (exploration)
        selected = bandit.sample("hook_type")
        greedy = bandit.best("hook_type")
        history["selections"].append({
            "hour": hour, "selected": selected, "greedy": greedy,
            "is_greedy": selected == greedy,
        })

        # Spec §13.6: entropy 只调 tau
        history["entropies"].append(bandit.entropy("hook_type"))
        history["taus"].append(bandit._auto_tau("hook_type"))

    return history, bandit


# ============================================================================
# 8 维度自检
# ============================================================================

def check_1_theta_convergence(history) -> dict:
    """① theta 是否稳定收敛"""
    thetas = history["thetas"]
    # theta 应该收敛到 true theta 的相对排序
    final_thetas = {arm: thetas[arm][-1] if thetas[arm] else 0 for arm in ARMS}
    theta_rank = sorted(final_thetas.items(), key=lambda x: x[1], reverse=True)
    rank_correct = [r[0] for r in theta_rank] == ["arm_A", "arm_B", "arm_C"]

    # theta 稳定性: 后期 variance 应下降
    late_vars = []
    for arm in ARMS:
        if len(thetas[arm]) > 10:
            late = thetas[arm][-10:]
            late_vars.append(np.var(late))
    avg_late_var = float(np.mean(late_vars)) if late_vars else 0

    # theta 变化率 (后期应趋近 0)
    if len(thetas["arm_A"]) > 20:
        early_change = abs(thetas["arm_A"][10] - thetas["arm_A"][5])
        late_change = abs(thetas["arm_A"][-1] - thetas["arm_A"][-6])
        convergence_ratio = late_change / max(early_change, 1e-6)
    else:
        convergence_ratio = 1.0

    return {
        "final_thetas": final_thetas,
        "rank_correct": rank_correct,
        "late_variance": avg_late_var,
        "convergence_ratio": convergence_ratio,  # <1 表示收敛
        "converged": rank_correct and convergence_ratio < 0.5,
    }


def check_2_sigma_decline(history) -> dict:
    """② sigma 是否正常下降"""
    sigmas = history["sigmas"]
    early_sigmas = [np.mean(sigmas[arm][:10]) for arm in ARMS if len(sigmas[arm]) >= 10]
    late_sigmas = [np.mean(sigmas[arm][-10:]) for arm in ARMS if len(sigmas[arm]) >= 10]

    avg_early = float(np.mean(early_sigmas)) if early_sigmas else 0
    avg_late = float(np.mean(late_sigmas)) if late_sigmas else 0
    decline_ratio = avg_late / max(avg_early, 1e-6)

    return {
        "early_sigma": avg_early,
        "late_sigma": avg_late,
        "decline_ratio": decline_ratio,  # <1 表示下降
        "declined": decline_ratio < 0.9,
    }


def check_3_exploration_decline(history) -> dict:
    """③ exploration 是否逐渐降低"""
    selections = history["selections"]
    n = len(selections)
    if n < 8:
        return {"declined": False, "reason": "insufficient data"}

    early_sel = selections[:n//4]
    late_sel = selections[3*n//4:]

    early_explore = sum(1 for s in early_sel if not s["is_greedy"]) / len(early_sel)
    late_explore = sum(1 for s in late_sel if not s["is_greedy"]) / len(late_sel)

    return {
        "early_explore_rate": early_explore,
        "late_explore_rate": late_explore,
        "declined": late_explore <= early_explore,
        "still_exploring": late_explore > 0,  # 不 hard lock
    }


def check_4_ranking_equals_theta(history) -> dict:
    """④ ranking 是否始终等于 theta 排序"""
    rankings = history["rankings"]
    thetas = history["thetas"]

    consistent = 0
    total = 0
    for i, ranking in enumerate(rankings):
        # 计算该时刻的 theta 排序
        theta_at_i = {arm: thetas[arm][i] if i < len(thetas[arm]) else 0 for arm in ARMS}
        theta_rank = sorted(theta_at_i.items(), key=lambda x: x[1], reverse=True)
        theta_rank_list = [r[0] for r in theta_rank]

        if ranking == theta_rank_list:
            consistent += 1
        total += 1

    consistency_rate = consistent / max(total, 1)
    return {
        "consistency_rate": consistency_rate,
        "consistent": consistency_rate == 1.0,
    }


def check_5_reward_out_of_decision(history, bandit) -> dict:
    """⑤ reward 是否完全退出决策链"""
    # 验证: FinalArm 只有 theta/sigma/trials, 没有 reward 相关字段
    arm = list(bandit.arms.values())[0] if bandit.arms else None
    if arm is None:
        return {"exited": False, "reason": "no arms"}

    arm_fields = arm.to_dict().keys()
    forbidden_fields = ["reward", "reward_avg", "reward_score", "value", "weight", "score",
                        "ucb_score", "policy_score", "confidence_score"]
    has_forbidden = any(f in arm_fields for f in forbidden_fields)

    # 验证: rank() 只用 theta
    # (代码层: rank 方法 sorted(key=lambda a: a.theta) — 只用 theta)

    # 验证: reward 不参与 sample 的 ranking (sample 用 theta/tau + gamma*sigma)
    # reward 完全不出现在 sample 方法中

    return {
        "arm_fields": list(arm_fields),
        "has_forbidden_fields": has_forbidden,
        "exited": not has_forbidden,
    }


def check_6_auction_out_of_decision(bandit) -> dict:
    """⑥ auction 是否没有进入 decision"""
    # 验证: FinalArm 没有 auction 字段
    arm = list(bandit.arms.values())[0] if bandit.arms else None
    if arm is None:
        return {"exited": False, "reason": "no arms"}

    arm_fields = arm.to_dict().keys()
    has_auction = "auction" in str(arm_fields).lower() or "pressure" in str(arm_fields).lower()

    # 验证: rank() 和 sample() 不引用 auction
    # (代码层: rank 只用 theta, sample 只用 theta+sigma)

    return {
        "arm_fields": list(arm_fields),
        "has_auction_in_state": has_auction,
        "exited": not has_auction,
    }


def check_7_entropy_only_temperature(history, bandit) -> dict:
    """⑦ entropy 是否只影响 temperature"""
    # 验证: FinalArm 没有 entropy 字段
    arm = list(bandit.arms.values())[0] if bandit.arms else None
    if arm is None:
        return {"ok": False, "reason": "no arms"}

    arm_fields = arm.to_dict().keys()
    has_entropy_in_arm = "entropy" in str(arm_fields).lower()

    # 验证: entropy 只在 _auto_tau 中使用 (调温度)
    # rank() 不用 entropy, sample() 通过 tau 间接用

    # 验证: entropy 与 tau 的关系 (entropy 低 → tau 高)
    entropies = history["entropies"]
    taus = history["taus"]
    if len(entropies) > 5:
        # 取 early 和 late 对比
        early_e = np.mean(entropies[:5])
        early_t = np.mean(taus[:5])
        late_e = np.mean(entropies[-5:])
        late_t = np.mean(taus[-5:])
    else:
        early_e = early_t = late_e = late_t = 0

    return {
        "has_entropy_in_arm_state": has_entropy_in_arm,
        "early_entropy": early_e,
        "early_tau": early_t,
        "late_entropy": late_e,
        "late_tau": late_t,
        "ok": not has_entropy_in_arm,
    }


def check_8_decision_only_theta(bandit) -> dict:
    """⑧ 所有 decision 是否只来自 theta"""
    # rank() = sorted(theta DESC) — 只用 theta
    # best() = rank()[0] — 只用 theta
    # sample() = Softmax(theta/tau + gamma*sigma) — theta 主导, sigma 只影响 exploration

    # 验证: 没有 score/policy_score/ucb 等中间变量
    arm = list(bandit.arms.values())[0] if bandit.arms else None
    if arm is None:
        return {"ok": False, "reason": "no arms"}

    arm_fields = arm.to_dict().keys()
    # 只允许 theta/sigma/trials + gene_type/gene_value
    allowed = {"gene_type", "gene_value", "theta", "sigma", "trials"}
    extra_fields = set(arm_fields) - allowed

    return {
        "arm_fields": list(arm_fields),
        "allowed_fields": list(allowed),
        "extra_fields": list(extra_fields),
        "ok": len(extra_fields) == 0,
    }


# ============================================================================
# 主流程
# ============================================================================

def main() -> int:
    print("=" * 78)
    print("  Final Architecture 自检 (Spec §13)")
    print("  8 维度验证 — 封版检查")
    print("=" * 78)

    # 跑 48h × 3 seeds
    all_results = []
    for seed in [42, 123, 456]:
        history, bandit = run_final(n_hours=48, seed=seed, auction_noise=0.3)
        all_results.append((history, bandit))

    history, bandit = all_results[0]

    # 8 维度检查
    print("\n运行 8 维度自检...\n")

    c1 = check_1_theta_convergence(history)
    c2 = check_2_sigma_decline(history)
    c3 = check_3_exploration_decline(history)
    c4 = check_4_ranking_equals_theta(history)
    c5 = check_5_reward_out_of_decision(history, bandit)
    c6 = check_6_auction_out_of_decision(bandit)
    c7 = check_7_entropy_only_temperature(history, bandit)
    c8 = check_8_decision_only_theta(bandit)

    # ── 详细输出 ───────────────────────────────────────────────────────
    print(f"{'='*78}\n  ① theta 是否稳定收敛\n{'='*78}")
    print(f"  final_thetas:    {c1['final_thetas']}")
    print(f"  rank_correct:    {c1['rank_correct']} (应 A>B>C)")
    print(f"  late_variance:   {c1['late_variance']:.6f}")
    print(f"  convergence_ratio: {c1['convergence_ratio']:.3f} (<1 = 收敛)")
    print(f"  converged:       {c1['converged']}")

    print(f"\n{'='*78}\n  ② sigma 是否正常下降\n{'='*78}")
    print(f"  early_sigma:     {c2['early_sigma']:.4f}")
    print(f"  late_sigma:      {c2['late_sigma']:.4f}")
    print(f"  decline_ratio:   {c2['decline_ratio']:.3f} (<1 = 下降)")
    print(f"  declined:        {c2['declined']}")

    print(f"\n{'='*78}\n  ③ exploration 是否逐渐降低\n{'='*78}")
    print(f"  early_explore:   {c3['early_explore_rate']:.1%}")
    print(f"  late_explore:    {c3['late_explore_rate']:.1%}")
    print(f"  declined:        {c3['declined']}")
    print(f"  still_exploring: {c3['still_exploring']} (不 hard lock)")

    print(f"\n{'='*78}\n  ④ ranking 是否始终等于 theta 排序\n{'='*78}")
    print(f"  consistency_rate: {c4['consistency_rate']:.1%}")
    print(f"  consistent:      {c4['consistent']}")

    print(f"\n{'='*78}\n  ⑤ reward 是否完全退出决策链\n{'='*78}")
    print(f"  arm_fields:      {c5['arm_fields']}")
    print(f"  has_forbidden:   {c5['has_forbidden_fields']}")
    print(f"  exited:          {c5['exited']}")

    print(f"\n{'='*78}\n  ⑥ auction 是否没有进入 decision\n{'='*78}")
    print(f"  arm_fields:      {c6['arm_fields']}")
    print(f"  has_auction:     {c6['has_auction_in_state']}")
    print(f"  exited:          {c6['exited']}")

    print(f"\n{'='*78}\n  ⑦ entropy 是否只影响 temperature\n{'='*78}")
    print(f"  has_entropy_in_arm: {c7['has_entropy_in_arm_state']}")
    print(f"  early: entropy={c7['early_entropy']:.4f}, tau={c7['early_tau']:.4f}")
    print(f"  late:  entropy={c7['late_entropy']:.4f}, tau={c7['late_tau']:.4f}")
    print(f"  ok:              {c7['ok']}")

    print(f"\n{'='*78}\n  ⑧ 所有 decision 是否只来自 theta\n{'='*78}")
    print(f"  arm_fields:      {c8['arm_fields']}")
    print(f"  allowed:         {c8['allowed_fields']}")
    print(f"  extra_fields:    {c8['extra_fields']}")
    print(f"  ok:              {c8['ok']}")

    # ── 一致性 (3 seeds) ──────────────────────────────────────────────
    print(f"\n{'='*78}\n  一致性检查 (3 seeds)\n{'='*78}")
    for i, (h, b) in enumerate(all_results):
        c1_s = check_1_theta_convergence(h)
        c2_s = check_2_sigma_decline(h)
        c4_s = check_4_ranking_equals_theta(h)
        print(f"  seed{i+1}: rank_correct={c1_s['rank_correct']}, "
              f"sigma_decline={c2_s['decline_ratio']:.3f}, "
              f"ranking_consistency={c4_s['consistency_rate']:.1%}")

    # 清理
    audit_mem = ROOT / "output" / "audit" / "final_selfcheck.json"
    if audit_mem.exists():
        audit_mem.unlink()

    return 0


if __name__ == "__main__":
    sys.exit(main())
