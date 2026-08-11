"""Winner DNA Shot Selector V3.8 — 基于 Buying Score 的智能素材选择

核心升级：
- 从视觉质量评分转向买量价值评分 (Buying Score)
- 结合 Winner DNA 相似度和 Archetype 匹配
- Performance Grade 分级筛选 (S+/S/A/B/Reject)
- 角色匹配 + Buying Score 双维度排序
"""
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from ..config import VIDEO_SOURCE_DIR, MEMORY_DIR
from ..winner_intelligence import (
    WinnerDNAExtractor,
    CreativeValuePredictor,
    PerformanceQualityGate,
    PerformanceGrade,
    ArchetypeDiscoveryEngine,
)


@dataclass
class V38ShotCandidate:
    """V3.8 Shot 候选"""
    filepath: Path
    v_num: str
    width: int
    height: int
    duration: float
    content_type: str
    role_scores: Dict[str, float] = field(default_factory=dict)
    top_roles: List[str] = field(default_factory=list)

    # V3.x 视觉指标
    visual_impact: float = 0
    motion_score: float = 0
    gameplay_clarity: float = 0
    hook_score_v2: float = 0
    reward_score: float = 0

    # V3.8 买量指标
    buying_score: float = 0
    predicted_ctr: float = 0
    predicted_cpi: float = 0
    predicted_d7_roi: float = 0
    performance_grade: str = "Reject"
    archetype: str = ""
    archetype_similarity: float = 0
    winner_dna_bonus: float = 0

    overall_score: float = 0
    recommended_start: float = 0
    recommended_duration: float = 3.0


