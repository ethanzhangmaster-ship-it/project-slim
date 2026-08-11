"""E11.3.5 — Vision Intelligence 测试。

测试范围：
  - VisualPattern: 数据模型 + 序列化
  - HookAnalysis: 数据模型 + 序列化
  - CompositionAnalysis: 数据模型 + 序列化
  - VisionInsight: 数据模型 + 序列化
  - WinnerVisualDNA: 数据模型 + 序列化
  - PatternMiner: 规则模式挖掘 + 聚合
  - HookAnalyzer: 前帧 Hook 分析
  - WinnerDNAExtractor: Winner DNA 提取
  - VisionIntelligenceEngine: 完整分析 + Winner DNA
  - Integration: FeatureStore → Engine → Insight → DNA
"""
from __future__ import annotations

from pathlib import Path

import pytest

from market_ops.creative_vision_runtime.feature_store.models import (
    VisionFeatureRecord,
    VisionFrameFeature,
)
from market_ops.creative_vision_runtime.feature_store.store import (
    VisionFeatureStore,
)
from market_ops.creative_vision_runtime.retrieval.retriever import (
    VisionRetrievalEngine,
)
from market_ops.creative_vision_runtime.intelligence.models import (
    VisualPattern,
    HookAnalysis,
    CompositionAnalysis,
    VisionInsight,
    WinnerVisualDNA,
)
from market_ops.creative_vision_runtime.intelligence.pattern_miner import (
    PatternMiner,
)
from market_ops.creative_vision_runtime.intelligence.hook_analyzer import (
    HookAnalyzer,
)
from market_ops.creative_vision_runtime.intelligence.dna_extractor import (
    WinnerDNAExtractor,
)
from market_ops.creative_vision_runtime.intelligence.engine import (
    VisionIntelligenceEngine,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _make_record(
    asset_id: str = "MW_VID_001",
    hook: float = 0.82,
    comp: float = 0.65,
    reward: float = 0.71,
    brightness: float = 0.61,
    contrast: float = 0.45,
    edge: float = 0.33,
    saturation: float = 0.55,
    entropy: float = 6.2,
    is_winner: bool = False,
    lifecycle: str = "TESTING",
    duration: float = 30.0,
) -> VisionFeatureRecord:
    return VisionFeatureRecord(
        creative_asset_id=asset_id,
        video_path=f"Y:/Eagle/{asset_id}.mp4",
        eagle_filename=f"{asset_id}.mp4",
        frame_count=6,
        duration_seconds=duration,
        resolution=(1920, 1080),
        hook_score=hook,
        comprehension_score=comp,
        reward_score=reward,
        avg_brightness=brightness,
        avg_contrast=contrast,
        avg_edge_density=edge,
        avg_saturation=saturation,
        avg_color_entropy=entropy,
        metric={"roas": 3.0} if is_winner else {"roas": 0.8},
        lifecycle_status=lifecycle,
        is_winner=is_winner,
    )


def _make_frames(
    feature_id: str = "vfr_001",
    brightness_vals: list[float] | None = None,
    contrast_vals: list[float] | None = None,
    edge_vals: list[float] | None = None,
    saturation_vals: list[float] | None = None,
    entropy_vals: list[float] | None = None,
    n: int = 6,
) -> list[VisionFrameFeature]:
    if brightness_vals is None:
        brightness_vals = [0.4 + i * 0.1 for i in range(n)]
    if contrast_vals is None:
        contrast_vals = [0.3 + i * 0.05 for i in range(n)]
    if edge_vals is None:
        edge_vals = [0.15] * n
    if saturation_vals is None:
        saturation_vals = [0.5] * n
    if entropy_vals is None:
        entropy_vals = [6.0] * n

    return [
        VisionFrameFeature(
            feature_id=feature_id,
            frame_index=i,
            timestamp_sec=i * 5.0,
            frame_path=f"/tmp/frame_{i:03d}.jpg",
            brightness=brightness_vals[i] if i < len(brightness_vals) else 0.5,
            contrast=contrast_vals[i] if i < len(contrast_vals) else 0.3,
            edge_density=edge_vals[i] if i < len(edge_vals) else 0.15,
            saturation=saturation_vals[i] if i < len(saturation_vals) else 0.5,
            color_entropy=entropy_vals[i] if i < len(entropy_vals) else 6.0,
        )
        for i in range(n)
    ]


def _make_store(tmp_path: Path) -> VisionFeatureStore:
    return VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))


