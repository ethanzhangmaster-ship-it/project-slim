"""AI Quality Checker — 创意质量升级检查"""
from pathlib import Path
from typing import List

from ..models import RemixRecipe, QAResult


class AIQualityChecker:
    """AI 驱动的创意质量检查"""

    def check(self, recipe: RemixRecipe, video_path: Path = None) -> QAResult:
        """全面检查创意质量"""
        result = QAResult(creative_id=recipe.recipe_id)
        score = 100

        roles = [s.role for s in recipe.segments]
        v_nums = [s.v_num for s in recipe.segments]

        # === 创意结构检查 ===

        # 必须有 hook
        if "hook" not in roles:
            result.passed = False
            result.issues.append("缺少 Hook 段")
            score -= 30

        # 必须有 gameplay 或 problem
        if "gameplay" not in roles and "problem" not in roles:
            result.warnings.append("缺少核心玩法/冲突展示")
            score -= 15

        # 必须有 reward 或 cta
        if "reward" not in roles and "cta" not in roles:
            result.warnings.append("缺少 Reward/CTA 段")
            score -= 15

        # === 时长检查 ===
        if recipe.total_duration < 5:
            result.passed = False
            result.issues.append(f"视频过短: {recipe.total_duration:.1f}s")
            score -= 20
        elif recipe.total_duration > 60:
            result.warnings.append(f"视频较长: {recipe.total_duration:.1f}s")
            score -= 5

        # === 素材多样性检查 ===
        unique_videos = len(set(v_nums))
        if unique_videos < len(recipe.segments) * 0.5:
            result.warnings.append("素材复用率过高")
            score -= 10

        # === 评分质量检查 ===
        avg_score = sum(s.material_score for s in recipe.segments) / max(len(recipe.segments), 1)
        if avg_score < 40:
            result.warnings.append("素材平均评分较低")
            score -= 10

        # === 视频文件检查 ===
        if video_path and video_path.exists():
            # 文件大小检查
            size_mb = video_path.stat().st_size / 1024 / 1024
            if size_mb < 1:
                result.issues.append("视频文件过小")
                score -= 20
            elif size_mb > 100:
                result.warnings.append("视频文件较大")
                score -= 5

        result.quality_score = max(0, score)

        # 如果扣分严重，标记为不通过
        if result.quality_score < 60:
            result.passed = False

        return result
