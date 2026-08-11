"""数据模型定义 V3.1"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path


@dataclass
class VideoAsset:
    """视频素材"""
    v_num: str
    filepath: Path
    ratio: str
    width: int
    height: int
    duration: float
    content_type: str = ""
    filename: str = ""


@dataclass
class PerformanceData:
    """投放性能数据"""
    creative_id: str
    v_num: str
    spend: float = 0
    revenue: float = 0
    roas: float = 0
    purchase: int = 0
    ctr: float = 0
    cvr: float = 0
    cost: float = 0
    installs: int = 0
    content_type: str = ""
    duration: str = ""
    ratio: str = ""


# ========== V3.1 新增 ==========

@dataclass
class VideoScene:
    """视频场景分析结果"""
    start: float
    end: float
    scene_type: str = ""  # hook / gameplay / reward / problem / cta
    visual_objects: List[str] = field(default_factory=list)
    motion_score: float = 0
    emotion_score: float = 0
    hook_score: float = 0
    gameplay_score: float = 0
    reward_score: float = 0


@dataclass
class VideoAnalysis:
    """视频智能分析结果"""
    video_id: str
    duration: float
    scenes: List[VideoScene] = field(default_factory=list)
    best_hook: Optional[VideoScene] = None
    best_gameplay: Optional[VideoScene] = None
    best_reward: Optional[VideoScene] = None


@dataclass
class DNAMatch:
    """DNA 匹配结果"""
    video_id: str
    theme_match: float = 0
    visual_match: float = 0
    scene_match: float = 0
    historical_perf: float = 0
    overall: float = 0


@dataclass
class SegmentScore:
    """片段评分"""
    start: float
    duration: float
    visual_impact: float = 0
    motion_score: float = 0
    emotion_score: float = 0
    audio_peak: float = 0
    hook_impact: float = 0
    gameplay_match: float = 0
    overall: float = 0


@dataclass
class MaterialScore:
    """素材综合评分 V3.1"""
    v_num: str
    role: str
    roas_score: float = 0
    purchase_score: float = 0
    dna_match_score: float = 0
    visual_quality_score: float = 0
    freshness_score: float = 0
    overall: float = 0
    best_segment: Optional[SegmentScore] = None
    video_analysis: Optional[VideoAnalysis] = None


@dataclass
class RemixSegment:
    """混剪片段定义"""
    role: str
    v_num: str
    start: float
    duration: float
    filepath: Path
    source_ratio: str = ""
    material_score: float = 0
    segment_score: float = 0
    mutation_type: str = ""  # V3.1: dragon_attack / fast_merge / etc.
    # V3.9.1: explicit resolved source window (set by ClipResolver).
    # Assembler/composer MUST consume these; it never computes source time itself.
    source_start: float = 0.0
    source_end: float = 0.0


@dataclass
class RemixRecipe:
    """混剪配方"""
    recipe_id: str
    template: str
    target_ratio: str
    total_duration: float
    segments: List[RemixSegment] = field(default_factory=list)
    creative_family: str = ""
    variant_type: str = ""
    parent_id: str = ""  # V3.1: 父创意ID
    generation: int = 1  # V3.1: 第几代


@dataclass
class CreativeFeature:
    """创意特征向量"""
    creative_id: str
    hook_score: float = 0
    dna_match: float = 0
    gameplay_score: float = 0
    duration: float = 0
    scene_count: int = 0
    text_density: float = 0
    mutation_type: str = ""


@dataclass
class CreativePrediction:
    """AI 创意预测 V3.1"""
    creative_id: str
    hook_score: float = 0
    ctr_score: float = 0
    purchase_score: float = 0
    expected_ctr: float = 0  # V3.1: 预测 CTR
    expected_cvr: float = 0  # V3.1: 预测 CVR
    expected_roas: float = 0  # V3.1: 预测 ROAS
    fatigue_risk: float = 0
    overall_score: float = 0
    recommendation: str = "TEST"
    confidence: float = 0


@dataclass
class QAResult:
    """质检结果 V3.1"""
    creative_id: str
    passed: bool = True
    quality_score: float = 0  # V3.1
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class WinnerDNA:
    """Winner DNA"""
    theme: List[str] = field(default_factory=list)
    visual_style: List[str] = field(default_factory=list)
    structure: List[str] = field(default_factory=list)
    emotion_arc: List[str] = field(default_factory=list)
    avg_ctr: float = 0
    avg_cvr: float = 0
    avg_roas: float = 0


@dataclass
class CreativeMemoryEntry:
    """创意记忆条目"""
    dna_key: str
    performance: Dict[str, float] = field(default_factory=dict)
    weight: float = 1.0
    used_count: int = 0
    last_used: str = ""


@dataclass
class CreativeMemory:
    """创意记忆"""
    winners: List[CreativeMemoryEntry] = field(default_factory=list)
    losers: List[str] = field(default_factory=list)
    fatigue_map: Dict[str, int] = field(default_factory=dict)
    dna_evolution: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VariantConfig:
    """变异配置"""
    hook_variant: str = ""
    gameplay_variant: str = ""
    ending_variant: str = ""
    speed_multiplier: float = 1.0
    transition_style: str = "fade"
