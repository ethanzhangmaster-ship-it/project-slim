"""E11.3.5 — Vision Intelligence Engine。

统一入口：Pattern Mining + Hook Analysis + Composition + Winner DNA。

Usage:
    engine = VisionIntelligenceEngine(feature_store, retrieval_engine)
    insight = engine.analyze(creative_asset_id="MW_WITCH_001")
    dna = engine.extract_winner_dna(winner_asset_ids=["MW_WIN_001", "MW_WIN_002"])
"""

from __future__ import annotations

import logging
from typing import Any

from ..feature_store.models import VisionFeatureRecord, VisionFrameFeature
from ..feature_store.store import VisionFeatureStore
from ..retrieval.retriever import VisionRetrievalEngine
from ..retrieval.models import SearchResult
from .models import (
    VisualPattern,
    HookAnalysis,
    CompositionAnalysis,
    VisionInsight,
    WinnerVisualDNA,
)
from .pattern_miner import PatternMiner
from .hook_analyzer import HookAnalyzer
from .dna_extractor import WinnerDNAExtractor

logger = logging.getLogger(__name__)


class VisionIntelligenceEngine:
    """视觉智能引擎。

    整合 Pattern Mining、Hook Analysis、Composition Analysis 和 Winner DNA Extraction。

    Attributes:
        store:        VisionFeatureStore（数据源）
        retriever:    VisionRetrievalEngine（相似检索）
        miner:        PatternMiner（模式挖掘）
        hook_analyzer: HookAnalyzer（Hook 分析）
        dna_extractor: WinnerDNAExtractor（DNA 提取）
    """

    def __init__(
        self,
        feature_store: VisionFeatureStore,
        retrieval_engine: VisionRetrievalEngine | None = None,
    ) -> None:
        self._store = feature_store
        self._retriever = retrieval_engine
        self._miner = PatternMiner()
        self._hook_analyzer = HookAnalyzer()
        self._dna_extractor = WinnerDNAExtractor()

        self._analyzed_count: int = 0

    # ── Analyze ──────────────────────────────────────────

    def analyze(self, creative_asset_id: str) -> VisionInsight | None:
        """对单个素材进行完整视觉分析。

        Args:
            creative_asset_id: 素材 ID

        Returns:
            VisionInsight 或 None
        """
        record = self._store.get(creative_asset_id)
        if record is None:
            logger.warning(
                f"VisionIntelligenceEngine: asset not found: {creative_asset_id}"
            )
            return None

        # 获取帧数据
        frames = self._store.get_frames(record.feature_id)

        # 模式挖掘
        visual_patterns = self._miner.mine(record, frames)

        # Hook 分析
        hook_analysis = None
        if frames and len(frames) >= 2:
            hook_analysis = self._hook_analyzer.analyze(frames)

        # 构图分析
        composition_analysis = self._analyze_composition(record)

        # Winner 概率
        winner_probability = self._estimate_winner_probability(
            creative_asset_id, record, visual_patterns
        )

        # 与 Winner 的相似度
        similarity_to_winners = self._compute_winner_similarity(
            creative_asset_id
        )

        # 生成总结
        summary = self._generate_summary(
            visual_patterns, hook_analysis, composition_analysis
        )

        self._analyzed_count += 1

        return VisionInsight(
            creative_asset_id=creative_asset_id,
            visual_patterns=visual_patterns,
            hook_analysis=hook_analysis,
            composition_analysis=composition_analysis,
            winner_probability=winner_probability,
            similarity_to_winners=similarity_to_winners,
            summary=summary,
        )

    def analyze_batch(
        self, creative_asset_ids: list[str]
    ) -> dict[str, VisionInsight | None]:
        """批量分析素材。"""
        return {
            aid: self.analyze(aid) for aid in creative_asset_ids
        }

    # ── Winner DNA ───────────────────────────────────────

    def extract_winner_dna(
        self,
        creative_asset_ids: list[str],
    ) -> WinnerVisualDNA:
        """从多个 Winner 素材中提取视觉 DNA。

        Args:
            creative_asset_ids: Winner 素材 ID 列表

        Returns:
            WinnerVisualDNA
        """
        records: list[VisionFeatureRecord] = []
        frames_map: dict[str, list[VisionFrameFeature]] = {}

        for asset_id in creative_asset_ids:
            record = self._store.get(asset_id)
            if record is None:
                logger.warning(
                    f"VisionIntelligenceEngine: winner not found: {asset_id}"
                )
                continue
            records.append(record)
            frames = self._store.get_frames(record.feature_id)
            if frames:
                frames_map[record.feature_id] = frames

        return self._dna_extractor.extract(records, frames_map)

    def extract_winner_dna_from_records(
        self,
        records: list[VisionFeatureRecord],
    ) -> WinnerVisualDNA:
        """从 VisionFeatureRecord 列表中提取视觉 DNA。"""
        frames_map: dict[str, list[VisionFrameFeature]] = {}
        for record in records:
            frames = self._store.get_frames(record.feature_id)
            if frames:
                frames_map[record.feature_id] = frames
        return self._dna_extractor.extract(records, frames_map)

    # ── Mine Patterns ────────────────────────────────────

    def mine_patterns(
        self,
        records: list[VisionFeatureRecord],
    ) -> dict[str, list[VisualPattern]]:
        """从多个记录中挖掘模式。"""
        frames_map: dict[str, list[VisionFrameFeature]] = {}
        for record in records:
            frames = self._store.get_frames(record.feature_id)
            if frames:
                frames_map[record.feature_id] = frames
        return self._miner.mine_batch(records, frames_map)

    # ── Stats ────────────────────────────────────────────

    @property
    def analyzed_count(self) -> int:
        return self._analyzed_count

    # ── Internal ────────────────────────────────────────

    def _analyze_composition(
        self, record: VisionFeatureRecord
    ) -> CompositionAnalysis:
        """分析构图。"""
        # 构图类型
        if record.avg_edge_density < 0.15:
            comp_type = "single_subject"
        elif record.avg_edge_density > 0.4:
            comp_type = "complex"
        else:
            comp_type = "multi_subject"

        # 色彩方案
        if record.avg_saturation > 0.5 and record.avg_brightness > 0.5:
            palette = "bright_saturated"
        elif record.avg_brightness < 0.3:
            palette = "dark_muted"
        else:
            palette = "neutral"

        # 运动类型
        if record.avg_edge_density > 0.35:
            motion = "fast_transition"
        elif record.avg_edge_density > 0.2:
            motion = "slow_pan"
        else:
            motion = "static"

        # 主体数量估计
        if comp_type == "single_subject":
            subject_count = 1
        elif comp_type == "complex":
            subject_count = 5
        else:
            subject_count = 3

        return CompositionAnalysis(
            composition_type=comp_type,
            subject_count=subject_count,
            color_palette=palette,
            motion_type=motion,
            avg_edge_density=record.avg_edge_density,
            avg_color_entropy=record.avg_color_entropy,
            avg_saturation=record.avg_saturation,
            description=f"{comp_type} composition with {palette} colors, {motion} motion",
        )

    def _estimate_winner_probability(
        self,
        asset_id: str,
        record: VisionFeatureRecord,
        patterns: list[VisualPattern],
    ) -> float:
        """估算 Winner 概率。

        基于：
          - hook_score + reward_score
          - 检测到的 Winner 模式数量
          - 相似 Winner 数量
        """
        # 基础概率：hook + reward 平均
        base = (record.hook_score + record.reward_score) / 2

        # 模式加成：每检测到一个 Winner 模式 +0.05
        pattern_bonus = min(len(patterns) * 0.05, 0.2)

        # 相似度加成
        similarity = self._compute_winner_similarity(asset_id)
        similarity_bonus = similarity * 0.15

        probability = base * 0.65 + pattern_bonus + similarity_bonus
        return round(min(max(probability, 0.0), 1.0), 3)

    def _compute_winner_similarity(self, asset_id: str) -> float:
        """计算与 Winner 的相似度。"""
        if self._retriever is None:
            return 0.0

        results = self._retriever.find_similar_asset(asset_id, top_k=5)
        if not results:
            return 0.0

        winner_results = [r for r in results if r.is_winner]
        if not winner_results:
            return 0.0

        return round(
            sum(r.similarity for r in winner_results) / len(winner_results), 3
        )

    @staticmethod
    def _generate_summary(
        patterns: list[VisualPattern],
        hook: HookAnalysis | None,
        composition: CompositionAnalysis | None,
    ) -> str:
        parts: list[str] = []

        if hook:
            parts.append(f"Hook: {hook.description}")
        if composition:
            parts.append(f"Composition: {composition.description}")
        if patterns:
            pattern_names = [p.name for p in patterns[:3]]
            parts.append(f"Patterns: {', '.join(pattern_names)}")

        return " | ".join(parts) if parts else "No significant visual patterns detected"

    def __repr__(self) -> str:
        return (
            f"VisionIntelligenceEngine(analyzed={self._analyzed_count})"
        )