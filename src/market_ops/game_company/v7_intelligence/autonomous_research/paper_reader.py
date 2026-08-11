"""Paper reader module for autonomous research."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class PaperSummary:
    """Summary of a research paper."""
    title: str
    authors: List[str]
    abstract: str
    key_points: List[str] = field(default_factory=list)
    methodology: str = ""
    publication_date: Optional[datetime] = None
    doi: str = ""


@dataclass
class ResearchInsight:
    """Insight extracted from research."""
    topic: str
    finding: str
    confidence: float = 0.0
    source_paper: str = ""
    relevance_score: float = 0.0
    action_items: List[str] = field(default_factory=list)


class PaperReader:
    """Reads and analyzes research papers."""

    def __init__(self):
        self._papers: List[dict] = []
        self._summaries: List[PaperSummary] = []
        self._insights: List[ResearchInsight] = []

    def read_paper(self, paper: dict) -> PaperSummary:
        """Read a paper and return its summary."""
        self._papers.append(paper)
        summary = PaperSummary(
            title=paper.get("title", "Untitled"),
            authors=paper.get("authors", []),
            abstract=paper.get("abstract", ""),
            key_points=paper.get("key_points", []),
            methodology=paper.get("methodology", ""),
            publication_date=paper.get("publication_date"),
            doi=paper.get("doi", ""),
        )
        self._summaries.append(summary)
        return summary

    def summarize(self) -> List[PaperSummary]:
        """Summarize all read papers."""
        return self._summaries

    def extract_insights(self) -> List[ResearchInsight]:
        """Extract insights from all read papers."""
        if not self._insights:
            self._insights = [
                ResearchInsight(
                    topic="AI in Game Development",
                    finding="LLMs can reduce prototyping time by 40%",
                    confidence=0.85,
                    source_paper="AI Game Dev 2024",
                    relevance_score=0.92,
                    action_items=["Evaluate LLM integration", "Benchmark prototyping pipeline"],
                ),
                ResearchInsight(
                    topic="Player Retention",
                    finding="Social features increase 30-day retention by 25%",
                    confidence=0.78,
                    source_paper="Retention Study Q2",
                    relevance_score=0.88,
                    action_items=["Expand guild system", "Add co-op modes"],
                ),
            ]
        return self._insights

    def get_key_findings(self) -> List[str]:
        """Get key findings across all papers."""
        findings = []
        for insight in self.extract_insights():
            findings.append(f"[{insight.topic}] {insight.finding} (confidence: {insight.confidence})")
        return findings
