"""跨 Agent 协同测试 — LiveOps ↔ CEO ↔ MessageBus.

验证:
  1. CEO Daily Run 的 STAGE_LIVEOPS 阶段正确触发 LiveOps 流失分析 + 活动设计
  2. LiveOps 执行后通过 MessageBus 广播事件 (campaign_executed/approved/rejected/churn_alert)
  3. 其他 Agent 可订阅 LiveOps 事件
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.market_ops.workspace.liveops_agent import (
    CampaignTemplate,
    ChurnAnalysis,
    LiveOpsAgent,
    WinbackCampaignConfig,
)
from src.market_ops.workspace.liveops_executor import (
    LiveOpsApprovalGate,
    LiveOpsBudgetWindowTracker,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    WinbackCampaignExecutor,
)


# ═══════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════


def _make_analysis(
    game_id: str = "test_game",
    at_risk: int = 10,
    high_value: int = 5,
) -> ChurnAnalysis:
    """构造流失分析数据."""
    return ChurnAnalysis(
        game_id=game_id,
        analysis_date="2026-08-07",
        total_players=1000,
        at_risk_count=at_risk,
        lapsed_count=0,
        churning_count=0,
        avg_churn_risk=0.35,
        segments={"at_risk_churn": at_risk},
        lifecycle_stages={"CHURNING": 0},
        high_value_at_risk=high_value,
    )


def _make_agent_with_executor(tmp_path: str) -> LiveOpsAgent:
    """构造带真实 executor 的 LiveOpsAgent."""
    agent = LiveOpsAgent(data_dir=tmp_path)
    agent._executor = WinbackCampaignExecutor(
        data_dir=tmp_path,
        dry_run=True,
        approval_gate=LiveOpsApprovalGate(
            window_tracker=LiveOpsBudgetWindowTracker(
                audit_log_dir=str(Path(tmp_path) / "liveops")
            ),
        ),
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
    return agent


def _make_mock_message_bus():
    """构造 Mock MessageBus，记录所有发送的消息."""
    bus = MagicMock()
    bus.sent_messages = []

    def fake_send(message):
        bus.sent_messages.append(message)
        return True

    bus.send = fake_send
    return bus


def _make_mock_identity():
    """构造 Mock AgentIdentity."""
    identity = MagicMock()
    identity.agent_id = "liveops_agent_001"
    identity.name = "LiveOps Agent"
    identity.role = "LIVEOPS"
    return identity


# ═══════════════════════════════════════════════════════════════
# 1. MessageBus 广播测试
# ═══════════════════════════════════════════════════════════════


class TestMessageBusBroadcast:
    """LiveOps 通过 MessageBus 广播事件测试."""

    def test_no_bus_silently_degrades(self, tmp_path):
        """未注入 message_bus 时静默降级，不报错."""
        agent = _make_agent_with_executor(str(tmp_path))
        # 不注入 message_bus
        campaign = agent.design_winback_campaign("g1", _make_analysis(high_value=5))
        agent.execute_campaign(campaign.campaign_id, dry_run=True)
        # 不抛异常即通过

    def test_churn_alert_broadcast_on_design(self, tmp_path):
        """发现高价值流失用户时广播 churn_alert."""
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        agent.design_winback_campaign("g1", _make_analysis(high_value=8))

        # 应广播 churn_alert
        assert len(bus.sent_messages) == 1
        msg = bus.sent_messages[0]
        assert msg.subject == "liveops:churn_alert"
        assert msg.body["event_type"] == "churn_alert"
        assert msg.body["high_value_at_risk"] == 8
        assert msg.body["game_id"] == "g1"

    def test_no_churn_alert_when_no_high_value(self, tmp_path):
        """无高价值流失用户时不广播 churn_alert."""
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        agent.design_winback_campaign("g1", _make_analysis(high_value=0))

        # 不应广播
        assert len(bus.sent_messages) == 0

    def test_campaign_executed_broadcast(self, tmp_path):
        """活动执行后广播 campaign_executed."""
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        campaign = agent.design_winback_campaign("g1", _make_analysis(high_value=5))
        # design 广播 1 次 churn_alert
        assert len(bus.sent_messages) == 1

        agent.execute_campaign(campaign.campaign_id, dry_run=True)
        # execute 再广播 1 次 campaign_executed
        assert len(bus.sent_messages) == 2
        exec_msg = bus.sent_messages[1]
        assert exec_msg.subject == "liveops:campaign_executed"
        assert exec_msg.body["event_type"] == "campaign_executed"
        assert exec_msg.body["dry_run"] is True

    def test_campaign_approved_broadcast(self, tmp_path):
        """审批通过后广播 campaign_approved."""
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        # Level 2 活动 → blocked
        agent.config.templates["at_risk_churn"].rewards_pool_per_user = 60.0
        campaign = agent.design_winback_campaign("g1", _make_analysis(high_value=5))
        result = agent.execute_campaign(campaign.campaign_id, dry_run=False)
        assert result.status == STATUS_BLOCKED

        # 清空消息，验证 approve 广播
        bus.sent_messages.clear()
        agent.approve_campaign(result.execution_id, approver="ceo")

        assert len(bus.sent_messages) == 1
        msg = bus.sent_messages[0]
        assert msg.subject == "liveops:campaign_approved"
        assert msg.body["approver"] == "ceo"

    def test_campaign_rejected_broadcast(self, tmp_path):
        """拒绝活动后广播 campaign_rejected."""
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        agent.config.templates["at_risk_churn"].rewards_pool_per_user = 60.0
        campaign = agent.design_winback_campaign("g1", _make_analysis(high_value=5))
        result = agent.execute_campaign(campaign.campaign_id, dry_run=False)

        bus.sent_messages.clear()
        agent.reject_campaign(result.execution_id, approver="ceo", reason="预算不足")

        assert len(bus.sent_messages) == 1
        msg = bus.sent_messages[0]
        assert msg.subject == "liveops:campaign_rejected"
        assert msg.body["reason"] == "预算不足"

    def test_broadcast_priority_high_for_churn_alert(self, tmp_path):
        """churn_alert 使用 HIGH 优先级."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            MessagePriority,
        )

        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        agent.design_winback_campaign("g1", _make_analysis(high_value=5))

        assert bus.sent_messages[0].priority == MessagePriority.HIGH


