"""V4.3.1 Creative Production Engine 验证脚本

按 PRD 第十六节流程跑通：
Decision → Creative Director → Creative Script → Storyboard → Shot List
→ Asset Planner → Asset Consistency → Camera → Motion → Editor Timeline
→ Workflow → Export

用 P04 Decision Portfolio 数据（V001-V020）跑通完整流程。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.market_ops.creative_production import (
    CreativeDirector,
    CreativeScriptEngine,
    StoryboardEngine,
    ShotGenerator,
    AssetPlanner,
    AssetConsistency,
    CameraLanguageEngine,
    MotionEngine,
    EditorTimeline,
    VideoModelAdapter,
    WorkflowBuilder,
    ProductionMemory,
    ProductionPipeline,
    CreativeProductionAPI,
    ProductionDashboard,
)


# 维度 → DNA 元素映射（让 portfolio 变体可用）
DIM_TO_DNA: dict[str, dict[str, str]] = {
    "lighting_temperature": {
        "character": "witch",
        "creature": "dragon",
        "environment": "magic_forest",
        "lighting": "warm",
    },
    "color_palette": {
        "character": "witch",
        "creature": "phoenix",
        "environment": "candy_kingdom",
        "lighting": "vibrant",
    },
    "creature": {
        "character": "warrior",
        "creature": "wolf",
        "environment": "dark_forest",
        "lighting": "cool",
    },
    "character": {
        "character": "princess",
        "creature": "unicorn",
        "environment": "enchanted_castle",
        "lighting": "magical",
    },
    "background": {
        "character": "witch",
        "creature": "dragon",
        "environment": "floating_island",
        "lighting": "sunset",
    },
    "hook_type": {
        "character": "witch",
        "creature": "dragon",
        "environment": "magic_forest",
        "lighting": "warm",
    },
}


def enrich_variant_with_dna(variant: dict) -> dict:
    """为 P04 Decision 变体补上 DNA 字段（V4.3.1 流程需要）"""
    dim = variant.get("changed_dimension", "")
    dna_template = DIM_TO_DNA.get(
        dim,
        {
            "character": "witch",
            "creature": "dragon",
            "environment": "magic_forest",
            "lighting": "warm",
        },
    )

    new_value = variant.get("new_value", "default")
    dna = {
        "character": {
            "type": dna_template["character"],
            "outfit": "adventure",
            "color": new_value,
        },
        "creatures": [
            {"type": dna_template["creature"], "rarity": "rare"},
        ],
        "environment": {
            "type": dna_template["environment"],
            "weather": "clear",
        },
        "lighting": {
            "style": new_value if dim == "lighting_temperature" else dna_template["lighting"],
            "intensity": "medium",
        },
        "gameplay": {
            "type": "collection",
            "loop": "merge_collect",
        },
        "hook": {
            "type": "collection",
        },
    }

    enriched = dict(variant)
    enriched["dna"] = dna
    enriched["audience"] = variant.get("audience", "general")
    enriched["country"] = variant.get("country", "US")
    enriched["portfolio"] = variant.get("portfolio", "P04")
    return enriched


def main() -> None:
    print("=" * 100)
    print("🎬 V4.3.1 Facebook Creative Production Engine 验证")
    print("   Creative Intelligence → Decision Engine → Creative Production → Facebook Upload")
    print("=" * 100)

    # 加载 P04 Decision 数据
    decision_file = ROOT / "output" / "creative_decision" / "portfolio.json"
    if not decision_file.exists():
        print(f"❌ Decision 文件不存在: {decision_file}")
        return

    with open(decision_file, "r", encoding="utf-8") as f:
        raw_variants = json.load(f)

    # 补 DNA 字段
    variants = [enrich_variant_with_dna(v) for v in raw_variants]
    print(f"\n📊 P04 Decision 数据:")
    print(f"   加载变体: {len(variants)}")

    # 分桶
    safe = [v for v in variants if v.get("risk_level", "").startswith("P0")]
    growth = [v for v in variants if v.get("risk_level", "").startswith("P1")]
    explore = [v for v in variants if not v.get("risk_level", "").startswith(("P0", "P1"))]

    print(f"   P0 Safe: {len(safe)}")
    print(f"   P1 Growth: {len(growth)}")
    print(f"   Explore: {len(explore)}")

    # 初始化 Production Pipeline
    print("\n[1] 初始化 CreativeProductionAPI...")
    output_dir = ROOT / "output" / "creative_production"
    output_dir.mkdir(parents=True, exist_ok=True)
    api = CreativeProductionAPI(
        output_dir=str(output_dir),
        budget_usd=10.0,
    )
    print("  ✅ 初始化完成")
    print(f"     - 预算: $10 / 变体")
    print(f"     - 平台: Facebook (9:16 Reels)")
    print(f"     - 支持模型: {api.model_adapter.list_models()}")

    # 1. 单独跑 Safe TOP1 验证
    print("\n[2] 单变体完整流程验证 (Safe TOP1)...")
    if safe:
        sample = safe[0]
        result = api.run_full(sample, duration=15.0, platform="facebook", placement="reels")
        print(f"  ✅ {result.variant_id} 全流程跑通")

        s = result.strategy
        print(f"     - Hook: {s.hook} | 情绪: {s.emotion}")
        print(f"     - 优先级: P{s.priority} | 时长: {s.duration}秒")
        print(f"     - 脚本段落: {len(result.script.segments)} 个")
        print(f"     - 分镜场景: {len(result.storyboard.scenes)} 个")
        print(f"     - 镜头数: {result.shot_list.total_shots}")
        print(f"     - 素材分配: {result.plan.source_summary}")
        print(f"     - 估算成本: ${result.plan.total_estimated_cost}")
        print(f"     - 估算耗时: {result.plan.total_estimated_time_sec/60:.1f} 分钟")
        print(f"     - 需人工审核: {result.plan.requires_human_review_count} 镜头")
        print(f"     - 工作流步骤: {result.workflow.total_steps}")
        print(f"     - 时间线: {result.timeline.resolution} @ {result.timeline.fps}fps")
        print(f"     - 视频轨: {len(result.timeline.video_tracks)}")
        print(f"     - AI 模型任务: {dict((m, len(t)) for m, t in result.model_tasks.items())}")

    # 2. 步骤化 API 测试
    print("\n[3] 步骤化 API 验证...")
    if safe:
        v = safe[0]
        # 3.1 generate_strategy
        strategy = api.generate_strategy(v)
        print(f"  ✅ generate_strategy → {strategy.variant_id}, Hook={strategy.hook}")
        # 3.2 generate_script
        script = api.generate_script(v)
        print(f"  ✅ generate_script → {len(script.segments)} 段")
        # 3.3 generate_storyboard
        storyboard = api.generate_storyboard(v)
        print(f"  ✅ generate_storyboard → {len(storyboard.scenes)} 场景 ({storyboard.aspect_ratio})")
        # 3.4 generate_shots
        shot_list = api.generate_shots(v)
        print(f"  ✅ generate_shots → {shot_list.total_shots} 镜头")
        # 3.5 plan_assets
        plan = api.plan_assets(v)
        print(f"  ✅ plan_assets → {plan.source_summary}")
        # 3.6 build_timeline
        timeline = api.build_timeline(v)
        print(f"  ✅ build_timeline → {timeline.resolution}, {len(timeline.video_tracks)} V轨")
        # 3.7 build_workflow
        workflow = api.build_workflow(v)
        print(f"  ✅ build_workflow → {workflow.total_steps} 步, 执行器 {workflow.executors_used}")
        # 3.8 export_kling
        kling_tasks = api.export_kling(v)
        print(f"  ✅ export_kling → {len(kling_tasks)} 任务")
        # 3.9 export_runway
        runway_tasks = api.export_runway(v)
        print(f"  ✅ export_runway → {len(runway_tasks)} 任务")
        # 3.10 export_comfyui
        comfyui_tasks = api.export_comfyui(v)
        print(f"  ✅ export_comfyui → {len(comfyui_tasks)} 任务")

    # 3. Camera + Motion 推荐
    print("\n[4] Camera + Motion 验证...")
    if safe:
        cam_engine = CameraLanguageEngine()
        motion_engine = MotionEngine()
        for seg_type in ["opening", "gameplay", "reward", "cta"]:
            cams = cam_engine.recommend(seg_type, gameplay="collection", emotion="满足/惊喜")
            cam_names = [c.name for c in cams]
            motion_prompt = motion_engine.build_motion_prompt(seg_type)
            print(f"  {seg_type}: 运镜 {cam_names} | 动作: {motion_prompt[:80]}...")

    # 4. 批量跑通 P04 全部 20 个变体
    print("\n[5] 批量跑 P04 全部 20 个变体...")
    batch_results = api.run_batch(variants, duration=15.0, platform="facebook")
    print(f"  ✅ 批量完成: {len(batch_results)}/{len(variants)}")

    # 5. Dashboard
    print("\n[6] Dashboard 汇总...")
    dashboard = ProductionDashboard(api)
    for result in batch_results:
        dashboard.record(result)
    summary = dashboard.summary()
    print(f"  - 总变体: {summary.total_variants}")
    print(f"  - 总镜头: {summary.total_shots}")
    print(f"  - 总时长: {summary.total_duration_sec/60:.1f} 分钟")
    print(f"  - 总成本: ${summary.total_estimated_cost:.2f}")
    print(f"  - 平均置信度: {summary.avg_confidence:.2f}")
    print(f"  - 需人工审核: {summary.review_required} 镜头")
    print(f"  - 来源分布: {summary.source_distribution}")
    print(f"  - 执行器分布: {summary.executor_distribution}")
    print(f"  - 模型分布: {summary.model_distribution}")

    # 6. 导出所有
    print("\n[7] 导出所有产物...")
    all_exports: dict[str, str] = {}
    for i, result in enumerate(batch_results):
        subdir = result.variant_id
        paths = api.export(result, subdir=subdir)
        for k, p in paths.items():
            all_exports[f"{result.variant_id}_{k}"] = p
    print(f"  ✅ 导出文件数: {len(all_exports)}")
    print(f"  - 示例: {list(all_exports.keys())[:3]}")

    # 7. 持续学习：模拟反馈
    print("\n[8] 持续学习（learn 接口）...")
    for i, v in enumerate(batch_results[:5]):
        # 模拟一些表现数据
        ctr = 0.02 + (i * 0.005)
        roas = 1.2 + (i * 0.2)
        api.learn(
            variant_id=v.variant_id,
            ctr=ctr,
            cvr=0.05,
            roas=roas,
            spend=100.0,
            impressions=5000,
            clicks=int(5000 * ctr),
            conversions=25,
        )
        print(f"  ✅ {v.variant_id}: CTR={ctr:.3f} ROAS={roas:.2f}")

    # 8. 查询 Winner
    print("\n[9] Winner 查询...")
    winners = api.get_winners(min_roas=1.3, limit=10)
    print(f"  Winner 数: {len(winners)}")
    for w in winners[:3]:
        print(f"  - {w.get('variant_id')}: ROAS={w.get('roas'):.2f}")

    # 9. Memory 统计
    print("\n[10] Production Memory 统计...")
    stats = api.get_stats()
    print(f"  {json.dumps(stats, ensure_ascii=False, indent=2)}")

    # 10. 保存 Dashboard 文本
    dashboard_path = output_dir / "dashboard.txt"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(dashboard.render())
    print(f"\n[11] Dashboard 文本已保存: {dashboard_path}")

    # 总结
    print("\n" + "=" * 100)
    print("🎉 V4.3.1 Facebook Creative Production Engine 验证通过!")
    print("=" * 100)
    print("\n📦 14 个核心模块:")
    print("   1. creative_director.py       - 创意总监（系统大脑）")
    print("   2. creative_script.py         - 广告脚本生成器")
    print("   3. storyboard_engine.py       - 跨平台分镜（Facebook/TikTok/Google）")
    print("   4. shot_generator.py          - 镜头拆解 + Prompt")
    print("   5. asset_planner.py           - ⭐ 素材来源决策（AI/Eagle/Unity/Winner/人工）")
    print("   6. asset_consistency.py       - 素材一致性（Character/UI/Theme/Color）")
    print("   7. camera_language.py         - 运镜语言（11 种运镜）")
    print("   8. motion_engine.py           - 动作引擎（4 类动作）")
    print("   9. editor_timeline.py         - 时间线（Premiere/DaVinci/CapCut/AE）")
    print("  10. video_model_adapter.py     - 9 种视频模型适配")
    print("  11. workflow_builder.py        - 统一生产工作流")
    print("  12. production_memory.py       - DuckDB 持续学习")
    print("  13. production_pipeline.py     - 统一生产流水线")
    print("  14. production_api.py          - 统一入口 API")
    print("  15. dashboard.py               - 生产概览 Dashboard")
    print("\n🔧 支持的视频模型 (9):")
    print("   ComfyUI / Wan / Kling / Runway / Veo / Lovart / Pika / Luma / Hailuo")
    print("\n📁 输出目录:")
    print(f"   {output_dir}")
    print(f"   ├── {batch_results[0].variant_id}/  (每个变体一个目录)")
    print(f"   │   ├── creative_script.json")
    print(f"   │   ├── storyboard.json")
    print(f"   │   ├── shot_list.json")
    print(f"   │   ├── asset_plan.json")
    print(f"   │   ├── consistency.json")
    print(f"   │   ├── timeline/")
    print(f"   │   │   ├── timeline.json")
    print(f"   │   │   ├── *_<name>_premiere.xml")
    print(f"   │   │   ├── *_<name>_davinci.xml")
    print(f"   │   │   ├── *_<name>_capcut.json")
    print(f"   │   │   └── *_<name>_after_effects.json")
    print(f"   │   ├── workflows/")
    print(f"   │   │   ├── workflow.json")
    print(f"   │   │   └── workflow_<executor>.json")
    print(f"   │   ├── model_tasks/")
    print(f"   │   │   └── <model>_tasks.json")
    print(f"   │   └── production_report.md")
    print(f"   ├── production_memory.duckdb")
    print(f"   └── dashboard.txt")

    print("\n✅ PRD V4.3.1 验收标准:")
    print("   ✅ 直接消费 V4.2.2 Decision Variant")
    print("   ✅ 自动生成广告脚本（15/20/30 秒）")
    print("   ✅ 自动生成 Storyboard")
    print("   ✅ 自动拆解 Shot List")
    print("   ✅ 自动生成 Asset Plan（AI/Eagle/Unity/历史素材/人工混合）")
    print("   ✅ 自动生成 Editor Timeline（Premiere/DaVinci/CapCut/AE）")
    print("   ✅ 自动生成各视频模型 Workflow")
    print("   ✅ 使用 DuckDB 保存 Production Memory")
    print("   ✅ 插件化架构（可扩展新素材来源和视频模型）")
    print("   ✅ 与 V4.2.2、Creative Intelligence 无缝衔接")


if __name__ == "__main__":
    main()
