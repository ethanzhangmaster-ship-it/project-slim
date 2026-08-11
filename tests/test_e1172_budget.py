"""E11.7.2 — Evolution Budget Manager 测试。

测试范围：
  - EvolutionBudget: 4 个工厂方法 + 序列化
  - BudgetUsage: 数据模型 + is_new_day
  - BudgetDecision: 数据模型 + 序列化
  - BudgetLevel: 枚举值
  - BudgetTracker: record + 每日重置 + 统计
  - BudgetPolicy: 6 层检查 + 批量检查
  - EvolutionBudgetManager: check/consume/complete + 级别切换 + lock/unlock
  - Scheduler Integration: submit 时 budget check + complete 时 budget 释放
  - Controller Integration: check_budget + can_evolve
  - Full Pipeline: Budget → Check → Consume → Complete
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.models import (
    EvolutionBudget,
    BudgetUsage,
    BudgetDecision,
    BudgetLevel,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.budget_tracker import (
    BudgetTracker,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.budget_policy import (
    BudgetPolicy,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.budget_manager import (
    EvolutionBudgetManager,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.models import (
    EvolutionTask,
    TaskStatus,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.scheduler import (
    EvolutionScheduler,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_task(
    task_id: str = "",
    genome_id: str = "g001",
    priority: int = 50,
) -> EvolutionTask:
    return EvolutionTask(
        task_id=task_id,
        genome_id=genome_id,
        action="mutate",
        mutation_strategy="medium",
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models — EvolutionBudget
# ═══════════════════════════════════════════════════════════

class TestEvolutionBudget:
    """EvolutionBudget 测试。"""

    def test_create_default(self):
        budget = EvolutionBudget()
        assert budget.budget_id.startswith("eb_")
        assert budget.daily_task_limit == 100
        assert budget.max_daily_cost == 100.0
        assert budget.level == BudgetLevel.NORMAL

    def test_create_with_values(self):
        budget = EvolutionBudget(
            daily_task_limit=50,
            daily_mutation_limit=25,
            max_daily_cost=50.0,
            max_parallel_tasks=3,
            level=BudgetLevel.CONSERVATIVE,
        )
        assert budget.daily_task_limit == 50
        assert budget.max_daily_cost == 50.0
        assert budget.max_parallel_tasks == 3
        assert budget.level == BudgetLevel.CONSERVATIVE

    def test_liberal(self):
        budget = EvolutionBudget.liberal()
        assert budget.daily_task_limit == 200
        assert budget.max_daily_cost == 500.0
        assert budget.max_parallel_tasks == 10
        assert budget.level == BudgetLevel.LIBERAL

    def test_normal(self):
        budget = EvolutionBudget.normal()
        assert budget.daily_task_limit == 100
        assert budget.max_daily_cost == 100.0
        assert budget.max_parallel_tasks == 5
        assert budget.level == BudgetLevel.NORMAL

    def test_conservative(self):
        budget = EvolutionBudget.conservative()
        assert budget.daily_task_limit == 20
        assert budget.max_daily_cost == 20.0
        assert budget.max_parallel_tasks == 2
        assert budget.level == BudgetLevel.CONSERVATIVE

    def test_locked(self):
        budget = EvolutionBudget.locked()
        assert budget.daily_task_limit == 0
        assert budget.max_daily_cost == 0.0
        assert budget.max_parallel_tasks == 0
        assert budget.level == BudgetLevel.LOCKED

    def test_to_dict(self):
        budget = EvolutionBudget(daily_task_limit=50, max_daily_cost=50.0)
        d = budget.to_dict()
        assert d["daily_task_limit"] == 50
        assert d["max_daily_cost"] == 50.0
        assert d["level"] == "normal"

    def test_repr(self):
        budget = EvolutionBudget(daily_task_limit=50, max_daily_cost=50.0)
        r = repr(budget)
        assert "50" in r
        assert "normal" in r


# ═══════════════════════════════════════════════════════════
# 2. Models — BudgetUsage / BudgetDecision / BudgetLevel
# ═══════════════════════════════════════════════════════════

class TestBudgetUsage:
    """BudgetUsage 测试。"""

    def test_create_default(self):
        usage = BudgetUsage()
        assert usage.date != ""
        assert usage.tasks_used == 0
        assert usage.cost_used == 0.0

    def test_create_with_values(self):
        usage = BudgetUsage(
            date="2026-01-01",
            tasks_used=50,
            cost_used=25.0,
            active_tasks=3,
        )
        assert usage.date == "2026-01-01"
        assert usage.tasks_used == 50
        assert usage.cost_used == 25.0
        assert usage.active_tasks == 3

    def test_is_new_day(self):
        from datetime import date
        usage = BudgetUsage(date="2020-01-01")
        assert usage.is_new_day() is True  # today != 2020-01-01

    def test_is_new_day_same(self):
        from datetime import date
        usage = BudgetUsage(date=date.today().isoformat())
        assert usage.is_new_day() is False

    def test_to_dict(self):
        usage = BudgetUsage(date="2026-01-01", tasks_used=30)
        d = usage.to_dict()
        assert d["date"] == "2026-01-01"
        assert d["tasks_used"] == 30

    def test_repr(self):
        usage = BudgetUsage(tasks_used=30, cost_used=15.5)
        r = repr(usage)
        assert "30" in r
        assert "15.50" in r


class TestBudgetDecision:
    """BudgetDecision 测试。"""

    def test_allowed(self):
        decision = BudgetDecision(
            allowed=True,
            remaining_tasks=50,
            remaining_cost=80.0,
            remaining_slots=3,
        )
        assert decision.allowed is True
        assert decision.remaining_tasks == 50

    def test_denied(self):
        decision = BudgetDecision(
            allowed=False,
            reason="Daily task limit reached",
            remaining_tasks=0,
        )
        assert decision.allowed is False
        assert "task limit" in decision.reason

    def test_to_dict(self):
        decision = BudgetDecision(
            allowed=False,
            reason="limit",
            remaining_tasks=0,
            remaining_cost=0.0,
            remaining_slots=0,
        )
        d = decision.to_dict()
        assert d["allowed"] is False
        assert d["reason"] == "limit"

    def test_repr_allowed(self):
        decision = BudgetDecision(allowed=True)
        assert "ALLOWED" in repr(decision)

    def test_repr_denied(self):
        decision = BudgetDecision(allowed=False, reason="test")
        assert "DENIED" in repr(decision)


class TestBudgetLevel:
    """BudgetLevel 枚举测试。"""

    def test_values(self):
        assert BudgetLevel.LIBERAL.value == "liberal"
        assert BudgetLevel.NORMAL.value == "normal"
        assert BudgetLevel.CONSERVATIVE.value == "conservative"
        assert BudgetLevel.LOCKED.value == "locked"


# ═══════════════════════════════════════════════════════════
# 3. BudgetTracker
# ═══════════════════════════════════════════════════════════

class TestBudgetTracker:
    """BudgetTracker 测试。"""

    def test_record_task(self):
        tracker = BudgetTracker()
        tracker.record_task(5)
        assert tracker.get_tasks_used() == 5

    def test_record_mutation(self):
        tracker = BudgetTracker()
        tracker.record_mutation(3)
        assert tracker.usage().mutations_used == 3

    def test_record_generation(self):
        tracker = BudgetTracker()
        tracker.record_generation(2)
        assert tracker.usage().generations_used == 2

    def test_record_cost(self):
        tracker = BudgetTracker()
        tracker.record_cost(15.5)
        assert tracker.get_cost_used() == 15.5
        assert tracker.get_total_cost() == 15.5

    def test_record_active_increment(self):
        tracker = BudgetTracker()
        tracker.record_active_increment(2)
        assert tracker.get_active_tasks() == 2

    def test_record_active_decrement(self):
        tracker = BudgetTracker()
        tracker.record_active_increment(3)
        tracker.record_active_decrement(1)
        assert tracker.get_active_tasks() == 2

    def test_record_active_decrement_not_negative(self):
        tracker = BudgetTracker()
        tracker.record_active_decrement(1)
        assert tracker.get_active_tasks() == 0

    def test_record_task_complete(self):
        tracker = BudgetTracker()
        tracker.record_active_increment(1)
        tracker.record_task_complete(cost=10.0)
        assert tracker.get_active_tasks() == 0
        assert tracker.get_cost_used() == 10.0

    def test_total_cost_accumulates(self):
        tracker = BudgetTracker()
        tracker.record_cost(10.0)
        tracker.record_cost(20.0)
        tracker.force_reset()  # 每日重置
        tracker.record_cost(5.0)
        assert tracker.get_cost_used() == 5.0  # 当日
        assert tracker.get_total_cost() == 35.0  # 累计

    def test_total_tasks_accumulates(self):
        tracker = BudgetTracker()
        tracker.record_task(3)
        tracker.force_reset()
        tracker.record_task(2)
        assert tracker.get_tasks_used() == 2
        assert tracker.get_total_tasks() == 5

    def test_force_reset(self):
        tracker = BudgetTracker()
        tracker.record_task(10)
        tracker.record_cost(50.0)
        tracker.force_reset()
        assert tracker.get_tasks_used() == 0
        assert tracker.get_cost_used() == 0
        assert tracker.get_active_tasks() == 0

    def test_get_stats(self):
        tracker = BudgetTracker()
        tracker.record_task(5)
        tracker.record_cost(25.0)
        stats = tracker.get_stats()
        assert stats["tasks_used"] == 5
        assert stats["cost_used"] == 25.0
        assert stats["total_cost"] == 25.0
        assert stats["total_tasks"] == 5

    def test_record_count(self):
        tracker = BudgetTracker()
        tracker.record_task(1)
        tracker.record_cost(10.0)
        assert tracker.record_count == 2

    def test_reset(self):
        tracker = BudgetTracker()
        tracker.record_task(5)
        tracker.record_cost(50.0)
        tracker.reset()
        assert tracker.get_tasks_used() == 0
        assert tracker.get_total_cost() == 0.0
        assert tracker.record_count == 0

    def test_repr(self):
        tracker = BudgetTracker()
        tracker.record_task(5)
        tracker.record_cost(25.0)
        r = repr(tracker)
        assert "5" in r
        assert "25.00" in r


# ═══════════════════════════════════════════════════════════
# 4. BudgetPolicy
# ═══════════════════════════════════════════════════════════

class TestBudgetPolicy:
    """BudgetPolicy 测试。"""

    def test_allow(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_task_limit=10, max_daily_cost=100.0, max_parallel_tasks=5)
        usage = BudgetUsage(tasks_used=0, cost_used=0.0, active_tasks=0)
        decision = policy.check(budget, usage)
        assert decision.allowed is True
        assert decision.remaining_tasks == 9  # 预扣 1

    def test_deny_task_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_task_limit=10)
        usage = BudgetUsage(tasks_used=10)
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "task limit" in decision.reason

    def test_deny_mutation_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_mutation_limit=10)
        usage = BudgetUsage(mutations_used=10)
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "mutation limit" in decision.reason

    def test_deny_generation_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_generation_limit=10)
        usage = BudgetUsage(generations_used=10)
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "generation limit" in decision.reason

    def test_deny_cost_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(max_daily_cost=100.0)
        usage = BudgetUsage(cost_used=100.0)
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "cost limit" in decision.reason

    def test_deny_concurrency_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(max_parallel_tasks=3)
        usage = BudgetUsage(active_tasks=3)
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "parallel" in decision.reason

    def test_deny_locked(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget.locked()
        usage = BudgetUsage()
        decision = policy.check(budget, usage)
        assert decision.allowed is False
        assert "locked" in decision.reason

    def test_check_batch_allowed(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_task_limit=10, max_parallel_tasks=5)
        usage = BudgetUsage(tasks_used=0, active_tasks=0)
        decision = policy.check_batch(budget, usage, count=3)
        assert decision.allowed is True

    def test_check_batch_task_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(daily_task_limit=10)
        usage = BudgetUsage(tasks_used=8)
        decision = policy.check_batch(budget, usage, count=5)
        assert decision.allowed is False
        assert "task quota" in decision.reason

    def test_check_batch_slot_limit(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget(max_parallel_tasks=5)
        usage = BudgetUsage(active_tasks=4)
        decision = policy.check_batch(budget, usage, count=3)
        assert decision.allowed is False
        assert "slots" in decision.reason

    def test_check_count(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget()
        usage = BudgetUsage()
        policy.check(budget, usage)
        policy.check(budget, usage)
        assert policy.check_count == 2

    def test_deny_count(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget.locked()
        usage = BudgetUsage()
        policy.check(budget, usage)
        assert policy.deny_count == 1

    def test_get_stats(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget()
        usage = BudgetUsage()
        policy.check(budget, usage)
        policy.check(budget, usage)
        policy.check(EvolutionBudget.locked(), BudgetUsage())
        stats = policy.get_stats()
        assert stats["check_count"] == 3
        assert stats["deny_count"] == 1
        assert stats["allow_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_reset(self):
        policy = BudgetPolicy()
        budget = EvolutionBudget()
        policy.check(budget, BudgetUsage())
        policy.reset()
        assert policy.check_count == 0
        assert policy.deny_count == 0

    def test_repr(self):
        policy = BudgetPolicy()
        r = repr(policy)
        assert "checks=0" in r


# ═══════════════════════════════════════════════════════════
# 5. EvolutionBudgetManager
# ═══════════════════════════════════════════════════════════

class TestEvolutionBudgetManager:
    """EvolutionBudgetManager 测试。"""

    def test_check_allowed(self):
        manager = EvolutionBudgetManager()
        decision = manager.check()
        assert decision.allowed is True

    def test_can_execute(self):
        manager = EvolutionBudgetManager()
        assert manager.can_execute() is True

    def test_check_batch(self):
        manager = EvolutionBudgetManager()
        decision = manager.check_batch(count=3)
        assert decision.allowed is True

    def test_consume(self):
        manager = EvolutionBudgetManager()
        decision = manager.consume(task_count=1)
        assert decision.allowed is True
        assert manager.usage().tasks_used == 1
        assert manager.usage().active_tasks == 1

    def test_consume_with_costs(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=1, mutation_count=5, generation_count=2, cost=10.0)
        assert manager.usage().tasks_used == 1
        assert manager.usage().mutations_used == 5
        assert manager.usage().generations_used == 2
        assert manager.usage().cost_used == 10.0

    def test_consume_denied_locked(self):
        manager = EvolutionBudgetManager(EvolutionBudget.locked())
        decision = manager.consume()
        assert decision.allowed is False
        assert manager.usage().tasks_used == 0  # 未记录

    def test_consume_until_limit(self):
        manager = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=2, max_parallel_tasks=5))
        assert manager.consume().allowed is True
        assert manager.consume().allowed is True
        assert manager.consume().allowed is False  # 第 3 个被拒
        assert manager.usage().tasks_used == 2

    def test_consume_until_concurrency(self):
        manager = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=100, max_parallel_tasks=2))
        assert manager.consume().allowed is True
        assert manager.consume().allowed is True
        assert manager.consume().allowed is False  # 并发满
        assert manager.usage().active_tasks == 2

    def test_complete(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=2)
        manager.complete()
        assert manager.usage().active_tasks == 1

    def test_complete_batch(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=3)
        manager.complete_batch(count=2, cost=20.0)
        assert manager.usage().active_tasks == 1
        assert manager.usage().cost_used == 20.0

    def test_set_level_liberal(self):
        manager = EvolutionBudgetManager()
        manager.set_level(BudgetLevel.LIBERAL)
        assert manager.budget.daily_task_limit == 200
        assert manager.budget.level == BudgetLevel.LIBERAL

    def test_set_level_conservative(self):
        manager = EvolutionBudgetManager()
        manager.set_level(BudgetLevel.CONSERVATIVE)
        assert manager.budget.daily_task_limit == 20
        assert manager.budget.max_parallel_tasks == 2

    def test_lock_unlock(self):
        manager = EvolutionBudgetManager()
        manager.lock()
        assert manager.can_execute() is False
        manager.unlock()
        assert manager.can_execute() is True

    def test_set_budget(self):
        manager = EvolutionBudgetManager()
        new_budget = EvolutionBudget(daily_task_limit=42, max_daily_cost=42.0)
        manager.set_budget(new_budget)
        assert manager.budget.daily_task_limit == 42

    def test_get_remaining(self):
        manager = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=10, max_daily_cost=100.0, max_parallel_tasks=5))
        manager.consume(task_count=3, cost=30.0)
        assert manager.get_remaining_tasks() == 7
        assert manager.get_remaining_cost() == 70.0
        assert manager.get_remaining_slots() == 2  # 5 - 3 active

    def test_get_utilization(self):
        manager = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=10))
        manager.consume(task_count=3)
        assert manager.get_utilization() == 0.3

    def test_get_utilization_zero_budget(self):
        manager = EvolutionBudgetManager(EvolutionBudget.locked())
        assert manager.get_utilization() == 0.0

    def test_get_cost_utilization(self):
        manager = EvolutionBudgetManager(EvolutionBudget(max_daily_cost=100.0))
        manager.consume(cost=30.0)
        assert manager.get_cost_utilization() == 0.3

    def test_get_stats(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=2, cost=20.0)
        stats = manager.get_stats()
        assert stats["budget"]["daily_task_limit"] == 100
        assert stats["usage"]["tasks_used"] == 2
        assert "remaining_tasks" in stats
        assert "utilization" in stats

    def test_reset(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=5)
        manager.reset()
        assert manager.usage().tasks_used == 0

    def test_dependency_injection(self):
        tracker = BudgetTracker()
        policy = BudgetPolicy()
        manager = EvolutionBudgetManager(
            budget=EvolutionBudget(daily_task_limit=10),
            tracker=tracker,
            policy=policy,
        )
        assert manager.can_execute() is True

    def test_repr(self):
        manager = EvolutionBudgetManager()
        manager.consume(task_count=3, cost=15.0)
        r = repr(manager)
        assert "3/100" in r
        assert "15.00" in r


# ═══════════════════════════════════════════════════════════
# 6. Scheduler Integration
# ═══════════════════════════════════════════════════════════

class TestSchedulerBudgetIntegration:
    """Scheduler + BudgetManager 集成测试。"""

    def test_submit_with_budget(self):
        """有预算时提交成功。"""
        budget = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=10, max_parallel_tasks=5))
        scheduler = EvolutionScheduler(budget_manager=budget)
        task = _make_task(genome_id="g001")
        task_id = scheduler.submit(task)
        assert task_id != ""
        assert scheduler.get_queue_size() == 1
        assert budget.usage().tasks_used == 1

    def test_submit_budget_rejected(self):
        """预算不足时提交被拒绝。"""
        budget = EvolutionBudgetManager(EvolutionBudget.locked())
        scheduler = EvolutionScheduler(budget_manager=budget)
        task = _make_task(genome_id="g001")
        task_id = scheduler.submit(task)
        assert task_id == ""
        assert scheduler.get_queue_size() == 0

    def test_submit_no_budget_manager(self):
        """无 budget_manager 时正常提交。"""
        scheduler = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        task_id = scheduler.submit(task)
        assert task_id != ""
        assert scheduler.get_queue_size() == 1

    def test_complete_releases_budget(self):
        """完成时释放活跃槽位。"""
        budget = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=10, max_parallel_tasks=5))
        scheduler = EvolutionScheduler(budget_manager=budget)
        task = _make_task(genome_id="g001")
        scheduler.submit(task)
        scheduler.next()
        assert budget.usage().active_tasks == 1
        scheduler.complete(task.task_id)
        assert budget.usage().active_tasks == 0

    def test_budget_manager_property(self):
        budget = EvolutionBudgetManager()
        scheduler = EvolutionScheduler(budget_manager=budget)
        assert scheduler.budget_manager is budget

    def test_submit_policies_with_budget(self):
        """批量提交受预算限制。"""
        budget = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=2, max_parallel_tasks=5))
        scheduler = EvolutionScheduler(budget_manager=budget)
        from market_ops.creative_vision_runtime.autonomous_controller.policy.models import (
            EvolutionAction,
            MutationStrategy,
            EvolutionPolicyDecision,
        )
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.MUTATE, mutation_strategy=MutationStrategy.MEDIUM),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.MUTATE, mutation_strategy=MutationStrategy.MEDIUM),
            EvolutionPolicyDecision(genome_id="g003", action=EvolutionAction.MUTATE, mutation_strategy=MutationStrategy.MEDIUM),
        ]
        ids = scheduler.submit_policies(decisions)
        # 前 2 个成功，第 3 个被预算拒绝
        non_empty = [tid for tid in ids if tid != ""]
        assert len(non_empty) == 2
        assert scheduler.get_queue_size() == 2


# ═══════════════════════════════════════════════════════════
# 7. Controller Integration
# ═══════════════════════════════════════════════════════════

class TestControllerBudgetIntegration:
    """Controller check_budget 测试。"""

    @pytest.fixture
    def controller(self):
        from market_ops.creative_vision_runtime.intelligence.engine import (
            VisionIntelligenceEngine,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.models import (
            ControllerConfig,
        )

        mock_intelligence = MagicMock(spec=VisionIntelligenceEngine)
        mock_intelligence.analyze_batch.return_value = {}
        mock_intelligence.extract_winner_dna.return_value = None

        config = ControllerConfig(max_cycles=1)
        return AutonomousCreativeController(
            intelligence_engine=mock_intelligence,
            config=config,
        )

    def test_check_budget_allowed(self, controller):
        decision = controller.check_budget()
        assert decision.allowed is True

    def test_can_evolve(self, controller):
        assert controller.can_evolve() is True

    def test_can_evolve_after_lock(self, controller):
        controller.budget_manager.lock()
        assert controller.can_evolve() is False

    def test_budget_manager_property(self, controller):
        assert isinstance(controller.budget_manager, EvolutionBudgetManager)


# ═══════════════════════════════════════════════════════════
# 8. Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路：Budget → Check → Consume → Complete。"""

    def test_pipeline_budget_lifecycle(self):
        """预算生命周期：创建 → 消耗 → 完成 → 释放。"""
        budget = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=5, max_parallel_tasks=3))
        # 消耗 3 个
        budget.consume(task_count=3)
        assert budget.usage().tasks_used == 3
        assert budget.usage().active_tasks == 3
        # 完成 2 个
        budget.complete_batch(count=2)
        assert budget.usage().active_tasks == 1
        # 可以再消耗
        assert budget.can_execute() is True
        budget.consume(task_count=2)
        assert budget.usage().tasks_used == 5
        # 达到上限
        assert budget.can_execute() is False

    def test_pipeline_lock_unlock_cycle(self):
        """锁定 → 解锁 → 恢复正常。"""
        budget = EvolutionBudgetManager()
        budget.consume(task_count=1)
        budget.lock()
        assert budget.can_execute() is False
        budget.unlock()
        assert budget.can_execute() is True
        budget.consume(task_count=1)
        assert budget.usage().tasks_used == 2

    def test_pipeline_level_switch(self):
        """级别切换影响预算限制。"""
        budget = EvolutionBudgetManager()
        budget.set_level(BudgetLevel.CONSERVATIVE)
        for _ in range(20):
            budget.consume()
        assert budget.can_execute() is False  # 达到 20 上限
        # 切换到 LIBERAL
        budget.set_level(BudgetLevel.LIBERAL)
        assert budget.can_execute() is True

    def test_pipeline_scheduler_with_budget_limit(self):
        """Scheduler + Budget 完整链路。"""
        budget = EvolutionBudgetManager(EvolutionBudget(daily_task_limit=3, max_parallel_tasks=5))
        scheduler = EvolutionScheduler(budget_manager=budget)
        for i in range(5):
            scheduler.submit(_make_task(genome_id=f"g{i}"))
        # 只有 3 个成功入队
        assert scheduler.get_queue_size() == 3
        assert budget.usage().tasks_used == 3
        # 全部执行
        started = scheduler.tick_all()
        assert len(started) == 3
        # 全部完成
        for task in started:
            scheduler.complete(task.task_id)
        assert budget.usage().active_tasks == 0


# ═══════════════════════════════════════════════════════════
# 9. Package Exports
# ═══════════════════════════════════════════════════════════

def test_package_exports():
    """__init__.py 导出所有核心类。"""
    import market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget as b

    assert hasattr(b, "EvolutionBudget")
    assert hasattr(b, "BudgetUsage")
    assert hasattr(b, "BudgetDecision")
    assert hasattr(b, "BudgetLevel")
    assert hasattr(b, "BudgetTracker")
    assert hasattr(b, "BudgetPolicy")
    assert hasattr(b, "EvolutionBudgetManager")