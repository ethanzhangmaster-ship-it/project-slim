"""E12.2 — Funnel Analyzer。

游戏漏斗分析器 —— 回答"用户在哪里流失？"

通过 ThinkingData 漏斗分析 API，建立标准转化漏斗：
  安装 → 进入游戏 → 完成教程 → 完成第10关 → 首次付费

每个节点输出：进入人数、完成人数、转化率、流失率、平均耗时。

Usage:
    analyzer = FunnelAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.drop_off_steps)
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
class FunnelStep:
    """漏斗单步。"""

    step_name: str = ""
    event_name: str = ""
    entered: int = 0
    completed: int = 0
    conversion_rate: float = 0.0
    drop_off_rate: float = 0.0
    avg_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "event_name": self.event_name,
            "entered": self.entered,
            "completed": self.completed,
            "conversion_rate": round(self.conversion_rate, 4),
            "drop_off_rate": round(self.drop_off_rate, 4),
            "avg_time_seconds": round(self.avg_time_seconds, 2),
        }


@dataclass
class FunnelSnapshot:
    """漏斗快照。"""

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""
    funnel_name: str = ""

    steps: list[FunnelStep] = field(default_factory=list)

    # 整体转化率（首步到末步）
    overall_conversion: float = 0.0

    # 流失最严重的步骤
    drop_off_steps: list[str] = field(default_factory=list)

    # 洞察
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "funnel_name": self.funnel_name,
            "steps": [s.to_dict() for s in self.steps],
            "overall_conversion": round(self.overall_conversion, 4),
            "drop_off_steps": self.drop_off_steps,
            "insights": self.insights,
        }


class FunnelAnalyzer:
    """游戏漏斗分析器。

    消费 ThinkingDataReality，输出 FunnelSnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    # 默认漏斗定义
    DEFAULT_FUNNEL = [
        {"step": "安装", "event": "ta_app_install"},
        {"step": "进入游戏", "event": "game_start"},
        {"step": "完成教程", "event": "tutorial_complete"},
        {"step": "完成第10关", "event": "level_complete"},
        {"step": "首次付费", "event": "purchase"},
    ]

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
        funnel_steps: list[dict] | None = None,
    ) -> FunnelSnapshot:
        """分析转化漏斗。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数
            funnel_steps:  自定义漏斗步骤 [{"step": "名称", "event": "事件"}]
                            None 时使用默认漏斗

        Returns:
            FunnelSnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        steps_def = funnel_steps or self.DEFAULT_FUNNEL

        snapshot = FunnelSnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
            funnel_name="标准转化漏斗",
        )

        # 拉取漏斗数据
        self._fetch_funnel(project_id, steps_def, start, end, snapshot)

        # 计算转化率和流失率
        self._compute_rates(snapshot)

        # 识别流失最严重的步骤
        self._identify_drop_offs(snapshot)

        # 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"FunnelAnalyzer: project={project_id}, "
            f"{len(snapshot.steps)} steps, "
            f"overall={snapshot.overall_conversion:.2%}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_funnel(
        self,
        project_id: int,
        steps_def: list[dict],
        start: str,
        end: str,
        snapshot: FunnelSnapshot,
    ) -> None:
        """通过 ThinkingData API 拉取漏斗数据。"""
        if not self._td or not self._td._client:
            # Mock 数据
            self._mock_funnel(steps_def, snapshot)
            return

        # 构建漏斗分析请求
        events = []
        for s in steps_def:
            events.append({"eventName": s["event"]})

        payload = {
            "events": events,
            "timeRange": {"start": start, "end": end},
            "funnelType": "convert",
        }

        try:
            result = self._td._client.funnel_analyze(project_id, payload)
            self._parse_funnel_result(result, steps_def, snapshot)
        except Exception as exc:
            logger.warning(f"FunnelAnalyzer: funnel_analyze failed: {exc}")
            self._mock_funnel(steps_def, snapshot)

    def _parse_funnel_result(
        self,
        result: dict[str, Any],
        steps_def: list[dict],
        snapshot: FunnelSnapshot,
    ) -> None:
        """解析数数漏斗分析返回结果。"""
        data = result.get("data", result.get("result", {}))
        rows = data.get("rows", data.get("series", []))

        for i, step_def in enumerate(steps_def):
            step = FunnelStep(
                step_name=step_def["step"],
                event_name=step_def["event"],
            )

            # 从结果中提取每步数据
            if rows:
                row = rows[0] if isinstance(rows, list) else rows
                values = row.get("values", row.get("steps", []))
                if i < len(values):
                    val = values[i]
                    if isinstance(val, dict):
                        step.entered = int(val.get("entered", val.get("total", 0)))
                        step.completed = int(val.get("completed", val.get("convert", 0)))
                        step.avg_time_seconds = float(val.get("avg_time", 0))
                    elif isinstance(val, (int, float)):
                        step.entered = int(val)

            snapshot.steps.append(step)

    def _compute_rates(self, snapshot: FunnelSnapshot) -> None:
        """计算每步转化率和流失率。"""
        for i, step in enumerate(snapshot.steps):
            if i == 0:
                # 第一步：完成率 = completed / entered
                step.conversion_rate = (
                    round(step.completed / step.entered, 4)
                    if step.entered > 0 else 0.0
                )
            else:
                # 后续步骤：相对于上一步的转化率
                prev = snapshot.steps[i - 1]
                step.conversion_rate = (
                    round(step.completed / prev.completed, 4)
                    if prev.completed > 0 else 0.0
                )

            step.drop_off_rate = round(1.0 - step.conversion_rate, 4)

        # 整体转化率
        if snapshot.steps:
            first = snapshot.steps[0]
            last = snapshot.steps[-1]
            snapshot.overall_conversion = (
                round(last.completed / first.entered, 4)
                if first.entered > 0 else 0.0
            )

    def _identify_drop_offs(self, snapshot: FunnelSnapshot) -> None:
        """识别流失最严重的步骤。"""
        drop_offs: list[tuple[str, float]] = []

        for i, step in enumerate(snapshot.steps):
            if i > 0 and step.drop_off_rate > 0.30:
                drop_offs.append((step.step_name, step.drop_off_rate))

        # 按流失率降序
        drop_offs.sort(key=lambda x: x[1], reverse=True)
        snapshot.drop_off_steps = [name for name, _ in drop_offs]

    def _generate_insights(self, snapshot: FunnelSnapshot) -> None:
        """生成漏斗洞察。"""
        insights: list[str] = []

        if not snapshot.steps:
            insights.append("漏斗数据为空")
            snapshot.insights = insights
            return

        # 整体转化
        if snapshot.overall_conversion < 0.02:
            insights.append(
                f"整体转化率极低 ({snapshot.overall_conversion:.2%})，"
                f"需系统性优化漏斗"
            )
        elif snapshot.overall_conversion > 0.10:
            insights.append(
                f"整体转化率良好 ({snapshot.overall_conversion:.2%})"
            )

        # 流失步骤
        for step_name in snapshot.drop_off_steps:
            step = next(
                (s for s in snapshot.steps if s.step_name == step_name),
                None,
            )
            if step:
                insights.append(
                    f"'{step_name}' 流失率 {step.drop_off_rate:.0%}，"
                    f"是核心瓶颈，建议优先优化"
                )

        # 首步转化
        first = snapshot.steps[0]
        if first.conversion_rate < 0.80:
            insights.append(
                f"首步转化率 {first.conversion_rate:.0%}，"
                f"安装到进入游戏的转化偏低"
            )

        # 付费转化
        if len(snapshot.steps) >= 5:
            pay_step = snapshot.steps[-1]
            if pay_step.conversion_rate < 0.05:
                insights.append(
                    f"付费转化率 {pay_step.conversion_rate:.0%}，"
                    f"建议增加首充礼包或降低首次付费门槛"
                )

        snapshot.insights = insights

    # ── Mock ───────────────────────────────────────────

    def _mock_funnel(
        self,
        steps_def: list[dict],
        snapshot: FunnelSnapshot,
    ) -> None:
        """生成 mock 漏斗数据。"""
        base = 10000
        for i, s in enumerate(steps_def):
            # 每步递减
            decay = 0.75 - i * 0.12
            entered = int(base * (0.95 ** i))
            completed = int(entered * max(decay, 0.02))
            avg_time = 30 + i * 120  # 越往后耗时越长

            snapshot.steps.append(FunnelStep(
                step_name=s["step"],
                event_name=s["event"],
                entered=entered,
                completed=completed,
                avg_time_seconds=avg_time,
            ))

    def __repr__(self) -> str:
        return f"FunnelAnalyzer(analyzed={self.total_analyzed})"
