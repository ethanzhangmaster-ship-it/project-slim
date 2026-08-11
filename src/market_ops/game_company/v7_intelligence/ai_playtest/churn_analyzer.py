from dataclasses import dataclass, field
from typing import List, Dict
import random


@dataclass
class ChurnReport:
    churn_rate: float
    top_reasons: List[str] = field(default_factory=list)
    risk_segments: List[str] = field(default_factory=list)


class ChurnAnalyzer:
    """Analyze player churn and reasons."""

    def __init__(self):
        self._report: ChurnReport = ChurnReport(churn_rate=0.0)

    def analyze_churn(self) -> ChurnReport:
        """Run churn analysis and return a report."""
        self._report = ChurnReport(
            churn_rate=round(random.uniform(0.1, 0.6), 4),
            top_reasons=random.sample(
                [
                    "difficulty_spike",
                    "lack_of_content",
                    "poor_matchmaking",
                    "monetization_pressure",
                    "social_toxicity",
                    "performance_issues",
                ],
                k=3,
            ),
            risk_segments=random.sample(
                ["new_players", "whales", "casual", "competitive"], k=2
            ),
        )
        return self._report

    def get_churn_reasons(self) -> List[str]:
        """Return top churn reasons."""
        if not self._report.top_reasons:
            self.analyze_churn()
        return self._report.top_reasons

    def predict_churn_rate(self) -> float:
        """Return predicted churn rate."""
        if self._report.churn_rate == 0.0:
            self.analyze_churn()
        return self._report.churn_rate
