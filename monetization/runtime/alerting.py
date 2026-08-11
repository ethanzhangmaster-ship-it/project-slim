"""
E14.2 — Module 6: Alert Provider Interface
============================================

The first version does NOT wire a real service (Datadog / CloudWatch / Slack).
It defines a clean `AlertProvider` interface plus a `MockAlertProvider` that
captures everything in-memory. Later (E14.5 Observability) a concrete
provider (HTTP / SDK) can be dropped in without touching the caller.

All runtime components (Supervisor, Recovery, Health) only ever call
`alert_provider.send(alert)` — so the delivery channel is fully pluggable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


# Alert severity levels (compatible with common observability back-ends)
ALERT_INFO = "info"
ALERT_WARNING = "warning"
ALERT_CRITICAL = "critical"
ALERT_LEVELS = (ALERT_INFO, ALERT_WARNING, ALERT_CRITICAL)


@dataclass
class Alert:
    """A structured alert emitted by the runtime layer."""
    level: str                      # ALERT_LEVELS
    message: str
    game: str = ""                  # empty = fleet-wide
    source: str = ""                # component that raised it (supervisor/recovery/health)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class AlertProvider(ABC):
    """Pluggable alert sink. Implement `send` to deliver to a real backend."""

    @abstractmethod
    def send(self, alert: Alert) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MockAlertProvider(AlertProvider):
    """In-memory capture used for v1 and for tests. No external side effects."""

    def __init__(self):
        self.sent: List[Alert] = []

    def send(self, alert: Alert) -> None:
        self.sent.append(alert)

    # ---- query helpers (for assertions / dashboards) ----
    def by_level(self, level: str) -> List[Alert]:
        return [a for a in self.sent if a.level == level]

    def for_game(self, game: str) -> List[Alert]:
        return [a for a in self.sent if a.game == game]

    def count(self) -> int:
        return len(self.sent)

    def to_dicts(self) -> List[dict]:
        return [a.to_dict() for a in self.sent]


__all__ = [
    "Alert", "AlertProvider", "MockAlertProvider",
    "ALERT_INFO", "ALERT_WARNING", "ALERT_CRITICAL", "ALERT_LEVELS",
]
