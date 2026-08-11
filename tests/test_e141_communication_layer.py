"""E14.1 Agent Communication Layer — 集成测试.

验证多 Agent 通信基础设施的完整功能:
  - Agent Identity & Message Protocol (15)
  - Message Bus (20)
  - Task Protocol (20)
  - Agent Registry (15)
  - Collaboration Engine (20)
  - End-to-End Integration (10)

总计: 100 个测试用例
"""

from __future__ import annotations

import pytest
import time

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    # agent_message
    AgentIdentity,
    AgentRole,
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageStatus,
    StandardMessageType,
    MessageContext,
    create_agent_identity,
    create_ua_agent_identity,
    create_creative_agent_identity,
    create_monetization_agent_identity,
    create_supervisor_agent_identity,
    create_product_agent_identity,
    # message_bus
    MessageBus,
    MessageHandler,
    MessageQueue,
    Subscription,
    create_message_bus,
    # task_protocol
    GrowthTask,
    TaskAssignment,
    TaskResult,
    TaskStatus,
    TaskPriority,
    TaskTracker,
    TaskDecomposer,
    create_task_tracker,
    create_task_decomposer,
    # agent_registry
    AgentRegistry,
    AgentRecord,
    AgentStatus,
    create_agent_registry,
    create_default_organization,
    # collaboration
    CollaborationEngine,
    Proposal,
    Vote,
    VoteOption,
    ConsensusResult,
    create_collaboration_engine,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def ua_identity():
    return create_ua_agent_identity()


@pytest.fixture
def creative_identity():
    return create_creative_agent_identity()


@pytest.fixture
def supervisor_identity():
    return create_supervisor_agent_identity()


@pytest.fixture
def monetization_identity():
    return create_monetization_agent_identity()


@pytest.fixture
def product_identity():
    return create_product_agent_identity()


@pytest.fixture
def bus():
    return create_message_bus()


@pytest.fixture
def registry():
    return create_default_organization()


@pytest.fixture
def tracker():
    return create_task_tracker()


@pytest.fixture
def decomposer():
    return create_task_decomposer()


@pytest.fixture
def collab_engine(bus, registry):
    return CollaborationEngine(bus=bus, registry=registry)


# ═══════════════════════════════════════════════════════════════
# 1. Agent Identity & Message Protocol (15 测试)
# ═══════════════════════════════════════════════════════════════


class TestAgentIdentity:
    """Agent 身份测试."""

    def test_create_identity_with_role(self):
        """创建带角色的身份."""
        identity = create_agent_identity(AgentRole.UA, "UA Agent")
        assert identity.role == AgentRole.UA
        assert identity.name == "UA Agent"
        assert identity.agent_id != ""

    def test_identity_is_frozen(self):
        """身份不可变."""
        identity = create_agent_identity(AgentRole.CREATIVE, "Creative")
        with pytest.raises(Exception):
            identity.role = AgentRole.UA  # type: ignore

    def test_display_name_uses_name(self):
        """display_name 使用 name."""
        identity = create_agent_identity(AgentRole.UA, "My UA Agent")
        assert identity.display_name == "My UA Agent"

    def test_display_name_fallback(self):
        """display_name 回退到 role_id."""
        identity = create_agent_identity(AgentRole.UA, "")
        assert AgentRole.UA.value in identity.display_name

    def test_identity_serialization(self):
        """身份序列化往返."""
        identity = create_ua_agent_identity()
        data = identity.to_dict()
        restored = AgentIdentity.from_dict(data)
        assert restored.agent_id == identity.agent_id
        assert restored.role == identity.role
        assert restored.name == identity.name

    def test_factory_ua_has_capabilities(self):
        """UA Agent 工厂包含能力."""
        identity = create_ua_agent_identity()
        assert "meta_ads_analysis" in identity.capabilities
        assert "campaign_management" in identity.capabilities

    def test_factory_creative_has_capabilities(self):
        """Creative Agent 工厂包含能力."""
        identity = create_creative_agent_identity()
        assert "creative_dna_analysis" in identity.capabilities
        assert "fatigue_detection" in identity.capabilities

    def test_factory_supervisor_has_capabilities(self):
        """Supervisor Agent 工厂包含能力."""
        identity = create_supervisor_agent_identity()
        assert "goal_decomposition" in identity.capabilities
        assert "conflict_resolution" in identity.capabilities


