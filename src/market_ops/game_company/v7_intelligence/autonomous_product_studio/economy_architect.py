"""Economy design module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class Currency:
    """In-game currency definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    symbol: str = ""
    type: str = ""  # soft, hard, premium, social
    initial_balance: float = 0.0
    earning_rate_per_hour: float = 0.0
    sink_sources: List[str] = field(default_factory=list)


@dataclass
class RewardLoop:
    """Reward loop configuration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    trigger: str = ""
    reward_currency: str = ""
    reward_amount: float = 0.0
    cooldown_minutes: float = 0.0


@dataclass
class EconomyModel:
    """Complete economy model for a game."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    currencies: List[Currency] = field(default_factory=list)
    reward_loops: List[RewardLoop] = field(default_factory=list)
    inflation_control: str = ""
    whale_curve: str = ""
    conversion_rate_usd: float = 0.0


class EconomyArchitect:
    """Designs and balances in-game economies."""

    def __init__(self):
        self._economy: EconomyModel | None = None

    def design_economy(self) -> EconomyModel:
        """Design a complete economy model."""
        currencies = [
            Currency(
                name="Gold",
                symbol="G",
                type="soft",
                initial_balance=1000.0,
                earning_rate_per_hour=50.0,
                sink_sources=["upgrades", "repairs", "travel"],
            ),
            Currency(
                name="Gems",
                symbol="💎",
                type="hard",
                initial_balance=10.0,
                earning_rate_per_hour=0.5,
                sink_sources=["premium_items", "speedups", "cosmetics"],
            ),
            Currency(
                name="Energy",
                symbol="⚡",
                type="soft",
                initial_balance=100.0,
                earning_rate_per_hour=10.0,
                sink_sources=["missions", "farming", "crafting"],
            ),
        ]
        reward_loops = [
            RewardLoop(
                name="Daily Login",
                trigger="login",
                reward_currency="Gems",
                reward_amount=5.0,
                cooldown_minutes=1440.0,
            ),
            RewardLoop(
                name="Mission Complete",
                trigger="mission_end",
                reward_currency="Gold",
                reward_amount=100.0,
                cooldown_minutes=0.0,
            ),
            RewardLoop(
                name="Achievement",
                trigger="milestone",
                reward_currency="Gems",
                reward_amount=10.0,
                cooldown_minutes=0.0,
            ),
        ]
        self._economy = EconomyModel(
            currencies=currencies,
            reward_loops=reward_loops,
            inflation_control="soft_cap_with_sinks",
            whale_curve="power_law_20_80",
            conversion_rate_usd=0.01,
        )
        return self._economy

    def balance_currency(self, currency_id: str) -> Dict[str, Any]:
        """Balance a specific currency and return tuning parameters."""
        if self._economy is None:
            self.design_economy()
        currency = next((c for c in self._economy.currencies if c.id == currency_id), None)
        if currency is None:
            return {"error": "Currency not found", "currency_id": currency_id}
        new_earning_rate = round(currency.earning_rate_per_hour * random.uniform(0.9, 1.1), 2)
        new_initial = round(currency.initial_balance * random.uniform(0.95, 1.05), 2)
        return {
            "currency_id": currency_id,
            "old_earning_rate": currency.earning_rate_per_hour,
            "new_earning_rate": new_earning_rate,
            "old_initial_balance": currency.initial_balance,
            "new_initial_balance": new_initial,
            "balance_status": "balanced" if 0.8 <= new_earning_rate / currency.earning_rate_per_hour <= 1.2 else "needs_review",
        }

    def design_reward_loop(self) -> RewardLoop:
        """Design a new reward loop."""
        return RewardLoop(
            name=f"Reward Loop {random.randint(1, 99)}",
            trigger=random.choice(["login", "mission_end", "pvp_win", "social_share", "milestone"]),
            reward_currency=random.choice(["Gold", "Gems", "Energy"]),
            reward_amount=round(random.uniform(10, 500), 2),
            cooldown_minutes=round(random.choice([0, 5, 60, 1440, 10080]), 1),
        )

    def get_economy_model(self) -> EconomyModel:
        """Return the current economy model."""
        if self._economy is None:
            return self.design_economy()
        return self._economy
