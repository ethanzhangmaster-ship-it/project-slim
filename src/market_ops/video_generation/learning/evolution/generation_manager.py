"""Generation Manager - 世代管理器"""
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class GenerationRecord:
    """世代记录"""
    generation_id: str = ""
    generation_number: int = 0
    parent_creative_id: str = ""
    child_creative_id: str = ""
    mutation_history: List[Dict[str, Any]] = None
    fitness_score: float = 0.0
    rank_in_generation: int = 0
    created_at: str = ""
    
    def __post_init__(self):
        if self.mutation_history is None:
            self.mutation_history = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "generation_number": self.generation_number,
            "parent_creative_id": self.parent_creative_id,
            "child_creative_id": self.child_creative_id,
            "mutation_history": self.mutation_history,
            "fitness_score": round(self.fitness_score, 2),
            "rank_in_generation": self.rank_in_generation,
            "created_at": self.created_at,
        }


class GenerationManager:
    """世代管理器"""
    
    def __init__(self):
        self._generations: List[GenerationRecord] = []
        self._current_generation = 0
        self._generation_counter = 0
    
    def create_generation(self, generation_number: int = None) -> str:
        """创建新世代"""
        if generation_number is not None:
            self._current_generation = generation_number
        else:
            self._current_generation += 1
        
        self._generation_counter += 1
        generation_id = f"gen_{self._generation_counter:03d}"
        
        return generation_id
    
    def add_creative(
        self,
        parent_id: str,
        child_id: str,
        mutation_history: List[Dict[str, Any]] = None,
        fitness_score: float = 0.0,
        rank: int = 0,
    ) -> GenerationRecord:
        """添加创意到当前世代"""
        record = GenerationRecord(
            generation_id=f"gen_{self._current_generation:03d}",
            generation_number=self._current_generation,
            parent_creative_id=parent_id,
            child_creative_id=child_id,
            mutation_history=mutation_history or [],
            fitness_score=fitness_score,
            rank_in_generation=rank,
            created_at=datetime.now().isoformat(),
        )
        
        self._generations.append(record)
        return record
    
    def get_generation(self, generation_number: int) -> List[GenerationRecord]:
        """获取指定世代"""
        return [
            g for g in self._generations
            if g.generation_number == generation_number
        ]
    
    def get_current_generation(self) -> List[GenerationRecord]:
        """获取当前世代"""
        return self.get_generation(self._current_generation)
    
    def get_best_creatives(self, generation_number: int = None, limit: int = 5) -> List[GenerationRecord]:
        """获取最佳创意"""
        if generation_number is None:
            generation_number = self._current_generation
        
        generation = self.get_generation(generation_number)
        return sorted(generation, key=lambda g: g.fitness_score, reverse=True)[:limit]
    
    def get_lineage(self, creative_id: str) -> List[GenerationRecord]:
        """获取创意血缘"""
        lineage = []
        current_id = creative_id
        
        while current_id:
            # 查找父创意
            record = next(
                (g for g in self._generations if g.child_creative_id == current_id),
                None
            )
            
            if record:
                lineage.append(record)
                current_id = record.parent_creative_id
            else:
                current_id = None
        
        return list(reversed(lineage))
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        total_generations = len(set(g.generation_number for g in self._generations))
        total_creatives = len(self._generations)
        
        best_creative = max(self._generations, key=lambda g: g.fitness_score) if self._generations else None
        
        return {
            "current_generation": self._current_generation,
            "total_generations": total_generations,
            "total_creatives": total_creatives,
            "best_fitness": best_creative.fitness_score if best_creative else 0,
            "best_creative": best_creative.child_creative_id if best_creative else "",
        }
    
    def advance_generation(self):
        """进入下一代"""
        self._current_generation += 1