# ════════════════════════════════════════════════════════════════════
# VisualPattern
# ════════════════════════════════════════════════════════════════════

class TestVisualPattern:
    """VisualPattern 数据模型测试。"""

    def test_create(self):
        p = VisualPattern(
            name="high_contrast_opening",
            description="High contrast visual opening",
            confidence=0.82,
            category="opening",
            evidence_count=1,
            source_assets=["MW_VID_001"],
        )
        assert p.pattern_id.startswith("vp_")
        assert p.name == "high_contrast_opening"
        assert p.confidence == 0.82

    def test_to_dict(self):
        p = VisualPattern(
            name="bright_visual",
            confidence=0.75,
            category="color",
            feature_values={"avg_brightness": 0.7},
        )
        d = p.to_dict()
        assert d["name"] == "bright_visual"
        assert d["feature_values"]["avg_brightness"] == 0.7

    def test_from_dict(self):
        data = {
            "pattern_id": "vp_test",
            "name": "clean_composition",
            "description": "Clean composition",
            "confidence": 0.6,
            "category": "composition",
            "evidence_count": 3,
            "source_assets": ["A", "B", "C"],
        }
        p = VisualPattern.from_dict(data)
        assert p.pattern_id == "vp_test"
        assert p.evidence_count == 3
        assert p.source_assets == ["A", "B", "C"]

    def test_repr(self):
        p = VisualPattern(name="test", confidence=0.7, category="color")
        r = repr(p)
        assert "test" in r
        assert "0.70" in r


# ════════════════════════════════════════════════════════════════════
# HookAnalysis
# ════════════════════════════════════════════════════════════════════

class TestHookAnalysis:
    """HookAnalysis 数据模型测试。"""

    def test_create(self):
        h = HookAnalysis(
            hook_strength=0.82,
            opening_type="instant_reward",
            visual_transition="high",
        )
        assert h.hook_strength == 0.82
        assert h.opening_type == "instant_reward"

    def test_to_dict(self):
        h = HookAnalysis(
            hook_strength=0.75,
            opening_type="motion",
            brightness_trend="rising",
            frame_by_frame=[{"frame_index": 0, "brightness": 0.5}],
            description="fast opening",
        )
        d = h.to_dict()
        assert d["hook_strength"] == 0.75
        assert d["brightness_trend"] == "rising"
        assert len(d["frame_by_frame"]) == 1

    def test_repr(self):
        h = HookAnalysis(hook_strength=0.82, opening_type="instant_reward")
        assert "0.82" in repr(h)


# ════════════════════════════════════════════════════════════════════
# CompositionAnalysis
# ════════════════════════════════════════════════════════════════════

class TestCompositionAnalysis:
    """CompositionAnalysis 数据模型测试。"""

    def test_create(self):
        c = CompositionAnalysis(
            composition_type="single_subject",
            color_palette="bright_saturated",
            motion_type="fast_transition",
        )
        assert c.composition_type == "single_subject"
        assert c.color_palette == "bright_saturated"

    def test_to_dict(self):
        c = CompositionAnalysis(
            composition_type="multi_subject",
            subject_count=3,
            color_palette="neutral",
            avg_edge_density=0.25,
            description="test",
        )
        d = c.to_dict()
        assert d["subject_count"] == 3
        assert d["avg_edge_density"] == 0.25

    def test_repr(self):
        c = CompositionAnalysis(composition_type="single_subject", color_palette="bright_saturated")
        assert "single_subject" in repr(c)


# ════════════════════════════════════════════════════════════════════
# VisionInsight
# ════════════════════════════════════════════════════════════════════

