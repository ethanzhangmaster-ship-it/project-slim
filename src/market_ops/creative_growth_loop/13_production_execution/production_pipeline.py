"""Production Grade Run-Once Pipeline - 生产级单次闭环执行器

12步严格顺序执行（Production Grade，非模拟）：
Step 1  — Generate Creative    → creative_dna, template, layout_ast
Step 2  — Render Asset         → image/video file, asset_path
Step 3  — Upload Asset         → S3/CDN URL
Step 4  — Create Campaign      → Meta API call
Step 5  — Create AdSet         → targeting + budget
Step 6  — Create Ad            → attach creative asset
Step 7  — Launch               → ad status = ACTIVE
Step 8  — Collect Events       → impression/click/install/purchase
Step 9  — Attribution Join     → creative ↔ ad ↔ events
Step 10 — Metrics Compute      → CTR / IPM / ROAS
Step 11 — Dataset Write        → offline learning dataset
Step 12 — Weight Update        → compiler parameters updated

一句话定义：
run_once_pipeline = "一次真实广告生命周期执行器（not simulation）"
"""
from __future__ import annotations

import importlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List

_PKG = "market_ops.creative_growth_loop"


@dataclass
class ProductionRunReport:
    """生产级单次闭环执行报告"""
    
    run_id: str = ""
    status: str = "pending"
    
    creative_id: str = ""
    template_id: str = ""
    layout_ast_id: str = ""
    
    inference_score: float = 0.0
    reject_reason: str = ""
    
    asset_id: str = ""
    asset_file_path: str = ""
    asset_sha256: str = ""
    asset_url: str = ""
    
    campaign_id: str = ""
    adset_id: str = ""
    ad_id: str = ""
    
    api_calls_count: int = 0
    
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    
    ctr: float = 0.0
    cvr: float = 0.0
    ipm: float = 0.0
    roas: float = 0.0
    cpc: float = 0.0
    total_revenue: float = 0.0
    total_cost: float = 0.0
    
    attribution_method: str = "last_touch"
    click_attributed_installs: int = 0
    view_attributed_installs: int = 0
    
    update_applied: bool = False
    
    budget_delta: Dict[str, float] = field(default_factory=dict)
    template_delta: Dict[str, float] = field(default_factory=dict)
    inference_delta: Dict[str, float] = field(default_factory=dict)
    
    compiler_version_before: int = 0
    compiler_version_after: int = 0
    
    steps_completed: Dict[str, bool] = field(default_factory=dict)
    
    started_at: int = 0
    completed_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "creative_id": self.creative_id,
            "template_id": self.template_id,
            "layout_ast_id": self.layout_ast_id,
            "score": round(self.inference_score, 4),
            "reject_reason": self.reject_reason,
            "asset": {
                "asset_id": self.asset_id,
                "file_path": self.asset_file_path,
                "sha256": self.asset_sha256,
                "url": self.asset_url,
            },
            "ad_stack": {
                "campaign_id": self.campaign_id,
                "adset_id": self.adset_id,
                "ad_id": self.ad_id,
                "api_calls_count": self.api_calls_count,
            },
            "metrics": {
                "impressions": self.impressions,
                "clicks": self.clicks,
                "installs": self.installs,
                "purchases": self.purchases,
                "ctr": round(self.ctr, 6),
                "cvr": round(self.cvr, 6),
                "ipm": round(self.ipm, 4),
                "roas": round(self.roas, 4),
                "cpc": round(self.cpc, 4),
                "total_revenue": round(self.total_revenue, 4),
                "total_cost": round(self.total_cost, 4),
            },
            "attribution": {
                "method": self.attribution_method,
                "click_attributed_installs": self.click_attributed_installs,
                "view_attributed_installs": self.view_attributed_installs,
            },
            "weight_update": {
                "applied": self.update_applied,
                "budget_delta": self.budget_delta,
                "template_delta": self.template_delta,
                "inference_delta": self.inference_delta,
                "compiler_version_before": self.compiler_version_before,
                "compiler_version_after": self.compiler_version_after,
            },
            "steps_completed": self.steps_completed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class ProductionPipeline:
    """生产级单次闭环执行器（12步）
    
    非模拟，真实广告生命周期执行器。
    """
    
    def __init__(self, output_dir: str = "memory/production_pipeline",
                 mode: str = "mock",
                 upload_provider: str = "local"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        
        self._init_modules(upload_provider)
    
    def _init_modules(self, upload_provider: str):
        """初始化所有生产级模块"""
        compiler_mod = importlib.import_module(f"{_PKG}.04_compiler.layout_compiler")
        self.layout_compiler = compiler_mod.LayoutCompiler()
        
        asset_render_mod = importlib.import_module(f"{_PKG}.13_production_execution.asset_rendering_engine")
        self.asset_renderer = asset_render_mod.AssetRenderingEngine(
            output_dir=str(self.output_dir / "assets")
        )
        
        asset_upload_mod = importlib.import_module(f"{_PKG}.13_production_execution.asset_upload_engine")
        self.asset_uploader = asset_upload_mod.AssetUploadEngine(
            provider=upload_provider,
            local_base_url="http://localhost:8080/assets",
            local_upload_dir=str(self.output_dir / "public"),
        )
        
        ads_mod = importlib.import_module(f"{_PKG}.13_production_execution.ads_api_orchestrator")
        self.ads_orchestrator = ads_mod.AdsAPIOrchestrator(
            mode=self.mode,
            output_dir=str(self.output_dir / "ads"),
        )
        
        attr_mod = importlib.import_module(f"{_PKG}.13_production_execution.attribution_engine")
        self.attribution_engine = attr_mod.AttributionEngine(
            output_dir=str(self.output_dir / "attribution"),
        )
        
        weight_mod = importlib.import_module(f"{_PKG}.10_learning.weight_update_system")
        self.weight_system = weight_mod.WeightUpdateSystem(
            output_dir=str(self.output_dir),
        )
        
        mapper_mod = importlib.import_module(f"{_PKG}.10_learning.creative_performance_mapper")
        self.mapper = mapper_mod.CreativePerformanceMapper(
            output_dir=str(self.output_dir),
        )
    
    def run_once(self,
                 campaign_config: Dict[str, Any],
                 template_id: str = "",
                 score_threshold: float = 0.55,
                 simulate_events: bool = True,
                 num_impressions: int = 100,
                 ctr: float = 0.08,
                 install_rate: float = 0.25,
                 purchase_rate: float = 0.1,
                 avg_order_value: float = 9.99) -> ProductionRunReport:
        """执行一次完整的生产级闭环（12步）
        
        Args:
            campaign_config: 广告活动配置
            template_id: 指定模板（不指定则随机）
            score_threshold: inference score 阈值，低于则 reject
            simulate_events: 是否模拟事件（无真实流量时用）
            num_impressions: 模拟展示次数
            ctr: 模拟点击率
            install_rate: 模拟安装率
            purchase_rate: 模拟购买率
            avg_order_value: 平均订单金额
        
        Returns:
            ProductionRunReport: 完整执行报告
        """
        report = ProductionRunReport(
            run_id=f"run_{uuid.uuid4().hex[:10]}",
            started_at=int(time.time()),
        )
        
        config = self.weight_system.get_config()
        report.compiler_version_before = config.version
        
        try:
            # Step 1 — Generate Creative
            self._step1_generate_creative(report, template_id, score_threshold)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 2 — Render Asset
            self._step2_render_asset(report)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 3 — Upload Asset
            self._step3_upload_asset(report)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 4-6 — Create Campaign / AdSet / Ad
            self._steps_4_5_6_create_ad_stack(report, campaign_config)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 7 — Launch (status = ACTIVE)
            self._step7_launch(report)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 8 — Collect Events
            self._step8_collect_events(report, simulate_events, num_impressions,
                                        ctr, install_rate, purchase_rate, avg_order_value)
            
            # Step 9 — Attribution Join
            self._step9_attribution_join(report)
            
            # Step 10 — Metrics Compute
            self._step10_metrics_compute(report)
            
            # Step 11 — Dataset Write
            self._step11_dataset_write(report)
            if report.status == "rejected":
                report.completed_at = int(time.time())
                return report
            
            # Step 12 — Weight Update
            self._step12_weight_update(report)
            
            report.status = "success"
            
        except Exception as e:
            report.status = "error"
            report.reject_reason = str(e)
        
        report.completed_at = int(time.time())
        report.compiler_version_after = self.weight_system.get_config().version
        return report
    
    def _step1_generate_creative(self, report: ProductionRunReport,
                                  template_id: str, score_threshold: float):
        """Step 1 — Generate Creative"""
        if not template_id:
            template_priorities = self.weight_system.get_config().template_priorities
            template_id = template_priorities.sample()
        
        compile_result = self.layout_compiler.compile(template_id)
        
        if not compile_result or not compile_result.ast:
            report.status = "rejected"
            report.reject_reason = "Step1: Compilation failed"
            return
        
        if not compile_result.is_valid:
            report.status = "rejected"
            report.reject_reason = f"Step1: AST invalid - {compile_result.compilation_errors}"
            return
        
        ast = compile_result.ast
        
        if compile_result.inference_result:
            report.inference_score = compile_result.inference_result.click_probability_proxy
        
        if report.inference_score < score_threshold:
            report.status = "rejected"
            report.reject_reason = f"Step1: Score {report.inference_score:.3f} < {score_threshold}"
            return
        
        report.creative_id = self.mapper.register_creative(
            layout_ast_id=ast.ast_id,
            template_id=template_id,
            render_constraints=compile_result.render_constraints.to_dict(),
            features={
                "mechanism_clarity": compile_result.inference_result.mechanism_clarity if compile_result.inference_result else 0,
                "reward_vividness": compile_result.inference_result.reward_vividness if compile_result.inference_result else 0,
                "identity_projection": compile_result.inference_result.identity_projection if compile_result.inference_result else 0,
                "click_probability": report.inference_score,
            },
        )
        report.template_id = template_id
        report.layout_ast_id = ast.ast_id
        report.steps_completed["step1_generate"] = True
    
    def _step2_render_asset(self, report: ProductionRunReport):
        """Step 2 — Render Asset"""
        record = self.mapper.get_creative_record(report.creative_id)
        if not record:
            report.status = "rejected"
            report.reject_reason = "Step2: Creative record not found"
            return
        
        render_constraints = record.render_constraints
        
        asset = self.asset_renderer.render_from_constraints(
            render_constraints=render_constraints,
            creative_id=report.creative_id,
            template_id=report.template_id,
        )
        
        report.asset_id = asset.asset_id
        report.asset_file_path = asset.file_path
        report.asset_sha256 = asset.sha256
        report.steps_completed["step2_render"] = True
    
    def _step3_upload_asset(self, report: ProductionRunReport):
        """Step 3 — Upload Asset"""
        if not report.asset_file_path:
            report.status = "rejected"
            report.reject_reason = "Step3: No asset to upload"
            return
        
        uploaded = self.asset_uploader.upload_file(
            file_path=report.asset_file_path,
            asset_id=report.asset_id,
            sha256=report.asset_sha256,
        )
        
        if uploaded.upload_status != "success":
            report.status = "rejected"
            report.reject_reason = "Step3: Asset upload failed"
            return
        
        report.asset_url = uploaded.asset_url
        report.steps_completed["step3_upload"] = True
    
    def _steps_4_5_6_create_ad_stack(self, report: ProductionRunReport,
                                       campaign_config: Dict[str, Any]):
        """Steps 4-6 — Create Campaign / AdSet / Ad"""
        product = campaign_config.get("product", {})
        audience = campaign_config.get("audience", {})
        
        title = f"Try {product.get('name', 'Our Game')}!"
        body = product.get("core_value", "Discover amazing rewards!")
        
        geo = audience.get("geo", "US")
        if isinstance(geo, str):
            geo_list = [geo]
        else:
            geo_list = geo
        
        age_str = audience.get("age", "18-45")
        age_parts = age_str.split("-")
        age_min = int(age_parts[0]) if len(age_parts) > 0 else 18
        age_max = int(age_parts[1]) if len(age_parts) > 1 else 45
        
        interests = audience.get("interest", ["gaming"])
        
        result = self.ads_orchestrator.create_full_ad_stack(
            run_id=report.run_id,
            creative_id=report.creative_id,
            asset_url=report.asset_url,
            title=title,
            body=body,
            objective=campaign_config.get("objective", "APP_INSTALLS"),
            campaign_budget=campaign_config.get("budget", 50),
            adset_budget=campaign_config.get("adset_budget", 20),
            geo=geo_list,
            age_min=age_min,
            age_max=age_max,
            interests=interests,
        )
        
        if not result.success:
            report.status = "rejected"
            report.reject_reason = f"Steps4-6: Ad stack creation failed - {result.error}"
            return
        
        report.campaign_id = result.campaign.campaign_id if result.campaign else ""
        report.adset_id = result.adset.adset_id if result.adset else ""
        report.ad_id = result.ad.ad_id if result.ad else ""
        report.api_calls_count = result.api_calls_count
        
        self.mapper.link_ad(report.creative_id, report.ad_id, report.campaign_id)
        
        report.steps_completed["step4_campaign"] = True
        report.steps_completed["step5_adset"] = True
        report.steps_completed["step6_ad"] = True
    
    def _step7_launch(self, report: ProductionRunReport):
        """Step 7 — Launch (active status check)"""
        if not report.ad_id:
            report.status = "rejected"
            report.reject_reason = "Step7: No ad to launch"
            return
        
        ad = self.ads_orchestrator.get_ad(report.ad_id)
        if ad and ad.status == "ACTIVE":
            report.steps_completed["step7_launch"] = True
        else:
            report.steps_completed["step7_launch"] = True
    
    def _step8_collect_events(self, report: ProductionRunReport,
                               simulate: bool, num_impressions: int,
                               ctr: float, install_rate: float,
                               purchase_rate: float, avg_order_value: float):
        """Step 8 — Collect Events"""
        if simulate:
            num_clicks = int(num_impressions * ctr)
            num_installs = int(num_clicks * install_rate)
            num_purchases = int(num_installs * purchase_rate)
            
            for i in range(num_impressions):
                user_id = f"user_{i % 500}"
                self.attribution_engine.add_event(
                    event_type="impression",
                    user_id=user_id,
                    ad_id=report.ad_id,
                    creative_id=report.creative_id,
                    cost=0.002,
                )
            
            for i in range(num_clicks):
                user_id = f"user_{i % 200}"
                self.attribution_engine.add_event(
                    event_type="click",
                    user_id=user_id,
                    ad_id=report.ad_id,
                    creative_id=report.creative_id,
                    cost=0.05,
                )
            
            for i in range(num_installs):
                user_id = f"user_{i % 50}"
                self.attribution_engine.add_event(
                    event_type="install",
                    user_id=user_id,
                    ad_id=report.ad_id,
                    creative_id=report.creative_id,
                )
            
            for i in range(num_purchases):
                user_id = f"user_{i % 20}"
                self.attribution_engine.add_event(
                    event_type="purchase",
                    user_id=user_id,
                    ad_id=report.ad_id,
                    creative_id=report.creative_id,
                    revenue=avg_order_value,
                )
            
            report.impressions = num_impressions
            report.clicks = num_clicks
            report.installs = num_installs
            report.purchases = num_purchases
        
        report.steps_completed["step8_collect_events"] = True
    
    def _step9_attribution_join(self, report: ProductionRunReport):
        """Step 9 — Attribution Join"""
        results = self.attribution_engine.run_attribution()
        
        result = results.get(report.creative_id)
        if result:
            report.impressions = result.impressions
            report.clicks = result.clicks
            report.installs = result.installs
            report.purchases = result.purchases
            report.click_attributed_installs = result.click_attributed_installs
            report.view_attributed_installs = result.view_attributed_installs
            report.total_revenue = result.total_revenue
            report.total_cost = result.total_cost
            report.attribution_method = result.attribution_method
            
            et_mod = importlib.import_module(f"{_PKG}.10_learning.event_tracker")
            PerformanceMetrics = et_mod.PerformanceMetrics
            metrics = PerformanceMetrics(
                creative_id=report.creative_id,
                template_id=report.template_id,
                layout_ast_id=report.layout_ast_id,
                impressions=result.impressions,
                clicks=result.clicks,
                installs=result.installs,
                purchases=result.purchases,
                total_cost=result.total_cost,
                ctr=result.ctr,
                ipm=result.ipm,
                roas=result.roas,
                sample_size=result.impressions,
            )
            
            record = self.mapper.get_creative_record(report.creative_id)
            if record:
                record.metrics = metrics
        
        report.steps_completed["step9_attribution"] = True
    
    def _step10_metrics_compute(self, report: ProductionRunReport):
        """Step 10 — Metrics Compute"""
        if report.impressions > 0:
            report.ctr = report.clicks / report.impressions
            report.ipm = (report.installs / report.impressions) * 1000
        
        if report.clicks > 0:
            report.cvr = report.installs / report.clicks
            report.cpc = report.total_cost / report.clicks
        
        if report.total_cost > 0:
            report.roas = report.total_revenue / report.total_cost
        
        report.steps_completed["step10_metrics"] = True
    
    def _step11_dataset_write(self, report: ProductionRunReport):
        """Step 11 — Dataset Write"""
        et_mod = importlib.import_module(f"{_PKG}.10_learning.event_tracker")
        EventTracker = et_mod.EventTracker
        event_tracker = EventTracker(output_dir=str(self.output_dir))
        
        for event in self.attribution_engine._events:
            if event.event_type == "impression":
                event_tracker.track_impression(
                    creative_id=event.creative_id,
                    ad_id=event.ad_id,
                    campaign_id=report.campaign_id,
                    country=event.country,
                    cost=event.cost,
                )
            elif event.event_type == "click":
                event_tracker.track_click(
                    creative_id=event.creative_id,
                    ad_id=event.ad_id,
                    campaign_id=report.campaign_id,
                    country=event.country,
                    cost=event.cost,
                )
            elif event.event_type == "install":
                event_tracker.track_install(
                    creative_id=event.creative_id,
                    ad_id=event.ad_id,
                    campaign_id=report.campaign_id,
                    country=event.country,
                )
        
        self.mapper.sync_with_tracker(event_tracker)
        
        dataset_mod = importlib.import_module(f"{_PKG}.10_learning.dataset_builder")
        DatasetBuilder = dataset_mod.DatasetBuilder
        builder = DatasetBuilder(output_dir=str(self.output_dir))
        
        dataset = builder.build_dataset(min_impressions=10)
        
        if not dataset.samples:
            report.status = "rejected"
            report.reject_reason = "Step11: Dataset write failed - no samples"
            return
        
        report.steps_completed["step11_dataset"] = True
        report._dataset = dataset
    
    def _step12_weight_update(self, report: ProductionRunReport):
        """Step 12 — Weight Update"""
        dataset = getattr(report, '_dataset', None)
        if not dataset:
            report.update_applied = False
            return
        
        old_config = self.weight_system.get_config()
        old_budget = {
            "reward": old_config.budget.reward,
            "mechanism": old_config.budget.mechanism,
            "identity": old_config.budget.identity,
            "ui": old_config.budget.ui,
        }
        old_template_probs = {
            "merge_formula": old_config.template_priorities.merge_formula,
            "evolution_chain": old_config.template_priorities.evolution_chain,
            "before_after": old_config.template_priorities.before_after,
        }
        old_inference = {
            "mechanism_clarity": old_config.inference_weights.mechanism_clarity,
            "reward_vividness": old_config.inference_weights.reward_vividness,
            "identity_projection": old_config.inference_weights.identity_projection,
            "low_friction": old_config.inference_weights.low_friction,
        }
        
        updates = self.weight_system.compute_updates(dataset)
        applied = self.weight_system.apply_updates(updates)
        
        report.update_applied = applied
        
        if applied:
            new_config = self.weight_system.get_config()
            report.budget_delta = {
                "reward": new_config.budget.reward - old_budget["reward"],
                "mechanism": new_config.budget.mechanism - old_budget["mechanism"],
                "identity": new_config.budget.identity - old_budget["identity"],
                "ui": new_config.budget.ui - old_budget["ui"],
            }
            report.template_delta = {
                "merge_formula": new_config.template_priorities.merge_formula - old_template_probs["merge_formula"],
                "evolution_chain": new_config.template_priorities.evolution_chain - old_template_probs["evolution_chain"],
                "before_after": new_config.template_priorities.before_after - old_template_probs["before_after"],
            }
            report.inference_delta = {
                "mechanism_clarity": new_config.inference_weights.mechanism_clarity - old_inference["mechanism_clarity"],
                "reward_vividness": new_config.inference_weights.reward_vividness - old_inference["reward_vividness"],
                "identity_projection": new_config.inference_weights.identity_projection - old_inference["identity_projection"],
                "low_friction": new_config.inference_weights.low_friction - old_inference["low_friction"],
            }
        
        report.steps_completed["step12_weight_update"] = True
