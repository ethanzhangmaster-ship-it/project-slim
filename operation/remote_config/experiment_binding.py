"""E15.2.8 §6 — Experiment binding: translates a Player Monetization
experiment into a concrete RemoteConfig A/B variant pair the SDK receives."""
from __future__ import annotations
from typing import Any, Dict, Optional
from operation.remote_config.models import RemoteConfig
from operation.remote_config.variant_generator import VariantGenerator


# Map experiment action → remote config section & parameter overrides
_BINDING = {
    "reward_cooldown": {
        "section": "reward",
        "param": "cooldown",
        "control": 300, "variant": 180,
    },
    "reward_multiplier": {
        "section": "reward",
        "param": "multiplier",
        "control": 1.0, "variant": 1.5,
    },
    "interstitial_interval": {
        "section": "interstitial",
        "param": "min_interval",
        "control": 120, "variant": 60,
    },
    "interstitial_after_fail": {
        "section": "interstitial",
        "param": "after_fail",
        "control": False, "variant": True,
    },
    "frequency_cap": {
        "section": "interstitial",
        "param": "max_daily",
        "control": 10, "variant": 15,
    },
}


class ExperimentBinder:
    def __init__(self) -> None:
        self._gen = VariantGenerator()

    def bind(self, base: RemoteConfig, action: str,
             target: str = "", experiment_id: str = "") -> Optional[tuple]:
        """Returns (control_cfg, variant_cfg) or None if action unknown."""
        spec = _BINDING.get(action)
        if not spec:
            return None
        section = spec["section"]
        overrides: Dict[str, Any] = {}
        if section == "reward":
            tgt = target or "revive"
            overrides = {tgt: {spec["param"]: spec["variant"]}}
        elif section == "interstitial":
            overrides = {spec["param"]: spec["variant"]}
        return self._gen.pair(base, experiment_id,
                              {section: overrides})