class TestVisionInsight:
    """VisionInsight 数据模型测试。"""

    def test_create_empty(self):
        vi = VisionInsight(creative_asset_id="MW_VID_001")
        assert vi.insight_id.startswith("vi_")
        assert vi.visual_patterns == []

    def test_create_full(self):
        patterns = [
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
            VisualPattern(name="bright_visual", confidence=0.7, category="color"),
        ]
        hook = HookAnalysis(hook_strength=0.82, opening_type="instant_reward")
        comp = CompositionAnalysis(composition_type="single_subject", color_palette="bright_saturated")

        vi = VisionInsight(
            creative_asset_id="MW_VID_001",
            visual_patterns=patterns,
            hook_analysis=hook,
            composition_analysis=comp,
            winner_probability=0.75,
            similarity_to_winners=0.85,
            summary="Strong visual pattern",
        )
        assert len(vi.visual_patterns) == 2
        assert vi.winner_probability == 0.75

    def test_to_dict(self):
        vi = VisionInsight(
            creative_asset_id="MW_VID_001",
            visual_patterns=[VisualPattern(name="test", confidence=0.5, category="color")],
            winner_probability=0.6,
        )
        d = vi.to_dict()
        assert d["creative_asset_id"] == "MW_VID_001"
        assert len(d["visual_patterns"]) == 1

    def test_repr(self):
        vi = VisionInsight(
            creative_asset_id="MW_VID_001",
            visual_patterns=[VisualPattern(name="test", confidence=0.5, category="color")],
            winner_probability=0.6,
        )
        r = repr(vi)
        assert "MW_VID_001" in r
        assert "0.60" in r


# ════════════════════════════════════════════════════════════════════
# WinnerVisualDNA
# ════════════════════════════════════════════════════════════════════

class TestWinnerVisualDNA:
    """WinnerVisualDNA 数据模型测试。"""

    def test_create(self):
        dna = WinnerVisualDNA(
            source_count=5,
            source_assets=["MW_WIN_001", "MW_WIN_002"],
            opening="high_contrast_center_focus",
            composition="single_subject",
            color="bright_saturated",
            motion="fast_transition",
        )
        assert dna.dna_id.startswith("wdna_")
        assert dna.source_count == 5

    def test_to_dict(self):
        dna = WinnerVisualDNA(
            source_count=3,
            opening="high_contrast",
            composition="single_subject",
            color="bright_saturated",
            motion="fast_transition",
            aggregated_metrics={"avg_hook_score": 0.85},
            description="Winner DNA",
        )
        d = dna.to_dict()
        assert d["source_count"] == 3
        assert d["aggregated_metrics"]["avg_hook_score"] == 0.85

    def test_repr(self):
        dna = WinnerVisualDNA(
            source_count=3,
            opening="high_contrast",
        )
        assert "3" in repr(dna)
        assert "high_contrast" in repr(dna)


# ════════════════════════════════════════════════════════════════════
# PatternMiner
# ════════════════════════════════════════════════════════════════════