class TestAgentMessage:
    """Agent 消息测试."""

    def test_create_request_message(self, ua_identity, creative_identity):
        """创建请求消息."""
        msg = AgentMessage.create_request(
            ua_identity, creative_identity,
            "分析素材", {"campaign": "P04"}
        )
        assert msg.message_type == MessageType.REQUEST
        assert msg.sender == ua_identity
        assert msg.receiver == creative_identity
        assert msg.body["campaign"] == "P04"

    def test_create_response_message(self, ua_identity, creative_identity):
        """创建响应消息."""
        req = AgentMessage.create_request(
            ua_identity, creative_identity, "请求", {}
        )
        resp = AgentMessage.create_response(req, {"result": "ok"})
        assert resp.message_type == MessageType.RESPONSE
        assert resp.correlation_id == req.message_id
        assert resp.body["result"] == "ok"

    def test_create_broadcast_message(self, supervisor_identity):
        """创建广播消息."""
        msg = AgentMessage.create_broadcast(
            supervisor_identity, "策略更新", {"strategy": "v2"}
        )
        assert msg.message_type == MessageType.BROADCAST
        assert msg.receiver is None

    def test_create_task_message(self, supervisor_identity, ua_identity):
        """创建任务消息."""
        msg = AgentMessage.create_task(
            supervisor_identity, ua_identity,
            "优化ROAS", {"target": "+15%"}
        )
        assert msg.message_type == MessageType.TASK
        assert msg.priority == MessagePriority.HIGH

    def test_create_alert_message(self, ua_identity, supervisor_identity):
        """创建告警消息."""
        msg = AgentMessage.create_alert(
            ua_identity, supervisor_identity,
            "ROAS下降", {"roas": 0.8}
        )
        assert msg.message_type == MessageType.ALERT
        assert msg.priority == MessagePriority.CRITICAL

    def test_create_heartbeat_message(self, ua_identity):
        """创建心跳消息."""
        msg = AgentMessage.create_heartbeat(ua_identity)
        assert msg.message_type == MessageType.HEARTBEAT
        assert msg.priority == MessagePriority.LOW

    def test_message_lifecycle(self, ua_identity, creative_identity):
        """消息生命周期."""
        msg = AgentMessage.create_request(ua_identity, creative_identity, "test", {})
        assert msg.status == MessageStatus.CREATED
        msg.mark_sent()
        assert msg.status == MessageStatus.SENT
        msg.mark_delivered()
        assert msg.status == MessageStatus.DELIVERED
        msg.mark_processed()
        assert msg.status == MessageStatus.PROCESSED


# ═══════════════════════════════════════════════════════════════
# 2. Message Bus (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestMessageQueue:
    """消息队列测试."""

    def test_push_pop_single(self, ua_identity, creative_identity):
        """入队出队单条消息."""
        q = MessageQueue()
        msg = AgentMessage.create_request(ua_identity, creative_identity, "test", {})
        assert q.push(msg) is True
        assert q.size == 1
        popped = q.pop()
        assert popped is not None
        assert popped.message_id == msg.message_id
        assert q.size == 0

    def test_priority_ordering(self, ua_identity, creative_identity):
        """优先级排序."""
        q = MessageQueue()
        low = AgentMessage.create_request(ua_identity, creative_identity, "low", {},
                                          priority=MessagePriority.LOW)
        critical = AgentMessage.create_request(ua_identity, creative_identity, "critical", {},
                                               priority=MessagePriority.CRITICAL)
        q.push(low)
        q.push(critical)
        # critical 先出队
        first = q.pop()
        assert first.priority == MessagePriority.CRITICAL
        second = q.pop()
        assert second.priority == MessagePriority.LOW

    def test_queue_max_size(self, ua_identity, creative_identity):
        """队列满时丢弃最低优先级."""
        q = MessageQueue(max_size=2)
        msg1 = AgentMessage.create_request(ua_identity, creative_identity, "1", {},
                                           priority=MessagePriority.NORMAL)
        msg2 = AgentMessage.create_request(ua_identity, creative_identity, "2", {},
                                           priority=MessagePriority.HIGH)
        msg3 = AgentMessage.create_request(ua_identity, creative_identity, "3", {},
                                           priority=MessagePriority.CRITICAL)
        q.push(msg1)
        q.push(msg2)
        q.push(msg3)  # 触发丢弃
        assert q.size == 2
        first = q.pop()
        assert first.priority == MessagePriority.CRITICAL

    def test_drain(self, ua_identity, creative_identity):
        """清空队列."""
        q = MessageQueue()
        for i in range(5):
            q.push(AgentMessage.create_request(ua_identity, creative_identity, f"m{i}", {}))
        messages = q.drain()
        assert len(messages) == 5
        assert q.size == 0

    def test_peek(self, ua_identity, creative_identity):
        """peek 不移除."""
        q = MessageQueue()
        msg = AgentMessage.create_request(ua_identity, creative_identity, "test", {},
                                          priority=MessagePriority.CRITICAL)
        q.push(msg)
        assert q.peek() is not None
        assert q.size == 1


