"""Attribution Engine - 归因引擎

归因规则：
- 1-day click attribution
- 7-day view attribution  
- last-touch model (MVP)

输出：
- creative_id / ad_id 级别的归因结果
- impressions / clicks / installs / revenue
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


CLICK_ATTRIBUTION_WINDOW_SEC = 24 * 60 * 60  # 1-day
VIEW_ATTRIBUTION_WINDOW_SEC = 7 * 24 * 60 * 60  # 7-day


@dataclass
class AttributionEvent:
    """归因事件"""
    event_id: str
    event_type: str  # impression / click / install / purchase
    user_id: str
    ad_id: str
    creative_id: str
    timestamp: int
    revenue: float = 0.0
    cost: float = 0.0
    country: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "ad_id": self.ad_id,
            "creative_id": self.creative_id,
            "timestamp": self.timestamp,
            "revenue": self.revenue,
            "cost": self.cost,
            "country": self.country,
        }


@dataclass
class AttributionResult:
    """归因结果"""
    creative_id: str
    ad_id: str
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    
    click_attributed_installs: int = 0
    view_attributed_installs: int = 0
    
    total_revenue: float = 0.0
    total_cost: float = 0.0
    
    ctr: float = 0.0
    cvr: float = 0.0
    ipm: float = 0.0
    roas: float = 0.0
    cpc: float = 0.0
    
    attribution_method: str = "last_touch"
    
    def compute_derived(self):
        """计算衍生指标"""
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
            self.ipm = (self.installs / self.impressions) * 1000
        
        if self.clicks > 0:
            self.cvr = self.installs / self.clicks
            self.cpc = self.total_cost / self.clicks
        
        if self.total_cost > 0:
            self.roas = self.total_revenue / self.total_cost
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "click_attributed_installs": self.click_attributed_installs,
            "view_attributed_installs": self.view_attributed_installs,
            "total_revenue": round(self.total_revenue, 4),
            "total_cost": round(self.total_cost, 4),
            "ctr": round(self.ctr, 6),
            "cvr": round(self.cvr, 6),
            "ipm": round(self.ipm, 4),
            "roas": round(self.roas, 4),
            "cpc": round(self.cpc, 4),
            "attribution_method": self.attribution_method,
        }


class AttributionEngine:
    """归因引擎 - Last-Touch MVP
    
    归因规则：
    - Click attribution: 1-day window
    - View attribution: 7-day window
    - Last-touch model: 最后一次交互归因
    """
    
    def __init__(self, output_dir: str = "memory/attribution"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._events: List[AttributionEvent] = []
        self._results: Dict[str, AttributionResult] = {}
    
    def add_event(self, event_type: str, user_id: str, ad_id: str,
                  creative_id: str, timestamp: int = 0,
                  revenue: float = 0.0, cost: float = 0.0,
                  country: str = "") -> AttributionEvent:
        """添加归因事件"""
        if timestamp == 0:
            timestamp = int(time.time())
        
        event = AttributionEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            user_id=user_id,
            ad_id=ad_id,
            creative_id=creative_id,
            timestamp=timestamp,
            revenue=revenue,
            cost=cost,
            country=country,
        )
        
        self._events.append(event)
        return event
    
    def add_events_batch(self, events: List[Dict[str, Any]]):
        """批量添加事件"""
        for e in events:
            self.add_event(
                event_type=e.get("event_type", ""),
                user_id=e.get("user_id", "unknown"),
                ad_id=e.get("ad_id", ""),
                creative_id=e.get("creative_id", ""),
                timestamp=e.get("timestamp", 0),
                revenue=e.get("revenue", 0.0),
                cost=e.get("cost", 0.0),
                country=e.get("country", ""),
            )
    
    def run_attribution(self) -> Dict[str, AttributionResult]:
        """运行归因（Last-Touch MVP）"""
        self._results = {}
        
        user_events: Dict[str, List[AttributionEvent]] = {}
        for event in self._events:
            if event.user_id not in user_events:
                user_events[event.user_id] = []
            user_events[event.user_id].append(event)
        
        for user_id in user_events:
            user_events[user_id].sort(key=lambda e: e.timestamp)
        
        for user_id, events in user_events.items():
            self._attribute_user(user_id, events)
        
        for result in self._results.values():
            result.compute_derived()
        
        return self._results
    
    def _attribute_user(self, user_id: str, events: List[AttributionEvent]):
        """对单个用户进行归因"""
        last_click = None
        last_view = None
        
        for event in events:
            key = event.creative_id
            
            if key not in self._results:
                self._results[key] = AttributionResult(
                    creative_id=event.creative_id,
                    ad_id=event.ad_id,
                )
            
            result = self._results[key]
            
            if event.event_type == "impression":
                result.impressions += 1
                result.total_cost += event.cost
                last_view = event
            
            elif event.event_type == "click":
                result.clicks += 1
                result.total_cost += event.cost
                last_click = event
            
            elif event.event_type == "install":
                attributed = self._attribute_conversion(event, last_click, last_view)
                if attributed:
                    result.installs += 1
                    if attributed == "click":
                        result.click_attributed_installs += 1
                    elif attributed == "view":
                        result.view_attributed_installs += 1
            
            elif event.event_type == "purchase":
                attributed = self._attribute_conversion(event, last_click, last_view)
                if attributed:
                    result.purchases += 1
                    result.total_revenue += event.revenue
    
    def _attribute_conversion(self, conversion_event: AttributionEvent,
                               last_click: Optional[AttributionEvent],
                               last_view: Optional[AttributionEvent]) -> Optional[str]:
        """对单个转化进行归因（Last-Touch）
        
        Returns:
            "click" | "view" | None
        """
        conv_time = conversion_event.timestamp
        
        if last_click and (conv_time - last_click.timestamp) <= CLICK_ATTRIBUTION_WINDOW_SEC:
            return "click"
        
        if last_view and (conv_time - last_view.timestamp) <= VIEW_ATTRIBUTION_WINDOW_SEC:
            return "view"
        
        return None
    
    def get_result(self, creative_id: str) -> Optional[AttributionResult]:
        return self._results.get(creative_id)
    
    def get_all_results(self) -> Dict[str, AttributionResult]:
        return self._results
