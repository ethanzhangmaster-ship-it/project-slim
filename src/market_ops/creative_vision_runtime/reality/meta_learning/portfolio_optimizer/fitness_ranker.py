"""E12.6.5 — Fitness Ranker。

产品适应度排名引擎 —— 计算每个产品在组合中的适应度评分。

公式:
  Product Fitness Score =
      Revenue Potential    × 0.30
    + Growth Velocity      × 0.25
    + Creative Scalability × 0.20
    + Market Opportunity   × 0.15
    + Risk                 × 0.10

其中 Risk 使用 (1 - risk_score)，风险越低越好。
"""

from __future__ import annotations

from .models import ProductFitness, ProductLifecycleStage


# 默认权重
DEFAULT_WEIGHTS = {
    "revenue_potential": 0.30,
    "growth_velocity": 0.25,
    "creative_scalability": 0.20,
    "market_opportunity": 0.15,
    "risk": 0.10,
}


class FitnessRanker:
    """产品适应度排名引擎。

    计算每个产品在组合中的适应度评分并排名。
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        """初始化适应度排名器。

        Args:
            weights: 自定义权重字典，默认使用 DEFAULT_WEIGHTS
        """
        self._weights = dict(weights or DEFAULT_WEIGHTS)
        self._validate_weights()

    def _validate_weights(self) -> None:
        """验证权重总和为 1.0。"""
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.4f}: {self._weights}"
            )

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def calculate_fitness(
        self,
        product_id: str,
        revenue_potential: float = 0.5,
        growth_velocity: float = 0.5,
        creative_scalability: float = 0.5,
        market_opportunity: float = 0.5,
        risk: float = 0.5,
        lifecycle_stage: str | ProductLifecycleStage | None = None,
        **metadata: object,
    ) -> ProductFitness:
        """计算单个产品适应度。

        Args:
            product_id:           产品 ID
            revenue_potential:    收入潜力 [0, 1]
            growth_velocity:      增长速度 [0, 1]
            creative_scalability: 创意可扩展性 [0, 1]
            market_opportunity:   市场机会 [0, 1]
            risk:                 风险评分 [0, 1]（越低越好）
            lifecycle_stage:      生命周期阶段
            **metadata:           附加元数据

        Returns:
            ProductFitness
        """
        # 风险取反：风险越低，贡献越大
        risk_score = 1.0 - risk

        total = (
            revenue_potential * self._weights["revenue_potential"]
            + growth_velocity * self._weights["growth_velocity"]
            + creative_scalability * self._weights["creative_scalability"]
            + market_opportunity * self._weights["market_opportunity"]
            + risk_score * self._weights["risk"]
        )

        # 解析生命周期阶段
        stage = self._parse_stage(lifecycle_stage)

        return ProductFitness(
            product_id=product_id,
            revenue_potential=round(revenue_potential, 4),
            growth_velocity=round(growth_velocity, 4),
            creative_scalability=round(creative_scalability, 4),
            market_opportunity=round(market_opportunity, 4),
            risk=round(risk, 4),
            total_fitness=round(total, 4),
            lifecycle_stage=stage,
            metadata=dict(metadata),
        )

    def rank(
        self,
        fitness_scores: list[ProductFitness],
    ) -> list[ProductFitness]:
        """对适应度评分排名。

        Args:
            fitness_scores: 适应度评分列表

        Returns:
            排名后的列表（按 total_fitness 降序）
        """
        sorted_scores = sorted(
            fitness_scores,
            key=lambda f: (f.total_fitness, f.risk_adjusted_fitness),
            reverse=True,
        )
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1
        return sorted_scores

    def calculate_and_rank(
        self,
        products: list[dict],
    ) -> list[ProductFitness]:
        """批量计算并排名。

        Args:
            products: 产品数据列表，每个字典包含:
                      product_id, revenue_potential, growth_velocity,
                      creative_scalability, market_opportunity, risk,
                      lifecycle_stage (可选)

        Returns:
            排名后的 ProductFitness 列表
        """
        scores = []
        for p in products:
            score = self.calculate_fitness(
                product_id=p.get("product_id", ""),
                revenue_potential=p.get("revenue_potential", 0.5),
                growth_velocity=p.get("growth_velocity", 0.5),
                creative_scalability=p.get("creative_scalability", 0.5),
                market_opportunity=p.get("market_opportunity", 0.5),
                risk=p.get("risk", 0.5),
                lifecycle_stage=p.get("lifecycle_stage"),
            )
            scores.append(score)

        return self.rank(scores)

    def _parse_stage(
        self, stage: str | ProductLifecycleStage | None
    ) -> ProductLifecycleStage:
        """解析生命周期阶段。"""
        if stage is None:
            return ProductLifecycleStage.PEAK
        if isinstance(stage, ProductLifecycleStage):
            return stage
        try:
            return ProductLifecycleStage(stage)
        except ValueError:
            return ProductLifecycleStage.PEAK

    def __repr__(self) -> str:
        w = self._weights
        return (
            f"FitnessRanker(rp={w['revenue_potential']:.2f}, "
            f"gv={w['growth_velocity']:.2f}, "
            f"cs={w['creative_scalability']:.2f}, "
            f"mo={w['market_opportunity']:.2f}, "
            f"risk={w['risk']:.2f})"
        )