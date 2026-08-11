from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedOffer:
    offer_id: str
    name: str
    price: float = 0.0
    original_price: float = 0.0
    discount: float = 0.0
    contents: List[str] = field(default_factory=list)
    target_segment: str = ""
    expected_conversion: float = 0.0


class OfferGenerator:
    def __init__(self):
        self.offers: Dict[str, GeneratedOffer] = {}

    def generate(self, genre: str, audience: str = "Female 25-44") -> List[GeneratedOffer]:
        offers = []
        
        offers.append(self._create_starter_pack(audience))
        offers.append(self._create_weekend_sale())
        offers.append(self._create_limited_time_offer(genre))
        
        for offer in offers:
            self.offers[offer.offer_id] = offer
        
        return offers

    def generate_event(self, genre: str, event_type: str) -> List[GeneratedOffer]:
        offers = []
        
        if event_type == "Christmas":
            offers.append(GeneratedOffer(
                offer_id="offer_christmas",
                name="Christmas Special",
                price=9.99,
                original_price=19.99,
                discount=50,
                contents=["2000 Gems", "50000 Coins", "Christmas Decorations"],
                target_segment="All Users",
                expected_conversion=0.03,
            ))
        elif event_type == "Anniversary":
            offers.append(GeneratedOffer(
                offer_id="offer_anniversary",
                name="1 Year Anniversary",
                price=14.99,
                original_price=29.99,
                discount=50,
                contents=["5000 Gems", "100000 Coins", "Anniversary Exclusive Items"],
                target_segment="Loyal Users",
                expected_conversion=0.025,
            ))
        else:
            offers.append(self._create_limited_time_offer(genre))
        
        for offer in offers:
            self.offers[offer.offer_id] = offer
        
        return offers

    def _create_starter_pack(self, audience: str) -> GeneratedOffer:
        return GeneratedOffer(
            offer_id="offer_starter",
            name="Starter Pack",
            price=4.99,
            original_price=9.99,
            discount=50,
            contents=["500 Gems", "10000 Coins", "1 Energy Refill", "Exclusive Item"],
            target_segment="New Users",
            expected_conversion=0.038,
        )

    def _create_weekend_sale(self) -> GeneratedOffer:
        return GeneratedOffer(
            offer_id="offer_weekend",
            name="Weekend Sale",
            price=7.99,
            original_price=14.99,
            discount=47,
            contents=["1000 Gems", "20000 Coins", "3 Energy Refills"],
            target_segment="Active Users",
            expected_conversion=0.025,
        )

    def _create_limited_time_offer(self, genre: str) -> GeneratedOffer:
        contents = ["800 Gems", "15000 Coins"]
        if "Decoration" in genre:
            contents.append("Limited Edition Decoration")
        
        return GeneratedOffer(
            offer_id="offer_limited",
            name="Limited Time Offer",
            price=6.99,
            original_price=11.99,
            discount=42,
            contents=contents,
            target_segment="All Users",
            expected_conversion=0.02,
        )

    def generate_demo(self) -> List[GeneratedOffer]:
        return self.generate("Merge + Decoration", "US Female 25-44")
