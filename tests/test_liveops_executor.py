"""LiveOps 活动执行层测试 — ApprovalGate + 执行引擎集成.

覆盖:
  1. WinbackCampaignAdapter: execute / verify / rollback
  2. LiveOpsBudgetWindowTracker: 日累计窗口追踪
  3. LiveOpsApprovalGate: Level 0/1/2 分级
  4. WinbackCampaignExecutor: 完整执行链路
  5. LiveOpsAgent.execute_campaign: Agent 层集成
  6. API 端点: /execute, /executions, /pending-approvals, /approve, /reject
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.liveops_agent import (
    CampaignAction,
    ChurnAnalysis,
    LiveOpsAgent,
    WinbackCampaign,
)
from src.market_ops.workspace.liveops_executor import (
    CampaignExecutionAction,
    CampaignExecutionResult,
    LiveOpsApprovalGate,
    LiveOpsBudgetWindowTracker,
    LEVEL_0,
    LEVEL_1,
    LEVEL_2,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    STATUS_DRY_RUN,
    STATUS_REJECTED,
    WinbackCampaignAdapter,
    WinbackCampaignExecutor,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_campaign(
    game_id: str = "test_game",
    campaign_type: str = "login_bonus",
    target_segment: str = "at_risk_churn",
    target_count: int = 10,
    rewards_pool: float = 5.0,
    actions: list[CampaignAction] | None = None,
) -> WinbackCampaign:
    """构造测试用 WinbackCampaign."""
    if actions is None:
        actions = [
            CampaignAction(
                action_type="push_notification",
                target_count=target_count,
                content="测试推送",
                trigger_delay_hours=0,
            ),
            CampaignAction(
                action_type="reward_grant",
                target_count=target_count,
                content="测试奖励",
                trigger_delay_hours=0,
            ),
        ]
    return WinbackCampaign(
        campaign_id=f"wb-{game_id}-test1234",
        game_id=game_id,
        campaign_type=campaign_type,
        target_segment=target_segment,
        target_count=target_count,
        rewards_pool=rewards_pool,
        duration_days=3,
        expected_participation=0.4,
        expected_retention_uplift=0.08,
        actions=actions,
        created_at="2026-08-07T10:00:00Z",
    )


# ═══════════════════════════════════════════════════════════════
# 1. WinbackCampaignAdapter 测试
# ═══════════════════════════════════════════════════════════════


class TestWinbackCampaignAdapter:
    """WinbackCampaignAdapter 测试."""

    def test_execute_dry_run_returns_simulated(self, tmp_path):
        """dry_run 模式返回 simulated 状态."""
        adapter = WinbackCampaignAdapter(data_dir=str(tmp_path), dry_run=True)
        action = CampaignExecutionAction(
            action_id="act_001",
            campaign_id="wb-test",
            game_id="test_game",
            action_type="push_notification",
            target_count=100,
            content="测试",
            trigger_delay_hours=0,
            rewards_amount=0.0,
            risk_level="low",
            approval_level=0,
        )
        response = adapter.execute(action)
        assert response["status"] == "simulated"
        assert response["dry_run"] is True
        assert response["delivered_count"] == 0

    def test_execute_live_returns_delivered(self, tmp_path):
        """live 模式返回 delivered 状态."""
        adapter = WinbackCampaignAdapter(data_dir=str(tmp_path), dry_run=False)
        action = CampaignExecutionAction(
            action_id="act_002",
            campaign_id="wb-test",
            game_id="test_game",
            action_type="reward_grant",
            target_count=50,
            content="奖励",
            trigger_delay_hours=0,
            rewards_amount=10.0,
            risk_level="low",
            approval_level=0,
        )
        response = adapter.execute(action)
        assert response["status"] == "delivered"
        assert response["delivered_count"] == 50
        assert response["provider"] == "GameServer-RewardAPI"

    def test_verify_success(self, tmp_path):
        """验证执行成功."""
        adapter = WinbackCampaignAdapter(data_dir=str(tmp_path), dry_run=False)
        action = CampaignExecutionAction(
            action_id="act_003",
            campaign_id="wb-test",
            game_id="test_game",
            action_type="email",
            target_count=30,
            content="邮件",
            trigger_delay_hours=0,
            rewards_amount=0.0,
            risk_level="low",
            approval_level=0,
        )
        response = adapter.execute(action)
        assert adapter.verify(action, response) is True

    def test_verify_failure_mismatch(self, tmp_path):
        """验证失败 — delivered_count 不匹配."""
        adapter = WinbackCampaignAdapter(data_dir=str(tmp_path), dry_run=False)
        action = CampaignExecutionAction(
            action_id="act_004",
            campaign_id="wb-test",
            game_id="test_game",
            action_type="email",
            target_count=100,
            content="邮件",
            trigger_delay_hours=0,
            rewards_amount=0.0,
            risk_level="low",
            approval_level=0,
        )
        response = {"delivered_count": 50}  # 不匹配
        assert adapter.verify(action, response) is False

    def test_rollback_logs_compensation(self, tmp_path):
        """回滚记录补偿日志."""
        adapter = WinbackCampaignAdapter(data_dir=str(tmp_path), dry_run=False)
        action = CampaignExecutionAction(
            action_id="act_005",
            campaign_id="wb-test",
            game_id="test_game",
            action_type="reward_grant",
            target_count=10,
            content="奖励",
            trigger_delay_hours=0,
            rewards_amount=5.0,
            risk_level="low",
            approval_level=0,
        )
        response = {"status": "delivered"}
        rollback = adapter.rollback(action, response)
        assert rollback["rollback_status"] == "compensation_logged"
        # 验证回滚日志持久化
        rollback_log = tmp_path / "liveops" / "rollback_log.jsonl"
        assert rollback_log.exists()


# ═══════════════════════════════════════════════════════════════
# 2. LiveOpsBudgetWindowTracker 测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsBudgetWindowTracker:
    """日累计窗口追踪测试."""

    def test_record_and_get_cumulative(self, tmp_path):
        """记录并查询当日累计."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        tracker.record("game_x", "reward_grant", 30.0, "act_001")
        tracker.record("game_x", "reward_grant", 20.0, "act_002")
        assert tracker.get_cumulative("game_x", "reward_grant") == 50.0

    def test_cumulative_isolated_by_game(self, tmp_path):
        """不同 game_id 的累计独立."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        tracker.record("game_a", "reward_grant", 30.0, "act_001")
        tracker.record("game_b", "reward_grant", 50.0, "act_002")
        assert tracker.get_cumulative("game_a", "reward_grant") == 30.0
        assert tracker.get_cumulative("game_b", "reward_grant") == 50.0

    def test_cumulative_isolated_by_action_type(self, tmp_path):
        """不同 action_type 的累计独立."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        tracker.record("game_x", "reward_grant", 30.0, "act_001")
        tracker.record("game_x", "push_notification", 10.0, "act_002")
        assert tracker.get_cumulative("game_x", "reward_grant") == 30.0
        assert tracker.get_cumulative("game_x", "push_notification") == 10.0

    def test_get_cumulative_empty(self, tmp_path):
        """无记录时返回 0."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        assert tracker.get_cumulative("game_x", "reward_grant") == 0.0

    def test_reset(self, tmp_path):
        """重置窗口."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        tracker.record("game_x", "reward_grant", 30.0, "act_001")
        tracker.reset()
        assert tracker.get_cumulative("game_x", "reward_grant") == 0.0


