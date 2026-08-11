"""快速验证脚本 — 所有新模块核心逻辑"""
import sys
import importlib
sys.path.insert(0, "src")

print("=" * 60)
print("验证 5 个新模块的核心逻辑")
print("=" * 60)

# 用 __import__ 绕过 Python 数字前缀模块名语法限制
gene_mod = __import__("market_ops.creative_growth_loop.03_gene.gene_extractor",
                       fromlist=["CreativeGene"])
CreativeGene = gene_mod.CreativeGene

# Test 1: copy_generator
copy_mod = importlib.import_module("market_ops.creative_growth_loop.05_prompt.copy_generator")
CopyGenerator = copy_mod.CopyGenerator
gen = CopyGenerator()
lang_cn = gen.get_language_for_country("CN")
lang_jp = gen.get_language_for_country("JP")
lang_us = gen.get_language_for_country("US")
print(f"[copy_generator] CN={lang_cn} JP={lang_jp} US={lang_us}")
assert lang_cn == "zh" and lang_jp == "ja" and lang_us == "en", "Language detection failed"
print("  PASS: 语言检测")

# Test 2: creative_strategy_matrix
matrix_mod = importlib.import_module("market_ops.creative_growth_loop.05_prompt.creative_strategy_matrix")
CreativeStrategyMatrix = matrix_mod.CreativeStrategyMatrix
mx = CreativeStrategyMatrix()
strat_jp = mx.get_strategy("casual", "JP")
strat_de = mx.get_strategy("rpg", "DE")
strat_us = mx.get_strategy("casual", "US")
print(f"[creative_strategy_matrix] JP: {strat_jp.color_palette}/{strat_jp.emotion}, DE: {strat_de.color_palette}, US: {strat_us.color_palette}")
assert strat_jp.color_palette == "pastel" and strat_jp.emotion == "curious"
assert strat_de.color_palette == "cool"
assert strat_us.color_palette == "vibrant"
print("  PASS: 国家视觉偏好")

ab_variants = mx.get_ab_test_strategies("casual", "US", n_variants=3)
emotions = [v[1].emotion for v in ab_variants]
print(f"  A/B variants emotions: {emotions}")
assert len(set(emotions)) > 1, "A/B variants should have different emotions"
print("  PASS: A/B变体生成")

# Test 3: campaign_strategy
strategy_mod = importlib.import_module("market_ops.creative_growth_loop.14_publish.campaign_strategy")
CampaignStrategyBuilder = strategy_mod.CampaignStrategyBuilder
CampaignStrategy = strategy_mod.CampaignStrategy
TargetingConfig = strategy_mod.TargetingConfig
CampaignConfig = strategy_mod.CampaignConfig
AdSetConfig = strategy_mod.AdSetConfig
sb = CampaignStrategyBuilder()
abo = sb.select_campaign_strategy(100, 1)
cbo = sb.select_campaign_strategy(500, 3)
asc = sb.select_campaign_strategy(100, 1, use_advantage_plus=True)
print(f"[campaign_strategy] ABO={abo} CBO={cbo} ASC={asc}")
assert abo == CampaignStrategy.ABO
assert cbo == CampaignStrategy.CBO
assert asc == CampaignStrategy.ASC
print("  PASS: 策略选择")

targeting = sb.build_targeting(countries=["US", "JP"], game_category="rpg", is_broad=False)
print(f"  Targeting: countries={targeting.countries}, interests={len(targeting.interests)}, langs={targeting.languages}")
assert targeting.countries == ["US", "JP"]
assert len(targeting.interests) > 0
assert "ja_JP" in targeting.languages
print("  PASS: Targeting构建")

full = sb.build_full_campaign("P04", 100, ["US", "JP"], "casual", adset_count=1)
assert full["campaign"].strategy == CampaignStrategy.ABO
assert len(full["adsets"]) == 2  # 每个国家一个AdSet
print(f"  Full campaign: strategy={full['campaign'].strategy}, adsets={len(full['adsets'])}")
print("  PASS: 完整Campaign构建")

