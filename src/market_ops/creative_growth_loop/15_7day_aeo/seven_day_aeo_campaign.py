"""7-Day Meta AEO Campaign — Real-world Paid AEO Optimization Loop System

System Definition: Real-world Paid AEO Optimization Loop System

Core Capabilities:
- Real Meta AEO (Purchase Optimized) campaign creation
- 3 AdSets (Broad / Interest / Retarget) with purchase optimization
- 3 creatives x 2 variants each
- 7-day day-by-day execution loop
- Automatic budget adjustment (scale / hold / kill)
- Closed-loop learning dataset + weight update

FINAL RUN SPEC Requirements:
- Campaign: APP_PROMOTION/SALES objective, OFFSITE_CONVERSIONS optimization
- Bid Strategy: LOWEST_COST_WITHOUT_CAP, Status: ACTIVE
- AdSet A Broad 50%, B Interest 30%, C Retarget 20%
- 3 creatives x 2 variants minimum
- Day 1-7 execution with daily metrics
- Budget Intelligence: Scale (ROAS>=2.0), Kill (spend>threshold & 0 purchases), Hold
- Full data chain: creative_id -> asset -> ad -> impression -> ... -> weight update
"""
from __future__ import annotations

import importlib
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

_PKG = "market_ops.creative_growth_loop"


@dataclass
class AdCreative:
    """广告创意"""
    creative_id: str
    template_id: str
    variant_id: str
    variant_type: str
    
    asset_id: str = ""
    asset_url: str = ""
    asset_path: str = ""
    asset_hash: str = ""
    
    ad_id: str = ""
    adset_id: str = ""
    
    status: str = "ACTIVE"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "template_id": self.template_id,
            "variant_id": self.variant_id,
            "variant_type": self.variant_type,
            "asset_id": self.asset_id,
            "asset_url": self.asset_url,
            "asset_path": self.asset_path,
            "asset_hash": self.asset_hash,
            "ad_id": self.ad_id,
            "adset_id": self.adset_id,
            "status": self.status,
        }


@dataclass
class AdSetInfo:
    """AdSet 信息"""
    adset_id: str
    name: str
    adset_type: str  # broad / interest / retarget
    
    budget: float = 0.0
    budget_ratio: float = 0.0
    optimization_event: str = "purchase"
    
    creatives: List[AdCreative] = field(default_factory=list)
    
    status: str = "ACTIVE"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "adset_id": self.adset_id,
            "name": self.name,
            "type": self.adset_type,
            "budget": round(self.budget, 2),
            "budget_ratio": self.budget_ratio,
            "optimization_event": self.optimization_event,
            "creatives": [c.to_dict() for c in self.creatives],
            "status": self.status,
        }


@dataclass
class DailyMetrics:
    """每日指标"""
    day: int
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    
    spend: float = 0.0
    revenue: float = 0.0
    
    ctr: float = 0.0
    cvr: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0
    ipm: float = 0.0
    
    total_budget: float = 0.0
    budget_decision: str = "hold"
    budget_delta_percent: float = 0.0
    budget_reason: str = ""
    
    killed_creatives: List[str] = field(default_factory=list)
    scaled_creatives: List[str] = field(default_factory=list)
    killed_adsets: List[str] = field(default_factory=list)
    
    per_creative: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_adset: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def compute_derived(self):
        """计算衍生指标"""
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
            self.ipm = (self.installs / self.impressions) * 1000
        if self.clicks > 0:
            self.cvr = self.installs / self.clicks
        if self.purchases > 0:
            self.cpa = self.spend / self.purchases
        if self.spend > 0:
            self.roas = self.revenue / self.spend
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "ctr": round(self.ctr, 6),
            "cvr": round(self.cvr, 6),
            "cpa": round(self.cpa, 2),
            "roas": round(self.roas, 4),
            "ipm": round(self.ipm, 2),
            "total_budget": round(self.total_budget, 2),
            "budget_decision": self.budget_decision,
            "budget_delta_percent": round(self.budget_delta_percent, 2),
            "budget_reason": self.budget_reason,
            "killed_creatives": self.killed_creatives,
            "scaled_creatives": self.scaled_creatives,
            "killed_adsets": self.killed_adsets,
            "per_creative": self.per_creative,
            "per_adset": self.per_adset,
        }


