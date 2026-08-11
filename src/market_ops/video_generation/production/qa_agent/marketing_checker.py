"""Marketing QA Checker for generated videos.

Detects marketing effectiveness issues:
- First 3 second hook
- Product visibility
- Call-to-action (CTA)
- Emotion engagement
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json
from pathlib import Path


class MarketingDimension(str, Enum):
    """Marketing effectiveness dimensions."""
    HOOK = "hook"  # First 3 second hook quality
    PRODUCT_VISIBILITY = "product_visibility"
    CTA = "cta"  # Call-to-action clarity
    EMOTION = "emotion"  # Emotional engagement


@dataclass
class MarketingCheckResult:
    """Result of marketing quality check."""
    video_id: str = ""
    passed: bool = True
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "passed": self.passed,
            "dimension_scores": self.dimension_scores,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "details": self.details
        }


@dataclass
class MarketingThreshold:
    """Thresholds for marketing quality checks."""
    hook_min_score: float = 70.0  # First 3 seconds engagement score
    product_visibility_min: float = 60.0  # Product visibility score
    cta_clarity_min: float = 65.0  # CTA clarity score
    emotion_min_score: float = 55.0  # Emotional engagement score
    overall_min_score: float = 65.0  # Overall marketing score


class MarketingChecker:
    """Marketing quality checker for generated videos.
    
    Evaluates marketing effectiveness across key dimensions:
    - Hook: First 3 seconds engagement and attention capture
    - Product Visibility: How well product is shown
    - CTA: Call-to-action clarity and placement
    - Emotion: Emotional resonance and engagement
    """
    
    def __init__(self, thresholds: Optional[MarketingThreshold] = None):
        self.thresholds = thresholds or MarketingThreshold()
        self._check_methods = {
            MarketingDimension.HOOK: self._check_hook,
            MarketingDimension.PRODUCT_VISIBILITY: self._check_product_visibility,
            MarketingDimension.CTA: self._check_cta,
            MarketingDimension.EMOTION: self._check_emotion
        }
    
    def check(self, video_path: str, video_id: str = "", 
              blueprint: Optional[Dict[str, Any]] = None) -> MarketingCheckResult:
        """Run all marketing quality checks on a video.
        
        Args:
            video_path: Path to video file
            video_id: Optional video identifier
            blueprint: Optional creative blueprint for context
            
        Returns:
            MarketingCheckResult with scores and recommendations
        """
        result = MarketingCheckResult(video_id=video_id)
        
        # Run all dimension checks
        for dimension, check_method in self._check_methods.items():
            try:
                score = check_method(video_path, blueprint)
                result.dimension_scores[dimension.value] = score
                
                # Check threshold
                threshold = self._get_threshold(dimension)
                if score < threshold:
                    issue = f"{dimension.value}_below_threshold"
                    result.issues.append(issue)
                    result.recommendations.append(self._get_recommendation(dimension, score))
            except Exception as e:
                result.details[f"{dimension.value}_error"] = str(e)
                result.dimension_scores[dimension.value] = 0.0
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(result.dimension_scores)
        result.details["overall_score"] = overall_score
        
        # Check if passed
        if overall_score < self.thresholds.overall_min_score:
            result.passed = False
            result.issues.append("overall_score_below_threshold")
        
        # Check if any dimension below threshold
        for dimension in MarketingDimension:
            if result.dimension_scores.get(dimension.value, 0) < self._get_threshold(dimension):
                result.passed = False
                break
        
        return result
    
    def check_batch(self, video_paths: List[str], 
                    blueprints: Optional[List[Dict[str, Any]]] = None) -> List[MarketingCheckResult]:
        """Check multiple videos in batch."""
        results = []
        for i, path in enumerate(video_paths):
            blueprint = blueprints[i] if blueprints and i < len(blueprints) else None
            results.append(self.check(path, f"video_{i}", blueprint))
        return results
    
    def _get_threshold(self, dimension: MarketingDimension) -> float:
        """Get threshold for a dimension."""
        threshold_map = {
            MarketingDimension.HOOK: self.thresholds.hook_min_score,
            MarketingDimension.PRODUCT_VISIBILITY: self.thresholds.product_visibility_min,
            MarketingDimension.CTA: self.thresholds.cta_clarity_min,
            MarketingDimension.EMOTION: self.thresholds.emotion_min_score
        }
        return threshold_map.get(dimension, 60.0)
    
    def _check_hook(self, video_path: str, blueprint: Optional[Dict[str, Any]]) -> float:
        """Check first 3 second hook quality.
        
        Evaluates:
        - Attention capture in first 3 seconds
        - Visual interest and movement
        - Curiosity/interest trigger
        
        Returns hook score (0-100)
        """
        # Simulated hook analysis
        # Production: Extract first 3 seconds, analyze engagement markers
        score = 78.0
        
        # Adjust based on blueprint if available
        if blueprint:
            # Check if blueprint has hook specifications
            hook_elements = blueprint.get("hook_elements", [])
            if hook_elements:
                score += min(10, len(hook_elements) * 2)
        
        return min(100.0, score)
    
    def _check_product_visibility(self, video_path: str, blueprint: Optional[Dict[str, Any]]) -> float:
        """Check product visibility and prominence.
        
        Evaluates:
        - Product screen time
        - Product clarity and focus
        - Product positioning
        
        Returns product visibility score (0-100)
        """
        # Simulated product visibility analysis
        # Production: Use object detection to track product visibility
        score = 72.0
        
        if blueprint:
            # Check if blueprint has product specifications
            product_focus = blueprint.get("product_focus", False)
            if product_focus:
                score += 10
        
        return min(100.0, score)
    
    def _check_cta(self, video_path: str, blueprint: Optional[Dict[str, Any]]) -> float:
        """Check call-to-action clarity and placement.
        
        Evaluates:
        - CTA presence and timing
        - CTA clarity and readability
        - CTA relevance to content
        
        Returns CTA score (0-100)
        """
        # Simulated CTA analysis
        # Production: OCR and text detection for CTA elements
        score = 68.0
        
        if blueprint:
            # Check if blueprint has CTA specifications
            cta_type = blueprint.get("cta_type", "")
            if cta_type:
                score += 12
        
        return min(100.0, score)
    
    def _check_emotion(self, video_path: str, blueprint: Optional[Dict[str, Any]]) -> float:
        """Check emotional engagement.
        
        Evaluates:
        - Emotional resonance
        - Story/flow coherence
        - Audience connection
        
        Returns emotion score (0-100)
        """
        # Simulated emotion analysis
        # Production: Use sentiment/emotion detection models
        score = 65.0
        
        if blueprint:
            # Check if blueprint has emotional targets
            emotional_tone = blueprint.get("emotional_tone", "")
            if emotional_tone:
                score += 8
        
        return min(100.0, score)
    
    def _calculate_overall_score(self, dimension_scores: Dict[str, float]) -> float:
        """Calculate weighted overall marketing score.
        
        Weights:
        - Hook: 35% (most important for ad performance)
        - Product: 25%
        - CTA: 20%
        - Emotion: 20%
        """
        weights = {
            "hook": 0.35,
            "product_visibility": 0.25,
            "cta": 0.20,
            "emotion": 0.20
        }
        
        total = 0.0
        for dimension, weight in weights.items():
            score = dimension_scores.get(dimension, 0.0)
            total += score * weight
        
        return total
    
    def _get_recommendation(self, dimension: MarketingDimension, score: float) -> str:
        """Get recommendation for improving a dimension."""
        recommendations = {
            MarketingDimension.HOOK: (
                "Enhance first 3 seconds with stronger visual hook, "
                "add movement or surprise element"
            ),
            MarketingDimension.PRODUCT_VISIBILITY: (
                "Increase product screen time, ensure clear product shots, "
                "improve lighting on product"
            ),
            MarketingDimension.CTA: (
                "Add clear call-to-action in last 2-3 seconds, "
                "make CTA text larger and more prominent"
            ),
            MarketingDimension.EMOTION: (
                "Strengthen emotional connection, add storytelling elements, "
                "align music and pacing with emotional arc"
            )
        }
        return recommendations.get(dimension, "Review and improve content quality")


def demo_marketing_checker():
    """Demo marketing checker functionality."""
    checker = MarketingChecker()
    
    # Simulated video check with blueprint
    blueprint = {
        "hook_elements": ["question", "movement", "contrast"],
        "product_focus": True,
        "cta_type": "button",
        "emotional_tone": "excitement"
    }
    
    result = checker.check("sample_video.mp4", "demo_001", blueprint)
    
    print("=== Marketing QA Result ===")
    print(f"Video ID: {result.video_id}")
    print(f"Passed: {result.passed}")
    print(f"\nDimension Scores:")
    for dimension, score in result.dimension_scores.items():
        threshold = checker._get_threshold(MarketingDimension(dimension))
        status = "✓" if score >= threshold else "✗"
        print(f"  {dimension}: {score:.1f} (threshold: {threshold}) {status}")
    
    print(f"\nOverall Score: {result.details.get('overall_score', 0):.1f}")
    
    if result.issues:
        print(f"\nIssues: {result.issues}")
    
    if result.recommendations:
        print(f"\nRecommendations:")
        for rec in result.recommendations:
            print(f"  - {rec}")


if __name__ == "__main__":
    demo_marketing_checker()