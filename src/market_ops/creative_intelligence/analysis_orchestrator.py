"""Phase 4.1 — IAP Creative Intelligence Analysis Orchestrator.

编排 6 层分析流水线，输出统一报告。

流水线：
  1. Performance Layer   → 广告表现分析
  2. Player Attribution  → 玩家归因
  3. Archetype Analysis  → 玩家类型分析
  4. Payment Behavior    → 付费行为分析
  5. LTV Correlation     → LTV 相关性
  6. IAP Fitness         → 综合价值评分
  7. DNA Evolution       → 进化方向生成

输出：
  - iap_analysis_report.json  — 完整分析报告
  - iap_winners.json          — IAP Winner 排名
  - evolution_directions.json — 进化方向（给 Lovart）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .models import CreativeValueProfile
from .creative_performance_analyzer import CreativePerformanceAnalyzer
from .player_attribution_analyzer import PlayerAttributionAnalyzer
from .archetype_analysis import ArchetypeAnalyzer
from .payment_behavior_analyzer import PaymentBehaviorAnalyzer
from .ltv_correlation_engine import LTVCorelationEngine
from .iap_fitness_engine import IAPFitnessEngine
from .creative_dna_evolution import CreativeDNAEvolutionEngine


@dataclass
class AnalysisReport:
    """Phase 4.1 完整分析报告."""
    phase: str = "4.1"
    name: str = "IAP Creative Intelligence Analysis"

    # Layer stats
    performance_stats: dict[str, Any] = field(default_factory=dict)
    player_attribution_stats: dict[str, Any] = field(default_factory=dict)
    archetype_stats: dict[str, Any] = field(default_factory=dict)
    payment_stats: dict[str, Any] = field(default_factory=dict)
    ltv_stats: dict[str, Any] = field(default_factory=dict)
    fitness_stats: dict[str, Any] = field(default_factory=dict)
    evolution_stats: dict[str, Any] = field(default_factory=dict)

    # Key findings
    top_iap_winners: list[dict[str, Any]] = field(default_factory=list)
    platform_comparison: dict[str, Any] = field(default_factory=dict)
    iap_vs_roas_comparison: dict[str, Any] = field(default_factory=dict)
    archetype_distribution: dict[str, Any] = field(default_factory=dict)
    top_evolution_directions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnalysisOrchestrator:
    """Phase 4.1 编排器。

    协调所有分析器，构建 CreativeValueProfile，
    计算 IAP Fitness，生成进化方向。
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        root = Path(__file__).parent.parent.parent.parent
        self._output_dir = output_dir or (
            root / "output" / "creative_intelligence"
        )
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Analyzers
        self.performance = CreativePerformanceAnalyzer()
        self.player_attribution = PlayerAttributionAnalyzer()
        self.archetype = ArchetypeAnalyzer()
        self.payment = PaymentBehaviorAnalyzer()
        self.ltv = LTVCorelationEngine()
        self.fitness = IAPFitnessEngine()
        self.evolution = CreativeDNAEvolutionEngine()

        # State
        self._profiles: dict[str, CreativeValueProfile] = {}
        self._report: AnalysisReport | None = None

    # ── Pipeline ───────────────────────────────────────────

    def run(
        self,
        load_player_data: bool = True,
        top_n: int = 20,
        evolution_generations: int = 3,
    ) -> AnalysisReport:
        """执行完整分析流水线。

        Args:
            load_player_data: 是否加载玩家数据（E9.4-E9.7）
            top_n: Top N 分析
            evolution_generations: 进化方向代数
        """
        report = AnalysisReport()

        # Layer 1: Performance
        print("[1/6] Loading performance data...")
        self.performance.load()
        report.performance_stats = self.performance.stats()
        report.platform_comparison = self.performance.ios_android_comparison()

        # Build base profiles
        for m in self.performance._metrics:
            cid = m.creative_id
            if cid not in self._profiles:
                self._profiles[cid] = CreativeValueProfile(creative_id=cid)
            self._profiles[cid].performance = m

        # Layer 2-5: Player data (if available)
        if load_player_data:
            print("[2/6] Loading player attribution...")
            self.player_attribution.load_from_player_data()
            report.player_attribution_stats = self.player_attribution.cohort_stats()

            print("[3/6] Loading archetype data...")
            self.archetype.load_predictions()
            self.archetype.load_actuals()
            self.archetype.calibrate()
            report.archetype_stats = self.archetype.archetype_stats()
            report.archetype_distribution = report.archetype_stats.get(
                "actual_distribution", {})

            print("[4/6] Analyzing payment behavior...")
            self.payment.load_from_player_data()
            report.payment_stats = self.payment.payment_stats()

            print("[5/6] Computing LTV correlation...")
            self.ltv.load_from_player_data()
            self.ltv.load_dna_contributions()
            report.ltv_stats = self.ltv.ltv_stats()

            # Merge player data into profiles
            self._merge_player_data()

        # Layer 6: IAP Fitness
        print("[6/6] Computing IAP Fitness...")
        profiles_list = list(self._profiles.values())
        self.fitness.compute_all(profiles_list)
        report.fitness_stats = self.fitness.fitness_stats()
        report.iap_vs_roas_comparison = self.fitness.compare_iap_vs_roas()

        # Top winners
        top_winners = self.fitness.rank_by_fitness(top_n)
        report.top_iap_winners = [w.to_dict() for w in top_winners]

        # Evolution directions
        print("Generating evolution directions...")
        self.evolution.evolve_from_winners(
            self.fitness.get_winners(),
            self._profiles,
            generations=evolution_generations,
        )
        report.evolution_stats = self.evolution.evolution_stats()
        report.top_evolution_directions = [
            d.to_dict() for d in self.evolution.get_all()
        ]

        self._report = report
        return report

    def _merge_player_data(self) -> None:
        """将玩家数据合并到 CreativeValueProfile."""
        for cid, profile in self._profiles.items():
            # Player attribution
            attr = self.player_attribution.get(cid)
            if attr:
                profile.player_attribution = attr

            # Archetype
            arch = self.archetype.get(cid)
            if arch:
                profile.archetype = arch

            # Payment
            pay = self.payment.get(cid)
            if pay:
                profile.payment = pay

            # LTV
            ltv = self.ltv.get(cid)
            if ltv:
                profile.ltv = ltv

    # ── Export ─────────────────────────────────────────────

    def export_report(self, report: AnalysisReport | None = None) -> Path:
        """导出完整分析报告."""
        r = report or self._report
        if not r:
            raise ValueError("No report. Run .run() first.")

        path = self._output_dir / "iap_analysis_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(r.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"  Report saved: {path}")
        return path

    def export_winners(self) -> Path:
        """导出 IAP Winner 排名."""
        path = self._output_dir / "iap_winners.json"
        winners = self.fitness.rank_by_fitness(100)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([w.to_dict() for w in winners], f, ensure_ascii=False, indent=2)
        print(f"  Winners saved: {path}")
        return path

    def export_evolution_directions(self) -> Path:
        """导出进化方向（给 Lovart）."""
        path = self._output_dir / "evolution_directions.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [d.to_dict() for d in self.evolution.get_all()],
                f, ensure_ascii=False, indent=2,
            )
        print(f"  Evolution directions saved: {path}")
        return path

    def export_lovart_contexts(self) -> Path:
        """导出 Lovart Prompt 上下文."""
        path = self._output_dir / "lovart_prompt_contexts.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self.evolution.get_lovart_contexts(),
                f, ensure_ascii=False, indent=2,
            )
        print(f"  Lovart contexts saved: {path}")
        return path

    def export_all(self) -> dict[str, Path]:
        """导出所有输出."""
        paths = {
            "report": self.export_report(),
            "winners": self.export_winners(),
            "evolution": self.export_evolution_directions(),
            "lovart": self.export_lovart_contexts(),
        }
        return paths

    # ── Summary ────────────────────────────────────────────

    def print_summary(self) -> None:
        """打印分析摘要."""
        if not self._report:
            print("No report. Run .run() first.")
            return

        r = self._report
        print("\n" + "=" * 65)
        print("  Phase 4.1 — IAP Creative Intelligence Analysis")
        print("  Complete")
        print("=" * 65)

        # Performance
        ps = r.performance_stats
        print(f"\n  [Advertising Layer]")
        print(f"    Creatives: {ps.get('total', 0)}")
        print(f"    Total Spend: ${ps.get('total_spend', 0):,.0f}")
        print(f"    Total Revenue: ${ps.get('total_revenue', 0):,.0f}")
        print(f"    Avg ROAS: {ps.get('avg_roas', 0)}")

        # Player
        pa = r.player_attribution_stats
        if pa.get("total_creatives", 0) > 0:
            print(f"\n  [Player Attribution]")
            print(f"    Total Players: {pa.get('total_players', 0):,}")
            print(f"    Payer Rate: {pa.get('overall_payer_rate', 0):.1%}")
            print(f"    Avg D30: {pa.get('avg_d30_retention', 0):.1%}")
            print(f"    High Value Cohorts: {pa.get('high_value_cohorts', 0)}")

        # Archetype
        ar = r.archetype_stats
        if ar.get("total", 0) > 0:
            print(f"\n  [Archetype]")
            print(f"    Dominant: {ar.get('dominant_map', {})}")
            print(f"    High Value Attractors: {ar.get('high_value_attractors', 0)}")

        # Payment
        pm = r.payment_stats
        if pm.get("total_creatives", 0) > 0:
            print(f"\n  [Payment]")
            print(f"    Total Revenue: ${pm.get('total_revenue', 0):,.0f}")
            print(f"    Avg ARPPU: ${pm.get('avg_arppu', 0)}")
            print(f"    Healthy Monetizers: {pm.get('healthy_monetizers', 0)}")

        # LTV
        lt = r.ltv_stats
        if lt.get("total_creatives", 0) > 0:
            print(f"\n  [LTV]")
            print(f"    Avg D30 LTV: ${lt.get('avg_d30_ltv', 0)}")
            print(f"    By Tier: {lt.get('by_tier', {})}")

        # IAP Fitness
        fs = r.fitness_stats
        print(f"\n  [IAP Fitness]")
        print(f"    Avg Fitness: {fs.get('avg_fitness', 0)}")
        print(f"    By Tier: {fs.get('by_tier', {})}")
        print(f"    IAP Winners: {fs.get('iap_winners', 0)}")
        print(f"    Tier S+A: {fs.get('iap_winners_tier_s_a', 0)}")

        # Evolution
        es = r.evolution_stats
        print(f"\n  [Evolution]")
        print(f"    Directions: {es.get('total_directions', 0)}")
        print(f"    Generations: {es.get('generations', 0)}")
        print(f"    Top Targets: {es.get('target_archetypes', {})}")
        print(f"    Top Triggers: {es.get('iap_triggers', {})}")

        # Comparison
        comp = r.iap_vs_roas_comparison
        print(f"\n  [IAP vs ROAS Comparison]")
        print(f"    IAP Winners: {comp.get('iap_winners', 0)}")
        print(f"    ROAS Winners: {comp.get('roas_winners', 0)}")
        print(f"    IAP Only: {comp.get('iap_only_winners', 0)}")
        print(f"    ROAS Only: {comp.get('roas_only_winners', 0)}")
        print(f"    Both: {comp.get('both_winners', 0)}")

        print("\n" + "=" * 65)
        print("  Next: Phase 4.2 — Lovart Creative Generator")
        print("  Input: evolution_directions.json")
        print("=" * 65 + "\n")


# ═══════════════════════════════════════════════════════════
# Quick Run
# ═══════════════════════════════════════════════════════════

def run_analysis(
    load_player_data: bool = True,
    output_dir: Path | None = None,
) -> AnalysisReport:
    """快速运行完整分析."""
    orchestrator = AnalysisOrchestrator(output_dir=output_dir)
    report = orchestrator.run(load_player_data=load_player_data)
    orchestrator.print_summary()
    orchestrator.export_all()
    return report


if __name__ == "__main__":
    run_analysis()