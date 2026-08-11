"""
P3.5.2 — Advisor 加权消费测试（防自我强化，契约冻结点 5/8）。

核心断言：
- CEO_DECISION 自生成经验按来源带权（realized=0.5 / simulated=0.2）并入
  historical_success_rate（加权平均），绝不等于自报成功率的 1.0；
- Knowledge Source Isolation：10 执行失败 + 10 CEO 自报成功 → weighted_sr ≈ 0.344，
  触发 low_historical_success 风险标记（防止自嗨）；
- 加权有效样本用于 confidence（自生成证据打折 → confidence 低于等量外部证据）；
- 知识建议被证伪（knowledge_used 有风险 + 结果失败）→ knowledge_advice_failed。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from .helpers import (
    build_advisor,
    build_kg_ceo_simulated,
    build_kg_ceo_success,
    build_kg_external_success,
    build_kg_isolation,
    build_kg_strategy_ceo_failed,
)


def test_no_ceo_records_unchanged_behavior():
    """无 CEO_DECISION 时行为与 P3.5.1 一致（零回归）：高成功率、无风险。"""
    kg = build_kg_external_success()
    sig = build_advisor(kg).advise_portfolio("game_a")
    assert sig.historical_success_rate > 0.8
    assert sig.risk_flags == []


def test_ceo_self_reports_discounted_vs_external():
    """同量证据：CEO 自报（w=0.5）置信严格低于外部执行结果（w=1.0）。"""
    ext_sig = build_advisor(build_kg_external_success()).advise_portfolio("game_a")
    ceo_sig = build_advisor(build_kg_ceo_success()).advise_portfolio("game_a")
    # 外部证据：共享策略(1) + 10 次执行成功(10) → 有效 11 → 置信 11/14≈0.786
    assert ext_sig.confidence == pytest.approx(11 / 14, abs=1e-3)
    # CEO 自报：共享策略(1) + 10 条 × 0.5 → 有效 6 → 置信 6/9≈0.667 < 外部
    assert ceo_sig.confidence == pytest.approx(6 / 9, abs=1e-3)
    assert ceo_sig.confidence < ext_sig.confidence


def test_knowledge_source_isolation():
    """10 执行失败 + 10 CEO 自报成功：加权 sr≈0.344（非 1.0/0.5），并触发风险。"""
    kg = build_kg_isolation()
    sig = build_advisor(kg).advise_portfolio("game_a")
    assert sig.historical_success_rate == pytest.approx(5.5 / 16, abs=1e-3)
    assert "low_historical_success" in sig.risk_flags
    # 不可能是 1.0（自嗨），也不可能是朴素 0.5（CEO 与外部同权）
    assert sig.historical_success_rate < 0.5


def test_ceo_simulated_weakest_weight():
    """模拟结果权重最弱（w=0.2）：10 模拟成功 + 10 执行失败 → sr≈0.167。"""
    kg = build_kg_ceo_simulated()
    sig = build_advisor(kg).advise_portfolio("game_a")
    assert sig.historical_success_rate == pytest.approx(2.5 / 13, abs=1e-3)


def test_strategy_advice_failed_flag():
    """知识建议（带风险标记）被证伪 → knowledge_advice_failed 风险标记。"""
    proposal = SimpleNamespace(
        current_strategy="aggressive_scale",
        proposed_change="increase budget 30%",
        expected_impact="retention uplift",
        confidence=0.82,
    )
    sig = build_advisor(build_kg_strategy_ceo_failed()).advise_strategy(
        proposal, game_id="game_a"
    )
    assert "knowledge_advice_failed" in sig.risk_flags
    assert sig.historical_success_rate == pytest.approx(0.1, abs=1e-3)
    # 模拟证据（w=0.2）→ 有效 0.2 → 置信 0.2/3.2≈0.0625
    assert sig.confidence == pytest.approx(0.2 / 3.2, abs=1e-3)


def test_advisor_real_api_called_false():
    assert build_advisor(build_kg_isolation()).real_api_called is False