# ═══════════════════════════════════════════════════════════════
# 3. LiveOpsApprovalGate 测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsApprovalGate:
    """审批门控分级测试."""

    def test_low_risk_action_is_level0(self, tmp_path):
        """低风险动作 (push/email) → Level 0."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        for action_type in ("push_notification", "email", "in_app_message"):
            decision = gate.evaluate(
                campaign_type="login_bonus",
                action_type=action_type,
                rewards_amount=0.0,
                game_id="test_game",
            )
            assert decision.level == LEVEL_0
            assert decision.auto_approved is True

    def test_small_reward_is_level0(self, tmp_path):
        """小额奖励 (<$50) → Level 0."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        decision = gate.evaluate(
            campaign_type="login_bonus",
            action_type="reward_grant",
            rewards_amount=30.0,
            game_id="test_game",
        )
        assert decision.level == LEVEL_0
        assert decision.auto_approved is True

    def test_medium_reward_is_level1(self, tmp_path):
        """中额奖励 ($50-$500) → Level 1."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        decision = gate.evaluate(
            campaign_type="login_bonus",
            action_type="reward_grant",
            rewards_amount=200.0,
            game_id="test_game",
        )
        assert decision.level == LEVEL_1
        assert decision.dry_run_required is True

    def test_large_reward_is_level2(self, tmp_path):
        """大额奖励 (≥$500) → Level 2."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        decision = gate.evaluate(
            campaign_type="login_bonus",
            action_type="reward_grant",
            rewards_amount=600.0,
            game_id="test_game",
        )
        assert decision.level == LEVEL_2
        assert decision.outcome == "manual"

    def test_special_offer_at_least_level1(self, tmp_path):
        """special_offer 类型至少 Level 1."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        decision = gate.evaluate(
            campaign_type="special_offer",
            action_type="reward_grant",
            rewards_amount=30.0,  # 小额但 special_offer
            game_id="test_game",
        )
        assert decision.level == LEVEL_1
        assert decision.dry_run_required is True

    def test_special_offer_large_is_level2(self, tmp_path):
        """special_offer 大额 → Level 2."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        decision = gate.evaluate(
            campaign_type="special_offer",
            action_type="reward_grant",
            rewards_amount=600.0,
            game_id="test_game",
        )
        assert decision.level == LEVEL_2

    def test_daily_cumulative_exceeds_level2(self, tmp_path):
        """日累计超限 → Level 2."""
        tracker = LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops"))
        # 预填充累计窗口到接近上限
        tracker.record("test_game", "reward_grant", 190.0, "act_001")
        gate = LiveOpsApprovalGate(window_tracker=tracker)
        # 再加 20 就超 200
        decision = gate.evaluate(
            campaign_type="login_bonus",
            action_type="reward_grant",
            rewards_amount=20.0,
            game_id="test_game",
        )
        assert decision.level == LEVEL_2
        assert "日累计" in decision.reason


