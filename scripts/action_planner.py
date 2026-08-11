"""Growth Strategy Layer — ActionPlanner.

动作规划器：将增长策略转化为具体的执行动作，连接 V1 执行层。

数据流:
  GrowthStrategy (策略类型 + 强度)
    + creative_to_adset_map (creative_id → adset_id 映射)
    + current_budgets (adset_id → 当前日预算)
      ↓
  ExecutionAction (统一执行动作格式)

不是 Agent，是 Engine。与 DiagnosticEngine / HypothesisGenerator / StrategySelector 同级。
不新建执行器，输出直接可被 V1 ExecutionBridge 消费。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from scripts.diagnostic_engine import StrategyType
from scripts.strategy_selector import GrowthStrategy

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

# 预算安全边界
_MIN_DAILY_BUDGET = 20.0       # 单 AdSet 最低日预算
_MAX_BUDGET_INCREASE_PCT = 30  # 单次最多升 30%
_MAX_BUDGET_REDUCE_PCT = 50    # 单次最多降 50%

# 风险阈值
_BUDGET_IMPACT_WARN = 50.0     # $50 警告
_BUDGET_IMPACT_APPROVAL = 200.0  # $200 需审批
_BUDGET_IMPACT_BLOCK = 500.0   # $500 阻断


# ──────────────────────────────────────────────
# ActionType 枚举
# ──────────────────────────────────────────────


class ActionType(str, Enum):
    """执行动作类型 — V2 首期支持 3 种。"""

    UPDATE_BUDGET = "update_budget"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    NOOP = "noop"

    # 后续扩展（首期不实现）
    # CREATE_TEST_CAMPAIGN = "create_test_campaign"
    # REPLACE_CREATIVE = "replace_creative"


class ActionStatus(str, Enum):
    """动作生命周期状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


# ──────────────────────────────────────────────
# ExecutionAction 数据模型
# ──────────────────────────────────────────────


@dataclass
class ExecutionAction:
    """统一执行动作 — 连接决策层与执行层的唯一契约。

    V1 设计中定义的格式，由 ActionPlanner 生成。
    """

    # ── 标识 ──
    action_id: str = ""
    strategy_id: str = ""
    hypothesis_id: str = ""
    diagnosis_id: str = ""
    signal_id: str = ""
    source_signal_id: str = ""  # 兼容 V1 字段名

    # ── 目标 ──
    creative_id: str = ""
    adset_id: str = ""

    # ── 动作 ──
    action_type: ActionType = ActionType.NOOP
    parameters: dict[str, Any] = field(default_factory=dict)

    # ── 决策元数据 ──
    confidence: float = 0.0
    risk_level: str = "low"  # low / medium / high / critical
    expected_impact: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    # ── 安全元数据 ──
    budget_impact: float = 0.0  # 正=增, 负=减, 0=无
    requires_approval: bool = False
    approval_level: int = 0  # 0=自动, 1=确认, 2=审批

    # ── 生命周期 ──
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = ""
    executed_at: str | None = None
    error: str = ""
    rollback_action_id: str = ""

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = f"exec_{uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.source_signal_id and self.signal_id:
            self.source_signal_id = self.signal_id

    @property
    def is_noop(self) -> bool:
        """是否为无操作。"""
        return self.action_type == ActionType.NOOP

    @property
    def needs_execution(self) -> bool:
        """是否需要真实执行。"""
        return self.action_type != ActionType.NOOP and self.status != ActionStatus.SKIPPED

    def to_dict(self) -> dict[str, Any]:
        """可序列化输出。"""
        return {
            "action_id": self.action_id,
            "strategy_id": self.strategy_id,
            "hypothesis_id": self.hypothesis_id,
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal_id,
            "source_signal_id": self.source_signal_id,
            "creative_id": self.creative_id,
            "adset_id": self.adset_id,
            "action_type": self.action_type.value,
            "parameters": dict(self.parameters),
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level,
            "expected_impact": dict(self.expected_impact),
            "reason": self.reason,
            "budget_impact": round(self.budget_impact, 2),
            "requires_approval": self.requires_approval,
            "approval_level": self.approval_level,
            "status": self.status.value,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "error": self.error,
            "rollback_action_id": self.rollback_action_id,
            "is_noop": self.is_noop,
            "needs_execution": self.needs_execution,
        }


# ──────────────────────────────────────────────
# ActionPlanner
# ──────────────────────────────────────────────