class WinnerDNAShotSelectorV38:
    """V3.8 Winner DNA Shot Selector — 基于 Buying Score 排序"""

    # Beat 角色权重配置
    ROLE_BUYING_WEIGHTS = {
        "hook": 0.50,
        "gameplay": 0.45,
        "reward": 0.45,
        "problem": 0.35,
        "cta": 0.40,
    }

    ROLE_FIT_WEIGHTS = {
        "hook": 0.20,
        "gameplay": 0.25,
        "reward": 0.25,
        "problem": 0.20,
        "cta": 0.20,
    }

    QUALITY_BOOST_WEIGHT = 0.20
    ARCHETYPE_BONUS_WEIGHT = 0.10

    # Performance Grade 加分
    GRADE_BONUS = {
        "S+": 20,
        "S": 15,
        "A": 8,
        "B": 3,
        "Reject": 0,
    }

    def __init__(self, game_code: str = "P04",
                 ranking_db_path: Optional[Path] = None,
                 winner_db_path: Optional[Path] = None):
        self.game_code = game_code
        self.shot_pool: List[V38ShotCandidate] = []
        self._ffprobe_cache: Dict[str, dict] = {}

        if ranking_db_path is None:
            ranking_db_path = Path(
                "d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json"
            )
        self.ranking_db_path = ranking_db_path

        if winner_db_path is None:
            winner_db_path = MEMORY_DIR / "winner_database_v38.json"
        self.winner_db_path = winner_db_path

        # V3.8 智能引擎
        self.dna_extractor = WinnerDNAExtractor(ranking_db_path)
        self.value_predictor = CreativeValuePredictor(ranking_db_path, winner_db_path)
        self.quality_gate = PerformanceQualityGate(ranking_db_path, winner_db_path)
        self.archetype_engine = ArchetypeDiscoveryEngine(winner_db_path)
        self.archetype_engine.discover_archetypes()

        self._ranking_data: Dict[str, dict] = {}
        self._load_ranking()

    def _load_ranking(self):
        """加载 Ranking 数据"""
        if self.ranking_db_path.exists():
            try:
                with open(self.ranking_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self._ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

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
            info = {
                "width": int(s.get("width", 0)),
                "height": int(s.get("height", 0)),
                "duration": float(s.get("duration", 0) or 0),
            }
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

    def build_pool(self, source_dir: Optional[Path] = None,
                   min_duration: float = 2.5,
                   min_grade: str = "B") -> List[V38ShotCandidate]:
        """构建候选池（带 Performance Grade 筛选）"""
        src = source_dir or VIDEO_SOURCE_DIR
        if not src.exists():
            return []

        candidates = []
        video_files = list(src.glob("*.mp4"))

        for vp in video_files:
            info = self._get_video_info(vp)
            if info["duration"] < min_duration or info["width"] == 0:
                continue

            stem = vp.stem
            ctype = self._infer_content_type(stem)
            rank = self._ranking_data.get(stem, {})

            # 基础角色分数
            role_scores = rank.get("role_scores", {}) or {}
            top_roles = rank.get("top_roles", [ctype]) or [ctype]

            # V3.x 视觉指标
            hook_v2 = rank.get("hook_score_v2", rank.get("hook_score", 0))
            gameplay = rank.get("gameplay_clarity", 0)
            reward = rank.get("reward_score", 0)
            impact = rank.get("impact_score", 0)
            motion = rank.get("motion_score", 0)

            # V3.8: 计算 Buying Score
            buying_result = self.value_predictor.predict(stem)
            buying_score = buying_result["buying_score"]
            pred_ctr = buying_result["predicted_ctr"]
            pred_cpi = buying_result["predicted_cpi"]
            pred_roi = buying_result["predicted_d7_roi"]
            winner_bonus = buying_result["breakdown"].get("winner_bonus", 0)

            # V3.8: DNA 提取 + Archetype 匹配
            dna = self.dna_extractor.extract(stem)
            archetype_result = self.archetype_engine.classify_creative(dna)
            archetype = archetype_result["archetype"]
            archetype_sim = archetype_result["similarity"]

            # V3.8: Performance Grade 评估
            grade_result = self.quality_gate.evaluate(stem, dna)
            perf_grade = grade_result.grade

            c = V38ShotCandidate(
                filepath=vp,
                v_num=stem[:30],
                width=info["width"],
                height=info["height"],
                duration=info["duration"],
                content_type=ctype,
                role_scores=role_scores,
                top_roles=top_roles,
                visual_impact=impact,
                motion_score=motion,
                gameplay_clarity=gameplay,
                hook_score_v2=hook_v2,
                reward_score=reward,
                buying_score=buying_score,
                predicted_ctr=pred_ctr,
                predicted_cpi=pred_cpi,
                predicted_d7_roi=pred_roi,
                performance_grade=perf_grade,
                archetype=archetype,
                archetype_similarity=archetype_sim,
                winner_dna_bonus=winner_bonus,
            )
            candidates.append(c)

        # 按 Grade 筛选
        grade_order = {"S+": 0, "S": 1, "A": 2, "B": 3, "Reject": 4}
        min_rank = grade_order.get(min_grade, 3)
        filtered = [c for c in candidates if grade_order.get(c.performance_grade, 99) <= min_rank]

        self.shot_pool = filtered
        print(
            f"[V38 ShotSelector] Pool: {len(filtered)} shots "
            f"(total: {len(candidates)}, min_grade: {min_grade}) | "
            f"S+: {sum(1 for c in filtered if c.performance_grade == 'S+')} "
            f"S: {sum(1 for c in filtered if c.performance_grade == 'S')} "
            f"A: {sum(1 for c in filtered if c.performance_grade == 'A')} "
            f"B: {sum(1 for c in filtered if c.performance_grade == 'B')}"
        )
        return filtered

    def select_for_beat(self, beat_role: str, beat_emotion: str = "",
                        beat_visual: str = "", target_duration: float = 3.0,
                        exclude_paths: Optional[List[Path]] = None,
                        top_n: int = 1,
                        use_buying_score: bool = True) -> List[Tuple[V38ShotCandidate, float, float]]:
        """为 Story Beat 选择最佳镜头

        V3.8 评分公式：
        overall = buying_score * buying_weight + role_fit * role_weight + grade_bonus + archetype_bonus
        """
        exclude_paths = exclude_paths or []
        exclude_set = {str(p) for p in exclude_paths}

        buying_weight = self.ROLE_BUYING_WEIGHTS.get(beat_role, 0.40)
        role_weight = self.ROLE_FIT_WEIGHTS.get(beat_role, 0.20)
        quality_weight = self.QUALITY_BOOST_WEIGHT
        archetype_weight = self.ARCHETYPE_BONUS_WEIGHT

        scored = []
        for shot in self.shot_pool:
            if str(shot.filepath) in exclude_set:
                continue

            # 1. 角色匹配度
            role_fit = self._calc_role_fit(shot, beat_role, beat_emotion)

            # 2. Buying Score（V3.8 核心）
            if use_buying_score:
                buying_component = shot.buying_score * buying_weight
            else:
                # Fallback 到 V3.x 的 ad_value 模式
                buying_component = (shot.hook_score_v2 * 0.3 + shot.gameplay_clarity * 0.3 +
                                    shot.reward_score * 0.2 + shot.visual_impact * 0.2) * buying_weight

            # 3. 角色匹配
            role_component = role_fit * role_weight

            # 4. Performance Grade 加分
            grade_bonus = self.GRADE_BONUS.get(shot.performance_grade, 0) * quality_weight

            # 5. Archetype 加分（与高绩效模式的相似度）
            archetype_bonus = shot.archetype_similarity * archetype_weight * 0.2

            # 综合评分
            overall = buying_component + role_component + grade_bonus + archetype_bonus
            overall = min(100, max(0, overall))

            # 确定起止时间
            dur = min(target_duration, shot.duration * 0.9)
            start = self._calc_start_time(shot, beat_role, dur)

            scored.append((shot, overall, start))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_n]

    @staticmethod
    def _calc_role_fit(shot: V38ShotCandidate, beat_role: str, beat_emotion: str) -> float:
        """计算角色匹配度"""
        base = 0.0

        # Top roles 匹配
        if beat_role in shot.top_roles:
            base += 30

        # Role scores 匹配
        if beat_role in shot.role_scores:
            base += shot.role_scores[beat_role] * 0.5

        # Content type 匹配
        if shot.content_type == beat_role:
            base += 20
        elif shot.content_type == "mixed":
            base += 10

        return min(100, base)

    @staticmethod
    def _calc_start_time(shot: V38ShotCandidate, beat_role: str, dur: float) -> float:
        """计算起始时间"""
        if beat_role == "hook":
            start = min(1.0, max(0, shot.duration - dur - 1.0))
        elif beat_role == "reward":
            start = max(0, shot.duration - dur - 1.5)
        elif beat_role == "gameplay":
            start = shot.duration * 0.2
        else:
            start = shot.duration * 0.1
        return max(0, min(start, shot.duration - dur - 0.1))

    def get_top_by_role(self, role: str, top_n: int = 10,
                         use_buying_score: bool = True) -> List[V38ShotCandidate]:
        """按角色获取 Top 素材"""
        results = self.select_for_beat(
            beat_role=role,
            target_duration=3.0,
            top_n=top_n,
            use_buying_score=use_buying_score,
        )
        return [shot for shot, _, _ in results]

    def get_grade_distribution(self) -> Dict[str, int]:
        """获取素材池的 Performance Grade 分布"""
        distribution = {"S+": 0, "S": 0, "A": 0, "B": 0, "Reject": 0}
        for shot in self.shot_pool:
            distribution[shot.performance_grade] = distribution.get(shot.performance_grade, 0) + 1
        return distribution

    def get_archetype_distribution(self) -> Dict[str, int]:
        """获取 Archetype 分布"""
        distribution = {}
        for shot in self.shot_pool:
            arch = shot.archetype or "Unknown"
            distribution[arch] = distribution.get(arch, 0) + 1
        return dict(sorted(distribution.items(), key=lambda x: -x[1]))

    def get_avg_buying_score(self) -> float:
        """获取平均 Buying Score"""
        if not self.shot_pool:
            return 0.0
        return sum(s.buying_score for s in self.shot_pool) / len(self.shot_pool)
