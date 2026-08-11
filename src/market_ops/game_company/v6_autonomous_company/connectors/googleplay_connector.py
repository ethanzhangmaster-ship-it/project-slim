from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult


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