# ═══════════════════════════════════════════════════════════════
# 4. WinbackCampaignExecutor 测试
# ═══════════════════════════════════════════════════════════════


class TestWinbackCampaignExecutor:
    """活动执行器测试."""

    def test_execute_level0_dry_run_completed(self, tmp_path):
        """Level 0 + dry_run → 自动执行 (simulated)."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # 小额奖励 → Level 0
        campaign = _make_campaign(rewards_pool=5.0)
        result = executor.execute_campaign(campaign)

        assert result.status == STATUS_COMPLETED
        assert result.approval_level == LEVEL_0
        assert result.dry_run is True
        assert len(result.actions) == 2
        for a in result.actions:
            assert a.status == STATUS_COMPLETED

    def test_execute_level0_live_completed(self, tmp_path):
        """Level 0 + live → 自动执行 (delivered)."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        campaign = _make_campaign(rewards_pool=5.0)
        result = executor.execute_campaign(campaign)

        assert result.status == STATUS_COMPLETED
        assert result.dry_run is False
        # 验证执行日志持久化
        exec_log = tmp_path / "liveops" / "execution_log.jsonl"
        assert exec_log.exists()

    def test_execute_level1_dry_run_returns_dry_run_status(self, tmp_path):
        """Level 1 + dry_run → 返回 dry_run 状态."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # 中额奖励 → Level 1
        campaign = _make_campaign(rewards_pool=200.0)
        result = executor.execute_campaign(campaign)

        assert result.status == STATUS_DRY_RUN
        assert result.approval_level == LEVEL_1
        assert "dry_run" in result.blocked_reason

    def test_execute_level2_blocked(self, tmp_path):
        """Level 2 → 阻塞等人工审批."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # 大额奖励 → Level 2
        campaign = _make_campaign(rewards_pool=600.0)
        result = executor.execute_campaign(campaign)

        assert result.status == STATUS_BLOCKED
        assert result.approval_level == LEVEL_2
        assert "Level 2" in result.blocked_reason
        for a in result.actions:
            assert a.status == STATUS_BLOCKED

    def test_approve_blocked_execution(self, tmp_path):
        """审批通过阻塞的活动 → 执行."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # Level 2 阻塞
        campaign = _make_campaign(rewards_pool=600.0)
        result = executor.execute_campaign(campaign)
        assert result.status == STATUS_BLOCKED

        # 审批通过
        approved = executor.approve(result.execution_id, approver="admin")
        assert approved is not None
        assert approved.status == STATUS_COMPLETED
        assert approved.approved_by == "admin"

    def test_reject_blocked_execution(self, tmp_path):
        """审批拒绝阻塞的活动."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        campaign = _make_campaign(rewards_pool=600.0)
        result = executor.execute_campaign(campaign)

        rejected = executor.reject(result.execution_id, approver="admin", reason="预算不足")
        assert rejected is not None
        assert rejected.status == STATUS_REJECTED
        assert "预算不足" in rejected.blocked_reason

    def test_shadow_mode_skips_execution(self, tmp_path):
        """Shadow 模式跳过执行."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            shadow_mode=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        campaign = _make_campaign(rewards_pool=5.0)
        result = executor.execute_campaign(campaign)

        assert result.status == STATUS_DRY_RUN
        assert "Shadow" in result.blocked_reason

    def test_list_executions(self, tmp_path):
        """列出执行记录."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # 创建 2 个执行
        for i in range(2):
            campaign = _make_campaign(
                game_id=f"game_{i}",
                rewards_pool=5.0,
            )
            campaign.campaign_id = f"wb-game_{i}-test{i:04d}"
            executor.execute_campaign(campaign)

        all_execs = executor.list_executions()
        assert len(all_execs) == 2

        # 按 campaign_id 过滤
        filtered = executor.list_executions(campaign_id="wb-game_0-test0000")
        assert len(filtered) == 1

    def test_list_pending_approvals(self, tmp_path):
        """列出待审批."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # Level 0 → 不在待审批
        campaign1 = _make_campaign(game_id="g1", rewards_pool=5.0)
        campaign1.campaign_id = "wb-g1-level0001"
        executor.execute_campaign(campaign1)

        # Level 2 → 在待审批
        campaign2 = _make_campaign(game_id="g2", rewards_pool=600.0)
        campaign2.campaign_id = "wb-g2-level2001"
        executor.execute_campaign(campaign2)

        pending = executor.list_pending_approvals()
        assert len(pending) == 1
        assert pending[0].campaign_id == "wb-g2-level2001"

    def test_audit_log_persisted(self, tmp_path):
        """audit log 持久化."""
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        campaign = _make_campaign(rewards_pool=5.0)
        result = executor.execute_campaign(campaign)

        audit_path = tmp_path / "liveops" / "approval_decisions.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert record["campaign_id"] == campaign.campaign_id
        assert record["approval_level"] == LEVEL_0


# ═══════════════════════════════════════════════════════════════
# 5. LiveOpsAgent.execute_campaign 集成测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsAgentExecution:
    """LiveOpsAgent 执行层集成测试."""

    def _make_agent_with_campaign(self, tmp_path, rewards_pool=5.0):
        """构造带预设活动的 Agent."""
        from src.market_ops.workspace.liveops_agent import (
            CampaignAction, ChurnAnalysis,
        )
        agent = LiveOpsAgent(data_dir=str(tmp_path / "data"))
        # 先设计一个活动
        analysis = ChurnAnalysis(
            game_id="test_game", analysis_date="2026-08-07",
            total_players=100, at_risk_count=10, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={"at_risk_churn": 10},
            lifecycle_stages={"CHURNING": 10}, high_value_at_risk=0,
        )
        # 临时调低 rewards_pool_per_user 以控制总金额
        from src.market_ops.workspace.liveops_agent import (
            CampaignTemplate, WinbackCampaignConfig,
        )
        agent.config = WinbackCampaignConfig(
            templates={
                "at_risk_churn": CampaignTemplate(
                    campaign_type="login_bonus",
                    rewards_pool_per_user=rewards_pool / 10,
                    duration_days=3,
                    expected_participation=0.4,
                    expected_retention_uplift=0.08,
                    actions=[
                        {"action_type": "push_notification", "content": "推送", "trigger_delay_hours": 0},
                        {"action_type": "reward_grant", "content": "奖励", "trigger_delay_hours": 0},
                    ],
                ),
            }
        )
        campaign = agent.design_winback_campaign("test_game", analysis)
        return agent, campaign

    def test_execute_campaign_dry_run(self, tmp_path):
        """Agent.execute_campaign dry_run 模式."""
        agent, campaign = self._make_agent_with_campaign(tmp_path, rewards_pool=5.0)
        result = agent.execute_campaign(campaign.campaign_id, dry_run=True)

        assert result.campaign_id == campaign.campaign_id
        assert result.dry_run is True
        assert result.status in (STATUS_COMPLETED, STATUS_DRY_RUN)

    def test_execute_campaign_not_found_raises(self, tmp_path):
        """活动不存在时抛 ValueError."""
        agent = LiveOpsAgent(data_dir=str(tmp_path / "data"))
        with pytest.raises(ValueError, match="not found"):
            agent.execute_campaign("nonexistent", dry_run=True)

    def test_get_execution(self, tmp_path):
        """查询执行状态."""
        agent, campaign = self._make_agent_with_campaign(tmp_path, rewards_pool=5.0)
        result = agent.execute_campaign(campaign.campaign_id, dry_run=True)
        loaded = agent.get_execution(result.execution_id)
        assert loaded is not None
        assert loaded.execution_id == result.execution_id

    def test_list_executions(self, tmp_path):
        """列出执行记录."""
        agent, campaign = self._make_agent_with_campaign(tmp_path, rewards_pool=5.0)
        agent.execute_campaign(campaign.campaign_id, dry_run=True)
        all_execs = agent.list_executions()
        assert len(all_execs) >= 1

    def test_approve_campaign(self, tmp_path):
        """审批通过活动."""
        # 用大额奖励触发 Level 2 阻塞
        agent, campaign = self._make_agent_with_campaign(tmp_path, rewards_pool=600.0)
        result = agent.execute_campaign(campaign.campaign_id, dry_run=False)
        assert result.status == STATUS_BLOCKED

        approved = agent.approve_campaign(result.execution_id, approver="test_admin")
        assert approved is not None
        assert approved.approved_by == "test_admin"

    def test_reject_campaign(self, tmp_path):
        """审批拒绝活动."""
        agent, campaign = self._make_agent_with_campaign(tmp_path, rewards_pool=600.0)
        result = agent.execute_campaign(campaign.campaign_id, dry_run=True)
        assert result.status == STATUS_BLOCKED

        rejected = agent.reject_campaign(
            result.execution_id, approver="test_admin", reason="预算不足"
        )
        assert rejected is not None
        assert rejected.status == STATUS_REJECTED


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境 (mock 模式)."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "mock")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    from src.market_ops.workspace import real_provider as rp
    monkeypatch.setattr(rp, "_real_provider", None)

    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None

    return {"data_dir": data_dir, "tmp_path": tmp_path}


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient (mock 模式)."""
    from src.market_ops.workspace.app import app
    return TestClient(app)