# ═══════════════════════════════════════════════════════════════
# 2. CEO Daily Run STAGE_LIVEOPS 测试
# ═══════════════════════════════════════════════════════════════


class TestStageLiveOps:
    """CEO Daily Run 的 STAGE_LIVEOPS 阶段测试."""

    def test_stage_liveops_constant_exists(self):
        """STAGE_LIVEOPS 常量已定义."""
        from src.operator.models import STAGE_LIVEOPS, ALL_STAGES
        assert STAGE_LIVEOPS == "liveops"
        assert STAGE_LIVEOPS in ALL_STAGES

    def test_stage_liveops_skipped_when_no_agent(self):
        """未注入 liveops_agent 时 STAGE_LIVEOPS 跳过."""
        from src.operator.models import STAGE_LIVEOPS, STAGE_SKIPPED, StageResult
        from src.operator.pipeline import DailyOperatorPipeline

        # 构造最小 pipeline mock
        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = None

        result = pipeline._liveops("2026-08-07", {}, "test_run")
        assert result.stage == STAGE_LIVEOPS
        assert result.status == STAGE_SKIPPED

    def test_stage_liveops_skipped_when_no_games(self):
        """无 game_ids 时跳过."""
        from src.operator.models import STAGE_LIVEOPS, STAGE_SKIPPED
        from src.operator.pipeline import DailyOperatorPipeline

        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = MagicMock()
        pipeline.ctx.game_ids = []
        # company None → 无游戏
        s = {"company": None}

        result = pipeline._liveops("2026-08-07", s, "test_run")
        assert result.status == STAGE_SKIPPED

    def test_stage_liveops_triggers_analysis_and_design(self, tmp_path):
        """STAGE_LIVEOPS 触发流失分析 + 活动设计."""
        from src.operator.pipeline import DailyOperatorPipeline

        # 构造真实 LiveOpsAgent
        agent = _make_agent_with_executor(str(tmp_path))

        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = agent
        pipeline.ctx.game_ids = ["game_a", "game_b"]

        # Mock 流失分析返回高价值用户
        original_analyze = agent.analyze_churn_risk
        call_count = {"analyze": 0, "design": 0}

        def mock_analyze(game_id):
            call_count["analyze"] += 1
            return _make_analysis(game_id=game_id, high_value=5)

        original_design = agent.design_winback_campaign

        def mock_design(game_id, analysis):
            call_count["design"] += 1
            return original_design(game_id, analysis)

        agent.analyze_churn_risk = mock_analyze
        agent.design_winback_campaign = mock_design

        s: dict = {"company": None}
        result = pipeline._liveops("2026-08-07", s, "test_run")

        assert result.status == "ok"
        assert call_count["analyze"] == 2  # 2 个游戏
        assert call_count["design"] == 2   # 2 个都有高价值用户 → 2 个活动
        assert len(s["liveops_campaigns"]) == 2
        assert s["liveops_high_risk_total"] == 10  # 5 + 5

    def test_stage_liveops_no_design_when_no_high_value(self, tmp_path):
        """无高价值流失用户时不设计活动."""
        from src.operator.pipeline import DailyOperatorPipeline

        agent = _make_agent_with_executor(str(tmp_path))

        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = agent
        pipeline.ctx.game_ids = ["game_a"]

        # Mock 返回无高价值用户
        agent.analyze_churn_risk = lambda gid: _make_analysis(
            game_id=gid, high_value=0
        )

        s: dict = {"company": None}
        result = pipeline._liveops("2026-08-07", s, "test_run")

        assert result.status == "ok"
        assert result.payload["campaigns_count"] == 0
        assert len(s["liveops_campaigns"]) == 0

    def test_stage_liveops_continues_on_single_game_failure(self, tmp_path):
        """单游戏分析失败不阻断其他游戏."""
        from src.operator.pipeline import DailyOperatorPipeline

        agent = _make_agent_with_executor(str(tmp_path))

        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = agent
        pipeline.ctx.game_ids = ["bad_game", "good_game"]

        call_count = {"analyze": 0}

        def mock_analyze(game_id):
            call_count["analyze"] += 1
            if game_id == "bad_game":
                raise RuntimeError("模拟失败")
            return _make_analysis(game_id=game_id, high_value=3)

        agent.analyze_churn_risk = mock_analyze

        s: dict = {"company": None}
        result = pipeline._liveops("2026-08-07", s, "test_run")

        # bad_game 失败，good_game 仍执行
        assert call_count["analyze"] == 2
        assert result.payload["analyses_count"] == 1  # 只有 good_game 成功
        assert result.payload["campaigns_count"] == 1


