"""AI Creative Predictor V3.1 — 预测创意表现"""
from ..models import RemixRecipe, CreativePrediction
from ..predictor.feature_builder import FeatureBuilder


class CreativePredictor:
    """V3.1: 基于配方特征预测 CTR / CVR / ROAS"""

    def __init__(self):
        self.feature_builder = FeatureBuilder()

    def predict(self, recipe: RemixRecipe) -> CreativePrediction:
        """预测单个创意的表现"""
        pred = CreativePrediction(creative_id=recipe.recipe_id)

        if not recipe.segments:
            pred.overall_score = 0
            pred.recommendation = "SKIP"
            return pred

        # 构建特征
        feature = self.feature_builder.build(recipe)

        # Hook 评分
        hook_segs = [s for s in recipe.segments if s.role == "hook"]
        if hook_segs:
            pred.hook_score = sum(s.material_score for s in hook_segs) / len(hook_segs)

        # V3.1: 预测 CTR（基于 hook_score + dna_match + duration）
        base_ctr = 1.5
        pred.expected_ctr = base_ctr + pred.hook_score * 0.025 + feature.dna_match * 0.01
        if recipe.total_duration > 30:
            pred.expected_ctr -= 0.3
        pred.ctr_score = min(pred.expected_ctr * 20, 100)  # 转换为 0-100

        # V3.1: 预测 CVR（基于 reward 段 + gameplay 段）
        reward_segs = [s for s in recipe.segments if s.role in ["reward", "cta"]]
        gameplay_segs = [s for s in recipe.segments if s.role == "gameplay"]
        reward_avg = sum(s.material_score for s in reward_segs) / len(reward_segs) if reward_segs else 0
        gameplay_avg = sum(s.segment_score for s in gameplay_segs) / len(gameplay_segs) if gameplay_segs else 0
        pred.expected_cvr = 0.5 + reward_avg * 0.02 + gameplay_avg * 0.015 + pred.hook_score * 0.01
        pred.purchase_score = min(pred.expected_cvr * 25, 100)

        # V3.1: 预测 ROAS
        pred.expected_roas = 0.5 + pred.expected_ctr * 0.2 + pred.expected_cvr * 0.5
        if pred.expected_roas > 5.0:
            pred.expected_roas = 5.0

        # Fatigue 风险
        used_count = len(set(s.v_num for s in recipe.segments))
        total_segments = len(recipe.segments)
        if total_segments > 0:
            unique_ratio = used_count / total_segments
            pred.fatigue_risk = (1 - unique_ratio) * 50

        # 综合评分
        pred.overall_score = (
            pred.hook_score * 0.25 +
            pred.ctr_score * 0.20 +
            pred.purchase_score * 0.25 +
            min(pred.expected_roas * 15, 15) +  # ROAS 贡献最多15分
            (100 - pred.fatigue_risk) * 0.15
        )

        # V3.1: 推荐决策（基于 expected_roas）
        if pred.expected_roas >= 1.5 and pred.overall_score >= 75:
            pred.recommendation = "TEST"
            pred.confidence = 0.85
        elif pred.expected_roas >= 1.0 and pred.overall_score >= 60:
            pred.recommendation = "TEST_LOW_BUDGET"
            pred.confidence = 0.65
        else:
            pred.recommendation = "SKIP"
            pred.confidence = 0.40

        return pred