class ActionPlanner:
    """动作规划器 — 将策略转化为执行动作。

    使用方式:
        planner = ActionPlanner()
        actions = planner.plan(
            strategy,
            creative_to_adset_map={"c_001": "adset_123"},
            current_budgets={"adset_123": 200.0},
        )
    """

    def plan(
        self,
        strategy: GrowthStrategy,
        creative_to_adset_map: dict[str, str] | None = None,
        current_budgets: dict[str, float] | None = None,
    ) -> list[ExecutionAction]:
        """将单个策略转化为执行动作列表。

        Args:
            strategy: StrategySelector 的输出
            creative_to_adset_map: creative_id → adset_id 映射
            current_budgets: adset_id → 当前日预算

        Returns:
            list[ExecutionAction]，通常为 1 个动作（MAINTAIN → NOOP）
        """
        creative_to_adset_map = creative_to_adset_map or {}
        current_budgets = current_budgets or {}

        # MAINTAIN → NOOP
        if not strategy.requires_execution:
            return [self._make_noop(strategy)]

        # 查找 adset_id
        creative_id = strategy.target_creative_id
        adset_id = creative_to_adset_map.get(creative_id, "")

        # 缺失 adset_id → SKIPPED
        if not adset_id:
            return [
                self._make_skipped(
                    strategy, creative_id, "creative_id 无对应 adset_id"
                )
            ]

        # 按策略类型生成动作
        if strategy.strategy_type == StrategyType.SUPPRESS:
            return [
                self._make_budget_action(
                    strategy, adset_id, current_budgets, reduce=True
                )
            ]

        if strategy.strategy_type == StrategyType.SCALE:
            return [
                self._make_budget_action(
                    strategy, adset_id, current_budgets, reduce=False
                )
            ]

        if strategy.strategy_type == StrategyType.REFRESH:
            return [self._make_pause_action(strategy, adset_id)]

        if strategy.strategy_type == StrategyType.PAUSE:
            return [self._make_pause_action(strategy, adset_id)]

        # 未知策略类型 → NOOP
        logger.warning(
            "ActionPlanner: unknown strategy_type %s, fallback to NOOP",
            strategy.strategy_type,
        )
        return [self._make_noop(strategy)]

    def plan_batch(
        self,
        strategies: list[GrowthStrategy],
        creative_to_adset_map: dict[str, str] | None = None,
        current_budgets: dict[str, float] | None = None,
    ) -> list[ExecutionAction]:
        """批量生成执行动作。"""
        actions: list[ExecutionAction] = []
        for s in strategies:
            actions.extend(self.plan(s, creative_to_adset_map, current_budgets))
        return actions

    # ── 内部方法 ──

    def _make_budget_action(
        self,
        strategy: GrowthStrategy,
        adset_id: str,
        current_budgets: dict[str, float],
        reduce: bool,
    ) -> ExecutionAction:
        """生成预算调整动作。"""
        current_budget = current_budgets.get(adset_id, 0.0)

        # 计算目标预算
        ratio = strategy.budget_change_ratio
        target_budget = round(current_budget * ratio, 2)

        # 安全边界
        if reduce:
            # 最多降 50%
            min_budget = current_budget * (1 - _MAX_BUDGET_REDUCE_PCT / 100)
            target_budget = max(target_budget, min_budget)
        else:
            # 最多升 30%
            max_budget = current_budget * (1 + _MAX_BUDGET_INCREASE_PCT / 100)
            target_budget = min(target_budget, max_budget)

        # 最低预算底线
        target_budget = max(target_budget, _MIN_DAILY_BUDGET)

        # 预算变化金额
        budget_impact = round(target_budget - current_budget, 2)

        # 风险等级
        risk_level = self._compute_risk_level(budget_impact)

        # 审批需求
        requires_approval, approval_level = self._compute_approval(
            budget_impact, risk_level
        )

        # 变化百分比
        if current_budget > 0:
            change_pct = round(
                (target_budget - current_budget) / current_budget * 100, 1
            )
        else:
            change_pct = 0.0

        return ExecutionAction(
            strategy_id=strategy.strategy_id,
            hypothesis_id=strategy.hypothesis_id,
            diagnosis_id=strategy.diagnosis_id,
            signal_id=strategy.signal_id,
            creative_id=strategy.target_creative_id,
            adset_id=adset_id,
            action_type=ActionType.UPDATE_BUDGET,
            parameters={
                "adset_id": adset_id,
                "current_budget": current_budget,
                "target_budget": target_budget,
                "change_ratio": round(ratio, 4),
                "change_pct": change_pct,
            },
            confidence=strategy.confidence,
            risk_level=risk_level,
            expected_impact=strategy.expected_impact,
            reason=self._build_reason(strategy, "budget_change"),
            budget_impact=budget_impact,
            requires_approval=requires_approval,
            approval_level=approval_level,
        )

    def _make_pause_action(
        self,
        strategy: GrowthStrategy,
        adset_id: str,
    ) -> ExecutionAction:
        """生成暂停动作。"""
        return ExecutionAction(
            strategy_id=strategy.strategy_id,
            hypothesis_id=strategy.hypothesis_id,
            diagnosis_id=strategy.diagnosis_id,
            signal_id=strategy.signal_id,
            creative_id=strategy.target_creative_id,
            adset_id=adset_id,
            action_type=ActionType.PAUSE_CAMPAIGN,
            parameters={
                "adset_id": adset_id,
                "current_status": "ACTIVE",
                "target_status": "PAUSED",
            },
            confidence=strategy.confidence,
            risk_level="medium",
            expected_impact=strategy.expected_impact,
            reason=self._build_reason(strategy, "pause"),
            budget_impact=0.0,
            requires_approval=False,
            approval_level=0,
        )

    def _make_noop(self, strategy: GrowthStrategy) -> ExecutionAction:
        """生成无操作。"""
        return ExecutionAction(
            strategy_id=strategy.strategy_id,
            hypothesis_id=strategy.hypothesis_id,
            diagnosis_id=strategy.diagnosis_id,
            signal_id=strategy.signal_id,
            creative_id=strategy.target_creative_id,
            action_type=ActionType.NOOP,
            parameters={},
            confidence=strategy.confidence,
            risk_level="low",
            expected_impact=strategy.expected_impact,
            reason=f"策略 {strategy.strategy_type.value} 无需执行",
            budget_impact=0.0,
            requires_approval=False,
            approval_level=0,
            status=ActionStatus.SKIPPED,
        )

    def _make_skipped(
        self,
        strategy: GrowthStrategy,
        creative_id: str,
        reason: str,
    ) -> ExecutionAction:
        """生成跳过动作（缺失 adset_id 等）。"""
        return ExecutionAction(
            strategy_id=strategy.strategy_id,
            hypothesis_id=strategy.hypothesis_id,
            diagnosis_id=strategy.diagnosis_id,
            signal_id=strategy.signal_id,
            creative_id=creative_id,
            action_type=ActionType.NOOP,
            parameters={},
            confidence=strategy.confidence,
            risk_level="low",
            expected_impact=strategy.expected_impact,
            reason=reason,
            budget_impact=0.0,
            requires_approval=False,
            approval_level=0,
            status=ActionStatus.SKIPPED,
        )

    def _compute_risk_level(self, budget_impact: float) -> str:
        """根据预算变化金额计算风险等级。"""
        abs_impact = abs(budget_impact)
        if abs_impact >= _BUDGET_IMPACT_BLOCK:
            return "critical"
        if abs_impact >= _BUDGET_IMPACT_APPROVAL:
            return "high"
        if abs_impact >= _BUDGET_IMPACT_WARN:
            return "medium"
        return "low"

    def _compute_approval(
        self,
        budget_impact: float,
        risk_level: str,
        # V2 新增参数（Spec §4.1）：绝对金额维度，可选
        budget_impact_usd: float | None = None,
    ) -> tuple[bool, int]:
        """根据风险等级 + 金额计算审批需求。

        V2 升级（见 docs/p0_approval_gate_v2_spec.md §4.1）：
        - 优先使用 budget_impact_usd（绝对金额）做 Level 分级
        - budget_impact_usd 缺失（None）时回退 V1 逻辑（基于归一化 budget_impact）
        - 与 policy.py 的 Level 0/1/2 分级对齐

        Returns:
            (requires_approval, approval_level)
            - (False, 0) — 自动执行（Level 0）
            - (True, 1)  — 需确认（Level 1，dry_run 验证后可升 AUTO）
            - (True, 2)  — 需审批（Level 2，强制人工）
        """
        # V1 兼容路径：无 budget_impact_usd 时走原逻辑
        if budget_impact_usd is None:
            abs_impact = abs(budget_impact)
            if abs_impact >= _BUDGET_IMPACT_BLOCK:
                return (True, 2)  # 需审批
            if abs_impact >= _BUDGET_IMPACT_APPROVAL:
                return (True, 1)  # 需确认
            return (False, 0)  # 自动

        # V2 路径：基于绝对金额（USD）分级
        # 阈值复用 V1 常量（$50 / $200 / $500），与 policy.py 默认配置一致
        abs_amount = abs(budget_impact_usd)
        if abs_amount >= _BUDGET_IMPACT_BLOCK:  # >= $500 → Level 2
            return (True, 2)
        if abs_amount >= _BUDGET_IMPACT_WARN:   # >= $50 → Level 1
            return (True, 1)
        # < $50 → Level 0（仍受 policy.evaluate() 的 risk/conf/allowlist 约束）
        # risk_level 为 high/critical 时升级到 Level 1
        if risk_level in ("high", "critical"):
            return (True, 1)
        return (False, 0)

    def _build_reason(
        self, strategy: GrowthStrategy, action_category: str
    ) -> str:
        """构建人类可读的执行理由。"""
        if action_category == "budget_change":
            direction = (
                "降低" if strategy.intensity < 1.0 else "提升"
            )
            pct = round(abs(strategy.intensity - 1.0) * 100)
            return (
                f"{strategy.strategy_type.value}: {direction}预算 {pct}%"
                f" (根因: {strategy.root_cause}, 置信度: {strategy.confidence:.2f})"
            )
        if action_category == "pause":
            return (
                f"{strategy.strategy_type.value}: 暂停 AdSet"
                f" (根因: {strategy.root_cause}, 置信度: {strategy.confidence:.2f})"
            )
        return strategy.strategy_type.value
