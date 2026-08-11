"""CTR Predictor"""
from ..models import RemixRecipe


class CTRPredictor:
    """预测 CTR"""

    def predict(self, recipe: RemixRecipe) -> float:
        """基于 hook 段质量预测 CTR"""
        hook_segs = [s for s in recipe.segments if s.role == "hook"]
        if not hook_segs:
            return 1.0
        avg_score = sum(s.material_score for s in hook_segs) / len(hook_segs)
        # 基础 CTR 1.5%，每分增加 0.02%
        return 1.5 + avg_score * 0.02
