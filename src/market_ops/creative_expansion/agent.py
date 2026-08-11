"""Facebook Creative Expansion Agent - V4.x 主入口

编排全流程：
1. 输入 Winning Creative 数据
2. 提取 Creative DNA
3. 构建 Variable Matrix
4. 扩量生成 Variants（控制变量法）
5. 生成 Prompts（7类）
6. 质量评分 + 排序
7. 输出结构化文件
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.market_ops.creative_expansion.dna_extractor import CreativeDNAExtractor
from src.market_ops.creative_expansion.expansion_engine import ExpansionEngine, VariableMatrix
from src.market_ops.creative_expansion.prompt_generator import PromptGenerator
from src.market_ops.creative_expansion.quality_scorer import QualityScorer


class FacebookCreativeExpansionAgent:
    """Facebook 爆款素材扩量系统
    
    输入: Facebook Winning Creative + 数据
    输出: Facebook 可测试 Creative Variants（含完整 Prompts + 评分）
    """

    def __init__(self, output_dir: str | Path = ""):
        self.dna_extractor = CreativeDNAExtractor()
        self.variable_matrix = VariableMatrix()
        self.prompt_generator = PromptGenerator()
        self.quality_scorer = QualityScorer()

        self.output_dir = Path(output_dir) if output_dir else (
            ROOT / "output" / "creative_expansion"
        )

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(
        self,
        lovart_results: list[dict],
        video_analysis: dict,
        target_variants: int = 100,
    ) -> dict:
        """运行完整扩量流程

        Args:
            lovart_results: Lovart AI 分析结果列表
            video_analysis: video_feature_analysis.json 内容
            target_variants: 目标变体数量

        Returns:
            汇总报告 dict
        """
        t0 = datetime.now()
        print("=" * 100)
        print("🚀 Facebook Creative Expansion Agent - V4.x")
        print("=" * 100)

        # Step 1: 提取 Creative DNA
        print("\n[Step 1] 提取 Creative DNA...")
        dna_list = self.dna_extractor.extract(lovart_results, video_analysis)
        print(f"  ✅ 提取了 {len(dna_list)} 个 Winning Creative DNA")
        for d in dna_list:
            print(f"    #{d.variant_id} | ROAS={d.performance.get('roas', 'N/A')}")

        if not dna_list:
            print("  ❌ 无 Winning Creative DNA，退出")
            return {}

        # 取最佳 Creative 作为扩量基准
        best_dna = max(dna_list, key=lambda d: float(d.performance.get("roas", 0)))
        best_dna_dict = asdict(best_dna)
        print(f"\n  🏆 扩量基准: #{best_dna.variant_id} (ROAS={best_dna.performance.get('roas', 'N/A')})")

        # DNA 树状图
        graph_text = self.dna_extractor.to_graph_text(best_dna)
        print(f"\n{graph_text}")

        # Step 2: 构建 Variable Matrix
        print("\n[Step 2] 构建 Variable Matrix...")
        matrix = self.variable_matrix.get_variable_slots(best_dna_dict)
        p0_count = sum(1 for v in matrix if v.risk_level == "P0")
        p1_count = sum(1 for v in matrix if v.risk_level == "P1")
        p2_count = sum(1 for v in matrix if v.risk_level == "P2")
        total_combos = 1
        for v in matrix:
            if v.candidate_values:
                total_combos *= len(v.candidate_values)
        print(f"  ✅ 变量维度: P0={p0_count} P1={p1_count} P2={p2_count}")
        print(f"  📊 理论组合数: {total_combos}")

        # Step 3: 扩量生成 Variants
        print(f"\n[Step 3] 扩量生成 Variants (目标={target_variants})...")
        engine = ExpansionEngine(self.variable_matrix, max_variants=target_variants)
        variants = engine.expand(best_dna_dict, target_count=target_variants)
        print(f"  ✅ 生成 {len(variants)} 个 Variants")
        p0_variants = [v for v in variants if v.risk_level == "P0"]
        p1_variants = [v for v in variants if v.risk_level == "P1"]
        p2_variants = [v for v in variants if v.risk_level == "P2"]
        print(f"     P0(安全): {len(p0_variants)} | P1(中风险): {len(p1_variants)} | P2(高风险): {len(p2_variants)}")

        # Step 4: 生成 Prompts
        print(f"\n[Step 4] 生成 Prompts...")
        all_prompts = []
        for v in variants:
            prompts = self.prompt_generator.generate(v.modified_dna, best_dna_dict)
            prompts_dict = asdict(prompts)
            prompts_dict["variant_id"] = v.variant_id
            prompts_dict["changed_dimension"] = v.changed_dimension
            prompts_dict["changed_path"] = v.changed_path
            prompts_dict["old_value"] = v.old_value
            prompts_dict["new_value"] = v.new_value
            prompts_dict["risk_level"] = v.risk_level
            prompts_dict["modified_dna"] = v.modified_dna
            prompts_dict["generation_priority"] = v.generation_priority
            all_prompts.append(prompts_dict)
        print(f"  ✅ 为 {len(all_prompts)} 个 Variants 生成了完整 Prompts")

        # Step 5: 质量评分
        print(f"\n[Step 5] 质量评分...")
        scored_variants = []
        for v in variants:
            v_dna = v.modified_dna.copy()
            v_dna["variant_id"] = v.variant_id
            score = self.quality_scorer.score(v_dna, best_dna_dict)
            scored_variants.append((v, score))
        
        # 按 overall_score 降序排序
        scored_variants.sort(key=lambda x: x[1].overall_score, reverse=True)
        print(f"  ✅ 评分完成")
        if scored_variants:
            top = scored_variants[0]
            print(f"  🥇 最高分: {top[0].variant_id} = {top[1].overall_score:.1f}/100")
            print(f"     变更: {top[0].changed_dimension} | {top[0].old_value} → {top[0].new_value}")

        # Step 6: 输出文件
        print(f"\n[Step 6] 输出文件...")
        self._write_output(
            best_dna=best_dna,
            best_dna_dict=best_dna_dict,
            dna_list=dna_list,
            matrix=matrix,
            variants=variants,
            scored_variants=scored_variants,
            all_prompts=all_prompts,
            graph_text=graph_text,
        )

        elapsed = (datetime.now() - t0).total_seconds()
        print(f"\n{'=' * 100}")
        print(f"✅ 全流程完成! 耗时 {elapsed:.1f}s")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"{'=' * 100}")

        return {
            "total_dna": len(dna_list),
            "total_variants": len(variants),
            "total_scored": len(scored_variants),
            "output_dir": str(self.output_dir),
            "elapsed_sec": elapsed,
        }

    # ------------------------------------------------------------------
    # 输出文件
    # ------------------------------------------------------------------
    def _write_output(
        self,
        best_dna,
        best_dna_dict: dict,
        dna_list,
        matrix,
        variants,
        scored_variants,
        all_prompts,
        graph_text: str,
    ):
        """按 PRD 目录结构输出文件"""
        # 创建目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        summary_dir = self.output_dir / "summary"
        summary_dir.mkdir(exist_ok=True)

        # 每个Variant一个目录
        for v, score in scored_variants:
            v_dir = self.output_dir / v.variant_id
            v_dir.mkdir(exist_ok=True)

            # variables.json
            variables = {
                "variant_id": v.variant_id,
                "parent_dna_id": v.parent_dna_id,
                "changed_dimension": v.changed_dimension,
                "changed_path": v.changed_path,
                "old_value": v.old_value,
                "new_value": v.new_value,
                "risk_level": v.risk_level,
                "generation_priority": v.generation_priority,
            }
            with open(v_dir / "variables.json", "w", encoding="utf-8") as f:
                json.dump(variables, f, indent=2, ensure_ascii=False)

            # prompts.json - 找到对应的 prompts
            prompts_for_v = next(
                (p for p in all_prompts if p["variant_id"] == v.variant_id), None
            )
            if prompts_for_v:
                with open(v_dir / "prompts.json", "w", encoding="utf-8") as f:
                    json.dump(prompts_for_v, f, indent=2, ensure_ascii=False, default=str)

            # storyboard.json
            storyboard = prompts_for_v.get("storyboard_prompt", "") if prompts_for_v else ""
            with open(v_dir / "storyboard.json", "w", encoding="utf-8") as f:
                json.dump({"storyboard": storyboard}, f, indent=2, ensure_ascii=False)

            # thumbnail.json
            thumbnail = prompts_for_v.get("thumbnail_prompt", "") if prompts_for_v else ""
            with open(v_dir / "thumbnail.json", "w", encoding="utf-8") as f:
                json.dump({"thumbnail_prompt": thumbnail}, f, indent=2, ensure_ascii=False)

            # quality.json
            quality = asdict(score)
            with open(v_dir / "quality.json", "w", encoding="utf-8") as f:
                json.dump(quality, f, indent=2, ensure_ascii=False, default=str)

        # summary/ranking.csv
        ranking_path = summary_dir / "ranking.csv"
        with open(ranking_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "rank", "variant_id", "overall_score",
                "creative_similarity", "facebook_readability",
                "hook_strength", "visual_quality",
                "brand_consistency", "ai_generation_confidence",
                "changed_dimension", "old_value", "new_value",
                "risk_level",
            ])
            for rank, (v, score) in enumerate(scored_variants, 1):
                writer.writerow([
                    rank, v.variant_id, f"{score.overall_score:.1f}",
                    f"{score.creative_similarity:.1f}",
                    f"{score.facebook_readability:.1f}",
                    f"{score.hook_strength:.1f}",
                    f"{score.visual_quality:.1f}",
                    f"{score.brand_consistency:.1f}",
                    f"{score.ai_generation_confidence:.1f}",
                    v.changed_dimension, v.old_value, v.new_value,
                    v.risk_level,
                ])
        print(f"  📊 ranking.csv → {ranking_path}")

        # summary/expansion_report.md
        report = self._build_report(
            best_dna, dna_list, matrix, variants, scored_variants, graph_text
        )
        report_path = summary_dir / "expansion_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  📄 expansion_report.md → {report_path}")

        # summary/variable_matrix.json
        matrix_data = {
            "total_dimensions": len(matrix),
            "p0_count": sum(1 for v in matrix if v.risk_level == "P0"),
            "p1_count": sum(1 for v in matrix if v.risk_level == "P1"),
            "p2_count": sum(1 for v in matrix if v.risk_level == "P2"),
            "dimensions": [
                {
                    "dimension": v.dimension_name,
                    "path": v.path,
                    "risk_level": v.risk_level,
                    "current_value": "",
                    "possible_values": v.candidate_values,
                }
                for v in matrix
            ],
        }
        with open(summary_dir / "variable_matrix.json", "w", encoding="utf-8") as f:
            json.dump(matrix_data, f, indent=2, ensure_ascii=False)
        print(f"  📋 variable_matrix.json → {summary_dir / 'variable_matrix.json'}")

    def _build_report(
        self, best_dna, dna_list, matrix, variants, scored_variants, graph_text
    ) -> str:
        """生成 expansion_report.md"""
        lines = [
            "# Facebook Creative Expansion Report",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 项目: P04 Merge Witches",
            f"> 扩量基准: #{best_dna.variant_id} (ROAS={best_dna.performance.get('roas', 'N/A')})",
            "",
            "---",
            "",
            "## 一、Winning Creative DNA",
            "",
            "```",
            graph_text,
            "```",
            "",
            "---",
            "",
            "## 二、变量矩阵",
            "",
            "| 风险等级 | 维度数 | 说明 |",
            "|----------|--------|------|",
        ]

        p0 = sum(1 for v in matrix if v.risk_level == "P0")
        p1 = sum(1 for v in matrix if v.risk_level == "P1")
        p2 = sum(1 for v in matrix if v.risk_level == "P2")
        lines.append(f"| P0(安全) | {p0} | 换颜色/粒子/生物，低风险 |")
        lines.append(f"| P1(中等) | {p1} | 换场景/服装/镜头，中风险 |")
        lines.append(f"| P2(高风险) | {p2} | 换角色/风格/Hook，高风险 |")
        lines.extend(["", "---", "", "## 三、扩量结果", ""])

        lines.append(f"- **总变体数**: {len(variants)}")
        lines.append(f"- **P0 变体**: {sum(1 for v, _ in scored_variants if v.risk_level == 'P0')}")
        lines.append(f"- **P1 变体**: {sum(1 for v, _ in scored_variants if v.risk_level == 'P1')}")
        lines.append(f"- **P2 变体**: {sum(1 for v, _ in scored_variants if v.risk_level == 'P2')}")

        # TOP 10
        lines.extend(["", "### TOP 10 变体", "",
            "| 排名 | Variant | 总分 | 变更维度 | 旧值 → 新值 | 风险 |",
            "|------|---------|------|----------|------------|------|",
        ])
        for rank, (v, score) in enumerate(scored_variants[:10], 1):
            lines.append(
                f"| {rank} | {v.variant_id} | {score.overall_score:.1f} | "
                f"{v.changed_dimension} | {v.old_value} → {v.new_value} | {v.risk_level} |"
            )

        # 控制变量说明
        lines.extend([
            "", "---", "",
            "## 四、控制变量实验说明", "",
            "每个 Variant 仅变更 **一个** 变量，确保 A/B 测试可归因。",
            "",
            "| 风险 | 建议测试数量 | 每组预算 | 测试周期 |",
            "|------|------------|---------|---------|",
            "| P0 | 10-20组 | $500/天 | 3天 |",
            "| P1 | 5-10组 | $500/天 | 3天 |",
            "| P2 | 2-5组 | $300/天 | 5天 |",
            "",
            "---", "",
            "## 五、Facebook 最佳实践约束", "",
            "- Hook 优先: 前3秒主体必须突出",
            "- 画面主体: 占40-70%",
            "- 竖屏优先: 默认9:16",
            "- 节奏: 15-30s默认，支持6s Hook Cut",
            "- 品牌元素: Logo左上角固定位置",
            "- 风格一致性: 与Winning Creative视觉DNA一致",
        ])

        return "\n".join(lines)


# ======================================================================
# CLI 入口
# ======================================================================
def main():
    """用 P04 数据运行全流程"""
    import argparse

    parser = argparse.ArgumentParser(description="Facebook Creative Expansion Agent")
    parser.add_argument("--target", type=int, default=100, help="目标变体数量")
    parser.add_argument("--output", type=str, default="", help="输出目录")
    args = parser.parse_args()

    # 加载 P04 数据
    p04_dir = ROOT / "output" / "video_intelligence" / "p04"
    lovart_file = p04_dir / "lovart_analysis_results.json"
    analysis_file = p04_dir / "video_feature_analysis.json"

    if not lovart_file.exists():
        print(f"❌ Lovart分析文件不存在: {lovart_file}")
        return
    if not analysis_file.exists():
        print(f"❌ 视觉特征分析文件不存在: {analysis_file}")
        return

    with open(lovart_file, "r", encoding="utf-8") as f:
        lovart_results = json.load(f)

    with open(analysis_file, "r", encoding="utf-8") as f:
        video_analysis = json.load(f)

    output_dir = args.output or str(ROOT / "output" / "creative_expansion")
    agent = FacebookCreativeExpansionAgent(output_dir=output_dir)
    result = agent.run(
        lovart_results=lovart_results,
        video_analysis=video_analysis,
        target_variants=args.target,
    )
    print(f"\n🎯 结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
