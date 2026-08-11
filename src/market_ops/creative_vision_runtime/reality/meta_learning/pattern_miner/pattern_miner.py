"""E12.5.2 — Pattern Extractor。

从经验记录中提取基因聚类，构建 MetaPattern。

核心流程:
  Experience Records
         │
         ▼
  Gene Extraction (GeneAnalyzer)
         │
         ▼
  Gene Clustering (by feature_key)
         │
         ▼
  Performance Aggregation
         │
         ▼
  MetaPattern Construction

算法:
  Step 1: 聚合相似 DNA（基于 feature_key 聚类）
  Step 2: 统计每个聚类的表现（成功率、ROAS/CTR/CVR 提升）
  Step 3: 构建 MetaPattern 输出
"""

from __future__ import annotations

from collections import defaultdict

from ..models import ExperienceRecord, GeneCategory
from .models import (
    ExtractedGene,
    GeneCluster,
    MetaPattern,
    PatternType,
)
from .gene_analyzer import GeneAnalyzer


# ── Pattern Naming ─────────────────────────────────────────


def _generate_pattern_name(
    pattern_type: PatternType,
    features: dict[str, str],
) -> str:
    """根据基因特征生成人类可读的模式名称。"""
    name_parts: list[str] = []

    if pattern_type == PatternType.HOOK:
        emotion = features.get("emotion", "")
        character = features.get("character", "")
        conflict = features.get("conflict", "")
        if emotion:
            name_parts.append(emotion.replace("_", " ").title())
        if character:
            name_parts.append(character.replace("_", " ").title())
        if conflict:
            name_parts.append(conflict.replace("_", " ").title())
        if name_parts:
            return " ".join(name_parts) + " Hook"
        return "Unknown Hook"

    if pattern_type == PatternType.VISUAL:
        style = features.get("style", "")
        if style:
            return style.replace("_", " ").title() + " Visual"
        return "Unknown Visual"

    if pattern_type == PatternType.GAMEPLAY:
        mechanism = features.get("mechanism", "")
        if mechanism:
            return mechanism.replace("_", " ").title() + " Gameplay"
        return "Unknown Gameplay"

    if pattern_type == PatternType.REWARD:
        reward = features.get("reward_type", "")
        if reward:
            return reward.replace("_", " ").title() + " Reward"
        return "Unknown Reward"

    if pattern_type == PatternType.PSYCHOLOGY:
        drive = features.get("drive", "")
        if drive:
            return drive.replace("_", " ").title() + " Psychology"
        return "Unknown Psychology"

    return "Unknown Pattern"


def _map_to_pattern_type(gene_category: str) -> PatternType:
    """将基因类别映射到 PatternType。"""
    mapping: dict[str, PatternType] = {
        "hook": PatternType.HOOK,
        "visual": PatternType.VISUAL,
        "visual_style": PatternType.VISUAL,
        "gameplay": PatternType.GAMEPLAY,
        "reward": PatternType.REWARD,
        "monetization": PatternType.REWARD,
        "audience": PatternType.AUDIENCE,
        "market": PatternType.MARKET,
        "psychology": PatternType.PSYCHOLOGY,
        "context": PatternType.MARKET,
    }
    return mapping.get(gene_category, PatternType.FULL_CREATIVE)


# ── PatternExtractor ───────────────────────────────────────


