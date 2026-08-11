from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult


class AppStoreConnector(BaseConnector):
    def __init__(self, key_id: str = None, issuer_id: str = None):
        super().__init__(key_id, issuer_id)
        self.platform = "app_store"
        self.key_id = key_id
        self.issuer_id = issuer_id
        self._mock_app = {
            "app_id": "1234567890",
            "name": "Merge Cozy",
            "bundle_id": "com.game.mergecozy",
            "current_version": "1.5.2",
            "status": "Ready for Sale",
        }

    def get_app_info(self, app_id: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, self._mock_app)

    def get_reviews(self, app_id: str = None, limit: int = 50) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        reviews = [
            {"id": "rev_001", "rating": 5, "title": "Love this game!", "body": "So addictive and cozy", "country": "US", "date": "2026-07-07"},
            {"id": "rev_002", "rating": 4, "title": "Great but slow", "body": "Fun merge game, wish it was faster", "country": "GB", "date": "2026-07-06"},
            {"id": "rev_003", "rating": 5, "title": "Best merge game", "body": "Better than Merge Mansion", "country": "CA", "date": "2026-07-05"},
        ]
        return self._make_result(True, {"reviews": reviews[:limit], "average_rating": 4.7, "total_reviews": 45230})

    def get_rankings(self, app_id: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        rankings = {
            "free": {"US": 28, "GB": 45, "DE": 62, "JP": 115},
            "paid": {"US": 0, "GB": 0, "DE": 0, "JP": 0},
            "top_grossing": {"US": 85, "GB": 112, "DE": 130, "JP": 210},
            "category": {"Puzzle": {"US": 12, "GB": 18, "DE": 22}},
        }
        return self._make_result(True, rankings)

    def get_sales_report(self, date: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self._make_result(True, {
            "date": date,
            "downloads": 12500,
            "updates": 8500,
            "iap_revenue": 8420.50,
            "app_revenue": 0,
            "refunds": 12,
            "proceeds": 7157.43,
        })

    def submit_build(self, app_id: str, build_number: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {
            "app_id": app_id,
            "build_number": build_number,
            "status": "Uploaded",
            "processing": True,
        })


class GooglePlayConnector(BaseConnector):
    def __init__(self, service_account_key: str = None, package_name: str = None):
        super().__init__(service_account_key, package_name)
        self.platform = "google_play"
        self.package_name = package_name
        self._mock_app = {
            "package_name": "com.game.mergecozy",
            "name": "Merge Cozy",
            "current_version": "1.5.2",
            "status": "published",
        }

    def get_app_info(self) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, self._mock_app)

    def get_reviews(self, limit: int = 50) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        reviews = [
            {"id": "gplay_001", "rating": 5, "title": "Amazing", "body": "Best merge game ever", "country": "US", "date": "2026-07-07"},
            {"id": "gplay_002", "rating": 4, "title": "Good", "body": "Fun but needs more content", "country": "IN", "date": "2026-07-06"},
        ]
        return self._make_result(True, {"reviews": reviews[:limit], "average_rating": 4.5, "total_reviews": 38500})

    def get_stats(self, date: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "installs": 8900,
            "uninstalls": 1200,
            "active_devices": 45000,
            "crashes": 45,
            "anrs": 12,
        })

    def get_rankings(self) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {
            "top_free": {"US": 35, "IN": 12, "BR": 22},
            "top_grossing": {"US": 92, "IN": 55, "BR": 48},
            "category_rank": {"Puzzle": {"US": 15, "IN": 8}},
        })
