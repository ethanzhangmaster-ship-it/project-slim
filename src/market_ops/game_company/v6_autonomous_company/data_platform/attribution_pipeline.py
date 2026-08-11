from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict


@dataclass
class AttributionResult:
    user_id: str
    channel: str
    campaign: str
    adset: str
    creative: str
    attributed_touchpoint: str
    model: str
    confidence: float
    install_time: Optional[datetime] = None
    first_touch_time: Optional[datetime] = None


class AttributionPipeline:
    def __init__(self):
        self._touchpoints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._attributions: Dict[str, AttributionResult] = {}
        self.supported_models = [
            "last_click",
            "first_click",
            "linear",
            "time_decay",
        ]

    def add_touchpoint(
        self,
        user_id: str,
        channel: str,
        campaign: str,
        adset: str = "",
        creative: str = "",
        timestamp: datetime = None,
        touch_type: str = "click",
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = datetime.now()

        touchpoint = {
            "user_id": user_id,
            "channel": channel,
            "campaign": campaign,
            "adset": adset,
            "creative": creative,
            "timestamp": timestamp,
            "touch_type": touch_type,
        }

        self._touchpoints[user_id].append(touchpoint)
        self._touchpoints[user_id].sort(key=lambda x: x["timestamp"])

        return touchpoint

    def attribute(
        self,
        user_id: str,
        install_time: datetime = None,
        model: str = "last_click",
    ) -> Optional[AttributionResult]:
        if install_time is None:
            install_time = datetime.now()

        touchpoints = [
            tp for tp in self._touchpoints.get(user_id, [])
            if tp["timestamp"] <= install_time
        ]

        if not touchpoints:
            return None

        if model == "last_click":
            tp = touchpoints[-1]
            result = AttributionResult(
                user_id=user_id,
                channel=tp["channel"],
                campaign=tp["campaign"],
                adset=tp["adset"],
                creative=tp["creative"],
                attributed_touchpoint="last",
                model=model,
                confidence=0.85,
                install_time=install_time,
                first_touch_time=touchpoints[0]["timestamp"],
            )
        elif model == "first_click":
            tp = touchpoints[0]
            result = AttributionResult(
                user_id=user_id,
                channel=tp["channel"],
                campaign=tp["campaign"],
                adset=tp["adset"],
                creative=tp["creative"],
                attributed_touchpoint="first",
                model=model,
                confidence=0.75,
                install_time=install_time,
                first_touch_time=touchpoints[0]["timestamp"],
            )
        else:
            tp = touchpoints[-1]
            result = AttributionResult(
                user_id=user_id,
                channel=tp["channel"],
                campaign=tp["campaign"],
                adset=tp["adset"],
                creative=tp["creative"],
                attributed_touchpoint="last",
                model=model,
                confidence=0.85,
                install_time=install_time,
                first_touch_time=touchpoints[0]["timestamp"],
            )

        self._attributions[user_id] = result
        return result

    def get_channel_breakdown(
        self,
        model: str = "last_click",
    ) -> Dict[str, int]:
        breakdown = defaultdict(int)
        for attr in self._attributions.values():
            breakdown[attr.channel] += 1
        return dict(breakdown)

    def get_campaign_breakdown(
        self,
        channel: str = None,
        model: str = "last_click",
    ) -> Dict[str, int]:
        breakdown = defaultdict(int)
        for attr in self._attributions.values():
            if channel and attr.channel != channel:
                continue
            breakdown[attr.campaign] += 1
        return dict(breakdown)

    def compare_models(self, user_id: str) -> Dict[str, AttributionResult]:
        results = {}
        for model in self.supported_models:
            result = self.attribute(user_id, model=model)
            if result:
                results[model] = result
        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_touchpoints": sum(len(tps) for tps in self._touchpoints.values()),
            "total_attributions": len(self._attributions),
            "unique_users": len(self._touchpoints),
            "channels": list(self.get_channel_breakdown().keys()),
        }
