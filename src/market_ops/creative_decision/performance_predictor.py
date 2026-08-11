"""Module 1: Performance Prediction

基于 V4.2 Ranking 结果 + 历史 Facebook 数据，预测每个 Variant 的投放表现潜力。

预测指标：
- CTR (Click-Through Rate)
- CVR (Conversion Rate)  
- IPM (Installs Per Mille)
- CPP (Cost Per Purchase)
- CPI (Cost Per Install)
- D1 ROAS
- D7 ROAS
- D30 ROAS

输出：Performance Potential Score (0-100)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerformancePrediction:
    variant_id: str
    ctr_potential: float = 0.0       # 0-100
    cvr_potential: float = 0.0
    ipm_potential: float = 0.0
    cpp_potential: float = 0.0       # lower is better, but we score 0-100
    cpi_potential: float = 0.0
    d1_roas_potential: float = 0.0
    d7_roas_potential: float = 0.0
    d30_roas_potential: float = 0.0
    overall_performance: float = 0.0  # weighted average
    breakdown: dict = field(default_factory=dict)


class PerformancePredictor:
    """基于规则和历史的性能预测器
    
    逻辑：
    - Hook Score 高 → CTR 预测高
    - Brand Consistency 高 → CVR 预测高
    - Gameplay Consistency 高 → IPM 预测高
    - AI Risk 低 → 质量稳定 → 各项预测更可靠
    - Winning Similarity 高 → 历史数据可迁移 → 预测更准
    
    权重：
    - CTR:  Hook(40%) + Readability(30%) + Novelty(20%) + Similarity(10%)
    - CVR:  Brand(35%) + Gameplay(30%) + Hook(20%) + Similarity(15%)
    - IPM:  Gameplay(40%) + Hook(30%) + Brand(20%) + Readability(10%)
    - ROAS: Winning Similarity(30%) + Brand(25%) + Gameplay(25%) + Hook(20%)
    """

    # 性能预测权重
    CTR_WEIGHTS = {
        "facebook_hook": 0.40,
        "visual_readability": 0.30,
        "novelty": 0.20,
        "winning_similarity": 0.10,
    }
    CVR_WEIGHTS = {
        "brand_consistency": 0.35,
        "gameplay_consistency": 0.30,
        "facebook_hook": 0.20,
        "winning_similarity": 0.15,
    }
    IPM_WEIGHTS = {
        "gameplay_consistency": 0.40,
        "facebook_hook": 0.30,
        "brand_consistency": 0.20,
        "visual_readability": 0.10,
    }
    ROAS_WEIGHTS = {
        "winning_similarity": 0.30,
        "brand_consistency": 0.25,
        "gameplay_consistency": 0.25,
        "facebook_hook": 0.20,
    }

    # 总体性能各指标权重
    OVERALL_WEIGHTS = {
        "ctr": 0.20,
        "cvr": 0.20,
        "ipm": 0.15,
        "cpp": 0.10,
        "cpi": 0.10,
        "d1_roas": 0.10,
        "d7_roas": 0.10,
        "d30_roas": 0.05,
    }

    # AI Risk 对预测的可靠性折扣（AI Risk 越高，预测置信度越低）
    AI_RISK_DISCOUNT_FACTOR = 0.30

    def predict(self, variant_ranking: dict, history: dict | None = None) -> PerformancePrediction:
        """预测单个 variant 的表现
        
        Args:
            variant_ranking: V4.2 ranking.json 中的单个 variant 条目
            history: facebook_history 数据（可选）
        """
        variant_id = variant_ranking.get("variant_id", "unknown")
        dimensions = variant_ranking.get("dimensions", {})

        # 提取各维度分数（带安全默认值）
        dim_scores = self._extract_dimension_scores(dimensions)

        # 计算 CTR 潜力
        ctr = self._weighted_score(dim_scores, self.CTR_WEIGHTS)

        # 计算 CVR 潜力
        cvr = self._weighted_score(dim_scores, self.CVR_WEIGHTS)

        # 计算 IPM 潜力
        ipm = self._weighted_score(dim_scores, self.IPM_WEIGHTS)

        # 计算 CPP / CPI 潜力（成本类：质量越高 → 成本越低 → 分数越高）
        # 基础分由 Brand + Gameplay + Hook 决定，再用 AI Risk 修正
        cost_base = (
            dim_scores["brand_consistency"] * 0.35
            + dim_scores["gameplay_consistency"] * 0.30
            + dim_scores["facebook_hook"] * 0.20
            + dim_scores["visual_readability"] * 0.15
        )
        # AI Risk 高 → 生成质量不稳定 → 实际成本可能更高 → 分数下调
        ai_risk_penalty = (100 - dim_scores["ai_generation_risk"]) * 0.15
        cpp = max(0.0, min(100.0, cost_base - ai_risk_penalty))
        cpi = max(0.0, min(100.0, cost_base * 0.8 + dim_scores["winning_similarity"] * 0.2 - ai_risk_penalty * 0.8))

        # 计算 ROAS 潜力
        roas_base = self._weighted_score(dim_scores, self.ROAS_WEIGHTS)
        # Novelty 适度加分（新鲜感带来短期 ROAS），但 Fatigue 高则减分
        novelty_bonus = (dim_scores["novelty"] - 50) * 0.10
        fatigue_penalty = max(0, (dim_scores["creative_fatigue"] - 50)) * 0.20
        d1_roas = max(0.0, min(100.0, roas_base + novelty_bonus - fatigue_penalty))
        d7_roas = max(0.0, min(100.0, roas_base * 0.9 + dim_scores["brand_consistency"] * 0.10 - fatigue_penalty * 0.8))
        d30_roas = max(0.0, min(100.0, roas_base * 0.85 + dim_scores["brand_consistency"] * 0.15 - fatigue_penalty * 0.6))

        # 应用 AI Risk 可靠性折扣
        ai_risk = dim_scores["ai_generation_risk"]
        reliability = 1.0 - (max(0, 100 - ai_risk) / 100.0) * self.AI_RISK_DISCOUNT_FACTOR

        ctr *= reliability
        cvr *= reliability
        ipm *= reliability
        cpp *= reliability
        cpi *= reliability
        d1_roas *= reliability
        d7_roas *= reliability
        d30_roas *= reliability

        # 历史数据修正（如有）
        if history:
            ctr, cvr, ipm, cpp, cpi, d1_roas, d7_roas, d30_roas = self._apply_history_adjustment(
                variant_ranking, history, ctr, cvr, ipm, cpp, cpi, d1_roas, d7_roas, d30_roas
            )

        # 计算总体表现
        overall = (
            ctr * self.OVERALL_WEIGHTS["ctr"]
            + cvr * self.OVERALL_WEIGHTS["cvr"]
            + ipm * self.OVERALL_WEIGHTS["ipm"]
            + cpp * self.OVERALL_WEIGHTS["cpp"]
            + cpi * self.OVERALL_WEIGHTS["cpi"]
            + d1_roas * self.OVERALL_WEIGHTS["d1_roas"]
            + d7_roas * self.OVERALL_WEIGHTS["d7_roas"]
            + d30_roas * self.OVERALL_WEIGHTS["d30_roas"]
        )

        breakdown = {
            "ctr": {
                "score": round(ctr, 1),
                "weights": self.CTR_WEIGHTS,
                "input_scores": {k: dim_scores[k] for k in self.CTR_WEIGHTS},
            },
            "cvr": {
                "score": round(cvr, 1),
                "weights": self.CVR_WEIGHTS,
                "input_scores": {k: dim_scores[k] for k in self.CVR_WEIGHTS},
            },
            "ipm": {
                "score": round(ipm, 1),
                "weights": self.IPM_WEIGHTS,
                "input_scores": {k: dim_scores[k] for k in self.IPM_WEIGHTS},
            },
            "cpp": {
                "score": round(cpp, 1),
                "cost_base": round(cost_base, 1),
                "ai_risk_penalty": round(ai_risk_penalty, 1),
            },
            "cpi": {
                "score": round(cpi, 1),
            },
            "d1_roas": {
                "score": round(d1_roas, 1),
                "roas_base": round(roas_base, 1),
                "novelty_bonus": round(novelty_bonus, 1),
                "fatigue_penalty": round(fatigue_penalty, 1),
            },
            "d7_roas": {
                "score": round(d7_roas, 1),
            },
            "d30_roas": {
                "score": round(d30_roas, 1),
            },
            "reliability": round(reliability, 3),
            "ai_risk": ai_risk,
            "history_applied": history is not None,
        }

        return PerformancePrediction(
            variant_id=variant_id,
            ctr_potential=round(ctr, 1),
            cvr_potential=round(cvr, 1),
            ipm_potential=round(ipm, 1),
            cpp_potential=round(cpp, 1),
            cpi_potential=round(cpi, 1),
            d1_roas_potential=round(d1_roas, 1),
            d7_roas_potential=round(d7_roas, 1),
            d30_roas_potential=round(d30_roas, 1),
            overall_performance=round(overall, 1),
            breakdown=breakdown,
        )

    def predict_batch(self, rankings: list[dict], history: dict | None = None) -> list[PerformancePrediction]:
        """批量预测"""
        return [self.predict(r, history) for r in rankings]

    def _extract_dimension_scores(self, dimensions: dict) -> dict[str, float]:
        """从 ranking dimensions 中提取各维度分数，缺失时返回 50.0 默认"""
        keys = [
            "winning_similarity",
            "facebook_hook",
            "visual_readability",
            "novelty",
            "creative_fatigue",
            "brand_consistency",
            "ai_generation_risk",
            "gameplay_consistency",
            "facebook_policy_risk",
        ]
        scores = {}
        for key in keys:
            dim = dimensions.get(key, {})
            scores[key] = float(dim.get("score", 50.0))
        return scores

    def _weighted_score(self, dim_scores: dict[str, float], weights: dict[str, float]) -> float:
        """按权重计算加权分数"""
        total = 0.0
        for key, weight in weights.items():
            total += dim_scores.get(key, 50.0) * weight
        return max(0.0, min(100.0, total))

    def _apply_history_adjustment(
        self,
        variant_ranking: dict,
        history: dict,
        ctr: float,
        cvr: float,
        ipm: float,
        cpp: float,
        cpi: float,
        d1_roas: float,
        d7_roas: float,
        d30_roas: float,
    ) -> tuple[float, float, float, float, float, float, float, float]:
        """使用历史数据修正预测值
        
        当前版本仅做简单规则修正：
        - 如果历史中有相同 changed_dimension 的数据，按历史表现微调 ±5%
        """
        changed_dim = variant_ranking.get("changed_dimension", "")
        if not changed_dim or "historical_performance" not in history:
            return ctr, cvr, ipm, cpp, cpi, d1_roas, d7_roas, d30_roas

        hist_perf = history.get("historical_performance", {})
        dim_hist = hist_perf.get(changed_dim, {})
        if not dim_hist:
            return ctr, cvr, ipm, cpp, cpi, d1_roas, d7_roas, d30_roas

        # 历史 CTR 相对基准的偏差
        hist_ctr_relative = dim_hist.get("ctr_relative", 1.0)
        hist_cvr_relative = dim_hist.get("cvr_relative", 1.0)
        hist_ipm_relative = dim_hist.get("ipm_relative", 1.0)

        ctr = max(0.0, min(100.0, ctr * hist_ctr_relative))
        cvr = max(0.0, min(100.0, cvr * hist_cvr_relative))
        ipm = max(0.0, min(100.0, ipm * hist_ipm_relative))

        # 成本与 ROAS 反向调整
        hist_cpp_relative = dim_hist.get("cpp_relative", 1.0)
        hist_cpi_relative = dim_hist.get("cpi_relative", 1.0)
        hist_roas_relative = dim_hist.get("roas_relative", 1.0)

        # cpp_relative < 1 表示历史成本更低（更好），所以 cpp 分数应该更高
        if cpp > 0:
            cpp = max(0.0, min(100.0, cpp / max(0.1, hist_cpp_relative)))
        if cpi > 0:
            cpi = max(0.0, min(100.0, cpi / max(0.1, hist_cpi_relative)))

        d1_roas = max(0.0, min(100.0, d1_roas * hist_roas_relative))
        d7_roas = max(0.0, min(100.0, d7_roas * hist_roas_relative))
        d30_roas = max(0.0, min(100.0, d30_roas * hist_roas_relative))

        return ctr, cvr, ipm, cpp, cpi, d1_roas, d7_roas, d30_roas
