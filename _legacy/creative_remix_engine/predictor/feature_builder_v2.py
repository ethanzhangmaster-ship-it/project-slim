"""Feature Builder V2 — 从多源数据构建特征向量"""
import csv
from pathlib import Path
from typing import List, Dict, Optional

from ..predictor.feature_schema import CreativeFeatureVector, MODEL_FEATURES
from ..models import RemixRecipe, PerformanceData, VideoAnalysis
from ..analyzer.video_intelligence_adapter import VideoIntelligenceAdapter
from ..selector.dna_matcher import DNAMatcher


class FeatureBuilderV2:
    """V3.2 特征工程：融合 Creative + Video Intelligence + DNA + Performance"""

    def __init__(self, video_intel: VideoIntelligenceAdapter = None,
                 dna_matcher: DNAMatcher = None):
        self.video_intel = video_intel or VideoIntelligenceAdapter()
        self.dna_matcher = dna_matcher or DNAMatcher()

    def build_from_recipe(self, recipe: RemixRecipe) -> CreativeFeatureVector:
        """从 Remix Recipe 构建特征"""
        feature = CreativeFeatureVector(creative_id=recipe.recipe_id)
        feature.duration = recipe.total_duration

        # 从 segments 聚合 Video Intelligence 特征（差异化！）
        for seg in recipe.segments:
            analysis = self.video_intel.load_analysis(seg.v_num)
            if analysis:
                if seg.role == "hook":
                    # V3.3: 使用segment实际评分，不是固定值
                    actual_score = seg.segment_score if seg.segment_score > 0 else 70
                    feature.hook_score = max(feature.hook_score, actual_score)
                elif seg.role == "gameplay":
                    actual_score = seg.segment_score if seg.segment_score > 0 else 65
                    feature.gameplay_score = max(feature.gameplay_score, actual_score)
                elif seg.role == "reward":
                    actual_score = seg.segment_score if seg.segment_score > 0 else 60
                    feature.reward_score = max(feature.reward_score, actual_score)

            # DNA match（差异化）
            dna = self.dna_matcher.match(seg.v_num, "", None)
            feature.dna_match = max(feature.dna_match, dna.overall)
            feature.theme_match = max(feature.theme_match, dna.theme_match)
            feature.visual_match = max(feature.visual_match, dna.visual_match)

        # 场景数
        feature.scene_count = len(recipe.segments)
        feature.scene_change_rate = feature.scene_count / max(feature.duration, 1)

        # V3.3: 基于实际segment分数计算其他特征
        feature.emotion_score = feature.hook_score * 0.85 + 10
        feature.motion_score = feature.gameplay_score * 0.8 + 10
        # 文字密度基于content_type估算
        has_text = any("文字" in str(s.filepath) for s in recipe.segments)
        feature.text_density = 0.08 if has_text else 0.02
        feature.contrast = 0.65 + (feature.hook_score / 1000)
        feature.saturation = 0.6 + (feature.gameplay_score / 1000)
        feature.color_score = 65 + feature.hook_score * 0.2
        feature.character_count = 2 + int(feature.reward_score / 40)

        return feature

    def build_from_performance(self, perf: PerformanceData) -> CreativeFeatureVector:
        """从 PerformanceData 构建训练特征"""
        feature = CreativeFeatureVector(
            creative_id=perf.creative_id,
            video_id=perf.v_num,
            duration=self._parse_duration(perf.duration),
            content_type=perf.content_type,
        )

        # Performance 标签
        feature.ctr = perf.ctr
        feature.cvr = perf.cvr
        feature.roas = perf.roas
        feature.purchase_rate = perf.purchase / max(perf.spend, 1) * 1000

        # Video Intelligence
        analysis = self.video_intel.load_analysis(perf.v_num)
        if analysis:
            best_hook = analysis.best_hook
            best_gameplay = analysis.best_gameplay
            best_reward = analysis.best_reward

            if best_hook:
                feature.hook_score = best_hook.hook_score
                feature.emotion_score = best_hook.emotion_score * 100
            if best_gameplay:
                feature.gameplay_score = best_gameplay.gameplay_score
                feature.motion_score = best_gameplay.motion_score * 100
            if best_reward:
                feature.reward_score = best_reward.reward_score

            feature.scene_count = len(analysis.scenes)
            feature.scene_change_rate = len(analysis.scenes) / max(analysis.duration, 1)

        # DNA Match
        dna = self.dna_matcher.match(perf.v_num, perf.content_type, perf)
        feature.dna_match = dna.overall
        feature.theme_match = dna.theme_match
        feature.visual_match = dna.visual_match

        # Visual 估算
        feature.text_density = 0.05 if "文字" in perf.content_type else 0.02
        feature.contrast = 0.7
        feature.saturation = 0.65
        feature.color_score = 75
        feature.character_count = 2 if "角色" in perf.content_type else 1

        return feature

    def build_training_set(self, performance_data: List[PerformanceData]) -> List[CreativeFeatureVector]:
        """构建完整训练集"""
        return [self.build_from_performance(p) for p in performance_data]

    @staticmethod
    def _parse_duration(dur_str: str) -> float:
        try:
            return float(str(dur_str).lower().replace("s", "").strip())
        except:
            return 30.0
