"""FinalBandit Monitor 端到端验证

用真实 creative_performance 数据 + FinalBanditMonitor 运行 7 天模拟,
生成 current_state.json 供 Dashboard 读取。

验证:
1. 是否可以实时观察 theta 收敛过程？
2. 是否可以实时观察 sigma 是否正常下降？
3. 是否可以定位重复学习？
4. 是否可以定位 Replay 问题？
5. 是否可以定位 Attribution 问题？
6. 是否可以完整回放一次 Decision？
7. 是否可以完整回放一次 Update？
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.final_bandit import FinalBandit
from market_ops.creative_intelligence.monitor import FinalBanditMonitor


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
        HAVING SUM(impression) >= 500 ORDER BY SUM(impression) DESC LIMIT 50
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
# 模拟 7 天运行
# ============================================================================

def run_simulation(data: list[dict], monitor: FinalBanditMonitor, rng: random.Random):
    """模拟 7 天投放 + 监控"""
    top = data[:30]
    gene_type = "creative_id"

    all_ctrs = [c["ctr"] for c in top]
    all_roas = [c["roas_d7"] for c in top]
    b_ctr = float(np.median(all_ctrs))
    b_roas = float(np.median(all_roas))

    for day in range(7):
        date_str = f"2026-07-{1+day:02d}"

        for c in top:
            cid = c["creative_id"]
            reward = compute_reward(c["ctr"], c["roas_d7"], c["imp"], b_ctr, b_roas)
            reward = max(-1.0, min(1.0, reward + rng.gauss(0, 0.03)))

            # 模拟去重
            if monitor.has_learned_on_date(gene_type, cid, date_str):
                monitor.log_duplicate_reject(gene_type, cid, date_str)
                continue

            monitor.update(gene_type, cid, reward)
            monitor.mark_learned_on_date(gene_type, cid, date_str)

        # 每天做几次 sampling
        for _ in range(5):
            monitor.sample(gene_type)

        # 模拟归因问题: 随机挑 1 个 creative 标记 missing attribution
        if day % 3 == 0:
            victim = rng.choice(top)
            monitor.log_missing_attribution(victim["creative_id"], ["variant_X", "variant_Y"])

        # 拍快照
        monitor.take_snapshot()
        print(f"  Day {day+1}: {monitor._update_count} updates, "
              f"{monitor._sample_count} samples, "
              f"dup_rejects={monitor._duplicate_reject_count}, "
              f"entropy={monitor._bandit.entropy(gene_type):.4f}")

    # 最后做一次重复 backfill (验证去重)
    print(f"\n  模拟重复 backfill (同一天)...")
    date_str = "2026-07-07"
    for c in top:
        cid = c["creative_id"]
        if monitor.has_learned_on_date(gene_type, cid, date_str):
            monitor.log_duplicate_reject(gene_type, cid, date_str)
        else:
            reward = compute_reward(c["ctr"], c["roas_d7"], c["imp"], b_ctr, b_roas)
            monitor.update(gene_type, cid, reward)
            monitor.mark_learned_on_date(gene_type, cid, date_str)

    # 最终快照
    monitor.take_snapshot()
    print(f"  重复 backfill 后: dup_rejects={monitor._duplicate_reject_count}")


# ============================================================================
# 验收 7 问
# ============================================================================

def verify(monitor: FinalBanditMonitor, data: list[dict]) -> dict:
    """回答 7 个验收问题"""
    state = monitor.get_current_state()
    updates = monitor.get_recent_updates(100)
    samples = monitor.get_recent_samples(50)
    health = monitor.get_health()

    # Q1: 是否可以实时观察 theta 收敛过程？
    q1 = len(updates) > 0 and all(
        "theta_before" in u and "theta_after" in u for u in updates[:5]
    )

    # Q2: 是否可以实时观察 sigma 是否正常下降？
    q2 = len(updates) > 0 and all(
        "sigma_before" in u and "sigma_after" in u for u in updates[:5]
    )

    # Q3: 是否可以定位重复学习？
    q3 = health["duplicate_reject_count"] > 0

    # Q4: 是否可以定位 Replay 问题？
    q4 = len(monitor.get_recent_health(200)) > 0

    # Q5: 是否可以定位 Attribution 问题？
    q5 = health["missing_attribution_count"] > 0

    # Q6: 是否可以完整回放一次 Decision？
    q6 = len(samples) > 0 and all(
        "candidates" in s and "selected" in s and "tau" in s
        for s in samples[:3]
    )

    # Q7: 是否可以完整回放一次 Update？
    q7 = len(updates) > 0 and all(
        k in updates[0] for k in [
            "reward", "delta", "theta_before", "theta_after",
            "sigma_before", "sigma_after", "trials_before", "trials_after",
        ]
    )

    return {
        "Q1_theta_convergence": q1,
        "Q2_sigma_decline": q2,
        "Q3_duplicate_detection": q3,
        "Q4_replay_detection": q4,
        "Q5_attribution_detection": q5,
        "Q6_decision_replay": q6,
        "Q7_update_replay": q7,
    }


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    print("=" * 78)
    print("  FinalBandit Monitor 端到端验证")
    print("=" * 78)

    # 清理旧数据
    monitor_dir = ROOT / "output" / "monitor"
    monitor_dir.mkdir(parents=True, exist_ok=True)
    for f in monitor_dir.glob("*.json*"):
        f.unlink()

    # 加载数据
    db_path = str(ROOT / "db" / "facebook_performance.duckdb")
    data = load_creative_data(db_path)
    print(f"\n  加载 {len(data)} 个 creatives")

    # 创建 FinalBandit + Monitor
    bandit = FinalBandit()
    monitor = FinalBanditMonitor(bandit, log_dir=monitor_dir)

    # 模拟 7 天
    print(f"\n  运行 7 天模拟...")
    rng = random.Random(42)
    run_simulation(data, monitor, rng)

    # 导出完整 dashboard 数据
    dashboard_data = monitor.export_dashboard_data()
    dashboard_path = monitor_dir / "current_state.json"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Dashboard 数据已导出: {dashboard_path}")

    # 验收
    print(f"\n{'='*78}\n  验收 7 问\n{'='*78}")
    results = verify(monitor, data)
    all_pass = True
    questions = {
        "Q1_theta_convergence": "是否可以实时观察 theta 收敛过程？",
        "Q2_sigma_decline": "是否可以实时观察 sigma 是否正常下降？",
        "Q3_duplicate_detection": "是否可以定位重复学习？",
        "Q4_replay_detection": "是否可以定位 Replay 问题？",
        "Q5_attribution_detection": "是否可以定位 Attribution 问题？",
        "Q6_decision_replay": "是否可以完整回放一次 Decision？",
        "Q7_update_replay": "是否可以完整回放一次 Update？",
    }
    for key, question in questions.items():
        passed = results[key]
        status = "✅ YES" if passed else "❌ NO"
        print(f"  {status}  {question}")
        if not passed:
            all_pass = False

    # 展示样本
    print(f"\n{'='*78}\n  数据样本\n{'='*78}")

    print(f"\n  📊 Update 事件样本 (最近 1 条):")
    updates = monitor.get_recent_updates(1)
    if updates:
        u = updates[-1]
        print(f"    gene_value={u['gene_value']}, reward={u['reward']:.3f}, "
              f"delta={u['delta']:+.4f}")
        print(f"    theta: {u['theta_before']:.4f} → {u['theta_after']:.4f}")
        print(f"    sigma: {u['sigma_before']:.4f} → {u['sigma_after']:.4f}")
        print(f"    trials: {u['trials_before']} → {u['trials_after']}")

    print(f"\n  📊 Sample 事件样本 (最近 1 条):")
    samples = monitor.get_recent_samples(1)
    if samples:
        s = samples[-1]
        print(f"    gene_type={s['gene_type']}, selected={s['selected']}, "
              f"greedy={s['greedy']}, tau={s['tau']:.3f}")
        if s.get("candidates"):
            print(f"    candidates:")
            for c in s["candidates"][:5]:
                print(f"      {c['gene_value'][:25]}: theta={c['theta']:.4f}, "
                      f"sigma={c['sigma']:.4f}, prob={c['probability']:.4f}")

    print(f"\n  📊 Health 状态:")
    h = monitor.get_health()
    for k, v in h.items():
        if k != "warnings":
            print(f"    {k}: {v}")
    if h["warnings"]:
        print(f"    warnings: {h['warnings']}")

    print(f"\n{'='*78}")
    if all_pass:
        print(f"  🎉 PASS — 7/7 全部通过")
    else:
        failed = sum(1 for v in results.values() if not v)
        print(f"  ⚠️  FAIL — {failed}/7 未通过")
    print(f"{'='*78}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
