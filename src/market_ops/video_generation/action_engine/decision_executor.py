from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class ActionResult:
    action_id: str
    decision_id: str
    action_type: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class DecisionExecutor:
    def __init__(self):
        self.executors = {
            "scale_up": self._execute_scale_up,
            "scale_down": self._execute_scale_down,
            "pause": self._execute_pause,
            "resume": self._execute_resume,
            "kill": self._execute_kill,
            "create_campaign": self._execute_create_campaign,
            "update_budget": self._execute_update_budget,
            "upload_creative": self._execute_upload_creative,
            "adjust_bid": self._execute_adjust_bid,
        }

    def execute(self, decision: Dict[str, Any]) -> ActionResult:
        action_type = decision.get("action_type", "")
        executor = self.executors.get(action_type)
        
        if not executor:
            return ActionResult(
                action_id=f"action_{hash(decision.get('decision_id', '')) % 10000:04d}",
                decision_id=decision.get("decision_id", ""),
                action_type=action_type,
                status="failed",
                details={"error": f"Unknown action type: {action_type}"},
            )
        
        try:
            result = executor(decision)
            return ActionResult(
                action_id=f"action_{hash(decision.get('decision_id', '')) % 10000:04d}",
                decision_id=decision.get("decision_id", ""),
                action_type=action_type,
                status="success",
                details=result,
            )
        except Exception as e:
            return ActionResult(
                action_id=f"action_{hash(decision.get('decision_id', '')) % 10000:04d}",
                decision_id=decision.get("decision_id", ""),
                action_type=action_type,
                status="failed",
                details={"error": str(e)},
            )

    def _execute_scale_up(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "old_budget": decision.get("old_budget", 0),
            "new_budget": decision.get("new_budget", 0),
            "platform": decision.get("platform", ""),
            "campaign_id": decision.get("campaign_id", ""),
            "message": f"Scaled up budget from ${decision.get('old_budget', 0)} to ${decision.get('new_budget', 0)}",
        }

    def _execute_scale_down(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "old_budget": decision.get("old_budget", 0),
            "new_budget": decision.get("new_budget", 0),
            "platform": decision.get("platform", ""),
            "campaign_id": decision.get("campaign_id", ""),
            "message": f"Scaled down budget from ${decision.get('old_budget', 0)} to ${decision.get('new_budget', 0)}",
        }

    def _execute_pause(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_id": decision.get("campaign_id", ""),
            "platform": decision.get("platform", ""),
            "reason": decision.get("reason", ""),
            "message": f"Paused campaign {decision.get('campaign_id', '')} on {decision.get('platform', '')}",
        }

    def _execute_resume(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_id": decision.get("campaign_id", ""),
            "platform": decision.get("platform", ""),
            "message": f"Resumed campaign {decision.get('campaign_id', '')} on {decision.get('platform', '')}",
        }

    def _execute_kill(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_id": decision.get("campaign_id", ""),
            "platform": decision.get("platform", ""),
            "reason": decision.get("reason", ""),
            "message": f"Killed campaign {decision.get('campaign_id', '')} on {decision.get('platform', '')}",
        }

    def _execute_create_campaign(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_name": decision.get("campaign_name", ""),
            "platform": decision.get("platform", ""),
            "objective": decision.get("objective", ""),
            "budget": decision.get("budget", 0),
            "message": f"Created campaign {decision.get('campaign_name', '')} on {decision.get('platform', '')}",
        }

    def _execute_update_budget(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_id": decision.get("campaign_id", ""),
            "old_budget": decision.get("old_budget", 0),
            "new_budget": decision.get("new_budget", 0),
            "platform": decision.get("platform", ""),
            "message": f"Updated budget for {decision.get('campaign_id', '')}: ${decision.get('old_budget', 0)} → ${decision.get('new_budget', 0)}",
        }

    def _execute_upload_creative(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "creative_id": decision.get("creative_id", ""),
            "campaign_id": decision.get("campaign_id", ""),
            "platform": decision.get("platform", ""),
            "message": f"Uploaded creative {decision.get('creative_id', '')} to campaign {decision.get('campaign_id', '')}",
        }

    def _execute_adjust_bid(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign_id": decision.get("campaign_id", ""),
            "old_bid": decision.get("old_bid", 0),
            "new_bid": decision.get("new_bid", 0),
            "platform": decision.get("platform", ""),
            "message": f"Adjusted bid: ${decision.get('old_bid', 0):.2f} → ${decision.get('new_bid', 0):.2f}",
        }

    def execute_demo(self) -> List[ActionResult]:
        decisions = [
            {"decision_id": "d1", "action_type": "scale_up", "old_budget": 500, "new_budget": 700, "platform": "meta", "campaign_id": "c1"},
            {"decision_id": "d2", "action_type": "pause", "campaign_id": "c2", "platform": "google", "reason": "CTR -35%"},
            {"decision_id": "d3", "action_type": "create_campaign", "campaign_name": "US_WITCH_WINNER_002", "platform": "meta", "objective": "purchase", "budget": 500},
        ]
        return [self.execute(d) for d in decisions]
