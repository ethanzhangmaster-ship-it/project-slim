"""Creative Intelligence Layer Phase 2 - 知识应用闭环测试

跑通: M4 Pattern Discovery → M5 Knowledge Base → M6 Creative Planner

Usage:
    python scripts/test_phase2.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from market_ops.creative_intelligence import (
    CreativeKnowledgeBase,
    CreativePlanner,
    FeatureAnalyticsEngine,
    WinnerPatternDiscovery,
)


def main():
    project = "P04"

    # ==============================
    # M4: Winner Pattern Discovery
    # ==============================
    print(f"\n{'='*60}")
    print("  M4: Winner Pattern Discovery")
    print(f"{'='*60}")

    discovery = WinnerPatternDiscovery()
    pattern_report = discovery.discover(
        project=project,
        min_spend=50,
        min_impressions=1000,
    )
    discovery.close()

    if "error" in pattern_report:
        print(f"[M4] 错误: {pattern_report['error']}")
        return

    print(f"\n[M4] Winners: {pattern_report['winner_count']} (avg CTR {pattern_report['winner_avg_ctr']}%)")
    print(f"[M4] Losers: {pattern_report['loser_count']} (avg CTR {pattern_report['loser_avg_ctr']}%)")

    print(f"\n--- 单Feature规律 ---")
    for p in pattern_report["single_feature_patterns"][:5]:
        print(f"  {p['pattern']:<30} Winner={p['winner_pct']:>5.1f}% Loser={p['loser_pct']:>5.1f}% | {p['insight']}")

    print(f"\n--- Feature组合规律 (Top 5) ---")
    for c in pattern_report["combo_patterns"][:5]:
        print(f"  {c['pattern']:<35} CTR={c['avg_ctr']:>5.1f}% vs {c['baseline_ctr']:>5.1f}% (+{c['lift_pct']}%) n={c['sample_count']}")

    print(f"\n--- Winner vs Loser关键差异 ---")
    for d in pattern_report["winner_loser_comparison"]["key_differences"][:5]:
        direction = "↑Winner" if d["gap"] > 0 else "↓Loser"
        print(f"  {d['feature']:<25} Winner={d['winner_pct']:>5.1f}% Loser={d['loser_pct']:>5.1f}% gap={d['gap']:>+5.1f}% {direction}")

    # ==============================
    # M5: Knowledge Base
    # ==============================
    print(f"\n{'='*60}")
    print("  M5: Creative Knowledge Base")
    print(f"{'='*60}")

    kb = CreativeKnowledgeBase()

    # 从M3 Analytics更新 (复用之前的analytics报告)
    analytics_files = list((ROOT / "output" / "creative_intelligence" / "analytics").glob(f"analytics_{project}_*.json"))
    if analytics_files:
        latest = max(analytics_files, key=lambda p: p.stat().st_mtime)
        with open(latest, "r", encoding="utf-8") as f:
            analytics_report = json.load(f)
        n1 = kb.update_from_analytics(analytics_report)
        print(f"[M5] 从Analytics更新: {n1} 条")

    # 从M4 Pattern Discovery更新
    n2 = kb.update_from_patterns(pattern_report)
    print(f"[M5] 从Patterns更新: {n2} 条")

    # 知识库摘要
    summary = kb.get_summary()
    print(f"\n[M5] 知识库摘要:")
    print(f"  总规则: {summary['total_rules']}")
    print(f"  活跃规则: {summary['active_rules']}")
    print(f"  按来源: {summary['by_source']}")
    print(f"  按效果: {summary['by_effect']}")
    print(f"  按项目: {summary['by_project']}")

    # Top规则
    print(f"\n--- Top 5 正向规则 (CTR) ---")
    for r in kb.get_top_rules(project=project, effect="positive", limit=5):
        print(f"  {r['pattern']:<35} {r['metric']}={r['effect']} lift={r['lift_pct']:>+.1f}% conf={r['confidence']:.1f} n={r['sample_count']}")

    print(f"\n--- 应避免的规则 ---")
    for r in kb.get_avoid_rules(project=project, limit=5):
        print(f"  {r['pattern']:<35} {r['effect']} lift={r['lift_pct']:>+.1f}% conf={r['confidence']:.1f} n={r['sample_count']}")

    # ==============================
    # M6: Creative Planner
    # ==============================
    print(f"\n{'='*60}")
    print("  M6: Creative Planner")
    print(f"{'='*60}")

    planner = CreativePlanner()
    prompts = planner.plan(project=project, count=6, strategy="balanced")

    print(f"\n[M6] 生成 {len(prompts)} 个prompt:")
    for p in prompts:
        print(f"\n  [{p['type']}] {p['prompt_id']}")
        print(f"    Prompt: {p['prompt_text'][:120]}...")
        print(f"    基于规则: {p.get('based_on_rules', [])}")
        print(f"    预测特征: {p.get('predicted_features', [])}")

    print(f"\n{'='*60}")
    print("  Phase 2 闭环测试完成")
    print(f"  M4 Pattern → M5 Knowledge → M6 Planner")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
