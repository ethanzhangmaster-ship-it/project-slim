"""E12.7.2 — Reasoning Engine。

Agent 推理引擎 —— 从观察中诊断根因。

职责:
  1. 分析 GrowthObservation
  2. 匹配已知原因模式
  3. 排序根因（按置信度）
  4. 输出 RootCause 列表
"""

from __future__ import annotations

from typing import Any

from .models import (
    GrowthObservation,
    ObservationSeverity,
    RootCause,
)


# 根因规则
# 格式: (信号条件, 类别, 描述模板, 基础置信度, 建议修复)
_CAUSE_RULES: list[dict[str, Any]] = [
    {
        "condition": lambda o: o.creative_state.is_fatigued,
        "category": "creative_fatigue",
        "description": "Creative assets are saturated; audience has seen them too many times",
        "base_confidence": 0.85,
        "suggested_fix": "Generate new creative variants with fresh hooks and visuals",
        "evidence_signals": ["creative_fatigued", "creative_highly_fatigued"],
    },
    {
        "condition": lambda o: o.creative_state.diversity_score < 0.30,
        "category": "creative_diversity_low",
        "description": "Creative portfolio lacks diversity; too many similar variants",
        "base_confidence": 0.75,
        "suggested_fix": "Expand creative diversity with new DNA combinations and audiences",
        "evidence_signals": ["creative_diversity_low"],
    },
    {
        "condition": lambda o: o.creative_state.winner_ratio < 0.10 and o.creative_state.total_creatives > 10,
        "category": "winner_scarcity",
        "description": "Too few winning creatives; need to find more high-performers",
        "base_confidence": 0.70,
        "suggested_fix": "Increase experiment volume and test new creative directions",
        "evidence_signals": ["winner_ratio_low"],
    },
    {
        "condition": lambda o: o.metrics.roas < 0.80,
        "category": "roas_decline",
        "description": "ROAS has dropped below target; revenue efficiency is declining",
        "base_confidence": 0.80,
        "suggested_fix": "Audit creative performance, adjust budget allocation, optimize targeting",
        "evidence_signals": ["roas_warning", "roas_critical"],
    },
    {
        "condition": lambda o: o.metrics.roas < 0.50,
        "category": "roas_critical",
        "description": "ROAS critically low; immediate action required",
        "base_confidence": 0.90,
        "suggested_fix": "Pause underperforming campaigns, reduce budget, emergency creative refresh",
        "evidence_signals": ["roas_critical"],
    },
    {
        "condition": lambda o: o.metrics.ctr < 0.01,
        "category": "ctr_decline",
        "description": "Click-through rate is too low; creative hooks are not engaging",
        "base_confidence": 0.75,
        "suggested_fix": "Test new hook strategies, optimize first 3 seconds of creative",
        "evidence_signals": ["ctr_low"],
    },
    {
        "condition": lambda o: o.metrics.cpi > 5.0,
        "category": "cpi_inflation",
        "description": "Cost per install is rising; audience acquisition cost increasing",
        "base_confidence": 0.70,
        "suggested_fix": "Explore new audience segments, optimize creative for lower CPI",
        "evidence_signals": ["cpi_high"],
    },
    {
        "condition": lambda o: o.market_state.is_declining,
        "category": "market_decline",
        "description": "Market is declining; overall demand is shrinking",
        "base_confidence": 0.65,
        "suggested_fix": "Evaluate product lifecycle, consider sunset or pivot strategy",
        "evidence_signals": ["market_declining"],
    },
    {
        "condition": lambda o: o.market_state.is_highly_competitive,
        "category": "high_competition",
        "description": "Market competition is intense; CPI may rise and ROAS may drop",
        "base_confidence": 0.60,
        "suggested_fix": "Differentiate creative strategy, find niche audiences, optimize LTV",
        "evidence_signals": ["market_highly_competitive"],
    },
    {
        "condition": lambda o: (
            o.creative_state.is_fatigued
            and o.metrics.roas < 0.80
        ),
        "category": "combined_fatigue_roas",
        "description": "Creative fatigue is driving ROAS decline; need fresh creatives urgently",
        "base_confidence": 0.88,
        "suggested_fix": "Immediate creative refresh + budget reallocation to winning formats",
        "evidence_signals": ["creative_fatigued", "roas_warning"],
    },
]


