"""Video Prompt Engine - 从 Decision Variant 生成视频提示词

输入: Decision Variant（含 DNA、决策分数、预测指标等）
输出: Master Video Prompt（视频专用，支持不同平台和模型）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoPrompt:
    """视频提示词"""
    prompt_id: str
    variant_id: str
    master_prompt: str
    platform: str            # facebook / google / tiktok
    placement: str           # feed / reels / stories
    duration: float          # 15 / 20 / 30 秒
    style: str               # pixar / disney / realistic
    hook_type: str           # collection / reward / merge
    model_optimized: dict[str, str] = field(default_factory=dict)  # 各模型专用版本
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "variant_id": self.variant_id,
            "master_prompt": self.master_prompt,
            "platform": self.platform,
            "placement": self.placement,
            "duration": self.duration,
            "style": self.style,
            "hook_type": self.hook_type,
            "model_optimized": self.model_optimized,
            "metadata": self.metadata,
        }


class VideoPromptEngine:
    """视频提示词引擎
    
    直接消费 V4.2.2 Decision Variant，生成视频专用提示词。
    """

    # 平台风格修饰
    PLATFORM_MODIFIERS: dict[str, list[str]] = {
        "facebook": [
            "Facebook mobile game advertisement",
            "thumb-stopping scroll pauser",
            "first 2 seconds maximum impact",
            "clear at small size",
            "sound-on and sound-off friendly",
        ],
        "google": [
            "Google Ads video",
            "YouTube pre-roll friendly",
            "skip-proof first 5 seconds",
            "wide reach appeal",
        ],
        "tiktok": [
            "TikTok native",
            "trend-aware",
            "fast-paced",
            "young audience appeal",
            "loop-friendly",
        ],
    }

    # 版位尺寸和风格
    PLACEMENT_CONFIGS: dict[str, dict[str, Any]] = {
        "feed": {
            "aspect_ratio": "4:5",
            "safe_zone": "center 80%",
            "cta_zone": "bottom 15%",
            "style": "thumb-stopping, bold colors",
        },
        "reels": {
            "aspect_ratio": "9:16",
            "safe_zone": "center 90%",
            "cta_zone": "bottom 10%",
            "style": "vertical native, full screen",
        },
        "stories": {
            "aspect_ratio": "9:16",
            "safe_zone": "center 90%",
            "cta_zone": "bottom 10%",
            "style": "quick hook, 15 seconds max",
        },
    }

    # Hook 类型视频描述
    HOOK_VIDEO_DESCRIPTIONS: dict[str, str] = {
        "collection": "Collect rare items, discovery moment, gathering gameplay",
        "reward": "Massive reward explosion, coins burst, treasure chest opening",
        "merge": "Top-down merge gameplay, combining items, upgrade animation",
        "transformation": "Character transformation, evolution, power-up sequence",
        "boss": "Boss unlock, boss battle preview, dramatic reveal",
        "emotion": "Emotional story moment, character bond, heartwarming scene",
        "fail": "Comedy fail moment, retry challenge, can you do better",
    }

    # 模型专用优化
    MODEL_PROMPT_STYLES: dict[str, dict[str, Any]] = {
        "kling": {
            "prefix": "",
            "suffix": "",
            "max_length": 500,
            "style": "natural language preferred",
        },
        "wan": {
            "prefix": "",
            "suffix": "",
            "max_length": 800,
            "style": "detailed description",
        },
        "veo": {
            "prefix": "",
            "suffix": "",
            "max_length": 600,
            "style": "cinematic language",
        },
        "runway": {
            "prefix": "",
            "suffix": "",
            "max_length": 400,
            "style": "concise motion focus",
        },
        "lovart": {
            "prefix": "mobile game advertisement, ",
            "suffix": "",
            "max_length": 1000,
            "style": "game ad optimized",
        },
        "pika": {
            "prefix": "",
            "suffix": "",
            "max_length": 300,
            "style": "simple action focus",
        },
        "luma": {
            "prefix": "",
            "suffix": "",
            "max_length": 500,
            "style": "realistic motion",
        },
        "hailuo": {
            "prefix": "",
            "suffix": "",
            "max_length": 400,
            "style": "anime style preferred",
        },
    }

    def __init__(self):
        self._platform_mods = dict(self.PLATFORM_MODIFIERS)
        self._placement_configs = dict(self.PLACEMENT_CONFIGS)
        self._hook_descs = dict(self.HOOK_VIDEO_DESCRIPTIONS)
        self._model_styles = dict(self.MODEL_PROMPT_STYLES)

    # ------------------------------------------------------------------
    # 核心生成方法
    # ------------------------------------------------------------------
    def generate(
        self,
        variant: dict[str, Any],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
        style: str = "pixar",
    ) -> VideoPrompt:
        """从 Decision Variant 生成视频提示词

        Args:
            variant: V4.2.2 Decision Variant
            duration: 视频时长（15/20/30）
            platform: 平台
            placement: 版位
            style: 风格

        Returns:
            VideoPrompt
        """
        variant_id = variant.get("variant_id", "unknown")
        dna = variant.get("dna", {})
        decision_score = variant.get("decision_score", 0)

        # 推断 Hook 类型
        hook_type = self._infer_hook_type(variant, dna)

        # 从 DNA 提取元素
        elements = self._extract_video_elements(dna, variant)

        # 构建主提示词
        master_prompt = self._build_master_prompt(
            elements=elements,
            hook_type=hook_type,
            platform=platform,
            placement=placement,
            duration=duration,
            style=style,
        )

        # 为各模型优化
        model_optimized = {}
        for model, config in self._model_styles.items():
            model_optimized[model] = self._optimize_for_model(master_prompt, model)

        return VideoPrompt(
            prompt_id=f"vp_{variant_id}",
            variant_id=variant_id,
            master_prompt=master_prompt,
            platform=platform,
            placement=placement,
            duration=duration,
            style=style,
            hook_type=hook_type,
            model_optimized=model_optimized,
            metadata={
                "decision_score": decision_score,
                "predicted_ctr": variant.get("predicted_ctr", 0),
                "predicted_cvr": variant.get("predicted_cvr", 0),
                "predicted_roas": variant.get("predicted_roas", 0),
                "changed_dimension": variant.get("changed_dimension", ""),
                "new_value": variant.get("new_value", ""),
                "elements": elements,
            },
        )

    def _infer_hook_type(self, variant: dict[str, Any], dna: dict[str, Any]) -> str:
        """推断 Hook 类型"""
        # 从 DNA hook 字段
        hook = dna.get("hook", {})
        hook_type = hook.get("type", "")
        if hook_type:
            return hook_type

        # 从 changed_dimension 推断
        dim = variant.get("changed_dimension", "").lower()
        dim_map = {
            "creature": "collection",
            "character": "emotion",
            "lighting": "collection",
            "background": "collection",
            "hook_type": "reward",
        }
        return dim_map.get(dim, "collection")

    def _extract_video_elements(self, dna: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        """提取视频元素"""
        elements = {}

        # 角色
        character = dna.get("character", {})
        elements["character_type"] = character.get("type", "witch")
        elements["character_pose"] = character.get("pose", "standing")

        # 生物
        creatures = dna.get("creatures", [{}])
        if creatures:
            creature = creatures[0]
            elements["creature_type"] = creature.get("type", "dragon")
            elements["creature_color"] = creature.get("color", "blue")
            elements["creature_motion"] = self._get_creature_motion(creature.get("type", "dragon"))

        # 环境
        env = dna.get("environment", {})
        elements["environment_type"] = env.get("type", "magic_forest")
        elements["time_of_day"] = env.get("time", "night")

        # 光照
        lighting = dna.get("lighting", {})
        elements["lighting_type"] = lighting.get("color_temperature", "warm")

        # 构图
        camera = dna.get("camera", {})
        elements["camera_shot"] = camera.get("shot_type", "medium")
        elements["camera_angle"] = camera.get("angle", "eye_level")

        # 动作
        elements["motion"] = self._suggest_motion(elements.get("creature_type", "dragon"))
        elements["camera_motion"] = self._suggest_camera_motion(variant.get("changed_dimension", ""))

        return elements

    def _get_creature_motion(self, creature_type: str) -> str:
        """获取生物动作"""
        motions = {
            "dragon": "flying, diving, landing",
            "phoenix": "flying, fire trail, circling",
            "unicorn": "running, prancing, magical aura",
            "wolf": "running, howling, prowling",
        }
        return motions.get(creature_type, "moving, action")

    def _suggest_motion(self, creature_type: str) -> str:
        """建议动作"""
        return self._get_creature_motion(creature_type)

    def _suggest_camera_motion(self, changed_dim: str) -> str:
        """根据改动维度建议运镜"""
        camera_map = {
            "lighting": "slow push in",
            "creature": "orbit around creature",
            "background": "wide establishing shot",
            "camera": "tracking shot",
        }
        return camera_map.get(changed_dim.lower(), "push in")

    def _build_master_prompt(
        self,
        elements: dict[str, Any],
        hook_type: str,
        platform: str,
        placement: str,
        duration: float,
        style: str,
    ) -> str:
        """构建主提示词"""
        parts = []

        # 1. 平台前缀
        platform_mods = self._platform_mods.get(platform, [])
        if platform_mods:
            parts.append(platform_mods[0])

        # 2. 时长和版位
        parts.append(f"{duration}-second video advertisement")
        placement_config = self._placement_configs.get(placement, {})
        parts.append(f"aspect ratio {placement_config.get('aspect_ratio', '4:5')}")

        # 3. 视觉元素
        parts.append(f"fantasy world, {elements.get('environment_type', 'magic forest')}")
        parts.append(f"{elements.get('time_of_day', 'night')} atmosphere")
        parts.append(f"cute {elements.get('creature_type', 'dragon')} with {elements.get('creature_color', 'blue')} color")

        # 4. 角色
        parts.append(f"{elements.get('character_type', 'witch')} character")
        parts.append(f"{elements.get('character_pose', 'standing')} pose")

        # 5. 动作和运镜
        parts.append(f"{elements.get('motion', 'dynamic action')}")
        parts.append(f"camera {elements.get('camera_motion', 'push in')}")

        # 6. Hook 类型描述
        hook_desc = self._hook_descs.get(hook_type, "")
        if hook_desc:
            parts.append(hook_desc)

        # 7. 光照和风格
        parts.append(f"{elements.get('lighting_type', 'warm cinematic')} lighting")
        parts.append(f"{style} quality, ultra detailed")

        # 8. 版位风格
        placement_style = placement_config.get("style", "")
        if placement_style:
            parts.append(placement_style)

        # 9. Facebook 专用
        if platform == "facebook":
            parts.append("commercial advertising quality")
            parts.append("safe zone center 80%, CTA bottom 15%")

        return ", ".join(parts)

    def _optimize_for_model(self, prompt: str, model: str) -> str:
        """为特定模型优化"""
        config = self._model_styles.get(model, {})
        max_len = config.get("max_length", 500)

        # 添加前缀
        prefix = config.get("prefix", "")
        result = f"{prefix}{prompt}"

        # 截断到最大长度
        if len(result) > max_len:
            result = result[:max_len].rsplit(",", 1)[0]

        return result

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        variants: list[dict[str, Any]],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
    ) -> list[VideoPrompt]:
        """批量生成"""
        results = []
        for v in variants:
            try:
                vp = self.generate(v, duration, platform, placement)
                results.append(vp)
            except Exception:
                continue
        return results