"""Generation Dashboard"""
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, date


@dataclass
class DashboardData:
    """Dashboard 数据"""
    date: str = ""
    total_generated: int = 0
    successful: int = 0
    failed: int = 0
    total_cost: float = 0.0
    success_rate: float = 0.0
    best_platform: str = ""
    best_platform_stats: Dict[str, Any] = field(default_factory=dict)
    platform_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quality_avg: float = 0.0
    queue_size: int = 0
    active_workers: int = 0
    daily_budget_used: float = 0.0
    daily_budget_remaining: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GenerationDashboard:
    """生成仪表盘"""

    def __init__(self):
        self.storage = None
        self.budget_manager = None
        self.asset_manager = None

    def _ensure_storage(self):
        if self.storage is None:
            from ..storage.generation_storage import GenerationStorage
            self.storage = GenerationStorage()
        return self.storage

    def _ensure_budget(self):
        if self.budget_manager is None:
            from ..cost.budget_manager import BudgetManager
            self.budget_manager = BudgetManager()
        return self.budget_manager

    def _ensure_assets(self):
        if self.asset_manager is None:
            from ..assets.asset_manager import AssetManager
            self.asset_manager = AssetManager()
        return self.asset_manager

    def get_today_summary(self) -> DashboardData:
        data = DashboardData(date=date.today().isoformat())

        storage = self._ensure_storage()
        stats = storage.get_stats()
        data.total_generated = stats["total_tasks"]
        data.successful = stats["completed"]
        data.failed = stats["failed"]
        data.success_rate = stats["success_rate"]
        data.total_cost = stats["total_cost"]

        budget = self._ensure_budget()
        data.daily_budget_used = budget.get_daily_spent()
        data.daily_budget_remaining = budget.get_daily_remaining()

        tasks = storage.list_tasks(limit=100)
        platform_stats = {}
        for task in tasks:
            p = task.platform
            if p not in platform_stats:
                platform_stats[p] = {"count": 0, "success": 0, "cost": 0}
            platform_stats[p]["count"] += 1
            if task.status.value == "completed":
                platform_stats[p]["success"] += 1
            platform_stats[p]["cost"] += task.cost

        for p in platform_stats:
            s = platform_stats[p]
            s["success_rate"] = round(s["success"] / s["count"] * 100, 1) if s["count"] > 0 else 0
            s["cost"] = round(s["cost"], 2)

        data.platform_breakdown = platform_stats

        if platform_stats:
            best = max(platform_stats.keys(),
                       key=lambda k: platform_stats[k].get("success_rate", 0))
            data.best_platform = best
            data.best_platform_stats = platform_stats[best]

        try:
            assets = self._ensure_assets().list_assets()
            if assets:
                data.quality_avg = round(sum(a.quality_score for a in assets) / len(assets), 1)
        except Exception:
            pass

        return data

    def render_text(self) -> str:
        data = self.get_today_summary()
        lines = []
        lines.append("=" * 50)
        lines.append("  Generation Dashboard")
        lines.append(f"  Date: {data.date}")
        lines.append("=" * 50)
        lines.append("")
        lines.append("  Today:")
        lines.append(f"    Generated:  {data.total_generated} videos")
        lines.append(f"    Success:    {data.successful}")
        lines.append(f"    Failed:     {data.failed}")
        lines.append(f"    Cost:       ${data.total_cost:.2f}")
        lines.append(f"    Success Rate: {data.success_rate:.1f}%")
        lines.append("")
        lines.append("  Budget:")
        lines.append(f"    Used:       ${data.daily_budget_used:.2f}")
        lines.append(f"    Remaining:  ${data.daily_budget_remaining:.2f}")
        lines.append("")
        if data.best_platform:
            lines.append(f"  Best Platform: {data.best_platform}")
            lines.append(f"    Success Rate: {data.best_platform_stats.get('success_rate', 0):.1f}%")
        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)

    def to_json(self) -> str:
        import json
        return json.dumps(self.get_today_summary().to_dict(), indent=2, ensure_ascii=False)
