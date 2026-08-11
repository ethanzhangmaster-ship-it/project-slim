"""Creative Performance Database — 创意表现数据库

存储所有创意的表现数据，支持查询和统计。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import numpy as np

from ..config import OUTPUT_DIR


class CreativePerformanceDB:
    """创意表现数据库"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = OUTPUT_DIR / "v38_1" / "creative_performance_db.json"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.data: List[dict] = []
        self._load()

    def _load(self):
        """加载数据库"""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.data = data.get("data", [])
            except Exception:
                pass

    def save(self):
        """保存数据库"""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": self.data,
                "timestamp": datetime.now().isoformat(),
                "total": len(self.data),
                "summary": self.get_summary(),
            }, f, ensure_ascii=False, indent=2)

    def add_performance(self, creative_id: str, video_name: str,
                        platform: str, dna: dict, performance: dict,
                        raw: dict = None):
        """添加表现数据"""
        # 检查是否已存在
        existing = self.get_by_creative_id(creative_id)
        if existing:
            # 更新
            existing["performance"] = performance
            existing["updated_at"] = datetime.now().isoformat()
            if raw:
                existing["raw"] = raw
        else:
            # 新增
            self.data.append({
                "creative_id": creative_id,
                "video_name": video_name,
                "platform": platform,
                "dna": dna,
                "performance": performance,
                "raw": raw or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
        self.save()

    def get_by_creative_id(self, creative_id: str) -> Optional[dict]:
        """按 creative_id 查询"""
        for item in self.data:
            if item.get("creative_id") == creative_id:
                return item
        return None

    def query(self, filters: Dict = None) -> List[dict]:
        """复杂查询"""
        results = self.data

        if filters:
            # DNA 过滤
            if "hook" in filters:
                results = [r for r in results if r.get("dna", {}).get("hook") == filters["hook"]]
            if "gameplay" in filters:
                results = [r for r in results if r.get("dna", {}).get("gameplay") == filters["gameplay"]]
            if "subject" in filters:
                results = [r for r in results if r.get("dna", {}).get("subject") == filters["subject"]]
            if "reward" in filters:
                results = [r for r in results if r.get("dna", {}).get("reward") == filters["reward"]]

            # Performance 过滤
            if "min_ctr" in filters:
                results = [r for r in results if r.get("performance", {}).get("ctr", 0) >= filters["min_ctr"]]
            if "max_cpi" in filters:
                results = [r for r in results if r.get("performance", {}).get("cpi", float('inf')) <= filters["max_cpi"]]
            if "min_roi" in filters:
                results = [r for r in results if r.get("performance", {}).get("d7_roi", 0) >= filters["min_roi"]]

            # Platform 过滤
            if "platform" in filters:
                results = [r for r in results if r.get("platform") == filters["platform"]]

        return results

    def get_winners(self, min_ctr: float = 3.0, max_cpi: float = 0.6,
                    min_roi: float = 0.2) -> List[dict]:
        """获取 Winner"""
        return self.query({
            "min_ctr": min_ctr,
            "max_cpi": max_cpi,
            "min_roi": min_roi,
        })

    def get_summary(self) -> dict:
        """获取数据库汇总"""
        if not self.data:
            return {}

        ctrs = [r["performance"]["ctr"] for r in self.data]
        cpis = [r["performance"]["cpi"] for r in self.data if r["performance"]["cpi"] < 10]
        d7_rois = [r["performance"]["d7_roi"] for r in self.data]
        d30_rois = [r["performance"]["d30_roi"] for r in self.data]

        return {
            "total_creatives": len(self.data),
            "avg_ctr": round(np.mean(ctrs), 2),
            "median_ctr": round(np.median(ctrs), 2),
            "avg_cpi": round(np.mean(cpis), 2),
            "median_cpi": round(np.median(cpis), 2),
            "avg_d7_roi": round(np.mean(d7_rois), 3),
            "avg_d30_roi": round(np.mean(d30_rois), 3),
            "winners_count": len(self.get_winners()),
        }

    def export_training_data(self, output_path: Optional[Path] = None) -> Path:
        """导出训练数据"""
        if output_path is None:
            output_path = OUTPUT_DIR / "v38_1" / "training_data.json"

        training_data = []
        for item in self.data:
            dna = item.get("dna", {})
            perf = item.get("performance", {})

            training_data.append({
                "features": {
                    "hook": dna.get("hook", ""),
                    "subject": dna.get("subject", ""),
                    "gameplay": dna.get("gameplay", ""),
                    "reward": dna.get("reward", ""),
                },
                "targets": {
                    "ctr": perf.get("ctr", 0),
                    "cpi": perf.get("cpi", 0),
                    "d7_roi": perf.get("d7_roi", 0),
                    "d30_roi": perf.get("d30_roi", 0),
                },
                "meta": {
                    "creative_id": item.get("creative_id", ""),
                    "video_name": item.get("video_name", ""),
                    "platform": item.get("platform", ""),
                },
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": training_data,
                "timestamp": datetime.now().isoformat(),
                "total_samples": len(training_data),
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def get_dna_distribution(self) -> Dict[str, Dict[str, int]]:
        """获取 DNA 分布"""
        dist = {
            "hook": {},
            "subject": {},
            "gameplay": {},
            "reward": {},
        }

        for item in self.data:
            dna = item.get("dna", {})
            for key in dist.keys():
                val = dna.get(key, "unknown")
                dist[key][val] = dist[key].get(val, 0) + 1

        return dist
