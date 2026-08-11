"""E13.5 Pattern Retriever — 模式检索与决策增强.

核心职责:
  从 PatternStore 中检索与当前场景匹配的历史成功模式，
  为 DecisionEngine 提供经验驱动的决策建议。

功能:
  - retrieve: 多维度相似度匹配检索
  - rank_patterns: 按样本量、成功率、奖励、置信度排序
  - get_top_recommendation: 获取最佳推荐动作
  - get_avoid_recommendations: 获取应避免的动作

连接:
  PatternStore → PatternRetriever → DecisionEnhancer → DecisionEngine
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..memory.models import PatternCondition, PatternMemory, PatternQuery


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class RetrievalContext:
    """检索上下文 — 描述当前需要匹配的场景.

    这是 PatternRetriever 的输入，描述当前发生了什么，
    需要从历史中查找类似场景的成功模式。

    Attributes:
        opportunity_type: 机会类型 (e.g., "creative_fatigue", "roas_drop")
        product_category: 产品类别 (e.g., "merge", "puzzle")
        audience_segment: 受众分群 (e.g., "iOS_FB", "Android_GG")
        signal_types: 当前触发的信号 (e.g., ["roas_decay", "fatigue_high"])
        metrics_snapshot: 当前指标快照 (e.g., {"roas": 0.35, "ctr": 0.021})
        dna_genes: 涉及的DNA基因 (e.g., {"hook": "rescue", "visual": "gameplay"})
        category: 经验类别 (e.g., "creative", "ua")
        entity_type: 实体类型 (e.g., "creative", "campaign")
        action_type: 当前候选动作类型 (可选)
    """
    opportunity_type: str = ""
    product_category: str = ""
    audience_segment: str = ""
    signal_types: list[str] = field(default_factory=list)
    metrics_snapshot: dict[str, float] = field(default_factory=dict)
    dna_genes: dict[str, Any] = field(default_factory=dict)
    category: str = ""
    entity_type: str = ""
    action_type: str = ""

    def to_query(self) -> PatternQuery:
        """将检索上下文转换为 PatternQuery."""
        q = PatternQuery(
            sort_by="score",
            sort_desc=True,
            actionable_only=False,  # 不过滤，让 _rank_patterns 中分类
            min_samples=3,
            limit=50,
        )
        if self.opportunity_type:
            q.opportunity_types = [self.opportunity_type]
        # 不设置 action_types 过滤，让 _rank_patterns 通过相似度分类
        # 这样能检索到同一机会类型下的所有模式（包括应避免的）
        if self.category:
            q.categories = [self.category]
        if self.audience_segment:
            q.audience_segment = self.audience_segment
        if self.signal_types:
            q.signal_types = self.signal_types
        if self.dna_genes:
            q.dna_genes = self.dna_genes
        return q

    @classmethod
    def from_opportunity(cls, opportunity: Any) -> RetrievalContext:
        """从 GrowthOpportunity 构建检索上下文."""
        ctx = cls()
        if hasattr(opportunity, "action"):
            ctx.opportunity_type = opportunity.action.value if hasattr(opportunity.action, "value") else str(opportunity.action)
        if hasattr(opportunity, "product_id"):
            ctx.product_category = opportunity.product_id
        if hasattr(opportunity, "source_insight") and opportunity.source_insight:
            insight = opportunity.source_insight
            if hasattr(insight, "insight_type"):
                ctx.opportunity_type = insight.insight_type.value if hasattr(insight.insight_type, "value") else str(insight.insight_type)
            if hasattr(insight, "metrics"):
                ctx.metrics_snapshot = dict(insight.metrics)
        return ctx

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_type": self.opportunity_type,
            "product_category": self.product_category,
            "audience_segment": self.audience_segment,
            "signal_types": self.signal_types,
            "metrics_snapshot": self.metrics_snapshot,
            "dna_genes": self.dna_genes,
            "category": self.category,
            "entity_type": self.entity_type,
            "action_type": self.action_type,
        }


@dataclass
class PatternRecommendation:
    """模式推荐 — 单个检索匹配结果.

    Attributes:
        pattern: 匹配到的增长模式
        similarity_score: 相似度分数 [0, 1]
        rank: 排名 (1-based)
        recommendation_type: 推荐类型 (strong_recommend, recommend, suggest, caution)
        reasoning: 人类可读的推荐理由
        confidence: 推荐置信度 [0, 1]
    """
    pattern: PatternMemory
    similarity_score: float = 0.0
    rank: int = 0
    recommendation_type: str = "suggest"
    reasoning: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern.pattern_id,
            "action_type": self.pattern.action.action_type,
            "similarity_score": round(self.similarity_score, 4),
            "rank": self.rank,
            "recommendation_type": self.recommendation_type,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "performance": {
                "samples": self.pattern.performance.samples,
                "success_rate": round(self.pattern.performance.success_rate, 4),
                "avg_reward": round(self.pattern.performance.avg_reward, 4),
                "quality": self.pattern.performance.quality.value,
            },
        }

    @property
    def is_actionable(self) -> bool:
        return self.recommendation_type in ("strong_recommend", "recommend")


@dataclass
class RetrievalResult:
    """检索结果 — PatternRetriever 的完整输出.

    Attributes:
        recommendations: 排序后的推荐列表
        top_action: 最佳推荐动作
        avoid_actions: 应避免的动作列表
        retrieval_summary: 检索摘要
        total_matched: 总匹配数
        context: 查询上下文
    """
    recommendations: list[PatternRecommendation] = field(default_factory=list)
    top_action: PatternRecommendation | None = None
    avoid_actions: list[PatternRecommendation] = field(default_factory=list)
    retrieval_summary: str = ""
    total_matched: int = 0
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_matched": self.total_matched,
            "top_action": self.top_action.to_dict() if self.top_action else None,
            "recommendations": [r.to_dict() for r in self.recommendations[:5]],
            "avoid_actions": [a.to_dict() for a in self.avoid_actions[:5]],
            "retrieval_summary": self.retrieval_summary,
            "context": self.context,
        }

    @property
    def has_recommendations(self) -> bool:
        return len(self.recommendations) > 0

    @property
    def has_avoid_actions(self) -> bool:
        return len(self.avoid_actions) > 0


# ═══════════════════════════════════════════════════════════════
# Pattern Retriever
# ═══════════════════════════════════════════════════════════════


class PatternRetriever:
    """模式检索器 — 从 PatternStore 中查找与当前场景匹配的历史成功模式.

    核心流程:
      1. 构建 PatternQuery 从 PatternStore 中检索候选模式
      2. 对每个候选模式计算多维度相似度
      3. 按综合评分排序 (similarity × sample_factor × success_rate × reward)
      4. 生成推荐和应避免的行动建议

    用法:
        store = PatternStore()
        retriever = PatternRetriever(store)
        result = retriever.retrieve(RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            metrics_snapshot={"roas": 0.32, "ctr": 0.021},
        ))
        if result.top_action:
            print(f"推荐: {result.top_action.pattern.action.action_type}")
    """

    # ── 相似度权重配置 ────────────────────────────────────────

    # 各维度的相似度权重
    DIMENSION_WEIGHTS = {
        "opportunity_type": 0.25,   # 机会类型匹配最重要
        "action_type": 0.10,        # 动作类型匹配
        "audience_segment": 0.15,   # 受众匹配 (平台/渠道)
        "signal_types": 0.15,       # 信号类型匹配
        "product_category": 0.10,   # 产品类别匹配
        "dna_genes": 0.10,          # DNA基因匹配
        "category": 0.05,           # 经验类别匹配
        "metrics_similarity": 0.10,  # 指标相似度
    }

    # ── 推荐阈值 ──────────────────────────────────────────────

    STRONG_RECOMMEND_THRESHOLD = 0.55    # 综合评分 >= 此值 → strong_recommend
    RECOMMEND_THRESHOLD = 0.30           # 综合评分 >= 此值 → recommend
    SUGGEST_THRESHOLD = 0.12             # 综合评分 >= 此值 → suggest
    AVOID_SUCCESS_RATE_THRESHOLD = 0.30  # 成功率 <= 此值 → caution

    # ── 默认参数 ──────────────────────────────────────────────

    DEFAULT_MIN_SIMILARITY = 0.15        # 最低相似度，低于此值过滤
    DEFAULT_MAX_RECOMMENDATIONS = 10     # 最多返回推荐数
    DEFAULT_MIN_SAMPLES = 3              # 最低样本数

    def __init__(
        self,
        pattern_store: Any,
        dimension_weights: dict[str, float] | None = None,
        min_similarity: float = 0.15,
        max_recommendations: int = 10,
        min_samples: int = 3,
    ):
        """初始化模式检索器.

        Args:
            pattern_store: PatternStore 实例
            dimension_weights: 自定义维度权重
            min_similarity: 最低相似度阈值
            max_recommendations: 最多返回推荐数
            min_samples: 最低样本数
        """
        self._store = pattern_store
        self._weights = {**self.DIMENSION_WEIGHTS, **(dimension_weights or {})}
        self._min_similarity = min_similarity
        self._max_recommendations = max_recommendations
        self._min_samples = min_samples

    # ═══════════════════════════════════════════════════════════
    # Main API
    # ═══════════════════════════════════════════════════════════

    def retrieve(self, context: RetrievalContext) -> RetrievalResult:
        """检索与当前场景匹配的历史成功模式.

        Args:
            context: 检索上下文 (描述当前场景)

        Returns:
            RetrievalResult: 包含推荐和应避免动作的完整结果
        """
        # Step 1: 从 PatternStore 查询候选模式
        query = context.to_query()
        candidates = self._store.query(query)

        if not candidates:
            return RetrievalResult(
                recommendations=[],
                top_action=None,
                avoid_actions=[],
                retrieval_summary="No matching patterns found in history.",
                total_matched=0,
                context=context.to_dict(),
            )

        # Step 2: 计算相似度并排序
        recommendations = self._rank_patterns(candidates, context)

        # Step 3: 分离推荐和避免
        top_actions = [r for r in recommendations if r.is_actionable]
        avoid_actions = [r for r in recommendations if r.recommendation_type == "caution"]

        # Step 4: 生成摘要
        top_action = top_actions[0] if top_actions else None
        summary = self._generate_summary(recommendations, top_action, avoid_actions, context)

        return RetrievalResult(
            recommendations=recommendations[:self._max_recommendations],
            top_action=top_action,
            avoid_actions=avoid_actions,
            retrieval_summary=summary,
            total_matched=len(candidates),
            context=context.to_dict(),
        )

    def get_top_recommendation(self, context: RetrievalContext) -> PatternRecommendation | None:
        """快捷方法: 获取最佳推荐."""
        result = self.retrieve(context)
        return result.top_action

    def get_avoid_recommendations(self, context: RetrievalContext) -> list[PatternRecommendation]:
        """快捷方法: 获取应避免的动作."""
        result = self.retrieve(context)
        return result.avoid_actions

    # ═══════════════════════════════════════════════════════════
    # Similarity Computation
    # ═══════════════════════════════════════════════════════════

    def _compute_similarity(
        self,
        pattern: PatternMemory,
        context: RetrievalContext,
    ) -> float:
        """计算模式与上下文的多维度相似度.

        加权公式:
          similarity = Σ(weight_i × match_score_i)

        各维度:
          - opportunity_type: 精确匹配=1.0, 否则0
          - action_type: 精确匹配=1.0, 否则0
          - audience_segment: 精确匹配=1.0, 部分匹配=0.5, 否则0
          - signal_types: Jaccard 相似度
          - product_category: 精确匹配=1.0, 否则0
          - dna_genes: key匹配比例
          - category: 精确匹配=1.0, 否则0
          - metrics_similarity: 基于指标距离的相似度
        """
        condition = pattern.condition
        weights = self._weights
        total = 0.0

        # 1. opportunity_type
        if context.opportunity_type and condition.opportunity_type:
            if condition.opportunity_type == context.opportunity_type:
                total += weights["opportunity_type"]

        # 2. action_type
        if context.action_type and condition.action_type:
            if condition.action_type == context.action_type:
                total += weights["action_type"]

        # 3. audience_segment
        if context.audience_segment and condition.audience_segment:
            audience_score = self._audience_similarity(
                condition.audience_segment,
                context.audience_segment,
            )
            total += weights["audience_segment"] * audience_score

        # 4. signal_types (Jaccard)
        if context.signal_types and condition.signal_types:
            jaccard = self._jaccard_similarity(
                set(context.signal_types),
                set(condition.signal_types),
            )
            total += weights["signal_types"] * jaccard

        # 5. product_category
        if context.product_category and condition.product_category:
            if condition.product_category == context.product_category:
                total += weights["product_category"]

        # 6. dna_genes
        if context.dna_genes and condition.dna_genes:
            gene_score = self._dna_similarity(context.dna_genes, condition.dna_genes)
            total += weights["dna_genes"] * gene_score

        # 7. category
        if context.category and condition.category:
            if condition.category == context.category:
                total += weights["category"]

        # 8. metrics_similarity (基于指标快照)
        if context.metrics_snapshot and condition.market_conditions:
            metric_score = self._metrics_similarity(
                context.metrics_snapshot,
                condition.market_conditions,
            )
            total += weights["metrics_similarity"] * metric_score

        return round(total, 4)

    @staticmethod
    def _audience_similarity(audience_a: str, audience_b: str) -> float:
        """计算受众相似度.

        支持部分匹配: "iOS_FB" vs "iOS_FB" → 1.0
                      "iOS_FB" vs "iOS_GG" → 0.5 (同一平台)
                      "iOS_FB" vs "Android_GG" → 0.0
        """
        if audience_a == audience_b:
            return 1.0
        # 检查平台前缀匹配
        parts_a = audience_a.split("_")
        parts_b = audience_b.split("_")
        if parts_a and parts_b and parts_a[0] == parts_b[0]:
            return 0.5
        return 0.0

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """计算 Jaccard 相似度."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _dna_similarity(dna_a: dict[str, Any], dna_b: dict[str, Any]) -> float:
        """计算 DNA 基因相似度 (key 匹配比例)."""
        if not dna_a or not dna_b:
            return 0.0
        keys_a = set(dna_a.keys())
        keys_b = set(dna_b.keys())
        common = keys_a & keys_b
        if not common:
            return 0.0
        # 检查共同 key 的值是否匹配
        matches = sum(1 for k in common if dna_a.get(k) == dna_b.get(k))
        return matches / len(common)

    @staticmethod
    def _metrics_similarity(
        snapshot: dict[str, float],
        market_conditions: dict[str, tuple[float, float]],
    ) -> float:
        """计算指标相似度.

        基于指标快照是否落在模式的市场条件范围内。
        每个指标对: 如果 snapshot 值在 [min, max] 范围内，得分 1.0;
        否则按距离衰减。

        Args:
            snapshot: 当前指标快照 {"roas": 0.35, "ctr": 0.021}
            market_conditions: 模式市场条件 {"roas": (0.3, 0.5), "ctr": (0.015, 0.025)}

        Returns:
            float: 指标相似度 [0, 1]
        """
        if not snapshot or not market_conditions:
            return 0.0

        scores: list[float] = []
        for metric, current_value in snapshot.items():
            if metric not in market_conditions:
                continue
            low, high = market_conditions[metric]
            if low <= current_value <= high:
                scores.append(1.0)
            else:
                # 距离衰减: 距离越远分数越低
                mid = (low + high) / 2
                range_half = (high - low) / 2
                if range_half == 0:
                    scores.append(0.0)
                else:
                    distance = abs(current_value - mid) / range_half
                    scores.append(max(0.0, 1.0 - distance * 0.5))

        return sum(scores) / len(scores) if scores else 0.0

    # ═══════════════════════════════════════════════════════════
    # Ranking
    # ═══════════════════════════════════════════════════════════

    def _rank_patterns(
        self,
        patterns: list[PatternMemory],
        context: RetrievalContext,
    ) -> list[PatternRecommendation]:
        """对候选模式进行相似度评分和排序.

        综合评分 = similarity × sample_factor × success_rate × (0.5 + 0.5 × avg_reward)

        其中 sample_factor 使用对数平滑避免大样本过度主导。
        """
        recommendations: list[PatternRecommendation] = []

        for pattern in patterns:
            # 计算相似度
            similarity = self._compute_similarity(pattern, context)

            # 过滤低相似度
            if similarity < self._min_similarity:
                continue

            # 样本因子
            samples = pattern.performance.samples
            sample_factor = min(1.0, math.log(samples + 1) / math.log(50))

            # 综合评分
            composite_score = (
                similarity
                * sample_factor
                * pattern.performance.success_rate
                * (0.5 + 0.5 * max(pattern.performance.avg_reward, 0.01))
            )

            # 推荐类型
            recommendation_type = self._classify_recommendation(
                composite_score,
                pattern.performance.success_rate,
            )

            # 置信度
            confidence = round(
                similarity * sample_factor * pattern.performance.success_rate,
                4,
            )

            # 推理理由
            reasoning = self._build_reasoning(pattern, similarity, context)

            recommendations.append(PatternRecommendation(
                pattern=pattern,
                similarity_score=round(similarity, 4),
                rank=0,
                recommendation_type=recommendation_type,
                reasoning=reasoning,
                confidence=confidence,
            ))

        # 按综合评分排序
        recommendations.sort(
            key=lambda r: (
                -1 if r.is_actionable else 0,
                r.confidence * r.pattern.performance.success_rate * r.pattern.performance.avg_reward,
            ),
            reverse=True,
        )

        # 分配排名
        for i, rec in enumerate(recommendations):
            rec.rank = i + 1

        return recommendations

    def _classify_recommendation(
        self,
        composite_score: float,
        success_rate: float,
    ) -> str:
        """根据综合评分和成功率分类推荐类型."""
        if success_rate <= self.AVOID_SUCCESS_RATE_THRESHOLD:
            return "caution"
        if composite_score >= self.STRONG_RECOMMEND_THRESHOLD:
            return "strong_recommend"
        if composite_score >= self.RECOMMEND_THRESHOLD:
            return "recommend"
        if composite_score >= self.SUGGEST_THRESHOLD:
            return "suggest"
        return "caution"

    def _build_reasoning(
        self,
        pattern: PatternMemory,
        similarity: float,
        context: RetrievalContext,
    ) -> list[str]:
        """构建人类可读的推荐理由."""
        reasons: list[str] = []
        perf = pattern.performance
        condition = pattern.condition

        # 样本量
        reasons.append(f"{perf.samples} similar cases in history")

        # 成功率
        reasons.append(f"{perf.success_rate * 100:.0f}% success rate")

        # 平均奖励
        if perf.avg_reward > 0:
            reasons.append(f"avg reward {perf.avg_reward:.2f}")

        # 匹配维度说明
        matched_dims: list[str] = []
        if context.opportunity_type and condition.opportunity_type == context.opportunity_type:
            matched_dims.append("same opportunity type")
        if context.audience_segment and condition.audience_segment == context.audience_segment:
            matched_dims.append("same audience")
        if context.signal_types and set(context.signal_types) & set(condition.signal_types):
            matched_dims.append("matching signals")
        if matched_dims:
            reasons.append("matched: " + ", ".join(matched_dims))

        # 相似度
        reasons.append(f"similarity {similarity:.2f}")

        return reasons

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════

    def _generate_summary(
        self,
        recommendations: list[PatternRecommendation],
        top_action: PatternRecommendation | None,
        avoid_actions: list[PatternRecommendation],
        context: RetrievalContext,
    ) -> str:
        """生成检索摘要."""
        parts: list[str] = []

        total = len(recommendations)
        if total == 0:
            return "No matching patterns found in history."

        parts.append(f"Found {total} matching patterns.")

        if top_action:
            parts.append(
                f"Best action: {top_action.pattern.action.action_type} "
                f"(confidence: {top_action.confidence:.2f}, "
                f"success rate: {top_action.pattern.performance.success_rate * 100:.0f}%)"
            )

        if avoid_actions:
            avoid_names = [a.pattern.action.action_type for a in avoid_actions[:3]]
            parts.append(f"Avoid: {', '.join(avoid_names)}")

        return " | ".join(parts)