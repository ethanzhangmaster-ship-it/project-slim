"""Creative Strategy Matrix - 显式生图决策矩阵

将"WHY"从隐式加权评分中提取为显式映射表：
Game × Country × Audience → Style / Emotion / Color / Composition / Camera / Lighting

这是策略驱动的生图决策层，回答"为什么这个游戏、这个国家、这个受众应该用这个风格"。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Creative Strategy Dataclass
# ---------------------------------------------------------------------------

@dataclass
class CreativeStrategy:
    """创意策略输出：决定一张图的所有视觉参数"""
    game: str
    country: str
    audience: str

    # 视觉决策
    style: str  # 3D cartoon / dark fantasy / anime / realistic / ...
    emotion: str  # surprise / excited / happy / panic / ...
    color_palette: str  # warm / cool / vibrant / dark / pastel / ...
    composition: str  # center focus / rule of thirds / diagonal / ...
    camera_angle: str  # front / low angle / overhead / close-up / ...
    lighting: str  # soft / dramatic / rim / backlit / ...

    # 可选：负向提示词
    negative_prompt: str = ""

    def to_dict(self) -> Dict:
        return {
            "game": self.game,
            "country": self.country,
            "audience": self.audience,
            "style": self.style,
            "emotion": self.emotion,
            "color_palette": self.color_palette,
            "composition": self.composition,
            "camera_angle": self.camera_angle,
            "lighting": self.lighting,
            "negative_prompt": self.negative_prompt,
        }

    def to_prompt_params(self) -> Dict[str, str]:
        """转换为 prompt_builder 可用的参数"""
        return {
            "style": self.style,
            "emotion": self.emotion,
            "palette": self.color_palette,
            "composition": self.composition,
            "camera": self.camera_angle,
            "background": self._gen_background(),
        }

    def _gen_background(self) -> str:
        """根据风格和灯光生成背景描述"""
        bg_map = {
            ("dark fantasy", "dramatic"): "dark castle interior, dramatic shadows",
            ("dark fantasy", "rim"): "misty battlefield, rim highlights",
            ("3D cartoon", "soft"): "bright colorful world, soft sky",
            ("3D cartoon", "backlit"): "sunny magical forest, backlight glow",
            ("anime", "soft"): "cherry blossom garden, soft sunlight",
            ("anime", "dramatic"): "futuristic city, neon lights",
            ("realistic", "soft"): "clean studio background, soft light",
            ("realistic", "dramatic"): "epic mountain landscape, golden hour",
        }
        return bg_map.get(
            (self.style, self.lighting),
            f"{self.style} background, {self.lighting} lighting",
        )


# ---------------------------------------------------------------------------
# Strategy Matrix - 核心映射表
# ---------------------------------------------------------------------------

class CreativeStrategyMatrix:
    """Game × Country × Audience → CreativeStrategy 的显式决策矩阵

    所有决策都是可审计的显式规则，不使用ML黑盒。
    """

    # ── Game Category → 默认视觉风格 ──
    GAME_STYLE_MAP: Dict[str, str] = {
        "puzzle": "3D cartoon",
        "rpg": "dark fantasy",
        "casual": "3D cartoon",
        "strategy": "realistic",
        "hyper_casual": "3D cartoon",
        "match3": "3D cartoon",
        "simulation": "realistic",
        "action": "dark fantasy",
    }

    # ── Game Category → 默认构图 ──
    GAME_COMPOSITION_MAP: Dict[str, str] = {
        "puzzle": "center focus",
        "rpg": "rule of thirds",
        "casual": "center focus",
        "strategy": "diagonal",
        "hyper_casual": "center focus",
        "match3": "center focus",
        "simulation": "rule of thirds",
        "action": "diagonal",
    }

    # ── Game Category → 默认镜头 ──
    GAME_CAMERA_MAP: Dict[str, str] = {
        "puzzle": "front",
        "rpg": "low angle",
        "casual": "front",
        "strategy": "overhead",
        "hyper_casual": "close-up",
        "match3": "front",
        "simulation": "overhead",
        "action": "low angle",
    }

    # ── Country → 文化色彩偏好 + 情绪基调 ──
    # 基于跨文化色彩心理学研究
    COUNTRY_VISUAL_PREFERENCE: Dict[str, Dict] = {
        "US": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "soft",
            "note": "美国偏好高饱和度、强对比、积极情绪",
        },
        "JP": {
            "color_palette": "pastel",
            "emotion_bias": "curious",
            "lighting": "soft",
            "note": "日本偏好柔和色调、可爱风格、好奇心驱动",
        },
        "KR": {
            "color_palette": "vibrant",
            "emotion_bias": "wow",
            "lighting": "backlit",
            "note": "韩国偏好高饱和度、惊艳效果、背光发光",
        },
        "CN": {
            "color_palette": "warm",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "中国偏好暖色调、强烈情绪、戏剧性光影",
        },
        "TW": {
            "color_palette": "warm",
            "emotion_bias": "happy",
            "lighting": "soft",
            "note": "台湾偏好暖色调、轻松愉快",
        },
        "HK": {
            "color_palette": "vibrant",
            "emotion_bias": "wow",
            "lighting": "dramatic",
            "note": "香港偏好高饱和度、惊艳效果",
        },
        "SG": {
            "color_palette": "vibrant",
            "emotion_bias": "happy",
            "lighting": "soft",
            "note": "新加坡偏好鲜艳、愉悦",
        },
        "DE": {
            "color_palette": "cool",
            "emotion_bias": "curious",
            "lighting": "soft",
            "note": "德国偏好冷色调、理性好奇",
        },
        "FR": {
            "color_palette": "dark",
            "emotion_bias": "mysterious",
            "lighting": "dramatic",
            "note": "法国偏好暗色调、神秘感",
        },
        "GB": {
            "color_palette": "cool",
            "emotion_bias": "curious",
            "lighting": "soft",
            "note": "英国偏好冷色调、克制好奇",
        },
        "BR": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "巴西偏好极度鲜艳、热情",
        },
        "MX": {
            "color_palette": "warm",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "墨西哥偏好暖色调、热情",
        },
        "IN": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "印度偏好极高饱和度、强烈",
        },
        "ID": {
            "color_palette": "vibrant",
            "emotion_bias": "happy",
            "lighting": "soft",
            "note": "印尼偏好鲜艳、愉悦",
        },
        "TH": {
            "color_palette": "warm",
            "emotion_bias": "happy",
            "lighting": "soft",
            "note": "泰国偏好暖色调、愉悦",
        },
        "VN": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "越南偏好鲜艳、激动",
        },
        "PH": {
            "color_palette": "vibrant",
            "emotion_bias": "happy",
            "lighting": "soft",
            "note": "菲律宾偏好鲜艳、愉悦",
        },
        "RU": {
            "color_palette": "dark",
            "emotion_bias": "mysterious",
            "lighting": "dramatic",
            "note": "俄罗斯偏好暗色调、神秘",
        },
        "TR": {
            "color_palette": "warm",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "土耳其偏好暖色调、热情",
        },
        "SA": {
            "color_palette": "warm",
            "emotion_bias": "wow",
            "lighting": "dramatic",
            "note": "沙特偏好暖色调、奢华",
        },
        "AE": {
            "color_palette": "warm",
            "emotion_bias": "wow",
            "lighting": "dramatic",
            "note": "阿联酋偏好暖色调、奢华",
        },
        "AU": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "soft",
            "note": "澳大利亚偏好鲜艳、积极",
        },
        "CA": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "soft",
            "note": "加拿大偏好鲜艳、积极",
        },
        "ES": {
            "color_palette": "warm",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "西班牙偏好暖色调、热情",
        },
        "IT": {
            "color_palette": "warm",
            "emotion_bias": "wow",
            "lighting": "dramatic",
            "note": "意大利偏好暖色调、惊艳",
        },
        "AR": {
            "color_palette": "warm",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "阿根廷偏好暖色调、热情",
        },
        "CO": {
            "color_palette": "vibrant",
            "emotion_bias": "excited",
            "lighting": "dramatic",
            "note": "哥伦比亚偏好鲜艳、热情",
        },
    }

    # ── Audience Segment → 视觉复杂度 ──
    AUDIENCE_VISUAL_ADJUSTMENT: Dict[str, Dict] = {
        "casual": {
            "complexity": "simple",
            "character_count": "single",
            "text_overlay": "yes",
            "note": "休闲玩家：简单明了、单角色、需要文字引导",
        },
        "hardcore": {
            "complexity": "complex",
            "character_count": "multiple",
            "text_overlay": "no",
            "note": "硬核玩家：复杂场景、多角色、以画面为主",
        },
        "f2p": {
            "complexity": "simple",
            "character_count": "single",
            "text_overlay": "yes",
            "note": "免费玩家：极简设计、强CTA、高诱惑力",
        },
        "midcore": {
            "complexity": "medium",
            "character_count": "single",
            "text_overlay": "optional",
            "note": "中度玩家：中等复杂度、平衡",
        },
    }

    # ── Emotion → 负向提示词 ──
    EMOTION_NEGATIVE_PROMPTS: Dict[str, str] = {
        "surprise": "calm, boring, normal, plain",
        "excited": "sad, depressed, calm, boring",
        "happy": "sad, angry, dark, scary",
        "panic": "calm, relaxed, peaceful, boring",
        "wow": "plain, simple, ugly, low quality",
        "cry": "happy, smiling, joyful, bright",
        "angry": "happy, smiling, cute, soft",
        "curious": "boring, obvious, known, revealed",
        "mysterious": "bright, obvious, clear, revealed",
        "proud": "shameful, weak, small, scared",
    }

    # ── 默认值 ──
    DEFAULT_STRATEGY = CreativeStrategy(
        game="casual",
        country="US",
        audience="casual",
        style="3D cartoon",
        emotion="excited",
        color_palette="vibrant",
        composition="center focus",
        camera_angle="front",
        lighting="soft",
        negative_prompt="low quality, blurry, ugly, deformed",
    )

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # 核心查找方法
    # ------------------------------------------------------------------

    def get_strategy(
        self,
        game: str,
        country: str,
        audience: str = "casual",
        override_emotion: Optional[str] = None,
    ) -> CreativeStrategy:
        """根据 Game × Country × Audience 返回完整的创意策略

        Args:
            game: 游戏类型 (puzzle, rpg, casual, strategy, hyper_casual, match3, simulation, action)
            country: 国家代码 (US, JP, KR, CN, ...)
            audience: 受众类型 (casual, hardcore, f2p, midcore)
            override_emotion: 覆盖情绪（不传则根据国家推断）

        Returns:
            CreativeStrategy 完整的创意策略
        """
        game = game.lower()
        country = country.upper()

        # 1. Style from Game
        style = self.GAME_STYLE_MAP.get(game, self.DEFAULT_STRATEGY.style)

        # 2. Country visual preferences
        country_pref = self.COUNTRY_VISUAL_PREFERENCE.get(
            country,
            self.COUNTRY_VISUAL_PREFERENCE["US"],
        )
        color_palette = country_pref["color_palette"]
        lighting = country_pref["lighting"]

        # 3. Emotion: 可覆盖，否则用国家偏好
        if override_emotion:
            emotion = override_emotion
        else:
            emotion = country_pref["emotion_bias"]

        # 4. Composition from Game
        composition = self.GAME_COMPOSITION_MAP.get(game, self.DEFAULT_STRATEGY.composition)

        # 5. Camera from Game
        camera_angle = self.GAME_CAMERA_MAP.get(game, self.DEFAULT_STRATEGY.camera_angle)

        # 6. Audience adjustment
        audience_adj = self.AUDIENCE_VISUAL_ADJUSTMENT.get(
            audience,
            self.AUDIENCE_VISUAL_ADJUSTMENT["casual"],
        )

        # 7. Negative prompt adjustment
        neg_prompt = self.EMOTION_NEGATIVE_PROMPTS.get(emotion, self.DEFAULT_STRATEGY.negative_prompt)

        # 根据受众复杂度加额外负向词
        if audience_adj["complexity"] == "simple":
            neg_prompt += ", crowded, busy, complex, cluttered"

        return CreativeStrategy(
            game=game,
            country=country,
            audience=audience,
            style=style,
            emotion=emotion,
            color_palette=color_palette,
            composition=composition,
            camera_angle=camera_angle,
            lighting=lighting,
            negative_prompt=neg_prompt,
        )

    def get_strategies_for_countries(
        self,
        game: str,
        countries: List[str],
        audience: str = "casual",
    ) -> Dict[str, CreativeStrategy]:
        """为多个国家批量生成策略"""
        return {
            country: self.get_strategy(game, country, audience)
            for country in countries
        }

    def get_ab_test_strategies(
        self,
        game: str,
        country: str,
        audience: str = "casual",
        n_variants: int = 3,
    ) -> List[Tuple[str, CreativeStrategy]]:
        """生成多组A/B测试策略变体（改变情绪/灯光/配色）

        用于同一素材在不同视觉策略下的A/B测试。
        """
        base = self.get_strategy(game, country, audience)
        variants: List[Tuple[str, CreativeStrategy]] = []

        emotion_options = ["excited", "surprise", "curious", "wow", "mysterious"]
        palette_options = ["vibrant", "warm", "cool", "dark", "pastel"]
        lighting_options = ["soft", "dramatic", "rim", "backlit"]

        for i in range(min(n_variants, 5)):
            emotion = emotion_options[i % len(emotion_options)]
            palette = palette_options[i % len(palette_options)]
            light = lighting_options[i % len(lighting_options)]

            variant = CreativeStrategy(
                game=base.game,
                country=base.country,
                audience=base.audience,
                style=base.style,
                emotion=emotion,
                color_palette=palette,
                composition=base.composition,
                camera_angle=base.camera_angle,
                lighting=light,
                negative_prompt=self.EMOTION_NEGATIVE_PROMPTS.get(
                    emotion, base.negative_prompt
                ),
            )
            variants.append((f"variant_{i:02d}_{emotion}_{palette}", variant))

        return variants

    # ------------------------------------------------------------------
    # 诊断/审计方法
    # ------------------------------------------------------------------

    def explain_strategy(self, strategy: CreativeStrategy) -> str:
        """解释为什么选择了这个策略（可审计性）"""
        lines = [
            f"## 创意策略解释：{strategy.game} × {strategy.country} × {strategy.audience}",
            "",
            f"| 参数 | 值 | 理由 |",
            f"|------|-----|------|",
        ]

        # Style
        style_reason = f"游戏类型 '{strategy.game}' 的默认风格"
        lines.append(f"| Style | {strategy.style} | {style_reason} |")

        # Color
        country_pref = self.COUNTRY_VISUAL_PREFERENCE.get(
            strategy.country, {}
        )
        color_reason = country_pref.get("note", "默认")
        lines.append(f"| Color Palette | {strategy.color_palette} | {color_reason} |")

        # Emotion
        lines.append(f"| Emotion | {strategy.emotion} | 国家偏好情绪基调 |")

        # Composition
        comp_reason = f"游戏类型 '{strategy.game}' 的默认构图"
        lines.append(f"| Composition | {strategy.composition} | {comp_reason} |")

        # Camera
        cam_reason = f"游戏类型 '{strategy.game}' 的默认镜头角度"
        lines.append(f"| Camera | {strategy.camera_angle} | {cam_reason} |")

        # Lighting
        lines.append(f"| Lighting | {strategy.lighting} | 国家偏好光照风格 |")

        # Audience
        aud_adj = self.AUDIENCE_VISUAL_ADJUSTMENT.get(strategy.audience, {})
        aud_reason = aud_adj.get("note", "默认")
        lines.append(f"| Audience Adjust | {strategy.audience} | {aud_reason} |")

        return "\n".join(lines)

    def get_all_supported_games(self) -> List[str]:
        return list(self.GAME_STYLE_MAP.keys())

    def get_all_supported_countries(self) -> List[str]:
        return list(self.COUNTRY_VISUAL_PREFERENCE.keys())

    def get_all_supported_audiences(self) -> List[str]:
        return list(self.AUDIENCE_VISUAL_ADJUSTMENT.keys())