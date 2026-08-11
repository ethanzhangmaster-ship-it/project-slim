"""QA Agent Module for Creative Quality Assessment.

Provides comprehensive quality assessment for generated videos:
- Visual QA: Detects blur, artifacts, flicker, frame errors, bad generation
- Marketing QA: Evaluates hook, product visibility, CTA, emotion
- QA Score: Combines both into final quality score
"""

from .visual_checker import (
    VisualChecker,
    VisualCheckResult,
    VisualIssue,
    VisualThreshold
)

from .marketing_checker import (
    MarketingChecker,
    MarketingCheckResult,
    MarketingDimension,
    MarketingThreshold
)

from .qa_score import (
    QAScorer,
    QAScore,
    QAGrade,
    QAThreshold
)

__all__ = [
    # Visual QA
    "VisualChecker",
    "VisualCheckResult",
    "VisualIssue",
    "VisualThreshold",
    
    # Marketing QA
    "MarketingChecker",
    "MarketingCheckResult",
    "MarketingDimension",
    "MarketingThreshold",
    
    # QA Score
    "QAScorer",
    "QAScore",
    "QAGrade",
    "QAThreshold"
]