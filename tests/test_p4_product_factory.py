"""P4.3 ProductFactory 单元测试 — 产品组合生命周期与确定性晋升门禁.

测试覆盖:
  1. ProductStage 枚举
  2. ProductGate 默认值与自定义
  3. ProductAsset 默认状态
  4. IDEA → PROTOTYPE 晋升
  5. PROTOTYPE → MARKET_TEST (build_passed) / RETIRED (build failed)
  6. MARKET_TEST → LIVE (gates passed) / RETIRED (gates failed)
  7. MARKET_TEST 样本不足不晋升
  8. RETIRED 终态不可变
  9. history 轨迹记录
  10. 自定义 gate 阈值
"""
from __future__ import annotations

import pytest

from src.autonomous_growth.product_factory import (
    ProductAsset,
    ProductFactory,
    ProductGate,
    ProductStage,
)


# ═══════════════════════════════════════════════════════════════
# 1. ProductStage 枚举
# ═══════════════════════════════════════════════════════════════


class TestProductStage:
    """ProductStage 枚举."""

    def test_all_stages_present(self):
        """5 个阶段全部存在."""
        assert len(ProductStage) == 5

    def test_stage_values(self):
        """阶段值正确."""
        assert ProductStage.IDEA.value == "idea"
        assert ProductStage.PROTOTYPE.value == "prototype"
        assert ProductStage.MARKET_TEST.value == "market_test"
        assert ProductStage.LIVE.value == "live"
        assert ProductStage.RETIRED.value == "retired"

    def test_stage_is_string_enum(self):
        """ProductStage 是 str Enum."""
        assert isinstance(ProductStage.IDEA, str)


# ═══════════════════════════════════════════════════════════════
# 2. ProductGate
# ═══════════════════════════════════════════════════════════════


class TestProductGate:
    """ProductGate 配置."""

    def test_default_gate(self):
        """默认 gate 阈值."""
        gate = ProductGate()
        assert gate.max_cpi == 1.0
        assert gate.min_d1_retention == 0.25
        assert gate.min_roas == 0.8
        assert gate.min_installs == 100

    def test_custom_gate(self):
        """自定义 gate 阈值."""
        gate = ProductGate(max_cpi=2.0, min_d1_retention=0.30, min_roas=1.0, min_installs=200)
        assert gate.max_cpi == 2.0
        assert gate.min_d1_retention == 0.30
        assert gate.min_roas == 1.0
        assert gate.min_installs == 200


# ═══════════════════════════════════════════════════════════════
# 3. ProductAsset
# ═══════════════════════════════════════════════════════════════


