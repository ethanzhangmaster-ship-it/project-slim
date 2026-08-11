"""L3 - Traffic & Tracking Layer — 流量与追踪层

真实数据回收能力：
- Pixel Tracking：impression / click / view_content / install / purchase
- App Events SDK：install / session / purchase / retention
- Server-side Tracking (CAPI)：Meta Conversion API / TikTok Events API

输出标准：
{
  "event": "click",
  "ad_id": "...",
  "creative_id": "...",
  "timestamp": 123456
}
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum
from collections import defaultdict


class EventType(Enum):
    IMPRESSION = "impression"
    CLICK = "click"
    VIEW_CONTENT = "view_content"
    INSTALL = "install"
    PURCHASE = "purchase"
    SESSION = "session"
    RETENTION = "retention"
    ADD_TO_CART = "add_to_cart"
    LEAD = "lead"
    COMPLETE_REGISTRATION = "complete_registration"


class EventSource(Enum):
    PIXEL = "pixel"
    SDK = "sdk"
    CAPI = "capi"  # Server-side / Conversion API
    WEBHOOK = "webhook"


@dataclass
class TrackingEvent:
    """追踪事件标准"""
    event_id: str
    event_type: EventType
    event_source: EventSource
    
    ad_id: str
    creative_id: str
    campaign_id: str = ""
    adset_id: str = ""
    
    user_id: str = ""
    device_id: str = ""
    ip_address: str = ""
    
    timestamp: int = 0
    
    revenue: float = 0.0
    value: float = 0.0
    currency: str = "USD"
    
    country: str = ""
    platform: str = ""
    
    attribution_token: str = ""
    
    custom_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "event_source": self.event_source.value,
            "ad_id": self.ad_id,
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "revenue": self.revenue,
            "value": self.value,
            "currency": self.currency,
            "country": self.country,
            "platform": self.platform,
            "custom_params": self.custom_params,
        }
    
    def to_pixel_payload(self) -> Dict[str, Any]:
        """转换为 Pixel API Payload"""
        return {
            "event_name": self.event_type.value,
            "event_time": self.timestamp,
            "user_data": {
                "client_ip_address": self.ip_address,
                "client_user_agent": self.custom_params.get("user_agent", ""),
            },
            "custom_data": {
                "ad_id": self.ad_id,
                "creative_id": self.creative_id,
                "campaign_id": self.campaign_id,
                "value": self.value,
                "currency": self.currency,
            },
            "event_id": self.event_id,
        }
    
    def to_capi_payload(self) -> Dict[str, Any]:
        """转换为 Conversion API Payload"""
        return {
            "event_name": self.event_type.value,
            "event_time": self.timestamp,
            "user_data": {
                "em": self._hash_field(self.user_id),
                "client_ip_address": self.ip_address,
            },
            "custom_data": {
                "ad_id": self.ad_id,
                "creative_id": self.creative_id,
                "value": self.value,
                "currency": self.currency,
            },
            "action_source": "website",
            "event_id": self.event_id,
        }
    
    def _hash_field(self, value: str) -> str:
        """SHA256 Hash"""
        return hashlib.sha256(value.lower().encode()).hexdigest()


class PixelTracker:
    """Pixel Tracker — 浏览器端追踪
    
    事件类型：
    - impression
    - click
    - view_content
    - install
    - purchase
    """
    
    def __init__(self, pixel_id: str = "",
                 output_dir: str = "memory/tracking"):
        self.pixel_id = pixel_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._events: List[TrackingEvent] = []
        self._events_by_ad: Dict[str, List[TrackingEvent]] = defaultdict(list)
    
    def track(self,
              event_type: EventType,
              ad_id: str,
              creative_id: str,
              user_id: str = "",
              campaign_id: str = "",
              adset_id: str = "",
              revenue: float = 0.0,
              value: float = 0.0,
              country: str = "",
              custom_params: Dict[str, Any] = None) -> TrackingEvent:
        """追踪事件"""
        event = TrackingEvent(
            event_id=f"px_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            event_source=EventSource.PIXEL,
            ad_id=ad_id,
            creative_id=creative_id,
            campaign_id=campaign_id,
            adset_id=adset_id,
            user_id=user_id,
            timestamp=int(time.time()),
            revenue=revenue,
            value=value,
            country=country,
            custom_params=custom_params or {},
        )
        
        self._events.append(event)
        self._events_by_ad[ad_id].append(event)
        
        return event
    
    def track_impression(self, ad_id: str, creative_id: str,
                          user_id: str = "", country: str = "") -> TrackingEvent:
        """追踪展示"""
        return self.track(
            event_type=EventType.IMPRESSION,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            country=country,
        )
    
    def track_click(self, ad_id: str, creative_id: str,
                    user_id: str = "", country: str = "") -> TrackingEvent:
        """追踪点击"""
        return self.track(
            event_type=EventType.CLICK,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            country=country,
        )
    
    def track_install(self, ad_id: str, creative_id: str,
                       user_id: str = "", country: str = "") -> TrackingEvent:
        """追踪安装"""
        return self.track(
            event_type=EventType.INSTALL,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            country=country,
        )
    
    def track_purchase(self, ad_id: str, creative_id: str,
                        user_id: str = "", revenue: float = 0.0,
                        country: str = "") -> TrackingEvent:
        """追踪购买"""
        return self.track(
            event_type=EventType.PURCHASE,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            revenue=revenue,
            value=revenue,
            country=country,
        )
    
    def get_events(self) -> List[TrackingEvent]:
        return self._events
    
    def get_events_for_ad(self, ad_id: str) -> List[TrackingEvent]:
        return self._events_by_ad.get(ad_id, [])
    
    def get_events_for_creative(self, creative_id: str) -> List[TrackingEvent]:
        return [e for e in self._events if e.creative_id == creative_id]


class AppEventsSDK:
    """App Events SDK — App 内事件追踪
    
    事件类型：
    - install
    - session
    - purchase
    - retention
    """
    
    def __init__(self, app_id: str = "",
                 output_dir: str = "memory/tracking"):
        self.app_id = app_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._events: List[TrackingEvent] = []
        self._user_sessions: Dict[str, List[TrackingEvent]] = defaultdict(list)
    
    def track(self,
              event_type: EventType,
              ad_id: str,
              creative_id: str,
              user_id: str,
              revenue: float = 0.0,
              session_duration: float = 0.0) -> TrackingEvent:
        """追踪 App 事件"""
        event = TrackingEvent(
            event_id=f"sdk_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            event_source=EventSource.SDK,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            timestamp=int(time.time()),
            revenue=revenue,
            value=revenue,
            platform="app",
            custom_params={"session_duration": session_duration},
        )
        
        self._events.append(event)
        self._user_sessions[user_id].append(event)
        
        return event
    
    def track_install(self, ad_id: str, creative_id: str,
                       user_id: str) -> TrackingEvent:
        """追踪 App 安装"""
        return self.track(
            event_type=EventType.INSTALL,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
        )
    
    def track_session(self, ad_id: str, creative_id: str,
                       user_id: str, duration: float) -> TrackingEvent:
        """追踪 App 会话"""
        return self.track(
            event_type=EventType.SESSION,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            session_duration=duration,
        )
    
    def track_purchase(self, ad_id: str, creative_id: str,
                        user_id: str, revenue: float) -> TrackingEvent:
        """追踪 App 内购买"""
        return self.track(
            event_type=EventType.PURCHASE,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            revenue=revenue,
        )
    
    def track_retention(self, ad_id: str, creative_id: str,
                         user_id: str, day: int) -> TrackingEvent:
        """追踪留存"""
        return self.track(
            event_type=EventType.RETENTION,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            custom_params={"retention_day": day},
        )
    
    def get_events(self) -> List[TrackingEvent]:
        return self._events
    
    def get_user_sessions(self, user_id: str) -> List[TrackingEvent]:
        return self._user_sessions.get(user_id, [])


class ConversionAPIClient:
    """Server-side Tracking (CAPI) — 转化 API
    
    支持：
    - Meta Conversion API
    - TikTok Events API
    """
    
    def __init__(self, platform: str = "meta",
                 access_token: str = "",
                 pixel_id: str = "",
                 mode: str = "mock",
                 output_dir: str = "memory/tracking"):
        self.platform = platform
        self.access_token = access_token
        self.pixel_id = pixel_id
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._sent_events: List[Dict[str, Any]] = []
        self._failed_events: List[Dict[str, Any]] = []
    
    def send_event(self, event: TrackingEvent) -> bool:
        """发送事件到 Conversion API"""
        payload = event.to_capi_payload()
        payload["pixel_id"] = self.pixel_id
        
        if self.mode == "live" and self.access_token:
            success = self._live_send(payload)
        else:
            success = self._mock_send(payload)
        
        if success:
            self._sent_events.append({
                "event_id": event.event_id,
                "payload": payload,
                "timestamp": int(time.time()),
            })
        else:
            self._failed_events.append({
                "event_id": event.event_id,
                "payload": payload,
                "timestamp": int(time.time()),
            })
        
        return success
    
    def _mock_send(self, payload: Dict[str, Any]) -> bool:
        """Mock 发送"""
        return True
    
    def _live_send(self, payload: Dict[str, Any]) -> bool:
        """真实发送（预留）"""
        return self._mock_send(payload)
    
    def send_batch(self, events: List[TrackingEvent]) -> Dict[str, int]:
        """批量发送"""
        sent = 0
        failed = 0
        
        for event in events:
            if self.send_event(event):
                sent += 1
            else:
                failed += 1
        
        return {"sent": sent, "failed": failed}
    
    def get_sent_events(self) -> List[Dict[str, Any]]:
        return self._sent_events
    
    def get_failed_events(self) -> List[Dict[str, Any]]:
        return self._failed_events


class EventStreamCollector:
    """事件流收集器 — L3 层主入口
    
    统一收集：
    - Pixel Events
    - SDK Events
    - CAPI Events
    """
    
    def __init__(self, pixel_id: str = "",
                 app_id: str = "",
                 mode: str = "mock",
                 output_dir: str = "memory/tracking"):
        self.mode = mode
        self.output_dir = output_dir
        
        self.pixel_tracker = PixelTracker(pixel_id=pixel_id, output_dir=output_dir)
        self.sdk_tracker = AppEventsSDK(app_id=app_id, output_dir=output_dir)
        self.capi_client = ConversionAPIClient(
            platform="meta",
            mode=mode,
            pixel_id=pixel_id,
            output_dir=output_dir,
        )
        
        self._all_events: List[TrackingEvent] = []
    
    def collect_pixel_event(self,
                            event_type: EventType,
                            ad_id: str,
                            creative_id: str,
                            **kwargs) -> TrackingEvent:
        """收集 Pixel 事件"""
        event = self.pixel_tracker.track(
            event_type=event_type,
            ad_id=ad_id,
            creative_id=creative_id,
            **kwargs,
        )
        self._all_events.append(event)
        
        if self.mode == "live":
            self.capi_client.send_event(event)
        
        return event
    
    def collect_sdk_event(self,
                          event_type: EventType,
                          ad_id: str,
                          creative_id: str,
                          user_id: str,
                          **kwargs) -> TrackingEvent:
        """收集 SDK 事件"""
        event = self.sdk_tracker.track(
            event_type=event_type,
            ad_id=ad_id,
            creative_id=creative_id,
            user_id=user_id,
            **kwargs,
        )
        self._all_events.append(event)
        
        return event
    
    def stream_events(self,
                      ad_id: str,
                      creative_id: str,
                      event_sequence: List[Dict[str, Any]]) -> List[TrackingEvent]:
        """流式收集事件序列
        
        用于模拟真实用户行为流：
        impression → click → install → purchase
        """
        events = []
        
        for event_data in event_sequence:
            event_type = EventType(event_data.get("event_type", "impression"))
            user_id = event_data.get("user_id", f"user_{uuid.uuid4().hex[:6]}")
            revenue = event_data.get("revenue", 0.0)
            delay = event_data.get("delay", 0)
            
            if delay > 0:
                time.sleep(delay)
            
            event = self.collect_pixel_event(
                event_type=event_type,
                ad_id=ad_id,
                creative_id=creative_id,
                user_id=user_id,
                revenue=revenue,
            )
            events.append(event)
        
        return events
    
    def get_all_events(self) -> List[TrackingEvent]:
        return self._all_events
    
    def get_events_by_type(self, event_type: EventType) -> List[TrackingEvent]:
        return [e for e in self._all_events if e.event_type == event_type]
    
    def get_events_for_creative(self, creative_id: str) -> List[TrackingEvent]:
        return [e for e in self._all_events if e.creative_id == creative_id]
    
    def get_event_summary(self) -> Dict[str, int]:
        """事件汇总"""
        summary = defaultdict(int)
        for event in self._all_events:
            summary[event.event_type.value] += 1
        return dict(summary)
    
    def to_attribution_input(self) -> List[Dict[str, Any]]:
        """转换为 Attribution Engine 输入"""
        return [e.to_dict() for e in self._all_events]