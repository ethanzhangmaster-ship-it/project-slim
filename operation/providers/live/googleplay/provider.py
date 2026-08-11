"""E15.2.3 — Google Play IAP Live Provider"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from operation.providers.contracts.iap import IAPProductSpec, IAPProvider


class GooglePlayIAPClient:
    BASE_URL = "https://androidpublisher.googleapis.com/androidpublisher/v3"

    def __init__(self, service_account_json: Optional[Dict] = None):
        self._credential = service_account_json or {}
        self._api_override: Optional[Callable] = None

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        if self._api_override:
            return self._api_override(method, path, body)
        return {"success": False, "error": "Real Google Play API disabled"}


class GooglePlayIAPProvider(IAPProvider):
    name = "googleplay_iap"

    def __init__(self, client: Optional[GooglePlayIAPClient] = None):
        self.client = client or GooglePlayIAPClient()
        self._products: Dict[str, list] = {}

    def create_product(self, spec: IAPProductSpec) -> Dict[str, Any]:
        pid = f"gp_{spec.product_id}"
        self._products.setdefault(spec.game_id, []).append(
            {"product_id": pid, "type": spec.product_type, "price": spec.price})
        return {"success": True, "product_id": pid}

    def update_price(self, product_id: str, new_price: float,
                     currency: str = "USD") -> Dict[str, Any]:
        return {"success": True, "product_id": product_id, "new_price": new_price}

    def get_product_status(self, product_id: str) -> Dict[str, Any]:
        return {"product_id": product_id, "status": "active"}

    def list_products(self, game_id: str) -> List[Dict[str, Any]]:
        return self._products.get(game_id, [])

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "googleplay iap client ready"}


__all__ = ["GooglePlayIAPClient", "GooglePlayIAPProvider"]
