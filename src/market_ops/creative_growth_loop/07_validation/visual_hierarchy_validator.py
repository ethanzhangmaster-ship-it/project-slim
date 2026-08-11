"""Visual Hierarchy Validator - 视觉层级强制规则验证器

强制规则：
  L1 = Reward
  L2 = Mechanism
  L3 = Brand / Character
  L4 = UI / CTA

校验：
  如果 Character == L1 → reject
  如果 Reward != L1 → reject
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

_PKG = "market_ops.creative_growth_loop"

_dna_module = importlib.import_module(f"{_PKG}.03_gene.creative_dna_v2")
CreativeDNAV2 = _dna_module.CreativeDNAV2
VisualHierarchySpec = _dna_module.VisualHierarchySpec

_template_module = importlib.import_module(f"{_PKG}.03_gene.template_library")
TemplateLibrary = _template_module.TemplateLibrary
AdTemplate = _template_module.AdTemplate


REWARD_ELEMENTS = {
    "result_c", "final_form", "after_side", "reward", "legendary_item",
    "transformation_result", "merged_creature", "evolved_form",
}

MECHANISM_ELEMENTS = {
    "merge_process", "evolution_path", "transformation", "mechanism",
    "merge_formula", "progression_chain", "before_after_divider",
}

CHARACTER_ELEMENTS = {
    "character", "character_hands", "witch", "brand_character",
    "mascot", "avatar",
}

UI_CTA_ELEMENTS = {
    "cta_banner", "ui", "button", "text_overlay", "logo", "badge",
}


@dataclass
class HierarchyValidationResult:
    passed: bool
    issues: List[str]
    hierarchy_score: float
    expected_hierarchy: Dict[str, str]
    actual_hierarchy: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "hierarchy_score": self.hierarchy_score,
            "expected_hierarchy": self.expected_hierarchy,
            "actual_hierarchy": self.actual_hierarchy,
        }


class VisualHierarchyValidator:
    STANDARD_L1 = "reward"
    STANDARD_L2 = "mechanism"
    STANDARD_L3 = "brand_character"
    STANDARD_L4 = "ui_cta"
    
    @classmethod
    def validate(cls, dna: CreativeDNAV2, 
                 visual_analysis: Dict[str, Any] = None) -> HierarchyValidationResult:
        issues = []
        
        template = TemplateLibrary.get(dna.layout_template)
        expected = cls._get_expected_hierarchy(dna, template)
        
        actual = cls._extract_actual_hierarchy(dna, visual_analysis)
        
        if actual["level1"] in CHARACTER_ELEMENTS:
            issues.append(f"Character occupies L1: {actual['level1']}")
        
        is_l1_reward = (
            actual["level1"] in REWARD_ELEMENTS or
            "reward" in actual["level1"].lower() or
            "result" in actual["level1"].lower() or
            "final" in actual["level1"].lower() or
            "after" in actual["level1"].lower()
        )
        if not is_l1_reward and actual["level1"]:
            issues.append(f"Reward is not L1. L1 is: {actual['level1']}")
        
        is_l2_mechanism = (
            actual["level2"] in MECHANISM_ELEMENTS or
            "merge" in actual["level2"].lower() or
            "evolut" in actual["level2"].lower() or
            "transform" in actual["level2"].lower() or
            "mechanism" in actual["level2"].lower()
        )
        if not is_l2_mechanism and actual["level2"]:
            issues.append(f"Mechanism may not be L2. L2 is: {actual['level2']}")
        
        hierarchy_score = cls._calculate_hierarchy_score(expected, actual, template)
        
        passed = len([i for i in issues if "occupies L1" in i or "not L1" in i]) == 0
        
        return HierarchyValidationResult(
            passed=passed,
            issues=issues,
            hierarchy_score=hierarchy_score,
            expected_hierarchy=expected,
            actual_hierarchy=actual,
        )
    
    @classmethod
    def _get_expected_hierarchy(cls, dna: CreativeDNAV2, 
                                template: Optional[AdTemplate]) -> Dict[str, str]:
        if template:
            return template.visual_hierarchy.to_dict()
        
        return {
            "level1": cls.STANDARD_L1,
            "level2": cls.STANDARD_L2,
            "level3": cls.STANDARD_L3,
            "level4": cls.STANDARD_L4,
        }
    
    @classmethod
    def _extract_actual_hierarchy(cls, dna: CreativeDNAV2,
                                  visual_analysis: Dict[str, Any] = None) -> Dict[str, str]:
        if visual_analysis and "visual_hierarchy" in visual_analysis:
            vh = visual_analysis["visual_hierarchy"]
            return {
                "level1": vh.get("level1", ""),
                "level2": vh.get("level2", ""),
                "level3": vh.get("level3", ""),
                "level4": vh.get("level4", ""),
            }
        
        return dna.visual_hierarchy.to_dict()
    
    @classmethod
    def _calculate_hierarchy_score(cls, expected: Dict[str, str], 
                                   actual: Dict[str, str],
                                   template: Optional[AdTemplate]) -> float:
        if not template:
            return 60.0
        
        score = 50.0
        
        actual_l1 = actual.get("level1", "").lower()
        expected_l1 = expected.get("level1", "").lower()
        
        if actual_l1 and expected_l1:
            if actual_l1 == expected_l1 or expected_l1 in actual_l1:
                score += 30.0
            elif any(r in actual_l1 for r in ["result", "final", "after", "reward", "merge"]):
                score += 15.0
            else:
                score -= 20.0
        
        actual_l2 = actual.get("level2", "").lower()
        expected_l2 = expected.get("level2", "").lower()
        
        if actual_l2 and expected_l2:
            if actual_l2 == expected_l2 or expected_l2 in actual_l2:
                score += 15.0
            elif any(m in actual_l2 for m in ["merge", "evolut", "transform", "mechanism"]):
                score += 5.0
        
        return max(0.0, min(100.0, score))
    
    @classmethod
    def validate_template_compliance(cls, dna: CreativeDNAV2) -> Tuple[bool, List[str]]:
        issues = []
        
        if not dna.layout_template:
            issues.append("No template_id assigned")
        
        if dna.layout_template and not TemplateLibrary.validate_template_id(dna.layout_template):
            issues.append(f"Invalid template_id: {dna.layout_template}")
        
        template = TemplateLibrary.get(dna.layout_template)
        if template:
            if dna.mechanism_type and dna.mechanism_type != template.mechanism_type:
                issues.append(
                    f"Mechanism type mismatch: DNA has {dna.mechanism_type}, "
                    f"template expects {template.mechanism_type}"
                )
        
        passed = len(issues) == 0
        return passed, issues
