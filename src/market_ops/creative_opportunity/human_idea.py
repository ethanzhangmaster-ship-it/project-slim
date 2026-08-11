"""Human Idea Inbox — collect and manage human game concepts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from market_ops.creative_opportunity.schemas import HumanIdea, OpportunitySource, OpportunityStatus


class HumanIdeaInbox:
    """Collect, store, and retrieve human-submitted ideas."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._ideas: list[HumanIdea] = []
        self._storage_dir = storage_dir

    # ── Input Methods ───────────────────────────────────────

    def submit_text(
        self,
        title: str,
        description: str,
        reference_games: list[str] | None = None,
        creator: str = "",
        tags: list[str] | None = None,
    ) -> HumanIdea:
        """Submit a text-based idea."""
        idea = HumanIdea(
            source=OpportunitySource.HUMAN,
            title=title,
            description=description,
            reference_games=reference_games or [],
            creator=creator,
            tags=tags or [],
        )
        self._ideas.append(idea)
        return idea

    def submit_url(self, url: str, creator: str = "", notes: str = "") -> HumanIdea:
        """Submit an idea from a URL (Google Play, App Store, etc.)."""
        # In MVP, we just store the URL as metadata
        # In v2, we could scrape/analyze the URL content
        idea = HumanIdea(
            source=OpportunitySource.HUMAN,
            title=f"URL: {url[:50]}",
            description=notes,
            creator=creator,
            metadata={"url": url, "source_type": self._detect_url_type(url)},
        )
        self._ideas.append(idea)
        return idea

    # ── Query Methods ───────────────────────────────────────

    def get_all(self) -> list[HumanIdea]:
        """Return all submitted ideas."""
        return list(self._ideas)

    def get_pending(self) -> list[HumanIdea]:
        """Return ideas awaiting review."""
        return [i for i in self._ideas if i.status == OpportunityStatus.PENDING]

    def get_by_id(self, idea_id: str) -> HumanIdea | None:
        """Find an idea by ID."""
        for idea in self._ideas:
            if idea.idea_id == idea_id:
                return idea
        return None

    def get_by_creator(self, creator: str) -> list[HumanIdea]:
        """Find ideas by creator."""
        return [i for i in self._ideas if i.creator == creator]

    # ── State Management ────────────────────────────────────

    def approve(self, idea_id: str) -> HumanIdea | None:
        """Mark an idea as approved."""
        idea = self.get_by_id(idea_id)
        if idea:
            idea.status = OpportunityStatus.APPROVED
        return idea

    def reject(self, idea_id: str) -> HumanIdea | None:
        """Mark an idea as rejected."""
        idea = self.get_by_id(idea_id)
        if idea:
            idea.status = OpportunityStatus.REJECTED
        return idea

    # ── Internal ────────────────────────────────────────────

    @staticmethod
    def _detect_url_type(url: str) -> str:
        """Detect what kind of URL was submitted."""
        url_lower = url.lower()
        if "play.google.com" in url_lower:
            return "google_play"
        if "apps.apple.com" in url_lower:
            return "app_store"
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "reddit.com" in url_lower:
            return "reddit"
        return "unknown"
