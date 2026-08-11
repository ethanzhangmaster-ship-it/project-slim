from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class BidDecision:
    campaign_id: str
    platform: str
    old_bid: float
    new_bid: float
    action: str
    reason: str
    confidence: float = 0.0


class BidOptimizer:
    def __init__(self):
        self.target_cpi = 2.0
        self.target_roas = 2.0
        self.bid_min = 0.5
        self.bid_max = 20.0

    def optimize(self, campaign_id: str, platform: str, metrics: Dict[str, float]) -> BidDecision:
        cpi = metrics.get("cpi", 0.0)
        cpp = metrics.get("cpp", 0.0)
        roas = metrics.get("roas", 0.0)
        purchase_prob = metrics.get("purchase_prob", 0.0)
        current_bid = metrics.get("current_bid", 10.0)

        if cpi == 0:
            cpi = float("inf")

        if roas > self.target_roas * 1.5 and cpi < self.target_cpi:
            new_bid = min(current_bid * 1.2, self.bid_max)
            action = "increase"
            reason = f"ROAS {roas:.1f} exceeds target, CPI {cpi:.2f} below target"
            confidence = 0.9
        elif roas < self.target_roas * 0.5 or cpi > self.target_cpi * 2:
            new_bid = max(current_bid * 0.8, self.bid_min)
            action = "decrease"
            reason = f"ROAS {roas:.1f} below target or CPI {cpi:.2f} too high"
            confidence = 0.85
        elif purchase_prob < 0.1:
            new_bid = max(current_bid * 0.5, self.bid_min)
            action = "decrease"
            reason = f"Purchase probability {purchase_prob:.2f} too low"
            confidence = 0.8
        elif cpp > 5.0:
            new_bid = max(current_bid * 0.7, self.bid_min)
            action = "decrease"
            reason = f"CPP {cpp:.2f} exceeds threshold"
            confidence = 0.75
        else:
            new_bid = current_bid
            action = "maintain"
            reason = "Metrics within acceptable range"
            confidence = 0.95

        return BidDecision(
            campaign_id=campaign_id,
            platform=platform,
            old_bid=current_bid,
            new_bid=round(new_bid, 2),
            action=action,
            reason=reason,
            confidence=confidence,
        )

    def optimize_demo(self) -> BidDecision:
        metrics = {
            "cpi": 1.5,
            "cpp": 2.3,
            "roas": 3.5,
            "purchase_prob": 0.25,
            "current_bid": 10.0,
        }
        return self.optimize("campaign_001", "meta", metrics)
