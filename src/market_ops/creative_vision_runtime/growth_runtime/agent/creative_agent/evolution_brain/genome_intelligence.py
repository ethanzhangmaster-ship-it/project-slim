"""E14.5.1 Genome Intelligence Layer — 基因级别智能分析.

职责:
  1. 从 CreativeMemory 中提取历史 DNA 表现数据
  2. 计算每个基因值 (e.g. transformation hook) 的性能指标
  3. 分析基因值的最佳上下文 (游戏/平台/市场/阶段)
  4. 生成 GenomeIntelligenceReport 为进化规划提供基础

核心概念:
  - GenePerformance: 基因值的性能统计 (样本量、胜率、平均ROAS/LTV)
  - ContextAffinity: 基因值在特定上下文中的表现
  - GeneIntelligence: 基因类别的完整智能画像
  - GenomeIntelligenceReport: 全基因组智能分析报告

数据流:
  CreativeMemory (DNA entries + 决策记录)
       ↓
  GenomeIntelligence.analyze()
       ↓
  GenomeIntelligenceReport
       ↓
  EvolutionPlanner (E14.5.3)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.memory import (
    CreativeMemory,
    CreativeDNAMemoryEntry,
)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class GenePerformance:
    """单个基因值的性能统计.

    例如: hook=transformation 在 124 个样本中的表现.

    Attributes:
        gene_value: 基因值 (e.g. "transformation", "fantasy")
        samples: 样本数量
        win_count: 赢家数量
        win_rate: 胜率
        avg_roas: 平均 ROAS
        avg_ltv: 平均 LTV
        avg_ctr: 平均 CTR
        avg_payer_rate: 平均付费率
        confidence: 置信度 (基于样本量和胜率)
    """
    gene_value: str = ""
    samples: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    avg_roas: float = 0.0
    avg_ltv: float = 0.0
    avg_ctr: float = 0.0
    avg_payer_rate: float = 0.0
    confidence: float = 0.0

    @property
    def is_reliable(self) -> bool:
        """置信度 >= 0.5 且样本 >= 5."""
        return self.confidence >= 0.5 and self.samples >= 5

    @property
    def is_high_confidence(self) -> bool:
        """置信度 >= 0.7 且样本 >= 10."""
        return self.confidence >= 0.7 and self.samples >= 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_value": self.gene_value,
            "samples": self.samples,
            "win_count": self.win_count,
            "win_rate": round(self.win_rate, 3),
            "avg_roas": round(self.avg_roas, 2),
            "avg_ltv": round(self.avg_ltv, 1),
            "avg_ctr": round(self.avg_ctr, 4),
            "avg_payer_rate": round(self.avg_payer_rate, 3),
            "confidence": round(self.confidence, 3),
            "is_reliable": self.is_reliable,
            "is_high_confidence": self.is_high_confidence,
        }


@dataclass
class ContextAffinity:
    """基因值在特定上下文中的表现.

    e.g. transformation hook 在
      game=merge, platform=android, market=US, stage=growth
    中的表现.

    Attributes:
        game: 游戏类型
        platform: 平台
        market: 市场
        stage: 生命周期阶段
        samples: 该上下文中的样本数
        avg_roas: 该上下文中的平均 ROAS
        win_rate: 该上下文中的胜率
        affinity_score: 亲和力分数 (越高越适合该上下文)
    """
    game: str = ""
    platform: str = ""
    market: str = ""
    stage: str = ""
    samples: int = 0
    avg_roas: float = 0.0
    win_rate: float = 0.0
    affinity_score: float = 0.0

    @property
    def context_key(self) -> str:
        return f"{self.game}:{self.platform}:{self.market}:{self.stage}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "platform": self.platform,
            "market": self.market,
            "stage": self.stage,
            "samples": self.samples,
            "avg_roas": round(self.avg_roas, 2),
            "win_rate": round(self.win_rate, 3),
            "affinity_score": round(self.affinity_score, 3),
        }


@dataclass
class GeneIntelligence:
    """基因类别的完整智能画像.

    例如: hook 基因的所有已知值及其表现.

    Attributes:
        gene_category: 基因类别 (e.g. "hook", "visual", "emotion")
        values: 该类别下所有基因值及其性能
        best_value: 最佳基因值
        best_roas: 最佳 ROAS
        best_contexts: 最佳上下文
        total_samples: 总样本数
        diversity: 基因值多样性 (唯一值数量)
    """
    gene_category: str = ""
    values: list[GenePerformance] = field(default_factory=list)
    best_value: str = ""
    best_roas: float = 0.0
    best_contexts: list[ContextAffinity] = field(default_factory=list)
    total_samples: int = 0
    diversity: int = 0

    @property
    def has_reliable_data(self) -> bool:
        return any(v.is_reliable for v in self.values)

    @property
    def top_values(self) -> list[GenePerformance]:
        """返回 Top 5 基因值 (按 win_rate * confidence 排序)."""
        sorted_values = sorted(
            self.values,
            key=lambda v: v.win_rate * v.confidence,
            reverse=True,
        )
        return sorted_values[:5]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "values": [v.to_dict() for v in self.values],
            "best_value": self.best_value,
            "best_roas": round(self.best_roas, 2),
            "best_contexts": [c.to_dict() for c in self.best_contexts],
            "total_samples": self.total_samples,
            "diversity": self.diversity,
            "has_reliable_data": self.has_reliable_data,
            "top_values": [v.to_dict() for v in self.top_values],
        }


@dataclass
class GenomeIntelligenceReport:
    """全基因组智能分析报告.

    Attributes:
        report_id: 报告 ID
        genes: 各基因类别的智能画像
        total_dnas_analyzed: 分析的 DNA 总数
        winner_count: 赢家数量
        overall_diversity_score: 整体多样性分数
        summary: 文字摘要
        created_at: 创建时间
    """
    report_id: str = ""
    genes: dict[str, GeneIntelligence] = field(default_factory=dict)
    total_dnas_analyzed: int = 0
    winner_count: int = 0
    overall_diversity_score: float = 0.0
    summary: str = ""
    created_at: str = ""

    def get_gene(self, category: str) -> GeneIntelligence | None:
        return self.genes.get(category)

    def get_best_genes(self) -> dict[str, GenePerformance]:
        """获取每个基因类别的最佳值."""
        return {
            cat: GenePerformance(
                gene_value=gi.best_value,
                avg_roas=gi.best_roas,
            )
            for cat, gi in self.genes.items()
            if gi.best_value
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "genes": {k: v.to_dict() for k, v in self.genes.items()},
            "total_dnas_analyzed": self.total_dnas_analyzed,
            "winner_count": self.winner_count,
            "overall_diversity_score": round(self.overall_diversity_score, 3),
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# GenomeIntelligence — 核心引擎
# ═══════════════════════════════════════════════════════════

class GenomeIntelligence:
    """基因级别智能分析引擎.

    理解「一个 Creative DNA 为什么成功」，从历史数据中提取:
      - 每个基因值的性能指标 (ROAS, LTV, 胜率)
      - 基因值在特定上下文中的最佳表现
      - 全基因组多样性分析

    用法:
        engine = GenomeIntelligence(memory)
        report = engine.analyze()
        # report.get_gene("hook").best_value  → "transformation"
        # report.get_gene("hook").best_roas   → 1.82
    """

    # 基因类别定义 (与 E11 GENE_SLOTS 对齐)
    GENE_CATEGORIES = ["hook", "visual", "reward", "emotion", "gameplay"]

    def __init__(
        self,
        memory: CreativeMemory | None = None,
        min_samples: int = 5,
        min_confidence: float = 0.3,
    ):
        self._memory = memory or CreativeMemory()
        self._min_samples = min_samples
        self._min_confidence = min_confidence

    # ── 核心分析 ──────────────────────────────────────────

    def analyze(
        self,
        dna_entries: list[CreativeDNAMemoryEntry] | None = None,
        context_data: dict[str, dict[str, str]] | None = None,
    ) -> GenomeIntelligenceReport:
        """执行全基因组智能分析.

        Args:
            dna_entries: DNA 记忆条目列表 (None = 从 memory 获取全部)
            context_data: 上下文数据 {creative_id: {game, platform, market, stage}}

        Returns:
            GenomeIntelligenceReport: 全基因组智能分析报告
        """
        if dna_entries is None:
            dna_entries = self._memory.get_dna_entries_by_performance(min_roas=0.0)

        context_data = context_data or {}

        # 1. 计算每个基因类别的智能画像
        genes: dict[str, GeneIntelligence] = {}
        for category in self.GENE_CATEGORIES:
            gi = self._analyze_gene_category(category, dna_entries, context_data)
            if gi.total_samples > 0:
                genes[category] = gi

        # 2. 计算整体指标
        winner_count = sum(1 for e in dna_entries if e.is_winner)
        total_entries = len(dna_entries)

        # 3. 多样性分数
        diversity_score = self._calculate_diversity_score(genes)

        # 4. 生成摘要
        summary = self._generate_summary(genes, total_entries, winner_count)

        return GenomeIntelligenceReport(
            report_id=f"gi_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            genes=genes,
            total_dnas_analyzed=total_entries,
            winner_count=winner_count,
            overall_diversity_score=diversity_score,
            summary=summary,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _analyze_gene_category(
        self,
        category: str,
        entries: list[CreativeDNAMemoryEntry],
        context_data: dict[str, dict[str, str]],
    ) -> GeneIntelligence:
        """分析单个基因类别.

        从 DNA entries 中提取该基因类别的所有值及其表现.
        """
        # 按基因值聚合
        value_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for entry in entries:
            if not entry.dna or not entry.dna.genes:
                continue

            gene = entry.dna.genes.get(category)
            if not gene:
                continue

            # 提取基因值 (兼容 Gene 对象和 dict)
            if hasattr(gene, 'value'):
                gene_value = str(gene.value)
            elif isinstance(gene, dict):
                gene_value = str(gene.get("value", gene.get("type", "")))
            else:
                gene_value = str(gene)

            perf = entry.performance or {}
            creative_id = entry.dna.creative_id if entry.dna else ""

            value_stats[gene_value].append({
                "creative_id": creative_id,
                "roas": perf.get("roas", 0),
                "ltv": perf.get("ltv", 0),
                "ctr": perf.get("ctr", 0),
                "payer_rate": perf.get("payer_rate", 0),
                "is_winner": entry.is_winner,
                "context": context_data.get(creative_id, {}),
            })

        # 计算每个基因值的性能
        performances: list[GenePerformance] = []
        for gene_value, records in value_stats.items():
            count = len(records)
            if count < self._min_samples:
                continue

            win_count = sum(1 for r in records if r["is_winner"])
            win_rate = win_count / count
            avg_roas = sum(r["roas"] for r in records) / count
            avg_ltv = sum(r["ltv"] for r in records) / count
            avg_ctr = sum(r["ctr"] for r in records) / count
            avg_payer_rate = sum(r["payer_rate"] for r in records) / count

            # 置信度: 样本量 + 胜率
            sample_factor = min(count / 20.0, 1.0)
            confidence = sample_factor * 0.6 + win_rate * 0.4

            gp = GenePerformance(
                gene_value=gene_value,
                samples=count,
                win_count=win_count,
                win_rate=win_rate,
                avg_roas=avg_roas,
                avg_ltv=avg_ltv,
                avg_ctr=avg_ctr,
                avg_payer_rate=avg_payer_rate,
                confidence=confidence,
            )
            performances.append(gp)

        # 按 win_rate * confidence 排序
        performances.sort(key=lambda p: p.win_rate * p.confidence, reverse=True)

        # 最佳值
        best_value = ""
        best_roas = 0.0
        if performances:
            best_value = performances[0].gene_value
            best_roas = performances[0].avg_roas

        # 最佳上下文分析
        best_contexts = self._analyze_best_contexts(category, value_stats)

        total_samples = sum(p.samples for p in performances)

        return GeneIntelligence(
            gene_category=category,
            values=performances,
            best_value=best_value,
            best_roas=best_roas,
            best_contexts=best_contexts,
            total_samples=total_samples,
            diversity=len(performances),
        )

    def _analyze_best_contexts(
        self,
        category: str,
        value_stats: dict[str, list[dict[str, Any]]],
    ) -> list[ContextAffinity]:
        """分析基因值的最佳上下文.

        为每个基因值找出表现最好的上下文 (游戏/平台/市场/阶段).
        """
        context_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"samples": 0, "roas_sum": 0.0, "win_count": 0}
        )

        for records in value_stats.values():
            for r in records:
                ctx = r.get("context", {})
                if not ctx:
                    continue

                key = (
                    f"{ctx.get('game', '')}:{ctx.get('platform', '')}:"
                    f"{ctx.get('market', '')}:{ctx.get('stage', '')}"
                )
                stats = context_stats[key]
                stats["samples"] += 1
                stats["roas_sum"] += r["roas"]
                if r["is_winner"]:
                    stats["win_count"] += 1

        affinities = []
        for key, stats in context_stats.items():
            if stats["samples"] < 3:
                continue

            parts = key.split(":")
            if len(parts) != 4:
                continue

            avg_roas = stats["roas_sum"] / max(stats["samples"], 1)
            win_rate = stats["win_count"] / max(stats["samples"], 1)
            affinity_score = avg_roas * 0.5 + win_rate * 0.5

            affinities.append(ContextAffinity(
                game=parts[0],
                platform=parts[1],
                market=parts[2],
                stage=parts[3],
                samples=stats["samples"],
                avg_roas=avg_roas,
                win_rate=win_rate,
                affinity_score=affinity_score,
            ))

        affinities.sort(key=lambda a: a.affinity_score, reverse=True)
        return affinities[:5]

    def _calculate_diversity_score(
        self,
        genes: dict[str, GeneIntelligence],
    ) -> float:
        """计算整体多样性分数.

        多样性 = 各基因类别 diversity 的加权平均.
        值域 [0, 1], 越高表示基因池越丰富.
        """
        if not genes:
            return 0.0

        scores = []
        for gi in genes.values():
            if gi.total_samples > 0:
                # 多样性归一化: 用 tanh 映射到 [0, 1]
                import math
                scores.append(math.tanh(gi.diversity / 10.0))

        return sum(scores) / len(scores) if scores else 0.0

    def _generate_summary(
        self,
        genes: dict[str, GeneIntelligence],
        total_entries: int,
        winner_count: int,
    ) -> str:
        """生成分析摘要."""
        parts = [f"分析 {total_entries} 个 DNA, {winner_count} 个赢家"]

        for cat, gi in genes.items():
            if gi.best_value:
                parts.append(
                    f"{cat} 最佳={gi.best_value} "
                    f"(ROAS {gi.best_roas:.1f}, {gi.total_samples} 样本)"
                )

        return "; ".join(parts)

    # ── 快捷查询 ──────────────────────────────────────────

    def get_gene_performance(
        self,
        gene_category: str,
        gene_value: str,
        dna_entries: list[CreativeDNAMemoryEntry] | None = None,
    ) -> GenePerformance | None:
        """获取特定基因值的性能统计."""
        if dna_entries is None:
            dna_entries = self._memory.get_dna_entries_by_performance(min_roas=0.0)

        matching = []
        for entry in dna_entries:
            if not entry.dna or not entry.dna.genes:
                continue
            gene = entry.dna.genes.get(gene_category)
            if not gene:
                continue
            value = gene.value if hasattr(gene, 'value') else str(gene)
            if value == gene_value:
                perf = entry.performance or {}
                matching.append({
                    "roas": perf.get("roas", 0),
                    "ltv": perf.get("ltv", 0),
                    "ctr": perf.get("ctr", 0),
                    "payer_rate": perf.get("payer_rate", 0),
                    "is_winner": entry.is_winner,
                })

        if len(matching) < self._min_samples:
            return None

        count = len(matching)
        win_count = sum(1 for r in matching if r["is_winner"])
        return GenePerformance(
            gene_value=gene_value,
            samples=count,
            win_count=win_count,
            win_rate=win_count / count,
            avg_roas=sum(r["roas"] for r in matching) / count,
            avg_ltv=sum(r["ltv"] for r in matching) / count,
            avg_ctr=sum(r["ctr"] for r in matching) / count,
            avg_payer_rate=sum(r["payer_rate"] for r in matching) / count,
            confidence=min(count / 20.0, 1.0) * 0.6 + (win_count / count) * 0.4,
        )

    def get_rising_genes(
        self,
        recent_entries: list[CreativeDNAMemoryEntry],
        historical_entries: list[CreativeDNAMemoryEntry] | None = None,
    ) -> dict[str, list[str]]:
        """识别上升趋势的基因值.

        对比近期 vs 历史数据，找出表现提升的基因值.

        Returns:
            {gene_category: [rising_gene_values]}
        """
        historical_entries = historical_entries or []

        if not historical_entries:
            # 没有历史数据，返回近期表现好的基因
            report = self.analyze(dna_entries=recent_entries)
            rising = {}
            for cat, gi in report.genes.items():
                high_performers = [
                    v.gene_value for v in gi.values
                    if v.is_reliable and v.win_rate >= 0.5
                ]
                if high_performers:
                    rising[cat] = high_performers
            return rising

        # 对比近期 vs 历史
        recent_report = self.analyze(dna_entries=recent_entries)
        historical_report = self.analyze(dna_entries=historical_entries)

        rising = {}
        for cat in self.GENE_CATEGORIES:
            recent_gi = recent_report.get_gene(cat)
            hist_gi = historical_report.get_gene(cat)
            if not recent_gi or not hist_gi:
                continue

            hist_perf = {v.gene_value: v.win_rate for v in hist_gi.values}
            rising_values = []
            for v in recent_gi.values:
                hist_rate = hist_perf.get(v.gene_value, 0)
                if v.win_rate > hist_rate + 0.1 and v.is_reliable:
                    rising_values.append(v.gene_value)

            if rising_values:
                rising[cat] = rising_values

        return rising

    def get_declining_genes(
        self,
        recent_entries: list[CreativeDNAMemoryEntry],
        historical_entries: list[CreativeDNAMemoryEntry],
    ) -> dict[str, list[str]]:
        """识别下降趋势的基因值."""
        recent_report = self.analyze(dna_entries=recent_entries)
        historical_report = self.analyze(dna_entries=historical_entries)

        declining = {}
        for cat in self.GENE_CATEGORIES:
            recent_gi = recent_report.get_gene(cat)
            hist_gi = historical_report.get_gene(cat)
            if not recent_gi or not hist_gi:
                continue

            hist_perf = {v.gene_value: v.win_rate for v in hist_gi.values}
            declining_values = []
            for v in recent_gi.values:
                hist_rate = hist_perf.get(v.gene_value, 0.5)
                if v.win_rate < hist_rate - 0.1 and v.is_reliable:
                    declining_values.append(v.gene_value)

            if declining_values:
                declining[cat] = declining_values

        return declining

    # ── 生命周期 ──────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "min_samples": self._min_samples,
            "min_confidence": self._min_confidence,
            "gene_categories": self.GENE_CATEGORIES,
        }

    def reset(self) -> None:
        """重置状态 (无内部状态，占位)."""
        pass


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_genome_intelligence(
    memory: CreativeMemory | None = None,
    min_samples: int = 5,
    min_confidence: float = 0.3,
) -> GenomeIntelligence:
    """创建 GenomeIntelligence 实例."""
    return GenomeIntelligence(
        memory=memory,
        min_samples=min_samples,
        min_confidence=min_confidence,
    )