class TestProductAsset:
    """ProductAsset 数据结构."""

    def test_default_values(self):
        """默认值."""
        asset = ProductAsset(product_id="p1")
        assert asset.stage == ProductStage.IDEA
        assert asset.metrics == {}
        assert asset.history == []
        assert asset.reason == ""

    def test_custom_metrics(self):
        """自定义 metrics."""
        asset = ProductAsset(
            product_id="p1",
            stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        assert asset.metrics["cpi"] == 0.8
        assert asset.stage == ProductStage.MARKET_TEST


# ═══════════════════════════════════════════════════════════════
# 4. IDEA → PROTOTYPE
# ═══════════════════════════════════════════════════════════════


class TestIdeaToPrototype:
    """IDEA → PROTOTYPE 晋升."""

    def test_idea_advances_to_prototype(self):
        """IDEA 无条件晋升到 PROTOTYPE."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.IDEA)
        result = factory.advance(asset)
        assert result.stage == ProductStage.PROTOTYPE
        assert "idea accepted for prototype" in result.reason

    def test_history_records_transition(self):
        """history 记录转换."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.IDEA)
        factory.advance(asset)
        assert len(asset.history) == 1
        assert "idea->prototype" in asset.history[0]


# ═══════════════════════════════════════════════════════════════
# 5. PROTOTYPE → MARKET_TEST / RETIRED
# ═══════════════════════════════════════════════════════════════


class TestPrototypeTransition:
    """PROTOTYPE 阶段转换."""

    def test_prototype_with_build_passed_advances(self):
        """build_passed=True 晋升到 MARKET_TEST."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.PROTOTYPE,
            metrics={"build_passed": 1},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.MARKET_TEST
        assert "prototype build passed" in result.reason

    def test_prototype_with_build_failed_retires(self):
        """build_passed=0 退役."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.PROTOTYPE,
            metrics={"build_passed": 0},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED
        assert "prototype build failed" in result.reason

    def test_prototype_without_build_metric_retires(self):
        """无 build_passed metric 视为失败."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.PROTOTYPE, metrics={})
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED


# ═══════════════════════════════════════════════════════════════
# 6. MARKET_TEST → LIVE / RETIRED
# ═══════════════════════════════════════════════════════════════


class TestMarketTestGates:
    """MARKET_TEST 阶段 KPI 门禁."""

    def test_all_gates_passed_advances_to_live(self):
        """所有 KPI 达标晋升到 LIVE."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.LIVE
        assert "market gates passed" in result.reason

    def test_cpi_too_high_retires(self):
        """CPI 超标退役."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 1.5, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED

    def test_d1_retention_too_low_retires(self):
        """D1 留存不达标退役."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.20, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED

    def test_roas_too_low_retires(self):
        """ROAS 不达标退役."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.5, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED

    def test_boundary_values_pass(self):
        """边界值 (恰好等于阈值) 通过."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 1.0, "d1_retention": 0.25, "roas": 0.8, "installs": 100},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.LIVE


# ═══════════════════════════════════════════════════════════════
# 7. MARKET_TEST 样本不足
# ═══════════════════════════════════════════════════════════════


class TestInsufficientSample:
    """MARKET_TEST 样本不足."""

    def test_insufficient_installs_no_advance(self):
        """installs < min_installs 不晋升."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 50},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.MARKET_TEST
        assert "insufficient market-test sample" in result.reason

    def test_zero_installs_no_advance(self):
        """0 installs 不晋升."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 0},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.MARKET_TEST


# ═══════════════════════════════════════════════════════════════
# 8. RETIRED 终态
# ═══════════════════════════════════════════════════════════════


class TestRetiredTerminal:
    """RETIRED 终态不可变."""

    def test_retired_stays_retired(self):
        """RETIRED 不再变化."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.RETIRED)
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED
        assert result.history == []  # 不记录任何转换

    def test_retired_with_metrics_stays_retired(self):
        """RETIRED 即使有 metrics 也不变."""
        factory = ProductFactory()
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.RETIRED,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED


# ═══════════════════════════════════════════════════════════════
# 9. history 轨迹
# ═══════════════════════════════════════════════════════════════


class TestHistoryTrail:
    """history 轨迹记录."""

    def test_full_lifecycle_history(self):
        """完整成功生命周期 history."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.IDEA)
        factory.advance(asset)  # IDEA → PROTOTYPE
        asset.metrics = {"build_passed": 1}
        factory.advance(asset)  # PROTOTYPE → MARKET_TEST
        asset.metrics = {"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150}
        factory.advance(asset)  # MARKET_TEST → LIVE
        assert len(asset.history) == 3
        assert "idea->prototype" in asset.history[0]
        assert "prototype->market_test" in asset.history[1]
        assert "market_test->live" in asset.history[2]

    def test_retired_lifecycle_history(self):
        """退役生命周期 history."""
        factory = ProductFactory()
        asset = ProductAsset(product_id="p1", stage=ProductStage.IDEA)
        factory.advance(asset)  # IDEA → PROTOTYPE
        asset.metrics = {"build_passed": 0}
        factory.advance(asset)  # PROTOTYPE → RETIRED
        assert len(asset.history) == 2
        assert "prototype->retired" in asset.history[1]


# ═══════════════════════════════════════════════════════════════
# 10. 自定义 gate 阈值
# ═══════════════════════════════════════════════════════════════


class TestCustomGate:
    """自定义 gate 阈值."""

    def test_strict_gate_rejects_marginal_product(self):
        """严格 gate 拒绝边缘产品 (installs 满足但 KPI 不达标)."""
        strict_gate = ProductGate(max_cpi=0.5, min_d1_retention=0.35, min_roas=1.0, min_installs=100)
        factory = ProductFactory(gate=strict_gate)
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.RETIRED

    def test_loose_gate_accepts_marginal_product(self):
        """宽松 gate 接受边缘产品."""
        loose_gate = ProductGate(max_cpi=2.0, min_d1_retention=0.15, min_roas=0.5, min_installs=50)
        factory = ProductFactory(gate=loose_gate)
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.LIVE

    def test_custom_min_installs_threshold(self):
        """自定义 min_installs 阈值."""
        gate = ProductGate(min_installs=200)
        factory = ProductFactory(gate=gate)
        asset = ProductAsset(
            product_id="p1", stage=ProductStage.MARKET_TEST,
            metrics={"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        )
        result = factory.advance(asset)
        assert result.stage == ProductStage.MARKET_TEST  # 150 < 200 不晋升
