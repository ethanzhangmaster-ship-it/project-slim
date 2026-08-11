"""Performance Grounded Intelligence — CLI 入口

用法:
  cd project_slim
  python -m performance_grounded_intelligence.run [--phase N] [--skip-clip]

Phases:
  1: Data Fusion (Facebook + Adjust → creative_performance_raw.json)
  2: Asset Resolver (CLIP 聚类 → visual_assets.json)  [--skip-clip 则用 URL 分组]
  3: Image Detection (已集成到 Phase 1)
  4: Winner Mining (三池输出)
  5: Vision DNA (需要 OpenAI API, 无则用规则模式)
  6: Generation Pipeline (Prompt Builder)
  7: Quality Gate (CLIP + DNA Match)
  8: Reports (HTML + JSON 导出)
  9: DNA Evolution Engine (Winner 变异 + Quality Gate + 排名 + FB测试批次)
"""
import sys
import json
import argparse
from pathlib import Path

# 确保 project_slim 在 path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from performance_grounded_intelligence.config import OUTPUT_DIR, WINNERS_DIR, ensure_dirs
from performance_grounded_intelligence.data_connector import PerformanceFuser
from performance_grounded_intelligence.asset_resolver.asset_mapper import AssetMapper
from performance_grounded_intelligence.winner_miner.winner_pools import WinnerPools


def run_phase1():
    """Phase 1 + 3: Data Fusion + Image Detection"""
    print("\n" + "=" * 80)
    print("Phase 1: Data Fusion (Facebook + Adjust)")
    print("=" * 80)
    fuser = PerformanceFuser()
    records = fuser.fuse()
    return records


def run_phase2(records, skip_clip=False):
    """Phase 2: Asset Resolver"""
    print("\n" + "=" * 80)
    print("Phase 2: Asset Resolver")
    print("=" * 80)

    mapper = AssetMapper()

    if skip_clip:
        print("[Phase 2] 使用 thumbnail_url 分组 (跳过 CLIP)")
        assets = mapper.build_from_thumbnail_url(records)
    else:
        # 尝试 CLIP pipeline
        try:
            from performance_grounded_intelligence.asset_resolver.thumbnail_downloader import ThumbnailDownloader
            from performance_grounded_intelligence.asset_resolver.image_embedding import ImageEmbedding
            from performance_grounded_intelligence.asset_resolver.asset_cluster import AssetCluster

            # Step 1: Download thumbnails
            downloader = ThumbnailDownloader()
            image_paths = downloader.download_all(records)

            if not image_paths:
                print("[Phase 2] 无缩略图下载成功, 回退到 URL 分组")
                assets = mapper.build_from_thumbnail_url(records)
            else:
                # Step 2: CLIP embedding
                embedder = ImageEmbedding()
                cache_path = OUTPUT_DIR / "clip_embeddings.npz"
                embeddings = embedder.encode_batch(image_paths, cache_path)

                # Step 3: Cluster
                clusterer = AssetCluster()
                labels = clusterer.cluster(embeddings)

                # Step 4: Map
                assets = mapper.build_assets(labels, records)

        except ImportError as e:
            print(f"[Phase 2] CLIP 依赖缺失 ({e}), 回退到 URL 分组")
            assets = mapper.build_from_thumbnail_url(records)

    mapper.save()
    return assets


def run_phase4(assets):
    """Phase 4: Winner Mining"""
    print("\n" + "=" * 80)
    print("Phase 4: Winner Mining")
    print("=" * 80)

    pools = WinnerPools()
    pools.mine(assets)
    pools.save()
    pools.print_summary()
    return pools


def run_phase5():
    """Phase 5: Vision DNA Extraction"""
    print("\n" + "=" * 80)
    print("Phase 5: Vision DNA Extraction")
    print("=" * 80)

    from performance_grounded_intelligence.vision_dna.dna_extractor import DNAExtractor

    # 加载 pattern winners (包含最多 winner 信息)
    pattern_path = WINNERS_DIR / "creative_pattern_winners.json"
    if not pattern_path.exists():
        print("[Phase 5] 错误: creative_pattern_winners.json 不存在, 请先运行 Phase 4")
        return None

    with open(pattern_path, "r", encoding="utf-8") as f:
        pattern_data = json.load(f)

    winner_assets = pattern_data.get("top_20", [])
    if not winner_assets:
        print("[Phase 5] 无 winner 可分析")
        return None

    extractor = DNAExtractor()
    results = extractor.extract_from_winners(winner_assets)
    return results


def run_phase6():
    """Phase 6: Generation Pipeline (Prompt Builder)"""
    print("\n" + "=" * 80)
    print("Phase 6: Generation Pipeline")
    print("=" * 80)

    from performance_grounded_intelligence.generation.prompt_builder import PromptBuilder

    builder = PromptBuilder()
    builder.load()
    prompts = builder.build_batch(n_variations=3, top_n_winners=3)
    output_path = builder.save_prompts(prompts)

    # 打印摘要
    if prompts:
        print(f"\n  示例 Prompt (Top1 Winner, default):")
        print(f"  {prompts[0]['prompt'][:200]}...")
        print(f"  Constraints: {prompts[0].get('constraints', {})}")

    return prompts


