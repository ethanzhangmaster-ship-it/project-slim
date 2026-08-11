"""E11.4.1 — Vision Decision Models。

VisionDecision:        视觉决策（keep/mutate/remove）
DecisionRule:          单条决策规则
MutationInstruction:   突变指令（连接 Mutation Engine）
ExperimentHypothesis:  实验假设（连接 V5 Evolution Layer）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DecisionRule:
    """单条决策规则。

    Attributes:
        rule_id:       规则 ID
        action:        决策动作 (keep/mutate/remove)
        pattern_name:  关联的视觉模式名
        reason:        决策理由
        confidence:    置信度 (0-1)
        priority:      优先级 (0=low, 1=high)
    """

    rule_id: str = ""
    action: str = ""  # keep / mutate / remove
    pattern_name: str = ""
    reason: str = ""
    confidence: float = 0.0
    priority: float = 0.0

    def __post_init__(self) -> None:
        if not self.rule_id:
            self.rule_id = f"dr_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action": self.action,
            "pattern_name": self.pattern_name,
            "reason": self.reason,
            "confidence": self.confidence,
            "priority": self.priority,
        }

    def __repr__(self) -> str:
        return (
            f"DecisionRule({self.action}:{self.pattern_name}, "
            f"conf={self.confidence:.2f})"
        )


@dataclass
class MutationInstruction:
    """突变指令 — 连接 Mutation Engine 的桥梁。

    Attributes:
        instruction_id:  指令 ID
        target_gene:     目标基因名 (hook_contrast/color_palette/object_count/...)
        operator:        操作符 (increase/decrease/replace/set)
        magnitude:       变化幅度 (0-1)
        current_value:   当前值
        target_value:    目标值
        source_pattern:  来源视觉模式
        description:     文字描述
    """

    instruction_id: str = ""
    target_gene: str = ""
    operator: str = ""  # increase / decrease / replace / set
    magnitude: float = 0.0
    current_value: float = 0.0
    target_value: float = 0.0
    source_pattern: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.instruction_id:
            self.instruction_id = f"mi_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction_id": self.instruction_id,
            "target_gene": self.target_gene,
            "operator": self.operator,
            "magnitude": self.magnitude,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "source_pattern": self.source_pattern,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"MutationInstruction({self.target_gene}: "
            f"{self.operator} {self.magnitude:.0%})"
        )


@dataclass
class ExperimentHypothesis:
    """实验假设 — 连接 V5 Evolution Layer。

    Attributes:
        hypothesis_id:  假设 ID
        statement:      假设陈述
        variables:      实验变量
        expected_metric: 预期影响指标
        expected_direction: 预期变化方向 (increase/decrease)
        expected_magnitude: 预期变化幅度
        source_insight_id: 来源 VisionInsight
        confidence:     置信度
        created_at:     创建时间
    """

    hypothesis_id: str = ""
    statement: str = ""
    variables: list[str] = field(default_factory=list)
    expected_metric: str = ""
    expected_direction: str = "increase"
    expected_magnitude: float = 0.0
    source_insight_id: str = ""
    confidence: float = 0.0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            self.hypothesis_id = f"eh_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "variables": self.variables,
            "expected_metric": self.expected_metric,
            "expected_direction": self.expected_direction,
            "expected_magnitude": self.expected_magnitude,
            "source_insight_id": self.source_insight_id,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"ExperimentHypothesis({self.expected_metric}: "
            f"{self.expected_direction}, "
            f"conf={self.confidence:.2f})"
        )


@dataclass
class VisionDecision:
    """视觉决策 — 核心决策输出。

    Attributes:
        decision_id:        决策 ID
        creative_asset_id:  素材 ID
        confidence:         总体置信度
        rules:              决策规则列表
        keep_patterns:      保留的视觉模式
        mutate_patterns:    需要变异的模式
        remove_patterns:    需要移除的模式
        mutation_instructions: 突变指令列表
        hypotheses:         实验假设列表
        summary:            决策总结
        created_at:         创建时间
    """

    decision_id: str = ""
    creative_asset_id: str = ""
    confidence: float = 0.0

    rules: list[DecisionRule] = field(default_factory=list)
    keep_patterns: list[str] = field(default_factory=list)
    mutate_patterns: list[str] = field(default_factory=list)
    remove_patterns: list[str] = field(default_factory=list)

    mutation_instructions: list[MutationInstruction] = field(default_factory=list)
    hypotheses: list[ExperimentHypothesis] = field(default_factory=list)

    summary: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"vd_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def total_rules(self) -> int:
        return len(self.rules)

    @property
    def action_summary(self) -> dict[str, int]:
        return {
            "keep": len(self.keep_patterns),
            "mutate": len(self.mutate_patterns),
            "remove": len(self.remove_patterns),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "creative_asset_id": self.creative_asset_id,
            "confidence": self.confidence,
            "rules": [r.to_dict() for r in self.rules],
            "keep_patterns": self.keep_patterns,
            "mutate_patterns": self.mutate_patterns,
            "remove_patterns": self.remove_patterns,
            "mutation_instructions": [mi.to_dict() for mi in self.mutation_instructions],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "summary": self.summary,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"VisionDecision(asset={self.creative_asset_id}, "
            f"keep={len(self.keep_patterns)}, "
            f"mutate={len(self.mutate_patterns)}, "
            f"conf={self.confidence:.2f})"
        )