"""Feature Schema V3.2 — 定义所有特征字段"""
from dataclasses import dataclass, field
from typing import List, Dict


FEATURE_SCHEMA = {
    # Creative 基础特征
    "creative_id": "str",
    "video_id": "str",
    "duration": "float",
    "ratio": "str",
    "content_type": "str",

    # Video Intelligence 特征
    "hook_score": "float",
    "emotion_score": "float",
    "motion_score": "float",
    "gameplay_score": "float",
    "reward_score": "float",
    "scene_count": "int",
    "scene_change_rate": "float",

    # Visual DNA 特征
    "text_density": "float",
    "contrast": "float",
    "saturation": "float",
    "color_score": "float",
    "character_count": "int",

    # DNA Match
    "dna_match": "float",
    "theme_match": "float",
    "visual_match": "float",

    # Performance (训练标签)
    "spend": "float",
    "impressions": "float",
    "clicks": "float",
    "installs": "float",
    "purchases": "float",
    "revenue": "float",

    # 衍生标签
    "ctr": "float",
    "cvr": "float",
    "purchase_rate": "float",
    "roas": "float",
}

# 模型输入特征（排除 ID 和标签）
MODEL_FEATURES = [
    "duration",
    "hook_score",
    "emotion_score",
    "motion_score",
    "gameplay_score",
    "reward_score",
    "scene_count",
    "scene_change_rate",
    "text_density",
    "contrast",
    "saturation",
    "color_score",
    "character_count",
    "dna_match",
    "theme_match",
    "visual_match",
]

# 标签定义
LABEL_CTR = "ctr"
LABEL_CVR = "cvr"
LABEL_PURCHASE_RATE = "purchase_rate"
LABEL_ROAS = "roas"


@dataclass
class CreativeFeatureVector:
    """创意特征向量"""
    creative_id: str = ""
    video_id: str = ""

    # VI 特征
    hook_score: float = 0
    emotion_score: float = 0
    motion_score: float = 0
    gameplay_score: float = 0
    reward_score: float = 0
    scene_count: int = 0
    scene_change_rate: float = 0

    # Visual
    text_density: float = 0
    contrast: float = 0
    saturation: float = 0
    color_score: float = 0
    character_count: int = 0

    # DNA
    dna_match: float = 0
    theme_match: float = 0
    visual_match: float = 0

    # 基础
    duration: float = 0
    ratio: str = "9X16"
    content_type: str = ""

    # 标签（训练用）
    ctr: float = 0
    cvr: float = 0
    purchase_rate: float = 0
    roas: float = 0

    def to_model_input(self) -> List[float]:
        """转换为模型输入向量"""
        return [
            self.duration,
            self.hook_score,
            self.emotion_score,
            self.motion_score,
            self.gameplay_score,
            self.reward_score,
            self.scene_count,
            self.scene_change_rate,
            self.text_density,
            self.contrast,
            self.saturation,
            self.color_score,
            self.character_count,
            self.dna_match,
            self.theme_match,
            self.visual_match,
        ]

    def to_dict(self) -> Dict:
        return {
            "creative_id": self.creative_id,
            "duration": self.duration,
            "hook_score": self.hook_score,
            "gameplay_score": self.gameplay_score,
            "dna_match": self.dna_match,
            "text_density": self.text_density,
            "contrast": self.contrast,
            "purchase_rate": self.purchase_rate,
            "roas": self.roas,
        }
