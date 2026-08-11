"""
E15.1.6 — Review Agent
"""
from operation.publishing.review.models import ReviewFixPlan, ReviewRejectEvent
from operation.publishing.review.rule_engine import ReviewRuleEngine


class ReviewAgent:
    """Analyzes store rejection events and produces a fix plan."""

    def __init__(self, engine: ReviewRuleEngine = None):
        self.engine = engine or ReviewRuleEngine()

    def analyze(self, event: ReviewRejectEvent) -> ReviewFixPlan:
        return self.engine.analyze(event)


__all__ = ["ReviewAgent"]
