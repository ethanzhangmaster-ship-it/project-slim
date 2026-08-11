"""E15.2.8 §6 — Variant generator: creates A/B RemoteConfig variants from
experiment definitions so the SDK receives control or treatment per user."""
from __future__ import annotations
import copy
from typing import Any, Dict, Optional
from operation.remote_config.models import RemoteConfig


class VariantGenerator:
    def generate(self, base: RemoteConfig, experiment_id: str,
                 variant_spec: Dict[str, Any]) -> RemoteConfig:
        """variant_spec: {"reward": {"revive": {"cooldown": 180}}}"""
        a = copy.deepcopy(base)
        a.experiment_id = experiment_id
        a.variant = "control"
        b = copy.deepcopy(base)
        b.experiment_id = experiment_id
        b.variant = "variant"
        self._apply(b, variant_spec)
        return b  # caller also needs A — both returned explicitly via pair

    def pair(self, base: RemoteConfig, experiment_id: str,
             variant_spec: Dict[str, Any]) -> tuple:
        control = copy.deepcopy(base)
        control.experiment_id = experiment_id
        control.variant = "control"
        variant = copy.deepcopy(base)
        variant.experiment_id = experiment_id
        variant.variant = "variant"
        self._apply(variant, variant_spec)
        return (control, variant)

    @staticmethod
    def _apply(cfg: RemoteConfig, spec: Dict[str, Any]):
        for section, params in spec.items():
            if section == "reward":
                for name, overrides in (params or {}).items():
                    if name in cfg.reward:
                        r = cfg.reward[name]
                        if "cooldown" in overrides:
                            r.cooldown_sec = int(overrides["cooldown"])
                        if "multiplier" in overrides:
                            r.multiplier = float(overrides["multiplier"])
                        if "enabled" in overrides:
                            r.enabled = bool(overrides["enabled"])
            elif section == "interstitial":
                i = cfg.interstitial
                for k, v in (params or {}).items():
                    if k == "min_interval": i.min_interval_sec = int(v)
                    if k == "after_level": i.after_level = bool(v)
                    if k == "max_daily": i.max_daily = int(v)
                    if k == "after_fail": i.after_fail = bool(v)
