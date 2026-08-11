"""Character Consistency - 角色一致性引擎

解决角色在不同镜头中的一致性问题。
支持:
- Character ID
- Reference Image
- LoRA
- Embedding
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterProfile:
    """角色档案"""
    character_id: str
    character_type: str          # witch / wizard / girl / boy
    name: str                    # 角色名（可选）
    appearance: dict[str, Any]   # 外观描述
    reference_images: list[str] = field(default_factory=list)  # 参考图片路径
    lora_path: str = ""          # LoRA 文件路径
    embedding: str = ""          # Embedding 标识
    color_palette: dict[str, str] = field(default_factory=dict)  # 颜色配置
    style_notes: str = ""        # 风格备注

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_type": self.character_type,
            "name": self.name,
            "appearance": self.appearance,
            "reference_images": self.reference_images,
            "lora_path": self.lora_path,
            "embedding": self.embedding,
            "color_palette": self.color_palette,
            "style_notes": self.style_notes,
        }


@dataclass
class ConsistencyConfig:
    """一致性配置"""
    character_id: str
    shots: list[str]             # 应用到的镜头列表
    consistency_strength: float  # 一致性强度 (0.0-1.0)
    method: str                  # reference / lora / embedding / description
    config: dict[str, Any] = field(default_factory=dict)


class CharacterConsistency:
    """角色一致性引擎
    
    确保角色在所有镜头中保持一致的外观、表情、服装等。
    """

    # P04 项目角色档案
    CHARACTER_LIBRARY: dict[str, CharacterProfile] = {
        "witch_01": CharacterProfile(
            character_id="witch_01",
            character_type="witch",
            name="Cute Witch",
            appearance={
                "hair": "long purple hair",
                "dress": "magical purple robe with golden trim",
                "hat": "pointed witch hat with star decorations",
                "accessories": "glowing amulet around neck",
                "pose": "standing centered",
                "expression": "cute smile",
                "age": "young adult",
                "body_type": "chibi proportions",
            },
            color_palette={
                "primary": "#6B4C9A",  # 紫色
                "secondary": "#FFD700",  # 金色
                "skin": "#FFE4C4",  # 皮肤色
            },
            style_notes="Q版可爱风格，大眼睛，圆润脸型，魔法少女感",
        ),
        "wizard_01": CharacterProfile(
            character_id="wizard_01",
            character_type="wizard",
            name="Mysterious Wizard",
            appearance={
                "hair": "short white hair",
                "robe": "blue wizard robe with silver embroidery",
                "staff": "glowing magical staff",
                "pose": "standing",
                "expression": "confident",
            },
            color_palette={
                "primary": "#1E3A8A",
                "secondary": "#C0C0C0",
            },
            style_notes="神秘感，智慧型角色",
        ),
        "fairy_queen_01": CharacterProfile(
            character_id="fairy_queen_01",
            character_type="fairy_queen",
            name="Fairy Queen",
            appearance={
                "hair": "flowing golden hair",
                "dress": "ethereal fairy gown with sparkles",
                "wings": "glowing butterfly wings",
                "pose": "floating",
                "expression": "serene",
            },
            color_palette={
                "primary": "#FFD700",
                "secondary": "#87CEEB",
            },
            style_notes="仙气飘飘，优雅高贵",
        ),
    }

    # 一致性方法配置
    CONSISTENCY_METHODS: dict[str, dict[str, Any]] = {
        "reference": {
            "description": "使用参考图片保持一致性",
            "strength_range": (0.5, 1.0),
            "requires": ["reference_image"],
            "best_for": ["pixar", "disney", "chibi"],
        },
        "lora": {
            "description": "使用 LoRA 微调模型",
            "strength_range": (0.3, 0.8),
            "requires": ["lora_path"],
            "best_for": ["all_styles"],
        },
        "embedding": {
            "description": "使用 Textual Inversion Embedding",
            "strength_range": (0.3, 0.7),
            "requires": ["embedding_name"],
            "best_for": ["stable_diffusion"],
        },
        "description": {
            "description": "使用详细文字描述保持一致",
            "strength_range": (0.5, 0.9),
            "requires": ["appearance_description"],
            "best_for": ["natural_language_models"],
        },
    }

    def __init__(self):
        self._library = dict(self.CHARACTER_LIBRARY)
        self._methods = dict(self.CONSISTENCY_METHODS)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def get_character(self, character_id: str) -> CharacterProfile | None:
        """获取角色档案"""
        return self._library.get(character_id.lower())

    def get_character_from_dna(self, dna: dict[str, Any]) -> CharacterProfile:
        """从 DNA 提取角色档案"""
        character = dna.get("character", {})
        character_type = character.get("type", "witch")

        # 查找预定义角色
        for profile in self._library.values():
            if profile.character_type == character_type:
                return profile

        # 创建临时档案
        return CharacterProfile(
            character_id=f"{character_type}_temp",
            character_type=character_type,
            name="",
            appearance={
                "pose": character.get("pose", "standing"),
                "clothes": character.get("clothes", "magical robe"),
            },
            style_notes="",
        )

    def generate_consistency_config(
        self,
        character: CharacterProfile,
        shot_ids: list[str],
        method: str = "description",
        strength: float = 0.8,
    ) -> ConsistencyConfig:
        """生成一致性配置"""
        method_config = self._methods.get(method, {})
        min_strength, max_strength = method_config.get("strength_range", (0.5, 1.0))
        clamped_strength = max(min_strength, min(max_strength, strength))

        return ConsistencyConfig(
            character_id=character.character_id,
            shots=shot_ids,
            consistency_strength=clamped_strength,
            method=method,
            config={
                "appearance": character.appearance,
                "color_palette": character.color_palette,
                "reference_images": character.reference_images,
                "lora_path": character.lora_path,
                "embedding": character.embedding,
                "style_notes": character.style_notes,
            },
        )

    def apply_to_shot_prompt(
        self,
        prompt: str,
        character: CharacterProfile,
        strength: float = 0.8,
    ) -> str:
        """将角色一致性应用到镜头提示词"""
        # 构建角色描述
        appearance_parts = []
        for key, value in character.appearance.items():
            if value:
                appearance_parts.append(f"{key}: {value}")

        character_desc = f"{character.character_type} character with {', '.join(appearance_parts[:3])}"

        # 插入到 prompt
        if strength > 0.7:
            # 高强度：完整描述
            return f"{prompt}, {character_desc}, consistent character design"
        elif strength > 0.5:
            # 中强度：关键特征
            return f"{prompt}, {character.character_type} character, {character.style_notes}"
        else:
            # 低强度：类型提示
            return f"{prompt}, {character.character_type}"

    def build_character_reference_section(
        self,
        character: CharacterProfile,
        model: str = "kling",
    ) -> dict[str, Any]:
        """构建角色参考部分（用于模型任务）"""
        section = {
            "character_id": character.character_id,
            "character_type": character.character_type,
        }

        # 根据模型添加不同内容
        if model.lower() in ["kling", "runway", "luma"]:
            # 这些模型支持参考图片
            if character.reference_images:
                section["character_reference"] = character.reference_images[0]

        elif model.lower() in ["lovart", "wan"]:
            # 这些模型用文字描述
            section["character_description"] = character.appearance

        elif model.lower() == "comfyui":
            # ComfyUI 可以加载 LoRA
            if character.lora_path:
                section["lora"] = {
                    "path": character.lora_path,
                    "strength": 0.8,
                }
            if character.reference_images:
                section["reference_image"] = character.reference_images[0]

        return section

    # ------------------------------------------------------------------
    # 批量应用
    # ------------------------------------------------------------------
    def apply_to_all_shots(
        self,
        shots: list[dict[str, Any]],
        character: CharacterProfile,
        strength: float = 0.8,
    ) -> list[dict[str, Any]]:
        """将角色一致性应用到所有镜头"""
        results = []
        for shot in shots:
            prompt = shot.get("prompt", "")
            updated_prompt = self.apply_to_shot_prompt(prompt, character, strength)
            shot_copy = dict(shot)
            shot_copy["prompt"] = updated_prompt
            shot_copy["character_id"] = character.character_id
            results.append(shot_copy)
        return results

    # ------------------------------------------------------------------
    # 角色库管理
    # ------------------------------------------------------------------
    def list_characters(self) -> list[CharacterProfile]:
        """列出所有角色"""
        return list(self._library.values())

    def add_character(self, profile: CharacterProfile) -> None:
        """添加角色档案"""
        self._library[profile.character_id] = profile

    def get_consistency_methods(self) -> list[str]:
        """获取一致性方法列表"""
        return list(self._methods.keys())