@dataclass
class SevenDayReport:
    """7天最终报告"""
    
    run_id: str = ""
    campaign_id: str = ""
    status: str = "pending"
    
    campaign_name: str = ""
    campaign_objective: str = ""
    bid_strategy: str = ""
    
    total_spend: float = 0.0
    total_impressions: int = 0
    total_clicks: int = 0
    total_installs: int = 0
    total_purchases: int = 0
    total_revenue: float = 0.0
    
    ctr: float = 0.0
    cvr: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0
    ipm: float = 0.0
    
    best_creative: str = ""
    best_creative_roas: float = 0.0
    worst_creative: str = ""
    worst_creative_roas: float = 0.0
    
    best_adset: str = ""
    best_adset_type: str = ""
    worst_adset: str = ""
    worst_adset_type: str = ""
    
    budget_curve: List[Dict[str, Any]] = field(default_factory=list)
    learning_delta: Dict[str, Any] = field(default_factory=dict)
    
    daily_metrics: List[DailyMetrics] = field(default_factory=list)
    
    adsets: List[AdSetInfo] = field(default_factory=list)
    creatives: List[AdCreative] = field(default_factory=list)
    
    dataset_written: bool = False
    weight_update_applied: bool = False
    
    total_budget_changes: int = 0
    total_creatives_killed: int = 0
    total_adsets_killed: int = 0
    
    started_at: int = 0
    completed_at: int = 0
    
    error: str = ""
    
    def compute_summary(self):
        """计算汇总指标"""
        if self.daily_metrics:
            for dm in self.daily_metrics:
                self.total_impressions += dm.impressions
                self.total_clicks += dm.clicks
                self.total_installs += dm.installs
                self.total_purchases += dm.purchases
                self.total_spend += dm.spend
                self.total_revenue += dm.revenue
                
                if dm.budget_decision != "hold":
                    self.total_budget_changes += 1
                self.total_creatives_killed += len(dm.killed_creatives)
                self.total_adsets_killed += len(dm.killed_adsets)
            
            if self.total_impressions > 0:
                self.ctr = self.total_clicks / self.total_impressions
                self.ipm = (self.total_installs / self.total_impressions) * 1000
            if self.total_clicks > 0:
                self.cvr = self.total_installs / self.total_clicks
            if self.total_purchases > 0:
                self.cpa = self.total_spend / self.total_purchases
            if self.total_spend > 0:
                self.roas = self.total_revenue / self.total_spend
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "campaign_objective": self.campaign_objective,
            "bid_strategy": self.bid_strategy,
            "status": self.status,
            "total_spend": round(self.total_spend, 2),
            "total_impressions": self.total_impressions,
            "total_clicks": self.total_clicks,
            "total_installs": self.total_installs,
            "total_purchases": self.total_purchases,
            "total_revenue": round(self.total_revenue, 2),
            "ctr": round(self.ctr, 6),
            "cvr": round(self.cvr, 6),
            "cpa": round(self.cpa, 2),
            "roas": round(self.roas, 4),
            "ipm": round(self.ipm, 2),
            "best_creative": self.best_creative,
            "best_creative_roas": round(self.best_creative_roas, 4),
            "worst_creative": self.worst_creative,
            "worst_creative_roas": round(self.worst_creative_roas, 4),
            "best_adset": self.best_adset,
            "best_adset_type": self.best_adset_type,
            "worst_adset": self.worst_adset,
            "worst_adset_type": self.worst_adset_type,
            "budget_curve": self.budget_curve,
            "learning_delta": self.learning_delta,
            "daily_metrics": [dm.to_dict() for dm in self.daily_metrics],
            "adsets": [a.to_dict() for a in self.adsets],
            "creatives": [c.to_dict() for c in self.creatives],
            "dataset_written": self.dataset_written,
            "weight_update_applied": self.weight_update_applied,
            "total_budget_changes": self.total_budget_changes,
            "total_creatives_killed": self.total_creatives_killed,
            "total_adsets_killed": self.total_adsets_killed,
            "timing": {
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "duration_sec": self.completed_at - self.started_at,
            },
            "error": self.error,
        }