# Test 4: kpi_action_rulebook
kpi_mod = importlib.import_module("market_ops.kpi_action_rulebook")
KpiActionRulebook = kpi_mod.KpiActionRulebook
KpiMetric = kpi_mod.KpiMetric
ActionType = kpi_mod.ActionType
Severity = kpi_mod.Severity
rb = KpiActionRulebook()

metrics_low_ctr = {
    KpiMetric.CTR: 0.3,
    KpiMetric.SPEND: 100.0,
    KpiMetric.IMPRESSIONS: 10000,
}
result = rb.evaluate_with_context(metrics_low_ctr)
print(f"[kpi_action_rulebook] CTR=0.3% -> {result['decision']}")
assert result["decision"] == ActionType.CHANGE_CREATIVE, f"Expected CHANGE_CREATIVE, got {result['decision']}"
print("  PASS: CTR低 → 换素材")

metrics_roas_low = {
    KpiMetric.ROAS: 0.3,
    KpiMetric.SPEND: 100.0,
    KpiMetric.IMPRESSIONS: 10000,
}
result2 = rb.evaluate_with_context(metrics_roas_low)
print(f"  ROAS=0.3 -> {result2['decision']}")
assert result2["decision"] == ActionType.PAUSE
print("  PASS: ROAS极低 → 暂停")

metrics_critical = {
    KpiMetric.CTR: 1.5,
    KpiMetric.CPM: 15.0,
    KpiMetric.CPI: 2.0,
    KpiMetric.ROAS: 1.5,
    KpiMetric.FREQUENCY: 1.5,
    KpiMetric.SPEND: 100.0,
    KpiMetric.IMPRESSIONS: 10000,
}
result3 = rb.evaluate_with_context(metrics_critical)
print(f"  全部正常 -> {result3['decision']}")
assert result3["decision"] == ActionType.HOLD
print("  PASS: 指标正常 → HOLD")

data_blocked = rb.evaluate_with_context(
    {KpiMetric.SPEND: 5.0, KpiMetric.IMPRESSIONS: 100, KpiMetric.CTR: 0.1},
    min_spend=10.0, min_impressions=1000
)
print(f"  数据不足 -> {data_blocked['decision']}")
assert data_blocked["decision"] == ActionType.DATA_BLOCKED
print("  PASS: 数据不足 → DATA_BLOCKED")

rules = rb.export_rules()
print(f"  总规则数: {len(rules)}")
assert len(rules) >= 15
print("  PASS: 规则导出")

# Test 5: decision_boundary
boundary_mod = importlib.import_module("market_ops.decision_boundary")
DecisionBoundary = boundary_mod.DecisionBoundary
DecisionCategory = boundary_mod.DecisionCategory
DecisionDomain = boundary_mod.DecisionDomain
db = DecisionBoundary()
print(f"[decision_boundary] HEADLINE={db.get_domain(DecisionCategory.HEADLINE)}, PAUSE={db.get_domain(DecisionCategory.PAUSE_DECISION)}, AUDIENCE={db.get_domain(DecisionCategory.AUDIENCE_SELECTION)}")
assert db.get_domain(DecisionCategory.HEADLINE) == DecisionDomain.AI
assert db.get_domain(DecisionCategory.PAUSE_DECISION) == DecisionDomain.RULE
assert db.get_domain(DecisionCategory.AUDIENCE_SELECTION) == DecisionDomain.HYBRID
print("  PASS: 决策域归属")

ai_cats = db.get_ai_categories()
rule_cats = db.get_rule_categories()
hybrid_cats = db.get_hybrid_categories()
print(f"  AI域:{len(ai_cats)} 规则域:{len(rule_cats)} 混合域:{len(hybrid_cats)}")
assert len(ai_cats) >= 5
assert len(rule_cats) >= 5
assert len(hybrid_cats) >= 3
print("  PASS: 域分类统计")

audit_valid = db.audit_decision(DecisionCategory.HEADLINE, DecisionDomain.AI)
audit_invalid = db.audit_decision(DecisionCategory.HEADLINE, DecisionDomain.RULE)
assert audit_valid["valid"] is True
assert audit_invalid["valid"] is False
print("  PASS: 边界审计")

print()
print("=" * 60)
print("ALL 5 MODULES VERIFIED")
print("=" * 60)
