"""Mutation Strategy - 变异策略"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Any


class MutationType(str, Enum):
    """变异类型"""
    HOOK_CHANGE = "hook_change"
    CAMERA_CHANGE = "camera_change"
    LIGHTING_CHANGE = "lighting_change"
    SCENE_CHANGE = "scene_change"
    CTA_CHANGE = "cta_change"
    STYLE_CHANGE = "style_change"
    EMOTION_CHANGE = "emotion_change"
    CHARACTER_CHANGE = "character_change"
    MULTI_CHANGE = "multi_change"


@dataclass
class MutationOption:
    """变异选项"""
    mutation_type: MutationType = MutationType.HOOK_CHANGE
    element: str = ""
    original_value: str = ""
    new_value: str = ""
    probability: float = 0.0
    impact: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_type": self.mutation_type.value,
            "element": self.element,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "probability": round(self.probability, 2),
            "impact": round(self.impact, 2),
        }


class MutationStrategy:
    """变异策略"""
    
    # 变异选项库
    MUTATION_POOL = {
        "hook": ["fast_action", "slow_build", "surprise_reveal", "instant_reward", "question_hook"],
        "camera": ["close_up", "wide", "medium", "zoom_in", "zoom_out", "pan", "tracking"],
        "lighting": ["warm", "cool", "dramatic", "soft", "bright"],
        "scene": ["reward", "battle", "character", "treasure", "journey"],
        "cta": ["download_now", "play_now", "free_trial", "limited_time", "reward_reveal"],
        "style": ["cinematic", "cartoon", "realistic", "pixel", "anime"],
        "emotion": ["surprise", "excitement", "curiosity", "joy", "fear"],
        "character": ["witch", "warrior", "hero", "monster", "explorer"],
    }
    
    def __init__(self):
        self._mutation_history: List[Dict[str, Any]] = []
    
    def get_mutation_options(self, dna: Dict[str, str]) -> List[MutationOption]:
        """获取变异选项"""
        options = []
        
        for element, current_value in dna.items():
            if element in self.MUTATION_POOL:
                available_values = [v for v in self.MUTATION_POOL[element] if v != current_value]
                
                for new_value in available_values[:3]:
                    mutation_type = self._get_mutation_type(element)
                    
                    options.append(MutationOption(
                        mutation_type=mutation_type,
                        element=element,
                        original_value=current_value,
                        new_value=new_value,
                        probability=self._calculate_probability(element),
                        impact=self._calculate_impact(element),
                    ))
        
        return options
    
    def _get_mutation_type(self, element: str) -> MutationType:
        """获取变异类型"""
        type_map = {
            "hook": MutationType.HOOK_CHANGE,
            "camera": MutationType.CAMERA_CHANGE,
            "lighting": MutationType.LIGHTING_CHANGE,
            "scene": MutationType.SCENE_CHANGE,
            "cta": MutationType.CTA_CHANGE,
            "style": MutationType.STYLE_CHANGE,
            "emotion": MutationType.EMOTION_CHANGE,
            "character": MutationType.CHARACTER_CHANGE,
        }
        return type_map.get(element, MutationType.MULTI_CHANGE)
    
    def _calculate_probability(self, element: str) -> float:
        """计算变异概率"""
        # 关键元素（hook/camera）变异概率较低，保持稳定性
        key_elements = ["hook", "camera"]
        if element in key_elements:
            return 0.30
        return 0.60
    
    def _calculate_impact(self, element: str) -> float:
        """计算变异影响"""
        impact_map = {
            "hook": 0.80,
            "camera": 0.60,
            "emotion": 0.50,
            "cta": 0.45,
            "lighting": 0.30,
            "scene": 0.35,
            "style": 0.25,
            "character": 0.40,
        }
        return impact_map.get(element, 0.30)
    
    def select_strategy(self, dna: Dict[str, str], count: int = 3) -> List[MutationOption]:
        """选择变异策略"""
        options = self.get_mutation_options(dna)
        
        # 按影响排序，优先选择高影响但低概率的变异（保持多样性）
        sorted_options = sorted(options, key=lambda o: o.impact * (1 - o.probability), reverse=True)
        
        return sorted_options[:count]