class TestPatternMiner:
    """PatternMiner 模式挖掘测试。"""

    @pytest.fixture
    def miner(self):
        return PatternMiner()

    def test_high_contrast_detected(self, miner):
        record = _make_record("MW_VID_001", contrast=0.65)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "high_contrast_opening" in names

    def test_high_contrast_not_detected(self, miner):
        record = _make_record("MW_VID_001", contrast=0.3)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "high_contrast_opening" not in names

    def test_bright_visual_detected(self, miner):
        record = _make_record("MW_VID_001", brightness=0.75)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "bright_visual" in names

    def test_dark_visual_detected(self, miner):
        record = _make_record("MW_VID_001", brightness=0.2)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "dark_visual" in names

    def test_clean_composition_detected(self, miner):
        record = _make_record("MW_VID_001", edge=0.3, entropy=4.0)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "clean_composition" in names

    def test_clean_composition_not_detected_high_entropy(self, miner):
        record = _make_record("MW_VID_001", edge=0.3, entropy=8.0)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "clean_composition" not in names

    def test_complex_scene_detected(self, miner):
        record = _make_record("MW_VID_001", edge=0.5)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "complex_scene" in names

    def test_high_saturation_detected(self, miner):
        record = _make_record("MW_VID_001", saturation=0.7)
        patterns = miner.mine(record)
        names = {p.name for p in patterns}
        assert "high_saturation" in names

    def test_fast_visual_change_detected(self, miner):
        record = _make_record("MW_VID_001")
        frames = _make_frames(edge_vals=[0.1, 0.1, 0.3, 0.3, 0.5, 0.5])
        patterns = miner.mine(record, frames)
        names = {p.name for p in patterns}
        assert "fast_visual_change" in names

    def test_fast_visual_change_not_detected(self, miner):
        record = _make_record("MW_VID_001")
        frames = _make_frames(edge_vals=[0.15, 0.15, 0.15, 0.15, 0.15, 0.15])
        patterns = miner.mine(record, frames)
        names = {p.name for p in patterns}
        assert "fast_visual_change" not in names

    def test_rising_brightness_detected(self, miner):
        frames = _make_frames(brightness_vals=[0.2, 0.35, 0.5, 0.65, 0.8, 0.9])
        patterns = miner.mine(_make_record(), frames)
        names = {p.name for p in patterns}
        assert "rising_brightness" in names

    def test_rising_brightness_not_detected(self, miner):
        frames = _make_frames(brightness_vals=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        patterns = miner.mine(_make_record(), frames)
        names = {p.name for p in patterns}
        assert "rising_brightness" not in names

    def test_mine_batch(self, miner):
        records = [
            _make_record("MW_VID_001", contrast=0.65, brightness=0.75),
            _make_record("MW_VID_002", contrast=0.3, brightness=0.2),
        ]
        result = miner.mine_batch(records)
        assert len(result) == 2
        assert "high_contrast_opening" in {p.name for p in result["MW_VID_001"]}

    def test_aggregate_patterns(self, miner):
        patterns = [
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening",
                          source_assets=["A"], evidence_count=1),
            VisualPattern(name="high_contrast_opening", confidence=0.7, category="opening",
                          source_assets=["B"], evidence_count=1),
            VisualPattern(name="bright_visual", confidence=0.6, category="color",
                          source_assets=["A"], evidence_count=1),
        ]
        aggregated = miner.aggregate_patterns(patterns)
        assert len(aggregated) == 2
        # 高置信度的应该排在前面
        assert aggregated[0].name == "high_contrast_opening"
        assert aggregated[0].evidence_count == 2

    def test_aggregate_min_confidence_filter(self, miner):
        patterns = [
            VisualPattern(name="high_contrast", confidence=0.8, category="opening"),
            VisualPattern(name="low_conf", confidence=0.2, category="color"),
        ]
        aggregated = miner.aggregate_patterns(patterns, min_confidence=0.5)
        assert len(aggregated) == 1
        assert aggregated[0].name == "high_contrast"

    def test_repr(self, miner):
        assert "PatternMiner" in repr(miner)


# ════════════════════════════════════════════════════════════════════
# HookAnalyzer
# ════════════════════════════════════════════════════════════════════

