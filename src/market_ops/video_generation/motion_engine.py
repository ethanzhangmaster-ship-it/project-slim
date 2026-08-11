"""Motion Engine - 动作引擎

负责角色动作、镜头动作、物体动作、特效动作的生成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MotionDefinition:
    """动作定义"""
    name: str
    category: str            # character / camera / object / fx
    description: str
    motion_prompt: str       # 用于 AI 模型的动作描述
    duration_range: tuple[float, float] = (1.0, 5.0)
    intensity: str = "medium"  # slow / medium / fast / intense


class MotionEngine:
    """动作引擎
    
    四类动作:
    1. 角色动作: 角色的动画和表演
    2. 镜头动作: 运镜和镜头运动
    3. 物体动作: 生物、物品、金币等的动作
    4. 特效动作: 魔法光效、爆炸、粒子等
    """

    # 角色动作库
    CHARACTER_MOTIONS: dict[str, MotionDefinition] = {
        "surprise": MotionDefinition(
            name="surprise",
            category="character",
            description="惊喜表情",
            motion_prompt="character showing surprise, eyes wide open, mouth open, excited expression",
            duration_range=(1.0, 3.0),
            intensity="medium",
        ),
        "celebrate": MotionDefinition(
            name="celebrate",
            category="character",
            description="庆祝动作",
            motion_prompt="character celebrating, jumping, raising arms, victory pose, smiling",
            duration_range=(2.0, 5.0),
            intensity="fast",
        ),
        "collect": MotionDefinition(
            name="collect",
            category="character",
            description="收集动作",
            motion_prompt="character collecting items, reaching out, grabbing, gathering motion",
            duration_range=(2.0, 6.0),
            intensity="medium",
        ),
        "invite": MotionDefinition(
            name="invite",
            category="character",
            description="邀请动作",
            motion_prompt="character inviting, waving hand, beckoning gesture, welcoming pose",
            duration_range=(2.0, 4.0),
            intensity="slow",
        ),
        "fight": MotionDefinition(
            name="fight",
            category="character",
            description="战斗动作",
            motion_prompt="character fighting, attacking, dodging, combat stance, action pose",
            duration_range=(3.0, 10.0),
            intensity="intense",
        ),
        "walk": MotionDefinition(
            name="walk",
            category="character",
            description="行走动作",
            motion_prompt="character walking, moving forward, casual movement",
            duration_range=(2.0, 10.0),
            intensity="slow",
        ),
        "fly": MotionDefinition(
            name="fly",
            category="character",
            description="飞行动作",
            motion_prompt="character flying, hovering, floating in air, magical flight",
            duration_range=(2.0, 8.0),
            intensity="medium",
        ),
    }

    # 物体动作库
    OBJECT_MOTIONS: dict[str, MotionDefinition] = {
        "dragon_fly": MotionDefinition(
            name="dragon_fly",
            category="object",
            description="龙飞行",
            motion_prompt="dragon flying, diving, landing, soaring, wing flapping",
            duration_range=(2.0, 8.0),
            intensity="medium",
        ),
        "dragon_attack": MotionDefinition(
            name="dragon_attack",
            category="object",
            description="龙攻击",
            motion_prompt="dragon attacking, fire breathing, claw strike, aggressive motion",
            duration_range=(2.0, 5.0),
            intensity="intense",
        ),
        "coin_explosion": MotionDefinition(
            name="coin_explosion",
            category="object",
            description="金币爆炸",
            motion_prompt="coins exploding, gold burst, treasure flying, sparkling coins",
            duration_range=(1.0, 3.0),
            intensity="fast",
        ),
        "chest_open": MotionDefinition(
            name="chest_open",
            category="object",
            description="宝箱开启",
            motion_prompt="treasure chest opening, lid lifting, gold reveal, reward reveal",
            duration_range=(2.0, 4.0),
            intensity="medium",
        ),
        "item_merge": MotionDefinition(
            name="item_merge",
            category="object",
            description="物品合成",
            motion_prompt="items merging, combining animation, glow effect, upgrade transformation",
            duration_range=(2.0, 5.0),
            intensity="medium",
        ),
        "phoenix_fly": MotionDefinition(
            name="phoenix_fly",
            category="object",
            description="凤凰飞行",
            motion_prompt="phoenix flying, fire trail, circling, magical bird soaring",
            duration_range=(3.0, 10.0),
            intensity="medium",
        ),
        "unicorn_run": MotionDefinition(
            name="unicorn_run",
            category="object",
            description="独角兽奔跑",
            motion_prompt="unicorn running, prancing, magical aura, graceful movement",
            duration_range=(2.0, 8.0),
            intensity="medium",
        ),
        "wolf_prowl": MotionDefinition(
            name="wolf_prowl",
            category="object",
            description="狼潜行",
            motion_prompt="wolf prowling, running, howling, stalking movement",
            duration_range=(3.0, 10.0),
            intensity="medium",
        ),
    }

    # 特效动作库
    FX_MOTIONS: dict[str, MotionDefinition] = {
        "magic_burst": MotionDefinition(
            name="magic_burst",
            category="fx",
            description="魔法爆发",
            motion_prompt="magical burst, spark explosion, energy wave, particle burst",
            duration_range=(1.0, 3.0),
            intensity="fast",
        ),
        "glow_pulse": MotionDefinition(
            name="glow_pulse",
            category="fx",
            description="发光脉冲",
            motion_prompt="glow pulsing, light emission, aura expanding, magical glow",
            duration_range=(2.0, 5.0),
            intensity="medium",
        ),
        "sparkle": MotionDefinition(
            name="sparkle",
            category="fx",
            description="闪光",
            motion_prompt="sparkle effect, glittering particles, shining light",
            duration_range=(1.0, 3.0),
            intensity="slow",
        ),
        "smoke_rise": MotionDefinition(
            name="smoke_rise",
            category="fx",
            description="烟雾上升",
            motion_prompt="smoke rising, fog floating, atmospheric effect",
            duration_range=(3.0, 10.0),
            intensity="slow",
        ),
        "energy_wave": MotionDefinition(
            name="energy_wave",
            category="fx",
            description="能量波",
            motion_prompt="energy wave, power surge, magical force field expanding",
            duration_range=(1.0, 3.0),
            intensity="fast",
        ),
        "boss_reveal": MotionDefinition(
            name="boss_reveal",
            category="fx",
            description="Boss 出场特效",
            motion_prompt="boss reveal effect, dramatic entrance, shadow emergence, power aura",
            duration_range=(2.0, 5.0),
            intensity="intense",
        ),
    }

    # 生物类型动作映射
    CREATURE_MOTION_MAP: dict[str, list[str]] = {
        "dragon": ["dragon_fly", "dragon_attack"],
        "phoenix": ["phoenix_fly"],
        "unicorn": ["unicorn_run"],
        "wolf": ["wolf_prowl"],
    }

    def __init__(self):
        self._char_motions = dict(self.CHARACTER_MOTIONS)
        self._obj_motions = dict(self.OBJECT_MOTIONS)
        self._fx_motions = dict(self.FX_MOTIONS)
        self._creature_map = dict(self.CREATURE_MOTION_MAP)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def get_character_motion(self, name: str) -> MotionDefinition | None:
        """获取角色动作"""
        return self._char_motions.get(name.lower())

    def get_object_motion(self, name: str) -> MotionDefinition | None:
        """获取物体动作"""
        return self._obj_motions.get(name.lower())

    def get_fx_motion(self, name: str) -> MotionDefinition | None:
        """获取特效动作"""
        return self._fx_motions.get(name.lower())

    def suggest_for_scene(self, scene_type: str, creature_type: str = "dragon") -> list[MotionDefinition]:
        """为场景建议动作组合"""
        motions = []

        # 场景类型动作
        scene_char_map = {
            "hook": ["surprise"],
            "gameplay": ["collect", "walk"],
            "reward": ["celebrate"],
            "boss": ["fight"],
            "cta": ["invite"],
            "ending": ["celebrate"],
        }
        char_motion_names = scene_char_map.get(scene_type, ["walk"])
        for name in char_motion_names:
            m = self.get_character_motion(name)
            if m:
                motions.append(m)

        # 生物动作
        creature_motions = self._creature_map.get(creature_type, ["dragon_fly"])
        for name in creature_motions:
            m = self.get_object_motion(name)
            if m:
                motions.append(m)

        # 特效
        scene_fx_map = {
            "hook": ["magic_burst"],
            "reward": ["coin_explosion", "glow_pulse"],
            "boss": ["boss_reveal", "energy_wave"],
            "gameplay": ["sparkle"],
        }
        fx_names = scene_fx_map.get(scene_type, [])
        for name in fx_names:
            m = self.get_fx_motion(name)
            if m:
                motions.append(m)

        return motions

    def generate_motion_sequence(
        self,
        scene_types: list[str],
        creature_type: str = "dragon",
    ) -> list[dict[str, Any]]:
        """生成完整动作序列"""
        sequence = []
        for scene_type in scene_types:
            motions = self.suggest_for_scene(scene_type, creature_type)
            for m in motions:
                sequence.append({
                    "scene": scene_type,
                    "category": m.category,
                    "motion": m.name,
                    "prompt": m.motion_prompt,
                    "duration_range": f"{m.duration_range[0]}-{m.duration_range[1]}s",
                    "intensity": m.intensity,
                })
        return sequence

    def build_motion_prompt(self, motions: list[MotionDefinition]) -> str:
        """构建动作提示词"""
        prompts = [m.motion_prompt for m in motions]
        return ", ".join(prompts)

    def get_all_character_motions(self) -> list[MotionDefinition]:
        """获取所有角色动作"""
        return list(self._char_motions.values())

    def get_all_object_motions(self) -> list[MotionDefinition]:
        """获取所有物体动作"""
        return list(self._obj_motions.values())

    def get_all_fx_motions(self) -> list[MotionDefinition]:
        """获取所有特效动作"""
        return list(self._fx_motions.values())