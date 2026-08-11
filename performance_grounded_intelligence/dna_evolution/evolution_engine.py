"""Evolution Engine — DNA 演化总编排

串联整个演化流程:
1. 加载 Winner DNA
2. 生成 Variant Pool (DNA Mutator)
3. Quality Gate 筛选 (Evolution Checker)
4. 生成 Prompts (Prompt Builder V2)
5. 排名 (Evolution Ranker)
6. 导出 Facebook 测试批次 (Experiment Builder)
7. 生成报告 (Evolution Report)
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..config import (
    OUTPUT_DIR, DNA_EVOLUTION_DIR,
    EVO_TOP_WINNERS, EVO_VARIANTS_PER, ensure_dirs,
)
from .dna_mutator import DNAMutator
from .evolution_checker import EvolutionChecker
from .evolution_ranker import EvolutionRanker
from .experiment_builder import ExperimentBuilder
from .evolution_report import EvolutionReporter
from ..generation.prompt_builder import PromptBuilder


class EvolutionEngine:
    """Winner DNA 演化引擎 — 总编排"""

    def __init__(self, skip_prompts: bool = False):
        """
        Args:
            skip_prompts: 跳过 Prompt 生成 (仅测试变异+检查流程)
        """
        self.skip_prompts = skip_prompts

        self.mutator = DNAMutator()
        self.checker = EvolutionChecker()
        self.ranker = EvolutionRanker()
        self.experiment_builder = ExperimentBuilder()
        self.prompt_builder = PromptBuilder()
        self.reporter = EvolutionReporter()

        # 运行时状态
        self.winners: List[dict] = []
        self.variants: List[dict] = []
        self.passed_variants: List[dict] = []
        self.failed_variants: List[dict] = []
        self.prompts: List[dict] = []
        self.ranked: List[dict] = []
        self.test_batch: dict = {}
        self.summary: dict = {}

    def run(self, top_winner_n: Optional[int] = None,
            variants_per: Optional[int] = None) -> dict:
        """运行完整演化流程

        Args:
            top_winner_n: 使用 Top N 个 winner
            variants_per: 每个 winner 变异策略数

        Returns:
            演化摘要 dict
        """
        start_time = time.time()
        top_winner_n = top_winner_n or EVO_TOP_WINNERS
        variants_per = variants_per or EVO_VARIANTS_PER

        print("=" * 60)
        print("  DNA Evolution Engine — Phase 2.1.8")
        print("=" * 60)

        # ── Step 1: 加载 Winner DNA ──
        print("\n[Step 1/7] 加载 Winner DNA...")
        self.winners = self.mutator.load_winner_dna()
        if not self.winners:
            print("[ERROR] 无 Winner DNA 数据, 退出")
            return {"error": "no_winner_dna"}

        # ── Step 2: 生成 Variant Pool ──
        print(f"\n[Step 2/7] 生成 Variant Pool ({top_winner_n} winners × {variants_per} strategies)...")
        self.variants = self.mutator.generate_pool(top_n=top_winner_n)

        # ── Step 3: Quality Gate 筛选 ──
        print(f"\n[Step 3/7] Quality Gate 筛选...")
        # 构建 winner DNA 索引
        winner_dnas = {}
        for w in self.winners:
            asset_id = w.get("asset_id", "")
            if asset_id:
                winner_dnas[asset_id] = w.get("dna", {})

        self.passed_variants, self.failed_variants = self.checker.filter_variants(
            self.variants, winner_dnas
        )
        self.checker.save_results()

        # ── Step 4: 生成 Prompts ──
        if not self.skip_prompts and self.passed_variants:
            print(f"\n[Step 4/7] 生成 Evolutionary Prompts...")
            self.prompts = self.prompt_builder.build_batch_from_mutations(
                self.passed_variants
            )
            self.prompt_builder.save_mutation_prompts(self.prompts)

        # ── Step 5: 排名 ──
        print(f"\n[Step 5/7] 排名...")
        self.ranked = self.ranker.rank(self.passed_variants)
        self.ranker.save()

        # ── Step 6: 导出测试批次 ──
        print(f"\n[Step 6/7] 导出 Facebook 测试批次...")
        self.test_batch = self.experiment_builder.build_test_batch(
            self.ranked, self.prompts
        )
        self.experiment_builder.save()

        # ── 生成摘要 ──
        elapsed = time.time() - start_time
        pass_rate = (len(self.passed_variants) / len(self.variants) * 100
                     if self.variants else 0)

        self.summary = {
            "version": "2.1.8-evo",
            "runtime_seconds": round(elapsed, 2),
            "winners_used": min(top_winner_n, len(self.winners)),
            "total_variants": len(self.variants),
            "passed_variants": len(self.passed_variants),
            "failed_variants": len(self.failed_variants),
            "pass_rate_pct": round(pass_rate, 1),
            "prompts_generated": len(self.prompts),
            "test_batch_size": self.test_batch.get("total_creatives", 0),
            "top5_scores": [
                {
                    "rank": i + 1,
                    "creative_id": v.get("creative_id", "?"),
                    "evolution_score": v.get("_evolution_score", 0),
                    "strategy": v.get("strategy", ""),
                }
                for i, v in enumerate(self.ranked[:5])
            ],
            "output_files": [
                str(DNA_EVOLUTION_DIR / "dna_variants.json"),
                str(DNA_EVOLUTION_DIR / "evolution_check_results.json"),
                str(DNA_EVOLUTION_DIR / "evolution_ranking.json"),
                str(DNA_EVOLUTION_DIR / "facebook_test_batch.json"),
            ],
        }

        # 保存摘要
        self._save_summary()

        # ── Step 7: 生成报告 ──
        print(f"\n[Step 7/7] 生成演化报告...")
        self.reporter.generate(
            self.summary,
            check_results_path=DNA_EVOLUTION_DIR / "evolution_check_results.json",
            ranking_path=DNA_EVOLUTION_DIR / "evolution_ranking.json",
        )
        self.reporter.save()
        self.reporter.print_report()

        print("\n" + "=" * 60)
        print("  Evolution Complete!")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Variants: {len(self.variants)} → Passed: {len(self.passed_variants)} ({pass_rate:.1f}%)")
        print(f"  Prompts: {len(self.prompts)}")
        print(f"  Test Batch: {self.summary['test_batch_size']} creatives")
        print("=" * 60)

        return self.summary

    def _save_summary(self):
        """保存演化摘要"""
        ensure_dirs()
        output_path = DNA_EVOLUTION_DIR / "evolution_summary.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)

        print(f"\n[EvolutionEngine] 摘要已保存: {output_path}")


def run_phase9(top_winner_n: int = 10, variants_per: int = 4,
               skip_prompts: bool = False) -> dict:
    """便捷函数: 运行 Phase 9 (DNA Evolution)

    Args:
        top_winner_n: Top N winners 参与变异
        variants_per: 每个 winner 的变异策略数
        skip_prompts: 跳过 Prompt 生成

    Returns:
        演化摘要
    """
    engine = EvolutionEngine(skip_prompts=skip_prompts)
    return engine.run(top_winner_n=top_winner_n, variants_per=variants_per)
