"""Prompt Builder - ComfyUI Prompt 构建器

格式：[Subject] + [Action] + [Environment] + [Camera] + [Lighting] + [Game Advertisement Style]

关键规则：
- 必须包含 glowing particles / transformation flash / merge glow
- 禁止 dark forest / wide landscape / scenery only
- 必须强调 9:16 vertical / mobile game ad
"""
from __future__ import annotations

from typing import Any

from .models import WinnerDNA, GameInfo, AdGoal


class PromptBuilder:
    """Prompt 构建器"""

    # 广告风格标签
    AD_STYLE_TAGS: list[str] = [
        "mobile game advertisement",
        "high quality cinematic",
        "dynamic motion",
        "engaging gameplay footage",
        "colorful vibrant",
    ]

    # 质量标签
    QUALITY_TAGS: list[str] = [
        "masterpiece",
        "best quality",
        "ultra detailed",
        "4K",
        "sharp focus",
    ]

    # 高 ROAS 特效关键词
    HIGH_ROAS_EFFECTS: list[str] = [
        "glowing particles",
        "magical transformation flash",
        "radiant light burst",
        "sparkling stardust",
        "energy aura",
        "chromatic aberration on glow",
        "bloom effect",
        "lens flare",
    ]

    # 负面 Prompt 模板
    NEGATIVE_TEMPLATE: str = (
        "dark forest, landscape, wide shot, scenery only, no character, "
        "text, watermark, blurry, low quality, deformed hands, extra fingers, "
        "bad anatomy, static image, freeze frame, ugly, distorted, "
        "character standing still, meaningless background"
    )

    # 内容类型 → 主题模板
    CONTENT_TEMPLATES: dict[str, str] = {
        "juesezhanshi": (
            "gorgeous {character} character close-up, "
            "dazzling magical transformation sequence, "
            "brilliant {color} glowing particles swirling around body, "
            "radiant light burst, elegant flowing dress transforming into legendary armor, "
            "sparkling gemstone staff, intense magical aura"
        ),
        "juqing": (
            "epic fantasy scene, {character} casting powerful spell, "
            "dragon breathing fire attack, magical explosion with bright flash, "
            "castle under siege with dramatic lighting, "
            "energy shockwave spreading across screen"
        ),
        "wanfashipin": (
            "top-down puzzle game view, magical items merging together, "
            "bright fusion glow explosion, match-3 cascade with sparkling effects, "
            "satisfying merge completion animation, UI elements with golden borders"
        ),
        "chongwuzhanshi": (
            "adorable cute fantasy pet, magical evolution sequence, "
            "tiny pet transforming into majestic creature, "
            "sparkling evolution particles, kawaii to epic glow-up, "
            "big sparkly eyes, magical egg cracking with brilliant light"
        ),
    }

    def __init__(self):
        self._ad_style = list(self.AD_STYLE_TAGS)
        self._quality = list(self.QUALITY_TAGS)
        self._effects = list(self.HIGH_ROAS_EFFECTS)
        self._negative = self.NEGATIVE_TEMPLATE
        self._templates = dict(self.CONTENT_TEMPLATES)

    def build(
        self,
        winner_dna: WinnerDNA,
        game_info: GameInfo,
        ad_goal: AdGoal,
        camera_plan: list[dict[str, Any]] | None = None,
        action_plan: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        """构建 ComfyUI 正负面 Prompt

        Returns:
            {"positive": ..., "negative": ..., "flux_positive": ..., "notes": ...}
        """
        content_type = winner_dna.content_type or "juesezhanshi"

        # 构建主体
        subject = self._build_subject(content_type, game_info, winner_dna)

        # 构建动作
        action = self._build_action(action_plan)

        # 构建环境
        environment = self._build_environment(winner_dna)

        # 构建镜头
        camera = self._build_camera(camera_plan, winner_dna)

        # 构建光照
        lighting = self._build_lighting(winner_dna)

        # 构建风格
        style = self._build_style(ad_goal)

        # 组合正面 Prompt
        positive = ", ".join(filter(None, [
            ", ".join(self._quality),
            subject,
            action,
            environment,
            camera,
            lighting,
            style,
            ", ".join(self._effects[:4]),
        ]))

        # 首帧图 Flux Prompt（更偏静态画面）
        flux_positive = ", ".join(filter(None, [
            ", ".join(self._quality),
            subject,
            environment,
            lighting,
            "static keyframe, beautiful composition",
        ]))

        return {
            "positive": positive,
            "negative": self._negative,
            "flux_positive": flux_positive,
            "notes": self._build_notes(winner_dna),
        }

    def _build_subject(self, content_type: str, game_info: GameInfo, winner_dna: WinnerDNA) -> str:
        """构建主体描述"""
        template = self._templates.get(content_type, self._templates["juesezhanshi"])

        # 填充变量
        character = game_info.key_characters[0] if game_info.key_characters else "witch"
        color = "golden and purple" if "golden" in winner_dna.theme else "bright magical"

        return template.format(character=character, color=color)

    def _build_action(self, action_plan: list[dict[str, Any]] | None) -> str:
        """构建动作描述"""
        if not action_plan:
            return "dynamic magical action, character performing powerful move"

        # 取前3个时间段的动作组合
        actions = [p["action"] for p in action_plan[:3]]
        return ", ".join(actions)

    def _build_environment(self, winner_dna: WinnerDNA) -> str:
        """构建环境描述"""
        # 禁止纯风景，必须有角色/物体
        return "fantasy magical environment with character in center frame, particle effects filling screen"

    def _build_camera(self, camera_plan: list[dict[str, Any]] | None, winner_dna: WinnerDNA) -> str:
        """构建镜头描述"""
        if not camera_plan:
            return "dynamic camera movement, cinematic vertical shot"

        cameras = [p["camera"] for p in camera_plan[:2]]
        return f"camera {', '.join(cameras)}, {winner_dna.aspect_ratio} vertical format"

    def _build_lighting(self, winner_dna: WinnerDNA) -> str:
        """构建光照描述"""
        return f"{winner_dna.lighting}, dramatic backlighting, volumetric light rays"

    def _build_style(self, ad_goal: AdGoal) -> str:
        """构建风格描述"""
        style_tags = list(self._ad_style)
        if ad_goal.format == "9:16":
            style_tags.append("vertical portrait composition")
        elif ad_goal.format == "1:1":
            style_tags.append("square format centered composition")
        return ", ".join(style_tags)

    def _build_notes(self, winner_dna: WinnerDNA) -> str:
        """构建提示词备注"""
        return (
            f"参考视频: {winner_dna.source_video_id} (ROAS: {winner_dna.roas:.2f}) | "
            f"内容类型: {winner_dna.content_type} | "
            f"必须包含: glowing particles, transformation flash, character close-up"
        )
