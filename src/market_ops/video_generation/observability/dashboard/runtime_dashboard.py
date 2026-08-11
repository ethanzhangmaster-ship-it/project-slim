"""Runtime Dashboard - 运行仪表板"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .dashboard_schema import (
    DailyDashboard,
    GenerationSummary,
    QueueSummary,
    CostSummary,
    PlatformSummary,
)


class RuntimeDashboard:
    """运行仪表板 - 生成每日运营摘要"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir) if storage_dir else Path(__file__).resolve().parent / "data"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_summary(
        self,
        generation_data: Dict[str, Any],
        queue_data: Dict[str, Any],
        cost_data: Dict[str, Any],
        platform_data: List[Dict[str, Any]] = None,
        top_creatives: List[Dict[str, Any]] = None,
        alerts: List[Dict[str, Any]] = None,
    ) -> DailyDashboard:
        """生成每日摘要"""
        
        generation = GenerationSummary(
            total=generation_data.get("total", 0),
            success=generation_data.get("success", 0),
            failed=generation_data.get("failed", 0),
            success_rate=generation_data.get("success_rate", 0.0),
        )
        
        queue = QueueSummary(
            pending=queue_data.get("pending", 0),
            processing=queue_data.get("processing", 0),
            retrying=queue_data.get("retrying", 0),
            dead_letter=queue_data.get("dead_letter", 0),
        )
        
        cost = CostSummary(
            total=cost_data.get("total", 0.0),
            avg_cost=cost_data.get("avg_cost", 0.0),
            success_cost=cost_data.get("success_cost", 0.0),
            failed_cost=cost_data.get("failed_cost", 0.0),
            budget_remaining=cost_data.get("budget_remaining", 0.0),
            budget_usage_percent=cost_data.get("budget_usage_percent", 0.0),
        )
        
        platforms = []
        if platform_data:
            for p in platform_data:
                platforms.append(PlatformSummary(
                    platform=p.get("platform", ""),
                    count=p.get("count", 0),
                    cost=p.get("cost", 0.0),
                    avg_cost=p.get("avg_cost", 0.0),
                    success_rate=p.get("success_rate", 0.0),
                    avg_time=p.get("avg_time", 0.0),
                ))
        
        dashboard = DailyDashboard(
            date=datetime.now().strftime("%Y-%m-%d"),
            generation=generation,
            queue=queue,
            cost=cost,
            platforms=platforms,
            top_creatives=top_creatives or [],
            alerts=alerts or [],
        )
        
        return dashboard
    
    def generate_demo(self) -> DailyDashboard:
        """生成演示数据"""
        generation_data = {"total": 842, "success": 812, "failed": 30, "success_rate": 0.964}
        queue_data = {"pending": 20, "processing": 15, "retrying": 3, "dead_letter": 2}
        cost_data = {
            "total": 320.5,
            "avg_cost": 0.38,
            "success_cost": 0.41,
            "failed_cost": 0.08,
            "budget_remaining": 679.5,
            "budget_usage_percent": 32.1,
        }
        platform_data = [
            {"platform": "kling", "count": 500, "cost": 250.0, "avg_cost": 0.50, "success_rate": 0.97, "avg_time": 45.0},
            {"platform": "veo", "count": 200, "cost": 110.0, "avg_cost": 0.55, "success_rate": 0.95, "avg_time": 60.0},
            {"platform": "comfyui", "count": 142, "cost": 11.5, "avg_cost": 0.08, "success_rate": 0.98, "avg_time": 120.0},
        ]
        top_creatives = [
            {"creative_id": "video_001", "ctr": 5.8, "qa_score": 92, "dna": "witch treasure opening"},
            {"creative_id": "video_002", "ctr": 4.2, "qa_score": 88, "dna": "battle scene epic"},
            {"creative_id": "video_003", "ctr": 3.9, "qa_score": 85, "dna": "character reveal surprise"},
        ]
        
        return self.generate_summary(
            generation_data=generation_data,
            queue_data=queue_data,
            cost_data=cost_data,
            platform_data=platform_data,
            top_creatives=top_creatives,
        )
    
    def save_dashboard(self, dashboard: DailyDashboard, filename: str = None) -> str:
        """保存仪表板数据"""
        if filename is None:
            filename = f"dashboard_{dashboard.date}.json"
        
        path = self.storage_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dashboard.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(path)
    
    def load_dashboard(self, date: str) -> Optional[DailyDashboard]:
        """加载指定日期的仪表板"""
        filename = f"dashboard_{date}.json"
        path = self.storage_dir / filename
        
        if not path.exists():
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return DailyDashboard(
            date=data.get("date", ""),
            generation=GenerationSummary(**data.get("generation", {})),
            queue=QueueSummary(**data.get("queue", {})),
            cost=CostSummary(**data.get("cost", {})),
            platforms=[PlatformSummary(**p) for p in data.get("platforms", [])],
            top_creatives=data.get("top_creatives", []),
            alerts=data.get("alerts", []),
        )
    
    def export_markdown(self, dashboard: DailyDashboard) -> str:
        """导出 Markdown 格式日报"""
        lines = [
            f"# Daily Runtime Dashboard - {dashboard.date}",
            "",
            "## Generation",
            f"- Total: {dashboard.generation.total}",
            f"- Success: {dashboard.generation.success}",
            f"- Failed: {dashboard.generation.failed}",
            f"- Success Rate: {dashboard.generation.success_rate * 100:.1f}%",
            "",
            "## Queue",
            f"- Pending: {dashboard.queue.pending}",
            f"- Processing: {dashboard.queue.processing}",
            "",
            "## Cost",
            f"- Total: ${dashboard.cost.total:.2f}",
            f"- Avg: ${dashboard.cost.avg_cost:.3f}",
            f"- Budget Remaining: ${dashboard.cost.budget_remaining:.2f}",
            "",
            "## Platforms",
            "| Platform | Count | Cost | Avg | Rate |",
            "|----------|-------|------|-----|------|",
        ]
        for p in dashboard.platforms:
            lines.append(
                f"| {p.platform} | {p.count} | ${p.cost:.2f} | ${p.avg_cost:.3f} | {p.success_rate * 100:.1f}% |"
            )
        
        lines.extend([
            "",
            "## Top Creatives",
            "| ID | CTR | QA | DNA |",
            "|----|-----|----|-----|",
        ])
        for c in dashboard.top_creatives:
            lines.append(
                f"| {c.get('creative_id', '')} | {c.get('ctr', 0)}% | {c.get('qa_score', 0)} | {c.get('dna', '')} |"
            )
        
        return "\n".join(lines)
