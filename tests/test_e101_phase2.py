"""E10.1 Phase 2 Acceptance Test — Execution Engine"""
import sys
import time
import pathlib
sys.path.insert(0, 'src')

from market_ops.execution_runtime import (
    ExecutionEngine, MockPlatformAdapter,
    ExecutionTask, ExecutionResult, ExecutionEvent,
    ExecutionStatus, ActionType, EventType,
    from_growth_action, ExecutionExporter,
)

# ── Helpers ────────────────────────────────────────────────

def _make_action(cid: str, action: str, budget_before: float = 100.0,
                 budget_after: float = 200.0, risk: str = "SAFE",
                 reasons: list[str] | None = None) -> dict:
    if reasons is None:
        reasons = [action]
    return {
        "creative_id": cid,
        "action": action,
        "budget_change": {"current": budget_before, "target": budget_after},
        "confidence": 0.95,
        "reason": reasons,
        "risk_level": risk,
    }


# ═══════════════════════════════════════════════════════════
# AC1: ExecutionEngine creates tasks
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC1: ExecutionEngine Creates Tasks")
print("=" * 50)

engine = ExecutionEngine()

task = engine.create_task(_make_action("C001", "SCALE"))
assert task.task_id, "No task_id"
assert task.status == ExecutionStatus.CREATED.value
assert task.action_type == "SCALE"
assert task.creative_id == "C001"
print(f"  Created: {task.task_id[:8]}... action={task.action_type}, status={task.status}")

# Batch creation
actions = [
    _make_action("C001", "SCALE"),
    _make_action("C002", "KILL", budget_after=0.0),
    _make_action("C003", "WATCH", budget_after=100.0),
    _make_action("C004", "RETEST", budget_after=50.0),
]
engine2 = ExecutionEngine()
tasks = engine2.create_tasks(actions)
assert len(tasks) == 4
assert all(t.status == ExecutionStatus.CREATED.value for t in tasks)
print(f"  Batch: {len(tasks)} tasks created")

