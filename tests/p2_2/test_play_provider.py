"""P2.2：Play Provider 执行纪律（关键安全约束）。

Play Provider **永不直接发布到 Google Play**：
- CREATE_RELEASE 只生成一份 ReleaseTask 工单
- 无论 DRY_RUN 还是 PRODUCTION，real_api_called 永远 False
- 这是「大脑提案，人落子」在发布域的硬编码边界
"""
import tempfile
from pathlib import Path

from src.execution.models import ExecutionAction, ExecutionDomain, ExecutionMode
from src.execution.providers import PlayExecutionProvider, JsonlReleaseStore
from src.execution.providers.result import STATUS_SUCCESS

from .conftest import make_request


def test_create_release_builds_task_dry_run():
    provider = PlayExecutionProvider()
    req = make_request(
        ExecutionAction.CREATE_RELEASE,
        mode=ExecutionMode.DRY_RUN,
        domain=ExecutionDomain.RELEASE,
        expected_impact={"release_type": "store_listing_update"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_SUCCESS
    # 关键：即使 PRODUCTION 也绝不真实发布
    assert res.real_api_called is False
    assert "task" in res.after_state
    assert res.after_state["task"]["requires_human_publish"] is True


def test_create_release_never_calls_live_store_in_production():
    provider = PlayExecutionProvider()
    req = make_request(
        ExecutionAction.CREATE_RELEASE,
        mode=ExecutionMode.PRODUCTION,
        domain=ExecutionDomain.RELEASE,
        expected_impact={"release_type": "new_build"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is False  # 永不触碰 Google Play
    assert res.after_state["task"]["game_id"] == "p04_merge_witch"


def test_release_task_persists_to_jsonl_store():
    with tempfile.TemporaryDirectory() as d:
        store = JsonlReleaseStore(Path(d) / "releases.jsonl")
        provider = PlayExecutionProvider(task_sink=store)
        req = make_request(
            ExecutionAction.CREATE_RELEASE,
            mode=ExecutionMode.DRY_RUN,
            domain=ExecutionDomain.RELEASE,
            expected_impact={"release_type": "store_listing_update"},
        )
        res = provider.execute(req)
        assert res.real_api_called is False
        stored = store.all()
        assert len(stored) == 1
        assert stored[0]["game_id"] == "p04_merge_witch"
        assert stored[0]["requires_human_publish"] is True
