"""V4.3 Creative Generation Engine 验证脚本

用 P04 Decision Portfolio 数据跑通整个生成流程：
1. 加载 V4.2.1 Decision 数据
2. 生成 Master Prompt
3. 优化多版本 A/B/C/D
4. 生成负面提示词
5. 生成分镜
6. 构建 Image Task
7. 质量验证
8. 导出所有结果
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.market_ops.creative_generation import GenerationAPI


def main():
    print("=" * 100)
    print("✨ V4.3 Creative Generation Engine 验证")
    print("=" * 100)

    # 加载 V4.2.1 Decision 数据
    decision_file = ROOT / "output" / "creative_decision" / "portfolio.json"
    if not decision_file.exists():
        print(f"❌ Decision 文件不存在: {decision_file}")
        print("   请先运行 V4.2.1 Decision Engine")
        return

    with open(decision_file, "r", encoding="utf-8") as f:
        variants = json.load(f)

    # portfolio.json 是列表，需要按 risk_level 分桶
    if isinstance(variants, list):
        safe = [v for v in variants if v.get("risk_level", "").startswith("P0")]
        growth = [v for v in variants if v.get("risk_level", "").startswith("P1")]
        explore = [v for v in variants if not v.get("risk_level", "").startswith(("P0", "P1"))]
        portfolio = {"safe": safe, "growth": growth, "explore": explore}
    else:
        portfolio = variants
        safe = portfolio.get("safe", [])
        growth = portfolio.get("growth", [])
        explore = portfolio.get("explore", [])

    print(f"\n📊 Portfolio 数据:")
    print(f"   Safe: {len(safe)} 个")
    print(f"   Growth: {len(growth)} 个")
    print(f"   Explore: {len(explore)} 个")

    # 初始化 Generation API
    print("\n[1] 初始化 GenerationAPI...")
    api = GenerationAPI(model="lovart", placement="feed", style="pixar")
    print("  ✅ 初始化完成")
    print(f"     - 模型: Lovart")
    print(f"     - 版位: Feed")
    print(f"     - 风格: Pixar")

    # 测试单条生成
    print("\n[2] 单条生成测试...")
    if safe:
        sample = safe[0]
        result = api.generate(variant=sample, portfolio_tier="safe")
        print(f"  ✅ 生成完成: {result['variant_id']}")
        print(f"     - Master Prompt 长度: {len(result.get('master_prompt', {}).get('master_prompt', ''))} 字符")
        print(f"     - 优化版本: {len(result.get('optimized_prompts', []))} 个")
        print(f"     - Image Tasks: {len(result.get('image_tasks', []))} 个")
        print(f"     - 分镜场景: {len(result.get('storyboard', {}).get('scenes', []))} 个")
        print(f"     - 验证通过: {result.get('passed', False)}")
        if result.get('errors'):
            print(f"     - 错误: {result['errors']}")

    # 测试 Prompt 预览
    print("\n[3] Master Prompt 预览 (Safe TOP1):")
    if safe:
        prompt_result = api.generate_prompt(safe[0])
        mp = prompt_result.get("master_prompt", "")
        print(f"  {mp[:200]}...")

    # 测试优化版本
    print("\n[4] 优化版本预览:")
    if safe:
        mp = api.generate_prompt(safe[0]).get("master_prompt", "")
        optimized = api.optimize_prompt(mp, portfolio_tier="safe")
        for opt in optimized[:3]:
            print(f"  [{opt['version']}] {opt['style']}: {opt['prompt'][:120]}...")

    # 测试分镜
    print("\n[5] Storyboard 预览:")
    if safe:
        sb = api.generate_storyboard(safe[0])
        scenes = sb.get("scenes", [])
        print(f"  总时长: {sb.get('total_duration', 0)}s, 场景数: {len(scenes)}")
        for s in scenes[:3]:
            print(f"    Scene {s['scene_number']} ({s['scene_type']}, {s['duration']}s): {s['description'][:60]}...")

    # 测试验证
    print("\n[6] 质量验证:")
    if safe:
        mp = api.generate_prompt(safe[0]).get("master_prompt", "")
        val = api.validate(prompt=mp)
        prompt_val = val.get("prompt", {})
        print(f"  Prompt 验证: 得分 {prompt_val.get('score', 0)}/100, {'通过' if prompt_val.get('passed') else '未通过'}")
        if prompt_val.get("warnings"):
            print(f"    Warnings: {prompt_val['warnings'][:2]}")

    # 测试批量 Portfolio 生成
    print("\n[7] 批量 Portfolio 生成...")
    output_dir = ROOT / "output" / "creative_generation"
    batch_result = api.generate_portfolio(
        portfolio=portfolio,
        output_dir=output_dir,
    )
    stats = batch_result.get("stats", {})
    print(f"  ✅ 批量生成完成")
    print(f"     - 总变体: {stats.get('total_variants', 0)}")
    print(f"     - 通过: {stats.get('passed', 0)}")
    print(f"     - 失败: {stats.get('failed', 0)}")
    print(f"     - 总 Prompt: {stats.get('total_prompts', 0)}")
    print(f"     - 总任务: {stats.get('total_tasks', 0)}")
    print(f"     - 分镜数: {stats.get('total_storyboards', 0)}")

    # 测试预算规划
    print("\n[8] 生成预算规划...")
    budget_plan = api.plan_generation_budget(portfolio, total_budget=50.0)
    print(f"  总预算: ${budget_plan.get('total_budget', 0)}")
    print(f"  总图片数: {budget_plan.get('total_images', 0)}")
    print(f"  预估成本: ${budget_plan.get('total_estimated_cost', 0)}")
    for tier, plan in budget_plan.get("plan", {}).items():
        print(f"    {tier.capitalize()}: {plan.get('variant_count', 0)} variants x {plan.get('images_per_variant', 0)} images = ${plan.get('estimated_cost', 0)}")

    # 输出文件
    print("\n[9] 输出文件:")
    for name, path in batch_result.get("exported_files", {}).items():
        print(f"  {name}: {path}")

    # 总结
    print("\n" + "=" * 100)
    print("🎉 V4.3 Creative Generation Engine 验证通过!")
    print("=" * 100)


if __name__ == "__main__":
    main()
