"""Creative Validator — 创意内容验证"""
from ..models import RemixRecipe, QAResult


class CreativeValidator:
    """验证创意内容完整性"""

    def validate(self, recipe: RemixRecipe) -> QAResult:
        """检查创意是否符合买量规范"""
        result = QAResult(creative_id=recipe.recipe_id)

        roles = [s.role for s in recipe.segments]

        # 必须有 hook
        if "hook" not in roles:
            result.passed = False
            result.issues.append("缺少 Hook 段")

        # 必须有 gameplay 或 problem
        if "gameplay" not in roles and "problem" not in roles:
            result.warnings.append("缺少核心玩法/冲突展示")

        # 必须有 reward 或 cta
        if "reward" not in roles and "cta" not in roles:
            result.warnings.append("缺少 Reward/CTA 段")

        # 时长检查
        if recipe.total_duration < 5:
            result.passed = False
            result.issues.append(f"视频过短: {recipe.total_duration:.1f}s")
        if recipe.total_duration > 60:
            result.warnings.append(f"视频较长: {recipe.total_duration:.1f}s")

        return result
