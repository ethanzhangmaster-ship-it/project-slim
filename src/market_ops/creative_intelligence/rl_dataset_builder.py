"""RL Dataset Builder — 164 素材评分系统 → RL-ready dataset

不改任何业务逻辑，只做数据结构迁移：
  ① creative_scores (164 素材评分)  →  policy features
  ② creative_performance (Facebook)  →  delivery state
  ③ ad_graph (Adjust / P04)          →  user outcome

目标：把分散的三张表压成一张可用于 RL 训练的 rl_state_t 表

reward 统一公式 (不改原有系统):
  reward = 0.6 * normalize(roas_d7) + 0.3 * normalize(purchase_proxy) + 0.1 * normalize(ctr)

MDP 结构:
  rl_state_t = {s_t, a_t, r_t, s_{t+1}}

用法:
  python -m market_ops.creative_intelligence.rl_dataset_builder --db db/facebook_performance.duckdb
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb


# ============================================================================
# 统一 Reward 权重 (不动原有系统)
# ============================================================================
REWARD_WEIGHTS = {
    "roas": 0.6,
    "p04": 0.3,
    "ctr": 0.1,
}


@dataclass
class RLState:
    """RL 状态: s_t, a_t, r_t, s_{t+1}"""
    s_t: dict[str, Any] = field(default_factory=dict)
    a_t: dict[str, Any] = field(default_factory=dict)
    r_t: float = 0.0
    s_t_plus_1: dict[str, Any] | None = None


# ============================================================================
# RL Dataset Builder
# ============================================================================

class RLDatasetBuilder:
    """从 164 素材评分系统构建 RL 训练数据集

    三表 JOIN:
      creative_scores (164 rows)  ←  评分输出
        LEFT JOIN creative_performance (1315 rows)  ←  Facebook 投放
        LEFT JOIN ad_graph (641 rows)                ←  Adjust / P04

    输出:
      rl_state_t: MDP-ready 状态表
      action_log: 动作记录表 (schema)
    """

    UNAVAILABLE_COLUMNS: dict[str, str] = {
        "p04_events": "app_events 表为空, 用 p_purchase_event 做代理",
        "frequency": "需 Facebook Insights API breakdown",
    }

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

    # ========================================================================
    # 主入口
    # ========================================================================

    def build(self) -> dict[str, Any]:
        """构建 RL dataset, 返回摘要"""
        print("=" * 60)
        print("  RL Dataset Builder — 164 素材 → RL-ready")
        print("=" * 60)

        self._create_action_log()
        self._create_rl_state_t()
        self._populate_rl_state_t()
        self._compute_unified_reward()
        self._link_s_t_plus_1()

        count = self.conn.execute("SELECT COUNT(*) FROM rl_state_t").fetchone()[0]
        print(f"\n  [RL Dataset] 构建完成: {count} 行 rl_state_t")

        summary = self._summary()
        self._print_summary(summary)
        return summary

    # ========================================================================
    # 1. action_log 表 — RL 关键跳板
    # ========================================================================

    def _create_action_log(self) -> None:
        """创建 action_log 表 (RL 从 Bandit → MDP 的关键补件)

        记录每次实际执行的动作:
          - budget_allocated: 分配的预算
          - mutation_type: 变异类型 (hook/visual/emotion/...)
          - action_type: 动作类型 (budget_change/mutation/bid_change/status_change)
        """
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                creative_id VARCHAR,
                action_type VARCHAR DEFAULT 'unknown',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                budget_allocated DOUBLE DEFAULT 0,
                mutation_type VARCHAR DEFAULT 'none',
                campaign_id VARCHAR,
                adset_id VARCHAR,
                ad_id VARCHAR,
                source VARCHAR DEFAULT 'manual',
                PRIMARY KEY (creative_id, timestamp)
            )
        """)

        # 尝试从 ad_graph 推断已有动作
        existing = self.conn.execute("SELECT COUNT(*) FROM action_log").fetchone()[0]
        if existing == 0:
            self._seed_action_log_from_ad_graph()
        else:
            print(f"    [action_log] 已有 {existing} 条记录, 跳过种子填充")

    def _seed_action_log_from_ad_graph(self) -> None:
        """从 ad_graph status 推断初始动作记录"""
        inserted = self.conn.execute("""
            INSERT INTO action_log (creative_id, action_type, timestamp, campaign_id, adset_id, ad_id)
            SELECT
                creative_id,
                CASE
                    WHEN status = 'PAUSED' THEN 'pause'
                    WHEN status = 'DELETED' THEN 'delete'
                    WHEN status = 'ARCHIVED' THEN 'archive'
                    ELSE 'unknown'
                END,
                COALESCE(pulled_at, CURRENT_TIMESTAMP),
                campaign_id,
                adset_id,
                ad_id
            FROM ad_graph
            WHERE creative_id IS NOT NULL
              AND status IN ('PAUSED', 'DELETED', 'ARCHIVED')
        """).fetchone()[0]
        print(f"    [action_log] 创建表, 从 ad_graph 种子填充 {inserted} 条")

    # ========================================================================
    # 2. rl_state_t 表 — RL-ready 状态表
    # ========================================================================

    def _create_rl_state_t(self) -> None:
        """建 rl_state_t 表 (精确对齐用户 schema)"""
        self.conn.execute("DROP TABLE IF EXISTS rl_state_t")
        self.conn.execute("""
            CREATE TABLE rl_state_t (
                -- ========== Identity ==========
                date VARCHAR,
                creative_id VARCHAR,

                -- ========== Policy Features (164 评分系统输出) ==========
                final_score DOUBLE DEFAULT 0,
                ctr_score DOUBLE DEFAULT 0,
                ipm_score DOUBLE DEFAULT 0,

                -- ========== Facebook Delivery ==========
                spend DOUBLE DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                ctr DOUBLE DEFAULT 0,
                cpm DOUBLE DEFAULT 0,
                frequency DOUBLE DEFAULT 0,

                -- ========== App Behavior (Adjust) ==========
                installs INTEGER DEFAULT 0,
                p04_events INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,

                -- ========== Economics ==========
                revenue DOUBLE DEFAULT 0,
                roas_d7 DOUBLE DEFAULT 0,
                cpi DOUBLE DEFAULT 0,

                -- ========== Derived Reward ==========
                reward DOUBLE DEFAULT 0,
                reward_type VARCHAR DEFAULT 'unknown',

                -- ========== RL Meta ==========
                cohort_bucket VARCHAR DEFAULT 'unknown',
                time_window VARCHAR DEFAULT 'D7',
                exploration_flag BOOLEAN DEFAULT TRUE,

                -- ========== MDP: s_{t+1} ==========
                s_t_plus_1_creative_id VARCHAR,
                s_t_plus_1_date VARCHAR,
                s_t_plus_1_reward DOUBLE DEFAULT 0,

                -- ========== Meta ==========
                built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            )
        """)
        # 用唯一索引代替主键 (允许 creative_performance 中潜在的重复行)
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_rl_state_creative_date "
            "ON rl_state_t (creative_id, date)"
        )

    # ========================================================================
    # 3. 三表 JOIN → rl_state_t
    # ========================================================================

    def _populate_rl_state_t(self) -> None:
        """核心迁移: creative_scores + creative_performance + ad_graph → rl_state_t

        Step 1: creative_scores → policy features (final_score, ctr_score, ipm_score)
        Step 2: creative_performance → delivery state (spend, impressions, clicks, ctr, cpm)
        Step 3: ad_graph → user outcome (purchases, revenue)
        """
        # 用 creative_performance 作为主表 (有时序), LEFT JOIN creative_scores + ad_graph
        self.conn.execute("""
            INSERT INTO rl_state_t (
                date, creative_id,
                final_score, ctr_score, ipm_score,
                spend, impressions, clicks, ctr, cpm,
                installs, purchases,
                revenue, roas_d7, cpi,
                cohort_bucket, time_window
            )
            SELECT
                date,
                creative_id,
                final_score, ctr_score, ipm_score,
                spend, impressions, clicks, ctr, cpm,
                installs, purchases,
                revenue, roas_d7, cpi,
                cohort_bucket, time_window
            FROM (
                SELECT
                    cp.date,
                    cp.creative_id,

                    -- Policy Features: 从 creative_scores 直接搬
                    COALESCE(cs.final_score, 0) as final_score,
                    COALESCE(cs.creative_score, 0) as ctr_score,
                    COALESCE(cs.intent_score, 0) as ipm_score,

                    -- Facebook Delivery: 从 creative_performance
                    COALESCE(cp.spend, 0) as spend,
                    COALESCE(cp.impression, 0) as impressions,
                    COALESCE(cp.click, 0) as clicks,
                    COALESCE(cp.ctr, 0) as ctr,
                    CASE WHEN COALESCE(cp.impression, 0) > 0
                         THEN cp.spend / cp.impression * 1000 ELSE 0 END as cpm,

                    -- App Behavior
                    COALESCE(cp.install, 0) as installs,
                    COALESCE(ag.purchases, 0) as purchases,

                    -- Economics
                    COALESCE(ag.purchase_value, 0) as revenue,
                    COALESCE(cp.roas_d7, 0) as roas_d7,
                    COALESCE(cp.cpi, 0) as cpi,

                    -- RL Meta
                    CASE
                        WHEN COALESCE(cp.spend, 0) < 100 THEN 'low_spend'
                        WHEN COALESCE(cp.spend, 0) < 500 THEN 'mid_spend'
                        WHEN COALESCE(cp.spend, 0) < 2000 THEN 'high_spend'
                        ELSE 'top_spend'
                    END as cohort_bucket,
                    'D7' as time_window,

                    ROW_NUMBER() OVER (PARTITION BY cp.creative_id, cp.date ORDER BY cp.spend DESC) as rn

                FROM creative_performance cp
                LEFT JOIN creative_scores cs ON cp.creative_id = cs.creative_id
                LEFT JOIN ad_graph ag ON cp.creative_id = ag.creative_id
                WHERE cp.creative_id IS NOT NULL
                  AND cp.creative_id != ''
            ) sub
            WHERE sub.rn = 1
        """)

        cnt = self.conn.execute("SELECT COUNT(*) FROM rl_state_t").fetchone()[0]
        print(f"    [rl_state_t] 三表 JOIN 完成: {cnt} 行")

    # ========================================================================
    # 4. 统一 Reward 计算
    # ========================================================================

    def _compute_unified_reward(self) -> None:
        """统一 reward 计算 (不改原有评分逻辑, 仅做表层统一)

        reward = 0.6 * normalize(roas_d7) + 0.3 * normalize(purchase_proxy) + 0.1 * normalize(ctr)

        归一化: 用全表最大值做 min-max normalization → [0, 1]
        """
        # 获取归一化基准
        stats = self.conn.execute("""
            SELECT
                MAX(roas_d7) as max_roas,
                MAX(purchases) as max_purchases,
                MAX(ctr) as max_ctr
            FROM rl_state_t
        """).fetchone()

        max_roas = max(stats[0] or 0.01, 0.01)
        max_purchases = max(stats[1] or 1, 1)
        max_ctr = max(stats[2] or 0.01, 0.01)

        self.conn.execute(f"""
            UPDATE rl_state_t
            SET
                reward = (
                    {REWARD_WEIGHTS['roas']} * LEAST(roas_d7 / {max_roas}, 1.0) +
                    {REWARD_WEIGHTS['p04']} * LEAST(CAST(purchases AS DOUBLE) / {max_purchases}, 1.0) +
                    {REWARD_WEIGHTS['ctr']} * LEAST(ctr / {max_ctr}, 1.0)
                ),
                reward_type = CASE
                    WHEN roas_d7 > 0 AND purchases > 0 THEN 'blended'
                    WHEN roas_d7 > 0 THEN 'roas'
                    WHEN purchases > 0 THEN 'p04'
                    WHEN ctr > 0 THEN 'ctr'
                    ELSE 'unknown'
                END
        """)

        reward_count = self.conn.execute(
            "SELECT COUNT(*) FROM rl_state_t WHERE reward > 0"
        ).fetchone()[0]
        avg_reward = self.conn.execute(
            "SELECT AVG(reward) FROM rl_state_t WHERE reward > 0"
        ).fetchone()[0]
        print(f"    [reward] 统一完成: {reward_count} 行 > 0, avg={avg_reward:.4f}")
        print(f"    [reward] 权重: roas={REWARD_WEIGHTS['roas']} "
              f"p04={REWARD_WEIGHTS['p04']} ctr={REWARD_WEIGHTS['ctr']}")

    # ========================================================================
    # 5. s_{t+1} 链接 — MDP transition
    # ========================================================================

    def _link_s_t_plus_1(self) -> None:
        """链接每个 state 到下一周期 state (按 creative_id + date)

        s_{t+1} = 同一 creative 的下一个 date 行
        """
        self.conn.execute("""
            UPDATE rl_state_t u
            SET
                s_t_plus_1_creative_id = next_row.next_creative_id,
                s_t_plus_1_date = next_row.next_date,
                s_t_plus_1_reward = COALESCE(next_row.next_reward, 0)
            FROM (
                SELECT
                    creative_id,
                    date,
                    LEAD(creative_id) OVER (PARTITION BY creative_id ORDER BY date) AS next_creative_id,
                    LEAD(date) OVER (PARTITION BY creative_id ORDER BY date) AS next_date,
                    LEAD(reward) OVER (PARTITION BY creative_id ORDER BY date) AS next_reward
                FROM rl_state_t
            ) next_row
            WHERE u.creative_id = next_row.creative_id
              AND u.date = next_row.date
        """)

        linked = self.conn.execute(
            "SELECT COUNT(*) FROM rl_state_t WHERE s_t_plus_1_creative_id IS NOT NULL"
        ).fetchone()[0]
        total = self.conn.execute("SELECT COUNT(*) FROM rl_state_t").fetchone()[0]
        print(f"    [MDP] s_(t+1) 链接: {linked}/{total} "
              f"({linked/total*100:.1f}%)" if total > 0 else "    [MDP] s_(t+1): 表为空")

    # ========================================================================
    # 6. 摘要报告
    # ========================================================================

    def _summary(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT COUNT(*) FROM rl_state_t").fetchone()[0]
        if total == 0:
            return {"error": "rl_state_t 为空"}

        return {
            "total_states": total,
            "unique_creatives": self.conn.execute(
                "SELECT COUNT(DISTINCT creative_id) FROM rl_state_t"
            ).fetchone()[0],
            "scored_creatives": self.conn.execute(
                "SELECT COUNT(DISTINCT creative_id) FROM rl_state_t WHERE final_score > 0"
            ).fetchone()[0],
            "states_with_spend": self.conn.execute(
                "SELECT COUNT(*) FROM rl_state_t WHERE spend > 0"
            ).fetchone()[0],
            "states_with_purchases": self.conn.execute(
                "SELECT COUNT(*) FROM rl_state_t WHERE purchases > 0"
            ).fetchone()[0],
            "states_with_s_t_plus_1": self.conn.execute(
                "SELECT COUNT(*) FROM rl_state_t WHERE s_t_plus_1_creative_id IS NOT NULL"
            ).fetchone()[0],
            "states_with_reward": self.conn.execute(
                "SELECT COUNT(*) FROM rl_state_t WHERE reward > 0"
            ).fetchone()[0],
            "avg_reward": self.conn.execute(
                "SELECT AVG(reward) FROM rl_state_t WHERE reward > 0"
            ).fetchone()[0],
            "reward_types": self.conn.execute("""
                SELECT reward_type, COUNT(*) as cnt
                FROM rl_state_t
                GROUP BY reward_type ORDER BY cnt DESC
            """).fetchall(),
            "date_range": self.conn.execute(
                "SELECT MIN(date), MAX(date) FROM rl_state_t"
            ).fetchone(),
            "action_log_rows": self.conn.execute(
                "SELECT COUNT(*) FROM action_log"
            ).fetchone()[0],
            "cohort_distribution": self.conn.execute("""
                SELECT cohort_bucket, COUNT(*) as cnt
                FROM rl_state_t
                GROUP BY cohort_bucket ORDER BY cnt DESC
            """).fetchall(),
        }

    def _print_summary(self, s: dict[str, Any]) -> None:
        print(f"\n  {'='*60}")
        print(f"  RL Dataset 摘要")
        print(f"  {'='*60}")
        print(f"  rl_state_t: {s['total_states']} 行 | "
              f"{s['unique_creatives']} 个 creative | "
              f"{s['scored_creatives']} 个已评分")
        print(f"  spend > 0: {s['states_with_spend']} | "
              f"purchases > 0: {s['states_with_purchases']} | "
              f"reward > 0: {s['states_with_reward']}")
        print(f"  s_(t+1): {s['states_with_s_t_plus_1']} | "
              f"avg_reward: {s['avg_reward']:.4f}")
        print(f"  action_log: {s['action_log_rows']} 条")
        print(f"  date_range: {s['date_range']}")

        print(f"\n  reward_type 分布:")
        for rt, cnt in s['reward_types']:
            print(f"    {rt:<15} {cnt:>5}")

        print(f"\n  cohort_bucket 分布:")
        for cb, cnt in s['cohort_distribution']:
            print(f"    {cb:<15} {cnt:>5}")

        print(f"\n  📋 数据缺口:")
        for col, reason in self.UNAVAILABLE_COLUMNS.items():
            print(f"    ⚠️  {col:<20} → {reason}")

    # ========================================================================
    # 7. MDP Trajectory 查询
    # ========================================================================

    def query_mdp_trajectory(self, creative_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """查询某个 creative 的完整 MDP 轨迹"""
        rows = self.conn.execute("""
            SELECT date, creative_id,
                   final_score, ctr_score, ipm_score,
                   spend, impressions, clicks, ctr, cpm,
                   installs, purchases, revenue, roas_d7, cpi,
                   reward, reward_type,
                   s_t_plus_1_creative_id, s_t_plus_1_date, s_t_plus_1_reward,
                   cohort_bucket, time_window
            FROM rl_state_t
            WHERE creative_id = ?
            ORDER BY date ASC
            LIMIT ?
        """, [creative_id, limit]).fetchall()

        return [{
            "date": r[0],
            "creative_id": r[1],
            "s_t": {
                "final_score": r[2], "ctr_score": r[3], "ipm_score": r[4],
                "spend": r[5], "impressions": r[6], "clicks": r[7],
                "ctr": r[8], "cpm": r[9],
                "installs": r[10], "purchases": r[11],
                "revenue": r[12], "roas_d7": r[13], "cpi": r[14],
                "cohort": r[20], "window": r[21],
            },
            "r_t": r[15],
            "reward_type": r[16],
            "s_t_plus_1": {
                "creative_id": r[17],
                "date": r[18],
                "reward": r[19],
            },
        } for r in rows]


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="RL Dataset Builder — 164 素材 → RL-ready")
    parser.add_argument("--db", type=str, default="db/facebook_performance.duckdb")
    parser.add_argument("--trajectory", type=str, default=None,
                        help="查询某个 creative_id 的 MDP 轨迹")
    args = parser.parse_args()

    builder = RLDatasetBuilder(args.db)
    try:
        builder.build()

        if args.trajectory:
            traj = builder.query_mdp_trajectory(args.trajectory)
            print(f"\n  🔗 MDP 轨迹: {args.trajectory}")
            print(f"  {'─'*80}")
            for t in traj:
                s = t['s_t']
                nxt = t['s_t_plus_1']
                nxt_str = f"s_next={nxt['date'] or 'END'} (r={nxt['reward']:.3f})" if nxt['date'] else "s_next=END"
                print(f"  {t['date']} | score={s['final_score']:.3f} | "
                      f"spend=${s['spend']:>8.0f} | ctr={s['ctr']:.1f}% | "
                      f"roas={s['roas_d7']:.3f} | "
                      f"r_t={t['r_t']:.3f} ({t['reward_type']}) | "
                      f"{nxt_str}")

        return 0
    finally:
        builder.close()


if __name__ == "__main__":
    main()