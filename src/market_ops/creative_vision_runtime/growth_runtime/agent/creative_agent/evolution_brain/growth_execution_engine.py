"""E14.7.2 Growth Execution Engine — 增长执行引擎.

E14.7「Autonomous Growth Execution Layer」第二层:
  将 GrowthActionRouter 发出的 GrowthAction 转化为真实执行结果.

职责:
  1. 执行器注册中心 (Executor Registry) — 动作类型 → 执行器映射
  2. 执行 GrowthAction — 调用对应执行器
  3. 批量执行与并发控制
  4. 错误处理与回滚
  5. 执行统计与监控

核心概念:
  - ExecutionStatus: 执行状态 (PENDING / RUNNING / SUCCESS / FAILED / PARTIAL)
  - ExecutionOutcome: 执行结果
  - BaseExecutor: 执行器抽象接口
  - CreativeExecutor: 创意执行器 (CREATE_CREATIVE / MUTATE_CREATIVE / CREATE_VARIANTS)
  - MetaAdsExecutor: Meta Ads 执行器 (PROMOTE_WINNER / SCALE_CAMPAIGN / REDUCE_BUDGET / PAUSE_CAMPAIGN)
  - ExperimentExecutor: 实验执行器 (START_EXPERIMENT / END_EXPERIMENT)
  - EvolutionExecutor: 进化执行器 (DIVERSIFY_POPULATION)
  - GrowthExecutionEngine: 核心执行引擎

数据流:
  GrowthAction (E14.7.1)
       ↓
  GrowthExecutionEngine.execute()
       ↓
  BaseExecutor → ExecutionOutcome
       ↓
  Reality Data (E13 / E11 / E14.6.2)
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionStatus,
    ActionPriority,
    ACTION_TO_EXECUTOR,
)


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class ExecutionStatus(str, Enum):
    """执行状态.

    PENDING  — 待执行
    RUNNING  — 执行中
    SUCCESS  — 执行成功
    FAILED   — 执行失败
    PARTIAL  — 部分成功 (批量执行中部分失败)
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutionOutcome:
    """执行结果.

    代表一次 GrowthAction 的执行结果.

    Attributes:
        execution_id: 执行 ID
        action_id: 对应 GrowthAction ID
        action_type: 动作类型
        status: 执行状态
        executor: 执行器名称
        output: 执行输出 (生成的 genome_ids / campaign_ids / experiment_ids)
        error: 错误信息
        duration_ms: 执行耗时 (毫秒)
        created_at: 创建时间
        metadata: 扩展元数据
    """
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    action_id: str = ""
    action_type: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    executor: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "status": self.status.value,
            "executor": self.executor,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "is_success": self.is_success,
            "is_failed": self.is_failed,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════
# 执行器抽象
# ═══════════════════════════════════════════════════════════

class BaseExecutor(ABC):
    """执行器抽象基类.

    所有执行器必须实现 execute 方法.

    用法:
        class MyExecutor(BaseExecutor):
            def execute(self, action: GrowthAction) -> ExecutionOutcome:
                return ExecutionOutcome(status=ExecutionStatus.SUCCESS)
    """

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

    @abstractmethod
    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        """执行 GrowthAction.

        Args:
            action: 待执行的 GrowthAction

        Returns:
            ExecutionOutcome: 执行结果
        """
        ...

    def validate(self, action: GrowthAction) -> bool:
        """验证动作是否可执行.

        Args:
            action: 待验证动作

        Returns:
            bool: 是否可通过验证
        """
        return True

    def _record_execution(self, outcome: ExecutionOutcome) -> None:
        """记录执行统计."""
        self._execution_count += 1
        if outcome.is_success:
            self._success_count += 1
        elif outcome.is_failed:
            self._failure_count += 1

    def stats(self) -> dict[str, Any]:
        """获取执行器统计."""
        return {
            "executor": self.name,
            "total": self._execution_count,
            "success": self._success_count,
            "failure": self._failure_count,
            "success_rate": round(
                self._success_count / max(self._execution_count, 1), 4
            ),
        }


