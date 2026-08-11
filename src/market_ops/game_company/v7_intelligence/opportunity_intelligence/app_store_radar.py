from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime, timedelta
import random


@dataclass
class AppInfo:
    app_id: str
    name: str
    developer: str
    category: str
    rating: float
    downloads: int
    revenue: float
    release_date: str
    store: str
    trend_score: float = 0.0


@dataclass
class TrendingApp:
    app: AppInfo
    rank_change: int
    momentum_score: float


@dataclass
class NewRelease:
    app: AppInfo
    launch_date: str
    early_rating: float
    download_velocity: int


class AppStoreRadar:
    """Monitor and analyze app store data across platforms."""

    _mock_apps: List[AppInfo] = field(default_factory=list)

    def __init__(self):
        self._mock_apps = self._generate_mock_apps()

    def _generate_mock_apps(self) -> List[AppInfo]:
        categories = ["RPG", "Strategy", "Puzzle", "Action", "Simulation", "Casual"]
        stores = ["App Store", "Google Play"]
        apps = []
        for i in range(20):
            cat = random.choice(categories)
            store = random.choice(stores)
            apps.append(
                AppInfo(
                    app_id=f"app_{i:03d}",
                    name=f"Game {cat} {i}",
                    developer=f"DevStudio {i}",
                    category=cat,
                    rating=round(random.uniform(3.5, 5.0), 2),
                    downloads=random.randint(10000, 10000000),
                    revenue=round(random.uniform(1000, 5000000), 2),
                    release_date=(datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
                    store=store,
                    trend_score=round(random.uniform(0, 100), 2),
                )
            )
        return apps

    def scan(self, store: str, category: str) -> Dict[str, Any]:
        """Scan a specific store and category."""
        filtered = [a for a in self._mock_apps if a.store == store and a.category == category]
        return {
            "store": store,
            "category": category,
            "app_count": len(filtered),
            "avg_rating": round(sum(a.rating for a in filtered) / len(filtered), 2) if filtered else 0.0,
            "total_downloads": sum(a.downloads for a in filtered),
            "apps": filtered,
        }

    def get_top_apps(self) -> List[AppInfo]:
        """Return top apps by downloads."""
        return sorted(self._mock_apps, key=lambda a: a.downloads, reverse=True)[:10]

    def get_trending(self) -> List[TrendingApp]:
        """Return trending apps with momentum."""
        trending = []
        for app in self._mock_apps[:10]:
            trending.append(
                TrendingApp(
                    app=app,
                    rank_change=random.randint(-20, 50),
                    momentum_score=round(random.uniform(0, 100), 2),
                )
            )
        return sorted(trending, key=lambda t: t.momentum_score, reverse=True)

    def get_new_releases(self) -> List[NewRelease]:
        """Return recent new releases."""
        recent = [a for a in self._mock_apps if datetime.strptime(a.release_date, "%Y-%m-%d") > datetime.now() - timedelta(days=30)]
        return [
            NewRelease(
                app=app,
                launch_date=app.release_date,
                early_rating=app.rating,
                download_velocity=random.randint(1000, 500000),
            )
            for app in recent
        ]
