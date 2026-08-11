#!/usr/bin/env python3
"""build_offline_rl_dataset.py — 将 rl_state_t (unified_state) 变成 policy learning dataset

从观测日志 → (state, action, reward, next_state) 可训练样本。

两种模式:
  Contextual Bandit:  s_t → a_t → r_t          (推荐先使用)
  Offline RL:         s_t → a_t → r_t → s_{t+1} (进阶)

数据源: unified_state 表 (919 行, 851 unique creatives, 2026-05-27 ~ 2026-06-26)

用法:
  python scripts/build_offline_rl_dataset.py
  python scripts/build_offline_rl_dataset.py --mode bandit   # 仅 contextual bandit
  python scripts/build_offline_rl_dataset.py --mode rl        # 完整 offline RL
  python scripts/build_offline_rl_dataset.py --summary        # 仅打印数据集摘要
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ============================================================================
# 一、State 特征编码
# ============================================================================

# 连续特征列 (直接从 unified_state 取值)
CONTINUOUS_FEATURES = [
    "ctr",           # 点击率
    "cpm",           # 千次展示成本
    "cpc",           # 单次点击成本
    "spend",         # 花费
    "impressions",   # 展示量
    "clicks",        # 点击数
    "installs",      # 安装数
    "p04_events",    # P04 事件 (内购相关)
    "purchase_events",   # 购买事件
    "purchase_value",    # 购买价值
    "roas_d0",       # 当日 ROAS
    "roas_d1",       # D1 ROAS
    "roas_d7",       # D7 ROAS
    "cpi",           # 单次安装成本
    "ipm",           # 千次展示安装
    "arpu_proxy",    # ARPU 代理
    "cohort_age",    # 素材年龄 (天)
    "engagement_score",  # 参与度分数
    "conversion_rate",   # 转化率
    "retention_proxy",   # 留存代理
    "revenue",       # 收入
    "frequency",     # 频次
]

# 类别特征列 → one-hot 映射
CATEGORICAL_FEATURE_MAPS: dict[str, list[str]] = {
    "spend_bucket": ["low", "medium", "high", "very_high"],
    "cpm_bucket": ["low", "medium", "high", "very_high"],
    "hook_type": ["crisis", "reward", "twist", "comparison", "curiosity",
                  "collection", "progress", "mystery", "other", "unknown"],
    "visual_style": ["warm", "cool", "neutral", "unknown"],
    "visual_density": ["low", "medium", "high", "unknown"],
    "emotion_tag": ["surprise", "failure", "success", "reward", "tension",
                    "satisfaction", "neutral", "unknown"],
    "game_mechanic_tag": ["merge", "level", "reward", "collection", "progress",
                          "inventory", "unknown"],
    "ad_status": ["ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "unknown"],
    "project": ["P04", "P04 Witch", "unknown"],
}


def encode_state_vector(row: dict[str, Any]) -> tuple[list[float], list[str]]:
    """将一行 unified_state 编码为 numeric state vector

    Returns:
        (vector, feature_names) — 向量和对应的特征名列表
    """
    vec: list[float] = []
    names: list[str] = []

    # 连续特征
    for feat in CONTINUOUS_FEATURES:
        val = row.get(feat, 0)
        try:
            val = float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            val = 0.0
        # 截断极端值 + log 变换大数值特征
        if feat in ("spend", "impressions", "clicks", "installs",
                     "purchase_events", "purchase_value", "revenue"):
            val = math.log(1 + max(0, val))
        elif feat in ("cpm", "cpc", "cpi"):
            val = min(val, 1000) / 1000  # 归一化到 [0, 1]
        elif feat == "ctr":
            val = min(val, 100) / 100     # 归一化到 [0, 1]
        elif feat == "roas_d0":
            val = min(val, 10) / 10
        elif feat in ("roas_d1", "roas_d7"):
            val = min(val, 5) / 5
        elif feat == "ipm":
            val = math.log(1 + max(0, val))
        elif feat == "cohort_age":
            val = min(val, 60) / 60
        elif feat in ("engagement_score", "conversion_rate", "retention_proxy", "arpu_proxy"):
            val = min(val, 2.0) / 2.0
        elif feat == "frequency":
            val = min(val, 10) / 10
        vec.append(val)
        names.append(feat)

    # 类别特征 → one-hot
    for feat, categories in CATEGORICAL_FEATURE_MAPS.items():
        raw_val = row.get(feat, "unknown") or "unknown"
        for cat in categories:
            vec.append(1.0 if raw_val == cat else 0.0)
            names.append(f"{feat}_{cat}")

    return vec, names


# ============================================================================
# 二、Action 重建 (从历史数据反推)
# ============================================================================

def reconstruct_action(row: dict[str, Any], global_ranks: dict[str, Any]) -> dict[str, Any]:
    """从 unified_state 历史数据反推 action

    由于缺少 action_log 表, 使用 proxy:
      - budget_bucket: 从 spend_bucket 映射
      - exploration_flag: ctr_rank < threshold (前 30% 视为探索)
      - creative_selection_rank: 按 reward 全局排名
      - bid_strategy: 从 cpm_bucket 推断 (high cpm = aggressive bid)
    """
    ctr = float(row.get("ctr", 0) or 0)
    reward = float(row.get("reward", 0) or 0)
    spend_bucket = row.get("spend_bucket", "unknown") or "unknown"
    cpm_bucket = row.get("cpm_bucket", "unknown") or "unknown"
    creative_id = row.get("creative_id", "")

    # budget_bucket 编码
    budget_map = {"low": 0, "medium": 1, "high": 2, "very_high": 3, "unknown": -1}
    budget_bucket = float(budget_map.get(spend_bucket, -1))

    # exploration_flag: 基于 ctr 排名的前 30%
    ctr_rank = global_ranks.get("ctr_rank", {}).get(creative_id, 1.0)
    exploration_flag = 1.0 if ctr_rank < 0.3 else 0.0

    # creative_selection_rank: reward 排名 (0~1, 越小越好)
    reward_rank = global_ranks.get("reward_rank", {}).get(creative_id, 1.0)

    # bid_strategy proxy: 从 cpm_bucket 推断
    bid_map = {"low": 0.0, "medium": 0.33, "high": 0.67, "very_high": 1.0, "unknown": 0.0}
    bid_strategy = bid_map.get(cpm_bucket, 0.0)

    return {
        "budget_bucket": budget_bucket,
        "exploration_flag": exploration_flag,
        "creative_selection_rank": round(reward_rank, 4),
        "bid_strategy": bid_strategy,
        "action_vector": [budget_bucket, exploration_flag, reward_rank, bid_strategy],
    }


# ============================================================================
# 三、Reward 统一标量
# ============================================================================

# 权重 (可调参数)
DEFAULT_REWARD_WEIGHTS = {
    "w_roas": 0.5,      # ROAS D7 权重
    "w_p04": 0.2,       # P04 事件权重
    "w_ctr": 0.15,      # CTR 权重
    "w_retention": 0.15, # 留存代理权重
}


def compute_reward(row: dict[str, Any], weights: dict[str, float] | None = None) -> float:
    """计算统一标量 reward

    reward = w_roas * roas_d7 + w_p04 * log(1 + p04_events) + w_ctr * ctr/100 + w_retention * retention_proxy
    """
    w = weights or DEFAULT_REWARD_WEIGHTS

    roas_d7 = float(row.get("roas_d7", 0) or 0)
    p04 = float(row.get("p04_events", 0) or 0)
    ctr = float(row.get("ctr", 0) or 0)
    retention = float(row.get("retention_proxy", 0) or 0)

    # 每个分量归一化
    roas_norm = min(roas_d7, 5.0) / 5.0           # [0, 1]
    p04_norm = math.log(1 + p04) / math.log(11)   # [0, 1], 假设 max p04=10
    ctr_norm = min(ctr, 20.0) / 20.0              # [0, 1]
    retention_norm = min(retention, 1.0)           # [0, 1]

    reward = (
        w["w_roas"] * roas_norm +
        w["w_p04"] * p04_norm +
        w["w_ctr"] * ctr_norm +
        w["w_retention"] * retention_norm
    )

    return round(reward, 6)


# ============================================================================
# 四、Offline RL Dataset
# ============================================================================

@dataclass
class DatasetStats:
    """数据集统计信息"""
    total_samples: int = 0
    contextual_bandit_samples: int = 0   # 有 s_t, a_t, r_t
    offline_rl_samples: int = 0          # 有 s_t, a_t, r_t, s_{t+1}
    unique_creatives: int = 0
    reward_mean: float = 0.0
    reward_std: float = 0.0
    reward_min: float = 0.0
    reward_max: float = 0.0
    state_dim: int = 0
    action_dim: int = 4
    date_range: tuple[str, str] = ("", "")
    feature_names: list[str] = field(default_factory=list)


class OfflineRLDatasetBuilder:
    """从 unified_state 构建 offline_rl_dataset"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def build(self, mode: str = "both",
              reward_weights: dict[str, float] | None = None) -> DatasetStats:
        """构建 offline_rl_dataset

        Args:
            mode: "bandit" (仅 contextual bandit), "rl" (完整 offline RL), "both" (两个都输出)
            reward_weights: 自定义 reward 权重

        Returns:
            DatasetStats
        """
        print("=" * 60)
        print("  Offline RL Dataset Builder")
        print(f"  模式: {mode}")
        print("=" * 60)

        # Step 1: 读取 unified_state
        print("\n  [Step 1] 读取 unified_state...")
        rows = self._read_unified_state()
        print(f"    读取 {len(rows)} 行")

        if len(rows) == 0:
            print("  ⚠️ unified_state 为空, 退出")
            return DatasetStats()

        # Step 2: 预计算全局排名 (用于 action 重建)
        print("\n  [Step 2] 计算全局排名...")
        global_ranks = self._compute_global_ranks(rows)
        print(f"    ctr_rank: {len(global_ranks.get('ctr_rank', {}))} creatives")
        print(f"    reward_rank: {len(global_ranks.get('reward_rank', {}))} creatives")

        # Step 3: 生成 state + action + reward
        print("\n  [Step 3] 生成 state / action / reward...")
        samples = []
        for row in rows:
            state_vec, feature_names = self._encode_row(row)
            action = reconstruct_action(row, global_ranks)
            reward = compute_reward(row, reward_weights)

            samples.append({
                "creative_id": row.get("creative_id", ""),
                "date": row.get("date", ""),
                "state_vector": state_vec,
                "action_vector": action["action_vector"],
                "reward": reward,
                "action_meta": {
                    "budget_bucket": action["budget_bucket"],
                    "exploration_flag": action["exploration_flag"],
                    "creative_selection_rank": action["creative_selection_rank"],
                    "bid_strategy": action["bid_strategy"],
                },
            })
        print(f"    生成 {len(samples)} 条样本")

        # Step 4: 构建 next_state (时间窗口对齐)
        print("\n  [Step 4] 构建 next_state (D0-D1 → D1-D2 对齐)...")
        samples = self._link_next_state(samples)
        cb_count = len(samples)  # 所有样本都有 s_t, a_t, r_t
        rl_count = sum(1 for s in samples if s.get("next_state_vector") is not None)
        print(f"    Contextual Bandit 样本: {cb_count}")
        print(f"    Offline RL 样本 (含 next_state): {rl_count}")

        # Step 5: 写入数据库 (先关闭读连接, 避免 write/read 冲突)
        print("\n  [Step 5] 写入 offline_rl_dataset 表...")
        self.close()  # 释放读连接
        state_dim = len(samples[0]["state_vector"]) if samples else 0
        self._write_dataset(samples, state_dim, mode)
        print(f"    写入完成")

        # 计算统计
        rewards = [s["reward"] for s in samples]
        stats = DatasetStats(
            total_samples=len(samples),
            contextual_bandit_samples=cb_count,
            offline_rl_samples=rl_count,
            unique_creatives=len(set(s["creative_id"] for s in samples)),
            reward_mean=round(float(np.mean(rewards)), 6),
            reward_std=round(float(np.std(rewards)), 6),
            reward_min=round(float(np.min(rewards)), 6),
            reward_max=round(float(np.max(rewards)), 6),
            state_dim=state_dim,
            action_dim=4,
            date_range=(
                min(s["date"] for s in samples),
                max(s["date"] for s in samples),
            ),
            feature_names=samples[0].get("_feature_names", []) if samples else [],
        )

        self._print_stats(stats)
        return stats

    def _read_unified_state(self) -> list[dict[str, Any]]:
        """读取 unified_state 全部行"""
        rows = self.conn.execute("""
            SELECT * FROM unified_state
            ORDER BY creative_id, date
        """).fetchall()
        col_names = [d[0] for d in self.conn.description]
        return [dict(zip(col_names, r)) for r in rows]

    def _compute_global_ranks(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """计算全局排名: ctr_rank, reward_rank

        按 creative_id 聚合, 取均值后排名 (0~1, 越小越好)
        """
        from collections import defaultdict

        ctr_vals: dict[str, float] = defaultdict(float)
        reward_vals: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)

        for row in rows:
            cid = row.get("creative_id", "")
            ctr_vals[cid] += float(row.get("ctr", 0) or 0)
            reward_vals[cid] += float(row.get("reward", 0) or 0)
            counts[cid] += 1

        # 计算均值
        for cid in ctr_vals:
            if counts[cid] > 0:
                ctr_vals[cid] /= counts[cid]
                reward_vals[cid] /= counts[cid]

        # 排名 (越小越好 → 排名越小)
        def to_rank(vals: dict[str, float]) -> dict[str, float]:
            sorted_ids = sorted(vals, key=vals.get, reverse=True)  # 高值排前面
            n = len(sorted_ids)
            if n <= 1:
                return {cid: 0.0 for cid in vals}
            return {cid: round(i / (n - 1), 4) for i, cid in enumerate(sorted_ids)}

        return {
            "ctr_rank": to_rank(ctr_vals),
            "reward_rank": to_rank(reward_vals),
        }

    def _encode_row(self, row: dict[str, Any]) -> tuple[list[float], list[str]]:
        """编码一行 → state vector"""
        return encode_state_vector(row)

    def _link_next_state(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按 creative_id 分组, 时间窗口对齐: s_t → s_{t+1}

        state_t   = D0-D1 window
        state_t+1 = D1-D2 window (同一 creative_id 的下一条)
        done_flag = 最后一条 (没有下一个状态)
        """
        # 按 creative_id 分组
        from collections import defaultdict
        groups: dict[str, list[int]] = defaultdict(list)
        for i, s in enumerate(samples):
            groups[s["creative_id"]].append(i)

        for cid, indices in groups.items():
            for j in range(len(indices)):
                idx = indices[j]
                if j + 1 < len(indices):
                    next_idx = indices[j + 1]
                    samples[idx]["next_state_vector"] = samples[next_idx]["state_vector"]
                    samples[idx]["next_creative_id"] = samples[next_idx]["creative_id"]
                    samples[idx]["next_date"] = samples[next_idx]["date"]
                    samples[idx]["done_flag"] = False
                else:
                    samples[idx]["next_state_vector"] = None
                    samples[idx]["next_creative_id"] = None
                    samples[idx]["next_date"] = None
                    samples[idx]["done_flag"] = True

        return samples

    def _write_dataset(self, samples: list[dict[str, Any]],
                       state_dim: int, mode: str) -> None:
        """写入 offline_rl_dataset 表"""
        conn = duckdb.connect(str(self.db_path), read_only=False)

        # 建表
        state_cols = ", ".join(f"s_{i} DOUBLE" for i in range(state_dim))
        ns_cols = ", ".join(f"ns_{i} DOUBLE" for i in range(state_dim))

        conn.execute(f"""
            CREATE OR REPLACE TABLE offline_rl_dataset (
                sample_id INTEGER,

                -- State (s_t)
                {state_cols},

                -- Action (a_t)
                a_budget_bucket DOUBLE,
                a_exploration_flag DOUBLE,
                a_creative_rank DOUBLE,
                a_bid_strategy DOUBLE,

                -- Reward (r_t)
                reward DOUBLE,

                -- Next State (s_{{t+1}})
                {ns_cols},
                next_creative_id VARCHAR,
                next_date VARCHAR,

                -- Done Flag
                done_flag BOOLEAN,

                -- Metadata
                creative_id VARCHAR,
                date VARCHAR,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (sample_id)
            )
        """)

        # 逐行插入
        for i, s in enumerate(samples):
            sv = s["state_vector"]
            av = s["action_vector"]
            nsv = s.get("next_state_vector") or [0.0] * state_dim

            state_vals = ", ".join(str(v) for v in sv)
            ns_vals = ", ".join(str(v) for v in nsv)

            conn.execute(f"""
                INSERT INTO offline_rl_dataset (
                    sample_id,
                    {', '.join(f's_{j}' for j in range(state_dim))},
                    a_budget_bucket, a_exploration_flag, a_creative_rank, a_bid_strategy,
                    reward,
                    {', '.join(f'ns_{j}' for j in range(state_dim))},
                    next_creative_id, next_date,
                    done_flag,
                    creative_id, date
                ) VALUES (
                    {i},
                    {state_vals},
                    {av[0]}, {av[1]}, {av[2]}, {av[3]},
                    {s['reward']},
                    {ns_vals},
                    {f"'{s.get('next_creative_id') or ''}'"},
                    {f"'{s.get('next_date') or ''}'"},
                    {s.get('done_flag', True)},
                    '{s['creative_id']}',
                    '{s['date']}'
                )
            """)

        conn.commit()

        # 如果 mode == "bandit", 也写一个简化版视图
        if mode in ("bandit", "both"):
            conn.execute("""
                CREATE OR REPLACE VIEW offline_rl_dataset_bandit AS
                SELECT
                    sample_id,
                    {0},
                    a_budget_bucket, a_exploration_flag, a_creative_rank, a_bid_strategy,
                    reward,
                    creative_id, date, timestamp
                FROM offline_rl_dataset
            """.format(", ".join(f"s_{j}" for j in range(state_dim))))

        if mode in ("rl", "both"):
            conn.execute("""
                CREATE OR REPLACE VIEW offline_rl_dataset_full AS
                SELECT *
                FROM offline_rl_dataset
                WHERE next_creative_id IS NOT NULL AND next_creative_id != ''
            """)

        conn.close()

    def _print_stats(self, stats: DatasetStats) -> None:
        print(f"\n  {'='*50}")
        print(f"  Offline RL Dataset 统计")
        print(f"  {'='*50}")
        print(f"  总样本数:           {stats.total_samples}")
        print(f"  Contextual Bandit:  {stats.contextual_bandit_samples}")
        print(f"  Offline RL (含s_t+1): {stats.offline_rl_samples}")
        print(f"  Unique Creatives:   {stats.unique_creatives}")
        print(f"  State 维度:         {stats.state_dim}")
        print(f"  Action 维度:        {stats.action_dim}")
        print(f"  Reward 均值:        {stats.reward_mean:.6f}")
        print(f"  Reward 标准差:      {stats.reward_std:.6f}")
        print(f"  Reward 范围:        [{stats.reward_min:.6f}, {stats.reward_max:.6f}]")
        print(f"  日期范围:           {stats.date_range[0]} ~ {stats.date_range[1]}")

    def export_json(self, output_path: str | Path,
                    mode: str = "bandit",
                    max_samples: int | None = None) -> int:
        """导出为 JSON 格式, 便于 Python 训练脚本直接加载

        Args:
            output_path: 输出路径
            mode: "bandit" 或 "rl"
            max_samples: 最大导出样本数 (None = 全部)

        Returns:
            导出样本数
        """
        conn = duckdb.connect(str(self.db_path), read_only=True)

        cols = [d[0] for d in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='offline_rl_dataset'"
        ).fetchall()]

        state_cols = [c for c in cols if c.startswith("s_")]
        ns_cols = [c for c in cols if c.startswith("ns_")]
        action_cols = ["a_budget_bucket", "a_exploration_flag", "a_creative_rank", "a_bid_strategy"]

        limit = f"LIMIT {max_samples}" if max_samples else ""

        if mode == "bandit":
            rows = conn.execute(f"""
                SELECT sample_id, {', '.join(state_cols)},
                       {', '.join(action_cols)},
                       reward, creative_id, date
                FROM offline_rl_dataset
                {limit}
            """).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT sample_id, {', '.join(state_cols)},
                       {', '.join(action_cols)},
                       reward, {', '.join(ns_cols)},
                       next_creative_id, next_date, done_flag,
                       creative_id, date
                FROM offline_rl_dataset
                WHERE next_creative_id IS NOT NULL AND next_creative_id != ''
                {limit}
            """).fetchall()

        samples = []
        for row in rows:
            if mode == "bandit":
                sample_id, *sv, a0, a1, a2, a3, reward, cid, date = row
                samples.append({
                    "state": sv,
                    "action": [a0, a1, a2, a3],
                    "reward": reward,
                    "creative_id": cid,
                    "date": date,
                })
            else:
                sample_id = row[0]
                sv = list(row[1:1+len(state_cols)])
                av = list(row[1+len(state_cols):1+len(state_cols)+4])
                reward = row[1+len(state_cols)+4]
                nsv = list(row[1+len(state_cols)+5:1+len(state_cols)+5+len(ns_cols)])
                nc_id = row[1+len(state_cols)+5+len(ns_cols)]
                nc_date = row[1+len(state_cols)+5+len(ns_cols)+1]
                done = row[1+len(state_cols)+5+len(ns_cols)+2]
                cid = row[1+len(state_cols)+5+len(ns_cols)+3]
                date = row[1+len(state_cols)+5+len(ns_cols)+4]
                samples.append({
                    "state": sv,
                    "action": av,
                    "reward": reward,
                    "next_state": nsv,
                    "next_creative_id": nc_id,
                    "next_date": nc_date,
                    "done": done,
                    "creative_id": cid,
                    "date": date,
                })

        conn.close()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "mode": mode,
                "samples": len(samples),
                "state_dim": len(state_cols),
                "action_dim": 4,
                "feature_names": CONTINUOUS_FEATURES + [
                    f"{feat}_{cat}"
                    for feat, cats in CATEGORICAL_FEATURE_MAPS.items()
                    for cat in cats
                ],
                "reward_weights": DEFAULT_REWARD_WEIGHTS,
                "data": samples,
            }, f, indent=2, ensure_ascii=False)

        print(f"  JSON 导出: {len(samples)} 条 → {output_path}")
        return len(samples)

    def query_summary(self) -> dict[str, Any]:
        """查询数据集摘要"""
        conn = duckdb.connect(str(self.db_path), read_only=True)
        try:
            total = conn.execute("SELECT COUNT(*) FROM offline_rl_dataset").fetchone()[0]
            if total == 0:
                return {"error": "offline_rl_dataset 为空"}
            return {
                "total_samples": total,
                "with_next_state": conn.execute(
                    "SELECT COUNT(*) FROM offline_rl_dataset WHERE next_creative_id IS NOT NULL AND next_creative_id != ''"
                ).fetchone()[0],
                "unique_creatives": conn.execute(
                    "SELECT COUNT(DISTINCT creative_id) FROM offline_rl_dataset"
                ).fetchone()[0],
                "reward_avg": conn.execute(
                    "SELECT AVG(reward) FROM offline_rl_dataset"
                ).fetchone()[0],
                "reward_std": conn.execute(
                    "SELECT STDDEV(reward) FROM offline_rl_dataset"
                ).fetchone()[0],
                "date_range": conn.execute(
                    "SELECT MIN(date), MAX(date) FROM offline_rl_dataset"
                ).fetchone(),
                "reward_distribution": conn.execute("""
                    SELECT
                        CASE
                            WHEN reward = 0 THEN 'zero'
                            WHEN reward < 0.1 THEN 'low'
                            WHEN reward < 0.3 THEN 'medium'
                            WHEN reward < 0.5 THEN 'high'
                            ELSE 'very_high'
                        END AS bucket,
                        COUNT(*) AS cnt
                    FROM offline_rl_dataset
                    GROUP BY bucket
                    ORDER BY bucket
                """).fetchall(),
            }
        finally:
            conn.close()


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="build_offline_rl_dataset — 将 rl_state_t 变成 policy learning dataset"
    )
    parser.add_argument("--db", type=str, default="db/facebook_performance.duckdb")
    parser.add_argument("--mode", type=str, default="both",
                        choices=["bandit", "rl", "both"],
                        help="bandit: 仅 contextual bandit; rl: 完整 offline RL; both: 两个都输出")
    parser.add_argument("--summary", action="store_true",
                        help="仅打印数据集摘要 (不重新构建)")
    parser.add_argument("--export", type=str, default=None,
                        help="导出 JSON 文件路径")
    parser.add_argument("--export-mode", type=str, default="bandit",
                        choices=["bandit", "rl"],
                        help="JSON 导出模式")
    parser.add_argument("--w-roas", type=float, default=0.5,
                        help="ROAS D7 权重 (default: 0.5)")
    parser.add_argument("--w-p04", type=float, default=0.2,
                        help="P04 事件权重 (default: 0.2)")
    parser.add_argument("--w-ctr", type=float, default=0.15,
                        help="CTR 权重 (default: 0.15)")
    parser.add_argument("--w-retention", type=float, default=0.15,
                        help="留存代理权重 (default: 0.15)")
    args = parser.parse_args()

    db_path = ROOT / args.db

    builder = OfflineRLDatasetBuilder(db_path)
    try:
        if args.summary:
            summary = builder.query_summary()
            print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
            return 0

        weights = {
            "w_roas": args.w_roas,
            "w_p04": args.w_p04,
            "w_ctr": args.w_ctr,
            "w_retention": args.w_retention,
        }

        stats = builder.build(mode=args.mode, reward_weights=weights)

        if args.export:
            builder.export_json(
                output_path=args.export,
                mode=args.export_mode,
            )

        return 0
    finally:
        builder.close()


if __name__ == "__main__":
    main()