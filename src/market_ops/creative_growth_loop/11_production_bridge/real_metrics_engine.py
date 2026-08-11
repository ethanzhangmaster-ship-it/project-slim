"""Real Metrics Engine - 真实指标引擎

P2.5-5: 基于追踪数据计算真实广告指标。

必须计算：
- CTR = click / impression
- IPM = installs per 1000 impressions
- CPC = cost / click
- ROAS = revenue / cost（如果可用）
"""
from __future__ import annotations

import importlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

_PKG = "market_ops.creative_growth_loop"


@dataclass
class CreativeMetrics:
    """创意级别的真实指标"""
    creative_id: str
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    
    total_cost: float = 0.0
    total_revenue: float = 0.0
    
    ctr: float = 0.0
    ipm: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0
    
    sample_size: int = 0
    data_source: str = ""
    
    last_updated: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "total_cost": round(self.total_cost, 2),
            "total_revenue": round(self.total_revenue, 2),
            "ctr": round(self.ctr, 4),
            "ipm": round(self.ipm, 3),
            "cpc": round(self.cpc, 4),
            "cpa": round(self.cpa, 2),
            "roas": round(self.roas, 2),
            "sample_size": self.sample_size,
            "data_source": self.data_source,
            "last_updated": self.last_updated,
        }


@dataclass
class TemplateAggregatedMetrics:
    """模板维度的聚合指标"""
    template_id: str
    
    total_impressions: int = 0
    total_clicks: int = 0
    total_installs: int = 0
    total_cost: float = 0.0
    
    avg_ctr: float = 0.0
    avg_ipm: float = 0.0
    avg_cpc: float = 0.0
    
    creative_count: int = 0
    winning_count: int = 0
    
    performance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "total_impressions": self.total_impressions,
            "total_clicks": self.total_clicks,
            "total_installs": self.total_installs,
            "total_cost": round(self.total_cost, 2),
            "avg_ctr": round(self.avg_ctr, 4),
            "avg_ipm": round(self.avg_ipm, 3),
            "avg_cpc": round(self.avg_cpc, 4),
            "creative_count": self.creative_count,
            "winning_count": self.winning_count,
            "performance_score": round(self.performance_score, 3),
        }


