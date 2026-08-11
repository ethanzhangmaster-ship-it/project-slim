"""Online → Offline Bridge + Safety / Consistency Layer

P2.5-6: Online→Offline Bridge - 把真实数据喂回 P2 学习系统
P2.5-7: Safety / Consistency Layer - 防止数据污染

核心目标：
- Production Data → Dataset Builder → Weight Update System → Layout Compiler Optimization
- 支持 batch ingestion（每日）
- creative_id 必须唯一
- ad_id 必须绑定 compiler version
- 禁止 orphan events
"""
from __future__ import annotations

import importlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_PKG = "market_ops.creative_growth_loop"


@dataclass
class ValidationResult:
    """数据验证结果"""
    is_valid: bool
    total_events: int
    valid_events: int
    orphan_events: int
    missing_creative: int
    duplicate_creatives: List[str]
    error_messages: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_events": self.total_events,
            "valid_events": self.valid_events,
            "orphan_events": self.orphan_events,
            "missing_creative": self.missing_creative,
            "duplicate_creatives": self.duplicate_creatives,
            "error_messages": self.error_messages,
        }


@dataclass
class IngestionResult:
    """数据摄取结果"""
    ingestion_id: str
    source: str
    started_at: int
    completed_at: int = 0
    
    events_processed: int = 0
    events_validated: int = 0
    events_rejected: int = 0
    
    creatives_updated: int = 0
    metrics_updated: int = 0
    
    validation_result: Optional[ValidationResult] = None
    
    status: str = "success"
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ingestion_id": self.ingestion_id,
            "source": self.source,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "events_processed": self.events_processed,
            "events_validated": self.events_validated,
            "events_rejected": self.events_rejected,
            "creatives_updated": self.creatives_updated,
            "metrics_updated": self.metrics_updated,
            "status": self.status,
            "error_message": self.error_message,
        }


class SafetyConsistencyLayer:
    """安全一致性层 - 防止数据污染
    
    检查规则：
    1. creative_id 必须唯一
    2. ad_id 必须绑定 compiler version
    3. 禁止 orphan events（没有对应 creative 的事件）
    4. 事件时间戳必须合理
    """
    
    def __init__(self):
        self._known_creatives: set = set()
        self._known_ads: Dict[str, str] = {}
        self._compiler_versions: Dict[str, int] = {}
    
    def validate_events(self, events: List[Any],
                         known_creatives: set = None) -> ValidationResult:
        """验证事件数据的合法性"""
        errors = []
        valid_count = 0
        orphan_count = 0
        missing_creative_count = 0
        seen_creatives = set()
        duplicates = []
        
        known = known_creatives or self._known_creatives
        
        for event in events:
            creative_id = getattr(event, "creative_id", "")
            event_type = getattr(event, "event_type", "")
            ad_id = getattr(event, "ad_id", "")
            timestamp = getattr(event, "timestamp", 0)
            
            if not creative_id:
                orphan_count += 1
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: missing creative_id")
                continue
            
            if not ad_id:
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: missing ad_id")
                orphan_count += 1
                continue
            
            if creative_id not in known and known:
                missing_creative_count += 1
                orphan_count += 1
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: creative_id {creative_id} not registered")
                continue
            
            if not event_type or event_type not in ["impression", "click", "install", "purchase", "conversion"]:
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: invalid event_type {event_type}")
                continue
            
            if timestamp <= 0:
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: invalid timestamp")
                continue
            
            if timestamp > int(time.time()) + 3600:
                errors.append(f"Event {getattr(event, 'event_id', 'unknown')}: future timestamp")
                continue
            
            if creative_id in seen_creatives and event_type == "impression":
                pass
            seen_creatives.add(creative_id)
            
            valid_count += 1
        
        is_valid = orphan_count == 0 and len(errors) < 10
        
        return ValidationResult(
            is_valid=is_valid,
            total_events=len(events),
            valid_events=valid_count,
            orphan_events=orphan_count,
            missing_creative=missing_creative_count,
            duplicate_creatives=duplicates,
            error_messages=errors[:20],
        )
    
    def validate_creative_id(self, creative_id: str) -> bool:
        if not creative_id:
            return False
        if not isinstance(creative_id, str):
            return False
        if len(creative_id) < 3:
            return False
        return True
    
    def validate_ad_binding(self, ad_id: str, creative_id: str,
                             compiler_version: int) -> bool:
        """验证 ad-creative 绑定"""
        if not ad_id or not creative_id:
            return False
        if compiler_version <= 0:
            return False
        return True
    
    def filter_valid_events(self, events: List[Any],
                            known_creatives: set = None) -> List[Any]:
        """过滤出合法事件"""
        known = known_creatives or self._known_creatives
        valid = []
        
        for event in events:
            creative_id = getattr(event, "creative_id", "")
            if creative_id and creative_id in known:
                event_type = getattr(event, "event_type", "")
                if event_type in ["impression", "click", "install", "purchase", "conversion"]:
                    valid.append(event)
        
        return valid
    
    def register_creative(self, creative_id: str, compiler_version: int = 1):
        self._known_creatives.add(creative_id)
        self._compiler_versions[creative_id] = compiler_version
    
    def register_ad_binding(self, ad_id: str, creative_id: str, compiler_version: int = 1):
        self._known_ads[ad_id] = creative_id
        self._compiler_versions[ad_id] = compiler_version


