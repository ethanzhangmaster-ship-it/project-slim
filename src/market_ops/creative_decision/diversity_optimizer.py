"""Module 3: Creative Diversity Optimizer

目标：确保 Top20 不是全部 Dragon。
自动聚类并按 cluster 保留 Top2。

200 Variants → Cluster → 20 Clusters → 每Cluster Top2 → Top20
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClusterResult:
    cluster_id: str
    cluster_features: dict                     # 聚类中心特征
    members: list[str] = field(default_factory=list)  # variant_id 列表
    top_variant: str = ""
    top_score: float = 0.0


class CreativeDiversityOptimizer:
    """创意多样性优化器
    
    聚类维度：
    - Creature Type (dragon/cat/fox/owl/unicorn/fairy)
    - Character Type (witch/wizard/girl/boy)
    - Background Type (forest/cave/lake/garden/tower)
    - Hook Type (collection/curiosity/crisis)
    - Lighting Type (warm/cool/golden/moon)
    - Color Theme (purple/blue/gold/pink)
    
    聚类方法：基于 DNA 字段的精确匹配聚类（规则聚类）
    例如：所有 "dragon + forest + warm" 的 variant 聚为一类
    
    选择策略：
    - 每个 cluster 保留 overall_score 最高的 1-2 个
    - 优先选择不同 cluster 的 variant
    - 确保最终 Top20 覆盖至少 10+ 个不同 cluster
    """

    CLUSTER_KEYS = [
        "creature_type",
        "character_type",
        "background_type",
        "hook_type",
        "lighting_type",
        "color_theme",
    ]

    def _extract_dna(self, variant: dict) -> dict:
        """从 variant 中提取聚类用的 DNA 字段。"""
        dna = {}
        for key in self.CLUSTER_KEYS:
            val = variant.get(key)
            if val is None:
                # 尝试从嵌套的 dna 或 features 结构读取
                val = variant.get("dna", {}).get(key)
            if val is None:
                val = variant.get("features", {}).get(key)
            dna[key] = val if val is not None else "unknown"
        return dna

    def _make_cluster_id(self, dna: dict) -> str:
        """根据 DNA 生成 cluster_id，例如 dragon|forest|warm."""
        parts = [str(dna.get(k, "unknown")) for k in self.CLUSTER_KEYS]
        return "|".join(parts)

    def cluster(self, variants: list[dict]) -> list[ClusterResult]:
        """对 variants 进行聚类
        
        Args:
            variants: ranking.json 中的 variant 列表
        """
        groups: dict[str, list[dict]] = {}
        for v in variants:
            dna = self._extract_dna(v)
            cid = self._make_cluster_id(dna)
            groups.setdefault(cid, []).append(v)

        results: list[ClusterResult] = []
        for cid, members in groups.items():
            # 按 overall_score 降序
            sorted_members = sorted(
                members,
                key=lambda x: x.get("overall_score", 0.0),
                reverse=True,
            )
            dna = self._extract_dna(sorted_members[0])
            top = sorted_members[0]
            results.append(
                ClusterResult(
                    cluster_id=cid,
                    cluster_features=dna,
                    members=[m.get("variant_id", "") for m in sorted_members],
                    top_variant=top.get("variant_id", ""),
                    top_score=top.get("overall_score", 0.0),
                )
            )

        # 按 top_score 降序排列 cluster
        results.sort(key=lambda c: c.top_score, reverse=True)
        return results

    def select_diverse_top(self, variants: list[dict], top_n: int = 20, per_cluster: int = 2) -> list[dict]:
        """选择多样性 Top N
        
        策略：
        1. 先按 overall_score 排序
        2. 聚类
        3. 从每个 cluster 选最高分的 1-2 个
        4. 如果总数不足，从剩余高分 variant 补充
        5. 如果总数超过，保留 cluster 代表中分数最高的
        """
        if not variants:
            return []

        clusters = self.cluster(variants)

        selected: list[dict] = []
        selected_ids: set[str] = set()

        # Step 3: 从每个 cluster 选最高分的 per_cluster 个
        for c in clusters:
            members = [v for v in variants if v.get("variant_id", "") in c.members]
            members = sorted(members, key=lambda x: x.get("overall_score", 0.0), reverse=True)
            for m in members[:per_cluster]:
                vid = m.get("variant_id", "")
                if vid not in selected_ids:
                    selected.append(m)
                    selected_ids.add(vid)

        # Step 4: 如果总数不足，从剩余高分 variant 补充
        if len(selected) < top_n:
            all_sorted = sorted(variants, key=lambda x: x.get("overall_score", 0.0), reverse=True)
            for v in all_sorted:
                vid = v.get("variant_id", "")
                if vid not in selected_ids:
                    selected.append(v)
                    selected_ids.add(vid)
                    if len(selected) >= top_n:
                        break

        # Step 5: 如果总数超过，按 overall_score 截断，同时保证 cluster 覆盖度
        if len(selected) > top_n:
            # 先按分数排序
            selected = sorted(selected, key=lambda x: x.get("overall_score", 0.0), reverse=True)
            # 确保至少覆盖 min(10, len(clusters)) 个 cluster
            min_clusters = min(10, len(clusters))
            final: list[dict] = []
            final_ids: set[str] = set()
            covered_clusters: set[str] = set()

            # 第一轮：优先保证每个 cluster 至少有一个代表
            for v in selected:
                dna = self._extract_dna(v)
                cid = self._make_cluster_id(dna)
                if cid not in covered_clusters and len(final) < top_n:
                    final.append(v)
                    final_ids.add(v.get("variant_id", ""))
                    covered_clusters.add(cid)

            # 第二轮：按分数补充到 top_n
            for v in selected:
                vid = v.get("variant_id", "")
                if vid not in final_ids and len(final) < top_n:
                    final.append(v)
                    final_ids.add(vid)

            selected = final

        return selected[:top_n]
