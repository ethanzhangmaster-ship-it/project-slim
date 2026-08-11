"""Template Compiler Rules - 模板编译规则库

Template = compilation rule（编译规则），不是 description（描述）。

每个模板定义：
  - 节点结构（nodes）
  - 空间约束（spatial constraints）
  - 推理链（inference chain）
  - 渲染顺序（render order）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional

from .layout_ast import (
    LayoutAST,
    LayoutNode,
    SpatialConstraint,
    HardConstraints,
)
from .visual_budget import VisualBudgetSystem


@dataclass
class TemplateCompilationRule:
    template_id: str
    template_name: str
    mechanism_type: str
    attention_goal: str
    
    node_specs: List[Dict[str, Any]] = field(default_factory=list)
    constraint_specs: List[Dict[str, Any]] = field(default_factory=list)
    inference_chain: List[str] = field(default_factory=list)
    render_order: List[str] = field(default_factory=list)
    
    budget_profile: str = "reward_first"
    
    hard_constraints: HardConstraints = field(default_factory=HardConstraints)
    
    def compile(self, dna_context: Dict[str, Any] = None) -> LayoutAST:
        ast = LayoutAST(
            template_id=self.template_id,
            mechanism_type=self.mechanism_type,
            hard_constraints=self.hard_constraints,
            inference_chain=self.inference_chain.copy(),
            render_order=self.render_order.copy(),
        )
        
        budget = VisualBudgetSystem.allocate_budget(
            self.template_id,
            self.mechanism_type,
            self.attention_goal,
        )
        ast.visual_budget = budget
        
        for spec in self.node_specs:
            node = self._create_node_from_spec(spec, budget.allocation)
            ast.nodes[node.node_id] = node
        
        for spec in self.constraint_specs:
            constraint = self._create_constraint_from_spec(spec)
            ast.spatial_constraints.append(constraint)
        
        return ast
    
    def _create_node_from_spec(self, spec: Dict[str, Any],
                                budget_allocation: Dict[str, float]) -> LayoutNode:
        budget_category = spec.get("budget_category", "mechanism")
        budget_amount = budget_allocation.get(budget_category, 0.0)
        
        node = LayoutNode(
            node_id=spec["node_id"],
            role=spec.get("role", "L3"),
            position=spec.get("position", "supporting"),
            size_ratio=spec.get("size_ratio", 0.2),
            brightness_bias=spec.get("brightness_bias", 0.0),
            contrast_bias=spec.get("contrast_bias", 0.0),
            glow_intensity=spec.get("glow_intensity", 0.0),
            z_index=spec.get("z_index", 0),
            opacity=spec.get("opacity", 1.0),
            color_temperature=spec.get("color_temperature", "neutral"),
            description=spec.get("description", ""),
        )
        
        if budget_amount > 0 and budget_category != "background":
            VisualBudgetSystem.apply_budget_to_node(node, budget_category, budget_amount)
        else:
            node.visual_budget = budget_amount
        
        return node
    
    def _create_constraint_from_spec(self, spec: Dict[str, Any]) -> SpatialConstraint:
        return SpatialConstraint(
            constraint_id=spec["constraint_id"],
            type=spec.get("type", "spatial"),
            subject=spec.get("subject", ""),
            reference=spec.get("reference", ""),
            operator=spec.get("operator", ""),
            value=spec.get("value", 0.0),
            description=spec.get("description", ""),
        )


class TemplateCompilerLibrary:
    _rules: Dict[str, TemplateCompilationRule] = {}
    
    @classmethod
    def get_rule(cls, template_id: str) -> Optional[TemplateCompilationRule]:
        if not cls._rules:
            cls._init_rules()
        return cls._rules.get(template_id)
    
    @classmethod
    def list_rules(cls) -> List[str]:
        if not cls._rules:
            cls._init_rules()
        return list(cls._rules.keys())
    
    @classmethod
    def compile_template(cls, template_id: str,
                         dna_context: Dict[str, Any] = None) -> LayoutAST:
        rule = cls.get_rule(template_id)
        if not rule:
            raise ValueError(f"Unknown template_id: {template_id}")
        return rule.compile(dna_context)
    
    @classmethod
    def _init_rules(cls):
        cls._rules = {}
        cls._init_merge_formula_rule()
        cls._init_evolution_chain_rule()
        cls._init_before_after_rule()
    
    @classmethod
    def _init_merge_formula_rule(cls):
        rule = TemplateCompilationRule(
            template_id="merge_formula",
            template_name="Merge Formula (A + B = C)",
            mechanism_type="merge",
            attention_goal="reward_first",
            budget_profile="reward_first",
            inference_chain=[
                "see_result_C",
                "understand_merge",
                "imagine_doing_it",
                "want_to_try",
            ],
            render_order=[
                "background",
                "item_a",
                "item_b",
                "plus_sign",
                "equals_sign",
                "result_c",
                "character_hands",
                "cta_banner",
            ],
        )
        
        rule.node_specs = [
            {
                "node_id": "result_c",
                "role": "L1",
                "position": "center",
                "size_ratio": 0.4,
                "brightness_bias": 0.3,
                "contrast_bias": 0.25,
                "glow_intensity": 0.7,
                "z_index": 10,
                "budget_category": "reward",
                "color_temperature": "warm",
                "description": "Merge result C - glowing reward, L1 visual focus",
            },
            {
                "node_id": "item_a",
                "role": "L2",
                "position": "left_side",
                "size_ratio": 0.22,
                "z_index": 5,
                "budget_category": "mechanism",
                "description": "Item A - left side merge ingredient",
            },
            {
                "node_id": "item_b",
                "role": "L2",
                "position": "right_side",
                "size_ratio": 0.22,
                "z_index": 5,
                "budget_category": "mechanism",
                "description": "Item B - right side merge ingredient",
            },
            {
                "node_id": "plus_sign",
                "role": "L2",
                "position": "center",
                "size_ratio": 0.05,
                "z_index": 6,
                "budget_category": "mechanism",
                "description": "Plus sign between A and B",
            },
            {
                "node_id": "equals_sign",
                "role": "L2",
                "position": "center",
                "size_ratio": 0.06,
                "z_index": 6,
                "budget_category": "mechanism",
                "description": "Equals sign pointing to result",
            },
            {
                "node_id": "character_hands",
                "role": "L3",
                "position": "peripheral",
                "size_ratio": 0.25,
                "z_index": 3,
                "opacity": 0.85,
                "budget_category": "identity",
                "description": "Witch character hands reaching in",
            },
            {
                "node_id": "cta_banner",
                "role": "L4",
                "position": "bottom_center",
                "size_ratio": 0.1,
                "z_index": 8,
                "budget_category": "ui",
                "description": "CTA text banner at bottom",
            },
            {
                "node_id": "background",
                "role": "L4",
                "position": "background",
                "size_ratio": 1.0,
                "z_index": 0,
                "budget_category": "background",
                "color_temperature": "cool",
                "description": "Background environment",
            },
        ]
        
        rule.constraint_specs = [
            {
                "constraint_id": "c1_result_above_a_b",
                "type": "vertical_position",
                "subject": "result_c",
                "reference": "item_a,item_b",
                "operator": "above_or_center",
                "value": 1.0,
                "description": "Result C must be visually dominant over A and B",
            },
            {
                "constraint_id": "c2_a_b_symmetric",
                "type": "horizontal_symmetry",
                "subject": "item_a",
                "reference": "item_b",
                "operator": "mirror",
                "value": 1.0,
                "description": "Items A and B must be horizontally symmetric",
            },
            {
                "constraint_id": "c3_result_glows_most",
                "type": "visual_dominance",
                "subject": "result_c",
                "reference": "all_others",
                "operator": "highest_glow",
                "value": 1.0,
                "description": "Result C must have highest glow intensity",
            },
            {
                "constraint_id": "c4_character_not_center",
                "type": "position_ban",
                "subject": "character_hands",
                "reference": "center",
                "operator": "not_in",
                "value": 1.0,
                "description": "Character must not occupy center position",
            },
        ]
        
        cls._rules["merge_formula"] = rule
    
    @classmethod
    def _init_evolution_chain_rule(cls):
        rule = TemplateCompilationRule(
            template_id="evolution_chain",
            template_name="Evolution Chain (1 -> 2 -> 3 -> MAX)",
            mechanism_type="evolution",
            attention_goal="reward_first",
            budget_profile="high_certainty",
            inference_chain=[
                "see_final_MAX",
                "understand_growth",
                "track_progression",
                "imagine_reaching_MAX",
            ],
            render_order=[
                "background",
                "stage1",
                "stage2",
                "stage3",
                "arrows",
                "final_form",
                "character",
                "cta_banner",
            ],
        )
        
        rule.node_specs = [
            {
                "node_id": "final_form",
                "role": "L1",
                "position": "right_side",
                "size_ratio": 0.45,
                "brightness_bias": 0.35,
                "contrast_bias": 0.3,
                "glow_intensity": 0.8,
                "z_index": 10,
                "budget_category": "reward",
                "color_temperature": "warm",
                "description": "Final MAX evolution form - largest, L1 focus",
            },
            {
                "node_id": "stage3",
                "role": "L2",
                "position": "center_right",
                "size_ratio": 0.28,
                "z_index": 5,
                "budget_category": "mechanism",
                "description": "Stage 3 - large pre-final form",
            },
            {
                "node_id": "stage2",
                "role": "L2",
                "position": "center_left",
                "size_ratio": 0.2,
                "z_index": 4,
                "budget_category": "mechanism",
                "description": "Stage 2 - medium form",
            },
            {
                "node_id": "stage1",
                "role": "L3",
                "position": "left_side",
                "size_ratio": 0.15,
                "z_index": 3,
                "budget_category": "mechanism",
                "description": "Stage 1 - smallest starting form",
            },
            {
                "node_id": "arrows",
                "role": "L2",
                "position": "linear_left_to_right",
                "size_ratio": 0.08,
                "z_index": 6,
                "budget_category": "mechanism",
                "description": "Evolution arrows between stages",
            },
            {
                "node_id": "character",
                "role": "L3",
                "position": "left_side",
                "size_ratio": 0.18,
                "z_index": 2,
                "opacity": 0.8,
                "budget_category": "identity",
                "description": "Witch character observing evolution",
            },
            {
                "node_id": "cta_banner",
                "role": "L4",
                "position": "bottom_center",
                "size_ratio": 0.08,
                "z_index": 8,
                "budget_category": "ui",
                "description": "CTA text banner at bottom",
            },
            {
                "node_id": "background",
                "role": "L4",
                "position": "background",
                "size_ratio": 1.0,
                "z_index": 0,
                "budget_category": "background",
                "description": "Background environment",
            },
        ]
        
        rule.constraint_specs = [
            {
                "constraint_id": "c1_size_progression",
                "type": "size_sequence",
                "subject": "stage1,stage2,stage3,final_form",
                "operator": "increasing",
                "value": 1.0,
                "description": "Forms must increase in size from stage1 to final",
            },
            {
                "constraint_id": "c2_linear_layout",
                "type": "horizontal_sequence",
                "subject": "stage1,stage2,stage3,final_form",
                "operator": "left_to_right",
                "value": 1.0,
                "description": "Progression must be left-to-right linear",
            },
            {
                "constraint_id": "c3_final_is_largest",
                "type": "visual_dominance",
                "subject": "final_form",
                "reference": "all_others",
                "operator": "largest",
                "value": 1.0,
                "description": "Final form must be largest element",
            },
            {
                "constraint_id": "c4_character_not_obstructing",
                "type": "position_ban",
                "subject": "character",
                "reference": "evolution_path",
                "operator": "not_on",
                "value": 1.0,
                "description": "Character must not obstruct evolution path",
            },
        ]
        
        cls._rules["evolution_chain"] = rule
    
    @classmethod
    def _init_before_after_rule(cls):
        rule = TemplateCompilationRule(
            template_id="before_after",
            template_name="Before/After Transformation",
            mechanism_type="transformation",
            attention_goal="reward_first",
            budget_profile="reward_first",
            inference_chain=[
                "see_after_state",
                "compare_before_after",
                "understand_transformation",
                "want_transformation",
            ],
            render_order=[
                "background",
                "before_side",
                "divider",
                "after_side",
                "character",
                "cta_banner",
            ],
        )
        
        rule.node_specs = [
            {
                "node_id": "after_side",
                "role": "L1",
                "position": "right_side",
                "size_ratio": 0.42,
                "brightness_bias": 0.35,
                "contrast_bias": 0.25,
                "glow_intensity": 0.6,
                "z_index": 8,
                "budget_category": "reward",
                "color_temperature": "warm",
                "description": "After/reward state - right side, brighter, L1 focus",
            },
            {
                "node_id": "before_side",
                "role": "L2",
                "position": "left_side",
                "size_ratio": 0.38,
                "brightness_bias": -0.1,
                "contrast_bias": -0.05,
                "z_index": 5,
                "budget_category": "mechanism",
                "color_temperature": "cool",
                "description": "Before/low state - left side, dimmer",
            },
            {
                "node_id": "divider",
                "role": "L2",
                "position": "center",
                "size_ratio": 0.05,
                "z_index": 10,
                "budget_category": "mechanism",
                "description": "Vertical divider with transformation arrow",
            },
            {
                "node_id": "character",
                "role": "L3",
                "position": "peripheral",
                "size_ratio": 0.18,
                "z_index": 3,
                "opacity": 0.85,
                "budget_category": "identity",
                "description": "Character shown in both states or as guide",
            },
            {
                "node_id": "cta_banner",
                "role": "L4",
                "position": "bottom_center",
                "size_ratio": 0.08,
                "z_index": 8,
                "budget_category": "ui",
                "description": "CTA text banner at bottom",
            },
            {
                "node_id": "background",
                "role": "L4",
                "position": "background",
                "size_ratio": 1.0,
                "z_index": 0,
                "budget_category": "background",
                "description": "Split background - left dim, right bright",
            },
        ]
        
        rule.constraint_specs = [
            {
                "constraint_id": "c1_after_brighter",
                "type": "brightness_comparison",
                "subject": "after_side",
                "reference": "before_side",
                "operator": "brighter_than",
                "value": 0.3,
                "description": "After side must be brighter than before side",
            },
            {
                "constraint_id": "c2_split_screen",
                "type": "layout",
                "subject": "before_side,after_side",
                "reference": "divider",
                "operator": "left_right_split",
                "value": 1.0,
                "description": "Before/after must be left/right split screen",
            },
            {
                "constraint_id": "c3_reward_on_right",
                "type": "position_rule",
                "subject": "after_side",
                "reference": "right",
                "operator": "is_at",
                "value": 1.0,
                "description": "Reward (after state) must be on right side",
            },
            {
                "constraint_id": "c4_divider_visible",
                "type": "visibility",
                "subject": "divider",
                "operator": "clearly_visible",
                "value": 1.0,
                "description": "Divider must be clearly visible",
            },
        ]
        
        cls._rules["before_after"] = rule
