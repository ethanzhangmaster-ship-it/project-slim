from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class ROIResult:
    campaign_id: str
    roi: float
    roas: float
    cpi: float
    ltv: float
    margin: float
    efficiency_score: float = 0.0
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ROIManager:
    def __init__(self):
        self.target_roas = 2.0
        self.target_cpi = 2.5
        self.target_margin = 0.3

    def calculate(self, campaign_data: Dict[str, Any]) -> ROIResult:
        spend = campaign_data.get("spend", 0.0)
        revenue = campaign_data.get("revenue", 0.0)
        installs = campaign_data.get("installs", 0)
        ltv = campaign_data.get("ltv", 0.0)
        cost_of_goods = campaign_data.get("cost_of_goods", 0.0)

        roas = revenue / spend if spend > 0 else 0.0
        cpi = spend / installs if installs > 0 else float("inf")
        roi = (revenue - cost_of_goods - spend) / spend if spend > 0 else 0.0
        margin = (revenue - cost_of_goods) / revenue if revenue > 0 else 0.0

        roas_score = min(roas / self.target_roas, 1.0)
        cpi_score = max(1 - (cpi - self.target_cpi) / self.target_cpi, 0) if cpi > 0 else 0
        margin_score = min(margin / self.target_margin, 1.0)
        
        efficiency_score = (roas_score * 0.4) + (cpi_score * 0.3) + (margin_score * 0.3)

        if efficiency_score >= 0.8:
            recommendation = "SCALE"
        elif efficiency_score >= 0.5:
            recommendation = "HOLD"
        else:
            recommendation = "KILL"

        return ROIResult(
            campaign_id=campaign_data.get("campaign_id", ""),
            roi=round(roi, 2),
            roas=round(roas, 2),
            cpi=round(cpi, 2),
            ltv=ltv,
            margin=round(margin, 2),
            efficiency_score=round(efficiency_score, 2),
            recommendation=recommendation,
        )

    def calculate_demo(self) -> ROIResult:
        data = {
            "campaign_id": "campaign_001",
            "spend": 5000,
            "revenue": 12500,
            "installs": 2000,
            "ltv": 3.2,
            "cost_of_goods": 2500,
        }
        return self.calculate(data)
