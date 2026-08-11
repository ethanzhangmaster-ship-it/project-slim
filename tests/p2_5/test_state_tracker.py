"""P2.5.3 — Execution State Tracker 状态机验收。"""

import pytest

from src.execution.monitor.models import (
    STATE_AUTHORIZED,
    STATE_BLOCKED,
    STATE_CREATED,
    STATE_ESCALATED,
    STATE_FAILED,
    STATE_ROLLBACK,
    STATE_ROLLED_BACK,
    STATE_RUNNING,
    STATE_SUCCESS,
    IllegalStateTransitionError,
)
from src.execution.monitor.state_tracker import (
    ExecutionStateTracker,
    TrackedState,
    validate_transition,
)
from src.execution.safe_executor.models import (
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
)
from tests.p2_5.conftest import make_outcome

# verdict -> 期望 P2.5 终态
EXPECTED_FINAL = {
    VERDICT_EXECUTED: STATE_SUCCESS,
    VERDICT_RETURN_EXISTING: STATE_SUCCESS,
    VERDICT_BLOCKED: STATE_BLOCKED,
    VERDICT_ROLLED_BACK: STATE_ROLLED_BACK,
    VERDICT_ESCALATED: STATE_ESCALATED,
    VERDICT_FAILED: STATE_FAILED,
}


@pytest.mark.parametrize("verdict,expected", list(EXPECTED_FINAL.items()))
def test_track_final_state(verdict, expected):
    o = make_outcome(verdict)
    tracked = ExecutionStateTracker().track_execution(o)
    assert isinstance(tracked, TrackedState)
    assert tracked.final_state == expected
    assert tracked.is_terminal is True
    assert tracked.legal is True


def test_trajectory_maps_ctx_to_p25():
    o = make_outcome(VERDICT_EXECUTED)
    tracked = ExecutionStateTracker().track_execution(o)
    assert tracked.trajectory[0] == STATE_CREATED
    assert STATE_AUTHORIZED in tracked.trajectory
    assert STATE_RUNNING in tracked.trajectory
    assert tracked.trajectory[-1] == STATE_SUCCESS


def test_validate_transition_legal():
    validate_transition(STATE_CREATED, STATE_AUTHORIZED)
    validate_transition(STATE_AUTHORIZED, STATE_SUCCESS)  # 幂等命中
    validate_transition(STATE_RUNNING, STATE_FAILED)
    validate_transition(STATE_FAILED, STATE_ROLLBACK)
    validate_transition(STATE_FAILED, STATE_ESCALATED)


def test_validate_transition_illegal():
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(STATE_SUCCESS, STATE_RUNNING)
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(STATE_CREATED, STATE_SUCCESS)
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(STATE_BLOCKED, STATE_RUNNING)


def test_same_state_transition_ok():
    # 同态迁移允许（RUNNING -> RUNNING 在 P2.4 多步里常见）
    validate_transition(STATE_RUNNING, STATE_RUNNING)


def test_step_builds_trajectory():
    tr = ExecutionStateTracker()
    traj = tr.step("exe_1", STATE_AUTHORIZED)
    assert traj == [STATE_CREATED, STATE_AUTHORIZED]
    traj2 = tr.step("exe_1", STATE_RUNNING)
    assert traj2[-1] == STATE_RUNNING


def test_step_illegal_raises():
    tr = ExecutionStateTracker()
    tr.step("exe_2", STATE_BLOCKED)
    with pytest.raises(IllegalStateTransitionError):
        tr.step("exe_2", STATE_RUNNING)  # BLOCKED 为终态，不可再迁移


def test_get_trajectory_persisted():
    o = make_outcome(VERDICT_ROLLED_BACK)
    tr = ExecutionStateTracker()
    tr.track_execution(o)
    traj = tr.get_trajectory(o.context.execution_id)
    assert traj is not None
    assert traj[-1] == STATE_ROLLED_BACK