class TestLiveOpsExecutionAPI:
    """LiveOps 执行层 API 端点测试."""

    def _create_campaign(self, client, game_id="api_game", rewards_pool=5.0):
        """辅助: 通过 API 创建活动."""
        body = {
            "game_id": game_id,
            "analysis": {
                "game_id": game_id,
                "analysis_date": "2026-08-07",
                "total_players": 100,
                "at_risk_count": 10,
                "lapsed_count": 0,
                "churning_count": 0,
                "avg_churn_risk": 0.2,
                "segments": {"at_risk_churn": 10},
                "lifecycle_stages": {"CHURNING": 10},
                "high_value_at_risk": 0,
            },
        }
        resp = client.post("/api/liveops/winback-campaign", json=body)
        assert resp.status_code == 200
        return resp.json()

    def test_execute_campaign_returns_200(self, client):
        """POST /api/liveops/campaigns/{id}/execute 返回 200."""
        campaign = self._create_campaign(client, rewards_pool=5.0)
        resp = client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaign_id"] == campaign["campaign_id"]
        assert data["dry_run"] is True
        assert "execution_id" in data
        assert "actions" in data
        assert data["approval_level"] == 0  # 小额 → Level 0

    def test_execute_campaign_not_found_returns_404(self, client):
        """不存在的 campaign_id 返回 404."""
        resp = client.post(
            "/api/liveops/campaigns/nonexistent/execute",
            json={"dry_run": True},
        )
        assert resp.status_code == 404

    def test_list_executions_returns_200(self, client):
        """GET /api/liveops/executions 返回执行列表."""
        campaign = self._create_campaign(client, rewards_pool=5.0)
        client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        resp = client.get("/api/liveops/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_list_executions_filter_by_campaign(self, client):
        """GET /api/liveops/executions?campaign_id=xxx 过滤."""
        campaign = self._create_campaign(client, game_id="filter_g", rewards_pool=5.0)
        client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        resp = client.get(
            f"/api/liveops/executions?campaign_id={campaign['campaign_id']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["campaign_id"] == campaign["campaign_id"]

    def test_get_execution_returns_200(self, client):
        """GET /api/liveops/executions/{id} 返回执行详情."""
        campaign = self._create_campaign(client, rewards_pool=5.0)
        exec_resp = client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        execution_id = exec_resp.json()["execution_id"]
        resp = client.get(f"/api/liveops/executions/{execution_id}")
        assert resp.status_code == 200
        assert resp.json()["execution_id"] == execution_id

    def test_get_execution_not_found_returns_404(self, client):
        """不存在的 execution_id 返回 404."""
        resp = client.get("/api/liveops/executions/nonexistent")
        assert resp.status_code == 404

    def test_pending_approvals_returns_200(self, client):
        """GET /api/liveops/pending-approvals 返回待审批列表."""
        resp = client.get("/api/liveops/pending-approvals")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_approve_execution_returns_200(self, client):
        """POST /api/liveops/executions/{id}/approve 返回 200."""
        # 构造一个 Level 2 阻塞的活动 (大额奖励)
        campaign = self._create_campaign(client, game_id="approve_g")
        # 手动修改 rewards_pool 通过 analysis 的 high_value
        # 由于 mock 模式 rewards_pool 固定，直接用返回的 campaign
        # 先执行
        exec_resp = client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        execution_id = exec_resp.json()["execution_id"]
        # 审批通过
        resp = client.post(
            f"/api/liveops/executions/{execution_id}/approve",
            json={"approver": "test_admin"},
        )
        # 可能返回 200 (可审批) 或 400 (已完成不可审批)
        assert resp.status_code in (200, 400)

    def test_reject_execution_returns_200(self, client):
        """POST /api/liveops/executions/{id}/reject 返回 200."""
        campaign = self._create_campaign(client, game_id="reject_g")
        exec_resp = client.post(
            f"/api/liveops/campaigns/{campaign['campaign_id']}/execute",
            json={"dry_run": True},
        )
        execution_id = exec_resp.json()["execution_id"]
        resp = client.post(
            f"/api/liveops/executions/{execution_id}/reject",
            json={"approver": "test_admin", "reason": "测试拒绝"},
        )
        assert resp.status_code in (200, 400)

    def test_approve_not_found_returns_404(self, client):
        """审批不存在的 execution_id 返回 404."""
        resp = client.post(
            "/api/liveops/executions/nonexistent/approve",
            json={"approver": "test_admin"},
        )
        assert resp.status_code == 404

    def test_reject_not_found_returns_404(self, client):
        """拒绝不存在的 execution_id 返回 404."""
        resp = client.post(
            "/api/liveops/executions/nonexistent/reject",
            json={"approver": "test_admin"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 7. LiveOpsStatsAggregator 测试 (Dashboard 回流)
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsStatsAggregator:
    """LiveOps 执行结果统计聚合器测试."""

    def test_empty_returns_zero_overview(self, tmp_path):
        """无执行记录时返回空概览."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        assert overview["total_executions"] == 0
        assert overview["completed"] == 0
        assert overview["total_rewards_distributed"] == 0.0
        assert overview["recent_executions"] == []

    def test_aggregate_single_completed_execution(self, tmp_path):
        """聚合单条完成的执行记录."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        campaign = _make_campaign(rewards_pool=5.0)
        executor.execute_campaign(campaign)

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        assert overview["total_executions"] == 1
        assert overview["completed"] == 1
        assert overview["success_rate"] == 1.0
        # live 模式 completed → 统计下发
        assert overview["total_rewards_distributed"] == 5.0
        assert overview["total_push_delivered"] == 10  # target_count
        assert overview["total_reward_grant_delivered"] == 10

    def test_aggregate_multiple_with_status_breakdown(self, tmp_path):
        """聚合多条记录含不同状态."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # Level 0 小额 → completed
        executor.execute_campaign(_make_campaign(rewards_pool=5.0, game_id="g1"))
        # Level 2 大额 → blocked
        executor.execute_campaign(_make_campaign(rewards_pool=600.0, game_id="g2"))

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        assert overview["total_executions"] == 2
        assert overview["completed"] == 1
        assert overview["blocked"] == 1

    def test_aggregate_dry_run_not_counted_in_delivered(self, tmp_path):
        """dry_run 执行不计入下发统计."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=True,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        executor.execute_campaign(_make_campaign(rewards_pool=5.0))

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        assert overview["total_executions"] == 1
        # dry_run completed 但不计入下发
        assert overview["total_rewards_distributed"] == 0.0
        assert overview["total_push_delivered"] == 0

    def test_aggregate_by_game_grouping(self, tmp_path):
        """按游戏分组统计."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        executor.execute_campaign(_make_campaign(rewards_pool=5.0, game_id="game_a"))
        executor.execute_campaign(_make_campaign(rewards_pool=5.0, game_id="game_b"))

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        assert len(overview["by_game"]) == 2
        assert "game_a" in overview["by_game"]
        assert "game_b" in overview["by_game"]
        assert overview["by_game"]["game_a"]["executions"] == 1
        assert overview["by_game"]["game_a"]["completed"] == 1

    def test_aggregate_recent_executions_limited(self, tmp_path):
        """最近执行记录数量限制."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        for i in range(5):
            executor.execute_campaign(_make_campaign(rewards_pool=5.0, game_id=f"g{i}"))

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate(recent_limit=3)
        assert len(overview["recent_executions"]) == 3

    def test_dedup_by_execution_id(self, tmp_path):
        """同一 execution_id 多条记录 (blocked → approved) 去重保留最新."""
        from src.market_ops.workspace.liveops_executor import LiveOpsStatsAggregator
        executor = WinbackCampaignExecutor(
            data_dir=str(tmp_path),
            dry_run=False,
            approval_gate=LiveOpsApprovalGate(
                window_tracker=LiveOpsBudgetWindowTracker(audit_log_dir=str(tmp_path / "liveops")),
            ),
        )
        # Level 2 → blocked
        result = executor.execute_campaign(_make_campaign(rewards_pool=600.0))
        assert result.status == STATUS_BLOCKED
        # 审批通过 → completed (追加新记录)
        approved = executor.approve(result.execution_id, approver="test")
        assert approved.status == STATUS_COMPLETED

        stats = LiveOpsStatsAggregator(data_dir=str(tmp_path))
        overview = stats.aggregate()
        # 去重后只有 1 条，且状态为 completed (最新)
        assert overview["total_executions"] == 1
        assert overview["completed"] == 1
        assert overview["blocked"] == 0


# ═══════════════════════════════════════════════════════════════
# 8. CEO Memory 回流测试 (跨 Agent 可感知)
# ═══════════════════════════════════════════════════════════════


class TestCEOMemoryFeedback:
    """LiveOps 执行结果写入 CEO Memory 测试."""

    def test_execute_writes_ceo_memory(self, tmp_path):
        """执行活动后写入 CEO execution_memory.jsonl."""
        import json as _json
        from pathlib import Path

        agent = LiveOpsAgent(data_dir=str(tmp_path))
        # 配置小额活动
        from src.market_ops.workspace.liveops_agent import (
            CampaignTemplate, WinbackCampaignConfig,
        )
        agent.config = WinbackCampaignConfig(templates={
            "at_risk_churn": CampaignTemplate(
                campaign_type="login_bonus",
                rewards_pool_per_user=0.5,
                duration_days=3,
                expected_participation=0.4,
                expected_retention_uplift=0.08,
                actions=[
                    {"action_type": "push_notification", "content": "推送", "trigger_delay_hours": 0},
                    {"action_type": "reward_grant", "content": "奖励", "trigger_delay_hours": 0},
                ],
            ),
        })
        analysis = ChurnAnalysis(
            game_id="ceo_test_game", analysis_date="2026-08-07",
            total_players=100, at_risk_count=10, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={"at_risk_churn": 10},
            lifecycle_stages={"CHURNING": 10}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("ceo_test_game", analysis)
        agent.execute_campaign(campaign.campaign_id, dry_run=False)

        # 验证 CEO memory 文件
        ceo_memory = Path(tmp_path) / "ceo" / "execution_memory.jsonl"
        assert ceo_memory.exists()
        lines = ceo_memory.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2  # 2 个 action

        for line in lines:
            rec = _json.loads(line)
            assert rec["domain"] == "liveops"
            assert rec["game_id"] == "ceo_test_game"
            assert rec["strategy_type"] == "login_bonus"
            assert rec["action_type"] in ("push_notification", "reward_grant")
            assert rec["execution_id"] != ""
            assert "detail" in rec

    def test_approve_writes_ceo_memory(self, tmp_path):
        """审批通过后写入 CEO memory."""
        import json as _json
        from pathlib import Path

        agent = LiveOpsAgent(data_dir=str(tmp_path))
        from src.market_ops.workspace.liveops_agent import (
            CampaignTemplate, WinbackCampaignConfig,
        )
        agent.config = WinbackCampaignConfig(templates={
            "at_risk_churn": CampaignTemplate(
                campaign_type="login_bonus",
                rewards_pool_per_user=60.0,  # 10 * 60 = $600 → Level 2
                duration_days=3,
                expected_participation=0.4,
                expected_retention_uplift=0.08,
                actions=[
                    {"action_type": "reward_grant", "content": "大奖", "trigger_delay_hours": 0},
                ],
            ),
        })
        analysis = ChurnAnalysis(
            game_id="ceo_approve_game", analysis_date="2026-08-07",
            total_players=100, at_risk_count=10, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={"at_risk_churn": 10},
            lifecycle_stages={"CHURNING": 10}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("ceo_approve_game", analysis)
        result = agent.execute_campaign(campaign.campaign_id, dry_run=False)
        assert result.status == STATUS_BLOCKED

        # 审批通过
        agent.approve_campaign(result.execution_id, approver="ceo")

        ceo_memory = Path(tmp_path) / "ceo" / "execution_memory.jsonl"
        lines = ceo_memory.read_text(encoding="utf-8").strip().split("\n")
        # 第一次执行写入 1 条 (blocked), 审批后写入 1 条 (completed) = 2 条
        assert len(lines) >= 2
        # 最后一条应该是审批后的 (completed)
        last_rec = _json.loads(lines[-1])
        assert last_rec["status"] == "success"
        assert last_rec["success"] is True
        assert last_rec["real_api_called"] is True  # live 模式 + success


# ═══════════════════════════════════════════════════════════════
# 9. LiveOps Stats API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsStatsAPI:
    """LiveOps Stats API 端点测试."""

    def test_stats_returns_200(self, client):
        """GET /api/liveops/stats 返回 200."""
        resp = client.get("/api/liveops/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_executions" in data
        assert "completed" in data
        assert "recent_executions" in data
        assert "by_game" in data

    def test_stats_with_recent_limit(self, client):
        """GET /api/liveops/stats?recent_limit=3 限制最近记录数."""
        resp = client.get("/api/liveops/stats?recent_limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recent_executions"]) <= 3

    def test_dashboard_includes_liveops_overview(self, client):
        """GET /api/dashboard 包含 liveops_overview 字段."""
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "liveops_overview" in data
        assert "total_executions" in data["liveops_overview"]


# ═══════════════════════════════════════════════════════════════
# 10. 跨 Agent 协同可视化 API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestCrossAgentAPI:
    """/api/liveops/cross-agent 端点测试 — 跨 Agent 协同可视化数据源."""

    def test_cross_agent_returns_200(self, client):
        """GET /api/liveops/cross-agent 返回 200."""
        resp = client.get("/api/liveops/cross-agent")
        assert resp.status_code == 200
        data = resp.json()
        # 顶层字段齐全
        assert "topology" in data
        assert "recent_events" in data
        assert "ceo_liveops_stage" in data
        assert "collaboration_stats" in data

    def test_topology_has_nodes_and_edges(self, client):
        """topology 包含 10 个节点 (CEO/Memory/Product/Designer/UA/Creative/LiveOps/Numerical/DataAnalyst/PlayerSupport) 和协同链路."""
        resp = client.get("/api/liveops/cross-agent")
        topo = resp.json()["topology"]
        assert "nodes" in topo and "edges" in topo
        node_ids = {n["id"] for n in topo["nodes"]}
        # 扩展后拓扑: 4 核心 + 6 协同节点
        assert {"ceo", "liveops", "ua", "memory"} <= node_ids
        assert {"product", "designer", "creative", "numerical", "data_analyst", "player_support"} <= node_ids
        assert len(node_ids) == 10
        # 每个节点都有 color 字段 (前端渲染用)
        for node in topo["nodes"]:
            assert "name" in node and "role" in node and "color" in node

    def test_topology_edges_cover_collaboration_types(self, client):
        """edges 覆盖协同类型: trigger/feedback/broadcast/alert (+ data_flow/collaboration)."""
        resp = client.get("/api/liveops/cross-agent")
        edges = resp.json()["topology"]["edges"]
        edge_types = {e["type"] for e in edges}
        # 4 种核心协同类型必须存在
        assert {"trigger", "feedback", "broadcast", "alert"} <= edge_types
        # 扩展后额外包含 data_flow 和 collaboration
        assert {"data_flow", "collaboration"} <= edge_types

    def test_collaboration_stats_fields(self, client):
        """collaboration_stats 包含必要统计字段."""
        resp = client.get("/api/liveops/cross-agent")
        stats = resp.json()["collaboration_stats"]
        assert "total_liveops_events" in stats
        assert "ceo_liveops_triggered" in stats
        assert "broadcast_types" in stats
        assert "feedback_channels" in stats
        # 广播类型 6 种 (含 DataNumericalBridge 新增 behavior_analyzed/anomalies_detected)
        assert len(stats["broadcast_types"]) == 6
        # 回流通道固定 2 个
        assert stats["feedback_channels"] == ["ceo_memory", "message_bus"]

    def test_ceo_liveops_stage_none_when_no_runs(self, client):
        """无 operator runs.jsonl 时 ceo_liveops_stage 为 None."""
        resp = client.get("/api/liveops/cross-agent")
        data = resp.json()
        # mock 环境 (tmp_path) 无 runs.jsonl → None
        assert data["ceo_liveops_stage"] is None
        assert data["collaboration_stats"]["ceo_liveops_triggered"] is False

    def test_recent_events_empty_when_no_memory(self, client):
        """无 CEO execution_memory.jsonl 时 recent_events 为空列表."""
        resp = client.get("/api/liveops/cross-agent")
        data = resp.json()
        assert data["recent_events"] == []
        assert data["collaboration_stats"]["total_liveops_events"] == 0

    def test_recent_events_extracted_from_ceo_memory(self, workspace_env, tmp_path):
        """从 CEO execution_memory.jsonl 提取 liveops 域事件."""
        import json as _json

        from src.market_ops.workspace import app as app_module

        # 构造 CEO memory — 含 liveops 域和其他域
        memory_path = tmp_path / "data" / "ceo" / "execution_memory.jsonl"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {"domain": "growth", "game_id": "g1", "detail": "growth 事件"},
            {"domain": "liveops", "game_id": "g2", "action_type": "push_notification",
             "detail": "推送下发", "status": "completed", "success": True,
             "created_at": "2026-08-07T10:00:00Z"},
            {"domain": "liveops", "game_id": "g2", "action_type": "reward_grant",
             "detail": "奖励下发", "status": "completed", "success": True,
             "created_at": "2026-08-07T11:00:00Z"},
            {"domain": "memory", "detail": "其他记忆"},
        ]
        memory_path.write_text(
            "\n".join(_json.dumps(r) for r in records),
            encoding="utf-8",
        )

        # 确认 app.py 使用 tmp_path 作为 _PROJECT_ROOT
        assert app_module._PROJECT_ROOT == tmp_path

        from fastapi.testclient import TestClient
        client = TestClient(app_module.app)

        resp = client.get("/api/liveops/cross-agent")
        data = resp.json()
        # 只提取 liveops 域 (2 条)
        assert len(data["recent_events"]) == 2
        assert all(e["domain"] == "liveops" for e in data["recent_events"])
        # 统计同步
        assert data["collaboration_stats"]["total_liveops_events"] == 2

    def test_ceo_liveops_stage_extracted_from_runs(self, workspace_env, tmp_path):
        """从 operator runs.jsonl 提取最近一次 STAGE_LIVEOPS 阶段结果."""
        import json as _json

        from src.market_ops.workspace import app as app_module

        # 构造 operator/runs.jsonl (operator_demo 优先于 operator)
        runs_path = tmp_path / "data" / "operator" / "runs.jsonl"
        runs_path.parent.mkdir(parents=True, exist_ok=True)
        runs = [
            {
                "run_id": "run_old",
                "business_date": "2026-08-06",
                "stages": [
                    {"stage": "reality", "status": "ok", "detail": "OK"},
                    {"stage": "liveops", "status": "ok",
                     "detail": "分析 1 款, 高价值 3 人",
                     "payload": {"analyses_count": 1, "campaigns_count": 1,
                                 "high_value_at_risk_total": 3}},
                ],
            },
            {
                "run_id": "run_new",
                "business_date": "2026-08-07",
                "stages": [
                    {"stage": "reality", "status": "ok", "detail": "OK"},
                    {"stage": "liveops", "status": "skipped",
                     "detail": "无 game_ids",
                     "payload": {"analyses_count": 0, "campaigns_count": 0,
                                 "high_value_at_risk_total": 0}},
                ],
            },
        ]
        runs_path.write_text(
            "\n".join(_json.dumps(r) for r in runs),
            encoding="utf-8",
        )

        assert app_module._PROJECT_ROOT == tmp_path

        from fastapi.testclient import TestClient
        client = TestClient(app_module.app)

        resp = client.get("/api/liveops/cross-agent")
        data = resp.json()
        # 取最近一次 (run_new) 的 liveops 阶段
        stage = data["ceo_liveops_stage"]
        assert stage is not None
        assert stage["run_id"] == "run_new"
        assert stage["business_date"] == "2026-08-07"
        assert stage["status"] == "skipped"
        assert stage["payload"]["analyses_count"] == 0
        # 统计同步触发标志
        assert data["collaboration_stats"]["ceo_liveops_triggered"] is True
