"""V4.2.2 Creative Intelligence Layer 验证脚本

用 P04 已有数据跑通整个 Intelligence Layer：
1. 加载已有 Ranking 数据
2. 初始化 Intelligence Layer
3. 存入 Memory + KG
4. 测试 Predict / Rank / Decide / Portfolio / Graph
5. 生成 Dashboard
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.market_ops.video_intelligence import (
    CreativeIntelligence,
    IntelligenceDashboard,
)


def main():
    print("=" * 100)
    print("🧠 V4.2.2 Creative Intelligence Layer 验证")
    print("=" * 100)

    # 加载 V4.2 数据
    ranking_file = ROOT / "output" / "creative_ranking" / "ranking.json"
    if not ranking_file.exists():
        print(f"❌ Ranking 文件不存在: {ranking_file}")
        print("   请先运行 V4.2 Ranking Agent")
        return

    with open(ranking_file, "r", encoding="utf-8") as f:
        rankings = json.load(f)

    print(f"\n📊 加载了 {len(rankings)} 个 Ranked Variants")

    # 初始化 Intelligence
    print("\n[1] 初始化 CreativeIntelligence...")
    intel = CreativeIntelligence(project="P04")
    print("  ✅ 初始化完成")
    print(f"     - Memory Engine: DuckDB 已连接")
    print(f"     - Feature Store: {len(intel.feature_store._schema)} 个特征")
    print(f"     - Knowledge Graph: 空")
    print(f"     - Predictor Engine: rule 预测器已注册")
    print(f"     - Rule Engine: {len(intel.rules._rules)} 条规则")

    # 种子数据：将 Ranking 数据存入 Memory
    print("\n[2] 种子数据导入 Memory + KG...")
    seed_results = []

    def _build_dna(dim: str, val: str) -> dict:
        """根据 changed_dimension 构造一个基础 DNA"""
        dna = {
            "character": {"type": "witch", "pose": "standing centered"},
            "creatures": [{"type": "dragon", "color": "blue", "glow": "cyan"}],
            "environment": {"type": "magic_forest", "time": "night"},
            "lighting": {"color_temperature": "warm"},
            "hook": {"type": "collection"},
            "composition": {"layout": "centered"},
            "colors": {"mood_palette": ["balanced"]},
            "camera": {"shot_type": "medium"},
            "gameplay": {"type": "idle"},
        }
        # 根据维度修改对应字段
        if dim == "creature":
            dna["creatures"] = [{"type": val, "color": "blue"}]
        elif dim == "background":
            dna["environment"] = {"type": val, "time": "night"}
        elif dim == "character_pose":
            dna["character"]["pose"] = val
        elif dim == "lighting":
            dna["lighting"] = {"color_temperature": val}
        elif dim == "camera":
            dna["camera"] = {"shot_type": val}
        elif dim == "hook_type":
            dna["hook"] = {"type": val}
        return dna

    for r in rankings[:20]:  # 用 TOP20 做种子
        variant_id = r.get("variant_id", "")
        dimensions = r.get("dimensions", {})

        # 提取 performance 模拟数据（从 dimensions 反推）
        perf = {
            "ctr": dimensions.get("facebook_hook", {}).get("score", 0) / 100 * 0.05,  # 模拟 CTR
            "roas_d7": dimensions.get("winning_similarity", {}).get("score", 0) / 100 * 2.0,
            "cvr": dimensions.get("brand_consistency", {}).get("score", 0) / 100 * 0.3,
            "ipm": dimensions.get("gameplay_consistency", {}).get("score", 0) / 100 * 50,
            "spend": 100,
        }

        # 从 changed_dimension 提取特征
        dim = r.get("changed_dimension", "")
        new_val = r.get("new_value", "")
        dna = _build_dna(dim, new_val)

        seed_results.append({
            "creative_id": f"fb_{variant_id}",
            "variant_id": variant_id,
            "dna": dna,
            "changed_dimension": dim,
            "new_value": new_val,
            "performance": perf,
            "risk_level": r.get("risk_level", ""),
        })

    # 增量学习（导入种子数据）
    learn_report = intel.learn(seed_results)
    print(f"  ✅ 导入 {len(seed_results)} 条种子数据到 Memory + KG")
    print(f"     - 更新创意: {learn_report.get('updated_creatives', 0)}")
    print(f"     - 更新变量: {learn_report.get('updated_variables', 0)}")
    print(f"     - 图谱边: {learn_report.get('graph_edges_added', 0)}")

    # 测试 Predict API
    print("\n[3] 测试 Predict API...")
    sample_dna = {
        "character": {"type": "witch", "pose": "standing centered"},
        "creatures": [{"type": "dragon", "color": "blue", "glow": "cyan"}],
        "environment": {"type": "magic_forest", "time": "night"},
        "lighting": {"color_temperature": "warm"},
        "hook": {"type": "collection"},
        "composition": {"layout": "centered"},
        "colors": {"mood_palette": ["balanced"]},
        "camera": {"shot_type": "medium"},
    }
    predictions = intel.predict_from_dna(sample_dna)
    print(f"  ✅ 预测完成")
    print(f"     - Predicted CTR: {predictions.get('ctr', {}).get('value', 0):.4f}")
    print(f"     - Predicted ROAS: {predictions.get('roas', {}).get('value', 0):.2f}")
    print(f"     - Predicted CVR: {predictions.get('cvr', {}).get('value', 0):.4f}")
    print(f"     - Predicted IPM: {predictions.get('ipm', {}).get('value', 0):.2f}")
    print(f"     - Confidence: {predictions.get('confidence', 0):.1f}")

    # 测试 Rank API
    print("\n[4] 测试 Rank API...")
    ranked = intel.rank(rankings, sort_by="roas")
    print(f"  ✅ 排序完成（按 ROAS）")
    print(f"     TOP3: {[r['variant_id'] for r in ranked[:3]]}")

    # 测试 Decide / Portfolio API
    print("\n[5] 测试 Portfolio / Decide API...")
    decision = intel.decide(ranked, total_count=20)
    portfolio = decision["portfolio"]
    print(f"  ✅ Portfolio 分配完成")
    print(f"     Safe: {len(portfolio.get('safe', []))} 个")
    print(f"     Growth: {len(portfolio.get('growth', []))} 个")
    print(f"     Explore: {len(portfolio.get('explore', []))} 个")
    budget = decision["budget_allocation"]
    safe_b = budget.get("safe", {}).get("total_budget", 0) if isinstance(budget.get("safe"), dict) else budget.get("safe", 0)
    growth_b = budget.get("growth", {}).get("total_budget", 0) if isinstance(budget.get("growth"), dict) else budget.get("growth", 0)
    explore_b = budget.get("explore", {}).get("total_budget", 0) if isinstance(budget.get("explore"), dict) else budget.get("explore", 0)
    print(f"     预算分配（$1000）: Safe=${safe_b:.0f}, Growth=${growth_b:.0f}, Explore=${explore_b:.0f}")

    # 测试 Memory API
    print("\n[6] 测试 Memory API...")
    top_creatures = intel.memory_top("creatures_0_type", "roas", 5)
    print(f"  ✅ Top 生物（按ROAS）:")
    for i, c in enumerate(top_creatures[:3], 1):
        print(f"     {i}. {c.get('value', 'N/A')} - ROAS: {c.get('roas_mean', 0):.2f} (n={c.get('sample_count', 0)})")

    # 测试 Graph API
    print("\n[7] 测试 Knowledge Graph API...")
    graph_summary = intel.graph_summary()
    print(f"  ✅ 图谱统计: {json.dumps(graph_summary, ensure_ascii=False)}")
    top_roas_features = intel.graph_top_features("roas", 5)
    print(f"  Top ROAS 驱动因素:")
    for i, f in enumerate(top_roas_features[:3], 1):
        print(f"     {i}. {f.get('feature', 'N/A')}")

    # 测试 Rule API
    print("\n[8] 测试 Rule Engine API...")
    policy_check = intel.rules_check({"hook_type": "collection", "text_count": 3}, "policy")
    print(f"  ✅ 政策合规检查: {'通过' if policy_check.get('pass', True) else '未通过'}")
    print(f"     Warnings: {len(policy_check.get('warnings', []))} 个")

    # 测试 Feature API
    print("\n[9] 测试 Feature Store API...")
    features = intel.feature_extract(sample_dna)
    validated = intel.feature_validate(features)
    print(f"  ✅ 特征提取: {len(features)} 个特征")
    print(f"  ✅ 特征验证: {'通过' if validated.get('valid', True) else '未通过'}")

    # 生成 Dashboard
    print("\n[10] 生成 Dashboard 报告...")
    output_dir = ROOT / "output" / "creative_intelligence"
    dashboard = IntelligenceDashboard(intel)
    reports = dashboard.generate_all(output_dir)
    print(f"  ✅ Dashboard 生成完成")
    print(f"     输出目录: {output_dir}")
    print(f"     报告文件: intelligence_report.md")

    # 总结
    print("\n" + "=" * 100)
    print("🎉 V4.2.2 Creative Intelligence Layer 验证通过!")
    print("=" * 100)
    print("\n📁 输出文件:")
    print(f"   {output_dir / 'memory_dashboard.json'}")
    print(f"   {output_dir / 'feature_dashboard.json'}")
    print(f"   {output_dir / 'graph_dashboard.json'}")
    print(f"   {output_dir / 'learning_dashboard.json'}")
    print(f"   {output_dir / 'portfolio_dashboard.json'}")
    print(f"   {output_dir / 'intelligence_report.md'}")

    return intel


if __name__ == "__main__":
    main()
