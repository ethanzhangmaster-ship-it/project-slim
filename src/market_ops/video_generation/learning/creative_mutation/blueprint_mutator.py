"""Blueprint Mutator - Blueprint 变异器"""
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class BlueprintVariant:
    """Blueprint 变体"""
    variant_id: str = ""
    parent_id: str = ""
    dna: Dict[str, str] = None
    mutations: List[Dict[str, Any]] = None
    mutation_strategy: str = ""
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.dna is None:
            self.dna = {}
        if self.mutations is None:
            self.mutations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "parent_id": self.parent_id,
            "dna": self.dna,
            "mutations": self.mutations,
            "mutation_strategy": self.mutation_strategy,
            "confidence": round(self.confidence, 2),
        }


class BlueprintMutator:
    """Blueprint 变异器"""
    
    def __init__(self):
        self._variant_counter = 0
    
    def mutate(
        self,
        parent_dna: Dict[str, str],
        mutations: List[Dict[str, Any]],
        parent_id: str = "",
        strategy: str = "",
    ) -> BlueprintVariant:
        """变异生成新 Blueprint"""
        self._variant_counter += 1
        variant_id = f"variant_{self._variant_counter:04d}"
        
        # 复制原始 DNA
        new_dna = parent_dna.copy()
        
        # 应用变异
        mutation_records = []
        for mutation in mutations:
            element = mutation.get("element", "")
            new_value = mutation.get("new_value", "")
            
            if element in new_dna:
                mutation_records.append({
                    "element": element,
                    "from": new_dna[element],
                    "to": new_value,
                })
                new_dna[element] = new_value
        
        # 计算置信度（保留的元素越多，置信度越高）
        preserved_elements = len(parent_dna) - len(mutation_records)
        confidence = max(0.5, preserved_elements / len(parent_dna))
        
        return BlueprintVariant(
            variant_id=variant_id,
            parent_id=parent_id,
            dna=new_dna,
            mutations=mutation_records,
            mutation_strategy=strategy,
            confidence=confidence,
        )
    
    def generate_variants(
        self,
        parent_dna: Dict[str, str],
        mutation_options: List[Dict[str, Any]],
        parent_id: str = "",
        strategy: str = "diverse",
    ) -> List[BlueprintVariant]:
        """生成多个变体"""
        variants = []
        
        # 策略 A: 相同 hook + 不同 camera
        if strategy == "diverse":
            # 生成多种组合
            for i, option in enumerate(mutation_options[:3]):
                mutations = [option]
                variant = self.mutate(parent_dna, mutations, parent_id, f"{strategy}_option_{i}")
                variants.append(variant)
            
            # 生成双重变异
            if len(mutation_options) >= 2:
                double_mutation = [mutation_options[0], mutation_options[1]]
                variant = self.mutate(parent_dna, double_mutation, parent_id, f"{strategy}_double")
                variants.append(variant)
        
        return variants
    
    def mutate_demo(self) -> List[BlueprintVariant]:
        """生成演示数据"""
        parent_dna = {
            "hook": "treasure_reveal",
            "camera": "close_up",
            "lighting": "warm",
            "emotion": "surprise",
        }
        
        mutation_options = [
            {"element": "camera", "new_value": "zoom_in"},
            {"element": "lighting", "new_value": "dramatic"},
            {"element": "emotion", "new_value": "excitement"},
        ]
        
        return self.generate_variants(parent_dna, mutation_options, "winner_001")
