"""MetaAds 真实平台调用场景测试。

验证 SafetyGate 的预算边界和审批逻辑在真实 MetaAds 场景下是否生效。

测试场景:
  1. SafetyGate 预算边界 — 最低预算 / 最大升幅 / 最大降幅
  2. SafetyGate 审批等级 — 自动通过 / 需要确认 / 需要审批
  3. MetaAdsPlatformAdapter — V2→V1 转换正确性
  4. ActionExecutor + MetaAds 全链路 — 执行/验证/回滚
  5. 安全边界阻断 — 超出边界时动作被跳过，不调用 API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from scripts.action_planner import ActionStatus, ActionType, ExecutionAction
from scripts.action_executor import (
    ActionExecutionStatus,
    ActionExecutor,
    SafetyGate,
)
from scripts.meta_ads_adapter import MetaAdsPlatformAdapter
from market_ops.execution_runtime.adapters.facebook import FacebookClient
from market_ops.execution_runtime.adapters.facebook.facebook_config import (
    FacebookConfig,
)


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────


def _make_meta_action(
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    adset_id: str = "120209876543210",
    creative_id: str = "c_meta_001",
    target_budget: float = 140.0,
    current_budget: float = 200.0,
    approval_level: int = 0,
    risk_level: str = "low",
) -> ExecutionAction:
    """构造一个真实 MetaAds 场景的 ExecutionAction。

    adset_id 使用真实的 Facebook campaign_id 格式 (15+ 位数字)。
    """
    return ExecutionAction(
        strategy_id="strat_meta_001",
        hypothesis_id="hyp_meta_001",
        diagnosis_id="diag_meta_001",
        signal_id="fs_meta_001",
        creative_id=creative_id,
        adset_id=adset_id,
        action_type=action_type,
        parameters={
            "target_budget": target_budget,
            "current_budget": current_budget,
        } if action_type == ActionType.UPDATE_BUDGET else {},
        confidence=0.78,
        risk_level=risk_level,
        expected_impact={"metric": "roas", "direction": "positive"},
        reason="MetaAds safety gate verification",
        budget_impact=target_budget - current_budget,
        approval_level=approval_level,
        requires_approval=approval_level > 0,
        status=ActionStatus.PENDING,
    )


def _make_sandbox_client() -> FacebookClient:
    """创建 sandbox 模式的 FacebookClient — 不发出真实 HTTP 请求。"""
    return FacebookClient(FacebookConfig(sandbox=True))


# ──────────────────────────────────────────────
# SafetyGate 预算边界验证
# ──────────────────────────────────────────────


class TestSafetyGateBudgetBoundaries:
    """验证 SafetyGate 在真实 MetaAds 预算场景下的边界检查。"""

    def test_normal_budget_reduce_passes(self):
        """正常降幅 (30%) 通过安全检查。"""
        gate = SafetyGate()
        action = _make_meta_action(
            target_budget=140.0,
            current_budget=200.0,  # 降 30%
        )
        passed, reason = gate.check(action)
        assert passed is True
        assert "passed" in reason.lower()

    def test_budget_reduce_at_max_boundary_passes(self):
        """降幅恰好等于 50% 边界 → 通过。"""
        gate = SafetyGate(max_budget_reduce_pct=0.50)
        action = _make_meta_action(
            target_budget=100.0,
            current_budget=200.0,  # 降 50% = 边界
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_budget_reduce_exceeds_max_blocked(self):
        """降幅 60% 超过 50% 上限 → 被阻断。"""
        gate = SafetyGate(max_budget_reduce_pct=0.50)
        action = _make_meta_action(
            target_budget=80.0,
            current_budget=200.0,  # 降 60%
        )
        passed, reason = gate.check(action)
        assert passed is False
        assert "reduce" in reason.lower()

    def test_extreme_budget_reduce_blocked(self):
        """极端降幅 90% → 被阻断。"""
        gate = SafetyGate()
        action = _make_meta_action(
            target_budget=20.0,
            current_budget=200.0,  # 降 90%
        )
        passed, reason = gate.check(action)
        assert passed is False

    def test_budget_increase_within_limit_passes(self):
        """正常升幅 (20%) 通过安全检查。"""
        gate = SafetyGate(max_budget_increase_pct=0.30)
        action = _make_meta_action(
            target_budget=240.0,
            current_budget=200.0,  # 升 20%
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_budget_increase_at_max_boundary_passes(self):
        """升幅恰好等于 30% 边界 → 通过。"""
        gate = SafetyGate(max_budget_increase_pct=0.30)
        action = _make_meta_action(
            target_budget=260.0,
            current_budget=200.0,  # 升 30% = 边界
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_budget_increase_exceeds_max_blocked(self):
        """升幅 50% 超过 30% 上限 → 被阻断。"""
        gate = SafetyGate(max_budget_increase_pct=0.30)
        action = _make_meta_action(
            target_budget=300.0,
            current_budget=200.0,  # 升 50%
        )
        passed, reason = gate.check(action)
        assert passed is False
        assert "increase" in reason.lower()

    def test_budget_below_minimum_blocked(self):
        """目标预算低于最低限额 → 被阻断。"""
        gate = SafetyGate(min_budget=20.0)
        action = _make_meta_action(
            target_budget=10.0,
            current_budget=200.0,  # $10 < $20 最低限额
        )
        passed, reason = gate.check(action)
        assert passed is False
        assert "minimum" in reason.lower()

    def test_budget_at_minimum_boundary_passes(self):
        """目标预算恰好等于最低限额 → 通过 (但需同时满足降幅限制)。"""
        gate = SafetyGate(min_budget=20.0, max_budget_reduce_pct=0.95)
        action = _make_meta_action(
            target_budget=20.0,
            current_budget=200.0,  # $20 = 最低限额, 降 90% < 95%
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_zero_current_budget_skip_pct_check(self):
        """current_budget=0 时跳过百分比检查 (新建广告组场景)。"""
        gate = SafetyGate()
        action = _make_meta_action(
            target_budget=50.0,
            current_budget=0.0,  # 新建 → 0
        )
        passed, _ = gate.check(action)
        assert passed is True


# ──────────────────────────────────────────────
# SafetyGate 审批等级验证
# ──────────────────────────────────────────────


class TestSafetyGateApprovalLevels:
    """验证 SafetyGate 在不同审批等级下的行为。"""

    def test_auto_approve_level_0_passes(self):
        """approval_level=0 (自动) → 自动通过。"""
        gate = SafetyGate(auto_approve_max_level=0)
        action = _make_meta_action(approval_level=0)
        passed, _ = gate.check(action)
        assert passed is True

    def test_approval_level_1_blocked_when_auto_max_0(self):
        """approval_level=1 (确认) 但 auto_max=0 → 需要人工确认。"""
        gate = SafetyGate(auto_approve_max_level=0)
        action = _make_meta_action(approval_level=1)
        passed, reason = gate.check(action)
        assert passed is False
        assert "Approval" in reason
        assert "level 1" in reason

    def test_approval_level_2_blocked_when_auto_max_0(self):
        """approval_level=2 (审批) 但 auto_max=0 → 需要人工审批。"""
        gate = SafetyGate(auto_approve_max_level=0)
        action = _make_meta_action(approval_level=2)
        passed, reason = gate.check(action)
        assert passed is False
        assert "Approval" in reason
        assert "level 2" in reason

    def test_approval_level_1_passes_when_auto_max_1(self):
        """approval_level=1 且 auto_max=1 → 自动通过。"""
        gate = SafetyGate(auto_approve_max_level=1)
        action = _make_meta_action(approval_level=1)
        passed, _ = gate.check(action)
        assert passed is True

    def test_approval_level_2_blocked_when_auto_max_1(self):
        """approval_level=2 但 auto_max=1 → 仍需审批。"""
        gate = SafetyGate(auto_approve_max_level=1)
        action = _make_meta_action(approval_level=2)
        passed, reason = gate.check(action)
        assert passed is False
        assert "level 2" in reason

    def test_pause_campaign_no_budget_check(self):
        """PAUSE_CAMPAIGN 不受预算边界检查 (无论预算多少)。"""
        gate = SafetyGate(min_budget=10000.0)  # 极高最低预算
        action = _make_meta_action(
            action_type=ActionType.PAUSE_CAMPAIGN,
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_resume_campaign_no_budget_check(self):
        """RESUME_CAMPAIGN 不受预算边界检查。"""
        gate = SafetyGate(min_budget=10000.0)
        action = _make_meta_action(
            action_type=ActionType.RESUME_CAMPAIGN,
        )
        passed, _ = gate.check(action)
        assert passed is True

    def test_high_risk_action_still_executes_if_approval_ok(self):
        """高风险动作在审批通过后仍可执行 (SafetyGate 只检查 approval_level)。"""
        gate = SafetyGate(auto_approve_max_level=2)
        action = _make_meta_action(
            approval_level=2,
            risk_level="critical",
            target_budget=260.0,
            current_budget=200.0,  # 升 30%
        )
        passed, _ = gate.check(action)
        assert passed is True


# ──────────────────────────────────────────────
# MetaAdsPlatformAdapter 转换验证
# ──────────────────────────────────────────────


class TestMetaAdsAdapterConversion:
    """验证 V2 ExecutionAction → V1 FacebookClient API 调用的转换正确性。"""

    def test_update_budget_dollars_to_cents(self):
        """验证美元 → cents 转换: $140.00 → 14000 cents。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(
            target_budget=140.00,
            current_budget=200.00,
        )
        resp = adapter.execute(action)

        assert resp["status"] == "ok"
        # V1 sandbox mock 返回 daily_budget 为 cents 字符串
        # MetaAdsPlatformAdapter 将其转回美元
        assert resp["data"]["budget"] == pytest.approx(140.00, abs=0.01)

    def test_update_budget_decimal_amount(self):
        """验证小数金额转换: $99.99 → 9999 cents。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(
            target_budget=99.99,
            current_budget=150.00,
        )
        resp = adapter.execute(action)
        assert resp["status"] == "ok"
        assert resp["data"]["budget"] == pytest.approx(99.99, abs=0.01)

    def test_pause_campaign(self):
        """验证暂停广告: campaign_id → POST status=PAUSED。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(action_type=ActionType.PAUSE_CAMPAIGN)
        resp = adapter.execute(action)

        assert resp["status"] == "ok"
        assert resp["data"]["status"] == "paused"
        assert resp["data"]["adset_id"] == "120209876543210"

    def test_resume_campaign(self):
        """验证恢复广告: campaign_id → POST status=ACTIVE。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(action_type=ActionType.RESUME_CAMPAIGN)
        resp = adapter.execute(action)

        assert resp["status"] == "ok"
        assert resp["data"]["status"] == "active"

    def test_verify_update_budget_success(self):
        """验证 execute 后 verify 能确认预算已更新 (sandbox 有状态 mock)。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(
            target_budget=150.00,
            current_budget=200.00,
        )
        resp = adapter.execute(action)
        verified = adapter.verify(action, resp)

        # sandbox mock 现在是有状态的 — execute 更新了预算,
        # verify 通过 get_campaign 能读到更新后的值
        assert verified is True

    def test_rollback_update_budget(self):
        """验证回滚: 恢复到 current_budget。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(
            target_budget=140.00,
            current_budget=200.00,
        )
        resp = adapter.rollback(action, {})

        assert resp["status"] == "ok"
        assert resp["data"]["budget"] == pytest.approx(200.00, abs=0.01)

    def test_rollback_pause_campaign(self):
        """验证回滚暂停: 恢复为 ACTIVE。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        action = _make_meta_action(action_type=ActionType.PAUSE_CAMPAIGN)
        resp = adapter.rollback(action, {})

        assert resp["status"] == "ok"
        assert resp["data"]["status"] == "active"

    def test_api_call_count_tracked(self):
        """验证 V1 FacebookClient 的 request_count 正确递增。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)

        assert client.request_count == 0
        adapter.execute(_make_meta_action())
        assert client.request_count == 1
        adapter.execute(_make_meta_action(action_type=ActionType.PAUSE_CAMPAIGN))
        assert client.request_count == 2


# ──────────────────────────────────────────────
# ActionExecutor + MetaAds 全链路验证
# ──────────────────────────────────────────────


class TestActionExecutorWithMetaAds:
    """验证 ActionExecutor 使用 MetaAdsPlatformAdapter 的完整执行流程。"""

    def test_normal_execution_success(self):
        """正常预算调整 (降 30%) → 安全检查通过 → 执行成功。"""
        adapter = MetaAdsPlatformAdapter(_make_sandbox_client())
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(
            target_budget=140.0,
            current_budget=200.0,
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True
        assert result.actual_budget == pytest.approx(140.0, abs=0.01)

    def test_budget_reduce_exceeds_max_skipped(self):
        """降幅超 50% → SafetyGate 阻断 → 动作跳过, 不调用 API。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(
            target_budget=50.0,
            current_budget=200.0,  # 降 75%
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert result.success is False
        assert "reduce" in result.error_message.lower()
        # 关键: API 未被调用
        assert client.request_count == 0

    def test_budget_increase_exceeds_max_skipped(self):
        """升幅超 30% → SafetyGate 阻断 → 动作跳过。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(
            target_budget=300.0,
            current_budget=200.0,  # 升 50%
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "increase" in result.error_message.lower()
        assert client.request_count == 0

    def test_budget_below_minimum_skipped(self):
        """预算低于 $20 → SafetyGate 阻断 → 动作跳过。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(
            target_budget=10.0,
            current_budget=200.0,
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "minimum" in result.error_message.lower()
        assert client.request_count == 0

    def test_approval_required_skipped(self):
        """approval_level=2 但 auto_max=0 → SafetyGate 阻断 → 动作跳过。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        gate = SafetyGate(auto_approve_max_level=0)
        executor = ActionExecutor(adapter=adapter, safety_gate=gate)

        action = _make_meta_action(
            approval_level=2,
            target_budget=140.0,
            current_budget=200.0,
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "Approval" in result.error_message
        assert "level 2" in result.error_message
        assert client.request_count == 0

    def test_approval_level_1_with_auto_max_1_executes(self):
        """approval_level=1 且 auto_max=1 → 自动通过 → 执行成功。"""
        adapter = MetaAdsPlatformAdapter(_make_sandbox_client())
        gate = SafetyGate(auto_approve_max_level=1)
        executor = ActionExecutor(adapter=adapter, safety_gate=gate)

        action = _make_meta_action(
            approval_level=1,
            target_budget=140.0,
            current_budget=200.0,
        )
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_pause_campaign_executes_without_budget_check(self):
        """PAUSE_CAMPAIGN 不受预算边界限制 → 直接执行。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(action_type=ActionType.PAUSE_CAMPAIGN)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True
        assert client.request_count >= 1

    def test_dry_run_does_not_call_api(self):
        """Dry-run 模式 → 不调用 V1 FacebookClient。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True
        assert result.dry_run is True
        # 关键: API 未被调用
        assert client.request_count == 0

    def test_batch_execution_mixed_safety_results(self):
        """批量执行: 部分通过安全检查, 部分被阻断。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        actions = [
            # 1. 正常降幅 30% → 通过
            _make_meta_action(
                adset_id="111111111111111",
                target_budget=140.0,
                current_budget=200.0,
            ),
            # 2. 降幅 75% → 阻断
            _make_meta_action(
                adset_id="222222222222222",
                target_budget=50.0,
                current_budget=200.0,
            ),
            # 3. 升幅 50% → 阻断
            _make_meta_action(
                adset_id="333333333333333",
                target_budget=300.0,
                current_budget=200.0,
            ),
            # 4. PAUSE → 通过 (无预算检查)
            _make_meta_action(
                action_type=ActionType.PAUSE_CAMPAIGN,
                adset_id="444444444444444",
            ),
        ]

        results = executor.execute_batch(actions)

        assert len(results) == 4
        assert results[0].status == ActionExecutionStatus.COMPLETED
        assert results[1].status == ActionExecutionStatus.SKIPPED
        assert results[2].status == ActionExecutionStatus.SKIPPED
        assert results[3].status == ActionExecutionStatus.COMPLETED

        # #1 和 #4 通过安全检查 → 各调用 execute(1) + verify(1) = 4 次
        # #2 和 #3 被阻断 → 0 次
        assert client.request_count == 4

    def test_full_chain_ids_preserved_in_meta_ads(self):
        """全链路 ID 在 MetaAds 执行结果中完整保留。"""
        adapter = MetaAdsPlatformAdapter(_make_sandbox_client())
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action()
        result = executor.execute(action)

        assert result.signal_id == "fs_meta_001"
        assert result.diagnosis_id == "diag_meta_001"
        assert result.hypothesis_id == "hyp_meta_001"
        assert result.strategy_id == "strat_meta_001"
        assert result.action_id == action.action_id


# ──────────────────────────────────────────────
# SafetyGate 阻断 → API 未调用 验证
# ──────────────────────────────────────────────


class TestSafetyGatePreventsApiCalls:
    """关键验证: SafetyGate 阻断时, V1 FacebookClient 的 API 确实未被调用。

    这是安全门控的核心价值: 在调用真实平台 API 之前拦截不安全操作。
    """

    def test_reduce_exceeds_max_no_api_call(self):
        """降幅超标 → API 调用次数为 0。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        executor.execute(_make_meta_action(
            target_budget=10.0, current_budget=200.0,  # 降 95%
        ))
        assert client.request_count == 0

    def test_increase_exceeds_max_no_api_call(self):
        """升幅超标 → API 调用次数为 0。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        executor.execute(_make_meta_action(
            target_budget=500.0, current_budget=200.0,  # 升 150%
        ))
        assert client.request_count == 0

    def test_below_minimum_no_api_call(self):
        """低于最低预算 → API 调用次数为 0。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        executor.execute(_make_meta_action(
            target_budget=5.0, current_budget=200.0,
        ))
        assert client.request_count == 0

    def test_approval_exceeded_no_api_call(self):
        """审批等级超标 → API 调用次数为 0。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        gate = SafetyGate(auto_approve_max_level=0)
        executor = ActionExecutor(adapter=adapter, safety_gate=gate)

        executor.execute(_make_meta_action(
            approval_level=2,
            target_budget=140.0, current_budget=200.0,
        ))
        assert client.request_count == 0

    def test_missing_adset_id_no_api_call(self):
        """缺少 adset_id → API 调用次数为 0。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        action = _make_meta_action(adset_id="")
        executor.execute(action)
        assert client.request_count == 0

    def test_normal_execution_calls_api_correctly(self):
        """正常执行 → API 被调用: execute 1次 + verify 1次 = 2次 (无回滚)。"""
        client = _make_sandbox_client()
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)

        executor.execute(_make_meta_action(
            target_budget=140.0, current_budget=200.0,
        ))
        # execute() 调用 client.update_campaign_budget 1 次
        # verify() 调用 client.get_campaign 1 次
        # verify 通过 → 不触发 rollback → 不额外调用
        assert client.request_count == 2
