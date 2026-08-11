"""E14.4.4.2 Pattern Miner — 创意模式挖掘引擎.

从历史赢家素材中挖掘高频 DNA 组合模式:

  输入: 历史 winner DNA 列表
  输出: CreativePattern (DNA 组合模式 + 成功率 + 置信度)

核心能力:
  - 单基因模式: 某个基因值的成功率 (e.g. transformation_hook → 72%)
  - 多基因模式: 两个基因组合的成功率 (e.g. transformation_hook + surprise_emotion → 85%)
  - 模式排序: 按成功率×置信度×样本量排序

设计原则:
  - 确定性、可解释 — 所有模式基于频次统计
  - 样本量过滤 — 避免小样本过拟合
  - 模式可追溯 — 每个模式记录来源证据
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..memory import CreativeMemory, CreativeDNAMemoryEntry


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class PatternCategory(str, Enum):
    """模式类别."""
    SINGLE_GENE = "single_gene"       # 单基因模式
    GENE_PAIR = "gene_pair"           # 双基因组合
    GENE_TRIPLE = "gene_triple"       # 三基因组合
    FULL_DNA = "full_dna"             # 完整 DNA 模式


class PatternConfidence(str, Enum):
    """模式置信度等级."""
    HIGH = "high"          # 样本 >= 20, 成功率 >= 70%
    MEDIUM = "medium"      # 样本 >= 10, 成功率 >= 50%
    LOW = "low"            # 样本 >= 5
    INSUFFICIENT = "insufficient"  # 样本不足


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class DNAPattern:
    """DNA 模式 — 基因组合 + 表现.

    Attributes:
        pattern_id: 模式 ID
        genes: 基因字典 {category: value}
        pattern_category: 模式类别
        occurrence_count: 出现次数
        success_count: 成功次数
        success_rate: 成功率
        avg_roas: 平均 ROAS
        avg_ltv: 平均 LTV
        confidence: 置信度等级
        confidence_score: 置信度分数 [0-1]
        evidence: 来源证据 (creative IDs)
        mined_at: 挖掘时间
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    genes: dict[str, str] = field(default_factory=dict)
    pattern_category: PatternCategory = PatternCategory.SINGLE_GENE
    occurrence_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_roas: float = 0.0
    avg_ltv: float = 0.0
    confidence: PatternConfidence = PatternConfidence.INSUFFICIENT
    confidence_score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    mined_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_reliable(self) -> bool:
        return self.confidence in (PatternConfidence.HIGH, PatternConfidence.MEDIUM)

    @property
    def gene_key(self) -> str:
        """生成基因键 (用于去重)."""
        pairs = sorted(self.genes.items())
        return "|".join(f"{k}={v}" for k, v in pairs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "genes": self.genes,
            "pattern_category": self.pattern_category.value,
            "occurrence_count": self.occurrence_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_roas": round(self.avg_roas, 4),
            "avg_ltv": round(self.avg_ltv, 4),
            "confidence": self.confidence.value,
            "confidence_score": round(self.confidence_score, 4),
            "evidence": self.evidence,
            "is_reliable": self.is_reliable,
            "mined_at": self.mined_at,
        }


@dataclass
class CreativePattern:
    """创意模式 — 高级模式 (包含 DNA 组合 + 策略建议).

    Attributes:
        pattern_id: 模式 ID
        dna_patterns: DNA 子模式列表
        aggregated_success_rate: 聚合成功率
        recommendation: 策略建议
        expected_impact: 预期影响
        confidence: 综合置信度
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dna_patterns: list[DNAPattern] = field(default_factory=list)
    aggregated_success_rate: float = 0.0
    recommendation: str = ""
    expected_impact: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "dna_patterns": [p.to_dict() for p in self.dna_patterns],
            "aggregated_success_rate": round(self.aggregated_success_rate, 4),
            "recommendation": self.recommendation,
            "expected_impact": self.expected_impact,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class MiningReport:
    """挖掘报告.

    Attributes:
        report_id: 报告 ID
        total_patterns: 总模式数
        reliable_patterns: 可靠模式数
        patterns: 所有模式
        top_patterns: Top 模式 (按成功率)
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_patterns: int = 0
    reliable_patterns: int = 0
    patterns: list[DNAPattern] = field(default_factory=list)
    top_patterns: list[DNAPattern] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_patterns": self.total_patterns,
            "reliable_patterns": self.reliable_patterns,
            "patterns": [p.to_dict() for p in self.patterns],
            "top_patterns": [p.to_dict() for p in self.top_patterns],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Pattern Miner
