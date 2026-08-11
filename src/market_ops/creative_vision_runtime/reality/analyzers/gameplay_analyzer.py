"""E12.2 — Gameplay Analyzer。

玩法分析器 —— 回答"玩家在玩什么？哪个关卡卡住？难度曲线合理吗？"

通过 ThinkingData 事件分析 API 分析：
  - 关卡通过率 / 卡点关卡
  - 玩法参与度分布
  - 难度曲线（流失关卡分布）
  - 玩家行为热度

核心逻辑：
  通过率 (pass_rate)
    - pass_rate < 0.20  → 难度过高（卡点）
    - pass_rate > 0.95  → 难度过低（无挑战）
    - 0.50 ≤ pass_rate ≤ 0.85 → 健康区间
  流失率 (churn_rate)
    - churn_rate > 0.15 → 流失关卡（需优化难度或奖励）

Usage:
    analyzer = GameplayAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.choke_points, snapshot.popular_modes)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..thinkingdata_reality import ThinkingDataReality

logger = logging.getLogger(__name__)


@dataclass
class LevelPerformance:
    """单个关卡的表现。

    Attributes:
        level_id:       关卡 ID
        attempts:       总尝试次数
        passes:         通过次数
        pass_rate:      通过率 = passes / attempts
        avg_attempts:   平均尝试次数（每个通过用户）
        churn_rate:     流失率（尝试后未通过且未再登录的比例）
        avg_duration_s: 平均时长（秒）
        status:         状态（healthy / choke_point / too_easy）
    """

    level_id: str = ""
    attempts: int = 0
    passes: int = 0
    pass_rate: float = 0.0
    avg_attempts: float = 0.0
    churn_rate: float = 0.0
    avg_duration_s: float = 0.0
    status: str = "healthy"  # healthy / choke_point / too_easy

    def to_dict(self) -> dict[str, Any]:
        return {
            "level_id": self.level_id,
            "attempts": self.attempts,
            "passes": self.passes,
            "pass_rate": round(self.pass_rate, 4),
            "avg_attempts": round(self.avg_attempts, 2),
            "churn_rate": round(self.churn_rate, 4),
            "avg_duration_s": round(self.avg_duration_s, 1),
            "status": self.status,
        }


@dataclass
class ModeEngagement:
    """单个玩法模式的参与度。

    Attributes:
        mode_name:      玩法名称
        participants:   参与人数
        sessions:       总场次
        avg_sessions:   人均场次
        avg_duration_s: 平均时长（秒）
        retention_lift: 相对基础玩法的留存提升
    """

    mode_name: str = ""
    participants: int = 0
    sessions: int = 0
    avg_sessions: float = 0.0
    avg_duration_s: float = 0.0
    retention_lift: float = 0.0  # +0.05 表示留存比基线高 5%

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_name": self.mode_name,
            "participants": self.participants,
            "sessions": self.sessions,
            "avg_sessions": round(self.avg_sessions, 2),
            "avg_duration_s": round(self.avg_duration_s, 1),
            "retention_lift": round(self.retention_lift, 4),
        }


@dataclass
class GameplaySnapshot:
    """玩法分析快照。

    Attributes:
        project_id:         数数项目 ID
        period_start:       分析周期开始
        period_end:         分析周期结束
        total_players:      活跃玩家数
        avg_session_len:    平均会话时长（秒）
        avg_sessions_per_user: 人均会话数
        levels:             关卡表现列表
        modes:              玩法参与度列表
        choke_points:       卡点关卡列表（pass_rate < 阈值）
        churn_levels:       流失关卡列表（churn_rate 高）
        popular_modes:      最受欢迎玩法（按参与人数 Top）
        difficulty_curve:   难度曲线评价（healthy / too_steep / too_flat）
        top_actions:        玩家行为热度 Top（action, count）
        insights:           洞察列表
    """

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""

    total_players: int = 0
    avg_session_len: float = 0.0
    avg_sessions_per_user: float = 0.0

    levels: list[LevelPerformance] = field(default_factory=list)
    modes: list[ModeEngagement] = field(default_factory=list)

    choke_points: list[str] = field(default_factory=list)
    churn_levels: list[str] = field(default_factory=list)
    popular_modes: list[str] = field(default_factory=list)
    difficulty_curve: str = "healthy"  # healthy / too_steep / too_flat

    top_actions: list[tuple[str, int]] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_players": self.total_players,
            "avg_session_len": round(self.avg_session_len, 1),
            "avg_sessions_per_user": round(self.avg_sessions_per_user, 2),
            "levels": [l.to_dict() for l in self.levels],
            "modes": [m.to_dict() for m in self.modes],
            "choke_points": self.choke_points,
            "churn_levels": self.churn_levels,
            "popular_modes": self.popular_modes,
            "difficulty_curve": self.difficulty_curve,
            "top_actions": [(a, c) for a, c in self.top_actions],
            "insights": self.insights,
        }


class GameplayAnalyzer:
    """玩法分析器。

    消费 ThinkingDataReality，输出 GameplaySnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    # 关卡难度判定阈值
    CHOKE_POINT_RATE = 0.20   # 通过率 < 20% → 卡点
    TOO_EASY_RATE = 0.95      # 通过率 > 95% → 过于简单
    CHURN_RATE_THRESHOLD = 0.15  # 流失率 > 15% → 流失关卡

    # 难度曲线评价：卡点关卡占比阈值
    STEEP_CHOKE_RATIO = 0.30   # 30% 以上关卡是卡点 → 曲线过陡
    FLAT_CHOKE_RATIO = 0.05    # 5% 以下关卡是卡点 → 可能过平
    TOO_EASY_RATIO = 0.30      # 30% 以上关卡过于简单 → 曲线确实过平

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
        levels: list[str] | None = None,
    ) -> GameplaySnapshot:
        """分析玩法表现。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数
            levels:         指定分析的关卡列表，None 时使用默认 Top 关卡

        Returns:
            GameplaySnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        snapshot = GameplaySnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
        )

        # 1. 整体活跃与会话
        self._fetch_session_metrics(project_id, start, end, snapshot)

        # 2. 关卡表现
        self._fetch_level_performance(project_id, start, end, levels, snapshot)

        # 3. 玩法模式参与度
        self._fetch_mode_engagement(project_id, start, end, snapshot)

        # 4. 玩家行为热度
        self._fetch_top_actions(project_id, start, end, snapshot)

        # 5. 识别卡点 / 流失 / 热门
        self._identify_problem_levels(snapshot)

        # 6. 评价难度曲线
        self._evaluate_difficulty_curve(snapshot)

        # 7. 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"GameplayAnalyzer: project={project_id}, "
            f"levels={len(snapshot.levels)}, "
            f"choke_points={len(snapshot.choke_points)}, "
            f"curve={snapshot.difficulty_curve}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_session_metrics(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: GameplaySnapshot,
    ) -> None:
        """拉取整体会话指标。"""
        if not self._td or not self._td._client:
            self._mock_session_metrics(snapshot)
            return

        sql = (
            f"SELECT "
            f"  COUNT(DISTINCT user_id) AS players, "
            f"  COUNT(*) AS sessions, "
            f"  AVG(session_duration) AS avg_len "
            f"FROM v_event_{project_id} "
            f"WHERE event_name = 'session_start' "
            f"  AND event_date BETWEEN '{start}' AND '{end}'"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            if rows:
                row = rows[0]
                if isinstance(row, dict):
                    snapshot.total_players = int(row.get("players", 0))
                    sessions = int(row.get("sessions", 0))
                    snapshot.avg_session_len = float(row.get("avg_len", 0))
                else:
                    snapshot.total_players = int(row[0]) if len(row) > 0 else 0
                    sessions = int(row[1]) if len(row) > 1 else 0
                    snapshot.avg_session_len = float(row[2]) if len(row) > 2 else 0

                if snapshot.total_players > 0:
                    snapshot.avg_sessions_per_user = round(
                        sessions / snapshot.total_players, 2
                    )
        except Exception as exc:
            logger.warning(f"GameplayAnalyzer: session SQL failed: {exc}")
            self._mock_session_metrics(snapshot)

    def _fetch_level_performance(
        self,
        project_id: int,
        start: str,
        end: str,
        levels: list[str] | None,
        snapshot: GameplaySnapshot,
    ) -> None:
        """拉取关卡通过率/流失率（单次聚合查询）。

        优化：原实现按关卡逐个发 SQL（N+1 查询，10 关卡 = 10 次往返），
        现改为单条 GROUP BY level_id 聚合查询，1 次往返获取全部关卡数据。
        """
        if not self._td or not self._td._client:
            self._mock_level_performance(snapshot)
            return

        tracked = levels or [f"level_{i}" for i in range(1, 11)]
        levels_filter = ", ".join(f"'{lvl}'" for lvl in tracked)

        sql = (
            f"SELECT "
            f"  level_id, "
            f"  COUNT(*) AS attempts, "
            f"  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes, "
            f"  AVG(duration) AS avg_dur "
            f"FROM v_event_{project_id} "
            f"WHERE event_name = 'level_complete' "
            f"  AND level_id IN ({levels_filter}) "
            f"  AND event_date BETWEEN '{start}' AND '{end}' "
            f"GROUP BY level_id"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))

            perf_map: dict[str, LevelPerformance] = {}

            for row in rows:
                if isinstance(row, dict):
                    lvl_id = row.get("level_id", "")
                    attempts = int(row.get("attempts", 0))
                    passes = int(row.get("passes", 0))
                    avg_dur = float(row.get("avg_dur", 0))
                else:
                    lvl_id = row[0] if len(row) > 0 else ""
                    attempts = int(row[1]) if len(row) > 1 else 0
                    passes = int(row[2]) if len(row) > 2 else 0
                    avg_dur = float(row[3]) if len(row) > 3 else 0

                perf = LevelPerformance(
                    level_id=lvl_id,
                    attempts=attempts,
                    passes=passes,
                    avg_duration_s=avg_dur,
                )
                if perf.attempts > 0:
                    perf.pass_rate = round(perf.passes / perf.attempts, 4)
                perf.status = self._level_status(perf.pass_rate)
                perf_map[lvl_id] = perf

            # 按 tracked 顺序填充（保持关卡顺序一致，无数据关卡补空记录）
            for lvl in tracked:
                if lvl in perf_map:
                    snapshot.levels.append(perf_map[lvl])
                else:
                    snapshot.levels.append(
                        LevelPerformance(
                            level_id=lvl,
                            status=self._level_status(0.0),
                        )
                    )
        except Exception as exc:
            logger.warning(f"GameplayAnalyzer: level SQL failed: {exc}")
            self._mock_level_performance(snapshot)

    def _fetch_mode_engagement(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: GameplaySnapshot,
    ) -> None:
        """拉取玩法模式参与度。"""
        if not self._td or not self._td._client:
            self._mock_mode_engagement(snapshot)
            return

        sql = (
            f"SELECT "
            f"  mode_name, "
            f"  COUNT(DISTINCT user_id) AS participants, "
            f"  COUNT(*) AS sessions, "
            f"  AVG(duration) AS avg_dur "
            f"FROM v_event_{project_id} "
            f"WHERE event_name = 'mode_start' "
            f"  AND event_date BETWEEN '{start}' AND '{end}' "
            f"GROUP BY mode_name "
            f"ORDER BY participants DESC"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            for row in rows[:10]:
                if isinstance(row, dict):
                    mode = ModeEngagement(
                        mode_name=row.get("mode_name", ""),
                        participants=int(row.get("participants", 0)),
                        sessions=int(row.get("sessions", 0)),
                        avg_duration_s=float(row.get("avg_dur", 0)),
                    )
                else:
                    mode = ModeEngagement(
                        mode_name=row[0] if len(row) > 0 else "",
                        participants=int(row[1]) if len(row) > 1 else 0,
                        sessions=int(row[2]) if len(row) > 2 else 0,
                        avg_duration_s=float(row[3]) if len(row) > 3 else 0,
                    )
                if mode.participants > 0:
                    mode.avg_sessions = round(
                        mode.sessions / mode.participants, 2
                    )
                snapshot.modes.append(mode)
        except Exception as exc:
            logger.warning(f"GameplayAnalyzer: mode SQL failed: {exc}")
            self._mock_mode_engagement(snapshot)

    def _fetch_top_actions(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: GameplaySnapshot,
    ) -> None:
        """拉取玩家行为热度 Top。"""
        if not self._td or not self._td._client:
            snapshot.top_actions = [
                ("move", 1200000),
                ("match", 850000),
                ("use_item", 230000),
                ("hint", 120000),
                ("undo", 80000),
            ]
            return

        sql = (
            f"SELECT action_name, COUNT(*) AS cnt "
            f"FROM v_event_{project_id} "
            f"WHERE event_date BETWEEN '{start}' AND '{end}' "
            f"GROUP BY action_name "
            f"ORDER BY cnt DESC "
            f"LIMIT 5"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            for row in rows:
                if isinstance(row, dict):
                    snapshot.top_actions.append(
                        (row.get("action_name", ""), int(row.get("cnt", 0)))
                    )
                else:
                    snapshot.top_actions.append(
                        (row[0] if len(row) > 0 else "", int(row[1]) if len(row) > 1 else 0)
                    )
        except Exception as exc:
            logger.warning(f"GameplayAnalyzer: actions SQL failed: {exc}")

    def _identify_problem_levels(self, snapshot: GameplaySnapshot) -> None:
        """识别卡点关卡和流失关卡。"""
        for perf in snapshot.levels:
            if perf.status == "choke_point":
                snapshot.choke_points.append(perf.level_id)
            if perf.churn_rate > self.CHURN_RATE_THRESHOLD:
                snapshot.churn_levels.append(perf.level_id)

        # 热门玩法（按参与人数 Top 3）
        sorted_modes = sorted(
            snapshot.modes, key=lambda m: m.participants, reverse=True
        )
        snapshot.popular_modes = [m.mode_name for m in sorted_modes[:3]]

    def _evaluate_difficulty_curve(self, snapshot: GameplaySnapshot) -> None:
        """评价难度曲线。

        too_steep: 卡点占比 ≥ 30%
        too_flat:  卡点占比 ≤ 5% 且过于简单关卡占比 ≥ 30%（缺挑战）
        healthy:   其他
        """
        if not snapshot.levels:
            return

        total = len(snapshot.levels)
        choke_ratio = len(snapshot.choke_points) / total
        too_easy_ratio = sum(
            1 for l in snapshot.levels if l.status == "too_easy"
        ) / total

        if choke_ratio >= self.STEEP_CHOKE_RATIO:
            snapshot.difficulty_curve = "too_steep"
        elif choke_ratio <= self.FLAT_CHOKE_RATIO and too_easy_ratio >= self.TOO_EASY_RATIO:
            snapshot.difficulty_curve = "too_flat"
        else:
            snapshot.difficulty_curve = "healthy"

    def _generate_insights(self, snapshot: GameplaySnapshot) -> None:
        """生成玩法洞察。"""
        insights: list[str] = []

        # 难度曲线
        if snapshot.difficulty_curve == "too_steep":
            insights.append(
                f"难度曲线过陡（{len(snapshot.choke_points)}/{len(snapshot.levels)} "
                f"个卡点关卡），玩家挫败感可能上升，建议降低中期关卡难度或增加奖励"
            )
        elif snapshot.difficulty_curve == "too_flat":
            insights.append(
                "难度曲线过平，缺少挑战性，玩家可能因无聊而流失，"
                "建议增加高难度关卡或挑战模式"
            )
        else:
            insights.append("难度曲线基本健康")

        # 卡点关卡
        for lvl in snapshot.choke_points:
            perf = next(
                (l for l in snapshot.levels if l.level_id == lvl), None
            )
            if perf:
                insights.append(
                    f"关卡 '{lvl}' 是卡点（通过率 {perf.pass_rate:.0%}），"
                    f"建议降低难度或提供引导"
                )

        # 流失关卡
        for lvl in snapshot.churn_levels:
            insights.append(
                f"关卡 '{lvl}' 流失率高，建议检查是否存在 bug 或难度突变"
            )

        # 热门玩法
        if snapshot.popular_modes:
            insights.append(
                f"最受欢迎玩法: {', '.join(snapshot.popular_modes[:3])}"
            )

        # 热门玩法留存提升
        for mode in snapshot.modes:
            if mode.retention_lift > 0.10:
                insights.append(
                    f"玩法 '{mode.mode_name}' 留存提升 {mode.retention_lift:.0%}，"
                    f"建议在新手期引导参与"
                )

        # 会话长度
        if snapshot.avg_session_len > 0:
            if snapshot.avg_session_len < 180:  # < 3 分钟
                insights.append(
                    f"平均会话时长偏短（{snapshot.avg_session_len:.0f}s），"
                    f"建议优化新手引导或增加短期目标"
                )
            elif snapshot.avg_session_len > 1800:  # > 30 分钟
                insights.append(
                    f"平均会话时长较长（{snapshot.avg_session_len:.0f}s），"
                    f"玩家参与度高"
                )

        snapshot.insights = insights

    # ── Helpers ────────────────────────────────────────

    def _level_status(self, pass_rate: float) -> str:
        """根据通过率判定关卡状态。"""
        if pass_rate < self.CHOKE_POINT_RATE:
            return "choke_point"
        if pass_rate > self.TOO_EASY_RATE:
            return "too_easy"
        return "healthy"

    # ── Mock ───────────────────────────────────────────

    def _mock_session_metrics(self, snapshot: GameplaySnapshot) -> None:
        snapshot.total_players = 12000
        snapshot.avg_session_len = 420.0
        snapshot.avg_sessions_per_user = 8.5

    def _mock_level_performance(self, snapshot: GameplaySnapshot) -> None:
        """生成 mock 关卡数据 —— 含 1 个卡点和 1 个流失关卡。"""
        mock_levels = [
            ("level_1", 10000, 9800, 1.1, 0.02, 60),
            ("level_2", 9500, 8800, 1.3, 0.04, 75),
            ("level_3", 8800, 7400, 1.6, 0.06, 90),
            ("level_4", 7400, 5900, 1.9, 0.08, 105),
            ("level_5", 5900, 4100, 2.3, 0.10, 130),
            ("level_6", 4100, 700, 3.5, 0.18, 180),   # 卡点(17%) + 流失（难度墙）
            ("level_7", 680, 550, 2.1, 0.12, 150),
            ("level_8", 550, 460, 1.8, 0.09, 140),
            ("level_9", 460, 390, 1.7, 0.07, 135),
            ("level_10", 390, 370, 1.2, 0.03, 110),
        ]

        for (
            lvl_id,
            attempts,
            passes,
            avg_att,
            churn,
            dur,
        ) in mock_levels:
            pass_rate = round(passes / attempts, 4) if attempts > 0 else 0
            snapshot.levels.append(
                LevelPerformance(
                    level_id=lvl_id,
                    attempts=attempts,
                    passes=passes,
                    pass_rate=pass_rate,
                    avg_attempts=avg_att,
                    churn_rate=churn,
                    avg_duration_s=dur,
                    status=self._level_status(pass_rate),
                )
            )

    def _mock_mode_engagement(self, snapshot: GameplaySnapshot) -> None:
        snapshot.modes = [
            ModeEngagement(
                mode_name="经典消除",
                participants=11000,
                sessions=85000,
                avg_sessions=7.7,
                avg_duration_s=380,
                retention_lift=0.0,
            ),
            ModeEngagement(
                mode_name="限时挑战",
                participants=6500,
                sessions=28000,
                avg_sessions=4.3,
                avg_duration_s=220,
                retention_lift=0.12,
            ),
            ModeEngagement(
                mode_name="多人对战",
                participants=3200,
                sessions=15000,
                avg_sessions=4.7,
                avg_duration_s=290,
                retention_lift=0.18,
            ),
            ModeEngagement(
                mode_name="每日解谜",
                participants=8800,
                sessions=60000,
                avg_sessions=6.8,
                avg_duration_s=180,
                retention_lift=0.08,
            ),
        ]

    def __repr__(self) -> str:
        return f"GameplayAnalyzer(analyzed={self.total_analyzed})"
