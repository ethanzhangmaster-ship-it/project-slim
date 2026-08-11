"""Shot Ranker V3.6.2 — Asset Intelligence Expansion

升级点：
  - Asset Diversity Score（素材池覆盖度 bonus）
  - Story Completeness 权重
  - Beat-specific 权重 V3.6.2
  - 更智能的角色匹配策略
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import VIDEO_SOURCE_DIR, MEMORY_DIR
from visual_intelligence.ranking_database import RankingDatabase
from intelligence.story_completeness import StoryCompletenessPredictor


@dataclass
class ShotCandidate:
    filepath: Path
    v_num: str
    width: int
    height: int
    duration: float
    content_type: str
    role_scores: Dict[str, float]
    top_roles: List[str]
    visual_impact: float = 0
    motion_score: float = 0
    gameplay_clarity: float = 0
    hook_score_v2: float = 0
    reward_score: float = 0
    dna_match: float = 0
    ad_value_score: float = 0
    story_score: float = 0
    diversity_bonus: float = 0
    overall_score: float = 0
    recommended_start: float = 0
    recommended_duration: float = 3.0


class ShotRankerV362:
    """V3.6.2 Shot Ranker — Asset Intelligence Expansion Layer"""

    # V3.6.2 Beat-specific 权重（更平衡）
    BEAT_WEIGHTS = {
        "hook": {
            "hook_score_v2": 0.35,
            "impact_score": 0.25,
            "motion_score": 0.20,
            "story_score": 0.10,
            "dna_match": 0.05,
            "ad_value": 0.05,
        },
        "gameplay": {
            "gameplay_clarity": 0.40,
            "motion_score": 0.20,
            "impact_score": 0.15,
            "story_score": 0.15,
            "ad_value": 0.07,
            "dna_match": 0.03,
        },
        "reward": {
            "reward_score": 0.35,
            "impact_score": 0.25,
            "story_score": 0.20,
            "motion_score": 0.10,
            "ad_value": 0.07,
            "dna_match": 0.03,
        },
        "cta": {
            "hook_score_v2": 0.20,
            "reward_score": 0.20,
            "impact_score": 0.20,
            "ad_value": 0.25,
            "story_score": 0.10,
            "dna_match": 0.05,
        },
        "problem": {
            "impact_score": 0.30,
            "motion_score": 0.20,
            "hook_score_v2": 0.15,
            "story_score": 0.20,
            "ad_value": 0.10,
            "dna_match": 0.05,
        },
    }

    # Diversity 配置
    DIVERSITY_CONFIG = {
        "min_pool_size_for_bonus": 5,
        "scarcity_threshold": 30,  # 素材数 < 30 认为稀缺
        "bonus_per_scarce_role": 8.0,
        "max_diversity_bonus": 20.0,
    }

    def __init__(self, game_code: str = "P04",
                 ranking_db_path: Optional[Path] = None):
        self.game_code = game_code
        self.dna = self._load_dna()
        self.shot_pool: List[ShotCandidate] = []
        self._ffprobe_cache: Dict[str, dict] = {}
        self._story_predictor = StoryCompletenessPredictor()
        self._pool_role_counts: Dict[str, int] = {}

        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_db = RankingDatabase(ranking_db_path)
        self._ranking_data: Dict[str, dict] = {}

    def _load_dna(self) -> Dict:
        dna_file = MEMORY_DIR / "winner_dna_v2.json"
        if dna_file.exists():
            try:
                with open(dna_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"theme": ["witch", "dragon", "castle"], "visual_style": ["dynamic"]}

    def _get_video_info(self, path: Path) -> dict:
        key = str(path)
        if key in self._ffprobe_cache:
            return self._ffprobe_cache[key]
        try:
            r = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "json", str(path)
            ], capture_output=True, text=True, timeout=10)
            s = json.loads(r.stdout).get("streams", [{}])[0]
            info = {"width": int(s.get("width", 0)), "height": int(s.get("height", 0)),
                    "duration": float(s.get("duration", 0) or 0)}
        except Exception:
            info = {"width": 0, "height": 0, "duration": 0}
        self._ffprobe_cache[key] = info
        return info

    def _infer_content_type(self, stem: str) -> str:
        s = stem.lower()
        if any(k in s for k in ["kaitou", "开场", "hook", "start"]):
            return "hook"
        if any(k in s for k in ["wanfa", "玩法", "gameplay", "merge", "play", "hecheng"]):
            return "gameplay"
        if any(k in s for k in ["juese", "角色", "reward", "character", "evol", "zhanshi"]):
            return "reward"
        if any(k in s for k in ["wenti", "问题", "problem", "challenge", "level", "boss"]):
            return "problem"
        if any(k in s for k in ["cta", "download", "结尾", "end"]):
            return "cta"
        return "mixed"

    def _load_ranking(self):
        for item in self.ranking_db.get_all():
            self._ranking_data[item.get("video_name", "")] = item

    def build_pool(self, source_dir: Optional[Path] = None,
                   min_duration: float = 2.5) -> List[ShotCandidate]:
        src = source_dir or VIDEO_SOURCE_DIR
        if not src.exists():
            return []

        self._load_ranking()

        candidates = []
        for vp in src.glob("*.mp4"):
            info = self._get_video_info(vp)
            if info["duration"] < min_duration or info["width"] == 0:
                continue
            stem = vp.stem
            ctype = self._infer_content_type(stem)
            rank = self._ranking_data.get(stem)

            if rank:
                role_scores = rank.get("role_scores", {})
                # 计算 story completeness
                story_result = self._story_predictor.predict(role_scores)

                c = ShotCandidate(
                    filepath=vp,
                    v_num=stem[:30],
                    width=info["width"],
                    height=info["height"],
                    duration=info["duration"],
                    content_type=ctype,
                    role_scores=role_scores,
                    top_roles=rank.get("top_roles", [ctype]),
                    visual_impact=rank.get("impact_score", 0),
                    motion_score=rank.get("motion_score", 0),
                    gameplay_clarity=rank.get("gameplay_clarity", 0),
                    hook_score_v2=rank.get("hook_score_v2", rank.get("hook_score", 0)),
                    reward_score=rank.get("reward_score", 0),
                    dna_match=rank.get("dna_score", 0),
                    ad_value_score=rank.get("ad_value_score", 0),
                    story_score=story_result.story_score,
                )
            else:
                c = ShotCandidate(
                    filepath=vp,
                    v_num=stem[:30],
                    width=info["width"],
                    height=info["height"],
                    duration=info["duration"],
                    content_type=ctype,
                    role_scores={},
                    top_roles=[ctype],
                    visual_impact=self._fallback_impact(info, stem),
                    motion_score=self._fallback_motion(info, stem),
                    gameplay_clarity=self._fallback_gameplay(info, stem),
                    hook_score_v2=self._fallback_hook(stem),
                    reward_score=self._fallback_reward(stem),
                    dna_match=self._fallback_dna(stem),
                    ad_value_score=30,
                    story_score=25,
                )
            candidates.append(c)

        # 计算素材池角色分布（用于 diversity bonus）
        self._calc_pool_distribution(candidates)

        # 为每个 candidate 计算 diversity bonus
        for c in candidates:
            c.diversity_bonus = self._calc_diversity_bonus(c)

        self.shot_pool = candidates
        print(f"[ShotRankerV362] Pool: {len(candidates)} shots | "
              f"Ranking hits: {sum(1 for c in candidates if c.hook_score_v2 > 0)} | "
              f"Story scored: {sum(1 for c in candidates if c.story_score > 0)}")
        return candidates

    def _calc_pool_distribution(self, candidates: List[ShotCandidate]) -> None:
        counts: Dict[str, int] = {}
        for c in candidates:
            for role in c.top_roles:
                counts[role] = counts.get(role, 0) + 1
        self._pool_role_counts = counts

    def _calc_diversity_bonus(self, candidate: ShotCandidate) -> float:
        """稀缺角色素材获得 diversity bonus。"""
        bonus = 0.0
        for role in candidate.top_roles:
            count = self._pool_role_counts.get(role, 0)
            if count < self.DIVERSITY_CONFIG["scarcity_threshold"]:
                bonus += self.DIVERSITY_CONFIG["bonus_per_scarce_role"]
        return min(bonus, self.DIVERSITY_CONFIG["max_diversity_bonus"])

    def _fallback_impact(self, info, stem): return 50
    def _fallback_motion(self, info, stem): return 50
    def _fallback_gameplay(self, info, stem): return 40
    def _fallback_hook(self, stem): return 30
    def _fallback_reward(self, stem): return 25
    def _fallback_dna(self, stem): return 30

    def select_for_beat(self, beat_role: str, beat_emotion: str,
                        beat_visual: str, target_duration: float,
                        exclude_paths: Optional[List[Path]] = None,
                        top_n: int = 1) -> List[Tuple[ShotCandidate, float, float]]:
        """V3.6.2 Beat 选择 — 加入 diversity + story completeness"""
        exclude_paths = exclude_paths or []
        exclude_set = {str(p) for p in exclude_paths}
        weights = self.BEAT_WEIGHTS.get(beat_role, self.BEAT_WEIGHTS["hook"])

        scored = []
        for shot in self.shot_pool:
            if str(shot.filepath) in exclude_set:
                continue

            # 多标签角色匹配 bonus
            role_bonus = 0
            if beat_role in shot.top_roles:
                role_bonus = 15
            elif beat_role in shot.role_scores and shot.role_scores[beat_role] >= 40:
                role_bonus = 10

            # V3.6.2: Beat-specific 加权评分 + diversity + story
            base = (
                shot.hook_score_v2 * weights.get("hook_score_v2", 0) +
                shot.gameplay_clarity * weights.get("gameplay_clarity", 0) +
                shot.reward_score * weights.get("reward_score", 0) +
                shot.visual_impact * weights.get("impact_score", 0) +
                shot.motion_score * weights.get("motion_score", 0) +
                shot.dna_match * weights.get("dna_match", 0) +
                shot.ad_value_score * weights.get("ad_value", 0) +
                shot.story_score * weights.get("story_score", 0) +
                shot.diversity_bonus * 0.5  # diversity 作为额外加分项
            )
            overall = base + role_bonus

            # 确定起止时间
            dur = min(target_duration, shot.duration * 0.9)
            if beat_role == "hook":
                start = min(1.0, max(0, shot.duration - dur - 1.0))
            elif beat_role == "reward":
                start = max(0, shot.duration - dur - 1.5)
            elif beat_role == "gameplay":
                start = shot.duration * 0.2
            else:
                start = shot.duration * 0.1
            start = max(0, min(start, shot.duration - dur - 0.1))
            dur = min(dur, shot.duration - start)

            shot.overall_score = overall
            shot.recommended_start = round(start, 2)
            shot.recommended_duration = round(dur, 2)
            scored.append((shot, overall))

        scored.sort(key=lambda x: -x[1])
        results = []
        for shot, _ in scored[:top_n]:
            results.append((shot, shot.recommended_start, shot.recommended_duration))
        return results

    def select_for_plan(self, beats: List,
                        avoid_duplicate_source: bool = True) -> Dict[str, List[Tuple[ShotCandidate, float, float]]]:
        selected = {}
        used_paths = []
        for beat in beats:
            top = self.select_for_beat(
                beat.role, beat.emotion_target, beat.visual_direction,
                beat.duration,
                exclude_paths=used_paths if avoid_duplicate_source else None,
                top_n=3
            )
            selected[beat.beat_id] = top
            if top and avoid_duplicate_source:
                used_paths.append(top[0][0].filepath)
        return selected
