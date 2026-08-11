"""E15.0.1 Growth Decision Audit — 决策审计数据模型.

记录 Agent 每一次决策的完整上下文:
  - 输入上下文 (input_context)
  - 检测到的问题 (detected_problem)
  - 决策内容 (decision)
  - 执行动作 (action)
  - 置信度 (confidence)
  - 执行状态 (execution_status)
  - 执行结果 (result)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """决策执行状态."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class GrowthDecisionAudit:
    """增长决策审计记录 — 单次 Agent 决策的完整追溯.

    Attributes:
        audit_id:          审计唯一标识
        timestamp:         决策时间
        agent_id:          Agent 标识
        game_id:           游戏/产品 ID
        input_context:     输入上下文 (Reality 数据摘要)
        detected_problem:  检测到的问题描述
        decision:          决策内容
        action:            执行动作
        confidence:        决策置信度 [0, 1]
        execution_status:  执行状态
        result:            执行结果 (ROAS变化、预算变化等)
        plan_id:           关联的增长计划 ID
        cycle_id:          关联的周期 ID
        safety_decision:   安全决策结果
        rollback_record_id: 回滚记录 ID
        metadata:          扩展元数据
    """

    audit_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: str = ""
    game_id: str = ""

    # 决策上下文
    input_context: dict[str, Any] = field(default_factory=dict)
    detected_problem: str = ""

    # 决策与执行
    decision: str = ""
    action: str = ""
    confidence: float = 0.0
    execution_status: ExecutionStatus = ExecutionStatus.PENDING

    # 结果
    result: dict[str, Any] = field(default_factory=dict)

    # 关联
    plan_id: str = ""
    cycle_id: str = ""
    safety_decision: str = ""
    rollback_record_id: str = ""

    # 扩展
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────

    @property
    def is_success(self) -> bool:
        return self.execution_status == ExecutionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.execution_status == ExecutionStatus.FAILED

    @property
    def needs_attention(self) -> bool:
        return self.execution_status in (
            ExecutionStatus.PENDING,
            ExecutionStatus.REJECTED,
            ExecutionStatus.FAILED,
        )

    @property
    def was_rolled_back(self) -> bool:
        return self.execution_status == ExecutionStatus.ROLLED_BACK

    # ── Serialization ───────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "game_id": self.game_id,
            "input_context": self.input_context,
            "detected_problem": self.detected_problem,
            "decision": self.decision,
            "action": self.action,
            "confidence": self.confidence,
            "execution_status": self.execution_status.value,
            "result": self.result,
            "plan_id": self.plan_id,
            "cycle_id": self.cycle_id,
            "safety_decision": self.safety_decision,
            "rollback_record_id": self.rollback_record_id,
            "metadata": self.metadata,
        }

    def to_summary(self) -> dict[str, Any]:
        """生成审计摘要 (用于报告)."""
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "game_id": self.game_id,
            "detected_problem": self.detected_problem,
            "decision": self.decision,
            "confidence": self.confidence,
            "execution_status": self.execution_status.value,
            "result_summary": {
                k: v for k, v in self.result.items()
                if k in ("roas_before", "roas_after", "roas_after_7d", "budget_change", "status")
            },
        }