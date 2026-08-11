"""
E15.2.3 — IAP Provider Contract
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IAPProductSpec:
    """Specification for creating an IAP product."""
    game_id: str
    product_id: str
    product_type: str     # "consumable" | "non_consumable" | "subscription"
    price: float
    currency: str = "USD"
    platform: str = ""    # "google_play" | "app_store"
    title: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class IAPProvider(ABC):
    """Provider contract for in-app purchase management."""

    name: str = "iap"

    @abstractmethod
    def create_product(self, spec: IAPProductSpec) -> Dict[str, Any]:
        """Create an IAP product on the store platform."""
        ...

    @abstractmethod
    def update_price(self, product_id: str, new_price: float,
                     currency: str = "USD") -> Dict[str, Any]:
        """Update product price."""
        ...

    @abstractmethod
    def get_product_status(self, product_id: str) -> Dict[str, Any]:
        """Check product status."""
        ...

    @abstractmethod
    def list_products(self, game_id: str) -> List[Dict[str, Any]]:
        """List all IAP products for a game."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check store connectivity."""
        ...


__all__ = ["IAPProvider", "IAPProductSpec"]