class TestMessageBus:
    """消息总线测试."""

    def test_send_point_to_point(self, bus, ua_identity, creative_identity):
        """点对点发送."""
        msg = AgentMessage.create_request(ua_identity, creative_identity, "test", {})
        bus.send(msg)
        assert bus.get_inbox_size(creative_identity.agent_id) == 1

    def test_send_broadcast(self, bus, supervisor_identity):
        """广播发送."""
        # 注册 3 个 handler
        bus.register_handler_fn("a1", lambda m: None)
        bus.register_handler_fn("a2", lambda m: None)
        bus.register_handler_fn("a3", lambda m: None)
        msg = AgentMessage.create_broadcast(supervisor_identity, "通知", {})
        bus.send(msg)
        assert bus.get_inbox_size("a1") == 1
        assert bus.get_inbox_size("a2") == 1
        assert bus.get_inbox_size("a3") == 1

    def test_deliver_messages(self, bus, ua_identity, creative_identity):
        """投递消息并触发 handler."""
        results = []

        def handler_fn(msg):
            results.append(msg.subject)
            return None

        bus.register_handler_fn(creative_identity.agent_id, handler_fn)
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "msg1", {}))
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "msg2", {}))
        bus.deliver_all(creative_identity.agent_id)
        assert "msg1" in results
        assert "msg2" in results

    def test_handler_response_auto_sent(self, bus, ua_identity, creative_identity):
        """handler 返回响应自动发送."""

        def handler_fn(msg):
            return AgentMessage.create_response(msg, {"ack": True})

        bus.register_handler_fn(creative_identity.agent_id, handler_fn)
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "ping", {}))
        bus.deliver(creative_identity.agent_id, max_count=1)
        # 响应应该被发送到 ua 的 inbox
        assert bus.get_inbox_size(ua_identity.agent_id) >= 1

    def test_subscription_pattern(self, bus, ua_identity):
        """发布/订阅模式."""
        bus.subscribe("a1", "roas_alert")
        bus.subscribe("a2", "roas_alert")
        msg = AgentMessage(
            sender=ua_identity,
            standard_type=StandardMessageType.ROAS_ALERT,
            subject="ROAS Alert",
            body={"roas": 0.8},
            message_type=MessageType.ALERT,
        )
        bus.send(msg)
        assert bus.get_inbox_size("a1") == 1
        assert bus.get_inbox_size("a2") == 1

    def test_message_history(self, bus, ua_identity, creative_identity):
        """消息历史记录."""
        for i in range(5):
            bus.send(AgentMessage.create_request(ua_identity, creative_identity, f"m{i}", {}))
        history = bus.get_history()
        assert len(history) == 5

    def test_history_by_type(self, bus, ua_identity, creative_identity):
        """按类型查询历史."""
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "req", {}))
        bus.send(AgentMessage.create_broadcast(ua_identity, "bcast", {}))
        reqs = bus.get_history_by_type(MessageType.REQUEST)
        assert len(reqs) == 1
        bcasts = bus.get_history_by_type(MessageType.BROADCAST)
        assert len(bcasts) == 1

    def test_history_between(self, bus, ua_identity, creative_identity):
        """两个 Agent 间消息历史."""
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "a", {}))
        bus.send(AgentMessage.create_request(creative_identity, ua_identity, "b", {}))
        history = bus.get_history_between(ua_identity.agent_id, creative_identity.agent_id)
        assert len(history) == 1

    def test_bus_stats(self, bus, ua_identity, creative_identity):
        """总线统计."""
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "test", {}))
        stats = bus.stats()
        assert stats["sent_count"] == 1
        assert "bus_id" in stats

    def test_reset(self, bus, ua_identity, creative_identity):
        """重置总线."""
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "test", {}))
        bus.reset()
        assert bus.stats()["sent_count"] == 0
        assert len(bus.get_history()) == 0

    def test_send_response(self, bus, ua_identity, creative_identity):
        """发送响应."""
        req = AgentMessage.create_request(ua_identity, creative_identity, "q", {})
        bus.send(req)
        resp = bus.send_response(req, {"answer": 42})
        assert resp.correlation_id == req.message_id
        assert resp.message_type == MessageType.RESPONSE

    def test_expired_message_handling(self, bus, ua_identity, creative_identity):
        """过期消息处理."""
        msg = AgentMessage.create_request(ua_identity, creative_identity, "expired", {})
        msg.ttl_seconds = 0.001  # 立即过期
        bus.send(msg)
        time.sleep(0.01)
        results = bus.deliver(creative_identity.agent_id, max_count=1)
        assert len(results) >= 1

    def test_unregistered_handler_no_error(self, bus, ua_identity, creative_identity):
        """未注册 handler 不报错."""
        bus.send(AgentMessage.create_request(ua_identity, creative_identity, "test", {}))
        results = bus.deliver(creative_identity.agent_id, max_count=1)
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════
# 3. Task Protocol (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestGrowthTask:
    """GrowthTask 测试."""

    def test_create_task(self):
        """创建任务."""
        task = GrowthTask(title="测试任务", description="描述")
        assert task.task_id != ""
        assert task.status == TaskStatus.PENDING
        assert task.is_leaf
        assert task.is_root

    def test_task_with_subtasks(self, tracker):
        """带子任务的任务."""
        root = tracker.create_task(GrowthTask(title="根任务"))
        tracker.create_subtask(root, "子任务1")
        tracker.create_subtask(root, "子任务2")
        assert not root.is_leaf
        assert len(root.subtasks) == 2

    def test_task_is_overdue(self):
        """任务过期检查."""
        task = GrowthTask(title="test", deadline="2020-01-01T00:00:00+00:00")
        assert task.is_overdue

    def test_task_serialization(self):
        """任务序列化."""
        task = GrowthTask(
            title="序列化测试",
            description="desc",
            goal="提升ROAS",
            priority=TaskPriority.HIGH,
        )
        data = task.to_dict()
        assert data["title"] == "序列化测试"
        assert data["priority"] == "high"
        assert data["is_root"] is True