# ═══════════════════════════════════════════════════════════
# 1. Creative Executor
# ═══════════════════════════════════════════════════════════

class CreativeExecutor(BaseExecutor):
    """创意执行器 — 负责创意生成与变异.

    处理动作类型:
      - CREATE_CREATIVE   → 创建新创意
      - MUTATE_CREATIVE   → 变异创意 DNA
      - CREATE_VARIANTS   → 创建变异体

    连接系统:
      - E11 PopulationManager
      - E11 GenomeManager
      - CreativeAgent
    """

    SUPPORTED_ACTIONS = {
        GrowthActionType.CREATE_CREATIVE,
        GrowthActionType.MUTATE_CREATIVE,
        GrowthActionType.CREATE_VARIANTS,
    }

    def __init__(self):
        super().__init__(name="CreativeExecutor")
        self._generated_genomes: list[str] = []

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        start = time.perf_counter()

        if action.action_type not in self.SUPPORTED_ACTIONS:
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=f"Unsupported action type: {action.action_type.value}",
            )
            self._record_execution(outcome)
            return outcome

        try:
            output = self._handle_action(action)
            duration_ms = int((time.perf_counter() - start) * 1000)

            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.SUCCESS,
                executor=self.name,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=str(e),
                duration_ms=duration_ms,
            )

        self._record_execution(outcome)
        return outcome

    def _handle_action(self, action: GrowthAction) -> dict[str, Any]:
        """根据动作类型生成创意."""
        payload = action.payload
        variant_count = max(1, payload.get("variant_count", 3))
        base_id = action.target_id or "base_genome"

        if action.action_type == GrowthActionType.CREATE_CREATIVE:
            genome_ids = [f"genome_new_{uuid.uuid4().hex[:6]}"]

        elif action.action_type == GrowthActionType.MUTATE_CREATIVE:
            genome_ids = [f"{base_id}_mut_{uuid.uuid4().hex[:4]}"]

        elif action.action_type == GrowthActionType.CREATE_VARIANTS:
            genome_ids = [f"{base_id}_v{i+1}" for i in range(variant_count)]

        else:
            genome_ids = []

        self._generated_genomes.extend(genome_ids)

        return {
            "generated_genomes": genome_ids,
            "count": len(genome_ids),
            "source": base_id,
            "gene_category": payload.get("gene_category", ""),
            "exploration_direction": payload.get("exploration_direction", ""),
        }

    def validate(self, action: GrowthAction) -> bool:
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False
        return True

    @property
    def generated_genomes(self) -> list[str]:
        return list(self._generated_genomes)


# ═══════════════════════════════════════════════════════════
# 2. Meta Ads Executor
# ═══════════════════════════════════════════════════════════

