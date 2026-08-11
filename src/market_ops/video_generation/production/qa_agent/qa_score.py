"""QA Score Calculator for Creative Quality Assessment.

Combines Visual QA and Marketing QA into final quality score.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

from .visual_checker import VisualChecker, VisualCheckResult, VisualIssue
from .marketing_checker import MarketingChecker, MarketingCheckResult, MarketingDimension


class QAGrade(str, Enum):
    """Quality grade levels."""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"           # 80-89
    ACCEPTABLE = "acceptable"  # 70-79
    BELOW_STANDARD = "below_standard"  # 60-69
    POOR = "poor"           # 0-59


@dataclass
class QAScore:
    """Combined QA score for a video."""
    video_id: str = ""
    visual_score: float = 0.0
    hook_score: float = 0.0
    conversion_score: float = 0.0
    final_score: float = 0.0
    grade: QAGrade = QAGrade.POOR
    passed: bool = False
    visual_issues: List[str] = field(default_factory=list)
    marketing_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "visual_score": round(self.visual_score, 2),
            "hook_score": round(self.hook_score, 2),
            "conversion_score": round(self.conversion_score, 2),
            "final_score": round(self.final_score, 2),
            "grade": self.grade.value,
            "passed": self.passed,
            "visual_issues": self.visual_issues,
            "marketing_issues": self.marketing_issues,
            "recommendations": self.recommendations,
            "details": self.details
        }


@dataclass
class QAThreshold:
    """Thresholds for QA scoring."""
    visual_weight: float = 0.40
    hook_weight: float = 0.35
    conversion_weight: float = 0.25
    passing_score: float = 70.0
    excellent_threshold: float = 90.0
    good_threshold: float = 80.0
    acceptable_threshold: float = 70.0
    below_standard_threshold: float = 60.0


class QAScorer:
    """QA Scorer combining Visual and Marketing quality assessments.
    
    Final score = Visual(40%) + Hook(35%) + Conversion(25%)
    
    Where:
    - Visual Score: From VisualChecker (blur, artifact, flicker, etc.)
    - Hook Score: First 3 second engagement from MarketingChecker
    - Conversion Score: Product visibility + CTA + Emotion
    """
    
    def __init__(
        self,
        visual_checker: Optional[VisualChecker] = None,
        marketing_checker: Optional[MarketingChecker] = None,
        thresholds: Optional[QAThreshold] = None
    ):
        self.visual_checker = visual_checker or VisualChecker()
        self.marketing_checker = marketing_checker or MarketingChecker()
        self.thresholds = thresholds or QAThreshold()
    
    def score(
        self,
        video_path: str,
        video_id: str = "",
        blueprint: Optional[Dict[str, Any]] = None
    ) -> QAScore:
        """Calculate comprehensive QA score for a video.
        
        Args:
            video_path: Path to video file
            video_id: Optional video identifier
            blueprint: Optional creative blueprint for context
            
        Returns:
            QAScore with visual, hook, conversion, and final scores
        """
        qa_score = QAScore(video_id=video_id)
        
        # Run Visual QA
        visual_result = self.visual_checker.check(video_path, video_id)
        qa_score.visual_score = self._calculate_visual_score(visual_result)
        qa_score.visual_issues = [issue.value for issue in visual_result.issues]
        
        # Run Marketing QA
        marketing_result = self.marketing_checker.check(video_path, video_id, blueprint)
        qa_score.hook_score = marketing_result.dimension_scores.get("hook", 0.0)
        qa_score.conversion_score = self._calculate_conversion_score(marketing_result)
        qa_score.marketing_issues = marketing_result.issues
        
        # Calculate final score
        qa_score.final_score = self._calculate_final_score(
            qa_score.visual_score,
            qa_score.hook_score,
            qa_score.conversion_score
        )
        
        # Determine grade
        qa_score.grade = self._determine_grade(qa_score.final_score)
        
        # Determine if passed
        qa_score.passed = qa_score.final_score >= self.thresholds.passing_score
        
        # Collect recommendations
        qa_score.recommendations = self._collect_recommendations(
            visual_result,
            marketing_result
        )
        
        # Store details
        qa_score.details = {
            "visual_scores": visual_result.scores,
            "marketing_scores": marketing_result.dimension_scores,
            "overall_marketing_score": marketing_result.details.get("overall_score", 0.0)
        }
        
        return qa_score
    
    def score_batch(
        self,
        video_paths: List[str],
        blueprints: Optional[List[Dict[str, Any]]] = None
    ) -> List[QAScore]:
        """Score multiple videos in batch."""
        results = []
        for i, path in enumerate(video_paths):
            blueprint = blueprints[i] if blueprints and i < len(blueprints) else None
            results.append(self.score(path, f"video_{i}", blueprint))
        return results
    
    def _calculate_visual_score(self, visual_result: VisualCheckResult) -> float:
        """Calculate visual quality score from VisualCheckResult.
        
        Score is penalized for each detected issue.
        Base score: 100
        Penalty per issue: 15 points
        """
        base_score = 100.0
        penalty_per_issue = 15.0
        
        # Calculate score based on issues
        score = base_score - (len(visual_result.issues) * penalty_per_issue)
        
        # Adjust based on individual scores (lower score = more severe issue)
        for issue_type, issue_score in visual_result.scores.items():
            # issue_score is 0-1 where 1 = severe issue
            score -= issue_score * 5  # Additional penalty
        
        return max(0.0, min(100.0, score))
    
    def _calculate_conversion_score(self, marketing_result: MarketingCheckResult) -> float:
        """Calculate conversion potential score from MarketingCheckResult.
        
        Conversion = Product Visibility * 0.4 + CTA * 0.3 + Emotion * 0.3
        """
        product = marketing_result.dimension_scores.get("product_visibility", 0.0)
        cta = marketing_result.dimension_scores.get("cta", 0.0)
        emotion = marketing_result.dimension_scores.get("emotion", 0.0)
        
        conversion_score = (product * 0.4) + (cta * 0.3) + (emotion * 0.3)
        
        return conversion_score
    
    def _calculate_final_score(
        self,
        visual_score: float,
        hook_score: float,
        conversion_score: float
    ) -> float:
        """Calculate final weighted QA score.
        
        Final = Visual(40%) + Hook(35%) + Conversion(25%)
        """
        final = (
            visual_score * self.thresholds.visual_weight +
            hook_score * self.thresholds.hook_weight +
            conversion_score * self.thresholds.conversion_weight
        )
        
        return final
    
    def _determine_grade(self, score: float) -> QAGrade:
        """Determine quality grade from score."""
        if score >= self.thresholds.excellent_threshold:
            return QAGrade.EXCELLENT
        elif score >= self.thresholds.good_threshold:
            return QAGrade.GOOD
        elif score >= self.thresholds.acceptable_threshold:
            return QAGrade.ACCEPTABLE
        elif score >= self.thresholds.below_standard_threshold:
            return QAGrade.BELOW_STANDARD
        else:
            return QAGrade.POOR
    
    def _collect_recommendations(
        self,
        visual_result: VisualCheckResult,
        marketing_result: MarketingCheckResult
    ) -> List[str]:
        """Collect improvement recommendations from both checkers."""
        recommendations = []
        
        # Visual recommendations
        for issue in visual_result.issues:
            fix = self.visual_checker.suggest_fix(issue)
            recommendations.append(f"[Visual] {fix}")
        
        # Marketing recommendations
        for rec in marketing_result.recommendations:
            recommendations.append(f"[Marketing] {rec}")
        
        return recommendations
    
    def get_grade_description(self, grade: QAGrade) -> str:
        """Get human-readable description of a grade."""
        descriptions = {
            QAGrade.EXCELLENT: "Production ready, high quality. No improvements needed.",
            QAGrade.GOOD: "Production ready, good quality. Minor improvements possible.",
            QAGrade.ACCEPTABLE: "Production acceptable. Some improvements recommended.",
            QAGrade.BELOW_STANDARD: "Below production standard. Improvements required.",
            QAGrade.POOR: "Not production ready. Major issues need to be addressed."
        }
        return descriptions.get(grade, "Unknown grade")


def demo_qa_scorer():
    """Demo QA scorer functionality."""
    scorer = QAScorer()
    
    # Simulated video with blueprint
    blueprint = {
        "hook_elements": ["question", "movement"],
        "product_focus": True,
        "cta_type": "button",
        "emotional_tone": "excitement"
    }
    
    qa_score = scorer.score("sample_video.mp4", "demo_001", blueprint)
    
    print("=== QA Score Result ===")
    print(f"Video ID: {qa_score.video_id}")
    print(f"\nScores:")
    print(f"  Visual Score: {qa_score.visual_score:.1f}")
    print(f"  Hook Score: {qa_score.hook_score:.1f}")
    print(f"  Conversion Score: {qa_score.conversion_score:.1f}")
    print(f"\n  Final Score: {qa_score.final_score:.1f}")
    print(f"  Grade: {qa_score.grade.value}")
    print(f"  Passed: {'✓' if qa_score.passed else '✗'}")
    
    print(f"\nGrade Description: {scorer.get_grade_description(qa_score.grade)}")
    
    if qa_score.visual_issues:
        print(f"\nVisual Issues: {qa_score.visual_issues}")
    
    if qa_score.marketing_issues:
        print(f"\nMarketing Issues: {qa_score.marketing_issues}")
    
    if qa_score.recommendations:
        print(f"\nRecommendations:")
        for rec in qa_score.recommendations:
            print(f"  - {rec}")
    
    print(f"\n=== JSON Output ===")
    print(json.dumps(qa_score.to_dict(), indent=2))


if __name__ == "__main__":
    demo_qa_scorer()