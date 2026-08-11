"""Storyboard Engine - 视频分镜引擎

生成 15/20/30 秒视频分镜，每个分镜拆解为场景。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoScene:
    """视频场景"""
    scene_number: int
    scene_type: str              # hook / gameplay / reward / boss / cta / ending
    duration: float              # 秒
    description: str             # 中文描述
    action: str                  # 动作描述
    camera_motion: str           # 运镜
    character_action: str        # 角色动作
    creature_action: str         # 生物动作
    fx: str                      # 特效
    transition: str              # 转场
    sound: str                   # 音效
    prompt_hint: str             # 提示词提示

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_number": self.scene_number,
            "scene_type": self.scene_type,
            "duration": self.duration,
            "description": self.description,
            "action": self.action,
            "camera_motion": self.camera_motion,
            "character_action": self.character_action,
            "creature_action": self.creature_action,
            "fx": self.fx,
            "transition": self.transition,
            "sound": self.sound,
            "prompt_hint": self.prompt_hint,
        }


@dataclass
class VideoStoryboard:
    """视频分镜"""
    storyboard_id: str
    variant_id: str
    hook_type: str
    total_duration: float
    scenes: list[VideoScene] = field(default_factory=list)
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


class StoryboardEngine:
    """视频分镜引擎
    
    生成完整视频分镜，支持 15/20/30 秒。
    """

    # Hook 类型分镜模板
    STORYBOARD_TEMPLATES: dict[str, dict[str, list[dict[str, Any]]]] = {
        "collection": {
            "15s": [
                {"type": "hook", "duration": 2, "action": "发现稀有物品", "camera": "close-up push in"},
                {"type": "gameplay", "duration": 5, "action": "收集玩法展示", "camera": "tracking"},
                {"type": "reward", "duration": 4, "action": "收集完成庆祝", "camera": "wide celebration"},
                {"type": "cta", "duration": 3, "action": "邀请下载", "camera": "medium inviting"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo reveal"},
            ],
            "20s": [
                {"type": "hook", "duration": 3, "action": "发现稀有物品", "camera": "close-up dramatic"},
                {"type": "gameplay", "duration": 7, "action": "收集玩法展示", "camera": "tracking"},
                {"type": "reward", "duration": 5, "action": "收集完成庆祝", "camera": "wide celebration"},
                {"type": "cta", "duration": 4, "action": "邀请下载", "camera": "medium inviting"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo reveal"},
            ],
            "30s": [
                {"type": "hook", "duration": 4, "action": "发现稀有物品惊喜", "camera": "close-up push in"},
                {"type": "gameplay", "duration": 10, "action": "收集玩法详细展示", "camera": "tracking"},
                {"type": "reward", "duration": 7, "action": "收集完成大庆祝", "camera": "wide celebration"},
                {"type": "cta", "duration": 7, "action": "邀请下载", "camera": "medium inviting"},
                {"type": "ending", "duration": 2, "action": "品牌结尾", "camera": "logo reveal"},
            ],
        },
        "reward": {
            "15s": [
                {"type": "hook", "duration": 1.5, "action": "金币爆发", "camera": "explosion zoom"},
                {"type": "gameplay", "duration": 4, "action": "奖励玩法", "camera": "medium"},
                {"type": "reward", "duration": 5, "action": "大奖展示", "camera": "hero shot"},
                {"type": "cta", "duration": 3.5, "action": "行动号召", "camera": "medium"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo"},
            ],
            "20s": [
                {"type": "hook", "duration": 2, "action": "金币爆发开场", "camera": "explosion zoom"},
                {"type": "gameplay", "duration": 6, "action": "奖励玩法展示", "camera": "medium tracking"},
                {"type": "reward", "duration": 6, "action": "大奖展示庆祝", "camera": "hero shot"},
                {"type": "cta", "duration": 4, "action": "行动号召", "camera": "medium"},
                {"type": "ending", "duration": 2, "action": "品牌结尾", "camera": "logo"},
            ],
            "30s": [
                {"type": "hook", "duration": 3, "action": "金币大爆发", "camera": "explosion zoom"},
                {"type": "gameplay", "duration": 8, "action": "奖励玩法详细", "camera": "medium tracking"},
                {"type": "reward", "duration": 9, "action": "大奖展示庆祝", "camera": "hero shot"},
                {"type": "cta", "duration": 7, "action": "行动号召", "camera": "medium"},
                {"type": "ending", "duration": 3, "action": "品牌结尾", "camera": "logo"},
            ],
        },
        "merge": {
            "15s": [
                {"type": "hook", "duration": 2, "action": "合成预览", "camera": "top-down"},
                {"type": "gameplay", "duration": 5, "action": "合成玩法", "camera": "top-down tracking"},
                {"type": "reward", "duration": 4, "action": "合成结果", "camera": "zoom reveal"},
                {"type": "cta", "duration": 3, "action": "邀请尝试", "camera": "medium"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo"},
            ],
            "20s": [
                {"type": "hook", "duration": 3, "action": "合成预览开场", "camera": "top-down"},
                {"type": "gameplay", "duration": 7, "action": "合成玩法详细", "camera": "top-down tracking"},
                {"type": "reward", "duration": 5, "action": "合成结果展示", "camera": "zoom reveal"},
                {"type": "cta", "duration": 4, "action": "邀请尝试", "camera": "medium"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo"},
            ],
            "30s": [
                {"type": "hook", "duration": 4, "action": "合成预览开场", "camera": "top-down"},
                {"type": "gameplay", "duration": 10, "action": "合成玩法详细展示", "camera": "top-down tracking"},
                {"type": "reward", "duration": 7, "action": "合成结果大展示", "camera": "zoom reveal"},
                {"type": "cta", "duration": 6, "action": "邀请尝试", "camera": "medium"},
                {"type": "ending", "duration": 3, "action": "品牌结尾", "camera": "logo"},
            ],
        },
        "boss": {
            "15s": [
                {"type": "hook", "duration": 2, "action": "Boss 出场", "camera": "orbit reveal"},
                {"type": "gameplay", "duration": 5, "action": "Boss 战斗", "camera": "dynamic action"},
                {"type": "reward", "duration": 4, "action": "击败 Boss", "camera": "hero shot"},
                {"type": "cta", "duration": 3, "action": "挑战邀请", "camera": "medium"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo"},
            ],
            "20s": [
                {"type": "hook", "duration": 3, "action": "Boss 震撼出场", "camera": "orbit reveal"},
                {"type": "gameplay", "duration": 7, "action": "Boss 战斗展示", "camera": "dynamic action"},
                {"type": "reward", "duration": 5, "action": "击败 Boss 庆祝", "camera": "hero shot"},
                {"type": "cta", "duration": 4, "action": "挑战邀请", "camera": "medium"},
                {"type": "ending", "duration": 1, "action": "品牌结尾", "camera": "logo"},
            ],
            "30s": [
                {"type": "hook", "duration": 4, "action": "Boss 震撼出场预告", "camera": "orbit reveal"},
                {"type": "gameplay", "duration": 10, "action": "Boss 战斗详细展示", "camera": "dynamic action"},
                {"type": "reward", "duration": 7, "action": "击败 Boss 大庆祝", "camera": "hero shot"},
                {"type": "cta", "duration": 6, "action": "挑战邀请", "camera": "medium"},
                {"type": "ending", "duration": 3, "action": "品牌结尾", "camera": "logo"},
            ],
        },
    }

    # 场景类型中文
    SCENE_TYPE_ZH: dict[str, str] = {
        "hook": "钩子（开头）",
        "gameplay": "玩法展示",
        "reward": "奖励时刻",
        "boss": "Boss 战斗",
        "cta": "行动号召",
        "ending": "结尾",
    }

    # 动作中文
    ACTION_ZH: dict[str, str] = {
        "发现稀有物品": "角色发现稀有物品，惊喜表情，物品发光",
        "收集玩法展示": "展示收集玩法，角色在环境中移动收集",
        "收集完成庆祝": "收集完成，角色庆祝，特效闪光",
        "金币爆发": "金币爆炸，物品发光，奖励出现",
        "奖励玩法": "展示奖励机制，宝箱开启",
        "大奖展示": "大奖展示，特效爆炸，满足感",
        "合成预览": "合成界面，物品合并动画",
        "合成玩法": "拖拽合成，升级动画",
        "合成结果": "合成完成，新物品展示",
        "Boss出场": "Boss 震撼出场，特效环绕",
        "Boss战斗": "Boss 战斗场景，角色动作",
        "击败Boss": "击败 Boss，胜利庆祝",
        "邀请下载": "角色邀请，CTA 按钮",
        "品牌结尾": "品牌 Logo，结尾画面",
    }

    # 音效建议
    SOUND_SUGGESTIONS: dict[str, str] = {
        "hook": "魔法音效 / 惊喜声 / 短促上升和弦",
        "gameplay": "轻快游戏背景音乐",
        "reward": "金币声 / 升级音效 / 欢快胜利音乐",
        "boss": "Boss 战斗音乐 / 紧张氛围",
        "cta": "音乐渐强 / 号召感音效",
        "ending": "柔和结尾音乐 / 品牌 Logo 音效",
    }

    def __init__(self):
        self._templates = dict(self.STORYBOARD_TEMPLATES)

    # ------------------------------------------------------------------
    # 核心生成方法
    # ------------------------------------------------------------------
    def generate(
        self,
        variant: dict[str, Any],
        video_prompt: str = "",
        hook_type: str = "collection",
        duration: float = 15.0,
    ) -> VideoStoryboard:
        """生成视频分镜

        Args:
            variant: Decision Variant
            video_prompt: 视频提示词（用于场景提示）
            hook_type: Hook 类型
            duration: 总时长

        Returns:
            VideoStoryboard
        """
        variant_id = variant.get("variant_id", "unknown")
        dna = variant.get("dna", {})

        # 获取模板
        duration_key = f"{int(duration)}s"
        template = self._templates.get(hook_type, {}).get(duration_key, self._templates["collection"]["15s"])

        # 构建场景
        scenes = []
        for i, tmpl in enumerate(template):
            scene = self._build_scene(
                scene_number=i + 1,
                tmpl=tmpl,
                dna=dna,
                variant=variant,
            )
            scenes.append(scene)

        return VideoStoryboard(
            storyboard_id=f"sb_{variant_id}",
            variant_id=variant_id,
            hook_type=hook_type,
            total_duration=duration,
            scenes=scenes,
            metadata={
                "video_prompt": video_prompt,
                "template_used": f"{hook_type}_{duration_key}",
            },
        )

    def _build_scene(
        self,
        scene_number: int,
        tmpl: dict[str, Any],
        dna: dict[str, Any],
        variant: dict[str, Any],
    ) -> VideoScene:
        """构建单个场景"""
        scene_type = tmpl["type"]
        duration = tmpl["duration"]
        action = tmpl["action"]
        camera = tmpl["camera"]

        # 提取元素
        character = dna.get("character", {}).get("type", "witch")
        creatures = dna.get("creatures", [{}])
        creature_type = creatures[0].get("type", "dragon") if creatures else "dragon"
        env = dna.get("environment", {}).get("type", "魔法森林")

        # 中文描述
        scene_type_cn = self.SCENE_TYPE_ZH.get(scene_type, scene_type)
        action_cn = self.ACTION_ZH.get(action, action)

        description = f"{scene_type_cn}: {action_cn}"

        # 构建动作
        character_action = self._get_character_action(scene_type, character)
        creature_action = self._get_creature_action(scene_type, creature_type)

        # 特效
        fx = self._get_fx(scene_type)

        # 转场
        transition = self._get_transition(scene_number)

        # 音效
        sound = self.SOUND_SUGGESTIONS.get(scene_type, "")

        # 提示词提示
        prompt_hint = f"{action_cn}, {character} {character_action}, {creature_type} {creature_action}, {camera}"

        return VideoScene(
            scene_number=scene_number,
            scene_type=scene_type,
            duration=duration,
            description=description,
            action=action,
            camera_motion=camera,
            character_action=character_action,
            creature_action=creature_action,
            fx=fx,
            transition=transition,
            sound=sound,
            prompt_hint=prompt_hint,
        )

    def _get_character_action(self, scene_type: str, character: str) -> str:
        """获取角色动作"""
        actions = {
            "hook": f"{character} 惊喜表情，伸出手",
            "gameplay": f"{character} 移动，操作",
            "reward": f"{character} 庆祝，微笑",
            "boss": f"{character} 战斗姿态",
            "cta": f"{character} 邀请姿势",
            "ending": f"{character} 满足微笑",
        }
        return actions.get(scene_type, "动作")

    def _get_creature_action(self, scene_type: str, creature: str) -> str:
        """获取生物动作"""
        actions = {
            "hook": f"{creature} 出现，飞入",
            "gameplay": f"{creature} 跟随，互动",
            "reward": f"{creature} 庆祝，发光",
            "boss": f"{creature} 战斗辅助",
            "cta": f"{creature} 看向观众",
            "ending": f"{creature} 陪伴",
        }
        return actions.get(scene_type, "动作")

    def _get_fx(self, scene_type: str) -> str:
        """获取特效"""
        fx = {
            "hook": "魔法光效，粒子飞散",
            "gameplay": "交互特效，UI 动画",
            "reward": "金币爆炸，闪光",
            "boss": "战斗特效，能量波",
            "cta": "按钮发光",
            "ending": "Logo 淡入",
        }
        return fx.get(scene_type, "")

    def _get_transition(self, scene_number: int) -> str:
        """获取转场"""
        transitions = ["硬切", "淡入淡出", "缩放", "淡入淡出", "淡出"]
        return transitions[scene_number - 1] if scene_number <= len(transitions) else "淡入淡出"

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        variants: list[dict[str, Any]],
        duration: float = 15.0,
    ) -> list[VideoStoryboard]:
        """批量生成"""
        results = []
        for v in variants:
            try:
                sb = self.generate(v, duration=duration)
                results.append(sb)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export(self, storyboard: VideoStoryboard, output_path: str) -> None:
        """导出为 JSON"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(storyboard.to_dict(), f, ensure_ascii=False, indent=2)