"""E15.2.4 — Mock IAP Client (Google Play Billing + App Store IAP)"""
from typing import Dict


class MockIAPClient:
    def __init__(self):
        self._products: Dict[str, dict] = {}

    def create_product(self, game_id: str, product_id: str,
                       product_type: str, price: float,
                       platform: str, title: str = "") -> dict:
        prod = {
            "game_id": game_id, "product_id": product_id,
            "product_type": product_type, "price": price,
            "platform": platform, "title": title, "status": "active",
        }
        key = f"{game_id}/{product_id}"
        self._products[key] = prod
        return {"success": True, "product_id": product_id, **prod}

    def update_price(self, game_id: str, product_id: str,
                     new_price: float) -> dict:
        key = f"{game_id}/{product_id}"
        if key in self._products:
            old = self._products[key]["price"]
            self._products[key]["price"] = new_price
            return {"success": True, "old_price": old, "new_price": new_price}
        return {"success": False, "error": "product not found"}

    def check_status(self, game_id: str, product_id: str) -> dict:
        key = f"{game_id}/{product_id}"
        p = self._products.get(key, {})
        return {"exists": key in self._products,
                "status": p.get("status", "not_found")}

    def list_products(self, game_id: str) -> list:
        return [v for k, v in self._products.items() if k.startswith(f"{game_id}/")]
