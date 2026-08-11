"""E17.8 — 模拟先验：E17.3 静态基线 + E17.7 记忆图谱先验的混合。

复用不重写：
- 静态基线走 E17.3 `OpportunitySimulator.simulate()` 公开接口（_BASE 表不复制）
- 记忆先验走 E17.7 `extract_patterns` / `confidence_boost_for`：
  - confidence += boost（≥2 样本才启用，公式与 E17.2/E17.3/E17.7 完全对齐）
  - risk -= boost / 2（历史成功 → 风险打折，下限 0.10）
  - expected_revenue_change 与 avg_revenue_delta 各半混合
    （实得收入变化把「拍脑袋基线」拉向「真实世界」）

确定性规则，无 LLM。opportunity_type 从 decision.opportunity_id
（格式 game_id:type，与 E17.4 strategy_type_from_decision 同款解析）取得。
"""
from __future__ import annotations

from typing import Optional

from src.ceo_intelligence.decision_engine.simulator import OpportunitySimulator

from .models import SimulationPrior

_MIN_SAMPLES = 2       # 与 E17.7 patterns._MIN_SAMPLES 对齐
_MEMORY_WEIGHT = 0.5   # 记忆实得均值与静态基线各半混合
_RISK_FLOOR = 0.10     # 与 E17.3 simulator 风险下限对齐
_CONF_CAP = 0.99


def opportunity_type_of(opportunity_id: str) -> str:
    """decision.opportunity_id（game_id:type）→ 机会类型。"""
    return opportunity_id.rsplit(":", 1)[-1]


def get_prior(
    opportunity_type: str,
    graph=None,
    *,
    domain: Optional[str] = None,
    action_type: Optional[str] = None,
    simulator: Optional[OpportunitySimulator] = None,
) -> SimulationPrior:
    """机会类型（+ 可选 E17.7 图谱）→ 模拟先验。

    graph 为 None 或无足量样本时退化为纯静态基线（source="static"）。
    """
    sim = simulator or OpportunitySimulator()
    base = sim.simulate(opportunity_type)

    prior = SimulationPrior(
        opportunity_type=opportunity_type,
        expected_revenue_change=base.expected_revenue_change,
        expected_roas_change=base.expected_roas_change,
        confidence=base.confidence,
        risk=base.risk,
        source="static",
    )
    if graph is None:
        return prior

    from src.ceo_intelligence.growth_memory_graph.patterns import (
        confidence_boost_for,
        extract_patterns,
    )

    # strategy_type 与 opportunity_type 同值（E17.4 直接从 opportunity_id 解析）
    boost = confidence_boost_for(
        graph, opportunity_type, domain=domain, action_type=action_type
    )
    matched = [
        p for p in extract_patterns(graph)
        if p.strategy_type == opportunity_type
        and (domain is None or p.domain == domain)
        and (action_type is None or p.action_type == action_type)
    ]
    samples = sum(p.samples for p in matched)
    if samples < _MIN_SAMPLES:
        return prior

    # 实得收入变化（record_outcome 回填）：按样本数加权
    delta_samples = sum(p.samples for p in matched if p.avg_revenue_delta != 0.0)
    avg_delta = (
        sum(p.avg_revenue_delta * p.samples for p in matched) / delta_samples
        if delta_samples
        else 0.0
    )

    rev = prior.expected_revenue_change
    if delta_samples:
        rev = (1 - _MEMORY_WEIGHT) * rev + _MEMORY_WEIGHT * avg_delta

    return SimulationPrior(
        opportunity_type=opportunity_type,
        expected_revenue_change=round(rev, 6),
        expected_roas_change=prior.expected_roas_change,
        confidence=round(min(_CONF_CAP, prior.confidence + boost), 6),
        risk=round(max(_RISK_FLOOR, prior.risk - boost / 2), 6),
        memory_boost=round(boost, 6),
        avg_revenue_delta=round(avg_delta, 6),
        samples=samples,
        source="static+memory",
    )


__all__ = ["get_prior", "opportunity_type_of"]
