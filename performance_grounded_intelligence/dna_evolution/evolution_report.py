"""Evolution Report — 演化报告摘要

从演化引擎的运行结果生成人类可读的演化报告。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import DNA_EVOLUTION_DIR, EVO_TOP_WINNERS, ensure_dirs


class EvolutionReporter:
    """演化报告生成器"""

    def __init__(self):
        self.summary: dict = {}
        self.report_lines: List[str] = []

    def generate(self, summary: dict,
                 check_results_path: Optional[Path] = None,
                 ranking_path: Optional[Path] = None) -> str:
        """生成演化报告

        Args:
            summary: 演化摘要 (from EvolutionEngine.run())
            check_results_path: evolution_check_results.json 路径
            ranking_path: evolution_ranking.json 路径

        Returns:
            报告文本
        """
        self.summary = summary
        lines = []
        width = 72

        lines.append("=" * width)
        lines.append("  DNA EVOLUTION REPORT — Phase 2.1.8".center(width))
        lines.append("=" * width)
        lines.append("")

        # ── 概述 ──
        lines.append("─" * width)
        lines.append("  OVERVIEW")
        lines.append("─" * width)
        lines.append(f"  Runtime:           {summary.get('runtime_seconds', 0):.1f}s")
        lines.append(f"  Winners Used:      {summary.get('winners_used', 0)}")
        lines.append(f"  Total Variants:    {summary.get('total_variants', 0)}")
        lines.append(f"  Passed:            {summary.get('passed_variants', 0)}")
        lines.append(f"  Failed:            {summary.get('failed_variants', 0)}")
        lines.append(f"  Pass Rate:         {summary.get('pass_rate_pct', 0):.1f}%")
        lines.append(f"  Prompts Generated: {summary.get('prompts_generated', 0)}")
        lines.append(f"  Test Batch Size:   {summary.get('test_batch_size', 0)}")
        lines.append("")

        # ── Quality Gate 分析 ──
        if check_results_path and check_results_path.exists():
            with open(check_results_path, "r", encoding="utf-8") as f:
                check_data = json.load(f)
            results = check_data.get("results", [])

            if results:
                avg_sim = sum(r.get("winner_similarity", 0) for r in results) / len(results)
                avg_div = sum(r.get("diversity", 0) for r in results) / len(results)
                avg_gp = sum(r.get("gameplay_preserve", 0) for r in results) / len(results)
                avg_rv = sum(r.get("reward_visibility", 0) for r in results) / len(results)

                lines.append("─" * width)
                lines.append("  QUALITY GATE METRICS")
                lines.append("─" * width)
                lines.append(f"  Avg Similarity:         {avg_sim:.4f}")
                lines.append(f"  Avg Diversity:          {avg_div:.4f}")
                lines.append(f"  Avg Gameplay Preserve:  {avg_gp:.4f}")
                lines.append(f"  Avg Reward Visibility:  {avg_rv:.4f}")
                lines.append("")

                # 失败原因分布
                fail_reasons: Dict[str, int] = {}
                for r in results:
                    if not r.get("pass", True):
                        for f in r.get("failures", []):
                            reason = f.split("(")[0] if "(" in f else f
                            fail_reasons[reason] = fail_reasons.get(reason, 0) + 1

                if fail_reasons:
                    lines.append("  Failure Reasons:")
                    for reason, count in sorted(fail_reasons.items(), key=lambda x: -x[1]):
                        lines.append(f"    - {reason}: {count}")
                    lines.append("")

        # ── Top 5 Ranking ──
        top5 = summary.get("top5_scores", [])
        if top5:
            lines.append("─" * width)
            lines.append("  TOP 5 EVOLUTION VARIANTS")
            lines.append("─" * width)
            lines.append(f"  {'Rank':<6}{'Score':<10}{'Strategy':<12}{'Creative ID'}")
            lines.append(f"  {'-'*6}{'-'*10}{'-'*12}{'-'*30}")
            for item in top5:
                lines.append(
                    f"  #{item['rank']:<5}"
                    f"{item['evolution_score']:.4f}    "
                    f"{item['strategy']:<12}"
                    f"{item['creative_id']}"
                )
            lines.append("")

        # ── 策略分布 ──
        strategy_counts: Dict[str, int] = {}
        if ranking_path and ranking_path.exists():
            with open(ranking_path, "r", encoding="utf-8") as f:
                ranking_data = json.load(f)
            for item in ranking_data.get("ranking", []):
                s = item.get("strategy", "?")
                strategy_counts[s] = strategy_counts.get(s, 0) + 1

        if strategy_counts:
            lines.append("─" * width)
            lines.append("  STRATEGY DISTRIBUTION")
            lines.append("─" * width)
            for s, c in sorted(strategy_counts.items()):
                lines.append(f"  Strategy {s}: {c} variants")
            lines.append("")

        # ── 输出文件 ──
        output_files = summary.get("output_files", [])
        if output_files:
            lines.append("─" * width)
            lines.append("  OUTPUT FILES")
            lines.append("─" * width)
            for f in output_files:
                lines.append(f"  {f}")
            lines.append("")

        lines.append("=" * width)
        lines.append("  END OF REPORT".center(width))
        lines.append("=" * width)

        self.report_lines = lines
        return "\n".join(lines)

    def save(self, output_path: Optional[Path] = None):
        """保存报告到文件"""
        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "evolution_report.txt")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.report_lines))
            f.write("\n")

        print(f"[EvolutionReporter] 报告已保存: {output_path}")
        return output_path

    def print_report(self):
        """打印报告到控制台"""
        print("\n" + "\n".join(self.report_lines))
