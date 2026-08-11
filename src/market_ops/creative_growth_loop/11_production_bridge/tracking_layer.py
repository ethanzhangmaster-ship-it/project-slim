"""Tracking Layer + Identity Binding System

P2.5-3: Tracking Layer - 捕获真实用户行为数据
P2.5-4: Identity Binding System - 建立完整追溯链路

Identity Binding 结构：
creative_id → ad_id → impression_id → user_event

要求：
- 每个 impression 必须可回溯 creative
- 不允许"孤立 CTR 数据"
"""
from __future__ import annotations

import importlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

_PKG = "market_ops.creative_growth_loop"


@dataclass
class TrackingEvent:
    """追踪事件"""
    event_id: str
    creative_id: str
    ad_id: str
    campaign_id: str
    
    timestamp: int
    event_type: str
    
    impression_id: str = ""
    user_id: str = ""
    
    cost: float = 0.0
    country: str = ""
    placement: str = ""
    device: str = ""
    
    value: float = 0.0
    currency: str = "USD"
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "impression_id": self.impression_id,
            "user_id": self.user_id,
            "cost": self.cost,
            "country": self.country,
            "placement": self.placement,
            "device": self.device,
            "value": self.value,
            "currency": self.currency,
            "metadata": self.metadata,
        }


@dataclass
class IdentityBinding:
    """身份绑定记录 - 确保数据可追溯"""
    creative_id: str
    ad_id: str
    campaign_id: str = ""
    
    layout_ast_id: str = ""
    template_id: str = ""
    compiler_version: int = 0
    
    render_id: str = ""
    publish_id: str = ""
    
    bound_at: int = 0
    
    impression_ids: List[str] = field(default_factory=list)
    click_ids: List[str] = field(default_factory=list)
    install_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "layout_ast_id": self.layout_ast_id,
            "template_id": self.template_id,
            "compiler_version": self.compiler_version,
            "render_id": self.render_id,
            "publish_id": self.publish_id,
            "bound_at": self.bound_at,
            "impression_count": len(self.impression_ids),
            "click_count": len(self.click_ids),
            "install_count": len(self.install_ids),
        }


