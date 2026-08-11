"""E15.2.7 §6 — Cooldown manager. Simple time-based gate: has the
required cooldown elapsed since the last ad was shown?"""
from datetime import datetime, timedelta, timezone

class CooldownManager:
    def can_show(self, last_shown_at: str, cooldown_sec: int) -> bool:
        if not last_shown_at:
            return True
        try:
            last = datetime.fromisoformat(last_shown_at)
            return (datetime.now(timezone.utc) - last).total_seconds() >= cooldown_sec
        except (ValueError, TypeError):
            return True