class MetaAdsExecutor(BaseExecutor):
    """Meta Ads 执行器 — 负责广告系列管理.

    处理动作类型:
      - PROMOTE_WINNER  → 推广 Winner 创意 (增加预算)
      - SCALE_CAMPAIGN  → 放量广告系列
      - REDUCE_BUDGET   → 降低预算
      - PAUSE_CAMPAIGN  → 暂停广告系列

    连接系统:
      - E13.1 Meta Ads Connector
    """

    SUPPORTED_ACTIONS = {
        GrowthActionType.PROMOTE_WINNER,
        GrowthActionType.SCALE_CAMPAIGN,
        GrowthActionType.REDUCE_BUDGET,
        GrowthActionType.PAUSE_CAMPAIGN,
    }

    def __init__(self):
        super().__init__(name="MetaAdsExecutor")
        self._campaigns: dict[str, dict[str, Any]] = {}

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        start = time.perf_counter()

        if action.action_type not in self.SUPPORTED_ACTIONS:
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=f"Unsupported action type: {action.action_type.value}",
            )
            self._record_execution(outcome)
            return outcome

        try:
            output = self._handle_action(action)
            duration_ms = int((time.perf_counter() - start) * 1000)

            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.SUCCESS,
                executor=self.name,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=str(e),
                duration_ms=duration_ms,
            )

        self._record_execution(outcome)
        return outcome

    def _handle_action(self, action: GrowthAction) -> dict[str, Any]:
        """根据动作类型操作广告系列."""
        payload = action.payload
        campaign_id = action.target_id or f"camp_{uuid.uuid4().hex[:6]}"
        budget_mult = payload.get("budget_multiplier", 1.0)
        current_budget = self._campaigns.get(campaign_id, {}).get("budget", 100.0)

        if action.action_type == GrowthActionType.PROMOTE_WINNER:
            new_budget = round(current_budget * budget_mult, 2)
            self._campaigns[campaign_id] = {
                "status": "active",
                "budget": new_budget,
                "budget_multiplier": budget_mult,
                "reason": payload.get("scale_reason", ""),
            }
            return {
                "campaign_id": campaign_id,
                "action": "budget_increased",
                "previous_budget": current_budget,
                "new_budget": new_budget,
                "budget_multiplier": budget_mult,
            }

        elif action.action_type == GrowthActionType.SCALE_CAMPAIGN:
            new_budget = round(current_budget * budget_mult, 2)
            self._campaigns[campaign_id] = {
                "status": "active",
                "budget": new_budget,
                "scale_reason": payload.get("scale_reason", ""),
            }
            return {
                "campaign_id": campaign_id,
                "action": "scaled",
                "previous_budget": current_budget,
                "new_budget": new_budget,
            }

        elif action.action_type == GrowthActionType.REDUCE_BUDGET:
            new_budget = round(current_budget * budget_mult, 2)
            self._campaigns[campaign_id] = {
                "status": "active",
                "budget": new_budget,
                "reduced": True,
                "reason": payload.get("reduce_reason", ""),
            }
            return {
                "campaign_id": campaign_id,
                "action": "budget_reduced",
                "previous_budget": current_budget,
                "new_budget": new_budget,
            }

        elif action.action_type == GrowthActionType.PAUSE_CAMPAIGN:
            self._campaigns[campaign_id] = {
                "status": "paused",
                "budget": current_budget,
                "paused": True,
                "reason": payload.get("reason", ""),
                "auto_resume_days": payload.get("auto_resume_days", 7),
            }
            return {
                "campaign_id": campaign_id,
                "action": "paused",
                "previous_budget": current_budget,
                "auto_resume_days": payload.get("auto_resume_days", 7),
            }

        return {"campaign_id": campaign_id, "action": "unknown"}

    def validate(self, action: GrowthAction) -> bool:
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False
        # 需要目标 ID
        if not action.target_id:
            return False
        return True

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return self._campaigns.get(campaign_id)

    @property
    def campaigns(self) -> dict[str, dict[str, Any]]:
        return dict(self._campaigns)


# ═══════════════════════════════════════════════════════════
# 3. Experiment Executor
# ═══════════════════════════════════════════════════════════

