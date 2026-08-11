"""E14.4.1 Creative Intelligence Foundation — 集成测试.

验证 Creative Agent 的基础功能:
  - CreativeMetrics & Models (15)
  - CreativeAnalyzer (25)
  - DNAEngine (25)
  - CreativeMemory (20)
  - CreativeAgent Core (30)
  - Integration & Communication (15)
  - Regression (10)

总计: 140 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    MessageBus,
    AgentRegistry,
    AgentRole,
    AgentStatus,
    create_default_organization,
    create_message_bus,
    create_agent_registry,
    StandardMessageType,
    MessagePriority,
    MessageType,
    create_ua_agent_identity as comm_ua_identity,
    create_creative_agent_identity as comm_creative_identity,
    create_supervisor_agent_identity as comm_supervisor_identity,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent import (
    # analyzer
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosis,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    CreativeAnalysisReport,
    CreativeThresholds,
    DEFAULT_CREATIVE_THRESHOLDS,
    create_creative_analyzer,
    # dna_engine
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    DNAComparisonResult,
    WinnerDNAReport,
    HookType,
    VisualStyle,
    EmotionType,
    GameplayFocus,
    MonetizationType,
    AudienceType,
    ContextType,
    create_dna_engine,
    # memory
    CreativeMemory,
    CreativeDecisionRecord,
    CreativeDecisionOutcome,
    CreativeActionType,
    CreativeExperienceEntry,
    CreativeDNAMemoryEntry,
    create_creative_memory,
    # creative_agent
    CreativeAgent,
    CreativeAgentState,
    CreativeRecommendation,
    CreativeReport,
    create_creative_agent,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def fatigue_metrics():
    """疲劳素材指标."""
    return CreativeMetrics(
        creative_id="C101", creative_name="Fatigue Creative",
        roas=0.45, ctr=0.018, fatigue=0.82, frequency=6.0,
        spend=2000, impressions=50000, days_running=14,
        cvr=0.03, cpi=3.5, payer_rate=0.04, ltv=3.2,
    )


@pytest.fixture
def winner_metrics():
    """赢家素材指标."""
    return CreativeMetrics(
        creative_id="C102", creative_name="Winner Creative",
        roas=2.1, ctr=0.035, fatigue=0.2, frequency=2.5,
        spend=8000, impressions=120000, days_running=21,
        cvr=0.06, cpi=1.2, payer_rate=0.08, ltv=8.5,
    )


@pytest.fixture
def underperformer_metrics():
    """低效素材指标."""
    return CreativeMetrics(
        creative_id="C103", creative_name="Underperformer Creative",
        roas=0.3, ctr=0.008, fatigue=0.3, frequency=2.0,
        spend=1000, impressions=8000, days_running=7,
        cvr=0.02, cpi=4.5, payer_rate=0.02, ltv=2.0,
    )


@pytest.fixture
def new_creative_metrics():
    """新素材指标."""
    return CreativeMetrics(
        creative_id="C104", creative_name="New Creative",
        roas=0.0, ctr=0.015, fatigue=0.0, frequency=1.0,
        spend=100, impressions=2000, days_running=1,
        cvr=0.0, cpi=0.0, payer_rate=0.0, ltv=0.0,
    )


@pytest.fixture
def high_potential_metrics():
    """高潜力素材指标."""
    return CreativeMetrics(
        creative_id="C105", creative_name="High Potential Creative",
        roas=1.2, ctr=0.025, fatigue=0.1, frequency=1.8,
        spend=500, impressions=6000, days_running=3,
        cvr=0.04, cpi=1.8, payer_rate=0.05, ltv=5.0,
    )


@pytest.fixture
def saturated_metrics():
    """受众饱和素材指标."""
    return CreativeMetrics(
        creative_id="C106", creative_name="Saturated Creative",
        roas=1.1, ctr=0.02, fatigue=0.3, frequency=8.0,
        spend=3000, impressions=80000, days_running=30,
        cvr=0.04, cpi=2.0, payer_rate=0.05, ltv=5.5,
    )


@pytest.fixture
def stable_metrics():
    """稳定素材指标."""
    return CreativeMetrics(
        creative_id="C107", creative_name="Stable Creative",
        roas=1.1, ctr=0.015, fatigue=0.3, frequency=2.0,
        spend=3000, impressions=30000, days_running=10,
        cvr=0.03, cpi=2.0, payer_rate=0.04, ltv=4.0,
    )


@pytest.fixture
def analyzer():
    return CreativeAnalyzer()


@pytest.fixture
def dna_engine():
    return DNAEngine()


@pytest.fixture
def memory():
    return CreativeMemory()


@pytest.fixture
def agent():
    return create_creative_agent()


@pytest.fixture
def sample_dna_full():
    """完整 7 基因 DNA."""
    return CreativeDNAProfile(
        creative_id="C102",
        creative_name="Winner Creative",
        genes={
            "hook": CreativeGene(name="hook", value="before_after", category="hook", confidence=0.9, weight=0.25, source="creative_agent"),
            "visual": CreativeGene(name="visual", value="fantasy", category="visual", confidence=0.85, weight=0.15, source="creative_agent"),
            "gameplay": CreativeGene(name="gameplay", value="merge", category="gameplay", confidence=0.8, weight=0.15, source="creative_agent"),
            "monetization": CreativeGene(name="monetization", value="iap", category="monetization", confidence=0.9, weight=0.1, source="creative_agent"),
            "emotion": CreativeGene(name="emotion", value="curiosity", category="emotion", confidence=0.85, weight=0.15, source="creative_agent"),
            "audience": CreativeGene(name="audience", value="casual_gamers", category="audience", confidence=0.8, weight=0.1, source="creative_agent"),
            "context": CreativeGene(name="context", value="weekend", category="context", confidence=0.7, weight=0.1, source="creative_agent"),
        },
        fitness={"roas": 2.1, "ctr": 0.035, "cvr": 0.06},
    )


@pytest.fixture
def sample_dna_variant():
    """变体 DNA (仅 hook 不同)."""
    return CreativeDNAProfile(
        creative_id="C201",
        creative_name="Variant Creative",
        generation=1,
        parent_id="",
        genes={
            "hook": CreativeGene(name="hook", value="challenge", category="hook", confidence=0.85, weight=0.25, source="creative_agent"),
            "visual": CreativeGene(name="visual", value="fantasy", category="visual", confidence=0.85, weight=0.15, source="creative_agent"),
            "gameplay": CreativeGene(name="gameplay", value="merge", category="gameplay", confidence=0.8, weight=0.15, source="creative_agent"),
            "monetization": CreativeGene(name="monetization", value="iap", category="monetization", confidence=0.9, weight=0.1, source="creative_agent"),
            "emotion": CreativeGene(name="emotion", value="curiosity", category="emotion", confidence=0.85, weight=0.15, source="creative_agent"),
            "audience": CreativeGene(name="audience", value="casual_gamers", category="audience", confidence=0.8, weight=0.1, source="creative_agent"),
            "context": CreativeGene(name="context", value="weekend", category="context", confidence=0.7, weight=0.1, source="creative_agent"),
        },
        fitness={"roas": 1.4, "ctr": 0.025, "cvr": 0.045},
    )


@pytest.fixture
def sample_dna_different():
    """完全不同的 DNA."""
    return CreativeDNAProfile(
        creative_id="C301",
        creative_name="Different Creative",
        genes={
            "hook": CreativeGene(name="hook", value="rescue", category="hook", confidence=0.8, weight=0.25, source="creative_agent"),
            "visual": CreativeGene(name="visual", value="dark", category="visual", confidence=0.8, weight=0.15, source="creative_agent"),
            "gameplay": CreativeGene(name="gameplay", value="puzzle", category="gameplay", confidence=0.8, weight=0.15, source="creative_agent"),
            "monetization": CreativeGene(name="monetization", value="iaa", category="monetization", confidence=0.8, weight=0.1, source="creative_agent"),
            "emotion": CreativeGene(name="emotion", value="fear", category="emotion", confidence=0.8, weight=0.15, source="creative_agent"),
            "audience": CreativeGene(name="audience", value="midcore_gamers", category="audience", confidence=0.8, weight=0.1, source="creative_agent"),
            "context": CreativeGene(name="context", value="competitive", category="context", confidence=0.8, weight=0.1, source="creative_agent"),
        },
        fitness={"roas": 0.8, "ctr": 0.015, "cvr": 0.02},
    )


# ═══════════════════════════════════════════════════════════════
# Part 1: CreativeMetrics & Models
# ═══════════════════════════════════════════════════════════════


class TestCreativeMetrics:
    """CreativeMetrics 模型测试 (15)."""

    def test_create_default(self):
        m = CreativeMetrics()
        assert m.creative_id == ""
        assert m.roas == 0.0
        assert m.platform == "meta"

    def test_create_with_values(self):
        m = CreativeMetrics(creative_id="C001", roas=1.5, ctr=0.03, fatigue=0.4)
        assert m.creative_id == "C001"
        assert m.roas == 1.5
        assert m.ctr == 0.03
        assert m.fatigue == 0.4

    def test_to_dict_roundtrip(self):
        m = CreativeMetrics(creative_id="C001", roas=1.5, ctr=0.03, spend=1000, impressions=50000)
        d = m.to_dict()
        assert d["creative_id"] == "C001"
        assert d["roas"] == 1.5
        assert d["ctr"] == 0.03
        assert d["spend"] == 1000
        assert d["impressions"] == 50000

    def test_from_dict(self):
        data = {"creative_id": "C001", "roas": 1.5, "ctr": 0.03, "spend": 1000, "impressions": 50000, "days_running": 7}
        m = CreativeMetrics.from_dict(data)
        assert m.creative_id == "C001"
        assert m.roas == 1.5
        assert m.ctr == 0.03
        assert m.spend == 1000
        assert m.impressions == 50000
        assert m.days_running == 7

    def test_from_dict_defaults(self):
        m = CreativeMetrics.from_dict({})
        assert m.creative_id == ""
        assert m.roas == 0.0
        assert m.platform == "meta"

    def test_timestamp_default(self):
        m = CreativeMetrics()
        assert m.timestamp != ""

    def test_metadata_default(self):
        m = CreativeMetrics()
        assert m.metadata == {}

    def test_metadata_custom(self):
        m = CreativeMetrics(metadata={"source": "adjust", "period": "7d"})
        assert m.metadata["source"] == "adjust"
        assert m.metadata["period"] == "7d"

    def test_all_fields_serializable(self, fatigue_metrics):
        d = fatigue_metrics.to_dict()
        assert "creative_id" in d
        assert "creative_name" in d
        assert "campaign_id" in d
        assert "platform" in d
        assert "spend" in d
        assert "revenue" in d
        assert "roas" in d
        assert "ctr" in d
        assert "cvr" in d
        assert "cpi" in d
        assert "fatigue" in d
        assert "frequency" in d
        assert "impressions" in d
        assert "installs" in d
        assert "payer_rate" in d
        assert "ltv" in d
        assert "d7_retention" in d
        assert "days_running" in d
        assert "timestamp" in d
        assert "metadata" in d

    def test_from_dict_to_dict_roundtrip(self, fatigue_metrics):
        d = fatigue_metrics.to_dict()
        m2 = CreativeMetrics.from_dict(d)
        assert m2.creative_id == fatigue_metrics.creative_id
        assert m2.roas == fatigue_metrics.roas
        assert m2.ctr == fatigue_metrics.ctr
        assert m2.fatigue == fatigue_metrics.fatigue

    def test_float_coercion(self):
        m = CreativeMetrics.from_dict({"roas": "1.5", "ctr": "0.03", "spend": "1000"})
        assert m.roas == 1.5
        assert m.ctr == 0.03
        assert m.spend == 1000

    def test_int_coercion(self):
        m = CreativeMetrics.from_dict({"impressions": "50000", "installs": "1000"})
        assert m.impressions == 50000
        assert m.installs == 1000
        assert isinstance(m.impressions, int)
        assert isinstance(m.installs, int)

    def test_creative_diagnosis_default(self):
        d = CreativeDiagnosis()
        assert d.diagnosis_type == CreativeDiagnosisType.UNKNOWN
        assert d.confidence == 0.0
        assert d.evidence == []

    def test_creative_diagnosis_properties(self):
        d = CreativeDiagnosis(
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            severity=CreativeDiagnosisSeverity.CRITICAL,
            confidence=0.9,
            evidence=["e1", "e2"],
        )
        assert d.is_critical is True
        assert d.is_positive is False
        assert "CRITICAL" in d.summary
        assert "creative_fatigue" in d.summary

    def test_creative_diagnosis_to_dict(self):
        d = CreativeDiagnosis(
            creative_id="C001", diagnosis_type=CreativeDiagnosisType.WINNER,
            severity=CreativeDiagnosisSeverity.POSITIVE, confidence=0.9,
        )
        result = d.to_dict()
        assert result["diagnosis_type"] == "winner"
        assert result["severity"] == "positive"
        assert result["confidence"] == 0.9


# ═══════════════════════════════════════════════════════════════
# Part 2: CreativeAnalyzer
# ═══════════════════════════════════════════════════════════════


class TestCreativeAnalyzerDiagnosis:
    """CreativeAnalyzer 诊断类型测试 (15)."""

    def test_diagnose_fatigue(self, analyzer, fatigue_metrics):
        d = analyzer.analyze(fatigue_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert d.confidence > 0.7
        assert len(d.evidence) >= 1

    def test_diagnose_winner(self, analyzer, winner_metrics):
        d = analyzer.analyze(winner_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.WINNER
        assert d.severity == CreativeDiagnosisSeverity.POSITIVE

    def test_diagnose_underperformer(self, analyzer, underperformer_metrics):
        d = analyzer.analyze(underperformer_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER

    def test_diagnose_new_creative(self, analyzer, new_creative_metrics):
        d = analyzer.analyze(new_creative_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.NEW_CREATIVE
        assert d.severity == CreativeDiagnosisSeverity.INFO

    def test_diagnose_high_potential(self, analyzer, high_potential_metrics):
        d = analyzer.analyze(high_potential_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.HIGH_POTENTIAL

    def test_diagnose_saturated(self, analyzer, saturated_metrics):
        d = analyzer.analyze(saturated_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.SATURATED

    def test_diagnose_stable(self, analyzer, stable_metrics):
        d = analyzer.analyze(stable_metrics)
        assert d.diagnosis_type == CreativeDiagnosisType.STABLE

    def test_fatigue_confidence(self, analyzer):
        m = CreativeMetrics(creative_id="C001", fatigue=0.9, days_running=10, impressions=10000, roas=0.5)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert d.confidence >= 0.9

    def test_fatigue_severity_critical(self, analyzer):
        m = CreativeMetrics(creative_id="C001", fatigue=0.85, days_running=10, impressions=10000, roas=0.4)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert d.severity == CreativeDiagnosisSeverity.CRITICAL

    def test_fatigue_severity_warning(self, analyzer):
        m = CreativeMetrics(creative_id="C001", fatigue=0.65, days_running=5, impressions=10000, roas=0.8)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert d.severity == CreativeDiagnosisSeverity.WARNING

    def test_winner_with_elevated_fatigue(self, analyzer):
        m = CreativeMetrics(creative_id="C001", roas=2.0, spend=1000, fatigue=0.55, impressions=10000, days_running=5)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.WINNER
        assert d.confidence < 0.8

    def test_underperformer_severity_critical(self, analyzer):
        m = CreativeMetrics(creative_id="C001", roas=0.2, impressions=10000, days_running=5)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER
        assert d.severity == CreativeDiagnosisSeverity.CRITICAL

    def test_diagnosis_has_expected_impact(self, analyzer, fatigue_metrics):
        d = analyzer.analyze(fatigue_metrics)
        assert d.expected_impact != ""

    def test_diagnosis_has_recommendation(self, analyzer, fatigue_metrics):
        d = analyzer.analyze(fatigue_metrics)
        assert d.recommendation != ""

    def test_diagnosis_priority_order(self, analyzer):
        """疲劳检测优先于W在赢家/饱和之前."""
        m = CreativeMetrics(creative_id="C001", fatigue=0.8, roas=2.5, spend=1000, frequency=7.0, impressions=10000, days_running=10)
        d = analyzer.analyze(m)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE


class TestCreativeAnalyzerBatch:
    """CreativeAnalyzer 批量分析测试 (5)."""

    def test_analyze_batch(self, analyzer, fatigue_metrics, winner_metrics, underperformer_metrics,
                           new_creative_metrics, high_potential_metrics):
        report = analyzer.analyze_batch([fatigue_metrics, winner_metrics, underperformer_metrics,
                                          new_creative_metrics, high_potential_metrics])
        assert report.total_creatives == 5
        assert report.diagnosis_count == 5
        assert report.winner_count >= 1
        assert report.fatigue_count >= 1
        assert report.underperformer_count >= 1

    def test_analyze_batch_empty(self, analyzer):
        report = analyzer.analyze_batch([])
        assert report.total_creatives == 0
        assert report.diagnosis_count == 0

    def test_detect_winners(self, analyzer, winner_metrics, fatigue_metrics):
        winners = analyzer.detect_winners([winner_metrics, fatigue_metrics])
        assert len(winners) == 1
        assert winners[0].creative_id == winner_metrics.creative_id

    def test_detect_fatigue(self, analyzer, fatigue_metrics, winner_metrics):
        fatigued = analyzer.detect_fatigue([fatigue_metrics, winner_metrics])
        assert len(fatigued) == 1
        assert fatigued[0].creative_id == fatigue_metrics.creative_id

    def test_detect_underperformers(self, analyzer, underperformer_metrics, winner_metrics):
        unders = analyzer.detect_underperformers([underperformer_metrics, winner_metrics])
        assert len(unders) == 1
        assert unders[0].creative_id == underperformer_metrics.creative_id


class TestCreativeAnalyzerQuick:
    """CreativeAnalyzer 快捷分析测试 (5)."""

    def test_quick_analysis_fatigue(self, analyzer):
        d = analyzer.quick_analysis(creative_id="C001", roas=0.4, ctr=0.01, fatigue=0.85, days_running=7, impressions=6000)
        assert d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE

    def test_quick_analysis_winner(self, analyzer):
        d = analyzer.quick_analysis(creative_id="C001", roas=2.0, ctr=0.03, fatigue=0.2, spend=1000, days_running=7, impressions=6000)
        assert d.diagnosis_type == CreativeDiagnosisType.WINNER

    def test_quick_analysis_new(self, analyzer):
        d = analyzer.quick_analysis(creative_id="C001", roas=0.0, ctr=0.01, fatigue=0.0, days_running=1, impressions=1000)
        assert d.diagnosis_type == CreativeDiagnosisType.NEW_CREATIVE

    def test_quick_analysis_saturated(self, analyzer):
        d = analyzer.quick_analysis(creative_id="C001", roas=1.2, ctr=0.02, fatigue=0.3, frequency=6.0, days_running=7, impressions=6000)
        assert d.diagnosis_type == CreativeDiagnosisType.SATURATED

    def test_quick_analysis_underperformer(self, analyzer):
        d = analyzer.quick_analysis(creative_id="C001", roas=0.3, ctr=0.01, fatigue=0.1, days_running=7, impressions=6000)
        assert d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER


# ═══════════════════════════════════════════════════════════════
# Part 3: DNAEngine
# ═══════════════════════════════════════════════════════════════


class TestCreativeGene:
    """CreativeGene 模型测试 (5)."""

    def test_create_gene(self):
        g = CreativeGene(name="hook", value="before_after", category="hook", confidence=0.9, weight=0.25)
        assert g.name == "hook"
        assert g.value == "before_after"
        assert g.category == "hook"
        assert g.confidence == 0.9
        assert g.weight == 0.25

    def test_gene_to_dict(self):
        g = CreativeGene(name="hook", value="before_after", category="hook", confidence=0.9, weight=0.25, source="agent")
        d = g.to_dict()
        assert d["name"] == "hook"
        assert d["value"] == "before_after"
        assert d["confidence"] == 0.9
        assert d["source"] == "agent"

    def test_gene_from_dict(self):
        g = CreativeGene.from_dict({"name": "hook", "value": "before_after", "category": "hook", "confidence": 0.9})
        assert g.name == "hook"
        assert g.value == "before_after"
        assert g.confidence == 0.9

    def test_gene_to_e11_gene(self):
        g = CreativeGene(name="hook", value="before_after", confidence=0.9, source="agent")
        e11 = g.to_e11_gene()
        assert e11["name"] == "hook"
        assert e11["value"] == "before_after"
        assert e11["confidence"] == 0.9
        assert e11["source"] == "agent"

    def test_gene_defaults(self):
        g = CreativeGene()
        assert g.name == ""
        assert g.value is None
        assert g.confidence == 0.0


class TestCreativeDNAProfile:
    """CreativeDNAProfile 模型测试 (5)."""

    def test_create_empty(self):
        dna = CreativeDNAProfile()
        assert dna.dna_id != ""
        assert dna.generation == 0
        assert dna.gene_count == 0

    def test_create_with_genes(self, sample_dna_full):
        assert sample_dna_full.gene_count == 7
        assert sample_dna_full.dominant_hook == "before_after"
        assert sample_dna_full.dominant_emotion == "curiosity"
        assert sample_dna_full.primary_audience == "casual_gamers"

    def test_get_gene(self, sample_dna_full):
        gene = sample_dna_full.get_gene("hook")
        assert gene is not None
        assert gene.value == "before_after"

    def test_get_gene_missing(self, sample_dna_full):
        gene = sample_dna_full.get_gene("nonexistent")
        assert gene is None

    def test_avg_confidence(self, sample_dna_full):
        assert sample_dna_full.avg_confidence > 0.7

    def test_avg_confidence_empty(self):
        dna = CreativeDNAProfile()
        assert dna.avg_confidence == 0.0

    def test_fingerprint_consistency(self, sample_dna_full):
        fp1 = sample_dna_full.fingerprint
        fp2 = sample_dna_full.fingerprint
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_fingerprint_changes_on_gene_change(self, sample_dna_full):
        fp1 = sample_dna_full.fingerprint
        sample_dna_full.set_gene("hook", CreativeGene(name="hook", value="challenge", category="hook"))
        fp2 = sample_dna_full.fingerprint
        assert fp1 != fp2

    def test_to_dict_roundtrip(self, sample_dna_full):
        d = sample_dna_full.to_dict()
        dna2 = CreativeDNAProfile.from_dict(d)
        assert dna2.creative_id == sample_dna_full.creative_id
        assert dna2.dominant_hook == sample_dna_full.dominant_hook
        assert dna2.fingerprint == sample_dna_full.fingerprint


class TestDNAEngineExtract:
    """DNAEngine 提取测试 (5)."""

    def test_extract_dna(self, dna_engine):
        dna = dna_engine.extract_dna(
            creative_id="C001", creative_name="Test",
            hook="before_after", visual="fantasy", gameplay="merge",
            monetization="iap", emotion="curiosity", audience="casual_gamers",
            context="weekend",
        )
        assert dna.creative_id == "C001"
        assert dna.gene_count == 7
        assert dna.dominant_hook == "before_after"
        assert dna.dominant_emotion == "curiosity"
        assert dna.primary_audience == "casual_gamers"

    def test_extract_dna_with_fitness(self, dna_engine):
        dna = dna_engine.extract_dna(
            creative_id="C001", hook="before_after", visual="fantasy",
            fitness={"roas": 2.1, "ctr": 0.035},
        )
        assert dna.fitness["roas"] == 2.1
        assert dna.fitness["ctr"] == 0.035

    def test_extract_dna_with_generation(self, dna_engine):
        dna = dna_engine.extract_dna(
            creative_id="C001", hook="before_after", visual="fantasy",
            generation=2, parent_id="dna_parent",
        )
        assert dna.generation == 2
        assert dna.parent_id == "dna_parent"

    def test_extract_from_dict(self, dna_engine):
        gene_data = {"hook": "before_after", "visual": "fantasy", "gameplay": "merge",
                      "emotion": "curiosity", "audience": "casual_gamers"}
        dna = dna_engine.extract_from_dict(creative_id="C001", gene_data=gene_data)
        assert dna.dominant_hook == "before_after"
        assert dna.dominant_emotion == "curiosity"

    def test_extract_dna_stored_in_engine(self, dna_engine):
        dna = dna_engine.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        assert dna_engine.get_dna_count() == 1
        assert dna_engine.get_dna(dna.dna_id) is not None


class TestDNAEngineCompare:
    """DNAEngine 比较测试 (5)."""

    def test_compare_identical(self, dna_engine, sample_dna_full):
        result = dna_engine.compare_dna(sample_dna_full, sample_dna_full)
        assert result.similarity_score == pytest.approx(1.0, rel=0.01)
        assert result.is_identical

    def test_compare_variant(self, dna_engine, sample_dna_full, sample_dna_variant):
        result = dna_engine.compare_dna(sample_dna_full, sample_dna_variant)
        assert result.similarity_score > 0.7
        assert result.is_similar

    def test_compare_different(self, dna_engine, sample_dna_full, sample_dna_different):
        result = dna_engine.compare_dna(sample_dna_full, sample_dna_different)
        assert result.similarity_score < 0.5
        assert result.is_different

    def test_compare_has_differences(self, dna_engine, sample_dna_full, sample_dna_variant):
        result = dna_engine.compare_dna(sample_dna_full, sample_dna_variant)
        assert len(result.differences) >= 1

    def test_compare_has_recommendation(self, dna_engine, sample_dna_full, sample_dna_variant):
        result = dna_engine.compare_dna(sample_dna_full, sample_dna_variant)
        assert result.recommendation != ""


class TestDNAEngineFingerprint:
    """DNAEngine 指纹测试 (5)."""

    def test_compare_by_fingerprint_identical(self, dna_engine, sample_dna_full):
        sim = dna_engine.compare_by_fingerprint(sample_dna_full, sample_dna_full)
        assert sim == 1.0

    def test_find_similar_dnas(self, dna_engine):
        dna1 = dna_engine.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        dna2 = dna_engine.extract_dna(creative_id="C002", hook="before_after", visual="fantasy")
        dna3 = dna_engine.extract_dna(creative_id="C003", hook="rescue", visual="dark")
        similar = dna_engine.find_similar_dnas(dna1, min_similarity=0.5)
        assert len(similar) >= 1

    def test_cluster_by_dna(self, dna_engine):
        dna1 = dna_engine.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        dna2 = dna_engine.extract_dna(creative_id="C002", hook="before_after", visual="fantasy")
        dna3 = dna_engine.extract_dna(creative_id="C003", hook="rescue", visual="dark")
        clusters = dna_engine.cluster_by_dna([dna1, dna2, dna3], min_similarity=0.5)
        assert len(clusters) >= 2

    def test_get_dna_by_creative(self, dna_engine):
        dna = dna_engine.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        found = dna_engine.get_dna_by_creative("C001")
        assert found is not None
        assert found.dna_id == dna.dna_id

    def test_get_dna_by_creative_not_found(self, dna_engine):
        found = dna_engine.get_dna_by_creative("NONEXISTENT")
        assert found is None


class TestDNAEngineWinner:
    """DNAEngine 赢家 DNA 分析测试 (5)."""

    def test_extract_winner_dna_empty(self, dna_engine):
        report = dna_engine.extract_winner_dna([])
        assert report.winner_count == 0

    def test_extract_winner_dna_common_genes(self, dna_engine, sample_dna_full, sample_dna_variant):
        report = dna_engine.extract_winner_dna([sample_dna_full, sample_dna_variant])
        assert report.winner_count == 2
        assert len(report.common_genes) >= 1

    def test_extract_winner_dna_has_recommendation(self, dna_engine, sample_dna_full, sample_dna_variant):
        report = dna_engine.extract_winner_dna([sample_dna_full, sample_dna_variant])
        assert report.recommendation != ""

    def test_winner_dna_distinct_genes(self, dna_engine, sample_dna_full, sample_dna_variant):
        report = dna_engine.extract_winner_dna([sample_dna_full, sample_dna_variant])
        assert "hook" in report.distinct_genes

    def test_winner_dna_average_fitness(self, dna_engine, sample_dna_full, sample_dna_variant):
        report = dna_engine.extract_winner_dna([sample_dna_full, sample_dna_variant])
        assert "roas" in report.average_fitness


# ═══════════════════════════════════════════════════════════════
# Part 4: CreativeMemory
# ═══════════════════════════════════════════════════════════════


class TestCreativeMemoryRecord:
    """CreativeMemory 决策记录测试 (6)."""

    def test_record_decision(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
            dna_id="dna_001",
        )
        assert record.record_id != ""
        assert record.creative_id == "C001"
        assert record.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert record.action_type == CreativeActionType.GENERATE_VARIANTS
        assert record.is_resolved is False

    def test_record_decision_with_metrics(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
            before_metrics={"roas": 1.3, "ctr": 0.02},
            confidence=0.9,
        )
        assert record.before_metrics["roas"] == 1.3
        assert record.confidence == 0.9

    def test_resolve_success(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
        )
        resolved = memory.resolve(
            record.record_id,
            outcome=CreativeDecisionOutcome.SUCCESS,
            after_metrics={"roas": 1.8},
            reward=0.5,
            learning="Variants improved ROAS",
        )
        assert resolved is not None
        assert resolved.is_resolved is True
        assert resolved.outcome == CreativeDecisionOutcome.SUCCESS
        assert resolved.reward == 0.5
        assert resolved.learning == "Variants improved ROAS"

    def test_resolve_failure(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
        )
        resolved = memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.FAILURE, reward=-0.3)
        assert resolved is not None
        assert resolved.is_success is False
        assert resolved.is_failure is True

    def test_resolve_not_found(self, memory):
        result = memory.resolve("nonexistent", outcome=CreativeDecisionOutcome.SUCCESS)
        assert result is None

    def test_resolve_batch(self, memory):
        r1 = memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        r2 = memory.record_decision(creative_id="C002", diagnosis_type=CreativeDiagnosisType.WINNER,
                                     action_type=CreativeActionType.SCALE_CREATIVE)
        results = memory.resolve_batch([
            {"record_id": r1.record_id, "outcome": "success", "reward": 0.5},
            {"record_id": r2.record_id, "outcome": "failure", "reward": -0.2},
        ])
        assert len(results) == 2
        assert all(r.is_resolved for r in results)


class TestCreativeMemoryDNA:
    """CreativeMemory DNA 存储测试 (4)."""

    def test_store_dna(self, memory, sample_dna_full):
        entry = memory.store_dna(sample_dna_full, is_winner=True, performance={"roas": 2.1})
        assert entry.entry_id != ""
        assert entry.is_winner is True
        assert entry.performance["roas"] == 2.1

    def test_mark_winner(self, memory, sample_dna_full):
        memory.store_dna(sample_dna_full, is_winner=False)
        assert memory.mark_winner(sample_dna_full.dna_id) is True

    def test_mark_winner_not_found(self, memory):
        assert memory.mark_winner("nonexistent") is False

    def test_get_winner_dnas(self, memory, sample_dna_full, sample_dna_variant):
        memory.store_dna(sample_dna_full, is_winner=True)
        memory.store_dna(sample_dna_variant, is_winner=False)
        winners = memory.get_winner_dnas()
        assert len(winners) == 1
        assert winners[0].dna.creative_id == sample_dna_full.creative_id


class TestCreativeMemoryExperience:
    """CreativeMemory 经验测试 (5)."""

    def test_experience_created_on_resolve(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
        )
        memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)
        exp = memory.get_experience(CreativeDiagnosisType.CREATIVE_FATIGUE, CreativeActionType.GENERATE_VARIANTS)
        assert exp is not None
        assert exp.total_count == 1
        assert exp.success_count == 1

    def test_experience_accumulates(self, memory):
        for i in range(5):
            record = memory.record_decision(
                creative_id=f"C00{i}",
                diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                action_type=CreativeActionType.GENERATE_VARIANTS,
            )
            outcome = CreativeDecisionOutcome.SUCCESS if i < 3 else CreativeDecisionOutcome.FAILURE
            memory.resolve(record.record_id, outcome=outcome, reward=0.5 if i < 3 else -0.3)
        exp = memory.get_experience(CreativeDiagnosisType.CREATIVE_FATIGUE, CreativeActionType.GENERATE_VARIANTS)
        assert exp.total_count == 5
        assert exp.success_count == 3
        assert exp.success_rate == 0.6

    def test_get_experiences_filtered(self, memory):
        record = memory.record_decision(
            creative_id="C001",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
        )
        memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)
        exps = memory.get_experiences(diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE)
        assert len(exps) >= 1

    def test_get_best_experiences(self, memory):
        for i in range(5):
            record = memory.record_decision(
                creative_id=f"C00{i}",
                diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                action_type=CreativeActionType.GENERATE_VARIANTS,
            )
            memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)
        best = memory.get_best_experiences(min_success_rate=0.8, min_count=3)
        assert len(best) >= 1

    def test_experience_confidence_boost(self, memory):
        for i in range(4):
            record = memory.record_decision(
                creative_id=f"C00{i}",
                diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                action_type=CreativeActionType.GENERATE_VARIANTS,
            )
            memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)
        exp = memory.get_experience(CreativeDiagnosisType.CREATIVE_FATIGUE, CreativeActionType.GENERATE_VARIANTS)
        assert exp.confidence_boost > 0


class TestCreativeMemoryQuery:
    """CreativeMemory 查询测试 (5)."""

    def test_get_pending(self, memory):
        r1 = memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        r2 = memory.record_decision(creative_id="C002", diagnosis_type=CreativeDiagnosisType.WINNER,
                                     action_type=CreativeActionType.SCALE_CREATIVE)
        memory.resolve(r1.record_id, outcome=CreativeDecisionOutcome.SUCCESS)
        pending = memory.get_pending()
        assert len(pending) == 1
        assert pending[0].record_id == r2.record_id

    def test_get_resolved(self, memory):
        r1 = memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        memory.resolve(r1.record_id, outcome=CreativeDecisionOutcome.SUCCESS)
        assert len(memory.get_resolved()) == 1

    def test_get_records_by_creative(self, memory):
        memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                               action_type=CreativeActionType.GENERATE_VARIANTS)
        memory.record_decision(creative_id="C002", diagnosis_type=CreativeDiagnosisType.WINNER,
                               action_type=CreativeActionType.SCALE_CREATIVE)
        records = memory.get_records(creative_id="C001")
        assert len(records) == 1
        assert records[0].creative_id == "C001"

    def test_get_success_rate(self, memory):
        r1 = memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        r2 = memory.record_decision(creative_id="C002", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        memory.resolve(r1.record_id, outcome=CreativeDecisionOutcome.SUCCESS)
        memory.resolve(r2.record_id, outcome=CreativeDecisionOutcome.FAILURE)
        rate = memory.get_success_rate(diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE)
        assert rate == 0.5

    def test_stats(self, memory):
        r1 = memory.record_decision(creative_id="C001", diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
                                     action_type=CreativeActionType.GENERATE_VARIANTS)
        memory.resolve(r1.record_id, outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5)
        stats = memory.stats()
        assert stats["total_records"] == 1
        assert stats["resolved"] == 1
        assert stats["pending"] == 0


# ═══════════════════════════════════════════════════════════════
# Part 5: CreativeAgent Core
# ═══════════════════════════════════════════════════════════════


class TestCreativeAgentAnalyze:
    """CreativeAgent 分析测试 (8)."""

    def test_agent_identity(self, agent):
        assert agent.identity is not None
        assert agent.agent_id != ""
        assert agent.identity.role == AgentRole.CREATIVE

    def test_initial_state(self, agent):
        assert agent.state == CreativeAgentState.IDLE

    def test_analyze_creative_from_dict(self, agent):
        rec = agent.analyze_creative({
            "creative_id": "C101", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82,
            "spend": 2000, "impressions": 50000, "days_running": 14,
        })
        assert rec.creative_id == "C101"
        assert rec.diagnosis is not None
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE
        assert rec.action == CreativeActionType.GENERATE_VARIANTS

    def test_analyze_creative_from_metrics(self, agent, fatigue_metrics):
        rec = agent.analyze_creative(fatigue_metrics)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE

    def test_analyze_creative_winner(self, agent, winner_metrics):
        rec = agent.analyze_creative(winner_metrics)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.WINNER
        assert rec.action == CreativeActionType.SCALE_CREATIVE

    def test_analyze_creative_underperformer(self, agent, underperformer_metrics):
        rec = agent.analyze_creative(underperformer_metrics)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER
        assert rec.action == CreativeActionType.PAUSE_CREATIVE

    def test_analyze_creative_records_memory(self, agent, fatigue_metrics):
        agent.analyze_creative(fatigue_metrics)
        stats = agent.get_memory().stats()
        assert stats["total_records"] >= 1

    def test_analyze_creative_returns_to_idle(self, agent, fatigue_metrics):
        agent.analyze_creative(fatigue_metrics)
        assert agent.state == CreativeAgentState.IDLE


class TestCreativeAgentBatch:
    """CreativeAgent 批量分析测试 (4)."""

    def test_analyze_batch(self, agent, fatigue_metrics, winner_metrics, underperformer_metrics):
        report = agent.analyze_creative_batch([fatigue_metrics, winner_metrics, underperformer_metrics])
        assert report.report_id != ""
        assert len(report.recommendations) == 3
        assert report.analysis_report is not None
        assert report.analysis_report.total_creatives == 3

    def test_analyze_batch_from_dicts(self, agent):
        metrics_list = [
            {"creative_id": "C101", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82, "spend": 2000, "impressions": 50000, "days_running": 14},
            {"creative_id": "C102", "roas": 2.1, "ctr": 0.035, "fatigue": 0.2, "spend": 8000, "impressions": 120000, "days_running": 21},
        ]
        report = agent.analyze_creative_batch(metrics_list)
        assert len(report.recommendations) == 2

    def test_analyze_batch_empty(self, agent):
        report = agent.analyze_creative_batch([])
        assert len(report.recommendations) == 0

    def test_analyze_batch_with_winner_dna(self, agent, winner_metrics):
        # 先存储赢家 DNA
        agent.extract_dna(creative_id="C102", hook="before_after", visual="fantasy", emotion="curiosity",
                          gameplay="merge", fitness={"roas": 2.1})
        report = agent.analyze_creative_batch([winner_metrics])
        assert report.winner_dna_report is not None


class TestCreativeAgentDNA:
    """CreativeAgent DNA 操作测试 (5)."""

    def test_extract_dna(self, agent):
        dna = agent.extract_dna(
            creative_id="C001", creative_name="Test Creative",
            hook="before_after", visual="fantasy", gameplay="merge",
            monetization="iap", emotion="curiosity", audience="casual_gamers",
            context="weekend",
        )
        assert dna.creative_id == "C001"
        assert dna.gene_count == 7
        assert dna.dominant_hook == "before_after"

    def test_extract_dna_stores_in_memory(self, agent):
        dna = agent.extract_dna(
            creative_id="C001", hook="before_after", visual="fantasy",
            fitness={"roas": 2.5},
        )
        mem = agent.get_memory()
        entry = mem.get_dna_by_creative("C001")
        assert entry is not None
        assert entry.is_winner is True

    def test_compare_dna(self, agent, sample_dna_full, sample_dna_different):
        result = agent.compare_dna(sample_dna_full, sample_dna_different)
        assert result.similarity_score < 0.5
        assert result.is_different

    def test_extract_winner_dna(self, agent):
        agent.extract_dna(creative_id="C001", hook="before_after", visual="fantasy", fitness={"roas": 2.1})
        agent.extract_dna(creative_id="C002", hook="before_after", visual="fantasy", fitness={"roas": 1.8})
        report = agent.extract_winner_dna()
        assert report.winner_count >= 2

    def test_find_similar_dnas(self, agent):
        agent.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        dna2 = agent.extract_dna(creative_id="C002", hook="before_after", visual="fantasy")
        similar = agent.find_similar_dnas(dna2, min_similarity=0.5)
        assert len(similar) >= 1


class TestCreativeAgentQuick:
    """CreativeAgent 快捷分析测试 (4)."""

    def test_quick_analysis_fatigue(self, agent):
        rec = agent.quick_analysis(creative_id="C001", roas=0.4, ctr=0.01, fatigue=0.85, days_running=7, impressions=6000)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE

    def test_quick_analysis_winner(self, agent):
        rec = agent.quick_analysis(creative_id="C001", roas=2.0, ctr=0.03, fatigue=0.2, spend=1000, days_running=7, impressions=6000)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.WINNER

    def test_quick_analysis_new(self, agent):
        rec = agent.quick_analysis(creative_id="C001", roas=0.0, ctr=0.01, fatigue=0.0, days_running=1, impressions=1000)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.NEW_CREATIVE

    def test_quick_analysis_underperformer(self, agent):
        rec = agent.quick_analysis(creative_id="C001", roas=0.3, ctr=0.01, fatigue=0.1, days_running=7, impressions=6000)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER


class TestCreativeAgentStrategy:
    """CreativeAgent 策略生成测试 (4)."""

    def test_generate_strategy_fatigue(self, agent):
        rec = agent.generate_strategy("C001", CreativeDiagnosisType.CREATIVE_FATIGUE)
        assert rec.action == CreativeActionType.GENERATE_VARIANTS
        assert rec.priority == "high"

    def test_generate_strategy_winner(self, agent):
        rec = agent.generate_strategy("C001", CreativeDiagnosisType.WINNER)
        assert rec.action == CreativeActionType.SCALE_CREATIVE
        assert rec.priority == "normal"

    def test_generate_strategy_underperformer(self, agent):
        rec = agent.generate_strategy("C001", CreativeDiagnosisType.UNDERPERFORMER)
        assert rec.action == CreativeActionType.PAUSE_CREATIVE
        assert rec.priority == "high"

    def test_generate_strategy_has_expected_impact(self, agent):
        rec = agent.generate_strategy("C001", CreativeDiagnosisType.CREATIVE_FATIGUE)
        assert rec.expected_impact != ""


class TestCreativeAgentSubmodules:
    """CreativeAgent 子模块访问测试 (3)."""

    def test_get_analyzer(self, agent):
        a = agent.get_analyzer()
        assert isinstance(a, CreativeAnalyzer)

    def test_get_dna_engine(self, agent):
        e = agent.get_dna_engine()
        assert isinstance(e, DNAEngine)

    def test_get_memory(self, agent):
        m = agent.get_memory()
        assert isinstance(m, CreativeMemory)


class TestCreativeAgentStats:
    """CreativeAgent 统计与重置测试 (2)."""

    def test_stats(self, agent, fatigue_metrics):
        agent.analyze_creative(fatigue_metrics)
        stats = agent.stats()
        assert stats["agent_id"] != ""
        assert stats["state"] == "idle"
        assert "analyzer" in stats
        assert "dna_engine" in stats
        assert "memory" in stats

    def test_reset(self, agent, fatigue_metrics):
        agent.analyze_creative(fatigue_metrics)
        agent.extract_dna(creative_id="C001", hook="before_after", visual="fantasy")
        agent.reset()
        assert agent.state == CreativeAgentState.IDLE
        assert agent.get_memory().stats()["total_records"] == 0
        assert agent.get_dna_engine().get_dna_count() == 0


# ═══════════════════════════════════════════════════════════════
# Part 6: Integration & Communication
# ═══════════════════════════════════════════════════════════════


class TestCreativeAgentCommunication:
    """CreativeAgent 通信集成测试 (9)."""

    @pytest.fixture
    def ua_id(self):
        return comm_ua_identity(name="UA Agent")

    @pytest.fixture
    def creative_id(self):
        return comm_creative_identity(name="Creative Agent")

    def test_handle_creative_analysis_request(self, agent, ua_id, creative_id):
        """测试处理 UA Agent 的创意分析请求."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import AgentMessage

        msg = AgentMessage(
            sender=ua_id,
            receiver=creative_id,
            subject="Analyze creative C101",
            body={
                "creative_id": "C101",
                "metrics": {
                    "creative_id": "C101", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82,
                    "spend": 2000, "impressions": 50000, "days_running": 14,
                },
            },
            standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
        )
        response = agent.handle_ua_request(msg)
        assert response is not None
        body = response.body
        assert body["creative_id"] == "C101"
        assert body["diagnosis"] is not None
        assert body["diagnosis"]["diagnosis_type"] == "creative_fatigue"

    def test_handle_creative_variants_request(self, agent, ua_id, creative_id):
        """测试处理 UA Agent 的变体请求."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import AgentMessage

        # 先存储一些赢家 DNA
        agent.extract_dna(creative_id="C001", hook="before_after", visual="fantasy", fitness={"roas": 2.5})
        agent.extract_dna(creative_id="C002", hook="before_after", visual="fantasy", fitness={"roas": 1.8})

        msg = AgentMessage(
            sender=ua_id,
            receiver=creative_id,
            subject="Request variants for C001",
            body={"creative_id": "C001"},
            standard_type=StandardMessageType.REQUEST_CREATIVE_VARIANTS,
        )
        response = agent.handle_ua_request(msg)
        assert response is not None
        body = response.body
        assert body["creative_id"] == "C001"
        assert "winner_dna_report" in body

    def test_handle_ua_request_unknown_type(self, agent, ua_id, creative_id):
        """测试处理未知类型的消息."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import AgentMessage

        msg = AgentMessage(
            sender=ua_id,
            receiver=creative_id,
            subject="Unknown",
            body={},
            standard_type=StandardMessageType.CAMPAIGN_ACTION,
        )
        response = agent.handle_ua_request(msg)
        assert response is None

    def test_handle_creative_analysis_without_metrics(self, agent, ua_id, creative_id):
        """测试处理仅有 creative_id 的分析请求."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import AgentMessage

        msg = AgentMessage(
            sender=ua_id,
            receiver=creative_id,
            subject="Analyze creative",
            body={"creative_id": "C001", "roas": 0.5, "ctr": 0.01, "fatigue": 0.7, "days_running": 10, "impressions": 6000},
            standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
        )
        response = agent.handle_ua_request(msg)
        assert response is not None

    def test_message_bus_integration(self, agent, creative_id):
        """测试消息总线注册."""
        bus = create_message_bus()
        registry = create_agent_registry()
        registry.register(creative_id)
        bus.register_handler_fn(
            agent_id=creative_id.agent_id,
            handler_fn=lambda msg: None,
            standard_types=[StandardMessageType.REQUEST_CREATIVE_ANALYSIS],
        )
        assert True  # 注册成功

    def test_agent_registry_creative_role(self, creative_id):
        """测试 Creative Agent 在注册中心注册."""
        registry = create_agent_registry()
        registry.register(creative_id)
        creatives = registry.find_by_role(AgentRole.CREATIVE)
        assert len(creatives) >= 1

    def test_default_organization_has_creative(self):
        """测试默认组织包含 Creative Agent."""
        org = create_default_organization()
        creatives = org.find_by_role(AgentRole.CREATIVE)
        assert len(creatives) >= 1

    def test_supervisor_to_creative_communication(self, agent, creative_id):
        """测试 Supervisor 到 Creative Agent 的消息路由."""
        supervisor_id = comm_supervisor_identity(name="Supervisor")
        bus = create_message_bus()
        bus.register_handler_fn(
            agent_id=creative_id.agent_id,
            handler_fn=lambda msg: None,
        )
        bus.register_handler_fn(
            agent_id=supervisor_id.agent_id,
            handler_fn=lambda msg: None,
        )

        from market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import AgentMessage

        msg = AgentMessage(
            sender=supervisor_id,
            receiver=creative_id,
            subject="Task: Analyze all creatives",
            body={"task": "analyze_all", "creative_ids": ["C101", "C102"]},
            standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
            message_type=MessageType.TASK,
            priority=MessagePriority.HIGH,
        )
        assert msg.sender.agent_id == supervisor_id.agent_id
        assert msg.receiver.agent_id == creative_id.agent_id
        assert msg.priority == MessagePriority.HIGH

    def test_creative_recommendation_serializable(self, agent, fatigue_metrics):
        """测试创意推荐可序列化."""
        rec = agent.analyze_creative(fatigue_metrics)
        d = rec.to_dict()
        assert d["creative_id"] == fatigue_metrics.creative_id
        assert d["diagnosis"]["diagnosis_type"] == "creative_fatigue"
        assert d["action"] == "generate_variants"


class TestCreativeAgentIntegration:
    """CreativeAgent 端到端集成测试 (6)."""

    def test_full_workflow_analyze(self, agent, fatigue_metrics):
        """完整分析工作流."""
        rec = agent.analyze_creative(fatigue_metrics)
        assert rec.diagnosis is not None
        assert rec.action == CreativeActionType.GENERATE_VARIANTS
        stats = agent.get_memory().stats()
        assert stats["total_records"] >= 1

    def test_full_workflow_extract_dna(self, agent):
        """完整 DNA 提取工作流."""
        dna = agent.extract_dna(
            creative_id="C001", hook="before_after", visual="fantasy",
            gameplay="merge", emotion="curiosity", fitness={"roas": 2.5},
        )
        assert dna.gene_count == 7
        mem = agent.get_memory()
        assert mem.get_dna_by_creative("C001") is not None
        assert len(mem.get_winner_dnas()) >= 1

    def test_full_workflow_analyze_then_extract(self, agent, winner_metrics):
        """分析后提取 DNA 的完整链路."""
        rec = agent.analyze_creative(winner_metrics)
        assert rec.diagnosis.diagnosis_type == CreativeDiagnosisType.WINNER

        dna = agent.extract_dna(
            creative_id=winner_metrics.creative_id,
            hook="before_after", visual="fantasy", emotion="curiosity",
            gameplay="merge", fitness={"roas": 2.1},
        )
        assert dna.creative_id == winner_metrics.creative_id

        # 验证记忆中有两条记录
        memory = agent.get_memory()
        records = memory.get_records(creative_id=winner_metrics.creative_id)
        assert len(records) >= 2

    def test_factory_creates_valid_agent(self):
        """工厂函数创建有效 Agent."""
        agent = create_creative_agent(name="Test Creative", fatigue_threshold=0.5, roas_winner_threshold=2.0)
        assert agent.identity is not None
        assert agent.state == CreativeAgentState.IDLE
        assert agent.get_analyzer().thresholds.fatigue_threshold == 0.5
        assert agent.get_analyzer().thresholds.roas_winner_threshold == 2.0

    def test_create_analyzer_factory(self):
        """工厂函数创建分析器."""
        a = create_creative_analyzer(fatigue_threshold=0.7, roas_winner_threshold=2.0)
        assert a.thresholds.fatigue_threshold == 0.7
        assert a.thresholds.roas_winner_threshold == 2.0

    def test_create_dna_engine_factory(self):
        """工厂函数创建 DNA 引擎."""
        e = create_dna_engine()
        assert isinstance(e, DNAEngine)

    def test_create_memory_factory(self):
        """工厂函数创建记忆."""
        m = create_creative_memory()
        assert isinstance(m, CreativeMemory)


# ═══════════════════════════════════════════════════════════════
# Part 7: Regression
# ═══════════════════════════════════════════════════════════════


class TestRegression:
    """回归测试 — 确保 E13/E14.1/E14.2/E14.3 未被破坏 (10)."""

    def test_e131_communication_imports(self):
        """E14.1 通信层导入正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            MessageBus, AgentRegistry, AgentMessage, AgentIdentity,
            AgentRole, StandardMessageType, CollaborationEngine,
            create_message_bus, create_agent_registry, create_default_organization,
        )
        assert MessageBus is not None
        assert AgentRegistry is not None
        assert CollaborationEngine is not None

    def test_e131_message_bus_basic(self):
        """E14.1 消息总线基本功能正常."""
        bus = create_message_bus()
        assert bus is not None

    def test_e131_agent_registry_basic(self):
        """E14.1 Agent 注册中心正常."""
        registry = create_agent_registry()
        assert registry is not None

    def test_e142_supervisor_imports(self):
        """E14.2 Supervisor 导入正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.supervisor import (
            GoalManager, PriorityEngine, TaskAllocator,
            ConflictResolver, SupervisorMemory,
        )
        assert GoalManager is not None
        assert PriorityEngine is not None
        assert TaskAllocator is not None
        assert ConflictResolver is not None
        assert SupervisorMemory is not None

    def test_e143_ua_agent_imports(self):
        """E14.3 UA Agent 导入正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.ua_agent import (
            UAGrowthAgent, UAAnalyzer, UADiagnosisEngine,
            UAStrategyEngine, UAActionSelector, UAMemory,
            create_ua_agent,
        )
        assert UAGrowthAgent is not None
        assert UAAnalyzer is not None
        assert UADiagnosisEngine is not None
        assert UAStrategyEngine is not None
        assert UAActionSelector is not None
        assert UAMemory is not None

    def test_e1431_feedback_loop_imports(self):
        """E14.3.1 反馈闭环导入正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.ua_agent import (
            FeedbackCollector, RewardCalculator, OutcomeEvaluator,
            LearningEngine, FeedbackLoop,
            create_feedback_collector, create_reward_calculator,
            create_outcome_evaluator, create_feedback_loop,
        )
        assert FeedbackCollector is not None
        assert RewardCalculator is not None
        assert OutcomeEvaluator is not None
        assert LearningEngine is not None
        assert FeedbackLoop is not None

    def test_e131_agent_identity_creation(self):
        """E14.1 Agent 身份创建正常."""
        # 确保所有身份创建函数正常工作
        ua = comm_ua_identity()
        creative = comm_creative_identity()
        supervisor = comm_supervisor_identity()
        assert ua.role == AgentRole.UA
        assert creative.role == AgentRole.CREATIVE
        assert supervisor.role == AgentRole.SUPERVISOR

    def test_e131_message_types(self):
        """E14.1 消息类型枚举正常."""
        assert StandardMessageType.REQUEST_CREATIVE_ANALYSIS is not None
        assert StandardMessageType.REQUEST_CREATIVE_VARIANTS is not None
        assert StandardMessageType.CREATIVE_VARIANTS_READY is not None
        assert StandardMessageType.CREATIVE_FATIGUE_ALERT is not None

    def test_creative_agent_does_not_break_ua_agent(self):
        """Creative Agent 不与 UA Agent 冲突."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.ua_agent import create_ua_agent
        ua = create_ua_agent()
        assert ua is not None
        rec = ua.analyze_metrics({
            "spend": 10000, "revenue": 13000, "roas": 1.3,
            "cpi": 2.1, "ctr": 0.8, "fatigue": 0.72,
        })
        assert rec is not None
        assert rec.summary != ""

    def test_default_organization_unchanged(self):
        """默认组织未被破坏."""
        org = create_default_organization()
        assert org.find_by_role(AgentRole.UA) is not None
        assert org.find_by_role(AgentRole.CREATIVE) is not None
        assert org.find_by_role(AgentRole.SUPERVISOR) is not None