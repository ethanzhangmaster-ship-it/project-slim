"""E11.4.1 — Vision Decision Layer 测试。

测试范围：
  - DecisionRule: 数据模型 + 序列化
  - MutationInstruction: 数据模型 + 序列化
  - ExperimentHypothesis: 数据模型 + 序列化
  - VisionDecision: 数据模型 + action_summary
  - MutationMapper: Pattern → Gene 映射 + 批量映射
  - VisionDecisionEngine: decide / decide_batch / 对比 Winner DNA
  - Integration: Insight → Decision → Mutation → Hypothesis
"""
from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.intelligence.models import (
    VisualPattern,
    HookAnalysis,
    CompositionAnalysis,
    VisionInsight,
    WinnerVisualDNA,
)
from market_ops.creative_vision_runtime.decision.models import (
    DecisionRule,
    MutationInstruction,
    ExperimentHypothesis,
    VisionDecision,
)
from market_ops.creative_vision_runtime.decision.mutation_mapper import (
    MutationMapper,
    PATTERN_TO_GENE,
)
from market_ops.creative_vision_runtime.decision.decision_engine import (
    VisionDecisionEngine,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _make_insight(asset_id: str = "MW_VID_001", **kwargs) -> VisionInsight:
    patterns = kwargs.pop("patterns", [
        VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
        VisualPattern(name="bright_visual", confidence=0.7, category="color"),
        VisualPattern(name="high_saturation", confidence=0.6, category="color"),
    ])
    hook = kwargs.pop("hook", HookAnalysis(
        hook_strength=0.82,
        opening_type="instant_reward",
        visual_transition="high",
    ))
    comp = kwargs.pop("composition", CompositionAnalysis(
        composition_type="single_subject",
        color_palette="bright_saturated",
        motion_type="fast_transition",
    ))
    return VisionInsight(
        creative_asset_id=asset_id,
        visual_patterns=patterns,
        hook_analysis=hook,
        composition_analysis=comp,
        winner_probability=kwargs.pop("winner_probability", 0.75),
        similarity_to_winners=kwargs.pop("similarity", 0.85),
        **kwargs,
    )


def _make_winner_dna(**kwargs) -> WinnerVisualDNA:
    patterns = kwargs.pop("patterns", [
        VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
        VisualPattern(name="bright_visual", confidence=0.75, category="color"),
        VisualPattern(name="high_saturation", confidence=0.7, category="color"),
        VisualPattern(name="clean_composition", confidence=0.65, category="composition"),
    ])
    return WinnerVisualDNA(
        source_count=kwargs.pop("source_count", 5),
        source_assets=kwargs.pop("source_assets", ["MW_WIN_001", "MW_WIN_002"]),
        opening=kwargs.pop("opening", "high_contrast_center_focus"),
        composition=kwargs.pop("composition", "single_subject"),
        color=kwargs.pop("color", "bright_saturated"),
        motion=kwargs.pop("motion", "fast_transition"),
        patterns=patterns,
        aggregated_metrics=kwargs.pop("metrics", {"avg_hook_score": 0.85}),
        **kwargs,
    )


# ════════════════════════════════════════════════════════════════════
# DecisionRule
# ════════════════════════════════════════════════════════════════════

class TestDecisionRule:
    """DecisionRule 数据模型测试。"""

    def test_create(self):
        r = DecisionRule(
            action="keep",
            pattern_name="high_contrast_opening",
            reason="Pattern matches winner DNA",
            confidence=0.8,
            priority=0.9,
        )
        assert r.rule_id.startswith("dr_")
        assert r.action == "keep"
        assert r.confidence == 0.8

    def test_to_dict(self):
        r = DecisionRule(
            action="mutate",
            pattern_name="dark_visual",
            reason="Should add brightness",
            confidence=0.6,
            priority=0.5,
        )
        d = r.to_dict()
        assert d["action"] == "mutate"
        assert d["pattern_name"] == "dark_visual"

    def test_repr(self):
        r = DecisionRule(action="remove", pattern_name="test", confidence=0.3)
        assert "remove" in repr(r)
        assert "test" in repr(r)


# ════════════════════════════════════════════════════════════════════
# MutationInstruction
# ════════════════════════════════════════════════════════════════════

class TestMutationInstruction:
    """MutationInstruction 数据模型测试。"""

    def test_create(self):
        mi = MutationInstruction(
            target_gene="hook_contrast",
            operator="increase",
            magnitude=0.2,
            current_value=0.45,
            target_value=0.65,
            source_pattern="high_contrast_opening",
            description="Visual contrast in opening scene",
        )
        assert mi.instruction_id.startswith("mi_")
        assert mi.target_gene == "hook_contrast"
        assert mi.magnitude == 0.2

    def test_to_dict(self):
        mi = MutationInstruction(
            target_gene="color_palette",
            operator="increase",
            magnitude=0.15,
            source_pattern="high_saturation",
        )
        d = mi.to_dict()
        assert d["target_gene"] == "color_palette"
        assert d["magnitude"] == 0.15

    def test_repr(self):
        mi = MutationInstruction(
            target_gene="hook_contrast",
            operator="increase",
            magnitude=0.2,
        )
        assert "hook_contrast" in repr(mi)
        assert "20%" in repr(mi)


# ════════════════════════════════════════════════════════════════════
# ExperimentHypothesis
# ════════════════════════════════════════════════════════════════════

class TestExperimentHypothesis:
    """ExperimentHypothesis 数据模型测试。"""

    def test_create(self):
        eh = ExperimentHypothesis(
            statement="Increasing contrast may improve hook rate",
            variables=["hook_contrast", "high_contrast_opening"],
            expected_metric="hook_rate",
            expected_direction="increase",
            expected_magnitude=0.15,
            confidence=0.7,
        )
        assert eh.hypothesis_id.startswith("eh_")
        assert eh.expected_metric == "hook_rate"

    def test_to_dict(self):
        eh = ExperimentHypothesis(
            statement="Test hypothesis",
            variables=["v1"],
            expected_metric="CTR",
            confidence=0.6,
        )
        d = eh.to_dict()
        assert d["variables"] == ["v1"]
        assert d["expected_metric"] == "CTR"

    def test_repr(self):
        eh = ExperimentHypothesis(
            expected_metric="hook_rate",
            expected_direction="increase",
            confidence=0.7,
        )
        assert "hook_rate" in repr(eh)


# ════════════════════════════════════════════════════════════════════
# VisionDecision
# ════════════════════════════════════════════════════════════════════

class TestVisionDecision:
    """VisionDecision 数据模型测试。"""

    def test_create_empty(self):
        vd = VisionDecision(creative_asset_id="MW_VID_001")
        assert vd.decision_id.startswith("vd_")
        assert vd.keep_patterns == []
        assert vd.mutate_patterns == []

    def test_create_full(self):
        vd = VisionDecision(
            creative_asset_id="MW_VID_001",
            confidence=0.8,
            keep_patterns=["high_contrast_opening"],
            mutate_patterns=["clean_composition"],
            remove_patterns=["dark_visual"],
            summary="Decision summary",
        )
        assert vd.confidence == 0.8
        assert vd.keep_patterns == ["high_contrast_opening"]
        assert vd.mutate_patterns == ["clean_composition"]

    def test_action_summary(self):
        vd = VisionDecision(
            keep_patterns=["a", "b"],
            mutate_patterns=["c"],
            remove_patterns=["d"],
        )
        s = vd.action_summary
        assert s["keep"] == 2
        assert s["mutate"] == 1
        assert s["remove"] == 1

    def test_total_rules(self):
        vd = VisionDecision(
            rules=[
                DecisionRule(action="keep", pattern_name="a", reason="r", confidence=0.8),
                DecisionRule(action="mutate", pattern_name="b", reason="r", confidence=0.6),
                DecisionRule(action="remove", pattern_name="c", reason="r", confidence=0.3),
            ],
        )
        assert vd.total_rules == 3

    def test_to_dict(self):
        vd = VisionDecision(
            creative_asset_id="MW_VID_001",
            confidence=0.8,
            keep_patterns=["a"],
            mutate_patterns=["b"],
            rules=[DecisionRule(action="keep", pattern_name="a", reason="r", confidence=0.8)],
            mutation_instructions=[MutationInstruction(
                target_gene="hook_contrast", operator="increase", magnitude=0.2,
            )],
            hypotheses=[ExperimentHypothesis(
                statement="test", expected_metric="CTR", confidence=0.6,
            )],
        )
        d = vd.to_dict()
        assert len(d["rules"]) == 1
        assert len(d["mutation_instructions"]) == 1
        assert len(d["hypotheses"]) == 1

    def test_repr(self):
        vd = VisionDecision(
            creative_asset_id="MW_VID_001",
            keep_patterns=["a"],
            mutate_patterns=["b"],
        )
        assert "MW_VID_001" in repr(vd)


# ════════════════════════════════════════════════════════════════════
# MutationMapper
# ════════════════════════════════════════════════════════════════════

class TestMutationMapper:
    """MutationMapper 映射测试。"""

    @pytest.fixture
    def mapper(self):
        return MutationMapper()

    def test_map_high_contrast(self, mapper):
        mi = mapper.map_to_mutation("high_contrast_opening", confidence=0.8)
        assert mi is not None
        assert mi.target_gene == "hook_contrast"
        assert mi.operator == "increase"
        assert mi.magnitude > 0

    def test_map_bright_visual(self, mapper):
        mi = mapper.map_to_mutation("bright_visual", confidence=0.7)
        assert mi is not None
        assert mi.target_gene == "brightness"

    def test_map_high_saturation(self, mapper):
        mi = mapper.map_to_mutation("high_saturation", confidence=0.6)
        assert mi is not None
        assert mi.target_gene == "color_palette"

    def test_map_clean_composition(self, mapper):
        mi = mapper.map_to_mutation("clean_composition", confidence=0.65)
        assert mi is not None
        assert mi.target_gene == "object_count"

    def test_map_fast_visual_change(self, mapper):
        mi = mapper.map_to_mutation("fast_visual_change", confidence=0.5)
        assert mi is not None
        assert mi.target_gene == "scene_transition"

    def test_map_unknown_pattern(self, mapper):
        mi = mapper.map_to_mutation("unknown_pattern", confidence=0.5)
        assert mi is None

    def test_magnitude_higher_with_confidence(self, mapper):
        mi_high = mapper.map_to_mutation("high_contrast_opening", confidence=0.9)
        mi_low = mapper.map_to_mutation("high_contrast_opening", confidence=0.3)
        assert mi_high is not None
        assert mi_low is not None
        assert mi_high.magnitude >= mi_low.magnitude

    def test_map_batch(self, mapper):
        instructions = mapper.map_batch(
            pattern_names=["high_contrast_opening", "bright_visual", "high_saturation"],
            confidences={
                "high_contrast_opening": 0.8,
                "bright_visual": 0.7,
                "high_saturation": 0.6,
            },
        )
        assert len(instructions) == 3
        genes = {mi.target_gene for mi in instructions}
        assert genes == {"hook_contrast", "brightness", "color_palette"}

    def test_map_batch_skips_unknown(self, mapper):
        instructions = mapper.map_batch(
            pattern_names=["high_contrast_opening", "unknown_pattern"],
        )
        assert len(instructions) == 1

    def test_get_gene(self, mapper):
        assert mapper.get_gene("high_contrast_opening") == "hook_contrast"
        assert mapper.get_gene("unknown") is None

    def test_get_operator(self, mapper):
        assert mapper.get_operator("hook_contrast") == "increase"
        assert mapper.get_operator("object_count") == "set"

    def test_list_mappable_patterns(self, mapper):
        patterns = mapper.list_mappable_patterns()
        assert "high_contrast_opening" in patterns
        assert "bright_visual" in patterns
        assert len(patterns) == len(PATTERN_TO_GENE)

    def test_list_genes(self, mapper):
        genes = mapper.list_genes()
        assert "hook_contrast" in genes
        assert "brightness" in genes
        assert "color_palette" in genes

    def test_target_value_computation(self, mapper):
        mi = mapper.map_to_mutation(
            "high_contrast_opening", confidence=0.8, current_value=0.5
        )
        assert mi is not None
        assert mi.target_value > mi.current_value
        assert mi.target_value <= 1.0

    def test_repr(self, mapper):
        assert "MutationMapper" in repr(mapper)


# ════════════════════════════════════════════════════════════════════
# VisionDecisionEngine
# ════════════════════════════════════════════════════════════════════

class TestVisionDecisionEngine:
    """VisionDecisionEngine 决策引擎测试。"""

    @pytest.fixture
    def engine(self):
        return VisionDecisionEngine()

    def test_decide_without_winner_dna(self, engine):
        insight = _make_insight("MW_VID_001")
        decision = engine.decide(insight)

        assert decision.creative_asset_id == "MW_VID_001"
        assert len(decision.keep_patterns) > 0
        assert len(decision.rules) > 0
        assert 0 <= decision.confidence <= 1
        assert len(decision.summary) > 0

    def test_decide_with_winner_dna(self, engine):
        insight = _make_insight("MW_VID_001")
        winner_dna = _make_winner_dna()
        decision = engine.decide(insight, winner_dna)

        assert decision.creative_asset_id == "MW_VID_001"
        # 素材 + Winner 都有的模式 → keep
        assert "high_contrast_opening" in decision.keep_patterns
        assert "bright_visual" in decision.keep_patterns
        assert "high_saturation" in decision.keep_patterns
        # Winner 有但素材没有的模式 → mutate
        assert "clean_composition" in decision.mutate_patterns

    def test_decide_winner_dna_missing_patterns(self, engine):
        # 素材有但 Winner 没有的模式 → remove
        insight = _make_insight("MW_VID_001", patterns=[
            VisualPattern(name="dark_visual", confidence=0.6, category="color"),
        ])
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="bright_visual", confidence=0.8, category="color"),
        ])
        decision = engine.decide(insight, winner_dna)

        assert "dark_visual" in decision.remove_patterns
        assert "bright_visual" in decision.mutate_patterns

    def test_decide_generates_mutations(self, engine):
        insight = _make_insight("MW_VID_001", patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
        ])
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
            VisualPattern(name="clean_composition", confidence=0.65, category="composition"),
        ])
        decision = engine.decide(insight, winner_dna)

        assert len(decision.mutation_instructions) > 0
        # clean_composition → 需要变异
        genes = {mi.target_gene for mi in decision.mutation_instructions}
        assert "object_count" in genes

    def test_decide_generates_hypotheses(self, engine):
        insight = _make_insight("MW_VID_001", patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
        ])
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
            VisualPattern(name="clean_composition", confidence=0.65, category="composition"),
            VisualPattern(name="fast_visual_change", confidence=0.55, category="motion"),
        ])
        decision = engine.decide(insight, winner_dna)

        assert len(decision.hypotheses) > 0
        assert all(h.expected_metric == "hook_rate" for h in decision.hypotheses)

    def test_decide_no_patterns(self, engine):
        insight = _make_insight("MW_VID_001", patterns=[])
        decision = engine.decide(insight)
        assert decision.creative_asset_id == "MW_VID_001"
        assert len(decision.rules) == 0

    def test_decide_batch(self, engine):
        insights = [
            _make_insight("MW_VID_001"),
            _make_insight("MW_VID_002"),
        ]
        decisions = engine.decide_batch(insights)
        assert len(decisions) == 2
        assert decisions[0].creative_asset_id == "MW_VID_001"

    def test_decide_batch_with_winner_dna(self, engine):
        insights = [
            _make_insight("MW_VID_001"),
            _make_insight("MW_VID_002"),
        ]
        winner_dna = _make_winner_dna()
        decisions = engine.decide_batch(insights, winner_dna)
        assert len(decisions) == 2
        # 两个素材都应该有 clean_composition 在 mutate 中
        for d in decisions:
            assert "clean_composition" in d.mutate_patterns

    def test_decision_count(self, engine):
        insight = _make_insight("MW_VID_001")
        assert engine.decision_count == 0
        engine.decide(insight)
        assert engine.decision_count == 1
        engine.decide(_make_insight("MW_VID_002"))
        assert engine.decision_count == 2

    def test_confidence_higher_with_winner_dna(self, engine):
        insight = _make_insight("MW_VID_001")
        d1 = engine.decide(insight)
        d2 = engine.decide(insight, _make_winner_dna())
        assert d2.confidence >= d1.confidence

    def test_repr(self, engine):
        assert "VisionDecisionEngine" in repr(engine)