class ExperimentExecutor(BaseExecutor):
    """实验执行器 — 负责实验管理.

    处理动作类型:
      - START_EXPERIMENT → 启动实验
      - END_EXPERIMENT   → 结束实验

    连接系统:
      - E14.6.2 ExperimentController
    """

    SUPPORTED_ACTIONS = {
        GrowthActionType.START_EXPERIMENT,
        GrowthActionType.END_EXPERIMENT,
    }

    def __init__(self):
        super().__init__(name="ExperimentExecutor")
        self._experiments: dict[str, dict[str, Any]] = {}

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        start = time.perf_counter()

        if action.action_type not in self.SUPPORTED_ACTIONS:
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=f"Unsupported action type: {action.action_type.value}",
            )
            self._record_execution(outcome)
            return outcome

        try:
            output = self._handle_action(action)
            duration_ms = int((time.perf_counter() - start) * 1000)

            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.SUCCESS,
                executor=self.name,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=str(e),
                duration_ms=duration_ms,
            )

        self._record_execution(outcome)
        return outcome

    def _handle_action(self, action: GrowthAction) -> dict[str, Any]:
        payload = action.payload
        experiment_id = action.target_id or f"exp_{uuid.uuid4().hex[:6]}"

        if action.action_type == GrowthActionType.START_EXPERIMENT:
            self._experiments[experiment_id] = {
                "status": "running",
                "name": payload.get("experiment_name", "Untitled"),
                "hypothesis": payload.get("hypothesis", ""),
                "duration_days": payload.get("duration_days", 7),
                "budget": payload.get("budget", 100.0),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            return {
                "experiment_id": experiment_id,
                "action": "started",
                "name": self._experiments[experiment_id]["name"],
                "duration_days": payload.get("duration_days", 7),
            }

        elif action.action_type == GrowthActionType.END_EXPERIMENT:
            if experiment_id in self._experiments:
                self._experiments[experiment_id]["status"] = "completed"
                self._experiments[experiment_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
            else:
                self._experiments[experiment_id] = {
                    "status": "completed",
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                }
            return {
                "experiment_id": experiment_id,
                "action": "ended",
            }

        return {"experiment_id": experiment_id, "action": "unknown"}

    def validate(self, action: GrowthAction) -> bool:
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False
        return True

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        return self._experiments.get(experiment_id)

    @property
    def experiments(self) -> dict[str, dict[str, Any]]:
        return dict(self._experiments)


# ═══════════════════════════════════════════════════════════
# 4. Evolution Executor
# ═══════════════════════════════════════════════════════════

class EvolutionExecutor(BaseExecutor):
    """进化执行器 — 负责种群管理.

    处理动作类型:
      - DIVERSIFY_POPULATION → 多样化种群

    连接系统:
      - E11 PopulationManager
    """

    SUPPORTED_ACTIONS = {
        GrowthActionType.DIVERSIFY_POPULATION,
    }

    def __init__(self):
        super().__init__(name="EvolutionExecutor")
        self._populations: dict[str, dict[str, Any]] = {}

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        start = time.perf_counter()

        if action.action_type not in self.SUPPORTED_ACTIONS:
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=f"Unsupported action type: {action.action_type.value}",
            )
            self._record_execution(outcome)
            return outcome

        try:
            output = self._handle_action(action)
            duration_ms = int((time.perf_counter() - start) * 1000)

            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.SUCCESS,
                executor=self.name,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                executor=self.name,
                error=str(e),
                duration_ms=duration_ms,
            )

        self._record_execution(outcome)
        return outcome

    def _handle_action(self, action: GrowthAction) -> dict[str, Any]:
        payload = action.payload
        pop_id = action.target_id or f"pop_{uuid.uuid4().hex[:6]}"
        count = max(1, payload.get("count", 5))
        diversity_target = payload.get("diversity_target", "general")

        genome_ids = [f"{pop_id}_g{i+1}" for i in range(count)]

        self._populations[pop_id] = {
            "genome_ids": genome_ids,
            "count": count,
            "diversity_target": diversity_target,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "population_id": pop_id,
            "action": "diversified",
            "generated_genomes": genome_ids,
            "count": count,
            "diversity_target": diversity_target,
        }

    def validate(self, action: GrowthAction) -> bool:
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False
        return True

    def get_population(self, pop_id: str) -> dict[str, Any] | None:
        return self._populations.get(pop_id)

    @property
    def populations(self) -> dict[str, dict[str, Any]]:
        return dict(self._populations)


# ═══════════════════════════════════════════════════════════
# NoOp Executor
# ═══════════════════════════════════════════════════════════

class NoOpExecutor(BaseExecutor):
    """空操作执行器 — 处理 HOLD 动作."""

    SUPPORTED_ACTIONS = {GrowthActionType.HOLD}

    def __init__(self):
        super().__init__(name="NoOpExecutor")

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        outcome = ExecutionOutcome(
            action_id=action.action_id,
            action_type=action.action_type.value,
            status=ExecutionStatus.SUCCESS,
            executor=self.name,
            output={"action": "hold", "reason": action.reasoning},
            duration_ms=0,
        )
        self._record_execution(outcome)
        return outcome

    def validate(self, action: GrowthAction) -> bool:
        return True


# ═══════════════════════════════════════════════════════════
# GrowthExecutionEngine — 核心执行引擎
# ═══════════════════════════════════════════════════════════

