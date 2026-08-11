"""Storyboard Generator - 视频分镜生成器

输入: Master Prompt + Decision Variant
输出: storyboard.json (含多个 Scene)

每个 Scene:
- scene_type: hook / gameplay / reward / cta / ending
- duration: 秒数
- description: 画面描述
- prompt: AI 生成用的提示词
- camera: 镜头信息
- transition: 转场方式
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Scene:
    """分镜场景"""
    scene_number: int
    scene_type: str          # hook / gameplay / reward / cta / ending
    duration: float          # 秒
    description: str         # 画面描述
    prompt: str              # AI 生成提示词
    camera: str = ""         # 镜头信息
    transition: str = "cut"  # 转场方式
    sound_note: str = ""     # 声音提示

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_number": self.scene_number,
            "scene_type": self.scene_type,
            "duration": self.duration,
            "description": self.description,
            "prompt": self.prompt,
            "camera": self.camera,
            "transition": self.transition,
            "sound_note": self.sound_note,
        }


@dataclass
class Storyboard:
    """故事板"""
    storyboard_id: str
    variant_id: str
    hook_type: str
    total_duration: float
    scenes: list[Scene] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "storyboard_id": self.storyboard_id,
            "variant_id": self.variant_id,
            "hook_type": self.hook_type,
            "total_duration": self.total_duration,
            "scenes": [s.to_dict() for s in self.scenes],
            "metadata": self.metadata,
        }


class StoryboardGenerator:
    """视频分镜生成器

    为每个 Decision Variant 生成完整的视频分镜脚本。
    """

    # 不同 Hook 类型的分镜结构
    STORYBOARD_TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "collection": [
            {"scene_type": "hook", "duration": 2.0, "camera": "close-up", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 4.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "reward", "duration": 3.0, "camera": "wide", "transition": "zoom"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.0, "camera": "close-up", "transition": "fade_out"},
        ],
        "reward": [
            {"scene_type": "hook", "duration": 1.5, "camera": "close-up", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 3.0, "camera": "medium", "transition": "cut"},
            {"scene_type": "reward", "duration": 5.0, "camera": "low_angle", "transition": "explosion_zoom"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 1.5, "camera": "wide", "transition": "fade_out"},
        ],
        "transformation": [
            {"scene_type": "hook", "duration": 2.0, "camera": "medium", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 3.0, "camera": "medium", "transition": "dissolve"},
            {"scene_type": "reward", "duration": 4.0, "camera": "dynamic", "transition": "flash"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.0, "camera": "hero_shot", "transition": "fade_out"},
        ],
        "fail": [
            {"scene_type": "hook", "duration": 2.0, "camera": "close-up", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 3.0, "camera": "medium", "transition": "cut"},
            {"scene_type": "reward", "duration": 3.0, "camera": "tilted", "transition": "shake"},
            {"scene_type": "cta", "duration": 2.5, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.0, "camera": "close-up", "transition": "fade_out"},
        ],
        "emotion": [
            {"scene_type": "hook", "duration": 2.5, "camera": "extreme_close_up", "transition": "soft_fade"},
            {"scene_type": "gameplay", "duration": 3.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "reward", "duration": 4.0, "camera": "close-up", "transition": "dissolve"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.5, "camera": "extreme_close_up", "transition": "fade_out"},
        ],
        "puzzle": [
            {"scene_type": "hook", "duration": 2.0, "camera": "over_shoulder", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 4.0, "camera": "top_down", "transition": "cut"},
            {"scene_type": "reward", "duration": 3.0, "camera": "wide", "transition": "zoom"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.0, "camera": "medium", "transition": "fade_out"},
        ],
        "merge": [
            {"scene_type": "hook", "duration": 2.0, "camera": "close-up", "transition": "cut"},
            {"scene_type": "gameplay", "duration": 4.0, "camera": "medium", "transition": "glow_dissolve"},
            {"scene_type": "reward", "duration": 3.0, "camera": "wide", "transition": "sparkle_zoom"},
            {"scene_type": "cta", "duration": 2.0, "camera": "medium", "transition": "fade"},
            {"scene_type": "ending", "duration": 2.0, "camera": "close-up", "transition": "fade_out"},
        ],
    }

    def __init__(self):
        self._templates = dict(self.STORYBOARD_TEMPLATES)

    # ------------------------------------------------------------------
    # 核心生成方法
    # ------------------------------------------------------------------
    def generate(
        self,
        master_prompt: str,
        variant: dict[str, Any],
        hook_type: str = "collection",
        total_duration: float = 15.0,
    ) -> Storyboard:
        """生成分镜

        Args:
            master_prompt: Master Prompt
            variant: Decision Variant
            hook_type: Hook 类型
            total_duration: 总时长（秒）

        Returns:
            Storyboard
        """
        variant_id = variant.get("variant_id", "unknown")
        dna = variant.get("dna", {})

        # 获取分镜模板
        template = self._templates.get(hook_type.lower(), self._templates["collection"])

        # 计算每个场景的实际时长
        base_duration = sum(t["duration"] for t in template)
        scale = total_duration / base_duration if base_duration > 0 else 1.0

        scenes = []
        for i, tmpl in enumerate(template):
            scene = self._build_scene(
                scene_number=i + 1,
                scene_type=tmpl["scene_type"],
                duration=round(tmpl["duration"] * scale, 1),
                camera=tmpl.get("camera", "medium"),
                transition=tmpl.get("transition", "cut"),
                master_prompt=master_prompt,
                dna=dna,
                variant=variant,
            )
            scenes.append(scene)

        # 调整最后一个场景使总时长精确
        actual_total = sum(s.duration for s in scenes)
        if scenes and abs(actual_total - total_duration) > 0.5:
            scenes[-1].duration = round(scenes[-1].duration + (total_duration - actual_total), 1)

        return Storyboard(
            storyboard_id=f"sb_{variant_id}",
            variant_id=variant_id,
            hook_type=hook_type,
            total_duration=round(sum(s.duration for s in scenes), 1),
            scenes=scenes,
            metadata={
                "scale_factor": scale,
                "requested_duration": total_duration,
                "hook_type": hook_type,
            },
        )

    def _build_scene(
        self,
        scene_number: int,
        scene_type: str,
        duration: float,
        camera: str,
        transition: str,
        master_prompt: str,
        dna: dict[str, Any],
        variant: dict[str, Any],
    ) -> Scene:
        """构建单个场景"""
        character = dna.get("character", {}).get("type", "witch")
        creatures = dna.get("creatures", [{}])
        creature = creatures[0] if creatures else {}
        creature_type = creature.get("type", "dragon")
        env = dna.get("environment", {}).get("type", "magic_forest")

        # 场景描述生成
        descriptions = {
            "hook": f"{character} 的特写，强烈表情抓住注意力，{creature_type} 出现在画面中，" "Hook 开场 - 前2秒必须停住手指",
            "gameplay": f"展示游戏核心玩法，{character} 在 {env} 中进行收藏/收集，" "中间玩法展示 - 让用户想看下去",
            "reward": f"奖励时刻！金币爆发/物品发光/{character} 庆祝胜利，" "奖励高潮 - 满足感和爽感",
            "cta": f"行动号召画面，{character} 邀请用户加入，按钮区域预留，" "CTA 场景 - 引导下载/点击",
            "ending": f"结尾画面，{character} 满足的微笑，品牌元素露出，" "结尾 - 品牌记忆",
        }

        description = descriptions.get(scene_type, f"{scene_type} 场景")

        # AI 生成提示词
        prompt = self._build_scene_prompt(
            scene_type, master_prompt, dna, camera
        )

        # 声音提示
        sound_notes = {
            "hook": "强烈音效 / 魔法音效 / 惊喜声",
            "gameplay": "轻快背景音乐 / 交互音效",
            "reward": "胜利音乐 / 金币声 / 升级音效",
            "cta": "音乐渐强 / 号召性音效",
            "ending": "品牌音效 / 柔和结尾音乐",
        }

        return Scene(
            scene_number=scene_number,
            scene_type=scene_type,
            duration=duration,
            description=description,
            prompt=prompt,
            camera=camera,
            transition=transition,
            sound_note=sound_notes.get(scene_type, ""),
        )

    def _build_scene_prompt(
        self,
        scene_type: str,
        master_prompt: str,
        dna: dict[str, Any],
        camera: str,
    ) -> str:
        """为场景构建 AI 生成提示词"""
        # 基础 prompt 来自 master
        base = master_prompt

        # 场景特定修饰
        scene_modifiers = {
            "hook": f"{camera} shot, intense expression, eye-catching, thumb-stopping",
            "gameplay": f"{camera} shot, gameplay action, interactive moment, engaging",
            "reward": f"{camera} shot, celebration, sparkling effects, victory moment",
            "cta": f"{camera} shot, inviting pose, clear focal point, action-ready",
            "ending": f"{camera} shot, satisfying conclusion, brand-friendly, memorable",
        }

        modifier = scene_modifiers.get(scene_type, f"{camera} shot")
        return f"{base}, {modifier}"

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        prompt_variants: list[dict[str, Any]],
        total_duration: float = 15.0,
    ) -> list[Storyboard]:
        """批量生成分镜"""
        results = []
        for pv in prompt_variants:
            try:
                sb = self.generate(
                    master_prompt=pv.get("master_prompt", ""),
                    variant=pv.get("variant", {}),
                    hook_type=pv.get("hook_type", "collection"),
                    total_duration=total_duration,
                )
                results.append(sb)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export(self, storyboard: Storyboard, output_path: str) -> None:
        """导出为 JSON 文件"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(storyboard.to_dict(), f, ensure_ascii=False, indent=2)

    def estimate_production_cost(self, storyboard: Storyboard) -> dict[str, Any]:
        """估算制作成本"""
        scene_count = len(storyboard.scenes)
        total_duration = storyboard.total_duration

        # 简化的成本估算
        image_cost = scene_count * 0.05  # 每张图 $0.05
        video_edit_cost = max(5.0, total_duration * 0.5)  # 视频剪辑

        return {
            "scene_count": scene_count,
            "total_duration": total_duration,
            "estimated_image_cost": round(image_cost, 2),
            "estimated_edit_cost": round(video_edit_cost, 2),
            "total_estimated": round(image_cost + video_edit_cost, 2),
        }
