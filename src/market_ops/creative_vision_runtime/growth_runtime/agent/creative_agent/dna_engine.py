"""E14.4.1 Creative DNA Engine — 创意 DNA 提取与理解.

从创意素材中提取、比较、进化 Creative DNA:

  输入: creative_id, creative_metadata, 素材分析结果
  输出: CreativeDNAProfile (7基因: hook, visual, gameplay, monetization, emotion, audience, context)

核心能力:
  - DNA 提取: 从素材元数据中构建 DNA 画像
  - DNA 比较: 两个素材的 DNA 相似度计算
  - Winner DNA: 提取赢家素材的 DNA 特征
  - DNA 指纹: 生成 DNA 哈希用于快速匹配

设计原则:
  - 与 E11 CreativeGenome 互补 (E11 负责进化，E14.4 负责理解)
  - DNA 结构兼容 E11 的 Gene 体系
  - 支持多维度相似度计算
  - 所有提取可追溯
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class HookType(str, Enum):
    """Hook 类型."""
    IMPOSSIBLE_RESULT = "impossible_result"
    BEFORE_AFTER = "before_after"
    COLLECTION = "collection"
    REWARD_REVEAL = "reward_reveal"
    PROGRESSION = "progression"
    RARE_ITEM = "rare_item"
    CURIOSITY = "curiosity"
    CHALLENGE = "challenge"
    RESCUE = "rescue"
    TRANSFORMATION = "transformation"
    STORY = "story"
    UNKNOWN = "unknown"


class VisualStyle(str, Enum):
    """视觉风格."""
    REALISTIC = "realistic"
    FANTASY = "fantasy"
    CARTOON = "cartoon"
    DARK = "dark"
    VIBRANT = "vibrant"
    MINIMAL = "minimal"
    PREMIUM = "premium"
    RETRO = "retro"
    UNKNOWN = "unknown"


class EmotionType(str, Enum):
    """情绪类型."""
    CURIOSITY = "curiosity"
    EXCITEMENT = "excitement"
    FEAR = "fear"
    SATISFACTION = "satisfaction"
    SURPRISE = "surprise"
    DESIRE = "desire"
    ACHIEVEMENT = "achievement"
    URGENCY = "urgency"
    RELAXATION = "relaxation"
    UNKNOWN = "unknown"


class GameplayFocus(str, Enum):
    """玩法焦点."""
    MERGE = "merge"
    PUZZLE = "puzzle"
    MATCH3 = "match3"
    RPG = "rpg"
    STRATEGY = "strategy"
    CASUAL = "casual"
    ACTION = "action"
    SIMULATION = "simulation"
    UNKNOWN = "unknown"


class MonetizationType(str, Enum):
    """变现类型."""
    IAP = "iap"
    IAA = "iaa"
    HYBRID = "hybrid"
    SUBSCRIPTION = "subscription"
    UNKNOWN = "unknown"


class AudienceType(str, Enum):
    """受众类型."""
    CASUAL_GAMERS = "casual_gamers"
    MIDCORE_GAMERS = "midcore_gamers"
    HARDCORE_GAMERS = "hardcore_gamers"
    WHALE_HUNTERS = "whale_hunters"
    FEMALE_25_45 = "female_25_45"
    MALE_18_35 = "male_18_35"
    BROAD = "broad"
    UNKNOWN = "unknown"


class ContextType(str, Enum):
    """投放场景."""
    WEEKEND = "weekend"
    WEEKDAY = "weekday"
    HOLIDAY = "holiday"
    EVENING = "evening"
    NEW_LAUNCH = "new_launch"
    COMPETITIVE = "competitive"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeGene:
    """单个创意基因 — 统一基因表达单元.

    兼容 E11 的 Gene 体系:
      - E11 Gene: (name, value, confidence, source) — 基础表达
      - E14.4 CreativeGene: 增加 weight 和 category 用于策略决策

    Attributes:
        name: 基因名称
        value: 基因值
        category: 基因类别 (hook/visual/gameplay/monetization/emotion/audience/context)
        confidence: 置信度 (0-1)
        weight: 权重 (0-1)
        source: 来源
        metadata: 扩展元数据
    """
    name: str = ""
    value: Any = None
    category: str = ""
    confidence: float = 0.0
    weight: float = 0.0
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "category": self.category,
            "confidence": self.confidence,
            "weight": self.weight,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeGene:
        return cls(
            name=data.get("name", ""),
            value=data.get("value"),
            category=data.get("category", ""),
            confidence=data.get("confidence", 0.0),
            weight=data.get("weight", 0.0),
            source=data.get("source", "unknown"),
            metadata=data.get("metadata", {}),
        )

    def to_e11_gene(self) -> dict[str, Any]:
        """转换为 E11 Gene 兼容格式."""
        return {
            "name": self.name,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class CreativeDNAProfile:
    """创意 DNA 画像 — 7 基因完整画像.

    7 个基因维度:
      - hook:         Hook 类型 (好奇心/前后对比/挑战/...)
      - visual:       视觉风格 (写实/幻想/暗黑/...)
      - gameplay:     玩法焦点 (合并/解谜/三消/...)
      - monetization: 变现方式 (IAP/IAA/混合/...)
      - emotion:      情绪驱动 (好奇/兴奋/恐惧/...)
      - audience:     目标受众 (休闲/中核/女性25-45/...)
      - context:      投放场景 (周末/假日/新品/...)

    Attributes:
        dna_id: DNA 唯一 ID
        creative_id: 关联创意 ID
        creative_name: 创意名称
        generation: 代数 (0=原始, 1=第一代变体)
        parent_id: 父 DNA ID
        genes: 7 基因字典
        fitness: 表现指标
        fingerprint: DNA 指纹 (用于快速相似度匹配)
        created_at: 创建时间
        metadata: 扩展元数据
    """
    dna_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    creative_name: str = ""
    generation: int = 0
    parent_id: str = ""
    genes: dict[str, CreativeGene] = field(default_factory=dict)
    fitness: dict[str, float] = field(default_factory=dict)
    fingerprint: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    # ── 基因访问 ──────────────────────────────────────────────

    def get_gene(self, category: str) -> CreativeGene | None:
        """获取指定类别的基因."""
        return self.genes.get(category)

    def get_gene_value(self, category: str) -> Any:
        """获取基因值."""
        gene = self.genes.get(category)
        return gene.value if gene else None

    def set_gene(self, category: str, gene: CreativeGene) -> None:
        """设置基因."""
        gene.category = category
        self.genes[category] = gene
        self.fingerprint = self._compute_fingerprint()

    @property
    def gene_count(self) -> int:
        return len(self.genes)

    @property
    def dominant_hook(self) -> str:
        gene = self.genes.get("hook")
        return str(gene.value) if gene else "unknown"

    @property
    def dominant_emotion(self) -> str:
        gene = self.genes.get("emotion")
        return str(gene.value) if gene else "unknown"

    @property
    def primary_audience(self) -> str:
        gene = self.genes.get("audience")
        return str(gene.value) if gene else "unknown"

    @property
    def avg_confidence(self) -> float:
        if not self.genes:
            return 0.0
        return sum(g.confidence for g in self.genes.values()) / len(self.genes)

    # ── 序列化 ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_id": self.dna_id,
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "genes": {k: v.to_dict() for k, v in self.genes.items()},
            "fitness": self.fitness,
            "fingerprint": self.fingerprint,
            "dominant_hook": self.dominant_hook,
            "dominant_emotion": self.dominant_emotion,
            "primary_audience": self.primary_audience,
            "avg_confidence": round(self.avg_confidence, 4),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeDNAProfile:
        genes_data = data.get("genes", {})
        genes = {
            k: CreativeGene.from_dict(v) if isinstance(v, dict) else v
            for k, v in genes_data.items()
        }
        return cls(
            dna_id=data.get("dna_id", ""),
            creative_id=data.get("creative_id", ""),
            creative_name=data.get("creative_name", ""),
            generation=data.get("generation", 0),
            parent_id=data.get("parent_id", ""),
            genes=genes,
            fitness=data.get("fitness", {}),
            fingerprint=data.get("fingerprint", ""),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _compute_fingerprint(self) -> str:
        """计算 DNA 指纹 — 基于基因值的 SHA256."""
        sorted_genes = sorted(self.genes.items(), key=lambda x: x[0])
        gene_str = json.dumps(
            {k: str(v.value) for k, v in sorted_genes},
            sort_keys=True,
        )
        return hashlib.sha256(gene_str.encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        parts = [f"CreativeDNAProfile(id={self.dna_id[:8]}"]
        for cat, gene in self.genes.items():
            parts.append(f"{cat}={gene.value}")
        return ", ".join(parts) + ")"


@dataclass
class DNAComparisonResult:
    """DNA 比较结果.

    Attributes:
        dna_a_id: DNA A ID
        dna_b_id: DNA B ID
        similarity_score: 总体相似度 (0-1)
        gene_similarities: 各基因相似度
        shared_genes: 共享基因数量
        total_genes: 总基因数
        differences: 差异描述
        recommendation: 推荐动作
    """
    dna_a_id: str = ""
    dna_b_id: str = ""
    similarity_score: float = 0.0
    gene_similarities: dict[str, float] = field(default_factory=dict)
    shared_genes: int = 0
    total_genes: int = 0
    differences: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_a_id": self.dna_a_id,
            "dna_b_id": self.dna_b_id,
            "similarity_score": round(self.similarity_score, 4),
            "gene_similarities": {k: round(v, 4) for k, v in self.gene_similarities.items()},
            "shared_genes": self.shared_genes,
            "total_genes": self.total_genes,
            "differences": self.differences,
            "recommendation": self.recommendation,
        }

    @property
    def is_identical(self) -> bool:
        return self.similarity_score >= 0.99

    @property
    def is_similar(self) -> bool:
        return self.similarity_score >= 0.7

    @property
    def is_different(self) -> bool:
        return self.similarity_score < 0.3


@dataclass
class WinnerDNAReport:
    """赢家 DNA 分析报告.

    Attributes:
        report_id: 报告 ID
        winner_dnas: 赢家 DNA 列表
        common_genes: 共同基因特征
        distinct_genes: 差异化基因
        average_fitness: 平均表现
        recommendation: 变异建议
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    winner_dnas: list[CreativeDNAProfile] = field(default_factory=list)
    common_genes: dict[str, Any] = field(default_factory=dict)
    distinct_genes: dict[str, list[Any]] = field(default_factory=dict)
    average_fitness: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "winner_dnas": [d.to_dict() for d in self.winner_dnas],
            "common_genes": self.common_genes,
            "distinct_genes": self.distinct_genes,
            "average_fitness": self.average_fitness,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }

    @property
    def winner_count(self) -> int:
        return len(self.winner_dnas)


