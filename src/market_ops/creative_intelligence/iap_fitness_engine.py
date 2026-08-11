"""Phase 4.1.5 — IAP Fitness Engine (IAP 综合价值评分).

替代 ROAS-based Winner 判定。
基于 CreativeValueProfile 的 6 层数据计算 IAP 综合适应度。

Phase 4.1.5 升级公式：
  IAP Fitness = 0.20 × Creative Performance + 0.20 × Payer Rate
              + 0.25 × D30 LTV + 0.15 × Retention
              + 0.10 × Archetype Quality + 0.10 × DNA Future Value

Winner 判定：
  S Tier: fitness >= 0.55 → SCALE
  A Tier: fitness >= 0.40 → SCALE
  B Tier: fitness >= 0.25 → OBSERVE
  C Tier: fitness < 0.25  → STOP

IAP 产品特殊逻辑：
  - 高付费率 (>=10%) + 高 LTV → 即使 ROAS < 1.0 也是 Winner
  - 低付费率 + 低 LTV → 即使 ROAS > 1.5 也不放量

ROAS 只是验证指标，不是核心。
"""

from __future__ import annotations

from typing import Any

from .models import (
    CreativeValueProfile,
    IAPFitnessResult,
    CreativeEvolutionDirection,
)


class IAPFitnessEngine:
    """IAP 综合适应度引擎（Phase 4.1.5 升级）。

    聚合 6 层数据，计算 IAP 适应度，输出 Winner 判定和进化方向。

    核心哲学：
      IAP 产品买的是未来价值，不是当次 ROAS。
      付费用率高 + LTV 高 = 真实的 Winner，
      即使 ROAS 暂时低于 1.0。
    """

    def __init__(self) -> None:
        self._results: dict[str, IAPFitnessResult] = {}

    # ── Computation ────────────────────────────────────────

    def compute(self, profile: CreativeValueProfile) -> IAPFitnessResult:
        """计算单个 Creative 的 IAP 适应度."""
        result = IAPFitnessResult.compute_from(profile)
        self._results[profile.creative_id] = result
        return result

    def compute_all(
        self, profiles: list[CreativeValueProfile]
    ) -> list[IAPFitnessResult]:
        """批量计算."""
        results = []
        for profile in profiles:
            result = self.compute(profile)
            results.append(result)
        return results

    # ── Query ──────────────────────────────────────────────

    def get(self, creative_id: str) -> IAPFitnessResult | None:
        return self._results.get(creative_id)

    def get_all(self) -> list[IAPFitnessResult]:
        return list(self._results.values())

    def get_winners(self) -> list[IAPFitnessResult]:
        """获取所有 IAP Winner."""
        return [r for r in self._results.values() if r.is_winner]

    def get_by_tier(self, tier: str) -> list[IAPFitnessResult]:
        return [r for r in self._results.values() if r.winner_tier == tier]

    def get_by_decision(self, decision: str) -> list[IAPFitnessResult]:
        return [r for r in self._results.values() if r.decision == decision]

    def get_by_recommendation(self, recommendation: str) -> list[IAPFitnessResult]:
        """按推荐操作筛选（Phase 4.1.5 新增）."""
        return [r for r in self._results.values() if r.recommendation == recommendation]

    def rank_by_fitness(self, n: int = 10) -> list[IAPFitnessResult]:
        """按 IAP 适应度排序."""
        return sorted(
            self._results.values(),
            key=lambda r: (r.fitness_score, r.confidence),
            reverse=True,
        )[:n]

    def rank_by_ltv(self, n: int = 10) -> list[IAPFitnessResult]:
        """按 LTV 排序（Phase 4.1.5 新增）."""
        return sorted(
            self._results.values(),
            key=lambda r: r.ltv_scaled,
            reverse=True,
        )[:n]

    # ── Comparison: IAP vs ROAS ────────────────────────────

    def compare_iap_vs_roas(self) -> dict[str, Any]:
        """对比 IAP Fitness 和 ROAS 的判定差异。

        Phase 4.1.5 升级：新增 IAP 产品特殊分析。
        """
        iap_winners = self.get_winners()
        roas_winners = [
            r for r in self._results.values() if r.roas >= 1.0
        ]

        # 只在 IAP 中是 Winner 但 ROAS < 1.0（IAP 价值被低估）
        iap_only = [
            r for r in iap_winners if r.roas < 1.0
        ]

        # 只在 ROAS 中是 Winner 但 IAP 不是（ROAS 虚高）
        roas_only = [
            r for r in roas_winners if not r.is_winner
        ]

        # 双重 Winner
        both = [
            r for r in iap_winners if r.roas >= 1.0
        ]

        # IAP 产品关键指标：高付费率 + 高 LTV 但低 ROAS
        high_value_low_roas = [
            r for r in iap_only
            if r.payer_rate >= 0.10 and r.ltv_scaled >= 0.4
        ]

        return {
            "iap_winners": len(iap_winners),
            "roas_winners": len(roas_winners),
            "iap_only_winners": len(iap_only),
            "roas_only_winners": len(roas_only),
            "both_winners": len(both),
            "high_value_low_roas": len(high_value_low_roas),
            "iap_only_samples": [
                {
                    "creative_id": r.creative_id,
                    "fitness": r.fitness_score,
                    "roas": r.roas,
                    "payer_rate": r.payer_rate,
                    "ltv_scaled": r.ltv_scaled,
                    "insight": r.insight,
                }
                for r in iap_only[:5]
            ],
            "roas_only_samples": [
                {
                    "creative_id": r.creative_id,
                    "fitness": r.fitness_score,
                    "roas": r.roas,
                    "payer_rate": r.payer_rate,
                    "ltv_scaled": r.ltv_scaled,
                    "insight": r.insight,
                }
                for r in roas_only[:5]
            ],
        }

    # ── Evolution Direction ────────────────────────────────

    def generate_evolution_directions(
        self, top_n: int = 5
    ) -> list[CreativeEvolutionDirection]:
        """为 Top N IAP Winner 生成进化方向."""
        top_winners = self.rank_by_fitness(top_n)
        directions = []

        for i, result in enumerate(top_winners):
            direction = CreativeEvolutionDirection(
                source_creative_id=result.creative_id,
                generation=i + 1,
                based_on_fitness=result.fitness_score,
                expected_fitness=min(result.fitness_score * 1.1, 1.0),
                evolution_reason=(
                    f"Tier {result.winner_tier} IAP Winner "
                    f"(fitness={result.fitness_score:.3f}, "
                    f"ROAS={result.roas:.2f})"
                ),
            )

            if result.strengths:
                direction.evolution_reason += (
                    f" | Strengths: {', '.join(result.strengths)}"
                )

            directions.append(direction)

        return directions

    # ── Statistics ─────────────────────────────────────────

    def fitness_stats(self) -> dict[str, Any]:
        """全局适应度统计（Phase 4.1.5 升级）."""
        all_results = list(self._results.values())
        if not all_results:
            return {"total": 0}

        iap_winners = self.get_winners()
        comparison = self.compare_iap_vs_roas()

        return {
            "total": len(all_results),
            "avg_fitness": round(
                sum(r.fitness_score for r in all_results) / len(all_results), 4
            ),
            "max_fitness": round(
                max(r.fitness_score for r in all_results), 4
            ),
            "by_tier": {
                "S": len(self.get_by_tier("S")),
                "A": len(self.get_by_tier("A")),
                "B": len(self.get_by_tier("B")),
                "C": len(self.get_by_tier("C")),
            },
            "by_recommendation": {
                "SCALE": len(self.get_by_recommendation("SCALE")),
                "OBSERVE": len(self.get_by_recommendation("OBSERVE")),
                "STOP": len(self.get_by_recommendation("STOP")),
                "EVOLVE": len(self.get_by_recommendation("EVOLVE")),
            },
            "by_decision": {
                "scale": len(self.get_by_decision("scale")),
                "observe": len(self.get_by_decision("observe")),
                "stop": len(self.get_by_decision("stop")),
            },
            "iap_winners": len(iap_winners),
            "iap_winners_tier_s_a": len(
                [r for r in iap_winners if r.winner_tier in ("S", "A")]
            ),
            "comparison": comparison,
        }