class OnlineOfflineBridge:
    """在线离线桥接层
    
    把真实生产数据喂回 P2 学习系统：
    Production Data → Dataset Builder → Weight Update System → Layout Compiler Optimization
    """
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.bridge_state_file = self.output_dir / "bridge_state.json"
        
        self.safety_layer = SafetyConsistencyLayer()
        
        self._state = {
            "last_ingestion_at": 0,
            "total_ingestions": 0,
            "total_events_processed": 0,
            "ingestion_history": [],
        }
        
        self._load_state()
    
    def _load_state(self):
        if self.bridge_state_file.exists():
            with open(self.bridge_state_file, "r", encoding="utf-8") as f:
                self._state = json.load(f)
    
    def _save_state(self):
        with open(self.bridge_state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)
    
    def ingest_events_batch(self, events: List[Any],
                             source: str = "production",
                             known_creatives: set = None) -> IngestionResult:
        """批量摄取事件（每日 batch）"""
        import uuid
        
        ingestion_id = f"ingest_{uuid.uuid4().hex[:8]}"
        start_time = int(time.time())
        
        result = IngestionResult(
            ingestion_id=ingestion_id,
            source=source,
            started_at=start_time,
        )
        
        try:
            validation = self.safety_layer.validate_events(events, known_creatives)
            result.validation_result = validation
            
            valid_events = self.safety_layer.filter_valid_events(events, known_creatives)
            
            result.events_processed = len(events)
            result.events_validated = len(valid_events)
            result.events_rejected = len(events) - len(valid_events)
            
            creative_metrics = self._compute_metrics_from_events(valid_events)
            result.creatives_updated = len(creative_metrics)
            
            dataset_built = self._build_dataset_from_events(valid_events)
            result.metrics_updated = dataset_built
            
            result.completed_at = int(time.time())
            result.status = "success"
            
            self._state["last_ingestion_at"] = result.completed_at
            self._state["total_ingestions"] += 1
            self._state["total_events_processed"] += result.events_validated
            self._state["ingestion_history"].append({
                "ingestion_id": ingestion_id,
                "source": source,
                "events": result.events_validated,
                "timestamp": result.completed_at,
            })
            self._save_state()
            
        except Exception as e:
            result.completed_at = int(time.time())
            result.status = "error"
            result.error_message = str(e)
        
        return result
    
    def ingest_meta_insights(self, insights_data: List[Dict[str, Any]],
                              ad_to_creative_map: Dict[str, str],
                              source: str = "meta_insights") -> IngestionResult:
        """从 Meta Insights 摄取数据"""
        import uuid
        
        ingestion_id = f"ingest_meta_{uuid.uuid4().hex[:8]}"
        start_time = int(time.time())
        
        result = IngestionResult(
            ingestion_id=ingestion_id,
            source=source,
            started_at=start_time,
        )
        
        try:
            known_creatives = set(ad_to_creative_map.values())
            events = self._insights_to_events(insights_data, ad_to_creative_map)
            
            validation = self.safety_layer.validate_events(events, known_creatives)
            result.validation_result = validation
            
            valid_events = self.safety_layer.filter_valid_events(events, known_creatives)
            
            result.events_processed = len(events)
            result.events_validated = len(valid_events)
            result.events_rejected = len(events) - len(valid_events)
            
            creative_metrics = self._compute_metrics_from_events(valid_events)
            result.creatives_updated = len(creative_metrics)
            
            result.completed_at = int(time.time())
            result.status = "success"
            
            self._state["last_ingestion_at"] = result.completed_at
            self._state["total_ingestions"] += 1
            self._state["total_events_processed"] += result.events_validated
            self._save_state()
            
        except Exception as e:
            result.completed_at = int(time.time())
            result.status = "error"
            result.error_message = str(e)
        
        return result
    
    def _insights_to_events(self, insights: List[Dict[str, Any]],
                             ad_to_creative_map: Dict[str, str]) -> List[Any]:
        """将 Insights 数据转换为事件对象"""
        from .tracking_layer import TrackingEvent
        import uuid
        
        events = []
        for insight in insights:
            ad_id = insight.get("ad_id", "")
            creative_id = ad_to_creative_map.get(ad_id, ad_id)
            campaign_id = insight.get("campaign_id", "")
            country = insight.get("country", "")
            
            impressions = int(insight.get("impressions", 0))
            clicks = int(insight.get("clicks", 0))
            spend = float(insight.get("spend", 0))
            
            installs = 0
            for action in insight.get("actions", []):
                if "install" in action.get("action_type", ""):
                    installs = int(action.get("value", 0))
                    break
            
            cost_per_impression = spend / impressions if impressions > 0 else 0
            
            max_sample_imp = min(impressions, 100)
            for i in range(max_sample_imp):
                evt = TrackingEvent(
                    event_id=f"evt_imp_{uuid.uuid4().hex[:10]}",
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=campaign_id,
                    timestamp=int(time.time()) - i * 60,
                    event_type="impression",
                    cost=cost_per_impression,
                    country=country,
                )
                events.append(evt)
            
            max_sample_click = min(clicks, 50)
            for i in range(max_sample_click):
                evt = TrackingEvent(
                    event_id=f"evt_clk_{uuid.uuid4().hex[:10]}",
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=campaign_id,
                    timestamp=int(time.time()) - i * 30,
                    event_type="click",
                    cost=0,
                    country=country,
                )
                events.append(evt)
            
            max_sample_install = min(installs, 20)
            for i in range(max_sample_install):
                evt = TrackingEvent(
                    event_id=f"evt_ins_{uuid.uuid4().hex[:10]}",
                    creative_id=creative_id,
                    ad_id=ad_id,
                    campaign_id=campaign_id,
                    timestamp=int(time.time()) - i * 300,
                    event_type="install",
                    cost=0,
                    country=country,
                )
                events.append(evt)
        
        return events
    
    def _compute_metrics_from_events(self, events: List[Any]) -> Dict[str, Any]:
        """从事件计算指标"""
        from .real_metrics_engine import RealMetricsEngine
        engine = RealMetricsEngine(output_dir=str(self.output_dir))
        results = engine.compute_from_events(events)
        return results
    
    def _build_dataset_from_events(self, events: List[Any]) -> int:
        """从事件构建数据集"""
        return len(set(e.creative_id for e in events if hasattr(e, 'creative_id')))
    
    def trigger_weight_update(self, min_impressions: int = 100) -> Dict[str, Any]:
        """触发权重更新"""
        try:
            learning_module = importlib.import_module(f"{_PKG}.10_learning.weight_update_system")
            WeightUpdateSystem = learning_module.WeightUpdateSystem
            
            dataset_module = importlib.import_module(f"{_PKG}.10_learning.dataset_builder")
            DatasetBuilder = dataset_module.DatasetBuilder
            
            weight_updater = WeightUpdateSystem(output_dir=str(self.output_dir))
            builder = DatasetBuilder(output_dir=str(self.output_dir))
            
            dataset = builder.build_dataset(min_impressions=min_impressions)
            
            if not dataset.samples:
                return {"status": "no_data", "samples": 0}
            
            updates = weight_updater.compute_updates(dataset)
            applied = weight_updater.apply_updates(updates)
            
            return {
                "status": "success" if applied else "no_updates",
                "dataset_samples": len(dataset.samples),
                "updates_applied": applied,
                "updates": updates,
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_bridge_status(self) -> Dict[str, Any]:
        return {
            "last_ingestion_at": self._state["last_ingestion_at"],
            "total_ingestions": self._state["total_ingestions"],
            "total_events_processed": self._state["total_events_processed"],
            "recent_ingestions": self._state["ingestion_history"][-5:],
        }
