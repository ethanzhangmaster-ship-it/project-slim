"""Creative ↔ Performance Mapping - 创意与表现映射

P2-2: 建立 creative_id ↔ ad_id ↔ performance metrics 的映射关系。

要求：
- 每个 render spec 必须绑定唯一 creative_id
- 每个 ad 必须能回溯 layout_ast
"""
from __future__ import annotations

import json
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .event_tracker import EventTracker, PerformanceMetrics


@dataclass
class CreativeRecord:
    """创意记录 - 绑定 creative_id 与其元数据"""
    creative_id: str
    layout_ast_id: str
    template_id: str
    render_constraints: Dict[str, Any]
    
    ad_id: str = ""
    campaign_id: str = ""
    
    created_at: int = 0
    deployed_at: int = 0
    status: str = "pending"
    
    features: Dict[str, float] = field(default_factory=dict)
    
    metrics: Optional[PerformanceMetrics] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "layout_ast_id": self.layout_ast_id,
            "template_id": self.template_id,
            "render_constraints": self.render_constraints,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "created_at": self.created_at,
            "deployed_at": self.deployed_at,
            "status": self.status,
            "features": self.features,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class PerformanceSnapshot:
    """表现快照 - 记录创意在特定时间点的表现"""
    creative_id: str
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    ctr: float = 0.0
    ipm: float = 0.0
    
    snapshot_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "ctr": round(self.ctr, 4),
            "ipm": round(self.ipm, 3),
            "snapshot_at": self.snapshot_at,
        }


