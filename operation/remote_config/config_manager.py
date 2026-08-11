"""E15.2.8 §5 — Config manager: load, save, validate RemoteConfig."""
from __future__ import annotations
import json, os, yaml
from typing import Any, Dict, Optional
from operation.remote_config.models import RemoteConfig


class ConfigManager:
    def load(self, path: str) -> RemoteConfig:
        if not os.path.exists(path):
            return RemoteConfig.default_for(os.path.splitext(
                os.path.basename(path))[0])
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) if path.endswith(".yaml") or path.endswith(".yml") \
                else json.load(f)
        return self._parse(raw)

    def save(self, cfg: RemoteConfig, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        d = {"game_id": cfg.game_id, "version": cfg.version,
             "reward": {k: v.to_dict() for k, v in cfg.reward.items()},
             "interstitial": cfg.interstitial.to_dict(),
             "segments": {k: v.to_dict() for k, v in cfg.segments.items()}}
        if cfg.experiment_id:
            d["experiment_id"] = cfg.experiment_id
            d["variant"] = cfg.variant
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
        return path

    def save_flat_json(self, cfg: RemoteConfig, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg.to_flat_dict(), f, ensure_ascii=False)
        return path

    def validate(self, cfg: RemoteConfig) -> Dict[str, Any]:
        issues = []
        if not cfg.game_id:
            issues.append("missing game_id")
        for name, r in cfg.reward.items():
            if r.cooldown_sec < 30:
                issues.append(f"reward.{name}.cooldown < 30s")
        if cfg.interstitial.min_interval_sec < 10:
            issues.append("interstitial.min_interval < 10s")
        return {"ok": len(issues) == 0, "issues": issues}

    def _parse(self, raw: Dict[str, Any]) -> RemoteConfig:
        from operation.remote_config.models import (
            RewardConfig, InterstitialConfig, SegmentOverride)
        rew = {}
        for k, v in (raw.get("reward") or {}).items():
            rew[k] = RewardConfig(k,
                v.get("enabled", True),
                v.get("cooldown", 300),
                v.get("multiplier", 1.0))
        inter = raw.get("interstitial", {})
        segs = {}
        for k, v in (raw.get("segments") or {}).items():
            segs[k] = SegmentOverride(k,
                v.get("reward_multiplier", 1.0),
                v.get("interstitial_frequency", 1.0),
                v.get("cooldown_multiplier", 1.0))
        return RemoteConfig(
            game_id=raw.get("game_id", ""),
            version=raw.get("version", "1.0"),
            reward=rew, interstitial=InterstitialConfig(
                inter.get("enabled", True),
                inter.get("min_interval", 120),
                inter.get("after_level", True),
                inter.get("max_daily", 10),
                inter.get("after_fail", False)),
            segments=segs,
            experiment_id=raw.get("experiment_id"),
            variant=raw.get("variant", "control"))