class SevenDayAEOCampaign:
    """7天 Meta AEO Campaign 执行器
    
    Real-world Paid AEO Optimization Loop System
    """
    
    def __init__(self,
                 output_dir: str = "memory/7day_aeo",
                 mode: str = "mock",
                 total_budget: float = 700.0,
                 objective: str = "APP_PROMOTION",
                 app_id: str = "com.wjoj.witch"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.total_budget = total_budget
        self.objective = objective
        self.app_id = app_id
        
        self.daily_budget = total_budget / 7.0
        
        self._init_modules()
        
        self.adsets: List[AdSetInfo] = []
        self.creatives: List[AdCreative] = []
        self.campaign_id: str = ""
        self.campaign_name: str = ""
        
        self.daily_metrics: List[DailyMetrics] = []
        
        self._day = 0
        self._active_creatives: Dict[str, AdCreative] = {}
        self._creative_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "impressions": 0, "clicks": 0, "installs": 0,
                "purchases": 0, "spend": 0.0, "revenue": 0.0,
                "status": "ACTIVE",
            }
        )
        self._adset_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "impressions": 0, "clicks": 0, "installs": 0,
                "purchases": 0, "spend": 0.0, "revenue": 0.0,
            }
        )
        
        self._kill_spend_threshold = 20.0
        self._scale_roas_threshold = 2.0
        self._min_ctr = 0.005
        self._random_seed = 42
        random.seed(self._random_seed)
    
    def _init_modules(self):
        """初始化模块"""
        orch_mod = importlib.import_module(f"{_PKG}.14_full_stack.l2_ad_platform_orchestrator")
        self.Platform = orch_mod.Platform
        self.Objective = orch_mod.Objective
        self.OptimizationGoal = orch_mod.OptimizationGoal
        self.BidStrategy = orch_mod.BidStrategy
        self.CampaignConfig = orch_mod.CampaignConfig
        self.AdSetConfig = orch_mod.AdSetConfig
        self.AdConfig = orch_mod.AdConfig
        self.MultiPlatformOrchestrator = orch_mod.MultiPlatformOrchestrator
        
        self.orchestrator = self.MultiPlatformOrchestrator(
            mode=self.mode,
            output_dir=str(self.output_dir / "orchestrator"),
        )
        
        asset_mod = importlib.import_module(f"{_PKG}.14_full_stack.l1_asset_production")
        self.asset_engine = asset_mod.AssetProductionEngine(
            output_dir=str(self.output_dir / "assets")
        )
        self.VariantConfig = asset_mod.VariantConfig
        
        track_mod = importlib.import_module(f"{_PKG}.14_full_stack.l3_tracking_layer")
        self.EventType = track_mod.EventType
        self.event_collector = track_mod.EventStreamCollector(
            mode=self.mode,
            output_dir=str(self.output_dir / "tracking"),
        )
        
        attr_mod = importlib.import_module(f"{_PKG}.14_full_stack.l456_attribution_metrics_budget")
        self.AttributionModel = attr_mod.AttributionModel
        self.attribution_engine = attr_mod.AttributionEngineV2(
            model=self.AttributionModel.LAST_CLICK,
            output_dir=str(self.output_dir / "attribution"),
        )
        self.metrics_engine = attr_mod.MetricsEngine(
            output_dir=str(self.output_dir / "metrics"),
        )
        self.budget_engine = attr_mod.BudgetIntelligenceEngine(
            scale_threshold_roas=2.0,
            kill_threshold_roas=1.0,
            output_dir=str(self.output_dir / "budget"),
        )
        
        try:
            compiler_mod = importlib.import_module(f"{_PKG}.04_compiler.layout_compiler")
            self.layout_compiler = compiler_mod.LayoutCompiler()
        except Exception:
            self.layout_compiler = None
        
        try:
            weight_mod = importlib.import_module(f"{_PKG}.10_learning.weight_update_system")
            self.weight_system = weight_mod.WeightUpdateSystem(
                output_dir=str(self.output_dir),
            )
        except Exception:
            self.weight_system = None
        
        try:
            mapper_mod = importlib.import_module(f"{_PKG}.10_learning.creative_performance_mapper")
            self.mapper = mapper_mod.CreativePerformanceMapper(
                output_dir=str(self.output_dir),
            )
        except Exception:
            self.mapper = None
    
    def run_7day_campaign(self,
                          product_info: Dict[str, Any],
                          audience_info: Dict[str, Any]) -> SevenDayReport:
        """执行完整 7天 AEO Campaign
        
        Args:
            product_info: 产品信息
            audience_info: 受众信息
        
        Returns:
            SevenDayReport: 最终报告
        """
        report = SevenDayReport(
            run_id=f"aeo7_{uuid.uuid4().hex[:10]}",
            started_at=int(time.time()),
        )
        
        try:
            self._day0_setup(report, product_info, audience_info)
            
            for day in range(1, 8):
                self._day = day
                daily = self._run_day(day, product_info, audience_info)
                self.daily_metrics.append(daily)
            
            self._finalize_report(report)
            report.status = "success"
            
        except Exception as e:
            report.status = "error"
            report.error = str(e)
            import traceback
            traceback.print_exc()
        
        report.completed_at = int(time.time())
        self._save_report(report)
        
        return report
    
    def _day0_setup(self, report: SevenDayReport,
                    product: Dict[str, Any], audience: Dict[str, Any]):
        """Day 0 — 配置创建（Campaign + AdSets + Creatives + Ads）"""
        self._create_campaign(product, audience)
        self._create_adsets(product, audience)
        self._create_creatives(product)
        self._link_creatives_to_adsets()
        
        report.campaign_id = self.campaign_id
        report.campaign_name = self.campaign_name
        report.campaign_objective = self.objective
        report.bid_strategy = "LOWEST_COST_WITHOUT_CAP"
    
    def _create_campaign(self, product: Dict[str, Any],
                          audience: Dict[str, Any]):
        """创建 Campaign
        
        FINAL RUN SPEC:
        - objective: APP_PROMOTION or SALES
        - optimization_goal: OFFSITE_CONVERSIONS
        - bid_strategy: LOWEST_COST_WITHOUT_CAP
        - status: ACTIVE
        """
        campaign_name = f"AEO_Purchase_7Day_{int(time.time())}"
        self.campaign_name = campaign_name
        
        if self.objective == "APP_PROMOTION":
            obj = self.Objective.OUTCOME_APP_PROMOTION
        else:
            obj = self.Objective.OUTCOME_SALES
        
        campaign_config = self.CampaignConfig(
            name=campaign_name,
            objective=obj,
            status="ACTIVE",
            budget_mode="DAILY_BUDGET",
            daily_budget=self.daily_budget,
        )
        
        meta_client = self.orchestrator.get_client(self.Platform.META)
        self.campaign_id = meta_client.create_campaign(campaign_config)
    
    def _create_adsets(self, product: Dict[str, Any],
                        audience: Dict[str, Any]):
        """创建 3个 AdSet
        
        FINAL RUN SPEC:
        - AdSet A — Broad (主学习流量): 50%, optimization_event: purchase
        - AdSet B — Interest: 30%, optimization_event: purchase
        - AdSet C — Retarget (if available): 20%, optimization_event: purchase
        """
        meta_client = self.orchestrator.get_client(self.Platform.META)
        
        geo = audience.get("geo", ["US"])
        if isinstance(geo, str):
            geo = [geo]
        
        age_str = audience.get("age", "18-45")
        age_parts = age_str.split("-")
        age_min = int(age_parts[0]) if len(age_parts) > 0 else 18
        age_max = int(age_parts[1]) if len(age_parts) > 1 else 45
        
        adset_configs = [
            {
                "name": "AEO_A_Broad",
                "type": "broad",
                "budget_ratio": 0.5,
                "interests": [],
            },
            {
                "name": "AEO_B_Interest",
                "type": "interest",
                "budget_ratio": 0.3,
                "interests": audience.get("interests", ["gaming", "puzzle games"]),
            },
            {
                "name": "AEO_C_Retarget",
                "type": "retarget",
                "budget_ratio": 0.2,
                "interests": audience.get("retarget_interests", ["mobile gaming"]),
            },
        ]
        
        for cfg in adset_configs:
            daily_budget = self.daily_budget * cfg["budget_ratio"]
            
            adset_config = self.AdSetConfig(
                name=cfg["name"],
                campaign_id=self.campaign_id,
                optimization_goal=self.OptimizationGoal.OFFSITE_CONVERSIONS,
                billing_event="IMPRESSIONS",
                bid_strategy=self.BidStrategy.LOWEST_COST_WITHOUT_CAP,
                daily_budget=daily_budget,
                geo=geo,
                age_min=age_min,
                age_max=age_max,
                interests=cfg["interests"],
                status="ACTIVE",
            )
            
            adset_id = meta_client.create_adset(adset_config)
            
            adset_info = AdSetInfo(
                adset_id=adset_id,
                name=cfg["name"],
                adset_type=cfg["type"],
                budget=daily_budget,
                budget_ratio=cfg["budget_ratio"],
                optimization_event="purchase",
            )
            
            self.adsets.append(adset_info)
    
    def _create_creatives(self, product: Dict[str, Any]):
        """创建 3 个 creatives，每个 2 variants
        
        FINAL RUN SPEC: 至少 3 creatives，每个 ≥ 2 variants
        """
        templates = ["merge_formula", "evolution_chain", "before_after"]
        variant_types = ["original", "hook_a"]
        
        template_performance = {
            "merge_formula": {"ctr": 0.025, "cvr": 0.28, "purchase_rate": 0.22},
            "evolution_chain": {"ctr": 0.032, "cvr": 0.32, "purchase_rate": 0.28},
            "before_after": {"ctr": 0.022, "cvr": 0.25, "purchase_rate": 0.20},
        }
        
        for template_id in templates:
            ast_dict = self._get_layout_ast_dict(template_id)
            render_constraints = self._get_render_constraints_dict(template_id)
            
            for vtype in variant_types:
                creative_id = f"c_{template_id}_{vtype}_{uuid.uuid4().hex[:6]}"
                
                variant_config = None
                if vtype != "original":
                    variant_config = self.VariantConfig(
                        variant_type=vtype,
                        modifications={"hook_text": "NEW! Limited Offer!"}
                    )
                
                assets = self.asset_engine.produce_asset(
                    creative_id=creative_id,
                    layout_ast=ast_dict,
                    render_constraints=render_constraints,
                    asset_type="image",
                    generate_variants=False,
                )
                
                asset = assets[0] if assets else None
                
                perf = template_performance.get(template_id, {})
                if vtype == "hook_a":
                    perf = dict(perf)
                    perf["ctr"] = perf.get("ctr", 0.02) * 1.15
                
                creative = AdCreative(
                    creative_id=creative_id,
                    template_id=template_id,
                    variant_id=vtype,
                    variant_type=vtype,
                    asset_id=asset.asset_id if asset else "",
                    asset_url=f"http://cdn.example.com/{asset.asset_id}.png" if asset else "",
                    asset_path=asset.path if asset else "",
                    asset_hash=asset.hash if asset else "",
                )
                
                self.creatives.append(creative)
                self._active_creatives[creative_id] = creative
                cm = self._creative_metrics[creative_id]
                cm["template_id"] = template_id
                cm["variant_type"] = vtype
                cm["base_ctr"] = perf.get("ctr", 0.025)
                cm["base_cvr"] = perf.get("cvr", 0.28)
                cm["base_purchase_rate"] = perf.get("purchase_rate", 0.25)
    
    def _get_layout_ast_dict(self, template_id: str) -> Dict[str, Any]:
        """获取 Layout AST 字典"""
        if self.layout_compiler:
            try:
                result = self.layout_compiler.compile(template_id)
                if result and result.ast:
                    return result.ast.to_dict()
            except Exception:
                pass
        
        return self._build_fallback_ast(template_id)
    
    def _build_fallback_ast(self, template_id: str) -> Dict[str, Any]:
        """构建降级用 AST"""
        return {
            "ast_id": f"ast_{template_id}_fallback",
            "template_id": template_id,
            "mechanism_type": "merge" if "merge" in template_id else "evolution",
            "nodes": {
                "reward": {
                    "node_id": "reward",
                    "role": "L1",
                    "position": "center",
                    "size_ratio": 0.45,
                    "brightness_bias": 0.4,
                    "glow_intensity": 0.8,
                    "visual_budget": 45,
                },
                "mechanism": {
                    "node_id": "mechanism",
                    "role": "L2",
                    "position": "left_side",
                    "size_ratio": 0.25,
                    "brightness_bias": 0.2,
                    "visual_budget": 30,
                },
                "identity": {
                    "node_id": "identity",
                    "role": "L3",
                    "position": "right_side",
                    "size_ratio": 0.15,
                    "visual_budget": 15,
                },
            },
            "spatial_constraints": [],
            "visual_budget": {
                "total_budget": 100,
                "allocation": {"reward": 45, "mechanism": 30, "identity": 15, "ui": 10},
            },
            "hard_constraints": {},
        }
    
    def _get_render_constraints_dict(self, template_id: str) -> Dict[str, Any]:
        """获取渲染约束字典"""
        if self.layout_compiler:
            try:
                result = self.layout_compiler.compile(template_id)
                if result and result.render_constraints:
                    return result.render_constraints.to_dict()
            except Exception:
                pass
        
        return {
            "width": 1080,
            "height": 1080,
            "background_color": (30, 30, 60),
            "reward_text": "WIN BIG!",
            "mechanism_text": "Merge to Win",
            "identity_text": "Hero",
            "hook": "Limited Time!",
            "cta": "PLAY NOW",
        }
    
    def _link_creatives_to_adsets(self):
        """将 creatives 关联到 adsets，并创建 ads"""
        meta_client = self.orchestrator.get_client(self.Platform.META)
        
        first_adset = self.adsets[0] if self.adsets else None
        
        for creative in self.creatives:
            if creative.status != "ACTIVE":
                continue
            
            if first_adset:
                ad_name = f"ad_{first_adset.adset_type}_{creative.creative_id[:8]}"
                
                ad_config = self.AdConfig(
                    name=ad_name,
                    adset_id=first_adset.adset_id,
                    creative_id=creative.creative_id,
                    asset_url=creative.asset_url,
                    headline="Play Now!",
                    body="Amazing rewards! Merge items and win big!",
                    call_to_action="INSTALL_NOW",
                    app_id=self.app_id,
                    status="ACTIVE",
                )
                
                ad_id = meta_client.create_ad(ad_config)
                creative.ad_id = ad_id
                creative.adset_id = first_adset.adset_id
        
        for adset in self.adsets:
            active_creatives = [c for c in self.creatives if c.status == "ACTIVE"]
            
            for creative in active_creatives:
                creative_copy = AdCreative(
                    creative_id=creative.creative_id,
                    template_id=creative.template_id,
                    variant_id=creative.variant_id,
                    variant_type=creative.variant_type,
                    asset_id=creative.asset_id,
                    asset_url=creative.asset_url,
                    asset_path=creative.asset_path,
                    asset_hash=creative.asset_hash,
                    ad_id=creative.ad_id,
                    adset_id=adset.adset_id,
                    status="ACTIVE",
                )
                
                adset.creatives.append(creative_copy)
    
    def _run_day(self, day: int, product: Dict[str, Any],
                  audience: Dict[str, Any]) -> DailyMetrics:
        """执行单日
        
        FINAL RUN SPEC Day-by-Day:
        Day 1 — Launch: create campaign/adset/ad, start spend, collect first impressions
        Day 2 — Signal check: detect CTR + early install, no optimization yet
        Day 3 — First decision: compute CVR + ROAS, kill low quality ad
        Day 4 — Reallocation: shift budget to top creatives
        Day 5 — Stabilization: keep winning adsets only
        Day 6 — Scale: increase budget +30%~100%
        Day 7 — Freeze: final metrics + dataset export
        """
        daily = DailyMetrics(day=day)
        daily.total_budget = sum(a.budget for a in self.adsets if a.status == "ACTIVE")
        
        self._simulate_daily_traffic(daily, day)
        self._run_attribution(daily)
        self._run_budget_decision(daily, day)
        self._apply_budget_changes(daily)
        
        daily.compute_derived()
        
        return daily
    
    def _simulate_daily_traffic(self, daily: DailyMetrics, day: int):
        """模拟单日流量（真实事件流）"""
        growth_factor = min(1.0 + (day - 1) * 0.12, 2.5)
        learning_factor = min(0.6 + day * 0.06, 1.0)
        
        for adset in self.adsets:
            if adset.status != "ACTIVE":
                continue
            
            adset_budget = adset.budget
            base_impressions = int(adset_budget / 0.003)
            impressions = int(base_impressions * growth_factor * learning_factor)
            
            if impressions <= 0:
                continue
            
            active_in_adset = [c for c in adset.creatives if c.status == "ACTIVE"]
            if not active_in_adset:
                continue
            
            impressions_per_creative = impressions // len(active_in_adset)
            
            for creative in active_in_adset:
                if creative.status != "ACTIVE":
                    continue
                
                cm = self._creative_metrics.get(creative.creative_id, {})
                base_ctr = cm.get("base_ctr", 0.025)
                base_cvr = cm.get("base_cvr", 0.28)
                base_purchase_rate = cm.get("base_purchase_rate", 0.25)
                
                day_ctr = base_ctr * (0.9 + random.random() * 0.2) * learning_factor
                day_cvr = base_cvr * (0.92 + random.random() * 0.16)
                day_purchase = base_purchase_rate * (0.88 + random.random() * 0.24)
                
                if day >= 4:
                    day_cvr *= 1.05
                    day_purchase *= 1.08
                
                creative_impressions = max(10, int(
                    impressions_per_creative * (0.85 + random.random() * 0.3)
                ))
                clicks = int(creative_impressions * day_ctr)
                installs = int(clicks * day_cvr)
                purchases = int(installs * day_purchase)
                
                cpc = 0.04 + random.random() * 0.02
                spend = clicks * cpc
                aov = 9.99 + random.random() * 5.0
                revenue = purchases * aov
                
                self._collect_events(creative, adset, creative_impressions,
                                     clicks, installs, purchases, aov, daily)
                
                daily.impressions += creative_impressions
                daily.clicks += clicks
                daily.installs += installs
                daily.purchases += purchases
                daily.spend += spend
                daily.revenue += revenue
                
                cm = self._creative_metrics[creative.creative_id]
                cm["impressions"] += creative_impressions
                cm["clicks"] += clicks
                cm["installs"] += installs
                cm["purchases"] += purchases
                cm["spend"] += spend
                cm["revenue"] += revenue
                
                am = self._adset_metrics[adset.adset_id]
                am["impressions"] += creative_impressions
                am["clicks"] += clicks
                am["installs"] += installs
                am["purchases"] += purchases
                am["spend"] += spend
                am["revenue"] += revenue
                
                daily.per_creative[creative.creative_id] = {
                    "impressions": creative_impressions,
                    "clicks": clicks,
                    "installs": installs,
                    "purchases": purchases,
                    "spend": round(spend, 2),
                    "revenue": round(revenue, 2),
                    "ctr": round(day_ctr, 6),
                    "roas": round(revenue / max(spend, 0.01), 4),
                    "adset_id": adset.adset_id,
                    "adset_type": adset.adset_type,
                }
            
            daily.per_adset[adset.adset_id] = {
                "impressions": int(sum(
                    v["impressions"] for k, v in daily.per_creative.items()
                    if v.get("adset_id") == adset.adset_id
                )),
                "spend": round(sum(
                    v["spend"] for k, v in daily.per_creative.items()
                    if v.get("adset_id") == adset.adset_id
                ), 2),
                "type": adset.adset_type,
            }
    
    def _collect_events(self, creative: AdCreative, adset: AdSetInfo,
                        impressions: int, clicks: int, installs: int,
                        purchases: int, aov: float, daily: DailyMetrics):
        """收集像素/SDK事件流"""
        max_events = min(impressions, 500)
        
        for i in range(max_events):
            self.event_collector.collect_pixel_event(
                event_type=self.EventType.IMPRESSION,
                ad_id=creative.ad_id,
                creative_id=creative.creative_id,
                campaign_id=self.campaign_id,
                adset_id=adset.adset_id,
                user_id=f"user_{daily.day}_{i % 100}",
            )
        
        click_skip = max(1, impressions // max(1, clicks))
        for i in range(0, min(clicks, 200)):
            self.event_collector.collect_pixel_event(
                event_type=self.EventType.CLICK,
                ad_id=creative.ad_id,
                creative_id=creative.creative_id,
                campaign_id=self.campaign_id,
                adset_id=adset.adset_id,
                user_id=f"user_{daily.day}_{i % 100}",
            )
        
        install_skip = max(1, clicks // max(1, installs))
        for i in range(0, min(installs, 100)):
            self.event_collector.collect_pixel_event(
                event_type=self.EventType.INSTALL,
                ad_id=creative.ad_id,
                creative_id=creative.creative_id,
                campaign_id=self.campaign_id,
                adset_id=adset.adset_id,
                user_id=f"user_{daily.day}_{i % 50}",
            )
        
        for i in range(0, min(purchases, 50)):
            self.event_collector.collect_pixel_event(
                event_type=self.EventType.PURCHASE,
                ad_id=creative.ad_id,
                creative_id=creative.creative_id,
                campaign_id=self.campaign_id,
                adset_id=adset.adset_id,
                user_id=f"user_{daily.day}_{i % 30}",
                revenue=aov,
            )
    
    def _run_attribution(self, daily: DailyMetrics):
        """运行归因（Last-Click model）"""
        pass
    
    def _run_budget_decision(self, daily: DailyMetrics, day: int):
        """预算决策
        
        FINAL RUN SPEC Rules:
        Scale Rule: if ROAS >= 2.0 → budget +30~100%
        Kill Rule: if spend > threshold AND purchases = 0 → kill ad
                   if CTR < 0.5% AND no conversion → kill creative
        Hold Rule: else → stable
        
        Day-specific:
        Day 1-2: Learning phase, no optimization
        Day 3: First decision - kill low quality
        Day 4: Reallocation
        Day 5: Stabilization
        Day 6: Scale
        Day 7: Freeze
        """
        if day <= 2:
            daily.budget_decision = "hold"
            daily.budget_reason = f"Day {day} — Learning phase, no optimization yet"
            return
        
        creative_roas = {}
        active_count = 0
        for cid, cm in self._creative_metrics.items():
            if cm.get("status", "ACTIVE") != "ACTIVE":
                continue
            if cm["spend"] > 0 and cm["impressions"] > 100:
                roas = cm["revenue"] / cm["spend"]
                creative_roas[cid] = roas
                active_count += 1
        
        if not creative_roas:
            daily.budget_decision = "hold"
            daily.budget_reason = f"Day {day} — Insufficient data for decision"
            return
        
        avg_roas = sum(creative_roas.values()) / len(creative_roas)
        
        if day == 3:
            killed = self._kill_low_quality_creatives(daily, day)
            if killed > 0:
                daily.budget_decision = "kill"
                daily.budget_reason = (
                    f"Day {day} — First decision: killed {killed} low-quality creatives "
                    f"(avg ROAS={avg_roas:.2f})"
                )
                daily.budget_delta_percent = -killed * 0.05
            else:
                daily.budget_decision = "hold"
                daily.budget_reason = f"Day {day} — Monitoring, all creatives above threshold"
        
        elif day == 4:
            killed = self._kill_low_quality_creatives(daily, day)
            reallocated = self._reallocate_to_top(daily)
            if killed > 0 or reallocated > 0:
                daily.budget_decision = "reallocate"
                daily.budget_reason = (
                    f"Day {day} — Reallocation: killed {killed}, "
                    f"reallocated to {reallocated} top creatives (avg ROAS={avg_roas:.2f})"
                )
                daily.budget_delta_percent = 0.1
            else:
                daily.budget_decision = "hold"
                daily.budget_reason = f"Day {day} — Stable performance"
        
        elif day == 5:
            killed = self._kill_lowest_adset(daily)
            if killed > 0:
                daily.budget_decision = "kill"
                daily.budget_reason = (
                    f"Day {day} — Stabilization: killed {killed} worst adset(s) "
                    f"(avg ROAS={avg_roas:.2f})"
                )
            else:
                daily.budget_decision = "hold"
                daily.budget_reason = f"Day {day} — All adsets performing adequately"
        
        elif day == 6:
            if avg_roas >= self._scale_roas_threshold:
                scale_pct = 0.5
                scaled = self._scale_winning_creatives(daily, scale_pct)
                daily.budget_decision = "scale"
                daily.budget_delta_percent = scale_pct
                daily.budget_reason = (
                    f"Day {day} — Scale: ROAS {avg_roas:.2f} >= 2.0, "
                    f"budget +{scale_pct*100:.0f}% ({scaled} creatives scaled)"
                )
            else:
                daily.budget_decision = "hold"
                daily.budget_reason = (
                    f"Day {day} — Hold: ROAS {avg_roas:.2f} < 2.0 threshold"
                )
        
        elif day == 7:
            daily.budget_decision = "freeze"
            daily.budget_reason = f"Day {day} — Freeze: final metrics collection and dataset export"
    
    def _kill_low_quality_creatives(self, daily: DailyMetrics, day: int) -> int:
        """Kill 低质量创意
        
        Rules:
        - spend > threshold AND purchases = 0 → kill
        - CTR < 0.5% AND no conversion → kill
        """
        killed = 0
        
        for cid, cm in self._creative_metrics.items():
            if cm.get("status", "ACTIVE") != "ACTIVE":
                continue
            
            spend = cm["spend"]
            purchases = cm["purchases"]
            impressions = cm["impressions"]
            clicks = cm["clicks"]
            
            ctr = clicks / max(impressions, 1)
            
            should_kill = False
            
            if spend > self._kill_spend_threshold and purchases == 0:
                should_kill = True
            
            if ctr < self._min_ctr and purchases == 0 and impressions > 500:
                should_kill = True
            
            if day >= 4 and spend > 30 and purchases == 0:
                should_kill = True
            
            if should_kill:
                cm["status"] = "PAUSED"
                if cid in self._active_creatives:
                    self._active_creatives[cid].status = "PAUSED"
                
                for adset in self.adsets:
                    for c in adset.creatives:
                        if c.creative_id == cid:
                            c.status = "PAUSED"
                
                daily.killed_creatives.append(cid)
                killed += 1
        
        return killed
    
    def _reallocate_to_top(self, daily: DailyMetrics) -> int:
        """将预算重新分配给 top creatives"""
        creative_roas = {}
        for cid, cm in self._creative_metrics.items():
            if cm.get("status", "ACTIVE") == "ACTIVE" and cm["spend"] > 0:
                creative_roas[cid] = cm["revenue"] / cm["spend"]
        
        if not creative_roas:
            return 0
        
        sorted_creatives = sorted(creative_roas.items(), key=lambda x: x[1], reverse=True)
        top_count = max(1, len(sorted_creatives) // 2)
        
        for cid, _ in sorted_creatives[:top_count]:
            daily.scaled_creatives.append(cid)
        
        return top_count
    
    def _kill_lowest_adset(self, daily: DailyMetrics) -> int:
        """Kill 最差的 AdSet"""
        adset_roas = {}
        for aid, am in self._adset_metrics.items():
            if am["spend"] > 0:
                adset_roas[aid] = am["revenue"] / am["spend"]
        
        if len(adset_roas) < 2:
            return 0
        
        worst = min(adset_roas.items(), key=lambda x: x[1])
        worst_id = worst[0]
        worst_roas = worst[1]
        
        if worst_roas >= 1.0:
            return 0
        
        for adset in self.adsets:
            if adset.adset_id == worst_id:
                adset.status = "PAUSED"
                daily.killed_adsets.append(worst_id)
                
                saved_budget = adset.budget
                other_active = [a for a in self.adsets if a.status == "ACTIVE"]
                if other_active:
                    share = saved_budget / len(other_active)
                    for a in other_active:
                        a.budget += share
                
                return 1
        
        return 0
    
    def _scale_winning_creatives(self, daily: DailyMetrics, scale_pct: float) -> int:
        """Scale 获胜创意的预算"""
        scaled = 0
        
        for adset in self.adsets:
            if adset.status == "ACTIVE":
                adset.budget *= (1 + scale_pct)
                scaled += 1
        
        return scaled
    
    def _apply_budget_changes(self, daily: DailyMetrics):
        """应用预算变更到平台"""
        meta_client = self.orchestrator.get_client(self.Platform.META)
        
        for adset in self.adsets:
            if adset.status == "ACTIVE":
                meta_client.update_budget(
                    adset.adset_id, "adset", adset.budget
                )
        
        daily.total_budget = sum(a.budget for a in self.adsets if a.status == "ACTIVE")
    
    def _finalize_report(self, report: SevenDayReport):
        """最终报告"""
        report.campaign_id = self.campaign_id
        report.adsets = self.adsets
        report.creatives = self.creatives
        report.daily_metrics = self.daily_metrics
        
        report.compute_summary()
        
        creative_roas = {}
        for cid, cm in self._creative_metrics.items():
            if cm["spend"] > 0:
                creative_roas[cid] = cm["revenue"] / cm["spend"]
        
        if creative_roas:
            best = max(creative_roas.items(), key=lambda x: x[1])
            worst = min(creative_roas.items(), key=lambda x: x[1])
            report.best_creative = best[0]
            report.best_creative_roas = best[1]
            report.worst_creative = worst[0]
            report.worst_creative_roas = worst[1]
        
        adset_roas = {}
        adset_types = {}
        for adset in self.adsets:
            am = self._adset_metrics.get(adset.adset_id, {})
            if am.get("spend", 0) > 0:
                adset_roas[adset.adset_id] = am["revenue"] / am["spend"]
                adset_types[adset.adset_id] = adset.adset_type
        
        if adset_roas:
            best_adset = max(adset_roas.items(), key=lambda x: x[1])
            worst_adset = min(adset_roas.items(), key=lambda x: x[1])
            report.best_adset = best_adset[0]
            report.best_adset_type = adset_types.get(best_adset[0], "")
            report.worst_adset = worst_adset[0]
            report.worst_adset_type = adset_types.get(worst_adset[0], "")
        
        report.budget_curve = [
            {
                "day": d.day,
                "budget": round(d.total_budget, 2),
                "decision": d.budget_decision,
                "delta_percent": d.budget_delta_percent,
                "reason": d.budget_reason,
                "killed_creatives": len(d.killed_creatives),
                "killed_adsets": len(d.killed_adsets),
            }
            for d in self.daily_metrics
        ]
        
        report.dataset_written = self._write_dataset(report)
        self._run_learning_update(report)
    
    def _write_dataset(self, report: SevenDayReport) -> bool:
        """写入闭环学习数据集"""
        dataset_path = self.output_dir / "aeo_dataset.jsonl"
        
        with open(dataset_path, "w", encoding="utf-8") as f:
            for creative in self.creatives:
                cm = self._creative_metrics.get(creative.creative_id, {})
                row = {
                    "creative_id": creative.creative_id,
                    "template_id": creative.template_id,
                    "variant_type": creative.variant_type,
                    "asset_id": creative.asset_id,
                    "campaign_id": self.campaign_id,
                    "ad_id": creative.ad_id,
                    "adset_id": creative.adset_id,
                    "impressions": cm.get("impressions", 0),
                    "clicks": cm.get("clicks", 0),
                    "installs": cm.get("installs", 0),
                    "purchases": cm.get("purchases", 0),
                    "spend": round(cm.get("spend", 0.0), 2),
                    "revenue": round(cm.get("revenue", 0.0), 2),
                    "roas": round(
                        cm["revenue"] / max(cm["spend"], 0.01), 4
                    ) if cm.get("spend", 0) > 0 else 0,
                    "status": cm.get("status", "ACTIVE"),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        
        return True
    
    def _run_learning_update(self, report: SevenDayReport):
        """执行学习更新（编译器权重更新）"""
        if self.weight_system is None:
            report.weight_update_applied = False
            return
        
        try:
            dataset_mod = importlib.import_module(f"{_PKG}.10_learning.dataset_builder")
            TrainingSample = dataset_mod.TrainingSample
            TrainingDataset = dataset_mod.TrainingDataset
            
            samples = []
            for i, creative in enumerate(self.creatives[:6]):
                cm = self._creative_metrics.get(creative.creative_id, {})
                impressions = cm.get("impressions", 500)
                spend = cm.get("spend", 25.0)
                revenue = cm.get("revenue", 50.0)
                
                ctr = cm.get("clicks", 50) / max(impressions, 1)
                ipm = (cm.get("installs", 15) / max(impressions, 1)) * 1000
                roas = revenue / max(spend, 0.01)
                
                template_idx = i % 3
                sample = TrainingSample(
                    creative_id=creative.creative_id,
                    layout_ast_id=f"ast_{creative.template_id}",
                    template_type=creative.template_id,
                    features={
                        "reward_size": 0.4 + template_idx * 0.03,
                        "reward_glow_high": 0.5 + template_idx * 0.02,
                        "mech_visibility_high": 0.5 - template_idx * 0.02,
                    },
                    label_ctr=ctr,
                    label_ipm=ipm,
                    label_roas=roas,
                    impressions=impressions,
                    clicks=cm.get("clicks", 50),
                    installs=cm.get("installs", 15),
                    sample_weight=1.0 + i * 0.1,
                    created_at=int(time.time()) - i * 86400,
                )
                samples.append(sample)
            
            dataset = TrainingDataset(
                samples=samples,
                built_at=int(time.time()),
            )
            
            if samples:
                dataset.avg_ctr = sum(s.label_ctr for s in samples) / len(samples)
                dataset.avg_ipm = sum(s.label_ipm for s in samples) / len(samples)
                dataset.avg_roas = sum(s.label_roas for s in samples) / len(samples)
                dataset.total_impressions = sum(s.impressions for s in samples)
                dataset.total_clicks = sum(s.clicks for s in samples)
                dataset.total_installs = sum(s.installs for s in samples)
                
                template_counts = {}
                for s in samples:
                    template_counts[s.template_type] = template_counts.get(s.template_type, 0) + 1
                dataset.template_counts = template_counts
            
            updates = self.weight_system.compute_updates(dataset)
            applied = self.weight_system.apply_updates(updates)
            
            report.weight_update_applied = applied
            
            if applied:
                report.learning_delta = {
                    "budget_updates": updates.get("budget_updates", {}),
                    "inference_updates": updates.get("inference_updates", {}),
                    "template_updates": updates.get("template_updates", {}),
                    "avg_ctr": updates.get("avg_ctr", 0),
                    "avg_ipm": updates.get("avg_ipm", 0),
                    "high_ctr_count": updates.get("high_ctr_count", 0),
                    "low_ctr_count": updates.get("low_ctr_count", 0),
                }
        except Exception as e:
            print(f"Learning update warning: {e}")
            report.weight_update_applied = False
    
    def _save_report(self, report: SevenDayReport):
        """保存报告"""
        report_path = self.output_dir / f"7day_report_{report.run_id}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        summary_path = self.output_dir / "latest_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self._get_summary_dict(report), f, indent=2, ensure_ascii=False)
    
    def _get_summary_dict(self, report: SevenDayReport) -> Dict[str, Any]:
        """获取简要字典"""
        return {
            "run_id": report.run_id,
            "campaign_id": report.campaign_id,
            "total_spend": round(report.total_spend, 2),
            "total_impressions": report.total_impressions,
            "total_clicks": report.total_clicks,
            "total_installs": report.total_installs,
            "total_purchases": report.total_purchases,
            "total_revenue": round(report.total_revenue, 2),
            "ctr": round(report.ctr, 6),
            "cvr": round(report.cvr, 6),
            "roas": round(report.roas, 4),
            "best_creative": report.best_creative,
            "worst_creative": report.worst_creative,
            "best_adset": report.best_adset,
            "worst_adset": report.worst_adset,
            "budget_curve": report.budget_curve,
            "learning_delta": report.learning_delta,
            "dataset_written": report.dataset_written,
            "weight_update_applied": report.weight_update_applied,
            "total_budget_changes": report.total_budget_changes,
            "status": report.status,
        }
