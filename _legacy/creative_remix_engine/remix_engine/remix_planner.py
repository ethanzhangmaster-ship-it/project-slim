"""Remix Planner — 根据 Winner 结构生成剪辑方案

输入：
- Winner Pattern（来自 WinnerStructureMiner）
- Shot Library（来自 ShotExtractor）

输出：remix_plan.json

例如：
Creative #001
  Hook: dragon_023.mp4 0-2s
  Gameplay: merge_105.mp4 2-8s
  Reward: witch_088.mp4 8-15s
  Ending: reward_032.mp4 15-20s
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np

from creative_remix_engine.shot_intelligence import ShotDatabase, ShotDNA, ShotEmbedding
from .winner_structure_miner import WinningStructure, StructureSegment


@dataclass
class RemixSegment:
    """剪辑方案片段"""
    role: str
    shot_id: str
    source_video: str
    start_time: float   # 在原视频中的起始时间
    end_time: float     # 在原视频中的结束时间
    duration: float     # 使用时长
    dna: dict
    match_score: float  # 匹配分数


@dataclass
class RemixPlan:
    """剪辑方案"""
    plan_id: str
    creative_id: str
    name: str
    segments: List[RemixSegment]
    total_duration: float
    structure_name: str
    predicted_score: float
    mutation_strategy: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "creative_id": self.creative_id,
            "name": self.name,
            "segments": [asdict(s) for s in self.segments],
            "total_duration": self.total_duration,
            "structure_name": self.structure_name,
            "predicted_score": self.predicted_score,
            "mutation_strategy": self.mutation_strategy,
        }


class RemixPlanner:
    """Remix 方案生成器"""

    def __init__(self, shot_db: ShotDatabase,
                 embedding: Optional[ShotEmbedding] = None):
        self.shot_db = shot_db
        self.embedding = embedding or ShotEmbedding()

    def plan(self, winning_structure: WinningStructure,
             n_creatives: int = 20,
             strategy: str = "best_match") -> List[RemixPlan]:
        """生成剪辑方案"""
        print(f"[RemixPlanner] Generating {n_creatives} remix plans...")

        plans = []
        for i in range(n_creatives):
            plan = self._create_single_plan(
                winning_structure,
                creative_id=f"creative_{i+1:03d}",
                strategy=strategy,
            )
            if plan:
                plans.append(plan)

        # 按预测分排序
        plans.sort(key=lambda p: -p.predicted_score)

        print(f"  Generated {len(plans)} valid plans")
        return plans

    def _create_single_plan(self, structure: WinningStructure,
                            creative_id: str,
                            strategy: str = "best_match") -> Optional[RemixPlan]:
        """创建单个剪辑方案"""
        segments = []
        total_score = 0.0

        for seg_template in structure.segments:
            # 查找匹配的 shot
            matched_shot, score = self._find_matching_shot(
                seg_template,
                strategy=strategy,
                exclude_shots=[s.shot_id for s in segments],
            )

            if not matched_shot:
                continue

            # 计算使用时长（取 shot 时长和模板时长的较小值）
            use_duration = min(matched_shot.duration, seg_template.duration)

            remix_seg = RemixSegment(
                role=seg_template.role,
                shot_id=matched_shot.shot_id,
                source_video=matched_shot.source_video,
                start_time=matched_shot.start_time,
                end_time=matched_shot.start_time + use_duration,
                duration=use_duration,
                dna=matched_shot.to_dict(),
                match_score=score,
            )
            segments.append(remix_seg)
            total_score += score

        if not segments:
            return None

        total_duration = sum(s.duration for s in segments)
        avg_score = total_score / len(segments) if segments else 0

        return RemixPlan(
            plan_id=f"plan_{creative_id}",
            creative_id=creative_id,
            name=f"{structure.name}_{creative_id}",
            segments=segments,
            total_duration=round(total_duration, 1),
            structure_name=structure.name,
            predicted_score=round(avg_score, 3),
        )

    def _find_matching_shot(self, template: StructureSegment,
                            strategy: str = "best_match",
                            exclude_shots: Optional[List[str]] = None) -> Tuple[Optional[ShotDNA], float]:
        """查找匹配的 shot"""
        exclude_shots = exclude_shots or []

        # 从数据库查询候选
        candidates = self.shot_db.query(
            role=template.role,
            subject=template.subject,
            min_performance_score=60,
            limit=50,
        )

        # 排除已使用的
        candidates = [c for c in candidates if c.shot_id not in exclude_shots]

        if not candidates:
            # 放宽条件
            candidates = self.shot_db.query(
                role=template.role,
                min_performance_score=50,
                limit=50,
            )
            candidates = [c for c in candidates if c.shot_id not in exclude_shots]

        if not candidates:
            return None, 0.0

        if strategy == "best_match":
            return self._best_match(template, candidates)
        elif strategy == "diverse":
            return self._diverse_match(template, candidates)
        elif strategy == "random":
            shot = np.random.choice(candidates)
            return shot, 0.7
        else:
            return self._best_match(template, candidates)

    def _best_match(self, template: StructureSegment,
                    candidates: List[ShotDNA]) -> Tuple[ShotDNA, float]:
        """最佳匹配"""
        best_shot = None
        best_score = -1

        for shot in candidates:
            score = self._calculate_match_score(template, shot)
            if score > best_score:
                best_score = score
                best_shot = shot

        return best_shot, best_score

    def _diverse_match(self, template: StructureSegment,
                       candidates: List[ShotDNA]) -> Tuple[ShotDNA, float]:
        """多样化匹配（确保不同视频来源）"""
        # 按来源视频分组，每组选一个最好的
        by_source = {}
        for shot in candidates:
            source = shot.source_video
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(shot)

        # 从每组选最佳
        best_per_source = []
        for source, shots in by_source.items():
            best = max(shots, key=lambda s: self._calculate_match_score(template, s))
            score = self._calculate_match_score(template, best)
            best_per_source.append((best, score))

        # 随机选择一个（确保多样性）
        if best_per_source:
            shot, score = best_per_source[np.random.randint(len(best_per_source))]
            return shot, score

        return None, 0.0

    def _calculate_match_score(self, template: StructureSegment, shot: ShotDNA) -> float:
        """计算模板和 shot 的匹配分数"""
        score = 0.0

        # 角色匹配（权重最高）
        if template.role == shot.role:
            score += 0.3

        # 主体匹配
        if template.subject == shot.subject:
            score += 0.2
        elif template.subject == "character" and shot.subject in ["monster", "character"]:
            score += 0.15

        # 动作匹配
        if template.action == shot.action:
            score += 0.15

        # 情绪匹配
        if template.emotion == shot.emotion:
            score += 0.1

        # 镜头匹配
        if template.camera == shot.camera:
            score += 0.05

        # 表现分加权
        score += (shot.performance_score / 100) * 0.15

        # 时长适配度
        duration_diff = abs(template.duration - shot.duration)
        if duration_diff < 2:
            score += 0.05

        return min(1.0, score)

    def plan_with_mutation(self, structure: WinningStructure,
                           mutation_strategy: str,
                           n_creatives: int = 10) -> List[RemixPlan]:
        """基于变异策略生成方案"""
        from .remix_mutation import RemixMutationEngine

        mutator = RemixMutationEngine()
        mutated_structures = mutator.mutate(structure, strategy=mutation_strategy)

        plans = []
        for i, mutated_struct in enumerate(mutated_structures):
            plan = self._create_single_plan(
                mutated_struct,
                creative_id=f"creative_mut_{i+1:03d}",
                strategy="best_match",
            )
            if plan:
                plan.mutation_strategy = mutation_strategy
                plans.append(plan)

        return plans

    def save_plans(self, plans: List[RemixPlan], output_path: Path):
        """保存方案"""
        data = {
            "plans": [p.to_dict() for p in plans],
            "total": len(plans),
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  Remix plans saved: {output_path}")

    def get_shot_usage_stats(self, plans: List[RemixPlan]) -> dict:
        """获取 shot 使用统计"""
        usage = {}
        for plan in plans:
            for seg in plan.segments:
                shot_id = seg.shot_id
                usage[shot_id] = usage.get(shot_id, 0) + 1

        return {
            "total_unique_shots": len(usage),
            "most_used": sorted(usage.items(), key=lambda x: -x[1])[:10],
            "avg_reuse_per_shot": sum(usage.values()) / len(usage) if usage else 0,
        }