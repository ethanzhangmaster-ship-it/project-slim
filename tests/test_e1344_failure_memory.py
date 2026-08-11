"""E13.4.4 Growth Failure Memory — 测试套件.

测试覆盖:
  - FailureSeverity / FailureCategory 枚举
  - FailureCondition: 创建、匹配、序列化
  - FailurePattern: 创建、置信度、严重程度、显著性、阻止级、序列化
  - FailureWarning: 创建、序列化
  - FailureQuery / FailureStats: 模型
  - FailureMemory: extract、store、query、check_action、check_strategy
  - FailureMemory: compute_risk_score、get_blocking_warnings
  - FailureMemory: 统计、去重更新、边界条件
  - 集成场景: 经验→失败模式→警告→风险评分闭环
"""

from __future__ import annotations

import pytest
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_context(
    product_id: str = "p001",
    date: str = "2026-07-24",
    opportunity_type: str = "creative_scale",
    action_type: str = "increase_budget",
    entity_id: str = "c001",
    audience_segment: str = "",
    trigger_signals: list[str] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
    return ExperienceContext(
        product_id=product_id,
        date=date,
        opportunity_type=opportunity_type,
        action_type=action_type,
        entity_id=entity_id,
        audience_segment=audience_segment,
        trigger_signals=trigger_signals or [],
        **kwargs,
    )


def _make_outcome(
    success: bool = True,
    actual_reward: float = 0.85,
    metrics_delta: dict[str, float] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceOutcome, ExperienceOutcomeLevel,
    )
    outcome_level = ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE
    return ExperienceOutcome(
        success=success,
        outcome_level=outcome_level,
        actual_reward=actual_reward,
        metrics_delta=metrics_delta or {},
        **kwargs,
    )


def _make_experience(
    action_type: str = "increase_budget",
    opportunity_type: str = "creative_scale",
    entity_id: str = "c001",
    reward: float = 0.85,
    success: bool = True,
    audience_segment: str = "",
    trigger_signals: list[str] | None = None,
    product_id: str = "p001",
    timestamp: str = "2026-07-24T10:00:00+00:00",
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import GrowthExperience
    ctx = _make_context(
        product_id=product_id,
        opportunity_type=opportunity_type,
        action_type=action_type,
        entity_id=entity_id,
        audience_segment=audience_segment,
        trigger_signals=trigger_signals or [],
    )
    return GrowthExperience(
        context=ctx,
        action_type=action_type,
        action_params={"test": True},
        outcome=_make_outcome(success=success, actual_reward=reward),
        reward=reward,
        timestamp=timestamp,
        **kwargs,
    )


def _make_failure_pattern(
    name: str = "Test Failure",
    action_type: str = "increase_budget",
    opportunity_type: str = "creative_scale",
    audience_segment: str = "",
    product_category: str = "p001",
    failure_rate: float = 0.8,
    total_attempts: int = 10,
    avg_loss: float = 500.0,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
        FailurePattern, FailureCondition, FailureSeverity,
    )
    cond = FailureCondition(
        action_type=action_type,
        opportunity_type=opportunity_type,
        audience_segment=audience_segment,
        product_category=product_category,
    )
    fp = FailurePattern(
        name=name,
        condition=cond,
        blocked_action=action_type,
        failure_rate=failure_rate,
        total_attempts=total_attempts,
        failed_attempts=int(total_attempts * failure_rate),
        avg_loss=avg_loss,
        severity=FailureSeverity.HIGH,
        **kwargs,
    )
    fp.compute_confidence()
    fp.compute_severity()
    return fp


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestFailureSeverity:
    """FailureSeverity 枚举."""

    def test_severities_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureSeverity
        assert FailureSeverity.CRITICAL.value == "critical"
        assert FailureSeverity.HIGH.value == "high"
        assert FailureSeverity.MEDIUM.value == "medium"
        assert FailureSeverity.LOW.value == "low"
        assert FailureSeverity.NEGLIGIBLE.value == "negligible"


class TestFailureCategory:
    """FailureCategory 枚举."""

    def test_categories_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCategory
        assert FailureCategory.BUDGET_WASTE.value == "budget_waste"
        assert FailureCategory.CREATIVE_BACKFIRE.value == "creative_backfire"
        assert FailureCategory.ROAS_COLLAPSE.value == "roas_collapse"
        assert FailureCategory.AUDIENCE_MISMATCH.value == "audience_mismatch"
        assert FailureCategory.SCALE_TOO_FAST.value == "scale_too_fast"
        assert FailureCategory.GENERAL.value == "general"


# ═══════════════════════════════════════════════════════════════
# Test: FailureCondition
# ═══════════════════════════════════════════════════════════════

class TestFailureCondition:
    """FailureCondition 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition()
        assert fc.scenario == ""
        assert fc.action_type == ""
        assert fc.opportunity_type == ""

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(
            scenario="Low ROAS",
            opportunity_type="roas_drop",
            signal_types=["ROAS_DROP"],
            metrics_conditions={"roas": ("<", 0.2)},
            audience_segment="female_25_35",
            product_category="merge",
            action_type="increase_budget",
        )
        assert fc.scenario == "Low ROAS"
        assert fc.action_type == "increase_budget"
        assert fc.opportunity_type == "roas_drop"
        assert fc.metrics_conditions == {"roas": ("<", 0.2)}

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(
            action_type="increase_budget",
            opportunity_type="roas_drop",
            metrics_conditions={"roas": ("<", 0.2)},
        )
        d = fc.to_dict()
        assert d["action_type"] == "increase_budget"
        assert d["metrics_conditions"] == {"roas": ["<", 0.2]}

    def test_matches_exact(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(action_type="increase_budget", opportunity_type="roas_drop")
        assert fc.matches(action_type="increase_budget", opportunity_type="roas_drop") is True

    def test_matches_wrong_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(action_type="increase_budget")
        assert fc.matches(action_type="scale_winner") is False

    def test_matches_empty_condition(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition()
        assert fc.matches(action_type="increase_budget") is True

    def test_matches_with_signals(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(signal_types=["ROAS_DROP", "BUDGET_WASTE"])
        assert fc.matches(signal_types=["ROAS_DROP"]) is True
        assert fc.matches(signal_types=["UNKNOWN"]) is False

    def test_matches_with_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(audience_segment="female_25_35")
        assert fc.matches(audience_segment="female_25_35") is True
        assert fc.matches(audience_segment="male_18_24") is False

    def test_matches_with_product(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCondition
        fc = FailureCondition(product_category="merge")
        assert fc.matches(product_category="merge") is True
        assert fc.matches(product_category="puzzle") is False


# ═══════════════════════════════════════════════════════════════
# Test: FailurePattern
# ═══════════════════════════════════════════════════════════════

class TestFailurePattern:
    """FailurePattern 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern()
        assert fp.failure_id != ""
        assert fp.failure_rate == 0.0
        assert fp.severity == FailureSeverity.NEGLIGIBLE

    def test_compute_confidence(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fp = FailurePattern(failure_rate=0.8, total_attempts=50)
        confidence = fp.compute_confidence()
        assert confidence > 0
        assert confidence <= 0.8

    def test_compute_confidence_zero_attempts(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fp = FailurePattern(failure_rate=0.8, total_attempts=0)
        assert fp.compute_confidence() == 0.0

    def test_compute_severity_critical(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(failure_rate=0.95, total_attempts=20)
        fp.compute_severity()
        assert fp.severity == FailureSeverity.CRITICAL

    def test_compute_severity_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(failure_rate=0.75, total_attempts=10)
        fp.compute_severity()
        assert fp.severity == FailureSeverity.HIGH

    def test_compute_severity_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(failure_rate=0.6, total_attempts=10)
        fp.compute_severity()
        assert fp.severity == FailureSeverity.MEDIUM

    def test_compute_severity_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(failure_rate=0.4, total_attempts=10)
        fp.compute_severity()
        assert fp.severity == FailureSeverity.LOW

    def test_compute_severity_negligible_low_attempts(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(failure_rate=0.95, total_attempts=2)  # 样本不足
        fp.compute_severity()
        assert fp.severity == FailureSeverity.NEGLIGIBLE

    def test_is_significant(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fp = FailurePattern(failure_rate=0.7, total_attempts=10)
        assert fp.is_significant() is True

    def test_is_not_significant_low_attempts(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fp = FailurePattern(failure_rate=0.9, total_attempts=2)
        assert fp.is_significant() is False

    def test_is_not_significant_low_failure_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fp = FailurePattern(failure_rate=0.3, total_attempts=10)
        assert fp.is_significant() is False

    def test_is_blocking(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(severity=FailureSeverity.CRITICAL)
        assert fp.is_blocking() is True
        fp2 = FailurePattern(severity=FailureSeverity.HIGH)
        assert fp2.is_blocking() is True

    def test_is_not_blocking(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureSeverity,
        )
        fp = FailurePattern(severity=FailureSeverity.MEDIUM)
        assert fp.is_blocking() is False

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailurePattern, FailureCondition, FailureSeverity,
        )
        fp = FailurePattern(
            name="Test",
            condition=FailureCondition(action_type="increase_budget"),
            blocked_action="increase_budget",
            failure_rate=0.8,
            total_attempts=10,
            severity=FailureSeverity.HIGH,
        )
        d = fp.to_dict()
        assert d["name"] == "Test"
        assert d["failure_rate"] == 0.8
        assert d["severity"] == "high"

    def test_unique_failure_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        ids = {FailurePattern().failure_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: FailureWarning
# ═══════════════════════════════════════════════════════════════

class TestFailureWarning:
    """FailureWarning 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailureWarning, FailureSeverity,
        )
        fw = FailureWarning()
        assert fw.warning_id != ""
        assert fw.risk_score == 0.0
        assert fw.severity == FailureSeverity.NEGLIGIBLE
        assert fw.requires_approval is False

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailureWarning, FailureSeverity,
        )
        fw = FailureWarning(
            pattern_id="fp_001",
            pattern_name="Avoid X",
            action_type="increase_budget",
            risk_score=0.72,
            failure_rate=0.8,
            expected_loss=500.0,
            severity=FailureSeverity.HIGH,
            suggestion="Do not increase budget",
            requires_approval=True,
            context_summary="roas_drop, female",
        )
        assert fw.risk_score == 0.72
        assert fw.requires_approval is True

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
            FailureWarning, FailureSeverity,
        )
        fw = FailureWarning(
            pattern_id="fp_001",
            action_type="increase_budget",
            risk_score=0.5,
            severity=FailureSeverity.HIGH,
            requires_approval=True,
        )
        d = fw.to_dict()
        assert d["risk_score"] == 0.5
        assert d["requires_approval"] is True


# ═══════════════════════════════════════════════════════════════
# Test: FailureQuery / FailureStats
# ═══════════════════════════════════════════════════════════════

class TestFailureQuery:
    """FailureQuery 模型."""

    def test_default_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        q = FailureQuery()
        assert q.limit == 100
        assert q.sort_by == "failure_rate"
        assert q.sort_desc is True

    def test_filtered_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        q = FailureQuery(
            action_types=["increase_budget"],
            blocking_only=True,
            min_failure_rate=0.7,
            limit=10,
        )
        assert q.action_types == ["increase_budget"]
        assert q.blocking_only is True


class TestFailureStats:
    """FailureStats 模型."""

    def test_default_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureStats
        s = FailureStats()
        assert s.total_patterns == 0
        assert s.avg_failure_rate == 0.0

    def test_populated_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureStats
        s = FailureStats(
            total_patterns=10,
            total_significant=6,
            total_blocking=3,
            avg_failure_rate=0.65,
            avg_loss=500.0,
            total_avoided_loss=5000.0,
        )
        assert s.total_patterns == 10
        assert s.total_blocking == 3
        assert s.total_avoided_loss == 5000.0

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureStats
        s = FailureStats(total_patterns=5, total_blocking=2)
        d = s.to_dict()
        assert d["total_patterns"] == 5
        assert d["total_blocking"] == 2


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Extract
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryExtract:
    """FailureMemory 提取功能."""

    def test_extract_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())
        patterns = fm.extract()
        assert patterns == []

    def test_extract_no_failures(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        for i in range(5):
            store.store(_make_experience(
                action_type="increase_budget", entity_id=f"c{i:03d}",
                success=True, reward=0.8,
            ))
        fm = FailureMemory(store)
        patterns = fm.extract()
        assert patterns == []

    def test_extract_single_failure_group(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        # 8 次失败 + 2 次成功 = 80% 失败率
        for i in range(8):
            store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="roas_drop",
                entity_id=f"c{i:03d}",
                success=False, reward=-200,
            ))
        for i in range(8, 10):
            store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="roas_drop",
                entity_id=f"c{i:03d}",
                success=True, reward=0.5,
            ))

        fm = FailureMemory(store)
        patterns = fm.extract()
        assert len(patterns) == 1
        assert patterns[0].blocked_action == "increase_budget"
        assert patterns[0].failure_rate == 0.8
        assert patterns[0].total_attempts == 10

    def test_extract_multiple_failure_groups(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        # 动作A: increase_budget, 高失败率
        for i in range(7):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="roas_drop",
                entity_id=f"ca{i:03d}", success=False, reward=-300,
            ))
        for i in range(7, 10):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="roas_drop",
                entity_id=f"ca{i:03d}", success=True, reward=0.3,
            ))
        # 动作B: scale_winner, 中等失败率
        for i in range(6):
            store.store(_make_experience(
                action_type="scale_winner", opportunity_type="creative_scale",
                entity_id=f"cb{i:03d}", success=False, reward=-150,
            ))
        for i in range(6, 10):
            store.store(_make_experience(
                action_type="scale_winner", opportunity_type="creative_scale",
                entity_id=f"cb{i:03d}", success=True, reward=0.4,
            ))

        fm = FailureMemory(store)
        patterns = fm.extract()
        assert len(patterns) == 2

    def test_extract_below_min_attempts_ignored(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        # 只有 2 次失败
        for i in range(2):
            store.store(_make_experience(
                action_type="increase_budget", entity_id=f"c{i:03d}",
                success=False, reward=-100,
            ))

        fm = FailureMemory(store)
        patterns = fm.extract(min_attempts=3)
        assert patterns == []

    def test_extract_below_min_failure_rate_ignored(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        # 3 次失败 + 7 次成功 = 30% 失败率
        for i in range(3):
            store.store(_make_experience(
                action_type="increase_budget", entity_id=f"c{i:03d}",
                success=False, reward=-100,
            ))
        for i in range(3, 10):
            store.store(_make_experience(
                action_type="increase_budget", entity_id=f"c{i:03d}",
                success=True, reward=0.5,
            ))

        fm = FailureMemory(store)
        patterns = fm.extract(min_failure_rate=0.5)
        assert patterns == []

    def test_extract_with_audience_segment(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        for i in range(7):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="roas_drop",
                entity_id=f"c{i:03d}", success=False, reward=-200,
                audience_segment="female_25_35",
            ))
        for i in range(7, 10):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="roas_drop",
                entity_id=f"c{i:03d}", success=True, reward=0.3,
                audience_segment="female_25_35",
            ))

        fm = FailureMemory(store)
        patterns = fm.extract()
        assert len(patterns) == 1
        assert patterns[0].condition.audience_segment == "female_25_35"

    def test_extract_severity_assignment(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureSeverity
        store = ExperienceStore()
        # 9/10 失败 = 90% → CRITICAL
        for i in range(9):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="roas_drop",
                entity_id=f"c{i:03d}", success=False, reward=-500,
            ))
        store.store(_make_experience(
            action_type="increase_budget", opportunity_type="roas_drop",
            entity_id="c009", success=True, reward=0.2,
        ))

        fm = FailureMemory(store)
        patterns = fm.extract()
        assert len(patterns) == 1
        assert patterns[0].severity == FailureSeverity.CRITICAL

    def test_extract_different_products_separate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        store = ExperienceStore()
        # merge 产品
        for i in range(7):
            store.store(_make_experience(
                action_type="increase_budget", product_id="merge",
                entity_id=f"cm{i:03d}", success=False, reward=-200,
            ))
        for i in range(7, 10):
            store.store(_make_experience(
                action_type="increase_budget", product_id="merge",
                entity_id=f"cm{i:03d}", success=True, reward=0.3,
            ))
        # puzzle 产品
        for i in range(7):
            store.store(_make_experience(
                action_type="increase_budget", product_id="puzzle",
                entity_id=f"cp{i:03d}", success=False, reward=-100,
            ))
        for i in range(7, 10):
            store.store(_make_experience(
                action_type="increase_budget", product_id="puzzle",
                entity_id=f"cp{i:03d}", success=True, reward=0.4,
            ))

        fm = FailureMemory(store)
        patterns = fm.extract()
        assert len(patterns) == 2


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Store
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryStore:
    """FailureMemory 存储功能."""

    def _setup_fm(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        return FailureMemory(ExperienceStore())

    def test_store_single(self):
        fm = self._setup_fm()
        fp = _make_failure_pattern()
        fid = fm.store(fp)
        assert fid == fp.failure_id
        assert fm.count == 1

    def test_store_batch(self):
        fm = self._setup_fm()
        fp1 = _make_failure_pattern(name="F1", action_type="increase_budget", opportunity_type="roas_drop")
        fp2 = _make_failure_pattern(name="F2", action_type="scale_winner", opportunity_type="creative_scale")
        ids = fm.store_batch([fp1, fp2])
        assert len(ids) == 2
        assert fm.count == 2

    def test_store_update_existing(self):
        fm = self._setup_fm()
        fp1 = _make_failure_pattern(name="F1", failure_rate=0.8, total_attempts=10)
        fm.store(fp1)

        # 更新相同模式
        fp2 = _make_failure_pattern(name="F1 Updated", failure_rate=0.85, total_attempts=20)
        fm.store(fp2)

        assert fm.count == 1
        all_p = fm.get_all()
        assert all_p[0].failure_rate == 0.85
        assert all_p[0].total_attempts == 20


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Query
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryQuery:
    """FailureMemory 查询功能."""

    def _setup_fm(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())

        # 模式1: 预算浪费
        fp1 = _make_failure_pattern(
            name="Budget Waste", action_type="increase_budget",
            opportunity_type="roas_drop", failure_rate=0.9, total_attempts=50,
            avg_loss=800.0,
        )
        fp1.compute_severity()

        # 模式2: 扩量过快
        fp2 = _make_failure_pattern(
            name="Scale Too Fast", action_type="scale_winner",
            opportunity_type="creative_scale", failure_rate=0.7, total_attempts=30,
            avg_loss=300.0,
        )
        fp2.compute_severity()

        # 模式3: 低失败率 (不显著)
        fp3 = _make_failure_pattern(
            name="Low Risk", action_type="mutate_hook",
            opportunity_type="creative_fatigue", failure_rate=0.4, total_attempts=10,
            avg_loss=50.0,
        )
        fp3.compute_severity()

        fm.store_batch([fp1, fp2, fp3])
        return fm

    def test_query_by_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(action_types=["increase_budget"]))
        assert len(results) == 1
        assert results[0].blocked_action == "increase_budget"

    def test_query_by_opportunity(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(opportunity_types=["creative_scale"]))
        assert len(results) == 1

    def test_query_blocking_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(blocking_only=True))
        assert len(results) >= 1
        assert all(p.is_blocking() for p in results)

    def test_query_significant_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(significant_only=True))
        assert len(results) == 2  # fp3 不显著
        assert all(p.is_significant() for p in results)

    def test_query_min_failure_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(min_failure_rate=0.8))
        assert len(results) == 1  # 只有 fp1

    def test_query_min_attempts(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(min_attempts=40))
        assert len(results) == 1

    def test_query_sort_by_avg_loss(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(sort_by="avg_loss", sort_desc=True))
        assert len(results) == 3
        assert results[0].avg_loss >= results[1].avg_loss

    def test_query_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(limit=1))
        assert len(results) == 1

    def test_query_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = FailureMemory(ExperienceStore())
        results = fm.query(FailureQuery())
        assert results == []

    def test_query_by_severity(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery
        fm = self._setup_fm()
        results = fm.query(FailureQuery(severity_levels=["critical"]))
        assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Check Action
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryCheckAction:
    """FailureMemory check_action 功能."""

    def _setup_fm(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())

        fp1 = _make_failure_pattern(
            name="Budget Waste on ROAS Drop",
            action_type="increase_budget", opportunity_type="roas_drop",
            failure_rate=0.87, total_attempts=30, avg_loss=800.0,
        )
        fp1.compute_confidence()
        fp1.compute_severity()

        fp2 = _make_failure_pattern(
            name="Scale Too Fast",
            action_type="scale_winner", opportunity_type="creative_scale",
            failure_rate=0.72, total_attempts=25, avg_loss=300.0,
        )
        fp2.compute_confidence()
        fp2.compute_severity()

        fm.store_batch([fp1, fp2])
        return fm

    def test_check_action_match(self):
        fm = self._setup_fm()
        warnings = fm.check_action(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert len(warnings) == 1
        assert warnings[0].action_type == "increase_budget"
        assert warnings[0].risk_score > 0

    def test_check_action_no_match(self):
        fm = self._setup_fm()
        warnings = fm.check_action(
            action_type="safe_action",
            opportunity_type="safe_context",
        )
        assert warnings == []

    def test_check_action_insignificant_ignored(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailurePattern
        fm = self._setup_fm()
        # 添加一个不显著的模式
        fp = FailurePattern(
            name="Insignificant", blocked_action="safe_action",
            failure_rate=0.9, total_attempts=2,
        )
        fp.condition.action_type = "safe_action"
        fp.compute_confidence()
        fp.compute_severity()
        fm.store(fp)
        warnings = fm.check_action(action_type="safe_action")
        assert warnings == []  # 不显著，被忽略

    def test_check_action_with_audience(self):
        fm = self._setup_fm()
        fp = _make_failure_pattern(
            name="Audience Specific",
            action_type="increase_budget", opportunity_type="roas_drop",
            audience_segment="female_25_35",
            failure_rate=0.85, total_attempts=15, avg_loss=600.0,
        )
        fp.compute_confidence()
        fp.compute_severity()
        fm.store(fp)

        warnings = fm.check_action(
            action_type="increase_budget", opportunity_type="roas_drop",
            audience_segment="female_25_35",
        )
        assert len(warnings) >= 1

    def test_check_action_wrong_audience_no_match(self):
        fm = self._setup_fm()
        fp = _make_failure_pattern(
            name="Audience Specific",
            action_type="increase_budget", opportunity_type="roas_drop",
            audience_segment="female_25_35",
            failure_rate=0.85, total_attempts=15, avg_loss=600.0,
        )
        fp.compute_confidence()
        fp.compute_severity()
        fm.store(fp)

        warnings = fm.check_action(
            action_type="increase_budget", opportunity_type="roas_drop",
            audience_segment="male_18_24",
        )
        # 不应该匹配，因为受众不同
        assert len(warnings) == 1  # 仍然有 fp1 匹配 (fp1 没有受众限制)
        # 但 fp1 没有 audience 限制，所以还是会匹配到
        # 让我们验证只有 fp1 匹配
        assert warnings[0].pattern_name == "Budget Waste on ROAS Drop"

    def test_get_blocking_warnings(self):
        fm = self._setup_fm()
        blocking = fm.get_blocking_warnings(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert len(blocking) >= 1
        assert all(w.requires_approval for w in blocking)

    def test_compute_risk_score_safe(self):
        fm = self._setup_fm()
        score = fm.compute_risk_score(action_type="safe_action")
        assert score == 0.0

    def test_compute_risk_score_risky(self):
        fm = self._setup_fm()
        score = fm.compute_risk_score(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert score > 0.5

    def test_warning_risk_score_range(self):
        fm = self._setup_fm()
        warnings = fm.check_action(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert len(warnings) == 1
        assert 0.0 <= warnings[0].risk_score <= 1.0


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Check Strategy
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryCheckStrategy:
    """FailureMemory check_strategy 功能."""

    def _setup_fm(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())

        fp = _make_failure_pattern(
            name="Dangerous Scale",
            action_type="scale_winner", opportunity_type="creative_scale",
            failure_rate=0.85, total_attempts=20, avg_loss=1000.0,
        )
        fp.compute_confidence()
        fp.compute_severity()
        fm.store(fp)
        return fm

    def _make_strategy(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyTriggerCondition,
        )
        return GrowthStrategyPattern(
            name="Test Strategy",
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner"),  # 危险动作
                StrategyStep(order=3, action_type="create_population"),
            ],
        )

    def test_check_strategy_finds_warnings(self):
        fm = self._setup_fm()
        strategy = self._make_strategy()
        all_warnings = fm.check_strategy(strategy)
        assert len(all_warnings) >= 1
        assert "step_2" in all_warnings  # scale_winner 是第2步

    def test_check_strategy_safe_strategy(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyTriggerCondition,
        )
        fm = self._setup_fm()
        strategy = GrowthStrategyPattern(
            name="Safe Strategy",
            trigger=StrategyTriggerCondition(opportunity_type="safe_context"),
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="create_population"),
            ],
        )
        all_warnings = fm.check_strategy(strategy)
        assert all_warnings == {}


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Convenience
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryConvenience:
    """FailureMemory 便捷方法."""

    def _setup_fm(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())
        fp = _make_failure_pattern(
            name="Test", action_type="increase_budget",
            failure_rate=0.8, total_attempts=10, avg_loss=500.0,
        )
        fp.compute_confidence()
        fp.compute_severity()
        fm.store(fp)
        return fm

    def test_get_all(self):
        fm = self._setup_fm()
        assert len(fm.get_all()) == 1

    def test_get_by_action(self):
        fm = self._setup_fm()
        results = fm.get_by_action("increase_budget")
        assert len(results) == 1

    def test_get_blocking_patterns(self):
        fm = self._setup_fm()
        results = fm.get_blocking_patterns()
        assert all(p.is_blocking() for p in results)

    def test_get_most_dangerous(self):
        fm = self._setup_fm()
        results = fm.get_most_dangerous(3)
        assert len(results) >= 1

    def test_count_property(self):
        fm = self._setup_fm()
        assert fm.count == 1

    def test_clear(self):
        fm = self._setup_fm()
        fm.clear()
        assert fm.count == 0


# ═══════════════════════════════════════════════════════════════
# Test: FailureMemory - Stats
# ═══════════════════════════════════════════════════════════════

class TestFailureMemoryStats:
    """FailureMemory 统计功能."""

    def test_stats_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        fm = FailureMemory(ExperienceStore())
        stats = fm.get_stats()
        assert stats.total_patterns == 0

    def test_stats_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureCategory
        fm = FailureMemory(ExperienceStore())

        fp1 = _make_failure_pattern(
            name="F1", action_type="increase_budget",
            failure_rate=0.8, total_attempts=10, avg_loss=500.0,
        )
        fp1.category = FailureCategory.BUDGET_WASTE
        fp1.compute_confidence()
        fp1.compute_severity()

        fp2 = _make_failure_pattern(
            name="F2", action_type="scale_winner",
            failure_rate=0.6, total_attempts=15, avg_loss=300.0,
        )
        fp2.category = FailureCategory.SCALE_TOO_FAST
        fp2.compute_confidence()
        fp2.compute_severity()

        fm.store_batch([fp1, fp2])

        stats = fm.get_stats()
        assert stats.total_patterns == 2
        assert stats.avg_failure_rate > 0
        assert stats.avg_loss == 400.0
        assert "budget_waste" in stats.by_category
        assert "scale_too_fast" in stats.by_category
        assert len(stats.top_dangerous) >= 1
        assert stats.total_avoided_loss > 0


# ═══════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试."""

    def test_full_extract_warning_loop(self):
        """完整闭环: 经验→失败模式→警告."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory

        # Step 1: 积累失败经验
        exp_store = ExperienceStore()
        for i in range(8):
            exp_store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="roas_drop",
                entity_id=f"c{i:03d}",
                success=False, reward=-300,
            ))
        for i in range(8, 10):
            exp_store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="roas_drop",
                entity_id=f"c{i:03d}",
                success=True, reward=0.3,
            ))

        # Step 2: 提取
        fm = FailureMemory(exp_store)
        patterns = fm.extract()
        assert len(patterns) == 1
        assert patterns[0].failure_rate == 0.8

        # Step 3: 存储
        fm.store_batch(patterns)

        # Step 4: 检查风险 (80% fail, 10 attempts, 300 avg_loss)
        risk = fm.compute_risk_score(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert risk > 0.2  # 风险评分 = failure_rate² × sample_factor × loss_weight

        # Step 5: 获取阻止级警告
        blocking = fm.get_blocking_warnings(
            action_type="increase_budget",
            opportunity_type="roas_drop",
        )
        assert len(blocking) >= 1

    def test_extract_and_store_then_query(self):
        """提取→存储→查询 完整流程."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import FailureQuery

        exp_store = ExperienceStore()
        for i in range(6):
            exp_store.store(_make_experience(
                action_type="scale_winner",
                opportunity_type="creative_scale",
                entity_id=f"c{i:03d}",
                success=False, reward=-150,
            ))
        for i in range(6, 10):
            exp_store.store(_make_experience(
                action_type="scale_winner",
                opportunity_type="creative_scale",
                entity_id=f"c{i:03d}",
                success=True, reward=0.5,
            ))

        fm = FailureMemory(exp_store)
        ids = fm.extract_and_store()
        assert len(ids) >= 1

        results = fm.query(FailureQuery(action_types=["scale_winner"]))
        assert len(results) >= 1
        assert results[0].failure_rate == 0.6

    def test_risk_aware_strategy_check(self):
        """风险感知策略检查: 模拟策略→失败检查→决策."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyTriggerCondition,
        )

        # 积累失败经验: scale_winner 在 creative_scale 下高风险
        exp_store = ExperienceStore()
        for i in range(9):
            exp_store.store(_make_experience(
                action_type="scale_winner",
                opportunity_type="creative_scale",
                entity_id=f"c{i:03d}",
                success=False, reward=-500,
            ))
        exp_store.store(_make_experience(
            action_type="scale_winner",
            opportunity_type="creative_scale",
            entity_id="c009",
            success=True, reward=0.2,
        ))

        fm = FailureMemory(exp_store)
        fm.extract_and_store()

        # 模拟策略推荐
        strategy = GrowthStrategyPattern(
            name="Creative Scale Pipeline",
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner"),  # 危险
                StrategyStep(order=3, action_type="create_population"),
            ],
        )

        # 检查策略
        all_warnings = fm.check_strategy(strategy)
        assert "step_2" in all_warnings
        assert len(all_warnings["step_2"]) >= 1
        assert all_warnings["step_2"][0].requires_approval is True

    def test_large_scale_extraction(self):
        """大规模提取测试."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory

        exp_store = ExperienceStore()
        action_configs = [
            ("increase_budget", "roas_drop", 0.8),
            ("scale_winner", "creative_scale", 0.7),
            ("expand_audience", "audience_expansion", 0.6),
            ("mutate_visual", "creative_fatigue", 0.55),
        ]

        for action_type, opp_type, fail_rate in action_configs:
            fail_count = int(30 * fail_rate)
            success_count = 30 - fail_count
            for i in range(fail_count):
                exp_store.store(_make_experience(
                    action_type=action_type, opportunity_type=opp_type,
                    entity_id=f"{action_type}_f{i:03d}",
                    success=False, reward=-200,
                ))
            for i in range(success_count):
                exp_store.store(_make_experience(
                    action_type=action_type, opportunity_type=opp_type,
                    entity_id=f"{action_type}_s{i:03d}",
                    success=True, reward=0.5,
                ))

        fm = FailureMemory(exp_store)
        patterns = fm.extract()
        assert len(patterns) >= 2  # 至少 2 个显著失败模式
        assert len(patterns) <= 4  # 最多 4 个

        # 验证所有模式都显著
        for p in patterns:
            assert p.is_significant()
            assert p.failure_rate >= 0.5