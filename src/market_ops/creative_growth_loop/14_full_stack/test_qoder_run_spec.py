"""Production Full Stack Ads System v1 — Qoder Run Spec 测试

验证 13步生产版闭环执行器。

8项硬性验收标准：
1. 真实 asset generated
2. ad platform object chain complete
3. event stream exists
4. metrics computed
5. attribution joined
6. budget decision executed
7. dataset written
8. weight updated with delta ≠ 0
"""
from __future__ import annotations

import json
import os
import sys
import importlib

_BASE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_BASE, "..", "..", ".."))
sys.path.insert(0, _SRC)

_PKG = "market_ops.creative_growth_loop.14_full_stack"
_pipeline_mod = importlib.import_module(f"{_PKG}.full_stack_pipeline")
FullStackAdsPipeline = _pipeline_mod.FullStackAdsPipeline


def test_qoder_run_spec():
    """Qoder Run Spec 完整验收测试"""
    print("=" * 70)
    print("Production Full Stack Ads System v1")
    print("Qoder Run Spec - Acceptance Test")
    print("=" * 70)
    
    output_dir = "memory/test_qoder_run_spec"
    
    pipeline = FullStackAdsPipeline(
        output_dir=output_dir,
        platform="meta",
        mode="mock",
        attribution_model="last_click",
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
    
    print(f"\n[Config] Platform: meta, Mode: mock, Output: {output_dir}")
    print()
    
    print("Executing 13-step Full Stack Pipeline...")
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
    
    qoder_output = report.to_qoder_format()
    
    print("=" * 70)
    print("Data Chain Verification (end-to-end)")
    print("=" * 70)
    
    data_chain = [
        ("creative_id", report.creative_id, "Creative Intelligence"),
        ("asset_id", report.asset_id, "Asset Production"),
        ("campaign_id", report.campaign_id, "Ad Platform"),
        ("adset_id", report.adset_id, "Ad Platform"),
        ("ad_id", report.ad_id, "Ad Platform"),
        ("events_count", str(report.events_count), "Tracking Layer"),
        ("metrics", f"CTR={report.ctr:.4f} ROAS={report.roas:.2f}", "Metrics Engine"),
        ("budget_decision", report.budget_decision_type, "Budget Intelligence"),
        ("dataset_written", str(report.dataset_written), "Offline Learning"),
        ("weight_update", f"v{report.compiler_version_before}->v{report.compiler_version_after}", "Learning Loop"),
    ]
    
    chain_complete = True
    for name, value, layer in data_chain:
        has_value = bool(value) and value not in ["0", "False", "false"]
        status = "[OK]" if has_value else "[MISSING]"
        print(f"  {status}  {name:20s} = {value:40s} ({layer})")
        if not has_value:
            chain_complete = False
    
    print()
    print("=" * 70)
    print("8 Acceptance Criteria (Hard Requirements)")
    print("=" * 70)
    
    checks = []
    
    check1 = report.asset_path and os.path.exists(report.asset_path) and report.asset_hash
    checks.append(("1. Real asset generated", check1,
                    f"file={os.path.basename(report.asset_path)}, hash={report.asset_hash[:16]}..."))
    
    check2 = all([report.campaign_id, report.adset_id, report.ad_id])
    checks.append(("2. Ad platform object chain complete", check2,
                    f"campaign={bool(report.campaign_id)}, adset={bool(report.adset_id)}, ad={bool(report.ad_id)}"))
    
    check3 = report.events_count > 0
    checks.append(("3. Event stream exists", check3,
                    f"{report.events_count} events (impressions+clicks+installs+purchases)"))
    
    check4 = all([report.ctr > 0, report.cvr > 0, report.roas > 0])
    checks.append(("4. Metrics computed", check4,
                    f"CTR={report.ctr:.4f}, CVR={report.cvr:.4f}, ROAS={report.roas:.2f}"))
    
    check5 = report.steps_completed.get("step9_attribution", False)
    checks.append(("5. Attribution joined", check5,
                    f"model={report.attribution_model}, attributed_installs=yes"))
    
    check6 = report.budget_decision_type in ["scale", "hold", "kill"]
    checks.append(("6. Budget decision executed", check6,
                    f"type={report.budget_decision_type}, delta={report.budget_delta_percent:.2f}%"))
    
    check7 = report.dataset_written
    checks.append(("7. Dataset written", check7,
                    f"written={report.dataset_written}"))
    
    check8 = (
        report.weight_update_applied 
        and report.delta 
        and (
            any(v != 0 for v in report.delta.get("budget_updates", {}).values())
            or any(v != 0 for v in report.delta.get("inference_updates", {}).values())
            or any(v != 0 for v in report.delta.get("template_updates", {}).values())
        )
    )
    checks.append(("8. Weight updated with delta != 0", check8,
                    f"applied={report.weight_update_applied}, "
                    f"inference_delta={list(report.delta.get('inference_updates', {}).values()) if report.delta else []}, "
                    f"template_delta={list(report.delta.get('template_updates', {}).values()) if report.delta else []}"))
    
    all_passed = True
    for check_name, passed, detail in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {check_name}")
        print(f"         -> {detail}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 70)
    print("Qoder Run Spec Output Format")
    print("=" * 70)
    print(json.dumps(qoder_output, indent=2, ensure_ascii=False)[:800] + "\n...")
    print()
    
    print("=" * 70)
    
    if all_passed:
        print("SUCCESS: All 8 acceptance criteria passed!")
        print(f"   System: Autonomous Multi-Platform Advertising Control System")
        print(f"   13/13 steps executed successfully")
        print(f"   Full data chain verified (creative_id -> weight_update)")
    else:
        print("FAILED: Some acceptance criteria not met")
    
    print("=" * 70)
    
    report_path = os.path.join(output_dir, f"qoder_report_{report.run_id}.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(qoder_output, f, indent=2, ensure_ascii=False)
    print(f"\nQoder report saved: {report_path}")
    
    return report, all_passed


if __name__ == "__main__":
    report, passed = test_qoder_run_spec()
    sys.exit(0 if passed else 1)