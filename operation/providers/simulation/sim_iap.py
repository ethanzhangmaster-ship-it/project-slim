"""E15.2.3 — Simulation IAP Provider"""
from __future__ import annotations
from typing import Any, Dict, List
from operation.providers.contracts.iap import IAPProductSpec, IAPProvider


class SimulationIAPProvider(IAPProvider):
    name = "simulation_iap"

    def __init__(self):
        self._products: Dict[str, list] = {}

    def create_product(self, spec: IAPProductSpec) -> Dict[str, Any]:
        prod = {
            "product_id": spec.product_id, "type": spec.product_type,
            "price": spec.price, "currency": spec.currency,
            "status": "active",
        }
        self._products.setdefault(spec.game_id, []).append(prod)
        return {"success": True, "product_id": spec.product_id}

    def update_price(self, product_id: str, new_price: float,
                     currency: str = "USD") -> Dict[str, Any]:
        return {"success": True, "product_id": product_id, "new_price": new_price}

    def get_product_status(self, product_id: str) -> Dict[str, Any]:
        return {"product_id": product_id, "status": "active"}

    def list_products(self, game_id: str) -> List[Dict[str, Any]]:
        return self._products.get(game_id, [])

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "simulation iap healthy"}


__all__ = ["SimulationIAPProvider"]
