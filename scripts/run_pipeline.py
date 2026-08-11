#!/usr/bin/env python3
"""FinalBandit Production Pipeline — 一键执行

完整流程:
  Step 1: 数据导入 (creative_library + creative_features)
  Step 2: 特征构建 → variant 表
  Step 2.5: Contextual State 构建
  Step 2.6: Unified State 构建 (MDP-ready)
  Step 3: FinalBandit 学习 (7 天模拟 backfill) + Reward Stabilizer + Policy Stabilizer
  Step 4: 投放策略输出
  Step 4.5: Distribution Controller 流量分配预算 (original FinalBandit-based)
  Step 4.6: Policy Budget Allocator (new policy-based, 替换决策层)
  Step 5: 信号引导 Prompt 生成
  Step 6: Autonomous Execution (NEW) — Policy → FacebookExecutor → Meta Ads

收敛约束 (Convergence Constraints):
  1. Reward Stabilizer: EMA 平滑 + cohort 归一化, 消除 ROAS 延迟噪声
  2. Policy Stabilizer: MutationRate = f(performance) + 全局探索衰减
  3. Distribution Controller: Top 20% → 70% budget, 防止分布漂移
  4. Policy Budget Allocator: state_t → PolicyNetwork → probability distribution → budget

生产级保护 (Step 6):
  P1: Budget Clamp     — budget = clip(budget, 0.2 * avg, 2.0 * avg)  防爆
  P2: Exploration Floor — p_i = max(p_i, 0.02)                         永不归零
  P3: Kill-Switch       — ROAS < threshold → fallback to Bandit        熔断

用法:
  python3 scripts/run_pipeline.py
  python3 scripts/run_pipeline.py --days 14
  python3 scripts/run_pipeline.py --no-stabilizers                       # 对比测试
  python3 scripts/run_pipeline.py --autonomous                          # 启用 autonomous 执行层
  python3 scripts/run_pipeline.py --policy-model xgboost                # Policy Budget Allocator
  python3 scripts/run_pipeline.py --policy-model hybrid                 # Hybrid mode
  python3 scripts/run_pipeline.py --policy-model pure                   # Pure policy (no bandit)
"""
from __future__ import annotations

import json
import math
import os
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
from market_ops.creative_intelligence.iap_observation import (
    CreativeObservation,
    QualityScoreBuilder,
)
from market_ops.creative_intelligence.reward_stabilizer import RewardStabilizer, unified_reward
from market_ops.creative_intelligence.policy_stabilizer_core import PolicyStabilizerCore
from market_ops.creative_intelligence.distribution_controller import DistributionController
from market_ops.creative_intelligence.contextual_state_builder import ContextualStateBuilder
from market_ops.creative_intelligence.unified_state_builder import UnifiedStateBuilder
from market_ops.creative_intelligence.policy_execution_bridge import (
    PolicyExecutionBridge,
    BridgeConfig,
    BridgeResult,
)
from market_ops.creative_intelligence.policy_budget_allocator import (
    NeuralPolicyRanker, XGBoostRanker, LightGBMRanker,
    PolicyBudgetAllocator, build_state_batch_from_db, build_state_batch_from_bandit,
)
from market_ops.creative_intelligence.rl_dataset_builder import RLDatasetBuilder


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
    # 注意: DuckDB 索引 DELETE bug — 直接 DELETE 会导致 index corruption
    # 改用 INSERT OR REPLACE 自动覆盖已存在的 variant_id,
    # stale variants (上次 run 有但本次无 creative_performance 数据) 不影响学习结果
    # 如需强制清理, 手动运行: DROP INDEX + DELETE + CREATE INDEX

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
# Step 2.5: Contextual State 构建 — Bandit → Contextual Bandit 桥梁
# ============================================================================

def step2_5_build_contextual_state(db_path: Path) -> dict:
    """构建 contextual_state 表 — 四维状态空间

    将 creative_performance + creative_features 合并为 state_t
    覆盖: 投放环境 (CPM/拍卖压力) + 创意 (Hook/情感/视觉) + 经济 (ROAS/CPI)
    缺失: 用户 (geo/平台) — 需要 Facebook Insights breakdowns
    """
    print("\n" + "━" * 60)
    print("  Step 2.5: Contextual State 构建")
    print("━" * 60)

    builder = ContextualStateBuilder(db_path)
    try:
        count = builder.build()
        return {
            "contextual_state_rows": count,
            "status": "ok",
        }
    finally:
        builder.close()


# ============================================================================
# Step 2.6: Unified State 构建 — MDP-ready state_t (三系统统一)
# ============================================================================

def step2_6_build_unified_state(db_path: Path) -> dict:
    """构建 unified_state 表 — 三系统 → MDP-ready state_t

    每个 creative 在每个时间窗口的完整 {s_t, a_t, r_t, s_{t+1}}
    三系统: Facebook (creative_performance + ad_graph) + Adjust (app_events)
           + Creative Graph (creative_features + creative_graph)

    s_t = {identity, creative, delivery, user_outcome, economic, derived}
    a_t = {action_taken, budget_change, mutation_flag, bid_change}
    r_t = {reward, reward_type}
    s_{t+1} = next row (creative_id + date)
    """
    print("\n" + "━" * 60)
    print("  Step 2.6: Unified State 构建 (MDP-ready)")
    print("━" * 60)

    builder = UnifiedStateBuilder(db_path)
    try:
        count = builder.build()
        summary = builder.query_mdp_summary()
        return {
            "unified_state_rows": count,
            "unique_creatives": summary.get("unique_creatives", 0),
            "states_with_s_t_plus_1": summary.get("states_with_s_t_plus_1", 0),
            "states_with_reward": summary.get("states_with_reward_gt_0", 0),
            "states_with_action": summary.get("states_with_action", 0),
            "avg_reward": summary.get("avg_reward", 0),
            "status": "ok",
        }
    finally:
        builder.close()


# ============================================================================
# Step 2.7: RL Dataset 构建 — 164 素材评分 → RL-ready
# ============================================================================

def step2_7_build_rl_dataset(db_path: Path) -> dict:
    """构建 rl_state_t 表 — 164 素材评分系统 → RL 训练数据集

    不改业务逻辑, 只做数据结构迁移:
      creative_scores (164) + creative_performance (1315) + ad_graph (641)
      → rl_state_t (919) + action_log (124)

    reward = 0.6 * normalize(roas) + 0.3 * normalize(purchases) + 0.1 * normalize(ctr)
    """
    print("\n" + "━" * 60)
    print("  Step 2.7: RL Dataset 构建 (164 素材 → RL-ready)")
    print("━" * 60)

    builder = RLDatasetBuilder(db_path)
    try:
        summary = builder.build()
        return {
            "rl_state_rows": summary.get("total_states", 0),
            "scored_creatives": summary.get("scored_creatives", 0),
            "states_with_reward": summary.get("states_with_reward", 0),
            "avg_reward": summary.get("avg_reward", 0),
            "action_log_rows": summary.get("action_log_rows", 0),
            "status": "ok",
        }
    finally:
        builder.close()


# ============================================================================
# Step 3: FinalBandit 学习
# ============================================================================

