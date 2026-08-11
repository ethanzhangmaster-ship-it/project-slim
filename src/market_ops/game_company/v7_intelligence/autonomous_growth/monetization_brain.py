from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class MonetizationRecommendation:
    recommendation_id: str
    type: str
    priority: str
    action: str
    expected_revenue_lift: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RevenueOptimization:
    segment: str
    current_arpu: float
    target_arpu: float
    tactics: List[str] = field(default_factory=list)
    timeline_days: int = 30


class MonetizationBrain:
    """变现大脑，负责内购和广告变现优化。"""

    def __init__(self):
        self.iap_history: List[Dict[str, Any]] = []
        self.ads_history: List[Dict[str, Any]] = []

    def optimize_iap(self, user_segments: List[Dict[str, Any]]) -> List[MonetizationRecommendation]:
        """优化内购策略。"""
        recommendations = []
        for segment in user_segments:
            spend = segment.get("avg_spend", 0.0)
            segment_name = segment.get("name", "unknown")
            if spend == 0:
                rec = MonetizationRecommendation(
                    recommendation_id=f"iap_{segment_name}_001",
                    type="iap",
                    priority="high",
                    action="introduce_starter_pack",
                    expected_revenue_lift=0.15,
                    details={"segment": segment_name, "price_point": 0.99},
                )
            elif spend < 5.0:
                rec = MonetizationRecommendation(
                    recommendation_id=f"iap_{segment_name}_002",
                    type="iap",
                    priority="medium",
                    action="limited_time_bundle",
                    expected_revenue_lift=0.10,
                    details={"segment": segment_name, "price_point": 4.99},
                )
            else:
                rec = MonetizationRecommendation(
                    recommendation_id=f"iap_{segment_name}_003",
                    type="iap",
                    priority="low",
                    action="vip_subscription",
                    expected_revenue_lift=0.20,
                    details={"segment": segment_name, "price_point": 19.99},
                )
            recommendations.append(rec)
        return recommendations

    def optimize_ads(self, ad_data: Dict[str, Any]) -> List[MonetizationRecommendation]:
        """优化广告变现策略。"""
        recommendations = []
        current_ecpm = ad_data.get("ecpm", 0.0)
        fill_rate = ad_data.get("fill_rate", 0.0)

        if current_ecpm < 3.0:
            recommendations.append(
                MonetizationRecommendation(
                    recommendation_id="ads_ecpm_001",
                    type="ads",
                    priority="high",
                    action="add_rewarded_video",
                    expected_revenue_lift=0.25,
                    details={"current_ecpm": current_ecpm, "target_ecpm": 4.0},
                )
            )
        if fill_rate < 0.9:
            recommendations.append(
                MonetizationRecommendation(
                    recommendation_id="ads_fill_001",
                    type="ads",
                    priority="medium",
                    action="integrate_mediation",
                    expected_revenue_lift=0.12,
                    details={"current_fill_rate": fill_rate, "target_fill_rate": 0.95},
                )
            )
        return recommendations

    def analyze_arpu(self, user_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析每用户平均收入。"""
        if not user_data:
            return {"arpu": 0.0, "arpdau": 0.0, "segments": []}

        total_revenue = sum(u.get("revenue", 0.0) for u in user_data)
        arpu = total_revenue / len(user_data)
        dau = sum(u.get("is_active_today", 0) for u in user_data)
        arpdau = total_revenue / dau if dau > 0 else 0.0

        segments = {}
        for u in user_data:
            seg = u.get("segment", "unknown")
            segments.setdefault(seg, []).append(u.get("revenue", 0.0))

        segment_arpu = {seg: round(sum(revs) / len(revs), 2) for seg, revs in segments.items()}

        return {
            "arpu": round(arpu, 2),
            "arpdau": round(arpdau, 2),
            "total_users": len(user_data),
            "active_users": dau,
            "segment_arpu": segment_arpu,
            "analyzed_at": datetime.now().isoformat(),
        }

    def suggest_offers(self, player_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于玩家状态建议个性化优惠。"""
        offers = []
        level = player_state.get("level", 1)
        days_since_purchase = player_state.get("days_since_purchase", 999)
        currency = player_state.get("in_game_currency", 0)

        if days_since_purchase > 7 and level > 5:
            offers.append({
                "offer_id": "win_back_001",
                "type": "win_back",
                "discount_pct": 50,
                "price": 4.99,
                "items": ["gems_500", " booster_pack"],
                "expires_in_hours": 24,
            })
        if currency < 100 and level > 3:
            offers.append({
                "offer_id": "currency_001",
                "type": "currency_top_up",
                "discount_pct": 20,
                "price": 0.99,
                "items": ["gems_200"],
                "expires_in_hours": 12,
            })
        if level % 10 == 0:
            offers.append({
                "offer_id": f"milestone_{level}",
                "type": "milestone",
                "discount_pct": 30,
                "price": 9.99,
                "items": ["premium_bundle"],
                "expires_in_hours": 48,
            })
        return offers
