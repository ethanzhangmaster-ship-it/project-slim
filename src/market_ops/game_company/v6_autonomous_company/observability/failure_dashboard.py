from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict


class FailureSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureCategory(Enum):
    AGENT = "agent"
    WORKFLOW = "workflow"
    CONNECTOR = "connector"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"
    BUSINESS = "business"


@dataclass
class FailureRecord:
    failure_id: str
    category: FailureCategory
    severity: FailureSeverity
    title: str
    description: str
    source: str = "unknown"
    component: str = ""
    error_message: str = ""
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution: str = ""
    occurrences: int = 1
    first_occurrence: datetime = field(default_factory=datetime.now)


class FailureDashboard:
    def __init__(self):
        self._failures: Dict[str, FailureRecord] = {}
        self._by_component: Dict[str, List[str]] = defaultdict(list)
        self._by_category: Dict[str, List[str]] = defaultdict(list)
        self._daily_failures: Dict[str, int] = defaultdict(int)

    def record_failure(
        self,
        category: FailureCategory,
        severity: FailureSeverity,
        title: str,
        description: str,
        source: str = "unknown",
        component: str = "",
        error_message: str = "",
        stack_trace: str = "",
    ) -> FailureRecord:
        failure_id = f"fail_{hash(title + component + str(datetime.now())) % 100000:05d}"

        failure = FailureRecord(
            failure_id=failure_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            source=source,
            component=component,
            error_message=error_message,
            stack_trace=stack_trace,
        )

        self._failures[failure_id] = failure
        self._by_component[component].append(failure_id)
        self._by_category[category.value].append(failure_id)
        self._daily_failures[failure.timestamp.strftime("%Y-%m-%d")] += 1

        return failure

    def get_failure(self, failure_id: str) -> Optional[FailureRecord]:
        return self._failures.get(failure_id)

    def get_active_failures(self, min_severity: FailureSeverity = None) -> List[FailureRecord]:
        active = [f for f in self._failures.values() if not f.resolved]
        if min_severity:
            level_order = {
                FailureSeverity.LOW: 1,
                FailureSeverity.MEDIUM: 2,
                FailureSeverity.HIGH: 3,
                FailureSeverity.CRITICAL: 4,
            }
            min_level = level_order.get(min_severity, 0)
            active = [f for f in active if level_order.get(f.severity, 0) >= min_level]
        return sorted(active, key=lambda f: f.timestamp, reverse=True)

    def get_failures_by_category(self, category: FailureCategory) -> List[FailureRecord]:
        ids = self._by_category.get(category.value, [])
        return [self._failures[fid] for fid in ids if fid in self._failures]

    def get_failures_by_component(self, component: str) -> List[FailureRecord]:
        ids = self._by_component.get(component, [])
        return [self._failures[fid] for fid in ids if fid in self._failures]

    def get_recent_failures(self, hours: int = 24) -> List[FailureRecord]:
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [f for f in self._failures.values() if f.timestamp >= cutoff]
        return sorted(recent, key=lambda f: f.timestamp, reverse=True)

    def resolve_failure(self, failure_id: str, resolution: str = "") -> bool:
        failure = self._failures.get(failure_id)
        if not failure:
            return False
        failure.resolved = True
        failure.resolved_at = datetime.now()
        failure.resolution = resolution
        return True

    def get_failure_summary(self) -> Dict[str, Any]:
        active = self.get_active_failures()
        critical = len(self.get_active_failures(FailureSeverity.CRITICAL))
        high = len(self.get_active_failures(FailureSeverity.HIGH))
        medium = len(self.get_active_failures(FailureSeverity.MEDIUM))
        low = len(self.get_active_failures(FailureSeverity.LOW))

        by_cat = {}
        for cat in FailureCategory:
            cat_failures = self.get_failures_by_category(cat)
            by_cat[cat.value] = {
                "total": len(cat_failures),
                "active": sum(1 for f in cat_failures if not f.resolved),
            }

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        return {
            "total_failures": len(self._failures),
            "active_failures": len(active),
            "by_severity": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
            },
            "by_category": by_cat,
            "today": self._daily_failures.get(today, 0),
            "yesterday": self._daily_failures.get(yesterday, 0),
            "resolved": sum(1 for f in self._failures.values() if f.resolved),
            "resolution_rate": round(
                sum(1 for f in self._failures.values() if f.resolved) / len(self._failures) * 100, 1
            ) if self._failures else 0,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        summary = self.get_failure_summary()
        recent = self.get_recent_failures(24)[:10]
        critical_active = self.get_active_failures(FailureSeverity.CRITICAL)

        return {
            "summary": summary,
            "critical_active": [f.title for f in critical_active],
            "recent_failures": [
                {"id": f.failure_id, "title": f.title, "severity": f.severity.value, "time": f.timestamp.isoformat()}
                for f in recent
            ],
            "timestamp": datetime.now().isoformat(),
        }
