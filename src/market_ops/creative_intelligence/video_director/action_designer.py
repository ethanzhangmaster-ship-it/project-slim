"""Action Designer - 动作设计师

负责让角色"做事情"。
禁止：character standing, character looking
必须：character performs action, object transforms, environment changes
"""
from __future__ import annotations

from typing import Any

from .models import WinnerDNA, GameInfo, AdGoal


class ActionDesigner:
    """动作设计师"""

    # 禁止的动作（会导致低留存）
    BANNED_ACTIONS: list[str] = [
        "character standing still",
        "character looking around",
        "character walking slowly with no purpose",
        "static pose",
        "idle animation",
    ]

    # 高价值动作（ROAS 驱动）
    HIGH_VALUE_ACTIONS: dict[str, list[str]] = {
        "juesezhanshi": [
            "magical transformation sequence",
            "character evolution with glowing particles",
            "legendary skin reveal with radiant light",
            "spell casting with energy burst",
            "costume upgrade with shimmering effects",
        ],
        "juqing": [
            "dragon attacks castle with fire breath",
            "witch defends with magic shield",
            "epic battle clash",
            "dramatic rescue sequence",
            "villain transformation",
        ],
        "wanfashipin": [
            "items merging with bright fusion glow",
            "puzzle pieces connecting with spark",
            "match-3 explosion cascade",
            "building upgrade animation",
            "resource collection burst",
        ],
        "chongwuzhanshi": [
            "cute pet evolution sequence",
            "pet hatching from magical egg",
            "pet merging with adorable glow",
            "pet power-up transformation",
            "pet collection reveal",
        ],
    }

    # 动作强度 → 时间段
    ACTION_TIMING: dict[str, dict[str, Any]] = {
        "0-3s": {
            "intensity": "maximum",
            "requirement": "动作必须在前1秒开始，不能有预热",
            "examples": ["instant explosion", "immediate transformation flash", "sudden attack"],
        },
        "3-8s": {
            "intensity": "high",
            "requirement": "展示核心玩法循环，动作要有节奏感",
            "examples": ["merge animation", "battle sequence", "puzzle solving"],
        },
        "8-12s": {
            "intensity": "climax",
            "requirement": "奖励/结果展示，动作要有满足感",
            "examples": ["evolution completion", "treasure reveal", "level up burst"],
        },
        "12-15s": {
            "intensity": "static",
            "requirement": "CTA 清晰展示，动作停止但视觉保持吸引",
            "examples": ["character poses with download button", "final reward showcase"],
        },
    }

    def __init__(self):
        self._banned = list(self.BANNED_ACTIONS)
        self._high_value = {k: list(v) for k, v in self.HIGH_VALUE_ACTIONS.items()}
        self._timing = {k: dict(v) for k, v in self.ACTION_TIMING.items()}

    def design(
        self,
        winner_dna: WinnerDNA,
        game_info: GameInfo,
        ad_goal: AdGoal,
    ) -> list[dict[str, Any]]:
        """设计每个时间段的动作方案

        Returns:
            每个时间段的动作描述
        """
        content_type = winner_dna.content_type or "juesezhanshi"
        actions = self._high_value.get(content_type, self._high_value["juesezhanshi"])

        # 根据游戏信息扩展动作
        extended_actions = self._extend_with_game_info(actions, game_info)

        plan: list[dict[str, Any]] = []
        time_slots = ["0-3s", "3-8s", "8-12s", "12-15s"]

        for i, time_slot in enumerate(time_slots):
            timing_rule = self._timing.get(time_slot, {})

            # 选择动作
            if i < len(extended_actions):
                action = extended_actions[i]
            else:
                action = extended_actions[-1] if extended_actions else "character transformation"

            plan.append({
                "time": time_slot,
                "action": action,
                "intensity": timing_rule.get("intensity", "medium"),
                "requirement": timing_rule.get("requirement", ""),
                "object_change": self._infer_object_change(action),
                "environment_change": self._infer_environment_change(action),
            })

        return plan

    def _extend_with_game_info(
        self,
        base_actions: list[str],
        game_info: GameInfo,
    ) -> list[str]:
        """根据游戏信息扩展动作"""
        extended = list(base_actions)

        # 加入关键角色
        for char in game_info.key_characters[:2]:
            extended.append(f"{char} performs magical attack")
            extended.append(f"{char} transforms with glowing aura")

        # 加入关键物品
        for item in game_info.key_items[:2]:
            extended.append(f"{item} merges with bright fusion glow")
            extended.append(f"{item} upgrades with sparkling effects")

        return extended[:8]  # 限制数量

    def _infer_object_change(self, action: str) -> str:
        """推断物体变化"""
        if "merge" in action.lower():
            return "two objects fuse into one upgraded object"
        elif "transform" in action.lower() or "evolution" in action.lower():
            return "object changes form with particle effects"
        elif "explosion" in action.lower():
            return "object shatters then reassembles"
        elif "collect" in action.lower():
            return "object glows and is absorbed"
        return "object emits magical particles"

    def _infer_environment_change(self, action: str) -> str:
        """推断环境变化"""
        if "attack" in action.lower() or "battle" in action.lower():
            return "environment shakes with impact effects"
        elif "transform" in action.lower():
            return "environment brightens with magical aura"
        elif "merge" in action.lower():
            return "environment sparkles with fusion energy"
        elif "reveal" in action.lower():
            return "environment transitions from dark to bright"
        return "subtle particle ambience"

    def validate(self, plan: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        """验证动作方案

        Returns:
            (是否通过, 问题列表)
        """
        issues: list[str] = []

        for p in plan:
            action = p.get("action", "").lower()

            # 检查禁止动作
            for banned in self._banned:
                if banned.lower() in action:
                    issues.append(f"时间段 {p['time']} 包含禁止动作: {banned}")

            # 检查是否有意义
            if "standing" in action and "still" in action:
                issues.append(f"时间段 {p['time']}: 角色不能静止站立")
            if "looking" in action and "around" in action:
                issues.append(f"时间段 {p['time']}: 角色不能无目的张望")

        # 检查前3秒
        if plan:
            first_action = plan[0].get("action", "").lower()
            if any(x in first_action for x in ["intro", "fade in", "slow", "walking"]):
                issues.append("前3秒动作太慢，必须直接有强动作")

        return len(issues) == 0, issues
