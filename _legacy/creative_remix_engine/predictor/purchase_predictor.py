"""Purchase Predictor"""
from ..models import RemixRecipe


class PurchasePredictor:
    """预测购买转化率"""

    def predict(self, recipe: RemixRecipe) -> float:
        """基于 reward 段质量预测 purchase"""
        reward_segs = [s for s in recipe.segments if s.role in ["reward", "cta"]]
        if not reward_segs:
            return 0.5
        avg_score = sum(s.material_score for s in reward_segs) / len(reward_segs)
        return 0.5 + avg_score * 0.03
