"""E12.5.1 — Experience Store。

持久化经验记忆存储，支持多维度查询和聚合统计。

核心功能:
  - 存储 ExperienceRecord
  - 多条件查询（产品、市场、平台、突变类型、结果）
  - 聚合统计（成功率、平均改善、按基因/突变分组）
  - 模式提取（从历史记录中总结规律）
  - 导入导出（JSON 序列化）
"""

from __future__ import annotations

from collections import defaultdict

from .models import (
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceQuery,
    ExperienceRecord,
    ExperienceStats,
    MutationType,
)


class ExperienceStore:
    """经验记忆存储引擎。

    存储所有实验经验，支持多维度查询和统计分析。

    Usage:
        >>> store = ExperienceStore()
        >>> store.add(record)
        >>> results = store.query(ExperienceQuery(product_id="p04"))
        >>> stats = store.get_stats()
        >>> patterns = store.extract_patterns(min_sample=5)
    """

    def __init__(self) -> None:
        self._records: list[ExperienceRecord] = []

        # 索引：加速查询
        self._by_product: dict[str, list[int]] = defaultdict(list)
        self._by_market: dict[str, list[int]] = defaultdict(list)
        self._by_mutation_type: dict[str, list[int]] = defaultdict(list)
        self._by_outcome: dict[str, list[int]] = defaultdict(list)
        self._by_gene: dict[str, list[int]] = defaultdict(list)

    # ── CRUD ───────────────────────────────────────────────

    def add(self, record: ExperienceRecord) -> None:
        """添加一条经验记录。"""
        idx = len(self._records)
        self._records.append(record)

        # 更新索引
        self._by_product[record.product_id].append(idx)
        self._by_market[record.context.market].append(idx)
        self._by_mutation_type[record.mutation_type.value].append(idx)
        self._by_outcome[record.result.outcome.value].append(idx)
        for gene in record.changed_genes:
            self._by_gene[gene].append(idx)

    def add_batch(self, records: list[ExperienceRecord]) -> None:
        """批量添加。"""
        for record in records:
            self.add(record)

    def get(self, experience_id: str) -> ExperienceRecord | None:
        """按 ID 获取。"""
        for record in self._records:
            if record.experience_id == experience_id:
                return record
        return None

    def remove(self, experience_id: str) -> bool:
        """删除一条记录。"""
        for i, record in enumerate(self._records):
            if record.experience_id == experience_id:
                self._records.pop(i)
                self._rebuild_indices()
                return True
        return False

    def clear(self) -> None:
        """清空所有记录。"""
        self._records.clear()
        self._by_product.clear()
        self._by_market.clear()
        self._by_mutation_type.clear()
        self._by_outcome.clear()
        self._by_gene.clear()

    # ── Query ──────────────────────────────────────────────

    def query(self, query: ExperienceQuery) -> list[ExperienceRecord]:
        """多条件查询。

        使用索引加速，优先使用选择性最高的条件。

        Args:
            query: 查询条件

        Returns:
            匹配的记录列表（按时间倒序）
        """
        # 使用索引缩小候选集
        candidate_indices: set[int] | None = None

        if query.product_id:
            candidate_indices = set(self._by_product.get(query.product_id, []))

        if query.mutation_type and query.mutation_type is not None:
            idx_set = set(self._by_mutation_type.get(query.mutation_type.value, []))
            candidate_indices = (
                idx_set if candidate_indices is None
                else candidate_indices & idx_set
            )

        if query.outcome and query.outcome is not None:
            idx_set = set(self._by_outcome.get(query.outcome.value, []))
            candidate_indices = (
                idx_set if candidate_indices is None
                else candidate_indices & idx_set
            )

        if query.changed_gene:
            idx_set = set(self._by_gene.get(query.changed_gene, []))
            candidate_indices = (
                idx_set if candidate_indices is None
                else candidate_indices & idx_set
            )

        if query.market:
            idx_set = set(self._by_market.get(query.market, []))
            candidate_indices = (
                idx_set if candidate_indices is None
                else candidate_indices & idx_set
            )

        # 获取候选记录
        if candidate_indices is not None:
            candidates = [
                self._records[i] for i in candidate_indices
                if i < len(self._records)
            ]
        else:
            candidates = list(self._records)

        # 精细过滤
        results = [r for r in candidates if query.matches(r)]

        # 按时间倒序
        results.sort(key=lambda r: r.created_at, reverse=True)

        # 分页
        if query.offset > 0:
            results = results[query.offset:]
        if query.limit > 0:
            results = results[:query.limit]

        return results

    def query_all(self) -> list[ExperienceRecord]:
        """获取所有记录。"""
        return list(self._records)

    def query_by_product(self, product_id: str) -> list[ExperienceRecord]:
        """按产品查询。"""
        indices = self._by_product.get(product_id, [])
        return [self._records[i] for i in indices if i < len(self._records)]

    def query_by_mutation_type(self, mutation_type: MutationType) -> list[ExperienceRecord]:
        """按突变类型查询。"""
        indices = self._by_mutation_type.get(mutation_type.value, [])
        return [self._records[i] for i in indices if i < len(self._records)]

    def query_by_outcome(self, outcome: ExperienceOutcome) -> list[ExperienceRecord]:
        """按结果查询。"""
        indices = self._by_outcome.get(outcome.value, [])
        return [self._records[i] for i in indices if i < len(self._records)]

    def query_successful(self) -> list[ExperienceRecord]:
        """查询所有成功的经验。"""
        return self.query_by_outcome(ExperienceOutcome.SUCCESS)

    def query_by_gene(self, gene: str) -> list[ExperienceRecord]:
        """按修改的基因查询。"""
        indices = self._by_gene.get(gene, [])
        return [self._records[i] for i in indices if i < len(self._records)]

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self, query: ExperienceQuery | None = None) -> ExperienceStats:
        """获取聚合统计。

        Args:
            query: 可选的过滤条件

        Returns:
            ExperienceStats
        """
        records = self.query(query) if query else self._records

        if not records:
            return ExperienceStats()

        total = len(records)
        successes = [r for r in records if r.is_success]
        success_count = len(successes)
        success_rate = success_count / total if total > 0 else 0.0

        improvements = [r.improvement for r in records]
        mean_improvement = sum(improvements) / total if total > 0 else 0.0
        best_improvement = max(improvements) if improvements else 0.0

        # 按突变类型分组
        by_mutation: dict[str, int] = defaultdict(int)
        for r in records:
            by_mutation[r.mutation_type.value] += 1

        # 按基因分组
        by_gene: dict[str, int] = defaultdict(int)
        for r in records:
            for gene in r.changed_genes:
                by_gene[gene] += 1

        # 按结果分组
        by_outcome: dict[str, int] = defaultdict(int)
        for r in records:
            by_outcome[r.result.outcome.value] += 1

        # 最佳洞察
        top_insights = [
            r.result.insight for r in successes
            if r.result.insight
        ][:5]

        return ExperienceStats(
            total_records=total,
            success_count=success_count,
            success_rate=success_rate,
            mean_improvement=mean_improvement,
            best_improvement=best_improvement,
            by_mutation_type=dict(by_mutation),
            by_gene=dict(by_gene),
            by_outcome=dict(by_outcome),
            top_insights=top_insights,
        )

    def get_stats_by_product(self) -> dict[str, ExperienceStats]:
        """按产品分组统计。"""
        result: dict[str, ExperienceStats] = {}
        for product_id in self._by_product:
            records = self.query_by_product(product_id)
            if records:
                result[product_id] = self.get_stats(
                    ExperienceQuery(product_id=product_id)
                )
        return result

    def get_stats_by_mutation_type(self) -> dict[str, ExperienceStats]:
        """按突变类型分组统计。"""
        result: dict[str, ExperienceStats] = {}
        for mt in MutationType:
            records = self.query_by_mutation_type(mt)
            if records:
                result[mt.value] = self.get_stats(
                    ExperienceQuery(mutation_type=mt)
                )
        return result

    # ── Pattern Extraction ─────────────────────────────────

    def extract_patterns(self, min_sample: int = 3) -> list[ExperiencePattern]:
        """从历史记录中提取经验模式。

        Args:
            min_sample: 最低样本量

        Returns:
            ExperiencePattern 列表（按置信度降序）
        """
        patterns: list[ExperiencePattern] = []

        # 1. 按突变类型提取模式
        for mt in MutationType:
            records = self.query_by_mutation_type(mt)
            if len(records) < min_sample:
                continue

            successes = [r for r in records if r.is_success]
            success_rate = len(successes) / len(records) if records else 0.0
            avg_imp = sum(r.improvement for r in records) / len(records) if records else 0.0

            genes = set()
            for r in records:
                genes.update(r.changed_genes)

            pattern = ExperiencePattern(
                pattern_type="mutation_pattern",
                description=f"Mutation type '{mt.value}' success rate",
                genes=list(genes),
                success_rate=success_rate,
                avg_improvement=avg_imp,
                sample_size=len(records),
                evidence=[r.experience_id for r in records],
                confidence=min(success_rate, 0.5 + 0.1 * min(len(records) / 10, 0.5)),
            )
            patterns.append(pattern)

        # 2. 按基因提取模式
        for gene, indices in self._by_gene.items():
            if len(indices) < min_sample:
                continue

            records = [self._records[i] for i in indices if i < len(self._records)]
            successes = [r for r in records if r.is_success]
            success_rate = len(successes) / len(records) if records else 0.0
            avg_imp = sum(r.improvement for r in records) / len(records) if records else 0.0

            pattern = ExperiencePattern(
                pattern_type="gene_pattern",
                description=f"Changing gene '{gene}' success rate",
                genes=[gene],
                success_rate=success_rate,
                avg_improvement=avg_imp,
                sample_size=len(records),
                evidence=[r.experience_id for r in records],
                confidence=min(success_rate, 0.5 + 0.1 * min(len(records) / 10, 0.5)),
            )
            patterns.append(pattern)

        # 3. 按产品+突变类型提取模式
        product_mutation_pairs: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for record in self._records:
            key = f"{record.product_id}:{record.mutation_type.value}"
            product_mutation_pairs[key].append(record)

        for key, records in product_mutation_pairs.items():
            if len(records) < min_sample:
                continue

            successes = [r for r in records if r.is_success]
            success_rate = len(successes) / len(records) if records else 0.0
            avg_imp = sum(r.improvement for r in records) / len(records) if records else 0.0

            genes = set()
            for r in records:
                genes.update(r.changed_genes)

            pattern = ExperiencePattern(
                pattern_type="context_pattern",
                description=f"Product-mutation combo '{key}' success rate",
                genes=list(genes),
                success_rate=success_rate,
                avg_improvement=avg_imp,
                sample_size=len(records),
                evidence=[r.experience_id for r in records],
                confidence=min(success_rate, 0.5 + 0.1 * min(len(records) / 10, 0.5)),
            )
            patterns.append(pattern)

        # 按置信度降序
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    def get_reliable_patterns(self, min_sample: int = 3) -> list[ExperiencePattern]:
        """获取可靠模式（样本量足够 + 置信度达标）。"""
        return [
            p for p in self.extract_patterns(min_sample=min_sample)
            if p.is_reliable
        ]

    # ── Export ─────────────────────────────────────────────

    def to_dict_list(self) -> list[dict]:
        """导出所有记录为字典列表。"""
        return [r.to_dict() for r in self._records]

    def to_summary(self) -> dict:
        """导出存储摘要。"""
        return {
            "total_records": len(self._records),
            "products": list(self._by_product.keys()),
            "markets": list(self._by_market.keys()),
            "mutation_types": list(self._by_mutation_type.keys()),
            "outcomes": list(self._by_outcome.keys()),
            "genes": list(self._by_gene.keys()),
            "stats": self.get_stats().to_dict(),
        }

    # ── Private ────────────────────────────────────────────

    def _rebuild_indices(self) -> None:
        """重建所有索引。"""
        self._by_product.clear()
        self._by_market.clear()
        self._by_mutation_type.clear()
        self._by_outcome.clear()
        self._by_gene.clear()

        for idx, record in enumerate(self._records):
            self._by_product[record.product_id].append(idx)
            self._by_market[record.context.market].append(idx)
            self._by_mutation_type[record.mutation_type.value].append(idx)
            self._by_outcome[record.result.outcome.value].append(idx)
            for gene in record.changed_genes:
                self._by_gene[gene].append(idx)

    def __len__(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"ExperienceStore(records={len(self._records)})"