# ═══════════════════════════════════════════════════════════════
# 3. 跨 Agent 协同集成测试
# ═══════════════════════════════════════════════════════════════


class TestCrossAgentIntegration:
    """跨 Agent 协同集成测试 — 完整链路验证."""

    def test_ceo_to_liveops_to_messagebus(self, tmp_path):
        """完整协同链路: CEO Daily Run → LiveOps 分析 → MessageBus 广播.

        验证:
          1. CEO Daily Run STAGE_LIVEOPS 触发 LiveOps 分析
          2. LiveOps 发现高价值流失用户 → 广播 churn_alert
          3. 活动执行 → 广播 campaign_executed
          4. 结果写入 CEO memory
        """
        import json

        # 1. 构造带 MessageBus 的 LiveOpsAgent
        bus = _make_mock_message_bus()
        identity = _make_mock_identity()
        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = identity

        # 2. CEO Daily Run STAGE_LIVEOPS 触发
        from src.operator.pipeline import DailyOperatorPipeline

        pipeline = object.__new__(DailyOperatorPipeline)
        pipeline.ctx = MagicMock()
        pipeline.ctx.liveops_agent = agent
        pipeline.ctx.game_ids = ["cross_game"]

        # Mock 分析返回高价值用户
        agent.analyze_churn_risk = lambda gid: _make_analysis(
            game_id=gid, high_value=7
        )

        s: dict = {"company": None}
        stage_result = pipeline._liveops("2026-08-07", s, "cross_run")

        # 3. 验证 STAGE_LIVEOPS 执行成功
        assert stage_result.status == "ok"
        assert stage_result.payload["high_value_at_risk_total"] == 7

        # 4. 验证 churn_alert 已广播 (design 触发)
        churn_alerts = [
            m for m in bus.sent_messages if m.subject == "liveops:churn_alert"
        ]
        assert len(churn_alerts) == 1
        assert churn_alerts[0].body["high_value_at_risk"] == 7

        # 5. 验证活动方案已生成
        campaign_id = s["liveops_campaigns"][0]["campaign_id"]
        assert campaign_id is not None

        # 6. 执行活动 → 验证 campaign_executed 广播
        exec_result = agent.execute_campaign(campaign_id, dry_run=True)
        exec_msgs = [
            m for m in bus.sent_messages if m.subject == "liveops:campaign_executed"
        ]
        assert len(exec_msgs) == 1
        assert exec_msgs[0].body["dry_run"] is True

        # 7. 验证 CEO memory 已写入
        ceo_memory_path = Path(tmp_path) / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()
        lines = ceo_memory_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            rec = json.loads(line)
            assert rec["domain"] == "liveops"
            assert rec["game_id"] == "cross_game"

    def test_other_agent_can_subscribe_liveops_events(self, tmp_path):
        """其他 Agent 可订阅 LiveOps 事件."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            AgentRegistry,
            MessageBus,
            MessageType,
            create_default_organization,
        )

        # 1. 创建注册中心和消息总线
        registry = AgentRegistry()
        create_default_organization(registry)
        bus = MessageBus()

        # 2. 记录 LiveOps 广播的消息
        received_messages = []

        def liveops_handler(message):
            received_messages.append(message)

        # 3. 注册一个订阅者 (模拟 CEO Agent 订阅 LiveOps BROADCAST 事件)
        bus.register_handler_fn(
            "ceo_subscriber",
            liveops_handler,
            message_types=[MessageType.BROADCAST],
            standard_types=None,
        )

        # 4. 构造 LiveOpsAgent 并注入 MessageBus
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            AgentRole,
        )
        liveops_records = registry.find_by_role(AgentRole.LIVEOPS)
        assert len(liveops_records) > 0
        liveops_identity = liveops_records[0].identity

        agent = _make_agent_with_executor(str(tmp_path))
        agent._message_bus = bus
        agent._agent_identity = liveops_identity

        # 5. 触发活动设计 → 广播 churn_alert
        agent.analyze_churn_risk = lambda gid: _make_analysis(
            game_id=gid, high_value=12
        )
        agent.design_winback_campaign("sub_game", _make_analysis(high_value=12))

        # 6. 投递 inbox 中的消息到 handler (MessageBus 是推-拉模式)
        bus.deliver("ceo_subscriber")

        # 7. 验证订阅者收到消息
        assert len(received_messages) >= 1
        churn_msgs = [m for m in received_messages if m.subject == "liveops:churn_alert"]
        assert len(churn_msgs) == 1
        assert churn_msgs[0].body["high_value_at_risk"] == 12
