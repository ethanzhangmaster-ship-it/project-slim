"""Unified State Builder — 三系统统一 MDP-ready state_t 表

将 Facebook (creative_performance + ad_graph) + Adjust (app_events) + Creative Graph
(creative_features + creative_graph) 压成一张可用于 RL 的 state_t 表。

每一行 = 某个 creative 在某个时间窗口内的完整环境状态 + 行为结果

MDP 结构:
  state_t = {s_t, a_t, r_t, s_{t+1}}
  s_t = {identity, creative_graph, facebook_delivery, adjust_outcome, economics, derived}
  a_t = {action_taken, budget_change, mutation_flag, bid_change}
  r_t = {reward, reward_type}
  s_{t+1} = next row (creative_id + date 链接)

数据源:
  creative_performance: 1315 rows — spend, impression, click, install, ctr, roas_d1/d7
  ad_graph: 641 rows — cpm, cpc, purchases, purchase_value, creative text
  creative_features: 58 fields — hook, visual, emotion, game mechanics
  creative_id_mapping: 1092 rows — adjust ↔ facebook ↔ duckdb identity resolution
  creative_graph: 360 rows — creative_hash, image_url, primary_text

已知缺口:
  - frequency / placement_distribution: 需 Facebook Insights API breakdown
  - parent_id: 需在 mutation 时写入 creative_graph
  - action_taken: 需 action log 表记录实际执行的动作
  - app_events (Adjust): 空表, 需导入 Adjust 数据
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb


# ============================================================================
# MDP State Schema
# ============================================================================

@dataclass
class MDPState:
    """完整的 MDP 状态: s_t, a_t, r_t, s_{t+1}"""
    s_t: dict[str, Any] = field(default_factory=dict)
    a_t: dict[str, Any] = field(default_factory=dict)
    r_t: float = 0.0
    s_t_plus_1: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "s_t": self.s_t,
            "a_t": self.a_t,
            "r_t": self.r_t,
            "s_t_plus_1": self.s_t_plus_1,
        }


# ============================================================================
# Unified State Builder
# ============================================================================

class UnifiedStateBuilder:
    """从 DuckDB 三系统构建 unified_state 表

    核心 JOIN:
      creative_performance
        LEFT JOIN creative_features (ON creative_id)
        LEFT JOIN ad_graph (ON creative_id)
        LEFT JOIN creative_id_mapping (ON creative_id)
        LEFT JOIN creative_graph (ON creative_id)
    """

    # 记录哪些列无法从现有数据源填充
    UNAVAILABLE_COLUMNS: dict[str, str] = {
        "frequency": "需 Facebook Insights API breakdown (frequency_distribution)",
        "placement_distribution": "需 Facebook Insights API breakdown (placement_asset)",
        "parent_id": "需在 mutation 时写入 creative_graph.parent_id",
        "action_taken": "需 action_log 表记录实际执行的动作",
        "action_budget_change": "需 action_log 表",
        "action_mutation_flag": "需 action_log 表",
        "action_bid_change": "需 action_log 表",
        "p04_events": "app_events 表为空 (Adjust 数据未导入)",
        "tutorial_complete": "app_events 表为空",
        "level_10_complete": "app_events 表为空",
        "session_time": "app_events 表为空",
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

    def build(self) -> int:
        """构建 unified_state 表, 返回行数"""
        print("=" * 60)
        print("  UnifiedState Builder — 三系统 → MDP-ready state_t")
        print("=" * 60)

        self._create_table()
        self._populate_identity()
        self._populate_creative()
        self._populate_delivery()
        self._populate_user_outcome()
        self._populate_economic()
        self._populate_derived()
        self._populate_reward()
        self._populate_action()
        self._link_s_t_plus_1()

        count = self.conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
        print(f"\n  [UnifiedState] 构建完成: {count} 行 unified_state")

        self._print_coverage()
        self._print_gaps()
        return count

    # ========================================================================
    # 1. 建表 — 精确对齐用户 schema
    # ========================================================================

    def _create_table(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS unified_state")
        self.conn.execute("""
            CREATE TABLE unified_state (
                -- ========== Identity ==========
                date VARCHAR,
                creative_id VARCHAR,
                campaign_id VARCHAR,
                adset_id VARCHAR,
                ad_id VARCHAR,
                project VARCHAR,
                adjust_creative_id VARCHAR,
                facebook_creative_id VARCHAR,

                -- ========== Creative Graph (Policy Input) ==========
                hook_type VARCHAR DEFAULT 'unknown',
                creative_type VARCHAR DEFAULT 'image',
                visual_style VARCHAR DEFAULT 'unknown',
                visual_density VARCHAR DEFAULT 'unknown',
                game_mechanic_tag VARCHAR DEFAULT 'unknown',
                primary_color VARCHAR DEFAULT 'unknown',
                warm_cool VARCHAR DEFAULT 'unknown',
                emotion_tag VARCHAR DEFAULT 'unknown',
                overlay_text VARCHAR DEFAULT 'unknown',
                creative_hash VARCHAR,
                primary_text VARCHAR,
                headline VARCHAR,
                call_to_action VARCHAR,
                mutation_type VARCHAR DEFAULT 'unknown',
                parent_id VARCHAR,
                generation_depth INTEGER DEFAULT 0,

                -- ========== Facebook Delivery State ==========
                spend DOUBLE DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                ctr DOUBLE DEFAULT 0,
                cpm DOUBLE DEFAULT 0,
                cpc DOUBLE DEFAULT 0,
                frequency DOUBLE DEFAULT 0,
                placement_distribution VARCHAR DEFAULT 'unknown',
                ad_status VARCHAR DEFAULT 'unknown',

                -- ========== Adjust / App State ==========
                installs INTEGER DEFAULT 0,
                p04_events INTEGER DEFAULT 0,
                purchase_events INTEGER DEFAULT 0,
                purchase_value DOUBLE DEFAULT 0,
                tutorial_complete INTEGER DEFAULT 0,
                level_10_complete INTEGER DEFAULT 0,
                session_time DOUBLE DEFAULT 0,

                -- ========== Economics ==========
                revenue DOUBLE DEFAULT 0,
                roas_d0 DOUBLE DEFAULT 0,
                roas_d1 DOUBLE DEFAULT 0,
                roas_d7 DOUBLE DEFAULT 0,
                cpi DOUBLE DEFAULT 0,
                ipm DOUBLE DEFAULT 0,
                arpu_proxy DOUBLE DEFAULT 0,

                -- ========== Derived RL State ==========
                cohort_age INTEGER DEFAULT 0,
                spend_bucket VARCHAR DEFAULT 'unknown',
                cpm_bucket VARCHAR DEFAULT 'unknown',
                engagement_score DOUBLE DEFAULT 0,
                conversion_rate DOUBLE DEFAULT 0,
                retention_proxy DOUBLE DEFAULT 0,

                -- ========== Reward ==========
                reward DOUBLE DEFAULT 0,
                reward_type VARCHAR DEFAULT 'unknown',

                -- ========== Action (a_t) ==========
                action_taken VARCHAR DEFAULT 'none',
                action_budget_change DOUBLE DEFAULT 0,
                action_mutation_flag BOOLEAN DEFAULT FALSE,
                action_bid_change DOUBLE DEFAULT 0,

                -- ========== MDP: s_{t+1} ==========
                s_t_plus_1_creative_id VARCHAR,
                s_t_plus_1_date VARCHAR,
                s_t_plus_1_reward DOUBLE DEFAULT 0,

                -- ========== RL Metadata ==========
                exploration_flag BOOLEAN DEFAULT TRUE,
                policy_version VARCHAR DEFAULT 'v1',
                t_temperature DOUBLE DEFAULT 1.0,
                built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (creative_id, date)
            )
        """)

    # ========================================================================
    # 2. Identity
    # ========================================================================

    def _populate_identity(self) -> None:
        self.conn.execute("""
            INSERT INTO unified_state (
                date, creative_id, campaign_id, adset_id, project
            )
            SELECT DISTINCT
                cp.date,
                cp.creative_id,
                cp.campaign_id,
                cp.adset_id,
                cp.project
            FROM creative_performance cp
            WHERE cp.creative_id IS NOT NULL
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
        print(f"  [Identity] 插入 {cnt} 行")

    # ========================================================================
    # 3. Creative Graph — Policy Input State
    # ========================================================================

    def _populate_creative(self) -> None:
        # 3a. creative_features → hook_type, visual_style, emotion, game_mechanic, etc.
        self.conn.execute("""
            UPDATE unified_state u
            SET
                hook_type = COALESCE(cf.hook_type, 'unknown'),
                creative_type = 'image',
                visual_style = COALESCE(cf.warm_cool, 'unknown'),
                visual_density = CASE
                    WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.5 THEN 'high'
                    WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.2 THEN 'medium'
                    ELSE 'low'
                END,
                game_mechanic_tag = CASE
                    WHEN COALESCE(cf.game_has_merge, FALSE) THEN 'merge'
                    WHEN COALESCE(cf.game_has_level, FALSE) THEN 'level'
                    WHEN COALESCE(cf.game_has_reward, FALSE) THEN 'reward'
                    WHEN COALESCE(cf.game_has_collection, FALSE) THEN 'collection'
                    WHEN COALESCE(cf.game_has_progress, FALSE) THEN 'progress'
                    WHEN COALESCE(cf.game_has_inventory, FALSE) THEN 'inventory'
                    ELSE 'unknown'
                END,
                primary_color = COALESCE(cf.primary_color, 'unknown'),
                warm_cool = COALESCE(cf.warm_cool, 'unknown'),
                emotion_tag = CASE
                    WHEN COALESCE(cf.emotion_surprise, FALSE) THEN 'surprise'
                    WHEN COALESCE(cf.emotion_failure, FALSE) THEN 'failure'
                    WHEN COALESCE(cf.emotion_success, FALSE) THEN 'success'
                    WHEN COALESCE(cf.emotion_reward, FALSE) THEN 'reward'
                    WHEN COALESCE(cf.emotion_tension, FALSE) THEN 'tension'
                    WHEN COALESCE(cf.emotion_satisfaction, FALSE) THEN 'satisfaction'
                    ELSE 'neutral'
                END,
                overlay_text = COALESCE(cf.overlay_text, 'unknown'),
                generation_depth = 0,
                mutation_type = 'unknown'
            FROM creative_features cf
            WHERE u.creative_id = cf.creative_id
        """)

        # 3b. ad_graph → creative 文本 (primary_text, headline, cta, hash)
        self.conn.execute("""
            UPDATE unified_state u
            SET
                primary_text = ag.primary_text,
                headline = ag.headline,
                call_to_action = ag.call_to_action,
                creative_hash = ag.creative_hash
            FROM ad_graph ag
            WHERE u.creative_id = ag.creative_id
        """)

        # 3c. creative_graph → 补充 hash
        self.conn.execute("""
            UPDATE unified_state u
            SET creative_hash = COALESCE(u.creative_hash, cg.creative_hash)
            FROM creative_graph cg
            WHERE u.creative_id = cg.creative_id
        """)

        # 3d. creative_id_mapping → adjust / facebook identity
        self.conn.execute("""
            UPDATE unified_state u
            SET
                adjust_creative_id = m.adjust_creative_id,
                facebook_creative_id = m.facebook_creative_id
            FROM creative_id_mapping m
            WHERE u.creative_id = m.duckdb_creative_id
        """)

        # 3e. parent_id — 尝试从 creative_graph 查找 (如果 mutation 时写入了)
        # 当前 creative_graph 没有 parent_id 列, 保持 NULL
        print("    [Creative] parent_id: 当前 creative_graph 无 parent_id 列, 保持 NULL")

    # ========================================================================
    # 4. Facebook Delivery State
    # ========================================================================

    def _populate_delivery(self) -> None:
        # 4a. creative_performance → spend, impressions, clicks, ctr, cpm
        self.conn.execute("""
            UPDATE unified_state u
            SET
                spend = COALESCE(cp.spend, 0),
                impressions = COALESCE(cp.impression, 0),
                clicks = COALESCE(cp.click, 0),
                ctr = COALESCE(cp.ctr, 0),
                cpm = CASE
                    WHEN COALESCE(cp.impression, 0) > 0
                    THEN cp.spend / cp.impression * 1000
                    ELSE 0
                END,
                cpc = CASE
                    WHEN COALESCE(cp.click, 0) > 0
                    THEN cp.spend / cp.click
                    ELSE 0
                END
            FROM creative_performance cp
            WHERE u.creative_id = cp.creative_id AND u.date = cp.date
        """)

        # 4b. ad_graph → ad_id, status, 精确 cpm/cpc
        self.conn.execute("""
            UPDATE unified_state u
            SET
                ad_id = ag.ad_id,
                ad_status = COALESCE(ag.status, 'unknown'),
                cpm = CASE WHEN ag.cpm IS NOT NULL AND ag.cpm > 0 THEN ag.cpm ELSE u.cpm END,
                cpc = CASE WHEN ag.cpc IS NOT NULL AND ag.cpc > 0 THEN ag.cpc ELSE u.cpc END
            FROM ad_graph ag
            WHERE u.creative_id = ag.creative_id
        """)

        # 4c. frequency / placement_distribution — 当前数据源不包含
        print("    [Delivery] frequency/placement_distribution: 需 Facebook Insights API breakdown")

    # ========================================================================
    # 5. Adjust / App State — User Outcome
    # ========================================================================

    def _populate_user_outcome(self) -> None:
        # 5a. creative_performance → installs
        self.conn.execute("""
            UPDATE unified_state u
            SET installs = COALESCE(cp.install, 0)
            FROM creative_performance cp
            WHERE u.creative_id = cp.creative_id AND u.date = cp.date
        """)

        # 5b. ad_graph → purchase_events, purchase_value (Facebook 端购买数据)
        self.conn.execute("""
            UPDATE unified_state u
            SET
                purchase_events = COALESCE(ag.purchases, 0),
                purchase_value = COALESCE(ag.purchase_value, 0)
            FROM ad_graph ag
            WHERE u.creative_id = ag.creative_id
        """)

        # 5c. Adjust app_events 为空, 标记缺口
        ae_count = self.conn.execute("SELECT COUNT(*) FROM app_events").fetchone()[0]
        if ae_count == 0:
            print("    [Adjust]  app_events 表为空 — p04_events/tutorial/level_10/session_time 保持 0")
        else:
            # 如果 app_events 有数据, 按 creative_id 和 date 更新
            # 当前 app_events 表结构: date, app, event_name, event_count, unique_users, revenue
            # 需要 creative_id 映射才能关联, 暂不实现
            print("    [Adjust]  app_events 有数据但缺少 creative_id 映射, 暂不关联")

    # ========================================================================
    # 6. Economics
    # ========================================================================

    def _populate_economic(self) -> None:
        self.conn.execute("""
            UPDATE unified_state u
            SET
                revenue = COALESCE(u.purchase_value, 0),
                roas_d1 = COALESCE(cp.roas_d1, 0),
                roas_d7 = COALESCE(cp.roas_d7, 0),
                roas_d0 = CASE
                    WHEN u.spend > 0 THEN u.purchase_value / u.spend
                    ELSE 0
                END,
                cpi = COALESCE(cp.cpi, 0),
                ipm = COALESCE(cp.ipm, 0),
                arpu_proxy = CASE
                    WHEN u.installs > 0 THEN u.revenue / u.installs
                    ELSE 0
                END
            FROM creative_performance cp
            WHERE u.creative_id = cp.creative_id AND u.date = cp.date
        """)

    # ========================================================================
    # 7. Derived RL State
    # ========================================================================

    def _populate_derived(self) -> None:
        # 用 CTE 预计算 cohort_age (不能用 UDF, 因为 UDF 内不能执行 SQL)
        self.conn.execute("""
            UPDATE unified_state u
            SET
                cohort_age = COALESCE(
                    (SELECT DATEDIFF('day', MIN(CAST(u2.date AS DATE)), CAST(u.date AS DATE))
                     FROM unified_state u2
                     WHERE u2.creative_id = u.creative_id),
                    0
                ),
                spend_bucket = CASE
                    WHEN u.spend < 100 THEN 'low'
                    WHEN u.spend < 500 THEN 'medium'
                    WHEN u.spend < 2000 THEN 'high'
                    ELSE 'very_high'
                END,
                cpm_bucket = CASE
                    WHEN u.cpm < 5 THEN 'low'
                    WHEN u.cpm < 15 THEN 'medium'
                    WHEN u.cpm < 30 THEN 'high'
                    ELSE 'very_high'
                END,
                engagement_score = CASE
                    WHEN u.impressions > 100
                    THEN (u.ctr / 10.0) * (CAST(u.installs AS DOUBLE) / u.impressions)
                    ELSE 0
                END,
                conversion_rate = CASE
                    WHEN u.clicks > 0 THEN CAST(u.installs AS DOUBLE) / u.clicks
                    ELSE 0
                END,
                retention_proxy = CASE
                    WHEN u.purchase_events > 0 AND u.installs > 0
                    THEN CAST(u.purchase_events AS DOUBLE) / u.installs
                    ELSE 0
                END
        """)

    # ========================================================================
    # 8. Reward — r_t
    # ========================================================================

    def _populate_reward(self) -> None:
        self.conn.execute("""
            UPDATE unified_state
            SET
                reward = CASE
                    WHEN purchase_events > 0 AND spend > 0
                    THEN LEAST(purchase_value / spend, 1.0)
                    WHEN roas_d7 > 0
                    THEN LEAST(roas_d7, 1.0)
                    WHEN ctr > 0
                    THEN LEAST(ctr / 10.0, 1.0)
                    ELSE 0
                END,
                reward_type = CASE
                    WHEN purchase_events > 0 THEN 'roas'
                    WHEN roas_d7 > 0 THEN 'roas_d7'
                    WHEN ctr > 0 THEN 'ctr_proxy'
                    ELSE 'unknown'
                END
        """)

    # ========================================================================
    # 9. Action — a_t (占位, 需 action_log 表)
    # ========================================================================

    def _populate_action(self) -> None:
        """尝试从 ad_graph 推断 action 历史

        当前策略: 检查 ad_graph 是否有 status 变化 (ACTIVE → PAUSED 等)
        作为 action 的代理信号。完整的 action 记录需要 action_log 表。
        """
        # 检查是否存在 action_log 表
        has_action_log = self.conn.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'action_log'
        """).fetchone()[0] > 0

        if has_action_log:
            # 如果有 action_log, 按 creative_id + date 关联
            self.conn.execute("""
                UPDATE unified_state u
                SET
                    action_taken = COALESCE(al.action_type, 'none'),
                    action_budget_change = COALESCE(al.budget_allocated, 0),
                    action_mutation_flag = CASE WHEN al.mutation_type IS NOT NULL AND al.mutation_type != 'none' THEN TRUE ELSE FALSE END,
                    action_bid_change = 0
                FROM action_log al
                WHERE u.creative_id = al.creative_id AND u.date = CAST(al.timestamp AS VARCHAR)
            """)
            print("    [Action] 从 action_log 表填充")
        else:
            # 无 action_log — 从 ad_graph status 推断简单动作
            # 仅标记 status 不为 'ACTIVE' 的 creative
            self.conn.execute("""
                UPDATE unified_state u
                SET
                    action_taken = CASE
                        WHEN ag.status = 'PAUSED' THEN 'pause'
                        WHEN ag.status = 'DELETED' THEN 'delete'
                        WHEN ag.status = 'ARCHIVED' THEN 'archive'
                        ELSE 'none'
                    END
                FROM ad_graph ag
                WHERE u.creative_id = ag.creative_id
            """)
            print("    [Action] 无 action_log 表, 从 ad_graph.status 推断 (仅 pause/delete/archive)")

    # ========================================================================
    # 10. s_{t+1} 链接 — MDP transition
    # ========================================================================

    def _link_s_t_plus_1(self) -> None:
        """链接每个 state 到下一周期的 state

        对于每个 (creative_id, date), 找到同一 creative_id 的下一个 date 行
        使用 LEAD 窗口函数一次性计算 s_{t+1} 的三列
        """
        self.conn.execute("""
            UPDATE unified_state u
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
                FROM unified_state
            ) next_row
            WHERE u.creative_id = next_row.creative_id
              AND u.date = next_row.date
        """)

        linked = self.conn.execute(
            "SELECT COUNT(*) FROM unified_state WHERE s_t_plus_1_creative_id IS NOT NULL"
        ).fetchone()[0]
        total = self.conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
        pct = linked / total * 100 if total > 0 else 0
        print(f"    [MDP] s_(t+1) 链接: {linked}/{total} ({pct:.1f}%)")

    # ========================================================================
    # 覆盖率报告
    # ========================================================================

    def _print_coverage(self) -> None:
        total = self.conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
        if total == 0:
            return

        dims = [
            # Identity
            ("campaign_id", "Identity-广告系列", "IS NOT NULL"),
            ("adset_id", "Identity-广告组", "IS NOT NULL"),
            ("ad_id", "Identity-广告ID", "IS NOT NULL"),
            ("adjust_creative_id", "Identity-Adjust映射", "IS NOT NULL"),
            ("facebook_creative_id", "Identity-Facebook映射", "IS NOT NULL"),
            # Creative
            ("hook_type", "创意-Hook类型", "IS NOT NULL AND hook_type != 'unknown'"),
            ("visual_style", "创意-视觉风格", "IS NOT NULL AND visual_style != 'unknown'"),
            ("visual_density", "创意-视觉密度", "IS NOT NULL AND visual_density != 'unknown'"),
            ("emotion_tag", "创意-情感标签", "IS NOT NULL AND emotion_tag NOT IN ('unknown', 'neutral')"),
            ("game_mechanic_tag", "创意-游戏机制", "IS NOT NULL AND game_mechanic_tag != 'unknown'"),
            ("creative_hash", "创意-Hash", "IS NOT NULL"),
            ("primary_text", "创意-文案", "IS NOT NULL AND primary_text != ''"),
            ("parent_id", "创意-父节点", "IS NOT NULL"),
            ("mutation_type", "创意-变异类型", "IS NOT NULL AND mutation_type != 'unknown'"),
            # Delivery
            ("spend", "投放-花费(>0)", "> 0"),
            ("cpm_bucket", "投放-CPM分桶", "IS NOT NULL AND cpm_bucket != 'unknown'"),
            ("frequency", "投放-频次", "> 0"),
            ("placement_distribution", "投放-版位", "IS NOT NULL AND placement_distribution != 'unknown'"),
            # User Outcome
            ("installs", "用户-安装(>0)", "> 0"),
            ("purchase_events", "用户-购买(>0)", "> 0"),
            ("p04_events", "用户-P04事件", "> 0"),
            # Economic
            ("roas_d7", "经济-ROAS D7(>0)", "> 0"),
            ("reward", "Reward(>0)", "> 0"),
            # Action
            ("action_taken", "动作-已记录", "IS NOT NULL AND action_taken != 'none'"),
            # MDP
            ("s_t_plus_1_creative_id", "MDP-s_{t+1}", "IS NOT NULL"),
        ]

        print(f"\n  {'维度':<28} {'覆盖率':>10} {'状态'}")
        print(f"  {'─'*28} {'─'*10} {'─'*10}")
        for col, label, condition in dims:
            try:
                non_default = self.conn.execute(
                    f"SELECT COUNT(*) FROM unified_state WHERE {col} {condition}"
                ).fetchone()[0]
            except Exception:
                non_default = 0
            pct = non_default / total * 100
            status = "✅" if pct > 80 else ("⚠️" if pct > 30 else ("🔸" if pct > 0 else "❌"))
            print(f"  {label:<28} {pct:>9.1f}% {status}")

    def _print_gaps(self) -> None:
        """打印已知数据缺口"""
        print(f"\n  📋 已知数据缺口:")
        for col, reason in self.UNAVAILABLE_COLUMNS.items():
            print(f"     ❌ {col:<30} → {reason}")

    # ========================================================================
    # MDP Trajectory 查询
    # ========================================================================

    def query_mdp_trajectory(self, creative_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """查询某个 creative 的完整 MDP 轨迹 (s_t → a_t → r_t → s_{t+1})"""
        rows = self.conn.execute("""
            SELECT date, creative_id, spend, impressions, clicks, ctr, cpm, cpc,
                   installs, purchase_events, purchase_value, roas_d7, reward, reward_type,
                   action_taken, action_budget_change, action_mutation_flag,
                   s_t_plus_1_creative_id, s_t_plus_1_date, s_t_plus_1_reward,
                   hook_type, emotion_tag, cpm_bucket, spend_bucket,
                   game_mechanic_tag, visual_style, cohort_age
            FROM unified_state
            WHERE creative_id = ?
            ORDER BY date ASC
            LIMIT ?
        """, [creative_id, limit]).fetchall()

        return [{
            "date": r[0],
            "creative_id": r[1],
            "s_t": {
                "spend": r[2], "impressions": r[3], "clicks": r[4],
                "ctr": r[5], "cpm": r[6], "cpc": r[7],
                "installs": r[8], "purchases": r[9], "purchase_value": r[10],
                "roas_d7": r[11], "hook_type": r[20], "emotion": r[21],
                "cpm_bucket": r[22], "spend_bucket": r[23],
                "game_mechanic": r[24], "visual_style": r[25], "cohort_age": r[26],
            },
            "a_t": {
                "action": r[14],
                "budget_change": r[15],
                "is_mutation": r[16],
            },
            "r_t": r[12],
            "reward_type": r[13],
            "s_t_plus_1": {
                "creative_id": r[17],
                "date": r[18],
                "reward": r[19],
            },
        } for r in rows]

    def query_mdp_summary(self) -> dict[str, Any]:
        """MDP 结构完整性摘要"""
        total = self.conn.execute("SELECT COUNT(*) FROM unified_state").fetchone()[0]
        if total == 0:
            return {"error": "unified_state 为空"}

        return {
            "total_states": total,
            "unique_creatives": self.conn.execute(
                "SELECT COUNT(DISTINCT creative_id) FROM unified_state"
            ).fetchone()[0],
            "states_with_s_t_plus_1": self.conn.execute(
                "SELECT COUNT(*) FROM unified_state WHERE s_t_plus_1_creative_id IS NOT NULL"
            ).fetchone()[0],
            "states_with_reward_gt_0": self.conn.execute(
                "SELECT COUNT(*) FROM unified_state WHERE reward > 0"
            ).fetchone()[0],
            "states_with_action": self.conn.execute(
                "SELECT COUNT(*) FROM unified_state WHERE action_taken != 'none'"
            ).fetchone()[0],
            "states_with_parent": self.conn.execute(
                "SELECT COUNT(*) FROM unified_state WHERE parent_id IS NOT NULL"
            ).fetchone()[0],
            "reward_types": self.conn.execute("""
                SELECT reward_type, COUNT(*) as cnt
                FROM unified_state
                GROUP BY reward_type
                ORDER BY cnt DESC
            """).fetchall(),
            "date_range": self.conn.execute(
                "SELECT MIN(date), MAX(date) FROM unified_state"
            ).fetchone(),
            "avg_reward": self.conn.execute(
                "SELECT AVG(reward) FROM unified_state WHERE reward > 0"
            ).fetchone()[0],
        }


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Unified State Builder — MDP-ready state_t")
    parser.add_argument("--db", type=str, default="db/facebook_performance.duckdb")
    parser.add_argument("--trajectory", type=str, default=None,
                        help="查询某个 creative_id 的 MDP 轨迹")
    parser.add_argument("--summary", action="store_true",
                        help="打印 MDP 结构摘要")
    args = parser.parse_args()

    builder = UnifiedStateBuilder(args.db)
    try:
        count = builder.build()

        if args.summary:
            summary = builder.query_mdp_summary()
            print(f"\n  📊 MDP 结构摘要:")
            for k, v in summary.items():
                if k == "reward_types":
                    print(f"     reward_types:")
                    for rt, cnt in v:
                        print(f"       {rt}: {cnt}")
                elif k == "date_range":
                    print(f"     date_range: {v[0]} → {v[1]}")
                else:
                    print(f"     {k}: {v}")

        if args.trajectory:
            traj = builder.query_mdp_trajectory(args.trajectory)
            print(f"\n  🔗 MDP 轨迹: {args.trajectory}")
            print(f"  {'─'*80}")
            for t in traj:
                print(f"  {t['date']} | spend=${t['s_t']['spend']:>8.0f} | "
                      f"ctr={t['s_t']['ctr']:.4f} | inst={t['s_t']['installs']:>4d} | "
                      f"r_t={t['r_t']:.3f} ({t['reward_type']}) | "
                      f"a_t={t['a_t']['action']} | "
                      f"s_next={t['s_t_plus_1']['date'] or 'END'} "
                      f"(r={t['s_t_plus_1']['reward']:.3f})" if t['s_t_plus_1']['date'] else
                      f"  {t['date']} | spend=${t['s_t']['spend']:>8.0f} | "
                      f"ctr={t['s_t']['ctr']:.4f} | inst={t['s_t']['installs']:>4d} | "
                      f"r_t={t['r_t']:.3f} ({t['reward_type']}) | "
                      f"a_t={t['a_t']['action']} | "
                      f"s_next=END")

        return 0
    finally:
        builder.close()


if __name__ == "__main__":
    main()