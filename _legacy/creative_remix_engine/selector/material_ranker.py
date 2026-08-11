"""Material Ranking Engine V2 — 素材综合评分（V3.1升级）"""
import math
from typing import List, Dict
from collections import defaultdict

from ..models import PerformanceData, MaterialScore, SegmentScore, VideoAnalysis
from ..config import SCORE_WEIGHTS_V2, CONTENT_ROLE_MAP
from ..analyzer.video_intelligence_adapter import VideoIntelligenceAdapter
from ..selector.dna_matcher import DNAMatcher


class MaterialRanker:
    """V3.1: 替代旧版 ROAS 排序，升级为 Creative Material Score"""

    def __init__(self, performance_data: List[PerformanceData],
                 dna_matcher: DNAMatcher = None,
                 video_intel: VideoIntelligenceAdapter = None):
        self.data = {p.v_num: p for p in performance_data}
        self._used_count = defaultdict(int)
        self.dna_matcher = dna_matcher or DNAMatcher()
        self.video_intel = video_intel or VideoIntelligenceAdapter()

    def score_all(self, target_ratio: str = "9X16") -> Dict[str, List[MaterialScore]]:
        """
        按 DNA 角色分组评分
        返回: {role: [MaterialScore, ...]}
        """
        role_scores = defaultdict(list)

        for v_num, perf in self.data.items():
            if not perf.ratio or target_ratio not in perf.ratio:
                continue

            content = perf.content_type or "其他"
            roles = CONTENT_ROLE_MAP.get(content, ["hook"])

            # V3.1: DNA 匹配评分
            dna_match = self.dna_matcher.match(v_num, content, perf)

            # V3.1: Video Intelligence 最佳片段
            best_segment = None
            for role in roles:
                seg = self.video_intel.find_best_segment(v_num, role)
                if seg and (not best_segment or seg.overall > best_segment.overall):
                    best_segment = seg

            # 如果 Video Intelligence 没找到，回退到基于时长的估算
            if not best_segment:
                duration_sec = self._parse_duration(perf.duration)
                best_start = min(duration_sec * 0.2, 2.0) if duration_sec > 0 else 0
                best_dur = min(5.0, duration_sec * 0.6) if duration_sec > 0 else 3.0
                best_segment = SegmentScore(
                    start=best_start, duration=best_dur,
                    visual_impact=70, motion_score=65, emotion_score=70,
                    overall=68,
                )

            # 计算各维度分数 (0-100)
            roas_score = min(perf.roas * 25, 100)
            purchase_score = min(perf.purchase / max(perf.spend, 1) * 5000, 100)
            dna_match_score = dna_match.overall
            visual_quality_score = dna_match.visual_match
            freshness_score = 100 - min(self._used_count[v_num] * 10, 90)

            # V3.1 权重
            overall = (
                roas_score * SCORE_WEIGHTS_V2["roas"] +
                purchase_score * SCORE_WEIGHTS_V2["purchase_rate"] +
                dna_match_score * SCORE_WEIGHTS_V2["dna_match"] +
                visual_quality_score * SCORE_WEIGHTS_V2["visual_quality"] +
                freshness_score * SCORE_WEIGHTS_V2["freshness"]
            )

            for role in roles:
                score = MaterialScore(
                    v_num=v_num,
                    role=role,
                    roas_score=roas_score,
                    purchase_score=purchase_score,
                    dna_match_score=dna_match_score,
                    visual_quality_score=visual_quality_score,
                    freshness_score=freshness_score,
                    overall=overall,
                    best_segment=best_segment,
                )
                role_scores[role].append(score)

        # 每个角色内按 overall 降序
        for role in role_scores:
            role_scores[role].sort(key=lambda x: -x.overall)

        return dict(role_scores)

    def mark_used(self, v_num: str):
        """标记素材已使用（影响 freshness）"""
        self._used_count[v_num] += 1

    @staticmethod
    def _parse_duration(dur_str: str) -> float:
        try:
            return float(dur_str.lower().replace("s", "").strip())
        except:
            return 30.0
