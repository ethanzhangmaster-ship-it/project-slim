"""Smart Mutation Engine V3.8 — 基于 Winner DNA 指导的智能变异

从随机变异转向基于 Winner DNA 模式的定向变异，提升变异成功率。
"""
import random
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

from .dna_similarity import DNASimilarityEngine
from .archetype_ranker import ArchetypeDiscoveryEngine


@dataclass
class MutationSuggestion:
    """变异建议"""
    target_dimension: str
    mutation_type: str
    direction: str
    expected_improvement: float
    confidence: float
    description: str


class SmartMutationEngine:
    """智能变异引擎 — 基于 Winner DNA 指导变异方向"""

    def __init__(self, winner_db_path: Optional[str] = None):
        self.similarity_engine = DNASimilarityEngine()
        self.archetype_engine = ArchetypeDiscoveryEngine(
            __import__('pathlib').Path(winner_db_path) if winner_db_path else None
        )
        self.archetype_engine.discover_archetypes()

    def suggest_mutations(self, current_dna: dict, current_score: float,
                          target_archetype: str = "",
                          num_suggestions: int = 3) -> List[MutationSuggestion]:
        """生成变异建议"""
        suggestions = []

        # 1. 找最接近的高绩效 Archetype
        if not target_archetype:
            archetype_result = self.archetype_engine.classify_creative(current_dna)
            target_archetype = archetype_result["archetype"]
            current_sim = archetype_result["similarity"]
        else:
            _, sim_result = self.similarity_engine.find_closest_archetype(current_dna)
            current_sim = sim_result.overall

        target_arch = self.archetype_engine.archetypes.get(target_archetype)
        if not target_arch:
            return self._fallback_suggestions(num_suggestions)

        target_dna = target_arch.representative_dna

        # 2. 分析各维度差距，优先改进差距最大且权重高的维度
        dimension_gaps = self._analyze_dimension_gaps(current_dna, target_dna)

        # 3. 生成变异建议
        for dim_name, gap_info in sorted(
            dimension_gaps.items(),
            key=lambda x: -x[1]["priority_score"]
        )[:num_suggestions]:
            suggestion = self._build_mutation_suggestion(dim_name, gap_info, target_archetype)
            if suggestion:
                suggestions.append(suggestion)

        return suggestions[:num_suggestions]

    def _analyze_dimension_gaps(self, current_dna: dict, target_dna: dict) -> Dict[str, dict]:
        """分析各维度差距"""
        gaps = {}

        dim_map = {
            "hook": ("hook_dna", "overall_hook", 0.30),
            "gameplay": ("gameplay_dna", "clarity", 0.25),
            "reward": ("reward_dna", "reward_score", 0.20),
            "subject": ("subject_dna", "size_ratio", 0.15),
            "structure": ("structure_dna", "hook_duration", 0.10),
        }

        for dim_name, (dna_key, metric_key, weight) in dim_map.items():
            curr_dna = current_dna.get(dna_key, {})
            tgt_dna = target_dna.get(dna_key, {})

            # 数值差距
            curr_val = curr_dna.get(metric_key, 50)
            tgt_val = tgt_dna.get(metric_key, 50)

            if isinstance(curr_val, (int, float)) and isinstance(tgt_val, (int, float)):
                gap = tgt_val - curr_val
                gap_pct = abs(gap) / max(tgt_val, 1) * 100
            else:
                gap = 0
                gap_pct = 20

            # 类型匹配度
            type_match = self._check_type_match(dim_name, curr_dna, tgt_dna)

            # 优先级 = 差距 * 权重
            priority_score = gap_pct * weight + (0 if type_match else 30 * weight)

            gaps[dim_name] = {
                "gap": gap,
                "gap_pct": gap_pct,
                "type_match": type_match,
                "weight": weight,
                "priority_score": priority_score,
                "current_val": curr_val,
                "target_val": tgt_val,
                "current_dna": curr_dna,
                "target_dna": tgt_dna,
            }

        return gaps

    @staticmethod
    def _check_type_match(dim_name: str, curr_dna: dict, tgt_dna: dict) -> bool:
        """检查类型是否匹配"""
        type_keys = {
            "hook": "hook_type",
            "gameplay": "action",
            "reward": "reward_type",
            "subject": "primary_subject",
            "structure": "pacing",
        }
        key = type_keys.get(dim_name, "")
        if not key:
            return True
        return curr_dna.get(key) == tgt_dna.get(key)

    def _build_mutation_suggestion(self, dim_name: str, gap_info: dict,
                                    target_archetype: str) -> Optional[MutationSuggestion]:
        """构建变异建议"""
        dim_display = {
            "hook": "Hook开场",
            "gameplay": "玩法展示",
            "reward": "奖励呈现",
            "subject": "主体呈现",
            "structure": "视频结构",
        }

        if gap_info["priority_score"] < 5:
            return None

        # 确定变异方向
        if not gap_info["type_match"]:
            mutation_type = "type_change"
            direction = "向 Winner 类型靠拢"
            expected_improvement = min(20, gap_info["priority_score"] * 0.5)
        else:
            mutation_type = "intensity_adjust"
            direction = "提升" if gap_info["gap"] > 0 else "降低"
            expected_improvement = min(15, abs(gap_info["gap_pct"]) * 0.3)

        description = (
            f"{dim_display.get(dim_name, dim_name)}优化: "
            f"{direction}强度，目标接近 {target_archetype} 模式"
        )

        confidence = min(95, 50 + gap_info["weight"] * 100 + gap_info["priority_score"] * 0.5)

        return MutationSuggestion(
            target_dimension=dim_name,
            mutation_type=mutation_type,
            direction=direction,
            expected_improvement=round(expected_improvement, 1),
            confidence=round(confidence, 1),
            description=description,
        )

    def _fallback_suggestions(self, num_suggestions: int) -> List[MutationSuggestion]:
        """无数据时的默认建议"""
        defaults = [
            MutationSuggestion(
                target_dimension="hook",
                mutation_type="intensity_adjust",
                direction="增强",
                expected_improvement=8.0,
                confidence=60.0,
                description="Hook开场优化: 增强首帧视觉冲击力",
            ),
            MutationSuggestion(
                target_dimension="gameplay",
                mutation_type="clarity_improve",
                direction="提升",
                expected_improvement=6.0,
                confidence=55.0,
                description="玩法展示优化: 提升玩法清晰度和节奏感",
            ),
            MutationSuggestion(
                target_dimension="reward",
                mutation_type="intensity_adjust",
                direction="增强",
                expected_improvement=5.0,
                confidence=50.0,
                description="奖励呈现优化: 增强奖励视觉效果和吸引力",
            ),
        ]
        return defaults[:num_suggestions]

    def generate_variant_config(self, base_dna: dict, suggestion: MutationSuggestion) -> dict:
        """根据建议生成变体配置"""
        config = {
            "base_dna": base_dna,
            "mutation_target": suggestion.target_dimension,
            "mutation_type": suggestion.mutation_type,
            "expected_improvement": suggestion.expected_improvement,
        }

        # 根据维度生成具体变异参数
        if suggestion.target_dimension == "hook":
            config.update({
                "hook_intensity_boost": 1.2 if "提升" in suggestion.direction else 0.85,
                "hook_type_variant": suggestion.mutation_type == "type_change",
                "motion_speed_adjust": 1.1,
            })
        elif suggestion.target_dimension == "gameplay":
            config.update({
                "gameplay_clarity_boost": 1.15,
                "pacing_adjust": "faster" if "提升" in suggestion.direction else "slower",
                "before_after_enhance": True,
            })
        elif suggestion.target_dimension == "reward":
            config.update({
                "reward_flash_boost": 1.3,
                "reward_duration_extend": 0.5,
                "evolution_visible": True,
            })

        return config

    def optimize_mutation_pool(self, current_pool: List[str],
                                performance_data: List[dict]) -> List[str]:
        """基于表现数据优化变异池"""
        if not performance_data:
            return current_pool

        # 简单的权重调整：高分素材的特征权重提升
        scored_pool = []
        for item in current_pool:
            base_score = 1.0
            for perf in performance_data:
                if perf.get("variant") == item:
                    if perf.get("ctr", 0) > 2.5:
                        base_score += 0.5
                    if perf.get("roi", 0) > 0.3:
                        base_score += 0.5
            scored_pool.append((item, base_score))

        # 按权重采样
        scored_pool.sort(key=lambda x: -x[1])
        return [item for item, _ in scored_pool]