def step3_learn(
    db_path: Path,
    n_days: int = 7,
    seed: int = 42,
    project: str | None = None,
    reward_stabilizer: RewardStabilizer | None = None,
    policy_core: PolicyStabilizerCore | None = None,
) -> tuple[dict, dict | None, FinalBandit]:
    """FinalBandit 模拟 N 天 backfill 学习

    project: 限定项目 (如 'P04'), None = 全量
    reward_stabilizer: Reward 稳定器 (EMA 平滑 + cohort 归一化)
    policy_core: Policy Stabilizer Core — 统一 T(t) 控制器, 驱动 Bandit 更新/选择/预算/变异

    Returns:
        (results, directives_guide) — directives_guide 是 T(t)-guided 变异指令
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

        # baseline (保留用于排序/对比，不进入 Bandit)
        all_cpis = [a["cpi"] for a in arms if a["cpi"] < 999]
        all_roas = [a.get("roas", 0) for a in arms]
        b_cpi = float(np.median(all_cpis)) if all_cpis else 10
        b_roas = float(np.median(all_roas)) if all_roas else 0.1

        # IAP Observation Layer: 用 QualityScoreBuilder 替换旧的 0.6*roas+0.4*cpi
        # Spec §9.1: FinalBandit 只接收 quality_score
        quality_builder = QualityScoreBuilder()

        for day in range(n_days):
            date_str = f"2026-07-{1+day:02d}"
            for arm in arms:
                gv = arm["gene_value"]
                if monitor.has_learned_on_date(gt, gv, date_str):
                    monitor.log_duplicate_reject(gt, gv, date_str)
                    continue
                if arm["installs"] < 1:
                    continue

                # 构造 CreativeObservation（arm 是按 gene_value 聚合的，creative_id 用 gv 占位）
                imp = int(arm["imp"])
                ctr = float(arm["ctr"])
                clicks = int(ctr / 100.0 * imp) if imp > 0 else 0
                installs = int(arm["installs"])
                spend = float(arm["spend"])
                roas_d7 = float(arm.get("roas", 0))

                obs = CreativeObservation(
                    creative_id=f"arm:{gv}",
                    date=date_str,
                    impression=imp,
                    click=clicks,
                    ctr=ctr,
                    install=installs,
                    spend=spend,
                    roas_d7=roas_d7,
                )
                obs.cvr = installs / max(clicks, 1)
                obs.cpi = spend / max(installs, 1)
                obs.ipm = installs / max(imp, 1) * 1000

                qs = quality_builder.build(obs)

                # Anti-noise: 不过门槛不进 Bandit (Spec §7)
                if not qs.sufficient_data:
                    continue

                # FinalBandit 只接收 quality_score (Spec §9.1)
                # 加微小噪声避免同分同列，clamp 到 [0,1]
                raw_reward = max(0.0, min(1.0, qs.score + rng.gauss(0, 0.01)))

                # 收敛约束 1/3: Reward 稳定器 — EMA 平滑 + cohort 归一化
                if reward_stabilizer:
                    arm_key = f"{gt}_{gv}"
                    smoothed = reward_stabilizer.smooth(arm_key, raw_reward)
                    reward_stabilizer.update_cohort(gt, smoothed)
                    reward = reward_stabilizer.normalize(arm_key, smoothed, cohort_key=gt)
                else:
                    reward = raw_reward

                # Policy Stabilizer Core: T(t) 直接驱动 Bandit 更新
                # theta += alpha * delta * T, sigma = (1-beta*T)*sigma + beta*abs(delta)
                if policy_core:
                    policy_core.update_bandit(bandit, gt, gv, reward)
                else:
                    bandit.update(gt, gv, reward)

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

    # 收敛约束: Policy Stabilizer Core — 生成 T(t)-guided 变异指令
    directives_guide = None
    if policy_core:
        # 聚合所有 gene_type 的 state
        directives_guide = {}
        for gene_type in gene_types:
            state = bandit.get_state(gene_type)
            if state["n_arms"] < 2:
                continue
            arms = state.get("arms", {})
            sorted_arms = sorted(arms.items(), key=lambda x: x[1]["theta"], reverse=True)
            best_gv, best = sorted_arms[0]
            worst_gv, worst = sorted_arms[-1]

            # 基于 T(t) 的变异指令
            avoid = []
            if worst["theta"] < 0 and worst["sigma"] < 0.20:
                avoid.append(worst_gv)

            directives_guide[gene_type] = {
                "target": best_gv if best["theta"] > 0.05 else None,
                "avoid": avoid,
                "rate": round(policy_core.mutation_strength, 4),
                "mutation_type": policy_core.mutation_type(),
                "reason": f"T={policy_core.temperature:.3f}, phase={policy_core.phase}, "
                          f"winner={best_gv}(theta={best['theta']:.3f},sigma={best['sigma']:.3f})",
            }

        # 保存 directives
        directives_path = ROOT / "output" / "pipeline_directives.json"
        with open(directives_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "policy_core": policy_core.stats(),
                "directives": directives_guide,
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  Policy Stabilizer Directives 已保存: {directives_path}")
        for gt, gd in directives_guide.items():
            print(f"    [{gt}] T={policy_core.temperature:.3f}, phase={policy_core.phase}, "
                  f"mutation={policy_core.mutation_type()}, "
                  f"target={gd.get('target')}, avoid={gd.get('avoid')}")

        # 推进时间步
        policy_core.advance()

    # 最终快照
    monitor.take_snapshot()
    dashboard_data = monitor.export_dashboard_data()
    dashboard_path = ROOT / "output" / "monitor" / "current_state.json"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Monitor 快照已保存: {dashboard_path}")

    return results, directives_guide, bandit


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
# Step 4.5: Distribution Controller — 流量分配预算
# ============================================================================

def step4_5_allocate_budget(
    results: dict,
    distribution_controller: DistributionController | None = None,
    total_budget: float = 1000.0,
    policy_core: PolicyStabilizerCore | None = None,
) -> dict | None:
    """收敛约束 3/3: Distribution Controller — 流量分配 + budget gating

    T(t) 模式: budget_i ∝ softmax(theta_i / T)
    固定模式: Top 20% → 70%, Middle 30% → 20%, Bottom 50% → 10%
    """
    if not distribution_controller:
        return None

    print("\n" + "━" * 60)
    mode_str = f"T(t)={policy_core.temperature:.3f}" if policy_core else "固定分层"
    print(f"  Step 4.5: Distribution Controller — 流量分配 ({mode_str})")
    print("━" * 60)

    # 从 bandit ranking 构建 ranking 列表
    ranking = []
    for gt, r in sorted(results.items()):
        if r.get("status") != "ok" or not r.get("ranking"):
            continue
        for arm in r["ranking"]:
            ranking.append({
                "creative_id": f"{gt}:{arm['gene_value']}",
                "theta": arm["theta"],
                "sigma": arm["sigma"],
                "trials": arm["trials"],
            })

    if not ranking:
        print("  ⚠️ 无可用 ranking, 跳过预算分配")
        return None

    proj = next((r.get("gene_value", "default") for r in ranking if r["creative_id"].startswith("game:")), "default")

    if policy_core:
        plan = distribution_controller.allocate_softmax(
            proj, ranking, total_budget=total_budget, temperature=policy_core.temperature,
        )
    else:
        plan = distribution_controller.allocate(proj, ranking, total_budget=total_budget)

    print(f"  Total Budget: \${total_budget:,.0f}")
    print(f"  Tier Summary: {plan.tier_summary}")
    for a in plan.allocations:
        print(f"    [{a.tier}] {a.creative_id}: "
              f"\${a.budget_share * total_budget:,.0f} ({a.budget_share:.1%}) — {a.reason}")

    # 保存
    budget_path = ROOT / "output" / "pipeline_budget.json"
    with open(budget_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": plan.project,
            "total_budget": plan.total_budget,
            "tier_summary": plan.tier_summary,
            "allocations": [
                {
                    "creative_id": a.creative_id,
                    "theta": a.theta,
                    "sigma": a.sigma,
                    "trials": a.trials,
                    "tier": a.tier,
                    "budget_share": a.budget_share,
                    "budget_amount": round(a.budget_share * total_budget, 2),
                    "reason": a.reason,
                }
                for a in plan.allocations
            ],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  预算分配已保存: {budget_path}")

    return {
        "project": plan.project,
        "tier_summary": plan.tier_summary,
        "allocations": [a.budget_share for a in plan.allocations],
    }


# ============================================================================
# Step 4.6: Policy Budget Allocator — 替换 FinalBandit 决策层
# ============================================================================

def step4_6_policy_allocate(
    db_path: Path,
    results: dict,
    bandit: FinalBandit,
    policy_core: PolicyStabilizerCore | None = None,
    total_budget: float = 1000.0,
    model_type: str = "xgboost",
    use_hybrid: bool = True,
) -> dict | None:
    """Policy Budget Allocator — 从 state_t → policy distribution → budget

    替换:
      FinalBandit(theta) → softmax → budget allocation
      ↓
      PolicyNetwork → probability distribution → budget allocation

    支持两种模式:
      - pure policy:   model.predict(state_t) → softmax → budget
      - hybrid:        0.6*policy + 0.3*bandit + 0.1*explore → softmax → budget

    Args:
        db_path: DuckDB 路径
        results: step3_learn 的结果
        bandit: FinalBandit 实例 (hybrid 模式需要)
        policy_core: PolicyStabilizerCore (驱动 T(t))
        total_budget: 总预算
        model_type: "xgboost" | "lightgbm"
        use_hybrid: 是否使用 hybrid 模式
    """
    print("\n" + "━" * 60)
    mode_str = "Hybrid" if use_hybrid else "Policy Only"
    print(f"  Step 4.6: Policy Budget Allocator — {mode_str} ({model_type})")
    print("━" * 60)

    # 1. 初始化 Policy Model
    if model_type == "neural":
        model = NeuralPolicyRanker()
    elif model_type == "lightgbm":
        model = LightGBMRanker()
    else:
        model = XGBoostRanker()

    # 尝试加载已训练的模型
    model_dir = ROOT / "output" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    if model_type == "neural":
        model_path = ROOT / "output" / "policy_model"
    else:
        model_path = model_dir / f"{model_type}_ranker.json"
    if model_path.exists():
        model.load(model_path)
        print(f"  Model loaded: {model_path}")
    else:
        print(f"  Model not found ({model_path}), using heuristic fallback")

    # 2. 初始化 PolicyBudgetAllocator
    T = policy_core.temperature if policy_core else 1.0
    allocator = PolicyBudgetAllocator(
        policy_model=model,
        temperature=T,
        memory_path=ROOT / "output" / "stabilizers" / "policy_budget_allocator.json",
    )

    # 3. 从 unified_state 构建 state_batch
    project = None
    for gt, r in results.items():
        if r.get("status") == "ok" and r.get("ranking"):
            project = r["ranking"][0].get("gene_value", None)
            if project:
                break

    state_batch = build_state_batch_from_db(db_path, project=project, limit=50)
    if not state_batch:
        print("  ⚠️ unified_state 表为空, 跳过 policy budget 分配")
        return None

    # 注入 bandit 的 theta/sigma
    state_batch = build_state_batch_from_bandit(bandit, state_batch)

    print(f"  State batch: {len(state_batch)} creatives")

    # 4. 分配预算
    if use_hybrid:
        plan = allocator.allocate_hybrid(
            state_batch, bandit, total_budget=total_budget,
            temperature=T,
        )
    else:
        plan = allocator.allocate(
            state_batch, total_budget=total_budget, temperature=T,
        )

    # 5. 输出结果
    print(f"  Mode: {plan.mode}, Temperature: {plan.temperature:.3f}")
    print(f"  Total Budget: ${total_budget:,.0f}")
    print(f"  {'Creative':<30} {'Prob':>8} {'Budget':>10} {'ROAS':>8} {'Explore':>8}")
    print(f"  {'─'*30} {'─'*8} {'─'*10} {'─'*8} {'─'*8}")

    for a in sorted(plan.allocations, key=lambda x: x.probability, reverse=True)[:10]:
        print(f"  {a.creative_id:<30} {a.probability:>8.4f} "
              f"${a.budget:>9.0f} {a.expected_roas:>8.3f} {a.exploration_score:>8.4f}")

    if len(plan.allocations) > 10:
        print(f"  ... and {len(plan.allocations) - 10} more")

    # 6. 保存
    budget_path = ROOT / "output" / "policy_budget.json"
    with open(budget_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": plan.mode,
            "model": model.name,
            "temperature": plan.temperature,
            "total_budget": total_budget,
            "meta": plan.meta,
            "allocations": plan.to_dict()["allocations"],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Policy Budget 已保存: {budget_path}")

    # 7. 训练模型 (如果有 XGBoost/LightGBM 可用且 unified_state 有足够数据)
    _try_train_model(db_path, model, model_path)

    return {
        "mode": plan.mode,
        "model": model.name,
        "n_creatives": len(plan.allocations),
        "temperature": plan.temperature,
    }


def _try_train_model(
    db_path: Path,
    model: XGBoostRanker | LightGBMRanker | NeuralPolicyRanker,
    model_path: Path,
) -> None:
    """尝试从 unified_state 训练 policy model

    训练数据: unified_state 中 reward > 0 的行 → X (features) + y (reward)
    """
    try:
        import duckdb
        conn = duckdb.connect(str(db_path), read_only=True)

        # 检查 unified_state 是否有足够数据
        count = conn.execute(
            "SELECT COUNT(*) FROM unified_state WHERE reward > 0"
        ).fetchone()[0]
        if count < 20:
            conn.close()
            return

        # 提取特征和目标
        col_str = ", ".join(f'COALESCE({c}, 0) as {c}' for c in [
            "ctr", "cpm", "spend", "installs", "roas_d7", "cpi", "ipm",
            "engagement_score", "conversion_rate", "retention_proxy",
            "cohort_age", "impressions", "clicks",
        ])
        rows = conn.execute(f"""
            SELECT {col_str}, reward
            FROM unified_state
            WHERE reward > 0
            ORDER BY date DESC
            LIMIT 500
        """).fetchall()

        if len(rows) < 20:
            conn.close()
            return

        X = np.array([list(r[:-1]) for r in rows], dtype=np.float64)
        y = np.array([r[-1] for r in rows], dtype=np.float64)

        conn.close()

        # 训练
        if isinstance(model, NeuralPolicyRanker):
            # Neural model: 使用 policy_trainer 的逻辑
            from market_ops.creative_intelligence.policy_network import PolicyModel as NNPolicyModel
            nn_model = NNPolicyModel(backend="linear")
            # 构建 dict rows
            col_names = [
                "ctr", "cpm", "spend", "installs", "roas_d7", "cpi", "ipm",
                "engagement_score", "conversion_rate", "retention_proxy",
                "cohort_age", "impressions", "clicks", "reward",
            ]
            dict_rows = [dict(zip(col_names, list(r))) for r in rows]
            nn_model.fit(dict_rows, epochs=50, batch_size=32, verbose=False)
            nn_model.save(model_path)
            model._nn_model = nn_model
            model._fitted = True
        else:
            model.fit(X, y)
            model.save(model_path)
        print(f"  Model trained on {len(rows)} samples, saved to {model_path}")

    except Exception as e:
        # 训练失败不影响主流程
        print(f"  Model training skipped: {e}")


# ============================================================================
# Step 5: 创意 Prompt 生成
# ============================================================================

def step5_generate_prompts(results: dict, directives_guide: dict | None = None) -> str:
    """基于 winner 特征组合, 生成下一轮裂变图片 prompt

    directives_guide: Policy Stabilizer Core 的输出, 用于引导变异方向
    """
    print("\n" + "━" * 60)
    print("  Step 5: AI 裂变 Prompt 生成")
    print("━" * 60)

    # 收集所有 winner — 以 theta 排名第一为准，不要求 match=true
    # match 字段是"theta 第一 == ROAS 第一"的参照标志，Bandit 用 QualityScore 综合评分
    # （非纯 ROAS），match=False 是正常的，不应阻塞闭环
    winners = {}
    for gt, r in results.items():
        if r.get("status") == "ok" and r.get("ranking"):
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

    # 收敛约束 2/3: Policy Stabilizer — 信号引导的 prompt 变异
    color_guide = directives_guide.get("color_tone", {}) if directives_guide else {}
    layout_guide = directives_guide.get("layout", {}) if directives_guide else {}

    # 基于信号生成定向 variant
    color_variant = color_guide.get("target", color) if color_guide.get("target") else color
    color_avoid = color_guide.get("avoid", [])
    layout_variant = layout_guide.get("target", layout) if layout_guide.get("target") else layout

    mutation_rate = color_guide.get("rate", 0.5)

    lines.append("---\n")
    lines.append("## 推荐 Prompt (5 个变体)\n")

    if directives_guide:
        lines.append(f"> **Policy Stabilizer 引导**: mutation_rate={mutation_rate:.2f}\n")
        for gt, gd in directives_guide.items():
            if gd.get("target") or gd.get("avoid"):
                lines.append(f"> - **{gt}**: target=`{gd.get('target')}`, avoid={gd.get('avoid')}, "
                            f"rate={gd.get('rate', 0):.2f}, reason={gd.get('reason', '')}\n")
        lines.append("")

    # 信号引导的定向 prompt: 优先使用 winner 特征, 但避开 avoid 值
    avoid_color_str = f"avoid {', '.join(color_avoid)} tones" if color_avoid else ""
    explore_mode = "explore" if mutation_rate > 0.4 else "exploit"

    prompts = [
        # Variant 1: 纯利用 winner 特征
        f"{game} mobile game ad, {color} color tone, {layout} layout, "
        f"show exciting merge gameplay, bright gems and magical effects, "
        f"clear CTA button, high CTR mobile game creative",

        # Variant 2: 利用 winner + 定向探索
        f"{game} puzzle game screenshot, {color_variant} palette, {layout} composition, "
        f"dramatic before-after moment, witch character casting spell, "
        f"bold text overlay 'Can You Solve This?', viral game ad style, {avoid_color_str}",

        # Variant 3: 利用 winner 特征
        f"{game} casual game ad creative, {color} tones, {layout_variant} structure, "
        f"progress bar showing level completion, reward chest opening, "
        f"satisfying game moment, high conversion mobile ad",

        # Variant 4: 探索方向 (基于 mutation_rate)
        f"{game} merge game scene, {color_variant} aesthetic, {layout} design, "
        f"multiple items merging with particle effects, coin shower reward, "
        f"engaging hook in first 3 seconds, Facebook ad format 1:1, {explore_mode} mode",

        # Variant 5: 动态方向
        f"{game} fantasy game ad, {color} mood, {layout_variant} visual flow, "
        f"character close-up with emotional expression, urgent situation, "
        f"simple UI overlay with download button, optimized for mobile feed, {avoid_color_str}",
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
# Step 5.1: Creative Strategy Matrix — 显式生图决策矩阵
# ============================================================================

def step5_1_creative_strategy(results: dict, game_category: str = "casual",
                              countries: list[str] | None = None) -> dict:
    """基于 CreativeStrategyMatrix 生成策略驱动的生图指导

    Game × Country × Audience → Style/Emotion/Color/Composition/Camera/Lighting
    """
    print("\n" + "━" * 60)
    print("  Step 5.1: Creative Strategy Matrix — 策略驱动生图")
    print("━" * 60)

    import importlib
    matrix_mod = importlib.import_module(
        "market_ops.creative_growth_loop.05_prompt.creative_strategy_matrix"
    )
    CreativeStrategyMatrix = matrix_mod.CreativeStrategyMatrix

    mx = CreativeStrategyMatrix()
    if not countries:
        countries = ["US", "JP", "CN", "DE", "BR"]

    # 收集 winner audience 信息（如有）
    winners = {}
    for gt, r in results.items():
        if r.get("status") == "ok" and r.get("ranking"):
            winners[gt] = r["ranking"][0]["gene_value"]

    audience_segment = "casual"  # 默认
    if "audience" in winners:
        audience_segment = winners["audience"]

    strategy_output = {
        "game_category": game_category,
        "audience": audience_segment,
        "countries": {},
        "ab_variants": [],
    }

    # 每个国家的策略
    for country in countries:
        strat = mx.get_strategy(game_category, country, audience_segment)
        strategy_output["countries"][country] = strat.to_dict()
        explanation = mx.explain_strategy(strat)
        print(f"\n  [{country}] style={strat.style} | emotion={strat.emotion} | color={strat.color_palette}")
        print(f"         composition={strat.composition} | camera={strat.camera_angle} | lighting={strat.lighting}")

    # 生成 A/B 测试变体
    ab_variants = mx.get_ab_test_strategies(game_category, countries[0], audience_segment, n_variants=3)
    for name, strat in ab_variants:
        strategy_output["ab_variants"].append({
            "variant_name": name,
            **strat.to_dict(),
        })

    print(f"\n  A/B 变体: {len(ab_variants)} 组")
    for name, strat in ab_variants:
        print(f"    - {name}: {strat.emotion} / {strat.color_palette}")

    # 保存
    out_path = ROOT / "output" / "creative_strategy_matrix.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(strategy_output, f, indent=2, ensure_ascii=False)
    print(f"\n  策略矩阵已保存: {out_path}")

    return strategy_output


# ============================================================================
# Step 5.2: Copy Generator — 多语言文案生成
# ============================================================================

def step5_2_copy_generation(results: dict, game_category: str = "casual",
                            countries: list[str] | None = None) -> dict:
    """基于 CopyGenerator 生成多语言文案变体

    输出每个国家的 Headline / Primary Text / Description / CTA 文案
    """
    print("\n" + "━" * 60)
    print("  Step 5.2: Copy Generator — 多语言文案生成")
    print("━" * 60)

    import importlib
    copy_mod = importlib.import_module(
        "market_ops.creative_growth_loop.05_prompt.copy_generator"
    )
    CopyGenerator = copy_mod.CopyGenerator

    # 从 winner 中提取 hook/reward/emotion，构造一个模拟 gene 对象
    winners = {}
    for gt, r in results.items():
        if r.get("status") == "ok" and r.get("ranking"):
            winners[gt] = r["ranking"][0]["gene_value"]

    # 构造 Mock Gene（duck typing，只需要 hook / reward / emotion）
    class MockGene:
        hook: str = winners.get("hook_type", "curiosity")
        reward: str = winners.get("reward", "treasure")
        emotion: str = winners.get("emotion", "excited")

    gene = MockGene()
    gen = CopyGenerator()

    if not countries:
        countries = ["US", "JP", "CN", "DE", "BR"]

    copy_output = {
        "game_category": game_category,
        "countries": {},
    }

    for country in countries:
        variants = gen.generate_variants(gene, game_category, country, audience="casual", count=5)
        copy_output["countries"][country] = [v.to_dict() for v in variants]
        print(f"\n  [{country}] language={variants[0].copies.language}")
        for i, v in enumerate(variants[:3]):  # 只打印前3个
            print(f"    V{i+1} headline: {v.copies.headline}")
            print(f"       CTA: {v.copies.cta}")

    # 保存
    out_path = ROOT / "output" / "copy_variants.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(copy_output, f, indent=2, ensure_ascii=False)
    print(f"\n  文案变体已保存: {out_path}")

    return copy_output


# ============================================================================
# Step 5.3: Campaign Strategy — 投放结构生成
# ============================================================================

def step5_3_campaign_strategy(results: dict, game_category: str = "casual",
                               countries: list[str] | None = None,
                               daily_budget: float = 500.0,
                               project_name: str = "P04") -> dict:
    """基于 CampaignStrategyBuilder 生成 Campaign/AdSet 投放结构配置

    自动选择 ABO/CBO/ASC，构建 Targeting、Budget、Bid 策略
    """
    print("\n" + "━" * 60)
    print("  Step 5.3: Campaign Strategy — 投放结构生成")
    print("━" * 60)

    import importlib
    strategy_mod = importlib.import_module(
        "market_ops.creative_growth_loop.14_publish.campaign_strategy"
    )
    CampaignStrategyBuilder = strategy_mod.CampaignStrategyBuilder
    CampaignStrategy = strategy_mod.CampaignStrategy

    if not countries:
        countries = ["US", "JP", "CN"]

    sb = CampaignStrategyBuilder()

    # 构建完整投放结构
    full = sb.build_full_campaign(
        project_name=project_name,
        daily_budget=daily_budget,
        countries=countries,
        game_category=game_category,
        adset_count=len(countries),
        is_broad=False,
        target_cpi=None,
    )

    campaign = full["campaign"]
    adsets = full["adsets"]

    print(f"\n  Campaign: {campaign.name}")
    print(f"    Strategy: {campaign.strategy.value}")
    print(f"    Objective: {campaign.objective.value}")
    print(f"    Status: {campaign.status}")
    print(f"\n  AdSets ({len(adsets)}):")
    for adset in adsets:
        budget_dollars = adset.daily_budget / 100
        targeting = adset.targeting
        print(f"    - {adset.name}")
        print(f"      daily_budget: ${budget_dollars:.2f}")
        print(f"      countries: {targeting.countries}")
        print(f"      optimization: {adset.optimization_goal.value}")
        print(f"      bid_strategy: {adset.bid_strategy.value}")

    # 保存
    campaign_output = {
        "campaign": campaign.to_dict(),
        "adsets": [a.to_dict() for a in adsets],
    }

    out_path = ROOT / "output" / "campaign_strategy.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(campaign_output, f, indent=2, ensure_ascii=False)
    print(f"\n  投放结构已保存: {out_path}")

    return campaign_output


# ============================================================================
# Step 6: Autonomous Execution — Policy → FacebookExecutor → Meta Ads
# ============================================================================

def step6_autonomous_execute(
    results: dict,
    bandit: FinalBandit,
    policy_core: PolicyStabilizerCore | None = None,
    distribution_controller: DistributionController | None = None,
    adset_mapping: dict[str, str] | None = None,
    total_budget: float = 1000.0,
    dry_run: bool = True,
    facebook_config: dict | None = None,
) -> dict | None:
    """Autonomous Execution Layer — 策略输出 → 真实资金执行

    这是整个系统的最后接口层，将"策略输出"变成"真实资金执行"。

    流程:
      1. 从 Bandit + PolicyStabilizerCore 获取策略概率分布
      2. PolicyExecutionBridge 执行:
         P3: Kill-Switch 检查
         P2: Exploration Floor
         P1: Budget Clamp
      3. 概率 → 预算 → FacebookExecutor → Meta Ads

    Args:
        results: Step 3 的学习结果
        bandit: FinalBandit 实例
        policy_core: PolicyStabilizerCore (T(t) 控制器)
        distribution_controller: DistributionController
        adset_mapping: {gene_type:gene_value → adset_id} 映射
        total_budget: 总日预算
        dry_run: 模拟模式 (不调用 Facebook API)
        facebook_config: Facebook 配置 {access_token, ad_account_id, api_version}

    Returns:
        执行结果摘要
    """
    print("\n" + "━" * 60)
    mode_str = "DRY RUN (模拟)" if dry_run else "LIVE (真实 Facebook API)"
    print(f"  Step 6: Autonomous Execution — {mode_str}")
    print("━" * 60)

    if not adset_mapping:
        print("  ⚠️  无 adset_mapping 配置, 跳过 autonomous 执行")
        print("     请通过 --adset-mapping 传入, 如: game:P04=adset_id_1,game:P07=adset_id_2")
        return None

    # ── KPI Rulebook + DecisionBoundary 审计 ──────────────────────────
    print("\n  📋 KPI 规则审计 (KpiActionRulebook + DecisionBoundary)")
    try:
        from market_ops.kpi_action_rulebook import KpiActionRulebook, KpiMetric, ActionType
        from market_ops.decision_boundary import DecisionBoundary, DecisionCategory, DecisionDomain

        rb = KpiActionRulebook()
        db = DecisionBoundary()

        # 汇总全局KPI指标（聚合所有 winner arm）
        global_spend = 0.0
        global_imp = 0
        global_clicks = 0
        global_installs = 0
        global_ctr_sum = 0.0
        global_ctr_n = 0
        global_roas_sum = 0.0
        global_roas_w = 0.0
        for gt, r in results.items():
            if r.get("status") == "ok" and r.get("ranking"):
                for arm in r.get("ranking", [])[:5]:
                    global_spend += float(arm.get("spend", 0))
                    global_imp += int(arm.get("imp", 0))
                    if arm.get("ctr", 0) > 0:
                        global_ctr_sum += float(arm["ctr"])
                        global_ctr_n += 1
                    if arm.get("roas", 0) > 0 and float(arm.get("spend", 0)) > 0:
                        global_roas_sum += float(arm["roas"]) * float(arm["spend"])
                        global_roas_w += float(arm["spend"])

        avg_ctr = global_ctr_sum / global_ctr_n if global_ctr_n > 0 else 0
        avg_cpm = (global_spend / global_imp * 1000) if global_imp > 0 else 0
        avg_cpi = (global_spend / global_installs) if global_installs > 0 else 0
        avg_roas = (global_roas_sum / global_roas_w) if global_roas_w > 0 else 0

        metrics = {
            KpiMetric.CTR: avg_ctr,
            KpiMetric.CPM: avg_cpm,
            KpiMetric.CPI: avg_cpi,
            KpiMetric.ROAS: avg_roas,
            KpiMetric.SPEND: global_spend,
            KpiMetric.IMPRESSIONS: global_imp,
        }

        kpi_result = rb.evaluate_with_context(metrics, min_spend=1.0, min_impressions=100)
        print(f"    CTR: {avg_ctr:.2f}%  CPM: ${avg_cpm:.2f}  CPI: ${avg_cpi:.2f}  ROAS: {avg_roas:.2f}")
        print(f"    规则决策: {kpi_result['decision'].value}")
        if kpi_result.get("triggered_rules"):
            for rule_id in kpi_result["triggered_rules"][:3]:
                print(f"    - {rule_id}")

        # 决策域审计
        print(f"\n  🔒 决策域审计 (DecisionBoundary)")
        budget_audit = db.audit_decision(DecisionCategory.BUDGET_ALLOCATION, DecisionDomain.RULE)
        creative_audit = db.audit_decision(DecisionCategory.IMAGE_STYLE, DecisionDomain.AI)
        print(f"    BUDGET_ALLOCATION → RULE: {'✅' if budget_audit['valid'] else '❌'} {budget_audit['message']}")
        print(f"    IMAGE_STYLE → AI: {'✅' if creative_audit['valid'] else '❌'} {creative_audit['message']}")

    except Exception as e:
        print(f"    ⚠️  KPI 审计跳过: {e}")

    # 初始化 FacebookExecutor (live 模式)
    executor = None
    if not dry_run:
        fb_config = facebook_config or {}
        token = fb_config.get("access_token") or os.environ.get("META_ACCESS_TOKEN", "")
        account_id = fb_config.get("ad_account_id") or os.environ.get("META_AD_ACCOUNT_ID", "")
        if not token or not account_id:
            print("  ⚠️  LIVE 模式需要 access_token 和 ad_account_id")
            print("     设置环境变量 META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 或传入 facebook_config")
            dry_run = True
        else:
            try:
                from market_ops.creative_intelligence.facebook_executor import FacebookExecutor
                executor = FacebookExecutor(
                    access_token=token,
                    ad_account_id=account_id,
                    api_version=fb_config.get("api_version", "v22.0"),
                )
                print(f"  ✅ FacebookExecutor 已初始化 (account: {account_id})")
            except Exception as e:
                print(f"  ❌ FacebookExecutor 初始化失败: {e}")
                dry_run = True

    # 初始化 PolicyExecutionBridge
    bridge = PolicyExecutionBridge(
        policy_core=policy_core,
        distribution_controller=distribution_controller,
        facebook_executor=executor,
        adset_mapping=adset_mapping,
        config=BridgeConfig(total_budget=total_budget),
        memory_path=ROOT / "output" / "stabilizers" / "policy_execution_bridge.json",
    )

    print(f"\n  Bridge 配置:")
    print(f"    P1 Budget Clamp: [{bridge.config.budget_clamp_min_ratio}, {bridge.config.budget_clamp_max_ratio}] × avg")
    print(f"    P2 Exploration Floor: {bridge.config.exploration_floor}")
    print(f"    P3 Kill-Switch: ROAS < {bridge.config.kill_switch_roas_threshold}")
    print(f"    Total Budget: ${bridge.config.total_budget:,.0f}")
    print(f"    Adset Mapping: {len(adset_mapping)} 个映射")

    # 收集 reward 历史 (从 results 提取)
    reward_history = _extract_reward_history(results)

    # 执行: Bandit → Policy → Bridge → Facebook
    print(f"\n  ── 执行 Policy → Budget → Facebook ──")
    bridge_results = bridge.execute_from_bandit(
        bandit=bandit,
        reward_history=reward_history,
        dry_run=dry_run,
    )

    if not bridge_results:
        print("  ⚠️  无可用 policy 输出, 跳过执行")
        return None

    # 汇总
    print(f"\n  ── 执行结果汇总 ──")
    summary = {
        "mode": "dry_run" if dry_run else "live",
        "total_budget": total_budget,
        "n_gene_types": len(bridge_results),
        "gene_types": {},
        "convergence": bridge.convergence_state if bridge_results else "unknown",
        "protections": {},
    }

    for gene_type, br in bridge_results.items():
        gt_summary = {
            "policy_output": br.policy_output,
            "protected_output": br.protected_output,
            "budget_plan": br.budget_plan,
            "execution": br.execution_result,
        }
        summary["gene_types"][gene_type] = gt_summary

        print(f"    [{gene_type}]")
        print(f"      Policy: { {k: f'{v:.1%}' for k, v in br.policy_output.items()} }")
        if br.protected_output != br.policy_output:
            print(f"      Protected: { {k: f'{v:.1%}' for k, v in br.protected_output.items()} }")
        print(f"      Budget: { {k: f'${v:,.0f}' for k, v in br.budget_plan.items()} }")
        print(f"      Protections: kill_switch={br.protections.get('kill_switch', {}).get('active', False)}, "
              f"convergence={br.convergence.get('action', 'hold')}")

    summary["protections"] = {
        "kill_switch_active": bridge._kill_switch_active,
        "convergence_state": bridge.convergence_state,
    }

    # 保存结果
    bridge_path = ROOT / "output" / "autonomous_execution.json"
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bridge_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bridge_stats": bridge.stats(),
            "summary": summary,
            "results": {gt: br.to_dict() for gt, br in bridge_results.items()},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Autonomous Execution 结果已保存: {bridge_path}")

    return summary


def _extract_reward_history(results: dict) -> list[float]:
    """从 results 提取 reward 历史 (ROAS 值)"""
    rewards: list[float] = []
    for gt, r in results.items():
        if r.get("status") != "ok" or not r.get("ranking"):
            continue
        for arm in r["ranking"]:
            roas = arm.get("roas", 0)
            if roas > 0:
                rewards.append(roas)
    return rewards


# ============================================================================
# Step 6 LIVE: 真实 Facebook API 发布
# ============================================================================

def step6_live_publish(
    results: dict,
    campaign_config_path: Path | None = None,
    copy_variants_path: Path | None = None,
    image_dir: str = "",
    app_link: str = "",
    access_token: str = "",
    ad_account_id: str = "",
    api_version: str = "v22.0",
    dry_run: bool = True,
) -> dict | None:
    """真实 Facebook API 发布 — 从 campaign_strategy.json 创建完整投放结构

    完整链路：
      1. 读取 campaign_strategy.json → CampaignConfig + AdSetConfig
      2. 读取 copy_variants.json → Headlines / Primary Texts
      3. FacebookPublisher.create_campaign → 真实 Campaign
      4. FacebookPublisher.create_adset → 真实 AdSet(s)
      5. FacebookPublisher.create_ad_creatives → 广告创意（使用 Step 5.2 文案）
      6. FacebookPublisher.create_ads → 广告

    Args:
        results: FinalBandit 学习结果
        campaign_config_path: campaign_strategy.json 路径
        copy_variants_path: copy_variants.json 路径
        image_dir: 生成图片目录（扫描 .png）
        app_link: App 下载链接
        access_token: Facebook API Access Token
        ad_account_id: Facebook Ad Account ID
        dry_run: True = 仅打印计划，不调用 API

    Returns:
        执行结果字典
    """
    print("\n" + "━" * 60)
    mode_str = "DRY RUN (仅预览)" if dry_run else "LIVE (真实 Facebook API)"
    print(f"  Step 6 LIVE: 真实 Facebook 发布 — {mode_str}")
    print("━" * 60)

    if dry_run:
        print("\n  [DRY RUN] 以下操作将在 LIVE 模式执行:")
        print("    1. FacebookPublisher.create_campaign()")
        print("    2. FacebookPublisher.create_adset() × N")
        print("    3. FacebookPublisher.create_ad_creatives()")
        print("    4. FacebookPublisher.create_ads() × N")
        print("\n  如需真实发布，请去掉 --dry-run 参数")
        return {"mode": "dry_run", "dry_run": True}

    # ── Step 1: 加载配置 ───────────────────────────────────────────────
    if not campaign_config_path or not campaign_config_path.exists():
        print("  ⚠️  campaign_strategy.json 不存在，跳过")
        return None

    with open(campaign_config_path, encoding="utf-8") as f:
        campaign_data = json.load(f)

    campaign_cfg_data = campaign_data.get("campaign", {})
    adset_cfgs_data = campaign_data.get("adsets", [])

    if not campaign_cfg_data or not adset_cfgs_data:
        print("  ⚠️  Campaign/AdSet 配置为空，跳过")
        return None

    # ── Step 2: 加载文案变体 ─────────────────────────────────────────────
    headlines = ["Play Now!"]
    primary_texts = [""]
    if copy_variants_path and copy_variants_path.exists():
        with open(copy_variants_path, encoding="utf-8") as f:
            copy_data = json.load(f)
        # 提取第一个国家的前3个变体
        first_country = list(copy_data.get("countries", {}).keys())[0] if copy_data.get("countries") else None
        if first_country:
            variants = copy_data["countries"][first_country][:3]
            headlines = [v["copies"]["headline"] for v in variants]
            primary_texts = [v["copies"]["primary_text"] for v in variants]
            print(f"\n  文案变体 ({first_country}): {len(headlines)} 条")

    # ── Step 3: 初始化 FacebookPublisher ───────────────────────────────
    if not access_token or not ad_account_id:
        print("  ⚠️  缺少 access_token 或 ad_account_id，跳过")
        print("     设置环境变量: META_ACCESS_TOKEN / META_AD_ACCOUNT_ID")
        return None

    try:
        import importlib
        pub_mod = importlib.import_module(
            "market_ops.creative_growth_loop.14_publish.facebook_publisher"
        )
        FacebookPublisher = pub_mod.FacebookPublisher
        CampaignConfig = pub_mod.CampaignConfig
        AdSetConfig = pub_mod.AdSetConfig
        OptimizationGoal = pub_mod.OptimizationGoal
        BillingEvent = pub_mod.BillingEvent
        BidStrategy = pub_mod.BidStrategy
    except Exception as e:
        print(f"  ❌ FacebookPublisher 导入失败: {e}")
        return None

    publisher = FacebookPublisher(
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=api_version,
    )
    print(f"\n  FacebookPublisher 已初始化 (account: {ad_account_id})")

    # ── Step 4: 创建 Campaign ────────────────────────────────────────────
    import importlib as _imp_mod
    strategy_mod = _imp_mod.import_module(
        "market_ops.creative_growth_loop.14_publish.campaign_strategy"
    )
    CampaignObjective = strategy_mod.CampaignObjective

    campaign_cfg = CampaignConfig(
        name=campaign_cfg_data.get("name", "Pipeline_Campaign"),
        objective=CampaignObjective(campaign_cfg_data.get("objective", "APP_INSTALLS")),
        buying_type=strategy_mod.CampaignBuyingType.AUCTION,
        status="PAUSED",
        special_ad_categories=[],
        strategy=strategy_mod.CampaignStrategy(campaign_cfg_data.get("strategy", "ABO")),
    )

    campaign_id = publisher.create_campaign_from_config(campaign_cfg)
    if not campaign_id:
        print("  ❌ Campaign 创建失败")
        return {"mode": "live", "success": False, "error": "campaign_creation_failed"}

    print(f"\n  ✅ Campaign 创建成功: {campaign_id}")

    # ── Step 5: 创建 AdSets ─────────────────────────────────────────────
    adset_ids: list[str] = []
    for adset_data in adset_cfgs_data:
        targeting_cfg = _build_targeting_from_dict(adset_data.get("targeting", {}))

        adset_cfg = AdSetConfig(
            name=adset_data.get("name", "Pipeline_AdSet"),
            campaign_id=campaign_id,
            daily_budget=adset_data.get("daily_budget", 5000),
            lifetime_budget=adset_data.get("lifetime_budget", 0),
            optimization_goal=OptimizationGoal(adset_data.get("optimization_goal", "APP_INSTALLS")),
            billing_event=BillingEvent.IMPRESSIONS,
            bid_strategy=BidStrategy(adset_data.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")),
            bid_amount=adset_data.get("bid_amount"),
            targeting=targeting_cfg,
            placements=adset_data.get("placements", []),
            attribution_spec=adset_data.get("attribution_spec"),
            status="PAUSED",
        )

        adset_id = publisher.create_adset_from_config(adset_cfg)
        if adset_id:
            adset_ids.append(adset_id)
            print(f"  ✅ AdSet 创建成功: {adset_id}")

    if not adset_ids:
        print("  ❌ 所有 AdSet 创建失败")
        return {"mode": "live", "success": False, "error": "adset_creation_failed"}

    # ── Step 6: 上传图片 + 创建创意 ────────────────────────────────────
    image_hashes: list[str] = []
    if image_dir:
        from pathlib import Path as _Path
        image_paths = list(_Path(image_dir).rglob("*.png"))
        if image_paths:
            image_hashes = publisher.upload_images([str(p) for p in image_paths[:5]])
            print(f"\n  图片上传: {len(image_hashes)} 张成功")

    if not image_hashes:
        # 无图片时，使用纯文案广告（如果 Facebook 支持）
        image_hashes = []

    # ── Step 7: 创建广告创意 ────────────────────────────────────────────
    creative_ids: list[str] = []
    if image_hashes:
        creative_ids = publisher.create_ad_creatives(
            image_hashes=image_hashes,
            headlines=headlines,
            primary_texts=primary_texts,
            call_to_action="INSTALL_MOBILE_APP",
            app_link=app_link,
        )
        print(f"\n  广告创意创建: {len(creative_ids)} 个成功")
    else:
        print("  ⚠️  无图片，跳过创意创建")

    # ── Step 8: 创建广告 ────────────────────────────────────────────────
    all_ad_ids: list[str] = []
    for adset_id in adset_ids:
        ad_names = [f"Pipeline_Ad_{adset_id}_{i}" for i in range(max(1, len(creative_ids)))]
        ad_ids = publisher.create_ads(
            creative_ids=creative_ids if creative_ids else [],
            adset_id=adset_id,
            names=ad_names,
            status="PAUSED",
        )
        all_ad_ids.extend(ad_ids)

    print(f"\n  广告创建: {len(all_ad_ids)} 个")

    # ── 保存结果 ────────────────────────────────────────────────────────
    result = {
        "mode": "live",
        "success": True,
        "campaign_id": campaign_id,
        "adset_ids": adset_ids,
        "creative_ids": creative_ids,
        "ad_ids": all_ad_ids,
        "image_hashes": image_hashes,
        "headlines_used": headlines,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    out_path = ROOT / "output" / "live_publish_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  发布结果已保存: {out_path}")

    print("\n  📋 发布摘要:")
    print(f"     Campaign: {campaign_id}")
    print(f"     AdSets:  {len(adset_ids)} 个")
    print(f"     Ads:     {len(all_ad_ids)} 个")
    print(f"     状态:    PAUSED (需手动激活)")
    print(f"\n  ⚠️  广告当前为 PAUSED 状态")
    print(f"     激活: 在 Facebook Business Manager 中手动启用，或调用:")
    print(f"     FacebookPublisher.update_ad_status(ad_ids, 'ACTIVE')")

    return result


def _build_targeting_from_dict(targeting_dict: dict) -> Any:
    """从字典构建 TargetingConfig（避免直接 import 数字前缀模块）"""
    import importlib
    strategy_mod = importlib.import_module(
        "market_ops.creative_growth_loop.14_publish.campaign_strategy"
    )
    TargetingConfig = strategy_mod.TargetingConfig

    geo = targeting_dict.get("geo_locations", {})
    return TargetingConfig(
        countries=geo.get("countries", ["US"]),
        age_min=targeting_dict.get("age_min", 18),
        age_max=targeting_dict.get("age_max", 65),
        genders=targeting_dict.get("genders", [1, 2]),
        languages=targeting_dict.get("locales", []),
        interests=[
            {"id": i.get("id", ""), "name": i.get("name", "")}
            for i in targeting_dict.get("interests", [])
        ],
        is_broad=False,
    )


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="FinalBandit Production Pipeline")
    parser.add_argument("--days", type=int, default=7, help="模拟学习天数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--project", type=str, default=None, help="限定项目 (如 P04)")
    parser.add_argument("--no-stabilizers", action="store_true", help="禁用三个收敛约束 (仅用于对比测试)")
    parser.add_argument("--total-budget", type=float, default=1000.0, help="Distribution Controller 总预算")
    parser.add_argument("--policy-model", type=str, default=None, choices=["xgboost", "lightgbm", "neural", "hybrid", "pure"],
                        help="启用 Policy Budget Allocator (替换 FinalBandit 决策层): xgboost/lightgbm/neural/hybrid/pure")
    parser.add_argument("--autonomous", action="store_true", help="启用 Autonomous Execution 层 (Policy → FacebookExecutor → Meta Ads)")
    parser.add_argument("--adset-mapping", type=str, default=None,
                        help="Adset ID 映射, 格式: gene_type:gene_value=adset_id,... 如 game:P04=12345,game:P07=67890")
    parser.add_argument("--no-live", action="store_true", help="Autonomous 模式下仍使用 DRY RUN (不调用 Facebook API)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Step 6 LIVE 模式下仅预览，不调用 Facebook API")
    parser.add_argument("--image-dir", type=str, default="",
                        help="Step 6 LIVE 模式使用的图片目录（扫描 .png）")
    parser.add_argument("--app-link", type=str, default="",
                        help="App 下载链接（用于广告 CTA）")
    args = parser.parse_args()

    print("=" * 60)
    print("  FinalBandit Production Pipeline")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ========================================================================
    # 初始化三个收敛约束
    # ========================================================================
    if args.no_stabilizers:
        print("\n  ⚠️ 收敛约束已禁用 (--no-stabilizers)")
        reward_stabilizer = None
        policy_core = None
        distribution_controller = None
    else:
        print("\n  🔒 Policy Stabilizer Core 已启用 (统一 T(t) 控制器)")
        reward_stabilizer = RewardStabilizer(
            ema_alpha=0.3,
            memory_path=output_dir / "stabilizers" / "reward_stabilizer.json",
        )
        policy_core = PolicyStabilizerCore(
            T0=1.0, T_min=0.1, k=0.03,
            memory_path=output_dir / "stabilizers" / "policy_stabilizer_core.json",
        )
        distribution_controller = DistributionController(
            memory_path=output_dir / "stabilizers" / "distribution_controller.json",
        )
        print(f"    Reward Stabilizer (EMA α={reward_stabilizer.ema_alpha})")
        print(f"    Policy Stabilizer Core (T={policy_core.temperature:.3f}, "
              f"phase={policy_core.phase}, k={policy_core.config.k})")
        print(f"    Distribution Controller (cold_start={distribution_controller.cold_start_count})")

    # Step 1
    data_info = step1_import_data(db_path)

    # Step 2
    feature_stats = step2_build_features(db_path)

    # Step 2.5: Contextual State
    state_stats = step2_5_build_contextual_state(db_path)

    # Step 2.6: Unified State (MDP-ready)
    unified_stats = step2_6_build_unified_state(db_path)

    # Step 2.7: RL Dataset (164 素材 → RL-ready)
    rl_stats = step2_7_build_rl_dataset(db_path)

    # Step 3
    results, directives_guide, bandit = step3_learn(
        db_path, n_days=args.days, seed=args.seed, project=args.project,
        reward_stabilizer=reward_stabilizer,
        policy_core=policy_core,
    )

    # Step 4
    step4_strategy(results, data_info)

    # Step 4.5: Distribution Controller (original FinalBandit-based)
    if not args.policy_model:
        step4_5_allocate_budget(
            results, distribution_controller=distribution_controller,
            total_budget=args.total_budget,
            policy_core=policy_core,
        )

    # Step 4.6: Policy Budget Allocator (new policy-based)
    policy_stats = None
    if args.policy_model:
        # Determine model type and hybrid mode
        if args.policy_model == "neural":
            model_type = "neural"
            use_hybrid = True
        elif args.policy_model in ("xgboost", "lightgbm"):
            model_type = args.policy_model
            use_hybrid = True  # default hybrid
        elif args.policy_model == "hybrid":
            model_type = "xgboost"
            use_hybrid = True
        elif args.policy_model == "pure":
            model_type = "xgboost"
            use_hybrid = False
        else:
            model_type = "xgboost"
            use_hybrid = True

        policy_stats = step4_6_policy_allocate(
            db_path, results, bandit,
            policy_core=policy_core,
            total_budget=args.total_budget,
            model_type=model_type,
            use_hybrid=use_hybrid,
        )

    # Step 5
    step5_generate_prompts(results, directives_guide=directives_guide)

    # Step 5.1: Creative Strategy Matrix — 显式生图决策
    game_cat = "casual"
    if args.project and "P04" in args.project:
        game_cat = "match3"
    elif args.project and "rpg" in args.project.lower():
        game_cat = "rpg"
    step5_1_result = step5_1_creative_strategy(results, game_category=game_cat)

    # Step 5.2: Copy Generator — 多语言文案生成
    step5_2_result = step5_2_copy_generation(results, game_category=game_cat)

    # Step 5.3: Campaign Strategy — 投放结构生成
    step5_3_result = step5_3_campaign_strategy(
        results,
        game_category=game_cat,
        daily_budget=args.total_budget,
        project_name=args.project or "P04",
    )

    # Step 6 LIVE: 真实 Facebook API 发布
    live_result = None
    if args.autonomous and not args.no_live:
        campaign_cfg_path = ROOT / "output" / "campaign_strategy.json"
        copy_variants_path = ROOT / "output" / "copy_variants.json"

        from market_ops.config import load_settings
        settings = load_settings()
        access_token = settings.meta_access_token or ""
        ad_account_id = settings.meta_ad_account_id or ""
        api_version = settings.meta_api_version

        live_result = step6_live_publish(
            results=results,
            campaign_config_path=campaign_cfg_path,
            copy_variants_path=copy_variants_path,
            image_dir=args.image_dir,
            app_link=args.app_link,
            access_token=access_token,
            ad_account_id=ad_account_id,
            dry_run=args.dry_run,
            api_version=api_version,
        )

    # Step 6: Autonomous Execution (Policy → FacebookExecutor → Meta Ads)
    autonomous_result = None
    if args.autonomous:
        # 解析 adset_mapping
        adset_mapping = {}
        if args.adset_mapping:
            for pair in args.adset_mapping.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    adset_mapping[k.strip()] = v.strip()
        else:
            # 默认 mapping: 从 bandit 的 gene_type 自动生成
            for gt in results:
                if isinstance(results[gt], dict) and results[gt].get("status") == "ok":
                    adset_mapping[gt] = f"adset_{gt}"

        dry_run = args.no_live or args.no_stabilizers
        autonomous_result = step6_autonomous_execute(
            results=results,
            bandit=bandit,
            policy_core=policy_core,
            distribution_controller=distribution_controller,
            adset_mapping=adset_mapping,
            total_budget=args.total_budget,
            dry_run=dry_run,
        )

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Pipeline 完成! 耗时 {elapsed:.1f}s")
    print(f"  MDP State: {unified_stats.get('unified_state_rows', 0)} 行 "
          f"| s_t+1: {unified_stats.get('states_with_s_t_plus_1', 0)} "
          f"| reward: {unified_stats.get('states_with_reward', 0)} "
          f"| action: {unified_stats.get('states_with_action', 0)}")
    if policy_stats:
        print(f"  Policy Budget: {policy_stats['mode']} mode ({policy_stats['model']}) "
              f"| T={policy_stats['temperature']:.3f} "
              f"| {policy_stats['n_creatives']} creatives")
    if autonomous_result:
        print(f"  Autonomous: {autonomous_result['mode']} mode "
              f"| convergence={autonomous_result.get('convergence', 'unknown')} "
              f"| {autonomous_result['n_gene_types']} gene_types")
    if live_result:
        lr = live_result
        print(f"  LIVE Publish: {lr.get('mode', 'unknown')} mode "
              f"| campaign={lr.get('campaign_id', 'N/A')} "
              f"| adsets={len(lr.get('adset_ids', []))} "
              f"| ads={len(lr.get('ad_ids', []))}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
