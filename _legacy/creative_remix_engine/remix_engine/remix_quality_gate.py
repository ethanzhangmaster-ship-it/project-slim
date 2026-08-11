"""Remix Quality Gate — 生成后自动评分

指标：
1. Hook Strength — 开场吸引力
2. Gameplay Clarity — 玩法清晰度
3. Reward Impact — 奖励冲击力
4. Visual Density — 视觉密度
5. Pacing — 节奏感
6. Similarity to Winner — 与 Winner 结构的相似度

等级：S+, S, A, B, Reject
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np

from creative_remix_engine.shot_intelligence import ShotEmbedding
from .remix_planner import RemixPlan
from .winner_structure_miner import WinningStructure


@dataclass
class QualityScore:
    """质量评分"""
    hook_strength: float       # 0-100
    gameplay_clarity: float    # 0-100
    reward_impact: float       # 0-100
    visual_density: float      # 0-100
    pacing: float              # 0-100
    winner_similarity: float   # 0-100
    overall_score: float       # 0-100
    grade: str                 # S+, S, A, B, Reject
    passed: bool

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert numpy types to Python native types for JSON serialization
        for key, value in d.items():
            if hasattr(value, 'item'):  # numpy scalar
                d[key] = value.item()
        return d


class RemixQualityGate:
    """Remix 质量门"""

    WEIGHTS = {
        "hook_strength": 0.25,
        "gameplay_clarity": 0.20,
        "reward_impact": 0.20,
        "visual_density": 0.15,
        "pacing": 0.10,
        "winner_similarity": 0.10,
    }

    GRADE_THRESHOLDS = {
        "S+": 90,
        "S": 80,
        "A": 65,
        "B": 50,
        "Reject": 0,
    }

    def __init__(self, pass_threshold: float = 60.0):
        self.pass_threshold = pass_threshold
        self.embedding = ShotEmbedding()

    def evaluate(self, plan: RemixPlan,
                 target_structure: Optional[WinningStructure] = None) -> QualityScore:
        """评估单个剪辑方案"""
        # 计算各项指标
        hook = self._score_hook_strength(plan)
        gameplay = self._score_gameplay_clarity(plan)
        reward = self._score_reward_impact(plan)
        visual = self._score_visual_density(plan)
        pacing = self._score_pacing(plan)
        similarity = self._score_winner_similarity(plan, target_structure)

        # 综合评分
        overall = (
            hook * self.WEIGHTS["hook_strength"] +
            gameplay * self.WEIGHTS["gameplay_clarity"] +
            reward * self.WEIGHTS["reward_impact"] +
            visual * self.WEIGHTS["visual_density"] +
            pacing * self.WEIGHTS["pacing"] +
            similarity * self.WEIGHTS["winner_similarity"]
        )

        grade = self._determine_grade(overall)
        passed = overall >= self.pass_threshold

        return QualityScore(
            hook_strength=round(hook, 1),
            gameplay_clarity=round(gameplay, 1),
            reward_impact=round(reward, 1),
            visual_density=round(visual, 1),
            pacing=round(pacing, 1),
            winner_similarity=round(similarity, 1),
            overall_score=round(overall, 1),
            grade=grade,
            passed=passed,
        )

    def batch_evaluate(self, plans: List[RemixPlan],
                       target_structure: Optional[WinningStructure] = None) -> List[QualityScore]:
        """批量评估"""
        return [self.evaluate(p, target_structure) for p in plans]

    def _score_hook_strength(self, plan: RemixPlan) -> float:
        """评分：Hook 强度"""
        hook_segs = [s for s in plan.segments if s.role == "hook"]
        if not hook_segs:
            return 30.0

        score = 0.0
        for seg in hook_segs:
            dna = seg.dna
            # 情绪为 surprise/excitement 加分
            if dna.get("emotion") in ["surprise", "excitement", "tension"]:
                score += 30
            # 镜头为 zoom_in/closeup 加分
            if dna.get("camera") in ["zoom_in", "closeup"]:
                score += 20
            # 动作为 attack/transform 加分
            if dna.get("action") in ["attack", "transform", "rescue"]:
                score += 20
            # 视觉分
            score += dna.get("visual_score", 50) * 0.3

        return min(100, score / len(hook_segs))

    def _score_gameplay_clarity(self, plan: RemixPlan) -> float:
        """评分：Gameplay 清晰度"""
        gameplay_segs = [s for s in plan.segments if s.role == "gameplay"]
        if not gameplay_segs:
            return 30.0

        score = 0.0
        for seg in gameplay_segs:
            dna = seg.dna
            # 时长适中（5-10s）加分
            if 5 <= seg.duration <= 10:
                score += 25
            # 动作清晰
            if dna.get("action") in ["merge", "upgrade", "collect"]:
                score += 25
            # 镜头稳定
            if dna.get("camera") in ["pan", "static", "tracking"]:
                score += 20
            # 表现分
            score += dna.get("performance_score", 50) * 0.3

        return min(100, score / len(gameplay_segs))

    def _score_reward_impact(self, plan: RemixPlan) -> float:
        """评分：Reward 冲击力"""
        reward_segs = [s for s in plan.segments if s.role == "reward"]
        if not reward_segs:
            return 30.0

        score = 0.0
        for seg in reward_segs:
            dna = seg.dna
            # 情绪为 satisfaction/excitement 加分
            if dna.get("emotion") in ["satisfaction", "excitement", "relief"]:
                score += 30
            # 镜头为 zoom_in 加分
            if dna.get("camera") in ["zoom_in", "closeup"]:
                score += 25
            # 动作为 upgrade/transform 加分
            if dna.get("action") in ["upgrade", "transform", "open"]:
                score += 25
            # 表现分
            score += dna.get("performance_score", 50) * 0.2

        return min(100, score / len(reward_segs))

    def _score_visual_density(self, plan: RemixPlan) -> float:
        """评分：视觉密度"""
        if not plan.segments:
            return 50.0

        # 计算平均视觉分
        avg_visual = np.mean([s.dna.get("visual_score", 50) for s in plan.segments])

        # 检查多样性
        subjects = set(s.dna.get("subject", "") for s in plan.segments)
        actions = set(s.dna.get("action", "") for s in plan.segments)
        diversity_bonus = min(20, len(subjects) * 5 + len(actions) * 3)

        return min(100, avg_visual + diversity_bonus)

    def _score_pacing(self, plan: RemixPlan) -> float:
        """评分：节奏感"""
        if len(plan.segments) < 2:
            return 50.0

        durations = [s.duration for s in plan.segments]
        total = sum(durations)

        if total == 0:
            return 50.0

        # 检查节奏变化（避免单调）
        duration_variance = np.var(durations)
        variance_score = min(30, duration_variance * 5)

        # 检查总时长
        duration_score = 0
        if 15 <= total <= 35:
            duration_score = 40
        elif 10 <= total <= 40:
            duration_score = 30
        else:
            duration_score = 15

        # 段数适当（3-6段）
        segment_score = 0
        if 3 <= len(plan.segments) <= 6:
            segment_score = 30
        else:
            segment_score = 15

        return min(100, variance_score + duration_score + segment_score)

    def _score_winner_similarity(self, plan: RemixPlan,
                                  target: Optional[WinningStructure]) -> float:
        """评分：与 Winner 结构的相似度"""
        if not target:
            return 70.0  # 默认中等

        # 比较角色序列
        plan_roles = [s.role for s in plan.segments]
        target_roles = [s.role for s in target.segments]

        if not plan_roles or not target_roles:
            return 50.0

        # 计算最长公共子序列的简化版
        matches = sum(1 for a, b in zip(plan_roles, target_roles) if a == b)
        max_len = max(len(plan_roles), len(target_roles))
        role_similarity = (matches / max_len) * 60 if max_len > 0 else 0

        # 时长相似度
        plan_duration = sum(s.duration for s in plan.segments)
        target_duration = target.total_duration
        duration_diff = abs(plan_duration - target_duration)
        duration_similarity = max(0, 40 - duration_diff * 2)

        return min(100, role_similarity + duration_similarity)

    def _determine_grade(self, score: float) -> str:
        """确定等级"""
        for grade, threshold in sorted(self.GRADE_THRESHOLDS.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return grade
        return "Reject"

    def filter_passed(self, plans: List[RemixPlan],
                      scores: List[QualityScore]) -> List[RemixPlan]:
        """过滤通过的方案"""
        return [p for p, s in zip(plans, scores) if s.passed]

    def get_grade_distribution(self, scores: List[QualityScore]) -> dict:
        """获取等级分布"""
        dist = {"S+": 0, "S": 0, "A": 0, "B": 0, "Reject": 0}
        for s in scores:
            dist[s.grade] += 1
        return dist

    def save_scores(self, scores: List[QualityScore], plans: List[RemixPlan],
                    output_path: Path):
        """保存评分结果"""
        data = {
            "evaluations": [
                {
                    "plan_id": p.plan_id,
                    "creative_id": p.creative_id,
                    "quality": s.to_dict(),
                }
                for p, s in zip(plans, scores)
            ],
            "grade_distribution": self.get_grade_distribution(scores),
            "pass_rate": sum(1 for s in scores if s.passed) / len(scores) if scores else 0,
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)