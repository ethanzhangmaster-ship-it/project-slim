"""Creative Scoring V2 - Inference-centric Scoring System

Creative Score V2:
  total_score =
    0.35 * mechanism_visibility
  + 0.25 * reward_salience
  + 0.20 * identity_projection
  + 0.10 * visual_hierarchy_match
  + 0.10 * scroll_stop_score

Reject Logic:
  - reward 不明确
  - mechanism 不可理解 (>1.5s)
  - character 占据视觉中心
  - 没有 template_id
  - identity projection < 60
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_PKG = "market_ops.creative_growth_loop"

_dna_module = importlib.import_module(f"{_PKG}.03_gene.creative_dna_v2")
CreativeDNAV2 = _dna_module.CreativeDNAV2
VisualHierarchySpec = _dna_module.VisualHierarchySpec
HierarchyRules = _dna_module.HierarchyRules

_template_module = importlib.import_module(f"{_PKG}.03_gene.template_library")
TemplateLibrary = _template_module.TemplateLibrary


WEIGHTS = {
    "mechanism_visibility": 0.35,
    "reward_salience": 0.25,
    "identity_projection": 0.20,
    "visual_hierarchy_match": 0.10,
    "scroll_stop": 0.10,
}

REJECT_THRESHOLDS = {
    "identity_projection_min": 60.0,
    "reward_salience_min": 40.0,
    "mechanism_visibility_min": 40.0,
}


class CreativeScoringV2:
    def __init__(self):
        pass
    
    def score_creative(self, dna: CreativeDNAV2, image_path: str = None,
                       visual_analysis: Dict[str, Any] = None) -> CreativeDNAV2:
        dna, _ = self.score_with_details(dna, image_path, visual_analysis)
        return dna
    
    def score_with_details(self, dna: CreativeDNAV2, image_path: str = None,
                           visual_analysis: Dict[str, Any] = None
                           ) -> Tuple[CreativeDNAV2, Dict[str, Any]]:
        details = {}
        
        if visual_analysis:
            dna.mechanism_visibility_score = self._assess_mechanism_visibility(
                visual_analysis, dna
            )
            dna.reward_salience_score = self._assess_reward_salience(
                visual_analysis, dna
            )
            dna.identity_projection_score = self._assess_identity_projection(
                visual_analysis, dna
            )
            dna.visual_hierarchy_match = self._assess_hierarchy_match(
                visual_analysis, dna
            )
            dna.scroll_stop_score = self._assess_scroll_stop(
                visual_analysis, dna
            )
        else:
            dna.mechanism_visibility_score = self._estimate_mechanism_from_dna(dna)
            dna.reward_salience_score = self._estimate_reward_from_dna(dna)
            dna.identity_projection_score = self._estimate_identity_from_dna(dna)
            dna.visual_hierarchy_match = self._estimate_hierarchy_from_dna(dna)
            dna.scroll_stop_score = self._estimate_scrollstop_from_dna(dna)
        
        dna.total_score = self._calculate_total(dna)
        
        rejected, reasons = self._check_reject(dna)
        dna.is_rejected = rejected
        dna.reject_reasons = reasons
        
        details = {
            "mechanism_visibility_breakdown": self._mechanism_breakdown(dna, visual_analysis),
            "reward_salience_breakdown": self._reward_breakdown(dna, visual_analysis),
            "identity_projection_breakdown": self._identity_breakdown(dna, visual_analysis),
            "hierarchy_match_breakdown": self._hierarchy_breakdown(dna, visual_analysis),
            "scroll_stop_breakdown": self._scrollstop_breakdown(dna, visual_analysis),
            "reject_check": {
                "is_rejected": rejected,
                "reasons": reasons,
            },
        }
        
        return dna, details
    
    def _assess_mechanism_visibility(self, va: Dict[str, Any], dna: CreativeDNAV2) -> float:
        score = 50.0
        
        if va.get("has_merge_formula") or va.get("has_evolution_chain"):
            score += 25.0
        
        if va.get("mechanism_is_central"):
            score += 15.0
        
        if va.get("mechanism_size_ratio", 0) > 0.3:
            score += 10.0
        
        return min(100.0, score)
    
    def _assess_reward_salience(self, va: Dict[str, Any], dna: CreativeDNAV2) -> float:
        score = 40.0
        
        if va.get("reward_is_l1") or va.get("reward_is_brightest"):
            score += 30.0
        
        if va.get("reward_glowing"):
            score += 15.0
        
        if va.get("reward_size_ratio", 0) > 0.25:
            score += 15.0
        
        return min(100.0, score)
    
    def _assess_identity_projection(self, va: Dict[str, Any], dna: CreativeDNAV2) -> float:
        score = 50.0
        
        if va.get("character_is_side", False):
            score += 20.0
        elif va.get("character_is_central", False):
            score -= 20.0
        
        if va.get("has_progression", False):
            score += 15.0
        
        if va.get("player_perspective", False):
            score += 15.0
        
        return max(0.0, min(100.0, score))
    
    def _assess_hierarchy_match(self, va: Dict[str, Any], dna: CreativeDNAV2) -> float:
        template = TemplateLibrary.get(dna.layout_template)
        if not template:
            return 50.0
        
        score = 60.0
        target_hierarchy = template.visual_hierarchy
        
        actual_l1 = va.get("level1_element", "")
        if actual_l1 and target_hierarchy.level1:
            if actual_l1 == target_hierarchy.level1 or actual_l1 in target_hierarchy.level1:
                score += 30.0
            else:
                score -= 20.0
        
        return max(0.0, min(100.0, score))
    
    def _assess_scroll_stop(self, va: Dict[str, Any], dna: CreativeDNAV2) -> float:
        score = 40.0
        
        if va.get("high_contrast", False):
            score += 20.0
        
        if va.get("glowing_element", False):
            score += 15.0
        
        if va.get("has_number_hook", False):
            score += 15.0
        
        if va.get("has_transformation", False):
            score += 10.0
        
        return min(100.0, score)
    
    def _estimate_mechanism_from_dna(self, dna: CreativeDNAV2) -> float:
        score = 30.0
        
        if dna.mechanism_type in ["merge", "evolution", "transformation"]:
            score += 30.0
        
        if dna.layout_template in ["merge_formula", "evolution_chain", "before_after"]:
            score += 25.0
        
        if "mechanism_first" in dna.attention_goal or "reward_first" in dna.attention_goal:
            score += 10.0
        
        return min(100.0, score)
    
    def _estimate_reward_from_dna(self, dna: CreativeDNAV2) -> float:
        score = 30.0
        
        if dna.reward_type in ["transformation", "unlock", "upgrade", "legendary_item"]:
            score += 25.0
        
        if dna.attention_goal == "reward_first":
            score += 25.0
        
        template = TemplateLibrary.get(dna.layout_template)
        if template and template.visual_hierarchy.level1 in ["result_c", "final_form", "after_side"]:
            score += 15.0
        
        return min(100.0, score)
    
    def _estimate_identity_from_dna(self, dna: CreativeDNAV2) -> float:
        score = 55.0
        
        if "self_projection" in dna.psychology_drive:
            score += 10.0
        
        if "progression_satisfaction" in dna.psychology_drive:
            score += 10.0
        
        if dna.mechanism_type in ["merge", "evolution"]:
            score += 10.0
        
        if dna.user_role_mapping and dna.user_role_mapping != "observer":
            score += 10.0
        
        return min(100.0, score)
    
    def _estimate_hierarchy_from_dna(self, dna: CreativeDNAV2) -> float:
        template = TemplateLibrary.get(dna.layout_template)
        if not template:
            return 50.0
        
        score = 70.0
        
        if dna.attention_goal == template.attention_goal:
            score += 20.0
        else:
            score -= 10.0
        
        return max(0.0, min(100.0, score))
    
    def _estimate_scrollstop_from_dna(self, dna: CreativeDNAV2) -> float:
        score = 45.0
        
        if dna.hook_type in ["transformation", "collection", "challenge"]:
            score += 20.0
        elif dna.hook_type in ["secret", "curiosity"]:
            score += 15.0
        
        if dna.reward_type in ["legendary_item", "transformation"]:
            score += 15.0
        
        if dna.layout_template in ["evolution_chain", "before_after"]:
            score += 10.0
        
        return min(100.0, score)
    
    def _calculate_total(self, dna: CreativeDNAV2) -> float:
        total = (
            dna.mechanism_visibility_score * WEIGHTS["mechanism_visibility"] +
            dna.reward_salience_score * WEIGHTS["reward_salience"] +
            dna.identity_projection_score * WEIGHTS["identity_projection"] +
            dna.visual_hierarchy_match * WEIGHTS["visual_hierarchy_match"] +
            dna.scroll_stop_score * WEIGHTS["scroll_stop"]
        )
        return round(max(0.0, min(100.0, total)), 1)
    
    def _check_reject(self, dna: CreativeDNAV2) -> Tuple[bool, List[str]]:
        reasons = []
        
        if not dna.layout_template or dna.layout_template == "unknown":
            reasons.append("No template_id assigned")
        
        if not dna.reward_type or dna.reward_type == "unknown":
            reasons.append("Reward type not specified")
        
        if dna.reward_salience_score < REJECT_THRESHOLDS["reward_salience_min"]:
            reasons.append(
                f"Reward salience too low: {dna.reward_salience_score:.1f} "
                f"(min {REJECT_THRESHOLDS['reward_salience_min']})"
            )
        
        if dna.mechanism_visibility_score < REJECT_THRESHOLDS["mechanism_visibility_min"]:
            reasons.append(
                f"Mechanism visibility too low: {dna.mechanism_visibility_score:.1f} "
                f"(min {REJECT_THRESHOLDS['mechanism_visibility_min']})"
            )
        
        if dna.identity_projection_score < REJECT_THRESHOLDS["identity_projection_min"]:
            reasons.append(
                f"Identity projection too low: {dna.identity_projection_score:.1f} "
                f"(min {REJECT_THRESHOLDS['identity_projection_min']})"
            )
        
        if dna.visual_hierarchy.level1 in ["character", "brand", "logo"]:
            reasons.append(f"Character/Brand is L1 visual: {dna.visual_hierarchy.level1}")
        
        is_rejected = len(reasons) > 0
        return is_rejected, reasons
    
    def _mechanism_breakdown(self, dna: CreativeDNAV2, va: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": dna.mechanism_visibility_score,
            "mechanism_type": dna.mechanism_type,
            "weight": WEIGHTS["mechanism_visibility"],
            "contribution": round(dna.mechanism_visibility_score * WEIGHTS["mechanism_visibility"], 1),
        }
    
    def _reward_breakdown(self, dna: CreativeDNAV2, va: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": dna.reward_salience_score,
            "reward_type": dna.reward_type,
            "is_l1": dna.visual_hierarchy.level1 in ["result_c", "final_form", "after_side", "reward"],
            "weight": WEIGHTS["reward_salience"],
            "contribution": round(dna.reward_salience_score * WEIGHTS["reward_salience"], 1),
        }
    
    def _identity_breakdown(self, dna: CreativeDNAV2, va: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": dna.identity_projection_score,
            "user_role": dna.user_role_mapping,
            "drives": dna.psychology_drive,
            "weight": WEIGHTS["identity_projection"],
            "contribution": round(dna.identity_projection_score * WEIGHTS["identity_projection"], 1),
        }
    
    def _hierarchy_breakdown(self, dna: CreativeDNAV2, va: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": dna.visual_hierarchy_match,
            "target_hierarchy": dna.visual_hierarchy.to_dict(),
            "weight": WEIGHTS["visual_hierarchy_match"],
            "contribution": round(dna.visual_hierarchy_match * WEIGHTS["visual_hierarchy_match"], 1),
        }
    
    def _scrollstop_breakdown(self, dna: CreativeDNAV2, va: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": dna.scroll_stop_score,
            "hook_type": dna.hook_type,
            "weight": WEIGHTS["scroll_stop"],
            "contribution": round(dna.scroll_stop_score * WEIGHTS["scroll_stop"], 1),
        }
