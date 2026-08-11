"""Phase 4.2.3 — Creative Evolution Policy Generator.

连接 Causal Discovery → V5 Mutation Engine。

不是随机变异，而是基于因果发现的定向进化：
  1. 从 CausalDiscoveryResult 提取基因影响力
  2. 生成 Amplify / Suppress / Explore 策略
  3. 生成 Creative Hypothesis（可验证的实验假设）
  4. 输出 MutationPolicy（V5 Mutation Engine 可用的策略）

核心流程：
  DNA Performance Matrix → Gene Impact → Evolution Policy → V5 Mutation
"""

from __future__ import annotations

import uuid
from typing import Any

from .models import (
    GeneImpact,
    CausalDiscoveryResult,
    CreativeHypothesis,
    MutationPolicy,
    IAPFitnessResult,
    CreativeValueProfile,
    ArchetypeProfile,
    LTVProfile,
    PaymentProfile,
)


class EvolutionPolicyGenerator:
    """创意进化策略生成器。

    将因果发现结果转化为可执行的进化策略。
    """

    def __init__(self) -> None:
        self._policies: list[MutationPolicy] = []
        self._hypotheses: list[CreativeHypothesis] = []

    # ── Generation ──────────────────────────────────────────

    def generate_policy(
        self,
        causal_results: list[CausalDiscoveryResult],
        fitness_results: dict[str, IAPFitnessResult] | None = None,
        profiles: dict[str, CreativeValueProfile] | None = None,
        generation: int = 1,
    ) -> MutationPolicy:
        """从因果发现结果生成进化策略。

        Args:
            causal_results: 因果发现结果列表
            fitness_results: IAP 适应度结果
            profiles: 完整创意画像
            generation: 当前代数
        """
        policy = MutationPolicy(
            policy_id=str(uuid.uuid4())[:8],
            generation=generation,
        )

        # 1. 聚合所有基因影响
        all_genes = self._aggregate_gene_impacts(causal_results)

        # 2. 分类：Amplify / Suppress
        policy.amplify_genes = [
            g for g in all_genes
            if g.is_positive_impact and g.is_high_confidence
        ]
        policy.amplify_genes = sorted(
            policy.amplify_genes,
            key=lambda g: g.impact_score, reverse=True,
        )[:5]

        policy.suppress_genes = [
            g for g in all_genes
            if not g.is_positive_impact and g.confidence >= 0.50
        ]
        policy.suppress_genes = sorted(
            policy.suppress_genes,
            key=lambda g: g.impact_score,
        )[:5]

        # 3. 探索新基因组合
        policy.explore_genes = self._suggest_exploration(
            all_genes, profiles, fitness_results
        )

        # 4. 生成假设
        policy.hypotheses = self._generate_hypotheses(
            policy.amplify_genes, profiles, fitness_results
        )

        # 5. 计算置信度
        if policy.amplify_genes:
            policy.confidence = round(
                sum(g.confidence for g in policy.amplify_genes)
                / len(policy.amplify_genes), 3
            )

        # 6. 洞察
        policy.based_on_insights = self._extract_insights(
            causal_results, fitness_results
        )

        self._policies.append(policy)
        self._hypotheses.extend(policy.hypotheses)
        return policy

    def generate_policy_batch(
        self,
        causal_results: list[CausalDiscoveryResult],
        generations: int = 3,
        fitness_results: dict[str, IAPFitnessResult] | None = None,
        profiles: dict[str, CreativeValueProfile] | None = None,
    ) -> list[MutationPolicy]:
        """多代进化策略生成."""
        policies = []
        for gen in range(1, generations + 1):
            # 每代使用的基因范围略有不同
            gen_causal = causal_results[
                (gen - 1) * len(causal_results) // generations :
                gen * len(causal_results) // generations
            ] if len(causal_results) >= generations else causal_results

            policy = self.generate_policy(
                causal_results=gen_causal,
                fitness_results=fitness_results,
                profiles=profiles,
                generation=gen,
            )
            # 每代调整探索率
            policy.exploration_rate = max(0.05, 0.15 - gen * 0.03)
            policies.append(policy)

        return policies

    @staticmethod
    def _aggregate_gene_impacts(
        causal_results: list[CausalDiscoveryResult],
    ) -> list[GeneImpact]:
        """聚合所有因果发现结果的基因影响."""
        gene_map: dict[str, GeneImpact] = {}
        counts: dict[str, int] = {}

        for result in causal_results:
            for gene in result.gene_impacts:
                if gene.gene_name not in gene_map:
                    gene_map[gene.gene_name] = gene
                    counts[gene.gene_name] = 1
                else:
                    # 合并影响
                    existing = gene_map[gene.gene_name]
                    existing.impact_score = round(
                        (existing.impact_score * counts[gene.gene_name] + gene.impact_score)
                        / (counts[gene.gene_name] + 1), 3
                    )
                    existing.confidence = round(
                        (existing.confidence * counts[gene.gene_name] + gene.confidence)
                        / (counts[gene.gene_name] + 1), 3
                    )
                    counts[gene.gene_name] += 1

        return list(gene_map.values())

    @staticmethod
    def _suggest_exploration(
        top_genes: list[GeneImpact],
        profiles: dict[str, CreativeValueProfile] | None,
        fitness_results: dict[str, IAPFitnessResult] | None,
    ) -> list[dict[str, Any]]:
        """建议探索新基因组合."""
        explores = []

        # 基于高影响力基因寻找互补基因
        for gene in top_genes[:3]:
            if gene.gene_category == "hook":
                explores.append({
                    "hook": gene.gene_name.split(":")[-1],
                    "reward": "social_proof",
                    "risk": 0.3,
                    "reason": f"complement high impact {gene.gene_name}",
                })
            elif gene.gene_category == "reward":
                explores.append({
                    "hook": "rescue",
                    "reward": gene.gene_name.split(":")[-1],
                    "risk": 0.25,
                    "reason": f"pair with proven hook",
                })

        # 基于 Archetype 建议
        if profiles:
            for cid, profile in list(profiles.items())[:3]:
                if profile.archetype:
                    dom = profile.archetype.dominant_archetype
                    if dom == "collector":
                        explores.append({
                            "hook": "collection_complete",
                            "reward": "missing_item",
                            "risk": 0.2,
                            "reason": f"target collector players",
                        })

        return explores[:5]

    def _generate_hypotheses(
        self,
        amplify_genes: list[GeneImpact],
        profiles: dict[str, CreativeValueProfile] | None,
        fitness_results: dict[str, IAPFitnessResult] | None,
    ) -> list[CreativeHypothesis]:
        """从高影响力基因生成可验证假设."""
        hypotheses = []

        for gene in amplify_genes:
            hypothesis = CreativeHypothesis(
                hypothesis_id=str(uuid.uuid4())[:8],
                creative_id=self._find_source_creative(gene, fitness_results),
                hypothesis=self._build_hypothesis_text(gene),
                target_player=gene.highest_archetype or "collector",
                target_psychology=self._infer_psychology(gene),
                expected_impact=self._build_expected_impact(gene),
                based_on_dna=[gene.gene_name],
                based_on_winners=self._find_winner_sources(gene, fitness_results),
                status="pending",
            )
            hypotheses.append(hypothesis)

        return hypotheses

    @staticmethod
    def _build_hypothesis_text(gene: GeneImpact) -> str:
        """构建假设文本."""
        category_map = {
            "hook": "hook",
            "visual": "视觉风格",
            "reward": "奖励展示",
            "gameplay": "玩法展示",
            "psychology": "心理机制",
        }
        cat_name = category_map.get(gene.gene_category, gene.gene_category)
        gene_value = gene.gene_name.split(":")[-1]

        if gene_category := gene.gene_category == "psychology":
            return f"触发 {gene_value} 心理机制将提升 D7 payer rate +{gene.payer_rate_lift:.0%}"
        if gene_category == "hook":
            return f"{gene_value} hook 将吸引 {gene.highest_archetype} 玩家，提升 D7 payer rate +{gene.payer_rate_lift:.0%}"
        return f"{cat_name}_{gene_value} 提升 LTV +{gene.ltv_lift:.2f}"

    @staticmethod
    def _infer_psychology(gene: GeneImpact) -> str:
        """推断心理机制."""
        psych_map = {
            "rescue": "loss_aversion",
            "collection": "completion_drive",
            "rare_item": "scarcity",
            "progression": "mastery",
            "reward_reveal": "anticipation",
            "social_proof": "social_proof",
            "challenge": "mastery",
        }
        return psych_map.get(gene.gene_name.split(":")[-1], "curiosity")

    @staticmethod
    def _build_expected_impact(gene: GeneImpact) -> str:
        """构建预期影响文本."""
        parts = []
        if gene.payer_rate_lift > 0:
            parts.append(f"payer_rate +{gene.payer_rate_lift:.0%}")
        if gene.ltv_lift > 0:
            parts.append(f"D30 LTV +{gene.ltv_lift:.2f}")
        if gene.retention_lift > 0:
            parts.append(f"D7 retention +{gene.retention_lift:.1%}")
        return "提升 " + ", ".join(parts) if parts else "验证效果"

    @staticmethod
    def _find_source_creative(
        gene: GeneImpact,
        fitness_results: dict[str, IAPFitnessResult] | None,
    ) -> str:
        """找到来源创意."""
        if fitness_results:
            winners = [
                cid for cid, f in fitness_results.items()
                if f.is_winner and f.winner_tier in ("S", "A")
            ]
            if winners:
                return winners[0]
        return ""

    @staticmethod
    def _find_winner_sources(
        gene: GeneImpact,
        fitness_results: dict[str, IAPFitnessResult] | None,
    ) -> list[str]:
        """找到 Winner 来源."""
        if fitness_results:
            return [
                cid for cid, f in fitness_results.items()
                if f.is_winner
            ][:3]
        return []

    @staticmethod
    def _extract_insights(
        causal_results: list[CausalDiscoveryResult],
        fitness_results: dict[str, IAPFitnessResult] | None,
    ) -> list[str]:
        """提取关键洞察."""
        insights = []

        # 基因影响力排名
        all_genes = []
        for r in causal_results:
            all_genes.extend(r.gene_impacts)
        top_genes = sorted(all_genes, key=lambda g: g.impact_score, reverse=True)[:3]
        for g in top_genes:
            insights.append(
                f"{g.gene_name}: impact={g.impact_score:.3f}, "
                f"ltv_lift={g.ltv_lift:.2f}, confidence={g.confidence:.3f}"
            )

        # Winning Patterns
        for r in causal_results[:3]:
            insights.extend(r.winning_patterns)

        # Fitness 统计
        if fitness_results:
            s_count = sum(1 for f in fitness_results.values() if f.winner_tier == "S")
            a_count = sum(1 for f in fitness_results.values() if f.winner_tier == "A")
            insights.append(
                f"Current: {s_count} S-tier, {a_count} A-tier winners"
            )

        return insights[:10]

    # ── Query ───────────────────────────────────────────────

    def get_all_policies(self) -> list[MutationPolicy]:
        return self._policies

    def get_by_generation(self, gen: int) -> list[MutationPolicy]:
        return [p for p in self._policies if p.generation == gen]

    def get_all_hypotheses(self) -> list[CreativeHypothesis]:
        return self._hypotheses

    def get_pending_hypotheses(self) -> list[CreativeHypothesis]:
        return [h for h in self._hypotheses if h.status == "pending"]

    def get_v5_mutation_requests(self) -> list[dict[str, Any]]:
        """获取所有 V5 Mutation Engine 可用的请求."""
        requests = []
        for policy in self._policies:
            requests.extend(policy.to_v5_mutation_requests())
        return requests

    # ── Statistics ──────────────────────────────────────────

    def policy_stats(self) -> dict[str, Any]:
        """策略统计."""
        if not self._policies:
            return {"total_policies": 0}

        all_amplify = []
        all_suppress = []
        all_explore = []
        for p in self._policies:
            all_amplify.extend(p.amplify_genes)
            all_suppress.extend(p.suppress_genes)
            all_explore.extend(p.explore_genes)

        return {
            "total_policies": len(self._policies),
            "total_hypotheses": len(self._hypotheses),
            "generations": max(p.generation for p in self._policies),
            "avg_amplify_count": round(
                sum(len(p.amplify_genes) for p in self._policies) / len(self._policies), 1
            ),
            "avg_suppress_count": round(
                sum(len(p.suppress_genes) for p in self._policies) / len(self._policies), 1
            ),
            "avg_explore_count": round(
                sum(len(p.explore_genes) for p in self._policies) / len(self._policies), 1
            ),
            "avg_confidence": round(
                sum(p.confidence for p in self._policies) / len(self._policies), 3
            ),
            "top_amplify_genes": [
                {"gene": g.gene_name, "impact": g.impact_score}
                for g in all_amplify[:5]
            ],
            "v5_mutation_requests": len(self.get_v5_mutation_requests()),
        }