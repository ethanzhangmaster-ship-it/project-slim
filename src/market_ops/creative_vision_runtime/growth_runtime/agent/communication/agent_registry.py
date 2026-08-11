"""E14.1.4 Agent Registry — Agent 注册中心.

Agent Registry 是多 Agent 组织的目录服务:
  - 注册: Agent 启动时注册身份和能力
  - 发现: 按 role / capability 查找 Agent
  - 健康检查: 心跳监控和超时检测
  - 能力路由: 根据 capability 路由消息

设计原则:
  - Registry 是轻量级目录服务，不是数据库
  - 每个 Agent 有唯一 ID
  - 支持按 role 和能力发现
  - 健康检查基于心跳超时
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .agent_message import AgentIdentity, AgentRole, AgentMessage, MessageType


# ═══════════════════════════════════════════════════════════════
# Agent Status
# ═══════════════════════════════════════════════════════════════


class AgentStatus(str, Enum):
    """Agent 运行状态."""
    ONLINE = "online"
    IDLE = "idle"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Agent Record
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentRecord:
    """Agent 注册记录 — 包含身份和运行时状态.

    Attributes:
        identity: Agent 身份
        registered_at: 注册时间
        last_heartbeat: 最后心跳时间
        status: 运行状态
        version: Agent 版本
        endpoint: 通信端点 (预留)
        metadata: 扩展元数据
    """
    identity: AgentIdentity
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: AgentStatus = AgentStatus.ONLINE
    version: str = "1.0.0"
    endpoint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status.value,
            "version": self.version,
            "endpoint": self.endpoint,
            "metadata": self.metadata,
        }

    def is_alive(self, heartbeat_timeout_seconds: float = 60.0) -> bool:
        """检查是否存活 (心跳超时)."""
        try:
            last = datetime.fromisoformat(self.last_heartbeat)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return elapsed < heartbeat_timeout_seconds
        except (ValueError, TypeError):
            return False


# ═══════════════════════════════════════════════════════════════
# Agent Registry
# ═══════════════════════════════════════════════════════════════


class AgentRegistry:
    """Agent 注册中心 — 多 Agent 组织的目录服务.

    职责:
      1. 注册: Agent 启动时注册
      2. 发现: 按 role / capability 查找
      3. 健康: 心跳监控和超时检测
      4. 路由: 能力到 Agent 的映射

    用法:
        registry = AgentRegistry()
        registry.register(ua_identity)
        agents = registry.find_by_role(AgentRole.UA)
        agents = registry.find_by_capability("meta_ads_analysis")
    """

    def __init__(self, heartbeat_timeout_seconds: float = 60.0):
        self._records: dict[str, AgentRecord] = {}
        self._heartbeat_timeout = heartbeat_timeout_seconds

    # ── 注册/注销 ─────────────────────────────────────────────

    def register(self, identity: AgentIdentity, version: str = "1.0.0") -> AgentRecord:
        """注册 Agent."""
        record = AgentRecord(
            identity=identity,
            version=version,
        )
        self._records[identity.agent_id] = record
        return record

    def unregister(self, agent_id: str) -> bool:
        """注销 Agent."""
        if agent_id in self._records:
            del self._records[agent_id]
            return True
        return False

    def heartbeat(self, agent_id: str) -> bool:
        """更新心跳."""
        record = self._records.get(agent_id)
        if not record:
            return False
        record.last_heartbeat = datetime.now(timezone.utc).isoformat()
        if record.status == AgentStatus.OFFLINE:
            record.status = AgentStatus.ONLINE
        return True

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """更新 Agent 状态."""
        record = self._records.get(agent_id)
        if not record:
            return False
        record.status = status
        return True

    # ── 发现 ──────────────────────────────────────────────────

    def get(self, agent_id: str) -> AgentRecord | None:
        """获取 Agent 记录."""
        return self._records.get(agent_id)

    def get_identity(self, agent_id: str) -> AgentIdentity | None:
        """获取 Agent 身份."""
        record = self._records.get(agent_id)
        return record.identity if record else None

    def find_by_role(self, role: AgentRole) -> list[AgentRecord]:
        """按角色查找 Agent."""
        return [r for r in self._records.values() if r.identity.role == role]

    def find_by_capability(self, capability: str) -> list[AgentRecord]:
        """按能力查找 Agent."""
        return [
            r for r in self._records.values()
            if capability in r.identity.capabilities
        ]

    def find_by_capabilities(self, capabilities: list[str]) -> list[AgentRecord]:
        """按多个能力查找 (AND)."""
        return [
            r for r in self._records.values()
            if all(c in r.identity.capabilities for c in capabilities)
        ]

    def find_by_status(self, status: AgentStatus) -> list[AgentRecord]:
        """按状态查找."""
        return [r for r in self._records.values() if r.status == status]

    def find_online(self) -> list[AgentRecord]:
        """查找所有在线 Agent."""
        return [r for r in self._records.values() if r.is_alive(self._heartbeat_timeout)]

    def get_all(self) -> list[AgentRecord]:
        """获取所有注册记录."""
        return list(self._records.values())

    def get_roles(self) -> list[AgentRole]:
        """获取当前组织的角色列表."""
        return list(set(r.identity.role for r in self._records.values()))

    # ── 健康检查 ──────────────────────────────────────────────

    def check_health(self) -> dict[str, Any]:
        """执行全面健康检查.

        Returns:
            health_report: 各 Agent 健康状态
        """
        online = []
        offline = []
        degraded = []

        for record in self._records.values():
            if record.status == AgentStatus.OFFLINE:
                offline.append(record.identity.agent_id)
            elif not record.is_alive(self._heartbeat_timeout):
                offline.append(record.identity.agent_id)
                record.status = AgentStatus.OFFLINE
            elif record.status == AgentStatus.DEGRADED:
                degraded.append(record.identity.agent_id)
            else:
                online.append(record.identity.agent_id)

        total = len(self._records)
        return {
            "total_agents": total,
            "online": len(online),
            "offline": len(offline),
            "degraded": len(degraded),
            "online_ids": online,
            "offline_ids": offline,
            "degraded_ids": degraded,
            "health_rate": len(online) / max(total, 1),
            "roles": [r.value for r in self.get_roles()],
        }

    def get_offline_agents(self) -> list[AgentRecord]:
        """获取离线 Agent."""
        return [
            r for r in self._records.values()
            if not r.is_alive(self._heartbeat_timeout)
        ]

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取注册中心统计."""
        total = len(self._records)
        return {
            "total_agents": total,
            "by_role": {
                role.value: len(self.find_by_role(role))
                for role in self.get_roles()
            },
            "by_status": {
                status.value: len(self.find_by_status(status))
                for status in AgentStatus
            },
            "heartbeat_timeout_seconds": self._heartbeat_timeout,
            "health": self.check_health(),
        }

    def reset(self) -> None:
        """重置注册中心."""
        self._records.clear()


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_agent_registry(heartbeat_timeout_seconds: float = 60.0) -> AgentRegistry:
    """创建默认 Agent 注册中心."""
    return AgentRegistry(heartbeat_timeout_seconds=heartbeat_timeout_seconds)


