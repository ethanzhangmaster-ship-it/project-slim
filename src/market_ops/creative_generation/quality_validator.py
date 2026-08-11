"""Quality Validator - 创意生成质量验证器

在生成前检查:
- Prompt 长度、重复、违规、Facebook 风险、品牌一致性
- Storyboard 节奏、Hook、主体、CTA
- Image Task 参数合法性
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    score: float                          # 0-100
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    category: str = ""                    # prompt / storyboard / image_task

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "errors": self.errors,
            "warnings": self.warnings,
            "category": self.category,
        }


class QualityValidator:
    """质量验证器"""

    # Facebook 广告政策风险词
    FACEBOOK_RISK_WORDS: set[str] = {
        "free", "100%", "guaranteed", "no risk", "act now", "limited time",
        "click here", "buy now", "order now", "call now", "limited offer",
        "urgent", "hurry", "act immediately", "don't miss", "last chance",
        "money back", "winner", "win", "congratulations", "you've won",
        "before/after", "before and after", "miracle", "cure", "melt fat",
        "lose weight fast", "get rich", "make money fast",
    }

    # 品牌一致性检查 (P04 示例)
    BRAND_REQUIREMENTS: dict[str, list[str]] = {
        "P04": [
            "witch", "chibi", "cute", "magic", "fantasy",
        ],
    }

    # Prompt 质量参数
    PROMPT_MIN_LENGTH = 80
    PROMPT_MAX_LENGTH = 2000
    PROMPT_IDEAL_LENGTH = (200, 600)

    def __init__(self):
        self._facebook_risk = set(self.FACEBOOK_RISK_WORDS)
        self._brand_reqs = dict(self.BRAND_REQUIREMENTS)

    # ------------------------------------------------------------------
    # Prompt 验证
    # ------------------------------------------------------------------
    def validate_prompt(
        self,
        prompt: str,
        project: str = "P04",
        check_brand: bool = True,
        check_policy: bool = True,
    ) -> ValidationResult:
        """验证 Prompt 质量"""
        errors: list[str] = []
        warnings: list[str] = []
        score = 100.0

        prompt_lower = prompt.lower()

        # 1. 长度检查
        length = len(prompt)
        if length < self.PROMPT_MIN_LENGTH:
            errors.append(f"Prompt 过短 ({length} 字符)，建议至少 {self.PROMPT_MIN_LENGTH} 字符")
            score -= 30
        elif length > self.PROMPT_MAX_LENGTH:
            errors.append(f"Prompt 过长 ({length} 字符)，建议不超过 {self.PROMPT_MAX_LENGTH} 字符")
            score -= 15
        elif not (self.PROMPT_IDEAL_LENGTH[0] <= length <= self.PROMPT_IDEAL_LENGTH[1]):
            warnings.append(f"Prompt 长度 {length} 不在理想范围 {self.PROMPT_IDEAL_LENGTH}")
            score -= 5

        # 2. 重复检查
        words = re.findall(r"\b\w+\b", prompt_lower)
        word_counts: dict[str, int] = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
        duplicates = {w: c for w, c in word_counts.items() if c > 3}
        if duplicates:
            dup_str = ", ".join([f"'{w}'x{c}" for w, c in list(duplicates.items())[:3]])
            warnings.append(f"Prompt 中有重复词: {dup_str}")
            score -= 10

        # 3. Facebook 政策风险
        if check_policy:
            risks = [w for w in self._facebook_risk if w in prompt_lower]
            if risks:
                errors.append(f"Facebook 政策风险词: {', '.join(risks[:5])}")
                score -= 40

        # 4. 品牌一致性
        if check_brand and project in self._brand_reqs:
            reqs = self._brand_reqs[project]
            missing = [r for r in reqs if r not in prompt_lower]
            if len(missing) > len(reqs) // 2:
                warnings.append(f"品牌元素不足，缺少: {', '.join(missing[:3])}")
                score -= 10

        # 5. 关键词丰富度
        key_categories = ["lighting", "camera", "color", "style", "composition"]
        missing_cats = [c for c in key_categories if c not in prompt_lower]
        if missing_cats:
            warnings.append(f"建议加入: {', '.join(missing_cats)} 相关描述")
            score -= 5 * len(missing_cats)

        # 6. 标点检查
        if prompt.count(",") < 3:
            warnings.append("Prompt 逗号太少，建议用逗号分隔不同元素")
            score -= 5

        score = max(0.0, min(100.0, score))
        passed = len(errors) == 0 and score >= 60

        return ValidationResult(
            passed=passed,
            score=round(score, 1),
            errors=errors,
            warnings=warnings,
            category="prompt",
        )

    # ------------------------------------------------------------------
    # Storyboard 验证
    # ------------------------------------------------------------------
    def validate_storyboard(
        self,
        storyboard: dict[str, Any],
        min_scenes: int = 3,
        max_scenes: int = 6,
        min_duration: int = 10,
        max_duration: int = 30,
    ) -> ValidationResult:
        """验证 Storyboard 质量"""
        errors: list[str] = []
        warnings: list[str] = []
        score = 100.0

        scenes = storyboard.get("scenes", [])
        total_duration = sum(s.get("duration", 0) for s in scenes)

        # 1. 场景数量
        if len(scenes) < min_scenes:
            errors.append(f"场景太少 ({len(scenes)} 个)，建议至少 {min_scenes} 个")
            score -= 25
        elif len(scenes) > max_scenes:
            warnings.append(f"场景较多 ({len(scenes)} 个)，可能节奏拖沓")
            score -= 10

        # 2. 时长
        if total_duration < min_duration:
            errors.append(f"总时长过短 ({total_duration}s)，建议至少 {min_duration}s")
            score -= 20
        elif total_duration > max_duration:
            warnings.append(f"总时长较长 ({total_duration}s)，建议控制在 {max_duration}s 内")
            score -= 10

        # 3. 必须有 Hook 场景
        has_hook = any("hook" in s.get("scene_type", "").lower() for s in scenes)
        if not has_hook:
            errors.append("缺少 Hook 场景，前 2 秒必须抓住注意力")
            score -= 30

        # 4. 必须有 CTA 场景
        has_cta = any("cta" in s.get("scene_type", "").lower() for s in scenes)
        if not has_cta:
            warnings.append("缺少明确的 CTA 场景")
            score -= 15

        # 5. 场景描述质量
        for i, scene in enumerate(scenes):
            desc = scene.get("description", "")
            if len(desc) < 20:
                warnings.append(f"场景 {i+1} 描述过短 ({len(desc)} 字符)")
                score -= 5
            if "character" not in desc.lower() and "subject" not in desc.lower():
                warnings.append(f"场景 {i+1} 未明确主体")
                score -= 5

        score = max(0.0, min(100.0, score))
        passed = len(errors) == 0 and score >= 60

        return ValidationResult(
            passed=passed,
            score=round(score, 1),
            errors=errors,
            warnings=warnings,
            category="storyboard",
        )

    # ------------------------------------------------------------------
    # Image Task 验证
    # ------------------------------------------------------------------
    def validate_image_task(self, task: dict[str, Any]) -> ValidationResult:
        """验证 Image Task 参数合法性"""
        errors: list[str] = []
        warnings: list[str] = []
        score = 100.0

        # 1. 必需字段
        required = ["model", "prompt", "width", "height"]
        for field in required:
            if not task.get(field):
                errors.append(f"缺少必需字段: {field}")
                score -= 20

        # 2. 尺寸检查
        width = task.get("width", 0)
        height = task.get("height", 0)
        if width <= 0 or height <= 0:
            errors.append(f"尺寸不合法: {width}x{height}")
            score -= 20
        elif width > 2048 or height > 2048:
            warnings.append(f"尺寸过大 ({width}x{height})，可能消耗过多资源")
            score -= 10
        elif width < 256 or height < 256:
            warnings.append(f"尺寸过小 ({width}x{height})，可能影响质量")
            score -= 10

        # 3. Steps 检查
        steps = task.get("steps", 30)
        if steps < 10:
            warnings.append(f"Steps 过少 ({steps})，可能影响质量")
            score -= 10
        elif steps > 50:
            warnings.append(f"Steps 较多 ({steps})，生成时间较长")
            score -= 5

        # 4. CFG Scale
        cfg = task.get("cfg_scale", 7.0)
        if cfg < 1.0 or cfg > 15.0:
            warnings.append(f"CFG Scale {cfg} 超出常见范围 (1-15)")
            score -= 10

        # 5. Prompt 检查 (复用)
        prompt = task.get("prompt", "")
        if prompt:
            prompt_result = self.validate_prompt(prompt, check_brand=False, check_policy=True)
            if not prompt_result.passed:
                errors.extend([f"[Prompt] {e}" for e in prompt_result.errors])
                score -= 20
            warnings.extend([f"[Prompt] {w}" for w in prompt_result.warnings])
            score -= (100 - prompt_result.score) * 0.3

        score = max(0.0, min(100.0, score))
        passed = len(errors) == 0 and score >= 60

        return ValidationResult(
            passed=passed,
            score=round(score, 1),
            errors=errors,
            warnings=warnings,
            category="image_task",
        )

    # ------------------------------------------------------------------
    # 批量验证
    # ------------------------------------------------------------------
    def validate_all(
        self,
        prompt: str | None = None,
        storyboard: dict[str, Any] | None = None,
        image_task: dict[str, Any] | None = None,
    ) -> dict[str, ValidationResult]:
        """批量验证所有组件"""
        results = {}
        if prompt:
            results["prompt"] = self.validate_prompt(prompt)
        if storyboard:
            results["storyboard"] = self.validate_storyboard(storyboard)
        if image_task:
            results["image_task"] = self.validate_image_task(image_task)
        return results