class TrackingLayer:
    """追踪层 - 收集真实用户行为数据
    
    数据来源：
    - Meta Ads API（离线拉取）
    - Pixel / SDK（前端上报）
    - Server-side event ingestion（服务端事件）
    """
    
    EVENT_TYPES = ["impression", "click", "install", "purchase", "conversion"]
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.events_file = self.output_dir / "tracking_events.jsonl"
        self.bindings_file = self.output_dir / "identity_bindings.json"
        
        self._events: List[TrackingEvent] = []
        self._bindings: Dict[str, IdentityBinding] = {}
        self._ad_to_creative: Dict[str, str] = {}
        
        self._load_events()
        self._load_bindings()
    
    def _load_events(self):
        if self.events_file.exists():
            with open(self.events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        self._events.append(TrackingEvent(**data))
    
    def _load_bindings(self):
        if self.bindings_file.exists():
            with open(self.bindings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for cid, binding_data in data.items():
                    self._bindings[cid] = IdentityBinding(**{
                        k: v for k, v in binding_data.items()
                        if k not in ["impression_count", "click_count", "install_count"]
                    })
                    if binding_data.get("ad_id"):
                        self._ad_to_creative[binding_data["ad_id"]] = cid
    
    def _save_events(self, event: TrackingEvent):
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_bindings(self):
        data = {cid: b.to_dict() for cid, b in self._bindings.items()}
        with open(self.bindings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def bind_identity(self, creative_id: str, ad_id: str, 
                      layout_ast_id: str = "", template_id: str = "",
                      compiler_version: int = 0, render_id: str = "",
                      publish_id: str = "", campaign_id: str = "") -> IdentityBinding:
        """建立身份绑定"""
        if creative_id in self._bindings:
            binding = self._bindings[creative_id]
            if ad_id and not binding.ad_id:
                binding.ad_id = ad_id
                self._ad_to_creative[ad_id] = creative_id
            if layout_ast_id and not binding.layout_ast_id:
                binding.layout_ast_id = layout_ast_id
            return binding
        
        binding = IdentityBinding(
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            layout_ast_id=layout_ast_id,
            template_id=template_id,
            compiler_version=compiler_version,
            render_id=render_id,
            publish_id=publish_id,
            bound_at=int(time.time()),
        )
        
        self._bindings[creative_id] = binding
        if ad_id:
            self._ad_to_creative[ad_id] = creative_id
        
        self._save_bindings()
        return binding
    
    def track_impression(self, creative_id: str, ad_id: str, campaign_id: str = "",
                          country: str = "", placement: str = "",
                          cost: float = 0.0) -> TrackingEvent:
        """追踪曝光"""
        event = self._create_event(
            event_type="impression",
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            country=country,
            placement=placement,
            cost=cost,
        )
        event.impression_id = f"imp_{uuid.uuid4().hex[:12]}"
        
        self._record_event(event)
        return event
    
    def track_click(self, creative_id: str, ad_id: str, campaign_id: str = "",
                     country: str = "", placement: str = "",
                     cost: float = 0.0, impression_id: str = "") -> TrackingEvent:
        """追踪点击"""
        event = self._create_event(
            event_type="click",
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            country=country,
            placement=placement,
            cost=cost,
        )
        event.impression_id = impression_id
        
        self._record_event(event)
        return event
    
    def track_install(self, creative_id: str, ad_id: str, campaign_id: str = "",
                       country: str = "", cost: float = 0.0,
                       value: float = 0.0) -> TrackingEvent:
        """追踪安装"""
        event = self._create_event(
            event_type="install",
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            country=country,
            cost=cost,
            value=value,
        )
        
        self._record_event(event)
        return event
    
    def track_purchase(self, creative_id: str, ad_id: str, campaign_id: str = "",
                        country: str = "", value: float = 0.0,
                        currency: str = "USD") -> TrackingEvent:
        """追踪购买"""
        event = self._create_event(
            event_type="purchase",
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            country=country,
            value=value,
        )
        event.currency = currency
        
        self._record_event(event)
        return event
    
    def _create_event(self, event_type: str, creative_id: str, ad_id: str,
                       campaign_id: str = "", **kwargs) -> TrackingEvent:
        return TrackingEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            creative_id=creative_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            timestamp=int(time.time()),
            event_type=event_type,
            **kwargs,
        )
    
    def _record_event(self, event: TrackingEvent):
        self._events.append(event)
        self._save_events(event)
        
        if event.creative_id in self._bindings:
            binding = self._bindings[event.creative_id]
            if event.event_type == "impression":
                binding.impression_ids.append(event.event_id)
            elif event.event_type == "click":
                binding.click_ids.append(event.event_id)
            elif event.event_type == "install":
                binding.install_ids.append(event.event_id)
    
    def get_creative_by_ad(self, ad_id: str) -> Optional[str]:
        """通过 ad_id 找到 creative_id"""
        return self._ad_to_creative.get(ad_id)
    
    def get_binding(self, creative_id: str) -> Optional[IdentityBinding]:
        return self._bindings.get(creative_id)
    
    def get_events_by_creative(self, creative_id: str) -> List[TrackingEvent]:
        return [e for e in self._events if e.creative_id == creative_id]
    
    def get_events_by_date_range(self, start_ts: int, end_ts: int) -> List[TrackingEvent]:
        return [e for e in self._events if start_ts <= e.timestamp <= end_ts]
    
    def ingest_meta_insights(self, insights_data: List[Dict[str, Any]]) -> int:
        """从 Meta Ads Insights 导入数据"""
        count = 0
        
        for insight in insights_data:
            ad_id = insight.get("ad_id", "")
            creative_id = self.get_creative_by_ad(ad_id)
            
            if not creative_id:
                continue
            
            impressions = int(insight.get("impressions", 0))
            clicks = int(insight.get("clicks", 0))
            installs = int(insight.get("mobile_app_installs", 
                                       insight.get("actions", [{}])[0].get("value", 0) 
                                       if insight.get("actions") else 0))
            spend = float(insight.get("spend", 0))
            date_start = insight.get("date_start", "")
            
            country = insight.get("country", "")
            
            per_impression_cost = spend / impressions if impressions > 0 else 0
            
            for i in range(min(impressions, 100)):
                self.track_impression(
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=insight.get("campaign_id", ""),
                    country=country,
                    cost=per_impression_cost,
                )
            
            for i in range(min(clicks, 50)):
                self.track_click(
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=insight.get("campaign_id", ""),
                    country=country,
                )
            
            for i in range(min(installs, 10)):
                self.track_install(
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=insight.get("campaign_id", ""),
                    country=country,
                )
            
            count += impressions + clicks + installs
        
        return count
    
    def get_tracking_summary(self) -> Dict[str, Any]:
        """获取追踪数据汇总"""
        event_counts = {}
        for event in self._events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        creative_ids = set(e.creative_id for e in self._events)
        ad_ids = set(e.ad_id for e in self._events)
        
        countries = set(e.country for e in self._events if e.country)
        
        total_cost = sum(e.cost for e in self._events)
        total_value = sum(e.value for e in self._events)
        
        return {
            "total_events": len(self._events),
            "event_counts": event_counts,
            "unique_creatives": len(creative_ids),
            "unique_ads": len(ad_ids),
            "unique_countries": len(countries),
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "bindings_count": len(self._bindings),
        }