def create_default_organization(registry: AgentRegistry | None = None) -> AgentRegistry:
    """创建默认多 Agent 组织 (预注册所有角色).

    预注册:
      - Growth Supervisor
      - UA Agent
      - Creative Agent
      - Monetization Agent
      - Product Agent
      - LiveOps Agent
      - Game Designer Agent
      - Numerical Designer Agent
      - Data Analyst Agent
      - Player Support Agent
    """
    from .agent_message import (
        create_creative_agent_identity,
        create_data_analyst_agent_identity,
        create_game_designer_agent_identity,
        create_liveops_agent_identity,
        create_monetization_agent_identity,
        create_numerical_designer_agent_identity,
        create_player_support_agent_identity,
        create_product_agent_identity,
        create_supervisor_agent_identity,
        create_ua_agent_identity,
    )

    registry = registry or create_agent_registry()

    registry.register(create_supervisor_agent_identity())
    registry.register(create_ua_agent_identity())
    registry.register(create_creative_agent_identity())
    registry.register(create_monetization_agent_identity())
    registry.register(create_product_agent_identity())
    registry.register(create_liveops_agent_identity())
    registry.register(create_game_designer_agent_identity())
    registry.register(create_numerical_designer_agent_identity())
    registry.register(create_data_analyst_agent_identity())
    registry.register(create_player_support_agent_identity())

    return registry