# ════════════════════════════════════════════════════════════════════
# Integration: Insight → Decision → Mutation → Hypothesis
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：完整决策流程。"""

    def test_full_pipeline(self):
        engine = VisionDecisionEngine()

        # 1. 创建 Insight（模拟 E11.3.5 输出）
        insight = _make_insight("MW_MUTANT_001", patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
            VisualPattern(name="bright_visual", confidence=0.7, category="color"),
            VisualPattern(name="complex_scene", confidence=0.55, category="composition"),
        ])

        # 2. 创建 Winner DNA（模拟 Winner 集合）
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
            VisualPattern(name="bright_visual", confidence=0.75, category="color"),
            VisualPattern(name="high_saturation", confidence=0.7, category="color"),
            VisualPattern(name="clean_composition", confidence=0.65, category="composition"),
            VisualPattern(name="fast_visual_change", confidence=0.6, category="motion"),
        ])

        # 3. 生成决策
        decision = engine.decide(insight, winner_dna)

        # 4. 验证 keep（素材 + Winner 共有）
        assert "high_contrast_opening" in decision.keep_patterns
        assert "bright_visual" in decision.keep_patterns

        # 5. 验证 remove（素材有，Winner 没有）
        assert "complex_scene" in decision.remove_patterns

        # 6. 验证 mutate（Winner 有，素材没有）
        assert "high_saturation" in decision.mutate_patterns
        assert "clean_composition" in decision.mutate_patterns
        assert "fast_visual_change" in decision.mutate_patterns

        # 7. 验证突变指令
        genes = {mi.target_gene for mi in decision.mutation_instructions}
        assert "color_palette" in genes  # from high_saturation
        assert "object_count" in genes    # from clean_composition
        assert "scene_transition" in genes  # from fast_visual_change

        # 8. 验证实验假设
        assert len(decision.hypotheses) > 0

        # 9. 验证序列化
        d = decision.to_dict()
        assert d["creative_asset_id"] == "MW_MUTANT_001"
        assert len(d["mutation_instructions"]) > 0
        assert len(d["hypotheses"]) > 0

    def test_keep_all_when_matches(self):
        engine = VisionDecisionEngine()

        insight = _make_insight("MW_PERFECT", patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.9, category="opening"),
            VisualPattern(name="bright_visual", confidence=0.8, category="color"),
            VisualPattern(name="high_saturation", confidence=0.75, category="color"),
        ])
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
            VisualPattern(name="bright_visual", confidence=0.75, category="color"),
            VisualPattern(name="high_saturation", confidence=0.7, category="color"),
        ])

        decision = engine.decide(insight, winner_dna)

        assert len(decision.keep_patterns) == 3
        assert len(decision.mutate_patterns) == 0
        assert len(decision.remove_patterns) == 0

    def test_mutation_instruction_serialization(self):
        engine = VisionDecisionEngine()

        insight = _make_insight("MW_VID_001", patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
        ])
        winner_dna = _make_winner_dna(patterns=[
            VisualPattern(name="high_contrast_opening", confidence=0.85, category="opening"),
            VisualPattern(name="clean_composition", confidence=0.65, category="composition"),
        ])

        decision = engine.decide(insight, winner_dna)

        for mi in decision.mutation_instructions:
            d = mi.to_dict()
            assert "target_gene" in d
            assert "operator" in d
            assert d["magnitude"] > 0
            assert d["target_value"] > 0

    def test_package_exports(self):
        from market_ops.creative_vision_runtime.decision import (
            VisionDecisionEngine as ExportedEngine,
            MutationMapper as ExportedMapper,
            VisionDecision as ExportedDecision,
            MutationInstruction as ExportedMI,
            ExperimentHypothesis as ExportedEH,
        )
        assert ExportedEngine is VisionDecisionEngine
        assert ExportedMapper is MutationMapper
        assert ExportedDecision is VisionDecision
        assert ExportedMI is MutationInstruction
        assert ExportedEH is ExperimentHypothesis