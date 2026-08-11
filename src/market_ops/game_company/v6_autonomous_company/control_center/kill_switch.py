from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum


class KillSwitchLevel(Enum):
    MONITOR = "monitor"
    WARN = "warn"
    PAUSE_NEW = "pause_new"
    PAUSE_ALL = "pause_all"
    FULL_STOP = "full_stop"


class KillSwitchTrigger(Enum):
    SPEND_SPIKE = "spend_spike"
    REVENUE_DROP = "revenue_drop"
    FRAUD_DETECTED = "fraud_detected"
    CRASH_SPIKE = "crash_spike"
    MANUAL = "manual"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class KillSwitchEvent:
    event_id: str
    trigger: KillSwitchTrigger
    level: KillSwitchLevel
    reason: str
    triggered_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    triggered_by: str = "system"
    affected_systems: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution_notes: str = ""


class KillSwitch:
    def __init__(self):
        self._current_level = KillSwitchLevel.MONITOR
        self._events: List[KillSwitchEvent] = []
        self._callbacks: Dict[str, List[Callable]] = {
            "on_pause": [],
            "on_resume": [],
            "on_stop": [],
        }
        self._paused_systems: set = set()
        self._thresholds = {
            "spend_spike_rate": 3.0,
            "revenue_drop_rate": 0.7,
            "fraud_rate": 0.3,
            "crash_rate": 0.1,
        }

    def register_callback(self, event_type: str, callback: Callable):
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def _trigger_event(
        self,
        trigger: KillSwitchTrigger,
        level: KillSwitchLevel,
        reason: str,
        triggered_by: str = "system",
        affected_systems: List[str] = None,
    ) -> KillSwitchEvent:
        event = KillSwitchEvent(
            event_id=f"ks_{trigger.value}_{hash(reason + str(datetime.now())) % 10000:04d}",
            trigger=trigger,
            level=level,
            reason=reason,
            triggered_by=triggered_by,
            affected_systems=affected_systems or [],
        )

        self._events.append(event)
        self._current_level = level

        if level in (KillSwitchLevel.PAUSE_ALL, KillSwitchLevel.FULL_STOP):
            self._paused_systems = {"ua", "creative", "bidding", "campaign_management"}
            for cb in self._callbacks.get("on_pause", []):
                try:
                    cb(event)
                except Exception:
                    pass

        if level == KillSwitchLevel.FULL_STOP:
            for cb in self._callbacks.get("on_stop", []):
                try:
                    cb(event)
                except Exception:
                    pass

        return event

    def check_spend(self, current_spend: float, baseline_spend: float) -> Optional[KillSwitchEvent]:
        if baseline_spend <= 0:
            return None

        rate = current_spend / baseline_spend

        if rate >= self._thresholds["spend_spike_rate"]:
            level = KillSwitchLevel.PAUSE_NEW if rate < 5.0 else KillSwitchLevel.PAUSE_ALL
            return self._trigger_event(
                trigger=KillSwitchTrigger.SPEND_SPIKE,
                level=level,
                reason=f"Spend spike: {rate:.1f}x baseline",
                affected_systems=["ua", "bidding"],
            )

        return None

    def check_revenue(self, current_revenue: float, baseline_revenue: float) -> Optional[KillSwitchEvent]:
        if baseline_revenue <= 0:
            return None

        drop_rate = 1.0 - (current_revenue / baseline_revenue)

        if drop_rate >= self._thresholds["revenue_drop_rate"]:
            level = KillSwitchLevel.WARN if drop_rate < 0.8 else KillSwitchLevel.PAUSE_NEW
            return self._trigger_event(
                trigger=KillSwitchTrigger.REVENUE_DROP,
                level=level,
                reason=f"Revenue drop: {drop_rate*100:.0f}% decrease",
                affected_systems=["ua"],
            )

        return None

    def check_fraud(self, fraud_rate: float) -> Optional[KillSwitchEvent]:
        if fraud_rate >= self._thresholds["fraud_rate"]:
            level = KillSwitchLevel.PAUSE_ALL if fraud_rate >= 0.5 else KillSwitchLevel.PAUSE_NEW
            return self._trigger_event(
                trigger=KillSwitchTrigger.FRAUD_DETECTED,
                level=level,
                reason=f"Fraud detected: {fraud_rate*100:.1f}% suspicious installs",
                affected_systems=["ua", "attribution"],
            )

        return None

    def manual_trigger(self, level: KillSwitchLevel, reason: str) -> KillSwitchEvent:
        return self._trigger_event(
            trigger=KillSwitchTrigger.MANUAL,
            level=level,
            reason=reason,
            triggered_by="manual",
        )

    def resolve(self, event_id: str, notes: str = "") -> bool:
        for event in self._events:
            if event.event_id == event_id and not event.resolved:
                event.resolved = True
                event.resolved_at = datetime.now()
                event.resolution_notes = notes

                active_events = [e for e in self._events if not e.resolved]
                if not active_events:
                    self._current_level = KillSwitchLevel.MONITOR
                    self._paused_systems.clear()
                    for cb in self._callbacks.get("on_resume", []):
                        try:
                            cb(event)
                        except Exception:
                            pass
                else:
                    highest = max(
                        active_events,
                        key=lambda e: [
                            KillSwitchLevel.MONITOR,
                            KillSwitchLevel.WARN,
                            KillSwitchLevel.PAUSE_NEW,
                            KillSwitchLevel.PAUSE_ALL,
                            KillSwitchLevel.FULL_STOP,
                        ].index(e.level),
                    )
                    self._current_level = highest.level

                return True
        return False

    def is_system_paused(self, system_name: str) -> bool:
        if self._current_level in (KillSwitchLevel.PAUSE_ALL, KillSwitchLevel.FULL_STOP):
            return True
        if self._current_level == KillSwitchLevel.PAUSE_NEW and system_name in self._paused_systems:
            return True
        return False

    def get_current_level(self) -> KillSwitchLevel:
        return self._current_level

    def get_active_events(self) -> List[KillSwitchEvent]:
        return [e for e in self._events if not e.resolved]

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_level": self._current_level.value,
            "active_events": len(self.get_active_events()),
            "paused_systems": list(self._paused_systems),
            "total_events": len(self._events),
            "is_paused": self._current_level in (KillSwitchLevel.PAUSE_ALL, KillSwitchLevel.FULL_STOP),
        }
