"""Render Constraint Engine - 渲染约束引擎

核心原则：prompt is NOT free text anymore.

输出格式（按角色分组）：
{
  "reward": {
    "position": "center",
    "size": 0.45,
    "glow": "high"
  },
  "mechanism": {
    "visibility": "high",
    "structure": "ui-based"
  },
  "identity": {
    "opacity": "low"
  }
}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .layout_ast import LayoutAST, LayoutNode


@dataclass
class RenderConstraintGroup:
    """按角色分组的渲染约束"""
    position: str = ""
    size: float = 0.0
    brightness: str = ""
    contrast: str = ""
    glow: str = ""
    opacity: float = 1.0
    dominance: str = ""
    visibility: str = "high"
    structure: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "size": self.size,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "glow": self.glow,
            "opacity": self.opacity,
            "dominance": self.dominance,
            "visibility": self.visibility,
            "structure": self.structure,
            "notes": self.notes,
        }


@dataclass
class RenderConstraints:
    """结构化的渲染约束（无自由文本）"""
    reward: RenderConstraintGroup = field(default_factory=RenderConstraintGroup)
    mechanism: RenderConstraintGroup = field(default_factory=RenderConstraintGroup)
    identity: RenderConstraintGroup = field(default_factory=RenderConstraintGroup)
    ui: RenderConstraintGroup = field(default_factory=RenderConstraintGroup)
    
    aspect_ratio: str = "9:16"
    color_palette_hint: str = ""
    negative_constraints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reward": self.reward.to_dict(),
            "mechanism": self.mechanism.to_dict(),
            "identity": self.identity.to_dict(),
            "ui": self.ui.to_dict(),
            "aspect_ratio": self.aspect_ratio,
            "color_palette_hint": self.color_palette_hint,
            "negative_constraints": self.negative_constraints,
        }


class RenderConstraintEngine:
    """将 Layout AST 编译为角色分组的渲染约束
    
    输出的不是自由文本，而是结构化的约束字典：
    - reward: center, 45% size, high glow
    - mechanism: high visibility, structured UI
    - identity: low opacity, peripheral
    """
    
    @classmethod
    def compile_constraints(cls, ast: LayoutAST,
                             style_hints: Dict[str, Any] = None) -> RenderConstraints:
        constraints = RenderConstraints()
        
        nodes_by_role = {"L1": [], "L2": [], "L3": [], "L4": []}
        for node_id, node in ast.nodes.items():
            if node.role in nodes_by_role:
                nodes_by_role[node.role].append(node)
        
        l1_nodes = nodes_by_role["L1"]
        l2_nodes = nodes_by_role["L2"]
        l3_nodes = nodes_by_role["L3"]
        l4_nodes = nodes_by_role["L4"]
        
        if l1_nodes:
            l1 = l1_nodes[0]
            if "result" in l1.node_id or "final" in l1.node_id or "after" in l1.node_id or "reward" in l1.node_id:
                constraints.reward = cls._node_to_group(l1)
            elif "character" in l1.node_id or "witch" in l1.node_id:
                constraints.identity = cls._node_to_group(l1)
        
        if l2_nodes:
            combined_mech = cls._combine_nodes(l2_nodes)
            constraints.mechanism = combined_mech
            constraints.mechanism.structure = "ui-based"
            constraints.mechanism.visibility = "high"
        
        if l3_nodes:
            combined_ident = cls._combine_nodes(l3_nodes)
            combined_ident.opacity = 0.3
            constraints.identity = combined_ident
        
        if l4_nodes:
            ui_nodes = [n for n in l4_nodes if "cta" in n.node_id or "banner" in n.node_id]
            if ui_nodes:
                constraints.ui = cls._node_to_group(ui_nodes[0])
        
        constraints.negative_constraints = cls._generate_negative_constraints(ast)
        
        if style_hints:
            constraints.aspect_ratio = style_hints.get("aspect_ratio", "9:16")
            constraints.color_palette_hint = style_hints.get("color_palette", "")
        
        return constraints
    
    @classmethod
    def _node_to_group(cls, node: LayoutNode) -> RenderConstraintGroup:
        group = RenderConstraintGroup()
        
        group.position = node.position
        group.size = node.size_ratio
        group.opacity = node.opacity
        
        if node.brightness_bias > 0.2:
            group.brightness = "high"
        elif node.brightness_bias > 0.1:
            group.brightness = "medium"
        else:
            group.brightness = "normal"
        
        if node.contrast_bias > 0.2:
            group.contrast = "high"
        elif node.contrast_bias > 0.1:
            group.contrast = "medium"
        else:
            group.contrast = "normal"
        
        if node.glow_intensity > 0.6:
            group.glow = "high"
        elif node.glow_intensity > 0.3:
            group.glow = "medium"
        elif node.glow_intensity > 0.1:
            group.glow = "low"
        else:
            group.glow = "none"
        
        if node.role == "L1":
            group.dominance = "highest"
        elif node.role == "L2":
            group.dominance = "high"
        elif node.role == "L3":
            group.dominance = "medium"
        else:
            group.dominance = "low"
        
        group.notes = node.description
        
        return group
    
    @classmethod
    def _combine_nodes(cls, nodes: List[LayoutNode]) -> RenderConstraintGroup:
        if not nodes:
            return RenderConstraintGroup()
        
        first = nodes[0]
        combined = cls._node_to_group(first)
        
        avg_size = sum(n.size_ratio for n in nodes) / len(nodes)
        combined.size = round(avg_size, 3)
        
        avg_brightness = sum(n.brightness_bias for n in nodes) / len(nodes)
        combined.brightness = "high" if avg_brightness > 0.15 else "normal"
        
        max_glow = max(n.glow_intensity for n in nodes)
        combined.glow = "high" if max_glow > 0.5 else "medium" if max_glow > 0.2 else "low"
        
        return combined
    
    @classmethod
    def _generate_negative_constraints(cls, ast: LayoutAST) -> List[str]:
        negatives = []
        
        l1 = ast.get_l1_node()
        if l1 and "character" not in l1.node_id:
            negatives.append("no character in center foreground")
            negatives.append("character not main focal point")
        
        negatives.extend([
            "no visual clutter",
            "no text dense areas",
        ])
        
        return negatives
    
    @classmethod
    def generate_structured_output(cls, constraints: RenderConstraints) -> str:
        """生成符合需求格式的结构化输出"""
        import json
        return json.dumps(constraints.to_dict(), indent=2)
