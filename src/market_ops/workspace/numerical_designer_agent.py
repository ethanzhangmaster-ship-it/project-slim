"""Numerical Designer Agent — 运营阶段数值建模与调优.

与 Game Designer Agent 的边界:
  - Game Designer: 设计阶段，从 GDD 生成初始 EconomyBalance 配置（只配置不算法）
  - Numerical Designer: 运营阶段，消费运营数据做数值建模/调优/A/B 测试/通胀监控

设计原则（继承纪律红线）:
  - 复用 v9_company/finance_division 和 product_division 的数据模型，不新增算法层
  - 默认 dry_run：调优建议只生成不执行
  - 参数走配置（NumericalModelConfig），禁止硬编码
  - 接入 MessageBus 广播数值事件
  - 执行结果回流 CEO Memory（domain="numerical"）

依赖注入:
  profitability_engine / economy_manager 可在 __init__ 注入（便于测试），
  默认懒加载 v9_company 的真实实例。当真实模块不可导入时（如纯 workspace
  部署），优雅降级到内置估算模型。

数据流:
  运营数据(KPI/留存/付费) → NumericalDesignerAgent → NumericalModel /
  RetentionCurveModel / PayConversionFunnel / TuningRecommendation /
  ABTestDesign / InflationReport / NumericalReport
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
class NumericalModel:
    """数值建模结果 — LTV/CAC/ROI/回本周期."""

    model_id: str
    game_id: str
    period: str                   # 建模周期 (e.g. "2026-W32")
    arpu: float                   # 每用户平均收入
    arppu: float                  # 每付费用户平均收入
    cac: float                    # 获客成本
    ltv_d7: float                 # 7 日 LTV
    ltv_d30: float                # 30 日 LTV
    ltv_d90: float                # 90 日 LTV (预测)
    ltv_cac_ratio: float          # LTV/CAC 比 (健康 >3.0)
    payback_days: float           # 回本天数
    roi_30d: float                # 30 日 ROI
    roi_90d: float                # 90 日 ROI (预测)
    gross_margin: float           # 毛利率
    contribution_margin: float    # 边际贡献率
    health_score: float           # 综合健康分 (0..100)
    diagnosis: str                # 诊断结论
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "game_id": self.game_id,
            "period": self.period,
            "arpu": round(self.arpu, 4),
            "arppu": round(self.arppu, 4),
            "cac": round(self.cac, 4),
            "ltv_d7": round(self.ltv_d7, 4),
            "ltv_d30": round(self.ltv_d30, 4),
            "ltv_d90": round(self.ltv_d90, 4),
            "ltv_cac_ratio": round(self.ltv_cac_ratio, 4),
            "payback_days": round(self.payback_days, 1),
            "roi_30d": round(self.roi_30d, 4),
            "roi_90d": round(self.roi_90d, 4),
            "gross_margin": round(self.gross_margin, 4),
            "contribution_margin": round(self.contribution_margin, 4),
            "health_score": round(self.health_score, 1),
            "diagnosis": self.diagnosis,
            "created_at": self.created_at,
        }


@dataclass
class RetentionCurveModel:
    """留存曲线模型 — D1/D7/D30 拟合与预测."""

    curve_id: str
    game_id: str
    retention_d1: float           # 次日留存
    retention_d3: float
    retention_d7: float           # 7 日留存
    retention_d14: float
    retention_d30: float          # 30 日留存
    retention_d60: float          # 60 日 (预测)
    retention_d90: float          # 90 日 (预测)
    decay_rate: float             # 衰减率 (幂函数指数)
    curve_type: str               # power_law / exponential / logarithmic
    predicted_d180: float         # 180 日预测
    benchmark_d1: float           # 品类基准 D1
    benchmark_d30: float          # 品类基准 D30
    gap_to_benchmark: str         # vs 基准差距描述
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "game_id": self.game_id,
            "retention_d1": round(self.retention_d1, 4),
            "retention_d3": round(self.retention_d3, 4),
            "retention_d7": round(self.retention_d7, 4),
            "retention_d14": round(self.retention_d14, 4),
            "retention_d30": round(self.retention_d30, 4),
            "retention_d60": round(self.retention_d60, 4),
            "retention_d90": round(self.retention_d90, 4),
            "decay_rate": round(self.decay_rate, 4),
            "curve_type": self.curve_type,
            "predicted_d180": round(self.predicted_d180, 4),
            "benchmark_d1": round(self.benchmark_d1, 4),
            "benchmark_d30": round(self.benchmark_d30, 4),
            "gap_to_benchmark": self.gap_to_benchmark,
            "created_at": self.created_at,
        }


@dataclass
class PayerSegment:
    """付费用户分群."""

    segment_name: str             # minnow / dolphin / whale
    user_count: int
    revenue_share: float          # 收入占比
    avg_spend: float              # 平均消费
    conversion_rate: float        # 转化率

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_name": self.segment_name,
            "user_count": self.user_count,
            "revenue_share": round(self.revenue_share, 4),
            "avg_spend": round(self.avg_spend, 4),
            "conversion_rate": round(self.conversion_rate, 4),
        }


@dataclass
class PayConversionFunnel:
    """付费转化漏斗."""

    funnel_id: str
    game_id: str
    total_users: int
    activated_users: int          # 完成新手引导
    first_pay_users: int          # 首充用户
    repeat_pay_users: int         # 复购用户
    whale_users: int              # 大 R 用户
    activation_rate: float        # 激活率
    first_pay_rate: float         # 首充率
    repeat_rate: float            # 复购率
    whale_rate: float             # 大 R 占比
    avg_first_pay_days: float     # 平均首充天数
    avg_first_pay_amount: float   # 平均首充金额
    payer_segments: list[PayerSegment]
    bottleneck: str               # 漏斗瓶颈描述
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "funnel_id": self.funnel_id,
            "game_id": self.game_id,
            "total_users": self.total_users,
            "activated_users": self.activated_users,
            "first_pay_users": self.first_pay_users,
            "repeat_pay_users": self.repeat_pay_users,
            "whale_users": self.whale_users,
            "activation_rate": round(self.activation_rate, 4),
            "first_pay_rate": round(self.first_pay_rate, 4),
            "repeat_rate": round(self.repeat_rate, 4),
            "whale_rate": round(self.whale_rate, 4),
            "avg_first_pay_days": round(self.avg_first_pay_days, 1),
            "avg_first_pay_amount": round(self.avg_first_pay_amount, 4),
            "payer_segments": [s.to_dict() for s in self.payer_segments],
            "bottleneck": self.bottleneck,
            "created_at": self.created_at,
        }


@dataclass
class TuningRecommendation:
    """数值调优建议."""

    recommendation_id: str
    game_id: str
    target_metric: str            # 目标指标 (e.g. "retention_d1", "arpu", "payback_days")
    current_value: float          # 当前值
    target_value: float           # 目标值
    gap: float                    # 差距
    parameter: str                # 调整参数 (e.g. "daily_faucet", "first_pay_threshold")
    current_param: float          # 当前参数值
    suggested_param: float        # 建议参数值
    adjustment_pct: float         # 调整幅度 %
    expected_impact: str          # 预期影响
    priority: str                 # HIGH / MEDIUM / LOW
    risk_level: str               # LOW / MEDIUM / HIGH
    rationale: str                # 调整理由

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "game_id": self.game_id,
            "target_metric": self.target_metric,
            "current_value": round(self.current_value, 4),
            "target_value": round(self.target_value, 4),
            "gap": round(self.gap, 4),
            "parameter": self.parameter,
            "current_param": round(self.current_param, 4),
            "suggested_param": round(self.suggested_param, 4),
            "adjustment_pct": round(self.adjustment_pct, 2),
            "expected_impact": self.expected_impact,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "rationale": self.rationale,
        }


@dataclass
class ABTestVariant:
    """A/B 测试变体."""

    variant_name: str             # control / treatment_a / treatment_b
    description: str
    parameter_changes: dict[str, float]  # 参数变更
    expected_effect: str          # 预期效果
    sample_ratio: float           # 流量占比

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ABTestDesign:
    """A/B 测试方案."""

    test_id: str
    game_id: str
    hypothesis: str               # 假设
    target_metric: str            # 目标指标
    variants: list[ABTestVariant]
    sample_size_per_variant: int  # 每组样本量
    significance_level: float     # 显著性水平
    power: float                  # 统计功效
    min_detectable_effect: float  # 最小可检测效应
    duration_days: int            # 预计运行天数
    success_criteria: str         # 成功标准
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "game_id": self.game_id,
            "hypothesis": self.hypothesis,
            "target_metric": self.target_metric,
            "variants": [v.to_dict() for v in self.variants],
            "sample_size_per_variant": self.sample_size_per_variant,
            "significance_level": self.significance_level,
            "power": self.power,
            "min_detectable_effect": self.min_detectable_effect,
            "duration_days": self.duration_days,
            "success_criteria": self.success_criteria,
            "created_at": self.created_at,
        }


@dataclass
class InflationReport:
    """通胀监控报告."""

    report_id: str
    game_id: str
    currencies: list[dict[str, Any]]  # 货币通胀状态
    overall_inflation_rate: float    # 整体通胀率
    target_inflation: float          # 目标通胀率
    inflation_status: str            # HEALTHY / WARNING / CRITICAL
    sink_to_faucet_ratio: float      # 消耗/产出比
    currency_imbalance: list[str]    # 失衡货币列表
    recommended_actions: list[str]   # 建议操作
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "currencies": self.currencies,
            "overall_inflation_rate": round(self.overall_inflation_rate, 4),
            "target_inflation": round(self.target_inflation, 4),
            "inflation_status": self.inflation_status,
            "sink_to_faucet_ratio": round(self.sink_to_faucet_ratio, 4),
            "currency_imbalance": self.currency_imbalance,
            "recommended_actions": self.recommended_actions,
            "created_at": self.created_at,
        }


@dataclass
class NumericalReport:
    """完整数值报告 — 聚合所有数值产物."""

    report_id: str
    game_id: str
    numerical_model: dict[str, Any]
    retention_curve: dict[str, Any]
    pay_conversion: dict[str, Any]
    tuning_recommendations: list[dict[str, Any]]
    inflation_report: dict[str, Any]
    overall_health: str           # HEALTHY / ATTENTION / CRITICAL
    health_score: float           # 综合分 (0..100)
    summary: str                  # 报告摘要
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "numerical_model": self.numerical_model,
            "retention_curve": self.retention_curve,
            "pay_conversion": self.pay_conversion,
            "tuning_recommendations": self.tuning_recommendations,
            "inflation_report": self.inflation_report,
            "overall_health": self.overall_health,
            "health_score": round(self.health_score, 1),
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class GenreBenchmark:
    """品类基准值."""

    benchmark_d1: float
    benchmark_d30: float
    target_arpu: float
    target_arppu: float
    target_payback_days: float
    target_ltv_cac: float
    target_first_pay_rate: float


_DEFAULT_BENCHMARKS: dict[str, GenreBenchmark] = {
    "Merge": GenreBenchmark(
        benchmark_d1=0.45, benchmark_d30=0.12,
        target_arpu=0.15, target_arppu=8.0,
        target_payback_days=60.0, target_ltv_cac=3.5,
        target_first_pay_rate=0.08,
    ),
    "Match3": GenreBenchmark(
        benchmark_d1=0.40, benchmark_d30=0.10,
        target_arpu=0.12, target_arppu=6.0,
        target_payback_days=75.0, target_ltv_cac=3.0,
        target_first_pay_rate=0.06,
    ),
    "Simulation": GenreBenchmark(
        benchmark_d1=0.38, benchmark_d30=0.15,
        target_arpu=0.20, target_arppu=12.0,
        target_payback_days=90.0, target_ltv_cac=4.0,
        target_first_pay_rate=0.05,
    ),
}


@dataclass
class NumericalModelConfig:
    """数值建模配置."""

    benchmarks: dict[str, GenreBenchmark] = field(
        default_factory=lambda: {k: v for k, v in _DEFAULT_BENCHMARKS.items()}
    )
    default_genre: str = "Merge"
    significance_level: float = 0.05   # A/B 测试显著性水平
    statistical_power: float = 0.80    # 统计功效
    min_detectable_effect: float = 0.05  # 最小可检测效应
    target_inflation: float = 0.02     # 目标通胀率


# ═══════════════════════════════════════════════════════════════
# 运营数据输入
# ═══════════════════════════════════════════════════════════════


@dataclass
class GameMetrics:
    """游戏运营指标输入 — 从 real_provider 或外部数据源获取."""

    game_id: str
    genre: str = "Merge"
    dau: int = 10000
    total_users: int = 100000
    revenue_total: float = 5000.0
    spend: float = 3000.0
    arpu: float = 0.15
    arppu: float = 8.0
    retention_d1: float = 0.42
    retention_d7: float = 0.18
    retention_d30: float = 0.10
    payer_rate: float = 0.06
    first_pay_rate: float = 0.05
    avg_first_pay_days: float = 3.5
    avg_first_pay_amount: float = 4.99

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# Numerical Designer Agent
# ═══════════════════════════════════════════════════════════════


class NumericalDesignerAgent:
    """Numerical Designer Agent — 运营阶段数值建模与调优.

    用法:
        agent = NumericalDesignerAgent(data_dir="data")
        model = agent.model_numerical(game_id, metrics)
        curve = agent.model_retention(game_id, metrics)
        funnel = agent.analyze_pay_conversion(game_id, metrics)
        recs = agent.recommend_tuning(game_id, metrics)
        ab_test = agent.design_ab_test(game_id, "提高首充率", metrics)
        report = agent.monitor_inflation(game_id, economy_data)
        full = agent.create_numerical_report(game_id, metrics)
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: NumericalModelConfig | None = None,
        profitability_engine: Any = None,
        economy_manager: Any = None,
        message_bus: Any = None,
        agent_identity: Any = None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or NumericalModelConfig()
        self._profitability_engine = profitability_engine
        self._economy_manager = economy_manager
        self._message_bus = message_bus
        self._agent_identity = agent_identity

    # ── 懒加载依赖（复用 v9_company，不导入则降级）──────────────

    def _get_profitability_engine(self) -> Any:
        if self._profitability_engine is not None:
            return self._profitability_engine
        try:
            from src.market_ops.game_company.v9_company.finance_division.profitability_engine import ProfitabilityEngine
            self._profitability_engine = ProfitabilityEngine()
        except ImportError as exc:
            logger.warning("ProfitabilityEngine unavailable, using built-in model: %s", exc)
            self._profitability_engine = None
        return self._profitability_engine

    def _get_economy_manager(self) -> Any:
        if self._economy_manager is not None:
            return self._economy_manager
        try:
            from src.market_ops.game_company.v9_company.product_division.economy_manager import EconomyManager
            self._economy_manager = EconomyManager()
        except ImportError as exc:
            logger.warning("EconomyManager unavailable, using built-in model: %s", exc)
            self._economy_manager = None
        return self._economy_manager

    def _load_design_economy_balance(self, game_id: str) -> dict[str, Any] | None:
        """从设计阶段 EconomyBalance 读取经济基准配置.

        数据源: data/design/economy_balances.jsonl（Game Designer Agent 产出）
        关联键: game_name 字段匹配 game_id（设计阶段以 game_name 作为游戏标识）

        转换逻辑: CurrencyConfig → 通胀监控所需格式
          - inflation_rate: 从 sink_to_faucet_ratio 反推（ratio<1 → 通胀风险高）
          - sink_to_faucet: 直接取设计阶段的实际比值
          - avg_wallet: 用 initial_amount 近似

        Returns:
            转换后的 economy_data dict, 或 None（无匹配记录）
        """
        design_path = Path(self.data_dir) / "design" / "economy_balances.jsonl"
        if not design_path.exists():
            return None

        try:
            text = design_path.read_text(encoding="utf-8")
        except OSError:
            return None

        # 倒序查找最近一条匹配 game_id（game_name）的记录
        for line in reversed([l for l in text.splitlines() if l.strip()]):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            # game_name 作为关联键（designer 用 game_name, numerical 用 game_id）
            if record.get("game_name") != game_id and record.get("gdd_id") != game_id:
                continue

            currencies_raw = record.get("currencies", [])
            if not currencies_raw:
                continue

            design_ratio = float(record.get("sink_to_faucet_ratio", 1.0))
            # 设计阶段 ratio 偏离 1.0 的程度 → 估算通胀率
            # ratio < 1.0 (产出>消耗) → 正通胀; ratio > 1.0 → 负通胀（通缩）
            estimated_inflation = max(0.0, (1.0 - design_ratio) * 0.5 + 0.005)

            currencies_converted = []
            for c in currencies_raw:
                c_ratio = 1.0
                faucet = float(c.get("daily_faucet", 1))
                sink = float(c.get("daily_sink", 1))
                if faucet > 0:
                    c_ratio = sink / faucet
                currencies_converted.append({
                    "name": c.get("currency_name", "unknown"),
                    "inflation_rate": round(max(0.0, (1.0 - c_ratio) * 0.5 + 0.005), 4),
                    "sink_to_faucet": round(c_ratio, 4),
                    "avg_wallet": float(c.get("initial_amount", 100)),
                })

            logger.info(
                "monitor_inflation: using design EconomyBalance %s (game=%s, %d currencies)",
                record.get("balance_id", ""), game_id, len(currencies_converted),
            )
            return {
                "currencies": currencies_converted,
                "source": "design_economy_balance",
                "balance_id": record.get("balance_id", ""),
            }

        return None

    def _get_benchmark(self, genre: str) -> GenreBenchmark:
        return self.config.benchmarks.get(genre, self.config.benchmarks[self.config.default_genre])

    # ── 核心方法 ─────────────────────────────────────────────

    def model_numerical(self, game_id: str, metrics: GameMetrics) -> NumericalModel:
        """数值建模 — LTV/CAC/ROI/回本周期.

        Args:
            game_id: 游戏 ID
            metrics: 运营指标

        Returns:
            NumericalModel 实例
        """
        benchmark = self._get_benchmark(metrics.genre)

        # 尝试复用 ProfitabilityEngine
        pe = self._get_profitability_engine()
        if pe is not None:
            try:
                ltv_cac = pe.get_ltv_cac_ratio()
                unit_econ = pe.get_unit_economics()
                cac = ltv_cac.cac if ltv_cac.cac > 0 else (metrics.spend / max(metrics.dau, 1))
                ltv_d30 = ltv_cac.ltv if ltv_cac.ltv > 0 else metrics.arpu * 30
                payback = ltv_cac.payback_months * 30 if ltv_cac.payback_months > 0 else 0
                gross_margin = 1.0 - (unit_econ.marginal_cost / max(unit_econ.arpu, 0.01))
                contribution = unit_econ.contribution_margin
            except Exception:
                cac = metrics.spend / max(metrics.dau, 1)
                ltv_d30 = metrics.arpu * 30
                payback = cac / max(metrics.arpu, 0.01) if metrics.arpu > 0 else 999
                gross_margin = 0.70
                contribution = 0.55
        else:
            # 降级估算
            cac = metrics.spend / max(metrics.dau, 1)
            ltv_d30 = metrics.arpu * 30
            payback = cac / max(metrics.arpu, 0.01) if metrics.arpu > 0 else 999
            gross_margin = 0.70
            contribution = 0.55

        # LTV 曲线（幂函数衰减）
        ltv_d7 = metrics.arpu * 7 * 0.85
        ltv_d90 = ltv_d30 * 2.2  # 90 日 LTV 约为 30 日的 2.2 倍

        # ROI
        roi_30d = (ltv_d30 - cac) / max(cac, 0.01)
        roi_90d = (ltv_d90 - cac) / max(cac, 0.01)

        # LTV/CAC 比
        ltv_cac_ratio = ltv_d30 / max(cac, 0.01)

        # 健康分评估
        health_score = self._calculate_numerical_health(
            ltv_cac_ratio, payback, roi_30d, metrics.arpu, benchmark
        )

        # 诊断
        diagnosis = self._diagnose_numerical(
            ltv_cac_ratio, payback, roi_30d, metrics.arpu, benchmark
        )

        model = NumericalModel(
            model_id=f"model_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            arpu=metrics.arpu,
            arppu=metrics.arppu,
            cac=cac,
            ltv_d7=ltv_d7,
            ltv_d30=ltv_d30,
            ltv_d90=ltv_d90,
            ltv_cac_ratio=ltv_cac_ratio,
            payback_days=payback,
            roi_30d=roi_30d,
            roi_90d=roi_90d,
            gross_margin=gross_margin,
            contribution_margin=contribution,
            health_score=health_score,
            diagnosis=diagnosis,
            created_at=_now_iso(),
        )

        self._persist_numerical_model(model)
        self._broadcast_event("numerical_modeled", {
            "model_id": model.model_id, "game_id": game_id,
            "ltv_cac_ratio": round(ltv_cac_ratio, 2),
            "health_score": round(health_score, 1),
        })
        self._write_ceo_memory({
            "execution_id": model.model_id,
            "action_id": f"numerical_model_{model.model_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "numerical_modeling",
            "domain": "numerical",
            "action_type": "ltv_cac_modeling",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"LTV/CAC={ltv_cac_ratio:.2f}, payback={payback:.0f}d, health={health_score:.0f}",
        })

        logger.info("Numerical model: %s (LTV/CAC=%.2f, health=%.1f)",
                    game_id, ltv_cac_ratio, health_score)
        return model

    def model_retention(self, game_id: str, metrics: GameMetrics) -> RetentionCurveModel:
        """留存曲线建模 — D1/D7/D30 拟合与预测.

        Args:
            game_id: 游戏 ID
            metrics: 运营指标

        Returns:
            RetentionCurveModel 实例
        """
        benchmark = self._get_benchmark(metrics.genre)

        # 幂函数拟合: R(d) = R1 * d^(-decay_rate)
        # 由 D1 和 D30 反推 decay_rate (R30 = R1 * 30^(-decay) => decay = log(R1/R30) / log(30))
        if metrics.retention_d1 > 0 and metrics.retention_d30 > 0 and metrics.retention_d30 < metrics.retention_d1:
            decay_rate = math.log(metrics.retention_d1 / metrics.retention_d30) / math.log(30)
        else:
            decay_rate = 0.35  # 默认衰减率

        curve_type = "power_law"

        # 插值和预测
        def predict_retention(day: int) -> float:
            if day <= 0:
                return 1.0
            return max(metrics.retention_d1 * (day ** (-decay_rate)), 0.001)

        retention_d3 = predict_retention(3)
        retention_d14 = predict_retention(14)
        retention_d60 = predict_retention(60)
        retention_d90 = predict_retention(90)
        predicted_d180 = predict_retention(180)

        # 与基准对比
        gap_d1 = metrics.retention_d1 - benchmark.benchmark_d1
        gap_d30 = metrics.retention_d30 - benchmark.benchmark_d30
        if gap_d1 >= 0 and gap_d30 >= 0:
            gap_desc = f"D1 +{gap_d1:.2%}, D30 +{gap_d30:.2%} (优于基准)"
        elif gap_d1 < 0 and gap_d30 < 0:
            gap_desc = f"D1 {gap_d1:.2%}, D30 {gap_d30:.2%} (低于基准，需优化)"
        else:
            gap_desc = f"D1 {gap_d1:+.2%}, D30 {gap_d30:+.2%} (混合表现)"

        curve = RetentionCurveModel(
            curve_id=f"ret_curve_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            retention_d1=metrics.retention_d1,
            retention_d3=retention_d3,
            retention_d7=metrics.retention_d7,
            retention_d14=retention_d14,
            retention_d30=metrics.retention_d30,
            retention_d60=retention_d60,
            retention_d90=retention_d90,
            decay_rate=decay_rate,
            curve_type=curve_type,
            predicted_d180=predicted_d180,
            benchmark_d1=benchmark.benchmark_d1,
            benchmark_d30=benchmark.benchmark_d30,
            gap_to_benchmark=gap_desc,
            created_at=_now_iso(),
        )

        self._persist_retention_curve(curve)
        self._broadcast_event("retention_modeled", {
            "curve_id": curve.curve_id, "game_id": game_id,
            "decay_rate": round(decay_rate, 4),
        })
        self._write_ceo_memory({
            "execution_id": curve.curve_id,
            "action_id": f"retention_curve_{curve.curve_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "retention_modeling",
            "domain": "numerical",
            "action_type": "retention_curve_modeling",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"D1={metrics.retention_d1:.2%}, D30={metrics.retention_d30:.2%}, decay={decay_rate:.3f}",
        })

        logger.info("Retention curve: %s (D1=%.2f%%, D30=%.2f%%, decay=%.3f)",
                    game_id, metrics.retention_d1 * 100, metrics.retention_d30 * 100, decay_rate)
        return curve

    def analyze_pay_conversion(self, game_id: str, metrics: GameMetrics) -> PayConversionFunnel:
        """付费转化漏斗分析.

        Args:
            game_id: 游戏 ID
            metrics: 运营指标

        Returns:
            PayConversionFunnel 实例
        """
        total_users = metrics.total_users
        activated_users = int(total_users * 0.85)  # 85% 完成新手引导
        first_pay_users = int(total_users * metrics.first_pay_rate)
        repeat_pay_users = int(first_pay_users * 0.45)  # 45% 复购
        whale_users = int(first_pay_users * 0.05)  # 5% 大 R

        activation_rate = activated_users / max(total_users, 1)
        first_pay_rate = first_pay_users / max(total_users, 1)
        repeat_rate = repeat_pay_users / max(first_pay_users, 1)
        whale_rate = whale_users / max(first_pay_users, 1)

        # 付费分群
        payer_segments: list[PayerSegment] = [
            PayerSegment(
                segment_name="minnow",
                user_count=first_pay_users - whale_users,
                revenue_share=0.30,
                avg_spend=metrics.arppu * 0.3,
                conversion_rate=0.95,
            ),
            PayerSegment(
                segment_name="dolphin",
                user_count=int(whale_users * 4),
                revenue_share=0.40,
                avg_spend=metrics.arppu * 2.0,
                conversion_rate=0.04,
            ),
            PayerSegment(
                segment_name="whale",
                user_count=whale_users,
                revenue_share=0.30,
                avg_spend=metrics.arppu * 10.0,
                conversion_rate=0.01,
            ),
        ]

        # 识别瓶颈
        if first_pay_rate < 0.03:
            bottleneck = "首充率过低 — 优化新手引导和首充礼包定价"
        elif repeat_rate < 0.30:
            bottleneck = "复购率不足 — 优化复购激励和限时活动"
        elif whale_rate < 0.03:
            bottleneck = "大 R 占比偏低 — 增加高端内容和深挖系统"
        else:
            bottleneck = "漏斗健康，持续监控"

        funnel = PayConversionFunnel(
            funnel_id=f"funnel_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            total_users=total_users,
            activated_users=activated_users,
            first_pay_users=first_pay_users,
            repeat_pay_users=repeat_pay_users,
            whale_users=whale_users,
            activation_rate=activation_rate,
            first_pay_rate=first_pay_rate,
            repeat_rate=repeat_rate,
            whale_rate=whale_rate,
            avg_first_pay_days=metrics.avg_first_pay_days,
            avg_first_pay_amount=metrics.avg_first_pay_amount,
            payer_segments=payer_segments,
            bottleneck=bottleneck,
            created_at=_now_iso(),
        )

        self._persist_pay_funnel(funnel)
        self._broadcast_event("pay_conversion_analyzed", {
            "funnel_id": funnel.funnel_id, "game_id": game_id,
            "first_pay_rate": round(first_pay_rate, 4),
        })
        self._write_ceo_memory({
            "execution_id": funnel.funnel_id,
            "action_id": f"pay_funnel_{funnel.funnel_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "pay_conversion_analysis",
            "domain": "numerical",
            "action_type": "pay_conversion_analysis",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"First pay rate={first_pay_rate:.2%}, bottleneck={bottleneck}",
        })

        logger.info("Pay conversion: %s (first_pay=%.2f%%, bottleneck=%s)",
                    game_id, first_pay_rate * 100, bottleneck)
        return funnel

    def recommend_tuning(
        self, game_id: str, metrics: GameMetrics
    ) -> list[TuningRecommendation]:
        """数值调优建议 — 基于 KPI 偏差.

        Args:
            game_id: 游戏 ID
            metrics: 运营指标

        Returns:
            TuningRecommendation 列表
        """
        benchmark = self._get_benchmark(metrics.genre)
        recommendations: list[TuningRecommendation] = []

        # 1. 留存调优
        if metrics.retention_d1 < benchmark.benchmark_d1:
            gap = benchmark.benchmark_d1 - metrics.retention_d1
            recommendations.append(TuningRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                game_id=game_id,
                target_metric="retention_d1",
                current_value=metrics.retention_d1,
                target_value=benchmark.benchmark_d1,
                gap=gap,
                parameter="onboarding_reward",
                current_param=50.0,
                suggested_param=80.0,
                adjustment_pct=60.0,
                expected_impact=f"D1 留存提升 +{gap:.1%}",
                priority="HIGH",
                risk_level="LOW",
                rationale="新手引导奖励不足，增加首日奖励提升 D1 留存",
            ))

        # 2. ARPU 调优
        if metrics.arpu < benchmark.target_arpu:
            gap = benchmark.target_arpu - metrics.arpu
            recommendations.append(TuningRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                game_id=game_id,
                target_metric="arpu",
                current_value=metrics.arpu,
                target_value=benchmark.target_arpu,
                gap=gap,
                parameter="ad_reward_frequency",
                current_param=3.0,
                suggested_param=5.0,
                adjustment_pct=66.7,
                expected_impact=f"ARPU 提升 +${gap:.3f}",
                priority="MEDIUM",
                risk_level="LOW",
                rationale="激励视频频次偏低，增加广告奖励频次提升 ARPU",
            ))

        # 3. 首充率调优
        if metrics.first_pay_rate < benchmark.target_first_pay_rate:
            gap = benchmark.target_first_pay_rate - metrics.first_pay_rate
            recommendations.append(TuningRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                game_id=game_id,
                target_metric="first_pay_rate",
                current_value=metrics.first_pay_rate,
                target_value=benchmark.target_first_pay_rate,
                gap=gap,
                parameter="first_pay_price",
                current_param=4.99,
                suggested_param=0.99,
                adjustment_pct=-80.0,
                expected_impact=f"首充率提升 +{gap:.1%}",
                priority="HIGH",
                risk_level="MEDIUM",
                rationale="首充门槛偏高，降价至 $0.99 提升首充转化",
            ))

        # 4. 回本周期调优
        cac = metrics.spend / max(metrics.dau, 1)
        payback = cac / max(metrics.arpu, 0.01) if metrics.arpu > 0 else 999
        if payback > benchmark.target_payback_days:
            recommendations.append(TuningRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                game_id=game_id,
                target_metric="payback_days",
                current_value=payback,
                target_value=benchmark.target_payback_days,
                gap=payback - benchmark.target_payback_days,
                parameter="daily_faucet_reduction",
                current_param=1.0,
                suggested_param=0.85,
                adjustment_pct=-15.0,
                expected_impact=f"回本周期缩短 {payback - benchmark.target_payback_days:.0f} 天",
                priority="MEDIUM",
                risk_level="MEDIUM",
                rationale="降低免费货币产出 15%，推动付费转化加速回本",
            ))

        # 持久化
        self._persist_tuning_recommendations(game_id, recommendations)

        self._broadcast_event("tuning_recommended", {
            "game_id": game_id,
            "recommendation_count": len(recommendations),
            "high_priority": sum(1 for r in recommendations if r.priority == "HIGH"),
        })
        self._write_ceo_memory({
            "execution_id": f"tuning_{game_id}",
            "action_id": f"tuning_recs_{game_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "numerical_tuning",
            "domain": "numerical",
            "action_type": "numerical_tuning",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Tuning recommendations: {len(recommendations)} items, {sum(1 for r in recommendations if r.priority == 'HIGH')} HIGH",
        })

        logger.info("Tuning recommendations: %s (%d items)",
                    game_id, len(recommendations))
        return recommendations

    def design_ab_test(
        self, game_id: str, hypothesis: str, metrics: GameMetrics,
        target_metric: str = "retention_d1"
    ) -> ABTestDesign:
        """A/B 测试方案设计.

        Args:
            game_id: 游戏 ID
            hypothesis: 测试假设
            metrics: 运营指标
            target_metric: 目标指标

        Returns:
            ABTestDesign 实例
        """
        # 样本量计算（基于正态近似）
        # n = (z_alpha/2 + z_beta)^2 * 2 * p*(1-p) / delta^2
        import statistics
        z_alpha = 1.96  # 95% 置信
        z_beta = 0.84   # 80% 功效
        p = metrics.retention_d1 if target_metric == "retention_d1" else metrics.first_pay_rate
        delta = self.config.min_detectable_effect
        sample_size = int(math.ceil(((z_alpha + z_beta) ** 2 * 2 * p * (1 - p)) / (delta ** 2)))
        sample_size = max(sample_size, 1000)  # 最小 1000

        duration_days = math.ceil(sample_size / max(metrics.dau * 0.5, 100))
        duration_days = max(duration_days, 7)

        # 变体设计
        variants: list[ABTestVariant] = [
            ABTestVariant(
                variant_name="control",
                description="对照组 — 保持当前数值",
                parameter_changes={},
                expected_effect="基准",
                sample_ratio=0.33,
            ),
            ABTestVariant(
                variant_name="treatment_a",
                description="方案 A — 温和调整",
                parameter_changes={"onboarding_reward": 70.0, "first_pay_price": 1.99},
                expected_effect="预期 D1 留存 +3%, 首充率 +1%",
                sample_ratio=0.33,
            ),
            ABTestVariant(
                variant_name="treatment_b",
                description="方案 B — 激进调整",
                parameter_changes={"onboarding_reward": 100.0, "first_pay_price": 0.99},
                expected_effect="预期 D1 留存 +5%, 首充率 +2%",
                sample_ratio=0.34,
            ),
        ]

        test = ABTestDesign(
            test_id=f"abtest_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            hypothesis=hypothesis,
            target_metric=target_metric,
            variants=variants,
            sample_size_per_variant=sample_size,
            significance_level=self.config.significance_level,
            power=self.config.statistical_power,
            min_detectable_effect=self.config.min_detectable_effect,
            duration_days=duration_days,
            success_criteria=f"{target_metric} 提升 ≥{self.config.min_detectable_effect:.1%} 且 p<{self.config.significance_level}",
            created_at=_now_iso(),
        )

        self._persist_ab_test(test)
        self._broadcast_event("ab_test_designed", {
            "test_id": test.test_id, "game_id": game_id,
            "sample_size": sample_size, "duration_days": duration_days,
        })
        self._write_ceo_memory({
            "execution_id": test.test_id,
            "action_id": f"ab_test_{test.test_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "ab_test_design",
            "domain": "numerical",
            "action_type": "ab_test_design",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"AB test: {hypothesis}, n={sample_size}/variant, {duration_days}d",
        })

        logger.info("AB test designed: %s (n=%d, %d days)",
                    game_id, sample_size, duration_days)
        return test

    def monitor_inflation(
        self, game_id: str, economy_data: dict[str, Any] | None = None
    ) -> InflationReport:
        """通胀监控 — 货币产出/消耗监控.

        Args:
            game_id: 游戏 ID
            economy_data: 经济数据（可选，无则尝试从 EconomyManager 获取）

        Returns:
            InflationReport 实例

        数据源优先级:
          1. 显式传入的 economy_data
          2. v9_company EconomyManager.analyze_economy()（运营数据）
          3. 设计阶段 EconomyBalance（data/design/economy_balances.jsonl）作为基准
          4. 内置默认降级值
        """
        # 尝试从 EconomyManager 获取
        em = self._get_economy_manager()
        if economy_data is None and em is not None:
            try:
                metrics_list = em.analyze_economy()
                if metrics_list:
                    economy_data = {
                        "currencies": [
                            {
                                "name": f"currency_{m.product_id}",
                                "inflation_rate": m.currency_inflation_rate,
                                "sink_to_faucet": m.sink_to_faucet_ratio,
                                "avg_wallet": m.avg_wallet_size,
                            }
                            for m in metrics_list
                        ]
                    }
            except Exception:
                economy_data = None

        # 降级到设计阶段 EconomyBalance（Game Designer 产出）
        if economy_data is None:
            economy_data = self._load_design_economy_balance(game_id)

        # 最终降级到默认
        if economy_data is None:
            economy_data = {
                "currencies": [
                    {"name": "Gems", "inflation_rate": 0.015, "sink_to_faucet": 1.08, "avg_wallet": 120},
                    {"name": "Coins", "inflation_rate": 0.025, "sink_to_faucet": 1.05, "avg_wallet": 8500},
                    {"name": "Energy", "inflation_rate": 0.005, "sink_to_faucet": 1.20, "avg_wallet": 95},
                ]
            }

        currencies = economy_data.get("currencies", [])
        overall_inflation = sum(c.get("inflation_rate", 0) for c in currencies) / max(len(currencies), 1)
        avg_ratio = sum(c.get("sink_to_faucet", 1.0) for c in currencies) / max(len(currencies), 1)

        # 通胀状态
        target = self.config.target_inflation
        if overall_inflation <= target:
            status = "HEALTHY"
        elif overall_inflation <= target * 2:
            status = "WARNING"
        else:
            status = "CRITICAL"

        # 失衡货币
        imbalance: list[str] = []
        for c in currencies:
            if c.get("inflation_rate", 0) > target * 1.5:
                imbalance.append(f"{c['name']} 通胀率 {c['inflation_rate']:.2%}")
            if c.get("sink_to_faucet", 1.0) < 1.0:
                imbalance.append(f"{c['name']} 产出 > 消耗 (ratio={c['sink_to_faucet']:.2f})")

        # 建议操作
        actions: list[str] = []
        if overall_inflation > target:
            actions.append("增加消耗点：新增限定道具商店")
        if avg_ratio < 1.0:
            actions.append("降低产出：调整每日任务奖励")
        if any(c.get("sink_to_faucet", 1.0) < 0.95 for c in currencies):
            actions.append("紧急调控：对失衡货币实施产出减半 7 天")
        if not actions:
            actions.append("经济系统健康，维持当前配置")

        report = InflationReport(
            report_id=f"inflation_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            currencies=currencies,
            overall_inflation_rate=overall_inflation,
            target_inflation=target,
            inflation_status=status,
            sink_to_faucet_ratio=avg_ratio,
            currency_imbalance=imbalance,
            recommended_actions=actions,
            created_at=_now_iso(),
        )

        self._persist_inflation_report(report)
        self._broadcast_event("inflation_monitored", {
            "report_id": report.report_id, "game_id": game_id,
            "status": status, "inflation_rate": round(overall_inflation, 4),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"inflation_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "inflation_monitoring",
            "domain": "numerical",
            "action_type": "inflation_monitoring",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Inflation: {overall_inflation:.2%}, status={status}, {len(imbalance)} imbalanced",
        })

        logger.info("Inflation monitor: %s (rate=%.2f%%, status=%s)",
                    game_id, overall_inflation * 100, status)
        return report

    def create_numerical_report(
        self, game_id: str, metrics: GameMetrics
    ) -> NumericalReport:
        """生成完整数值报告（聚合所有数值产物）.

        Args:
            game_id: 游戏 ID
            metrics: 运营指标

        Returns:
            NumericalReport 实例
        """
        model = self.model_numerical(game_id, metrics)
        curve = self.model_retention(game_id, metrics)
        funnel = self.analyze_pay_conversion(game_id, metrics)
        recs = self.recommend_tuning(game_id, metrics)
        inflation = self.monitor_inflation(game_id)

        # 综合健康评估
        health_score = model.health_score
        if inflation.inflation_status == "CRITICAL":
            overall_health = "CRITICAL"
        elif health_score < 50 or inflation.inflation_status == "WARNING":
            overall_health = "ATTENTION"
        else:
            overall_health = "HEALTHY"

        summary = (
            f"{game_id} 数值报告: "
            f"LTV/CAC={model.ltv_cac_ratio:.2f} (回本 {model.payback_days:.0f}天), "
            f"D1={metrics.retention_d1:.1%}/D30={metrics.retention_d30:.1%}, "
            f"首充率={metrics.first_pay_rate:.1%}, "
            f"通胀={inflation.overall_inflation_rate:.2%}({inflation.inflation_status}), "
            f"{len(recs)} 调优建议, 健康={health_score:.0f}/100"
        )

        report = NumericalReport(
            report_id=f"num_report_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            numerical_model=model.to_dict(),
            retention_curve=curve.to_dict(),
            pay_conversion=funnel.to_dict(),
            tuning_recommendations=[r.to_dict() for r in recs],
            inflation_report=inflation.to_dict(),
            overall_health=overall_health,
            health_score=health_score,
            summary=summary,
            created_at=_now_iso(),
        )

        self._persist_numerical_report(report)
        self._broadcast_event("numerical_report_created", {
            "report_id": report.report_id, "game_id": game_id,
            "overall_health": overall_health, "health_score": round(health_score, 1),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"num_report_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "numerical_report",
            "domain": "numerical",
            "action_type": "numerical_report",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Numerical report: {game_id}, health={overall_health}({health_score:.0f})",
        })

        logger.info("Numerical report: %s (health=%s, score=%.1f)",
                    game_id, overall_health, health_score)
        return report

    # ── 查询方法 ─────────────────────────────────────────────

    def list_numerical_models(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "models.jsonl"
        return _read_jsonl(path, limit)

    def list_retention_curves(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "retention_curves.jsonl"
        return _read_jsonl(path, limit)

    def list_pay_funnels(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "pay_funnels.jsonl"
        return _read_jsonl(path, limit)

    def list_tuning_recommendations(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "tuning_recommendations.jsonl"
        return _read_jsonl(path, limit)

    def list_ab_tests(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "ab_tests.jsonl"
        return _read_jsonl(path, limit)

    def list_inflation_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "inflation_reports.jsonl"
        return _read_jsonl(path, limit)

    def list_numerical_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "numerical" / "reports.jsonl"
        return _read_jsonl(path, limit)

    def get_numerical_report(self, report_id: str) -> dict[str, Any] | None:
        for r in self.list_numerical_reports(limit=500):
            if r.get("report_id") == report_id:
                return r
        return None

    def get_stats(self) -> dict[str, Any]:
        models = self.list_numerical_models(limit=1000)
        curves = self.list_retention_curves(limit=1000)
        funnels = self.list_pay_funnels(limit=1000)
        recs = self.list_tuning_recommendations(limit=1000)
        tests = self.list_ab_tests(limit=1000)
        inflations = self.list_inflation_reports(limit=1000)
        reports = self.list_numerical_reports(limit=1000)

        health_dist: dict[str, int] = {}
        for r in reports:
            h = r.get("overall_health", "UNKNOWN")
            health_dist[h] = health_dist.get(h, 0) + 1

        return {
            "total_numerical_models": len(models),
            "total_retention_curves": len(curves),
            "total_pay_funnels": len(funnels),
            "total_tuning_recommendations": len(recs),
            "total_ab_tests": len(tests),
            "total_inflation_reports": len(inflations),
            "total_numerical_reports": len(reports),
            "health_distribution": health_dist,
            "recent_reports": reports[:5],
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _calculate_numerical_health(
        self, ltv_cac: float, payback: float, roi_30d: float,
        arpu: float, benchmark: GenreBenchmark
    ) -> float:
        """计算数值健康分 (0..100)."""
        score = 50.0  # 基础分

        # LTV/CAC 比
        if ltv_cac >= benchmark.target_ltv_cac:
            score += 20
        elif ltv_cac >= benchmark.target_ltv_cac * 0.7:
            score += 10
        else:
            score -= 10

        # 回本周期
        if payback <= benchmark.target_payback_days:
            score += 15
        elif payback <= benchmark.target_payback_days * 1.5:
            score += 5
        else:
            score -= 15

        # ROI
        if roi_30d >= 0:
            score += 10
        else:
            score -= 10

        # ARPU
        if arpu >= benchmark.target_arpu:
            score += 5
        elif arpu >= benchmark.target_arpu * 0.7:
            score += 2

        return max(0, min(100, score))

    def _diagnose_numerical(
        self, ltv_cac: float, payback: float, roi_30d: float,
        arpu: float, benchmark: GenreBenchmark
    ) -> str:
        """诊断数值健康."""
        issues: list[str] = []
        if ltv_cac < benchmark.target_ltv_cac:
            issues.append(f"LTV/CAC={ltv_cac:.2f} 低于目标 {benchmark.target_ltv_cac}")
        if payback > benchmark.target_payback_days:
            issues.append(f"回本周期 {payback:.0f}天 超过目标 {benchmark.target_payback_days:.0f}天")
        if roi_30d < 0:
            issues.append(f"30日ROI={roi_30d:.1%} 为负")
        if arpu < benchmark.target_arpu:
            issues.append(f"ARPU=${arpu:.3f} 低于目标 ${benchmark.target_arpu:.3f}")

        if not issues:
            return "数值健康：LTV/CAC、回本周期、ROI 均达标"
        return "需关注: " + "; ".join(issues)

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_numerical_model(self, model: NumericalModel) -> None:
        path = Path(self.data_dir) / "numerical" / "models.jsonl"
        _append_jsonl(path, model.to_dict())

    def _persist_retention_curve(self, curve: RetentionCurveModel) -> None:
        path = Path(self.data_dir) / "numerical" / "retention_curves.jsonl"
        _append_jsonl(path, curve.to_dict())

    def _persist_pay_funnel(self, funnel: PayConversionFunnel) -> None:
        path = Path(self.data_dir) / "numerical" / "pay_funnels.jsonl"
        _append_jsonl(path, funnel.to_dict())

    def _persist_tuning_recommendations(
        self, game_id: str, recs: list[TuningRecommendation]
    ) -> None:
        path = Path(self.data_dir) / "numerical" / "tuning_recommendations.jsonl"
        record = {
            "game_id": game_id,
            "recommendations": [r.to_dict() for r in recs],
            "created_at": _now_iso(),
        }
        _append_jsonl(path, record)

    def _persist_ab_test(self, test: ABTestDesign) -> None:
        path = Path(self.data_dir) / "numerical" / "ab_tests.jsonl"
        _append_jsonl(path, test.to_dict())

    def _persist_inflation_report(self, report: InflationReport) -> None:
        path = Path(self.data_dir) / "numerical" / "inflation_reports.jsonl"
        _append_jsonl(path, report.to_dict())

    def _persist_numerical_report(self, report: NumericalReport) -> None:
        path = Path(self.data_dir) / "numerical" / "reports.jsonl"
        _append_jsonl(path, report.to_dict())

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
                subject=f"numerical:{event_type}",
                body={"event_type": event_type, "source_agent": "numerical", **payload},
                priority=MessagePriority.NORMAL,
                ttl_seconds=600.0,
            )
            self._message_bus.send(message)
        except Exception as exc:
            logger.warning("NumericalDesignerAgent broadcast event failed: %s", exc)

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
