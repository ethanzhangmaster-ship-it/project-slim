from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random


@dataclass
class CompetitorRecord:
    name: str
    market_share: float
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    last_updated: str = ""


class CompetitorMemory:
    """Track competitor intelligence."""

    def __init__(self):
        self._competitors: Dict[str, CompetitorRecord] = {}

    def record_competitor(self, name: str, data: CompetitorRecord) -> None:
        """Record or update competitor data."""
        data.name = name
        if not data.last_updated:
            from datetime import datetime
            data.last_updated = datetime.now().isoformat()
        self._competitors[name] = data

    def get_competitor(self, name: str) -> Optional[CompetitorRecord]:
        """Retrieve a specific competitor by name."""
        return self._competitors.get(name)

    def get_all_competitors(self) -> List[CompetitorRecord]:
        """Return all tracked competitors."""
        return list(self._competitors.values())
