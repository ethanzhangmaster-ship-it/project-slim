"""E11 Phase 4.1 — Creative Analysis Core Layer 测试（IAP 版）。

测试覆盖：
  1. 数据模型：VisualFeatures, HookFeatures, GameplayFeatures, MonetizationFeatures, CreativeAnalysis
  2. VisualAnalyzer — composition/color/emotion/quality
  3. HookAnalyzer — hook_type + hook_strength + purchase_intent
  4. GameplayAnalyzer — progression/economy/retention_signal
  5. MonetizationAnalyzer — purchase_trigger/iap_visibility/value_perception/urgency
  6. CreativeDNAExtractor — 分析 → DNA 提取
  7. AnalysisEngine — 统一分析引擎
  8. Validator — 分析质量验证
  9. PRD 验收：10 Winner + 10 Loser 区分度

目标：100+ tests PASS
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from market_ops.creative_repository import (
    CreativeEntity, CreativeIdentity, CreativePerformance,
    AcquisitionData, RevenueData, CreativeAnalysis as EntityAnalysis,
    CreativeType, CreativeAsset, CreativeSources,
)

from market_ops.creative_intelligence import (
    # Models
    VisualFeatures, HookFeatures, GameplayFeatures, MonetizationFeatures,
    CreativeAnalysis, HookType, VisualSubject, ColorStyle,
    Composition, ColorProfile, EmotionProfile, QualityProfile,
    ProgressionProfile, EconomyProfile, RetentionSignal, PurchaseTrigger,
    # Analyzers
    VisualAnalyzer, HookAnalyzer, GameplayAnalyzer, MonetizationAnalyzer,
    # Extractor
    CreativeDNAExtractor, CreativeDNA,
    # Engine
    AnalysisEngine, AnalysisReport, ANALYSIS_WEIGHTS,
    # Validator
    Validator, ValidationReport,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_entity(
    creative_id: str = "MW_VIDEO_001",
    name: str = "test",
    ctype: CreativeType = CreativeType.VIDEO,
    spend: float = 5000, impressions: int = 50000, clicks: int = 2000, installs: int = 2000,
    iap_d30: float = 0, purchasers: int = 0, payer_rate: float = 0.0,
    hook_type: str = "", reward_type: str = "",
    video_dna: dict | None = None, style: str = "",
) -> CreativeEntity:
    return CreativeEntity(
        creative_asset_id=creative_id,
        identity=CreativeIdentity(name=name, type=ctype),
        sources=CreativeSources(),
        performance=CreativePerformance(
            acquisition=AcquisitionData(
                spend=spend, impressions=impressions, clicks=clicks,
                ctr=clicks / max(impressions, 1) * 100, installs=installs,
            ),
            revenue=RevenueData(
                iap_d1=0, iap_d7=0, iap_d30=iap_d30,
                ad_d1=0, ad_d7=0, ad_d30=0,
                purchases=int(purchasers), payer_count=int(purchasers),
                payer_rate=payer_rate,
            ),
        ),
        asset=CreativeAsset(),
        analysis=EntityAnalysis(
            hook_type=hook_type, reward_type=reward_type,
            image_dna={}, video_dna=video_dna or {}, style=style,
        ),
    )


def _winner_entity(**overrides) -> CreativeEntity:
    kwargs = dict(
        creative_id="MW_WINNER_001",
        name="collect_legendary_dragon_unlock",
        spend=10000, impressions=100000, clicks=4000, installs=4000,
        iap_d30=13000, purchasers=320, payer_rate=0.08,
        hook_type="COLLECTION", reward_type="LEGENDARY_ITEM",
        style="premium",
        video_dna={
            "subject": "character", "character_focus": 70,
            "saturation": 80, "contrast": 75, "premium_feeling": 85,
            "complexity": 0.4,
        },
    )
    kwargs.update(overrides)
    return _make_entity(**kwargs)


def _loser_entity(**overrides) -> CreativeEntity:
    kwargs = dict(
        creative_id="MW_LOSER_001",
        name="OMG_impossible_wow",
        spend=5000, impressions=200000, clicks=20000, installs=5000,
        iap_d30=2000, purchasers=25, payer_rate=0.005,
        hook_type="CURIOSITY", reward_type="UNKNOWN",
        style="high_contrast",
        video_dna={
            "subject": "mixed", "character_focus": 10,
            "saturation": 90, "contrast": 90, "premium_feeling": 20,
            "complexity": 0.9,
        },
    )
    kwargs.update(overrides)
    return _make_entity(**kwargs)


# ═══════════════════════════════════════════════════════════
# 1. Models Tests
# ═══════════════════════════════════════════════════════════

class TestComposition:
    def test_winner(self):
        c = Composition(center_focus="character", character_focus=70, gameplay_focus=60)
        d = c.to_dict()
        r = Composition.from_dict(d)
        assert r.character_focus == 70

    def test_defaults(self):
        c = Composition()
        assert c.center_focus == "mixed"


class TestColorProfile:
    def test_premium(self):
        c = ColorProfile(saturation=80, contrast=70, premium_feeling=90, style=ColorStyle.PREMIUM)
        d = c.to_dict()
        r = ColorProfile.from_dict(d)
        assert r.premium_feeling == 90
        assert r.style == ColorStyle.PREMIUM

    def test_defaults(self):
        c = ColorProfile()
        assert c.saturation == 0


class TestEmotionProfile:
    def test_dominant_desire(self):
        e = EmotionProfile(curiosity=30, achievement=40, desire=85)
        assert e.dominant_emotion == "desire"

    def test_dominant_curiosity(self):
        e = EmotionProfile(curiosity=90, achievement=20, desire=30)
        assert e.dominant_emotion == "curiosity"

    def test_serialization(self):
        e = EmotionProfile(curiosity=70, achievement=50, desire=80)
        d = e.to_dict()
        r = EmotionProfile.from_dict(d)
        assert r.desire == 80


class TestPurchaseTrigger:
    def test_dominant_rarity(self):
        pt = PurchaseTrigger(rarity=90, power=30, customization=20, collection=70, progression=30)
        assert pt.dominant_trigger == "rarity"

    def test_dominant_collection(self):
        pt = PurchaseTrigger(rarity=70, power=30, customization=40, collection=90, progression=50)
        assert pt.dominant_trigger == "collection"

    def test_trigger_strength(self):
        pt = PurchaseTrigger(rarity=90, power=40, customization=30, collection=70, progression=30)
        assert pt.trigger_strength > 50

    def test_serialization(self):
        pt = PurchaseTrigger(rarity=90, power=40, customization=30, collection=70, progression=30)
        d = pt.to_dict()
        r = PurchaseTrigger.from_dict(d)
        assert r.rarity == 90


class TestVisualFeatures:
    def test_visual_score(self):
        vf = VisualFeatures(
            composition=Composition(character_focus=70),
            color=ColorProfile(premium_feeling=85),
            emotion=EmotionProfile(desire=80),
            quality=QualityProfile(mobile_ad_fit=75),
        )
        assert vf.visual_score > 50

    def test_serialization(self):
        vf = VisualFeatures(
            composition=Composition(character_focus=70),
            color=ColorProfile(premium_feeling=85),
            emotion=EmotionProfile(desire=80),
            quality=QualityProfile(mobile_ad_fit=75),
        )
        d = vf.to_dict()
        r = VisualFeatures.from_dict(d)
        assert r.visual_score == vf.visual_score


class TestHookFeatures:
    def test_is_clickbait(self):
        hf = HookFeatures(
            hook_type=HookType.CURIOSITY, curiosity=90, purchase_intent=10,
        )
        assert hf.is_clickbait is True

    def test_is_clickbait_false(self):
        hf = HookFeatures(
            hook_type=HookType.COLLECTION, curiosity=50, purchase_intent=75,
        )
        assert hf.is_clickbait is False

    def test_is_iap_quality(self):
        hf = HookFeatures(
            hook_type=HookType.RARE_ITEM, hook_strength=85, purchase_intent=80,
        )
        assert hf.is_iap_quality is True

    def test_hook_score_clickbait_penalty(self):
        hf = HookFeatures(
            hook_type=HookType.CURIOSITY, curiosity=90, purchase_intent=10,
        )
        assert hf.hook_score == 15.0

    def test_serialization(self):
        hf = HookFeatures(
            hook_type=HookType.COLLECTION, hook_strength=80,
            curiosity=50, reward_expectation=85, purchase_intent=75,
        )
        d = hf.to_dict()
        r = HookFeatures.from_dict(d)
        assert r.hook_type == HookType.COLLECTION
        assert r.hook_score == hf.hook_score


class TestGameplayFeatures:
    def test_gameplay_score(self):
        gf = GameplayFeatures(
            progression=ProgressionProfile(level_growth=80, collection_growth=90),
            economy=EconomyProfile(rare_item=85, unlock=70),
            retention_signal=RetentionSignal(long_term_goal=75),
        )
        assert gf.gameplay_score > 60

    def test_serialization(self):
        gf = GameplayFeatures(
            progression=ProgressionProfile(level_growth=80),
            economy=EconomyProfile(rare_item=85),
            retention_signal=RetentionSignal(long_term_goal=75),
        )
        d = gf.to_dict()
        r = GameplayFeatures.from_dict(d)
        assert r.gameplay_score == gf.gameplay_score


class TestMonetizationFeatures:
    def test_monetization_score(self):
        mf = MonetizationFeatures(
            purchase_trigger=PurchaseTrigger(rarity=90, collection=70, progression=50),
            iap_visibility=80, value_perception=75, urgency=30,
        )
        assert mf.monetization_score > 50

    def test_is_high_monetization(self):
        mf = MonetizationFeatures(
            purchase_trigger=PurchaseTrigger(rarity=90, collection=70, progression=50),
            iap_visibility=80, value_perception=75, urgency=30,
        )
        assert mf.is_high_monetization is True

    def test_serialization(self):
        mf = MonetizationFeatures(
            purchase_trigger=PurchaseTrigger(rarity=90),
            iap_visibility=70, value_perception=60, urgency=20,
        )
        d = mf.to_dict()
        r = MonetizationFeatures.from_dict(d)
        assert r.monetization_score == mf.monetization_score


class TestCreativeAnalysis:
    def test_is_winner(self):
        ca = CreativeAnalysis(creative_id="MW_001", analysis_score=75)
        assert ca.is_winner is True

    def test_is_winner_false(self):
        ca = CreativeAnalysis(creative_id="MW_002", analysis_score=50)
        assert ca.is_winner is False

    def test_is_iap_quality(self):
        ca = CreativeAnalysis(
            creative_id="MW_001",
            monetization_features=MonetizationFeatures(
                purchase_trigger=PurchaseTrigger(rarity=90, collection=70),
                iap_visibility=80, value_perception=75, urgency=50,
            ),
            hook_features=HookFeatures(
                hook_type=HookType.COLLECTION, curiosity=50, purchase_intent=75,
            ),
        )
        assert ca.is_iap_quality is True

    def test_serialization(self):
        ca = CreativeAnalysis(
            creative_id="MW_001",
            visual_features=VisualFeatures(composition=Composition(character_focus=70)),
            hook_features=HookFeatures(hook_type=HookType.COLLECTION),
            analysis_score=75,
            insight="Strong IAP potential",
        )
        d = ca.to_dict()
        r = CreativeAnalysis.from_dict(d)
        assert r.creative_id == "MW_001"
        assert r.analysis_score == 75
        assert r.insight == "Strong IAP potential"


# ═══════════════════════════════════════════════════════════
# 2. VisualAnalyzer Tests
# ═══════════════════════════════════════════════════════════

class TestVisualAnalyzer:
    def test_analyze_winner(self):
        entity = _winner_entity()
        analyzer = VisualAnalyzer()
        vf = analyzer.analyze(entity)
        assert vf.composition.character_focus >= 60
        assert vf.color.premium_feeling >= 60
        assert vf.emotion.desire >= 60

    def test_analyze_loser(self):
        entity = _loser_entity()
        analyzer = VisualAnalyzer()
        vf = analyzer.analyze(entity)
        assert vf.composition.character_focus < 40
        assert vf.emotion.curiosity >= 80
        assert vf.emotion.desire < 40

    def test_analyze_batch(self):
        analyzer = VisualAnalyzer()
        results = analyzer.analyze_batch([_winner_entity(), _loser_entity()])
        assert len(results) == 2

    def test_emotion_from_hook_type(self):
        entity = _make_entity(
            creative_id="MW_RARE_001", name="rare_item_reveal",
            hook_type="RARE_ITEM",
        )
        analyzer = VisualAnalyzer()
        vf = analyzer.analyze(entity)
        assert vf.emotion.desire >= 70


# ═══════════════════════════════════════════════════════════
# 3. HookAnalyzer Tests
# ═══════════════════════════════════════════════════════════

class TestHookAnalyzer:
    def test_analyze_winner_collection(self):
        entity = _winner_entity()
        analyzer = HookAnalyzer()
        hf = analyzer.analyze(entity)
        assert hf.hook_type == HookType.COLLECTION
        assert hf.is_clickbait is False
        assert hf.purchase_intent >= 60

    def test_analyze_loser_curiosity(self):
        entity = _loser_entity()
        analyzer = HookAnalyzer()
        hf = analyzer.analyze(entity)
        assert hf.hook_type == HookType.CURIOSITY
        assert hf.is_clickbait is True
        assert hf.purchase_intent <= 20

    def test_analyze_rare_item(self):
        entity = _make_entity(
            creative_id="MW_RARE_001", name="rare_legendary_dragon",
            hook_type="RARE_ITEM",
        )
        analyzer = HookAnalyzer()
        hf = analyzer.analyze(entity)
        assert hf.hook_type == HookType.RARE_ITEM
        assert hf.purchase_intent >= 70

    def test_analyze_from_name(self):
        entity = _make_entity(
            creative_id="MW_NAME_001", name="impossible_merge_result", hook_type="",
        )
        analyzer = HookAnalyzer()
        hf = analyzer.analyze(entity)
        assert hf.hook_type == HookType.IMPOSSIBLE_RESULT

    def test_analyze_batch(self):
        analyzer = HookAnalyzer()
        results = analyzer.analyze_batch([_winner_entity(), _loser_entity()])
        assert len(results) == 2


# ═══════════════════════════════════════════════════════════
# 4. GameplayAnalyzer Tests
# ═══════════════════════════════════════════════════════════

class TestGameplayAnalyzer:
    def test_analyze_winner(self):
        entity = _winner_entity()
        analyzer = GameplayAnalyzer()
        gf = analyzer.analyze(entity)
        assert gf.progression.collection_growth >= 60
        assert gf.economy.rare_item >= 60
        assert gf.gameplay_score > 40

    def test_analyze_loser(self):
        entity = _loser_entity()
        analyzer = GameplayAnalyzer()
        gf = analyzer.analyze(entity)
        assert gf.gameplay_score < 60

    def test_analyze_batch(self):
        analyzer = GameplayAnalyzer()
        results = analyzer.analyze_batch([_winner_entity(), _loser_entity()])
        assert len(results) == 2


# ═══════════════════════════════════════════════════════════
# 5. MonetizationAnalyzer Tests
# ═══════════════════════════════════════════════════════════

class TestMonetizationAnalyzer:
    def test_analyze_winner(self):
        entity = _winner_entity()
        analyzer = MonetizationAnalyzer()
        mf = analyzer.analyze(entity)
        assert mf.is_high_monetization is True
        assert mf.purchase_trigger.rarity >= 70
        assert mf.iap_visibility >= 60

    def test_analyze_loser(self):
        entity = _loser_entity()
        analyzer = MonetizationAnalyzer()
        mf = analyzer.analyze(entity)
        assert mf.is_high_monetization is False
        assert mf.iap_visibility < 40

    def test_analyze_with_hook_features(self):
        entity = _winner_entity()
        hf = HookFeatures(
            hook_type=HookType.RARE_ITEM, hook_strength=85,
            curiosity=70, reward_expectation=90, purchase_intent=80,
        )
        analyzer = MonetizationAnalyzer()
        mf = analyzer.analyze(entity, hook_features=hf)
        assert mf.purchase_trigger.rarity >= 80

    def test_analyze_batch(self):
        analyzer = MonetizationAnalyzer()
        results = analyzer.analyze_batch([_winner_entity(), _loser_entity()])
        assert len(results) == 2


# ═══════════════════════════════════════════════════════════
# 6. CreativeDNAExtractor Tests
# ═══════════════════════════════════════════════════════════

class TestCreativeDNAExtractor:
    def test_extract_winner(self):
        engine = AnalysisEngine()
        entity = _winner_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=1.3)
        assert dna.hook == "collection_completion"
        assert dna.emotion == "achievement" or "collection" in dna.hook
        assert dna.roas_correlation > 0.5
        assert len(dna.visual_rules) > 0

    def test_extract_loser(self):
        engine = AnalysisEngine()
        entity = _loser_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=0.4)
        assert "clickbait" in dna.hook.lower() or "curiosity" in dna.hook.lower()
        assert dna.roas_correlation < 0.3
        assert len(dna.avoid_rules) > 0

    def test_extract_batch(self):
        engine = AnalysisEngine()
        entities = [_winner_entity(), _loser_entity()]
        report = engine.analyze_batch(entities)
        extractor = CreativeDNAExtractor()
        dnas = extractor.extract_batch(
            report.analyses,
            roas_map={"MW_WINNER_001": 1.3, "MW_LOSER_001": 0.4},
        )
        assert len(dnas) == 2
        assert dnas[0].roas_correlation > dnas[1].roas_correlation

    def test_serialization(self):
        dna = CreativeDNA(
            hook="rare_collection_reward",
            scene="fantasy treasure opening",
            emotion="desire",
            monetization="exclusive_character_unlock",
            visual_rules=["use large character"],
            avoid_rules=["avoid empty backgrounds"],
            roas_correlation=0.65,
        )
        d = dna.to_dict()
        r = CreativeDNA.from_dict(d)
        assert r.hook == "rare_collection_reward"
        assert r.roas_correlation == 0.65


# ═══════════════════════════════════════════════════════════
# 7. AnalysisEngine Tests
# ═══════════════════════════════════════════════════════════

class TestAnalysisEngine:
    def test_analyze_winner(self):
        engine = AnalysisEngine()
        entity = _winner_entity()
        analysis = engine.analyze(entity)
        assert analysis.creative_id == "MW_WINNER_001"
        assert analysis.analysis_score > 50
        assert analysis.is_winner is True
        assert analysis.visual_features.composition.character_focus >= 60
        assert analysis.hook_features.hook_type == HookType.COLLECTION
        assert analysis.monetization_features.is_high_monetization is True
        assert len(analysis.insight) > 0

    def test_analyze_loser(self):
        engine = AnalysisEngine()
        entity = _loser_entity()
        analysis = engine.analyze(entity)
        assert analysis.is_winner is False
        assert analysis.hook_features.is_clickbait is True
        assert analysis.analysis_score < 50
        assert "clickbait" in analysis.insight.lower()

    def test_analyze_batch(self):
        engine = AnalysisEngine()
        entities = [_winner_entity(), _loser_entity()]
        report = engine.analyze_batch(entities)
        assert report.total_analyzed == 2
        assert report.winner_count == 1
        assert report.clickbait_count == 1
        assert report.winner_rate == 0.5
        assert len(report.analyses) == 2
        assert len(report.dna_list) == 2
        assert len(report.errors) == 0

    def test_weights_sum_to_one(self):
        total = sum(ANALYSIS_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_report_to_dict(self):
        engine = AnalysisEngine()
        entity = _winner_entity()
        report = engine.analyze_batch([entity])
        d = report.to_dict()
        assert d["total_analyzed"] == 1
        assert d["winner_count"] == 1

    def test_report_to_summary(self):
        engine = AnalysisEngine()
        entity = _winner_entity()
        report = engine.analyze_batch([entity])
        summary = report.to_summary()
        assert "Creative Analysis Report" in summary


# ═══════════════════════════════════════════════════════════
# 8. Validator Tests
# ═══════════════════════════════════════════════════════════

class TestValidator:
    def test_validate_normal(self):
        engine = AnalysisEngine()
        validator = Validator()
        entities = [_winner_entity(), _loser_entity()]
        report = engine.analyze_batch(entities)
        quality = validator.validate(report.analyses)
        assert quality.total_results == 2
        assert quality.winner_count == 1
        assert quality.clickbait_count == 1

    def test_validate_empty(self):
        validator = Validator()
        quality = validator.validate([])
        assert quality.is_valid is False
        assert len(quality.warnings) > 0

    def test_validate_winner_vs_loser(self):
        engine = AnalysisEngine()
        validator = Validator()
        winners = [engine.analyze(_winner_entity()) for _ in range(5)]
        losers = [engine.analyze(_loser_entity()) for _ in range(5)]
        result = validator.validate_winner_vs_loser(winners, losers)
        assert result["distinguishable"] is True
        assert result["winner_avg_score"] > result["loser_avg_score"]
        assert result["winner_avg_monetization"] > result["loser_avg_monetization"]

    def test_validation_report_to_dict(self):
        vr = ValidationReport(
            total_results=10, winner_count=3, clickbait_count=1,
            iap_quality_count=5, avg_analysis_score=65,
            avg_monetization_score=60, warnings=["test"],
            is_valid=False,
        )
        d = vr.to_dict()
        assert d["total_results"] == 10
        assert d["is_valid"] is False

    def test_validation_report_to_summary(self):
        vr = ValidationReport(
            total_results=10, winner_count=3, clickbait_count=1,
            iap_quality_count=5, avg_analysis_score=65,
            avg_monetization_score=60,
        )
        summary = vr.to_summary()
        assert "Analysis Quality Report" in summary


# ═══════════════════════════════════════════════════════════
# 9. PRD 验收：10 Winner + 10 Loser 区分度
# ═══════════════════════════════════════════════════════════

class TestPRDAcceptance:
    """PRD 验收测试。"""

    def test_winner_vs_loser_distinguishable(self):
        """10 Winner + 10 Loser → 可区分 Winner DNA。

        Winner: 展示稀有角色 → 高 desire + 高 rarity + 高 monetization
        Loser:  clickbait 好奇 → 高 curiosity + 低 purchase_intent + 低 monetization
        """
        engine = AnalysisEngine()
        validator = Validator()

        winners = []
        for i in range(10):
            entity = _winner_entity(
                creative_id=f"MW_WINNER_{i:03d}",
                name=f"collect_legendary_dragon_{i}",
            )
            winners.append(engine.analyze(entity))

        losers = []
        for i in range(10):
            entity = _loser_entity(
                creative_id=f"MW_LOSER_{i:03d}",
                name=f"OMG_impossible_{i}",
            )
            losers.append(engine.analyze(entity))

        result = validator.validate_winner_vs_loser(winners, losers)
        assert result["distinguishable"] is True, (
            f"Winner vs Loser should be distinguishable: {result}"
        )

        diffs = result["differences"]
        assert diffs["monetization_score"] > 0.1, (
            f"Winner monetization should be significantly higher: {diffs}"
        )
        assert result["winner_avg_score"] > result["loser_avg_score"] * 1.5, (
            f"Winner avg {result['winner_avg_score']} >> Loser {result['loser_avg_score']}"
        )

    def test_winner_roas_correlation(self):
        """Winner 素材 ROAS 关联度应 > 0.5。"""
        engine = AnalysisEngine()
        entity = _winner_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=1.3)
        assert dna.roas_correlation > 0.5

    def test_loser_roas_correlation(self):
        """Loser 素材 ROAS 关联度应 < 0.3。"""
        engine = AnalysisEngine()
        entity = _loser_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=0.4)
        assert dna.roas_correlation < 0.3

    def test_winner_dna_has_visual_rules(self):
        """Winner DNA 应包含视觉制作规则。"""
        engine = AnalysisEngine()
        entity = _winner_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=1.3)
        assert len(dna.visual_rules) > 0

    def test_loser_dna_has_avoid_rules(self):
        """Loser DNA 应包含避免规则。"""
        engine = AnalysisEngine()
        entity = _loser_entity()
        analysis = engine.analyze(entity)
        extractor = CreativeDNAExtractor()
        dna = extractor.extract(analysis, roas_d30=0.4)
        assert len(dna.avoid_rules) > 0


# ═══════════════════════════════════════════════════════════
# 10. Edge Cases
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_zero_data(self):
        entity = _make_entity()
        engine = AnalysisEngine()
        analysis = engine.analyze(entity)
        assert analysis.creative_id is not None
        assert analysis.analysis_score >= 0

    def test_winner_always_beats_loser(self):
        engine = AnalysisEngine()
        winner = engine.analyze(_winner_entity())
        loser = engine.analyze(_loser_entity())
        assert winner.analysis_score > loser.analysis_score