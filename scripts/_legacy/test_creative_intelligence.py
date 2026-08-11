"""Creative Intelligence Layer Phase 1 - 闭环测试

用已下载的P04 Top图片跑通:
  M1 Feature Engine → M2 Feature DB → M3 Analytics

先跑5张图片验证流程,再扩展到全量。

Usage:
    python scripts/test_creative_intelligence.py
    python scripts/test_creative_intelligence.py --full  # 全量424张
"""
import json
import os
import sys
import time
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
    FeatureAnalyticsEngine,
    FeatureDatabase,
    FeatureIntelligenceEngine,
)


def load_creatives_with_perf(limit: int = 5, project: str | None = None):
    """从 all_image_creatives_with_perf.json 加载素材清单"""
    perf_file = ROOT / "output" / "facebook_top_creatives" / "all_image_creatives_with_perf.json"
    with open(perf_file, "r", encoding="utf-8") as f:
        creatives = json.load(f)

    # 过滤有local_path且文件存在的
    valid = []
    for c in creatives:
        img_path = c.get("local_path", "")
        if not img_path or not Path(img_path).exists():
            continue
        if project and c.get("project") != project:
            continue
        valid.append(c)

    # 按spend排序
    valid.sort(key=lambda x: x.get("spend", 0), reverse=True)

    if limit:
        valid = valid[:limit]

    print(f"[Test] 加载 {len(valid)} 张素材")
    return valid


def run_m1_feature_extraction(creatives, engine):
    """M1: 提取Feature"""
    print(f"\n{'='*60}")
    print("  M1: Feature Intelligence Engine")
    print(f"{'='*60}")

    features = []
    for i, c in enumerate(creatives, 1):
        print(f"\n[{i}/{len(creatives)}] {c.get('creative_id', '?')} | {c.get('ad_name', '')[:40]}")
        print(f"  图片: {c.get('local_path', '')}")
        print(f"  项目: {c.get('project', '')} | 花费: ${c.get('spend', 0):.0f}")

        try:
            feature = engine.extract_features(
                image_path=c["local_path"],
                creative_id=c.get("creative_id", ""),
                project=c.get("project", ""),
                campaign=c.get("campaign", ""),
                adset=c.get("adset", ""),
            )

            # 打印关键特征
            print(f"  → 主体: {feature.subject.subject_type} ({feature.subject.subject_description[:30]})")
            print(f"  → 颜色: {feature.color.primary_color}/{feature.color.secondary_color} ({feature.color.warm_cool})")
            print(f"  → 亮度: {feature.color.brightness} | 饱和度: {feature.color.saturation}")
            print(f"  → 构图: 焦点={feature.composition.focus_grid} 对称={feature.composition.symmetry}")
            print(f"  → Hook: {feature.psychology.hook_type} | 情绪: {feature.psychology.mood}")
            print(f"  → 视觉: female={feature.visual_flags.has_female} coins={feature.visual_flags.has_coins} cta={feature.visual_flags.has_cta}")
            print(f"  → 游戏: merge={feature.game_elements.has_merge} progress={feature.game_elements.has_progress}")
            print(f"  → 来源: {feature.source}")

            features.append(feature)
        except Exception as e:
            print(f"  [ERR] {e}")
            import traceback
            traceback.print_exc()

    print(f"\n[M1] 完成: {len(features)}/{len(creatives)}")
    return features


def run_m2_save_to_db(features):
    """M2: 保存到DuckDB"""
    print(f"\n{'='*60}")
    print("  M2: Creative Feature Database")
    print(f"{'='*60}")

    with FeatureDatabase() as db:
        count = db.save_features(features)
        total = db.get_feature_count()
        print(f"[M2] 保存: {count} 条 | 总计: {total} 条")

        # 查询验证
        stats = db.get_project_stats()
        print(f"\n[M2] 项目分布:")
        for s in stats:
            print(f"  {s['project']}: {s['count']} 条 (hooks={s['hook_types']}, colors={s['colors']})")

        return total


def run_m3_analytics(project=None):
    """M3: 分析Feature效果"""
    print(f"\n{'='*60}")
    print("  M3: Feature Analytics Engine")
    print(f"{'='*60}")

    engine = FeatureAnalyticsEngine()
    report = engine.analyze(
        project=project,
        min_spend=50,
        min_impressions=100,
    )

    if "error" in report:
        print(f"[M3] {report['error']} (样本数: {report.get('count', 0)})")
        return report

    print(f"\n[M3] 样本: {report['sample_count']} 条 | 总花费: ${report['total_spend']:,.0f}")

    print(f"\n--- Top 10 Features (CTR提升) ---")
    top_ctr = [r for r in report["top_features"] if r["metric"] == "ctr"][:10]
    for r in top_ctr:
        sig = "***" if r["significant"] else ""
        val = r.get("value", "")
        print(f"  {r['feature']:<25} {val:<15} {r['with_mean']:>6} vs {r['without_mean']:>6} "
              f"→ {r['lift_pct']:>+6.1f}% {sig} (n={r['with_count']}/{r['without_count']})")

    print(f"\n--- Worst 5 Features (CTR下降) ---")
    worst_ctr = [r for r in report["worst_features"] if r["metric"] == "ctr"][:5]
    for r in worst_ctr:
        sig = "***" if r["significant"] else ""
        val = r.get("value", "")
        print(f"  {r['feature']:<25} {val:<15} {r['with_mean']:>6} vs {r['without_mean']:>6} "
              f"→ {r['lift_pct']:>+6.1f}% {sig}")

    print(f"\n--- Feature Correlations (Top 5) ---")
    for c in report["correlations"][:5]:
        print(f"  {c['feature1']:<20} + {c['feature2']:<20} co-occur={c['co_occurrence']} lift={c['lift']}")

    engine.close()
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="全量424张(否则只跑5张测试)")
    parser.add_argument("--project", default=None, help="只跑指定项目(P02/P04/P07)")
    parser.add_argument("--no-lovart", action="store_true", help="不用Lovart(仅local分析)")
    args = parser.parse_args()

    limit = None if args.full else 5
    creatives = load_creatives_with_perf(limit=limit, project=args.project)

    if not creatives:
        print("没有找到素材,请先运行 download_image_creatives.py")
        return

    # M1: Feature Extraction
    engine = FeatureIntelligenceEngine(
        use_lovart=not args.no_lovart,
        use_local=True,
    )
    features = run_m1_feature_extraction(creatives, engine)

    if not features:
        print("M1未输出任何Feature,终止")
        return

    # M2: Save to DB
    run_m2_save_to_db(features)

    # M3: Analytics (需要足够数据才有效)
    run_m3_analytics(project=args.project)

    print(f"\n{'='*60}")
    print("  Phase 1 闭环测试完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