# ═══════════════════════════════════════════════════════════════


class PatternMiner:
    """创意模式挖掘 — 从历史赢家中挖掘 DNA 模式.

    职责:
      1. 从 winner DNA 中挖掘单基因/多基因组合模式
      2. 计算每个模式的成功率和置信度
      3. 排序并推荐最高价值模式

    用法:
        miner = PatternMiner(memory)
        patterns = miner.mine_single_gene()  # 单基因模式
        patterns = miner.mine_gene_pairs()   # 双基因组合模式
        report = miner.mine_all()            # 全量挖掘
    """

    def __init__(
        self,
        memory: CreativeMemory | None = None,
        min_occurrence: int = 5,
        min_success_rate: float = 0.5,
        roas_winner_threshold: float = 1.5,
    ):
        self._memory = memory or CreativeMemory()
        self._min_occurrence = min_occurrence
        self._min_success_rate = min_success_rate
        self._roas_winner_threshold = roas_winner_threshold

    # ── 单基因模式挖掘 ────────────────────────────────────────

    def mine_single_gene(
        self,
        gene_category: str | None = None,
    ) -> list[DNAPattern]:
        """挖掘单基因模式.

        从所有 winner DNA 中提取每个基因值的成功率.

        Args:
            gene_category: 基因类别过滤 (None = 全部)

        Returns:
            list[DNAPattern]: 单基因模式列表
        """
        # 从 memory 中获取所有 DNA 条目 (不只是 winner)
        all_entries = self._memory.get_dna_entries_by_performance(min_roas=0.0)

        # 按 gene_category × gene_value 聚合
        stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in all_entries:
            if not entry.dna:
                continue
            perf = entry.performance
            for category, gene in entry.dna.genes.items():
                if gene_category and category != gene_category:
                    continue
                gene_value = gene.value if hasattr(gene, 'value') else str(gene)
                key = f"{category}:{gene_value}"
                stats[key].append({
                    "creative_id": entry.dna.creative_id,
                    "roas": perf.get("roas", 0),
                    "ltv": perf.get("ltv", 0),
                })

        patterns = []
        for key, entries in stats.items():
            category, gene_value = key.split(":", 1)
            count = len(entries)
            if count < self._min_occurrence:
                continue

            avg_roas = sum(e["roas"] for e in entries) / count
            avg_ltv = sum(e["ltv"] for e in entries) / count
            success_count = sum(1 for e in entries if e["roas"] >= self._roas_winner_threshold)
            success_rate = success_count / count

            # 计算置信度
            confidence_score = min(count / 20.0, 1.0) * 0.6 + success_rate * 0.4
            if count >= 20 and success_rate >= 0.7:
                confidence = PatternConfidence.HIGH
            elif count >= 10 and success_rate >= 0.5:
                confidence = PatternConfidence.MEDIUM
            elif count >= 5:
                confidence = PatternConfidence.LOW
            else:
                confidence = PatternConfidence.INSUFFICIENT

            patterns.append(DNAPattern(
                genes={category: gene_value},
                pattern_category=PatternCategory.SINGLE_GENE,
                occurrence_count=count,
                success_count=success_count,
                success_rate=success_rate,
                avg_roas=avg_roas,
                avg_ltv=avg_ltv,
                confidence=confidence,
                confidence_score=confidence_score,
                evidence=[e["creative_id"] for e in entries],
            ))

        # 按 success_rate × confidence_score 排序
        patterns.sort(key=lambda p: p.success_rate * p.confidence_score, reverse=True)
        return patterns

    # ── 双基因组合模式挖掘 ────────────────────────────────────

    def mine_gene_pairs(self) -> list[DNAPattern]:
        """挖掘双基因组合模式.

        从 winner DNA 中提取两个基因组合的成功率.

        Returns:
            list[DNAPattern]: 双基因组合模式列表
        """
        all_entries = self._memory.get_dna_entries_by_performance(min_roas=0.0)

        # 按基因组合聚合
        pair_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in all_entries:
            if not entry.dna or len(entry.dna.genes) < 2:
                continue
            perf = entry.performance
            gene_items = sorted(
                [(c, g.value if hasattr(g, 'value') else str(g))
                 for c, g in entry.dna.genes.items()]
            )
            # 生成所有两两组合
            for i in range(len(gene_items)):
                for j in range(i + 1, len(gene_items)):
                    key = f"{gene_items[i][0]}={gene_items[i][1]}|{gene_items[j][0]}={gene_items[j][1]}"
                    pair_stats[key].append({
                        "creative_id": entry.dna.creative_id,
                        "roas": perf.get("roas", 0),
                        "ltv": perf.get("ltv", 0),
                    })

        patterns = []
        for key, entries in pair_stats.items():
            count = len(entries)
            if count < self._min_occurrence:
                continue

            avg_roas = sum(e["roas"] for e in entries) / count
            avg_ltv = sum(e["ltv"] for e in entries) / count
            success_count = sum(1 for e in entries if e["roas"] >= self._roas_winner_threshold)
            success_rate = success_count / count

            # 解析键
            genes = {}
            for pair in key.split("|"):
                cat, val = pair.split("=", 1)
                genes[cat] = val

            confidence_score = min(count / 15.0, 1.0) * 0.6 + success_rate * 0.4
            if count >= 15 and success_rate >= 0.7:
                confidence = PatternConfidence.HIGH
            elif count >= 8 and success_rate >= 0.5:
                confidence = PatternConfidence.MEDIUM
            elif count >= 5:
                confidence = PatternConfidence.LOW
            else:
                confidence = PatternConfidence.INSUFFICIENT

            patterns.append(DNAPattern(
                genes=genes,
                pattern_category=PatternCategory.GENE_PAIR,
                occurrence_count=count,
                success_count=success_count,
                success_rate=success_rate,
                avg_roas=avg_roas,
                avg_ltv=avg_ltv,
                confidence=confidence,
                confidence_score=confidence_score,
                evidence=[e["creative_id"] for e in entries],
            ))

        patterns.sort(key=lambda p: p.success_rate * p.confidence_score, reverse=True)
        return patterns

    # ── 全量挖掘 ──────────────────────────────────────────────

    def mine_all(self) -> MiningReport:
        """执行全量模式挖掘.

        Returns:
            MiningReport: 挖掘报告
        """
        single_patterns = self.mine_single_gene()
        pair_patterns = self.mine_gene_pairs()
        all_patterns = single_patterns + pair_patterns

        reliable = [p for p in all_patterns if p.is_reliable]
        top = sorted(all_patterns, key=lambda p: p.success_rate * p.confidence_score, reverse=True)[:20]

        # 生成摘要
        if reliable:
            best = reliable[0]
            best_genes = ", ".join(f"{k}={v}" for k, v in best.genes.items())
            summary = (
                f"挖掘到 {len(all_patterns)} 个模式，{len(reliable)} 个可靠。"
                f"最佳模式: {best_genes} (成功率 {best.success_rate:.0%}, "
                f"样本 {best.occurrence_count})"
            )
        else:
            summary = f"挖掘到 {len(all_patterns)} 个模式，但无可靠模式 (样本不足)"

        return MiningReport(
            total_patterns=len(all_patterns),
            reliable_patterns=len(reliable),
            patterns=all_patterns,
            top_patterns=top,
            summary=summary,
        )

    def get_reliable_patterns(self) -> list[DNAPattern]:
        """获取所有可靠模式."""
        return [p for p in self.mine_all().patterns if p.is_reliable]

    def get_top_patterns(self, top_n: int = 10) -> list[DNAPattern]:
        """获取 Top N 模式."""
        all_patterns = self.mine_all().patterns
        return sorted(
            all_patterns,
            key=lambda p: p.success_rate * p.confidence_score,
            reverse=True,
        )[:top_n]

    def stats(self) -> dict[str, Any]:
        return {
            "min_occurrence": self._min_occurrence,
            "min_success_rate": self._min_success_rate,
            "roas_winner_threshold": self._roas_winner_threshold,
        }

    def reset(self) -> None:
        """PatternMiner 无状态，无需重置."""
        pass


def create_pattern_miner(
    memory: CreativeMemory | None = None,
    min_occurrence: int = 5,
    min_success_rate: float = 0.5,
    roas_winner_threshold: float = 1.5,
) -> PatternMiner:
    """创建默认 PatternMiner."""
    return PatternMiner(
        memory=memory,
        min_occurrence=min_occurrence,
        min_success_rate=min_success_rate,
        roas_winner_threshold=roas_winner_threshold,
    )