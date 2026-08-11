"""Inference Validator & Reject Engine - 推理验证器与拒绝引擎

P1-1 Inference Validator（替代 attention flow）：
  输出：mechanism clarity, reward vividness, identity projection, confusion risk

P1-2 Reject Engine（强化版）：
  必须 reject：
  - reward not L1
  - mechanism unclear
  - no spatial constraint
  - template missing
  - inference score < threshold
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from .layout_ast import LayoutAST
from .inference_model import ClickInferenceModel, InferenceResult


REJECT_THRESHOLDS = {
    "min_mechanism_clarity": 0.5,
    "min_reward_vividness": 0.5,
    "min_identity_projection": 0.4,
    "max_friction": 0.5,
    "max_confusion_risk": 0.5,
    "min_click_prob_proxy": 0.015,
    "min_reward_budget": 35.0,
}


@dataclass
class ValidationReport:
    mechanism_clarity: float
    reward_vividness: float
    identity_projection: float
    friction: float
    confusion_risk: float
    click_probability_proxy: float
    
    is_valid: bool
    issues: List[str]
    warnings: List[str]
    
    dimension_scores: Dict[str, float]
    inference_chain: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mechanism_clarity": round(self.mechanism_clarity, 3),
            "reward_vividness": round(self.reward_vividness, 3),
            "identity_projection": round(self.identity_projection, 3),
            "friction": round(self.friction, 3),
            "confusion_risk": round(self.confusion_risk, 3),
            "click_probability_proxy": round(self.click_probability_proxy, 4),
            "is_valid": self.is_valid,
            "issues": self.issues,
            "warnings": self.warnings,
            "dimension_scores": {k: round(v, 3) for k, v in self.dimension_scores.items()},
            "inference_chain": [round(p, 3) for p in self.inference_chain],
        }


class InferenceValidator:
    """推理验证器 - 验证创意的推理完整度
    
    替代原有的 attention flow（注意力流模拟）。
    不再做 saliency simulation（显著性模拟），
    而是做 inference validation（推理验证）。
    """
    
    @classmethod
    def validate(cls, ast: LayoutAST,
                  visual_analysis: Dict[str, Any] = None) -> ValidationReport:
        inference = ClickInferenceModel.infer_click_probability(ast, visual_analysis)
        
        issues = []
        warnings = []
        
        if inference.mechanism_clarity < REJECT_THRESHOLDS["min_mechanism_clarity"]:
            issues.append(
                f"Mechanism clarity too low: {inference.mechanism_clarity:.2f} "
                f"(min {REJECT_THRESHOLDS['min_mechanism_clarity']})"
            )
        
        if inference.reward_vividness < REJECT_THRESHOLDS["min_reward_vividness"]:
            issues.append(
                f"Reward vividness too low: {inference.reward_vividness:.2f} "
                f"(min {REJECT_THRESHOLDS['min_reward_vividness']})"
            )
        
        if inference.identity_projection < REJECT_THRESHOLDS["min_identity_projection"]:
            warnings.append(
                f"Identity projection low: {inference.identity_projection:.2f} "
                f"(min {REJECT_THRESHOLDS['min_identity_projection']})"
            )
        
        if inference.friction > REJECT_THRESHOLDS["max_friction"]:
            issues.append(
                f"Friction too high: {inference.friction:.2f} "
                f"(max {REJECT_THRESHOLDS['max_friction']})"
            )
        
        if inference.confusion_risk > REJECT_THRESHOLDS["max_confusion_risk"]:
            issues.append(
                f"Confusion risk too high: {inference.confusion_risk:.2f} "
                f"(max {REJECT_THRESHOLDS['max_confusion_risk']})"
            )
        
        if inference.click_probability_proxy < REJECT_THRESHOLDS["min_click_prob_proxy"]:
            warnings.append(
                f"Click probability proxy low: {inference.click_probability_proxy:.4f} "
                f"(min {REJECT_THRESHOLDS['min_click_prob_proxy']})"
            )
        
        l1 = ast.get_l1_node()
        if l1:
            is_reward_l1 = any(
                kw in l1.node_id.lower()
                for kw in ["result", "final", "after", "reward", "legendary"]
            )
            if not is_reward_l1:
                issues.append(f"L1 node is not reward: {l1.node_id}")
            
            is_character_l1 = any(
                kw in l1.node_id.lower()
                for kw in ["character", "witch", "mascot", "avatar"]
            )
            if is_character_l1:
                issues.append(f"Character is L1 node: {l1.node_id}")
        else:
            issues.append("No L1 node defined")
        
        reward_budget = ast.visual_budget.allocation.get("reward", 0)
        if reward_budget < REJECT_THRESHOLDS["min_reward_budget"]:
            issues.append(
                f"Reward budget too low: {reward_budget:.1f} "
                f"(min {REJECT_THRESHOLDS['min_reward_budget']})"
            )
        
        if not ast.template_id:
            issues.append("No template_id assigned")
        
        if len(ast.spatial_constraints) == 0:
            warnings.append("No spatial constraints defined")
        
        is_valid = len(issues) == 0
        
        dimension_scores = {
            "mechanism_clarity": inference.mechanism_clarity,
            "reward_vividness": inference.reward_vividness,
            "identity_projection": inference.identity_projection,
            "friction_inverse": 1.0 - inference.friction,
        }
        
        return ValidationReport(
            mechanism_clarity=inference.mechanism_clarity,
            reward_vividness=inference.reward_vividness,
            identity_projection=inference.identity_projection,
            friction=inference.friction,
            confusion_risk=inference.confusion_risk,
            click_probability_proxy=inference.click_probability_proxy,
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            dimension_scores=dimension_scores,
            inference_chain=inference.inference_chain_probability,
        )


class RejectEngine:
    """强化版拒绝引擎
    
    基于推理验证结果，决定是否 reject 该创意。
    
    硬拒绝条件（任一满足即 reject）：
    1. reward not L1
    2. mechanism unclear (clarity < threshold)
    3. no spatial constraint
    4. template missing
    5. inference score < threshold
    """
    
    HARD_REJECT_CONDITIONS = [
        "reward_not_l1",
        "character_is_l1",
        "no_template",
        "mechanism_unclear",
        "reward_not_visible",
        "confusion_too_high",
    ]
    
    @classmethod
    def check_reject(cls, ast: LayoutAST,
                      validation_report: ValidationReport = None) -> Tuple[bool, List[str]]:
        if validation_report is None:
            validation_report = InferenceValidator.validate(ast)
        
        reject_reasons = []
        
        l1 = ast.get_l1_node()
        if l1:
            is_reward_l1 = any(
                kw in l1.node_id.lower()
                for kw in ["result", "final", "after", "reward", "legendary"]
            )
            if not is_reward_l1:
                reject_reasons.append("reward_not_l1")
            
            is_character_l1 = any(
                kw in l1.node_id.lower()
                for kw in ["character", "witch", "mascot", "avatar"]
            )
            if is_character_l1:
                reject_reasons.append("character_is_l1")
        else:
            reject_reasons.append("no_l1_node")
        
        if not ast.template_id:
            reject_reasons.append("no_template")
        
        if validation_report.mechanism_clarity < REJECT_THRESHOLDS["min_mechanism_clarity"]:
            reject_reasons.append("mechanism_unclear")
        
        if validation_report.reward_vividness < REJECT_THRESHOLDS["min_reward_vividness"]:
            reject_reasons.append("reward_not_visible")
        
        if validation_report.confusion_risk > REJECT_THRESHOLDS["max_confusion_risk"]:
            reject_reasons.append("confusion_too_high")
        
        if len(ast.spatial_constraints) == 0:
            reject_reasons.append("no_spatial_constraints")
        
        reward_budget = ast.visual_budget.allocation.get("reward", 0)
        if reward_budget < REJECT_THRESHOLDS["min_reward_budget"]:
            reject_reasons.append("reward_budget_too_low")
        
        is_rejected = len(reject_reasons) > 0
        return is_rejected, reject_reasons
    
    @classmethod
    def get_reject_explanation(cls, reject_reasons: List[str]) -> Dict[str, str]:
        explanations = {
            "reward_not_l1": "Reward is not the L1 visual element",
            "character_is_l1": "Character occupies the L1 visual position",
            "no_template": "No template_id assigned",
            "mechanism_unclear": "Mechanism is not clearly understandable",
            "reward_not_visible": "Reward is not vivid/visible enough",
            "confusion_too_high": "Risk of user confusion is too high",
            "no_l1_node": "No L1 focal point defined",
            "no_spatial_constraints": "No spatial constraints defined",
            "reward_budget_too_low": "Reward visual budget is insufficient",
        }
        return {r: explanations.get(r, r) for r in reject_reasons}