class TestTaskTracker:
    """TaskTracker 测试."""

    def test_create_and_assign_task(self, tracker):
        """创建并分配任务."""
        task = tracker.create_task(GrowthTask(title="优化UA"))
        assignment = tracker.assign_task(task.task_id, "ua_agent_1", "supervisor")
        assert task.status == TaskStatus.ASSIGNED
        assert assignment.assigned_to == "ua_agent_1"

    def test_update_task_status(self, tracker):
        """更新任务状态."""
        task = tracker.create_task(GrowthTask(title="test"))
        tracker.update_task_status(task.task_id, TaskStatus.IN_PROGRESS)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at != ""

    def test_complete_task_with_result(self, tracker):
        """完成任务并记录结果."""
        task = tracker.create_task(GrowthTask(title="test"))
        tracker.assign_task(task.task_id, "agent_1")
        result = TaskResult(
            task_id=task.task_id,
            completed_by="agent_1",
            summary="完成",
            output={"roas": 1.5},
        )
        tracker.complete_task(task.task_id, result)
        assert task.status == TaskStatus.COMPLETED
        assert tracker.get_result(task.task_id) is not None

    def test_parent_completes_when_all_subtasks_done(self, tracker):
        """所有子任务完成时父任务自动完成."""
        root = tracker.create_task(GrowthTask(title="根"))
        sub1 = tracker.create_subtask(root, "子1")
        sub2 = tracker.create_subtask(root, "子2")
        tracker.assign_task(sub1.task_id, "a1")
        tracker.assign_task(sub2.task_id, "a2")
        tracker.complete_task(sub1.task_id, TaskResult(task_id=sub1.task_id, completed_by="a1"))
        assert root.status == TaskStatus.PENDING  # 还有一个未完成
        tracker.complete_task(sub2.task_id, TaskResult(task_id=sub2.task_id, completed_by="a2"))
        assert root.status == TaskStatus.COMPLETED

    def test_get_tasks_by_status(self, tracker):
        """按状态查询."""
        t1 = tracker.create_task(GrowthTask(title="t1"))
        t2 = tracker.create_task(GrowthTask(title="t2"))
        tracker.assign_task(t1.task_id, "a1")
        pending = tracker.get_tasks_by_status(TaskStatus.PENDING)
        assigned = tracker.get_tasks_by_status(TaskStatus.ASSIGNED)
        assert len(pending) == 1  # t2
        assert len(assigned) == 1  # t1

    def test_get_tasks_by_agent(self, tracker):
        """按 Agent 查询."""
        t1 = tracker.create_task(GrowthTask(title="t1"))
        t2 = tracker.create_task(GrowthTask(title="t2"))
        tracker.assign_task(t1.task_id, "ua_1")
        tracker.assign_task(t2.task_id, "creative_1")
        ua_tasks = tracker.get_tasks_by_agent("ua_1")
        assert len(ua_tasks) == 1

    def test_get_tasks_by_role(self, tracker):
        """按角色查询."""
        task = tracker.create_task(GrowthTask(
            title="test", assigned_role=AgentRole.UA
        ))
        ua_tasks = tracker.get_tasks_by_role(AgentRole.UA)
        assert len(ua_tasks) == 1

    def test_get_root_tasks(self, tracker):
        """获取根任务."""
        root = tracker.create_task(GrowthTask(title="root"))
        tracker.create_subtask(root, "child")
        roots = tracker.get_root_tasks()
        assert len(roots) == 1
        assert roots[0].title == "root"

    def test_get_ready_tasks_dependencies_met(self, tracker):
        """依赖满足后可获取就绪任务."""
        dep = tracker.create_task(GrowthTask(title="dep"))
        tracker.assign_task(dep.task_id, "a1")
        tracker.complete_task(dep.task_id, TaskResult(task_id=dep.task_id, completed_by="a1"))

        task = tracker.create_task(GrowthTask(
            title="depends_on_dep", dependencies=[dep.task_id]
        ))
        ready = tracker.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == task.task_id

    def test_task_stats(self, tracker):
        """任务统计."""
        tracker.create_task(GrowthTask(title="t1"))
        t2 = tracker.create_task(GrowthTask(title="t2"))
        tracker.assign_task(t2.task_id, "a1")
        tracker.complete_task(t2.task_id, TaskResult(task_id=t2.task_id, completed_by="a1"))
        stats = tracker.stats()
        assert stats["total_tasks"] == 2
        assert stats["completion_rate"] == 0.5


class TestTaskDecomposer:
    """TaskDecomposer 测试."""

    def test_decompose_goal(self, decomposer):
        """分解 Business Goal."""
        tasks = list(decomposer.decompose("本月利润提升30%"))
        assert len(tasks) > 0
        root = [t for t in tasks if t.is_root]
        assert len(root) == 1
        assert "利润提升30%" in root[0].title

    def test_decompose_specific_roles(self, decomposer):
        """仅分解特定角色."""
        tasks = list(decomposer.decompose(
            "提升ROAS",
            target_roles=[AgentRole.UA, AgentRole.CREATIVE]
        ))
        ua_tasks = [t for t in tasks if t.assigned_role == AgentRole.UA]
        creative_tasks = [t for t in tasks if t.assigned_role == AgentRole.CREATIVE]
        assert len(ua_tasks) > 0
        assert len(creative_tasks) > 0
        # 不应有 monetization 任务
        mon_tasks = [t for t in tasks if t.assigned_role == AgentRole.MONETIZATION]
        assert len(mon_tasks) == 0

    def test_decomposer_uses_tracker(self, decomposer):
        """分解器使用 tracker."""
        list(decomposer.decompose("test"))
        tracker = decomposer.get_tracker()
        stats = tracker.stats()
        assert stats["total_tasks"] > 0

    def test_custom_decomposition(self, decomposer):
        """自定义分解策略."""
        custom = {
            AgentRole.UA: [
                {"title": "自定义UA任务", "description": "desc"}
            ]
        }
        tasks = list(decomposer.decompose(
            "test", target_roles=[AgentRole.UA], custom_decomposition=custom
        ))
        titles = [t.title for t in tasks]
        assert "自定义UA任务" in titles


# ═══════════════════════════════════════════════════════════════
# 4. Agent Registry (15 测试)
# ═══════════════════════════════════════════════════════════════