def run_phase7():
    """Phase 7: Quality Gate (placeholder — needs generated images)"""
    print("\n" + "=" * 80)
    print("Phase 7: Quality Gate")
    print("=" * 80)
    print("[Phase 7] Quality Gate 模块已就绪")
    print("  - winner_similarity.py: CLIP 余弦相似度检查 (阈值 0.75)")
    print("  - dna_match_checker.py: DNA 4维匹配 + Production Score V3")
    print("  [Info] 需要生成图才能运行, 当前跳过实际检查")
    return True


def run_phase8():
    """Phase 8: Reports & Export"""
    print("\n" + "=" * 80)
    print("Phase 8: Reports & Export")
    print("=" * 80)

    from performance_grounded_intelligence.reports.ranking_report import RankingReport
    from performance_grounded_intelligence.reports.gallery_report import GalleryReport
    from performance_grounded_intelligence.reports.export import DataExporter

    # Ranking Report
    ranking = RankingReport()
    ranking.generate()

    # Gallery Report (需要 DNA 数据)
    dna_path = OUTPUT_DIR / "true_winner_dna.json"
    if dna_path.exists():
        gallery = GalleryReport()
        gallery.generate()
    else:
        print("[Phase 8] 跳过 Gallery (无 DNA 数据, 请先运行 Phase 5)")

    # Data Export
    exporter = DataExporter()
    export_paths = exporter.export_all()

    print("\n[Phase 8] 导出文件:")
    for name, path in export_paths.items():
        print(f"  - {name}: {path}")

    return export_paths


def run_phase9():
    """Phase 9: DNA Evolution Engine"""
    print("\n" + "=" * 80)
    print("Phase 9: DNA Evolution Engine")
    print("=" * 80)

    from performance_grounded_intelligence.dna_evolution.evolution_engine import run_phase9 as _run_evo

    summary = _run_evo(top_winner_n=10, variants_per=4)

    if summary:
        print("\n[Phase 9] 摘要:")
        print(f"  Winners: {summary.get('winners_used', 0)}")
        print(f"  Total Variants: {summary.get('total_variants', 0)}")
        print(f"  Passed: {summary.get('passed_variants', 0)} ({summary.get('pass_rate_pct', 0):.1f}%)")
        print(f"  Prompts: {summary.get('prompts_generated', 0)}")
        print(f"  Test Batch: {summary.get('test_batch_size', 0)}")

        top5 = summary.get('top5_scores', [])
        if top5:
            print(f"\n  Top 5:")
            for item in top5:
                print(f"    #{item['rank']}: {item['creative_id']} "
                      f"(score={item['evolution_score']:.4f}, {item['strategy']})")

        output_files = summary.get('output_files', [])
        if output_files:
            print(f"\n  输出文件 ({len(output_files)}):")
            for f in output_files:
                print(f"    - {f}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Performance Grounded Intelligence")
    parser.add_argument("--phase", type=int, default=0,
                        help="只运行指定 phase (0=全部)")
    parser.add_argument("--skip-clip", action="store_true",
                        help="跳过 CLIP, 用 thumbnail_url 分组")
    args = parser.parse_args()

    ensure_dirs()

    # Phase 1: Data Fusion
    if args.phase == 0 or args.phase == 1:
        records = run_phase1()
    else:
        # 从缓存加载
        raw_path = OUTPUT_DIR / "creative_performance_raw.json"
        if raw_path.exists():
            with open(raw_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data["records"]
            print(f"[Cache] 从缓存加载 {len(records)} 条记录")
        else:
            print("[Error] 未找到 creative_performance_raw.json, 请先运行 Phase 1")
            sys.exit(1)

    # Phase 2: Asset Resolver
    if args.phase == 0 or args.phase == 2:
        assets = run_phase2(records, skip_clip=args.skip_clip)
    else:
        # 从缓存加载
        assets_path = OUTPUT_DIR / "visual_assets.json"
        if assets_path.exists():
            with open(assets_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assets = data["assets"]
            print(f"[Cache] 从缓存加载 {len(assets)} 个 assets")
        else:
            # 即时生成
            mapper = AssetMapper()
            assets = mapper.build_from_thumbnail_url(records)
            mapper.save()

    # Phase 4: Winner Mining
    if args.phase == 0 or args.phase == 4:
        pools = run_phase4(assets)

    # Phase 5: Vision DNA
    if args.phase == 0 or args.phase == 5:
        run_phase5()

    # Phase 6: Generation Pipeline
    if args.phase == 0 or args.phase == 6:
        run_phase6()

    # Phase 7: Quality Gate
    if args.phase == 0 or args.phase == 7:
        run_phase7()

    # Phase 8: Reports
    if args.phase == 0 or args.phase == 8:
        run_phase8()

    # Phase 9: DNA Evolution Engine
    if args.phase == 0 or args.phase == 9:
        run_phase9()

    print("\n" + "=" * 80)
    print("Done! 输出目录:", OUTPUT_DIR)
    print("=" * 80)


if __name__ == "__main__":
    main()