class PatternExtractor:
    """模式提取引擎 —— 从经验中挖掘 Winner Pattern。

    Usage:
        >>> extractor = PatternExtractor()
        >>> patterns = extractor.extract(experiences)
        >>> for p in patterns:
        ...     print(p.name, p.success_rate, p.avg_roas_gain)
    """

    def __init__(self, min_cluster_size: int = 3) -> None:
        self._analyzer = GeneAnalyzer()
        self._min_cluster_size = min_cluster_size

    def extract(self, experiences: list[ExperienceRecord]) -> list[MetaPattern]:
        """从经验记录中提取 MetaPattern 列表。

        Args:
            experiences: 经验记录列表

        Returns:
            MetaPattern 列表（按 rank_score 降序）
        """
        if not experiences:
            return []

        # Step 1: 基因提取
        all_genes = self._analyzer.extract_genes_batch(experiences)

        # Step 2: 基因聚类
        clusters = self._cluster_genes(experiences, all_genes)

        # Step 3: 构建 MetaPattern
        patterns = self._build_patterns(clusters)

        return patterns

    def extract_from_store(
        self,
        store,  # ExperienceStore
        min_cluster_size: int | None = None,
    ) -> list[MetaPattern]:
        """从 ExperienceStore 中提取模式。

        Args:
            store:             ExperienceStore 实例
            min_cluster_size:  最低聚类大小

        Returns:
            MetaPattern 列表
        """
        if min_cluster_size is not None:
            self._min_cluster_size = min_cluster_size
        return self.extract(store.query_all())

    def _cluster_genes(
        self,
        experiences: list[ExperienceRecord],
        all_genes: list[list[ExtractedGene]],
    ) -> list[GeneCluster]:
        """按 feature_key 聚类基因。

        将具有相同 feature_key 的基因聚合在一起，
        统计每个聚类的表现指标。

        Args:
            experiences: 经验记录列表
            all_genes:   每条经验的基因提取结果

        Returns:
            GeneCluster 列表
        """
        # 按 (gene_category, feature_key) 分组
        cluster_map: dict[str, list[tuple[int, ExtractedGene]]] = defaultdict(list)

        for exp_idx, gene_list in enumerate(all_genes):
            for gene in gene_list:
                key = f"{gene.gene_category}:{gene.feature_key}"
                cluster_map[key].append((exp_idx, gene))

        # 构建 GeneCluster
        clusters: list[GeneCluster] = []
        for key, entries in cluster_map.items():
            if len(entries) < self._min_cluster_size:
                continue

            gene_category = key.split(":", 1)[0]
            exp_indices = [e[0] for e in entries]
            representative = entries[0][1]

            # 收集指标
            roas_gains: list[float] = []
            ctr_gains: list[float] = []
            cvr_gains: list[float] = []
            improvements: list[float] = []
            success_count = 0
            member_ids: list[str] = []

            for exp_idx in exp_indices:
                exp = experiences[exp_idx]
                member_ids.append(exp.experience_id)

                if exp.is_success:
                    success_count += 1

                # 从 metrics_delta 提取增益
                delta = exp.experiment.metrics_delta
                if "roas" in delta:
                    roas_gains.append(delta["roas"])
                if "ctr" in delta:
                    ctr_gains.append(delta["ctr"])
                if "cvr" in delta:
                    cvr_gains.append(delta["cvr"])

                improvements.append(exp.improvement)

            sample_count = len(entries)
            success_rate = success_count / sample_count if sample_count > 0 else 0.0

            cluster = GeneCluster(
                gene_category=gene_category,
                feature_key=representative.feature_key,
                members=member_ids,
                sample_count=sample_count,
                success_count=success_count,
                success_rate=success_rate,
                avg_roas_gain=sum(roas_gains) / len(roas_gains) if roas_gains else 0.0,
                avg_ctr_gain=sum(ctr_gains) / len(ctr_gains) if ctr_gains else 0.0,
                avg_cvr_gain=sum(cvr_gains) / len(cvr_gains) if cvr_gains else 0.0,
                avg_improvement=sum(improvements) / len(improvements) if improvements else 0.0,
                representative_genes=representative.features,
            )
            clusters.append(cluster)

        return clusters

    def _build_patterns(self, clusters: list[GeneCluster]) -> list[MetaPattern]:
        """从聚类构建 MetaPattern。

        Args:
            clusters: GeneCluster 列表

        Returns:
            MetaPattern 列表
        """
        patterns: list[MetaPattern] = []

        for cluster in clusters:
            pattern_type = _map_to_pattern_type(cluster.gene_category)
            name = _generate_pattern_name(pattern_type, cluster.representative_genes)

            # 置信度：基于样本量和成功率的综合置信度
            sample_factor = min(cluster.sample_count / 20, 1.0)
            confidence = cluster.success_rate * 0.6 + sample_factor * 0.4

            # 收集市场和产品
            markets_set: set[str] = set()
            products_set: set[str] = set()
            platforms_set: set[str] = set()

            # 从原始经验中提取（需要重新遍历，但 clusters 不持有原始引用）
            # 这里我们通过 cluster.members 查找，但当前实现不直接持有
            # 使用 representative_genes 作为默认
            if not markets_set:
                markets_set = {"unknown"}

            # 洞察生成
            insight = self._generate_insight(
                pattern_type=pattern_type,
                name=name,
                cluster=cluster,
            )

            # 推荐策略
            recommendation = self._generate_recommendation(
                pattern_type=pattern_type,
                cluster=cluster,
            )

            pattern = MetaPattern(
                pattern_type=pattern_type,
                name=name,
                genes=cluster.representative_genes,
                sample_count=cluster.sample_count,
                success_count=cluster.success_count,
                success_rate=cluster.success_rate,
                avg_roas_gain=cluster.avg_roas_gain,
                avg_ctr_gain=cluster.avg_ctr_gain,
                avg_cvr_gain=cluster.avg_cvr_gain,
                confidence=confidence,
                evidence=cluster.members,
                insight=insight,
                recommendation=recommendation,
            )

            patterns.append(pattern)

        # 按成功率降序排序
        patterns.sort(key=lambda p: p.success_rate, reverse=True)
        return patterns

    @staticmethod
    def _generate_insight(
        pattern_type: PatternType,
        name: str,
        cluster: GeneCluster,
    ) -> str:
        """生成模式洞察。"""
        if cluster.success_rate >= 0.7:
            quality = "strongly"
        elif cluster.success_rate >= 0.5:
            quality = "moderately"
        else:
            quality = "weakly"

        return (
            f"'{name}' pattern ({pattern_type.value}) is {quality} predictive "
            f"of success ({cluster.success_rate:.0%} success rate, "
            f"n={cluster.sample_count}). "
            f"Average improvement: {cluster.avg_improvement:+.2f}, "
            f"ROAS gain: {cluster.avg_roas_gain:+.2f}."
        )

    @staticmethod
    def _generate_recommendation(
        pattern_type: PatternType,
        cluster: GeneCluster,
    ) -> str:
        """生成推荐策略。"""
        if cluster.success_rate >= 0.7:
            action = "Amplify"
        elif cluster.success_rate >= 0.5:
            action = "Explore"
        else:
            action = "Suppress"

        return (
            f"{action} {pattern_type.value} pattern: "
            f"genes={cluster.representative_genes}, "
            f"expected success rate={cluster.success_rate:.0%}"
        )

    def __repr__(self) -> str:
        return f"PatternExtractor(min_cluster={self._min_cluster_size})"