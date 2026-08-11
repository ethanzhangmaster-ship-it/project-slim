"""Evolution Engine - 进化引擎"""
from dataclasses import dataclass
from typing import Dict, List, Any

from .fitness_function import FitnessFunction, FitnessScore
from .generation_manager import GenerationManager, GenerationRecord


@dataclass
class EvolutionResult:
    """进化结果"""
    generation_number: int = 0
    total_creatives: int = 0
    survived_creatives: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    new_generation_creatives: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.new_generation_creatives is None:
            self.new_generation_creatives = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation_number": self.generation_number,
            "total_creatives": self.total_creatives,
            "survived_creatives": self.survived_creatives,
            "best_fitness": round(self.best_fitness, 2),
            "avg_fitness": round(self.avg_fitness, 2),
            "new_generation_creatives": self.new_generation_creatives,
        }


class EvolutionEngine:
    """进化引擎"""
    
    def __init__(self, survival_rate: float = 0.20):
        self.fitness_function = FitnessFunction()
        self.generation_manager = GenerationManager()
        self.survival_rate = survival_rate
    
    def evolve(
        self,
        creatives: List[Dict[str, Any]],
        generation_number: int = None,
    ) -> EvolutionResult:
        """执行一轮进化
        
        流程:
        1. 计算所有创意的适应度
        2. 选择 Top N% 幸存者
        3. 准备下一代
        
        Args:
            creatives: 创意列表，包含 ctr, ipm, purchase_rate, roas
            generation_number: 世代编号
        
        Returns:
            EvolutionResult
        """
        # 创建世代
        self.generation_manager.create_generation(generation_number)
        
        # 计算适应度
        scores = {}
        for creative in creatives:
            creative_id = creative.get("creative_id", "")
            score = self.fitness_function.calculate(
                creative_id=creative_id,
                ctr=creative.get("ctr", 0),
                ipm=creative.get("ipm", 0),
                purchase_rate=creative.get("purchase_rate", 0),
                roas=creative.get("roas", 0),
            )
            scores[creative_id] = score
        
        # 选择幸存者
        survivors = self.fitness_function.select_survivors(scores, self.survival_rate)
        
        # 添加到世代管理器
        for i, survivor in enumerate(survivors):
            self.generation_manager.add_creative(
                parent_id=survivor.creative_id,
                child_id=f"gen{self.generation_manager._current_generation}_{i+1}",
                fitness_score=survivor.fitness,
                rank=i + 1,
            )
        
        # 准备下一代创意（仅返回幸存者 DNA）
        new_generation = []
        for survivor in survivors:
            creative = next((c for c in creatives if c.get("creative_id") == survivor.creative_id), {})
            new_generation.append({
                "creative_id": survivor.creative_id,
                "dna": creative.get("dna", {}),
                "fitness": survivor.fitness,
                "rank": survivor.rank,
            })
        
        # 计算统计
        all_fitness = [s.fitness for s in scores.values()]
        avg_fitness = sum(all_fitness) / len(all_fitness) if all_fitness else 0
        best_fitness = max(all_fitness) if all_fitness else 0
        
        return EvolutionResult(
            generation_number=self.generation_manager._current_generation,
            total_creatives=len(creatives),
            survived_creatives=len(survivors),
            best_fitness=best_fitness,
            avg_fitness=avg_fitness,
            new_generation_creatives=new_generation,
        )
    
    def run_cycle(
        self,
        initial_creatives: List[Dict[str, Any]],
        generations: int = 3,
    ) -> List[EvolutionResult]:
        """运行多轮进化"""
        results = []
        current_creatives = initial_creatives
        
        for gen in range(1, generations + 1):
            result = self.evolve(current_creatives, gen)
            results.append(result)
            
            # 准备下一代（模拟变异）
            current_creatives = self._generate_next_generation(result)
        
        return results
    
    def _generate_next_generation(self, result: EvolutionResult) -> List[Dict[str, Any]]:
        """生成下一代（模拟）"""
        next_gen = []
        
        for creative in result.new_generation_creatives:
            # 每个幸存者产生 3 个子代（模拟变异）
            for i in range(3):
                mutated_dna = self._mutate_dna(creative.get("dna", {}))
                next_gen.append({
                    "creative_id": f"{creative['creative_id']}_mut_{i+1}",
                    "dna": mutated_dna,
                    "ctr": creative.get("ctr", 0) + (i - 1) * 0.2,
                    "ipm": creative.get("ipm", 0) + (i - 1) * 5,
                    "purchase_rate": creative.get("purchase_rate", 0) + (i - 1) * 0.1,
                    "roas": creative.get("roas", 0) + (i - 1) * 0.1,
                })
        
        return next_gen
    
    def _mutate_dna(self, dna: Dict[str, str]) -> Dict[str, str]:
        """模拟 DNA 变异"""
        import random
        
        new_dna = dna.copy()
        
        # 随机变异一个元素
        elements = list(dna.keys())
        if elements:
            element_to_mutate = random.choice(elements)
            variations = {
                "hook": ["fast_action", "surprise_reveal", "instant_reward"],
                "camera": ["close_up", "zoom_in", "wide"],
                "lighting": ["warm", "dramatic", "cool"],
                "emotion": ["surprise", "excitement", "curiosity"],
            }
            
            if element_to_mutate in variations:
                new_dna[element_to_mutate] = random.choice(variations[element_to_mutate])
        
        return new_dna
    
    def evolve_demo(self) -> List[EvolutionResult]:
        """生成演示数据"""
        initial_creatives = [
            {"creative_id": "c001", "dna": {"hook": "fast_action", "camera": "close_up"}, "ctr": 5.8, "ipm": 83, "purchase_rate": 4.1, "roas": 1.8},
            {"creative_id": "c002", "dna": {"hook": "slow_build", "camera": "wide"}, "ctr": 2.1, "ipm": 30, "purchase_rate": 1.2, "roas": 0.8},
            {"creative_id": "c003", "dna": {"hook": "surprise_reveal", "camera": "zoom_in"}, "ctr": 4.2, "ipm": 65, "purchase_rate": 2.8, "roas": 1.5},
            {"creative_id": "c004", "dna": {"hook": "instant_reward", "camera": "close_up"}, "ctr": 3.9, "ipm": 55, "purchase_rate": 2.5, "roas": 1.2},
            {"creative_id": "c005", "dna": {"hook": "fast_action", "camera": "medium"}, "ctr": 3.5, "ipm": 48, "purchase_rate": 2.2, "roas": 1.1},
        ]
        
        return self.run_cycle(initial_creatives, generations=3)