class CreativePerformanceMapper:
    """创意表现映射器 - 建立 creative_id ↔ ad_id ↔ metrics 的完整映射"""
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.records_file = self.output_dir / "creative_records.json"
        self.snapshots_file = self.output_dir / "performance_snapshots.json"
        
        self._records: Dict[str, CreativeRecord] = {}
        self._ad_to_creative: Dict[str, str] = {}
        self._creative_to_ad: Dict[str, str] = {}
        
        self._load_records()
    
    def _load_records(self):
        if self.records_file.exists():
            with open(self.records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for cid, rec_data in data.items():
                    rec_data.pop("creative_id", None)
                    if rec_data.get("metrics"):
                        metrics = PerformanceMetrics(**rec_data["metrics"])
                        rec_data["metrics"] = metrics
                    self._records[cid] = CreativeRecord(
                        creative_id=cid,
                        **rec_data
                    )
                    if rec_data.get("ad_id"):
                        self._ad_to_creative[rec_data["ad_id"]] = cid
                        self._creative_to_ad[cid] = rec_data["ad_id"]
    
    def _save_records(self):
        data = {}
        for cid, rec in self._records.items():
            rec_dict = rec.to_dict()
            rec_dict.pop("creative_id")
            data[cid] = rec_dict
        
        with open(self.records_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def register_creative(self, layout_ast_id: str, template_id: str,
                         render_constraints: Dict[str, Any],
                         features: Dict[str, float] = None) -> str:
        creative_id = f"c_{template_id}_{uuid.uuid4().hex[:8]}"
        
        record = CreativeRecord(
            creative_id=creative_id,
            layout_ast_id=layout_ast_id,
            template_id=template_id,
            render_constraints=render_constraints,
            created_at=int(time.time()),
            status="registered",
            features=features or {},
        )
        
        self._records[creative_id] = record
        self._save_records()
        
        return creative_id
    
    def link_ad(self, creative_id: str, ad_id: str, campaign_id: str = "") -> bool:
        if creative_id not in self._records:
            return False
        
        if ad_id in self._ad_to_creative:
            old_creative = self._ad_to_creative[ad_id]
            print(f"Warning: Ad {ad_id} already linked to {old_creative}")
        
        record = self._records[creative_id]
        record.ad_id = ad_id
        record.campaign_id = campaign_id
        record.deployed_at = int(time.time())
        record.status = "deployed"
        
        self._ad_to_creative[ad_id] = creative_id
        self._creative_to_ad[creative_id] = ad_id
        
        self._save_records()
        return True
    
    def get_creative_record(self, creative_id: str) -> Optional[CreativeRecord]:
        return self._records.get(creative_id)
    
    def get_ad_creative(self, ad_id: str) -> Optional[CreativeRecord]:
        creative_id = self._ad_to_creative.get(ad_id)
        if creative_id:
            return self._records.get(creative_id)
        return None
    
    def update_metrics(self, creative_id: str, metrics: PerformanceMetrics) -> bool:
        if creative_id not in self._records:
            return False
        
        self._records[creative_id].metrics = metrics
        self._save_records()
        return True
    
    def sync_with_tracker(self, tracker: EventTracker) -> int:
        updated = 0
        
        for creative_id in self._records:
            metrics = tracker.get_creative_metrics(creative_id)
            if metrics.impressions > 0:
                self._records[creative_id].metrics = metrics
                updated += 1
        
        self._save_records()
        return updated
    
    def get_performing_creatives(self, min_impressions: int = 100,
                                 sort_by: str = "ctr") -> List[CreativeRecord]:
        performing = []
        
        for record in self._records.values():
            if record.metrics and record.metrics.impressions >= min_impressions:
                performing.append(record)
        
        if sort_by == "ctr":
            performing.sort(key=lambda r: r.metrics.ctr if r.metrics else 0, reverse=True)
        elif sort_by == "ipm":
            performing.sort(key=lambda r: r.metrics.ipm if r.metrics else 0, reverse=True)
        elif sort_by == "roas":
            performing.sort(key=lambda r: r.metrics.roas if r.metrics else 0, reverse=True)
        
        return performing
    
    def get_creative_features(self, creative_id: str) -> Optional[Dict[str, float]]:
        record = self._records.get(creative_id)
        if record and record.features:
            return record.features
        
        if record and record.metrics:
            return {
                "mechanism_visibility": 0.7,
                "reward_salience": 0.7,
                "identity_projection": 0.7,
                "ctr": record.metrics.ctr,
                "ipm": record.metrics.ipm,
            }
        
        return None
    
    def get_layout_ast_for_ad(self, ad_id: str) -> Optional[str]:
        record = self.get_ad_creative(ad_id)
        if record:
            return record.layout_ast_id
        return None
    
    def get_template_performance_rankings(self) -> Dict[str, List[Tuple[str, float]]]:
        template_rankings = {}
        
        by_template = {}
        for record in self._records.values():
            if record.template_id and record.metrics:
                if record.template_id not in by_template:
                    by_template[record.template_id] = []
                by_template[record.template_id].append(
                    (record.creative_id, record.metrics.ctr)
                )
        
        for template_id, items in by_template.items():
            items.sort(key=lambda x: x[1], reverse=True)
            template_rankings[template_id] = items
        
        return template_rankings
    
    def get_top_creatives_by_template(self, template_id: str,
                                      top_n: int = 5) -> List[CreativeRecord]:
        records = [
            r for r in self._records.values()
            if r.template_id == template_id and r.metrics
        ]
        records.sort(key=lambda r: r.metrics.ctr, reverse=True)
        return records[:top_n]
    
    def get_worst_creatives_by_template(self, template_id: str,
                                       bottom_n: int = 5) -> List[CreativeRecord]:
        records = [
            r for r in self._records.values()
            if r.template_id == template_id and r.metrics
        ]
        records.sort(key=lambda r: r.metrics.ctr)
        return records[:bottom_n]
    
    def get_all_records(self) -> List[CreativeRecord]:
        return list(self._records.values())
    
    def get_records_by_template(self, template_id: str) -> List[CreativeRecord]:
        return [
            r for r in self._records.values()
            if r.template_id == template_id
        ]
    
    def get_mapping_summary(self) -> Dict[str, Any]:
        total = len(self._records)
        deployed = sum(1 for r in self._records.values() if r.status == "deployed")
        with_metrics = sum(
            1 for r in self._records.values()
            if r.metrics and r.metrics.impressions > 0
        )
        
        template_counts = {}
        for r in self._records.values():
            template_counts[r.template_id] = template_counts.get(r.template_id, 0) + 1
        
        return {
            "total_creatives": total,
            "deployed": deployed,
            "with_metrics": with_metrics,
            "by_template": template_counts,
        }
