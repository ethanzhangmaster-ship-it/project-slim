"""Shot Ranker — 综合评分，生成 Top Hook / Gameplay / Reward / CTA 排行榜"""
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ShotRanking:
    """单个视频的排名数据"""
    video_path: Path
    video_name: str
    motion_score: float = 0
    impact_score: float = 0
    gameplay_score: float = 0
    hook_score: float = 0
    reward_score: float = 0
    dna_score: float = 0
    final_score: float = 0
    gameplay_type: str = ""
    reward_types: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class ShotRanker:
    """镜头综合排名器"""

    # 默认权重
    DEFAULT_WEIGHTS = {
        "motion": 0.20,
        "impact": 0.25,
        "gameplay": 0.20,
        "hook": 0.20,
        "reward": 0.10,
        "dna": 0.05,
    }

    def __init__(self, dna_keywords: Optional[List[str]] = None):
        self.dna_keywords = dna_keywords or ["witch", "dragon", "castle"]
        self.rankings: List[ShotRanking] = []

    def add_shot(self, video_path: Path, scores: Dict) -> ShotRanking:
        """添加一个视频的评分数据"""
        name = video_path.stem
        dna_score = self._calc_dna_score(name)

        ranking = ShotRanking(
            video_path=video_path,
            video_name=name,
            motion_score=scores.get("motion_score", 0),
            impact_score=scores.get("impact_score", 0),
            gameplay_score=scores.get("gameplay_score", 0),
            hook_score=scores.get("hook_score", 0),
            reward_score=scores.get("reward_score", 0),
            dna_score=dna_score,
            gameplay_type=scores.get("gameplay_type", ""),
            reward_types=scores.get("reward_types", []),
        )

        # 计算最终得分
        ranking.final_score = self._calc_final_score(ranking)

        # 生成标签
        ranking.tags = self._generate_tags(ranking)

        self.rankings.append(ranking)
        return ranking

    def _calc_dna_score(self, name: str) -> float:
        """计算与 Winner DNA 的匹配分"""
        s = name.lower()
        score = 30
        theme_kw = {
            "witch": ["witch", "女巫", "magic", "spell", "wizard"],
            "dragon": ["dragon", "龙", "egg", "evolution", "evolve", "legendary"],
            "castle": ["castle", "城堡", "kingdom", "fortress", "base"],
        }
        for theme in self.dna_keywords:
            for kw in theme_kw.get(theme, []):
                if kw in s:
                    score += 25
                    break
        return min(100, score)

    def _calc_final_score(self, r: ShotRanking) -> float:
        w = self.DEFAULT_WEIGHTS
        return (
            r.motion_score * w["motion"] +
            r.impact_score * w["impact"] +
            r.gameplay_score * w["gameplay"] +
            r.hook_score * w["hook"] +
            r.reward_score * w["reward"] +
            r.dna_score * w["dna"]
        )

    def _generate_tags(self, r: ShotRanking) -> List[str]:
        tags = []
        if r.motion_score > 60:
            tags.append("high_motion")
        if r.impact_score > 60:
            tags.append("high_impact")
        if r.gameplay_score > 60:
            tags.append(f"gameplay:{r.gameplay_type}")
        if r.hook_score > 60:
            tags.append("strong_hook")
        if r.reward_score > 60:
            tags.append(f"reward:{r.reward_types[0]}" if r.reward_types else "reward")
        if r.dna_score > 60:
            tags.append("dna_match")
        return tags

    def get_top(self, role: str, top_n: int = 20) -> List[ShotRanking]:
        """
        获取某角色的 Top N。
        role: hook / gameplay / reward / cta / overall
        """
        if role == "hook":
            key = lambda r: r.hook_score
        elif role == "gameplay":
            key = lambda r: r.gameplay_score
        elif role == "reward":
            key = lambda r: r.reward_score
        elif role == "cta":
            # CTA 通常用 hook 或 reward 的高分素材
            key = lambda r: max(r.hook_score, r.reward_score) * 0.5 + r.impact_score * 0.5
        else:
            key = lambda r: r.final_score

        sorted_list = sorted(self.rankings, key=key, reverse=True)
        return sorted_list[:top_n]

    def get_ranking_dict(self) -> Dict:
        """导出全部排名数据为字典"""
        return {
            "total": len(self.rankings),
            "top_hook": [self._to_dict(r) for r in self.get_top("hook", 20)],
            "top_gameplay": [self._to_dict(r) for r in self.get_top("gameplay", 20)],
            "top_reward": [self._to_dict(r) for r in self.get_top("reward", 20)],
            "top_cta": [self._to_dict(r) for r in self.get_top("cta", 20)],
            "top_overall": [self._to_dict(r) for r in self.get_top("overall", 50)],
        }

    @staticmethod
    def _to_dict(r: ShotRanking) -> Dict:
        return {
            "video_name": r.video_name,
            "video_path": str(r.video_path),
            "motion_score": r.motion_score,
            "impact_score": r.impact_score,
            "gameplay_score": r.gameplay_score,
            "hook_score": r.hook_score,
            "reward_score": r.reward_score,
            "dna_score": r.dna_score,
            "final_score": round(r.final_score, 1),
            "gameplay_type": r.gameplay_type,
            "reward_types": r.reward_types,
            "tags": r.tags,
        }
