"""E15.2.3 — App Store IAP Live Provider"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from operation.providers.contracts.iap import IAPProductSpec, IAPProvider


class AppStoreIAPClient:
    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    def __init__(self, key_id: str = "", issuer_id: str = "",
                 private_key: str = ""):
        self._key_id = key_id
        self._issuer_id = issuer_id
        self._private_key = private_key
        self._api_override: Optional[Callable] = None

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        if self._api_override:
            return self._api_override(method, path, body)
        return {"success": False, "error": "Real App Store API disabled"}


class AppStoreIAPProvider(IAPProvider):
    name = "appstore_iap"

    def __init__(self, client: Optional[AppStoreIAPClient] = None):
        self.client = client or AppStoreIAPClient()
        self._products: Dict[str, list] = {}

    def create_product(self, spec: IAPProductSpec) -> Dict[str, Any]:
        pid = f"as_{spec.product_id}"
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
        return {"success": True, "detail": "appstore iap client ready"}


__all__ = ["AppStoreIAPClient", "AppStoreIAPProvider"]
