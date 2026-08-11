"""5个新增模块的单元测试（全部 mock，无真实 Facebook API 调用）

运行：
    pytest tests/test_new_modules.py -v
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Setup import path ──────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# ── Load modules via importlib (绕过数字前缀模块名语法限制) ───────────────────

# CreativeGene 用 __import__ 绕过
_gene_mod = __import__(
    "market_ops.creative_growth_loop.03_gene.gene_extractor",
    fromlist=["CreativeGene"]
)
CreativeGene = _gene_mod.CreativeGene

_copy_mod = importlib.import_module(
    "market_ops.creative_growth_loop.05_prompt.copy_generator"
)
CopyGenerator = _copy_mod.CopyGenerator
AdCopy = _copy_mod.AdCopy
CopyVariant = _copy_mod.CopyVariant

_matrix_mod = importlib.import_module(
    "market_ops.creative_growth_loop.05_prompt.creative_strategy_matrix"
)
CreativeStrategyMatrix = _matrix_mod.CreativeStrategyMatrix
CreativeStrategy = _matrix_mod.CreativeStrategy

_strategy_mod = importlib.import_module(
    "market_ops.creative_growth_loop.14_publish.campaign_strategy"
)
CampaignStrategyBuilder = _strategy_mod.CampaignStrategyBuilder
CampaignConfig = _strategy_mod.CampaignConfig
AdSetConfig = _strategy_mod.AdSetConfig
TargetingConfig = _strategy_mod.TargetingConfig
CampaignStrategy = _strategy_mod.CampaignStrategy
CampaignObjective = _strategy_mod.CampaignObjective
OptimizationGoal = _strategy_mod.OptimizationGoal
BidStrategy = _strategy_mod.BidStrategy

_kpi_mod = importlib.import_module("market_ops.kpi_action_rulebook")
KpiActionRulebook = _kpi_mod.KpiActionRulebook
KpiRule = _kpi_mod.KpiRule
KpiMetric = _kpi_mod.KpiMetric
ActionType = _kpi_mod.ActionType
Severity = _kpi_mod.Severity

_boundary_mod = importlib.import_module("market_ops.decision_boundary")
DecisionBoundary = _boundary_mod.DecisionBoundary
DecisionCategory = _boundary_mod.DecisionCategory
DecisionDomain = _boundary_mod.DecisionDomain


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gene():
    """模拟 CreativeGene 对象"""
    from market_ops.creative_growth_loop.03_gene.gene_extractor import CreativeGene
    return CreativeGene(
        creative_id="gene_001",
        subject="cute dragon character",
        style="3D cartoon",
        hook="reward",
        reward="gold_dragon",
        emotion="excited",
        progress="lv100",
        overlay="+999",
        composition="center focus",
        camera="front",
        background="magical forest",
        palette="vibrant",
        character_pose="holding_reward",
    )


@pytest.fixture
def copy_gen():
    return CopyGenerator(output_dir="output/test_copy")


@pytest.fixture
def strategy_matrix():
    return CreativeStrategyMatrix()


@pytest.fixture
def strategy_builder():
    return CampaignStrategyBuilder()


@pytest.fixture
def rulebook():
    return KpiActionRulebook()


@pytest.fixture
def boundary():
    return DecisionBoundary()


# ===========================================================================
# Test: CopyGenerator
# ===========================================================================

class TestCopyGeneratorLanguageDetection:
    """语言推断"""

    def test_chinese_countries(self, copy_gen):
        assert copy_gen.get_language_for_country("CN") == "zh"
        assert copy_gen.get_language_for_country("HK") == "zh"
        assert copy_gen.get_language_for_country("TW") == "zh"
        assert copy_gen.get_language_for_country("SG") == "zh"

    def test_japanese(self, copy_gen):
        assert copy_gen.get_language_for_country("JP") == "ja"

    def test_korean(self, copy_gen):
        assert copy_gen.get_language_for_country("KR") == "ko"

    def test_spanish(self, copy_gen):
        assert copy_gen.get_language_for_country("ES") == "es"
        assert copy_gen.get_language_for_country("MX") == "es"
        assert copy_gen.get_language_for_country("AR") == "es"

    def test_unknown_defaults_english(self, copy_gen):
        assert copy_gen.get_language_for_country("XX") == "en"
        assert copy_gen.get_language_for_country("US") == "en"


class TestCopyGeneratorSingleCopy:
    """单条文案生成"""

    def test_generate_returns_adcopy(self, copy_gen, gene):
        copy = copy_gen.generate_ad_copy(gene, game_category="casual", country="US")
        assert isinstance(copy, AdCopy)
        assert copy.headline
        assert copy.primary_text
        assert copy.cta
        assert copy.language == "en"
        assert copy.hook_type == gene.hook
        assert copy.emotion == gene.emotion

    def test_japanese_language(self, copy_gen, gene):
        copy = copy_gen.generate_ad_copy(gene, country="JP")
        assert copy.language == "ja"
        assert copy.cta in CopyGenerator.CTA_TEMPLATES["ja"].values()

    def test_reward_replaced_in_headline(self, copy_gen, gene):
        """reward=gold_dragon → Headline 中应包含 Golden Dragon 或龙相关词"""
        copy = copy_gen.generate_ad_copy(gene, country="US")
        assert len(copy.headline) > 0
        # Headline 模板中 {reward} 应该被替换
        assert "{reward}" not in copy.headline

    def test_game_category_description(self, copy_gen, gene):
        copy = copy_gen.generate_ad_copy(gene, game_category="rpg", country="US")
        assert copy.description  # rpg 模板有内容
        assert len(copy.description) > 10

    def test_audience_adjustment(self, copy_gen, gene):
        copy_f2p = copy_gen.generate_ad_copy(gene, audience="f2p", country="US")
        copy_hardcore = copy_gen.generate_ad_copy(gene, audience="hardcore", country="US")
        # 不同受众的 primary_text 应该不完全相同
        assert copy_f2p.primary_text != copy_hardcore.primary_text

    def test_cta_type(self, copy_gen, gene):
        copy = copy_gen.generate_ad_copy(gene, cta_type="PLAY_NOW")
        assert copy.cta in ["Play Now", "今すぐプレイ", "지금 플레이"]  # 任何语言的对应CTA

    def test_all_cta_types_available(self, copy_gen, gene):
        for cta in ["INSTALL_MOBILE_APP", "PLAY_NOW", "DOWNLOAD", "GET_STARTED", "TRY_IT"]:
            copy = copy_gen.generate_ad_copy(gene, cta_type=cta)
            assert copy.cta, f"CTA {cta} should produce non-empty cta"


class TestCopyGeneratorVariants:
    """多变体生成"""

    def test_generate_variants_count(self, copy_gen, gene):
        variants = copy_gen.generate_variants(gene, count=5)
        assert len(variants) == 5
        assert all(isinstance(v, CopyVariant) for v in variants)

    def test_variants_have_unique_ids(self, copy_gen, gene):
        variants = copy_gen.generate_variants(gene, count=5)
        ids = [v.variant_id for v in variants]
        assert len(ids) == len(set(ids)), "variant_ids 应该唯一"

    def test_variants_have_different_ctas(self, copy_gen, gene):
        """5个变体应该轮换使用不同CTA类型"""
        variants = copy_gen.generate_variants(gene, count=5)
        ctas = [v.copies.cta for v in variants]
        # 至少有一个以上的不同 CTA
        assert len(set(ctas)) > 1

    def test_extract_methods(self, copy_gen, gene):
        variants = copy_gen.generate_variants(gene, count=3)
        assert len(copy_gen.extract_headlines(variants)) == 3
        assert len(copy_gen.extract_primary_texts(variants)) == 3
        assert len(copy_gen.extract_descriptions(variants)) == 3
        assert len(copy_gen.extract_ctas(variants)) == 3


class TestCopyGeneratorMultiLanguage:
    """多语言批量生成"""

    def test_multi_language(self, copy_gen, gene):
        result = copy_gen.generate_multi_language(
            gene,
            game_category="casual",
            countries=["US", "JP", "CN"],
        )
        assert set(result.keys()) == {"US", "JP", "CN"}
        assert result["US"].language == "en"
        assert result["JP"].language == "ja"
        assert result["CN"].language == "zh"


# ===========================================================================
# Test: CreativeStrategyMatrix
# ===========================================================================

class TestStrategyMatrixLookup:
    """策略查找"""

    def test_default_strategy(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "US", "casual")
        assert isinstance(strat, CreativeStrategy)
        assert strat.style == "3D cartoon"
        assert strat.country == "US"

    def test_unknown_game_defaults(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("unknown_game", "US")
        assert strat.style == "3D cartoon"  # 使用默认

    def test_unknown_country_defaults(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "XX")
        assert strat.country == "XX"
        assert strat.color_palette == "vibrant"  # 默认美国偏好

    def test_rpg_uses_dark_fantasy(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("rpg", "US")
        assert strat.style == "dark fantasy"

    def test_strategy_action(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "US")
        params = strat.to_prompt_params()
        assert "style" in params
        assert "emotion" in params
        assert "palette" in params


class TestStrategyMatrixCountryPreference:
    """国家视觉偏好"""

    def test_japan_pastel(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "JP")
        assert strat.color_palette == "pastel"
        assert strat.emotion == "curious"
        assert strat.lighting == "soft"

    def test_korea_vibrant_backlit(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "KR")
        assert strat.color_palette == "vibrant"
        assert strat.emotion == "wow"
        assert strat.lighting == "backlit"

    def test_germany_cool(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "DE")
        assert strat.color_palette == "cool"
        assert strat.emotion == "curious"

    def test_france_dark(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "FR")
        assert strat.color_palette == "dark"
        assert strat.emotion == "mysterious"

    def test_emotion_override(self, strategy_matrix):
        """override_emotion 参数可以覆盖国家偏好"""
        strat = strategy_matrix.get_strategy("casual", "US", override_emotion="panic")
        assert strat.emotion == "panic"


class TestStrategyMatrixAudience:
    """受众调整"""

    def test_hardcore_complexity(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "US", audience="hardcore")
        assert strat.negative_prompt  # 有负向提示词

    def test_f2p_simplicity(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "US", audience="f2p")
        assert "crowded" in strat.negative_prompt or "complex" in strat.negative_prompt


class TestStrategyMatrixABTesting:
    """A/B变体生成"""

    def test_ab_variants_count(self, strategy_matrix):
        variants = strategy_matrix.get_ab_test_strategies("casual", "US", n_variants=3)
        assert len(variants) == 3

    def test_ab_variants_different_emotions(self, strategy_matrix):
        variants = strategy_matrix.get_ab_test_strategies("casual", "US", n_variants=5)
        emotions = [v[1].emotion for v in variants]
        assert len(set(emotions)) > 1, "A/B变体应该有不同情绪"


class TestStrategyMatrixExplain:
    """策略解释"""

    def test_explain_returns_string(self, strategy_matrix):
        strat = strategy_matrix.get_strategy("casual", "US")
        explanation = strategy_matrix.explain_strategy(strat)
        assert isinstance(explanation, str)
        assert "## 创意策略解释" in explanation
        assert "Style" in explanation
        assert "Country" in explanation


class TestStrategyMatrixCatalog:
    """支持列表"""

    def test_supported_games(self, strategy_matrix):
        games = strategy_matrix.get_all_supported_games()
        assert "casual" in games
        assert "rpg" in games
        assert "puzzle" in games

    def test_supported_countries(self, strategy_matrix):
        countries = strategy_matrix.get_all_supported_countries()
        assert "US" in countries
        assert "JP" in countries
        assert "CN" in countries
        assert len(countries) >= 20  # 至少20个

    def test_supported_audiences(self, strategy_matrix):
        audiences = strategy_matrix.get_all_supported_audiences()
        assert set(audiences) == {"casual", "hardcore", "f2p", "midcore"}


# ===========================================================================
# Test: CampaignStrategyBuilder
# ===========================================================================

class TestCampaignStrategySelection:
    """策略选择"""

    def test_low_budget_abos(self, strategy_builder):
        """预算<$500 → 强制ABO"""
        strat = strategy_builder.select_campaign_strategy(budget=100, adset_count=1)
        assert strat == CampaignStrategy.ABO

    def test_high_budget_cbo(self, strategy_builder):
        """预算>=$500 且 adset>=3 → CBO"""
        strat = strategy_builder.select_campaign_strategy(budget=500, adset_count=3)
        assert strat == CampaignStrategy.CBO

    def test_advantage_plus(self, strategy_builder):
        strat = strategy_builder.select_campaign_strategy(budget=100, adset_count=1, use_advantage_plus=True)
        assert strat == CampaignStrategy.ASC


class TestTargetingBuilding:
    """Targeting 构建"""

    def test_build_basic_targeting(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US", "JP"],
            game_category="casual",
        )
        assert isinstance(targeting, TargetingConfig)
        assert targeting.countries == ["US", "JP"]
        assert targeting.age_min == 18
        assert targeting.age_max == 65

    def test_broad_no_interests(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US"],
            game_category="casual",
            is_broad=True,
        )
        assert targeting.is_broad
        assert len(targeting.interests) == 0  # Broad时不设兴趣

    def test_interests_for_game_category(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US"],
            game_category="rpg",
            is_broad=False,
        )
        assert len(targeting.interests) > 0
        assert any("RPG" in i["name"] or "fantasy" in i["name"].lower() for i in targeting.interests)

    def test_language_inference(self, strategy_builder):
        targeting_jp = strategy_builder.build_targeting(countries=["JP"])
        assert "ja_JP" in targeting_jp.languages

        targeting_cn = strategy_builder.build_targeting(countries=["CN"])
        assert "zh_CN" in targeting_cn.languages

    def test_custom_audiences(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US"],
            custom_audience_ids=["aud_123", "aud_456"],
        )
        assert len(targeting.custom_audiences) == 2
        assert targeting.custom_audiences[0]["id"] == "aud_123"

    def test_lookalike_audiences(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US"],
            lookalike_audience_ids=["la_789"],
        )
        assert len(targeting.lookalike_audiences) == 1

    def test_exclusions(self, strategy_builder):
        targeting = strategy_builder.build_targeting(
            countries=["US"],
            exclude_audience_ids=["excl_001"],
        )
        assert len(targeting.excluded_custom_audiences) == 1

    def test_targeting_to_facebook_spec(self, strategy_builder):
        targeting = strategy_builder.build_targeting(countries=["US", "GB"])
        spec = targeting.to_facebook_spec()
        assert "geo_locations" in spec
        assert "countries" in spec["geo_locations"]
        assert spec["age_min"] == 18
        assert spec["age_max"] == 65


class TestBidStrategy:
    """出价策略"""

    def test_cost_cap_with_target_cpi(self, strategy_builder):
        strat, bid, cap = strategy_builder.select_bid_strategy(
            daily_budget=100,
            target_cpi=2.5,
        )
        assert strat == BidStrategy.COST_CAP
        assert cap == 250  # 2.5美元 → 250分

    def test_no_cap_by_default(self, strategy_builder):
        strat, bid, cap = strategy_builder.select_bid_strategy(daily_budget=100)
        assert strat == BidStrategy.LOWEST_COST_WITHOUT_CAP


class TestPlacementSelection:
    """版位选择"""

    def test_automatic_placements(self, strategy_builder):
        placements = strategy_builder.select_placements("casual", use_automatic_placements=True)
        assert placements == []

    def test_manual_placements(self, strategy_builder):
        placements = strategy_builder.select_placements("casual", use_automatic_placements=False)
        assert "facebook_feed" in placements
        assert "instagram_feed" in placements

    def test_hyper_casual_audience_network(self, strategy_builder):
        placements = strategy_builder.select_placements("hyper_casual", use_automatic_placements=False)
        assert "audience_network_rewarded_video" in placements


class TestFullCampaignBuilder:
    """完整 Campaign + AdSet 构建"""

    def test_build_campaign_config(self, strategy_builder):
        campaign = strategy_builder.build_campaign(
            name="TestCampaign",
            strategy=CampaignStrategy.ABO,
        )
        assert campaign.name == "TestCampaign"
        assert campaign.strategy == CampaignStrategy.ABO
        assert campaign.status == "PAUSED"

    def test_build_adset_config(self, strategy_builder):
        adset = strategy_builder.build_adset(
            name="TestAdSet",
            campaign_id="camp_123",
            daily_budget=50.0,
            countries=["US"],
            game_category="casual",
        )
        assert adset.name == "TestAdSet"
        assert adset.daily_budget == 5000  # $50 → 5000分
        assert adset.optimization_goal == OptimizationGoal.APP_INSTALLS

    def test_build_full_campaign_abos(self, strategy_builder):
        result = strategy_builder.build_full_campaign(
            project_name="P04",
            daily_budget=100.0,
            countries=["US", "JP"],
            game_category="casual",
            adset_count=1,
        )
        assert "campaign" in result
        assert "adsets" in result
        assert result["campaign"].strategy == CampaignStrategy.ABO
        # ABO → 每个国家一个 AdSet
        assert len(result["adsets"]) == 2

    def test_build_full_campaign_cbo(self, strategy_builder):
        result = strategy_builder.build_full_campaign(
            project_name="P04",
            daily_budget=500.0,
            countries=["US", "JP"],
            game_category="casual",
            adset_count=3,
        )
        assert result["campaign"].strategy == CampaignStrategy.CBO
        # CBO → 一个 AdSet 包含所有国家
        assert len(result["adsets"]) == 1

    def test_broad_campaign(self, strategy_builder):
        result = strategy_builder.build_full_campaign(
            project_name="P04",
            daily_budget=100.0,
            countries=["US"],
            game_category="casual",
            adset_count=1,
            is_broad=True,
        )
        assert result["adsets"][0].targeting.is_broad


# ===========================================================================
# Test: KpiActionRulebook
# ===========================================================================

class TestKpiRuleConditions:
    """规则条件匹配"""

    def test_ctr_too_low_triggered(self, rulebook):
        rule = rulebook.get_rules_by_metric(KpiMetric.CTR)[0]
        assert rule.matches(0.3)  # CTR < 0.5%

    def test_ctr_not_triggered(self, rulebook):
        rule = rulebook.get_rules_by_metric(KpiMetric.CTR)[0]
        assert not rule.matches(1.5)  # CTR > 0.5%

    def test_cpm_too_high_triggered(self, rulebook):
        rule = rulebook.get_rules_by_metric(KpiMetric.CPM)[0]
        assert rule.matches(50.0)  # CPM > $30

    def test_roas_low_triggered(self, rulebook):
        rule = rulebook.get_rules_by_metric(KpiMetric.ROAS)[0]
        assert rule.matches(0.3)  # ROAS < 0.5

    def test_frequency_high_triggered(self, rulebook):
        rule = rulebook.get_rules_by_metric(KpiMetric.FREQUENCY)[0]
        assert rule.matches(5.0)  # freq > 3


class TestKpiRulebookEvaluate:
    """规则评估"""

    def test_evaluate_ctr_low_triggers_change_creative(self, rulebook):
        metrics = {
            KpiMetric.CTR: 0.3,
            KpiMetric.SPEND: 100.0,
            KpiMetric.IMPRESSIONS: 10000,
        }
        triggered = rulebook.evaluate(metrics)
        assert len(triggered) > 0
        assert triggered[0].action == ActionType.CHANGE_CREATIVE

    def test_evaluate_roas_critical_triggers_pause(self, rulebook):
        metrics = {
            KpiMetric.ROAS: 0.3,
            KpiMetric.SPEND: 100.0,
            KpiMetric.IMPRESSIONS: 10000,
        }
        triggered = rulebook.evaluate(metrics)
        assert triggered[0].action == ActionType.PAUSE

    def test_evaluate_all_normal_returns_hold(self, rulebook):
        """正常指标 → 返回 hold"""
        metrics = {
            KpiMetric.CTR: 1.5,
            KpiMetric.CPM: 15.0,
            KpiMetric.CPI: 2.0,
            KpiMetric.ROAS: 1.5,
            KpiMetric.FREQUENCY: 1.5,
            KpiMetric.SPEND: 100.0,
            KpiMetric.IMPRESSIONS: 10000,
        }
        result = rulebook.evaluate_with_context(metrics)
        assert result["decision"] == ActionType.HOLD

    def test_data_blocked_when_low_spend(self, rulebook):
        metrics = {
            KpiMetric.CTR: 0.1,
            KpiMetric.SPEND: 5.0,  # 低于 min_spend
            KpiMetric.IMPRESSIONS: 100,
        }
        result = rulebook.evaluate_with_context(metrics, min_spend=10.0, min_impressions=1000)
        assert result["decision"] == ActionType.DATA_BLOCKED

    def test_priority_order(self, rulebook):
        """同时触发多个规则时，按优先级排序"""
        metrics = {
            KpiMetric.CTR: 0.3,
            KpiMetric.CPI: 10.0,
            KpiMetric.SPEND: 100.0,
            KpiMetric.IMPRESSIONS: 10000,
        }
        triggered = rulebook.evaluate(metrics)
        assert len(triggered) >= 2
        # CTR规则的优先级应该 < CPI规则（数字小=优先级高）
        assert triggered[0].priority <= triggered[1].priority


class TestKpiRulebookContext:
    """上下文感知评估"""

    def test_creative_age_warning(self, rulebook):
        """素材超过7天，即使其他指标正常也建议换素材"""
        metrics = {
            KpiMetric.CTR: 1.0,
            KpiMetric.CPM: 15.0,
            KpiMetric.CPI: 2.0,
            KpiMetric.ROAS: 1.2,
            KpiMetric.SPEND: 100.0,
            KpiMetric.IMPRESSIONS: 10000,
        }
        result = rulebook.evaluate_with_context(metrics, creative_age_days=10)
        # 应该有素材老化提示
        age_note = any("CREATIVE_AGE" in e for e in result["explanations"])
        assert age_note


class TestKpiRulebookQueries:
    """规则查询"""

    def test_get_rules_by_action(self, rulebook):
        change_creative_rules = rulebook.get_rules_by_action(ActionType.CHANGE_CREATIVE)
        assert len(change_creative_rules) > 3  # 至少多个规则推荐换素材

    def test_get_critical_rules(self, rulebook):
        critical = rulebook.get_critical_rules()
        assert all(r.severity == Severity.CRITICAL for r in critical)

    def test_export_rules(self, rulebook):
        rules = rulebook.export_rules()
        assert len(rules) >= 15  # 至少15条规则
        assert all("rule_id" in r for r in rules)
        assert all("action" in r for r in rules)
        assert all("anti_action" in r for r in rules)


class TestKpiRulebookCustomThresholds:
    """自定义阈值"""

    def test_custom_threshold_override(self):
        custom = {"CTR_TOO_LOW": {"threshold_value": 1.0}}  # 把CTR阈值从0.5改为1.0
        rb = KpiActionRulebook(custom_thresholds=custom)
        metrics = {KpiMetric.CTR: 0.8, KpiMetric.SPEND: 100.0, KpiMetric.IMPRESSIONS: 10000}
        triggered = rb.evaluate(metrics)
        assert triggered[0].rule_id == "CTR_TOO_LOW"


# ===========================================================================
# Test: DecisionBoundary
# ===========================================================================

class TestBoundaryLookup:
    """边界查询"""

    def test_image_style_is_ai(self, boundary):
        assert boundary.is_ai_decision(DecisionCategory.IMAGE_STYLE)
        assert boundary.get_domain(DecisionCategory.IMAGE_STYLE) == DecisionDomain.AI

    def test_budget_allocation_is_rule(self, boundary):
        assert boundary.is_rule_decision(DecisionCategory.BUDGET_ALLOCATION)
        assert boundary.get_domain(DecisionCategory.BUDGET_ALLOCATION) == DecisionDomain.RULE

    def test_audience_selection_is_hybrid(self, boundary):
        assert boundary.is_hybrid_decision(DecisionCategory.AUDIENCE_SELECTION)
        assert boundary.get_domain(DecisionCategory.AUDIENCE_SELECTION) == DecisionDomain.HYBRID

    def test_pause_is_rule(self, boundary):
        assert boundary.is_rule_decision(DecisionCategory.PAUSE_DECISION)
        assert boundary.get_domain(DecisionCategory.PAUSE_DECISION) == DecisionDomain.RULE

    def test_kill_is_rule(self, boundary):
        assert boundary.is_rule_decision(DecisionCategory.KILL_DECISION)


class TestBoundaryCatalog:
    """分类统计"""

    def test_ai_categories(self, boundary):
        ai_cats = boundary.get_ai_categories()
        assert DecisionCategory.HEADLINE in ai_cats
        assert DecisionCategory.PRIMARY_TEXT in ai_cats
        assert DecisionCategory.PROMPT_GENERATION in ai_cats
        assert len(ai_cats) >= 5

    def test_rule_categories(self, boundary):
        rule_cats = boundary.get_rule_categories()
        assert DecisionCategory.BUDGET_ALLOCATION in rule_cats
        assert DecisionCategory.PAUSE_DECISION in rule_cats
        assert DecisionCategory.KILL_DECISION in rule_cats
        assert len(rule_cats) >= 5

    def test_hybrid_categories(self, boundary):
        hybrid_cats = boundary.get_hybrid_categories()
        assert DecisionCategory.AUDIENCE_SELECTION in hybrid_cats
        assert DecisionCategory.COUNTRY_SELECTION in hybrid_cats
        assert DecisionCategory.WINNER_IDENTIFICATION in hybrid_cats
        assert len(hybrid_cats) >= 3


class TestBoundaryAudit:
    """边界审计"""

    def test_audit_valid(self, boundary):
        result = boundary.audit_decision(
            DecisionCategory.HEADLINE,
            DecisionDomain.AI,
        )
        assert result["valid"] is True

    def test_audit_invalid(self, boundary):
        """如果 HEADLINE 被规则域执行，应该被标记为无效"""
        result = boundary.audit_decision(
            DecisionCategory.HEADLINE,
            DecisionDomain.RULE,
        )
        assert result["valid"] is False
        assert "WARNING" in result["message"]


class TestBoundaryExport:
    """导出映射表"""

    def test_export_boundary_map(self, boundary):
        data = boundary.export_boundary_map()
        assert len(data) >= 15  # 至少15个决策类别
        assert all("category" in row for row in data)
        assert all("domain" in row for row in data)
        assert all("responsible_module" in row for row in data)

    def test_get_all_assignments(self, boundary):
        assignments = boundary.get_all_assignments()
        assert len(assignments) >= 15
