"""Creative Intelligence Layer - Feature 数据模型

定义 CreativeFeature 完整字段,作为 M1/M2/M3 的统一数据结构。
所有字段均可序列化为 JSON / 入库 DuckDB。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VisualFlags:
    """视觉特征布尔标记 (Module 1 规格要求)"""

    has_female: bool = False
    has_monster: bool = False
    has_ui: bool = False
    has_reward: bool = False
    has_coins: bool = False
    has_chest: bool = False
    has_arrow: bool = False
    has_before_after: bool = False
    has_explosion: bool = False
    has_highlight: bool = False
    has_finger_guide: bool = False
    has_number: bool = False
    has_text: bool = False
    has_cta: bool = False


@dataclass(slots=True)
class ColorFeatures:
    """颜色特征"""

    primary_color: str = ""
    secondary_color: str = ""
    warm_cool: str = ""  # warm / cool / neutral
    saturation: float = 0.0  # 0-1
    brightness: float = 0.0  # 0-1
    color_distribution: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class CompositionFeatures:
    """构图特征"""

    symmetry: bool = False
    golden_ratio: bool = False
    left_right_layout: bool = False
    top_bottom_layout: bool = False
    center_layout: bool = False
    focus_grid: str = ""  # 9宫格焦点,如 "22"
    focus_contrast: float = 0.0


@dataclass(slots=True)
class GameElements:
    """游戏元素检测"""

    has_merge: bool = False
    has_level: bool = False
    has_reward: bool = False
    has_inventory: bool = False
    has_collection: bool = False
    has_progress: bool = False


@dataclass(slots=True)
class CopyFeatures:
    """文案/OCR特征"""

    ocr_title: str = ""
    ocr_numbers: list[str] = field(default_factory=list)
    ocr_cta: str = ""
    ocr_keywords: list[str] = field(default_factory=list)
    overlay_text: str = ""  # Lovart识别的overlay文字


@dataclass(slots=True)
class PsychologicalFeatures:
    """Hook和情绪特征"""

    hook_type: str = ""  # crisis/reward/twist/comparison/curiosity/collection/progress/mystery/other
    emotion_surprise: bool = False
    emotion_failure: bool = False
    emotion_success: bool = False
    emotion_reward: bool = False
    emotion_tension: bool = False
    emotion_satisfaction: bool = False
    mood: str = ""


@dataclass(slots=True)
class SubjectFeatures:
    """主体特征"""

    subject_type: str = ""  # character/creature/scene/object/ui
    subject_count: int = 0
    character_count: int = 0
    subject_description: str = ""


@dataclass(slots=True)
class CreativeFeature:
    """完整 Feature Intelligence Engine 输出

    一张图片对应一条 CreativeFeature,序列化后入库 creative_features 表。
    """

    # === 基础信息 ===
    creative_id: str = ""
    project: str = ""
    campaign: str = ""
    adset: str = ""
    image_path: str = ""

    # === 各维度特征 ===
    subject: SubjectFeatures = field(default_factory=SubjectFeatures)
    visual_flags: VisualFlags = field(default_factory=VisualFlags)
    color: ColorFeatures = field(default_factory=ColorFeatures)
    composition: CompositionFeatures = field(default_factory=CompositionFeatures)
    game_elements: GameElements = field(default_factory=GameElements)
    copy: CopyFeatures = field(default_factory=CopyFeatures)
    psychology: PsychologicalFeatures = field(default_factory=PsychologicalFeatures)

    # === 元信息 ===
    analyzed_at: str = ""
    analyzer_version: str = "1.0"
    source: str = ""  # lovart / local / hybrid

    def to_dict(self) -> dict[str, Any]:
        """展平为单层 dict,便于入库 DuckDB"""
        d = asdict(self)
        # 嵌套字段展平,用前缀区分
        flat: dict[str, Any] = {}
        flat["creative_id"] = d["creative_id"]
        flat["project"] = d["project"]
        flat["campaign"] = d["campaign"]
        flat["adset"] = d["adset"]
        flat["image_path"] = d["image_path"]

        # 主体
        s = d["subject"]
        flat["subject_type"] = s["subject_type"]
        flat["subject_count"] = s["subject_count"]
        flat["character_count"] = s["character_count"]
        flat["subject_description"] = s["subject_description"]

        # 视觉标记 - 展平为布尔列
        v = d["visual_flags"]
        for k, val in v.items():
            flat[k] = val

        # 颜色
        c = d["color"]
        flat["primary_color"] = c["primary_color"]
        flat["secondary_color"] = c["secondary_color"]
        flat["warm_cool"] = c["warm_cool"]
        flat["saturation"] = c["saturation"]
        flat["brightness"] = c["brightness"]
        flat["color_distribution"] = str(c["color_distribution"])

        # 构图
        comp = d["composition"]
        flat["symmetry"] = comp["symmetry"]
        flat["golden_ratio"] = comp["golden_ratio"]
        flat["left_right_layout"] = comp["left_right_layout"]
        flat["top_bottom_layout"] = comp["top_bottom_layout"]
        flat["center_layout"] = comp["center_layout"]
        flat["focus_grid"] = comp["focus_grid"]
        flat["focus_contrast"] = comp["focus_contrast"]

        # 游戏元素
        g = d["game_elements"]
        for k, val in g.items():
            flat[f"game_{k}"] = val

        # 文案
        cp = d["copy"]
        flat["ocr_title"] = cp["ocr_title"]
        flat["ocr_numbers"] = str(cp["ocr_numbers"])
        flat["ocr_cta"] = cp["ocr_cta"]
        flat["ocr_keywords"] = str(cp["ocr_keywords"])
        flat["overlay_text"] = cp["overlay_text"]

        # 心理
        p = d["psychology"]
        flat["hook_type"] = p["hook_type"]
        flat["mood"] = p["mood"]
        for k, val in p.items():
            if k.startswith("emotion_"):
                flat[k] = val

        # 元信息
        flat["analyzed_at"] = d["analyzed_at"]
        flat["analyzer_version"] = d["analyzer_version"]
        flat["source"] = d["source"]

        return flat

    def to_json(self) -> dict[str, Any]:
        """保留嵌套结构,用于JSON文件输出"""
        return asdict(self)
