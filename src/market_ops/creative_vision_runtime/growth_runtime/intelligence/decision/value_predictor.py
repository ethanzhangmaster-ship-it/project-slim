"""E13.7.2 DecisionValuePredictor — 决策价值预测引擎.

Day 7.2 核心模块:
  从"我相信这个策略"升级为"这个策略未来值多少钱"。

核心职责:
  1. 预测未来价值: avg_reward × success_probability × scalability × (1 - decay_risk)
  2. 计算决策效用: expected_value × prediction_confidence
  3. 多策略比较: 按 utility 排序

公式:
  expected_value = avg_reward × success_probability × scalability × (1 - decay_risk)
  decision_utility = expected_value × prediction_confidence

数据来源:
  - DecisionMemorySync: 历史决策记录 → avg_reward, success_probability, reward_std
  - PatternStore: 模式表现 → trend (衰减), samples (规模), quality (可靠性)

与现有模块的关系:
  - E12.2 ConfidenceEngine: 诊断置信度 (当前状态)
  - E12.3 PredictionConfidenceEngine: 预测置信度 (未来趋势)
  - E13.7.1 DecisionConfidenceEngine: 决策置信度 (动作价值)
  - E13.7.2 DecisionValuePredictor: 价值预测 (未来收益)

用法:
    predictor = DecisionValuePredictor(decision_sync=dsync, pattern_store=pstore)
    prediction = predictor.predict("S1", "creative_fatigue", "replace_creative")
    if prediction.expected_value > 0.5:
        execute()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# DecisionValuePrediction
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionValuePrediction:
    """决策价值预测 — 对未来价值的完整评估.

    Attributes:
        strategy_id: 策略 ID
        strategy_name: 策略名称
        opportunity_type: 机会类型
        action_type: 动作类型

        # 核心预测
        expected_value: 预期价值 [0, 1]
        decision_utility: 决策效用 = expected_value × prediction_confidence [0, 1]

        # 分解因子
        avg_reward: 历史平均奖励
        success_probability: 预测成功概率
        scalability_score: 扩量潜力 [0, 1]
        decay_risk: 衰减风险 [0, 1]

        # 数据质量
        sample_size: 样本量
        prediction_confidence: 预测自身置信度 [0, 1]

        # 预测解释
        horizon_days: 预测时间窗口 (天)
        warnings: 警告信息
        components: 各因子详细分解
        computed_at: 计算时间
    """
    strategy_id: str = ""
    strategy_name: str = ""
    opportunity_type: str = ""
    action_type: str = ""

    # 核心预测
    expected_value: float = 0.0
    decision_utility: float = 0.0

    # 分解因子
    avg_reward: float = 0.0
    success_probability: float = 0.0
    scalability_score: float = 0.0
    decay_risk: float = 0.0

    # 数据质量
    sample_size: int = 0
    prediction_confidence: float = 0.0

    # 预测解释
    horizon_days: int = 7
    warnings: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_high_value(self) -> bool:
        """是否高价值 (expected_value >= 0.6)."""
        return self.expected_value >= 0.6

    @property
    def is_viable(self) -> bool:
        """是否可行 (expected_value >= 0.3)."""
        return self.expected_value >= 0.3

    @property
    def is_high_decay(self) -> bool:
        """是否高衰减风险 (decay_risk >= 0.5)."""
        return self.decay_risk >= 0.5

    @property
    def has_sufficient_data(self) -> bool:
        """是否有足够数据 (sample_size >= 3)."""
        return self.sample_size >= 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "expected_value": round(self.expected_value, 4),
            "decision_utility": round(self.decision_utility, 4),
            "avg_reward": round(self.avg_reward, 4),
            "success_probability": round(self.success_probability, 4),
            "scalability_score": round(self.scalability_score, 4),
            "decay_risk": round(self.decay_risk, 4),
            "sample_size": self.sample_size,
            "prediction_confidence": round(self.prediction_confidence, 4),
            "horizon_days": self.horizon_days,
            "warnings": self.warnings,
            "components": self.components,
            "computed_at": self.computed_at,
        }


# ═══════════════════════════════════════════════════════════════
# DecisionValuePredictor
# ═══════════════════════════════════════════════════════════════


class DecisionValuePredictor:
    """E13.7.2 DecisionValuePredictor — 决策价值预测引擎.

    对每个策略预测未来价值，综合评估:
      1. avg_reward: 历史平均奖励 (来自 DecisionMemorySync)
      2. success_probability: 预测成功概率 (来自 DecisionMemorySync)
      3. scalability_score: 扩量潜力 (来自 PatternPerformance)
      4. decay_risk: 衰减风险 (来自 PatternPerformance.trend)

    公式:
      expected_value = avg_reward × success_probability × scalability × (1 - decay_risk)
      decision_utility = expected_value × prediction_confidence

    Attributes:
        _decision_sync: DecisionMemorySync 实例
        _pattern_store: PatternStore 实例
        _default_horizon_days: 默认预测时间窗口
    """

    # ── 阈值配置 ──────────────────────────────────────────────

    MIN_SAMPLES_PREDICT = 3     # 最低预测样本数
    MIN_SAMPLES_RELIABLE = 10   # 可靠预测样本数
    DEFAULT_HORIZON_DAYS = 7    # 默认预测窗口

    # ── 扩量因子权重 ──────────────────────────────────────────

    SCALABILITY_SAMPLE_WEIGHT = 0.6
    SCALABILITY_TREND_WEIGHT = 0.4

    # ── 衰减趋势窗口 ──────────────────────────────────────────

    TREND_WINDOW_RECENT = 3     # 最近 N 次用于衰减计算

    def __init__(
        self,
        decision_sync: Any = None,  # DecisionMemorySync
        pattern_store: Any = None,  # PatternStore
        horizon_days: int = 7,
    ):
        """初始化价值预测器.

        Args:
            decision_sync: DecisionMemorySync 实例
            pattern_store: PatternStore 实例
            horizon_days: 预测时间窗口 (默认 7 天)
        """
        self._decision_sync = decision_sync
        self._pattern_store = pattern_store
        self._horizon_days = horizon_days or self.DEFAULT_HORIZON_DAYS

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def predict(
        self,
        strategy_id: str = "",
        strategy_name: str = "",
        opportunity_type: str = "",
        action_type: str = "",
    ) -> DecisionValuePrediction:
        """预测单个策略的未来价值.

        Args:
            strategy_id: 策略 ID
            strategy_name: 策略名称
            opportunity_type: 机会类型
            action_type: 动作类型

        Returns:
            DecisionValuePrediction: 价值预测结果
        """
        pred = DecisionValuePrediction(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            opportunity_type=opportunity_type,
            action_type=action_type,
            horizon_days=self._horizon_days,
        )

        # 1. 从 DecisionMemorySync 获取历史数据
        records = self._get_historical_records(
            strategy_id=strategy_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
        )

        if not records:
            pred.warnings.append("No historical decision data for value prediction.")
            return pred

        # 2. 计算基础因子
        pred.sample_size = len(records)
        pred.avg_reward = self._compute_avg_reward(records)
        pred.success_probability = self._compute_success_probability(records)

        # 3. 从 PatternStore 获取扩量潜力和衰减风险
        perf = self._get_pattern_performance(opportunity_type, action_type)
        pred.scalability_score = self._compute_scalability(perf, pred.sample_size)
        pred.decay_risk = self._compute_decay_risk(perf, records)

        # 4. 计算预期价值
        pred.expected_value = self._compute_expected_value(pred)

        # 5. 计算预测置信度
        pred.prediction_confidence = self._compute_prediction_confidence(pred)

        # 6. 计算决策效用
        pred.decision_utility = self._compute_decision_utility(pred)

        # 7. 生成警告
        self._generate_warnings(pred)

        # 8. 记录组件分解
        pred.components = {
            "avg_reward": round(pred.avg_reward, 4),
            "success_probability": round(pred.success_probability, 4),
            "scalability": round(pred.scalability_score, 4),
            "decay_risk": round(pred.decay_risk, 4),
            "prediction_confidence": round(pred.prediction_confidence, 4),
        }

        return pred

    def compare_alternatives(
        self,
        strategies: list[dict[str, str]],
        opportunity_type: str = "",
    ) -> list[DecisionValuePrediction]:
        """比较多个备选策略，按 decision_utility 排序.

        Args:
            strategies: 策略列表 [{"strategy_id": "S1", "strategy_name": "...", "action_type": "..."}]
            opportunity_type: 机会类型

        Returns:
            list[DecisionValuePrediction]: 按 decision_utility 降序排列
        """
        results: list[DecisionValuePrediction] = []
        for s in strategies:
            sid = s.get("strategy_id", "")
            sname = s.get("strategy_name", "")
            atype = s.get("action_type", "")
            pred = self.predict(
                strategy_id=sid,
                strategy_name=sname,
                opportunity_type=opportunity_type,
                action_type=atype,
            )
            results.append(pred)

        results.sort(key=lambda p: p.decision_utility, reverse=True)
        return results

    # ═══════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════

    def _compute_expected_value(self, pred: DecisionValuePrediction) -> float:
        """计算预期价值.

        expected_value = avg_reward × success_probability × scalability × (1 - decay_risk)
        """
        # 负奖励 → 预期价值为负
        if pred.avg_reward < 0:
            return round(pred.avg_reward * pred.success_probability, 4)

        value = (
            pred.avg_reward
            * pred.success_probability
            * pred.scalability_score
            * (1.0 - pred.decay_risk)
        )
        return round(max(0.0, min(1.0, value)), 4)

    def _compute_decision_utility(self, pred: DecisionValuePrediction) -> float:
        """计算决策效用.

        decision_utility = expected_value × prediction_confidence
        """
        utility = pred.expected_value * pred.prediction_confidence
        return round(max(0.0, min(1.0, utility)), 4)

    def _compute_prediction_confidence(self, pred: DecisionValuePrediction) -> float:
        """计算预测自身置信度.

        基于样本量和数据质量:
          - sample_size >= 20 → 1.0
          - sample_size >= 10 → 0.8
          - sample_size >= 3  → 0.5
          - sample_size < 3   → 0.0 (不可预测)
        """
        if pred.sample_size < self.MIN_SAMPLES_PREDICT:
            return 0.0
        if pred.sample_size >= self.MIN_SAMPLES_RELIABLE * 2:
            return 1.0
        if pred.sample_size >= self.MIN_SAMPLES_RELIABLE:
            return 0.8
        # 3-9 samples: linear interpolation
        ratio = (pred.sample_size - self.MIN_SAMPLES_PREDICT) / (
            self.MIN_SAMPLES_RELIABLE - self.MIN_SAMPLES_PREDICT
        )
        return round(0.5 + 0.3 * ratio, 4)

    # ═══════════════════════════════════════════════════════════
    # 因子计算
    # ═══════════════════════════════════════════════════════════

    def _compute_avg_reward(self, records: list[Any]) -> float:
        """计算历史平均奖励."""
        rewards = [
            r.reward for r in records
            if getattr(r, "reward", None) is not None
        ]
        if not rewards:
            return 0.0
        return round(sum(rewards) / len(rewards), 4)

    def _compute_success_probability(self, records: list[Any]) -> float:
        """计算预测成功概率."""
        if not records:
            return 0.0
        success_count = sum(1 for r in records if getattr(r, "success", False))
        return round(success_count / len(records), 4)

    def _compute_scalability(
        self,
        perf: Any,
        sample_size: int,
    ) -> float:
        """计算扩量潜力.

        scalability = sample_factor × 0.6 + trend_stability × 0.4

        - sample_factor: 对数平滑样本量 (10→0.5, 100→0.7, 500→0.85)
        - trend_stability: 趋势稳定性 (平稳/上升→高, 波动/下降→低)
        """
        # 样本量因子
        total_samples = sample_size
        if perf is not None:
            total_samples = max(total_samples, getattr(perf, "samples", 0))

        if total_samples < self.MIN_SAMPLES_PREDICT:
            return 0.2  # 不可扩量

        sample_factor = min(1.0, math.log(total_samples + 1) / math.log(100))

        # 趋势稳定性
        trend_stability = 0.5  # 默认中性
        if perf is not None:
            trend = getattr(perf, "trend", [])
            if trend:
                trend_stability = self._compute_trend_stability(trend)

        return round(
            sample_factor * self.SCALABILITY_SAMPLE_WEIGHT
            + trend_stability * self.SCALABILITY_TREND_WEIGHT,
            4,
        )

    def _compute_decay_risk(
        self,
        perf: Any,
        records: list[Any],
    ) -> float:
        """计算衰减风险.

        来源:
          1. PatternPerformance.trend: 最近 N 次成功率变化
          2. 历史记录的时间衰减: 近期成功 vs 远期成功

        衰减率 = (recent_success - old_success) / old_success
        decay_risk = clamp(-decay_rate, 0, 1)
        """
        # 来源 1: PatternPerformance.trend
        if perf is not None:
            trend = getattr(perf, "trend", [])
            if trend and len(trend) >= 2:
                # 取最近与最早的趋势值对比
                recent = trend[-1]
                old = trend[0]
                if old > 0:
                    decay_rate = (recent - old) / old
                    # 负 decay_rate → 衰减 → decay_risk 高
                    decay_risk = max(0.0, min(1.0, -decay_rate))
                    return round(decay_risk, 4)

        # 来源 2: 历史记录时间衰减
        if len(records) >= 4:
            return self._compute_temporal_decay(records)

        return 0.0

    def _compute_temporal_decay(self, records: list[Any]) -> float:
        """基于时间序列计算衰减.

        比较近期与远期的成功率差异。
        """
        # 按时间排序
        sorted_records = sorted(
            records,
            key=lambda r: getattr(r, "created_at", "") or "",
        )

        half = len(sorted_records) // 2
        older = sorted_records[:half]
        recent = sorted_records[half:]

        older_rate = sum(1 for r in older if getattr(r, "success", False)) / max(len(older), 1)
        recent_rate = sum(1 for r in recent if getattr(r, "success", False)) / max(len(recent), 1)

        if older_rate > 0:
            decay_rate = (recent_rate - older_rate) / older_rate
            return round(max(0.0, min(1.0, -decay_rate)), 4)

        # 如果早期全部失败，近期有成功 → 衰减为 0 (正在改善)
        if recent_rate > 0:
            return 0.0

        return 0.5  # 全部失败 → 中性

    def _compute_trend_stability(self, trend: list[float]) -> float:
        """计算趋势稳定性.

        平稳或上升趋势 → 高稳定性
        剧烈波动或下降 → 低稳定性

        stability = 1 - abs(mean(trend) - last) / mean(trend)
        """
        if len(trend) < 2:
            return 0.5

        mean_val = sum(trend) / len(trend)
        if abs(mean_val) < 0.001:
            return 0.0

        last_val = trend[-1]
        deviation = abs(last_val - mean_val) / abs(mean_val)

        # 趋势上升 → 额外加分
        bonus = 0.0
        if len(trend) >= 3:
            first_half = sum(trend[:len(trend)//2]) / (len(trend)//2)
            second_half = sum(trend[len(trend)//2:]) / (len(trend) - len(trend)//2)
            if second_half > first_half:
                bonus = 0.15

        stability = max(0.0, min(1.0, 1.0 - deviation + bonus))
        return round(stability, 4)

    # ═══════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════

    def _get_historical_records(
        self,
        strategy_id: str = "",
        opportunity_type: str = "",
        action_type: str = "",
    ) -> list[Any]:
        """从 DecisionMemorySync 获取已完成的历史记录."""
        if self._decision_sync is None:
            return []

        try:
            records = self._decision_sync.get_completed_decisions(
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
            if strategy_id:
                records = [
                    r for r in records
                    if getattr(r, "strategy_id", "") == strategy_id
                ]
            return records
        except Exception:
            return []

    def _get_pattern_performance(
        self,
        opportunity_type: str,
        action_type: str,
    ) -> Any:
        """从 PatternStore 获取 PatternPerformance."""
        if self._pattern_store is None:
            return None

        try:
            # 尝试 query 方法
            if hasattr(self._pattern_store, "query"):
                from ...memory.models import PatternQuery
                query = PatternQuery(
                    opportunity_types=[opportunity_type] if opportunity_type else [],
                    action_types=[action_type] if action_type else [],
                    limit=1,
                    sort_by="score",
                )
                patterns = self._pattern_store.query(query)
                if patterns:
                    return getattr(patterns[0], "performance", None)

            # 尝试 get_all + 过滤
            if hasattr(self._pattern_store, "get_all"):
                all_patterns = self._pattern_store.get_all()
                for p in all_patterns:
                    cond = getattr(p, "condition", None)
                    if cond is None:
                        continue
                    if opportunity_type and getattr(cond, "opportunity_type", "") != opportunity_type:
                        continue
                    if action_type and getattr(cond, "action_type", "") != action_type:
                        continue
                    return getattr(p, "performance", None)

        except Exception:
            pass

        return None

    # ═══════════════════════════════════════════════════════════
    # 警告生成
    # ═══════════════════════════════════════════════════════════

    def _generate_warnings(self, pred: DecisionValuePrediction) -> None:
        """生成预测警告."""
        if pred.sample_size < self.MIN_SAMPLES_PREDICT:
            pred.warnings.append(
                f"Only {pred.sample_size} samples (min {self.MIN_SAMPLES_PREDICT}) — "
                f"prediction unreliable."
            )
        if pred.decay_risk >= 0.5:
            pred.warnings.append(
                f"High decay risk ({pred.decay_risk:.2f}) — "
                f"strategy value is declining."
            )
        if pred.avg_reward < 0:
            pred.warnings.append(
                f"Negative average reward ({pred.avg_reward:.2f}) — "
                f"this strategy has historically lost value."
            )
        if pred.scalability_score < 0.3:
            pred.warnings.append(
                f"Low scalability ({pred.scalability_score:.2f}) — "
                f"limited evidence this strategy can scale."
            )
        if pred.success_probability < 0.3 and pred.sample_size >= self.MIN_SAMPLES_PREDICT:
            pred.warnings.append(
                f"Low success probability ({pred.success_probability:.0%}) — "
                f"high risk of failure."
            )

    # ═══════════════════════════════════════════════════════════
    # 工具
    # ═══════════════════════════════════════════════════════════

    def is_worth_executing(
        self,
        prediction: DecisionValuePrediction,
        min_utility: float = 0.3,
    ) -> bool:
        """判断是否值得执行."""
        return prediction.decision_utility >= min_utility

    def __repr__(self) -> str:
        return (
            f"DecisionValuePredictor("
            f"sync={'yes' if self._decision_sync else 'no'}, "
            f"patterns={'yes' if self._pattern_store else 'no'}, "
            f"horizon={self._horizon_days}d)"
        )


__all__ = [
    "DecisionValuePrediction",
    "DecisionValuePredictor",
]