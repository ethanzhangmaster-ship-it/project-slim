from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    MARKET = "market"
    TECHNICAL = "technical"
    LEGAL = "legal"


@dataclass
class Risk:
    risk_id: str
    title: str
    description: str
    category: RiskCategory
    level: RiskLevel
    status: str = "open"
    identified_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "risk_id": self.risk_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "level": self.level.value,
            "status": self.status,
            "identified_at": self.identified_at.isoformat(),
        }


@dataclass
class MitigationPlan:
    plan_id: str
    risk_id: str
    actions: List[str] = field(default_factory=list)
    owner: Optional[str] = None
    deadline: Optional[datetime] = None
    status: str = "pending"

    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "risk_id": self.risk_id,
            "actions": self.actions,
            "owner": self.owner,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
        }


@dataclass
class RiskRegister:
    register_id: str
    risks: List[Risk] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "register_id": self.register_id,
            "risks": [r.to_dict() for r in self.risks],
            "created_at": self.created_at.isoformat(),
        }


class RiskReview:
    def __init__(self):
        self._risks: Dict[str, Risk] = {}
        self._mitigation_plans: Dict[str, MitigationPlan] = {}
        self._register = RiskRegister(register_id=str(uuid.uuid4()))

    def identify_risks(self) -> List[Risk]:
        sample_risks = [
            Risk(
                risk_id=str(uuid.uuid4()),
                title="核心服务器宕机",
                description="主数据库集群存在单点故障风险",
                category=RiskCategory.TECHNICAL,
                level=RiskLevel.HIGH,
            ),
            Risk(
                risk_id=str(uuid.uuid4()),
                title="汇率波动",
                description="海外收入受汇率波动影响较大",
                category=RiskCategory.FINANCIAL,
                level=RiskLevel.MEDIUM,
            ),
            Risk(
                risk_id=str(uuid.uuid4()),
                title="竞品新游上线",
                description="预计下月有两款同类型竞品上线",
                category=RiskCategory.MARKET,
                level=RiskLevel.MEDIUM,
            ),
        ]
        for r in sample_risks:
            self._risks[r.risk_id] = r
        self._register.risks = list(self._risks.values())
        return sample_risks

    def assess_risk(self, risk_id: str) -> Optional[Risk]:
        return self._risks.get(risk_id)

    def get_risk_register(self) -> RiskRegister:
        self._register.risks = list(self._risks.values())
        return self._register

    def get_mitigation_plan(self, risk_id: str) -> Optional[MitigationPlan]:
        for plan in self._mitigation_plans.values():
            if plan.risk_id == risk_id:
                return plan
        plan = MitigationPlan(
            plan_id=str(uuid.uuid4()),
            risk_id=risk_id,
            actions=["制定应急预案", "分配负责人", "定期复查"],
            owner="Risk Manager",
        )
        self._mitigation_plans[plan.plan_id] = plan
        return plan

    def update_risk_status(self, risk_id: str, status: str) -> Optional[Risk]:
        risk = self._risks.get(risk_id)
        if risk:
            risk.status = status
        return risk

    def get_stats(self) -> Dict:
        return {
            "total_risks": len(self._risks),
            "by_level": {lvl.value: sum(1 for r in self._risks.values() if r.level == lvl) for lvl in RiskLevel},
            "by_category": {cat.value: sum(1 for r in self._risks.values() if r.category == cat) for cat in RiskCategory},
            "open_risks": sum(1 for r in self._risks.values() if r.status == "open"),
            "mitigation_plans": len(self._mitigation_plans),
        }
