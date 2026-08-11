"""Creative Intelligence V4 - Inference-centric Creative Engine

将系统从 Image-centric learning → Inference-centric creative system

核心引擎，整合：
  - Creative DNA V2（结构化创意DNA）
  - Template System（强约束模板系统）
  - Visual Hierarchy Validator（视觉层级验证）
  - Attention Flow Validator（注意力流验证）
  - Creative Scoring V2（评分系统V2）
  - Prompt Builder V2（模板驱动的Prompt生成）

系统目标：
  generate creatives that maximize inference completion within 1 second
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

_template_module = importlib.import_module(f"{_PKG}.03_gene.template_library")
TemplateLibrary = _template_module.TemplateLibrary
AdTemplate = _template_module.AdTemplate

_extractor_module = importlib.import_module(f"{_PKG}.03_gene.gene_extractor_v2")
GeneExtractorV2 = _extractor_module.GeneExtractorV2
ExtractionResult = _extractor_module.ExtractionResult

_prompt_module = importlib.import_module(f"{_PKG}.05_prompt.prompt_builder_v2")
PromptBuilderV2 = _prompt_module.PromptBuilderV2
TemplatePrompt = _prompt_module.TemplatePrompt

_hierarchy_module = importlib.import_module(f"{_PKG}.07_validation.visual_hierarchy_validator")
VisualHierarchyValidator = _hierarchy_module.VisualHierarchyValidator
HierarchyValidationResult = _hierarchy_module.HierarchyValidationResult

_attention_module = importlib.import_module(f"{_PKG}.07_validation.attention_flow_validator")
AttentionFlowValidator = _attention_module.AttentionFlowValidator
AttentionFlowResult = _attention_module.AttentionFlowResult

_scoring_module = importlib.import_module(f"{_PKG}.08_scoring.creative_scoring_v2")
CreativeScoringV2 = _scoring_module.CreativeScoringV2


@dataclass
class CreativeValidationReport:
    dna: CreativeDNAV2
    hierarchy_validation: HierarchyValidationResult
    attention_flow: AttentionFlowResult
    scoring_details: Dict[str, Any]
    overall_passed: bool
    overall_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dna": self.dna.to_dict(),
            "hierarchy_validation": self.hierarchy_validation.to_dict(),
            "attention_flow": self.attention_flow.to_dict(),
            "scoring_details": self.scoring_details,
            "overall_passed": self.overall_passed,
            "overall_score": self.overall_score,
        }


@dataclass
class CreativeGenerationResult:
    dna: CreativeDNAV2
    prompts: List[TemplatePrompt]
    validation_report: CreativeValidationReport
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dna": self.dna.to_dict(),
            "prompts": [p.to_dict() for p in self.prompts],
            "validation_report": self.validation_report.to_dict(),
        }


class InferenceCreativeEngine:
    """推理中心创意引擎 - Decision Inference System
    
    系统目标不是 generate better images
    而是 generate creatives that maximize inference completion within 1 second
    """
    
    SYSTEM_GOAL = "generate creatives that maximize inference completion within 1 second"
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/v4"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.gene_extractor = GeneExtractorV2(
            output_dir=str(self.output_dir / "dna_memory")
        )
        self.prompt_builder = PromptBuilderV2(
            output_dir=str(self.output_dir / "prompts")
        )
        self.scoring = CreativeScoringV2()
    
    def analyze_and_score_image(self, image_path: str, 
                                 creative_id: str = None) -> CreativeValidationReport:
        extraction = self.gene_extractor.extract_dna(image_path, creative_id)
        dna = extraction.dna
        
        scored_dna, details = self.scoring.score_with_details(
            dna, image_path, extraction.raw_analysis
        )
        
        hierarchy_result = VisualHierarchyValidator.validate(
            scored_dna, extraction.raw_analysis
        )
        
        attention_result = AttentionFlowValidator.validate(
            scored_dna, extraction.raw_analysis
        )
        
        overall_passed = (
            not scored_dna.is_rejected 
            and hierarchy_result.passed
        )
        
        report = CreativeValidationReport(
            dna=scored_dna,
            hierarchy_validation=hierarchy_result,
            attention_flow=attention_result,
            scoring_details=details,
            overall_passed=overall_passed,
            overall_score=scored_dna.total_score,
        )
        
        self._save_report(report, scored_dna.source_creative_id)
        return report
    
    def generate_creatives(self, template_id: str = None,
                           mechanism_type: str = None,
                           reward_type: str = None,
                           hook_type: str = None,
                           count: int = 5) -> CreativeGenerationResult:
        if template_id is None:
            template_id = "merge_formula"
        
        if not TemplateLibrary.validate_template_id(template_id):
            raise ValueError(f"Invalid template_id: {template_id}")
        
        template = TemplateLibrary.get(template_id)
        
        dna = CreativeDNAV2(
            dna_id=f"dna_v4_{template_id}_{self._gen_id()}",
            mechanism_type=mechanism_type or template.mechanism_type,
            reward_type=reward_type or "transformation",
            hook_type=hook_type or "curiosity",
            layout_template=template_id,
            attention_goal=template.attention_goal,
            psychology_drive=template.psychology_drives.copy(),
            visual_hierarchy=VisualHierarchySpec(**template.visual_hierarchy.to_dict()),
            user_role_mapping=self._get_user_role(mechanism_type or template.mechanism_type),
        )
        
        scored_dna, scoring_details = self.scoring.score_with_details(dna)
        
        prompts = self.prompt_builder.build_prompts_from_dna(scored_dna, count)
        
        hierarchy_result = VisualHierarchyValidator.validate(scored_dna)
        attention_result = AttentionFlowValidator.validate(scored_dna)
        
        overall_passed = (
            not scored_dna.is_rejected
            and hierarchy_result.passed
        )
        
        report = CreativeValidationReport(
            dna=scored_dna,
            hierarchy_validation=hierarchy_result,
            attention_flow=attention_result,
            scoring_details=scoring_details,
            overall_passed=overall_passed,
            overall_score=scored_dna.total_score,
        )
        
        result = CreativeGenerationResult(
            dna=scored_dna,
            prompts=prompts,
            validation_report=report,
        )
        
        self._save_generation_result(result)
        return result
    
    def generate_batch(self, template_ids: List[str] = None,
                       count_per_template: int = 3) -> List[CreativeGenerationResult]:
        if template_ids is None:
            template_ids = TemplateLibrary.list_template_ids()
        
        results = []
        for template_id in template_ids:
            try:
                result = self.generate_creatives(
                    template_id=template_id,
                    count=count_per_template,
                )
                results.append(result)
            except Exception as e:
                print(f"Failed to generate for template {template_id}: {e}")
        
        return results
    
    def validate_dna(self, dna: CreativeDNAV2) -> CreativeValidationReport:
        template_ok, template_issues = VisualHierarchyValidator.validate_template_compliance(dna)
        
        hierarchy_result = VisualHierarchyValidator.validate(dna)
        attention_result = AttentionFlowValidator.validate(dna)
        
        scored_dna, scoring_details = self.scoring.score_with_details(dna)
        
        all_issues = template_issues + hierarchy_result.issues
        overall_passed = (
            template_ok
            and hierarchy_result.passed
            and not scored_dna.is_rejected
        )
        
        report = CreativeValidationReport(
            dna=scored_dna,
            hierarchy_validation=hierarchy_result,
            attention_flow=attention_result,
            scoring_details=scoring_details,
            overall_passed=overall_passed,
            overall_score=scored_dna.total_score,
        )
        
        return report
    
    def _get_user_role(self, mechanism_type: str) -> str:
        role_map = {
            "merge": "player_who_merges",
            "evolution": "player_who_evolves",
            "collection": "collector",
            "transformation": "transformer",
            "progression_chain": "progression_player",
        }
        return role_map.get(mechanism_type, "player_who_merges")
    
    def _gen_id(self) -> str:
        import uuid
        return uuid.uuid4().hex[:8]
    
    def _save_report(self, report: CreativeValidationReport, creative_id: str) -> Path:
        output_path = self.output_dir / "reports" / f"{creative_id}_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def _save_generation_result(self, result: CreativeGenerationResult) -> Path:
        output_path = self.output_dir / "generations" / f"{result.dna.dna_id}_generation.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def get_system_spec(self) -> Dict[str, Any]:
        templates = TemplateLibrary.get_all()
        
        return {
            "system_name": "Creative Intelligence V4",
            "system_goal": self.SYSTEM_GOAL,
            "paradigm_shift": "Image-centric → Inference-centric",
            "core_principles": [
                "Mechanism First (玩法机制优先)",
                "Reward Visibility (奖励可视化)",
                "Identity Projection (代入感)",
            ],
            "templates": [
                {
                    "template_id": t.template_id,
                    "template_name": t.template_name,
                    "mechanism_type": t.mechanism_type,
                    "attention_goal": t.attention_goal,
                    "visual_hierarchy": t.visual_hierarchy.to_dict(),
                    "psychology_drives": t.psychology_drives,
                }
                for t in templates
            ],
            "scoring_weights": {
                "mechanism_visibility": 0.35,
                "reward_salience": 0.25,
                "identity_projection": 0.20,
                "visual_hierarchy_match": 0.10,
                "scroll_stop": 0.10,
            },
            "reject_conditions": [
                "reward not clear",
                "mechanism not understandable (>1.5s)",
                "character occupies visual center (L1)",
                "no template_id",
                "identity projection < 60",
            ],
        }
