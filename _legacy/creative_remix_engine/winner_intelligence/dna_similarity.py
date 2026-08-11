"""DNA Similarity Engine — 计算创意 DNA 相似度

基于多维 DNA 特征（Hook/Subject/Gameplay/Reward/Structure）计算相似度，
识别新素材与 Winner DNA 的接近程度。
"""
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class SimilarityResult:
    """相似度结果"""
    overall: float
    hook_similarity: float
    subject_similarity: float
    gameplay_similarity: float
    reward_similarity: float
    structure_similarity: float
    matched_archetype: str = ""
    confidence: float = 0.0


class DNASimilarityEngine:
    """DNA 相似度计算引擎"""

    # 各维度权重
    DIMENSION_WEIGHTS = {
        "hook": 0.30,
        "subject": 0.20,
        "gameplay": 0.25,
        "reward": 0.15,
        "structure": 0.10,
    }

    def __init__(self):
        self.winner_dna_store: Dict[str, dict] = {}
        self.archetypes: Dict[str, dict] = {}

    def add_winner_dna(self, dna_id: str, dna: dict):
        """添加 Winner DNA 到比对库"""
        self.winner_dna_store[dna_id] = dna

    def add_archetype(self, name: str, archetype_dna: dict, avg_performance: dict = None):
        """添加 Performance Archetype"""
        self.archetypes[name] = {
            "dna": archetype_dna,
            "performance": avg_performance or {},
        }

    def compute_similarity(self, dna_a: dict, dna_b: dict) -> SimilarityResult:
        """计算两个 DNA 的相似度"""
        hook_sim = self._hook_similarity(
            dna_a.get("hook_dna", {}),
            dna_b.get("hook_dna", {})
        )
        subject_sim = self._subject_similarity(
            dna_a.get("subject_dna", {}),
            dna_b.get("subject_dna", {})
        )
        gameplay_sim = self._gameplay_similarity(
            dna_a.get("gameplay_dna", {}),
            dna_b.get("gameplay_dna", {})
        )
        reward_sim = self._reward_similarity(
            dna_a.get("reward_dna", {}),
            dna_b.get("reward_dna", {})
        )
        structure_sim = self._structure_similarity(
            dna_a.get("structure_dna", {}),
            dna_b.get("structure_dna", {})
        )

        overall = (
            hook_sim * self.DIMENSION_WEIGHTS["hook"] +
            subject_sim * self.DIMENSION_WEIGHTS["subject"] +
            gameplay_sim * self.DIMENSION_WEIGHTS["gameplay"] +
            reward_sim * self.DIMENSION_WEIGHTS["reward"] +
            structure_sim * self.DIMENSION_WEIGHTS["structure"]
        )

        return SimilarityResult(
            overall=round(overall, 2),
            hook_similarity=round(hook_sim, 2),
            subject_similarity=round(subject_sim, 2),
            gameplay_similarity=round(gameplay_sim, 2),
            reward_similarity=round(reward_sim, 2),
            structure_similarity=round(structure_sim, 2),
        )

    def find_closest_winner(self, target_dna: dict) -> Tuple[str, SimilarityResult]:
        """找最接近的 Winner"""
        best_id = ""
        best_sim = SimilarityResult(overall=0, hook_similarity=0, subject_similarity=0,
                                    gameplay_similarity=0, reward_similarity=0, structure_similarity=0)

        for dna_id, winner_dna in self.winner_dna_store.items():
            sim = self.compute_similarity(target_dna, winner_dna)
            if sim.overall > best_sim.overall:
                best_sim = sim
                best_id = dna_id

        return best_id, best_sim

    def find_closest_archetype(self, target_dna: dict) -> Tuple[str, SimilarityResult]:
        """找最接近的 Archetype"""
        best_name = ""
        best_sim = SimilarityResult(overall=0, hook_similarity=0, subject_similarity=0,
                                    gameplay_similarity=0, reward_similarity=0, structure_similarity=0)

        for name, archetype_info in self.archetypes.items():
            sim = self.compute_similarity(target_dna, archetype_info["dna"])
            if sim.overall > best_sim.overall:
                best_sim = sim
                best_name = name

        best_sim.matched_archetype = best_name
        best_sim.confidence = best_sim.overall
        return best_name, best_sim

    def match_against_all_winners(self, target_dna: dict) -> List[dict]:
        """与所有 Winner 比对，返回排序结果"""
        results = []
        for dna_id, winner_dna in self.winner_dna_store.items():
            sim = self.compute_similarity(target_dna, winner_dna)
            results.append({
                "winner_id": dna_id,
                "similarity": sim.overall,
                "details": sim,
            })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    def _hook_similarity(self, hook_a: dict, hook_b: dict) -> float:
        """Hook DNA 相似度"""
        score = 0.0
        total_weight = 0.0

        # Hook 类型匹配（权重最高）
        type_a = hook_a.get("hook_type", "general")
        type_b = hook_b.get("hook_type", "general")
        if type_a == type_b:
            score += 40
        elif self._are_types_related(type_a, type_b):
            score += 20
        total_weight += 40

        # 数值维度相似度
        numeric_keys = [
            ("first_frame_strength", 15),
            ("motion_speed", 10),
            ("novelty", 15),
            ("emotion", 10),
            ("overall_hook", 10),
        ]
        for key, weight in numeric_keys:
            val_a = hook_a.get(key, 50)
            val_b = hook_b.get(key, 50)
            diff = abs(val_a - val_b)
            sim_val = max(0, 100 - diff * 2)
            score += sim_val * weight / 100
            total_weight += weight

        return score / total_weight * 100 if total_weight > 0 else 50

    def _subject_similarity(self, subj_a: dict, subj_b: dict) -> float:
        """Subject DNA 相似度"""
        score = 0.0
        total_weight = 0.0

        # 主体匹配
        subs_a = set(subj_a.get("subjects", []))
        subs_b = set(subj_b.get("subjects", []))
        if subs_a and subs_b:
            overlap = subs_a & subs_b
            if overlap:
                score += 50 * len(overlap) / max(len(subs_a), len(subs_b))
        total_weight += 50

        # 主要主体匹配
        if subj_a.get("primary_subject") == subj_b.get("primary_subject"):
            score += 20
        total_weight += 20

        # 大小占比相似度
        size_a = subj_a.get("size_ratio", 0.3)
        size_b = subj_b.get("size_ratio", 0.3)
        size_diff = abs(size_a - size_b)
        size_sim = max(0, 100 - size_diff * 200)
        score += size_sim * 0.3
        total_weight += 30

        return score / total_weight * 100 if total_weight > 0 else 50

    def _gameplay_similarity(self, gp_a: dict, gp_b: dict) -> float:
        """Gameplay DNA 相似度"""
        score = 0.0
        total_weight = 0.0

        # 动作类型匹配
        action_a = gp_a.get("action", "showcase")
        action_b = gp_b.get("action", "showcase")
        if action_a == action_b:
            score += 35
        elif self._are_actions_related(action_a, action_b):
            score += 15
        total_weight += 35

        # 清晰度相似度
        clarity_a = gp_a.get("clarity", 50)
        clarity_b = gp_b.get("clarity", 50)
        clarity_sim = max(0, 100 - abs(clarity_a - clarity_b) * 2)
        score += clarity_sim * 0.25
        total_weight += 25

        # 动作分维度相似度
        dim_keys = [
            ("merge_score", 10),
            ("drag_score", 10),
            ("upgrade_score", 10),
            ("before_after", 10),
        ]
        for key, weight in dim_keys:
            val_a = gp_a.get(key, 30)
            val_b = gp_b.get(key, 30)
            sim_val = max(0, 100 - abs(val_a - val_b) * 2)
            score += sim_val * weight / 100
            total_weight += weight

        return score / total_weight * 100 if total_weight > 0 else 50

    def _reward_similarity(self, rew_a: dict, rew_b: dict) -> float:
        """Reward DNA 相似度"""
        score = 0.0
        total_weight = 0.0

        # 奖励类型匹配
        type_a = rew_a.get("reward_type", "general")
        type_b = rew_b.get("reward_type", "general")
        if type_a == type_b:
            score += 40
        total_weight += 40

        # 奖励分数相似度
        rs_a = rew_a.get("reward_score", 50)
        rs_b = rew_b.get("reward_score", 50)
        rs_sim = max(0, 100 - abs(rs_a - rs_b) * 2)
        score += rs_sim * 0.3
        total_weight += 30

        # 闪光强度相似度
        flash_a = rew_a.get("flash_strength", 30)
        flash_b = rew_b.get("flash_strength", 30)
        flash_sim = max(0, 100 - abs(flash_a - flash_b) * 2)
        score += flash_sim * 0.3
        total_weight += 30

        return score / total_weight * 100 if total_weight > 0 else 50

    def _structure_similarity(self, struct_a: dict, struct_b: dict) -> float:
        """Structure DNA 相似度"""
        score = 0.0
        total_weight = 0.0

        # 节奏匹配
        pacing_a = struct_a.get("pacing", "medium")
        pacing_b = struct_b.get("pacing", "medium")
        if pacing_a == pacing_b:
            score += 20
        total_weight += 20

        # 各阶段时长比例相似度
        duration_keys = [
            ("hook_duration", 25),
            ("gameplay_duration", 25),
            ("reward_duration", 15),
            ("cta_duration", 15),
        ]
        total_dur_a = struct_a.get("total_duration", 15)
        total_dur_b = struct_b.get("total_duration", 15)

        for key, weight in duration_keys:
            ratio_a = struct_a.get(key, 3) / max(total_dur_a, 1)
            ratio_b = struct_b.get(key, 3) / max(total_dur_b, 1)
            diff = abs(ratio_a - ratio_b)
            sim_val = max(0, 100 - diff * 300)
            score += sim_val * weight / 100
            total_weight += weight

        return score / total_weight * 100 if total_weight > 0 else 50

    @staticmethod
    def _are_types_related(type_a: str, type_b: str) -> bool:
        """判断 Hook 类型是否相关"""
        related_groups = [
            {"shock", "surprise", "urgency"},
            {"challenge", "curiosity"},
            {"transformation", "upgrade"},
        ]
        for group in related_groups:
            if type_a in group and type_b in group:
                return True
        return False

    @staticmethod
    def _are_actions_related(act_a: str, act_b: str) -> bool:
        """判断动作类型是否相关"""
        related_groups = [
            {"merge", "drag"},
            {"upgrade", "unlock"},
            {"battle", "challenge"},
        ]
        for group in related_groups:
            if act_a in group and act_b in group:
                return True
        return False
