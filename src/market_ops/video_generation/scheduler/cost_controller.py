"""Cost Controller - 成本控制器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class CostRecord:
    """成本记录"""
    platform: str
    shot_id: str
    duration: float
    resolution: str
    credits: float = 0.0
    usd: float = 0.0
    timestamp: str = ""


@dataclass
class CostReport:
    """成本报告"""
    total_duration: float = 0
    total_credits: float = 0
    total_usd: float = 0
    breakdown: List[CostRecord] = field(default_factory=list)


class CostController:
    """成本控制器"""

    PLATFORM_COST_PER_SECOND = {
        "veo": 0.15,
        "kling": 0.20,
        "runway": 0.25,
        "pika": 0.10,
        "hailuo": 0.18,
        "luma": 0.30,
        "comfyui": 0.05,
    }

    def __init__(self):
        self.records: List[CostRecord] = []

    def add_record(self, platform: str, shot_id: str, duration: float, resolution: str) -> CostRecord:
        """添加成本记录"""
        rate = self.PLATFORM_COST_PER_SECOND.get(platform, 0.15)
        usd = duration * rate
        credits = usd * 10

        record = CostRecord(
            platform=platform,
            shot_id=shot_id,
            duration=duration,
            resolution=resolution,
            credits=credits,
            usd=usd,
        )
        self.records.append(record)
        return record

    def generate_report(self) -> CostReport:
        """生成成本报告"""
        report = CostReport()
        for record in self.records:
            report.total_duration += record.duration
            report.total_credits += record.credits
            report.total_usd += record.usd
            report.breakdown.append(record)
        return report

    def save_report(self, path: str) -> None:
        """保存成本报告"""
        report = self.generate_report()
        data = {
            "total_duration": report.total_duration,
            "total_credits": report.total_credits,
            "total_usd": round(report.total_usd, 2),
            "breakdown": [
                {
                    "platform": r.platform,
                    "shot_id": r.shot_id,
                    "duration": r.duration,
                    "resolution": r.resolution,
                    "credits": round(r.credits, 2),
                    "usd": round(r.usd, 2),
                }
                for r in report.breakdown
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def estimate_cost(self, platform: str, duration: float) -> float:
        """估算成本"""
        rate = self.PLATFORM_COST_PER_SECOND.get(platform, 0.15)
        return duration * rate