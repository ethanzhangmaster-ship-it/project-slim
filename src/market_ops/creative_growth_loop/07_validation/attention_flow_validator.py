"""Attention Flow Validator - 注意力流验证工具

用途：仅用于 validation tool（验证工具），不用于生成。

输出：
  - expected_attention_path: 预期的注意力路径
  - actual_saliency_path: 实际的显著性路径
  - mismatch_score: 不匹配度得分
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

_PKG = "market_ops.creative_growth_loop"

_dna_module = importlib.import_module(f"{_PKG}.03_gene.creative_dna_v2")
CreativeDNAV2 = _dna_module.CreativeDNAV2

_template_module = importlib.import_module(f"{_PKG}.03_gene.template_library")
TemplateLibrary = _template_module.TemplateLibrary
AdTemplate = _template_module.AdTemplate


@dataclass
class AttentionFlowResult:
    expected_path: List[str]
    actual_path: List[str]
    mismatch_score: float
    match_score: float
    issues: List[str]
    step_by_step_analysis: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_path": self.expected_path,
            "actual_path": self.actual_path,
            "mismatch_score": self.mismatch_score,
            "match_score": self.match_score,
            "issues": self.issues,
            "step_by_step_analysis": self.step_by_step_analysis,
        }


class AttentionFlowValidator:
    STANDARD_ATTENTION_FLOW = [
        "reward",
        "mechanism",
        "character_brand",
        "cta_ui",
    ]
    
    TEMPLATE_FLOWS = {
        "merge_formula": [
            "result_c",
            "item_a",
            "item_b",
            "plus_equals_signs",
            "character_hands",
            "cta_banner",
        ],
        "evolution_chain": [
            "final_form",
            "stage3",
            "stage2",
            "stage1",
            "arrows",
            "character",
            "cta_banner",
        ],
        "before_after": [
            "after_side",
            "before_side",
            "divider",
            "character",
            "cta_banner",
        ],
    }
    
    @classmethod
    def validate(cls, dna: CreativeDNAV2,
                 saliency_data: Dict[str, Any] = None) -> AttentionFlowResult:
        expected_path = cls._get_expected_path(dna)
        
        actual_path = cls._extract_actual_path(dna, saliency_data)
        
        match_score, mismatch_score, analysis = cls._compare_paths(
            expected_path, actual_path
        )
        
        issues = cls._identify_issues(expected_path, actual_path, match_score)
        
        return AttentionFlowResult(
            expected_path=expected_path,
            actual_path=actual_path,
            mismatch_score=mismatch_score,
            match_score=match_score,
            issues=issues,
            step_by_step_analysis=analysis,
        )
    
    @classmethod
    def _get_expected_path(cls, dna: CreativeDNAV2) -> List[str]:
        template = TemplateLibrary.get(dna.layout_template)
        if template and template.template_id in cls.TEMPLATE_FLOWS:
            return cls.TEMPLATE_FLOWS[template.template_id]
        
        return cls.STANDARD_ATTENTION_FLOW.copy()
    
    @classmethod
    def _extract_actual_path(cls, dna: CreativeDNAV2,
                              saliency_data: Dict[str, Any] = None) -> List[str]:
        if saliency_data and "saliency_rank" in saliency_data:
            return saliency_data["saliency_rank"]
        
        if saliency_data and "regions_by_saliency" in saliency_data:
            return [r["name"] for r in saliency_data["regions_by_saliency"]]
        
        template = TemplateLibrary.get(dna.layout_template)
        if template:
            sorted_regions = sorted(
                template.regions,
                key=lambda r: r.visual_weight,
                reverse=True
            )
            return [r.name for r in sorted_regions]
        
        return cls.STANDARD_ATTENTION_FLOW.copy()
    
    @classmethod
    def _compare_paths(cls, expected: List[str], 
                        actual: List[str]) -> Tuple[float, float, List[Dict[str, Any]]]:
        analysis = []
        total_score = 0.0
        max_score = 0.0
        
        for i, expected_element in enumerate(expected):
            max_score += 1.0
            
            if i < len(actual):
                actual_element = actual[i]
                is_match = cls._elements_match(expected_element, actual_element)
                
                if is_match:
                    step_score = 1.0
                else:
                    position = cls._find_position(actual_element, expected)
                    if position is not None:
                        distance = abs(position - i)
                        step_score = max(0.0, 1.0 - distance * 0.2)
                    else:
                        step_score = 0.0
                
                total_score += step_score
                analysis.append({
                    "step": i + 1,
                    "expected": expected_element,
                    "actual": actual_element,
                    "score": step_score,
                    "is_correct_position": is_match,
                })
            else:
                analysis.append({
                    "step": i + 1,
                    "expected": expected_element,
                    "actual": None,
                    "score": 0.0,
                    "is_correct_position": False,
                    "note": "Missing from actual path",
                })
        
        if max_score > 0:
            match_score = round((total_score / max_score) * 100, 1)
        else:
            match_score = 0.0
        
        mismatch_score = round(100.0 - match_score, 1)
        
        return match_score, mismatch_score, analysis
    
    @classmethod
    def _elements_match(cls, expected: str, actual: str) -> bool:
        expected_lower = expected.lower()
        actual_lower = actual.lower()
        
        if expected_lower == actual_lower:
            return True
        
        reward_aliases = ["reward", "result", "final", "after", "legendary", "merged", "evolved"]
        mechanism_aliases = ["mechanism", "merge", "evolution", "transform", "process", "formula", "chain", "progression"]
        character_aliases = ["character", "witch", "mascot", "brand", "avatar", "hands"]
        cta_aliases = ["cta", "ui", "button", "banner", "text", "logo", "badge"]
        
        def in_category(elem: str, aliases: List[str]) -> bool:
            return any(a in elem for a in aliases)
        
        categories = [reward_aliases, mechanism_aliases, character_aliases, cta_aliases]
        
        for cat in categories:
            if in_category(expected_lower, cat) and in_category(actual_lower, cat):
                return True
        
        return False
    
    @classmethod
    def _find_position(cls, element: str, path: List[str]) -> Optional[int]:
        for i, p in enumerate(path):
            if cls._elements_match(element, p):
                return i
        return None
    
    @classmethod
    def _identify_issues(cls, expected: List[str], actual: List[str],
                         match_score: float) -> List[str]:
        issues = []
        
        if match_score < 70.0:
            issues.append(f"Attention flow mismatch score high: {100 - match_score:.1f}%")
        
        if expected and actual:
            first_expected = expected[0].lower()
            first_actual = actual[0].lower()
            
            reward_keywords = ["reward", "result", "final", "after", "legendary"]
            is_first_reward_expected = any(k in first_expected for k in reward_keywords)
            is_first_reward_actual = any(k in first_actual for k in reward_keywords)
            
            if is_first_reward_expected and not is_first_reward_actual:
                issues.append("First attention point is not reward element")
            
            char_keywords = ["character", "witch", "mascot", "brand", "avatar"]
            if any(k in first_actual for k in char_keywords):
                issues.append("Character captures first attention (should be reward)")
        
        if len(actual) < len(expected):
            missing = len(expected) - len(actual)
            issues.append(f"Missing {missing} attention points from expected path")
        
        return issues
    
    @classmethod
    def get_expected_flow_for_template(cls, template_id: str) -> Optional[List[str]]:
        return cls.TEMPLATE_FLOWS.get(template_id)
    
    @classmethod
    def calculate_attention_weight(cls, template_id: str, 
                                    region_name: str) -> float:
        flow = cls.TEMPLATE_FLOWS.get(template_id)
        if not flow:
            return 0.5
        
        for i, name in enumerate(flow):
            if cls._elements_match(region_name, name):
                base_weight = 1.0 - (i * 0.15)
                return max(0.1, base_weight)
        
        return 0.3
