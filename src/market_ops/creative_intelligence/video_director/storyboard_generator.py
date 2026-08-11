"""Storyboard Generator - 分镜生成器

根据 Winner DNA 自动生成：
- Hook (0-3s)
- Conflict/Gameplay (3-8s)
- Action/Reward (8-12s)
- CTA (12-15s)

规则：
- 0-3秒: 视觉冲击
- 3-8秒: 玩法展示
- 8-12秒: 奖励反馈
- 12-15秒: CTA
"""
from __future__ import annotations

from typing import Any

from .models import WinnerDNA, GameInfo, AdGoal, StoryboardScene


class StoryboardGenerator:
    """分镜生成器"""

    # 内容类型 → 分镜模板
    STORYBOARD_TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "juesezhanshi": [
            {
                "time": "0-3s",
                "scene": "character transformation flash",
                "emotion": "shock/awe",
                "visual_keywords": ["transformation", "particles", "flash", "close-up"],
            },
            {
                "time": "3-8s",
                "scene": "character showcases legendary skin",
                "emotion": "desire/aspiration",
                "visual_keywords": ["skin", "fashion", "glow", "rotate"],
            },
            {
                "time": "8-12s",
                "scene": "character performs ultimate skill",
                "emotion": "excitement/triumph",
                "visual_keywords": ["skill", "explosion", "power", "victory"],
            },
            {
                "time": "12-15s",
                "scene": "character poses with CTA button",
                "emotion": "call-to-action",
                "visual_keywords": ["CTA", "download", "pose", "smile"],
            },
        ],
        "juqing": [
            {
                "time": "0-3s",
                "scene": "dragon attacks castle",
                "emotion": "tension/shock",
                "visual_keywords": ["attack", "fire", "explosion", "destruction"],
            },
            {
                "time": "3-8s",
                "scene": "witch defends with magic",
                "emotion": "hope/struggle",
                "visual_keywords": ["magic", "shield", "defense", "spell"],
            },
            {
                "time": "8-12s",
                "scene": "witch counterattacks and wins",
                "emotion": "triumph/relief",
                "visual_keywords": ["counterattack", "victory", "light", "rescue"],
            },
            {
                "time": "12-15s",
                "scene": "rebuilt castle with CTA",
                "emotion": "call-to-action",
                "visual_keywords": ["castle", "rebuild", "CTA", "download"],
            },
        ],
        "wanfashipin": [
            {
                "time": "0-3s",
                "scene": "items start merging with glow",
                "emotion": "curiosity/anticipation",
                "visual_keywords": ["merge", "glow", "items", "fusion"],
            },
            {
                "time": "3-8s",
                "scene": "merge puzzle solving sequence",
                "emotion": "engagement/satisfaction",
                "visual_keywords": ["puzzle", "match", "cascade", "combo"],
            },
            {
                "time": "8-12s",
                "scene": "upgrade completion with rewards",
                "emotion": "reward/dopamine",
                "visual_keywords": ["upgrade", "reward", "treasure", "celebration"],
            },
            {
                "time": "12-15s",
                "scene": "game UI with download CTA",
                "emotion": "call-to-action",
                "visual_keywords": ["UI", "button", "download", "free"],
            },
        ],
        "chongwuzhanshi": [
            {
                "time": "0-3s",
                "scene": "cute pet hatches from egg",
                "emotion": "adorable/surprise",
                "visual_keywords": ["hatch", "egg", "cute", "baby"],
            },
            {
                "time": "3-8s",
                "scene": "pet evolution sequence",
                "emotion": "amazement/joy",
                "visual_keywords": ["evolution", "grow", "transform", "glow"],
            },
            {
                "time": "8-12s",
                "scene": "mighty pet showcases power",
                "emotion": "pride/excitement",
                "visual_keywords": ["power", "skill", "mighty", "epic"],
            },
            {
                "time": "12-15s",
                "scene": "pet collection with CTA",
                "emotion": "call-to-action",
                "visual_keywords": ["collection", "CTA", "collect", "download"],
            },
        ],
    }

    def __init__(self):
        self._templates = {k: [dict(item) for item in v] for k, v in self.STORYBOARD_TEMPLATES.items()}

    def generate(
        self,
        winner_dna: WinnerDNA,
        game_info: GameInfo,
        ad_goal: AdGoal,
        camera_plan: list[dict[str, Any]] | None = None,
        action_plan: list[dict[str, Any]] | None = None,
    ) -> list[StoryboardScene]:
        """生成分镜

        Returns:
            StoryboardScene 列表
        """
        content_type = winner_dna.content_type or "juesezhanshi"
        template = self._templates.get(content_type, self._templates["juesezhanshi"])

        scenes: list[StoryboardScene] = []
        for i, seg in enumerate(template):
            # 获取对应时间段的 camera 和 action
            camera = ""
            motion = ""
            if camera_plan and i < len(camera_plan):
                camera = camera_plan[i].get("camera", "")
                motion = camera_plan[i].get("purpose", "")

            action = ""
            if action_plan and i < len(action_plan):
                action = action_plan[i].get("action", "")

            # 构建场景描述
            scene_desc = self._build_scene_description(seg, game_info, action)

            scenes.append(StoryboardScene(
                time=seg["time"],
                scene=scene_desc,
                camera=camera or "dynamic movement",
                motion=motion or "continuous action",
                action=action or seg["scene"],
                emotion=seg["emotion"],
                visual_keywords=list(seg.get("visual_keywords", [])),
                duration=self._parse_duration(seg["time"]),
            ))

        return scenes

    def _build_scene_description(self, seg: dict[str, Any], game_info: GameInfo, action: str) -> str:
        """构建场景描述"""
        base = seg["scene"]

        # 替换角色名
        if game_info.key_characters:
            base = base.replace("witch", game_info.key_characters[0])
            base = base.replace("character", game_info.key_characters[0])

        # 如果有具体动作，优先用动作
        if action and len(action) > 10:
            return f"{base}: {action}"

        return base

    def _parse_duration(self, time_str: str) -> float:
        """解析时间段为时长"""
        try:
            parts = time_str.replace("s", "").split("-")
            if len(parts) == 2:
                return float(parts[1]) - float(parts[0])
        except (ValueError, IndexError):
            pass
        return 3.0

    def validate(self, scenes: list[StoryboardScene]) -> tuple[bool, list[str]]:
        """验证分镜是否符合广告标准

        Returns:
            (是否通过, 问题列表)
        """
        issues: list[str] = []

        if not scenes:
            issues.append("分镜为空")
            return False, issues

        # 检查前3秒
        first = scenes[0]
        if "0" not in first.time:
            issues.append("第一个场景必须从0秒开始")

        # 检查是否有 CTA
        has_cta = any("cta" in s.scene.lower() or "download" in s.scene.lower() for s in scenes)
        if not has_cta:
            issues.append("分镜缺少 CTA 场景")

        # 检查是否有角色/物体动作
        for s in scenes:
            if "standing" in s.action.lower() and "still" in s.action.lower():
                issues.append(f"场景 {s.time}: 角色不能静止站立")

        # 检查总时长
        total = sum(s.duration for s in scenes)
        if total < 12:
            issues.append(f"总时长 {total}s 不足，建议 >= 12s")

        return len(issues) == 0, issues
