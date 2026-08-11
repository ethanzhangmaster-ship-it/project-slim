"""Data Analyst Agent — 玩家行为分析与 BI 洞察.

与 Numerical Designer Agent 的边界:
  - Numerical Designer: 偏数值建模 (LTV/CAC 公式、调优建议、A/B 测试)
  - Data Analyst: 偏行为洞察 (玩家在做什么、为什么流失、漏斗在哪里断)

设计原则（继承纪律红线）:
  - 复用 v9_company 数据模型，不新增算法层
  - 默认 dry_run：洞察只生成不执行
  - 参数走配置（DataAnalystConfig），禁止硬编码
  - 接入 MessageBus 广播分析事件
  - 执行结果回流 CEO Memory（domain="data_analyst"）

数据流:
  玩家行为数据(Sessions/Events/Funnels) → DataAnalystAgent → BehaviorReport /
  FunnelAnalysis / RetentionPrediction / PlayerSegmentation / BIReport /
  AnomalyAlert
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class BehaviorReport:
    """玩家行为报告 — 活跃/会话/参与度."""

    report_id: str
    game_id: str
    period: str                    # 分析周期 (e.g. "2026-W32")
    dau: int                       # 日活
    mau: int                       # 月活
    avg_session_duration: float    # 平均会话时长 (秒)
    avg_sessions_per_user: float   # 人均会话数
    stickiness: float              # DAU/MAU 粘性比 (0..1)
    engagement_score: float        # 参与度评分 (0..100)
    top_actions: list[dict[str, Any]]  # 高频行为
    insights: list[str]            # 行为洞察
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "period": self.period,
            "dau": self.dau,
            "mau": self.mau,
            "avg_session_duration": round(self.avg_session_duration, 1),
            "avg_sessions_per_user": round(self.avg_sessions_per_user, 2),
            "stickiness": round(self.stickiness, 4),
            "engagement_score": round(self.engagement_score, 1),
            "top_actions": self.top_actions,
            "insights": self.insights,
            "created_at": self.created_at,
        }


@dataclass
class FunnelStep:
    """漏斗步骤."""

    step_name: str
    users: int
    conversion_rate: float         # 本步骤转化率
    drop_off_rate: float           # 流失率
    avg_time_to_next: float        # 到下一步平均时长 (秒)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "users": self.users,
            "conversion_rate": round(self.conversion_rate, 4),
            "drop_off_rate": round(self.drop_off_rate, 4),
            "avg_time_to_next": round(self.avg_time_to_next, 1),
        }


@dataclass
class FunnelAnalysis:
    """漏斗归因分析 — 安装→激活→留存→付费."""

    funnel_id: str
    game_id: str
    funnel_name: str
    steps: list[dict[str, Any]]    # FunnelStep.to_dict()
    overall_conversion: float      # 整体转化率
    bottleneck_step: str           # 瓶颈步骤
    bottleneck_reason: str         # 瓶颈原因
    recommendations: list[str]     # 优化建议
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "funnel_id": self.funnel_id,
            "game_id": self.game_id,
            "funnel_name": self.funnel_name,
            "steps": self.steps,
            "overall_conversion": round(self.overall_conversion, 4),
            "bottleneck_step": self.bottleneck_step,
            "bottleneck_reason": self.bottleneck_reason,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


@dataclass
class RetentionPrediction:
    """留存预测 — 基于历史数据预测未来留存."""

    prediction_id: str
    game_id: str
    historical_d1: float
    historical_d7: float
    historical_d30: float
    predicted_d60: float
    predicted_d90: float
    predicted_d180: float
    decay_model: str               # power_law / exponential
    confidence: float              # 置信度 (0..1)
    trend: str                     # improving / stable / declining
    forecast_summary: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "game_id": self.game_id,
            "historical_d1": round(self.historical_d1, 4),
            "historical_d7": round(self.historical_d7, 4),
            "historical_d30": round(self.historical_d30, 4),
            "predicted_d60": round(self.predicted_d60, 4),
            "predicted_d90": round(self.predicted_d90, 4),
            "predicted_d180": round(self.predicted_d180, 4),
            "decay_model": self.decay_model,
            "confidence": round(self.confidence, 2),
            "trend": self.trend,
            "forecast_summary": self.forecast_summary,
            "created_at": self.created_at,
        }


@dataclass
class PlayerSegment:
    """玩家分群."""

    segment_name: str
    user_count: int
    user_share: float              # 占比 (0..1)
    avg_revenue: float
    avg_retention_d7: float
    avg_sessions: float
    characteristics: list[str]     # 分群特征
    recommended_action: str        # 推荐运营动作

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_name": self.segment_name,
            "user_count": self.user_count,
            "user_share": round(self.user_share, 4),
            "avg_revenue": round(self.avg_revenue, 2),
            "avg_retention_d7": round(self.avg_retention_d7, 4),
            "avg_sessions": round(self.avg_sessions, 2),
            "characteristics": self.characteristics,
            "recommended_action": self.recommended_action,
        }


@dataclass
class PlayerSegmentation:
    """玩家分群洞察 — RFM/行为聚类."""

    segmentation_id: str
    game_id: str
    total_users: int
    segments: list[dict[str, Any]]  # PlayerSegment.to_dict()
    segmentation_method: str       # rfm / behavioral / value_based
    key_insight: str               # 核心洞察
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segmentation_id": self.segmentation_id,
            "game_id": self.game_id,
            "total_users": self.total_users,
            "segments": self.segments,
            "segmentation_method": self.segmentation_method,
            "key_insight": self.key_insight,
            "created_at": self.created_at,
        }


@dataclass
class BIReport:
    """BI 报表 — 自动生成运营数据报表."""

    report_id: str
    game_id: str
    period: str
    kpi_summary: dict[str, Any]    # 关键 KPI 摘要
    growth_metrics: dict[str, Any]  # 增长指标
    revenue_metrics: dict[str, Any]  # 收入指标
    engagement_metrics: dict[str, Any]  # 参与度指标
    health_status: str            # HEALTHY / ATTENTION / CRITICAL
    health_score: float           # 综合健康分 (0..100)
    highlights: list[str]         # 亮点
    risks: list[str]              # 风险点
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "period": self.period,
            "kpi_summary": self.kpi_summary,
            "growth_metrics": self.growth_metrics,
            "revenue_metrics": self.revenue_metrics,
            "engagement_metrics": self.engagement_metrics,
            "health_status": self.health_status,
            "health_score": round(self.health_score, 1),
            "highlights": self.highlights,
            "risks": self.risks,
            "created_at": self.created_at,
        }


@dataclass
class AnomalyAlert:
    """异常告警 — 指标异常波动."""

    alert_id: str
    game_id: str
    metric_name: str
    current_value: float
    expected_value: float
    deviation_pct: float           # 偏差百分比
    severity: str                  # info / warning / critical
    detected_at: str
    possible_cause: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "game_id": self.game_id,
            "metric_name": self.metric_name,
            "current_value": round(self.current_value, 4),
            "expected_value": round(self.expected_value, 4),
            "deviation_pct": round(self.deviation_pct, 2),
            "severity": self.severity,
            "detected_at": self.detected_at,
            "possible_cause": self.possible_cause,
            "recommended_action": self.recommended_action,
        }


# ═══════════════════════════════════════════════════════════════
# 配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class GenreBehaviorBenchmark:
    """品类行为基准值."""

    benchmark_d1: float
    benchmark_d30: float
    target_stickiness: float
    target_session_duration: float
    target_sessions_per_user: float


_DEFAULT_BEHAVIOR_BENCHMARKS: dict[str, GenreBehaviorBenchmark] = {
    "Merge": GenreBehaviorBenchmark(
        benchmark_d1=0.45, benchmark_d30=0.12,
        target_stickiness=0.20, target_session_duration=480.0,
        target_sessions_per_user=4.5,
    ),
    "Match3": GenreBehaviorBenchmark(
        benchmark_d1=0.40, benchmark_d30=0.10,
        target_stickiness=0.18, target_session_duration=360.0,
        target_sessions_per_user=5.0,
    ),
    "Simulation": GenreBehaviorBenchmark(
        benchmark_d1=0.38, benchmark_d30=0.15,
        target_stickiness=0.22, target_session_duration=600.0,
        target_sessions_per_user=3.5,
    ),
}


@dataclass
class DataAnalystConfig:
    """数据分析配置."""

    benchmarks: dict[str, GenreBehaviorBenchmark] = field(
        default_factory=lambda: {k: v for k, v in _DEFAULT_BEHAVIOR_BENCHMARKS.items()}
    )
    default_genre: str = "Merge"
    anomaly_threshold_warning: float = 0.15   # 偏差 15% 触发 warning
    anomaly_threshold_critical: float = 0.30  # 偏差 30% 触发 critical
    min_segment_size: int = 100               # 最小分群大小


# ═══════════════════════════════════════════════════════════════
# 行为数据输入
# ═══════════════════════════════════════════════════════════════


@dataclass
class BehaviorData:
    """玩家行为数据输入 — 从事件系统或数据仓库获取."""

    game_id: str
    genre: str = "Merge"
    dau: int = 10000
    mau: int = 80000
    new_users_today: int = 800
    avg_session_duration: float = 420.0
    avg_sessions_per_user: float = 4.0
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    revenue_total: float = 5000.0
    payer_count: int = 600
    top_actions: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"action": "level_complete", "count": 45000, "share": 0.32},
            {"action": "purchase_gems", "count": 3200, "share": 0.02},
            {"action": "watch_ad", "count": 28000, "share": 0.20},
            {"action": "daily_login", "count": 52000, "share": 0.37},
            {"action": "social_share", "count": 1800, "share": 0.01},
        ]
    )
    funnel_data: dict[str, int] = field(
        default_factory=lambda: {
            "install": 10000,
            "activate": 8500,
            "complete_tutorial": 6800,
            "first_session_d7": 4200,
            "first_pay": 500,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# Data Analyst Agent
# ═══════════════════════════════════════════════════════════════


class DataAnalystAgent:
    """Data Analyst Agent — 玩家行为分析与 BI 洞察.

    用法:
        agent = DataAnalystAgent(data_dir="data")
        behavior = agent.analyze_behavior(game_id, data)
        funnel = agent.analyze_funnel(game_id, data)
        prediction = agent.predict_retention(game_id, data)
        segments = agent.segment_players(game_id, data)
        bi_report = agent.generate_bi_report(game_id, data)
        anomalies = agent.detect_anomalies(game_id, data)
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: DataAnalystConfig | None = None,
        message_bus: Any = None,
        agent_identity: Any = None,
        query_engine=None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or DataAnalystConfig()
        self._message_bus = message_bus
        self._agent_identity = agent_identity
        self._query_engine = query_engine

    # ── pandas-ai 集成 ─────────────────────────────────────

    def set_query_engine(self, engine) -> None:
        """注入数据查询引擎 (pandas-ai 封装)."""
        self._query_engine = engine

    def has_query_engine(self) -> bool:
        return self._query_engine is not None

    def _get_query_engine(self):
        """Lazy-load DataQueryEngine, 不可用时返回 None."""
        if self._query_engine is not None:
            return self._query_engine
        try:
            from .data_query_engine import get_data_query_engine
            engine = get_data_query_engine()
            status = engine.check_status()
            if status["status"] == "ready":
                self._query_engine = engine
                return engine
        except Exception as exc:
            logger.debug("数据查询引擎不可用: %s", exc)
        return None

    def ask(
        self,
        question: str,
        data: BehaviorData | None = None,
        extra_dataframes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """用自然语言查询行为数据 — pandas-ai 驱动.

        将 BehaviorData 转为 DataFrame, 附加额外的 DataFrame, 用 pandas-ai
        让 LLM 生成代码并在 DataFrame 上执行.

        Args:
            question: 自然语言问题 (如 "D1 留存低于基准的游戏有哪些?")
            data: 行为数据 (转为 "behavior" DataFrame)
            extra_dataframes: 额外的命名 DataFrame (如 {"revenue": df})

        Returns:
            QueryResult.to_dict(), 不可用时返回降级信息
        """
        engine = self._get_query_engine()
        if engine is None:
            return {
                "question": question,
                "answer": "",
                "error": "pandas-ai 不可用, 请安装并配置 LLM",
                "success": False,
            }

        dataframes: dict[str, Any] = {}
        if data is not None:
            dataframes["behavior"] = data.to_dict()
        if extra_dataframes:
            dataframes.update(extra_dataframes)

        if not dataframes:
            return {
                "question": question,
                "answer": "",
                "error": "没有提供数据",
                "success": False,
            }

        result = engine.ask(question, dataframes)
        return result.to_dict()

    # ── 辅助 ───────────────────────────────────────────────

    def _get_benchmark(self, genre: str) -> GenreBehaviorBenchmark:
        return self.config.benchmarks.get(
            genre, self.config.benchmarks[self.config.default_genre]
        )

    # ── 核心方法 ─────────────────────────────────────────────

    def analyze_behavior(self, game_id: str, data: BehaviorData) -> BehaviorReport:
        """玩家行为分析 — 活跃/会话/参与度.

        Args:
            game_id: 游戏 ID
            data: 行为数据

        Returns:
            BehaviorReport 实例
        """
        benchmark = self._get_benchmark(data.genre)

        # 粘性比 DAU/MAU
        stickiness = data.dau / max(data.mau, 1)

        # 参与度评分 (0..100)
        engagement_score = self._calculate_engagement_score(
            stickiness, data.avg_session_duration,
            data.avg_sessions_per_user, data.retention_d1, benchmark
        )

        # 生成洞察
        insights: list[str] = []
        if stickiness < benchmark.target_stickiness:
            insights.append(
                f"粘性比 {stickiness:.1%} 低于基准 {benchmark.target_stickiness:.1%}，"
                f"建议增加日常任务和社交功能"
            )
        if data.avg_session_duration < benchmark.target_session_duration * 0.8:
            insights.append(
                f"平均会话时长 {data.avg_session_duration:.0f}s 偏短，"
                f"可能内容消耗过快，建议增加深度玩法"
            )
        if data.retention_d1 < benchmark.benchmark_d1:
            insights.append(
                f"D1 留存 {data.retention_d1:.1%} 低于基准 {benchmark.benchmark_d1:.1%}，"
                f"新手引导需优化"
            )
        if not insights:
            insights.append("行为指标整体健康，各项指标达到或超过品类基准")

        # 排序 top actions
        sorted_actions = sorted(
            data.top_actions, key=lambda x: x.get("count", 0), reverse=True
        )[:5]

        report = BehaviorReport(
            report_id=f"beh_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            dau=data.dau,
            mau=data.mau,
            avg_session_duration=data.avg_session_duration,
            avg_sessions_per_user=data.avg_sessions_per_user,
            stickiness=stickiness,
            engagement_score=engagement_score,
            top_actions=sorted_actions,
            insights=insights,
            created_at=_now_iso(),
        )

        self._persist_behavior_report(report)
        self._broadcast_event("behavior_analyzed", {
            "report_id": report.report_id, "game_id": game_id,
            "engagement_score": round(engagement_score, 1),
            "stickiness": round(stickiness, 3),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"behavior_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "behavior_analysis",
            "domain": "data_analyst",
            "action_type": "player_behavior_analysis",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"DAU={data.dau}, stickiness={stickiness:.2%}, engagement={engagement_score:.0f}",
        })

        logger.info("Behavior analyzed: %s (stickiness=%.2f, engagement=%.1f)",
                    game_id, stickiness, engagement_score)
        return report

    def analyze_funnel(self, game_id: str, data: BehaviorData) -> FunnelAnalysis:
        """漏斗归因分析 — 识别转化瓶颈.

        Args:
            game_id: 游戏 ID
            data: 行为数据（含 funnel_data）

        Returns:
            FunnelAnalysis 实例
        """
        funnel_data = data.funnel_data
        step_names = list(funnel_data.keys())
        steps: list[dict[str, Any]] = []
        prev_users = 0

        for i, step_name in enumerate(step_names):
            users = funnel_data[step_name]
            if i == 0:
                conv_rate = 1.0
                drop_off = 0.0
            else:
                conv_rate = users / max(prev_users, 1)
                drop_off = 1.0 - conv_rate
            # 估算到下一步平均时长 (递增)
            avg_time = i * 120.0  # 每步约 2 分钟
            step = FunnelStep(
                step_name=step_name,
                users=users,
                conversion_rate=conv_rate,
                drop_off_rate=drop_off,
                avg_time_to_next=avg_time,
            )
            steps.append(step.to_dict())
            prev_users = users

        # 整体转化率 = 最后一步 / 第一步
        overall_conversion = steps[-1]["users"] / max(steps[0]["users"], 1)

        # 识别瓶颈（流失率最高的步骤）
        max_drop_idx = 1
        max_drop = 0.0
        for i in range(1, len(steps)):
            if steps[i]["drop_off_rate"] > max_drop:
                max_drop = steps[i]["drop_off_rate"]
                max_drop_idx = i

        bottleneck_step = steps[max_drop_idx]["step_name"]
        bottleneck_reason = self._diagnose_bottleneck(bottleneck_step, max_drop)
        recommendations = self._recommend_funnel_fix(bottleneck_step, max_drop)

        funnel = FunnelAnalysis(
            funnel_id=f"funnel_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            funnel_name="install_to_pay",
            steps=steps,
            overall_conversion=overall_conversion,
            bottleneck_step=bottleneck_step,
            bottleneck_reason=bottleneck_reason,
            recommendations=recommendations,
            created_at=_now_iso(),
        )

        self._persist_funnel(funnel)
        self._broadcast_event("funnel_analyzed", {
            "funnel_id": funnel.funnel_id, "game_id": game_id,
            "overall_conversion": round(overall_conversion, 4),
            "bottleneck": bottleneck_step,
        })
        self._write_ceo_memory({
            "execution_id": funnel.funnel_id,
            "action_id": f"funnel_{funnel.funnel_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "funnel_attribution",
            "domain": "data_analyst",
            "action_type": "funnel_attribution",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Bottleneck={bottleneck_step}, overall_conv={overall_conversion:.2%}",
        })

        logger.info("Funnel analyzed: %s (bottleneck=%s, conv=%.2f%%)",
                    game_id, bottleneck_step, overall_conversion * 100)
        return funnel

    def predict_retention(
        self, game_id: str, data: BehaviorData
    ) -> RetentionPrediction:
        """留存预测 — 基于历史数据预测未来留存.

        使用幂函数衰减模型: R(d) = R_d1 * d^(-decay_rate)

        Args:
            game_id: 游戏 ID
            data: 行为数据

        Returns:
            RetentionPrediction 实例
        """
        # 衰减率拟合 (D1 → D30)
        if data.retention_d30 > 0 and data.retention_d1 > 0:
            decay_rate = math.log(data.retention_d1 / data.retention_d30) / math.log(30)
        else:
            decay_rate = 0.5

        # 预测 D60, D90, D180
        def predict(day: int) -> float:
            if day <= 1:
                return data.retention_d1
            predicted = data.retention_d1 * (day ** (-decay_rate))
            return max(min(predicted, 1.0), 0.0)

        predicted_d60 = predict(60)
        predicted_d90 = predict(90)
        predicted_d180 = predict(180)

        # 趋势判断 (D7 vs D1 衰减速度)
        d7_d1_ratio = data.retention_d7 / max(data.retention_d1, 0.01)
        if d7_d1_ratio > 0.45:
            trend = "improving"
            confidence = 0.85
        elif d7_d1_ratio > 0.35:
            trend = "stable"
            confidence = 0.75
        else:
            trend = "declining"
            confidence = 0.65

        benchmark = self._get_benchmark(data.genre)
        if predicted_d90 > benchmark.benchmark_d30 * 0.8:
            forecast_summary = (
                f"D90 预测 {predicted_d90:.1%}，接近或超过品类基准，留存健康"
            )
        else:
            forecast_summary = (
                f"D90 预测 {predicted_d90:.1%}，低于品类基准 {benchmark.benchmark_d30:.1%}，"
                f"需要优化中长期留存机制"
            )

        prediction = RetentionPrediction(
            prediction_id=f"pred_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            historical_d1=data.retention_d1,
            historical_d7=data.retention_d7,
            historical_d30=data.retention_d30,
            predicted_d60=predicted_d60,
            predicted_d90=predicted_d90,
            predicted_d180=predicted_d180,
            decay_model="power_law",
            confidence=confidence,
            trend=trend,
            forecast_summary=forecast_summary,
            created_at=_now_iso(),
        )

        self._persist_retention_prediction(prediction)
        self._broadcast_event("retention_predicted", {
            "prediction_id": prediction.prediction_id, "game_id": game_id,
            "predicted_d90": round(predicted_d90, 4),
            "trend": trend,
        })
        self._write_ceo_memory({
            "execution_id": prediction.prediction_id,
            "action_id": f"retention_pred_{prediction.prediction_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "retention_prediction",
            "domain": "data_analyst",
            "action_type": "retention_prediction",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"D90_pred={predicted_d90:.2%}, trend={trend}, confidence={confidence:.0%}",
        })

        logger.info("Retention predicted: %s (D90=%.2f%%, trend=%s)",
                    game_id, predicted_d90 * 100, trend)
        return prediction

    def segment_players(
        self, game_id: str, data: BehaviorData
    ) -> PlayerSegmentation:
        """玩家分群 — RFM (Recency/Frequency/Monetary) 分群.

        Args:
            game_id: 游戏 ID
            data: 行为数据

        Returns:
            PlayerSegmentation 实例
        """
        total_users = data.mau
        payer_count = data.payer_count
        non_payer_count = total_users - payer_count

        # RFM 分群
        # 高价值: 近期活跃 + 高频 + 付费
        high_value_users = int(payer_count * 0.20)
        # 中价值: 活跃 + 偶尔付费
        mid_value_users = int(payer_count * 0.50)
        # 低价值付费: 付费但不活跃
        low_value_payers = payer_count - high_value_users - mid_value_users
        # 活跃非付费: 活跃但不付费
        active_non_payers = int(non_payer_count * 0.40)
        # 流失风险: 不活跃
        churn_risk_users = non_payer_count - active_non_payers

        avg_revenue = data.revenue_total / max(payer_count, 1)

        segments: list[PlayerSegment] = [
            PlayerSegment(
                segment_name="vip_whale",
                user_count=high_value_users,
                user_share=high_value_users / total_users,
                avg_revenue=avg_revenue * 8.0,
                avg_retention_d7=0.65,
                avg_sessions=8.0,
                characteristics=["高消费", "高频活跃", "社交活跃"],
                recommended_action="专属客服 + 限量礼包 + 新内容抢先体验",
            ),
            PlayerSegment(
                segment_name="dolphin",
                user_count=mid_value_users,
                user_share=mid_value_users / total_users,
                avg_revenue=avg_revenue * 2.5,
                avg_retention_d7=0.45,
                avg_sessions=5.5,
                characteristics=["中等消费", "稳定活跃", "偶尔社交"],
                recommended_action="中期礼包 + 成长基金 + 社交激励",
            ),
            PlayerSegment(
                segment_name="minnow_payer",
                user_count=low_value_payers,
                user_share=low_value_payers / total_users,
                avg_revenue=avg_revenue * 0.5,
                avg_retention_d7=0.25,
                avg_sessions=3.0,
                characteristics=["低消费", "活跃度下降", "需刺激"],
                recommended_action="首充翻倍 + 回归礼包 + 推送召回",
            ),
            PlayerSegment(
                segment_name="active_free",
                user_count=active_non_payers,
                user_share=active_non_payers / total_users,
                avg_revenue=0.0,
                avg_retention_d7=0.35,
                avg_sessions=4.0,
                characteristics=["免费玩家", "活跃", "广告变现潜力"],
                recommended_action="激励视频广告 + 首充特惠 + 限时免费",
            ),
            PlayerSegment(
                segment_name="churn_risk",
                user_count=churn_risk_users,
                user_share=churn_risk_users / total_users,
                avg_revenue=0.0,
                avg_retention_d7=0.08,
                avg_sessions=1.5,
                characteristics=["流失风险", "低活跃", "需要召回"],
                recommended_action="流失召回活动 + 推送 + 邮件召回",
            ),
        ]

        # 核心洞察
        payer_share = payer_count / total_users
        if payer_share < 0.03:
            key_insight = f"付费率仅 {payer_share:.1%}，低于行业基准 5%，付费转化是核心瓶颈"
        elif churn_risk_users / total_users > 0.4:
            key_insight = f"流失风险用户占比 {churn_risk_users/total_users:.1%}，召回优先级最高"
        else:
            key_insight = (
                f"用户结构健康，VIP/Dolphin 贡献 "
                f"{(high_value_users+mid_value_users)/max(payer_count,1):.0%} 收入"
            )

        segmentation = PlayerSegmentation(
            segmentation_id=f"seg_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            total_users=total_users,
            segments=[s.to_dict() for s in segments if s.user_count >= self.config.min_segment_size],
            segmentation_method="rfm",
            key_insight=key_insight,
            created_at=_now_iso(),
        )

        self._persist_segmentation(segmentation)
        self._broadcast_event("players_segmented", {
            "segmentation_id": segmentation.segmentation_id, "game_id": game_id,
            "segment_count": len(segmentation.segments),
            "payer_share": round(payer_share, 4),
        })
        self._write_ceo_memory({
            "execution_id": segmentation.segmentation_id,
            "action_id": f"segmentation_{segmentation.segmentation_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "player_segmentation",
            "domain": "data_analyst",
            "action_type": "player_segmentation",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"{len(segmentation.segments)} segments, payer_share={payer_share:.1%}",
        })

        logger.info("Players segmented: %s (%d segments, payer_share=%.1f%%)",
                    game_id, len(segmentation.segments), payer_share * 100)
        return segmentation

    def generate_bi_report(self, game_id: str, data: BehaviorData) -> BIReport:
        """生成 BI 报表 — 自动汇总运营数据.

        Args:
            game_id: 游戏 ID
            data: 行为数据

        Returns:
            BIReport 实例
        """
        benchmark = self._get_benchmark(data.genre)

        # KPI 摘要
        kpi_summary = {
            "dau": data.dau,
            "mau": data.mau,
            "new_users": data.new_users_today,
            "payer_count": data.payer_count,
            "payer_rate": round(data.payer_count / max(data.dau, 1), 4),
            "arpu": round(data.revenue_total / max(data.dau, 1), 4),
            "stickiness": round(data.dau / max(data.mau, 1), 4),
        }

        # 增长指标
        growth_metrics = {
            "d1_retention": data.retention_d1,
            "d7_retention": data.retention_d7,
            "d30_retention": data.retention_d30,
            "new_user_ratio": round(data.new_users_today / max(data.dau, 1), 4),
            "d1_vs_benchmark": round(data.retention_d1 - benchmark.benchmark_d1, 4),
        }

        # 收入指标
        revenue_metrics = {
            "total_revenue": data.revenue_total,
            "arpu": round(data.revenue_total / max(data.dau, 1), 4),
            "arppu": round(data.revenue_total / max(data.payer_count, 1), 2),
            "payer_rate": round(data.payer_count / max(data.dau, 1), 4),
        }

        # 参与度指标
        engagement_metrics = {
            "avg_session_duration": data.avg_session_duration,
            "avg_sessions_per_user": data.avg_sessions_per_user,
            "stickiness": round(data.dau / max(data.mau, 1), 4),
            "session_vs_benchmark": round(
                data.avg_session_duration - benchmark.target_session_duration, 1
            ),
        }

        # 健康评估
        health_score = self._calculate_bi_health_score(
            data, benchmark
        )
        if health_score >= 75:
            health_status = "HEALTHY"
        elif health_score >= 50:
            health_status = "ATTENTION"
        else:
            health_status = "CRITICAL"

        # 亮点与风险
        highlights: list[str] = []
        risks: list[str] = []

        if data.retention_d1 >= benchmark.benchmark_d1:
            highlights.append(f"D1 留存 {data.retention_d1:.1%} 达到基准")
        else:
            risks.append(f"D1 留存 {data.retention_d1:.1%} 低于基准 {benchmark.benchmark_d1:.1%}")

        payer_rate = data.payer_count / max(data.dau, 1)
        if payer_rate >= 0.05:
            highlights.append(f"付费率 {payer_rate:.1%} 达到行业基准")
        else:
            risks.append(f"付费率 {payer_rate:.1%} 低于 5% 基准")

        stickiness = data.dau / max(data.mau, 1)
        if stickiness >= benchmark.target_stickiness:
            highlights.append(f"粘性比 {stickiness:.1%} 达到基准")
        else:
            risks.append(f"粘性比 {stickiness:.1%} 低于基准 {benchmark.target_stickiness:.1%}")

        if not highlights:
            highlights.append("各项指标稳定运行")
        if not risks:
            risks.append("暂无显著风险")

        report = BIReport(
            report_id=f"bi_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            kpi_summary=kpi_summary,
            growth_metrics=growth_metrics,
            revenue_metrics=revenue_metrics,
            engagement_metrics=engagement_metrics,
            health_status=health_status,
            health_score=health_score,
            highlights=highlights,
            risks=risks,
            created_at=_now_iso(),
        )

        self._persist_bi_report(report)
        self._broadcast_event("bi_report_generated", {
            "report_id": report.report_id, "game_id": game_id,
            "health_status": health_status,
            "health_score": round(health_score, 1),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"bi_report_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "bi_reporting",
            "domain": "data_analyst",
            "action_type": "bi_reporting",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"BI report: {game_id}, health={health_status}({health_score:.0f})",
        })

        logger.info("BI report generated: %s (health=%s, score=%.1f)",
                    game_id, health_status, health_score)
        return report

    def detect_anomalies(
        self, game_id: str, data: BehaviorData
    ) -> list[AnomalyAlert]:
        """异常检测 — 指标异常波动.

        Args:
            game_id: 游戏 ID
            data: 行为数据

        Returns:
            AnomalyAlert 列表
        """
        benchmark = self._get_benchmark(data.genre)
        alerts: list[AnomalyAlert] = []

        # 检查各项指标偏差
        checks = [
            ("retention_d1", data.retention_d1, benchmark.benchmark_d1,
             "新手引导/首日体验问题", "优化新手引导流程"),
            ("retention_d30", data.retention_d30, benchmark.benchmark_d30,
             "中长期内容消耗过快", "增加中后期内容和社交系统"),
            ("stickiness", data.dau / max(data.mau, 1), benchmark.target_stickiness,
             "用户活跃度下降", "增加日常任务和签到激励"),
            ("session_duration", data.avg_session_duration, benchmark.target_session_duration,
             "会话时长下降", "检查内容更新和难度曲线"),
        ]

        for metric_name, current, expected, cause, action in checks:
            if expected <= 0:
                continue
            deviation = (current - expected) / expected
            # 只对负向偏差告警
            if deviation < -self.config.anomaly_threshold_warning:
                if deviation < -self.config.anomaly_threshold_critical:
                    severity = "critical"
                else:
                    severity = "warning"
                alert = AnomalyAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:8]}",
                    game_id=game_id,
                    metric_name=metric_name,
                    current_value=current,
                    expected_value=expected,
                    deviation_pct=deviation * 100,
                    severity=severity,
                    detected_at=_now_iso(),
                    possible_cause=cause,
                    recommended_action=action,
                )
                alerts.append(alert)

        # 持久化告警
        for alert in alerts:
            self._persist_anomaly_alert(alert)

        if alerts:
            critical_count = sum(1 for a in alerts if a.severity == "critical")
            self._broadcast_event("anomalies_detected", {
                "game_id": game_id,
                "alert_count": len(alerts),
                "critical_count": critical_count,
            })
            self._write_ceo_memory({
                "execution_id": f"anomaly_batch_{uuid.uuid4().hex[:8]}",
                "action_id": f"anomaly_detect_{game_id}",
                "decision_id": game_id,
                "game_id": game_id,
                "strategy_type": "anomaly_detection",
                "domain": "data_analyst",
                "action_type": "anomaly_detection",
                "status": "success", "success": True,
                "real_api_called": False, "rolled_back": False,
                "detail": f"{len(alerts)} anomalies, {critical_count} critical",
            })

        logger.info("Anomalies detected: %s (%d alerts, %d critical)",
                    game_id, len(alerts),
                    sum(1 for a in alerts if a.severity == "critical"))
        return alerts

    # ── 查询方法 ─────────────────────────────────────────────

    def list_behavior_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "behavior_reports.jsonl"
        return _read_jsonl(path, limit)

    def list_funnels(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "funnels.jsonl"
        return _read_jsonl(path, limit)

    def list_retention_predictions(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "retention_predictions.jsonl"
        return _read_jsonl(path, limit)

    def list_segmentations(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "segmentations.jsonl"
        return _read_jsonl(path, limit)

    def list_bi_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "bi_reports.jsonl"
        return _read_jsonl(path, limit)

    def list_anomaly_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "data_analyst" / "anomaly_alerts.jsonl"
        return _read_jsonl(path, limit)

    def get_bi_report(self, report_id: str) -> dict[str, Any] | None:
        for r in self.list_bi_reports(limit=500):
            if r.get("report_id") == report_id:
                return r
        return None

    def get_stats(self) -> dict[str, Any]:
        behavior = self.list_behavior_reports(limit=1000)
        funnels = self.list_funnels(limit=1000)
        predictions = self.list_retention_predictions(limit=1000)
        segmentations = self.list_segmentations(limit=1000)
        bi_reports = self.list_bi_reports(limit=1000)
        alerts = self.list_anomaly_alerts(limit=1000)

        health_dist: dict[str, int] = {}
        for r in bi_reports:
            h = r.get("health_status", "UNKNOWN")
            health_dist[h] = health_dist.get(h, 0) + 1

        severity_dist: dict[str, int] = {}
        for a in alerts:
            s = a.get("severity", "unknown")
            severity_dist[s] = severity_dist.get(s, 0) + 1

        return {
            "total_behavior_reports": len(behavior),
            "total_funnels": len(funnels),
            "total_retention_predictions": len(predictions),
            "total_segmentations": len(segmentations),
            "total_bi_reports": len(bi_reports),
            "total_anomaly_alerts": len(alerts),
            "health_distribution": health_dist,
            "severity_distribution": severity_dist,
            "recent_bi_reports": bi_reports[:5],
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _calculate_engagement_score(
        self, stickiness: float, session_duration: float,
        sessions_per_user: float, retention_d1: float,
        benchmark: GenreBehaviorBenchmark
    ) -> float:
        """计算参与度评分 (0..100)."""
        score = 0.0
        # 粘性 30%
        stickiness_ratio = min(stickiness / max(benchmark.target_stickiness, 0.01), 1.0)
        score += stickiness_ratio * 30
        # 会话时长 25%
        session_ratio = min(session_duration / max(benchmark.target_session_duration, 1.0), 1.0)
        score += session_ratio * 25
        # 会话频次 20%
        sessions_ratio = min(sessions_per_user / max(benchmark.target_sessions_per_user, 0.1), 1.0)
        score += sessions_ratio * 20
        # D1 留存 25%
        d1_ratio = min(retention_d1 / max(benchmark.benchmark_d1, 0.01), 1.0)
        score += d1_ratio * 25
        return min(score, 100.0)

    def _calculate_bi_health_score(
        self, data: BehaviorData, benchmark: GenreBehaviorBenchmark
    ) -> float:
        """计算 BI 健康分 (0..100)."""
        score = 0.0
        # 留存 40%
        d1_score = min(data.retention_d1 / max(benchmark.benchmark_d1, 0.01), 1.0) * 20
        d30_score = min(data.retention_d30 / max(benchmark.benchmark_d30, 0.01), 1.0) * 20
        score += d1_score + d30_score
        # 付费 30%
        payer_rate = data.payer_count / max(data.dau, 1)
        payer_score = min(payer_rate / 0.05, 1.0) * 30
        score += payer_score
        # 参与度 30%
        stickiness = data.dau / max(data.mau, 1)
        stickiness_score = min(stickiness / max(benchmark.target_stickiness, 0.01), 1.0) * 30
        score += stickiness_score
        return min(score, 100.0)

    def _diagnose_bottleneck(self, step_name: str, drop_rate: float) -> str:
        """诊断漏斗瓶颈原因."""
        reasons = {
            "activate": "激活阶段流失严重 — 可能安装包过大或启动慢",
            "complete_tutorial": "新手引导完成率低 — 引导流程过长或难度不当",
            "first_session_d7": "7 日回流率低 — 缺乏中长期留存动力",
            "first_pay": "首充转化率低 — 首充礼包吸引力不足或定价过高",
        }
        return reasons.get(step_name, f"{step_name} 阶段流失率 {drop_rate:.1%}，需进一步分析")

    def _recommend_funnel_fix(self, step_name: str, drop_rate: float) -> list[str]:
        """推荐漏斗修复方案."""
        recs_map = {
            "activate": [
                "优化安装包大小，减少启动加载时间",
                "提供游客登录和一键登录选项",
                "首屏展示核心玩法，减少前置动画",
            ],
            "complete_tutorial": [
                "简化新手引导，仅保留核心操作教学",
                "新手引导首通奖励翻倍",
                "A/B 测试不同引导流程长度",
            ],
            "first_session_d7": [
                "设计 D2-D7 每日登录递增奖励",
                "增加社交系统（好友/公会）绑定",
                "推送个性化召回消息",
            ],
            "first_pay": [
                "首充礼包定价降至 $0.99，提供超值回报",
                "增加限时首充倒计时",
                "新手引导末尾植入首充引导",
            ],
        }
        return recs_map.get(step_name, [f"分析 {step_name} 阶段用户行为，定位流失原因"])

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_behavior_report(self, report: BehaviorReport) -> None:
        path = Path(self.data_dir) / "data_analyst" / "behavior_reports.jsonl"
        _append_jsonl(path, report.to_dict())

    def _persist_funnel(self, funnel: FunnelAnalysis) -> None:
        path = Path(self.data_dir) / "data_analyst" / "funnels.jsonl"
        _append_jsonl(path, funnel.to_dict())

    def _persist_retention_prediction(self, prediction: RetentionPrediction) -> None:
        path = Path(self.data_dir) / "data_analyst" / "retention_predictions.jsonl"
        _append_jsonl(path, prediction.to_dict())

    def _persist_segmentation(self, segmentation: PlayerSegmentation) -> None:
        path = Path(self.data_dir) / "data_analyst" / "segmentations.jsonl"
        _append_jsonl(path, segmentation.to_dict())

    def _persist_bi_report(self, report: BIReport) -> None:
        path = Path(self.data_dir) / "data_analyst" / "bi_reports.jsonl"
        _append_jsonl(path, report.to_dict())

    def _persist_anomaly_alert(self, alert: AnomalyAlert) -> None:
        path = Path(self.data_dir) / "data_analyst" / "anomaly_alerts.jsonl"
        _append_jsonl(path, alert.to_dict())

    # ── 跨 Agent 协同 ──────────────────────────────────────

    def _broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._message_bus is None or self._agent_identity is None:
            return
        try:
            from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                AgentMessage, MessageType, MessagePriority,
            )
            message = AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:12]}",
                sender=self._agent_identity,
                receiver=None,
                message_type=MessageType.BROADCAST,
                subject=f"data_analyst:{event_type}",
                body={"event_type": event_type, "source_agent": "data_analyst", **payload},
                priority=MessagePriority.NORMAL,
                ttl_seconds=600.0,
            )
            self._message_bus.send(message)
        except Exception as exc:
            logger.warning("DataAnalystAgent broadcast event failed: %s", exc)

    def _write_ceo_memory(self, record: dict[str, Any]) -> None:
        ceo_memory_path = Path(self.data_dir) / "ceo" / "execution_memory.jsonl"
        ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("created_at", _now_iso())
        with ceo_memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """追加写入 JSONL 文件 (带轮转保护)."""
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(path.parent.parent) if path.parent.parent else "data")
    rotator.maybe_rotate(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records
