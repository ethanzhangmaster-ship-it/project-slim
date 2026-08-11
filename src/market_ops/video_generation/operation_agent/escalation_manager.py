from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class EscalationAlert:
    alert_id: str
    type: str
    severity: str
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EscalationAction:
    action_id: str
    alert_id: str
    action: str
    status: str = "pending"
    assignee: str = ""
    completed_at: Optional[datetime] = None


class EscalationManager:
    def __init__(self):
        self.alerts: Dict[str, EscalationAlert] = {}
        self.actions: Dict[str, EscalationAction] = {}
        self.escalation_rules = {
            "roas_crash": {"threshold": 0.5, "severity": "critical", "action": "pause_all"},
            "spend_spike": {"threshold": 200, "severity": "high", "action": "reduce_budget"},
            "no_purchase": {"threshold": 300, "severity": "medium", "action": "kill_campaign"},
            "api_error": {"threshold": 5, "severity": "high", "action": "notify_engineer"},
        }

    def check_escalations(self, metrics: Dict[str, Any]) -> List[EscalationAlert]:
        alerts = []

        roas = metrics.get("roas", 0)
        if roas < self.escalation_rules["roas_crash"]["threshold"]:
            alert = EscalationAlert(
                alert_id=f"alert_roas_{hash(str(datetime.now())) % 1000:03d}",
                type="roas_crash",
                severity="critical",
                message=f"ROAS crashed to {roas:.2f}",
                metrics={"roas": roas},
            )
            alerts.append(alert)
            self.alerts[alert.alert_id] = alert

        spend_spike = metrics.get("spend_spike_percent", 0)
        if spend_spike > self.escalation_rules["spend_spike"]["threshold"]:
            alert = EscalationAlert(
                alert_id=f"alert_spend_{hash(str(datetime.now())) % 1000:03d}",
                type="spend_spike",
                severity="high",
                message=f"Spend increased by {spend_spike}%",
                metrics={"spend_spike": spend_spike},
            )
            alerts.append(alert)
            self.alerts[alert.alert_id] = alert

        spend_without_purchase = metrics.get("spend_without_purchase", 0)
        if spend_without_purchase > self.escalation_rules["no_purchase"]["threshold"]:
            alert = EscalationAlert(
                alert_id=f"alert_no_purchase_{hash(str(datetime.now())) % 1000:03d}",
                type="no_purchase",
                severity="medium",
                message=f"${spend_without_purchase:.0f} spent with no purchases",
                metrics={"spend": spend_without_purchase},
            )
            alerts.append(alert)
            self.alerts[alert.alert_id] = alert

        return alerts

    def create_action(self, alert: EscalationAlert) -> EscalationAction:
        rule = self.escalation_rules.get(alert.type, {})
        action_type = rule.get("action", "notify")
        
        action = EscalationAction(
            action_id=f"action_{alert.alert_id}",
            alert_id=alert.alert_id,
            action=action_type,
            assignee=self._get_assignee(alert.severity),
        )
        self.actions[action.action_id] = action
        return action

    def _get_assignee(self, severity: str) -> str:
        assignees = {
            "critical": "CTO",
            "high": "Growth Lead",
            "medium": "UA Specialist",
            "low": "Operations",
        }
        return assignees.get(severity, "Operations")

    def check_escalations_demo(self) -> List[EscalationAlert]:
        metrics = {
            "roas": 0.4,
            "spend_spike_percent": 250,
            "spend_without_purchase": 350,
        }
        return self.check_escalations(metrics)
