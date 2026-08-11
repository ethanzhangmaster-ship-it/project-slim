"""Production Grade Run-Once Pipeline 端到端测试

验证 12 步生产级闭环执行器。
"""
from __future__ import annotations

import json
import os
import sys
import importlib

_BASE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_BASE, "..", "..", ".."))
sys.path.insert(0, _SRC)

_PKG = "market_ops.creative_growth_loop"
_pipeline_mod = importlib.import_module(f"{_PKG}.13_production_execution.production_pipeline")
ProductionPipeline = _pipeline_mod.ProductionPipeline


def test_production_pipeline():
    """测试完整 12 步生产级 pipeline"""
    print("=" * 70)
    print("Production Grade Run-Once Pipeline - 端到端测试")
    print("=" * 70)
    
    output_dir = "memory/test_production_pipeline"
    
    pipeline = ProductionPipeline(
        output_dir=output_dir,
        mode="mock",
        upload_provider="local",
    )
    
    campaign_config = {
        "objective": "APP_INSTALLS",
        "budget": 50,
        "adset_budget": 20,
        "product": {
            "name": "Epic Quest",
            "core_value": "Win real rewards in this epic adventure!",
        },
        "audience": {
            "geo": ["US", "TW"],
            "age": "18-45",
            "interest": ["gaming", "apps"],
        },
    }
    
    print(f"\n[Init] Output dir: {output_dir}, Mode: mock")
    print()
    
    print("Starting Production Pipeline (12 steps)...")
    print()
    
    report = pipeline.run_once(
        campaign_config=campaign_config,
        score_threshold=0.45,
        simulate_events=True,
        num_impressions=500,
        ctr=0.10,
        install_rate=0.30,
        purchase_rate=0.30,
        avg_order_value=9.99,
    )
    
    report_dict = report.to_dict()
    
    print("=" * 70)
    print("12-Step Execution Status")
    print("=" * 70)
    
    steps = [
        ("Step 1  - Generate Creative", "step1_generate"),
        ("Step 2  - Render Asset", "step2_render"),
        ("Step 3  - Upload Asset", "step3_upload"),
        ("Step 4  - Create Campaign", "step4_campaign"),
        ("Step 5  - Create AdSet", "step5_adset"),
        ("Step 6  - Create Ad", "step6_ad"),
        ("Step 7  - Launch", "step7_launch"),
        ("Step 8  - Collect Events", "step8_collect_events"),
        ("Step 9  - Attribution Join", "step9_attribution"),
        ("Step 10 - Metrics Compute", "step10_metrics"),
        ("Step 11 - Dataset Write", "step11_dataset"),
        ("Step 12 - Weight Update", "step12_weight_update"),
    ]
    
    all_passed = True
    for step_name, step_key in steps:
        done = report.steps_completed.get(step_key, False)
        status = "[PASS]" if done else "[FAIL]"
        print(f"  {status}  {step_name}")
        if not done:
            all_passed = False
    
    print()
    print("=" * 70)
    print("Production Grade Constraints Verification")
    print("=" * 70)
    
    checks = []
    
    api_check = report.api_calls_count >= 1
    checks.append(("At least 1 real API call", api_check, f"{report.api_calls_count} calls"))
    
    asset_exists = report.asset_file_path and os.path.exists(report.asset_file_path)
    checks.append(("At least 1 real asset file", asset_exists, report.asset_file_path))
    
    event_count = len(pipeline.attribution_engine._events)
    event_check = event_count > 0
    checks.append(("At least 1 real event stream", event_check, f"{event_count} events"))
    
    attr_check = report.steps_completed.get("step9_attribution", False)
    checks.append(("At least 1 attribution join", attr_check, f"method={report.attribution_method}"))
    
    metrics_check = (report.ctr > 0 and report.ipm > 0 and report.roas > 0)
    checks.append(("Real CTR/IPM/ROAS computed", metrics_check,
                    f"CTR={report.ctr:.4f}, IPM={report.ipm:.2f}, ROAS={report.roas:.2f}"))
    
    ad_stack_check = bool(report.campaign_id and report.adset_id and report.ad_id)
    checks.append(("Real campaign/adset/ad IDs", ad_stack_check,
                    f"camp={report.campaign_id[:12]}... adset={report.adset_id[:12]}... ad={report.ad_id[:12]}..."))
    
    for check_name, passed, detail in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {check_name}")
        print(f"         -> {detail}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 70)
    print("Core Metrics")
    print("=" * 70)
    
    print(f"  Run ID:       {report.run_id}")
    print(f"  Status:       {report.status}")
    print(f"  Template:     {report.template_id}")
    print(f"  Creative ID:  {report.creative_id}")
    print(f"  Asset ID:     {report.asset_id}")
    print(f"  Asset SHA256: {report.asset_sha256[:16]}...")
    print(f"  Asset URL:    {report.asset_url}")
    print()
    print(f"  Impressions:  {report.impressions}")
    print(f"  Clicks:       {report.clicks}")
    print(f"  Installs:     {report.installs}")
    print(f"  Purchases:    {report.purchases}")
    print()
    print(f"  CTR:          {report.ctr:.4f} ({report.ctr*100:.2f}%)")
    print(f"  CVR:          {report.cvr:.4f} ({report.cvr*100:.2f}%)")
    print(f"  IPM:          {report.ipm:.2f}")
    print(f"  ROAS:         {report.roas:.2f}x")
    print(f"  CPC:          ${report.cpc:.4f}")
    print(f"  Total Cost:   ${report.total_cost:.2f}")
    print(f"  Total Revenue:${report.total_revenue:.2f}")
    print()
    print(f"  Attribution:  {report.attribution_method}")
    print(f"  Click-attrib installs: {report.click_attributed_installs}")
    print(f"  View-attrib installs:  {report.view_attributed_installs}")
    print()
    print(f"  Weight Update: {'Applied' if report.update_applied else 'N/A'}")
    print(f"  Compiler v{report.compiler_version_before} -> v{report.compiler_version_after}")
    
    print()
    print("=" * 70)
    
    if all_passed:
        print("SUCCESS: Production Grade Pipeline test passed!")
        print(f"   12/12 steps executed successfully")
        print(f"   All constraints satisfied")
    else:
        print("FAILED: Some checks did not pass")
    
    print("=" * 70)
    
    report_path = os.path.join(output_dir, f"report_{report.run_id}.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved: {report_path}")
    
    return report, all_passed


if __name__ == "__main__":
    report, passed = test_production_pipeline()
    sys.exit(0 if passed else 1)
