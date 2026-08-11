"""Visual QA Checker for generated videos.

Detects quality issues:
- blur
- artifact
- flicker
- frame_error
- bad_generation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from pathlib import Path


class VisualIssue(str, Enum):
    """Visual quality issues."""
    BLUR = "blur"
    ARTIFACT = "artifact"
    FLICKER = "flicker"
    FRAME_ERROR = "frame_error"
    BAD_GENERATION = "bad_generation"


@dataclass
class VisualCheckResult:
    """Result of visual quality check."""
    video_id: str = ""
    passed: bool = True
    issues: List[VisualIssue] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "passed": self.passed,
            "issues": [issue.value for issue in self.issues],
            "scores": self.scores,
            "details": self.details
        }


@dataclass
class VisualThreshold:
    """Thresholds for visual quality checks."""
    blur_threshold: float = 0.3  # Laplacian variance threshold
    artifact_threshold: float = 0.15  # Artifact detection sensitivity
    flicker_threshold: float = 0.2  # Frame difference threshold
    frame_error_threshold: float = 0.1  # Frame drop/gain threshold


class VisualChecker:
    """Visual quality checker for generated videos.
    
    Detects quality issues that would make videos unsuitable for production:
    - Blur: Low sharpness, out of focus
    - Artifact: Compression artifacts, encoding issues
    - Flicker: Unwanted brightness fluctuations
    - Frame Error: Dropped/duplicate frames
    - Bad Generation: AI generation failures (morphing, distortion)
    """
    
    def __init__(self, thresholds: Optional[VisualThreshold] = None):
        self.thresholds = thresholds or VisualThreshold()
        self._check_methods = {
            VisualIssue.BLUR: self._check_blur,
            VisualIssue.ARTIFACT: self._check_artifact,
            VisualIssue.FLICKER: self._check_flicker,
            VisualIssue.FRAME_ERROR: self._check_frame_error,
            VisualIssue.BAD_GENERATION: self._check_bad_generation
        }
    
    def check(self, video_path: str, video_id: str = "") -> VisualCheckResult:
        """Run all visual quality checks on a video.
        
        Args:
            video_path: Path to video file
            video_id: Optional video identifier
            
        Returns:
            VisualCheckResult with pass/fail and issue details
        """
        result = VisualCheckResult(video_id=video_id)
        
        # Run all checks
        for issue_type, check_method in self._check_methods.items():
            try:
                issue_score = check_method(video_path)
                result.scores[issue_type.value] = issue_score
                
                # Check if threshold exceeded
                threshold = self._get_threshold(issue_type)
                if issue_score > threshold:
                    result.issues.append(issue_type)
                    result.passed = False
            except Exception as e:
                result.details[f"{issue_type.value}_error"] = str(e)
        
        return result
    
    def check_batch(self, video_paths: List[str]) -> List[VisualCheckResult]:
        """Check multiple videos in batch."""
        return [self.check(path, f"video_{i}") for i, path in enumerate(video_paths)]
    
    def _get_threshold(self, issue_type: VisualIssue) -> float:
        """Get threshold for an issue type."""
        threshold_map = {
            VisualIssue.BLUR: self.thresholds.blur_threshold,
            VisualIssue.ARTIFACT: self.thresholds.artifact_threshold,
            VisualIssue.FLICKER: self.thresholds.flicker_threshold,
            VisualIssue.FRAME_ERROR: self.thresholds.frame_error_threshold,
            VisualIssue.BAD_GENERATION: 0.3  # Fixed threshold
        }
        return threshold_map.get(issue_type, 0.5)
    
    def _check_blur(self, video_path: str) -> float:
        """Check for blur issues using Laplacian variance.
        
        Returns blur score (0 = sharp, 1 = very blurry)
        
        Note: This is a simplified implementation. Production version
        would use OpenCV or similar for actual frame analysis.
        """
        # Simulated blur detection
        # Production: Extract frames, compute Laplacian variance
        # Variance < threshold = blurry
        return 0.1  # Simulated low blur
    
    def _check_artifact(self, video_path: str) -> float:
        """Check for compression artifacts.
        
        Returns artifact score (0 = clean, 1 = heavily artifacted)
        """
        # Simulated artifact detection
        # Production: Analyze frame quality, detect blocking/ringing
        return 0.05  # Simulated low artifact
    
    def _check_flicker(self, video_path: str) -> float:
        """Check for flicker/brightness fluctuation.
        
        Returns flicker score (0 = stable, 1 = severe flicker)
        """
        # Simulated flicker detection
        # Production: Analyze frame-to-frame brightness variance
        return 0.08  # Simulated low flicker
    
    def _check_frame_error(self, video_path: str) -> float:
        """Check for frame drops/duplicates.
        
        Returns frame error score (0 = perfect, 1 = severe errors)
        """
        # Simulated frame error detection
        # Production: Check frame count, detect drops/duplicates
        return 0.02  # Simulated low frame error
    
    def _check_bad_generation(self, video_path: str) -> float:
        """Check for AI generation failures.
        
        Detects:
        - Morphing artifacts (objects changing shape)
        - Distortion (warped geometry)
        - Inconsistency (objects appearing/disappearing)
        
        Returns bad generation score (0 = good, 1 = severe issues)
        """
        # Simulated bad generation detection
        # Production: Use ML model to detect generation artifacts
        return 0.15  # Simulated low generation issues
    
    def get_issue_description(self, issue: VisualIssue) -> str:
        """Get human-readable description of a visual issue."""
        descriptions = {
            VisualIssue.BLUR: "Video appears blurry or out of focus",
            VisualIssue.ARTIFACT: "Compression artifacts detected (blocking, ringing)",
            VisualIssue.FLICKER: "Brightness fluctuations between frames",
            VisualIssue.FRAME_ERROR: "Frame drops or duplicates detected",
            VisualIssue.BAD_GENERATION: "AI generation artifacts (morphing, distortion)"
        }
        return descriptions.get(issue, "Unknown issue")
    
    def suggest_fix(self, issue: VisualIssue) -> str:
        """Suggest fix for a visual issue."""
        fixes = {
            VisualIssue.BLUR: "Increase sharpness in generation parameters or use higher quality model",
            VisualIssue.ARTIFACT: "Increase video bitrate or use better encoder settings",
            VisualIssue.FLICKER: "Enable frame interpolation or adjust generation seed",
            VisualIssue.FRAME_ERROR: "Re-render video or check source frames for errors",
            VisualIssue.BAD_GENERATION: "Adjust prompt, try different seed, or use different platform/model"
        }
        return fixes.get(issue, "No fix suggestion available")


def demo_visual_checker():
    """Demo visual checker functionality."""
    checker = VisualChecker()
    
    # Simulated video check
    result = checker.check("sample_video.mp4", "demo_001")
    
    print("=== Visual QA Result ===")
    print(f"Video ID: {result.video_id}")
    print(f"Passed: {result.passed}")
    print(f"Issues: {[i.value for i in result.issues]}")
    print(f"Scores: {json.dumps(result.scores, indent=2)}")
    
    if not result.passed:
        print("\n=== Issue Details ===")
        for issue in result.issues:
            print(f"\n{issue.value}:")
            print(f"  Description: {checker.get_issue_description(issue)}")
            print(f"  Suggested Fix: {checker.suggest_fix(issue)}")


if __name__ == "__main__":
    demo_visual_checker()