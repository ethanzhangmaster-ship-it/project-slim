"""Layout Compiler - 布局编译器

核心：将 Creative DNA + Template 编译为 Layout AST（可执行的视觉结构约束）

这不是生成系统，而是编译系统：
  输入：创意意图（Creative DNA）
  输出：可执行的视觉结构约束（Layout AST + Render Constraints）

系统定义：
  This is a creative inference compilation system 
  that translates user psychological drivers 
  into structured visual constraints.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from .layout_ast import (
    LayoutAST,
    LayoutNode,
    VisualBudgetAllocation,
    HardConstraints,
)
from .template_compiler import TemplateCompilerLibrary, TemplateCompilationRule
from .visual_budget import VisualBudgetSystem
from .inference_model import ClickInferenceModel, InferenceResult
from .render_constraint_engine import RenderConstraintEngine, RenderConstraints


@dataclass
class CompilationResult:
    ast: LayoutAST
    render_constraints: RenderConstraints
    inference_result: InferenceResult
    compilation_errors: List[str]
    compilation_warnings: List[str]
    is_valid: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ast": self.ast.to_dict(),
            "render_constraints": self.render_constraints.to_dict(),
            "inference_result": self.inference_result.to_dict(),
            "compilation_errors": self.compilation_errors,
            "compilation_warnings": self.compilation_warnings,
            "is_valid": self.is_valid,
        }


class LayoutCompiler:
    """布局编译器 - 将创意意图编译为视觉结构约束
    
    编译流程：
    1. Template Selection → 选择模板编译规则
    2. AST Generation → 生成 Layout AST 节点
    3. Budget Allocation → 分配视觉预算
    4. Constraint Generation → 生成空间约束
    5. Inference Validation → 推理验证（点击概率）
    6. Render Compilation → 渲染约束编译
    """
    
    SYSTEM_NAME = "Creative Inference Compilation System"
    SYSTEM_DEFINITION = (
        "This is not a generative image system. "
        "This is a creative inference compilation system "
        "that translates user psychological drivers "
        "into structured visual constraints."
    )
    
    def __init__(self):
        pass
    
    def compile(self, template_id: str,
                dna_context: Dict[str, Any] = None,
                style_hints: Dict[str, Any] = None) -> CompilationResult:
        errors = []
        warnings = []
        
        if not template_id:
            errors.append("No template_id provided")
            return self._error_result(errors)
        
        if not TemplateCompilerLibrary.get_rule(template_id):
            errors.append(f"Unknown template_id: {template_id}")
            return self._error_result(errors)
        
        ast = TemplateCompilerLibrary.compile_template(template_id, dna_context)
        ast.ast_id = f"ast_{template_id}_{self._gen_id()}"
        
        ast_ok, ast_issues = ast.validate()
        if not ast_ok:
            errors.extend(ast_issues)
        
        budget_ok, budget_issues = VisualBudgetSystem.validate_budget_distribution(
            ast.visual_budget.allocation
        )
        if not budget_ok:
            warnings.extend(budget_issues)
        
        inference_result = ClickInferenceModel.infer_click_probability(ast)
        
        if inference_result.confusion_risk > 0.5:
            warnings.append(
                f"High confusion risk: {inference_result.confusion_risk:.2f}"
            )
        
        if inference_result.click_probability_proxy < 0.01:
            warnings.append(
                f"Low click probability proxy: {inference_result.click_probability_proxy:.4f}"
            )
        
        render_constraints = RenderConstraintEngine.compile_constraints(ast, style_hints)
        
        is_valid = len(errors) == 0
        
        return CompilationResult(
            ast=ast,
            render_constraints=render_constraints,
            inference_result=inference_result,
            compilation_errors=errors,
            compilation_warnings=warnings,
            is_valid=is_valid,
        )
    
    def compile_from_dna(self, dna: Any,
                          style_hints: Dict[str, Any] = None) -> CompilationResult:
        template_id = getattr(dna, 'layout_template', '')
        if not template_id:
            template_id = getattr(dna, 'template_id', 'merge_formula')
        
        dna_context = {
            "mechanism_type": getattr(dna, 'mechanism_type', ''),
            "reward_type": getattr(dna, 'reward_type', ''),
            "hook_type": getattr(dna, 'hook_type', ''),
            "attention_goal": getattr(dna, 'attention_goal', 'reward_first'),
            "psychology_drive": getattr(dna, 'psychology_drive', []),
            "dna_id": getattr(dna, 'dna_id', ''),
        }
        
        return self.compile(template_id, dna_context, style_hints)
    
    def compile_batch(self, template_ids: List[str],
                       style_hints: Dict[str, Any] = None) -> List[CompilationResult]:
        results = []
        for tid in template_ids:
            try:
                result = self.compile(tid, style_hints=style_hints)
                results.append(result)
            except Exception as e:
                print(f"Compilation failed for {tid}: {e}")
        return results
    
    def _error_result(self, errors: List[str]) -> CompilationResult:
        from .layout_ast import LayoutAST
        from .inference_model import InferenceResult
        from .render_constraint_engine import RenderConstraints
        
        return CompilationResult(
            ast=LayoutAST(),
            render_constraints=RenderConstraints(),
            inference_result=InferenceResult(
                mechanism_clarity=0.0,
                reward_vividness=0.0,
                identity_projection=0.0,
                friction=1.0,
                click_probability_proxy=0.0,
                mechanism_breakdown={},
                reward_breakdown={},
                identity_breakdown={},
                friction_breakdown={},
                confusion_risk=1.0,
                inference_chain_probability=[],
            ),
            compilation_errors=errors,
            compilation_warnings=[],
            is_valid=False,
        )
    
    def _gen_id(self) -> str:
        return uuid.uuid4().hex[:8]
    
    def get_system_spec(self) -> Dict[str, Any]:
        return {
            "system_name": self.SYSTEM_NAME,
            "system_definition": self.SYSTEM_DEFINITION,
            "paradigm": "inference-driven layout compiler",
            "compilation_pipeline": [
                "template_selection",
                "ast_generation",
                "budget_allocation",
                "constraint_generation",
                "inference_validation",
                "render_compilation",
            ],
            "available_templates": TemplateCompilerLibrary.list_rules(),
            "inference_formula": (
                "P(click) = P(understand_mechanism) "
                "* P(imagine_reward) "
                "* P(project_self) "
                "* P(low_friction)"
            ),
        }
