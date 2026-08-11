"""Quality Checker - 质量检查器

检查视频是否符合 Facebook 规范。
输出: Quality Score + Suggestions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityIssue:
    category: str
    severity: str
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "severity": self.severity, "message": self.message, "suggestion": self.suggestion}


@dataclass
class QualityReport:
    variant_id: str
    score: int
    passed: list[str] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "score": self.score,
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": [w.to_dict() for w in self.warnings],
            "suggestions": self.suggestions,
        }


class QualityChecker:
    """质量检查器"""

    def check(
        self,
        dna: VideoDNA,
        blueprint: VideoBlueprint,
        storyboard: Storyboard,
        shotlist: Shotlist,
        subtitle: SubtitleProfile,
        music: Any | None = None,
        editing: Any | None = None,
    ) -> QualityReport:
        issues = []
        warnings = []
        passed = []

        # 1. Hook
        if self._check_hook(storyboard):
            passed.append("前三秒有 Hook")
        else:
            issues.append(QualityIssue("Hook", "critical", "前三秒没有出现 Hook", "确保 Scene 1 在 0-3s 内展示核心钩子"))

        # 2. Gameplay
        if self._check_gameplay(storyboard):
            passed.append("有 Gameplay")
        else:
            issues.append(QualityIssue("Gameplay", "critical", "缺少 Gameplay 场景", "添加至少一个 Gameplay 场景"))

        # 3. Reward
        if self._check_reward(storyboard):
            passed.append("有 Reward")
        else:
            warnings.append(QualityIssue("Reward", "warning", "缺少 Reward 场景", "添加 Reward 场景增加吸引力"))

        # 4. CTA
        if self._check_cta(storyboard):
            passed.append("有 CTA")
        else:
            issues.append(QualityIssue("CTA", "critical", "缺少 CTA", "确保视频末尾有清晰的 CTA"))

        # 5. Story 完整
        if self._check_story_complete(storyboard):
            passed.append("Story 结构完整")
        else:
            warnings.append(QualityIssue("Story", "warning", "Story 结构不完整", "确保包含 Hook/Gameplay/Reward/CTA"))

        # 6. Camera 合理
        if self._check_camera_valid(storyboard):
            passed.append("Camera 设置合理")
        else:
            warnings.append(QualityIssue("Camera", "warning", "部分场景缺少 Camera 设置", "为每个 Scene 分配 Camera"))

        # 7. Subtitle
        if self._check_subtitle(subtitle):
            passed.append("字幕长度正常")
        else:
            warnings.append(QualityIssue("Subtitle", "warning", "部分字幕过长", "字幕应控制在 5-7 个字以内"))

        # 8. Music 匹配
        if music and self._check_music_match(music, blueprint):
            passed.append("Music 与时长匹配")
        else:
            warnings.append(QualityIssue("Music", "warning", "Music 时间轴可能不匹配", "检查 Music Segment 覆盖完整时长"))

        # 9. Editing 完整
        if editing and self._check_editing_complete(editing):
            passed.append("Editing 规范完整")
        else:
            warnings.append(QualityIssue("Editing", "warning", "Editing 规范不完整", "确保包含 LUT/Exposure/Contrast 等"))

        # 10. Facebook 合规
        if self._check_facebook_compliant(blueprint, dna):
            passed.append("Facebook 合规")
        else:
            warnings.append(QualityIssue("Facebook", "warning", "可能不符合 Facebook 规范", "检查时长与版位要求"))

        # 11. 时长符合 Placement
        if self._check_placement_duration(blueprint, dna):
            passed.append("时长符合 Placement")
        else:
            warnings.append(QualityIssue("Placement", "warning", "视频时长不符合版位要求", "Reels 建议 15s，Feed 建议 15-30s"))

        # 12. Shot length
        if self._check_shot_length(shotlist):
            passed.append("镜头长度正常")
        else:
            warnings.append(QualityIssue("Pacing", "warning", "部分镜头超过 2 秒", "缩短过长镜头，加快节奏"))

        # 13. Pacing
        if self._check_pacing(shotlist):
            passed.append("节奏正常")
        else:
            warnings.append(QualityIssue("Pacing", "warning", "节奏可能过慢", "增加每秒镜头数"))

        score = max(0, min(100, len(passed) * 8 - len(issues) * 3 - len(warnings) * 1))

        all_suggestions = [i.suggestion for i in issues + warnings if i.suggestion]

        return QualityReport(
            variant_id=dna.variant_id,
            score=score,
            passed=passed,
            issues=issues,
            warnings=warnings,
            suggestions=all_suggestions,
        )

    def _check_hook(self, storyboard: Storyboard) -> bool:
        if not storyboard.scenes:
            return False
        return storyboard.scenes[0].end_time <= 3.0

    def _check_gameplay(self, storyboard: Storyboard) -> bool:
        gameplay_names = {"Collect", "Merge", "Match", "Gameplay", "Battle", "Attack", "Solve", "Decorate"}
        return any(s.name in gameplay_names for s in storyboard.scenes)

    def _check_reward(self, storyboard: Storyboard) -> bool:
        return any(s.name in {"Reward", "Victory", "LevelUp"} for s in storyboard.scenes)

    def _check_cta(self, storyboard: Storyboard) -> bool:
        return any(s.name == "CTA" for s in storyboard.scenes)

    def _check_story_complete(self, storyboard: Storyboard) -> bool:
        names = {s.name for s in storyboard.scenes}
        has_hook = any(n in names for n in {"Hook", "Opening"})
        has_gameplay = any(n in names for n in {"Collect", "Merge", "Match", "Gameplay", "Battle", "Attack", "Solve", "Decorate"})
        has_reward = any(n in names for n in {"Reward", "Victory", "LevelUp"})
        has_cta = "CTA" in names
        return has_hook and has_gameplay and has_reward and has_cta

    def _check_camera_valid(self, storyboard: Storyboard) -> bool:
        return all(bool(s.camera) for s in storyboard.scenes)

    def _check_music_match(self, music: Any, blueprint: VideoBlueprint) -> bool:
        if not music or not music.segments:
            return False
        last_end = max(seg.end for seg in music.segments)
        return last_end >= blueprint.video_length * 0.9

    def _check_editing_complete(self, editing: Any) -> bool:
        if not editing or not getattr(editing, "scenes", None):
            return False
        required = {"lut", "exposure", "contrast", "saturation", "temperature", "tint", "sharpness", "film_grain"}
        for scene in editing.scenes:
            scene_keys = {k.lower() for k in scene.to_dict().keys()}
            if not required.issubset(scene_keys):
                return False
        return True

    def _check_facebook_compliant(self, blueprint: VideoBlueprint, dna: Any) -> bool:
        return blueprint.video_length <= 30

    def _check_placement_duration(self, blueprint: VideoBlueprint, dna: Any) -> bool:
        length = blueprint.video_length
        placement = dna.placement if isinstance(dna.placement, str) else str(dna.placement)
        placement_lower = placement.lower()
        if "reels" in placement_lower:
            return 5 <= length <= 30
        elif "feed" in placement_lower:
            return 5 <= length <= 60
        elif "story" in placement_lower:
            return 5 <= length <= 15
        return 5 <= length <= 60

    def _check_subtitle(self, subtitle: SubtitleProfile) -> bool:
        if not subtitle or not getattr(subtitle, "scenes", None):
            return True
        return all(len(s.caption) <= 15 for s in subtitle.scenes)

    def _check_shot_length(self, shotlist: Shotlist) -> bool:
        return all(s.duration <= 2.0 for s in shotlist.shots)

    def _check_pacing(self, shotlist: Shotlist) -> bool:
        avg = shotlist.total_duration / max(1, shotlist.total_shots)
        return avg <= 1.0
