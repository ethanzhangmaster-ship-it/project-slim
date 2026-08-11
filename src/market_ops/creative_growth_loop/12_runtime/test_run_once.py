"""run_once_pipeline 测试脚本

验证单次闭环执行：
1. Creative Generation → creative_id, layout_ast
2. Inference Scoring → score, reject if < threshold
3. Render Stage → asset
4. Ad Publishing → ad_id
5. Traffic Tracking → metrics
6. Dataset Write → samples
7. Weight Update → delta
8. Output Summary → report

必须满足的闭环条件：
- creative 被生成
- 至少 1 次 ad publish
- 至少 1 次 metrics 回收
- dataset 写入成功
- weight update 被执行（必须有变化）
"""
from __future__ import annotations

import sys
import os
import shutil
import importlib

_BASE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_BASE, "..", "..", ".."))
sys.path.insert(0, _SRC)

_PKG = "market_ops.creative_growth_loop"
_runtime_mod = importlib.import_module(f"{_PKG}.12_runtime.production_runtime_engine")
ProductionRuntimeEngine = _runtime_mod.ProductionRuntimeEngine
RunOnceReport = _runtime_mod.RunOnceReport


def test_run_once_pipeline():
    output_dir = "memory/test_run_once"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    runtime = ProductionRuntimeEngine(output_dir=output_dir)
    
    campaign_input = {
        "campaign_id": "camp_once_001",
        "product": {
            "name": "Merge Quest",
            "type": "idle_merger",
            "core_value": "Merge items, unlock worlds!",
        },
        "audience": {
            "geo": "US",
            "age": "18-45",
            "interest": ["puzzle", "idle games"],
        },
        "budget": 100.0,
    }
    
    print("=" * 70)
    print("RUN_ONCE_PIPELINE - 单次闭环执行测试")
    print("=" * 70)
    
    print("\n📝 执行 run_once_pipeline...")
    print("-" * 70)
    
    report = runtime.run_once_pipeline(
        campaign_input=campaign_input,
        template_id="merge_formula",
        score_threshold=0.55,
        min_impressions=30,
        simulate_traffic=True,
        simulated_ctr=0.10,
    )
    
    print(f"Status: {report.status}")
    print(f"Creative ID: {report.creative_id}")
    print(f"Ad ID: {report.ad_id}")
    print(f"Template: {report.template_id}")
    print(f"Inference Score: {report.inference_score:.3f}")
    print(f"Click Probability: {report.click_probability:.3f}")
    
    print("\n📊 Metrics:")
    metrics = report.metrics
    if metrics:
        print(f"  Impressions: {metrics.get('impressions', 0)}")
        print(f"  Clicks: {metrics.get('clicks', 0)}")
        print(f"  Installs: {metrics.get('installs', 0)}")
        print(f"  CTR: {metrics.get('ctr', 0):.2%}")
        print(f"  IPM: {metrics.get('ipm', 0):.1f}")
        print(f"  CPC: ${metrics.get('cpc', 0):.2f}")
    
    print("\n⚙️ Weight Update:")
    print(f"  Update Applied: {report.update_applied}")
    print(f"  Budget Delta:")
    for k, v in report.budget_delta.items():
        print(f"    {k}: {v:+.2f}")
    print(f"  Template Delta:")
    for k, v in report.template_delta.items():
        print(f"    {k}: {v:+.3f}")
    print(f"  Inference Delta:")
    for k, v in report.inference_delta.items():
        print(f"    {k}: {v:+.3f}")
    
    print("\n" + "=" * 70)
    print("✅ 闭环条件验证")
    print("=" * 70)
    
    conditions = report.conditions_met
    
    condition_names = {
        "creative_generated": "creative 被生成",
        "inference_score_passed": "inference score 通过阈值",
        "render_completed": "render 完成",
        "ad_published": "至少 1 次 ad publish",
        "metrics_collected": "至少 1 次 metrics 回收",
        "dataset_written": "dataset 写入成功",
        "weight_updated": "weight update 被执行",
        "has_delta": "参数有变化 (delta ≠ 0)",
    }
    
    all_passed = True
    for key, name in condition_names.items():
        passed = conditions.get(key, False)
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_passed = False
    
    print("-" * 70)
    if all_passed and report.status == "success":
        print("✅ 闭环成功完成")
    else:
        print(f"❌ 闭环失败: {report.reject_reason}")
    
    print("\n" + "=" * 70)
    print("📋 完整报告 (JSON)")
    print("=" * 70)
    import json
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    
    return report.status == "success"


def test_reject_low_score():
    """测试低分 reject"""
    output_dir = "memory/test_run_once_reject"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    runtime = ProductionRuntimeEngine(output_dir=output_dir)
    
    campaign_input = {
        "campaign_id": "camp_reject_001",
        "product": {
            "name": "Test",
            "type": "game",
            "core_value": "test",
        },
        "audience": {"geo": "US"},
        "budget": 50.0,
    }
    
    print("\n" + "=" * 70)
    print("REJECT TEST - 低分 reject")
    print("=" * 70)
    
    report = runtime.run_once_pipeline(
        campaign_input=campaign_input,
        score_threshold=0.90,
        min_impressions=10,
        simulate_traffic=True,
    )
    
    print(f"Status: {report.status}")
    print(f"Reject Reason: {report.reject_reason}")
    
    if report.status == "rejected" and "Score below threshold" in report.reject_reason:
        print("✅ 低分正确 reject")
        return True
    else:
        print("❌ 低分未正确 reject")
        return False


if __name__ == "__main__":
    passed1 = test_run_once_pipeline()
    passed2 = test_reject_low_score()
    
    print("\n" + "=" * 70)
    print("🏁 测试完成")
    print("=" * 70)
    print(f"Pipeline: {'✅ 通过' if passed1 else '❌ 失败'}")
    print(f"Reject: {'✅ 通过' if passed2 else '❌ 失败'}")
    
    sys.exit(0 if (passed1 and passed2) else 1)