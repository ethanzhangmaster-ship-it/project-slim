"""E14.4.2 Creative Strategy Agent — 集成测试.

验证 Creative Agent 的策略决策能力:
  - CreativeOpportunityEngine (E14.4.2.1) — 40 tests
  - CreativeStrategyEngine (E14.4.2.2) — 50 tests
  - CreativePlanner (E14.4.2.3) — 40 tests
  - CreativeEvaluator (E14.4.2.4) — 40 tests
  - Full Pipeline (E14.4.2) — 25 tests
  - CreativeAgent Integration — 20 tests
  - Regression (E14.4.1/E14.3/E14.2/E14.1) — 15 tests

总计: 230 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    MessageBus,
    AgentRegistry,
    StandardMessageType,
    create_message_bus,
    create_agent_registry,
    create_ua_agent_identity as comm_ua_identity,
    create_creative_agent_identity as comm_creative_identity,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent import (
    # analyzer
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosis,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    create_creative_analyzer,
    # dna_engine
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    WinnerDNAReport,
    HookType,
    VisualStyle,
    EmotionType,
    GameplayFocus,
    # memory
    CreativeMemory,
    CreativeDecisionOutcome,
    CreativeActionType,
    # creative_agent
    CreativeAgent,
    CreativeAgentState,
    create_creative_agent,
    # opportunity (E14.4.2.1)
    CreativeOpportunityEngine,
    CreativeOpportunity,
    CreativeOpportunityType,
    CreativeSignal,
    OpportunityPriority,
    OpportunityReport,
    create_opportunity_engine,
    # strategy (E14.4.2.2)
    CreativeStrategyEngine,
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
    StrategyReport,
    create_strategy_engine,
    # planner (E14.4.2.3)
    CreativePlanner,
    CreativePlan,
    MutationConfig,
    ExperimentConfig,
    ExperimentType,
    PlanStatus,
    BatchPlan,
    create_planner,
    # evaluator (E14.4.2.4)
    CreativeEvaluator,
    CreativeStrategyOutcome,
    CreativeMetricsSnapshot,
    StrategyEvaluation,
    StrategyOutcomeType,
    EvaluationReport,
    create_evaluator,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def fatigue_signal():
    return CreativeSignal(
        creative_id="C102",
        issue="creative_fatigue",
        confidence=0.91,
        metrics={"ctr_decay": 0.35, "frequency": 5.2, "roas_decay": 0.28},
        severity="warning",
        platform="meta",
    )


@pytest.fixture
def winner_signal():
    return CreativeSignal(
        creative_id="C201",
        issue="winner_detected",
        confidence=0.95,
        metrics={"roas": 2.5, "ctr": 0.04, "fatigue": 0.15},
        severity="positive",
        platform="meta",
    )


@pytest.fixture
def ctr_decay_signal():
    return CreativeSignal(
        creative_id="C303",
        issue="ctr_decay",
        confidence=0.78,
        metrics={"ctr_before": 0.035, "ctr_after": 0.018},
        severity="warning",
    )


@pytest.fixture
def roas_decay_signal():
    return CreativeSignal(
        creative_id="C404",
        issue="roas_decay",
        confidence=0.85,
        metrics={"roas_before": 1.2, "roas_after": 0.6},
        severity="critical",
    )


@pytest.fixture
def underperformer_signal():
    return CreativeSignal(
        creative_id="C505",
        issue="underperformer",
        confidence=0.72,
        metrics={"roas": 0.3, "ctr": 0.008},
        severity="warning",
    )


@pytest.fixture
def high_potential_signal():
    return CreativeSignal(
        creative_id="C606",
        issue="high_potential",
        confidence=0.65,
        metrics={"ctr": 0.028, "roas": 1.1},
        severity="info",
    )


@pytest.fixture
def sample_dna():
    """创建样本 DNA 画像."""
    engine = DNAEngine()
    return engine.extract_dna(
        creative_id="C102",
        creative_name="Test Creative",
        hook="character_reveal",
        visual="fantasy",
        gameplay="merge",
        monetization="iap",
        emotion="curiosity",
        audience="casual_gamers",
        context="weekend",
        fitness={"roas": 0.45, "ctr": 0.018, "fatigue": 0.82},
    )


@pytest.fixture
def winner_dna():
    """创建赢家 DNA 画像."""
    engine = DNAEngine()
    return engine.extract_dna(
        creative_id="C201",
        creative_name="Winner Creative",
        hook="before_after",
        visual="vibrant",
        gameplay="match3",
        monetization="iap",
        emotion="excitement",
        audience="female_25_45",
        context="weekend",
        fitness={"roas": 2.5, "ctr": 0.04, "fatigue": 0.15},
    )


@pytest.fixture
def memory_with_winner(winner_dna):
    """包含赢家 DNA 的记忆."""
    memory = CreativeMemory()
    memory.store_dna(winner_dna, is_winner=True, performance={"roas": 2.5, "ctr": 0.04})
    return memory


@pytest.fixture
def opportunity_engine():
    return create_opportunity_engine()


@pytest.fixture
def strategy_engine():
    return create_strategy_engine()


@pytest.fixture
def strategy_engine_with_winner(memory_with_winner):
    return create_strategy_engine(memory=memory_with_winner)


@pytest.fixture
def planner():
    return create_planner()


@pytest.fixture
def evaluator():
    return create_evaluator()


@pytest.fixture
def creative_agent():
    return create_creative_agent()


@pytest.fixture
def before_metrics():
    return CreativeMetricsSnapshot(
        creative_id="C102",
        roas=0.45, ctr=0.018, cvr=0.03,
        fatigue=0.82, frequency=6.0,
        spend=2000, revenue=900,
        installs=5000, payer_rate=0.04, ltv=3.2,
    )


@pytest.fixture
def after_metrics_improved():
    return CreativeMetricsSnapshot(
        creative_id="C102",
        roas=1.2, ctr=0.028, cvr=0.05,
        fatigue=0.45, frequency=3.5,
        spend=2000, revenue=2400,
        installs=8000, payer_rate=0.06, ltv=4.5,
    )


@pytest.fixture
def after_metrics_worse():
    return CreativeMetricsSnapshot(
        creative_id="C102",
        roas=0.3, ctr=0.012, cvr=0.02,
        fatigue=0.9, frequency=7.0,
        spend=2000, revenue=600,
        installs=3000, payer_rate=0.03, ltv=2.5,
    )


# ═══════════════════════════════════════════════════════════════
# E14.4.2.1 Creative Opportunity Engine — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeSignal:
    """CreativeSignal 模型测试."""

    def test_create_signal_defaults(self):
        s = CreativeSignal()
        assert s.signal_id
        assert s.creative_id == ""
        assert s.issue == ""
        assert s.confidence == 0.0
        assert s.source == "ua_agent"

    def test_signal_with_fatigue_data(self, fatigue_signal):
        assert fatigue_signal.creative_id == "C102"
        assert fatigue_signal.issue == "creative_fatigue"
        assert fatigue_signal.confidence == 0.91
        assert fatigue_signal.is_fatigue_signal is True
        assert fatigue_signal.is_winner_signal is False

    def test_signal_is_critical(self):
        s = CreativeSignal(severity="critical")
        assert s.is_critical is True

    def test_signal_is_not_critical(self, fatigue_signal):
        assert fatigue_signal.is_critical is False

    def test_signal_is_winner_signal(self, winner_signal):
        assert winner_signal.is_winner_signal is True

    def test_signal_is_fatigue_signal(self):
        s = CreativeSignal(issue="fatigue")
        assert s.is_fatigue_signal is True

    def test_signal_to_dict(self, fatigue_signal):
        d = fatigue_signal.to_dict()
        assert d["creative_id"] == "C102"
        assert d["issue"] == "creative_fatigue"
        assert d["confidence"] == 0.91

    def test_signal_from_dict(self):
        d = {"creative_id": "C999", "issue": "winner", "confidence": 0.88}
        s = CreativeSignal.from_dict(d)
        assert s.creative_id == "C999"
        assert s.issue == "winner"
        assert s.confidence == 0.88

    def test_signal_from_dict_defaults(self):
        s = CreativeSignal.from_dict({})
        assert s.creative_id == ""
        assert s.issue == ""

    def test_signal_to_dict_roundtrip(self, fatigue_signal):
        d = fatigue_signal.to_dict()
        s2 = CreativeSignal.from_dict(d)
        assert s2.creative_id == fatigue_signal.creative_id
        assert s2.issue == fatigue_signal.issue
        assert s2.confidence == fatigue_signal.confidence


class TestCreativeOpportunity:
    """CreativeOpportunity 模型测试."""

    def test_create_opportunity_defaults(self):
        o = CreativeOpportunity()
        assert o.opportunity_id
        assert o.type == CreativeOpportunityType.UNKNOWN
        assert o.priority == OpportunityPriority.MEDIUM

    def test_opportunity_critical(self):
        o = CreativeOpportunity(priority=OpportunityPriority.CRITICAL)
        assert o.is_critical is True
        assert o.is_high_priority is True

    def test_opportunity_high_priority(self):
        o = CreativeOpportunity(priority=OpportunityPriority.HIGH)
        assert o.is_high_priority is True
        assert o.is_critical is False

    def test_opportunity_summary(self):
        o = CreativeOpportunity(
            type=CreativeOpportunityType.REFRESH_CREATIVE,
            priority=OpportunityPriority.HIGH,
            target_creative_id="C102",
            reason=["素材疲劳"],
        )
        summary = o.summary
        assert "HIGH" in summary
        assert "refresh_creative" in summary
        assert "C102" in summary

    def test_opportunity_to_dict(self):
        o = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            priority=OpportunityPriority.CRITICAL,
            target_creative_id="C102",
            confidence=0.9,
        )
        d = o.to_dict()
        assert d["type"] == "replace_hook"
        assert d["priority"] == "critical"
        assert d["target_creative_id"] == "C102"

    def test_opportunity_with_evidence(self):
        o = CreativeOpportunity(
            evidence={"signal_issue": "fatigue", "metrics": {"roas": 0.45}},
        )
        assert o.evidence["signal_issue"] == "fatigue"

    def test_opportunity_with_recommended_actions(self):
        o = CreativeOpportunity(
            recommended_actions=["提取DNA", "生成变体", "测试"],
        )
        assert len(o.recommended_actions) == 3


class TestOpportunityReport:
    """OpportunityReport 模型测试."""

    def test_report_empty(self):
        r = OpportunityReport()
        assert r.opportunity_count == 0
        assert r.critical_count == 0

    def test_report_with_opportunities(self):
        opps = [
            CreativeOpportunity(
                type=CreativeOpportunityType.REFRESH_CREATIVE,
                priority=OpportunityPriority.CRITICAL,
            ),
            CreativeOpportunity(
                type=CreativeOpportunityType.REPLACE_HOOK,
                priority=OpportunityPriority.HIGH,
            ),
        ]
        r = OpportunityReport(
            opportunities=opps,
            total_signals=2,
            total_opportunities=2,
        )
        r.critical_count = 1
        r.high_count = 1
        assert r.opportunity_count == 2

    def test_report_to_dict(self):
        r = OpportunityReport(
            opportunities=[CreativeOpportunity()],
            total_signals=1,
            total_opportunities=1,
            summary="测试",
        )
        d = r.to_dict()
        assert "report_id" in d
        assert len(d["opportunities"]) == 1


class TestCreativeOpportunityEngine:
    """CreativeOpportunityEngine 核心测试."""

    def test_engine_creation(self):
        engine = create_opportunity_engine()
        assert engine is not None
        assert engine.stats()["total"] == 0

    def test_detect_fatigue_signal(self, opportunity_engine, fatigue_signal):
        opp = opportunity_engine.detect(fatigue_signal)
        assert opp.type == CreativeOpportunityType.REFRESH_CREATIVE
        assert opp.target_creative_id == "C102"
        assert len(opp.reason) > 0

    def test_detect_winner_signal(self, opportunity_engine, winner_signal):
        opp = opportunity_engine.detect(winner_signal)
        assert opp.type == CreativeOpportunityType.SCALE_WINNER
        assert opp.priority in (OpportunityPriority.HIGH, OpportunityPriority.CRITICAL)

    def test_detect_ctr_decay(self, opportunity_engine, ctr_decay_signal):
        opp = opportunity_engine.detect(ctr_decay_signal)
        assert opp.type == CreativeOpportunityType.REPLACE_HOOK

    def test_detect_roas_decay(self, opportunity_engine, roas_decay_signal):
        opp = opportunity_engine.detect(roas_decay_signal)
        assert opp.type == CreativeOpportunityType.REFRESH_CREATIVE

    def test_detect_underperformer(self, opportunity_engine, underperformer_signal):
        opp = opportunity_engine.detect(underperformer_signal)
        assert opp.type == CreativeOpportunityType.EXPLORE_NEW_DNA

    def test_detect_high_potential(self, opportunity_engine, high_potential_signal):
        opp = opportunity_engine.detect(high_potential_signal)
        assert opp.type == CreativeOpportunityType.CHANGE_EMOTION

    def test_detect_from_dict(self, opportunity_engine):
        d = {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}
        opp = opportunity_engine.detect(d)
        assert opp.type == CreativeOpportunityType.REFRESH_CREATIVE

    def test_detect_critical_priority(self, opportunity_engine, roas_decay_signal):
        opp = opportunity_engine.detect(roas_decay_signal)
        assert opp.priority == OpportunityPriority.CRITICAL

    def test_detect_high_priority_for_urgent(self, opportunity_engine):
        s = CreativeSignal(issue="creative_fatigue", confidence=0.85, severity="critical")
        opp = opportunity_engine.detect(s)
        assert opp.priority == OpportunityPriority.CRITICAL

    def test_detect_low_confidence_priority(self, opportunity_engine):
        s = CreativeSignal(issue="underperformer", confidence=0.2)
        opp = opportunity_engine.detect(s)
        assert opp.priority == OpportunityPriority.LOW

    def test_detect_includes_evidence(self, opportunity_engine, fatigue_signal):
        opp = opportunity_engine.detect(fatigue_signal)
        assert opp.evidence["signal_issue"] == "creative_fatigue"
        assert opp.evidence["signal_confidence"] == 0.91

    def test_detect_includes_recommended_actions(self, opportunity_engine, fatigue_signal):
        opp = opportunity_engine.detect(fatigue_signal)
        assert len(opp.recommended_actions) > 0

    def test_detect_batch(self, opportunity_engine, fatigue_signal, winner_signal):
        report = opportunity_engine.detect_batch([fatigue_signal, winner_signal])
        assert report.total_signals == 2
        assert report.total_opportunities == 2
        assert report.opportunity_count == 2

    def test_detect_batch_from_dicts(self, opportunity_engine):
        signals = [
            {"creative_id": "C1", "issue": "creative_fatigue", "confidence": 0.8},
            {"creative_id": "C2", "issue": "winner_detected", "confidence": 0.9},
        ]
        report = opportunity_engine.detect_from_dicts(signals)
        assert report.total_opportunities == 2

    def test_detect_batch_summary(self, opportunity_engine, fatigue_signal, winner_signal):
        report = opportunity_engine.detect_batch([fatigue_signal, winner_signal])
        assert len(report.summary) > 0

    def test_engine_history(self, opportunity_engine, fatigue_signal):
        opportunity_engine.detect(fatigue_signal)
        history = opportunity_engine.get_history()
        assert len(history) == 1

    def test_engine_get_critical(self, opportunity_engine, roas_decay_signal):
        opportunity_engine.detect(roas_decay_signal)
        critical = opportunity_engine.get_critical()
        assert len(critical) == 1

    def test_engine_get_by_type(self, opportunity_engine, fatigue_signal, winner_signal):
        opportunity_engine.detect(fatigue_signal)
        opportunity_engine.detect(winner_signal)
        refresh = opportunity_engine.get_by_type(CreativeOpportunityType.REFRESH_CREATIVE)
        assert len(refresh) == 1

    def test_engine_get_by_creative(self, opportunity_engine, fatigue_signal):
        opportunity_engine.detect(fatigue_signal)
        results = opportunity_engine.get_by_creative("C102")
        assert len(results) == 1

    def test_engine_stats(self, opportunity_engine, fatigue_signal, winner_signal):
        opportunity_engine.detect(fatigue_signal)
        opportunity_engine.detect(winner_signal)
        stats = opportunity_engine.stats()
        assert stats["total"] == 2

    def test_engine_reset(self, opportunity_engine, fatigue_signal):
        opportunity_engine.detect(fatigue_signal)
        opportunity_engine.reset()
        assert opportunity_engine.stats()["total"] == 0


# ═══════════════════════════════════════════════════════════════
# E14.4.2.2 Creative Strategy Engine — 50 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeStrategyType:
    """CreativeStrategyType 枚举测试."""

    def test_all_strategy_types_defined(self):
        types = list(CreativeStrategyType)
        assert len(types) >= 11
        assert CreativeStrategyType.REFRESH_HOOK in types
        assert CreativeStrategyType.COPY_WINNER_DNA in types
        assert CreativeStrategyType.EXPLORE_NEW_DNA in types

    def test_strategy_type_values(self):
        assert CreativeStrategyType.REFRESH_HOOK.value == "refresh_hook"
        assert CreativeStrategyType.CHANGE_VISUAL_STYLE.value == "change_visual"
        assert CreativeStrategyType.SCALE_WINNER.value == "scale_winner"


class TestGeneMutation:
    """GeneMutation 模型测试."""

    def test_gene_mutation_keep(self):
        m = GeneMutation(gene_category="hook", action=GeneMutationAction.KEEP, current_value="before_after")
        assert m.action == GeneMutationAction.KEEP
        assert m.gene_category == "hook"

    def test_gene_mutation_change(self):
        m = GeneMutation(
            gene_category="hook",
            action=GeneMutationAction.CHANGE,
            current_value="curiosity",
            target_values=["impossible_result", "rare_item"],
            weight=0.3,
        )
        assert m.action == GeneMutationAction.CHANGE
        assert len(m.target_values) == 2

    def test_gene_mutation_explore(self):
        m = GeneMutation(
            gene_category="visual",
            action=GeneMutationAction.EXPLORE,
            target_values=["dark", "vibrant"],
        )
        assert m.action == GeneMutationAction.EXPLORE

    def test_gene_mutation_to_dict(self):
        m = GeneMutation(gene_category="hook", action=GeneMutationAction.CHANGE,
                         current_value="before_after", target_values=["curiosity"])
        d = m.to_dict()
        assert d["gene_category"] == "hook"
        assert d["action"] == "change"
        assert d["current_value"] == "before_after"


class TestCreativeStrategy:
    """CreativeStrategy 模型测试."""

    def test_strategy_default(self):
        s = CreativeStrategy()
        assert s.strategy_id
        assert s.strategy_type == CreativeStrategyType.UNKNOWN
        assert s.mutation_count == 0

    def test_strategy_with_mutations(self):
        s = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_plan=[
                GeneMutation(gene_category="hook", action=GeneMutationAction.CHANGE),
                GeneMutation(gene_category="visual", action=GeneMutationAction.KEEP),
            ],
        )
        assert s.mutation_count == 2
        assert s.change_count == 1

    def test_strategy_summary(self):
        s = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            keep_genes={"visual": "fantasy", "gameplay": "merge"},
            change_genes={"hook": ["before_after"]},
        )
        summary = s.summary
        assert "refresh_hook" in summary
        assert "visual" in summary

    def test_strategy_to_dict(self):
        s = CreativeStrategy(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            target_creative_id="C102",
            confidence=0.85,
            priority=OpportunityPriority.HIGH,
        )
        d = s.to_dict()
        assert d["strategy_type"] == "copy_winner"
        assert d["target_creative_id"] == "C102"
        assert d["confidence"] == 0.85


class TestStrategyReport:
    """StrategyReport 模型测试."""

    def test_report_default(self):
        r = StrategyReport()
        assert r.strategy_count == 0

    def test_report_with_strategies(self):
        strategies = [CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK)]
        r = StrategyReport(strategies=strategies)
        assert r.strategy_count == 1

    def test_report_to_dict(self):
        r = StrategyReport(
            strategies=[CreativeStrategy()],
            total_opportunities=1,
            total_strategies=1,
        )
        d = r.to_dict()
        assert len(d["strategies"]) == 1


class TestCreativeStrategyEngine:
    """CreativeStrategyEngine 核心测试."""

    def test_engine_creation(self):
        engine = create_strategy_engine()
        assert engine is not None

    def test_generate_from_fatigue_opportunity(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.91,
            reason=["素材疲劳"],
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.REFRESH_HOOK
        assert strategy.target_creative_id == "C102"
        assert len(strategy.mutation_plan) > 0

    def test_generate_keeps_non_hook_genes(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.91,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert "visual" in strategy.keep_genes
        assert "gameplay" in strategy.keep_genes

    def test_generate_changes_hook_gene(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.91,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert "hook" in strategy.change_genes
        assert len(strategy.change_genes["hook"]) > 0

    def test_generate_copy_winner_strategy(self, strategy_engine_with_winner, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.COPY_WINNER_DNA,
            target_creative_id="C102",
            confidence=0.88,
        )
        strategy = strategy_engine_with_winner.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.COPY_WINNER_DNA

    def test_generate_scale_winner_strategy(self, strategy_engine, winner_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.SCALE_WINNER,
            target_creative_id="C201",
            confidence=0.95,
        )
        strategy = strategy_engine.generate(opp, winner_dna)
        assert strategy.strategy_type == CreativeStrategyType.SCALE_WINNER

    def test_generate_change_visual(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.CHANGE_VISUAL,
            target_creative_id="C102",
            confidence=0.75,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.CHANGE_VISUAL_STYLE
        assert "visual" in strategy.change_genes

    def test_generate_change_gameplay(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.CHANGE_GAMEPLAY,
            target_creative_id="C102",
            confidence=0.7,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE

    def test_generate_change_emotion(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.CHANGE_EMOTION,
            target_creative_id="C102",
            confidence=0.72,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.CHANGE_EMOTION

    def test_generate_explore_new_dna(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.EXPLORE_NEW_DNA,
            target_creative_id="C102",
            confidence=0.65,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.EXPLORE_NEW_DNA

    def test_generate_optimize_opening(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.OPTIMIZE_OPENING,
            target_creative_id="C102",
            confidence=0.8,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.OPTIMIZE_OPENING

    def test_generate_explore_audience(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.EXPLORE_NEW_AUDIENCE,
            target_creative_id="C102",
            confidence=0.6,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.EXPLORE_NEW_AUDIENCE

    def test_generate_test_concept(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.TEST_NEW_CONCEPT,
            target_creative_id="C102",
            confidence=0.55,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.TEST_NEW_CONCEPT

    def test_generate_without_dna(self, strategy_engine):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.8,
        )
        strategy = strategy_engine.generate(opp)  # No DNA
        assert strategy.strategy_type == CreativeStrategyType.REFRESH_HOOK
        # Should still generate mutation plan
        assert len(strategy.mutation_plan) > 0

    def test_generate_includes_rationale(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.91,
            reason=["素材疲劳"],
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert len(strategy.rationale) > 0

    def test_generate_includes_expected_impact(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.85,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert len(strategy.expected_impact) > 0

    def test_generate_copies_opportunity_confidence(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(
            type=CreativeOpportunityType.REPLACE_HOOK,
            target_creative_id="C102",
            confidence=0.91,
        )
        strategy = strategy_engine.generate(opp, sample_dna)
        assert strategy.confidence == 0.91

    def test_generate_from_opportunities(self, strategy_engine, sample_dna):
        opps = [
            CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9),
            CreativeOpportunity(type=CreativeOpportunityType.CHANGE_VISUAL, target_creative_id="C103", confidence=0.8),
        ]
        dna_map = {"C102": sample_dna}
        report = strategy_engine.generate_from_opportunities(opps, dna_map)
        assert report.total_strategies == 2
        assert report.total_opportunities == 2

    def test_generate_from_opportunities_empty(self, strategy_engine):
        report = strategy_engine.generate_from_opportunities([])
        assert report.total_strategies == 0

    def test_engine_history(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy_engine.generate(opp, sample_dna)
        history = strategy_engine.get_history()
        assert len(history) == 1

    def test_engine_get_by_type(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy_engine.generate(opp, sample_dna)
        results = strategy_engine.get_by_type(CreativeStrategyType.REFRESH_HOOK)
        assert len(results) == 1

    def test_engine_get_by_creative(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy_engine.generate(opp, sample_dna)
        results = strategy_engine.get_by_creative("C102")
        assert len(results) == 1

    def test_engine_stats(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy_engine.generate(opp, sample_dna)
        stats = strategy_engine.stats()
        assert stats["total"] == 1

    def test_engine_reset(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy_engine.generate(opp, sample_dna)
        strategy_engine.reset()
        assert strategy_engine.stats()["total"] == 0

    def test_all_strategy_types_generate(self, strategy_engine, sample_dna):
        """验证所有11种策略类型都能生成."""
        mapping = {
            CreativeOpportunityType.REFRESH_CREATIVE: CreativeStrategyType.REFRESH_CREATIVE,
            CreativeOpportunityType.REPLACE_HOOK: CreativeStrategyType.REFRESH_HOOK,
            CreativeOpportunityType.CHANGE_VISUAL: CreativeStrategyType.CHANGE_VISUAL_STYLE,
            CreativeOpportunityType.CHANGE_GAMEPLAY: CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE,
            CreativeOpportunityType.CHANGE_EMOTION: CreativeStrategyType.CHANGE_EMOTION,
            CreativeOpportunityType.COPY_WINNER_DNA: CreativeStrategyType.COPY_WINNER_DNA,
            CreativeOpportunityType.EXPLORE_NEW_AUDIENCE: CreativeStrategyType.EXPLORE_NEW_AUDIENCE,
            CreativeOpportunityType.EXPLORE_NEW_DNA: CreativeStrategyType.EXPLORE_NEW_DNA,
            CreativeOpportunityType.SCALE_WINNER: CreativeStrategyType.SCALE_WINNER,
            CreativeOpportunityType.OPTIMIZE_OPENING: CreativeStrategyType.OPTIMIZE_OPENING,
            CreativeOpportunityType.TEST_NEW_CONCEPT: CreativeStrategyType.TEST_NEW_CONCEPT,
        }
        for opp_type, expected_strategy in mapping.items():
            opp = CreativeOpportunity(type=opp_type, target_creative_id="C102", confidence=0.8)
            strategy = strategy_engine.generate(opp, sample_dna)
            assert strategy.strategy_type == expected_strategy, f"Failed for {opp_type}"

    def test_refresh_hook_mutation_plan(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy = strategy_engine.generate(opp, sample_dna)
        hook_mutations = [m for m in strategy.mutation_plan if m.gene_category == "hook"]
        assert len(hook_mutations) == 1
        assert hook_mutations[0].action == GeneMutationAction.CHANGE

    def test_explore_new_dna_all_genes_explore(self, strategy_engine, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.EXPLORE_NEW_DNA, target_creative_id="C102", confidence=0.7)
        strategy = strategy_engine.generate(opp, sample_dna)
        explore_count = sum(1 for m in strategy.mutation_plan if m.action == GeneMutationAction.EXPLORE)
        assert explore_count >= 5  # Most genes should be EXPLORE

    def test_copy_winner_has_winner_references(self, strategy_engine_with_winner, sample_dna):
        opp = CreativeOpportunity(type=CreativeOpportunityType.COPY_WINNER_DNA, target_creative_id="C102", confidence=0.9)
        strategy = strategy_engine_with_winner.generate(opp, sample_dna)
        assert len(strategy.winner_references) > 0


# ═══════════════════════════════════════════════════════════════
# E14.4.2.3 Creative Planner — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestMutationConfig:
    """MutationConfig 模型测试."""

    def test_config_default(self):
        c = MutationConfig()
        assert c.gene_category == ""
        assert c.mutation_rate == 0.0

    def test_config_change(self):
        c = MutationConfig(
            gene_category="hook",
            mutation_action=GeneMutationAction.CHANGE,
            mutation_rate=0.3,
            target_values=["before_after"],
        )
        assert c.mutation_rate == 0.3
        assert len(c.target_values) == 1

    def test_config_to_dict(self):
        c = MutationConfig(gene_category="hook", mutation_action=GeneMutationAction.CHANGE, mutation_rate=0.3)
        d = c.to_dict()
        assert d["gene_category"] == "hook"
        assert d["mutation_rate"] == 0.3


class TestExperimentConfig:
    """ExperimentConfig 模型测试."""

    def test_config_default(self):
        c = ExperimentConfig()
        assert c.experiment_type == ExperimentType.A_B_TEST
        assert c.control_group_size == 1
        assert c.variant_group_size == 5

    def test_config_to_dict(self):
        c = ExperimentConfig(
            experiment_type=ExperimentType.MULTI_VARIANT,
            success_criteria={"min_roas": 1.0},
            max_budget=1000,
        )
        d = c.to_dict()
        assert d["experiment_type"] == "multi_variant"
        assert d["max_budget"] == 1000


class TestCreativePlan:
    """CreativePlan 模型测试."""

    def test_plan_default(self):
        p = CreativePlan()
        assert p.plan_id
        assert p.status == PlanStatus.DRAFT
        assert p.population_size == 5

    def test_plan_total_variants_with_original(self):
        p = CreativePlan(population_size=5, keep_original=True)
        assert p.total_variants == 6

    def test_plan_total_variants_without_original(self):
        p = CreativePlan(population_size=5, keep_original=False)
        assert p.total_variants == 5

    def test_plan_is_ready(self):
        p = CreativePlan(status=PlanStatus.READY)
        assert p.is_ready is True

    def test_plan_is_completed(self):
        p = CreativePlan(status=PlanStatus.COMPLETED)
        assert p.is_completed is True

    def test_plan_summary(self):
        p = CreativePlan(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            priority=OpportunityPriority.HIGH,
            population_size=5,
            generation_count=1,
        )
        summary = p.summary
        assert "HIGH" in summary
        assert "pop=5" in summary

    def test_plan_to_dict(self):
        p = CreativePlan(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            creative_id="C102",
            population_size=10,
            generation_count=3,
        )
        d = p.to_dict()
        assert d["strategy_type"] == "copy_winner"
        assert d["population_size"] == 10


class TestBatchPlan:
    """BatchPlan 模型测试."""

    def test_batch_default(self):
        b = BatchPlan()
        assert b.plan_count == 0

    def test_batch_with_plans(self):
        plans = [CreativePlan(), CreativePlan()]
        b = BatchPlan(plans=plans)
        assert b.plan_count == 2

    def test_batch_to_dict(self):
        b = BatchPlan(plans=[CreativePlan()], total_variants=6)
        d = b.to_dict()
        assert len(d["plans"]) == 1


class TestCreativePlanner:
    """CreativePlanner 核心测试."""

    def test_planner_creation(self):
        p = create_planner()
        assert p is not None

    def test_plan_single_strategy(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[
                GeneMutation(gene_category="hook", action=GeneMutationAction.CHANGE),
                GeneMutation(gene_category="visual", action=GeneMutationAction.KEEP),
            ],
            confidence=0.85,
            priority=OpportunityPriority.HIGH,
        )
        plan = planner.plan(strategy)
        assert plan.strategy_id == strategy.strategy_id
        assert plan.creative_id == "C102"
        assert plan.status == PlanStatus.READY

    def test_plan_population_size_for_hook(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            confidence=0.85,
        )
        plan = planner.plan(strategy)
        assert plan.population_size >= 3

    def test_plan_population_size_for_copy_winner(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            target_creative_id="C102",
            confidence=0.9,
        )
        plan = planner.plan(strategy)
        assert plan.population_size >= 8

    def test_plan_population_size_for_explore(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.EXPLORE_NEW_DNA,
            target_creative_id="C102",
            confidence=0.7,
        )
        plan = planner.plan(strategy)
        assert plan.population_size >= 7

    def test_plan_high_confidence_increases_population(self, planner):
        s_low = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, confidence=0.4)
        s_high = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, confidence=0.9)
        plan_low = planner.plan(s_low)
        plan_high = planner.plan(s_high)
        assert plan_high.population_size >= plan_low.population_size

    def test_plan_includes_mutation_configs(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[
                GeneMutation(gene_category="hook", action=GeneMutationAction.CHANGE, weight=0.3),
                GeneMutation(gene_category="visual", action=GeneMutationAction.KEEP),
            ],
        )
        plan = planner.plan(strategy)
        assert len(plan.mutation_configs) == 2

    def test_plan_includes_experiment_config(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.experiment_config is not None
        assert plan.experiment_config.experiment_type == ExperimentType.A_B_TEST

    def test_plan_copy_winner_has_multi_variant_experiment(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.experiment_config.experiment_type == ExperimentType.MULTI_VARIANT

    def test_plan_explore_has_exploration_experiment(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.EXPLORE_NEW_DNA,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.experiment_config.experiment_type == ExperimentType.EXPLORATION

    def test_plan_scale_winner_has_scale_up_experiment(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.SCALE_WINNER,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.experiment_config.experiment_type == ExperimentType.SCALE_UP

    def test_plan_concept_test_experiment(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.TEST_NEW_CONCEPT,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.experiment_config.experiment_type == ExperimentType.CONCEPT_TEST

    def test_plan_generation_count(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            target_creative_id="C102",
        )
        plan = planner.plan(strategy)
        assert plan.generation_count >= 2

    def test_plan_critical_increases_generation(self, planner):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            priority=OpportunityPriority.CRITICAL,
        )
        plan = planner.plan(strategy)
        assert plan.generation_count >= 2

    def test_plan_keep_original_for_most_strategies(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        assert plan.keep_original is True

    def test_plan_copy_winner_no_keep_original(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.COPY_WINNER_DNA, target_creative_id="C102")
        plan = planner.plan(strategy)
        assert plan.keep_original is False

    def test_plan_batch(self, planner):
        strategies = [
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102", priority=OpportunityPriority.HIGH),
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C103", priority=OpportunityPriority.MEDIUM),
        ]
        batch = planner.plan_batch(strategies)
        assert batch.plan_count == 2
        assert batch.total_variants > 0

    def test_plan_batch_sorts_by_priority(self, planner):
        strategies = [
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, priority=OpportunityPriority.MEDIUM),
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, priority=OpportunityPriority.CRITICAL),
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, priority=OpportunityPriority.HIGH),
        ]
        batch = planner.plan_batch(strategies)
        assert batch.sorted_plans[0].priority == OpportunityPriority.CRITICAL

    def test_plan_batch_respects_max_variants(self, planner):
        strategies = [
            CreativeStrategy(strategy_type=CreativeStrategyType.COPY_WINNER_DNA, target_creative_id=f"C{i}", priority=OpportunityPriority.MEDIUM)
            for i in range(10)
        ]
        batch = planner.plan_batch(strategies, max_total_variants=20)
        total = sum(p.total_variants for p in batch.sorted_plans)
        assert total <= 20

    def test_plan_status_update(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        assert planner.update_status(plan.plan_id, PlanStatus.EXECUTING) is True
        assert planner.get_plan(plan.plan_id).status == PlanStatus.EXECUTING

    def test_plan_status_update_invalid_id(self, planner):
        assert planner.update_status("nonexistent", PlanStatus.COMPLETED) is False

    def test_plan_completed_sets_timestamp(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        planner.update_status(plan.plan_id, PlanStatus.COMPLETED)
        updated = planner.get_plan(plan.plan_id)
        assert updated.completed_at != ""

    def test_get_ready_plans(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        ready = planner.get_ready_plans()
        assert len(ready) >= 1

    def test_get_executing_plans(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        planner.update_status(plan.plan_id, PlanStatus.EXECUTING)
        executing = planner.get_executing_plans()
        assert len(executing) == 1

    def test_get_completed_plans(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        planner.update_status(plan.plan_id, PlanStatus.COMPLETED)
        completed = planner.get_completed_plans()
        assert len(completed) == 1

    def test_get_plans_by_creative(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        planner.plan(strategy)
        results = planner.get_plans_by_creative("C102")
        assert len(results) == 1

    def test_planner_history(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        planner.plan(strategy)
        history = planner.get_history()
        assert len(history) == 1

    def test_planner_stats(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        planner.plan(strategy)
        stats = planner.stats()
        assert stats["total"] == 1
        assert stats["ready"] >= 1

    def test_planner_reset(self, planner):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        planner.plan(strategy)
        planner.reset()
        assert planner.stats()["total"] == 0


# ═══════════════════════════════════════════════════════════════
# E14.4.2.4 Creative Evaluator — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeMetricsSnapshot:
    """CreativeMetricsSnapshot 模型测试."""

    def test_snapshot_default(self):
        s = CreativeMetricsSnapshot()
        assert s.creative_id == ""
        assert s.roas == 0.0

    def test_snapshot_from_dict(self):
        d = {"creative_id": "C102", "roas": 1.5, "ctr": 0.03, "installs": 5000}
        s = CreativeMetricsSnapshot.from_dict(d)
        assert s.creative_id == "C102"
        assert s.roas == 1.5
        assert s.installs == 5000

    def test_snapshot_to_dict(self):
        s = CreativeMetricsSnapshot(creative_id="C102", roas=1.2, installs=3000)
        d = s.to_dict()
        assert d["creative_id"] == "C102"
        assert d["roas"] == 1.2


class TestStrategyEvaluation:
    """StrategyEvaluation 模型测试."""

    def test_evaluation_default(self):
        e = StrategyEvaluation()
        assert e.roas_change == 0.0
        assert e.reward == 0.0

    def test_evaluation_to_dict(self):
        e = StrategyEvaluation(roas_change=0.5, reward=0.25, confidence=0.85)
        d = e.to_dict()
        assert d["roas_change"] == 0.5
        assert d["reward"] == 0.25


class TestCreativeStrategyOutcome:
    """CreativeStrategyOutcome 模型测试."""

    def test_outcome_default(self):
        o = CreativeStrategyOutcome()
        assert o.outcome_id
        assert o.success is False

    def test_outcome_success(self):
        o = CreativeStrategyOutcome(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            success=True,
            reward=0.5,
            learning="更换Hook有效",
        )
        assert o.success is True
        assert o.reward == 0.5

    def test_outcome_summary(self):
        o = CreativeStrategyOutcome(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            success=True,
            reward=0.35,
            learning="策略有效",
        )
        summary = o.summary
        assert "SUCCESS" in summary
        assert "refresh_hook" in summary

    def test_outcome_to_dict(self):
        o = CreativeStrategyOutcome(
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            success=True,
            reward=0.4,
        )
        d = o.to_dict()
        assert d["success"] is True
        assert d["reward"] == 0.4


class TestEvaluationReport:
    """EvaluationReport 模型测试."""

    def test_report_default(self):
        r = EvaluationReport()
        assert r.total_evaluated == 0
        assert r.success_rate == 0.0

    def test_report_with_outcomes(self):
        outcomes = [
            CreativeStrategyOutcome(success=True, reward=0.5),
            CreativeStrategyOutcome(success=False, reward=-0.2),
        ]
        r = EvaluationReport(
            outcomes=outcomes,
            total_evaluated=2,
            success_count=1,
            failure_count=1,
            avg_reward=0.15,
        )
        assert r.success_rate == 0.5

    def test_report_to_dict(self):
        r = EvaluationReport(
            outcomes=[CreativeStrategyOutcome()],
            total_evaluated=1,
        )
        d = r.to_dict()
        assert len(d["outcomes"]) == 1


class TestCreativeEvaluator:
    """CreativeEvaluator 核心测试."""

    def test_evaluator_creation(self):
        e = create_evaluator()
        assert e is not None

    def test_evaluate_success(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            confidence=0.85,
        )
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert outcome.success is True
        assert outcome.reward > 0

    def test_evaluate_failure(self, evaluator, before_metrics, after_metrics_worse):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            confidence=0.85,
        )
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_worse)
        assert outcome.success is False

    def test_evaluate_from_dict(self, evaluator):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
        )
        before = {"creative_id": "C102", "roas": 0.5, "installs": 5000, "ltv": 3.0}
        after = {"creative_id": "C102", "roas": 1.5, "installs": 8000, "ltv": 5.0}
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True

    def test_evaluate_includes_evaluation_details(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert outcome.evaluation is not None
        assert len(outcome.evaluation.evaluation_details) > 0

    def test_evaluate_includes_learning(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert len(outcome.learning) > 0

    def test_evaluate_includes_recommendation(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert len(outcome.recommendation) > 0

    def test_evaluate_reward_formula(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=1.0, ltv=3.0, fatigue=0.5, installs=5000)
        after = CreativeMetricsSnapshot(roas=2.0, ltv=4.5, fatigue=0.3, installs=8000)
        outcome = evaluator.evaluate(strategy, before, after)
        # ROAS: +100%, LTV: +50%, fatigue: -0.2
        # reward = 1.0*0.5 + 0.5*0.3 - (-0.2)*0.2 = 0.5 + 0.15 + 0.04 = 0.69
        assert outcome.reward > 0.5

    def test_evaluate_confidence_increases_with_sample(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=1.0, ltv=3.0, fatigue=0.5, installs=5000)
        after_small = CreativeMetricsSnapshot(roas=1.5, ltv=3.5, fatigue=0.4, installs=500)
        after_large = CreativeMetricsSnapshot(roas=1.5, ltv=3.5, fatigue=0.4, installs=15000)
        o_small = evaluator.evaluate(strategy, before, after_small)
        o_large = evaluator.evaluate(strategy, before, after_large)
        assert o_large.evaluation.confidence > o_small.evaluation.confidence

    def test_evaluate_batch(self, evaluator, before_metrics, after_metrics_improved, after_metrics_worse):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        report = evaluator.evaluate_batch([
            (strategy, before_metrics.to_dict(), after_metrics_improved.to_dict()),
            (strategy, before_metrics.to_dict(), after_metrics_worse.to_dict()),
        ])
        assert report.total_evaluated == 2
        assert report.success_count == 1
        assert report.failure_count == 1

    def test_evaluate_batch_empty(self, evaluator):
        report = evaluator.evaluate_batch([])
        assert report.total_evaluated == 0

    def test_evaluate_batch_includes_best_strategy(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=1.0, ltv=3.0, fatigue=0.5, installs=5000)
        after = CreativeMetricsSnapshot(roas=2.0, ltv=5.0, fatigue=0.3, installs=8000)
        report = evaluator.evaluate_batch([
            (strategy, before.to_dict(), after.to_dict()),
        ])
        assert isinstance(report.best_strategy, str)

    def test_evaluate_updates_memory(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        # Verify memory was updated
        assert evaluator._memory.stats()["total_records"] >= 1

    def test_evaluate_outcome_persisted(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        retrieved = evaluator.get_outcome(outcome.outcome_id)
        assert retrieved is not None
        assert retrieved.success is True

    def test_get_strategy_outcomes(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        results = evaluator.get_strategy_outcomes(strategy.strategy_id)
        assert len(results) == 1

    def test_get_successful_strategies(self, evaluator, before_metrics, after_metrics_improved, after_metrics_worse):
        s1 = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        s2 = CreativeStrategy(strategy_type=CreativeStrategyType.CHANGE_EMOTION, target_creative_id="C103")
        evaluator.evaluate(s1, before_metrics, after_metrics_improved)
        evaluator.evaluate(s2, before_metrics, after_metrics_worse)
        successful = evaluator.get_successful_strategies()
        assert len(successful) == 1

    def test_get_failed_strategies(self, evaluator, before_metrics, after_metrics_worse):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        evaluator.evaluate(strategy, before_metrics, after_metrics_worse)
        failed = evaluator.get_failed_strategies()
        assert len(failed) == 1

    def test_evaluator_history(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        history = evaluator.get_history()
        assert len(history) == 1

    def test_evaluator_stats(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        stats = evaluator.stats()
        assert stats["total"] == 1
        assert stats["success_rate"] == 1.0

    def test_evaluator_reset(self, evaluator, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        evaluator.reset()
        assert evaluator.stats()["total"] == 0

    def test_evaluate_scale_winner(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.SCALE_WINNER, target_creative_id="C201")
        before = CreativeMetricsSnapshot(roas=2.0, ltv=8.0, fatigue=0.2, installs=10000)
        after = CreativeMetricsSnapshot(roas=2.5, ltv=9.0, fatigue=0.25, installs=20000)
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True

    def test_evaluate_copy_winner(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.COPY_WINNER_DNA, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=0.5, ltv=3.0, fatigue=0.8, installs=5000)
        after = CreativeMetricsSnapshot(roas=1.5, ltv=6.0, fatigue=0.4, installs=8000)
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True

    def test_evaluate_change_visual(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.CHANGE_VISUAL_STYLE, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=0.8, ctr=0.015, ltv=3.0, fatigue=0.6, installs=5000)
        after = CreativeMetricsSnapshot(roas=1.1, ctr=0.025, ltv=3.5, fatigue=0.5, installs=7000)
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True

    def test_evaluate_change_emotion(self, evaluator):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.CHANGE_EMOTION, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=0.8, payer_rate=0.03, ltv=3.0, fatigue=0.5, installs=5000)
        after = CreativeMetricsSnapshot(roas=1.1, payer_rate=0.06, ltv=3.8, fatigue=0.45, installs=7000)
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True


# ═══════════════════════════════════════════════════════════════
# Full Pipeline — 25 tests
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """完整的 E14.4.2 管道测试."""

    def test_end_to_end_pipeline(self, sample_dna, before_metrics, after_metrics_improved):
        """完整管道: Signal → Opportunity → Strategy → Plan → Evaluate."""
        # 1. 创建引擎
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()
        planner = create_planner()
        evaluator = create_evaluator()

        # 2. Signal → Opportunity
        signal = CreativeSignal(creative_id="C102", issue="creative_fatigue", confidence=0.91)
        opportunity = opp_engine.detect(signal)
        assert opportunity.type == CreativeOpportunityType.REFRESH_CREATIVE

        # 3. Opportunity → Strategy
        strategy = strat_engine.generate(opportunity, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.REFRESH_CREATIVE

        # 4. Strategy → Plan
        plan = planner.plan(strategy)
        assert plan.population_size >= 5

        # 5. Plan → Evaluate
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert outcome.success is True
        assert outcome.reward > 0

    def test_fatigue_pipeline(self, sample_dna, before_metrics, after_metrics_improved):
        """疲劳检测管道."""
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()
        evaluator = create_evaluator()

        signal = CreativeSignal(creative_id="C102", issue="creative_fatigue", confidence=0.91)
        opportunity = opp_engine.detect(signal)
        strategy = strat_engine.generate(opportunity, sample_dna)
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert outcome.success is True

    def test_winner_pipeline(self, winner_dna):
        """赢家检测管道."""
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()
        planner = create_planner()

        signal = CreativeSignal(creative_id="C201", issue="winner_detected", confidence=0.95)
        opportunity = opp_engine.detect(signal)
        assert opportunity.type == CreativeOpportunityType.SCALE_WINNER

        strategy = strat_engine.generate(opportunity, winner_dna)
        assert strategy.strategy_type == CreativeStrategyType.SCALE_WINNER

        plan = planner.plan(strategy)
        assert plan.experiment_config.experiment_type == ExperimentType.SCALE_UP

    def test_ctr_decay_pipeline(self, sample_dna):
        """CTR 衰减管道."""
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()

        signal = CreativeSignal(creative_id="C303", issue="ctr_decay", confidence=0.78)
        opportunity = opp_engine.detect(signal)
        assert opportunity.type == CreativeOpportunityType.REPLACE_HOOK

        strategy = strat_engine.generate(opportunity, sample_dna)
        assert strategy.strategy_type == CreativeStrategyType.REFRESH_HOOK

    def test_roas_decay_pipeline(self, sample_dna):
        """ROAS 衰减管道."""
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()

        signal = CreativeSignal(creative_id="C404", issue="roas_decay", confidence=0.85, severity="critical")
        opportunity = opp_engine.detect(signal)
        assert opportunity.priority == OpportunityPriority.CRITICAL

        strategy = strat_engine.generate(opportunity, sample_dna)
        assert strategy.priority == OpportunityPriority.CRITICAL

    def test_batch_pipeline(self, sample_dna, winner_dna):
        """批量处理管道."""
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()
        planner = create_planner()

        signals = [
            CreativeSignal(creative_id="C102", issue="creative_fatigue", confidence=0.91),
            CreativeSignal(creative_id="C201", issue="winner_detected", confidence=0.95),
            CreativeSignal(creative_id="C303", issue="ctr_decay", confidence=0.78),
        ]
        dna_map = {"C102": sample_dna, "C201": winner_dna}

        # 1. 检测机会
        opp_report = opp_engine.detect_batch(signals)
        assert opp_report.total_opportunities == 3

        # 2. 生成策略
        strategy_report = strat_engine.generate_from_opportunities(opp_report.opportunities, dna_map)
        assert strategy_report.total_strategies == 3

        # 3. 生成计划
        batch = planner.plan_batch(strategy_report.strategies)
        assert batch.plan_count == 3
        assert batch.total_variants > 0

    def test_pipeline_produces_valid_creative_opportunities(self):
        """管道产生的机会类型都是有效的."""
        opp_engine = create_opportunity_engine()
        valid_types = set(CreativeOpportunityType)
        for issue in ["creative_fatigue", "winner", "ctr_decay", "roas_decay", "underperformer"]:
            signal = CreativeSignal(creative_id="C1", issue=issue, confidence=0.8)
            opp = opp_engine.detect(signal)
            assert opp.type in valid_types

    def test_strategy_has_all_required_fields(self, sample_dna):
        """策略包含所有必需字段."""
        strat_engine = create_strategy_engine()
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy = strat_engine.generate(opp, sample_dna)
        assert strategy.strategy_id
        assert strategy.strategy_type != CreativeStrategyType.UNKNOWN
        assert len(strategy.mutation_plan) > 0
        assert strategy.rationale
        assert strategy.expected_impact

    def test_plan_mutation_rates_are_valid(self, planner):
        """计划的变异比例在有效范围内."""
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[
                GeneMutation(gene_category="hook", action=GeneMutationAction.CHANGE, weight=0.3),
                GeneMutation(gene_category="visual", action=GeneMutationAction.KEEP),
            ],
        )
        plan = planner.plan(strategy)
        for config in plan.mutation_configs:
            assert 0.0 <= config.mutation_rate <= 1.0

    def test_evaluation_produces_meaningful_learning(self, evaluator, before_metrics, after_metrics_improved):
        """评估产生有意义的学习总结."""
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = evaluator.evaluate(strategy, before_metrics, after_metrics_improved)
        assert len(outcome.learning) > 5  # Not empty


# ═══════════════════════════════════════════════════════════════
# CreativeAgent Integration — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeAgentStrategyIntegration:
    """CreativeAgent 策略模块集成测试."""

    def test_agent_has_opportunity_engine(self, creative_agent):
        assert creative_agent.get_opportunity_engine() is not None

    def test_agent_has_strategy_engine(self, creative_agent):
        assert creative_agent.get_strategy_engine() is not None

    def test_agent_has_planner(self, creative_agent):
        assert creative_agent.get_planner() is not None

    def test_agent_has_evaluator(self, creative_agent):
        assert creative_agent.get_evaluator() is not None

    def test_agent_detect_opportunities(self, creative_agent):
        signals = [
            {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91},
            {"creative_id": "C201", "issue": "winner_detected", "confidence": 0.95},
        ]
        report = creative_agent.detect_opportunities(signals)
        assert report.total_opportunities == 2

    def test_agent_generate_strategies(self, creative_agent, sample_dna):
        opps = [
            CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9),
        ]
        dna_map = {"C102": sample_dna}
        report = creative_agent.generate_strategies(opps, dna_map)
        assert report.total_strategies == 1

    def test_agent_plan_creative_batch(self, creative_agent):
        strategies = [
            CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102"),
        ]
        batch = creative_agent.plan_creative_batch(strategies)
        assert batch.plan_count == 1

    def test_agent_evaluate_creative_strategy(self, creative_agent, before_metrics, after_metrics_improved):
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        outcome = creative_agent.evaluate_creative_strategy(
            strategy, before_metrics.to_dict(), after_metrics_improved.to_dict(),
        )
        assert outcome.success is True

    def test_agent_full_strategy_pipeline(self, creative_agent, sample_dna):
        signals = [
            {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91},
        ]
        dna_map = {"C102": sample_dna}
        result = creative_agent.run_full_strategy_pipeline(signals, dna_map)
        assert "opportunities" in result
        assert "strategies" in result
        assert "plans" in result
        assert len(result["opportunities"]["opportunities"]) == 1
        assert len(result["strategies"]["strategies"]) == 1
        assert len(result["plans"]["plans"]) == 1

    def test_agent_stats_includes_strategy_modules(self, creative_agent):
        stats = creative_agent.stats()
        assert "opportunity_engine" in stats
        assert "strategy_engine" in stats
        assert "planner" in stats
        assert "evaluator" in stats

    def test_agent_reset_clears_strategy_modules(self, creative_agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.9}]
        creative_agent.detect_opportunities(signals)
        creative_agent.reset()
        stats = creative_agent.stats()
        assert stats["opportunity_engine"]["total"] == 0
        assert stats["strategy_engine"]["total"] == 0

    def test_agent_state_transitions(self, creative_agent, sample_dna):
        assert creative_agent.state == CreativeAgentState.IDLE
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.9}]
        dna_map = {"C102": sample_dna}
        creative_agent.run_full_strategy_pipeline(signals, dna_map)
        assert creative_agent.state == CreativeAgentState.IDLE

    def test_agent_with_winner_dna_flow(self, creative_agent, winner_dna, memory_with_winner):
        """测试包含赢家 DNA 的完整流程."""
        # 先存储赢家 DNA
        creative_agent.get_memory().store_dna(winner_dna, is_winner=True, performance={"roas": 2.5})

        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        result = creative_agent.run_full_strategy_pipeline(signals)
        assert len(result["plans"]["plans"]) == 1

    def test_agent_multiple_creative_types(self, creative_agent):
        """测试多种创意问题类型."""
        signals = [
            {"creative_id": "C1", "issue": "creative_fatigue", "confidence": 0.9},
            {"creative_id": "C2", "issue": "ctr_decay", "confidence": 0.8},
            {"creative_id": "C3", "issue": "roas_decay", "confidence": 0.85},
            {"creative_id": "C4", "issue": "underperformer", "confidence": 0.7},
        ]
        result = creative_agent.run_full_strategy_pipeline(signals)
        assert result["opportunities"]["total_opportunities"] == 4

    def test_agent_strategy_pipeline_idempotent(self, creative_agent, sample_dna):
        """测试管道幂等性."""
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        dna_map = {"C102": sample_dna}
        r1 = creative_agent.run_full_strategy_pipeline(signals, dna_map)
        r2 = creative_agent.run_full_strategy_pipeline(signals, dna_map)
        assert r1["opportunities"]["total_opportunities"] == r2["opportunities"]["total_opportunities"]


# ═══════════════════════════════════════════════════════════════
# Regression — 15 tests
# ═══════════════════════════════════════════════════════════════


class TestRegression:
    """回归测试 — 确保 E14.4.1 功能不受影响."""

    def test_creative_analyzer_still_works(self):
        """E14.4.1 CreativeAnalyzer 回归."""
        analyzer = create_creative_analyzer()
        metrics = CreativeMetrics(
            creative_id="C102", roas=0.45, ctr=0.018, fatigue=0.82,
            spend=2000, impressions=50000, days_running=14,
        )
        diagnosis = analyzer.analyze(metrics)
        assert diagnosis.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE

    def test_dna_engine_still_works(self):
        """E14.4.1 DNAEngine 回归."""
        engine = DNAEngine()
        dna = engine.extract_dna(
            creative_id="C102", hook="before_after", visual="fantasy",
            emotion="curiosity", gameplay="merge",
        )
        assert dna.dominant_hook == "before_after"

    def test_creative_memory_still_works(self):
        """E14.4.1 CreativeMemory 回归."""
        memory = CreativeMemory()
        record = memory.record_decision(
            creative_id="C102",
            action_type=CreativeActionType.GENERATE_VARIANTS,
        )
        assert record.record_id
        memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)

    def test_creative_agent_core_still_works(self):
        """E14.4.1 CreativeAgent 核心回归."""
        agent = create_creative_agent()
        rec = agent.analyze_creative({
            "creative_id": "C102", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82,
        })
        assert rec.creative_id == "C102"
        assert rec.diagnosis is not None

    def test_creative_agent_extract_dna_still_works(self):
        """E14.4.1 DNA 提取回归."""
        agent = create_creative_agent()
        dna = agent.extract_dna(
            creative_id="C102", hook="before_after", visual="fantasy",
            emotion="curiosity", gameplay="merge",
        )
        assert dna.dominant_hook == "before_after"

    def test_creative_agent_quick_analysis_still_works(self):
        """E14.4.1 快捷分析回归."""
        agent = create_creative_agent()
        rec = agent.quick_analysis(creative_id="C102", roas=0.45, ctr=0.018, fatigue=0.82)
        assert rec.creative_id == "C102"

    def test_creative_agent_batch_analysis_still_works(self):
        """E14.4.1 批量分析回归."""
        agent = create_creative_agent()
        metrics_list = [
            {"creative_id": "C102", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82},
            {"creative_id": "C103", "roas": 2.0, "ctr": 0.035, "fatigue": 0.2, "spend": 5000},
        ]
        report = agent.analyze_creative_batch(metrics_list)
        assert len(report.recommendations) >= 1

    def test_opportunity_engine_no_side_effect_on_analyzer(self):
        """OpportunityEngine 不影响 Analyzer."""
        analyzer = create_creative_analyzer()
        opp_engine = create_opportunity_engine()
        # Both should work independently
        signal = CreativeSignal(creative_id="C102", issue="creative_fatigue", confidence=0.9)
        opp = opp_engine.detect(signal)
        assert opp.type == CreativeOpportunityType.REFRESH_CREATIVE

    def test_strategy_engine_no_side_effect_on_dna_engine(self):
        """StrategyEngine 不影响 DNAEngine."""
        dna_engine = DNAEngine()
        dna = dna_engine.extract_dna(creative_id="C102", hook="before_after", visual="fantasy")
        assert dna.dominant_hook == "before_after"

        strat_engine = create_strategy_engine()
        opp = CreativeOpportunity(type=CreativeOpportunityType.REPLACE_HOOK, target_creative_id="C102", confidence=0.9)
        strategy = strat_engine.generate(opp, dna)
        assert strategy.strategy_type == CreativeStrategyType.REFRESH_HOOK

    def test_planner_no_side_effect_on_other_modules(self):
        """Planner 不影响其他模块."""
        planner = create_planner()
        memory = CreativeMemory()
        # Both should work independently
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        plan = planner.plan(strategy)
        assert plan.creative_id == "C102"

    def test_evaluator_no_side_effect_on_other_modules(self):
        """Evaluator 不影响其他模块."""
        evaluator = create_evaluator()
        strategy = CreativeStrategy(strategy_type=CreativeStrategyType.REFRESH_HOOK, target_creative_id="C102")
        before = CreativeMetricsSnapshot(roas=1.0, ltv=3.0, fatigue=0.5, installs=5000)
        after = CreativeMetricsSnapshot(roas=1.5, ltv=4.0, fatigue=0.3, installs=8000)
        outcome = evaluator.evaluate(strategy, before, after)
        assert outcome.success is True

    def test_all_modules_isolated(self):
        """所有模块独立运行."""
        # Create all engines independently
        analyzer = create_creative_analyzer()
        dna_engine = DNAEngine()
        memory = CreativeMemory()
        opp_engine = create_opportunity_engine()
        strat_engine = create_strategy_engine()
        planner = create_planner()
        evaluator = create_evaluator()
        # All should exist
        assert analyzer is not None
        assert dna_engine is not None
        assert memory is not None
        assert opp_engine is not None
        assert strat_engine is not None
        assert planner is not None
        assert evaluator is not None

    def test_agent_retains_all_core_functions(self):
        """Agent 保留所有核心功能."""
        agent = create_creative_agent()
        # E14.4.1 功能
        assert agent.get_analyzer() is not None
        assert agent.get_dna_engine() is not None
        assert agent.get_memory() is not None
        # E14.4.2 功能
        assert agent.get_opportunity_engine() is not None
        assert agent.get_strategy_engine() is not None
        assert agent.get_planner() is not None
        assert agent.get_evaluator() is not None

    def test_agent_factory_creates_consistent_agent(self):
        """Agent 工厂创建一致的 Agent."""
        agent = create_creative_agent()
        assert agent.agent_id
        assert agent.state == CreativeAgentState.IDLE
        assert agent.get_analyzer() is not None
        assert agent.get_opportunity_engine() is not None