class ReasoningEngine:
    """Agent 推理引擎。

    分析观察数据，诊断根因。
    """

    def __init__(self) -> None:
        self._rules = list(_CAUSE_RULES)
        self._diagnosis_history: list[dict[str, Any]] = []

    def analyze(
        self, observation: GrowthObservation
    ) -> list[RootCause]:
        """分析观察，诊断根因。

        Args:
            observation: 增长观察

        Returns:
            根因列表（按置信度降序）
        """
        causes: list[RootCause] = []

        for rule in self._rules:
            try:
                if rule["condition"](observation):
                    confidence = self._calculate_confidence(
                        observation, rule["base_confidence"], rule["evidence_signals"]
                    )
                    severity = self._map_severity(rule["category"])

                    cause = RootCause(
                        category=rule["category"],
                        description=rule["description"],
                        confidence=round(confidence, 4),
                        evidence=self._gather_evidence(observation, rule["evidence_signals"]),
                        severity=severity,
                        suggested_fix=rule["suggested_fix"],
                    )
                    causes.append(cause)
            except Exception:
                continue

        # 按置信度降序排序
        causes.sort(key=lambda c: c.confidence, reverse=True)

        # 记录诊断
        self._diagnosis_history.append({
            "observation_id": observation.observation_id,
            "product_id": observation.product_id,
            "cause_count": len(causes),
            "top_cause": causes[0].category if causes else "none",
            "top_confidence": causes[0].confidence if causes else 0.0,
        })

        return causes

    def get_top_cause(
        self, observation: GrowthObservation
    ) -> RootCause | None:
        """获取最高置信度根因。"""
        causes = self.analyze(observation)
        return causes[0] if causes else None

    def get_causes_by_category(
        self, observation: GrowthObservation
    ) -> dict[str, list[RootCause]]:
        """按类别分组根因。"""
        causes = self.analyze(observation)
        result: dict[str, list[RootCause]] = {}
        for c in causes:
            result.setdefault(c.category, []).append(c)
        return result

    def _calculate_confidence(
        self,
        observation: GrowthObservation,
        base_confidence: float,
        evidence_signals: list[str],
    ) -> float:
        """计算调整后置信度。

        基于实际信号匹配度调整基础置信度。
        """
        # 证据匹配度
        match_count = sum(
            1 for s in evidence_signals if s in observation.signals
        )
        match_ratio = match_count / len(evidence_signals) if evidence_signals else 1.0

        # 严重程度加成
        severity_boost = 0.0
        if observation.severity == ObservationSeverity.CRITICAL:
            severity_boost = 0.05
        elif observation.severity == ObservationSeverity.FATAL:
            severity_boost = 0.10

        confidence = base_confidence * match_ratio + severity_boost
        return min(1.0, max(0.0, confidence))

    def _gather_evidence(
        self,
        observation: GrowthObservation,
        evidence_signals: list[str],
    ) -> list[str]:
        """收集证据。"""
        evidence: list[str] = []
        for signal in evidence_signals:
            if signal in observation.signals:
                evidence.append(f"Signal detected: {signal}")

        # 添加具体指标证据
        if observation.metrics.roas < 0.80:
            evidence.append(f"ROAS={observation.metrics.roas:.2f}")
        if observation.creative_state.is_fatigued:
            evidence.append(f"Fatigue={observation.creative_state.fatigue_score:.2f}")
        if observation.metrics.ctr < 0.01:
            evidence.append(f"CTR={observation.metrics.ctr:.4f}")

        return evidence

    def _map_severity(self, category: str) -> ObservationSeverity:
        """映射根因类别到严重程度。"""
        critical_categories = {"roas_critical", "combined_fatigue_roas"}
        if category in critical_categories:
            return ObservationSeverity.CRITICAL
        return ObservationSeverity.WARNING

    def add_rule(self, rule: dict[str, Any]) -> None:
        """添加自定义根因规则。"""
        self._rules.append(rule)

    def get_diagnosis_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取诊断历史。"""
        return self._diagnosis_history[-limit:]

    def clear_history(self) -> None:
        """清除诊断历史。"""
        self._diagnosis_history.clear()

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"ReasoningEngine(rules={self.rule_count})"