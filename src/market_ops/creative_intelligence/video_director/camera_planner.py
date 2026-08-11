"""Camera Planner - 镜头规划器

根据 Winner DNA + 广告目标，生成具体的运镜方案。
禁止：random shake, meaningless movement
必须：every camera move serves the hook or gameplay
"""
from __future__ import annotations

from typing import Any

from .models import WinnerDNA, AdGoal


class CameraPlanner:
    """镜头规划器"""

    CAMERA_LIBRARY: dict[str, dict[str, Any]] = {
        "fast_push_in": {
            "movement": "fast push in",
            "angle": "low angle",
            "lens": "cinematic wide to close",
            "speed": "fast",
            "intensity": 0.9,
            "best_for": ["hook", "impact", "reveal"],
            "description": "快速推进，强化视觉冲击",
        },
        "slow_push_in": {
            "movement": "slow push in",
            "angle": "eye level",
            "lens": "medium to close",
            "speed": "slow",
            "intensity": 0.6,
            "best_for": ["emotion", "character", "intimacy"],
            "description": "缓慢推进，营造期待感",
        },
        "zoom_out": {
            "movement": "zoom out",
            "angle": "high angle",
            "lens": "wide",
            "speed": "medium",
            "intensity": 0.5,
            "best_for": ["reveal_scale", "ending", "context"],
            "description": "拉远展示全貌",
        },
        "orbit": {
            "movement": "orbit",
            "angle": "eye level",
            "lens": "medium",
            "speed": "medium",
            "intensity": 0.7,
            "best_for": ["boss", "reward", "character_showcase"],
            "description": "环绕展示主体立体感",
        },
        "tracking": {
            "movement": "tracking",
            "angle": "dynamic",
            "lens": "medium",
            "speed": "medium",
            "intensity": 0.6,
            "best_for": ["gameplay", "chase", "movement"],
            "description": "跟随主体移动",
        },
        "handheld_shake": {
            "movement": "handheld shake",
            "angle": "dynamic",
            "lens": "wide",
            "speed": "fast",
            "intensity": 0.8,
            "best_for": ["conflict", "fail", "action"],
            "description": "手持晃动，紧张感",
        },
        "static_lock": {
            "movement": "static",
            "angle": "eye level",
            "lens": "medium",
            "speed": "none",
            "intensity": 0.0,
            "best_for": ["cta", "ui_showcase", "merge_result"],
            "description": "固定镜头，清晰展示",
        },
        "topdown": {
            "movement": "topdown",
            "angle": "overhead",
            "lens": "wide",
            "speed": "medium",
            "intensity": 0.5,
            "best_for": ["merge", "puzzle", "strategy"],
            "description": "俯视展示策略布局",
        },
        "whip_pan": {
            "movement": "whip pan",
            "angle": "dynamic",
            "lens": "wide",
            "speed": "fast",
            "intensity": 0.85,
            "best_for": ["transition", "fast_cut", "energy"],
            "description": "快速甩镜，高能量过渡",
        },
    }

    # 内容类型 → 推荐运镜组合
    CONTENT_CAMERA_MAP: dict[str, list[str]] = {
        "juesezhanshi": ["fast_push_in", "orbit", "slow_push_in", "zoom_out"],
        "juqing": ["tracking", "handheld_shake", "whip_pan", "zoom_out"],
        "wanfashipin": ["topdown", "tracking", "static_lock", "zoom_out"],
        "chongwuzhanshi": ["fast_push_in", "orbit", "slow_push_in", "zoom_out"],
    }

    # 时间段 → 运镜目的
    TIMING_CAMERA_RULES: dict[str, str] = {
        "0-3s": "必须用 fast_push_in 或 whip_pan，前3秒必须有视觉冲击",
        "3-8s": "用 tracking 或 topdown，展示玩法过程",
        "8-12s": "用 orbit 或 zoom_out，展示奖励/结果",
        "12-15s": "用 static_lock，清晰展示 CTA",
    }

    def __init__(self):
        self._library = dict(self.CAMERA_LIBRARY)
        self._content_map = dict(self.CONTENT_CAMERA_MAP)
        self._timing_rules = dict(self.TIMING_CAMERA_RULES)

    def plan(
        self,
        winner_dna: WinnerDNA,
        ad_goal: AdGoal,
        segment_times: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """生成完整镜头方案

        Args:
            winner_dna: Winner DNA
            ad_goal: 广告目标
            segment_times: 时间段列表，如 ["0-3s", "3-8s", "8-12s", "12-15s"]

        Returns:
            每个时间段的镜头方案
        """
        if segment_times is None:
            segment_times = ["0-3s", "3-8s", "8-12s", "12-15s"]

        # 根据内容类型获取推荐运镜
        content_type = winner_dna.content_type or "juesezhanshi"
        preferred = self._content_map.get(content_type, ["fast_push_in", "orbit", "static_lock"])

        plan: list[dict[str, Any]] = []
        for time_slot in segment_times:
            rule = self._timing_rules.get(time_slot, "")

            # 选择最适合当前时间段的运镜
            selected = self._select_for_timing(time_slot, preferred)
            cam = self._library.get(selected, self._library["static_lock"])

            plan.append({
                "time": time_slot,
                "camera": cam["movement"],
                "angle": cam["angle"],
                "lens": cam["lens"],
                "speed": cam["speed"],
                "intensity": cam["intensity"],
                "rule": rule,
                "purpose": cam["description"],
            })

        return plan

    def _select_for_timing(self, time_slot: str, preferred: list[str]) -> str:
        """为时间段选择最合适的运镜"""
        if time_slot == "0-3s":
            # 前3秒必须强冲击
            for c in ["fast_push_in", "whip_pan", "zoom"]:
                if c in preferred:
                    return c
            return "fast_push_in"
        elif time_slot in ("3-8s", "8-12s"):
            # 玩法/奖励展示
            for c in ["tracking", "orbit", "topdown", "slow_push_in"]:
                if c in preferred:
                    return c
            return preferred[1] if len(preferred) > 1 else "tracking"
        else:
            # CTA 固定
            return "static_lock"

    def validate(self, plan: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        """验证镜头方案是否符合广告要求

        Returns:
            (是否通过, 问题列表)
        """
        issues: list[str] = []

        # 检查前3秒
        if plan:
            first = plan[0]
            if first["intensity"] < 0.7:
                issues.append("前3秒运镜强度不足，必须 >= 0.7")
            if first["speed"] == "none":
                issues.append("前3秒不能是静态镜头")

        # 检查是否有静态CTA
        if len(plan) >= 4:
            last = plan[-1]
            if last["camera"] != "static":
                issues.append("最后一段建议用 static_lock 展示 CTA")

        # 检查是否有意义不明的运镜
        for p in plan:
            if p["camera"] in ("random pan", "meaningless shake"):
                issues.append(f"时间段 {p['time']} 使用了无意义运镜")

        return len(issues) == 0, issues
