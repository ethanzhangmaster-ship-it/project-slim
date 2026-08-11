"""Event Tracking System - 事件收集与指标计算

P2-1: 建立事件追踪基础设施，收集广告创意表现数据。

Event Schema:
{
  "creative_id": "string",
  "ad_id": "string",
  "campaign_id": "string",
  "timestamp": "int",
  "event_type": "impression | click | install | purchase",
  "cost": "float",
  "country": "string"
}

支持的指标:
- CTR = click / impression
- IPM = installs per 1000 impressions
- CPA / ROAS（如果可用）
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


EVENT_TYPES = ["impression", "click", "install", "purchase"]


@dataclass
class CreativeEvent:
    creative_id: str
    ad_id: str
    campaign_id: str
    timestamp: int
    event_type: str
    cost: float = 0.0
    country: str = ""
    template_id: str = ""
    layout_ast_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "cost": self.cost,
            "country": self.country,
            "template_id": self.template_id,
            "layout_ast_id": self.layout_ast_id,
        }


@dataclass
class PerformanceMetrics:
    creative_id: str
    template_id: str = ""
    layout_ast_id: str = ""
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    total_cost: float = 0.0
    
    ctr: float = 0.0
    ipm: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0
    
    sample_size: int = 0
    
    computed_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "template_id": self.template_id,
            "layout_ast_id": self.layout_ast_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "total_cost": self.total_cost,
            "ctr": round(self.ctr, 4),
            "ipm": round(self.ipm, 3),
            "cpa": round(self.cpa, 2) if self.cpa > 0 else 0.0,
            "roas": round(self.roas, 2) if self.roas > 0 else 0.0,
            "sample_size": self.sample_size,
            "computed_at": self.computed_at,
        }


@dataclass
class AggregatedMetrics:
    template_id: str
    
    total_impressions: int = 0
    total_clicks: int = 0
    total_installs: int = 0
    total_cost: float = 0.0
    
    avg_ctr: float = 0.0
    avg_ipm: float = 0.0
    winning_count: int = 0
    sample_count: int = 0
    
    performance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "total_impressions": self.total_impressions,
            "total_clicks": self.total_clicks,
            "total_installs": self.total_installs,
            "total_cost": self.total_cost,
            "avg_ctr": round(self.avg_ctr, 4),
            "avg_ipm": round(self.avg_ipm, 3),
            "winning_count": self.winning_count,
            "sample_count": self.sample_count,
            "performance_score": round(self.performance_score, 3),
        }


class EventTracker:
    """事件追踪器 - 收集和管理广告创意事件"""
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.events_file = self.output_dir / "events.jsonl"
        self.metrics_file = self.output_dir / "metrics.json"
        self.compiler_config_file = self.output_dir / "compiler_config.json"
        
        self._events_cache: List[CreativeEvent] = []
        self._load_events()
    
    def _load_events(self):
        if self.events_file.exists():
            with open(self.events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        event = CreativeEvent(**data)
                        self._events_cache.append(event)
    
    def track_event(self, creative_id: str, ad_id: str, campaign_id: str,
                   event_type: str, cost: float = 0.0,
                   country: str = "", template_id: str = "",
                   layout_ast_id: str = "") -> CreativeEvent:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {event_type}")
        
        event = CreativeEvent(
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            timestamp=int(time.time()),
            event_type=event_type,
            cost=cost,
            country=country,
            template_id=template_id,
            layout_ast_id=layout_ast_id,
        )
        
        self._events_cache.append(event)
        
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        
        return event
    
    def track_impression(self, creative_id: str, ad_id: str, campaign_id: str,
                        country: str = "", **kwargs) -> CreativeEvent:
        return self.track_event(creative_id, ad_id, campaign_id, "impression",
                               country=country, **kwargs)
    
    def track_click(self, creative_id: str, ad_id: str, campaign_id: str,
                   cost: float = 0.0, country: str = "", **kwargs) -> CreativeEvent:
        return self.track_event(creative_id, ad_id, campaign_id, "click",
                               cost=cost, country=country, **kwargs)
    
    def track_install(self, creative_id: str, ad_id: str, campaign_id: str,
                      cost: float = 0.0, country: str = "", **kwargs) -> CreativeEvent:
        return self.track_event(creative_id, ad_id, campaign_id, "install",
                               cost=cost, country=country, **kwargs)
    
    def get_creative_metrics(self, creative_id: str) -> PerformanceMetrics:
        events = [e for e in self._events_cache if e.creative_id == creative_id]
        
        if not events:
            return PerformanceMetrics(creative_id=creative_id)
        
        impressions = sum(1 for e in events if e.event_type == "impression")
        clicks = sum(1 for e in events if e.event_type == "click")
        installs = sum(1 for e in events if e.event_type == "install")
        purchases = sum(1 for e in events if e.event_type == "purchase")
        total_cost = sum(e.cost for e in events)
        
        ctr = clicks / impressions if impressions > 0 else 0.0
        ipm = (installs / impressions * 1000) if impressions > 0 else 0.0
        cpa = total_cost / installs if installs > 0 else 0.0
        
        revenue = purchases * 1.0
        roas = revenue / total_cost if total_cost > 0 else 0.0
        
        template_id = events[0].template_id if events else ""
        layout_ast_id = events[0].layout_ast_id if events else ""
        
        return PerformanceMetrics(
            creative_id=creative_id,
            template_id=template_id,
            layout_ast_id=layout_ast_id,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            purchases=purchases,
            total_cost=total_cost,
            ctr=ctr,
            ipm=ipm,
            cpa=cpa,
            roas=roas,
            sample_size=impressions,
            computed_at=int(time.time()),
        )
    
    def get_template_aggregated_metrics(self, template_id: str) -> AggregatedMetrics:
        events = [e for e in self._events_cache if e.template_id == template_id]
        
        creative_ids = set(e.creative_id for e in events)
        
        total_impressions = sum(1 for e in events if e.event_type == "impression")
        total_clicks = sum(1 for e in events if e.event_type == "click")
        total_installs = sum(1 for e in events if e.event_type == "install")
        total_cost = sum(e.cost for e in events)
        
        ctr_list = []
        ipm_list = []
        
        for cid in creative_ids:
            metrics = self.get_creative_metrics(cid)
            if metrics.impressions > 0:
                ctr_list.append(metrics.ctr)
                ipm_list.append(metrics.ipm)
        
        avg_ctr = sum(ctr_list) / len(ctr_list) if ctr_list else 0.0
        avg_ipm = sum(ipm_list) / len(ipm_list) if ipm_list else 0.0
        
        return AggregatedMetrics(
            template_id=template_id,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_installs=total_installs,
            total_cost=total_cost,
            avg_ctr=avg_ctr,
            avg_ipm=avg_ipm,
            sample_count=len(creative_ids),
        )
    
    def get_all_creatives_metrics(self) -> List[PerformanceMetrics]:
        creative_ids = set(e.creative_id for e in self._events_cache)
        return [self.get_creative_metrics(cid) for cid in creative_ids]
    
    def get_events_by_date_range(self, start_ts: int, end_ts: int) -> List[CreativeEvent]:
        return [e for e in self._events_cache
                if start_ts <= e.timestamp <= end_ts]
    
    def get_recent_events(self, days: int = 7) -> List[CreativeEvent]:
        cutoff = int(time.time()) - (days * 86400)
        return [e for e in self._events_cache if e.timestamp >= cutoff]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        all_metrics = self.get_all_creatives_metrics()
        template_metrics = {}
        
        for m in all_metrics:
            if m.template_id:
                if m.template_id not in template_metrics:
                    template_metrics[m.template_id] = {
                        "count": 0,
                        "total_impressions": 0,
                        "total_clicks": 0,
                        "total_installs": 0,
                        "ctr_list": [],
                        "ipm_list": [],
                    }
                
                tm = template_metrics[m.template_id]
                tm["count"] += 1
                tm["total_impressions"] += m.impressions
                tm["total_clicks"] += m.clicks
                tm["total_installs"] += m.installs
                if m.impressions > 0:
                    tm["ctr_list"].append(m.ctr)
                    tm["ipm_list"].append(m.ipm)
        
        summary = {
            "total_creatives": len(all_metrics),
            "total_events": len(self._events_cache),
            "total_impressions": sum(m.impressions for m in all_metrics),
            "total_clicks": sum(m.clicks for m in all_metrics),
            "total_installs": sum(m.installs for m in all_metrics),
            "templates": {},
        }
        
        for tid, tm in template_metrics.items():
            avg_ctr = sum(tm["ctr_list"]) / len(tm["ctr_list"]) if tm["ctr_list"] else 0.0
            avg_ipm = sum(tm["ipm_list"]) / len(tm["ipm_list"]) if tm["ipm_list"] else 0.0
            
            summary["templates"][tid] = {
                "count": tm["count"],
                "total_impressions": tm["total_impressions"],
                "total_clicks": tm["total_clicks"],
                "total_installs": tm["total_installs"],
                "avg_ctr": round(avg_ctr, 4),
                "avg_ipm": round(avg_ipm, 3),
            }
        
        return summary
    
    def save_metrics(self):
        summary = self.get_performance_summary()
        
        with open(self.metrics_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary
