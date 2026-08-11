#!/usr/bin/env python3
"""Policy Network Trainer — 从 rl_state_t 训练 Policy Model

将 offline_rl_dataset (state_t, action_t, reward_t) 转换成训练数据，
训练 Contextual Bandit Policy Network。

训练流程:
  1. 从 DuckDB 加载 rl_state_t 或 unified_state
  2. 特征编码 + target 构建
  3. 训练 PolicyModel (PyTorch 或 Linear)
  4. 评估 + 保存模型

用法:
  python -m market_ops.creative_intelligence.policy_trainer --db db/facebook_performance.duckdb
  python -m market_ops.creative_intelligence.policy_trainer --db db/facebook_performance.duckdb --table unified_state --backend linear
  python -m market_ops.creative_intelligence.policy_trainer --db db/facebook_performance.duckdb --epochs 200 --output output/policy_v1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.policy_network import (
    HAS_TORCH,
    FEATURE_COLUMNS,
    PolicyModel,
    PolicyPrediction,
)


# ============================================================================
# 数据加载
# ============================================================================

def load_training_data(
    db_path: str | Path,
    table: str = "rl_state_t",
    min_reward: float = 0.0,
    min_spend: float = 0.0,
    max_rows: int = 0,
) -> list[dict]:
    """从 DuckDB 加载训练数据

    Args:
        db_path: DuckDB 路径
        table: 表名 (rl_state_t 或 unified_state)
        min_reward: 最低 reward 过滤
        min_spend: 最低 spend 过滤
        max_rows: 最大行数限制 (0=不限制)
    """
    conn = duckdb.connect(str(db_path), read_only=True)

    # 检查表是否存在
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name = ?", [table]
    ).fetchall()
    if not tables:
        print(f"  ❌ 表 {table} 不存在")
        conn.close()
        return []

    # 检查列 — 看看哪些 feature columns 实际存在
    existing_cols = conn.execute(f"SELECT * FROM {table} LIMIT 0").description
    existing_col_names = {c[0].lower() for c in existing_cols}
    available_features = [f for f in FEATURE_COLUMNS if f.lower() in existing_col_names]
    missing = [f for f in FEATURE_COLUMNS if f.lower() not in existing_col_names]
    if missing:
        print(f"  ⚠️  缺失特征列 ({len(missing)}/{len(FEATURE_COLUMNS)}): {missing}")

    # 构建 SQL
    select_cols = []
    for f in FEATURE_COLUMNS:
        if f.lower() in existing_col_names:
            select_cols.append(f)
        else:
            select_cols.append(f"0 AS {f}")

    # 添加 creative_id (推理需要)
    if "creative_id" in existing_col_names:
        select_cols.append("creative_id")
    if "date" in existing_col_names:
        select_cols.append("date")

    where_clauses = []
    if min_reward > 0:
        where_clauses.append(f"reward >= {min_reward}")
    if min_spend > 0:
        where_clauses.append(f"spend >= {min_spend}")

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    limit = f"LIMIT {max_rows}" if max_rows > 0 else ""

    sql = f"SELECT {', '.join(select_cols)} FROM {table} {where} ORDER BY date {limit}"
    print(f"  SQL: {sql[:200]}...")

    result = conn.execute(sql)
    col_names = [desc[0] for desc in result.description]
    rows = [dict(zip(col_names, row)) for row in result.fetchall()]

    conn.close()
    print(f"  加载 {len(rows)} 行训练数据 (table={table})")
    return rows


# ============================================================================
# 训练
# ============================================================================

def train(
    rows: list[dict],
    backend: str = "auto",
    epochs: int = 100,
    batch_size: int = 64,
    output_path: str | Path | None = None,
    verbose: bool = True,
) -> PolicyModel:
    """训练 PolicyModel

    Args:
        rows: 训练数据行
        backend: "torch" | "linear" | "auto"
        epochs: 训练轮数 (仅 PyTorch)
        batch_size: batch 大小 (仅 PyTorch)
        output_path: 模型保存路径 (None=不保存)
        verbose: 打印训练日志
    """
    eff_backend = backend
    if eff_backend == "auto":
        eff_backend = "torch" if HAS_TORCH else "linear"
    elif eff_backend == "torch" and not HAS_TORCH:
        print("  ⚠️  PyTorch 不可用, 回退到 linear")
        eff_backend = "linear"

    print(f"\n  Backend: {eff_backend}")
    print(f"  Rows: {len(rows)}")
    if eff_backend == "torch":
        print(f"  Epochs: {epochs}, Batch size: {batch_size}")

    model = PolicyModel(backend=eff_backend)
    history = model.fit(rows, epochs=epochs, batch_size=batch_size, verbose=verbose)

    if output_path:
        model.save(output_path)
        print(f"\n  模型已保存: {output_path}")

    return model, history


# ============================================================================
# 评估
# ============================================================================

def evaluate(
    model: PolicyModel,
    rows: list[dict],
    top_k: int = 5,
) -> dict:
    """评估模型

    指标:
      - 概率分布: min/max/mean/std of serve_prob
      - 集中度: top-1/top-3/top-5 占比
      - 与真实 reward 的排序一致性 (Kendall tau)
    """
    # 按 creative_id 聚合: 取最新日期的 state
    creative_states: dict[str, dict] = {}
    for r in rows:
        cid = r.get("creative_id", "unknown")
        if cid not in creative_states:
            creative_states[cid] = r
        else:
            # 保留更新的
            existing_date = creative_states[cid].get("date", "")
            new_date = r.get("date", "")
            if new_date > existing_date:
                creative_states[cid] = r

    cids = list(creative_states.keys())
    state_rows = [creative_states[c] for c in cids]

    if len(cids) < 2:
        return {"error": "不足 2 个 creative, 无法评估"}

    predictions = model.predict_for_creatives(state_rows, cids)

    # 排序
    sorted_preds = sorted(predictions, key=lambda p: p.serve_prob, reverse=True)

    # 概率分布统计
    probs = [p.serve_prob for p in predictions]
    prob_stats = {
        "min": round(min(probs), 4),
        "max": round(max(probs), 4),
        "mean": round(float(np.mean(probs)), 4),
        "std": round(float(np.std(probs)), 4),
    }

    # 集中度
    top_1_share = sum(p.serve_prob for p in sorted_preds[:1])
    top_3_share = sum(p.serve_prob for p in sorted_preds[:min(3, len(sorted_preds))])
    top_5_share = sum(p.serve_prob for p in sorted_preds[:min(5, len(sorted_preds))])
    concentration = {
        "top_1": round(top_1_share, 4),
        "top_3": round(top_3_share, 4),
        "top_5": round(top_5_share, 4),
    }

    # 与真实 reward 的排序一致性
    true_rewards = [float(creative_states[c].get("reward", 0) or 0) for c in cids]
    pred_probs = [p.serve_prob for p in predictions]

    # Spearman rank correlation
    from scipy.stats import spearmanr
    try:
        rho, p_value = spearmanr(true_rewards, pred_probs)
    except Exception:
        rho, p_value = 0.0, 1.0

    ranking_corr = {
        "spearman_rho": round(float(rho), 4),
        "p_value": round(float(p_value), 4),
    }

    result = {
        "n_creatives": len(cids),
        "prob_distribution": prob_stats,
        "concentration": concentration,
        "ranking_correlation": ranking_corr,
        "top_5": [
            {
                "creative_id": p.creative_id,
                "serve_prob": p.serve_prob,
                "budget_weight": p.budget_weight,
                "exploration_score": p.exploration_score,
                "ctr_pred": p.ctr_pred,
                "roas_pred": p.roas_pred,
                "risk_pred": p.risk_pred,
                "true_reward": round(float(creative_states[p.creative_id].get("reward", 0) or 0), 4),
            }
            for p in sorted_preds[:min(top_k, len(sorted_preds))]
        ],
    }

    return result


# ============================================================================
# 对比 FinalBandit
# ============================================================================

def compare_with_bandit(
    model: PolicyModel,
    rows: list[dict],
    bandit_theta: dict[str, float],  # creative_id → theta
) -> dict:
    """对比 PolicyNetwork vs FinalBandit 的排序结果"""
    # 按 creative_id 聚合
    creative_states: dict[str, dict] = {}
    for r in rows:
        cid = r.get("creative_id", "unknown")
        if cid not in creative_states:
            creative_states[cid] = r

    # 只保留两边都有的 creative
    common = set(creative_states.keys()) & set(bandit_theta.keys())
    if len(common) < 2:
        return {"error": f"仅有 {len(common)} 个共同 creative, 无法对比"}

    cids = sorted(common)
    state_rows = [creative_states[c] for c in cids]

    # Policy 预测
    predictions = model.predict_for_creatives(state_rows, cids)
    policy_ranking = sorted(predictions, key=lambda p: p.serve_prob, reverse=True)
    policy_rank = {p.creative_id: i for i, p in enumerate(policy_ranking)}

    # Bandit 排名
    bandit_ranking = sorted(bandit_theta.items(), key=lambda x: x[1], reverse=True)
    bandit_rank = {cid: i for i, (cid, _) in enumerate(bandit_ranking) if cid in common}

    # 排名对比
    rank_diff = {}
    for cid in common:
        pr = policy_rank.get(cid, 999)
        br = bandit_rank.get(cid, 999)
        rank_diff[cid] = {
            "policy_rank": pr,
            "bandit_rank": br,
            "delta": pr - br,
            "theta": bandit_theta.get(cid, 0),
        }

    # 统计
    diffs = [abs(v["delta"]) for v in rank_diff.values()]
    agreements = sum(1 for v in rank_diff.values() if v["delta"] == 0)

    return {
        "n_common": len(common),
        "rank_agreement": round(agreements / len(common), 4),
        "mean_rank_diff": round(float(np.mean(diffs)), 2),
        "max_rank_diff": int(max(diffs)),
        "top_match": policy_ranking[0].creative_id == bandit_ranking[0][0] if bandit_ranking else False,
        "details": dict(sorted(rank_diff.items(), key=lambda x: abs(x[1]["delta"]), reverse=True)[:5]),
    }


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Policy Network Trainer — 从 rl_state_t 训练 Policy Model",
    )
    parser.add_argument("--db", type=str, default="db/facebook_performance.duckdb",
                        help="DuckDB 数据库路径")
    parser.add_argument("--table", type=str, default="rl_state_t",
                        help="数据表名 (rl_state_t 或 unified_state)")
    parser.add_argument("--backend", type=str, default="auto",
                        choices=["auto", "torch", "linear"],
                        help="模型后端: auto/torch/linear")
    parser.add_argument("--epochs", type=int, default=100,
                        help="训练轮数 (仅 PyTorch)")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Batch 大小 (仅 PyTorch)")
    parser.add_argument("--output", type=str, default="output/policy_model",
                        help="模型保存路径 (不含扩展名)")
    parser.add_argument("--min-reward", type=float, default=0.0,
                        help="最低 reward 过滤")
    parser.add_argument("--min-spend", type=float, default=0.0,
                        help="最低 spend 过滤")
    parser.add_argument("--max-rows", type=int, default=0,
                        help="最大训练行数 (0=不限制)")
    parser.add_argument("--evaluate", action="store_true",
                        help="仅评估已有模型, 不训练")
    parser.add_argument("--compare-bandit", type=str, default=None,
                        help="与 FinalBandit memory JSON 对比 (path)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Policy Network Trainer")
    print("=" * 60)
    print(f"  DB: {args.db}")
    print(f"  Table: {args.table}")
    print(f"  Backend: {args.backend}")
    print(f"  PyTorch available: {HAS_TORCH}")

    if args.evaluate:
        # 仅评估
        print("\n  [Evaluate] 加载已有模型...")
        model = PolicyModel.load(args.output)
        rows = load_training_data(args.db, args.table, args.min_reward, args.min_spend, args.max_rows)
        if not rows:
            print("  ❌ 无数据")
            return 1
        result = evaluate(model, rows)
        print(f"\n  📊 评估结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # 训练
    rows = load_training_data(args.db, args.table, args.min_reward, args.min_spend, args.max_rows)
    if not rows:
        print("  ❌ 无训练数据")
        return 1

    model, history = train(
        rows,
        backend=args.backend,
        epochs=args.epochs,
        batch_size=args.batch_size,
        output_path=args.output,
        verbose=True,
    )

    # 评估
    print("\n" + "=" * 60)
    print("  评估")
    print("=" * 60)
    eval_result = evaluate(model, rows)
    print(json.dumps(eval_result, indent=2, ensure_ascii=False))

    # 与 Bandit 对比
    if args.compare_bandit:
        bandit_path = Path(args.compare_bandit)
        if bandit_path.exists():
            with open(bandit_path, "r", encoding="utf-8") as f:
                bandit_data = json.load(f)
            bandit_theta = {}
            for key, arm in bandit_data.get("arms", {}).items():
                cid = arm.get("gene_value", key)
                bandit_theta[cid] = arm.get("theta", 0)
            print(f"\n  📊 与 FinalBandit 对比 ({len(bandit_theta)} arms):")
            cmp = compare_with_bandit(model, rows, bandit_theta)
            print(json.dumps({k: v for k, v in cmp.items() if k != "details"}, indent=2, ensure_ascii=False))

    # 保存评估结果
    eval_path = Path(args.output).with_suffix(".eval.json")
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "backend": args.backend,
            "n_rows": len(rows),
            "evaluation": eval_result,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  评估结果已保存: {eval_path}")

    return 0


if __name__ == "__main__":
    main()