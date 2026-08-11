from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class QAResult(Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass
class QACheck:
    check_id: str
    name: str
    category: str
    result: QAResult = QAResult.PASS
    score: float = 1.0
    detail: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "category": self.category,
            "result": self.result.value,
            "score": self.score,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


@dataclass
class QAReport:
    video_name: str
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    overall: QAResult = QAResult.PASS
    checks: List[QACheck] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_name": self.video_name,
            "total_checks": self.total_checks if self.total_checks > 0 else len(self.checks),
            "passed": self.passed,
            "warnings": self.warnings,
            "failed": self.failed,
            "overall": self.overall.value,
            "score": self.score,
            "checks": [c.to_dict() for c in self.checks],
        }


class QAChecker:
    def __init__(self):
        self._checks = []

    def check(self, video_data: Dict[str, Any]) -> QAReport:
        report = QAReport(video_name=video_data.get("name", "unknown"))
        checks = []

        checks.append(self._check_subject_center(video_data))
        checks.append(self._check_first_frame_contrast(video_data))
        checks.append(self._check_first_frame_saturation(video_data))
        checks.append(self._check_text_density_3s(video_data))
        checks.append(self._check_motion_change_3s(video_data))
        checks.append(self._check_reward_6s(video_data))
        checks.append(self._check_cta(video_data))
        checks.append(self._check_aspect_ratio(video_data))
        checks.append(self._check_warm_palette(video_data))

        report.checks = checks
        report.total_checks = len(checks)
        report.passed = sum(1 for c in checks if c.result == QAResult.PASS)
        report.warnings = sum(1 for c in checks if c.result == QAResult.WARNING)
        report.failed = sum(1 for c in checks if c.result == QAResult.FAIL)
        report.score = sum(c.score for c in checks) / len(checks) if checks else 0

        if report.failed > 0:
            report.overall = QAResult.FAIL
        elif report.warnings > 2:
            report.overall = QAResult.WARNING
        else:
            report.overall = QAResult.PASS

        return report

    def _check_subject_center(self, data: Dict) -> QACheck:
        score = data.get("subject_center_score", 0.5)
        if score >= 0.40:
            return QACheck("V1", "Subject in center 40%", "framing", QAResult.PASS, 1.0,
                           f"Subject center score: {score:.2f} >= 0.40", "Great framing!")
        elif score >= 0.30:
            return QACheck("V1", "Subject in center 40%", "framing", QAResult.WARNING, 0.6,
                           f"Subject center score: {score:.2f}, slightly off-center", "Move subject closer to center")
        else:
            return QACheck("V1", "Subject in center 40%", "framing", QAResult.FAIL, 0.2,
                           f"Subject center score: {score:.2f} < 0.40", "Subject must be in center 40% of frame")

    def _check_first_frame_contrast(self, data: Dict) -> QACheck:
        contrast = data.get("first_frame_contrast", 0.12)
        if contrast >= 0.15:
            return QACheck("V2", "First frame contrast >= 0.15", "visual", QAResult.PASS, 1.0,
                           f"Contrast: {contrast:.3f} >= 0.15", "Good contrast!")
        elif contrast >= 0.12:
            return QACheck("V2", "First frame contrast >= 0.15", "visual", QAResult.WARNING, 0.5,
                           f"Contrast: {contrast:.3f} < 0.15", "Increase contrast using S-curve")
        else:
            return QACheck("V2", "First frame contrast >= 0.15", "visual", QAResult.FAIL, 0.2,
                           f"Contrast: {contrast:.3f} too low", "Use S-curve to boost contrast. Ensure pure black and white areas.")

    def _check_first_frame_saturation(self, data: Dict) -> QACheck:
        sat = data.get("first_frame_saturation", 0.40)
        if sat >= 0.45:
            return QACheck("V3", "First frame saturation >= 0.45", "color", QAResult.PASS, 1.0,
                           f"Saturation: {sat:.3f} >= 0.45", "Vibrant colors!")
        elif sat >= 0.40:
            return QACheck("V3", "First frame saturation >= 0.45", "color", QAResult.WARNING, 0.6,
                           f"Saturation: {sat:.3f} < 0.45", "Increase saturation by 15-20%")
        else:
            return QACheck("V3", "First frame saturation >= 0.45", "color", QAResult.FAIL, 0.2,
                           f"Saturation: {sat:.3f} too low", "Boost saturation significantly. Target > 0.45")

    def _check_text_density_3s(self, data: Dict) -> QACheck:
        density = data.get("text_density_0_3s", 0.02)
        if density <= 0.015:
            return QACheck("V4", "Text density < 0.015 in first 3s", "text", QAResult.PASS, 1.0,
                           f"Text density: {density:.4f} < 0.015", "Clean first 3 seconds!")
        elif density <= 0.03:
            return QACheck("V4", "Text density < 0.015 in first 3s", "text", QAResult.WARNING, 0.5,
                           f"Text density: {density:.4f} > 0.015", "Reduce text overlay in first 3 seconds")
        else:
            return QACheck("V4", "Text density < 0.015 in first 3s", "text", QAResult.FAIL, 0.1,
                           f"Text density: {density:.4f} too high", "Remove all text from first 3 seconds")

    def _check_motion_change_3s(self, data: Dict) -> QACheck:
        motion = data.get("motion_change_0_3s", 0.08)
        if motion >= 0.10:
            return QACheck("V5", "Visual structure change within 3s", "motion", QAResult.PASS, 1.0,
                           f"Motion change: {motion:.3f} >= 0.10", "Good visual dynamic!")
        else:
            return QACheck("V5", "Visual structure change within 3s", "motion", QAResult.FAIL, 0.3,
                           f"Motion change: {motion:.3f} < 0.10", "Add structural scene change between 0.8-3.0s")

    def _check_reward_6s(self, data: Dict) -> QACheck:
        reward = data.get("reward_visual_surge", 0.03)
        if reward >= 0.05:
            return QACheck("V6", "Visual reward after 6s", "reward", QAResult.PASS, 1.0,
                           f"Reward surge: {reward:.3f} >= 0.05", "Great reward moment!")
        else:
            return QACheck("V6", "Visual reward after 6s", "reward", QAResult.FAIL, 0.3,
                           f"Reward surge: {reward:.3f} < 0.05", "Add brightness + saturation spike after 6s")

    def _check_cta(self, data: Dict) -> QACheck:
        cta = data.get("cta_present", False)
        if cta:
            return QACheck("V7", "CTA present", "cta", QAResult.PASS, 1.0,
                           "CTA button/banner present", "Good CTA placement!")
        else:
            return QACheck("V7", "CTA present", "cta", QAResult.FAIL, 0.0,
                           "No CTA detected", "Add CTA button in last 3 seconds")

    def _check_aspect_ratio(self, data: Dict) -> QACheck:
        ratio = data.get("aspect_ratio", "1:1")
        if ratio == "9:16":
            return QACheck("V8", "Aspect ratio 9:16", "format", QAResult.PASS, 1.0,
                           f"Ratio: {ratio}", "Correct format!")
        else:
            return QACheck("V8", "Aspect ratio 9:16", "format", QAResult.WARNING, 0.5,
                           f"Ratio: {ratio}", "Convert to 9:16 vertical ratio")

    def _check_warm_palette(self, data: Dict) -> QACheck:
        palette = data.get("palette", "unknown")
        if palette == "warm":
            return QACheck("V9", "Warm palette", "color", QAResult.PASS, 1.0,
                           "Warm palette detected", "Good palette choice!")
        elif palette == "neutral":
            return QACheck("V9", "Warm palette", "color", QAResult.WARNING, 0.5,
                           "Neutral palette", "Shift toward warm golden/amber tones")
        else:
            return QACheck("V9", "Warm palette", "color", QAResult.WARNING, 0.4,
                           f"Palette: {palette}", "Use warm palette (warm preferred over cool {1039:790} in data)")

    def get_stats(self) -> Dict[str, Any]:
        return {"total_check_types": 9}
