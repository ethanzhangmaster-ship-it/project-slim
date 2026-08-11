"""Phase 4.1 — Creative DNA Evolution Engine.

从 IAP Winner 分析结果中提取进化方向，
输出给 Phase 4.2 / Lovart 的 Prompt Director。

核心流程：
  1. 从 Top IAP Winners 提取获胜 DNA 元素
  2. 识别目标玩家类型
  3. 推导 IAP 触发点
  4. 建议变异操作
  5. 输出 Lovart Prompt Context
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import (
    CreativeValueProfile,
    IAPFitnessResult,
    CreativeEvolutionDirection,
    ArchetypeProfile,
    PaymentProfile,
)


class CreativeDNAEvolutionEngine:
    """Creative DNA 进化引擎。

    不是生成图片，而是输出进化方向：
      → 目标玩家类型
      → 获胜 Hook 模式
      → 玩法展示策略
      → IAP 触发点
      → 视觉方向
    """

    def __init__(self) -> None:
        self._directions: list[CreativeEvolutionDirection] = []

    # ── Generation ─────────────────────────────────────────

    def evolve_from_winners(
        self,
        winners: list[IAPFitnessResult],
        profiles: dict[str, CreativeValueProfile],
        generations: int = 3,
    ) -> list[CreativeEvolutionDirection]:
        """从 IAP Winners 生成进化方向。

        Args:
            winners: IAP 适应度排名结果
            profiles: CreativeValueProfile 完整数据
            generations: 生成代数
        """
        self._directions = []

        for gen in range(1, generations + 1):
            # Take top winners for each generation
            gen_size = max(3, len(winners) // generations)
            gen_winners = winners[(gen - 1) * gen_size : gen * gen_size]

            for i, winner in enumerate(gen_winners):
                profile = profiles.get(winner.creative_id)
                if not profile:
                    continue

                direction = self._generate_direction(
                    winner, profile, generation=gen
                )
                self._directions.append(direction)

        return self._directions

    def _generate_direction(
        self,
        winner: IAPFitnessResult,
        profile: CreativeValueProfile,
        generation: int,
    ) -> CreativeEvolutionDirection:
        """从单个 Winner 生成进化方向."""
        direction = CreativeEvolutionDirection(
            source_creative_id=winner.creative_id,
            generation=generation,
            based_on_fitness=winner.fitness_score,
        )

        # 1. 目标玩家类型
        if profile.archetype:
            direction.target_archetypes = self._extract_target_archetypes(
                profile.archetype
            )

        # 2. 获胜 DNA 元素
        if profile.creative_analysis:
            ca = profile.creative_analysis
            direction.winning_hook = ca.hook_features.hook_type.value
            direction.winning_visual = self._extract_visual_style(ca)
            direction.winning_gameplay = self._extract_gameplay(ca)

        # 3. IAP 触发
        if profile.payment:
            direction.iap_trigger = profile.payment.dominant_trigger
            direction.iap_trigger_strength = round(
                profile.payment.payment_health_score, 3
            )

        # 4. 变异策略
        direction.mutation_operations = self._suggest_mutations(
            winner, profile
        )

        # 5. 预期效果
        direction.expected_fitness = round(
            min(winner.fitness_score * 1.15, 1.0), 4
        )

        # 6. 进化原因
        direction.evolution_reason = self._build_evolution_reason(
            winner, profile
        )

        return direction

    @staticmethod
    def _extract_target_archetypes(
        archetype: ArchetypeProfile,
    ) -> list[str]:
        """提取目标玩家类型."""
        dist = {
            "collector": archetype.actual_collector,
            "power": archetype.actual_power,
            "progression": archetype.actual_progression,
            "explorer": archetype.actual_explorer,
            "casual": archetype.actual_casual,
        }
        # 取 Top 2
        sorted_archs = sorted(dist.items(), key=lambda x: x[1], reverse=True)
        return [a for a, v in sorted_archs[:2] if v > 0.15]

    @staticmethod
    def _extract_visual_style(ca) -> str:
        """提取视觉风格."""
        parts = []
        if ca.visual_features.color.style.value != "unknown":
            parts.append(ca.visual_features.color.style.value)
        if ca.visual_features.composition.subject.value != "unknown":
            parts.append(ca.visual_features.composition.subject.value)
        if ca.visual_features.emotion.dominant_emotion:
            parts.append(ca.visual_features.emotion.dominant_emotion)
        return "_".join(parts) if parts else "standard"

    @staticmethod
    def _extract_gameplay(ca) -> str:
        """提取玩法展示."""
        prog = ca.gameplay_features.progression
        econ = ca.gameplay_features.economy
        if econ.rare_item > 50:
            return "rare_item_showcase"
        if prog.collection_growth > 50:
            return "collection_progression"
        if prog.level_growth > 50:
            return "level_progression"
        return "gameplay_showcase"

    @staticmethod
    def _suggest_mutations(
        winner: IAPFitnessResult,
        profile: CreativeValueProfile,
    ) -> list[str]:
        """建议变异操作."""
        mutations = []

        # 基于弱点建议变异
        if "weak_monetization" in winner.weaknesses:
            mutations.append("add_purchase_trigger")
            mutations.append("enhance_reward_visibility")
        if "low_roas_despite_fitness" in winner.weaknesses:
            mutations.append("improve_hook_strength")
            mutations.append("optimize_cta_placement")

        # 基于强项建议放大
        if "healthy_monetization" in winner.strengths:
            mutations.append("amplify_iap_trigger")
        if "high_roas_despite_low_fitness" in winner.strengths:
            mutations.append("evolve_dna_for_retention")

        # 基于 Archetype 建议
        if profile.archetype:
            dom = profile.archetype.dominant_archetype
            if dom == "collector":
                mutations.append("add_collection_meta")
                mutations.append("show_rare_item_progression")
            elif dom == "power":
                mutations.append("add_power_progression")
                mutations.append("show_character_upgrade")
            elif dom == "progression":
                mutations.append("add_merge_evolution")
                mutations.append("show_area_unlock")

        return mutations[:3]  # Top 3

    @staticmethod
    def _build_evolution_reason(
        winner: IAPFitnessResult,
        profile: CreativeValueProfile,
    ) -> str:
        """构建进化原因."""
        parts = [
            f"Tier {winner.winner_tier} IAP Winner",
            f"fitness={winner.fitness_score:.3f}",
        ]

        if profile.archetype:
            parts.append(
                f"attracts {profile.archetype.dominant_archetype}"
            )

        if profile.payment and profile.payment.dominant_trigger != "unknown":
            parts.append(
                f"trigger={profile.payment.dominant_trigger}"
            )

        return " | ".join(parts)

    # ── Query ──────────────────────────────────────────────

    def get_all(self) -> list[CreativeEvolutionDirection]:
        return self._directions

    def get_by_generation(self, gen: int) -> list[CreativeEvolutionDirection]:
        return [d for d in self._directions if d.generation == gen]

    def get_lovart_contexts(self) -> list[dict[str, Any]]:
        """获取所有 Lovart Prompt 上下文."""
        return [d.to_lovart_prompt_context() for d in self._directions]

    def get_aggregated_mutations(self) -> list[tuple[str, int]]:
        """聚合所有建议的变异操作."""
        counter = Counter()
        for d in self._directions:
            for op in d.mutation_operations:
                counter[op] += 1
        return counter.most_common(20)

    # ── Statistics ─────────────────────────────────────────

    def evolution_stats(self) -> dict[str, Any]:
        """进化统计."""
        if not self._directions:
            return {"total_directions": 0}

        all_targets = []
        for d in self._directions:
            all_targets.extend(d.target_archetypes)
        target_counter = Counter(all_targets)

        all_triggers = [d.iap_trigger for d in self._directions if d.iap_trigger]
        trigger_counter = Counter(all_triggers)

        return {
            "total_directions": len(self._directions),
            "generations": max(d.generation for d in self._directions),
            "avg_expected_fitness": round(
                sum(d.expected_fitness for d in self._directions)
                / len(self._directions), 4
            ),
            "target_archetypes": dict(target_counter.most_common()),
            "iap_triggers": dict(trigger_counter.most_common()),
            "top_mutations": [
                {"operation": op, "count": count}
                for op, count in self.get_aggregated_mutations()[:10]
            ],
        }