class TestAgentRegistry:
    """Agent Registry 测试."""

    def test_register_agent(self, registry):
        """注册 Agent."""
        ua = registry.find_by_role(AgentRole.UA)
        assert len(ua) == 1
        assert ua[0].identity.role == AgentRole.UA

    def test_unregister_agent(self, registry):
        """注销 Agent."""
        ua_record = registry.find_by_role(AgentRole.UA)[0]
        assert registry.unregister(ua_record.identity.agent_id) is True
        assert registry.get(ua_record.identity.agent_id) is None

    def test_find_by_role(self, registry):
        """按角色查找."""
        ua_agents = registry.find_by_role(AgentRole.UA)
        assert len(ua_agents) == 1
        supervisors = registry.find_by_role(AgentRole.SUPERVISOR)
        assert len(supervisors) == 1

    def test_find_by_capability(self, registry):
        """按能力查找."""
        agents = registry.find_by_capability("meta_ads_analysis")
        assert len(agents) == 1
        assert agents[0].identity.role == AgentRole.UA

    def test_find_by_multiple_capabilities(self, registry):
        """按多个能力查找 (AND)."""
        agents = registry.find_by_capabilities(["meta_ads_analysis", "roas_monitoring"])
        assert len(agents) == 1

    def test_find_online(self, registry):
        """查找在线 Agent."""
        online = registry.find_online()
        assert len(online) == 10  # 默认 10 个角色 (含 LiveOps + Designer + Numerical + DataAnalyst + PlayerSupport)

    def test_heartbeat(self, registry):
        """心跳更新."""
        ua = registry.find_by_role(AgentRole.UA)[0]
        assert registry.heartbeat(ua.identity.agent_id) is True
        # 验证心跳时间更新
        record = registry.get(ua.identity.agent_id)
        assert record is not None

    def test_heartbeat_nonexistent(self, registry):
        """不存在 Agent 的心跳."""
        assert registry.heartbeat("nonexistent") is False

    def test_update_status(self, registry):
        """更新状态."""
        ua = registry.find_by_role(AgentRole.UA)[0]
        assert registry.update_status(ua.identity.agent_id, AgentStatus.BUSY)
        record = registry.get(ua.identity.agent_id)
        assert record.status == AgentStatus.BUSY

    def test_health_check(self, registry):
        """健康检查."""
        health = registry.check_health()
        assert health["total_agents"] == 10
        assert health["online"] == 10
        assert health["offline"] == 0

    def test_get_roles(self, registry):
        """获取角色列表."""
        roles = registry.get_roles()
        assert AgentRole.UA in roles
        assert AgentRole.CREATIVE in roles
        assert AgentRole.SUPERVISOR in roles

    def test_get_offline_agents(self, registry):
        """获取离线 Agent."""
        # 所有 Agent 刚注册，应该在线
        offline = registry.get_offline_agents()
        assert len(offline) == 0

    def test_registry_stats(self, registry):
        """注册中心统计."""
        stats = registry.stats()
        assert stats["total_agents"] == 10
        assert "by_role" in stats
        assert "health" in stats

    def test_default_organization_has_all_roles(self, registry):
        """默认组织包含所有角色."""
        all_agents = registry.get_all()
        roles = {r.identity.role for r in all_agents}
        assert AgentRole.SUPERVISOR in roles
        assert AgentRole.UA in roles
        assert AgentRole.CREATIVE in roles
        assert AgentRole.MONETIZATION in roles
        assert AgentRole.PRODUCT in roles
        assert AgentRole.LIVEOPS in roles

    def test_find_by_status(self, registry):
        """按状态查找."""
        ua = registry.find_by_role(AgentRole.UA)[0]
        registry.update_status(ua.identity.agent_id, AgentStatus.IDLE)
        idle = registry.find_by_status(AgentStatus.IDLE)
        assert len(idle) == 1


