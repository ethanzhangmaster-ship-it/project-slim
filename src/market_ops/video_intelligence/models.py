"""Shared data models for Video Intelligence Pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VideoRecord:
    video_id: str
    creative_id: str
    ad_id: str
    adset_id: str
    campaign_id: str
    video_url: str = ""
    local_path: str = ""
    thumbnail_url: str = ""
    creative_name: str = ""
    creative_type: str = "video"


@dataclass(slots=True)
class VideoMetrics:
    video_id: str
    creative_id: str
    spend: float = 0.0
    impression: float = 0.0
    click: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    install: float = 0.0
    purchase: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    retention: float = 0.0
    ipm: float = 0.0
    ltv: float = 0.0
    cpa: float = 0.0


@dataclass(slots=True)
class HookAnalysis:
    hook_type: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StoryAnalysis:
    structure: str = ""
    description: str = ""


@dataclass(slots=True)
class RewardAnalysis:
    reward_type: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CharacterAnalysis:
    age: str = ""
    gender: str = ""
    clothing: str = ""
    hairstyle: str = ""
    profession: str = ""
    action: str = ""
    expression: str = ""


@dataclass(slots=True)
class EnvironmentAnalysis:
    scene: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CameraAnalysis:
    shot_type: str = ""
    movement: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MotionAnalysis:
    pace: str = ""
    cut_speed: str = ""
    action_speed: str = ""
    rhythm_changes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EmotionAnalysis:
    emotions: list[str] = field(default_factory=list)
    intensity: str = ""


@dataclass(slots=True)
class CTAAnalysis:
    cta_type: str = ""
    timing: str = ""
    display_style: str = ""


@dataclass(slots=True)
class StyleAnalysis:
    video_style: str = ""
    color_tone: str = ""
    saturation: str = ""


@dataclass(slots=True)
class AudioAnalysis:
    has_narration: bool = False
    has_sfx: bool = False
    has_bgm: bool = False
    tempo: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VideoAnalysis:
    video_id: str
    creative_id: str
    hook: HookAnalysis = field(default_factory=HookAnalysis)
    story: StoryAnalysis = field(default_factory=StoryAnalysis)
    reward: RewardAnalysis = field(default_factory=RewardAnalysis)
    character: CharacterAnalysis = field(default_factory=CharacterAnalysis)
    environment: EnvironmentAnalysis = field(default_factory=EnvironmentAnalysis)
    camera: CameraAnalysis = field(default_factory=CameraAnalysis)
    motion: MotionAnalysis = field(default_factory=MotionAnalysis)
    emotion: EmotionAnalysis = field(default_factory=EmotionAnalysis)
    cta: CTAAnalysis = field(default_factory=CTAAnalysis)
    style: StyleAnalysis = field(default_factory=StyleAnalysis)
    color: StyleAnalysis = field(default_factory=StyleAnalysis)
    audio: AudioAnalysis = field(default_factory=AudioAnalysis)
    raw_response: str = ""

    def to_flattened_dict(self) -> dict[str, Any]:
        d = asdict(self)
        flat: dict[str, Any] = {"video_id": d["video_id"], "creative_id": d["creative_id"]}

        for section in ("hook", "story", "reward", "character", "environment",
                        "camera", "motion", "emotion", "cta", "style", "color", "audio"):
            section_data = d.get(section, {})
            for k, v in section_data.items():
                if isinstance(v, list):
                    flat[f"{section}_{k}"] = v
                elif isinstance(v, bool):
                    flat[f"{section}_{k}"] = v
                else:
                    flat[f"{section}_{k}"] = str(v)
        return flat


@dataclass(slots=True)
class FeatureCount:
    name: str
    count: int = 0
    percentage: float = 0.0


@dataclass(slots=True)
class SegmentFeatureStats:
    segment_name: str
    segment_label: str
    video_count: int
    hook_counts: dict[str, FeatureCount] = field(default_factory=dict)
    character_counts: dict[str, FeatureCount] = field(default_factory=dict)
    camera_counts: dict[str, FeatureCount] = field(default_factory=dict)
    reward_counts: dict[str, FeatureCount] = field(default_factory=dict)
    color_counts: dict[str, FeatureCount] = field(default_factory=dict)
    story_counts: dict[str, FeatureCount] = field(default_factory=dict)
    emotion_counts: dict[str, FeatureCount] = field(default_factory=dict)
    environment_counts: dict[str, FeatureCount] = field(default_factory=dict)
    motion_counts: dict[str, FeatureCount] = field(default_factory=dict)
    audio_counts: dict[str, FeatureCount] = field(default_factory=dict)
    cta_counts: dict[str, FeatureCount] = field(default_factory=dict)
    style_counts: dict[str, FeatureCount] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureStatistics:
    total_videos: int
    analyzed_at: str
    segments: dict[str, SegmentFeatureStats] = field(default_factory=dict)


@dataclass(slots=True)
class PatternResult:
    metric: str
    segment: str
    common_features: list[str] = field(default_factory=list)
    feature_detail: dict[str, Any] = field(default_factory=dict)
    avg_performance: dict[str, float] = field(default_factory=dict)
    insight: str = ""


@dataclass(slots=True)
class DirectionItem:
    element: str
    rating: int
    description: str = ""
    data_evidence: str = ""


@dataclass(slots=True)
class DirectionReport:
    generated_at: str
    total_videos_analyzed: int
    recommend: list[DirectionItem] = field(default_factory=list)
    avoid: list[DirectionItem] = field(default_factory=list)
    hook_directions: list[str] = field(default_factory=list)
    character_directions: list[str] = field(default_factory=list)
    story_directions: list[str] = field(default_factory=list)
    camera_directions: list[str] = field(default_factory=list)
    pacing_directions: list[str] = field(default_factory=list)
    reward_directions: list[str] = field(default_factory=list)
    cta_directions: list[str] = field(default_factory=list)
    pattern_insights: dict[str, PatternResult] = field(default_factory=dict)