class TestHookAnalyzer:
    """HookAnalyzer 开头分析测试。"""

    @pytest.fixture
    def analyzer(self):
        return HookAnalyzer()

    def test_instant_reward(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.85, 0.8, 0.75],
            contrast_vals=[0.65, 0.6, 0.55],
            saturation_vals=[0.7, 0.65, 0.6],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.opening_type == "instant_reward"
        assert result.hook_strength >= 0.5

    def test_curiosity(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.4, 0.45, 0.5],
            contrast_vals=[0.3, 0.3, 0.35],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.opening_type == "curiosity"

    def test_motion(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.5, 0.5, 0.5],
            contrast_vals=[0.3, 0.3, 0.3],
            edge_vals=[0.5, 0.5, 0.5],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.opening_type == "motion"

    def test_rising_trend(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.3, 0.5, 0.7],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.brightness_trend == "rising"

    def test_stable_trend(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.5, 0.52, 0.48],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.brightness_trend == "stable"

    def test_falling_trend(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.7, 0.5, 0.3],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.brightness_trend == "falling"

    def test_high_transition(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.2, 0.5, 0.8],
            contrast_vals=[0.2, 0.5, 0.8],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.visual_transition == "high"

    def test_low_transition(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.5, 0.5, 0.5],
            contrast_vals=[0.3, 0.3, 0.3],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert result.visual_transition == "low"

    def test_insufficient_frames(self, analyzer):
        frames = _make_frames(n=1)
        result = analyzer.analyze(frames)
        assert result.hook_strength == 0.0
        assert result.opening_type == "calm"

    def test_frame_by_frame(self, analyzer):
        frames = _make_frames(n=3)
        result = analyzer.analyze(frames)
        assert len(result.frame_by_frame) == 3
        assert result.frame_by_frame[0]["frame_index"] == 0

    def test_hook_strength_range(self, analyzer):
        frames = _make_frames(n=3)
        result = analyzer.analyze(frames)
        assert 0 <= result.hook_strength <= 1

    def test_description(self, analyzer):
        frames = _make_frames(
            brightness_vals=[0.8, 0.7, 0.6],
            contrast_vals=[0.6, 0.5, 0.5],
            n=3,
        )
        result = analyzer.analyze(frames)
        assert len(result.description) > 0

    def test_repr(self, analyzer):
        assert "HookAnalyzer" in repr(analyzer)


# ════════════════════════════════════════════════════════════════════
# WinnerDNAExtractor
# ════════════════════════════════════════════════════════════════════

class TestWinnerDNAExtractor:
    """WinnerDNAExtractor DNA 提取测试。"""

    @pytest.fixture
    def extractor(self):
        return WinnerDNAExtractor()

    def test_extract_empty(self, extractor):
        dna = extractor.extract([])
        assert dna.source_count == 0

    def test_extract_single_winner(self, extractor):
        records = [_make_record("MW_WIN_001", hook=0.9, contrast=0.65, brightness=0.75,
                                saturation=0.7, is_winner=True)]
        dna = extractor.extract(records)
        assert dna.source_count == 1
        assert dna.opening == "high_contrast_center_focus"
        assert dna.color == "bright_saturated"

    def test_extract_multiple_winners(self, extractor):
        records = [
            _make_record("MW_WIN_001", hook=0.9, contrast=0.65, brightness=0.75, is_winner=True),
            _make_record("MW_WIN_002", hook=0.88, contrast=0.6, brightness=0.7, is_winner=True),
            _make_record("MW_WIN_003", hook=0.85, contrast=0.62, brightness=0.72, is_winner=True),
        ]
        dna = extractor.extract(records)
        assert dna.source_count == 3
        assert len(dna.source_assets) == 3
        assert len(dna.patterns) > 0

    def test_extract_with_frames(self, extractor):
        records = [_make_record("MW_WIN_001", is_winner=True)]
        frames_map = {records[0].feature_id: _make_frames(feature_id=records[0].feature_id)}
        dna = extractor.extract(records, frames_map)
        assert dna.source_count == 1
        assert len(dna.patterns) > 0

    def test_extract_aggregated_metrics(self, extractor):
        records = [
            _make_record("MW_WIN_001", hook=0.9, reward=0.85, brightness=0.7, contrast=0.6, is_winner=True),
            _make_record("MW_WIN_002", hook=0.8, reward=0.75, brightness=0.6, contrast=0.5, is_winner=True),
        ]
        dna = extractor.extract(records)
        assert dna.aggregated_metrics["avg_hook_score"] == pytest.approx(0.85, abs=0.01)
        assert dna.aggregated_metrics["avg_reward_score"] == pytest.approx(0.80, abs=0.01)

    def test_extract_description(self, extractor):
        records = [_make_record("MW_WIN_001", is_winner=True)]
        dna = extractor.extract(records)
        assert len(dna.description) > 0
        assert "Winner DNA" in dna.description

    def test_extract_low_contrast_winner(self, extractor):
        records = [_make_record("MW_WIN_001", contrast=0.3, brightness=0.45, is_winner=True)]
        dna = extractor.extract(records)
        assert dna.opening != "high_contrast_center_focus"

    def test_repr(self, extractor):
        assert "WinnerDNAExtractor" in repr(extractor)


