"""Ranking Engine V4 — Creative Opportunity Score"""
from typing import List, Dict, Tuple

from ..models import RemixRecipe, CreativePrediction


class RankingEngineV4:
    """V4: Expected Profit Score 排序"""

    def rank(self, recipes: List[RemixRecipe],
             predictions: List[CreativePrediction],
             dna_scores: Dict[str, float] = None,
             novelty_scores: Dict[str, float] = None) -> List[Tuple[RemixRecipe, CreativePrediction, Dict]]:
        """
        排序并输出详细理由
        返回: [(recipe, prediction, rank_info), ...]
        """
        scored = []

        for recipe, pred in zip(recipes, predictions):
            # V4 评分公式
            dna_score = dna_scores.get(recipe.recipe_id, 50) if dna_scores else 50
            novelty = novelty_scores.get(recipe.recipe_id, 50) if novelty_scores else 50

            opportunity_score = (
                pred.expected_roas * 10 * 0.40 +        # 40% Expected ROAS
                pred.purchase_score * 0.25 +              # 25% Purchase Probability
                dna_score * 0.15 +                        # 15% Winner DNA Match
                novelty * 0.10 +                          # 10% Novelty
                (100 - pred.fatigue_risk) * 0.10         # 10% Diversity/Freshness
            )

            # 测试优先级
            if opportunity_score >= 80:
                priority = "P0_CRITICAL"
                reason = f"高ROAS潜力(eROAS={pred.expected_roas:.2f})+强DNA匹配"
            elif opportunity_score >= 65:
                priority = "P1_HIGH"
                reason = f"良好购买概率({pred.purchase_score:.1f})+DNA匹配"
            elif opportunity_score >= 50:
                priority = "P2_MEDIUM"
                reason = "中等潜力，建议小预算测试"
            else:
                priority = "P3_LOW"
                reason = "潜力较低，建议优化后重测"

            rank_info = {
                "opportunity_score": round(opportunity_score, 1),
                "priority": priority,
                "reason": reason,
                "breakdown": {
                    "roas_contrib": round(pred.expected_roas * 10 * 0.40, 1),
                    "purchase_contrib": round(pred.purchase_score * 0.25, 1),
                    "dna_contrib": round(dna_score * 0.15, 1),
                    "novelty_contrib": round(novelty * 0.10, 1),
                    "freshness_contrib": round((100 - pred.fatigue_risk) * 0.10, 1),
                }
            }

            scored.append((recipe, pred, rank_info))

        # 按opportunity_score降序
        scored.sort(key=lambda x: -x[2]["opportunity_score"])
        return scored
