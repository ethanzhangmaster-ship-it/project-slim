"""Explicit binding contract required before any real platform write."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CampaignBinding:
    creative_id: str
    platform: str
    campaign_id: str
    current_daily_budget: float
    active: bool = True


class CampaignBindingIndex:
    """Reject ambiguous, inactive or malformed creative-to-campaign mappings."""

    def __init__(self, bindings: list[CampaignBinding]) -> None:
        self._bindings: dict[str, CampaignBinding] = {}
        for binding in bindings:
            if not binding.creative_id or not binding.platform or not binding.campaign_id:
                raise ValueError("Campaign binding requires creative_id, platform and campaign_id")
            if binding.current_daily_budget < 0:
                raise ValueError("Campaign binding budget cannot be negative")
            if binding.creative_id in self._bindings:
                raise ValueError(f"Ambiguous campaign binding for creative: {binding.creative_id}")
            self._bindings[binding.creative_id] = binding

    @classmethod
    def from_payload(cls, payload: list[dict[str, Any]]) -> CampaignBindingIndex:
        return cls([CampaignBinding(
            creative_id=str(item.get("creative_id") or ""),
            platform=str(item.get("platform") or ""),
            campaign_id=str(item.get("campaign_id") or ""),
            current_daily_budget=float(item.get("current_daily_budget") or 0.0),
            active=bool(item.get("active", True)),
        ) for item in payload])

    def resolve(self, creative_id: str) -> CampaignBinding:
        binding = self._bindings.get(creative_id)
        if binding is None:
            raise KeyError(f"No verified campaign binding for creative: {creative_id}")
        if not binding.active:
            raise ValueError(f"Campaign binding is inactive for creative: {creative_id}")
        return binding