# ════════════════════════════════════════════════════════════════════
# VisionIntelligenceEngine
# ════════════════════════════════════════════════════════════════════

class TestVisionIntelligenceEngine:
    """VisionIntelligenceEngine 完整分析测试。"""

    @pytest.fixture
    def engine(self, tmp_path):
        store = _make_store(tmp_path)
        return VisionIntelligenceEngine(feature_store=store)

    def _populate(self, engine, store):
        """填充 store 数据。"""
        records = [
            _make_record("MW_WIN_001", hook=0.9, contrast=0.65, brightness=0.75,
                         saturation=0.7, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_002", hook=0.88, contrast=0.6, brightness=0.7,
                         is_winner=True, lifecycle="WINNER"),
            _make_record("MW_LOSE_001", hook=0.3, contrast=0.2, brightness=0.25,
                         is_winner=False),
        ]
        for r in records:
            store._repo.save_record(r)
            frames = _make_frames(feature_id=r.feature_id)
            store._repo.save_frames(r.feature_id, frames)

    def test_analyze(self, engine):
        store = engine._store
        self._populate(engine, store)

        insight = engine.analyze("MW_WIN_001")
        assert insight is not None
        assert insight.creative_asset_id == "MW_WIN_001"
        assert len(insight.visual_patterns) > 0
        assert insight.hook_analysis is not None
        assert insight.composition_analysis is not None
        assert len(insight.summary) > 0

    def test_analyze_not_found(self, engine):
        insight = engine.analyze("NONEXISTENT")
        assert insight is None

    def test_analyze_winner_probability(self, engine):
        store = engine._store
        self._populate(engine, store)

        insight = engine.analyze("MW_WIN_001")
        assert insight is not None
        assert 0 <= insight.winner_probability <= 1

    def test_analyze_batch(self, engine):
        store = engine._store
        self._populate(engine, store)

        results = engine.analyze_batch(["MW_WIN_001", "MW_LOSE_001"])
        assert len(results) == 2
        assert results["MW_WIN_001"] is not None
        assert results["MW_LOSE_001"] is not None

    def test_extract_winner_dna(self, engine):
        store = engine._store
        self._populate(engine, store)

        dna = engine.extract_winner_dna(["MW_WIN_001", "MW_WIN_002"])
        assert dna.source_count == 2
        assert len(dna.source_assets) == 2
        assert len(dna.patterns) > 0
        assert dna.aggregated_metrics["avg_hook_score"] > 0.8

    def test_extract_winner_dna_not_found(self, engine):
        store = engine._store
        self._populate(engine, store)

        dna = engine.extract_winner_dna(["MW_WIN_001", "NONEXISTENT"])
        assert dna.source_count == 1

    def test_extract_winner_dna_from_records(self, engine):
        store = engine._store
        self._populate(engine, store)

        records = [
            store._repo.find_by_asset_id("MW_WIN_001"),
            store._repo.find_by_asset_id("MW_WIN_002"),
        ]
        records = [r for r in records if r is not None]
        dna = engine.extract_winner_dna_from_records(records)
        assert dna.source_count == 2

    def test_mine_patterns(self, engine):
        store = engine._store
        self._populate(engine, store)

        records = store.list_all()
        result = engine.mine_patterns(records)
        assert len(result) > 0

    def test_analyze_winner_has_more_patterns(self, engine):
        store = engine._store
        self._populate(engine, store)

        winner_insight = engine.analyze("MW_WIN_001")
        loser_insight = engine.analyze("MW_LOSE_001")

        assert winner_insight is not None
        assert loser_insight is not None
        # Winner 应该有高对比度 + 亮度模式
        assert len(winner_insight.visual_patterns) >= len(loser_insight.visual_patterns)

    def test_repr(self, engine):
        assert "VisionIntelligenceEngine" in repr(engine)


