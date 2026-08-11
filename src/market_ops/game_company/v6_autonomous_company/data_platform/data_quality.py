from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class QualityIssueSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataIssueType(Enum):
    MISSING_DATA = "missing_data"
    DUPLICATE = "duplicate"
    OUTLIER = "outlier"
    ANOMALY = "anomaly"
    SCHEMA_MISMATCH = "schema_mismatch"
    LATENCY = "latency"


@dataclass
class QualityIssue:
    issue_id: str
    issue_type: DataIssueType
    severity: QualityIssueSeverity
    description: str
    affected_records: int = 0
    source: str = "unknown"
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class QualityReport:
    report_id: str
    total_records: int
    issues: List[QualityIssue] = field(default_factory=list)
    overall_quality_score: float = 0.0
    data_freshness_minutes: float = 0.0
    completeness: float = 0.0
    uniqueness: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)


class DataQualityMonitor:
    def __init__(self):
        self._issues: Dict[str, QualityIssue] = {}
        self._reports: List[QualityReport] = []
        self._thresholds: Dict[str, float] = {
            "min_completeness": 0.95,
            "min_uniqueness": 0.99,
            "max_latency_minutes": 60,
            "max_missing_rate": 0.05,
        }

    def check_completeness(self, data: List[Dict[str, Any]], required_fields: List[str]) -> QualityIssue:
        if not data:
            return QualityIssue(
                issue_id=f"issue_{hash(str(datetime.now())) % 10000:04d}",
                issue_type=DataIssueType.MISSING_DATA,
                severity=QualityIssueSeverity.HIGH,
                description="Empty dataset",
                affected_records=0,
            )

        missing_count = 0
        for record in data:
            for field in required_fields:
                if field not in record or record[field] is None or record[field] == "":
                    missing_count += 1
                    break

        missing_rate = missing_count / len(data) if data else 0
        severity = self._severity_from_rate(missing_rate, "missing")

        return QualityIssue(
            issue_id=f"issue_completeness_{hash(str(data[:3])) % 10000:04d}",
            issue_type=DataIssueType.MISSING_DATA,
            severity=severity,
            description=f"{missing_count}/{len(data)} records missing required fields",
            affected_records=missing_count,
        )

    def _severity_from_rate(self, rate: float, issue_type: str) -> QualityIssueSeverity:
        if rate >= 0.5:
            return QualityIssueSeverity.CRITICAL
        elif rate >= 0.2:
            return QualityIssueSeverity.HIGH
        elif rate >= 0.05:
            return QualityIssueSeverity.MEDIUM
        else:
            return QualityIssueSeverity.LOW

    def check_uniqueness(self, data: List[Dict[str, Any]], key_fields: List[str]) -> QualityIssue:
        seen = set()
        duplicates = 0

        for record in data:
            key = tuple(record.get(f, "") for f in key_fields)
            if key in seen:
                duplicates += 1
            seen.add(key)

        dup_rate = duplicates / len(data) if data else 0
        severity = self._severity_from_rate(dup_rate, "duplicate")

        return QualityIssue(
            issue_id=f"issue_uniqueness_{hash(str(data[:3])) % 10000:04d}",
            issue_type=DataIssueType.DUPLICATE,
            severity=severity,
            description=f"{duplicates} duplicate records found",
            affected_records=duplicates,
        )

    def check_outliers(self, values: List[float], threshold: float = 3.0) -> QualityIssue:
        if len(values) < 4:
            return QualityIssue(
                issue_id=f"issue_outlier_{hash(str(values)) % 10000:04d}",
                issue_type=DataIssueType.OUTLIER,
                severity=QualityIssueSeverity.LOW,
                description="Insufficient data for outlier detection",
                affected_records=0,
            )

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5

        outliers = sum(1 for v in values if abs(v - mean) > threshold * std_dev)
        outlier_rate = outliers / len(values) if values else 0
        severity = self._severity_from_rate(outlier_rate, "outlier")

        return QualityIssue(
            issue_id=f"issue_outlier_{hash(str(values[:5])) % 10000:04d}",
            issue_type=DataIssueType.OUTLIER,
            severity=severity,
            description=f"{outliers} outliers detected (threshold={threshold}σ)",
            affected_records=outliers,
        )

    def check_freshness(self, last_update: datetime, threshold_minutes: int = 60) -> QualityIssue:
        now = datetime.now()
        latency = (now - last_update).total_seconds() / 60

        if latency > threshold_minutes * 3:
            severity = QualityIssueSeverity.CRITICAL
        elif latency > threshold_minutes * 2:
            severity = QualityIssueSeverity.HIGH
        elif latency > threshold_minutes:
            severity = QualityIssueSeverity.MEDIUM
        else:
            severity = QualityIssueSeverity.LOW

        return QualityIssue(
            issue_id=f"issue_freshness_{hash(str(last_update)) % 10000:04d}",
            issue_type=DataIssueType.LATENCY,
            severity=severity,
            description=f"Data is {latency:.1f} minutes old",
            affected_records=0,
        )

    def run_full_check(
        self,
        data: List[Dict[str, Any]],
        required_fields: List[str],
        key_fields: List[str],
        last_update: datetime = None,
    ) -> QualityReport:
        issues = []

        completeness_issue = self.check_completeness(data, required_fields)
        issues.append(completeness_issue)
        self._track_issue(completeness_issue)

        uniqueness_issue = self.check_uniqueness(data, key_fields)
        issues.append(uniqueness_issue)
        self._track_issue(uniqueness_issue)

        if last_update:
            freshness_issue = self.check_freshness(last_update)
            issues.append(freshness_issue)
            self._track_issue(freshness_issue)

        total_records = len(data)
        completeness = 1.0 - (completeness_issue.affected_records / total_records if total_records > 0 else 0)
        uniqueness = 1.0 - (uniqueness_issue.affected_records / total_records if total_records > 0 else 0)

        score = (completeness + uniqueness) / 2 * 100

        report = QualityReport(
            report_id=f"report_{hash(str(datetime.now())) % 100000:05d}",
            total_records=total_records,
            issues=issues,
            overall_quality_score=round(score, 2),
            data_freshness_minutes=0,
            completeness=round(completeness, 4),
            uniqueness=round(uniqueness, 4),
        )

        self._reports.append(report)
        return report

    def _track_issue(self, issue: QualityIssue):
        self._issues[issue.issue_id] = issue

    def get_open_issues(self, min_severity: QualityIssueSeverity = None) -> List[QualityIssue]:
        open_issues = [i for i in self._issues.values() if not i.resolved]
        if min_severity:
            severity_order = {
                QualityIssueSeverity.LOW: 1,
                QualityIssueSeverity.MEDIUM: 2,
                QualityIssueSeverity.HIGH: 3,
                QualityIssueSeverity.CRITICAL: 4,
            }
            min_level = severity_order.get(min_severity, 0)
            open_issues = [i for i in open_issues if severity_order.get(i.severity, 0) >= min_level]
        return sorted(open_issues, key=lambda i: i.detected_at, reverse=True)

    def resolve_issue(self, issue_id: str) -> bool:
        issue = self._issues.get(issue_id)
        if issue:
            issue.resolved = True
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        open_count = len(self.get_open_issues())
        critical_count = len(self.get_open_issues(QualityIssueSeverity.CRITICAL))
        return {
            "total_issues": len(self._issues),
            "open_issues": open_count,
            "critical_issues": critical_count,
            "resolved_issues": len(self._issues) - open_count,
            "total_reports": len(self._reports),
        }