class RealMetricsEngine:
    """真实指标引擎 - 计算广告创意的真实表现指标"""
    
    CTR_WEIGHT = 0.5
    IPM_WEIGHT = 0.3
    COST_EFFICIENCY_WEIGHT = 0.2
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = self.output_dir / "real_metrics.json"
        self._creative_metrics: Dict[str, CreativeMetrics] = {}
        self._load_metrics()
    
    def _load_metrics(self):
        if self.metrics_file.exists():
            with open(self.metrics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for cid, metrics_data in data.get("creative_metrics", {}).items():
                    self._creative_metrics[cid] = CreativeMetrics(**metrics_data)
    
    def _save_metrics(self):
        data = {
            "creative_metrics": {
                cid: m.to_dict() for cid, m in self._creative_metrics.items()
            },
            "updated_at": int(time.time()),
        }
        with open(self.metrics_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def compute_from_events(self, events: List[Any]) -> Dict[str, CreativeMetrics]:
        """从事件列表计算指标"""
        by_creative = defaultdict(list)
        for event in events:
            by_creative[event.creative_id].append(event)
        
        results = {}
        for creative_id, creative_events in by_creative.items():
            metrics = self._compute_single_creative(creative_id, creative_events)
            results[creative_id] = metrics
            self._creative_metrics[creative_id] = metrics
        
        self._save_metrics()
        return results
    
    def _compute_single_creative(self, creative_id: str,
                                  events: List[Any]) -> CreativeMetrics:
        impressions = 0
        clicks = 0
        installs = 0
        purchases = 0
        total_cost = 0.0
        total_revenue = 0.0
        
        for event in events:
            if event.event_type == "impression":
                impressions += 1
                total_cost += event.cost
            elif event.event_type == "click":
                clicks += 1
                total_cost += event.cost
            elif event.event_type == "install":
                installs += 1
                total_cost += event.cost
            elif event.event_type == "purchase":
                purchases += 1
                total_revenue += event.value
        
        ctr = clicks / impressions if impressions > 0 else 0.0
        ipm = (installs / impressions * 1000) if impressions > 0 else 0.0
        cpc = total_cost / clicks if clicks > 0 else 0.0
        cpa = total_cost / installs if installs > 0 else 0.0
        roas = total_revenue / total_cost if total_cost > 0 else 0.0
        
        return CreativeMetrics(
            creative_id=creative_id,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            purchases=purchases,
            total_cost=total_cost,
            total_revenue=total_revenue,
            ctr=ctr,
            ipm=ipm,
            cpc=cpc,
            cpa=cpa,
            roas=roas,
            sample_size=impressions,
            data_source="event_based",
            last_updated=int(time.time()),
        )
    
    def compute_from_meta_insights(self, insights: List[Dict[str, Any]],
                                    creative_id_map: Dict[str, str]) -> Dict[str, CreativeMetrics]:
        """从 Meta Ads Insights 数据计算指标
        
        Args:
            insights: Meta Insights API 返回的数据列表
            creative_id_map: ad_id -> creative_id 的映射
        """
        by_creative = defaultdict(lambda: {
            "impressions": 0, "clicks": 0, "installs": 0,
            "spend": 0.0, "purchases": 0, "revenue": 0.0
        })
        
        for insight in insights:
            ad_id = insight.get("ad_id", "")
            creative_id = creative_id_map.get(ad_id, ad_id)
            
            data = by_creative[creative_id]
            data["impressions"] += int(insight.get("impressions", 0))
            data["clicks"] += int(insight.get("clicks", 0))
            data["spend"] += float(insight.get("spend", 0))
            
            actions = insight.get("actions", [])
            for action in actions:
                action_type = action.get("action_type", "")
                value = int(action.get("value", 0))
                if "install" in action_type:
                    data["installs"] += value
                elif "purchase" in action_type:
                    data["purchases"] += value
            
            action_values = insight.get("action_values", [])
            for av in action_values:
                if "purchase" in av.get("action_type", ""):
                    data["revenue"] += float(av.get("value", 0))
        
        results = {}
        for creative_id, data in by_creative.items():
            impressions = data["impressions"]
            clicks = data["clicks"]
            installs = data["installs"]
            spend = data["spend"]
            revenue = data["revenue"]
            
            ctr = clicks / impressions if impressions > 0 else 0.0
            ipm = (installs / impressions * 1000) if impressions > 0 else 0.0
            cpc = spend / clicks if clicks > 0 else 0.0
            cpa = spend / installs if installs > 0 else 0.0
            roas = revenue / spend if spend > 0 else 0.0
            
            metrics = CreativeMetrics(
                creative_id=creative_id,
                impressions=impressions,
                clicks=clicks,
                installs=installs,
                purchases=data["purchases"],
                total_cost=spend,
                total_revenue=revenue,
                ctr=ctr,
                ipm=ipm,
                cpc=cpc,
                cpa=cpa,
                roas=roas,
                sample_size=impressions,
                data_source="meta_insights",
                last_updated=int(time.time()),
            )
            
            results[creative_id] = metrics
            self._creative_metrics[creative_id] = metrics
        
        self._save_metrics()
        return results
    
    def get_creative_metrics(self, creative_id: str) -> Optional[CreativeMetrics]:
        return self._creative_metrics.get(creative_id)
    
    def get_template_metrics(self, template_to_creatives: Dict[str, List[str]]) -> Dict[str, TemplateAggregatedMetrics]:
        """按模板聚合指标"""
        results = {}
        
        for template_id, creative_ids in template_to_creatives.items():
            agg = TemplateAggregatedMetrics(template_id=template_id)
            
            ctr_list = []
            ipm_list = []
            cpc_list = []
            
            for cid in creative_ids:
                metrics = self._creative_metrics.get(cid)
                if not metrics:
                    continue
                
                agg.total_impressions += metrics.impressions
                agg.total_clicks += metrics.clicks
                agg.total_installs += metrics.installs
                agg.total_cost += metrics.total_cost
                agg.creative_count += 1
                
                if metrics.impressions > 0:
                    ctr_list.append(metrics.ctr)
                    ipm_list.append(metrics.ipm)
                    if metrics.clicks > 0:
                        cpc_list.append(metrics.cpc)
            
            if ctr_list:
                agg.avg_ctr = sum(ctr_list) / len(ctr_list)
            if ipm_list:
                agg.avg_ipm = sum(ipm_list) / len(ipm_list)
            if cpc_list:
                agg.avg_cpc = sum(cpc_list) / len(cpc_list)
            
            agg.performance_score = self._compute_performance_score(agg)
            
            results[template_id] = agg
        
        return results
    
    def _compute_performance_score(self, agg: TemplateAggregatedMetrics) -> float:
        """计算综合表现分数（0-1）"""
        ctr_score = min(agg.avg_ctr / 0.05, 1.0) if agg.avg_ctr > 0 else 0.0
        ipm_score = min(agg.avg_ipm / 10.0, 1.0) if agg.avg_ipm > 0 else 0.0
        cost_score = 1.0 if agg.avg_cpc == 0 else min(1.0 / (agg.avg_cpc * 100), 1.0)
        
        return (
            self.CTR_WEIGHT * ctr_score +
            self.IPM_WEIGHT * ipm_score +
            self.COST_EFFICIENCY_WEIGHT * cost_score
        )
    
    def get_top_creatives(self, n: int = 10, metric: str = "ctr",
                          min_impressions: int = 100) -> List[CreativeMetrics]:
        """获取表现最好的创意"""
        qualified = [
            m for m in self._creative_metrics.values()
            if m.impressions >= min_impressions
        ]
        
        if metric == "ctr":
            qualified.sort(key=lambda m: m.ctr, reverse=True)
        elif metric == "ipm":
            qualified.sort(key=lambda m: m.ipm, reverse=True)
        elif metric == "roas":
            qualified.sort(key=lambda m: m.roas, reverse=True)
        elif metric == "cpc":
            qualified.sort(key=lambda m: m.cpc)
        
        return qualified[:n]
    
    def get_all_metrics(self) -> List[CreativeMetrics]:
        return list(self._creative_metrics.values())
    
    def get_summary(self) -> Dict[str, Any]:
        total_impressions = sum(m.impressions for m in self._creative_metrics.values())
        total_clicks = sum(m.clicks for m in self._creative_metrics.values())
        total_installs = sum(m.installs for m in self._creative_metrics.values())
        total_cost = sum(m.total_cost for m in self._creative_metrics.values())
        
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        avg_ipm = (total_installs / total_impressions * 1000) if total_impressions > 0 else 0.0
        
        return {
            "total_creatives": len(self._creative_metrics),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_installs": total_installs,
            "total_cost": round(total_cost, 2),
            "avg_ctr": round(avg_ctr, 4),
            "avg_ipm": round(avg_ipm, 3),
        }
