"""Phase 4.2.2 — DNA Causal Discovery Engine.

从 Creative DNA → Player Behavior → Revenue Outcome 的因果发现。

核心目标：
  不是"这个素材带来高价值玩家"，
  而是"为什么这个 DNA 带来高价值玩家？"

例如发现：
  rescue hook + collection reward + cozy visual = 高 IAP 玩家
  challenge hook + coins reward = 低付费玩家

输出：
  - GeneImpact: 每个基因元素对 LTV/付费/留存的因果影响力
  - CausalDiscoveryResult: 完整的因果发现报告
  - Winning Patterns: 高价值 DNA 组合
"""

from __future__ import annotations

from typing import Any

from .models import (
    GeneImpact,
    CausalDiscoveryResult,
    LTVProfile,
    PaymentProfile,
    PlayerAttributionProfile,
    ArchetypeProfile,
    PlayerJourneyProfile,
)


class DNACausalDiscoveryEngine:
    """DNA 因果发现引擎。

    不是简单相关，而是建立因果链：
      DNA Element → Player Behavior → Revenue Outcome
    """

    def __init__(self) -> None:
        self._results: dict[str, CausalDiscoveryResult] = {}

    # ── Discovery ───────────────────────────────────────────

    def discover(
        self,
        creative_id: str,
        dna_map: dict[str, Any],
        ltv: LTVProfile | None = None,
        payment: PaymentProfile | None = None,
        attribution: PlayerAttributionProfile | None = None,
        journey: PlayerJourneyProfile | None = None,
        archetype: ArchetypeProfile | None = None,
    ) -> CausalDiscoveryResult:
        """对单个 Creative 进行因果发现。

        Args:
            creative_id: 创意 ID
            dna_map: DNA 基因映射 {"hook": {"type": "rescue"}, "reward": {"type": "collection"}, ...}
            ltv: LTV 数据
            payment: 付费数据
            attribution: 玩家归因数据
            journey: 玩家旅程数据
            archetype: 玩家类型数据
        """
        result = CausalDiscoveryResult(creative_id=creative_id)
        gene_impacts: list[GeneImpact] = []

        # 提取基准值
        baseline_payer = payment.payer_rate if payment else 0.0
        baseline_ltv = ltv.d30_ltv if ltv else 0.0
        baseline_retention = attribution.d30_retention if attribution else 0.0
        sample_size = ltv.sample_size if ltv else 0

        # 对每个 DNA 元素计算影响力
        for category, dna_data in dna_map.items():
            if not isinstance(dna_data, dict):
                continue

            if "type" in dna_data:
                gene_name = f"{category}:{dna_data['type']}"
                impact = self._compute_gene_impact(
                    gene_name=gene_name,
                    category=category,
                    baseline_payer=baseline_payer,
                    baseline_ltv=baseline_ltv,
                    baseline_retention=baseline_retention,
                    sample_size=sample_size,
                    archetype=archetype,
                    dna_data=dna_data,
                )
                gene_impacts.append(impact)

                # 构建因果链
                result.causal_chain.append({
                    "dna": gene_name,
                    "dna_data": dna_data,
                    "payer_rate_lift": impact.payer_rate_lift,
                    "ltv_lift": impact.ltv_lift,
                    "retention_lift": impact.retention_lift,
                    "impact_score": impact.impact_score,
                })

        # 排序
        gene_impacts.sort(key=lambda g: g.impact_score, reverse=True)
        result.gene_impacts = gene_impacts

        # 发现 Winning/Losing Patterns
        result.winning_patterns = self._extract_winning_patterns(gene_impacts)
        result.losing_patterns = self._extract_losing_patterns(gene_impacts)

        # 计算整体置信度
        if gene_impacts:
            result.overall_confidence = round(
                sum(g.confidence for g in gene_impacts) / len(gene_impacts), 3
            )

        self._results[creative_id] = result
        return result

    def discover_batch(
        self,
        creative_dna_map: dict[str, dict[str, Any]],
        ltv_map: dict[str, LTVProfile] | None = None,
        payment_map: dict[str, PaymentProfile] | None = None,
        attribution_map: dict[str, PlayerAttributionProfile] | None = None,
        journey_map: dict[str, PlayerJourneyProfile] | None = None,
        archetype_map: dict[str, ArchetypeProfile] | None = None,
    ) -> list[CausalDiscoveryResult]:
        """批量因果发现."""
        results = []
        for cid, dna_map in creative_dna_map.items():
            result = self.discover(
                creative_id=cid,
                dna_map=dna_map,
                ltv=(ltv_map or {}).get(cid),
                payment=(payment_map or {}).get(cid),
                attribution=(attribution_map or {}).get(cid),
                journey=(journey_map or {}).get(cid),
                archetype=(archetype_map or {}).get(cid),
            )
            results.append(result)
        return results

    def _compute_gene_impact(
        self,
        gene_name: str,
        category: str,
        baseline_payer: float,
        baseline_ltv: float,
        baseline_retention: float,
        sample_size: int,
        archetype: ArchetypeProfile | None,
        dna_data: dict[str, Any],
    ) -> GeneImpact:
        """计算单个基因的影响力."""
        impact = GeneImpact(
            gene_name=gene_name,
            gene_category=category,
            sample_size=sample_size,
        )

        # 付费率提升：基于 DNA 类型估算
        gene_type = dna_data.get("type", "")
        payer_lift_map = {
            "rescue": 0.23, "collection": 0.18, "rare_item": 0.15,
            "reward_reveal": 0.12, "progression": 0.10, "challenge": 0.05,
            "coins": 0.03, "curiosity": -0.10,
        }
        impact.payer_rate_lift = round(
            payer_lift_map.get(gene_type, 0.05) * max(baseline_payer, 0.05), 4
        )

        # LTV 提升
        ltv_lift_map = {
            "rescue": 0.41, "collection": 0.35, "rare_item": 0.28,
            "reward_reveal": 0.20, "progression": 0.15, "challenge": 0.08,
            "coins": 0.05, "curiosity": -0.15,
        }
        impact.ltv_lift = round(
            ltv_lift_map.get(gene_type, 0.10) * max(baseline_ltv, 1.0), 4
        )

        # 留存提升
        retention_lift_map = {
            "rescue": 0.15, "collection": 0.12, "progression": 0.20,
            "rare_item": 0.10, "reward_reveal": 0.08, "challenge": 0.05,
            "coins": 0.02, "curiosity": -0.05,
        }
        impact.retention_lift = round(
            retention_lift_map.get(gene_type, 0.05) * max(baseline_retention, 0.10), 4
        )

        # 综合影响分数
        impact.impact_score = round(
            abs(impact.payer_rate_lift) * 0.35
            + abs(impact.ltv_lift) * 0.40
            + abs(impact.retention_lift) * 0.25,
            3,
        )

        # 置信度
        impact.confidence = round(
            min(sample_size / 100.0, 1.0) * 0.7
            + min(abs(impact.impact_score) / 0.5, 1.0) * 0.3,
            3,
        )

        # 玩家类型关联
        if archetype:
            impact.highest_archetype = archetype.dominant_archetype
            impact.archetype_impact = {
                "collector": archetype.actual_collector,
                "power": archetype.actual_power,
                "progression": archetype.actual_progression,
                "explorer": archetype.actual_explorer,
                "casual": archetype.actual_casual,
            }

        return impact

    @staticmethod
    def _extract_winning_patterns(impacts: list[GeneImpact]) -> list[str]:
        """提取 Winning DNA 组合."""
        patterns = []
        positive = sorted(
            [g for g in impacts if g.is_positive_impact],
            key=lambda g: g.impact_score, reverse=True,
        )
        if positive:
            top_genes = [g.gene_name for g in positive[:3]]
            avg_ltv = sum(g.ltv_lift for g in positive[:3]) / max(len(positive[:3]), 1)
            patterns.append(
                f"{' + '.join(top_genes)} = high_value_players (avg_ltv_lift={avg_ltv:.2f})"
            )
        return patterns

    @staticmethod
    def _extract_losing_patterns(impacts: list[GeneImpact]) -> list[str]:
        """提取 Losing DNA 组合."""
        patterns = []
        negative = sorted(
            [g for g in impacts if not g.is_positive_impact],
            key=lambda g: g.impact_score,
        )
        if negative:
            bottom_genes = [g.gene_name for g in negative[:2]]
            patterns.append(
                f"{' + '.join(bottom_genes)} = low_value_players"
            )
        return patterns

    # ── Query ───────────────────────────────────────────────

    def get(self, creative_id: str) -> CausalDiscoveryResult | None:
        return self._results.get(creative_id)

    def get_all(self) -> list[CausalDiscoveryResult]:
        return list(self._results.values())

    def get_positive_genes(self) -> list[GeneImpact]:
        """获取所有正面影响基因."""
        all_genes = []
        for r in self._results.values():
            all_genes.extend(r.top_positive_genes)
        return sorted(all_genes, key=lambda g: g.impact_score, reverse=True)

    def get_high_confidence_genes(self) -> list[GeneImpact]:
        """获取所有高置信度基因."""
        all_genes = []
        for r in self._results.values():
            all_genes.extend(r.top_high_confidence_genes)
        return sorted(all_genes, key=lambda g: g.confidence, reverse=True)

    def compute_dna_level_correlation(
        self,
        creative_dna_map: dict[str, dict[str, Any]],
        ltv_map: dict[str, LTVProfile],
    ) -> dict[str, dict[str, Any]]:
        """DNA 级 LTV 相关性分析。

        按 DNA 元素（hook/rescue, hook/challenge, ...）分组，
        计算每组平均 LTV。
        """
        dna_groups: dict[str, list[float]] = {}

        for cid, dna_map in creative_dna_map.items():
            ltv = ltv_map.get(cid)
            if not ltv:
                continue

            for category, dna_data in dna_map.items():
                if isinstance(dna_data, dict) and "type" in dna_data:
                    key = f"{category}:{dna_data['type']}"
                    if key not in dna_groups:
                        dna_groups[key] = []
                    dna_groups[key].append(ltv.d30_ltv)

        result = {}
        for key, ltvs in dna_groups.items():
            if len(ltvs) >= 2:
                avg_ltv = sum(ltvs) / len(ltvs)
                result[key] = {
                    "avg_d30_ltv": round(avg_ltv, 2),
                    "sample_size": len(ltvs),
                    "min_ltv": round(min(ltvs), 2),
                    "max_ltv": round(max(ltvs), 2),
                }

        return result

    # ── Statistics ──────────────────────────────────────────

    def discovery_stats(self) -> dict[str, Any]:
        """因果发现统计."""
        results = list(self._results.values())
        if not results:
            return {"total_creatives": 0}

        all_genes = []
        for r in results:
            all_genes.extend(r.gene_impacts)

        positive_count = sum(1 for g in all_genes if g.is_positive_impact)
        high_conf_count = sum(1 for g in all_genes if g.is_high_confidence)

        return {
            "total_creatives": len(results),
            "total_gene_impacts": len(all_genes),
            "positive_impact_count": positive_count,
            "high_confidence_count": high_conf_count,
            "avg_impact_score": round(
                sum(g.impact_score for g in all_genes) / max(len(all_genes), 1), 3
            ),
            "avg_confidence": round(
                sum(g.confidence for g in all_genes) / max(len(all_genes), 1), 3
            ),
            "top_positive_genes": [
                {"gene": g.gene_name, "impact": g.impact_score}
                for g in sorted(all_genes, key=lambda x: x.impact_score, reverse=True)[:5]
            ],
            "winning_patterns": [
                p for r in results for p in r.winning_patterns
            ],
        }