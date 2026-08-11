"""E13.6.5 DecisionMemorySync — 决策生命周期同步.

Day 6.5 核心模块:
  管理 DecisionMemory 中决策的完整生命周期，连接 DecisionEngine 与 ExecutionResultBridge，
  使 DecisionMemory 从"被动记录"升级为"主动同步"。

核心职责:
  1. DecisionStatus 生命周期管理 (CREATED → EXECUTING → COMPLETED/FAILED/EXPIRED)
  2. DecisionMemoryRecord 增强数据模型 (含 execution_id, reward, status)
  3. 执行结果同步 (ExecutionResult → DecisionMemory 更新)
  4. 决策评估 (reward 计算)
  5. 为 Pattern 提取提供已完成的决策

决策生命周期:
  CREATED ──→ EXECUTING ──→ COMPLETED
                            ├──→ FAILED
                            └──→ EXPIRED (超时未完成)

与 ExecutionResultBridge 的集成:
  ExecutionResultBridge.capture() → DecisionMemorySync.mark_executing()
  ExecutionResultBridge.evaluate() → DecisionMemorySync.sync_execution_result()

与 DecisionPatternSync 的集成:
  DecisionMemorySync.get_completed_decisions() → DecisionPatternSync.extract_learning_cases()

用法:
    sync = DecisionMemorySync(decision_memory)
    sync.record_decision(decision_output)
    # ... 执行 ...
    sync.mark_executing(decision_id, execution_id)
    # ... 执行完成 ...
    sync.sync_execution_result(
        decision_id=decision_id,
        status="success",
        metrics={"roas_change": 0.15, "ctr_change": 0.02},
    )
    # 提取已完成决策用于 Pattern 学习
    completed = sync.get_completed_decisions()
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .decision_memory import DecisionExperience, DecisionMemory
from .models import DecisionOutput


# ═══════════════════════════════════════════════════════════════
# DecisionStatus
# ═══════════════════════════════════════════════════════════════


class DecisionStatus(str, Enum):
    """决策生命周期状态.

    | 状态       | 说明               |
    |-----------|-------------------|
    | CREATED   | 决策已创建，等待执行 |
    | EXECUTING | 正在执行中          |
    | COMPLETED | 执行成功完成        |
    | FAILED    | 执行失败            |
    | EXPIRED   | 超时未完成，已过期  |
    """
    CREATED = "created"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        """是否为终态."""
        return self in {DecisionStatus.COMPLETED, DecisionStatus.FAILED, DecisionStatus.EXPIRED}

    @property
    def is_active(self) -> bool:
        """是否为活跃状态."""
        return self in {DecisionStatus.CREATED, DecisionStatus.EXECUTING}


# ═══════════════════════════════════════════════════════════════
# 状态转换规则
# ═══════════════════════════════════════════════════════════════

VALID_TRANSITIONS: dict[DecisionStatus, set[DecisionStatus]] = {
    DecisionStatus.CREATED:   {DecisionStatus.EXECUTING, DecisionStatus.EXPIRED},
    DecisionStatus.EXECUTING: {DecisionStatus.COMPLETED, DecisionStatus.FAILED, DecisionStatus.EXPIRED},
    DecisionStatus.COMPLETED: set(),   # 终态
    DecisionStatus.FAILED:    set(),   # 终态
    DecisionStatus.EXPIRED:   set(),   # 终态
}


# ═══════════════════════════════════════════════════════════════
# DecisionMemoryRecord
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionMemoryRecord:
    """增强的决策记忆记录 — 比 DecisionExperience 更丰富的生命周期信息.

    在 DecisionExperience 基础上增加:
      - status: 决策生命周期状态
      - execution_id: 关联的执行 ID
      - reward: 评估后的奖励
      - decision_context: 决策时的完整上下文
      - decision_detail: 决策内容详情
      - outcome_detail: 执行结果详情

    Attributes:
        decision_id: 决策唯一标识
        opportunity_type: 机会类型
        action_type: 动作类型
        strategy_id: 策略 ID
        strategy_name: 策略名称
        confidence: 决策置信度
        risk_score: 决策风险评分
        final_score: 最终评分
        status: 生命周期状态
        execution_id: 关联的执行 ID
        reward: 评估奖励 [-1, 1]
        success: 是否成功
        decision_context: 决策上下文 (product, platform, metrics 等)
        decision_detail: 决策内容 (action, budget_change, target 等)
        outcome_detail: 执行结果 (roas_change, revenue_change 等)
        created_at: 决策时间
        completed_at: 完成时间
        lessons: 经验教训
        metadata: 扩展元数据
    """
    decision_id: str = ""
    opportunity_type: str = ""
    action_type: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    confidence: float = 0.0
    risk_score: float = 0.0
    final_score: float = 0.0
    status: DecisionStatus = DecisionStatus.CREATED
    execution_id: str | None = None
    reward: float | None = None
    success: bool | None = None
    decision_context: dict[str, Any] = field(default_factory=dict)
    decision_detail: dict[str, Any] = field(default_factory=dict)
    outcome_detail: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    lessons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_decision_output(
        cls,
        output: DecisionOutput,
        opportunity_type: str = "",
    ) -> DecisionMemoryRecord:
        """从 DecisionOutput 创建记录.

        Args:
            output: 决策输出
            opportunity_type: 机会类型

        Returns:
            DecisionMemoryRecord
        """
        action_type = ""
        if output.action_plan:
            action_type = output.action_plan.action_type

        return cls(
            decision_id=output.decision_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
            strategy_id=output.strategy_id,
            strategy_name=output.strategy_name,
            confidence=output.confidence,
            risk_score=output.risk_score,
            final_score=output.final_score,
            status=DecisionStatus.CREATED,
            decision_context={
                "opportunity_id": output.opportunity_id,
                "decision_type": output.decision_type.value,
                "risk_level": output.risk_level,
                "requires_approval": output.requires_approval,
            },
            decision_detail=output.action_plan.to_dict() if output.action_plan else {},
            metadata=output.metadata,
        )

    @classmethod
    def from_decision_experience(
        cls,
        exp: DecisionExperience,
    ) -> DecisionMemoryRecord:
        """从 DecisionExperience 创建记录.

        Args:
            exp: DecisionExperience 实例

        Returns:
            DecisionMemoryRecord
        """
        action_type = ""
        if exp.action_plan:
            action_type = exp.action_plan.get("action_type", "")

        # 推断状态
        status = DecisionStatus.CREATED
        if exp.is_resolved:
            status = DecisionStatus.COMPLETED if exp.is_success else DecisionStatus.FAILED
        elif exp.result == "executing":
            status = DecisionStatus.EXECUTING

        # 计算 reward
        reward = cls._compute_reward_from_metrics(
            exp.result_metrics, exp.result,
        )

        return cls(
            decision_id=exp.decision_id,
            opportunity_type=exp.opportunity_type,
            action_type=action_type,
            strategy_id=exp.strategy_id,
            strategy_name=exp.strategy_name,
            confidence=exp.confidence,
            risk_score=exp.risk_score,
            final_score=exp.final_score,
            status=status,
            execution_id=exp.metadata.get("execution_id") if exp.metadata else None,
            reward=reward,
            success=exp.is_success,
            decision_context={
                "opportunity_id": exp.opportunity_id,
                "decision_type": exp.decision_type,
            },
            decision_detail=exp.action_plan,
            outcome_detail=exp.result_metrics,
            created_at=exp.created_at,
            completed_at=exp.resolved_at if exp.resolved_at else None,
            lessons=exp.lessons_learned,
            metadata=exp.metadata,
        )

    @staticmethod
    def _compute_reward_from_metrics(
        metrics: dict[str, Any],
        result: str,
    ) -> float:
        """从指标计算奖励."""
        if result == "failure":
            return -1.0
        if not metrics:
            return 0.0

        reward = 0.0
        count = 0
        roas = metrics.get("roas_change", 0)
        if isinstance(roas, (int, float)) and roas != 0:
            reward += 1.0 if roas > 0 else -0.5
            count += 1
        ctr = metrics.get("ctr_change", 0)
        if isinstance(ctr, (int, float)) and ctr != 0:
            reward += 0.5 if ctr > 0 else -0.3
            count += 1
        return round(reward / max(count, 1), 4) if count > 0 else 0.0

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "final_score": round(self.final_score, 4),
            "status": self.status.value,
            "execution_id": self.execution_id,
            "reward": round(self.reward, 4) if self.reward is not None else None,
            "success": self.success,
            "decision_context": self.decision_context,
            "decision_detail": self.decision_detail,
            "outcome_detail": self.outcome_detail,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "lessons": self.lessons,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# DecisionMemorySync
# ═══════════════════════════════════════════════════════════════


class DecisionMemorySync:
    """E13.6.5 DecisionMemorySync — 决策生命周期同步器.

    管理决策从创建到完成的完整生命周期，连接 DecisionEngine 与 Execution 层。

    核心流程:
      DecisionEngine.decide() → DecisionMemorySync.record_decision()
      ExecutionManager.execute() → DecisionMemorySync.mark_executing()
      ExecutionResultBridge.evaluate() → DecisionMemorySync.sync_execution_result()
      DecisionPatternSync.extract() → DecisionMemorySync.get_completed_decisions()

    Attributes:
        memory: 底层 DecisionMemory 实例
        _records: DecisionMemoryRecord 索引 (decision_id → record)
        _expiration_hours: 决策过期时间 (小时)
    """

    # 默认过期时间: 7 天
    DEFAULT_EXPIRATION_HOURS = 168.0

    def __init__(
        self,
        decision_memory: DecisionMemory | None = None,
        expiration_hours: float = 168.0,
    ):
        """初始化同步器.

        Args:
            decision_memory: DecisionMemory 实例 (默认创建)
            expiration_hours: 决策过期时间 (小时)
        """
        self.memory = decision_memory or DecisionMemory()
        self._expiration_hours = expiration_hours
        # 增强索引: decision_id → DecisionMemoryRecord
        self._records: dict[str, DecisionMemoryRecord] = {}

    # ═══════════════════════════════════════════════════════════
    # 记录决策
    # ═══════════════════════════════════════════════════════════

    def record_decision(
        self,
        decision: DecisionOutput,
        opportunity_type: str = "",
    ) -> DecisionMemoryRecord:
        """记录决策 (决策产生时调用).

        Args:
            decision: 决策输出
            opportunity_type: 机会类型

        Returns:
            DecisionMemoryRecord: 创建的记忆记录
        """
        # 写入底层 DecisionMemory
        self.memory.record_decision(decision, opportunity_type=opportunity_type)

        # 创建增强记录
        record = DecisionMemoryRecord.from_decision_output(
            decision, opportunity_type=opportunity_type,
        )
        self._records[record.decision_id] = record
        return record

    # ═══════════════════════════════════════════════════════════
    # 状态转换
    # ═══════════════════════════════════════════════════════════

    def mark_executing(
        self,
        decision_id: str,
        execution_id: str | None = None,
    ) -> DecisionMemoryRecord:
        """标记决策开始执行.

        Args:
            decision_id: 决策 ID
            execution_id: 关联的执行 ID

        Returns:
            DecisionMemoryRecord: 更新后的记录

        Raises:
            ValueError: 如果决策不存在或状态不合法
        """
        record = self._get_record(decision_id)
        new_status = DecisionStatus.EXECUTING
        self._validate_transition(record.status, new_status)

        record.status = new_status
        record.execution_id = execution_id or str(uuid.uuid4())[:8]
        return record

    def sync_execution_result(
        self,
        decision_id: str,
        status: str,
        metrics: dict[str, Any] | None = None,
        reason: str = "",
        lessons: list[str] | None = None,
    ) -> DecisionMemoryRecord:
        """同步执行结果 (执行完成后调用).

        Args:
            decision_id: 决策 ID
            status: 结果状态 (success/failure/partial)
            metrics: 结果指标
            reason: 结果原因
            lessons: 经验教训

        Returns:
            DecisionMemoryRecord: 更新后的记录

        Raises:
            ValueError: 如果决策不存在或状态不合法
        """
        record = self._get_record(decision_id)

        # 映射 status → DecisionStatus
        new_status = self._map_result_status(status)
        self._validate_transition(record.status, new_status)

        # 更新底层 DecisionMemory
        self.memory.record_outcome(
            decision_id=decision_id,
            result=status,
            metrics=metrics or {},
            reason=reason,
            lessons=lessons,
        )

        # 更新增强记录
        record.status = new_status
        if new_status == DecisionStatus.COMPLETED:
            record.success = True
        elif new_status == DecisionStatus.FAILED:
            record.success = False
        record.outcome_detail = metrics or {}
        record.reward = self._compute_reward(
            metrics=metrics or {},
            result=status,
        )
        record.completed_at = datetime.now(timezone.utc).isoformat()
        if lessons:
            record.lessons = lessons

        return record

    def expire_decision(self, decision_id: str) -> DecisionMemoryRecord:
        """标记决策过期.

        Args:
            decision_id: 决策 ID

        Returns:
            DecisionMemoryRecord: 更新后的记录
        """
        record = self._get_record(decision_id)
        if record.status.is_terminal:
            return record  # 已是终态，无需操作

        record.status = DecisionStatus.EXPIRED
        record.completed_at = datetime.now(timezone.utc).isoformat()
        return record

    def expire_stale_decisions(self) -> int:
        """过期所有超时的活跃决策.

        Returns:
            int: 已过期的决策数
        """
        now = datetime.now(timezone.utc)
        expired_count = 0

        for record in list(self._records.values()):
            if record.status.is_terminal:
                continue
            try:
                created = datetime.fromisoformat(record.created_at)
                age_hours = (now - created).total_seconds() / 3600
                if age_hours >= self._expiration_hours:
                    self.expire_decision(record.decision_id)
                    expired_count += 1
            except (ValueError, TypeError):
                pass

        return expired_count

    # ═══════════════════════════════════════════════════════════
    # 决策评估
    # ═══════════════════════════════════════════════════════════

    def evaluate_decision(
        self,
        decision_id: str,
    ) -> dict[str, Any]:
        """评估决策 (计算 reward).

        Args:
            decision_id: 决策 ID

        Returns:
            dict: {
                "decision_id": 决策ID,
                "reward": 奖励值,
                "success": 是否成功,
                "status": 生命周期状态,
                "metrics": 结果指标,
                "lessons": 经验教训,
            }
        """
        record = self._get_record(decision_id)

        return {
            "decision_id": record.decision_id,
            "reward": record.reward,
            "success": record.success,
            "status": record.status.value,
            "opportunity_type": record.opportunity_type,
            "action_type": record.action_type,
            "confidence": record.confidence,
            "metrics": record.outcome_detail,
            "lessons": record.lessons,
            "completed_at": record.completed_at,
        }

    # ═══════════════════════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════════════════════

    def get_record(self, decision_id: str) -> DecisionMemoryRecord | None:
        """获取决策记录."""
        return self._records.get(decision_id)

    def get_completed_decisions(
        self,
        opportunity_type: str = "",
        action_type: str = "",
        min_samples: int = 0,
    ) -> list[DecisionMemoryRecord]:
        """获取已完成的决策 (用于 Pattern 提取).

        Args:
            opportunity_type: 机会类型过滤 (可选)
            action_type: 动作类型过滤 (可选)
            min_samples: 最少样本数

        Returns:
            list[DecisionMemoryRecord]: 已完成的决策记录
        """
        completed = [
            r for r in self._records.values()
            if r.is_terminal and r.success is not None
        ]

        if opportunity_type:
            completed = [
                r for r in completed
                if r.opportunity_type == opportunity_type
            ]
        if action_type:
            completed = [
                r for r in completed
                if r.action_type == action_type
            ]

        if min_samples > 0 and len(completed) < min_samples:
            return []

        return completed

    def get_active_decisions(self) -> list[DecisionMemoryRecord]:
        """获取活跃中的决策."""
        return [r for r in self._records.values() if r.is_active]

    def get_pending_sync(self) -> list[DecisionMemoryRecord]:
        """获取等待执行结果同步的决策 (EXECUTING 状态)."""
        return [
            r for r in self._records.values()
            if r.status == DecisionStatus.EXECUTING
        ]

    def get_by_execution(self, execution_id: str) -> DecisionMemoryRecord | None:
        """按执行 ID 查找决策."""
        for r in self._records.values():
            if r.execution_id == execution_id:
                return r
        return None

    def get_by_opportunity_type(
        self,
        opportunity_type: str,
    ) -> list[DecisionMemoryRecord]:
        """按机会类型查找决策."""
        return [
            r for r in self._records.values()
            if r.opportunity_type == opportunity_type
        ]

    # ═══════════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════════

    def stats(self) -> dict[str, Any]:
        """获取决策同步统计."""
        total = len(self._records)
        completed = [r for r in self._records.values() if r.status == DecisionStatus.COMPLETED]
        failed = [r for r in self._records.values() if r.status == DecisionStatus.FAILED]
        expired = [r for r in self._records.values() if r.status == DecisionStatus.EXPIRED]
        executing = [r for r in self._records.values() if r.status == DecisionStatus.EXECUTING]
        created = [r for r in self._records.values() if r.status == DecisionStatus.CREATED]

        resolved = completed + failed
        success_count = sum(1 for r in resolved if r.success)

        return {
            "total": total,
            "created": len(created),
            "executing": len(executing),
            "completed": len(completed),
            "failed": len(failed),
            "expired": len(expired),
            "success_rate": round(
                success_count / len(resolved), 4,
            ) if resolved else 0.0,
            "avg_reward": round(
                sum(r.reward for r in resolved if r.reward is not None) / max(len(resolved), 1), 4,
            ),
            "terminated": len(resolved) + len(expired),
            "active": len(created) + len(executing),
        }

    def get_success_rate_by_action(self) -> dict[str, dict[str, Any]]:
        """按动作类型统计成功率."""
        action_groups: dict[str, list[DecisionMemoryRecord]] = {}
        for r in self._records.values():
            if not r.is_terminal or r.success is None:
                continue
            action = r.action_type or "unknown"
            if action not in action_groups:
                action_groups[action] = []
            action_groups[action].append(r)

        result: dict[str, dict[str, Any]] = {}
        for action, records in action_groups.items():
            success_count = sum(1 for r in records if r.success)
            rewards = [r.reward for r in records if r.reward is not None]
            result[action] = {
                "total": len(records),
                "successes": success_count,
                "success_rate": round(success_count / len(records), 4),
                "avg_reward": round(sum(rewards) / len(rewards), 4) if rewards else 0.0,
            }

        return result

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    def _get_record(self, decision_id: str) -> DecisionMemoryRecord:
        """获取记录 (不存在则抛异常)."""
        record = self._records.get(decision_id)
        if record is None:
            raise ValueError(f"Decision '{decision_id}' not found in DecisionMemorySync")
        return record

    @staticmethod
    def _validate_transition(
        current: DecisionStatus,
        target: DecisionStatus,
    ) -> None:
        """验证状态转换合法性."""
        valid = VALID_TRANSITIONS.get(current, set())
        if target not in valid:
            raise ValueError(
                f"Invalid status transition: {current.value} → {target.value}. "
                f"Valid transitions from '{current.value}': "
                f"{[v.value for v in valid]}"
            )

    @staticmethod
    def _map_result_status(result: str) -> DecisionStatus:
        """映射执行结果 → DecisionStatus."""
        status_map = {
            "success": DecisionStatus.COMPLETED,
            "failure": DecisionStatus.FAILED,
            "partial": DecisionStatus.COMPLETED,  # 部分成功也算完成
        }
        return status_map.get(result, DecisionStatus.FAILED)

    @staticmethod
    def _compute_reward(
        metrics: dict[str, Any],
        result: str,
    ) -> float:
        """计算奖励.

        Args:
            metrics: 结果指标
            result: 执行结果

        Returns:
            float: 奖励 [-1, 1]
        """
        if result == "failure":
            return -1.0

        if not metrics:
            return 0.0

        reward = 0.0
        count = 0

        roas = metrics.get("roas_change", metrics.get("roas", 0))
        if isinstance(roas, (int, float)) and roas != 0:
            reward += 1.0 if roas > 0 else -0.5
            count += 1

        ctr = metrics.get("ctr_change", metrics.get("ctr", 0))
        if isinstance(ctr, (int, float)) and ctr != 0:
            reward += 0.5 if ctr > 0 else -0.3
            count += 1

        cvr = metrics.get("cvr_change", metrics.get("cvr", 0))
        if isinstance(cvr, (int, float)) and cvr != 0:
            reward += 0.5 if cvr > 0 else -0.3
            count += 1

        return round(reward / max(count, 1), 4) if count > 0 else 0.0

    # ═══════════════════════════════════════════════════════════
    # 管理
    # ═══════════════════════════════════════════════════════════

    def clear(self) -> None:
        """清空所有记录."""
        self._records.clear()
        self.memory.clear()

    def reset(self) -> None:
        """重置同步器."""
        self.clear()

    @property
    def total_records(self) -> int:
        return len(self._records)

    @property
    def completed_count(self) -> int:
        return sum(
            1 for r in self._records.values()
            if r.status == DecisionStatus.COMPLETED
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for r in self._records.values()
            if r.status == DecisionStatus.FAILED
        )

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"DecisionMemorySync(total={s['total']}, "
            f"active={s['active']}, "
            f"completed={s['completed']}, "
            f"failed={s['failed']})"
        )


__all__ = [
    "DecisionStatus",
    "DecisionMemoryRecord",
    "DecisionMemorySync",
    "VALID_TRANSITIONS",
]