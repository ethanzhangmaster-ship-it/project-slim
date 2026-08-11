"""E12.3 — Base Business Intelligence Agent。

所有业务 Agent 的抽象基类，定义统一的决策生成接口。

设计原则：
  - 输入：分析域 Snapshot（Lifecycle/Funnel/Retention/Monetization）
  - 输出：OptimizationAction 列表（可执行建议）
  - 每个 Action 包含：类型、目标、优先级、预期收益、证据
  - Mock 友好：无 analyzer 时自动生成 mock 建议
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ActionPriority(str, Enum):
    """行动优先级。"""

    P0_CRITICAL = "p0"    # 立即执行（如暂停亏损 campaign）
    P1_HIGH = "p1"        # 尽快执行（如修复严重流失点）
    P2_MEDIUM = "p2"      # 计划执行（如优化 Offer 定价）
    P3_LOW = "p3"         # 观察记录（如小幅 CTR 下降）


@dataclass
class OptimizationAction:
    """优化行动建议。

    这是所有业务 Agent 的统一输出格式。

    Attributes:
        action_id:         行动 ID
        agent_type:        Agent 类型 (product/monetization/ua)
        action_type:       行动类型 (如 fix_funnel, adjust_price, scale_campaign)
        target:            目标对象 (如 "level_15", "offer_starter_pack", "camp_001")
        priority:          优先级
        expected_impact:   预期影响 (如 "D7留存+5%", "收入+15%", "ROAS+20%")
        confidence:        置信度 (0-1)
        evidence:          证据列表
        recommendation:    具体建议
        metadata:          额外元数据
        created_at:        创建时间
    """

    action_id: str = ""
    agent_type: str = ""
    action_type: str = ""
    target: str = ""
    priority: ActionPriority = ActionPriority.P2_MEDIUM
    expected_impact: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "agent_type": self.agent_type,
            "action_type": self.action_type,
            "target": self.target,
            "priority": self.priority.value,
            "expected_impact": self.expected_impact,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"OptimizationAction(type={self.action_type}, "
            f"target={self.target}, "
            f"priority={self.priority.value}, "
            f"confidence={self.confidence:.2f})"
        )


class BaseAgent:
    """业务 Agent 抽象基类。

    子类必须实现 _generate_actions() 方法。

    Attributes:
        agent_type:    Agent 类型标识
        total_decisions: 累计决策数
    """

    agent_type: str = "base"

    def __init__(self) -> None:
        self.total_decisions: int = 0

    def decide(self, *args, **kwargs) -> list[OptimizationAction]:
        """生成优化决策。

        子类实现 _generate_actions() 提供具体逻辑。

        Returns:
            OptimizationAction 列表
        """
        actions = self._generate_actions(*args, **kwargs)

        # 按 priority 排序
        priority_order = {
            ActionPriority.P0_CRITICAL: 0,
            ActionPriority.P1_HIGH: 1,
            ActionPriority.P2_MEDIUM: 2,
            ActionPriority.P3_LOW: 3,
        }
        actions.sort(key=lambda a: priority_order.get(a.priority, 99))

        self.total_decisions += len(actions)

        logger.info(
            f"{self.__class__.__name__}: generated {len(actions)} actions "
            f"(total: {self.total_decisions})"
        )
        return actions

    def _generate_actions(self, *args, **kwargs) -> list[OptimizationAction]:
        """子类实现：生成具体优化行动。"""
        raise NotImplementedError

    def _create_action(
        self,
        action_type: str,
        target: str,
        priority: ActionPriority,
        expected_impact: str,
        confidence: float,
        evidence: list[str],
        recommendation: str,
        **metadata: Any,
    ) -> OptimizationAction:
        """便捷创建 OptimizationAction。"""
        return OptimizationAction(
            agent_type=self.agent_type,
            action_type=action_type,
            target=target,
            priority=priority,
            expected_impact=expected_impact,
            confidence=confidence,
            evidence=evidence,
            recommendation=recommendation,
            metadata=metadata,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(decisions={self.total_decisions})"
