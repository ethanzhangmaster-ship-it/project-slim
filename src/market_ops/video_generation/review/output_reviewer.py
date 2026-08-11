"""Output Reviewer - 输出审查器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class VideoIssue:
    """视频问题"""
    type: str
    severity: str
    message: str
    shot_id: str = ""


@dataclass
class ReviewResult:
    """审查结果"""
    passed: bool = True
    issues: List[VideoIssue] = field(default_factory=list)
    warnings: List[VideoIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class OutputReviewer:
    """输出审查器"""

    def review(self, video_metadata: Dict[str, Any], blueprint: Dict[str, Any]) -> ReviewResult:
        """审查视频输出"""
        result = ReviewResult()
        result.metadata = video_metadata

        shot_list = blueprint.get("shot_list", {}).get("shots", [])

        for shot in shot_list:
            shot_id = shot.get("shot_id", "")
            expected_duration = shot.get("duration", 0)
            expected_fps = shot.get("camera", {}).get("frame_rate", 60)

            video_data = video_metadata.get(shot_id, {})
            actual_duration = video_data.get("duration", 0)
            actual_fps = video_data.get("fps", 0)
            actual_resolution = video_data.get("resolution", "")

            if not video_data.get("exists", False):
                result.passed = False
                result.issues.append(VideoIssue(
                    type="missing",
                    severity="critical",
                    message="Video file not found",
                    shot_id=shot_id,
                ))
                continue

            if actual_duration < expected_duration * 0.5:
                result.passed = False
                result.issues.append(VideoIssue(
                    type="duration",
                    severity="critical",
                    message=f"Duration mismatch: expected {expected_duration}s, got {actual_duration}s",
                    shot_id=shot_id,
                ))

            if abs(actual_fps - expected_fps) > 5:
                result.warnings.append(VideoIssue(
                    type="fps",
                    severity="warning",
                    message=f"FPS mismatch: expected {expected_fps}, got {actual_fps}",
                    shot_id=shot_id,
                ))

            if not actual_resolution or actual_resolution not in ["1080p", "720p", "4K"]:
                result.warnings.append(VideoIssue(
                    type="resolution",
                    severity="warning",
                    message=f"Unknown or low resolution: {actual_resolution}",
                    shot_id=shot_id,
                ))

            if video_data.get("black_frame_ratio", 0) > 0.3:
                result.passed = False
                result.issues.append(VideoIssue(
                    type="black_frame",
                    severity="critical",
                    message=f"High black frame ratio: {video_data['black_frame_ratio']}",
                    shot_id=shot_id,
                ))

            if video_data.get("missing_frames", False):
                result.warnings.append(VideoIssue(
                    type="missing_frames",
                    severity="warning",
                    message="Missing frames detected",
                    shot_id=shot_id,
                ))

        if shot_list and not video_metadata:
            result.passed = False
            result.issues.append(VideoIssue(
                type="no_output",
                severity="critical",
                message="No video output generated",
            ))

        return result

    def save_review(self, result: ReviewResult, path: str) -> None:
        """保存审查结果"""
        data = {
            "passed": result.passed,
            "issues": [
                {
                    "type": i.type,
                    "severity": i.severity,
                    "message": i.message,
                    "shot_id": i.shot_id,
                }
                for i in result.issues
            ],
            "warnings": [
                {
                    "type": w.type,
                    "severity": w.severity,
                    "message": w.message,
                    "shot_id": w.shot_id,
                }
                for w in result.warnings
            ],
            "metadata": result.metadata,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)