# ════════════════════════════════════════════════════════════════════
# Integration: FeatureStore → Engine → Insight → DNA
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：FeatureStore → Engine → Insight → DNA。"""

    def test_full_pipeline(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionIntelligenceEngine(feature_store=store)

        # 1. 保存 Winner 和 Loser 素材
        winners = [
            _make_record("MW_WIN_001", hook=0.9, contrast=0.65, brightness=0.75,
                         saturation=0.7, edge=0.3, entropy=4.0, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_002", hook=0.88, contrast=0.6, brightness=0.72,
                         saturation=0.68, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_003", hook=0.85, contrast=0.62, brightness=0.7,
                         saturation=0.65, is_winner=True, lifecycle="WINNER"),
        ]
        losers = [
            _make_record("MW_LOSE_001", hook=0.35, contrast=0.25, brightness=0.3,
                         is_winner=False),
            _make_record("MW_LOSE_002", hook=0.3, contrast=0.2, brightness=0.28,
                         is_winner=False),
        ]

        for r in winners + losers:
            store._repo.save_record(r)
            frames = _make_frames(feature_id=r.feature_id)
            store._repo.save_frames(r.feature_id, frames)

        # 2. 分析单个素材
        insight = engine.analyze("MW_WIN_001")
        assert insight is not None
        assert len(insight.visual_patterns) > 0
        assert insight.hook_analysis is not None
        assert insight.composition_analysis is not None
        assert insight.winner_probability > 0.5

        # 3. 提取 Winner DNA
        dna = engine.extract_winner_dna(
            ["MW_WIN_001", "MW_WIN_002", "MW_WIN_003"]
        )
        assert dna.source_count == 3
        assert dna.opening in (
            "high_contrast_center_focus", "high_contrast", "bright_opening"
        )
        assert dna.color in ("bright_saturated", "bright")

        # 4. 序列化往返
        d = insight.to_dict()
        assert "insight_id" in d
        assert "visual_patterns" in d

        dna_d = dna.to_dict()
        assert "dna_id" in dna_d
        assert "patterns" in dna_d

    def test_winner_loser_dna_comparison(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionIntelligenceEngine(feature_store=store)

        winners = [
            _make_record("MW_WIN_001", hook=0.9, contrast=0.65, brightness=0.75,
                         saturation=0.7, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_002", hook=0.88, contrast=0.6, brightness=0.72,
                         is_winner=True, lifecycle="WINNER"),
        ]
        losers = [
            _make_record("MW_LOSE_001", hook=0.35, contrast=0.25, brightness=0.3,
                         is_winner=False),
            _make_record("MW_LOSE_002", hook=0.3, contrast=0.2, brightness=0.28,
                         is_winner=False),
        ]

        for r in winners + losers:
            store._repo.save_record(r)
            frames = _make_frames(feature_id=r.feature_id)
            store._repo.save_frames(r.feature_id, frames)

        winner_dna = engine.extract_winner_dna(["MW_WIN_001", "MW_WIN_002"])
        loser_dna = engine.extract_winner_dna(["MW_LOSE_001", "MW_LOSE_002"])

        # Winner DNA 应该有更多模式
        assert len(winner_dna.patterns) >= len(loser_dna.patterns)
        # Winner DNA 的 hook 分数更高
        assert winner_dna.aggregated_metrics["avg_hook_score"] > loser_dna.aggregated_metrics["avg_hook_score"]

    def test_package_exports(self):
        from market_ops.creative_vision_runtime.intelligence import (
            VisionIntelligenceEngine as ExportedEngine,
            PatternMiner as ExportedMiner,
            HookAnalyzer as ExportedHook,
            WinnerDNAExtractor as ExportedExtractor,
            VisionInsight as ExportedInsight,
            WinnerVisualDNA as ExportedDNA,
        )
        assert ExportedEngine is VisionIntelligenceEngine
        assert ExportedMiner is PatternMiner
        assert ExportedHook is HookAnalyzer
        assert ExportedExtractor is WinnerDNAExtractor
        assert ExportedInsight is VisionInsight
        assert ExportedDNA is WinnerVisualDNA