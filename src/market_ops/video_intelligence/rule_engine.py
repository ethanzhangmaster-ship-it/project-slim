"""Rule Engine - 统一规则管理

集中管理所有Facebook规则：
- Feed Rules
- Reels Rules
- ASC Rules
- AEO Rules
- VO Rules
- Policy Rules

不要散落在各个模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class Rule:
    rule_id: str
    category: str
    description: str
    condition: str
    action: str
    weight: float = 1.0
    enabled: bool = True
    score_modifier: float = 0.0


class RuleEngine:
    """统一规则管理引擎"""

    def __init__(self):
        self._rules: dict[str, Rule] = {}
        self._rule_categories: dict[str, list[str]] = {
            "feed": [],
            "reels": [],
            "stories": [],
            "asc": [],
            "aeo": [],
            "vo": [],
            "policy": [],
            "creatives": [],
        }
        self._condition_evaluators: dict[str, Callable[[dict], bool]] = {}

        self._init_default_rules()
        self._init_condition_evaluators()

    def _init_default_rules(self) -> None:
        """初始化所有默认规则"""

        feed_rules = [
            {
                "rule_id": "feed_duration_15_30s",
                "category": "feed",
                "description": "Feed视频最佳时长15-30秒",
                "condition": "duration_between_15_30",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "feed_hook_first_3s",
                "category": "feed",
                "description": "前3秒必须有强钩子",
                "condition": "has_hook_in_first_3s",
                "action": "score_modifier",
                "weight": 1.2,
                "score_modifier": 8.0,
            },
            {
                "rule_id": "feed_text_overlay_limit",
                "category": "feed",
                "description": "文字覆盖不超过20%",
                "condition": "text_overlay_under_20pct",
                "action": "score_modifier",
                "weight": 0.8,
                "score_modifier": 3.0,
            },
            {
                "rule_id": "feed_cta_clear",
                "category": "feed",
                "description": "清晰的CTA按钮",
                "condition": "has_clear_cta",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "feed_aspect_ratio_9_16",
                "category": "feed",
                "description": "推荐9:16竖屏比例",
                "condition": "aspect_ratio_9_16",
                "action": "score_modifier",
                "weight": 0.6,
                "score_modifier": 2.0,
            },
        ]

        reels_rules = [
            {
                "rule_id": "reels_duration_15_60s",
                "category": "reels",
                "description": "Reels最佳时长15-60秒",
                "condition": "duration_between_15_60",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "reels_vertical_format",
                "category": "reels",
                "description": "必须是竖屏格式",
                "condition": "is_vertical",
                "action": "score_modifier",
                "weight": 1.5,
                "score_modifier": 10.0,
            },
            {
                "rule_id": "reels_text_on_screen",
                "category": "reels",
                "description": "屏幕文字辅助理解",
                "condition": "has_screen_text",
                "action": "score_modifier",
                "weight": 0.7,
                "score_modifier": 3.0,
            },
            {
                "rule_id": "reels_trending_audio",
                "category": "reels",
                "description": "使用热门音频",
                "condition": "uses_trending_audio",
                "action": "score_modifier",
                "weight": 0.8,
                "score_modifier": 4.0,
            },
            {
                "rule_id": "reels_fast_paced",
                "category": "reels",
                "description": "快节奏剪辑",
                "condition": "fast_paced_editing",
                "action": "score_modifier",
                "weight": 0.9,
                "score_modifier": 4.0,
            },
        ]

        stories_rules = [
            {
                "rule_id": "stories_duration_5_15s",
                "category": "stories",
                "description": "Stories最佳时长5-15秒",
                "condition": "duration_between_5_15",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "stories_vertical_fullscreen",
                "category": "stories",
                "description": "全屏竖屏格式",
                "condition": "is_fullscreen_vertical",
                "action": "score_modifier",
                "weight": 1.3,
                "score_modifier": 8.0,
            },
            {
                "rule_id": "stories_interactive_elements",
                "category": "stories",
                "description": "包含互动元素",
                "condition": "has_interactive_elements",
                "action": "score_modifier",
                "weight": 0.9,
                "score_modifier": 5.0,
            },
        ]

        asc_rules = [
            {
                "rule_id": "asc_creative_variety",
                "category": "asc",
                "description": "ASC需要足够的创意多样性",
                "condition": "has_sufficient_variety",
                "action": "score_modifier",
                "weight": 1.2,
                "score_modifier": 6.0,
            },
            {
                "rule_id": "asc_min_5_creatives",
                "category": "asc",
                "description": "ASC至少5个创意",
                "condition": "min_5_creatives",
                "action": "warning",
                "weight": 1.0,
                "score_modifier": 0.0,
            },
            {
                "rule_id": "asc_no_duplicate_assets",
                "category": "asc",
                "description": "避免重复素材",
                "condition": "no_duplicate_assets",
                "action": "score_modifier",
                "weight": 0.8,
                "score_modifier": 4.0,
            },
            {
                "rule_id": "asc_aspect_ratio_mix",
                "category": "asc",
                "description": "混合多种比例效果更好",
                "condition": "mixed_aspect_ratios",
                "action": "score_modifier",
                "weight": 0.7,
                "score_modifier": 3.0,
            },
        ]

        aeo_rules = [
            {
                "rule_id": "aeo_app_install_focus",
                "category": "aeo",
                "description": "AEO聚焦应用安装价值",
                "condition": "focuses_on_app_value",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "aeo_gameplay_showcase",
                "category": "aeo",
                "description": "展示实际游戏/应用玩法",
                "condition": "shows_gameplay",
                "action": "score_modifier",
                "weight": 1.1,
                "score_modifier": 6.0,
            },
            {
                "rule_id": "aeo_clear_value_proposition",
                "category": "aeo",
                "description": "清晰的价值主张",
                "condition": "clear_value_proposition",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
        ]

        vo_rules = [
            {
                "rule_id": "vo_value_focused",
                "category": "vo",
                "description": "VO广告聚焦高价值用户",
                "condition": "high_value_focus",
                "action": "score_modifier",
                "weight": 1.2,
                "score_modifier": 7.0,
            },
            {
                "rule_id": "vo_premium_feel",
                "category": "vo",
                "description": "高端质感吸引付费用户",
                "condition": "premium_quality",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "vo_long_term_value",
                "category": "vo",
                "description": "突出长期价值",
                "condition": "shows_long_term_value",
                "action": "score_modifier",
                "weight": 0.9,
                "score_modifier": 4.0,
            },
        ]

        policy_rules = [
            {
                "rule_id": "policy_no_misleading_claims",
                "category": "policy",
                "description": "禁止误导性声明",
                "condition": "no_misleading_claims",
                "action": "reject",
                "weight": 2.0,
                "score_modifier": -50.0,
            },
            {
                "rule_id": "policy_no_prohibited_content",
                "category": "policy",
                "description": "禁止违规内容",
                "condition": "no_prohibited_content",
                "action": "reject",
                "weight": 2.0,
                "score_modifier": -50.0,
            },
            {
                "rule_id": "policy_no_exaggeration",
                "category": "policy",
                "description": "禁止夸大宣传",
                "condition": "no_exaggeration",
                "action": "warning",
                "weight": 1.5,
                "score_modifier": -10.0,
            },
            {
                "rule_id": "policy_proper_disclosure",
                "category": "policy",
                "description": "适当的广告披露",
                "condition": "has_ad_disclosure",
                "action": "warning",
                "weight": 0.8,
                "score_modifier": -5.0,
            },
            {
                "rule_id": "policy_no_before_after_weight_loss",
                "category": "policy",
                "description": "禁止减肥前后对比",
                "condition": "no_before_after_weight_loss",
                "action": "reject",
                "weight": 2.0,
                "score_modifier": -50.0,
            },
            {
                "rule_id": "policy_targeting_compliance",
                "category": "policy",
                "description": "定位设置合规",
                "condition": "targeting_compliant",
                "action": "warning",
                "weight": 1.0,
                "score_modifier": -5.0,
            },
        ]

        creatives_rules = [
            {
                "rule_id": "creative_high_quality",
                "category": "creatives",
                "description": "高质量视觉效果",
                "condition": "high_quality_visual",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "creative_clear_message",
                "category": "creatives",
                "description": "信息传达清晰",
                "condition": "clear_message",
                "action": "score_modifier",
                "weight": 1.1,
                "score_modifier": 6.0,
            },
            {
                "rule_id": "creative_brand_consistency",
                "category": "creatives",
                "description": "品牌一致性",
                "condition": "brand_consistent",
                "action": "score_modifier",
                "weight": 0.8,
                "score_modifier": 3.0,
            },
            {
                "rule_id": "creative_emotional_engagement",
                "category": "creatives",
                "description": "情感共鸣",
                "condition": "emotionally_engaging",
                "action": "score_modifier",
                "weight": 1.0,
                "score_modifier": 5.0,
            },
            {
                "rule_id": "creative_audio_quality",
                "category": "creatives",
                "description": "音频质量良好",
                "condition": "good_audio_quality",
                "action": "score_modifier",
                "weight": 0.7,
                "score_modifier": 3.0,
            },
            {
                "rule_id": "creative_no_black_bars",
                "category": "creatives",
                "description": "无黑边",
                "condition": "no_black_bars",
                "action": "score_modifier",
                "weight": 0.9,
                "score_modifier": 4.0,
            },
        ]

        all_rules = (
            feed_rules + reels_rules + stories_rules
            + asc_rules + aeo_rules + vo_rules
            + policy_rules + creatives_rules
        )

        for rule_data in all_rules:
            rule = Rule(**rule_data)
            self._rules[rule.rule_id] = rule
            if rule.category in self._rule_categories:
                self._rule_categories[rule.category].append(rule.rule_id)

    def _init_condition_evaluators(self) -> None:
        """初始化条件评估器"""
        self._condition_evaluators = {
            "duration_between_15_30": self._check_duration_15_30,
            "duration_between_15_60": self._check_duration_15_60,
            "duration_between_5_15": self._check_duration_5_15,
            "has_hook_in_first_3s": self._check_hook_first_3s,
            "text_overlay_under_20pct": self._check_text_overlay,
            "has_clear_cta": self._check_clear_cta,
            "aspect_ratio_9_16": self._check_aspect_9_16,
            "is_vertical": self._check_vertical,
            "has_screen_text": self._check_screen_text,
            "uses_trending_audio": self._check_trending_audio,
            "fast_paced_editing": self._check_fast_paced,
            "is_fullscreen_vertical": self._check_fullscreen_vertical,
            "has_interactive_elements": self._check_interactive,
            "has_sufficient_variety": self._check_variety,
            "min_5_creatives": self._check_min_5,
            "no_duplicate_assets": self._check_no_duplicates,
            "mixed_aspect_ratios": self._check_mixed_ratios,
            "focuses_on_app_value": self._check_app_value,
            "shows_gameplay": self._check_gameplay,
            "clear_value_proposition": self._check_value_prop,
            "high_value_focus": self._check_high_value,
            "premium_quality": self._check_premium,
            "shows_long_term_value": self._check_long_term,
            "no_misleading_claims": self._check_no_misleading,
            "no_prohibited_content": self._check_no_prohibited,
            "no_exaggeration": self._check_no_exaggeration,
            "has_ad_disclosure": self._check_ad_disclosure,
            "no_before_after_weight_loss": self._check_no_before_after,
            "targeting_compliant": self._check_targeting,
            "high_quality_visual": self._check_high_quality,
            "clear_message": self._check_clear_message,
            "brand_consistent": self._check_brand_consistent,
            "emotionally_engaging": self._check_emotional,
            "good_audio_quality": self._check_audio_quality,
            "no_black_bars": self._check_no_black_bars,
        }

    def _check_duration_15_30(self, variant: dict) -> bool:
        duration = variant.get("duration", 0)
        return 15 <= duration <= 30

    def _check_duration_15_60(self, variant: dict) -> bool:
        duration = variant.get("duration", 0)
        return 15 <= duration <= 60

    def _check_duration_5_15(self, variant: dict) -> bool:
        duration = variant.get("duration", 0)
        return 5 <= duration <= 15

    def _check_hook_first_3s(self, variant: dict) -> bool:
        return variant.get("has_hook", False) and variant.get("hook_timing", 0) <= 3

    def _check_text_overlay(self, variant: dict) -> bool:
        text_ratio = variant.get("text_overlay_ratio", 0)
        return text_ratio <= 0.2

    def _check_clear_cta(self, variant: dict) -> bool:
        return variant.get("has_cta", False) and variant.get("cta_clarity", 0) > 0.7

    def _check_aspect_9_16(self, variant: dict) -> bool:
        ratio = variant.get("aspect_ratio", "")
        return ratio in ("9:16", "9/16", "vertical")

    def _check_vertical(self, variant: dict) -> bool:
        ratio = variant.get("aspect_ratio", "")
        orientation = variant.get("orientation", "")
        return ratio in ("9:16", "9/16") or orientation == "vertical"

    def _check_screen_text(self, variant: dict) -> bool:
        return variant.get("has_screen_text", False)

    def _check_trending_audio(self, variant: dict) -> bool:
        return variant.get("uses_trending_audio", False)

    def _check_fast_paced(self, variant: dict) -> bool:
        pace = variant.get("pace", "")
        return pace in ("fast", "very_fast")

    def _check_fullscreen_vertical(self, variant: dict) -> bool:
        is_vertical = self._check_vertical(variant)
        is_fullscreen = variant.get("is_fullscreen", True)
        return is_vertical and is_fullscreen

    def _check_interactive(self, variant: dict) -> bool:
        return variant.get("has_interactive_elements", False)

    def _check_variety(self, variant: dict) -> bool:
        variety_score = variant.get("variety_score", 0)
        return variety_score > 0.6

    def _check_min_5(self, variant: dict) -> bool:
        creative_count = variant.get("creative_count", 1)
        return creative_count >= 5

    def _check_no_duplicates(self, variant: dict) -> bool:
        return not variant.get("has_duplicates", False)

    def _check_mixed_ratios(self, variant: dict) -> bool:
        ratios = variant.get("aspect_ratios", [])
        return len(ratios) >= 2

    def _check_app_value(self, variant: dict) -> bool:
        return variant.get("focuses_on_app_value", True)

    def _check_gameplay(self, variant: dict) -> bool:
        return variant.get("shows_gameplay", False)

    def _check_value_prop(self, variant: dict) -> bool:
        return variant.get("has_clear_value_prop", False)

    def _check_high_value(self, variant: dict) -> bool:
        return variant.get("targets_high_value", False)

    def _check_premium(self, variant: dict) -> bool:
        quality = variant.get("quality_score", 0)
        return quality > 0.8

    def _check_long_term(self, variant: dict) -> bool:
        return variant.get("shows_long_term_value", False)

    def _check_no_misleading(self, variant: dict) -> bool:
        return not variant.get("has_misleading_claims", False)

    def _check_no_prohibited(self, variant: dict) -> bool:
        return not variant.get("has_prohibited_content", False)

    def _check_no_exaggeration(self, variant: dict) -> bool:
        return not variant.get("has_exaggeration", False)

    def _check_ad_disclosure(self, variant: dict) -> bool:
        return variant.get("has_ad_disclosure", True)

    def _check_no_before_after(self, variant: dict) -> bool:
        return not variant.get("has_before_after_weight_loss", False)

    def _check_targeting(self, variant: dict) -> bool:
        return variant.get("targeting_compliant", True)

    def _check_high_quality(self, variant: dict) -> bool:
        quality = variant.get("quality_score", 0)
        return quality > 0.7

    def _check_clear_message(self, variant: dict) -> bool:
        clarity = variant.get("message_clarity", 0)
        return clarity > 0.7

    def _check_brand_consistent(self, variant: dict) -> bool:
        return variant.get("brand_consistent", True)

    def _check_emotional(self, variant: dict) -> bool:
        engagement = variant.get("emotional_engagement", 0)
        return engagement > 0.6

    def _check_audio_quality(self, variant: dict) -> bool:
        quality = variant.get("audio_quality", 0)
        return quality > 0.7

    def _check_no_black_bars(self, variant: dict) -> bool:
        return not variant.get("has_black_bars", False)

    def get_rules(self, category: str) -> list[dict]:
        """获取某类规则"""
        if category not in self._rule_categories:
            return []

        rule_ids = self._rule_categories[category]
        result = []
        for rule_id in rule_ids:
            if rule_id in self._rules and self._rules[rule_id].enabled:
                rule = self._rules[rule_id]
                result.append({
                    "rule_id": rule.rule_id,
                    "category": rule.category,
                    "description": rule.description,
                    "condition": rule.condition,
                    "action": rule.action,
                    "weight": rule.weight,
                    "enabled": rule.enabled,
                    "score_modifier": rule.score_modifier,
                })
        return result

    def check_compliance(self, variant: dict, category: str = "policy") -> dict[str, Any]:
        """检查合规性"""
        rules = self.get_rules(category)

        passed = True
        warnings: list[str] = []
        violations: list[str] = []
        details: list[dict] = []

        for rule_data in rules:
            rule_id = rule_data["rule_id"]
            condition_name = rule_data["condition"]
            evaluator = self._condition_evaluators.get(condition_name)

            if evaluator is None:
                continue

            try:
                condition_met = evaluator(variant)
            except Exception:
                condition_met = True

            action = rule_data["action"]

            if action == "reject":
                if not condition_met:
                    passed = False
                    violations.append(rule_id)
                    details.append({
                        "rule_id": rule_id,
                        "passed": False,
                        "action": action,
                        "description": rule_data["description"],
                    })
                else:
                    details.append({
                        "rule_id": rule_id,
                        "passed": True,
                        "action": action,
                        "description": rule_data["description"],
                    })
            elif action == "warning":
                if not condition_met:
                    warnings.append(rule_data["description"])
                    details.append({
                        "rule_id": rule_id,
                        "passed": False,
                        "action": action,
                        "description": rule_data["description"],
                    })
                else:
                    details.append({
                        "rule_id": rule_id,
                        "passed": True,
                        "action": action,
                        "description": rule_data["description"],
                    })
            else:
                details.append({
                    "rule_id": rule_id,
                    "passed": condition_met,
                    "action": action,
                    "description": rule_data["description"],
                })

        return {
            "pass": passed,
            "warnings": warnings,
            "violations": violations,
            "details": details,
            "category": category,
        }

    def apply_rules(self, variant: dict, categories: list[str] | None = None) -> dict[str, Any]:
        """应用规则评分"""
        if categories is None:
            categories = list(self._rule_categories.keys())

        total_score = 0.0
        max_possible_score = 0.0
        warnings: list[str] = []
        rule_results: list[dict] = []

        for category in categories:
            rules = self.get_rules(category)

            for rule_data in rules:
                rule_id = rule_data["rule_id"]
                condition_name = rule_data["condition"]
                weight = rule_data["weight"]
                score_modifier = rule_data["score_modifier"]
                action = rule_data["action"]

                evaluator = self._condition_evaluators.get(condition_name)
                if evaluator is None:
                    continue

                try:
                    condition_met = evaluator(variant)
                except Exception:
                    condition_met = True

                if action == "score_modifier":
                    if score_modifier > 0:
                        max_possible_score += score_modifier * weight
                    if condition_met:
                        total_score += score_modifier * weight
                elif action == "warning":
                    if not condition_met:
                        warnings.append(rule_data["description"])
                        total_score += score_modifier * weight
                elif action == "reject":
                    if not condition_met:
                        total_score += score_modifier * weight

                rule_results.append({
                    "rule_id": rule_id,
                    "category": category,
                    "condition_met": condition_met,
                    "action": action,
                    "weight": weight,
                    "score_modifier": score_modifier,
                })

        normalized_score = 0.0
        if max_possible_score > 0:
            normalized_score = max(0, min(100, (total_score / max_possible_score) * 100))

        return {
            "score": round(normalized_score, 2),
            "raw_score": round(total_score, 2),
            "max_score": round(max_possible_score, 2),
            "warnings": warnings,
            "categories_checked": categories,
            "rule_count": len(rule_results),
            "rule_results": rule_results,
        }

    def add_rule(self, category: str, rule: dict) -> str:
        """添加规则"""
        rule_id = rule.get("rule_id", "")
        if not rule_id:
            rule_id = f"{category}_{len(self._rules) + 1}"

        new_rule = Rule(
            rule_id=rule_id,
            category=category,
            description=rule.get("description", ""),
            condition=rule.get("condition", ""),
            action=rule.get("action", "score_modifier"),
            weight=rule.get("weight", 1.0),
            enabled=rule.get("enabled", True),
            score_modifier=rule.get("score_modifier", 0.0),
        )

        self._rules[rule_id] = new_rule

        if category not in self._rule_categories:
            self._rule_categories[category] = []
        if rule_id not in self._rule_categories[category]:
            self._rule_categories[category].append(rule_id)

        return rule_id

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        if rule_id not in self._rules:
            return False
        self._rules[rule_id].enabled = False
        return True

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        if rule_id not in self._rules:
            return False
        self._rules[rule_id].enabled = True
        return True

    def validate_creative(self, variant: dict) -> dict[str, Any]:
        """综合验证创意

        返回 {pass: bool, warnings: list, score: float}
        """
        policy_result = self.check_compliance(variant, "policy")

        creative_categories = ["creatives", "feed", "reels", "stories"]
        creative_type = variant.get("creative_type", "feed")

        if creative_type == "reels":
            check_categories = ["creatives", "reels"]
        elif creative_type == "stories":
            check_categories = ["creatives", "stories"]
        else:
            check_categories = ["creatives", "feed"]

        score_result = self.apply_rules(variant, check_categories)

        all_warnings = list(policy_result["warnings"]) + list(score_result["warnings"])
        passed = policy_result["pass"]

        return {
            "pass": passed,
            "warnings": all_warnings,
            "score": score_result["score"],
            "policy_pass": policy_result["pass"],
            "policy_violations": policy_result["violations"],
            "creative_score": score_result["score"],
            "categories_checked": check_categories + ["policy"],
        }

    def get_all_categories(self) -> list[str]:
        """获取所有规则分类"""
        return list(self._rule_categories.keys())

    def get_rule_stats(self) -> dict[str, Any]:
        """获取规则统计"""
        stats: dict[str, Any] = {
            "total_rules": len(self._rules),
            "enabled_rules": 0,
            "disabled_rules": 0,
            "by_category": {},
            "by_action": {},
        }

        for rule in self._rules.values():
            if rule.enabled:
                stats["enabled_rules"] += 1
            else:
                stats["disabled_rules"] += 1

            if rule.category not in stats["by_category"]:
                stats["by_category"][rule.category] = 0
            stats["by_category"][rule.category] += 1

            if rule.action not in stats["by_action"]:
                stats["by_action"][rule.action] = 0
            stats["by_action"][rule.action] += 1

        return stats
