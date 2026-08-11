"""L4-L5-L6 — Attribution Engine + Metrics Engine + Budget Intelligence

L4 Attribution Engine：
- last-click (MVP)
- 7-day click / 1-day view
- multi-touch (进阶)

L5 Metrics Engine：
- CTR / CPC / CVR / IPM / ROAS
- LTV (optional)

L6 Budget Intelligence Engine：
- ROAS ↑ → budget ↑
- CTR ↑ but CVR ↓ → creative problem
- IPM ↑ → scale adset
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from enum import Enum


CLICK_WINDOW_DAYS = 7
VIEW_WINDOW_DAYS = 1


class AttributionModel(Enum):
    LAST_CLICK = "last_click"
    LAST_VIEW = "last_view"
    MULTI_TOUCH = "multi_touch"
    DATA_DRIVEN = "data_driven"


@dataclass
class AttributionResult:
    """归因结果"""
    creative_id: str
    ad_id: str
    campaign_id: str = ""
    adset_id: str = ""
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    
    click_attributed_installs: int = 0
    view_attributed_installs: int = 0
    multi_touch_installs: int = 0
    
    total_revenue: float = 0.0
    total_cost: float = 0.0
    
    ctr: float = 0.0
    cvr: float = 0.0
    ipm: float = 0.0
    roas: float = 0.0
    cpc: float = 0.0
    ltv: float = 0.0
    
    attribution_model: AttributionModel = AttributionModel.LAST_CLICK
    
    attribution_paths: List[Dict[str, Any]] = field(default_factory=list)
    
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
        
        if self.installs > 0:
            self.ltv = self.total_revenue / self.installs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "click_attributed_installs": self.click_attributed_installs,
            "view_attributed_installs": self.view_attributed_installs,
            "multi_touch_installs": self.multi_touch_installs,
            "total_revenue": round(self.total_revenue, 4),
            "total_cost": round(self.total_cost, 4),
            "ctr": round(self.ctr, 6),
            "cvr": round(self.cvr, 6),
            "ipm": round(self.ipm, 4),
            "roas": round(self.roas, 4),
            "cpc": round(self.cpc, 4),
            "ltv": round(self.ltv, 4),
            "attribution_model": self.attribution_model.value,
        }


class AttributionEngineV2:
    """归因引擎 V2 — 支持多种归因模型
    
    支持：
    - last-click (MVP)
    - 7-day click / 1-day view
    - multi-touch (进阶)
    """
    
    def __init__(self, model: AttributionModel = AttributionModel.LAST_CLICK,
                 output_dir: str = "memory/attribution"):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._events: List[Dict[str, Any]] = []
        self._results: Dict[str, AttributionResult] = {}
    
    def add_events(self, events: List[Dict[str, Any]]):
        """添加事件列表"""
        self._events.extend(events)
    
    def run_attribution(self) -> Dict[str, AttributionResult]:
        """运行归因"""
        self._results = {}
        
        user_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for event in self._events:
            user_id = event.get("user_id", "unknown")
            user_events[user_id].append(event)
        
        for user_id in user_events:
            user_events[user_id].sort(key=lambda e: e.get("timestamp", 0))
        
        for user_id, events in user_events.items():
            self._attribute_user(user_id, events)
        
        for result in self._results.values():
            result.compute_derived()
        
        return self._results
    
    def _attribute_user(self, user_id: str, events: List[Dict[str, Any]]):
        """对单个用户进行归因"""
        last_click = None
        last_view = None
        touch_points: List[Dict[str, Any]] = []
        
        for event in events:
            event_type = event.get("event_type", "")
            creative_id = event.get("creative_id", "")
            ad_id = event.get("ad_id", "")
            
            if creative_id not in self._results:
                self._results[creative_id] = AttributionResult(
                    creative_id=creative_id,
                    ad_id=ad_id,
                    attribution_model=self.model,
                )
            
            result = self._results[creative_id]
            
            if event_type == "impression":
                result.impressions += 1
                result.total_cost += event.get("cost", 0.001)
                last_view = event
                touch_points.append(event)
            
            elif event_type == "click":
                result.clicks += 1
                result.total_cost += event.get("cost", 0.01)
                last_click = event
                touch_points.append(event)
            
            elif event_type == "install":
                attributed = self._attribute_conversion(
                    event, last_click, last_view, touch_points
                )
                if attributed:
                    result.installs += 1
                    if attributed == "click":
                        result.click_attributed_installs += 1
                    elif attributed == "view":
                        result.view_attributed_installs += 1
                    elif attributed == "multi_touch":
                        result.multi_touch_installs += 1
            
            elif event_type == "purchase":
                attributed = self._attribute_conversion(
                    event, last_click, last_view, touch_points
                )
                if attributed:
                    result.purchases += 1
                    result.total_revenue += event.get("revenue", 0.0)
    
    def _attribute_conversion(self,
                               conversion: Dict[str, Any],
                               last_click: Optional[Dict[str, Any]],
                               last_view: Optional[Dict[str, Any]],
                               touch_points: List[Dict[str, Any]]) -> Optional[str]:
        """对转化进行归因
        
        Returns:
            "click" | "view" | "multi_touch" | None
        """
        conv_time = conversion.get("timestamp", 0)
        
        if self.model == AttributionModel.LAST_CLICK:
            if last_click:
                click_time = last_click.get("timestamp", 0)
                window = CLICK_WINDOW_DAYS * 24 * 60 * 60
                if conv_time - click_time <= window:
                    return "click"
            return None
        
        elif self.model == AttributionModel.LAST_VIEW:
            if last_view:
                view_time = last_view.get("timestamp", 0)
                window = VIEW_WINDOW_DAYS * 24 * 60 * 60
                if conv_time - view_time <= window:
                    return "view"
            return None
        
        elif self.model == AttributionModel.MULTI_TOUCH:
            if touch_points:
                return "multi_touch"
            return None
        
        return None
    
    def get_result(self, creative_id: str) -> Optional[AttributionResult]:
        return self._results.get(creative_id)
    
    def get_all_results(self) -> Dict[str, AttributionResult]:
        return self._results


class MetricsEngine:
    """Metrics Engine — 真实 ROI 计算
    
    计算：
    - CTR = clicks / impressions
    - CVR = installs / clicks
    - IPM = installs / 1000 impressions
    - ROAS = revenue / spend
    - LTV = revenue / installs
    """
    
    def __init__(self, output_dir: str = "memory/metrics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._metrics: Dict[str, Dict[str, float]] = {}
    
    def compute_metrics(self, attribution_result: AttributionResult) -> Dict[str, float]:
        """计算指标"""
        metrics = {
            "ctr": attribution_result.ctr,
            "cvr": attribution_result.cvr,
            "ipm": attribution_result.ipm,
            "roas": attribution_result.roas,
            "cpc": attribution_result.cpc,
            "ltv": attribution_result.ltv,
            "total_revenue": attribution_result.total_revenue,
            "total_cost": attribution_result.total_cost,
            "impressions": attribution_result.impressions,
            "clicks": attribution_result.clicks,
            "installs": attribution_result.installs,
            "purchases": attribution_result.purchases,
        }
        
        self._metrics[attribution_result.creative_id] = metrics
        return metrics
    
    def compute_batch(self, results: Dict[str, AttributionResult]) -> Dict[str, Dict[str, float]]:
        """批量计算"""
        for creative_id, result in results.items():
            self.compute_metrics(result)
        return self._metrics
    
    def get_metrics(self, creative_id: str) -> Optional[Dict[str, float]]:
        return self._metrics.get(creative_id)
    
    def rank_by_roas(self) -> List[Tuple[str, float]]:
        """按 ROAS 排序"""
        ranked = sorted(
            self._metrics.items(),
            key=lambda x: x[1].get("roas", 0),
            reverse=True
        )
        return [(c, m.get("roas", 0)) for c, m in ranked]
    
    def get_winners(self, threshold_roas: float = 1.5) -> List[str]:
        """获取 Winners"""
        return [c for c, m in self._metrics.items() if m.get("roas", 0) >= threshold_roas]
    
    def get_losers(self, threshold_roas: float = 0.5) -> List[str]:
        """获取 Losers"""
        return [c for c, m in self._metrics.items() if m.get("roas", 0) < threshold_roas]


@dataclass
class BudgetDecision:
    """预算决策"""
    entity_id: str
    entity_type: str  # campaign / adset / ad
    
    current_budget: float
    new_budget: float
    delta: float
    delta_percent: float
    
    decision_type: str  # scale / kill / hold
    reason: str
    
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "current_budget": self.current_budget,
            "new_budget": self.new_budget,
            "delta": round(self.delta, 2),
            "delta_percent": round(self.delta_percent, 2),
            "decision_type": self.decision_type,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
        }


class BudgetIntelligenceEngine:
    """Budget Intelligence Engine — 自动预算分配
    
    Rules：
    - ROAS ↑ → budget ↑ (scale winners)
    - CTR ↑ but CVR ↓ → creative problem (hold)
    - IPM ↑ → scale adset
    - ROAS ↓ → kill losers
    
    输出：
    {
      "adset_id": "...",
      "new_budget": 120,
      "delta": +30%
    }
    """
    
    def __init__(self,
                 scale_threshold_roas: float = 1.5,
                 kill_threshold_roas: float = 0.5,
                 max_budget_per_adset: float = 500,
                 min_budget_per_adset: float = 10,
                 max_scale_percent: float = 0.5,
                 output_dir: str = "memory/budget"):
        self.scale_threshold = scale_threshold_roas
        self.kill_threshold = kill_threshold_roas
        self.max_budget = max_budget_per_adset
        self.min_budget = min_budget_per_adset
        self.max_scale_percent = max_scale_percent
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._decisions: Dict[str, BudgetDecision] = {}
    
    def analyze_and_decide(self,
                            metrics: Dict[str, Dict[str, float]],
                            current_budgets: Dict[str, float],
                            entity_type: str = "adset") -> List[BudgetDecision]:
        """分析并做出预算决策"""
        decisions = []
        
        for creative_id, m in metrics.items():
            current_budget = current_budgets.get(creative_id, 50.0)
            
            roas = m.get("roas", 0)
            ctr = m.get("ctr", 0)
            cvr = m.get("cvr", 0)
            ipm = m.get("ipm", 0)
            
            decision = self._make_decision(
                entity_id=creative_id,
                entity_type=entity_type,
                current_budget=current_budget,
                roas=roas,
                ctr=ctr,
                cvr=cvr,
                ipm=ipm,
            )
            
            decisions.append(decision)
            self._decisions[creative_id] = decision
        
        return decisions
    
    def _make_decision(self,
                        entity_id: str,
                        entity_type: str,
                        current_budget: float,
                        roas: float,
                        ctr: float,
                        cvr: float,
                        ipm: float) -> BudgetDecision:
        """做出单个决策"""
        
        if roas >= self.scale_threshold:
            if ipm > 20:
                delta_percent = self.max_scale_percent
            else:
                delta_percent = 0.3
            
            new_budget = min(current_budget * (1 + delta_percent), self.max_budget)
            delta = new_budget - current_budget
            
            return BudgetDecision(
                entity_id=entity_id,
                entity_type=entity_type,
                current_budget=current_budget,
                new_budget=new_budget,
                delta=delta,
                delta_percent=delta_percent,
                decision_type="scale",
                reason=f"ROAS {roas:.2f} >= {self.scale_threshold}, scale",
                confidence=min(roas / self.scale_threshold, 1.0),
            )
        
        elif roas < self.kill_threshold:
            new_budget = self.min_budget
            delta = new_budget - current_budget
            
            return BudgetDecision(
                entity_id=entity_id,
                entity_type=entity_type,
                current_budget=current_budget,
                new_budget=new_budget,
                delta=delta,
                delta_percent=(delta / current_budget) if current_budget > 0 else -1,
                decision_type="kill",
                reason=f"ROAS {roas:.2f} < {self.kill_threshold}, kill",
                confidence=1.0 - (roas / self.kill_threshold),
            )
        
        elif ctr > 0.05 and cvr < 0.1:
            return BudgetDecision(
                entity_id=entity_id,
                entity_type=entity_type,
                current_budget=current_budget,
                new_budget=current_budget,
                delta=0,
                delta_percent=0,
                decision_type="hold",
                reason=f"CTR high {ctr:.2f} but CVR low {cvr:.2f}, creative problem",
                confidence=0.5,
            )
        
        else:
            return BudgetDecision(
                entity_id=entity_id,
                entity_type=entity_type,
                current_budget=current_budget,
                new_budget=current_budget,
                delta=0,
                delta_percent=0,
                decision_type="hold",
                reason="Metrics within acceptable range",
                confidence=0.3,
            )
    
    def get_decision(self, entity_id: str) -> Optional[BudgetDecision]:
        return self._decisions.get(entity_id)
    
    def get_scale_decisions(self) -> List[BudgetDecision]:
        return [d for d in self._decisions.values() if d.decision_type == "scale"]
    
    def get_kill_decisions(self) -> List[BudgetDecision]:
        return [d for d in self._decisions.values() if d.decision_type == "kill"]
    
    def apply_decisions(self,
                         orchestrator: Any,
                         platform: str = "meta") -> Dict[str, bool]:
        """应用决策到广告平台"""
        results = {}
        
        for entity_id, decision in self._decisions.items():
            if decision.decision_type in ["scale", "kill"]:
                success = orchestrator.update_budget(
                    platform=platform,
                    entity_id=entity_id,
                    entity_type=decision.entity_type,
                    new_budget=decision.new_budget,
                )
                results[entity_id] = success
        
        return results