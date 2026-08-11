from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class ReportType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


@dataclass
class KPISet:
    kpi_id: str
    name: str
    value: float
    target: float
    unit: str
    period: str

    def to_dict(self) -> Dict:
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "value": self.value,
            "target": self.target,
            "unit": self.unit,
            "period": self.period,
        }


@dataclass
class TrendAnalysis:
    trend_id: str
    metric_name: str
    direction: str
    change_percent: float
    analysis: str

    def to_dict(self) -> Dict:
        return {
            "trend_id": self.trend_id,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "change_percent": self.change_percent,
            "analysis": self.analysis,
        }


@dataclass
class ReportData:
    report_id: str
    report_type: ReportType
    title: str
    generated_at: datetime
    kpis: List[KPISet] = field(default_factory=list)
    trends: List[TrendAnalysis] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "kpis": [k.to_dict() for k in self.kpis],
            "trends": [t.to_dict() for t in self.trends],
            "summary": self.summary,
        }


class CompanyReport:
    def __init__(self):
        self._reports: Dict[str, ReportData] = {}

    def generate_report(self, report_type: ReportType) -> ReportData:
        report_id = str(uuid.uuid4())
        kpis = [
            KPISet(str(uuid.uuid4()), "DAU", 125000.0, 150000.0, "users", report_type.value),
            KPISet(str(uuid.uuid4()), "Revenue", 850000.0, 1000000.0, "USD", report_type.value),
            KPISet(str(uuid.uuid4()), "Retention", 42.5, 50.0, "%", report_type.value),
        ]
        trends = [
            TrendAnalysis(
                str(uuid.uuid4()),
                "DAU",
                "up",
                5.2,
                "日活跃用户较上期增长 5.2%",
            ),
            TrendAnalysis(
                str(uuid.uuid4()),
                "Revenue",
                "down",
                -2.1,
                "收入较上期下降 2.1%，需关注付费转化",
            ),
        ]
        report = ReportData(
            report_id=report_id,
            report_type=report_type,
            title=f"{report_type.value.upper()} Report",
            generated_at=datetime.now(),
            kpis=kpis,
            trends=trends,
            summary="整体运营平稳，需加强用户留存与付费转化。",
        )
        self._reports[report_id] = report
        return report

    def get_reports(self) -> List[ReportData]:
        return list(self._reports.values())

    def get_report(self, report_id: str) -> Optional[ReportData]:
        return self._reports.get(report_id)

    def get_kpis(self) -> List[KPISet]:
        kpis: List[KPISet] = []
        for report in self._reports.values():
            kpis.extend(report.kpis)
        return kpis

    def get_trend_analysis(self) -> List[TrendAnalysis]:
        trends: List[TrendAnalysis] = []
        for report in self._reports.values():
            trends.extend(report.trends)
        return trends

    def get_stats(self) -> Dict:
        return {
            "total_reports": len(self._reports),
            "by_type": {rt.value: sum(1 for r in self._reports.values() if r.report_type == rt) for rt in ReportType},
            "total_kpis": sum(len(r.kpis) for r in self._reports.values()),
            "total_trends": sum(len(r.trends) for r in self._reports.values()),
        }