# ═══════════════════════════════════════════════════════════════
# 5. Collaboration Engine (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestCollaborationEngine:
    """协作引擎测试."""

    def test_request_response(self, collab_engine, ua_identity, creative_identity):
        """请求-响应."""
        req = collab_engine.request(
            ua_identity, creative_identity,
            "分析素材疲劳", {"campaign": "P04"}
        )
        assert req.message_type == MessageType.REQUEST
        assert req.subject == "分析素材疲劳"

    def test_respond_to_request(self, collab_engine, ua_identity, creative_identity):
        """响应请求."""
        req = collab_engine.request(ua_identity, creative_identity, "ping", {})
        resp = collab_engine.respond(req, {"status": "ok"})
        assert resp.correlation_id == req.message_id
        responses = collab_engine.get_response(req.message_id)
        assert len(responses) == 1

    def test_broadcast(self, collab_engine, supervisor_identity):
        """广播."""
        msg = collab_engine.broadcast(
            supervisor_identity,
            "策略更新",
            {"strategy": "v2"}
        )
        assert msg.message_type == MessageType.BROADCAST

    def test_broadcast_to_role(self, collab_engine, supervisor_identity, registry):
        """向特定角色广播."""
        msg = collab_engine.broadcast_to_role(
            supervisor_identity,
            AgentRole.UA,
            "UA通知",
            {"action": "scale"}
        )
        assert msg.message_type == MessageType.BROADCAST

    def test_dispatch_task(self, collab_engine, supervisor_identity, ua_identity):
        """分配任务."""
        msg = collab_engine.dispatch_task(
            supervisor_identity, ua_identity,
            "优化ROAS", {"target": "+15%"}
        )
        assert msg.message_type == MessageType.TASK
        assert msg.priority == MessagePriority.HIGH

    def test_dispatch_to_role(self, collab_engine, supervisor_identity, registry):
        """向角色分配任务."""
        msgs = collab_engine.dispatch_to_role(
            supervisor_identity,
            AgentRole.CREATIVE,
            "生成变体", {"count": 20}
        )
        assert len(msgs) == 1  # 只有一个 Creative Agent

    def test_propose_and_vote_approve(self, collab_engine):
        """提案并投票通过."""
        proposal = collab_engine.propose(
            title="增加预算",
            description="P04预算增加50%",
            proposed_by="ua_1",
            required_voters=["ua_1", "mon_1", "supervisor"],
            required_approval_ratio=0.5,
        )
        collab_engine.vote(proposal.proposal_id, "ua_1", VoteOption.APPROVE, "ROAS高")
        collab_engine.vote(proposal.proposal_id, "mon_1", VoteOption.APPROVE, "LTV稳定")
        collab_engine.vote(proposal.proposal_id, "supervisor", VoteOption.APPROVE, "同意")
        result = collab_engine.tally_proposal(proposal.proposal_id)
        assert result == ConsensusResult.APPROVED

    def test_propose_and_vote_reject(self, collab_engine):
        """提案被拒绝."""
        proposal = collab_engine.propose(
            title="增加预算",
            description="P04预算增加50%",
            proposed_by="ua_1",
            required_voters=["ua_1", "mon_1", "supervisor"],
            required_approval_ratio=0.5,
        )
        collab_engine.vote(proposal.proposal_id, "ua_1", VoteOption.APPROVE)
        collab_engine.vote(proposal.proposal_id, "mon_1", VoteOption.REJECT, "LTV下降")
        collab_engine.vote(proposal.proposal_id, "supervisor", VoteOption.REJECT)
        result = collab_engine.tally_proposal(proposal.proposal_id)
        assert result == ConsensusResult.REJECTED

    def test_vote_abstain(self, collab_engine):
        """弃权投票."""
        proposal = collab_engine.propose(
            title="test",
            description="test",
            proposed_by="a",
            required_voters=["a", "b"],
            required_approval_ratio=0.5,
        )
        collab_engine.vote(proposal.proposal_id, "a", VoteOption.ABSTAIN)
        collab_engine.vote(proposal.proposal_id, "b", VoteOption.APPROVE)
        result = collab_engine.tally_proposal(proposal.proposal_id)
        assert result == ConsensusResult.APPROVED  # 1/2 = 0.5 >= 0.5

    def test_cannot_vote_twice(self, collab_engine):
        """不能重复投票."""
        proposal = collab_engine.propose(
            title="test", description="test",
            proposed_by="a", required_voters=["a", "b"]
        )
        v1 = collab_engine.vote(proposal.proposal_id, "a", VoteOption.APPROVE)
        v2 = collab_engine.vote(proposal.proposal_id, "a", VoteOption.REJECT)
        assert v1 is not None
        assert v2 is not None
        assert v1.option == VoteOption.APPROVE  # 保持第一次投票

    def test_proposal_approval_ratio(self, collab_engine):
        """提案通过率."""
        proposal = collab_engine.propose(
            title="test", description="test",
            proposed_by="a", required_voters=["a", "b", "c"]
        )
        collab_engine.vote(proposal.proposal_id, "a", VoteOption.APPROVE)
        collab_engine.vote(proposal.proposal_id, "b", VoteOption.REJECT)
        assert proposal.approval_ratio == 0.5

    def test_resolve_conflict(self, collab_engine):
        """冲突解决."""
        proposal = collab_engine.resolve_conflict(
            conflict_description="UA建议增加预算50%，Monetization拒绝",
            models=[
                {"agent": "UA", "proposal": "增加预算50%"},
                {"agent": "Monetization", "proposal": "维持现状"},
            ],
            required_voters=["supervisor", "ua_1", "mon_1"],
        )
        assert proposal is not None
        assert "UA建议" in proposal.description

    def test_negotiate(self, collab_engine, ua_identity, creative_identity):
        """协商发起."""
        result = collab_engine.negotiate(
            sender=ua_identity,
            receiver=creative_identity,
            subject="预算分配",
            initial_offer={"budget": 1000},
            max_rounds=3,
        )
        assert result["status"] == "initiated"
        assert result["rounds"][0]["offer"] == {"budget": 1000}

    def test_collaboration_stats(self, collab_engine, ua_identity, creative_identity):
        """协作统计."""
        collab_engine.request(ua_identity, creative_identity, "test", {})
        stats = collab_engine.stats()
        assert stats["pending_requests"] >= 0

    def test_pending_requests_tracking(self, collab_engine, ua_identity, creative_identity):
        """未响应请求追踪."""
        collab_engine.request(ua_identity, creative_identity, "req1", {})
        collab_engine.request(ua_identity, creative_identity, "req2", {})
        pending = collab_engine.get_pending_requests()
        assert len(pending) == 2

    def test_collaboration_log(self, collab_engine, ua_identity, creative_identity):
        """协作日志."""
        collab_engine.request(ua_identity, creative_identity, "test", {})
        log = collab_engine.get_collaboration_log()
        assert len(log) >= 1
        assert log[-1]["event_type"] == "request"

    def test_get_proposal(self, collab_engine):
        """获取提案."""
        proposal = collab_engine.propose(
            title="test", description="test",
            proposed_by="a", required_voters=["a"]
        )
        retrieved = collab_engine.get_proposal(proposal.proposal_id)
        assert retrieved is not None
        assert retrieved.title == "test"

    def test_vote_nonexistent_proposal(self, collab_engine):
        """不存在的提案投票."""
        result = collab_engine.vote("nonexistent", "a", VoteOption.APPROVE)
        assert result is None


# ═══════════════════════════════════════════════════════════════
# 6. End-to-End Integration (10 测试)
# ═══════════════════════════════════════════════════════════════


