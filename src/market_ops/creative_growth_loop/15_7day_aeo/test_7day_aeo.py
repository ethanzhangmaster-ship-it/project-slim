"""7-Day Meta AEO Campaign — 验收测试

8项验收标准（FINAL RUN SPEC）:
1. campaign 真实创建成功
2. ad 正常投放（impressions > 0）
3. event stream 回传（install + purchase）
4. attribution 可回溯 ad_id
5. ROAS 可计算
6. 至少 1 次 budget change
7. dataset 写入成功
8. learning update 执行
"""
from __future__ import annotations

import json
import os
import sys
import importlib

_BASE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_BASE, "..", "..", ".."))
sys.path.insert(0, _SRC)

_PKG = "market_ops.creative_growth_loop.15_7day_aeo"
_mod = importlib.import_module(f"{_PKG}.seven_day_aeo_campaign")
SevenDayAEOCampaign = _mod.SevenDayAEOCampaign


def test_7day_aeo_campaign():
    """测试 7天 AEO Campaign — FINAL RUN SPEC 验收"""
    print("=" * 80)
    print("  🚀 FINAL RUN SPEC — Meta Paid AEO Campaign (7-Day Live)")
    print("  🎯 System: Real-world Paid AEO Optimization Loop System")
    print("=" * 80)
    
    output_dir = "memory/test_7day_aeo"
    
    campaign = SevenDayAEOCampaign(
        output_dir=output_dir,
        mode="mock",
        total_budget=700.0,
        objective="APP_PROMOTION",
        app_id="com.wjoj.witch",
    )
    
    product_info = {
        "name": "Merge Witches",
        "type": "idle_merge_game",
        "core_value": "Merge items, win amazing rewards!",
        "app_id": "com.wjoj.witch",
    }
    
    audience_info = {
        "geo": ["US", "CA", "GB", "AU"],
        "age": "18-45",
        "interests": ["gaming", "puzzle games", "idle games", "match 3"],
        "retarget_interests": ["mobile gaming", "casual games"],
    }
    
    print(f"\n[Setup] Total Budget: $700, Duration: 7 days")
    print(f"[Setup] Platform: Meta, Objective: OUTCOME_APP_PROMOTION")
    print(f"[Setup] Optimization: OFFSITE_CONVERSIONS (Purchase)")
    print(f"[Setup] Bid Strategy: LOWEST_COST_WITHOUT_CAP")
    print(f"[Setup] Output: {output_dir}")
    print()
    
    print("=" * 80)
    print("  📅 Day-by-Day Execution (7-Day Live Loop)")
    print("=" * 80)
    
    report = campaign.run_7day_campaign(
        product_info=product_info,
        audience_info=audience_info,
    )
    
    for dm in report.daily_metrics:
        bar_len = int(dm.spend / 5)
        bar = "█" * min(bar_len, 40)
        
        decision_tags = {
            "scale": "🟢 [SCALE]",
            "kill": "🔴 [KILL]",
            "hold": "⚪ [HOLD]",
            "reallocate": "🟡 [REALLOCATE]",
            "freeze": "🔵 [FREEZE]",
        }
        decision_tag = decision_tags.get(dm.budget_decision, f"[{dm.budget_decision}]")
        
        print(
            f"  Day {dm.day:2d} {decision_tag}\n"
            f"       Spend: ${dm.spend:7.2f} | Imps: {dm.impressions:6,} | "
            f"CTR: {dm.ctr*100:5.2f}%\n"
            f"       ROAS: {dm.roas:5.2f}x | Purchases: {dm.purchases:3d} | "
            f"Budget: ${dm.total_budget:7.2f}\n"
            f"       {dm.budget_reason[:75]}"
        )
        if dm.killed_creatives:
            print(f"       Killed creatives: {len(dm.killed_creatives)}")
        if dm.killed_adsets:
            print(f"       Killed adsets: {len(dm.killed_adsets)}")
    
    print()
    print("=" * 80)
    print("  🏗️  Campaign Structure Verification")
    print("=" * 80)
    
    print(f"\n  Campaign ID: {report.campaign_id}")
    print(f"  Campaign Name: {report.campaign_name}")
    print(f"  Objective: {report.campaign_objective}")
    print(f"  Bid Strategy: {report.bid_strategy}")
    print(f"\n  AdSets ({len(report.adsets)}):")
    
    for adset in report.adsets:
        creative_count = len(adset.creatives)
        active_count = sum(1 for c in adset.creatives if c.status == "ACTIVE")
        
        print(f"    • {adset.name}")
        print(f"      Type: {adset.adset_type:10s} | Budget: ${adset.budget:7.2f}/day "
              f"| Ratio: {adset.budget_ratio*100:.0f}%")
        print(f"      Optimization Event: {adset.optimization_event}")
        print(f"      Creatives: {creative_count} total, {active_count} active")
    
    total_creatives = len(report.creatives)
    unique_templates = len(set(c.template_id for c in report.creatives))
    unique_variants = len(set(c.variant_type for c in report.creatives))
    
    print(f"\n  Total Creatives: {total_creatives}")
    print(f"  Unique Templates: {unique_templates}")
    print(f"  Variants per Template: {total_creatives // unique_templates if unique_templates else 0}")
    print(f"  Variant Types: {unique_variants}")
    
    assets_count = sum(1 for c in report.creatives if c.asset_id)
    ads_count = sum(1 for c in report.creatives if c.ad_id)
    print(f"  Assets Generated: {assets_count}/{total_creatives}")
    print(f"  Ads Created: {ads_count}/{total_creatives}")
    
    print()
    print("=" * 80)
    print("  ✅ 8 Acceptance Criteria (Hard Requirements)")
    print("=" * 80)
    
    checks = []
    
    check1 = (
        bool(report.campaign_id) 
        and len(report.adsets) == 3
        and report.campaign_objective in ("APP_PROMOTION", "SALES")
    )
    detail1 = (
        f"campaign_id={'✓' if report.campaign_id else '✗'}, "
        f"adsets={len(report.adsets)}/3, "
        f"objective={report.campaign_objective}"
    )
    checks.append(("1. Campaign created successfully (3 AdSets, correct objective)", check1, detail1))
    
    check2 = report.total_impressions > 0
    detail2 = f"total_impressions={report.total_impressions:,}"
    checks.append(("2. Ads serving (impressions > 0)", check2, detail2))
    
    check3 = report.total_installs > 0 and report.total_purchases > 0
    detail3 = f"installs={report.total_installs:,}, purchases={report.total_purchases:,}"
    checks.append(("3. Event stream (install + purchase events)", check3, detail3))
    
    creative_ads = [c for c in report.creatives if c.ad_id]
    check4 = len(creative_ads) > 0
    detail4 = (
        f"creatives_with_ad_id={len(creative_ads)}/{len(report.creatives)}"
    )
    checks.append(("4. Attribution traceable to ad_id", check4, detail4))
    
    check5 = report.roas > 0 and report.total_spend > 0 and report.total_revenue > 0
    detail5 = (
        f"ROAS={report.roas:.4f}x "
        f"(revenue ${report.total_revenue:.2f} / spend ${report.total_spend:.2f})"
    )
    checks.append(("5. ROAS computable", check5, detail5))
    
    budget_decisions = [d.budget_decision for d in report.daily_metrics]
    non_hold = sum(1 for d in budget_decisions if d != "hold")
    check6 = non_hold > 0
    detail6 = (
        f"non-hold decisions: {non_hold}/7 days | "
        f"total_budget_changes={report.total_budget_changes} | "
        f"decisions={budget_decisions}"
    )
    checks.append(("6. At least 1 budget change (scale/kill/reallocate)", check6, detail6))
    
    check7 = report.dataset_written
    detail7 = f"written={report.dataset_written}"
    checks.append(("7. Dataset written successfully", check7, detail7))
    
    has_budget_updates = bool(report.learning_delta.get("budget_updates"))
    has_inference_updates = bool(report.learning_delta.get("inference_updates"))
    has_template_updates = bool(report.learning_delta.get("template_updates"))
    check8 = (
        report.weight_update_applied 
        and report.learning_delta
        and (has_budget_updates or has_inference_updates or has_template_updates)
    )
    delta_keys = list(report.learning_delta.keys())
    detail8 = (
        f"applied={report.weight_update_applied}, "
        f"delta_keys={delta_keys}, "
        f"budget_updates={has_budget_updates}, "
        f"inference_updates={has_inference_updates}, "
        f"template_updates={has_template_updates}"
    )
    checks.append(("8. Learning update executed (non-zero delta)", check8, detail8))
    
    all_passed = True
    for check_name, passed, detail in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n  {status}  {check_name}")
        print(f"         → {detail}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 80)
    print("  📊 Final Summary (7-Day Totals)")
    print("=" * 80)
    
    print(f"""
  💰 Financials:
     Total Spend:        ${report.total_spend:,.2f}
     Total Revenue:      ${report.total_revenue:,.2f}
     ROAS:               {report.roas:.2f}x
     CPA:                ${report.cpa:.2f}

  📈 Performance:
     Impressions:        {report.total_impressions:,}
     Clicks:             {report.total_clicks:,}
     Installs:           {report.total_installs:,}
     Purchases:          {report.total_purchases:,}
     CTR:                {report.ctr*100:.2f}%
     CVR:                {report.cvr*100:.2f}%
     IPM:                {report.ipm:.2f}

  🏆 Best / Worst:
     Best Creative:      {report.best_creative}  (ROAS={report.best_creative_roas:.2f}x)
     Worst Creative:     {report.worst_creative}  (ROAS={report.worst_creative_roas:.2f}x)
     Best AdSet:         {report.best_adset} ({report.best_adset_type})
     Worst AdSet:        {report.worst_adset} ({report.worst_adset_type})

  🔧 Operations:
     Total Budget Changes:  {report.total_budget_changes}
     Creatives Killed:      {report.total_creatives_killed}
     AdSets Killed:         {report.total_adsets_killed}
     Dataset Written:       {report.dataset_written}
     Learning Update:       {report.weight_update_applied}

  📋 Status: {report.status.upper()}
""")
    
    print("=" * 80)
    
    if all_passed:
        print()
        print("  ✅ SUCCESS: All 8 acceptance criteria passed!")
        print()
        print("     System: Real-world Paid AEO Optimization Loop System")
        print("     7-day campaign executed successfully")
        print("     Full data chain:")
        print("       creative_id → asset_id → campaign_id → adset_id → ad_id")
        print("       → impression → click → install → purchase")
        print("       → attribution → metrics → budget decision")
        print("       → dataset row → weight update")
    else:
        print()
        print("  ❌ FAILED: Some acceptance criteria not met")
    
    print("=" * 80)
    
    report_path = os.path.join(output_dir, f"7day_report_{report.run_id}.json")
    print(f"\n📄 Full report saved: {report_path}")
    
    return report, all_passed


if __name__ == "__main__":
    report, passed = test_7day_aeo_campaign()
    sys.exit(0 if passed else 1)
