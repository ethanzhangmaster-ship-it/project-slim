"""Layout AST - 布局抽象语法树

核心思想：每个 Creative 必须先编译成结构化的 Layout AST，再进行约束式渲染。

这不是描述性 metadata，而是可执行的编译规则。

Layout AST 结构：
{
  "ast_id": "xxx",
  "template_id": "merge_formula",
  "nodes": {
    "reward": {
      "role": "L1",
      "position": "center",
      "size_ratio": 0.45,
      "brightness_bias": 0.4,
      "contrast_bias": 0.3,
      "glow_intensity": 0.8,
      "visual_budget": 45
    },
    "mechanism": {
      "role": "L2",
      ...
    }
  },
  "spatial_constraints": [...],
  "visual_budget_allocation": {...},
  "hard_constraints": {...}
}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


NODE_ROLES = ["L1", "L2", "L3", "L4"]

POSITION_TYPES = [
    "center", "top_center", "bottom_center",
    "left", "right", "left_side", "right_side",
    "supporting", "peripheral", "background",
    "linear_left_to_right", "linear_bottom_to_top",
    "split_left", "split_right",
]

VISUAL_BUDGET_TOTAL = 100

BUDGET_CATEGORIES = ["reward", "mechanism", "identity", "ui", "background"]


@dataclass
class LayoutNode:
    node_id: str
    role: str
    position: str
    size_ratio: float
    brightness_bias: float = 0.0
    contrast_bias: float = 0.0
    glow_intensity: float = 0.0
    visual_budget: float = 0.0
    z_index: int = 0
    opacity: float = 1.0
    color_temperature: str = "neutral"
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "position": self.position,
            "size_ratio": self.size_ratio,
            "brightness_bias": self.brightness_bias,
            "contrast_bias": self.contrast_bias,
            "glow_intensity": self.glow_intensity,
            "visual_budget": self.visual_budget,
            "z_index": self.z_index,
            "opacity": self.opacity,
            "color_temperature": self.color_temperature,
            "description": self.description,
        }


@dataclass
class SpatialConstraint:
    constraint_id: str
    type: str
    subject: str
    reference: str = ""
    operator: str = ""
    value: float = 0.0
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "type": self.type,
            "subject": self.subject,
            "reference": self.reference,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }


@dataclass
class VisualBudgetAllocation:
    total_budget: float = VISUAL_BUDGET_TOTAL
    allocation: Dict[str, float] = field(default_factory=dict)
    
    def validate(self) -> tuple[bool, List[str]]:
        issues = []
        total = sum(self.allocation.values())
        
        if abs(total - self.total_budget) > 1.0:
            issues.append(
                f"Budget sum {total:.1f} != total {self.total_budget}"
            )
        
        if "reward" in self.allocation:
            for cat in BUDGET_CATEGORIES:
                if cat != "reward" and cat in self.allocation:
                    if self.allocation[cat] > self.allocation["reward"]:
                        issues.append(
                            f"{cat} budget ({self.allocation[cat]}) "
                            f"> reward budget ({self.allocation['reward']})"
                        )
        
        return len(issues) == 0, issues
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "allocation": self.allocation,
        }


@dataclass
class HardConstraints:
    l1_must_be_reward: bool = True
    no_character_as_l1: bool = True
    reward_must_be_central: bool = True
    mechanism_must_be_traceable: bool = True
    template_required: bool = True
    minimum_reward_budget: float = 35.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "l1_must_be_reward": self.l1_must_be_reward,
            "no_character_as_l1": self.no_character_as_l1,
            "reward_must_be_central": self.reward_must_be_central,
            "mechanism_must_be_traceable": self.mechanism_must_be_traceable,
            "template_required": self.template_required,
            "minimum_reward_budget": self.minimum_reward_budget,
        }


@dataclass
class LayoutAST:
    ast_id: str = ""
    template_id: str = ""
    mechanism_type: str = ""
    
    nodes: Dict[str, LayoutNode] = field(default_factory=dict)
    spatial_constraints: List[SpatialConstraint] = field(default_factory=list)
    visual_budget: VisualBudgetAllocation = field(default_factory=VisualBudgetAllocation)
    hard_constraints: HardConstraints = field(default_factory=HardConstraints)
    
    render_order: List[str] = field(default_factory=list)
    inference_chain: List[str] = field(default_factory=list)
    
    def get_node_by_role(self, role: str) -> Optional[LayoutNode]:
        for node in self.nodes.values():
            if node.role == role:
                return node
        return None
    
    def get_l1_node(self) -> Optional[LayoutNode]:
        return self.get_node_by_role("L1")
    
    def validate(self) -> tuple[bool, List[str]]:
        issues = []
        
        if self.hard_constraints.template_required and not self.template_id:
            issues.append("No template_id assigned")
        
        l1 = self.get_l1_node()
        if l1 is None:
            issues.append("No L1 node defined")
        else:
            if self.hard_constraints.l1_must_be_reward:
                if "reward" not in l1.node_id and "result" not in l1.node_id and "final" not in l1.node_id and "after" not in l1.node_id:
                    issues.append(f"L1 node is not reward: {l1.node_id}")
            
            if self.hard_constraints.no_character_as_l1:
                if "character" in l1.node_id or "witch" in l1.node_id or "mascot" in l1.node_id:
                    issues.append(f"Character is L1 node: {l1.node_id}")
            
            if self.hard_constraints.reward_must_be_central:
                if l1.position not in ["center", "top_center", "bottom_center"]:
                    if "reward" in l1.node_id or "result" in l1.node_id:
                        pass
        
        budget_ok, budget_issues = self.visual_budget.validate()
        if not budget_ok:
            issues.extend(budget_issues)
        
        if self.hard_constraints.minimum_reward_budget > 0:
            reward_budget = self.visual_budget.allocation.get("reward", 0)
            if reward_budget < self.hard_constraints.minimum_reward_budget:
                issues.append(
                    f"Reward budget {reward_budget:.1f} < minimum "
                    f"{self.hard_constraints.minimum_reward_budget}"
                )
        
        if self.spatial_constraints:
            pass
        
        return len(issues) == 0, issues
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ast_id": self.ast_id,
            "template_id": self.template_id,
            "mechanism_type": self.mechanism_type,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "spatial_constraints": [c.to_dict() for c in self.spatial_constraints],
            "visual_budget": self.visual_budget.to_dict(),
            "hard_constraints": self.hard_constraints.to_dict(),
            "render_order": self.render_order,
            "inference_chain": self.inference_chain,
        }
