"""Inference Model - 点击推断模型

核心变化：不再是"评分系统"，而是 click inference model（点击推断模型）。

User Click = P(mechanism understood)
            × P(reward imagined)
            × P(identity projection)
            × P(friction low)

输出：
  - mechanism_inference_score (0-1)
  - reward_simulation_score (0-1)
  - identity_projection_score (0-1)
  - friction_score (0-1)
  - click_probability_proxy (0-1)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import math

from .layout_ast import LayoutAST


@dataclass
class InferenceResult:
    mechanism_clarity: float
    reward_vividness: float
    identity_projection: float
    friction: float
    
    click_probability_proxy: float
    
    mechanism_breakdown: Dict[str, Any]
    reward_breakdown: Dict[str, Any]
    identity_breakdown: Dict[str, Any]
    friction_breakdown: Dict[str, Any]
    
    confusion_risk: float
    inference_chain_probability: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mechanism_clarity": round(self.mechanism_clarity, 3),
            "reward_vividness": round(self.reward_vividness, 3),
            "identity_projection": round(self.identity_projection, 3),
            "friction": round(self.friction, 3),
            "click_probability_proxy": round(self.click_probability_proxy, 4),
            "mechanism_breakdown": self.mechanism_breakdown,
            "reward_breakdown": self.reward_breakdown,
            "identity_breakdown": self.identity_breakdown,
            "friction_breakdown": self.friction_breakdown,
            "confusion_risk": round(self.confusion_risk, 3),
            "inference_chain_probability": [round(p, 3) for p in self.inference_chain_probability],
        }


class ClickInferenceModel:
    """用户点击决策的推断模型
    
    这不是启发式加权，而是概率分解模型：
    P(click) = P(understand_mechanism) * P(imagine_reward) * P(project_self) * P(low_friction)
    """
    
    BASELINE_CLICK_PROB = 0.02
    
    @classmethod
    def infer_click_probability(cls, ast: LayoutAST,
                                 visual_analysis: Dict[str, Any] = None) -> InferenceResult:
        mechanism_clarity, mech_breakdown = cls._infer_mechanism_clarity(ast, visual_analysis)
        reward_vividness, reward_breakdown = cls._infer_reward_vividness(ast, visual_analysis)
        identity_projection, ident_breakdown = cls._infer_identity_projection(ast, visual_analysis)
        friction, friction_breakdown = cls._infer_friction(ast, visual_analysis)
        
        click_prob = cls._compute_joint_probability(
            mechanism_clarity,
            reward_vividness,
            identity_projection,
            1.0 - friction,
        )
        
        confusion_risk = cls._compute_confusion_risk(
            mechanism_clarity,
            reward_vividness,
            friction,
        )
        
        chain_probs = [
            mechanism_clarity,
            mechanism_clarity * reward_vividness,
            mechanism_clarity * reward_vividness * identity_projection,
            click_prob,
        ]
        
        return InferenceResult(
            mechanism_clarity=mechanism_clarity,
            reward_vividness=reward_vividness,
            identity_projection=identity_projection,
            friction=friction,
            click_probability_proxy=click_prob,
            mechanism_breakdown=mech_breakdown,
            reward_breakdown=reward_breakdown,
            identity_breakdown=ident_breakdown,
            friction_breakdown=friction_breakdown,
            confusion_risk=confusion_risk,
            inference_chain_probability=chain_probs,
        )
    
    @classmethod
    def _compute_joint_probability(cls, p_mechanism: float, p_reward: float,
                                    p_identity: float, p_no_friction: float) -> float:
        joint = p_mechanism * p_reward * p_identity * p_no_friction
        scaled = cls.BASELINE_CLICK_PROB + joint * (1.0 - cls.BASELINE_CLICK_PROB)
        return min(1.0, max(0.0, scaled))
    
    @classmethod
    def _infer_mechanism_clarity(cls, ast: LayoutAST,
                                  visual_analysis: Dict[str, Any] = None) -> Tuple[float, Dict[str, Any]]:
        score = 0.5
        breakdown = {}
        
        l1 = ast.get_l1_node()
        if l1 and l1.role == "L1":
            score += 0.15
            breakdown["l1_defined"] = True
        
        mechanism_nodes = [n for n in ast.nodes.values() if n.role == "L2"]
        if mechanism_nodes:
            score += 0.15
            breakdown["mechanism_nodes_count"] = len(mechanism_nodes)
        
        has_process_indicator = any(
            "arrow" in n_id.lower() or "plus" in n_id.lower() or "equal" in n_id.lower() or "divider" in n_id.lower()
            for n_id in ast.nodes
        )
        if has_process_indicator:
            score += 0.1
            breakdown["process_indicator"] = True
        
        mechanism_budget = ast.visual_budget.allocation.get("mechanism", 0)
        if mechanism_budget >= 25:
            score += 0.1
        breakdown["mechanism_budget"] = mechanism_budget
        
        spatial_constraints = len(ast.spatial_constraints)
        if spatial_constraints >= 2:
            score += 0.05
        breakdown["spatial_constraints_count"] = spatial_constraints
        
        if visual_analysis:
            if visual_analysis.get("mechanism_visible"):
                score += 0.1
            if visual_analysis.get("mechanism_tracable"):
                score += 0.05
        
        score = min(1.0, max(0.0, score))
        breakdown["total"] = round(score, 3)
        
        return score, breakdown
    
    @classmethod
    def _infer_reward_vividness(cls, ast: LayoutAST,
                                 visual_analysis: Dict[str, Any] = None) -> Tuple[float, Dict[str, Any]]:
        score = 0.4
        breakdown = {}
        
        l1 = ast.get_l1_node()
        if l1:
            is_reward_l1 = any(kw in l1.node_id.lower() for kw in ["result", "final", "after", "reward", "legendary"])
            if is_reward_l1:
                score += 0.2
                breakdown["reward_is_l1"] = True
            
            if l1.glow_intensity > 0.5:
                score += 0.1
                breakdown["high_glow"] = True
            
            if l1.brightness_bias > 0.2:
                score += 0.05
                breakdown["high_brightness"] = True
            
            if l1.size_ratio > 0.35:
                score += 0.1
                breakdown["large_size"] = True
        
        reward_budget = ast.visual_budget.allocation.get("reward", 0)
        if reward_budget >= 40:
            score += 0.1
        elif reward_budget >= 35:
            score += 0.05
        breakdown["reward_budget"] = reward_budget
        
        if visual_analysis:
            if visual_analysis.get("reward_emotional"):
                score += 0.05
            if visual_analysis.get("reward_clear"):
                score += 0.1
        
        score = min(1.0, max(0.0, score))
        breakdown["total"] = round(score, 3)
        
        return score, breakdown
    
    @classmethod
    def _infer_identity_projection(cls, ast: LayoutAST,
                                     visual_analysis: Dict[str, Any] = None) -> Tuple[float, Dict[str, Any]]:
        score = 0.5
        breakdown = {}
        
        identity_nodes = [n for n in ast.nodes.values() if n.role == "L3"]
        if identity_nodes:
            score += 0.1
            breakdown["identity_nodes_count"] = len(identity_nodes)
            
            for node in identity_nodes:
                if "hand" in node.node_id.lower() or "character" in node.node_id.lower():
                    if node.position in ["peripheral", "side", "left_side", "right_side"]:
                        score += 0.15
                        breakdown["character_side_position"] = True
                    elif node.position == "center":
                        score -= 0.1
                        breakdown["character_central"] = True
                    break
        
        mechanism_type = ast.mechanism_type
        if mechanism_type in ["merge", "evolution"]:
            score += 0.1
            breakdown["projection_mechanism"] = mechanism_type
        
        if ast.inference_chain:
            score += 0.05
            breakdown["has_inference_chain"] = True
        
        if visual_analysis:
            if visual_analysis.get("player_perspective"):
                score += 0.1
            if visual_analysis.get("character_relatable"):
                score += 0.05
        
        score = min(1.0, max(0.0, score))
        breakdown["total"] = round(score, 3)
        
        return score, breakdown
    
    @classmethod
    def _infer_friction(cls, ast: LayoutAST,
                         visual_analysis: Dict[str, Any] = None) -> Tuple[float, Dict[str, Any]]:
        friction = 0.2
        breakdown = {}
        
        node_count = len(ast.nodes)
        if node_count > 8:
            friction += 0.15
            breakdown["too_many_elements"] = True
        elif node_count <= 5:
            friction -= 0.05
        breakdown["node_count"] = node_count
        
        has_clear_l1 = ast.get_l1_node() is not None
        if not has_clear_l1:
            friction += 0.2
            breakdown["no_clear_focus"] = True
        
        mechanism_nodes = [n for n in ast.nodes.values() if n.role == "L2"]
        if len(mechanism_nodes) == 0:
            friction += 0.15
            breakdown["no_mechanism_layer"] = True
        
        constraint_count = len(ast.spatial_constraints)
        if constraint_count >= 3:
            friction -= 0.05
            breakdown["good_constraints"] = True
        elif constraint_count == 0:
            friction += 0.1
            breakdown["no_constraints"] = True
        breakdown["constraint_count"] = constraint_count
        
        if visual_analysis:
            if visual_analysis.get("visual_clutter"):
                friction += 0.1
            if visual_analysis.get("text_dense"):
                friction += 0.1
        
        friction = min(1.0, max(0.0, friction))
        breakdown["total"] = round(friction, 3)
        
        return friction, breakdown
    
    @classmethod
    def _compute_confusion_risk(cls, mechanism_clarity: float,
                                 reward_vividness: float,
                                 friction: float) -> float:
        confusion = (
            (1.0 - mechanism_clarity) * 0.4 +
            (1.0 - reward_vividness) * 0.3 +
            friction * 0.3
        )
        return min(1.0, max(0.0, confusion))
