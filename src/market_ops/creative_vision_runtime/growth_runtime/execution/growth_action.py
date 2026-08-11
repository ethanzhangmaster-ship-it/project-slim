"""E15.0.9 Growth Action — 统一执行动作模型.

GrowthAction 是 E15.0.9 Execution Adapter Layer 的核心输入模型，
提供比 ExecutionAction 更简洁、更高层的动作抽象，
让 Agent 不关心具体平台 API 实现细节。

设计原则:
  - 平台无关: 同一 ActionType 可路由到不同平台 Adapter
  - 参数灵活: 使用 dict 而非强类型字段，适配不同平台需求
  - 可审计: 包含 game_id / action_id / created_at 等追踪字段

与 E13.6 ExecutionAction 的关系:
  GrowthAction (高层) → Adapter → ExecutionAction (底层) → BaseExecutor → Platform API
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Action Type
# ═══════════════════════════════════════════════════════════════


class ActionType(str, Enum):
    """E15.0.9 统一动作类型 — 平台无关的高层动作分类.

    与 E13.6 ExecutionActionType 的关系:
      ActionType 是高层抽象，ExecutionActionType 是底层原子操作。
      Adapter 负责将 ActionType 映射到对应的 ExecutionActionType。
    """

    # ── Meta Ads 操作 ──────────────────────────────────────
    UPDATE_CAMPAIGN_BUDGET = "update_campaign_budget"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    CREATE_CAMPAIGN = "create_campaign"
    UPLOAD_CREATIVE = "upload_creative"
    PAUSE_CREATIVE = "pause_creative"

    # ── Google Play 操作 ───────────────────────────────────
    PUBLISH_RELEASE = "publish_release"
    UPDATE_STORE_METADATA = "update_store_metadata"
    START_ROLLOUT = "start_rollout"

    # ── Creative 操作 ──────────────────────────────────────
    GENERATE_CREATIVE = "generate_creative"
    MUTATE_CREATIVE = "mutate_creative"

    # ── Adjust 操作 ────────────────────────────────────────
    VERIFY_ATTRIBUTION = "verify_attribution"
    SYNC_METADATA = "sync_metadata"

    # ── 通用 ───────────────────────────────────────────────
    MONITOR = "monitor"
    NOOP = "noop"


# ═══════════════════════════════════════════════════════════════
# Growth Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthAction:
    """统一执行动作 — E15.0.9 Execution Adapter Layer 核心输入模型.

    与 E13.6 ExecutionAction 的区别:
      - GrowthAction: 高层业务语义 (e.g. "把 campaign_123 预算从 100 调到 120")
      - ExecutionAction: 底层平台操作 (e.g. "POST /campaign_123 body={daily_budget: 12000}")

    Attributes:
        action_id:   动作唯一标识 (UUID)
        game_id:     游戏 ID (e.g. "merge_witch")
        action_type: 动作类型 (平台无关)
        target:      目标实体 (campaign_id / creative_id / package_name)
        parameters:  动作参数 (灵活 dict)
        created_at:  创建时间 (ISO 8601)
        priority:    优先级 (critical / high / medium / low)
        metadata:    扩展元数据 (来源决策 ID 等)
    """

    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str = ""
    action_type: ActionType = ActionType.NOOP
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "game_id": self.game_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "parameters": self.parameters,
            "created_at": self.created_at,
            "priority": self.priority,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrowthAction":
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            game_id=data.get("game_id", ""),
            action_type=ActionType(data.get("action_type", "noop")),
            target=data.get("target", ""),
            parameters=data.get("parameters", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            priority=data.get("priority", "medium"),
            metadata=data.get("metadata", {}),
        )

    # ── Properties ───────────────────────────────────────────

    @property
    def is_meta_action(self) -> bool:
        return self.action_type in {
            ActionType.UPDATE_CAMPAIGN_BUDGET,
            ActionType.PAUSE_CAMPAIGN,
            ActionType.RESUME_CAMPAIGN,
            ActionType.CREATE_CAMPAIGN,
            ActionType.UPLOAD_CREATIVE,
            ActionType.PAUSE_CREATIVE,
        }

    @property
    def is_play_action(self) -> bool:
        return self.action_type in {
            ActionType.PUBLISH_RELEASE,
            ActionType.UPDATE_STORE_METADATA,
            ActionType.START_ROLLOUT,
        }

    @property
    def is_creative_action(self) -> bool:
        return self.action_type in {
            ActionType.GENERATE_CREATIVE,
            ActionType.MUTATE_CREATIVE,
        }

    @property
    def is_adjust_action(self) -> bool:
        return self.action_type in {
            ActionType.VERIFY_ATTRIBUTION,
            ActionType.SYNC_METADATA,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthAction(id={self.action_id[:8]}..., "
            f"type={self.action_type.value}, "
            f"target={self.target}, "
            f"game={self.game_id})"
        )


# ═══════════════════════════════════════════════════════════════
# Factory Helpers
# ═══════════════════════════════════════════════════════════════


def create_budget_action(
    game_id: str,
    campaign_id: str,
    old_budget: float,
    new_budget: float,
    **kwargs: Any,
) -> GrowthAction:
    """创建预算调整动作."""
    return GrowthAction(
        game_id=game_id,
        action_type=ActionType.UPDATE_CAMPAIGN_BUDGET,
        target=campaign_id,
        parameters={
            "old_budget": old_budget,
            "new_budget": new_budget,
        },
        **kwargs,
    )


def create_pause_action(
    game_id: str,
    campaign_id: str,
    **kwargs: Any,
) -> GrowthAction:
    """创建暂停广告系列动作."""
    return GrowthAction(
        game_id=game_id,
        action_type=ActionType.PAUSE_CAMPAIGN,
        target=campaign_id,
        **kwargs,
    )


def create_resume_action(
    game_id: str,
    campaign_id: str,
    **kwargs: Any,
) -> GrowthAction:
    """创建恢复广告系列动作."""
    return GrowthAction(
        game_id=game_id,
        action_type=ActionType.RESUME_CAMPAIGN,
        target=campaign_id,
        **kwargs,
    )


def create_upload_creative_action(
    game_id: str,
    asset_id: str,
    platform: str = "meta",
    **kwargs: Any,
) -> GrowthAction:
    """创建上传素材动作."""
    return GrowthAction(
        game_id=game_id,
        action_type=ActionType.UPLOAD_CREATIVE,
        target=platform,
        parameters={"asset_id": asset_id},
        **kwargs,
    )


def create_publish_release_action(
    game_id: str,
    package_name: str,
    version: str,
    track: str = "production",
    **kwargs: Any,
) -> GrowthAction:
    """创建发布商店版本动作."""
    return GrowthAction(
        game_id=game_id,
        action_type=ActionType.PUBLISH_RELEASE,
        target=package_name,
        parameters={
            "track": track,
            "version": version,
        },
        **kwargs,
    )


__all__ = [
    "ActionType",
    "GrowthAction",
    "create_budget_action",
    "create_pause_action",
    "create_resume_action",
    "create_upload_creative_action",
    "create_publish_release_action",
]