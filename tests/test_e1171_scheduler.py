"""E11.7.1 — Runtime Scheduler 测试。

测试范围：
  - TaskStatus: 枚举值 + 状态转换规则
  - EvolutionTask: 创建 + 属性 + 状态转换 + 序列化
  - TaskFactory: 从 PolicyDecision 创建任务
  - EvolutionPriorityQueue: push/pop/peek + 优先级排序 + 批量操作 + 查询
  - EvolutionScheduler: submit/next/complete/fail/retry/cancel/tick + 回调 + 并发控制
  - Controller Integration: schedule_evolution + schedule_evolution_and_tick
  - Full Pipeline: PolicyDecision → Task → Scheduler → Controller
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call

from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.models import (
    EvolutionTask,
    TaskStatus,
    TaskFactory,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.priority_queue import (
    EvolutionPriorityQueue,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.scheduler import (
    EvolutionScheduler,
)
from market_ops.creative_vision_runtime.autonomous_controller.policy.models import (
    EvolutionAction,
    MutationStrategy,
    EvolutionPolicyDecision,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.models import (
    LearningSignal,
    LearningDirection,
    FitnessScore,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_task(
    task_id: str = "",
    genome_id: str = "g001",
    action: str = "mutate",
    priority: int = 50,
    status: TaskStatus = TaskStatus.PENDING,
    retry_count: int = 0,
    max_retries: int = 3,
) -> EvolutionTask:
    return EvolutionTask(
        task_id=task_id,
        genome_id=genome_id,
        action=action,
        mutation_strategy="medium",
        priority=priority,
        status=status,
        retry_count=retry_count,
        max_retries=max_retries,
    )


def _make_decision(
    genome_id: str = "g001",
    action: EvolutionAction = EvolutionAction.MUTATE,
    strategy: MutationStrategy = MutationStrategy.MEDIUM,
) -> EvolutionPolicyDecision:
    return EvolutionPolicyDecision(
        genome_id=genome_id,
        action=action,
        mutation_strategy=strategy,
        confidence=0.7,
        reason="test decision",
    )


def _make_winner_signal(genome_id: str = "g_w") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.KEEP,
        confidence=0.92,
    )


def _make_improve_signal(genome_id: str = "g_a") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.IMPROVE,
        confidence=0.65,
    )


def _make_failure_signal(genome_id: str = "g_l") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.MUTATE,
        confidence=0.35,
        consecutive_failures=1,
    )


def _make_winner_fitness(genome_id: str = "g_w") -> FitnessScore:
    return FitnessScore(genome_id=genome_id, overall_score=85.0, rank=1)


def _make_avg_fitness(genome_id: str = "g_a") -> FitnessScore:
    return FitnessScore(genome_id=genome_id, overall_score=65.0, rank=2)


def _make_low_fitness(genome_id: str = "g_l") -> FitnessScore:
    return FitnessScore(genome_id=genome_id, overall_score=30.0, rank=3)


# ═══════════════════════════════════════════════════════════
# 1. Models — TaskStatus
# ═══════════════════════════════════════════════════════════

class TestTaskStatus:
    """TaskStatus 枚举测试。"""

    def test_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_valid_transitions_from_pending(self):
        assert TaskStatus.QUEUED in VALID_TRANSITIONS[TaskStatus.PENDING]
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.PENDING]
        assert TaskStatus.RUNNING not in VALID_TRANSITIONS[TaskStatus.PENDING]

    def test_valid_transitions_from_queued(self):
        assert TaskStatus.RUNNING in VALID_TRANSITIONS[TaskStatus.QUEUED]
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.QUEUED]

    def test_valid_transitions_from_running(self):
        assert TaskStatus.COMPLETED in VALID_TRANSITIONS[TaskStatus.RUNNING]
        assert TaskStatus.FAILED in VALID_TRANSITIONS[TaskStatus.RUNNING]
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.RUNNING]

    def test_valid_transitions_from_failed(self):
        assert TaskStatus.QUEUED in VALID_TRANSITIONS[TaskStatus.FAILED]  # retry

    def test_terminal_no_transitions(self):
        assert len(VALID_TRANSITIONS[TaskStatus.COMPLETED]) == 0
        assert len(VALID_TRANSITIONS[TaskStatus.CANCELLED]) == 0


# ═══════════════════════════════════════════════════════════
# 2. Models — EvolutionTask
# ═══════════════════════════════════════════════════════════

class TestEvolutionTask:
    """EvolutionTask 数据模型测试。"""

    def test_create_default(self):
        task = EvolutionTask()
        assert task.task_id.startswith("et_")
        assert task.status == TaskStatus.PENDING
        assert task.max_retries == 3

    def test_create_with_values(self):
        task = EvolutionTask(
            genome_id="g001",
            action="mutate",
            mutation_strategy="medium",
            priority=60,
            max_retries=5,
        )
        assert task.genome_id == "g001"
        assert task.action == "mutate"
        assert task.priority == 60
        assert task.max_retries == 5

    def test_is_terminal(self):
        assert EvolutionTask(status=TaskStatus.COMPLETED).is_terminal is True
        assert EvolutionTask(status=TaskStatus.CANCELLED).is_terminal is True
        assert EvolutionTask(status=TaskStatus.RUNNING).is_terminal is False

    def test_is_running(self):
        assert EvolutionTask(status=TaskStatus.RUNNING).is_running is True
        assert EvolutionTask(status=TaskStatus.QUEUED).is_running is False

    def test_is_queued(self):
        assert EvolutionTask(status=TaskStatus.QUEUED).is_queued is True
        assert EvolutionTask(status=TaskStatus.RUNNING).is_queued is False

    def test_can_retry(self):
        assert EvolutionTask(retry_count=0, max_retries=3).can_retry is True
        assert EvolutionTask(retry_count=2, max_retries=3).can_retry is True
        assert EvolutionTask(retry_count=3, max_retries=3).can_retry is False

    def test_duration_none(self):
        task = EvolutionTask()
        assert task.duration is None

    def test_duration_computed(self):
        task = EvolutionTask(
            started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:00:05+00:00",
        )
        assert task.duration == 5.0

    # ── 状态转换 ──────────────────────────────────────────

    def test_transition_valid(self):
        task = _make_task(status=TaskStatus.PENDING)
        assert task.transition_to(TaskStatus.QUEUED) is True
        assert task.status == TaskStatus.QUEUED

    def test_transition_invalid(self):
        task = _make_task(status=TaskStatus.PENDING)
        assert task.transition_to(TaskStatus.RUNNING) is False
        assert task.status == TaskStatus.PENDING

    def test_mark_running(self):
        task = _make_task(status=TaskStatus.QUEUED)
        assert task.mark_running() is True
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None

    def test_mark_completed(self):
        task = _make_task(status=TaskStatus.RUNNING)
        assert task.mark_completed() is True
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_mark_failed(self):
        task = _make_task(status=TaskStatus.RUNNING)
        assert task.mark_failed("test error") is True
        assert task.status == TaskStatus.FAILED
        assert task.error == "test error"

    def test_mark_cancelled(self):
        task = _make_task(status=TaskStatus.QUEUED)
        assert task.mark_cancelled() is True
        assert task.status == TaskStatus.CANCELLED

    def test_mark_retry_success(self):
        task = _make_task(status=TaskStatus.FAILED, retry_count=0, max_retries=3)
        assert task.mark_retry() is True
        assert task.status == TaskStatus.QUEUED
        assert task.retry_count == 1
        assert task.error is None

    def test_mark_retry_exceeded(self):
        task = _make_task(status=TaskStatus.FAILED, retry_count=3, max_retries=3)
        assert task.mark_retry() is False
        assert task.status == TaskStatus.FAILED

    # ── 序列化 ────────────────────────────────────────────

    def test_to_dict(self):
        task = EvolutionTask(
            genome_id="g001",
            action="exploit",
            mutation_strategy="small",
            priority=80,
            metadata={"key": "value"},
        )
        d = task.to_dict()
        assert d["genome_id"] == "g001"
        assert d["action"] == "exploit"
        assert d["status"] == "pending"
        assert d["metadata"] == {"key": "value"}

    def test_repr(self):
        task = EvolutionTask(task_id="et_abc", genome_id="g001", action="mutate", priority=60)
        r = repr(task)
        assert "et_abc" in r
        assert "g001" in r
        assert "mutate" in r


# ═══════════════════════════════════════════════════════════
# 3. TaskFactory
# ═══════════════════════════════════════════════════════════

class TestTaskFactory:
    """TaskFactory 测试。"""

    def test_create_from_decision(self):
        decision = _make_decision(genome_id="g001", action=EvolutionAction.MUTATE)
        task = TaskFactory.create(decision)
        assert task.genome_id == "g001"
        assert task.action == "mutate"
        assert task.mutation_strategy == "medium"
        assert task.priority == 60  # mutate → 60

    def test_create_priority_mapping(self):
        """验证 action → priority 映射。"""
        assert TaskFactory.create(_make_decision(action=EvolutionAction.RETIRE)).priority == 100
        assert TaskFactory.create(_make_decision(action=EvolutionAction.EXPLOIT)).priority == 80
        assert TaskFactory.create(_make_decision(action=EvolutionAction.CROSSOVER)).priority == 70
        assert TaskFactory.create(_make_decision(action=EvolutionAction.MUTATE)).priority == 60
        assert TaskFactory.create(_make_decision(action=EvolutionAction.EXPLORE)).priority == 40
        assert TaskFactory.create(_make_decision(action=EvolutionAction.KEEP)).priority == 10

    def test_create_custom_priority(self):
        decision = _make_decision()
        task = TaskFactory.create(decision, priority=99)
        assert task.priority == 99

    def test_create_metadata(self):
        decision = _make_decision(genome_id="g001")
        task = TaskFactory.create(decision)
        assert "decision_id" in task.metadata
        assert "confidence" in task.metadata
        assert "mutation_rate" in task.metadata
        assert "target_genes" in task.metadata
        assert task.metadata["confidence"] == 0.7

    def test_create_batch(self):
        decisions = [
            _make_decision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            _make_decision(genome_id="g002", action=EvolutionAction.MUTATE),
        ]
        tasks = TaskFactory.create_batch(decisions)
        assert len(tasks) == 2
        assert tasks[0].priority == 80
        assert tasks[1].priority == 60

    def test_create_batch_custom_priorities(self):
        decisions = [
            _make_decision(genome_id="g001"),
            _make_decision(genome_id="g002"),
        ]
        tasks = TaskFactory.create_batch(
            decisions,
            priorities={"g001": 99, "g002": 10},
        )
        assert tasks[0].priority == 99
        assert tasks[1].priority == 10


# ═══════════════════════════════════════════════════════════
# 4. EvolutionPriorityQueue
# ═══════════════════════════════════════════════════════════

class TestEvolutionPriorityQueue:
    """EvolutionPriorityQueue 测试。"""

    def test_push_and_pop(self):
        q = EvolutionPriorityQueue()
        task = _make_task(genome_id="g001")
        q.push(task)
        assert q.size() == 1
        popped = q.pop()
        assert popped is not None
        assert popped.genome_id == "g001"

    def test_pop_empty(self):
        q = EvolutionPriorityQueue()
        assert q.pop() is None

    def test_priority_ordering(self):
        """高优先级先出。"""
        q = EvolutionPriorityQueue()
        t1 = _make_task(genome_id="g_low", priority=10)
        t2 = _make_task(genome_id="g_mid", priority=50)
        t3 = _make_task(genome_id="g_high", priority=90)
        q.push(t1)
        q.push(t2)
        q.push(t3)
        assert q.pop().genome_id == "g_high"
        assert q.pop().genome_id == "g_mid"
        assert q.pop().genome_id == "g_low"

    def test_fifo_same_priority(self):
        """同优先级按 FIFO。"""
        q = EvolutionPriorityQueue()
        t1 = _make_task(genome_id="g_first", priority=50)
        t2 = _make_task(genome_id="g_second", priority=50)
        q.push(t1)
        q.push(t2)
        assert q.pop().genome_id == "g_first"
        assert q.pop().genome_id == "g_second"

    def test_peek(self):
        q = EvolutionPriorityQueue()
        t1 = _make_task(genome_id="g001", priority=90)
        q.push(t1)
        peeked = q.peek()
        assert peeked is not None
        assert peeked.genome_id == "g001"
        assert q.size() == 1  # 不移除

    def test_peek_empty(self):
        q = EvolutionPriorityQueue()
        assert q.peek() is None

    def test_push_batch(self):
        q = EvolutionPriorityQueue()
        tasks = [_make_task(genome_id=f"g{i}") for i in range(3)]
        q.push_batch(tasks)
        assert q.size() == 3

    def test_pop_batch(self):
        q = EvolutionPriorityQueue()
        tasks = [_make_task(genome_id=f"g{i}", priority=50 - i) for i in range(5)]
        q.push_batch(tasks)
        popped = q.pop_batch(3)
        assert len(popped) == 3
        assert q.size() == 2

    def test_pop_batch_more_than_size(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task(genome_id="g001"))
        popped = q.pop_batch(5)
        assert len(popped) == 1

    def test_pop_all(self):
        q = EvolutionPriorityQueue()
        for i in range(3):
            q.push(_make_task(genome_id=f"g{i}"))
        all_tasks = q.pop_all()
        assert len(all_tasks) == 3
        assert q.is_empty()

    def test_is_empty(self):
        q = EvolutionPriorityQueue()
        assert q.is_empty() is True
        q.push(_make_task())
        assert q.is_empty() is False

    def test_clear(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        q.clear()
        assert q.size() == 0
        assert q.is_empty()

    def test_get_all(self):
        q = EvolutionPriorityQueue()
        t1 = _make_task(genome_id="g_low", priority=10)
        t2 = _make_task(genome_id="g_high", priority=90)
        q.push(t1)
        q.push(t2)
        all_tasks = q.get_all()
        assert len(all_tasks) == 2
        assert all_tasks[0].genome_id == "g_high"  # 高优先级在前
        assert q.size() == 2  # 不移除

    def test_get_by_genome(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task(genome_id="g001"))
        q.push(_make_task(genome_id="g002"))
        q.push(_make_task(genome_id="g001"))
        found = q.get_by_genome("g001")
        assert len(found) == 2

    def test_remove_by_genome(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task(genome_id="g001"))
        q.push(_make_task(genome_id="g002"))
        removed = q.remove_by_genome("g001")
        assert removed == 1
        assert q.size() == 1
        assert q.has_genome("g001") is False

    def test_has_genome(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task(genome_id="g001"))
        assert q.has_genome("g001") is True
        assert q.has_genome("g002") is False

    def test_push_pop_count(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        q.push(_make_task())
        q.pop()
        assert q.push_count == 2
        assert q.pop_count == 1

    def test_get_stats(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        stats = q.get_stats()
        assert stats["size"] == 1
        assert stats["push_count"] == 1

    def test_reset_stats(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        q.reset_stats()
        assert q.push_count == 0
        assert q.pop_count == 0

    def test_len(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        q.push(_make_task())
        assert len(q) == 2

    def test_repr(self):
        q = EvolutionPriorityQueue()
        q.push(_make_task())
        r = repr(q)
        assert "size=1" in r


# ═══════════════════════════════════════════════════════════
# 5. EvolutionScheduler
# ═══════════════════════════════════════════════════════════

class TestEvolutionScheduler:
    """EvolutionScheduler 测试。"""

    # ── 提交 ──────────────────────────────────────────────

    def test_submit(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        task_id = s.submit(task)
        assert task_id == task.task_id
        assert task.status == TaskStatus.QUEUED
        assert s.get_queue_size() == 1
        assert s.submit_count == 1

    def test_submit_policy(self):
        s = EvolutionScheduler()
        decision = _make_decision(genome_id="g001", action=EvolutionAction.EXPLOIT)
        task_id = s.submit_policy(decision)
        assert task_id.startswith("et_")
        task = s.get_task(task_id)
        assert task is not None
        assert task.genome_id == "g001"
        assert task.action == "exploit"
        assert task.priority == 80

    def test_submit_policies(self):
        s = EvolutionScheduler()
        decisions = [
            _make_decision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            _make_decision(genome_id="g002", action=EvolutionAction.MUTATE),
        ]
        task_ids = s.submit_policies(decisions)
        assert len(task_ids) == 2
        assert s.get_queue_size() == 2

    # ── 调度 ──────────────────────────────────────────────

    def test_next(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        next_task = s.next()
        assert next_task is not None
        assert next_task.task_id == task.task_id
        assert next_task.status == TaskStatus.RUNNING
        assert s.running_count == 1

    def test_next_empty_queue(self):
        s = EvolutionScheduler()
        assert s.next() is None

    def test_next_parallel_limit(self):
        s = EvolutionScheduler(max_parallel=2)
        for i in range(3):
            s.submit(_make_task(genome_id=f"g{i}"))
        # 取出 2 个
        s.next()
        s.next()
        # 第 3 个因并行上限不可取
        assert s.next() is None
        assert s.running_count == 2

    def test_complete(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        assert s.complete(task.task_id) is True
        assert task.status == TaskStatus.COMPLETED
        assert s.running_count == 0
        assert s.complete_count == 1

    def test_complete_not_running(self):
        s = EvolutionScheduler()
        assert s.complete("nonexistent") is False

    def test_fail_with_retry(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        assert s.fail(task.task_id, "test error") is True
        assert task.status == TaskStatus.QUEUED  # 重新入队
        assert task.retry_count == 1
        assert s.fail_count == 1
        assert s.retry_count == 1
        assert s.get_queue_size() == 1  # 回到队列

    def test_fail_exceed_retries(self):
        s = EvolutionScheduler(max_retries=2)
        task = _make_task(genome_id="g001", max_retries=2)
        s.submit(task)
        s.next()
        s.fail(task.task_id, "e1")  # retry 1
        s.next()
        s.fail(task.task_id, "e2")  # retry 2
        s.next()
        s.fail(task.task_id, "e3")  # exceed
        assert task.retry_count == 2
        assert task.status == TaskStatus.FAILED
        assert task.error == "e3"
        assert s.get_queue_size() == 0  # 不再入队

    def test_fail_not_running(self):
        s = EvolutionScheduler()
        assert s.fail("nonexistent") is False

    def test_retry_priority_decay(self):
        """重试时优先级降低 10。"""
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001", priority=80)
        s.submit(task)
        s.next()
        s.fail(task.task_id, "error")
        assert task.priority == 70  # 80 - 10

    def test_cancel_running(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        assert s.cancel(task.task_id) is True
        assert task.status == TaskStatus.CANCELLED
        assert s.running_count == 0

    def test_cancel_queued(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        assert s.cancel(task.task_id) is True
        assert task.status == TaskStatus.CANCELLED
        assert s.get_queue_size() == 0

    def test_cancel_nonexistent(self):
        s = EvolutionScheduler()
        assert s.cancel("nonexistent") is False

    # ── Tick ──────────────────────────────────────────────

    def test_tick(self):
        s = EvolutionScheduler(max_parallel=3)
        for i in range(3):
            s.submit(_make_task(genome_id=f"g{i}"))
        started = s.tick()
        assert len(started) == 3
        assert s.running_count == 3
        assert s.get_queue_size() == 0

    def test_tick_partial(self):
        s = EvolutionScheduler(max_parallel=2)
        for i in range(3):
            s.submit(_make_task(genome_id=f"g{i}"))
        started = s.tick()
        assert len(started) == 2
        assert s.get_queue_size() == 1

    def test_tick_all(self):
        s = EvolutionScheduler(max_parallel=5)
        for i in range(5):
            s.submit(_make_task(genome_id=f"g{i}"))
        started = s.tick_all()
        assert len(started) == 5
        assert s.get_queue_size() == 0

    def test_tick_with_executor(self):
        """tick 调用 executor 回调。"""
        executor = MagicMock()
        s = EvolutionScheduler(max_parallel=2, executor=executor)
        s.submit(_make_task(genome_id="g001"))
        s.submit(_make_task(genome_id="g002"))
        s.tick()
        assert executor.call_count == 2

    def test_tick_executor_error(self):
        """executor 抛异常 → fail + retry。"""
        def failing_executor(task):
            raise RuntimeError("boom")

        s = EvolutionScheduler(max_parallel=1, max_retries=1, executor=failing_executor)
        s.submit(_make_task(genome_id="g001"))
        s.tick()
        assert s.fail_count == 1

    # ── 回调 ──────────────────────────────────────────────

    def test_on_complete_callback(self):
        on_complete = MagicMock()
        s = EvolutionScheduler(on_complete=on_complete)
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        s.complete(task.task_id)
        on_complete.assert_called_once()

    def test_on_fail_callback(self):
        on_fail = MagicMock()
        s = EvolutionScheduler(on_fail=on_fail)
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        s.fail(task.task_id, "error")
        on_fail.assert_called_once()

    def test_on_cancel_callback(self):
        on_cancel = MagicMock()
        s = EvolutionScheduler(on_cancel=on_cancel)
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.cancel(task.task_id)
        on_cancel.assert_called_once()

    # ── 查询 ──────────────────────────────────────────────

    def test_get_task(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        found = s.get_task(task.task_id)
        assert found is not None
        assert found.genome_id == "g001"

    def test_get_task_history(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        s.complete(task.task_id)
        # 完成后仍在 history 中
        found = s.get_task(task.task_id)
        assert found is not None
        assert found.status == TaskStatus.COMPLETED

    def test_get_running_tasks(self):
        s = EvolutionScheduler()
        for i in range(3):
            s.submit(_make_task(genome_id=f"g{i}"))
        s.tick_all()
        assert len(s.get_running_tasks()) == 3

    def test_get_pending_count(self):
        s = EvolutionScheduler()
        s.submit(_make_task(genome_id="g001"))
        s.submit(_make_task(genome_id="g002"))
        s.next()
        assert s.get_pending_count() == 2  # 1 running + 1 queued

    def test_get_tasks_by_genome(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        found = s.get_tasks_by_genome("g001")
        assert len(found) == 1

    def test_get_tasks_by_status(self):
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        s.next()
        s.complete(task.task_id)
        completed = s.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed) == 1

    # ── 属性 ──────────────────────────────────────────────

    def test_available_slots(self):
        s = EvolutionScheduler(max_parallel=3)
        assert s.available_slots == 3
        s.submit(_make_task(genome_id="g001"))
        s.next()
        assert s.available_slots == 2

    def test_running_count(self):
        s = EvolutionScheduler()
        s.submit(_make_task(genome_id="g001"))
        s.next()
        assert s.running_count == 1

    # ── Stats ─────────────────────────────────────────────

    def test_get_stats(self):
        s = EvolutionScheduler(max_parallel=3)
        s.submit(_make_task(genome_id="g001"))
        s.next()
        stats = s.get_stats()
        assert stats["queue_size"] == 0
        assert stats["running_count"] == 1
        assert stats["max_parallel"] == 3
        assert stats["submit_count"] == 1

    def test_reset(self):
        s = EvolutionScheduler()
        s.submit(_make_task(genome_id="g001"))
        s.next()
        s.reset()
        assert s.submit_count == 0
        assert s.running_count == 0
        assert s.get_queue_size() == 0

    def test_repr(self):
        s = EvolutionScheduler(max_parallel=3)
        s.submit(_make_task(genome_id="g001"))
        r = repr(s)
        assert "queue=1" in r
        assert "slots=3/3" in r


# ═══════════════════════════════════════════════════════════
# 6. Controller Integration
# ═══════════════════════════════════════════════════════════

class TestControllerSchedulerIntegration:
    """Controller schedule_evolution 测试。"""

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

    def test_schedule_evolution(self, controller):
        """schedule_evolution 返回 policy_result + tasks。"""
        signals = [
            _make_winner_signal("g_w"),
            _make_improve_signal("g_a"),
            _make_failure_signal("g_l"),
        ]
        fitness_map = {
            "g_w": _make_winner_fitness("g_w"),
            "g_a": _make_avg_fitness("g_a"),
            "g_l": _make_low_fitness("g_l"),
        }
        result = controller.schedule_evolution(signals, fitness_map)

        assert "policy_result" in result
        assert "tasks" in result
        assert "scheduled_count" in result
        # g_w=EXPLOIT(active) + g_a=MUTATE(active) + g_l=EXPLORE(active) → 3
        assert result["scheduled_count"] == 3
        assert all(isinstance(t, EvolutionTask) for t in result["tasks"])

    def test_schedule_evolution_and_tick(self, controller):
        """schedule_evolution_and_tick 返回 started_count。"""
        signals = [
            _make_winner_signal("g_w"),
            _make_improve_signal("g_a"),
        ]
        fitness_map = {
            "g_w": _make_winner_fitness("g_w"),
            "g_a": _make_avg_fitness("g_a"),
        }
        result = controller.schedule_evolution_and_tick(signals, fitness_map)

        assert result["scheduled_count"] == 2
        assert result["started_count"] == 2  # max_parallel=5, 2 tasks fit

    def test_schedule_evolution_all_keep(self, controller):
        """所有 KEEP → 无任务调度。"""
        signals = [
            LearningSignal(genome_id="g_k1", direction=LearningDirection.KEEP, confidence=0.5),
        ]
        result = controller.schedule_evolution(signals, None)
        assert result["scheduled_count"] == 0

    def test_scheduler_property(self, controller):
        assert isinstance(controller.scheduler, EvolutionScheduler)


# ═══════════════════════════════════════════════════════════
# 7. Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路：PolicyDecision → Task → Scheduler → Execute。"""

    def test_pipeline_decision_to_task(self):
        """PolicyDecision → TaskFactory → EvolutionTask。"""
        decision = _make_decision(genome_id="g001", action=EvolutionAction.EXPLOIT)
        task = TaskFactory.create(decision)
        assert task.genome_id == "g001"
        assert task.action == "exploit"
        assert task.priority == 80

    def test_pipeline_submit_to_complete(self):
        """Submit → Next → Complete。"""
        s = EvolutionScheduler()
        task = _make_task(genome_id="g001")
        s.submit(task)
        assert task.status == TaskStatus.QUEUED
        next_task = s.next()
        assert next_task.status == TaskStatus.RUNNING
        s.complete(task.task_id)
        assert task.status == TaskStatus.COMPLETED

    def test_pipeline_submit_to_fail_to_retry(self):
        """Submit → Next → Fail → Retry → Complete。"""
        s = EvolutionScheduler(max_retries=3)
        task = _make_task(genome_id="g001", priority=60)
        s.submit(task)
        s.next()
        s.fail(task.task_id, "error")
        assert task.retry_count == 1
        assert task.priority == 50  # decayed
        # 重试
        next_task = s.next()
        assert next_task.task_id == task.task_id
        assert next_task.retry_count == 1
        s.complete(task.task_id)
        assert task.status == TaskStatus.COMPLETED

    def test_pipeline_priority_execution_order(self):
        """验证优先级执行顺序：RETIRE > EXPLOIT > MUTATE > EXPLORE"""
        s = EvolutionScheduler(max_parallel=4)
        decisions = [
            _make_decision(genome_id="g_explore", action=EvolutionAction.EXPLORE),
            _make_decision(genome_id="g_mutate", action=EvolutionAction.MUTATE),
            _make_decision(genome_id="g_exploit", action=EvolutionAction.EXPLOIT),
            _make_decision(genome_id="g_retire", action=EvolutionAction.RETIRE),
        ]
        s.submit_policies(decisions)
        order = []
        while True:
            task = s.next()
            if task is None:
                break
            order.append(task.genome_id)
        assert order == ["g_retire", "g_exploit", "g_mutate", "g_explore"]

    def test_pipeline_tick_all_with_completion(self):
        """Tick all → 全部完成。"""
        s = EvolutionScheduler(max_parallel=3)
        for i in range(3):
            s.submit(_make_task(genome_id=f"g{i}"))
        started = s.tick_all()
        assert len(started) == 3
        for task in started:
            s.complete(task.task_id)
        assert s.complete_count == 3
        assert s.running_count == 0


# ═══════════════════════════════════════════════════════════
# 8. Package Exports
# ═══════════════════════════════════════════════════════════

def test_package_exports():
    """__init__.py 导出所有核心类。"""
    import market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler as s

    assert hasattr(s, "EvolutionTask")
    assert hasattr(s, "TaskStatus")
    assert hasattr(s, "TaskFactory")
    assert hasattr(s, "VALID_TRANSITIONS")
    assert hasattr(s, "EvolutionPriorityQueue")
    assert hasattr(s, "EvolutionScheduler")