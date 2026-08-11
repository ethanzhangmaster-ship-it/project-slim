"""E11 Phase 2.5 — Budget Manager。

预算管理模块，负责：
  1. 计算放量预算（基于 multiplier 和 max_budget）
  2. 计算缩减预算（基于 reduce_ratio）
  3. 生成预算操作建议（BudgetAction）

预算策略：
  - Winner 不放原 Campaign 预算（避免打乱 Facebook Learning Phase）
  - 新建 ROAS Campaign，复制素材
  - 新 Campaign 预算 = 原预算 × multiplier
  - 原 Campaign 保持运行（作为对照组）
  - 阶梯式缩放：每次最多 2x，间隔至少 3 天
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BudgetActionType(str, Enum):
    """预算操作类型。"""
    SCALE_UP = "SCALE_UP"           # 扩大预算
    SCALE_DOWN = "SCALE_DOWN"       # 缩减预算
    NEW_CAMPAIGN = "NEW_CAMPAIGN"   # 新建 Campaign
    PAUSE = "PAUSE"                 # 暂停
    RESUME = "RESUME"               # 恢复
    NO_CHANGE = "NO_CHANGE"         # 不变


@dataclass
class BudgetAction:
    """预算操作建议。"""

    action_type: BudgetActionType = BudgetActionType.NO_CHANGE
    creative_asset_id: str = ""
    current_budget: float = 0.0
    new_budget: float = 0.0
    reason: str = ""
    requires_new_campaign: bool = False
    cooldown_days: int = 0          # 操作后冷却天数
    risk_level: str = "low"         # low / medium / high

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "creative_asset_id": self.creative_asset_id,
            "current_budget": self.current_budget,
            "new_budget": self.new_budget,
            "reason": self.reason,
            "requires_new_campaign": self.requires_new_campaign,
            "cooldown_days": self.cooldown_days,
            "risk_level": self.risk_level,
        }

    @property
    def is_noop(self) -> bool:
        return self.action_type == BudgetActionType.NO_CHANGE

    @property
    def budget_change_pct(self) -> float:
        if self.current_budget <= 0:
            return 0.0
        return round((self.new_budget - self.current_budget) / self.current_budget, 4)


class BudgetManager:
    """预算管理器。

    负责计算预算调整方案，遵循以下原则：
      - 阶梯式缩放：每次最多 2x，间隔至少 3 天
      - 新建 Campaign 放量，不动原 Campaign
      - 预算上限保护

    Usage:
        mgr = BudgetManager()
        action = mgr.calculate_scale_up("MW_IMG_001", current=50, multiplier=2.0)
        # → BudgetAction(SCALE_UP, new_budget=100, requires_new_campaign=True)
    """

    # 默认配置
    DEFAULT_MAX_BUDGET = 1000.0          # 单素材最大日预算
    DEFAULT_MIN_BUDGET = 10.0            # 单素材最小日预算
    DEFAULT_STEP_MAX_MULTIPLIER = 2.0    # 单次最大缩放倍数
    DEFAULT_COOLDOWN_DAYS = 3            # 缩放后冷却天数

    def __init__(
        self,
        max_budget: float = DEFAULT_MAX_BUDGET,
        min_budget: float = DEFAULT_MIN_BUDGET,
        step_max_multiplier: float = DEFAULT_STEP_MAX_MULTIPLIER,
        cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    ) -> None:
        self.max_budget = max_budget
        self.min_budget = min_budget
        self.step_max_multiplier = step_max_multiplier
        self.cooldown_days = cooldown_days

    # ── Primary API ─────────────────────────────────────

    def calculate_scale_up(
        self,
        creative_asset_id: str,
        current_budget: float,
        multiplier: float,
        max_budget: float | None = None,
    ) -> BudgetAction:
        """计算放量预算。

        Args:
            creative_asset_id: 素材 ID
            current_budget:    当前日预算
            multiplier:        目标倍数
            max_budget:        预算上限（不传则用默认值）

        Returns:
            BudgetAction
        """
        cap = max_budget if max_budget is not None else self.max_budget

        # 阶梯限制：单次最多 2x
        effective_multiplier = min(multiplier, self.step_max_multiplier)
        raw_new = current_budget * effective_multiplier

        # 上限保护
        new_budget = min(raw_new, cap)
        new_budget = round(new_budget, 2)

        if new_budget <= current_budget:
            return BudgetAction(
                action_type=BudgetActionType.NO_CHANGE,
                creative_asset_id=creative_asset_id,
                current_budget=current_budget,
                new_budget=current_budget,
                reason=f"Already at max budget (${cap:.0f}/day)",
                cooldown_days=0,
            )

        return BudgetAction(
            action_type=BudgetActionType.SCALE_UP,
            creative_asset_id=creative_asset_id,
            current_budget=current_budget,
            new_budget=new_budget,
            reason=f"Scale up from ${current_budget:.0f} to ${new_budget:.0f}/day (multiplier={effective_multiplier}x)",
            requires_new_campaign=True,
            cooldown_days=self.cooldown_days,
            risk_level="medium" if new_budget >= 200 else "low",
        )

    def calculate_scale_down(
        self,
        creative_asset_id: str,
        current_budget: float,
        reduce_ratio: float = 0.5,
    ) -> BudgetAction:
        """计算缩减预算。

        Args:
            creative_asset_id: 素材 ID
            current_budget:    当前日预算
            reduce_ratio:      缩减比例（0.0 - 1.0）

        Returns:
            BudgetAction
        """
        new_budget = round(current_budget * reduce_ratio, 2)

        # 低于最小预算 → 建议暂停
        if new_budget < self.min_budget:
            return BudgetAction(
                action_type=BudgetActionType.PAUSE,
                creative_asset_id=creative_asset_id,
                current_budget=current_budget,
                new_budget=0.0,
                reason=f"Reduced budget (${new_budget:.2f}) below minimum (${self.min_budget:.0f}), recommend pause",
                cooldown_days=0,
                risk_level="low",
            )

        return BudgetAction(
            action_type=BudgetActionType.SCALE_DOWN,
            creative_asset_id=creative_asset_id,
            current_budget=current_budget,
            new_budget=new_budget,
            reason=f"Scale down from ${current_budget:.0f} to ${new_budget:.0f}/day (reduce={reduce_ratio:.0%})",
            cooldown_days=self.cooldown_days,
            risk_level="low",
        )

    def calculate_pause(
        self,
        creative_asset_id: str,
        current_budget: float,
        reason: str = "",
    ) -> BudgetAction:
        """计算暂停操作。"""
        return BudgetAction(
            action_type=BudgetActionType.PAUSE,
            creative_asset_id=creative_asset_id,
            current_budget=current_budget,
            new_budget=0.0,
            reason=reason or f"Pause {creative_asset_id} (budget: ${current_budget:.0f}/day)",
            cooldown_days=0,
            risk_level="low",
        )

    def calculate_new_campaign_budget(
        self,
        creative_asset_id: str,
        test_budget: float,
        multiplier: float,
        max_budget: float | None = None,
    ) -> BudgetAction:
        """计算新建 Campaign 的预算。

        与 calculate_scale_up 的区别：
          - 明确标记 requires_new_campaign=True
          - 新 Campaign 用于 ROAS 放量

        Args:
            creative_asset_id: 素材 ID
            test_budget:       测试阶段预算
            multiplier:        放量倍数
            max_budget:        预算上限

        Returns:
            BudgetAction
        """
        cap = max_budget if max_budget is not None else self.max_budget
        new_budget = round(min(test_budget * multiplier, cap), 2)

        return BudgetAction(
            action_type=BudgetActionType.NEW_CAMPAIGN,
            creative_asset_id=creative_asset_id,
            current_budget=test_budget,
            new_budget=new_budget,
            reason=f"Create new ROAS campaign at ${new_budget:.0f}/day (original test budget: ${test_budget:.0f}/day)",
            requires_new_campaign=True,
            cooldown_days=self.cooldown_days,
            risk_level="medium" if new_budget >= 500 else "low",
        )

    # ── Batch ───────────────────────────────────────────

    def calculate_batch(
        self,
        actions: list[dict[str, Any]],
    ) -> list[BudgetAction]:
        """批量计算预算操作。

        Args:
            actions: 每个元素包含 creative_asset_id, current_budget, multiplier/reduce_ratio, action_type

        Returns:
            BudgetAction 列表
        """
        results: list[BudgetAction] = []
        for a in actions:
            action_type = a.get("action_type", "scale_up")
            creative_id = a.get("creative_asset_id", "")

            if action_type == "scale_up":
                result = self.calculate_scale_up(
                    creative_id,
                    a.get("current_budget", 0.0),
                    a.get("multiplier", 1.0),
                    a.get("max_budget"),
                )
            elif action_type == "scale_down":
                result = self.calculate_scale_down(
                    creative_id,
                    a.get("current_budget", 0.0),
                    a.get("reduce_ratio", 0.5),
                )
            elif action_type == "pause":
                result = self.calculate_pause(
                    creative_id,
                    a.get("current_budget", 0.0),
                    a.get("reason", ""),
                )
            elif action_type == "new_campaign":
                result = self.calculate_new_campaign_budget(
                    creative_id,
                    a.get("test_budget", 50.0),
                    a.get("multiplier", 2.0),
                    a.get("max_budget"),
                )
            else:
                result = BudgetAction(
                    creative_asset_id=creative_id,
                    reason=f"Unknown action type: {action_type}",
                )

            results.append(result)

        return results

    # ── Summary ─────────────────────────────────────────

    def summarize(self, actions: list[BudgetAction]) -> dict[str, Any]:
        """汇总预算操作。"""
        total_new_budget = sum(a.new_budget for a in actions)
        total_current_budget = sum(a.current_budget for a in actions)
        scale_ups = [a for a in actions if a.action_type == BudgetActionType.SCALE_UP]
        scale_downs = [a for a in actions if a.action_type == BudgetActionType.SCALE_DOWN]
        pauses = [a for a in actions if a.action_type == BudgetActionType.PAUSE]
        new_campaigns = [a for a in actions if a.action_type == BudgetActionType.NEW_CAMPAIGN]

        return {
            "total_actions": len(actions),
            "total_current_budget": total_current_budget,
            "total_new_budget": total_new_budget,
            "budget_delta": round(total_new_budget - total_current_budget, 2),
            "scale_ups": len(scale_ups),
            "scale_downs": len(scale_downs),
            "pauses": len(pauses),
            "new_campaigns": len(new_campaigns),
            "total_new_campaign_budget": sum(a.new_budget for a in new_campaigns),
        }

    def __repr__(self) -> str:
        return (
            f"BudgetManager(max_budget={self.max_budget}, "
            f"min_budget={self.min_budget}, "
            f"step_limit={self.step_max_multiplier}x, "
            f"cooldown={self.cooldown_days}d)"
        )