# ═══════════════════════════════════════════════════════════════
# DNA Engine
# ═══════════════════════════════════════════════════════════════


class DNAEngine:
    """Creative DNA 引擎 — 提取、比较、理解创意 DNA.

    职责:
      1. 从素材元数据中提取 DNA 画像
      2. 比较两个 DNA 的相似度
      3. 提取赢家 DNA 的共同特征
      4. 生成 DNA 指纹用于快速匹配

    DNA 提取维度:
      - hook: Hook 类型 (好奇心/前后对比/挑战/救援/...)
      - visual: 视觉风格 (写实/幻想/卡通/暗黑/...)
      - gameplay: 玩法焦点 (合并/解谜/策略/...)
      - monetization: 变现方式 (IAP/IAA/混合)
      - emotion: 情绪驱动 (好奇/兴奋/恐惧/满足/...)
      - audience: 目标受众 (休闲/中核/女性25-45/...)
      - context: 投放场景 (周末/假日/新品/...)

    用法:
        engine = DNAEngine()
        dna = engine.extract_dna(
            creative_id="C102",
            hook="before_after",
            visual="fantasy",
            emotion="curiosity",
            gameplay="merge",
            monetization="iap",
            audience="casual_gamers",
            context="weekend",
        )
        comparison = engine.compare_dna(dna1, dna2)
    """

    # 基因类别权重 (用于相似度计算)
    DEFAULT_GENE_WEIGHTS = {
        "hook": 0.25,
        "visual": 0.15,
        "gameplay": 0.15,
        "monetization": 0.10,
        "emotion": 0.15,
        "audience": 0.10,
        "context": 0.10,
    }

    def __init__(self, gene_weights: dict[str, float] | None = None):
        self._gene_weights = gene_weights or dict(self.DEFAULT_GENE_WEIGHTS)
        self._extracted_dnas: dict[str, CreativeDNAProfile] = {}
        self._comparisons: list[DNAComparisonResult] = []

    @property
    def gene_weights(self) -> dict[str, float]:
        return dict(self._gene_weights)

    # ── DNA 提取 ──────────────────────────────────────────────

    def extract_dna(
        self,
        creative_id: str,
        creative_name: str = "",
        hook: str = "",
        visual: str = "",
        gameplay: str = "",
        monetization: str = "",
        emotion: str = "",
        audience: str = "",
        context: str = "",
        fitness: dict[str, float] | None = None,
        generation: int = 0,
        parent_id: str = "",
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CreativeDNAProfile:
        """从素材元数据中提取 DNA 画像.

        Args:
            creative_id: 创意 ID
            creative_name: 创意名称
            hook: Hook 类型
            visual: 视觉风格
            gameplay: 玩法焦点
            monetization: 变现方式
            emotion: 情绪驱动
            audience: 目标受众
            context: 投放场景
            fitness: 表现指标
            generation: 代数
            parent_id: 父 DNA ID
            metadata: 扩展元数据
            **kwargs: 其他基因参数

        Returns:
            CreativeDNAProfile: DNA 画像
        """
        genes = {
            "hook": CreativeGene(
                name="hook", value=hook, category="hook",
                confidence=0.8, weight=self._gene_weights.get("hook", 0.2),
                source="creative_agent",
            ),
            "visual": CreativeGene(
                name="visual", value=visual, category="visual",
                confidence=0.8, weight=self._gene_weights.get("visual", 0.15),
                source="creative_agent",
            ),
            "gameplay": CreativeGene(
                name="gameplay", value=gameplay, category="gameplay",
                confidence=0.8, weight=self._gene_weights.get("gameplay", 0.15),
                source="creative_agent",
            ),
            "monetization": CreativeGene(
                name="monetization", value=monetization, category="monetization",
                confidence=0.8, weight=self._gene_weights.get("monetization", 0.1),
                source="creative_agent",
            ),
            "emotion": CreativeGene(
                name="emotion", value=emotion, category="emotion",
                confidence=0.8, weight=self._gene_weights.get("emotion", 0.15),
                source="creative_agent",
            ),
            "audience": CreativeGene(
                name="audience", value=audience, category="audience",
                confidence=0.8, weight=self._gene_weights.get("audience", 0.1),
                source="creative_agent",
            ),
            "context": CreativeGene(
                name="context", value=context, category="context",
                confidence=0.8, weight=self._gene_weights.get("context", 0.1),
                source="creative_agent",
            ),
        }

        profile = CreativeDNAProfile(
            creative_id=creative_id,
            creative_name=creative_name,
            genes=genes,
            fitness=fitness or {},
            generation=generation,
            parent_id=parent_id,
            metadata=metadata or {},
        )

        self._extracted_dnas[profile.dna_id] = profile
        return profile

    def extract_from_dict(
        self,
        creative_id: str,
        gene_data: dict[str, Any],
        fitness: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> CreativeDNAProfile:
        """从字典数据提取 DNA.

        Args:
            creative_id: 创意 ID
            gene_data: 基因数据 {"hook": "before_after", "visual": "fantasy", ...}
            fitness: 表现指标
            **kwargs: 其他参数

        Returns:
            CreativeDNAProfile
        """
        return self.extract_dna(
            creative_id=creative_id,
            hook=gene_data.get("hook", ""),
            visual=gene_data.get("visual", ""),
            gameplay=gene_data.get("gameplay", ""),
            monetization=gene_data.get("monetization", ""),
            emotion=gene_data.get("emotion", ""),
            audience=gene_data.get("audience", ""),
            context=gene_data.get("context", ""),
            fitness=fitness,
            **kwargs,
        )

    # ── DNA 比较 ──────────────────────────────────────────────

    def compare_dna(
        self,
        dna_a: CreativeDNAProfile,
        dna_b: CreativeDNAProfile,
    ) -> DNAComparisonResult:
        """比较两个 DNA 画像.

        Args:
            dna_a: DNA A
            dna_b: DNA B

        Returns:
            DNAComparisonResult: 比较结果
        """
        gene_similarities: dict[str, float] = {}
        shared = 0
        total = 0
        differences: list[str] = []

        all_categories = set(dna_a.genes.keys()) | set(dna_b.genes.keys())

        for category in all_categories:
            gene_a = dna_a.genes.get(category)
            gene_b = dna_b.genes.get(category)

            if gene_a and gene_b:
                total += 1
                if str(gene_a.value) == str(gene_b.value):
                    gene_similarities[category] = 1.0
                    shared += 1
                else:
                    gene_similarities[category] = 0.0
                    differences.append(f"{category}: {gene_a.value} → {gene_b.value}")
            elif gene_a:
                gene_similarities[category] = 0.0
                differences.append(f"{category}: {gene_a.value} → (缺失)")
            elif gene_b:
                gene_similarities[category] = 0.0
                differences.append(f"{category}: (缺失) → {gene_b.value}")

        # 加权相似度
        if total > 0:
            weighted_score = sum(
                gene_similarities.get(cat, 0) * self._gene_weights.get(cat, 0.14)
                for cat in all_categories
            )
            # 归一化
            total_weight = sum(self._gene_weights.get(cat, 0.14) for cat in all_categories)
            similarity_score = weighted_score / total_weight if total_weight > 0 else 0.0
        else:
            similarity_score = 0.0

        # 推荐
        if similarity_score >= 0.8:
            recommendation = "DNA高度相似，建议探索不同基因组合"
        elif similarity_score >= 0.5:
            recommendation = "DNA有相似性，可在此基础上变异"
        else:
            recommendation = "DNA差异大，可探索互补基因"

        result = DNAComparisonResult(
            dna_a_id=dna_a.dna_id,
            dna_b_id=dna_b.dna_id,
            similarity_score=similarity_score,
            gene_similarities=gene_similarities,
            shared_genes=shared,
            total_genes=total,
            differences=differences,
            recommendation=recommendation,
        )

        self._comparisons.append(result)
        return result

    def compare_by_fingerprint(
        self,
        dna_a: CreativeDNAProfile,
        dna_b: CreativeDNAProfile,
    ) -> float:
        """通过指纹快速比较相似度."""
        fp_a = dna_a.fingerprint
        fp_b = dna_b.fingerprint
        if not fp_a or not fp_b:
            return 0.0
        # 简单比较指纹中相同字符数
        matches = sum(1 for a, b in zip(fp_a, fp_b) if a == b)
        return matches / max(len(fp_a), len(fp_b))

    # ── Winner DNA 分析 ───────────────────────────────────────

    def extract_winner_dna(
        self,
        winner_dnas: list[CreativeDNAProfile],
    ) -> WinnerDNAReport:
        """提取赢家 DNA 的共同特征.

        Args:
            winner_dnas: 赢家 DNA 列表

        Returns:
            WinnerDNAReport: 赢家 DNA 分析报告
        """
        if not winner_dnas:
            return WinnerDNAReport()

        # 收集所有基因值
        gene_values: dict[str, list[Any]] = {}
        for dna in winner_dnas:
            for cat, gene in dna.genes.items():
                if gene.value:
                    if cat not in gene_values:
                        gene_values[cat] = []
                    gene_values[cat].append(gene.value)

        # 找出共同基因 (出现频率最高的值)
        common_genes: dict[str, Any] = {}
        distinct_genes: dict[str, list[Any]] = {}
        for cat, values in gene_values.items():
            from collections import Counter
            counter = Counter(values)
            most_common = counter.most_common(1)
            if most_common and most_common[0][1] >= 2:
                common_genes[cat] = most_common[0][0]
            distinct_genes[cat] = list(set(values))

        # 平均表现
        avg_fitness: dict[str, float] = {}
        if winner_dnas:
            all_fitness_keys = set()
            for dna in winner_dnas:
                all_fitness_keys.update(dna.fitness.keys())
            for key in all_fitness_keys:
                values = [dna.fitness.get(key, 0) for dna in winner_dnas]
                avg_fitness[key] = sum(values) / len(values)

        # 推荐
        rec_parts = []
        if common_genes:
            rec_parts.append(f"共同基因: {', '.join(f'{k}={v}' for k, v in common_genes.items())}")
        if distinct_genes:
            variant_cats = [
                cat for cat, vals in distinct_genes.items()
                if len(vals) > 1
            ]
            if variant_cats:
                rec_parts.append(f"可变异维度: {', '.join(variant_cats)}")
        recommendation = " | ".join(rec_parts) if rec_parts else "数据不足"

        return WinnerDNAReport(
            winner_dnas=winner_dnas,
            common_genes=common_genes,
            distinct_genes=distinct_genes,
            average_fitness=avg_fitness,
            recommendation=recommendation,
        )

    # ── DNA 指纹 ──────────────────────────────────────────────

    def get_dna_fingerprint(self, dna: CreativeDNAProfile) -> str:
        """获取 DNA 指纹."""
        return dna.fingerprint

    def find_similar_dnas(
        self,
        target: CreativeDNAProfile,
        min_similarity: float = 0.5,
    ) -> list[tuple[CreativeDNAProfile, float]]:
        """查找相似的 DNA."""
        results = []
        for dna_id, dna in self._extracted_dnas.items():
            if dna_id == target.dna_id:
                continue
            sim = self.compare_by_fingerprint(target, dna)
            if sim >= min_similarity:
                results.append((dna, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def cluster_by_dna(
        self,
        dnas: list[CreativeDNAProfile],
        min_similarity: float = 0.6,
    ) -> list[list[CreativeDNAProfile]]:
        """按 DNA 相似度聚类."""
        clusters: list[list[CreativeDNAProfile]] = []
        assigned: set[str] = set()

        for dna in dnas:
            if dna.dna_id in assigned:
                continue
            cluster = [dna]
            assigned.add(dna.dna_id)
            for other in dnas:
                if other.dna_id in assigned:
                    continue
                sim = self.compare_by_fingerprint(dna, other)
                if sim >= min_similarity:
                    cluster.append(other)
                    assigned.add(other.dna_id)
            clusters.append(cluster)

        return clusters

    # ── 查询 ──────────────────────────────────────────────────

    def get_dna(self, dna_id: str) -> CreativeDNAProfile | None:
        return self._extracted_dnas.get(dna_id)

    def get_dna_by_creative(self, creative_id: str) -> CreativeDNAProfile | None:
        for dna in self._extracted_dnas.values():
            if dna.creative_id == creative_id:
                return dna
        return None

    def get_all_dnas(self) -> list[CreativeDNAProfile]:
        return list(self._extracted_dnas.values())

    def get_dna_count(self) -> int:
        return len(self._extracted_dnas)

    def get_comparisons(self, n: int = 20) -> list[DNAComparisonResult]:
        return self._comparisons[-n:]

    def reset(self) -> None:
        self._extracted_dnas.clear()
        self._comparisons.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_dna_engine() -> DNAEngine:
    """创建默认 DNA 引擎."""
    return DNAEngine()