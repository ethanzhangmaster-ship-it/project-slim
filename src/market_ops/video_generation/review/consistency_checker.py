"""Consistency Checker - 一致性检查器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConsistencyScore:
    """一致性评分"""
    camera: float = 0.0
    prompt: float = 0.0
    character: float = 0.0
    environment: float = 0.0
    overall: float = 0.0


@dataclass
class ConsistencyReport:
    """一致性报告"""
    scores: ConsistencyScore = field(default_factory=ConsistencyScore)
    details: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


class ConsistencyChecker:
    """一致性检查器"""

    def check(self, video_metadata: Dict[str, Any], blueprint: Dict[str, Any]) -> ConsistencyReport:
        """检查视频与 Blueprint 的一致性"""
        report = ConsistencyReport()
        scores = ConsistencyScore()

        shot_list = blueprint.get("shot_list", {}).get("shots", [])
        camera_specs = blueprint.get("camera_spec", {}).get("specs", [])
        asset_mappings = blueprint.get("asset_spec", {}).get("mappings", [])

        camera_map = {s.get("shot_id"): s for s in camera_specs}
        asset_map = {m.get("shot_id"): m for m in asset_mappings}

        total_camera = 0
        total_prompt = 0
        total_character = 0
        total_environment = 0
        count = 0

        for shot in shot_list:
            shot_id = shot.get("shot_id", "")
            video_data = video_metadata.get(shot_id, {})

            if not video_data.get("exists", False):
                report.issues.append(f"{shot_id}: Video not generated")
                continue

            expected_camera = camera_map.get(shot_id, {})
            expected_asset = asset_map.get(shot_id, {})

            if expected_camera:
                cam_score = self._score_camera(expected_camera, video_data)
                scores.camera += cam_score
                total_camera += cam_score

            if shot.get("character"):
                char_score = self._score_character(shot["character"], video_data)
                scores.character += char_score
                total_character += char_score

            if shot.get("environment"):
                env_score = self._score_environment(shot["environment"], video_data)
                scores.environment += env_score
                total_environment += env_score

            prompt_score = self._score_prompt(shot, video_data)
            scores.prompt += prompt_score
            total_prompt += prompt_score

            count += 1

        if count > 0:
            scores.camera = round(total_camera / count, 2)
            scores.prompt = round(total_prompt / count, 2)
            scores.character = round(total_character / count, 2)
            scores.environment = round(total_environment / count, 2)
            scores.overall = round((scores.camera + scores.prompt + scores.character + scores.environment) / 4, 2)

        report.scores = scores
        report.details = {
            "camera_score": scores.camera,
            "prompt_score": scores.prompt,
            "character_score": scores.character,
            "environment_score": scores.environment,
            "overall_score": scores.overall,
        }

        return report

    def _score_camera(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> float:
        """评分相机参数一致性"""
        matches = 0
        total = 0

        if expected.get("move") and actual.get("camera_move"):
            total += 1
            if expected["move"].lower() in actual["camera_move"].lower():
                matches += 1

        if expected.get("frame_rate") and actual.get("fps"):
            total += 1
            if abs(expected["frame_rate"] - actual["fps"]) <= 5:
                matches += 1

        if expected.get("lens") and actual.get("lens_used"):
            total += 1
            if expected["lens"] in actual["lens_used"]:
                matches += 1

        return matches / total if total > 0 else 0.5

    def _score_character(self, expected: str, actual: Dict[str, Any]) -> float:
        """评分角色一致性"""
        if not actual.get("detected_characters"):
            return 0.5
        detected = actual["detected_characters"]
        if expected.lower() in str(detected).lower():
            return 0.9
        return 0.4

    def _score_environment(self, expected: str, actual: Dict[str, Any]) -> float:
        """评分环境一致性"""
        if not actual.get("detected_environment"):
            return 0.5
        detected = actual["detected_environment"]
        if expected.lower() in str(detected).lower():
            return 0.85
        return 0.35

    def _score_prompt(self, shot: Dict[str, Any], actual: Dict[str, Any]) -> float:
        """评分提示词一致性"""
        if not actual.get("generated_prompt"):
            return 0.5
        generated = actual["generated_prompt"].lower()
        matches = 0
        keywords = []

        if shot.get("character"):
            keywords.append(shot["character"].lower())
        if shot.get("environment"):
            keywords.append(shot["environment"].lower())
        if shot.get("motion"):
            keywords.append(shot["motion"].lower())

        for kw in keywords:
            if kw in generated:
                matches += 1

        return matches / len(keywords) if keywords else 0.5

    def save_report(self, report: ConsistencyReport, path: str) -> None:
        """保存一致性报告"""
        data = {
            "scores": {
                "camera": report.scores.camera,
                "prompt": report.scores.prompt,
                "character": report.scores.character,
                "environment": report.scores.environment,
                "overall": report.scores.overall,
            },
            "details": report.details,
            "issues": report.issues,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)