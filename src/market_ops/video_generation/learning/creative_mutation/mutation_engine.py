"""Mutation Engine - 变异引擎"""
from dataclasses import dataclass
from typing import Dict, List, Any

from .mutation_strategy import MutationStrategy, MutationOption
from .blueprint_mutator import BlueprintMutator, BlueprintVariant


@dataclass
class MutationResult:
    """变异结果"""
    parent_id: str = ""
    variants: List[BlueprintVariant] = None
    strategy: str = ""
    mutation_count: int = 0
    
    def __post_init__(self):
        if self.variants is None:
            self.variants = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "variants": [v.to_dict() for v in self.variants],
            "strategy": self.strategy,
            "mutation_count": self.mutation_count,
        }


class MutationEngine:
    """变异引擎"""
    
    def __init__(self):
        self.strategy = MutationStrategy()
        self.mutator = BlueprintMutator()
    
    def mutate(
        self,
        winner_dna: Dict[str, str],
        count: int = 5,
        parent_id: str = "",
        strategy: str = "diverse",
    ) -> MutationResult:
        """根据赢家 DNA 生成下一代创意
        
        Args:
            winner_dna: 赢家 DNA
            count: 生成变体数量
            parent_id: 父创意 ID
            strategy: 变异策略
        
        Returns:
            MutationResult with variants
        """
        # 获取变异选项
        options = self.strategy.get_mutation_options(winner_dna)
        
        # 生成变体
        variants = []
        
        # 策略 A: 单元素变异
        for i in range(min(count - 2, len(options))):
            option = options[i]
            mutation = [{"element": option.element, "new_value": option.new_value}]
            variant = self.mutator.mutate(winner_dna, mutation, parent_id, f"single_{i}")
            variants.append(variant)
        
        # 策略 B: 双元素变异（保持多样性）
        if len(options) >= 2 and len(variants) < count:
            double_mutation = [
                {"element": options[0].element, "new_value": options[0].new_value},
                {"element": options[1].element, "new_value": options[1].new_value},
            ]
            variant = self.mutator.mutate(winner_dna, double_mutation, parent_id, "double")
            variants.append(variant)
        
        # 策略 C: 保留核心，变更次要元素
        if len(options) >= 3 and len(variants) < count:
            minor_element = [o for o in options if o.impact < 0.5]
            if minor_element:
                mutation = [{"element": minor_element[0].element, "new_value": minor_element[0].new_value}]
                variant = self.mutator.mutate(winner_dna, mutation, parent_id, "minor_change")
                variants.append(variant)
        
        return MutationResult(
            parent_id=parent_id,
            variants=variants[:count],
            strategy=strategy,
            mutation_count=len(variants),
        )
    
    def mutate_pattern(self, winner_pattern: Dict[str, Any], count: int = 5) -> MutationResult:
        """根据赢家模式生成变异"""
        dna = winner_pattern.get("dna", {})
        parent_id = winner_pattern.get("winner_pattern_id", "")
        
        return self.mutate(dna, count, parent_id)
    
    def mutate_demo(self) -> MutationResult:
        """生成演示数据"""
        winner_dna = {
            "hook": "fast_action",
            "camera": "close_up",
            "lighting": "warm",
            "emotion": "surprise",
        }
        
        return self.mutate(winner_dna, count=5, parent_id="pattern_001")
