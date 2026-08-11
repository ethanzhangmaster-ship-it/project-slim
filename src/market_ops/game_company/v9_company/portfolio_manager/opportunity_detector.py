from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class GameOpportunity:
    opp_id: str
    title: str
    genre: str
    estimated_budget: float
    expected_roi: float

    def to_dict(self):
        return {
            "opp_id": self.opp_id,
            "title": self.title,
            "genre": self.genre,
            "estimated_budget": self.estimated_budget,
            "expected_roi": self.expected_roi,
        }


@dataclass
class ExpansionOpportunity:
    opp_id: str
    game_id: str
    market: str
    expansion_type: str
    projected_revenue: float

    def to_dict(self):
        return {
            "opp_id": self.opp_id,
            "game_id": self.game_id,
            "market": self.market,
            "expansion_type": self.expansion_type,
            "projected_revenue": self.projected_revenue,
        }


@dataclass
class PartnerOpportunity:
    opp_id: str
    partner_name: str
    partnership_type: str
    value: float

    def to_dict(self):
        return {
            "opp_id": self.opp_id,
            "partner_name": self.partner_name,
            "partnership_type": self.partnership_type,
            "value": self.value,
        }


class OpportunityDetector:
    def __init__(self):
        self._game_opps: List[GameOpportunity] = [
            GameOpportunity(
                opp_id="go_001",
                title="Cyber RPG",
                genre="RPG",
                estimated_budget=2000000.0,
                expected_roi=0.35,
            ),
        ]
        self._expansion_opps: List[ExpansionOpportunity] = [
            ExpansionOpportunity(
                opp_id="eo_001",
                game_id="g001",
                market="Asia",
                expansion_type="localization",
                projected_revenue=500000.0,
            ),
        ]
        self._partner_opps: List[PartnerOpportunity] = [
            PartnerOpportunity(
                opp_id="po_001",
                partner_name="Epic Games",
                partnership_type="cross_promotion",
                value=300000.0,
            ),
        ]

    def scan_opportunities(self) -> Dict:
        return {
            "new_games": [o.to_dict() for o in self._game_opps],
            "expansions": [o.to_dict() for o in self._expansion_opps],
            "partnerships": [o.to_dict() for o in self._partner_opps],
        }

    def get_new_game_opportunities(self) -> List[GameOpportunity]:
        return self._game_opps

    def get_expansion_opportunities(self) -> List[ExpansionOpportunity]:
        return self._expansion_opps

    def get_partner_opportunities(self) -> List[PartnerOpportunity]:
        return self._partner_opps

    def evaluate_opportunity(self, opp_id: str) -> Optional[Dict]:
        for o in self._game_opps + self._expansion_opps + self._partner_opps:
            if o.opp_id == opp_id:
                return {
                    "opportunity": o.to_dict(),
                    "score": 80,
                    "recommendation": "pursue",
                }
        return None

    def get_stats(self) -> Dict:
        return {
            "new_game_opportunities": len(self._game_opps),
            "expansion_opportunities": len(self._expansion_opps),
            "partner_opportunities": len(self._partner_opps),
        }