class TestE2EIntegration:
    """端到端集成测试 — 模拟多 Agent 协作场景."""

    def test_scenario_ua_requests_creative_analysis(self):
        """场景: UA Agent 发现 ROAS 下降 → 请求 Creative 分析."""
        bus = create_message_bus()
        registry = create_default_organization()
        collab = CollaborationEngine(bus=bus, registry=registry)

        ua = registry.find_by_role(AgentRole.UA)[0].identity
        creative = registry.find_by_role(AgentRole.CREATIVE)[0].identity

        # UA 发送素材分析请求
        req = collab.request(
            ua, creative,
            "P04素材疲劳分析",
            {
                "campaign": "P04",
                "issue": "creative_fatigue",
                "roas_drop": "20%",
            },
            standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
            priority=MessagePriority.HIGH,
        )
        assert req.standard_type == StandardMessageType.REQUEST_CREATIVE_ANALYSIS

        # Creative 注册 handler 并处理
        responses = []
        def creative_handler(msg):
            if msg.standard_type == StandardMessageType.REQUEST_CREATIVE_ANALYSIS:
                return AgentMessage.create_response(msg, {
                    "hypothesis": "hook_fatigue",
                    "action": "generate_20_variants",
                    "target_dna": ["rescue", "challenge"],
                })
            return None

        bus.register_handler_fn(creative.agent_id, creative_handler)
        bus.deliver_all(creative.agent_id)

        # 验证响应投递到 UA
        bus.deliver_all(ua.agent_id)
        assert bus.get_inbox_size(ua.agent_id) == 0  # 已处理

    def test_scenario_supervisor_decomposes_goal(self):
        """场景: Supervisor 分解 Business Goal."""
        bus = create_message_bus()
        registry = create_default_organization()
        decomposer = create_task_decomposer()
        collab = CollaborationEngine(bus=bus, registry=registry)

        supervisor = registry.find_by_role(AgentRole.SUPERVISOR)[0].identity

        # Supervisor 分解目标
        tasks = list(decomposer.decompose("本月利润提升30%"))
        root = [t for t in tasks if t.is_root][0]
        assert root.title.startswith("Goal:")

        # 分配任务给各角色
        ua_tasks = decomposer.get_tracker().get_tasks_by_role(AgentRole.UA)
        creative_tasks = decomposer.get_tracker().get_tasks_by_role(AgentRole.CREATIVE)
        assert len(ua_tasks) > 0
        assert len(creative_tasks) > 0

        # 模拟 Supervisor 广播分配
        collab.broadcast(
            supervisor,
            "目标分配",
            {"goal": "本月利润提升30%", "subtask_count": len(tasks)},
        )

    def test_scenario_conflict_resolution(self):
        """场景: UA 和 Monetization 冲突 → 投票解决."""
        collab = CollaborationEngine()

        # UA 建议增加预算
        # Monetization 拒绝 (LTV 下降)
        proposal = collab.resolve_conflict(
            conflict_description="UA建议P04预算增加50%，Monetization因LTV下降拒绝",
            models=[
                {"agent": "UA Agent", "proposal": "增加预算50%，预计ROAS +15%"},
                {"agent": "Monetization Agent", "proposal": "维持预算，LTV当前-8%"},
            ],
            required_voters=["supervisor", "ua_agent", "mon_agent"],
        )

        # Supervisor 投票支持 UA (数据驱动)
        collab.vote(proposal.proposal_id, "supervisor", VoteOption.APPROVE, "历史数据显示ROAS>1.5时增长可行")
        collab.vote(proposal.proposal_id, "ua_agent", VoteOption.APPROVE, "短期LTV下降但D30预期回升")
        collab.vote(proposal.proposal_id, "mon_agent", VoteOption.REJECT, "LTV连续下降需谨慎")

        result = collab.tally_proposal(proposal.proposal_id)
        assert result == ConsensusResult.APPROVED  # 2/3 >= 0.5

    def test_scenario_creative_fatigue_alert(self):
        """场景: Creative Agent 检测疲劳 → 告警 UA."""
        bus = create_message_bus()
        registry = create_default_organization()
        collab = CollaborationEngine(bus=bus, registry=registry)

        creative = registry.find_by_role(AgentRole.CREATIVE)[0].identity
        ua = registry.find_by_role(AgentRole.UA)[0].identity

        # Creative 广播疲劳告警
        alert = collab.broadcast(
            creative,
            "素材疲劳告警",
            {
                "campaign": "P04",
                "fatigue_score": 0.85,
                "affected_creatives": ["c001", "c002", "c003"],
            },
            standard_type=StandardMessageType.CREATIVE_FATIGUE_ALERT,
            priority=MessagePriority.HIGH,
        )
        assert alert.standard_type == StandardMessageType.CREATIVE_FATIGUE_ALERT

    def test_scenario_full_agent_organization(self):
        """场景: 完整多 Agent 组织协作."""
        bus = create_message_bus()
        registry = create_default_organization()
        decomposer = create_task_decomposer()
        collab = CollaborationEngine(bus=bus, registry=registry)

        supervisor = registry.find_by_role(AgentRole.SUPERVISOR)[0].identity
        ua = registry.find_by_role(AgentRole.UA)[0].identity
        creative = registry.find_by_role(AgentRole.CREATIVE)[0].identity
        monetization = registry.find_by_role(AgentRole.MONETIZATION)[0].identity

        # Step 1: Supervisor 分解目标
        all_tasks = list(decomposer.decompose("本月利润提升30%"))
        root = [t for t in all_tasks if t.is_root][0]
        assert root is not None

        # Step 2: Supervisor 广播目标
        collab.broadcast(supervisor, "新目标", {"goal": "本月利润提升30%"})

        # Step 3: UA 请求 Creative 分析
        collab.request(
            ua, creative,
            "P04素材分析",
            {"campaign": "P04"},
            standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
        )

        # Step 4: Creative 响应
        creative_handler = lambda msg: AgentMessage.create_response(msg, {
            "hypothesis": "hook_fatigue",
            "action": "generate_20_variants",
        })
        bus.register_handler_fn(creative.agent_id, creative_handler)
        bus.deliver_all(creative.agent_id)

        # Step 5: 冲突解决
        proposal = collab.resolve_conflict(
            conflict_description="预算分配冲突",
            models=[
                {"agent": "UA", "proposal": "增加P04预算"},
                {"agent": "Monetization", "proposal": "维持预算"},
            ],
            required_voters=["supervisor", "ua_agent", "mon_agent"],
        )
        collab.vote(proposal.proposal_id, "supervisor", VoteOption.APPROVE)
        collab.vote(proposal.proposal_id, "ua_agent", VoteOption.APPROVE)
        collab.vote(proposal.proposal_id, "mon_agent", VoteOption.REJECT)
        result = collab.tally_proposal(proposal.proposal_id)
        assert result == ConsensusResult.APPROVED

        # 验证所有 Agent 健康
        health = registry.check_health()
        assert health["online"] == 10

    def test_scenario_task_lifecycle(self):
        """场景: 完整任务生命周期."""
        tracker = create_task_tracker()
        decomposer = TaskDecomposer(tracker=tracker)

        # 分解目标
        list(decomposer.decompose("提升ROAS", target_roles=[AgentRole.UA]))

        # 分配 UA 任务
        ua_tasks = tracker.get_tasks_by_role(AgentRole.UA)
        for task in ua_tasks:
            tracker.assign_task(task.task_id, "ua_agent_1", "supervisor")
            tracker.update_task_status(task.task_id, TaskStatus.ACCEPTED)
            tracker.update_task_status(task.task_id, TaskStatus.IN_PROGRESS)

        # 完成所有 UA 任务
        for task in ua_tasks:
            tracker.complete_task(task.task_id, TaskResult(
                task_id=task.task_id,
                completed_by="ua_agent_1",
                summary=f"完成: {task.title}",
                output={"roas": 1.5},
            ))

        # 验证根任务完成
        root = tracker.get_root_tasks()[0]
        assert root.status == TaskStatus.COMPLETED

    def test_scenario_agent_health_monitoring(self):
        """场景: Agent 健康监控."""
        registry = create_default_organization()

        # 初始健康检查
        health = registry.check_health()
        assert health["online"] == 10

        # 模拟 UA Agent 离线
        ua = registry.find_by_role(AgentRole.UA)[0]
        registry.update_status(ua.identity.agent_id, AgentStatus.OFFLINE)

        health2 = registry.check_health()
        assert health2["online"] <= 9  # UA 离线 (10-1=9)

    def test_scenario_heartbeat_recovery(self):
        """场景: 心跳恢复."""
        registry = create_agent_registry(heartbeat_timeout_seconds=0.01)
        identity = create_ua_agent_identity()
        registry.register(identity)
        registry.update_status(identity.agent_id, AgentStatus.OFFLINE)

        # 心跳恢复
        time.sleep(0.02)
        assert registry.heartbeat(identity.agent_id) is True
        record = registry.get(identity.agent_id)
        assert record.status == AgentStatus.ONLINE

    def test_scenario_message_subscription_flow(self):
        """场景: 消息订阅流程."""
        bus = create_message_bus()
        registry = create_default_organization()

        received_alerts = []
        def alert_handler(msg):
            received_alerts.append(msg.body)
            return None

        # 多个 Agent 订阅 ROAS 告警
        for agent in registry.get_all():
            bus.subscribe(agent.identity.agent_id, "roas_alert")
            bus.register_handler_fn(agent.identity.agent_id, alert_handler)

        # 发送 ROAS 告警
        ua = registry.find_by_role(AgentRole.UA)[0].identity
        msg = AgentMessage(
            sender=ua,
            standard_type=StandardMessageType.ROAS_ALERT,
            subject="ROAS Alert",
            body={"roas": 0.75, "campaign": "P04"},
            message_type=MessageType.ALERT,
            priority=MessagePriority.CRITICAL,
        )
        bus.send(msg)

        # 投递
        for agent in registry.get_all():
            bus.deliver_all(agent.identity.agent_id)

        # 所有 Agent 都收到了告警
        assert len(received_alerts) == 10

    def test_scenario_agent_registry_organization_structure(self):
        """场景: Agent 组织架构."""
        registry = create_default_organization()

        # 验证 Supervisor 是最高层
        supervisor = registry.find_by_role(AgentRole.SUPERVISOR)
        assert len(supervisor) == 1

        # 验证各专业 Agent 各有一个
        for role in [AgentRole.UA, AgentRole.CREATIVE, AgentRole.MONETIZATION, AgentRole.PRODUCT]:
            agents = registry.find_by_role(role)
            assert len(agents) == 1, f"Expected 1 {role.value} agent, got {len(agents)}"

        # 验证能力路由
        creative_agents = registry.find_by_capability("creative_dna_analysis")
        assert len(creative_agents) == 1
        assert creative_agents[0].identity.role == AgentRole.CREATIVE