print("AC1: ExecutionEngine Creates Tasks — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC2: SCALE complete state chain
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC2: SCALE Complete State Chain")
print("=" * 50)

engine_scale = ExecutionEngine()
task_scale = engine_scale.create_task(_make_action("S001", "SCALE"))

result = engine_scale.execute(task_scale)
assert result.status == ExecutionStatus.COMPLETED.value
assert result.platform_response.get("verified") is True
assert result.actual_change["before"] == 100.0
assert result.actual_change["after"] == 200.0
print(f"  Result: {result.status}, budget={result.actual_change}")

# Verify state chain via events
events = engine_scale.get_events_for_task(task_scale.task_id)
states = [e.new_state for e in events]
print(f"  State chain: {' → '.join(states)}")

# Expected chain: CREATED → APPROVED → EXECUTING → VERIFYING → COMPLETED
expected_states = ["CREATED", "APPROVED", "EXECUTING", "VERIFYING", "COMPLETED"]
assert states == expected_states, f"Expected {expected_states}, got {states}"
assert len(events) == 5  # 5 state changes

print("AC2: SCALE Complete State Chain — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC3: KILL complete state chain
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC3: KILL Complete State Chain")
print("=" * 50)

engine_kill = ExecutionEngine()
task_kill = engine_kill.create_task(_make_action("K001", "KILL", budget_after=0.0))

# Phase 3: KILL always requires HUMAN approval, so first execute blocks
result_kill_pending = engine_kill.execute(task_kill)
assert result_kill_pending.status == ExecutionStatus.PENDING_APPROVAL.value
print(f"  First execute: {result_kill_pending.status} (blocked by ApprovalGate)")

# Approve manually, then re-execute
engine_kill.approve_task(task_kill.task_id, approved_by="ops_lead")
result_kill = engine_kill.execute(task_kill)

assert result_kill.status == ExecutionStatus.COMPLETED.value
assert result_kill.actual_change["after"] == 0.0
assert result_kill.platform_response.get("verified") is True
print(f"  After approval: {result_kill.status}, actual_change={result_kill.actual_change}")

events_kill = engine_kill.get_events_for_task(task_kill.task_id)
states_kill = [e.new_state for e in events_kill]
print(f"  State chain: {' → '.join(states_kill)}")
assert "COMPLETED" in states_kill

print("AC3: KILL Complete State Chain — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC4: WATCH / RETEST
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC4: WATCH / RETEST")
print("=" * 50)

# WATCH: no execution, goes directly to COMPLETED
engine_watch = ExecutionEngine()
task_watch = engine_watch.create_task(_make_action("W001", "WATCH", budget_after=100.0))
result_watch = engine_watch.execute(task_watch)
assert result_watch.status == ExecutionStatus.COMPLETED.value
assert result_watch.platform_response.get("noop") is True

events_watch = engine_watch.get_events_for_task(task_watch.task_id)
states_watch = [e.new_state for e in events_watch]
print(f"  WATCH chain: {' → '.join(states_watch)}")
assert "EXECUTING" not in states_watch  # No execution step
assert "COMPLETED" in states_watch

# RETEST: no execution, goes directly to COMPLETED
engine_retest = ExecutionEngine()
task_retest = engine_retest.create_task(_make_action("R001", "RETEST", budget_after=50.0))
result_retest = engine_retest.execute(task_retest)
assert result_retest.status == ExecutionStatus.COMPLETED.value

events_retest = engine_retest.get_events_for_task(task_retest.task_id)
states_retest = [e.new_state for e in events_retest]
print(f"  RETEST chain: {' → '.join(states_retest)}")
assert "EXECUTING" not in states_retest
assert "COMPLETED" in states_retest

print("AC4: WATCH / RETEST — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC5: Failure → Rollback
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC5: Failure → Rollback")
print("=" * 50)

# Use adapter with 100% failure rate
failing_adapter = MockPlatformAdapter(failure_rate=1.0)
engine_fail = ExecutionEngine(adapter=failing_adapter)
task_fail = engine_fail.create_task(_make_action("F001", "SCALE"))

result_fail = engine_fail.execute(task_fail)
assert result_fail.status == ExecutionStatus.ROLLED_BACK.value
assert result_fail.error_message.startswith("Mock adapter: simulated random failure")
print(f"  Result: {result_fail.status}, error={result_fail.error_message}")

# Verify failure → rollback chain
events_fail = engine_fail.get_events_for_task(task_fail.task_id)
states_fail = [e.new_state for e in events_fail]
print(f"  State chain: {' → '.join(states_fail)}")

assert "EXECUTING" in states_fail
assert "FAILED" in states_fail
assert "ROLLBACK_PENDING" in states_fail
assert "ROLLED_BACK" in states_fail
assert "COMPLETED" not in states_fail  # Failed → never completed

print("AC5: Failure → Rollback — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC6: Event Log Complete
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC6: Event Log Complete")
print("=" * 50)

# Run a full cycle with multiple tasks
engine_events = ExecutionEngine()
actions_events = [
    _make_action("E001", "SCALE"),
    _make_action("E002", "KILL", budget_after=0.0),
    _make_action("E003", "WATCH", budget_after=100.0),
]
tasks_events = engine_events.create_tasks(actions_events)
results_events = engine_events.execute_all(tasks_events)

all_events = engine_events.events
print(f"  Total events: {len(all_events)}")

# Each SCALE: 5 events (CREATED→APPROVED→EXECUTING→VERIFYING→COMPLETED)
# Each KILL: 2 events (CREATED→PENDING_APPROVAL) — blocked by ApprovalGate
# Each WATCH: 3 events (CREATED→APPROVED→COMPLETED)
# Total: 5 + 2 + 3 = 10
assert len(all_events) == 10, f"Expected 10 events, got {len(all_events)}"

# Verify event structure
for e in all_events:
    assert e.event_id, "Missing event_id"
    assert e.task_id, "Missing task_id"
    assert e.timestamp, "Missing timestamp"
    assert e.event_type == EventType.STATE_CHANGED.value
    assert e.new_state, "Missing new_state"

# Verify events per task
scale_events = engine_events.get_events_for_task(tasks_events[0].task_id)
assert len(scale_events) == 5
print(f"  SCALE events: {len(scale_events)}")

kill_events = engine_events.get_events_for_task(tasks_events[1].task_id)
assert len(kill_events) == 2
print(f"  KILL events: {len(kill_events)} (blocked at PENDING_APPROVAL)")

watch_events = engine_events.get_events_for_task(tasks_events[2].task_id)
assert len(watch_events) == 3
print(f"  WATCH events: {len(watch_events)}")

# Export events
exporter = ExecutionExporter()
path = exporter.export_events(all_events, filename="phase2_events.json")
print(f"  Exported: {path}")

print("AC6: Event Log Complete — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC7: No Real Platform API
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC7: No Real Platform API")
print("=" * 50)

e101_dir = pathlib.Path('src/market_ops/execution_runtime')
platform_keywords = [
    'facebook', 'google_ads_api', 'tiktok', 'requests.post',
    'requests.get', 'httpx', 'aiohttp', 'oauth', 'access_token', 'app_secret',
]

violations = []
for py_file in e101_dir.glob('*.py'):
    code = py_file.read_text(encoding='utf-8')
    for kw in platform_keywords:
        idx = code.lower().find(kw)
        if idx >= 0:
            # Check if in comment/docstring
            line_start = code.rfind('\n', 0, idx) + 1
            line = code[line_start:code.find('\n', idx)].strip()
            if not line.startswith('#') and not line.startswith('"""') and not line.startswith('*'):
                # Exclude false positives like self._requests.get(...)
                if kw == 'requests.get' and '_requests.get' in line.lower():
                    continue
                violations.append(f"{py_file.name}: {kw}")

assert len(violations) == 0, f"Platform API violations: {violations}"
print("  NO real platform API calls")
print("  NO HTTP requests, OAuth, tokens")
print("  Mock adapter only")

print("AC7: No Real Platform API — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC8: 1000 tasks < 5s
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC8: 1000 Tasks < 5s")
print("=" * 50)

engine_perf = ExecutionEngine()
perf_actions = []
for i in range(1000):
    perf_actions.append(_make_action(
        f"PERF_{i:04d}",
        ["SCALE", "KILL", "WATCH", "RETEST"][i % 4],
        budget_after=200.0 if i % 4 == 0 else 0.0 if i % 4 == 1 else 100.0,
    ))

start = time.perf_counter()
perf_tasks = engine_perf.create_tasks(perf_actions)
perf_results = engine_perf.execute_all(perf_tasks)
elapsed = time.perf_counter() - start

completed = sum(1 for r in perf_results if r.status == "COMPLETED")
rolled_back = sum(1 for r in perf_results if r.status == "ROLLED_BACK")
pending = sum(1 for r in perf_results if r.status == "PENDING_APPROVAL")
failed = sum(1 for r in perf_results if r.status == "FAILED")

print(f"  Tasks: {len(perf_tasks)}")
print(f"  Results: COMPLETED={completed}, ROLLED_BACK={rolled_back}, PENDING={pending}, FAILED={failed}")
print(f"  Time: {elapsed:.3f}s")

assert elapsed < 5.0, f"Performance degraded: {elapsed:.3f}s > 5s"
print(f"  Performance: {elapsed:.3f}s < 5s target")

print("AC8: Performance — PASS\n")


# ═══════════════════════════════════════════════════════════
# Extra: Forbidden Transitions
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("EXTRA: Forbidden Transitions")
print("=" * 50)

from market_ops.execution_runtime.execution_engine import (
    FORBIDDEN_TRANSITIONS, VALID_TRANSITIONS,
)

# Verify forbidden transitions are enforced
assert (ExecutionStatus.COMPLETED.value, ExecutionStatus.EXECUTING.value) in FORBIDDEN_TRANSITIONS
assert (ExecutionStatus.FAILED.value, ExecutionStatus.COMPLETED.value) in FORBIDDEN_TRANSITIONS
assert (ExecutionStatus.ROLLED_BACK.value, ExecutionStatus.EXECUTING.value) in FORBIDDEN_TRANSITIONS
assert (ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value) in FORBIDDEN_TRANSITIONS

# Verify terminal states have no outgoing transitions
assert ExecutionStatus.COMPLETED.value not in VALID_TRANSITIONS or \
    len(VALID_TRANSITIONS.get(ExecutionStatus.COMPLETED.value, [])) == 0
assert ExecutionStatus.ROLLED_BACK.value not in VALID_TRANSITIONS or \
    len(VALID_TRANSITIONS.get(ExecutionStatus.ROLLED_BACK.value, [])) == 0

print("  COMPLETED → EXECUTING: FORBIDDEN")
print("  FAILED → COMPLETED: FORBIDDEN")
print("  COMPLETED: terminal state (no outgoing)")
print("  ROLLED_BACK: terminal state (no outgoing)")
print("EXTRA: Forbidden Transitions — PASS\n")


# ═══════════════════════════════════════════════════════════
print(f"\n{'=' * 50}")
print(f"E10.1 Phase 2: 8/8 PASS")
print(f"{'=' * 50}")