class GrowthExecutionEngine:
    """增长执行引擎 — 将 GrowthAction 转化为真实执行结果.

    核心职责:
      1. 管理执行器注册中心
      2. 执行单个/批量 GrowthAction
      3. 错误处理与部分失败
      4. 执行统计与监控

    MediaBuyingAgent 注入:
      当注入 MediaBuyingAgent 时，UA 类动作 (SCALE_CAMPAIGN, REDUCE_BUDGET,
      PAUSE_CAMPAIGN, PROMOTE_WINNER) 会通过它调用真实 Facebook API，
      包含审批分级、预算检查和回滚支持。

    用法:
        # 默认模式 (内部 mock executor)
        engine = GrowthExecutionEngine()
        engine.register_default_executors()

        # 注入真实执行能力
        from .media_buying_agent import create_media_buying_agent
        buying_agent = create_media_buying_agent()
        engine = GrowthExecutionEngine(media_buying_agent=buying_agent)

        outcome = engine.execute(action)
        print(f"Executed: {outcome.status.value}")

        outcomes = engine.execute_batch(actions)
        print(f"Batch: {len(outcomes)} outcomes")
    """

    # 默认并发上限
    DEFAULT_MAX_CONCURRENT = 10

    def __init__(self, max_concurrent: int = 10, media_buying_agent: Any = None):
        self._max_concurrent = max_concurrent
        self._registry: dict[GrowthActionType, BaseExecutor] = {}
        self._execution_history: list[ExecutionOutcome] = []
        self._media_buying_agent = media_buying_agent

    # ── 执行器注册 ────────────────────────────────────────

    def register_executor(self, action_type: GrowthActionType, executor: BaseExecutor) -> None:
        """注册执行器.

        Args:
            action_type: 动作类型
            executor: 执行器实例
        """
        self._registry[action_type] = executor

    def register_default_executors(self) -> None:
        """注册所有默认执行器 (同类型动作共享同一执行器实例)."""
        creative = CreativeExecutor()
        meta = MetaAdsExecutor()
        experiment = ExperimentExecutor()
        evolution = EvolutionExecutor()
        noop = NoOpExecutor()

        self.register_executor(GrowthActionType.CREATE_CREATIVE, creative)
        self.register_executor(GrowthActionType.MUTATE_CREATIVE, creative)
        self.register_executor(GrowthActionType.CREATE_VARIANTS, creative)
        self.register_executor(GrowthActionType.PROMOTE_WINNER, meta)
        self.register_executor(GrowthActionType.SCALE_CAMPAIGN, meta)
        self.register_executor(GrowthActionType.REDUCE_BUDGET, meta)
        self.register_executor(GrowthActionType.PAUSE_CAMPAIGN, meta)
        self.register_executor(GrowthActionType.START_EXPERIMENT, experiment)
        self.register_executor(GrowthActionType.END_EXPERIMENT, experiment)
        self.register_executor(GrowthActionType.DIVERSIFY_POPULATION, evolution)
        self.register_executor(GrowthActionType.HOLD, noop)

    def get_executor(self, action_type: GrowthActionType) -> BaseExecutor | None:
        """获取执行器."""
        return self._registry.get(action_type)

    def unregister_executor(self, action_type: GrowthActionType) -> None:
        """注销执行器."""
        self._registry.pop(action_type, None)

    # ── 核心: 执行 ────────────────────────────────────────

    def execute(self, action: GrowthAction) -> ExecutionOutcome:
        """执行单个 GrowthAction.

        如果注入 MediaBuyingAgent 且动作为 UA 类，优先通过它执行（真实 API），
        否则回退到内部 executor。

        Args:
            action: 待执行的 GrowthAction

        Returns:
            ExecutionOutcome: 执行结果
        """
        # ── 优先路由到 MediaBuyingAgent (真实 API) ────────
        if self._media_buying_agent is not None and action.action_type in (
            GrowthActionType.PAUSE_CAMPAIGN,
            GrowthActionType.SCALE_CAMPAIGN,
            GrowthActionType.REDUCE_BUDGET,
            GrowthActionType.PROMOTE_WINNER,
            GrowthActionType.CREATE_CREATIVE,
            GrowthActionType.START_EXPERIMENT,
        ):
            outcome = self._media_buying_agent.execute(action)
            self._execution_history.append(outcome)
            return outcome

        # ── 回退到内部 executor ───────────────────────────
        executor = self._registry.get(action.action_type)

        if executor is None:
            outcome = ExecutionOutcome(
                action_id=action.action_id,
                action_type=action.action_type.value,
                status=ExecutionStatus.FAILED,
                error=f"No executor registered for: {action.action_type.value}",
            )
            self._execution_history.append(outcome)
            return outcome

        outcome = executor.execute(action)
        self._execution_history.append(outcome)
        return outcome

    def execute_batch(self, actions: list[GrowthAction]) -> list[ExecutionOutcome]:
        """批量执行 GrowthAction.

        Args:
            actions: 待执行的 GrowthAction 列表

        Returns:
            list[ExecutionOutcome]: 执行结果列表
        """
        outcomes: list[ExecutionOutcome] = []

        # 限制并发数
        actions_to_execute = actions[:self._max_concurrent] if len(actions) > self._max_concurrent else actions

        for action in actions_to_execute:
            outcome = self.execute(action)
            outcomes.append(outcome)

        return outcomes

    # ── 查询 ──────────────────────────────────────────────

    def get_execution_history(self) -> list[ExecutionOutcome]:
        """获取执行历史."""
        return list(self._execution_history)

    def get_executions_by_status(self, status: ExecutionStatus) -> list[ExecutionOutcome]:
        """按状态获取执行结果."""
        return [e for e in self._execution_history if e.status == status]

    def get_executions_by_executor(self, executor_name: str) -> list[ExecutionOutcome]:
        """按执行器获取执行结果."""
        return [e for e in self._execution_history if e.executor == executor_name]

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取引擎统计."""
        total = len(self._execution_history)
        success = sum(1 for e in self._execution_history if e.is_success)
        failed = sum(1 for e in self._execution_history if e.is_failed)

        by_executor: dict[str, dict[str, int]] = {}
        for e in self._execution_history:
            if e.executor not in by_executor:
                by_executor[e.executor] = {"total": 0, "success": 0, "failed": 0}
            by_executor[e.executor]["total"] += 1
            if e.is_success:
                by_executor[e.executor]["success"] += 1
            elif e.is_failed:
                by_executor[e.executor]["failed"] += 1

        by_status: dict[str, int] = {}
        for e in self._execution_history:
            s = e.status.value
            by_status[s] = by_status.get(s, 0) + 1

        executor_stats = {}
        for at, ex in self._registry.items():
            if ex.name not in executor_stats:
                executor_stats[ex.name] = ex.stats()

        return {
            "total_executions": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / max(total, 1), 4),
            "by_status": by_status,
            "by_executor": by_executor,
            "executor_stats": executor_stats,
            "registered_executors": len(self._registry),
            "registry_actions": [at.value for at in self._registry],
        }

    def reset(self) -> None:
        """重置所有状态."""
        self._registry.clear()
        self._execution_history.clear()

    @property
    def registry(self) -> dict[GrowthActionType, BaseExecutor]:
        return dict(self._registry)

    @property
    def media_buying_agent(self) -> Any:
        return self._media_buying_agent


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_growth_execution_engine(
    max_concurrent: int = 10,
    register_defaults: bool = True,
    media_buying_agent: Any = None,
) -> GrowthExecutionEngine:
    """创建默认 GrowthExecutionEngine.

    Args:
        max_concurrent: 最大并发执行数
        register_defaults: 是否自动注册默认执行器
        media_buying_agent: 可选，注入 MediaBuyingAgent 实现真实 API 调用

    Returns:
        GrowthExecutionEngine: 配置好的执行引擎
    """
    engine = GrowthExecutionEngine(
        max_concurrent=max_concurrent,
        media_buying_agent=media_buying_agent,
    )
    if register_defaults:
        engine.register_default_executors()
    return engine