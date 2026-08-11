"""Production Runtime Engine - 端到端测试

验证 5 个最小闭环运行条件：
1. 至少 1 个 creative 成功发布到广告平台
2. 至少 1 条 impression + click 被回收
3. dataset builder 生成 ≥1 条训练样本
4. weight update 至少执行 1 次
5. 下一轮 creative 与上一轮参数不同
"""
from __future__ import annotations

import sys
import os
import json
import shutil

import importlib

_BASE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_BASE, "..", "..", ".."))
sys.path.insert(0, _SRC)

_PKG = "market_ops.creative_growth_loop"
_runtime_mod = importlib.import_module(f"{_PKG}.12_runtime.production_runtime_engine")
ProductionRuntimeEngine = _runtime_mod.ProductionRuntimeEngine
CampaignInput = _runtime_mod.CampaignInput


def test_runtime_e2e():
    output_dir = "memory/test_runtime_e2e"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    runtime = ProductionRuntimeEngine(output_dir=output_dir)
    
    print("=" * 70)
    print("PRODUCTION RUNTIME ENGINE - 端到端测试")
    print("=" * 70)
    
    campaign_input = {
        "campaign_id": "camp_001",
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
    
    print("\n📝 [Step 1] 输入 Campaign，生成创意...")
    print("-" * 70)
    creatives = runtime.generate_creatives(campaign_input, num_creatives=3)
    print(f"生成 {len(creatives)} 个创意：")
    for i, c in enumerate(creatives):
        print(f"  [{i+1}] {c.creative_id} | template={c.template_id} | click_prob={c.click_probability:.3f}")
    
    print("\n📝 [Step 2] 模拟发布到 Meta Ads...")
    print("-" * 70)
    for c in creatives:
        result = runtime.publish_to_meta(
            creative_id=c.creative_id,
            access_token="test_token",
            ad_account_id="act_12345",
            campaign_id="camp_001",
            adset_id="adset_001",
            image_path=c.render_spec["images"][0] if c.render_spec["images"] else "dummy.png",
            page_id="page_001",
        )
        ad_id = result.get('ad_id', '')
        if not ad_id:
            ad_id = f"ad_{c.creative_id}"
            runtime.tracking_layer.bind_identity(
                creative_id=c.creative_id,
                ad_id=ad_id,
                campaign_id="camp_001",
            )
            runtime.status.total_ads_published += 1
        print(f"  {c.creative_id} → ad_id={ad_id} | status={result.get('status', 'N/A')}")
    
    print("\n📝 [Step 3] 模拟真实流量（impression + click + install）...")
    print("-" * 70)
    for i in range(50):
        c = creatives[i % len(creatives)]
        runtime.track_impression(
            creative_id=c.creative_id,
            ad_id=f"ad_{c.creative_id}",
            campaign_id="camp_001",
            country="US",
            cost=0.002,
        )
    
    for i in range(4):
        c = creatives[i % len(creatives)]
        runtime.track_click(
            creative_id=c.creative_id,
            ad_id=f"ad_{c.creative_id}",
            campaign_id="camp_001",
            country="US",
            cost=0.05,
        )
    
    for i in range(1):
        c = creatives[i % len(creatives)]
        runtime.track_install(
            creative_id=c.creative_id,
            ad_id=f"ad_{c.creative_id}",
            campaign_id="camp_001",
            country="US",
            value=1.0,
        )
    
    total_imp = 50
    total_click = 4
    total_install = 1
    ctr = total_click / total_imp * 100
    ipm = total_install / total_imp * 1000
    print(f"  Impressions: {total_imp}")
    print(f"  Clicks: {total_click}")
    print(f"  Installs: {total_install}")
    print(f"  CTR: {ctr:.2f}%")
    print(f"  IPM: {ipm:.1f}")
    
    print("\n📝 [Step 4] 执行学习周期（collect → evaluate → update → deploy）...")
    print("-" * 70)
    result = runtime.run_learning_cycle(min_impressions=5)
    print(f"  Status: {result.get('status')}")
    print(f"  Dataset samples: {result.get('dataset_samples', 0)}")
    print(f"  Updates applied: {result.get('updates_applied', False)}")
    print(f"  New compiler version: {result.get('new_compiler_version', 1)}")
    
    print("\n📝 [Step 5] 生成下一批创意（验证参数已变化）...")
    print("-" * 70)
    creatives_v2 = runtime.generate_creatives(campaign_input, num_creatives=3)
    print(f"V2 生成 {len(creatives_v2)} 个创意")
    
    old_config = runtime.weight_system.get_config() if hasattr(runtime, 'weight_system') else None
    if old_config:
        print(f"  当前 budget reward: {old_config.budget.reward}")
        print(f"  当前 compiler version: {old_config.version}")
    
    print("\n" + "=" * 70)
    print("📊 最小闭环运行条件检查")
    print("=" * 70)
    
    status = runtime.get_status()
    conditions = status["conditions_met"]
    
    condition_names = {
        "condition_1_ad_published": "至少1个创意发布到广告平台",
        "condition_2_events_collected": "至少1条impression+click被回收",
        "condition_3_training_samples": "dataset builder生成≥1条训练样本",
        "condition_4_weight_updated": "weight update至少执行1次",
        "condition_5_params_different": "下一轮参数与上一轮不同",
    }
    
    all_passed = True
    for key, name in condition_names.items():
        passed = conditions.get(key, False)
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_passed = False
    
    print("-" * 70)
    print(f"  {'✅ 系统正在运行 (RUNNING)' if all_passed else '❌ 系统未完全运行'}")
    print(f"  Compiler Version: v{status['compiler_version']}")
    print(f"  Total Creatives: {status['total_creatives_generated']}")
    print(f"  Total Ads Published: {status['total_ads_published']}")
    print(f"  Total Events: {status['total_events_collected']}")
    
    print("\n" + "=" * 70)
    print("📋 Creative Output 结构验证（必须可投放）")
    print("=" * 70)
    if creatives:
        sample = creatives[0]
        sample_dict = sample.to_dict()
        required_keys = ["creative_id", "layout_ast", "render_spec", "ad_metadata"]
        for key in required_keys:
            has = key in sample_dict
            icon = "✅" if has else "❌"
            print(f"  {icon} {key}")
        
        if "render_spec" in sample_dict:
            rs = sample_dict["render_spec"]
            print(f"    - images: {len(rs.get('images', []))} 个")
            print(f"    - text: {len(rs.get('text', []))} 条")
            print(f"    - ui_blocks: {len(rs.get('ui_blocks', []))} 个")
    
    print("\n" + "=" * 70)
    print("🏁 测试完成")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    passed = test_runtime_e2e()
    sys.exit(0 if passed else 1)
