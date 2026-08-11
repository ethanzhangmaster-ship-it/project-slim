"""E15.2.6 — Config Agent (monetization params: frequency_cap, cooldown, prices)"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MonetizationConfig:
    game_id: str
    reward_cooldown_min: int = 30
    frequency_cap_per_day: int = 10
    placement_switch: Dict[str, bool] = field(default_factory=dict)
    iap_prices: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "reward_cooldown_min": self.reward_cooldown_min,
            "frequency_cap_per_day": self.frequency_cap_per_day,
            "placement_switch": self.placement_switch,
            "iap_prices": self.iap_prices,
        }


class ConfigAgent:
    def build_default(self, game_id: str) -> MonetizationConfig:
        return MonetizationConfig(
            game_id=game_id,
            placement_switch={"rewarded_video": True,
                              "interstitial": True, "banner": True},
            iap_prices={"coin100": 0.99, "coin500": 4.99,
                        "vip_monthly": 9.99, "remove_ads": 3.99},
        )

    def update(self, cfg: MonetizationConfig, key: str,
               value: Any) -> MonetizationConfig:
        old = getattr(cfg, key, None)
        setattr(cfg, key, value)
        cfg._rollback = {key: old}  # simplistic rollback
        return cfg

    def rollback(self, cfg: MonetizationConfig) -> MonetizationConfig:
        if hasattr(cfg, "_rollback"):
            for k, v in cfg._rollback.items():
                setattr(cfg, k, v)
        return cfg
