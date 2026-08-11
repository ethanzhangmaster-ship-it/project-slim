"""Visual Budget System - 视觉预算分配系统

核心思想：用户的注意力是有限的"预算"，必须按优先级分配给各个视觉元素。

预算控制维度：
  - size（尺寸）
  - brightness（亮度）
  - contrast（对比度）
  - centrality（中心度）
  - glow（发光强度）

分配规则：
  reward must get highest budget
  mechanism second
  identity / character third
  ui / cta fourth
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from .layout_ast import (
    LayoutAST,
    LayoutNode,
    VisualBudgetAllocation,
    BUDGET_CATEGORIES,
    VISUAL_BUDGET_TOTAL,
)


DEFAULT_BUDGET_PROFILES = {
    "reward_first": {
        "reward": 45,
        "mechanism": 30,
        "identity": 15,
        "ui": 10,
    },
    "mechanism_first": {
        "reward": 35,
        "mechanism": 40,
        "identity": 15,
        "ui": 10,
    },
    "balanced": {
        "reward": 35,
        "mechanism": 30,
        "identity": 20,
        "ui": 15,
    },
    "high_certainty": {
        "reward": 50,
        "mechanism": 25,
        "identity": 15,
        "ui": 10,
    },
}


BUDGET_TO_VISUAL_FACTORS = {
    "size": 0.35,
    "brightness": 0.25,
    "contrast": 0.20,
    "centrality": 0.15,
    "glow": 0.05,
}


@dataclass
class BudgetBreakdown:
    category: str
    total_budget: float
    size_contribution: float
    brightness_contribution: float
    contrast_contribution: float
    centrality_contribution: float
    glow_contribution: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "total_budget": self.total_budget,
            "size_contribution": self.size_contribution,
            "brightness_contribution": self.brightness_contribution,
            "contrast_contribution": self.contrast_contribution,
            "centrality_contribution": self.centrality_contribution,
            "glow_contribution": self.glow_contribution,
        }


class VisualBudgetSystem:
    @classmethod
    def allocate_budget(cls, template_id: str, mechanism_type: str,
                        attention_goal: str = "reward_first") -> VisualBudgetAllocation:
        profile = cls._select_profile(attention_goal, mechanism_type)
        allocation = {}
        
        for category, amount in profile.items():
            allocation[category] = float(amount)
        
        total = sum(allocation.values())
        if total != VISUAL_BUDGET_TOTAL:
            scale = VISUAL_BUDGET_TOTAL / total if total > 0 else 1.0
            for k in allocation:
                allocation[k] = round(allocation[k] * scale, 1)
        
        return VisualBudgetAllocation(
            total_budget=VISUAL_BUDGET_TOTAL,
            allocation=allocation,
        )
    
    @classmethod
    def _select_profile(cls, attention_goal: str, mechanism_type: str) -> Dict[str, float]:
        if attention_goal == "mechanism_first":
            return DEFAULT_BUDGET_PROFILES["mechanism_first"]
        
        if mechanism_type in ["collection", "progression_chain"]:
            return DEFAULT_BUDGET_PROFILES["high_certainty"]
        
        if mechanism_type in ["transformation", "merge"]:
            return DEFAULT_BUDGET_PROFILES["reward_first"]
        
        return DEFAULT_BUDGET_PROFILES["reward_first"]
    
    @classmethod
    def apply_budget_to_node(cls, node: LayoutNode, budget_category: str,
                              budget_amount: float) -> LayoutNode:
        normalized_budget = budget_amount / 100.0
        
        node.size_ratio = cls._budget_to_size(normalized_budget, budget_category)
        node.brightness_bias = cls._budget_to_brightness(normalized_budget, budget_category)
        node.contrast_bias = cls._budget_to_contrast(normalized_budget, budget_category)
        node.glow_intensity = cls._budget_to_glow(normalized_budget, budget_category)
        node.visual_budget = budget_amount
        
        return node
    
    @classmethod
    def _budget_to_size(cls, budget_norm: float, category: str) -> float:
        base_sizes = {
            "reward": 0.35,
            "mechanism": 0.25,
            "identity": 0.18,
            "ui": 0.10,
            "background": 0.12,
        }
        base = base_sizes.get(category, 0.2)
        return round(base + budget_norm * 0.25, 3)
    
    @classmethod
    def _budget_to_brightness(cls, budget_norm: float, category: str) -> float:
        base_bias = {
            "reward": 0.2,
            "mechanism": 0.1,
            "identity": 0.0,
            "ui": 0.05,
            "background": -0.1,
        }
        base = base_bias.get(category, 0.0)
        return round(base + budget_norm * 0.3, 2)
    
    @classmethod
    def _budget_to_contrast(cls, budget_norm: float, category: str) -> float:
        base_bias = {
            "reward": 0.15,
            "mechanism": 0.1,
            "identity": 0.0,
            "ui": 0.05,
            "background": -0.05,
        }
        base = base_bias.get(category, 0.0)
        return round(base + budget_norm * 0.25, 2)
    
    @classmethod
    def _budget_to_glow(cls, budget_norm: float, category: str) -> float:
        base_glow = {
            "reward": 0.3,
            "mechanism": 0.1,
            "identity": 0.0,
            "ui": 0.15,
            "background": 0.0,
        }
        base = base_glow.get(category, 0.0)
        return round(base + budget_norm * 0.5, 2)
    
    @classmethod
    def breakdown_budget(cls, budget_amount: float, category: str) -> BudgetBreakdown:
        normalized = budget_amount / 100.0
        
        return BudgetBreakdown(
            category=category,
            total_budget=budget_amount,
            size_contribution=round(normalized * BUDGET_TO_VISUAL_FACTORS["size"] * 100, 1),
            brightness_contribution=round(normalized * BUDGET_TO_VISUAL_FACTORS["brightness"] * 100, 1),
            contrast_contribution=round(normalized * BUDGET_TO_VISUAL_FACTORS["contrast"] * 100, 1),
            centrality_contribution=round(normalized * BUDGET_TO_VISUAL_FACTORS["centrality"] * 100, 1),
            glow_contribution=round(normalized * BUDGET_TO_VISUAL_FACTORS["glow"] * 100, 1),
        )
    
    @classmethod
    def validate_budget_distribution(cls, allocation: Dict[str, float]) -> Tuple[bool, List[str]]:
        issues = []
        
        total = sum(allocation.values())
        if abs(total - VISUAL_BUDGET_TOTAL) > 1.0:
            issues.append(f"Budget total {total:.1f} != {VISUAL_BUDGET_TOTAL}")
        
        if "reward" not in allocation:
            issues.append("No reward budget allocated")
        else:
            for category, amount in allocation.items():
                if category != "reward" and amount > allocation["reward"]:
                    issues.append(
                        f"{category} budget ({amount}) > reward budget ({allocation['reward']})"
                    )
        
        if "reward" in allocation and allocation["reward"] < 30:
            issues.append(f"Reward budget too low: {allocation['reward']} (min 30)")
        
        return len(issues) == 0, issues
    
    @classmethod
    def reallocate_budget(cls, allocation: Dict[str, float],
                          adjustments: Dict[str, float]) -> Dict[str, float]:
        new_allocation = dict(allocation)
        
        for category, delta in adjustments.items():
            new_allocation[category] = max(0, new_allocation.get(category, 0) + delta)
        
        total = sum(new_allocation.values())
        if total != VISUAL_BUDGET_TOTAL and total > 0:
            scale = VISUAL_BUDGET_TOTAL / total
            for k in new_allocation:
                new_allocation[k] = round(new_allocation[k] * scale, 1)
        
        return new_allocation
