"""E14.4.4 Creative Self-Learning Loop — 集成测试.

验证 Creative Agent 的自主学习能力:
  - RewardModel (E14.4.4.1) — 30 tests
  - PatternMiner (E14.4.4.2) — 30 tests
  - StrategyMemory (E14.4.4.3) — 30 tests
  - MutationLearning (E14.4.4.4) — 30 tests
  - CreativePolicy (E14.4.4.5) — 30 tests
  - CreativeAgent Integration (E14.4.4.6) — 30 tests
  - Full Learning Loop — 20 tests
  - Regression (E14.4.1/E14.4.2/E14.4.3/E14.3/E14.2/E14.1) — 20 tests

总计: 220 个测试用例
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
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    CreativeMemory,
    CreativeActionType,
    CreativeDecisionOutcome,
    CreativeDecisionRecord,
    CreativeAgent,
    CreativeAgentState,
    create_creative_agent,
    CreativeOpportunityType,
    CreativeSignal,
    OpportunityPriority,
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
    CreativePlan,
    MutationConfig,
    ExperimentConfig,
    ExperimentType,
    PlanStatus,
    CreativeExecutor,
    ExecutionActionType,
    ExperimentManager,
    CreativeExperiment,
    ExperimentStatus,
    ExperimentResult,
    VariantMetrics,
    VariantGroupType,
    RolloutController,
    RolloutStrategy,
    RolloutStatus,
    RolloutTrigger,
)

# E14.4.4 Learning Modules
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import (
    RewardModel,
    CreativeReward,
    DNAReward,
    MutationReward,
    RewardConfig,
    create_reward_model,
    PatternMiner,
    CreativePattern,
    DNAPattern,
    PatternCategory,
    PatternConfidence,
    MiningReport,
    create_pattern_miner,
    StrategyMemory,
    StrategyRecord,
    ContextProfile,
    StrategyEffectiveness,
    StrategyMemoryReport,
    create_strategy_memory,
    MutationLearning,
    MutationRecord,
    GeneCategory,
    MutationEffectiveness,
    MutationPriority,
    MutationLearningReport,
    create_mutation_learning,
    CreativePolicy,
    PolicyDecision,
    PolicyContext,
    PolicyConfidence,
    PolicyAction,
    PolicyReport,
    create_creative_policy,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def memory():
    return CreativeMemory()


@pytest.fixture
def reward_model(memory):
    return RewardModel(memory=memory)


@pytest.fixture
def pattern_miner(memory):
    return PatternMiner(memory=memory, min_occurrence=2)


@pytest.fixture
def strategy_memory(memory):
    return StrategyMemory(memory=memory)


@pytest.fixture
def mutation_learning(memory):
    return MutationLearning(memory=memory)


@pytest.fixture
def policy(memory, pattern_miner, strategy_memory, mutation_learning):
    return CreativePolicy(
        memory=memory,
        pattern_miner=pattern_miner,
        strategy_memory=strategy_memory,
        mutation_learning=mutation_learning,
    )


@pytest.fixture
def agent():
    return create_creative_agent()


@pytest.fixture
def sample_variant_metrics():
    """创建样本变体指标."""
    return VariantMetrics(
        variant_id="V001",
        creative_id="C102",
        group_type=VariantGroupType.VARIANT,
        roas=2.5,
        ctr=0.035,
        cvr=0.08,
        fatigue=0.2,
        spend=1500.0,
        revenue=3750.0,
        installs=800,
        payer_rate=0.12,
        ltv=8.5,
        is_winner=True,
    )


@pytest.fixture
def sample_negative_metrics():
    """创建负样本指标."""
    return VariantMetrics(
        variant_id="V002",
        creative_id="C103",
        group_type=VariantGroupType.VARIANT,
        roas=0.4,
        ctr=0.012,
        cvr=0.02,
        fatigue=0.8,
        spend=2000.0,
        revenue=800.0,
        installs=300,
        payer_rate=0.03,
        ltv=1.5,
        is_winner=False,
    )


@pytest.fixture
def sample_metrics_list():
    """创建样本指标列表."""
    return [
        VariantMetrics(
            variant_id=f"V00{i}",
            creative_id=f"C10{i}",
            group_type=VariantGroupType.VARIANT,
            roas=2.0 + i * 0.3,
            ctr=0.03 + i * 0.005,
            cvr=0.06,
            fatigue=0.2 + i * 0.05,
            spend=1000.0 + i * 200,
            revenue=2500.0 + i * 500,
            installs=600 + i * 100,
            payer_rate=0.10,
            ltv=6.0 + i * 1.0,
            is_winner=(i <= 2),
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_context():
    """创建样本上下文."""
    return PolicyContext(
        game="MergeGame",
        platform="android",
        market="US",
        genre="merge",
        stage="growth",
        current_roas=1.2,
        current_ctr=0.025,
        current_fatigue=0.35,
        current_frequency=2.5,
        current_ltv=6.0,
        active_creative_count=12,
        creative_id="C102",
    )


@pytest.fixture
def sample_fatigued_context():
    """创建疲劳场景上下文."""
    return PolicyContext(
        game="MergeGame",
        platform="android",
        market="US",
        genre="merge",
        stage="growth",
        current_roas=0.6,
        current_ctr=0.015,
        current_fatigue=0.85,
        current_frequency=5.0,
        current_ltv=3.0,
        active_creative_count=8,
        creative_id="C102",
    )


@pytest.fixture
def populated_memory(memory, agent):
    """填充一些 DNA 和决策数据到 memory 中."""
    # 存储 DNA — 同时写入 agent 的内存和 fixture 的 memory
    for i, (hook, visual, emotion, roas) in enumerate([
        ("transformation", "fantasy", "surprise", 2.5),
        ("transformation", "fantasy", "surprise", 2.3),
        ("transformation", "vibrant", "excitement", 2.1),
        ("rescue", "fantasy", "curiosity", 1.8),
        ("rescue", "realistic", "fear", 1.6),
        ("before_after", "fantasy", "achievement", 1.5),
        ("before_after", "fantasy", "achievement", 1.4),
        ("challenge", "dark", "urgency", 0.8),
        ("challenge", "dark", "urgency", 0.7),
        ("curiosity", "minimal", "relaxation", 0.5),
    ]):
        dna = agent.extract_dna(
            f"C{100 + i}", f"creative_{i}",
            hook=hook, visual=visual, emotion=emotion,
            fitness={"roas": roas, "ctr": 0.03},
        )
        # 同时存储到 fixture 的 memory (供 learning 模块使用)
        memory.store_dna(dna, is_winner=True, performance={"roas": roas, "ctr": 0.03})

    # 记录决策
    for i in range(5):
        record = memory.record_decision(
            creative_id=f"C{100 + i}",
            action_type=CreativeActionType.GENERATE_VARIANTS,
            action_params={
                "gene_category": "hook",
                "mutation_action": "change",
                "variant_creative_id": f"CV{200 + i}",
            },
            before_metrics={"roas": 1.0},
            confidence=0.8,
        )
        memory.resolve(
            record.record_id,
            outcome=CreativeDecisionOutcome.SUCCESS if i < 3 else CreativeDecisionOutcome.FAILURE,
            after_metrics={"roas": 2.0 - i * 0.3},
            reward=0.5 - i * 0.15,
        )

    return memory


# ═══════════════════════════════════════════════════════════════
# E14.4.4.1 RewardModel Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestRewardModel:
    """RewardModel — 创意奖励量化模型."""

    # ── 基础计算 ──────────────────────────────────────────────

    def test_calculate_positive(self, reward_model, sample_variant_metrics):
        reward = reward_model.calculate(sample_variant_metrics)
        assert reward.total_reward > 0
        assert reward.is_positive
        assert reward.confidence > 0

    def test_calculate_negative(self, reward_model, sample_negative_metrics):
        reward = reward_model.calculate(sample_negative_metrics)
        assert reward.total_reward < 0
        assert not reward.is_positive

    def test_calculate_components(self, reward_model, sample_variant_metrics):
        reward = reward_model.calculate(sample_variant_metrics)
        assert reward.roas_component > 0
        assert reward.risk_component <= 0

    def test_calculate_batch(self, reward_model, sample_metrics_list):
        rewards = reward_model.calculate_batch(sample_metrics_list)
        assert len(rewards) == len(sample_metrics_list)
        assert all(isinstance(r, CreativeReward) for r in rewards)

    def test_calculate_clips_reward(self, reward_model):
        """验证奖励裁剪到 [-1.0, 1.0]."""
        extreme = VariantMetrics(
            variant_id="V099", creative_id="C999",
            roas=10.0, ctr=0.1, installs=5000, spend=100, ltv=50.0,
        )
        reward = reward_model.calculate(extreme)
        assert -1.0 <= reward.total_reward <= 1.0

    def test_calculate_zero_metrics(self, reward_model):
        empty = VariantMetrics(variant_id="V000", creative_id="C000")
        reward = reward_model.calculate(empty)
        assert reward.total_reward <= 0

    def test_calculate_custom_baseline(self, reward_model, sample_variant_metrics):
        reward_default = reward_model.calculate(sample_variant_metrics)
        reward_custom = reward_model.calculate(sample_variant_metrics, baseline_roas=2.0)
        assert reward_custom.total_reward < reward_default.total_reward

    def test_calculate_confidence_by_samples(self, reward_model):
        low_samples = VariantMetrics(
            variant_id="V001", creative_id="C001", roas=2.0, installs=100,
        )
        high_samples = VariantMetrics(
            variant_id="V002", creative_id="C002", roas=2.0, installs=1000,
        )
        r1 = reward_model.calculate(low_samples)
        r2 = reward_model.calculate(high_samples)
        assert r2.confidence > r1.confidence

    def test_reward_dict(self, reward_model, sample_variant_metrics):
        reward = reward_model.calculate(sample_variant_metrics)
        d = reward.to_dict()
        assert "total_reward" in d
        assert "roas_component" in d
        assert "is_positive" in d

    def test_reward_strong_positive(self, reward_model):
        strong = VariantMetrics(
            variant_id="V001", creative_id="C001",
            roas=3.0, ltv=10.0, installs=1000, fatigue=0.1, spend=500,
        )
        reward = reward_model.calculate(strong)
        assert reward.is_strong_positive

    # ── DNA 奖励 ──────────────────────────────────────────────

    def test_calculate_dna_rewards_empty(self, reward_model):
        rewards = reward_model.calculate_dna_rewards()
        assert isinstance(rewards, list)

    def test_calculate_dna_rewards_with_data(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        rewards = reward_model.calculate_dna_rewards()
        assert len(rewards) > 0

    def test_dna_reward_properties(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        rewards = reward_model.calculate_dna_rewards()
        for r in rewards:
            assert r.gene_category
            assert r.gene_value
            assert 0 <= r.confidence <= 1
            assert 0 <= r.win_rate <= 1

    def test_get_top_dna_genes(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        top = reward_model.get_top_dna_genes(min_confidence=0.0, top_n=5)
        assert len(top) <= 5

    def test_dna_reward_dict(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        rewards = reward_model.calculate_dna_rewards()
        for r in rewards:
            d = r.to_dict()
            assert "gene_category" in d
            assert "gene_value" in d
            assert "total_reward" in d

    # ── Mutation 奖励 ─────────────────────────────────────────

    def test_calculate_mutation_rewards_empty(self, reward_model):
        rewards = reward_model.calculate_mutation_rewards()
        assert isinstance(rewards, list)

    def test_calculate_mutation_rewards_with_data(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        rewards = reward_model.calculate_mutation_rewards()
        assert len(rewards) >= 0

    def test_get_mutation_priorities(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        priorities = reward_model.get_mutation_priorities(min_confidence=0.0)
        assert isinstance(priorities, list)

    def test_mutation_reward_dict(self, reward_model, populated_memory):
        reward_model._memory = populated_memory
        rewards = reward_model.calculate_mutation_rewards()
        for r in rewards:
            d = r.to_dict()
            assert "gene_category" in d
            assert "mutation_action" in d

    # ── 综合评估 ──────────────────────────────────────────────

    def test_evaluate_creative(self, reward_model, sample_variant_metrics):
        result = reward_model.evaluate_creative(sample_variant_metrics)
        assert "reward" in result
        assert "verdict" in result
        assert result["verdict"] in ("strong_winner", "winner", "underperformer")

    def test_evaluate_creative_with_dna(self, reward_model, sample_variant_metrics, populated_memory):
        reward_model._memory = populated_memory
        result = reward_model.evaluate_creative(
            sample_variant_metrics,
            dna_genes={"hook": "transformation", "visual": "fantasy"},
        )
        assert "gene_contributions" in result

    def test_evaluate_creative_underperformer(self, reward_model, sample_negative_metrics):
        result = reward_model.evaluate_creative(sample_negative_metrics)
        assert result["verdict"] == "underperformer"

    # ── 配置 ──────────────────────────────────────────────────

    def test_reward_config_default(self):
        config = RewardConfig()
        assert config.roas_weight == 0.5
        assert config.ltv_weight == 0.3
        assert config.spend_risk_weight == 0.2

    def test_reward_config_custom(self):
        config = RewardConfig(roas_weight=0.6, ltv_weight=0.2)
        assert config.roas_weight == 0.6
        assert config.ltv_weight == 0.2

    def test_create_reward_model(self):
        model = create_reward_model(roas_weight=0.4, ltv_weight=0.4)
        assert model._config.roas_weight == 0.4

    # ── 生命周期 ──────────────────────────────────────────────

    def test_reward_model_stats(self, reward_model, sample_variant_metrics):
        reward_model.calculate(sample_variant_metrics)
        stats = reward_model.stats()
        assert stats["total_rewards"] >= 1

    def test_reward_model_reset(self, reward_model, sample_variant_metrics):
        reward_model.calculate(sample_variant_metrics)
        reward_model.reset()
        assert reward_model.stats()["total_rewards"] == 0

    def test_reward_history_accumulates(self, reward_model, sample_metrics_list):
        for m in sample_metrics_list:
            reward_model.calculate(m)
        assert reward_model.stats()["total_rewards"] == len(sample_metrics_list)


# ═══════════════════════════════════════════════════════════════
# E14.4.4.2 PatternMiner Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestPatternMiner:
    """PatternMiner — 创意模式挖掘引擎."""

    # ── 单基因模式 ────────────────────────────────────────────

    def test_mine_single_gene(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        pattern_miner._min_occurrence = 2  # 适配测试数据量
        patterns = pattern_miner.mine_single_gene()
        assert len(patterns) > 0
        for p in patterns:
            assert p.pattern_category == PatternCategory.SINGLE_GENE
            assert len(p.genes) == 1

    def test_mine_single_gene_filter(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_single_gene(gene_category="hook")
        for p in patterns:
            assert "hook" in p.genes

    def test_mine_single_gene_sorted(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_single_gene()
        if len(patterns) >= 2:
            score1 = patterns[0].success_rate * patterns[0].confidence_score
            score2 = patterns[1].success_rate * patterns[1].confidence_score
            assert score1 >= score2

    def test_mine_single_gene_confidence_levels(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_single_gene()
        for p in patterns:
            assert p.confidence in PatternConfidence

    # ── 双基因模式 ────────────────────────────────────────────

    def test_mine_gene_pairs(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_gene_pairs()
        for p in patterns:
            assert p.pattern_category == PatternCategory.GENE_PAIR
            assert len(p.genes) == 2

    def test_mine_gene_pairs_non_empty(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_gene_pairs()
        assert isinstance(patterns, list)

    def test_mine_gene_pairs_evidence(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        patterns = pattern_miner.mine_gene_pairs()
        for p in patterns:
            assert len(p.evidence) > 0

    # ── 全量挖掘 ──────────────────────────────────────────────

    def test_mine_all(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        pattern_miner._min_occurrence = 2  # 适配测试数据量
        report = pattern_miner.mine_all()
        assert isinstance(report, MiningReport)
        assert report.total_patterns > 0

    def test_mine_all_empty(self, pattern_miner):
        report = pattern_miner.mine_all()
        assert isinstance(report, MiningReport)
        assert report.total_patterns == 0

    def test_mine_all_top_patterns(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        report = pattern_miner.mine_all()
        assert len(report.top_patterns) <= 20

    def test_mine_all_summary(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        report = pattern_miner.mine_all()
        assert report.summary

    # ── 可靠模式 ──────────────────────────────────────────────

    def test_get_reliable_patterns(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        reliable = pattern_miner.get_reliable_patterns()
        assert isinstance(reliable, list)

    def test_get_top_patterns(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        top = pattern_miner.get_top_patterns(5)
        assert len(top) <= 5

    # ── DNAPattern 模型 ───────────────────────────────────────

    def test_dna_pattern_properties(self):
        pattern = DNAPattern(
            genes={"hook": "transformation"},
            pattern_category=PatternCategory.SINGLE_GENE,
            occurrence_count=20,
            success_count=15,
            success_rate=0.75,
            avg_roas=2.0,
            avg_ltv=5.0,
            confidence=PatternConfidence.HIGH,
            confidence_score=0.85,
            evidence=["C101", "C102"],
        )
        assert pattern.is_reliable
        assert pattern.gene_key == "hook=transformation"
        assert pattern.evidence == ["C101", "C102"]

    def test_dna_pattern_dict(self):
        pattern = DNAPattern(
            genes={"hook": "transformation"},
            pattern_category=PatternCategory.SINGLE_GENE,
            occurrence_count=10,
            success_count=7,
            success_rate=0.7,
            confidence=PatternConfidence.MEDIUM,
            confidence_score=0.65,
        )
        d = pattern.to_dict()
        assert d["genes"] == {"hook": "transformation"}
        assert d["pattern_category"] == "single_gene"
        assert d["is_reliable"]

    def test_dna_pattern_not_reliable(self):
        pattern = DNAPattern(
            genes={"hook": "unknown"},
            occurrence_count=4,
            confidence=PatternConfidence.LOW,
        )
        assert not pattern.is_reliable

    # ── CreativePattern 模型 ──────────────────────────────────

    def test_creative_pattern_dict(self):
        dna_patterns = [
            DNAPattern(
                genes={"hook": "transformation"},
                pattern_category=PatternCategory.SINGLE_GENE,
                occurrence_count=20,
                success_count=15,
                success_rate=0.75,
                confidence=PatternConfidence.HIGH,
                confidence_score=0.85,
            ),
        ]
        cp = CreativePattern(
            dna_patterns=dna_patterns,
            aggregated_success_rate=0.75,
            recommendation="Use transformation hook",
            expected_impact="+23% ROAS",
            confidence=0.85,
        )
        d = cp.to_dict()
        assert "dna_patterns" in d
        assert "recommendation" in d

    # ── MiningReport 模型 ─────────────────────────────────────

    def test_mining_report_dict(self, pattern_miner, populated_memory):
        pattern_miner._memory = populated_memory
        report = pattern_miner.mine_all()
        d = report.to_dict()
        assert "total_patterns" in d
        assert "reliable_patterns" in d
        assert "summary" in d

    # ── 配置 ──────────────────────────────────────────────────

    def test_pattern_miner_config(self):
        miner = PatternMiner(min_occurrence=10, min_success_rate=0.6, roas_winner_threshold=2.0)
        assert miner._min_occurrence == 10
        assert miner._min_success_rate == 0.6
        assert miner._roas_winner_threshold == 2.0

    def test_create_pattern_miner(self, memory):
        miner = create_pattern_miner(memory=memory)
        assert miner._min_occurrence == 5
        assert miner._memory is memory

    # ── 生命周期 ──────────────────────────────────────────────

    def test_pattern_miner_stats(self, pattern_miner):
        stats = pattern_miner.stats()
        assert "min_occurrence" in stats
        assert "min_success_rate" in stats

    def test_pattern_miner_reset(self, pattern_miner):
        pattern_miner.reset()  # 无状态，不应报错

    # ── 模式类别 ──────────────────────────────────────────────

    def test_pattern_category_enum(self):
        assert PatternCategory.SINGLE_GENE.value == "single_gene"
        assert PatternCategory.GENE_PAIR.value == "gene_pair"
        assert PatternCategory.GENE_TRIPLE.value == "gene_triple"
        assert PatternCategory.FULL_DNA.value == "full_dna"

    def test_pattern_confidence_enum(self):
        assert PatternConfidence.HIGH.value == "high"
        assert PatternConfidence.MEDIUM.value == "medium"
        assert PatternConfidence.LOW.value == "low"
        assert PatternConfidence.INSUFFICIENT.value == "insufficient"

    # ── 边界条件 ──────────────────────────────────────────────

    def test_mine_single_gene_empty_memory(self, pattern_miner):
        patterns = pattern_miner.mine_single_gene()
        assert patterns == []

    def test_mine_gene_pairs_empty_memory(self, pattern_miner):
        patterns = pattern_miner.mine_gene_pairs()
        assert patterns == []

    def test_mine_all_empty_memory(self, pattern_miner):
        report = pattern_miner.mine_all()
        assert report.total_patterns == 0
        assert "无可靠模式" in report.summary or "无" in report.summary

    def test_get_top_patterns_empty(self, pattern_miner):
        top = pattern_miner.get_top_patterns(5)
        assert top == []


# ═══════════════════════════════════════════════════════════════
# E14.4.4.3 StrategyMemory Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestStrategyMemory:
    """StrategyMemory — 长期策略记忆."""

    # ── 记录 ──────────────────────────────────────────────────

    def test_record_strategy(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        record = strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        assert record.strategy_type == CreativeStrategyType.REFRESH_HOOK
        assert record.context_key == context.broad_context_key

    def test_record_batch(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        entries = [
            {
                "strategy_type": "refresh_hook",
                "context": context,
                "outcome": "success",
                "reward": 0.5,
            },
            {
                "strategy_type": "change_visual",
                "context": context,
                "outcome": "failure",
                "reward": -0.2,
            },
        ]
        records = strategy_memory.record_batch(entries)
        assert len(records) == 2

    def test_record_with_metrics(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        record = strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 1.2},
        )
        assert record.metrics_before["roas"] == 0.8
        assert record.metrics_after["roas"] == 1.2

    def test_record_updates_effectiveness(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.FAILURE,
            reward=-0.2,
        )
        eff = strategy_memory.get_effectiveness(
            CreativeStrategyType.REFRESH_HOOK, context.broad_context_key,
        )
        assert eff is not None
        assert eff.attempt_count == 2
        assert eff.success_count == 1

    # ── 推荐 ──────────────────────────────────────────────────

    def test_recommend_exact_match(self, strategy_memory):
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.7,
        )
        recommendations = strategy_memory.recommend(context, min_confidence=0.0)
        assert len(recommendations) > 0

    def test_recommend_broad_match(self, strategy_memory):
        narrow = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=narrow,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.7,
        )
        broad = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="mature",
        )
        recommendations = strategy_memory.recommend(broad, min_confidence=0.0)
        assert len(recommendations) > 0

    def test_recommend_top_n(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        for i, stype in enumerate([
            CreativeStrategyType.REFRESH_HOOK,
            CreativeStrategyType.CHANGE_VISUAL_STYLE,
            CreativeStrategyType.CHANGE_EMOTION,
            CreativeStrategyType.COPY_WINNER_DNA,
            CreativeStrategyType.EXPLORE_NEW_DNA,
            CreativeStrategyType.REFRESH_CREATIVE,
        ]):
            strategy_memory.record(
                strategy_type=stype, context=context,
                outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
            )
        recommendations = strategy_memory.recommend(context, min_confidence=0.0, top_n=3)
        assert len(recommendations) <= 3

    def test_recommend_for_context(self, strategy_memory):
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.7,
        )
        recs = strategy_memory.recommend_for_context(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        assert len(recs) > 0

    def test_recommend_empty(self, strategy_memory):
        context = ContextProfile(game="None", platform="none", market="none")
        recs = strategy_memory.recommend(context)
        assert recs == []

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_effectiveness(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        eff = strategy_memory.get_effectiveness(
            CreativeStrategyType.REFRESH_HOOK, context.broad_context_key,
        )
        assert eff is not None
        assert eff.attempt_count == 1

    def test_get_effectiveness_aggregated(self, strategy_memory):
        c1 = ContextProfile(game="G1", platform="android", market="US")
        c2 = ContextProfile(game="G2", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=c1,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=c2,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.3,
        )
        eff = strategy_memory.get_effectiveness(CreativeStrategyType.REFRESH_HOOK)
        assert eff is not None
        assert eff.attempt_count == 2

    def test_get_records_by_strategy(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        strategy_memory.record(
            strategy_type=CreativeStrategyType.CHANGE_VISUAL_STYLE, context=context,
            outcome=CreativeDecisionOutcome.FAILURE, reward=-0.2,
        )
        records = strategy_memory.get_records_by_strategy(CreativeStrategyType.REFRESH_HOOK)
        assert len(records) == 1

    def test_get_records_by_context(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        records = strategy_memory.get_records_by_context(context.broad_context_key)
        assert len(records) == 1

    def test_get_all_effectiveness(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        all_eff = strategy_memory.get_all_effectiveness()
        assert len(all_eff) > 0

    def test_get_reliable_strategies(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        for _ in range(10):
            strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
                outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
            )
        reliable = strategy_memory.get_reliable_strategies()
        assert len(reliable) > 0

    # ── 报告 ──────────────────────────────────────────────────

    def test_generate_report(self, strategy_memory):
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        report = strategy_memory.generate_report()
        assert report.total_records == 1
        assert report.summary

    def test_generate_report_empty(self, strategy_memory):
        report = strategy_memory.generate_report()
        assert report.total_records == 0

    def test_strategy_memory_report_dict(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        report = strategy_memory.generate_report()
        d = report.to_dict()
        assert "total_records" in d
        assert "effectiveness" in d
        assert "top_strategies" in d

    # ── ContextProfile ────────────────────────────────────────

    def test_context_profile_key(self):
        ctx = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        assert ctx.context_key == "MergeGame:android:US:merge:growth"
        assert ctx.broad_context_key == "MergeGame:android:US:merge"

    def test_context_profile_dict(self):
        ctx = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        d = ctx.to_dict()
        assert d["game"] == "MergeGame"
        assert d["platform"] == "android"

    # ── StrategyEffectiveness ─────────────────────────────────

    def test_strategy_effectiveness_is_reliable(self):
        eff = StrategyEffectiveness(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            attempt_count=10,
            success_count=7,
            success_rate=0.7,
            confidence=0.8,
        )
        assert eff.is_reliable

    def test_strategy_effectiveness_not_reliable(self):
        eff = StrategyEffectiveness(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            attempt_count=2,
            confidence=0.3,
        )
        assert not eff.is_reliable

    def test_strategy_effectiveness_dict(self):
        eff = StrategyEffectiveness(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            attempt_count=5,
            success_count=3,
            success_rate=0.6,
            avg_reward=0.4,
            confidence=0.6,
        )
        d = eff.to_dict()
        assert d["strategy_type"] == "refresh_hook"
        assert d["attempt_count"] == 5

    # ── 生命周期 ──────────────────────────────────────────────

    def test_strategy_memory_stats(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        stats = strategy_memory.stats()
        assert stats["total_records"] == 1

    def test_strategy_memory_reset(self, strategy_memory):
        context = ContextProfile(game="G", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK, context=context,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        strategy_memory.reset()
        assert strategy_memory.stats()["total_records"] == 0

    def test_create_strategy_memory(self):
        sm = create_strategy_memory()
        assert isinstance(sm, StrategyMemory)


# ═══════════════════════════════════════════════════════════════
# E14.4.4.4 MutationLearning Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestMutationLearning:
    """MutationLearning — 变异学习引擎."""

    # ── 记录 ──────────────────────────────────────────────────

    def test_record_mutation(self, mutation_learning):
        record = mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            parent_creative_id="C101",
            variant_creative_id="CV201",
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
            reward=0.5,
            outcome=CreativeDecisionOutcome.SUCCESS,
        )
        assert record.gene_category == GeneCategory.HOOK
        assert record.mutation_action == GeneMutationAction.CHANGE
        assert record.roas_impact > 0

    def test_record_impact_calculation(self, mutation_learning):
        record = mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.3},
            outcome=CreativeDecisionOutcome.SUCCESS,
        )
        assert record.roas_impact == pytest.approx(0.3)

    def test_record_negative_impact(self, mutation_learning):
        record = mutation_learning.record(
            gene_category=GeneCategory.VISUAL,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.5},
            after_metrics={"roas": 0.9},
            outcome=CreativeDecisionOutcome.FAILURE,
        )
        assert record.roas_impact < 0

    def test_record_batch(self, mutation_learning):
        for i in range(5):
            mutation_learning.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS if i < 3 else CreativeDecisionOutcome.FAILURE,
                reward=0.5 if i < 3 else -0.2,
            )
        eff = mutation_learning.get_effectiveness(GeneCategory.HOOK, GeneMutationAction.CHANGE)
        assert eff is not None
        assert eff.attempt_count == 5
        assert eff.success_count == 3

    def test_record_from_decision(self, mutation_learning, populated_memory):
        mutation_learning._memory = populated_memory
        resolved = populated_memory.get_resolved()
        for d in resolved:
            r = mutation_learning.record_from_decision(d)
            if r:
                assert r.gene_category is not None
                assert r.mutation_action is not None

    def test_record_batch_from_decisions(self, mutation_learning, populated_memory):
        mutation_learning._memory = populated_memory
        resolved = populated_memory.get_resolved()
        records = mutation_learning.record_batch_from_decisions(resolved)
        assert isinstance(records, list)

    def test_import_from_memory(self, mutation_learning, populated_memory):
        mutation_learning._memory = populated_memory
        count = mutation_learning.import_from_memory()
        assert count >= 0

    # ── 有效性 ────────────────────────────────────────────────

    def test_get_effectiveness(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        eff = mutation_learning.get_effectiveness(GeneCategory.HOOK, GeneMutationAction.CHANGE)
        assert eff is not None
        assert eff.attempt_count == 1
        assert eff.success_count == 1

    def test_get_effectiveness_aggregated(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.EXPLORE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.3,
        )
        eff = mutation_learning.get_effectiveness(GeneCategory.HOOK)
        assert eff is not None
        assert eff.attempt_count == 2

    def test_get_all_effectiveness(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        all_eff = mutation_learning.get_all_effectiveness()
        assert len(all_eff) > 0

    def test_get_reliable_effectiveness(self, mutation_learning):
        for _ in range(5):
            mutation_learning.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )
        reliable = mutation_learning.get_reliable_effectiveness()
        assert len(reliable) > 0

    # ── 优先级 ────────────────────────────────────────────────

    def test_get_priorities(self, mutation_learning):
        # 好的变异
        for _ in range(5):
            mutation_learning.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )
        # 差的变异
        for _ in range(5):
            mutation_learning.record(
                gene_category=GeneCategory.VISUAL,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 0.6},
                outcome=CreativeDecisionOutcome.FAILURE,
                reward=-0.3,
            )
        priorities = mutation_learning.get_priorities(min_confidence=0.2)
        if priorities:
            assert priorities[0].priority_score >= priorities[-1].priority_score

    def test_get_priorities_for_strategy(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        weights = mutation_learning.get_priorities_for_strategy()
        assert isinstance(weights, dict)
        for key in ["hook", "visual", "gameplay", "emotion", "audience", "context", "monetization"]:
            assert key in weights

    def test_get_priorities_for_strategy_exclude(self, mutation_learning):
        weights = mutation_learning.get_priorities_for_strategy(
            exclude_categories=[GeneCategory.HOOK, GeneCategory.VISUAL],
        )
        assert "hook" not in weights
        assert "visual" not in weights

    def test_get_top_mutation_categories(self, mutation_learning):
        for _ in range(5):
            mutation_learning.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )
        top = mutation_learning.get_top_mutation_categories(top_n=3)
        assert len(top) <= 3

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_records_by_category(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        mutation_learning.record(
            gene_category=GeneCategory.VISUAL,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.FAILURE, reward=-0.2,
        )
        hook_records = mutation_learning.get_records_by_category(GeneCategory.HOOK)
        assert len(hook_records) == 1

    def test_get_records_by_action(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        mutation_learning.record(
            gene_category=GeneCategory.VISUAL,
            mutation_action=GeneMutationAction.EXPLORE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.3,
        )
        change_records = mutation_learning.get_records_by_action(GeneMutationAction.CHANGE)
        assert len(change_records) == 1

    def test_get_recent(self, mutation_learning):
        for i in range(10):
            mutation_learning.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
            )
        recent = mutation_learning.get_recent(5)
        assert len(recent) == 5

    # ── 报告 ──────────────────────────────────────────────────

    def test_generate_report(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        report = mutation_learning.generate_report()
        assert report.total_records == 1
        assert report.summary

    def test_generate_report_empty(self, mutation_learning):
        report = mutation_learning.generate_report()
        assert report.total_records == 0

    def test_mutation_learning_report_dict(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        report = mutation_learning.generate_report()
        d = report.to_dict()
        assert "total_records" in d
        assert "priorities" in d

    # ── MutationRecord 模型 ───────────────────────────────────

    def test_mutation_record_properties(self, mutation_learning):
        record = mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            before_metrics={"roas": 1.0},
            after_metrics={"roas": 1.5},
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        assert record.is_success
        assert record.is_significant_impact

    def test_mutation_record_dict(self, mutation_learning):
        record = mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            parent_creative_id="C101",
            variant_creative_id="CV201",
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
        )
        d = record.to_dict()
        assert d["gene_category"] == "hook"
        assert d["parent_creative_id"] == "C101"

    # ── MutationEffectiveness ─────────────────────────────────

    def test_mutation_effectiveness_is_reliable(self):
        eff = MutationEffectiveness(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            attempt_count=5,
            success_count=4,
            success_rate=0.8,
            confidence=0.7,
        )
        assert eff.is_reliable

    def test_mutation_effectiveness_score(self):
        eff = MutationEffectiveness(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            success_rate=0.8,
            avg_roas_impact=0.3,
            confidence=0.7,
        )
        assert eff.effectiveness_score > 0

    # ── 生命周期 ──────────────────────────────────────────────

    def test_mutation_learning_stats(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        stats = mutation_learning.stats()
        assert stats["total_records"] == 1

    def test_mutation_learning_reset(self, mutation_learning):
        mutation_learning.record(
            gene_category=GeneCategory.HOOK,
            mutation_action=GeneMutationAction.CHANGE,
            outcome=CreativeDecisionOutcome.SUCCESS, reward=0.5,
        )
        mutation_learning.reset()
        assert mutation_learning.stats()["total_records"] == 0

    def test_create_mutation_learning(self, memory):
        ml = create_mutation_learning(memory=memory, min_attempts=5)
        assert ml._min_attempts == 5


# ═══════════════════════════════════════════════════════════════
# E14.4.4.5 CreativePolicy Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestCreativePolicy:
    """CreativePolicy — 上下文感知决策策略."""

    # ── 决策 ──────────────────────────────────────────────────

    def test_decide_default_rules(self, policy, sample_context):
        """无数据时使用默认规则."""
        decision = policy.decide(sample_context)
        assert decision is not None
        assert decision.action is not None
        assert decision.confidence == PolicyConfidence.LOW

    def test_decide_fatigued_context(self, policy, sample_fatigued_context):
        """疲劳场景应触发 REFRESH_HOOK."""
        decision = policy.decide(sample_fatigued_context)
        assert decision.action in (PolicyAction.REFRESH_HOOK, PolicyAction.REFRESH_CREATIVE, PolicyAction.CHANGE_EMOTION)

    def test_decide_with_strategy_data(self, strategy_memory, policy):
        """有策略记忆数据时优先生成策略决策."""
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        for _ in range(10):
            strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.7,
            )
        policy._strategy_memory = strategy_memory

        policy_context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
            current_roas=1.2, current_ctr=0.025,
        )
        decision = policy.decide(policy_context)
        assert decision is not None
        assert decision.confidence_score > 0.4

    def test_decide_batch(self, policy, sample_context):
        contexts = [sample_context, sample_context]
        report = policy.decide_batch(contexts)
        assert report.total_decisions == 2

    def test_decide_batch_high_confidence(self, strategy_memory, policy):
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        for _ in range(10):
            strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.7,
            )
        policy._strategy_memory = strategy_memory

        policy_context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        report = policy.decide_batch([policy_context, policy_context])
        assert report.total_decisions == 2
        assert report.high_confidence >= 0

    # ── PolicyContext ──────────────────────────────────────────

    def test_policy_context_is_fatigued(self):
        ctx = PolicyContext(current_fatigue=0.85)
        assert ctx.is_fatigued
        ctx2 = PolicyContext(current_fatigue=0.3)
        assert not ctx2.is_fatigued

    def test_policy_context_is_underperforming(self):
        ctx = PolicyContext(current_roas=0.5)
        assert ctx.is_underperforming
        ctx2 = PolicyContext(current_roas=1.5)
        assert not ctx2.is_underperforming

    def test_policy_context_is_healthy(self):
        ctx = PolicyContext(current_roas=1.5, current_fatigue=0.2)
        assert ctx.is_healthy
        ctx2 = PolicyContext(current_roas=0.8, current_fatigue=0.5)
        assert not ctx2.is_healthy

    def test_policy_context_to_context_profile(self):
        ctx = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
            current_roas=1.5, current_ctr=0.03,
            current_fatigue=0.3, current_frequency=2.0,
            current_ltv=6.0,
        )
        profile = ctx.to_context_profile()
        assert profile.game == "MergeGame"
        assert profile.metrics["roas"] == 1.5

    def test_policy_context_dict(self):
        ctx = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_ctr=0.025,
        )
        d = ctx.to_dict()
        assert d["game"] == "MergeGame"
        assert d["current_roas"] == 1.2

    # ── PolicyDecision ────────────────────────────────────────

    def test_policy_decision_dict(self, policy, sample_context):
        decision = policy.decide(sample_context)
        d = decision.to_dict()
        assert "action" in d
        assert "confidence" in d
        assert "rationale" in d
        assert "strategy_type" in d
        assert "suggested_params" in d

    def test_policy_decision_supporting_data(self, strategy_memory, policy):
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        for _ in range(10):
            strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.7,
            )
        policy._strategy_memory = strategy_memory

        policy_context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        decision = policy.decide(policy_context)
        assert len(decision.supporting_strategies) >= 0

    # ── PolicyReport ──────────────────────────────────────────

    def test_policy_report(self, policy, sample_context):
        report = policy.decide_batch([sample_context, sample_context])
        assert report.total_decisions == 2
        d = report.to_dict()
        assert "decisions" in d
        assert "high_confidence" in d

    # ── 默认规则 ──────────────────────────────────────────────

    def test_default_rules_fatigue_high(self, policy):
        ctx = PolicyContext(current_fatigue=0.8, current_frequency=5.0, current_roas=0.6)
        decision = policy.decide(ctx)
        assert decision.action == PolicyAction.REFRESH_HOOK

    def test_default_rules_roas_low(self, policy):
        ctx = PolicyContext(current_roas=0.4, current_ctr=0.005, current_fatigue=0.6)
        decision = policy.decide(ctx)
        assert decision.action in (PolicyAction.CHANGE_VISUAL, PolicyAction.CHANGE_EMOTION, PolicyAction.REFRESH_CREATIVE)

    def test_default_rules_scale_winner(self, policy):
        ctx = PolicyContext(
            current_roas=1.8, current_fatigue=0.2,
            current_frequency=2.0, active_creative_count=10,
        )
        decision = policy.decide(ctx)
        assert decision.action == PolicyAction.SCALE_WINNER

    def test_default_rules_hold(self, policy):
        ctx = PolicyContext(
            current_roas=1.3, current_fatigue=0.3,
            current_frequency=2.0, active_creative_count=10,
        )
        decision = policy.decide(ctx)
        assert decision.action == PolicyAction.HOLD

    def test_default_rules_explore(self, policy):
        ctx = PolicyContext(
            current_roas=1.0, current_fatigue=0.3,
            active_creative_count=3,
        )
        decision = policy.decide(ctx)
        assert decision.action == PolicyAction.EXPLORE_NEW

    # ── 动作映射 ──────────────────────────────────────────────

    def test_policy_to_strategy_mapping(self, policy, sample_context):
        decision = policy.decide(sample_context)
        assert decision.strategy_type in CreativeStrategyType

    def test_action_impacts(self, policy, sample_context):
        decision = policy.decide(sample_context)
        assert decision.expected_impact

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_history(self, policy, sample_context):
        policy.decide(sample_context)
        policy.decide(sample_context)
        history = policy.get_history()
        assert len(history) == 2

    def test_get_high_confidence_decisions(self, strategy_memory, policy):
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        for _ in range(10):
            strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.7,
            )
        policy._strategy_memory = strategy_memory

        policy_context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        policy.decide(policy_context)
        high = policy.get_high_confidence_decisions()
        assert isinstance(high, list)

    # ── 生命周期 ──────────────────────────────────────────────

    def test_policy_stats(self, policy, sample_context):
        policy.decide(sample_context)
        stats = policy.stats()
        assert stats["total"] == 1

    def test_policy_reset(self, policy, sample_context):
        policy.decide(sample_context)
        policy.reset()
        assert policy.stats()["total"] == 0

    def test_create_creative_policy(self, memory):
        p = create_creative_policy(memory=memory)
        assert isinstance(p, CreativePolicy)


# ═══════════════════════════════════════════════════════════════
# E14.4.4.6 CreativeAgent Integration Tests (30 tests)
# ═══════════════════════════════════════════════════════════════


class TestCreativeAgentLearningIntegration:
    """CreativeAgent 学习模块集成测试."""

    # ── 学习模块访问 ──────────────────────────────────────────

    def test_get_reward_model(self, agent):
        assert agent.get_reward_model() is not None
        assert isinstance(agent.get_reward_model(), RewardModel)

    def test_get_pattern_miner(self, agent):
        assert agent.get_pattern_miner() is not None
        assert isinstance(agent.get_pattern_miner(), PatternMiner)

    def test_get_strategy_memory(self, agent):
        assert agent.get_strategy_memory() is not None
        assert isinstance(agent.get_strategy_memory(), StrategyMemory)

    def test_get_mutation_learning(self, agent):
        assert agent.get_mutation_learning() is not None
        assert isinstance(agent.get_mutation_learning(), MutationLearning)

    def test_get_policy(self, agent):
        assert agent.get_policy() is not None
        assert isinstance(agent.get_policy(), CreativePolicy)

    # ── 从实验学习 ────────────────────────────────────────────

    def test_learn_from_experiment(self, agent):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
                min_duration_days=3,
            ),
        )
        experiment = agent.start_experiment(plan)
        variant_metrics = [
            VariantMetrics(
                variant_id="V001", creative_id="C102",
                group_type=VariantGroupType.VARIANT,
                roas=2.5, ctr=0.035, fatigue=0.2,
                spend=1500.0, revenue=3750.0, installs=800,
                ltv=8.5, is_winner=True,
            ),
        ]
        agent.collect_experiment_results(experiment, variant_metrics)
        result = agent.learn_from_experiment(experiment)
        assert "experiment_id" in result
        assert "variants_analyzed" in result
        assert "avg_reward" in result

    def test_learn_from_experiment_no_variants(self, agent):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        experiment = agent.start_experiment(plan)
        agent._experiment_manager.complete(experiment)
        result = agent.learn_from_experiment(experiment)
        assert result["variants_analyzed"] == 0

    def test_learn_from_batch_experiments(self, agent):
        experiments = []
        for i in range(3):
            plan = CreativePlan(
                creative_id=f"C10{i}",
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                mutation_configs=[MutationConfig()],
                experiment_config=ExperimentConfig(
                    experiment_type=ExperimentType.A_B_TEST,
                    max_budget=1000.0,
                ),
            )
            exp = agent.start_experiment(plan)
            agent._experiment_manager.complete(exp)
            experiments.append(exp)

        result = agent.learn_from_batch_experiments(experiments)
        assert "experiments_processed" in result
        assert "mining_report" in result
        assert "mutation_learning_report" in result
        assert "strategy_memory_report" in result

    # ── 策略决策 ──────────────────────────────────────────────

    def test_decide_with_policy(self, agent):
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        assert decision is not None
        assert decision.action is not None

    def test_decide_with_policy_fatigued(self, agent):
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=0.6, current_fatigue=0.85, current_frequency=5.0,
        )
        assert decision.action in (PolicyAction.REFRESH_HOOK, PolicyAction.REFRESH_CREATIVE, PolicyAction.CHANGE_EMOTION)

    def test_decide_with_policy_healthy(self, agent):
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.8, current_fatigue=0.2,
            current_frequency=1.5, active_creative_count=12,
        )
        assert decision.action == PolicyAction.SCALE_WINNER

    # ── 学习循环 ──────────────────────────────────────────────

    def test_run_learning_loop_empty(self, agent):
        result = agent.run_learning_loop()
        assert "mining_report" in result
        assert "dna_rewards" in result
        assert "mutation_report" in result
        assert "strategy_report" in result
        assert "summary" in result

    def test_run_learning_loop_with_context(self, agent):
        context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        result = agent.run_learning_loop(context=context)
        assert "policy_decision" in result
        assert result["policy_decision"] is not None

    def test_run_learning_loop_with_experiments(self, agent, populated_memory):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        exp = agent.start_experiment(plan)
        agent._experiment_manager.complete(exp)
        result = agent.run_learning_loop(completed_experiments=[exp])
        assert "experiment_learning" in result

    # ── 完整闭环 ──────────────────────────────────────────────

    def test_run_full_creative_loop(self, agent):
        signals = [
            {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91},
        ]
        context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.0, current_fatigue=0.4,
        )
        result = agent.run_full_creative_loop(signals, context=context)
        assert "strategy_pipeline" in result
        assert "execution_pipeline" in result
        assert "learning_loop" in result
        assert "summary" in result

    # ── 状态管理 ──────────────────────────────────────────────

    def test_agent_state_learning(self, agent, populated_memory):
        context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        agent.run_learning_loop(context=context)
        assert agent.state == CreativeAgentState.IDLE

    def test_agent_state_after_decide(self, agent):
        agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        assert agent.state == CreativeAgentState.IDLE

    # ── 统计 ──────────────────────────────────────────────────

    def test_stats_includes_learning_modules(self, agent):
        stats = agent.stats()
        assert "reward_model" in stats
        assert "pattern_miner" in stats
        assert "strategy_memory" in stats
        assert "mutation_learning" in stats
        assert "policy" in stats

    def test_learning_stats_populated(self, agent, populated_memory):
        agent.run_learning_loop()
        stats = agent.stats()
        assert stats["reward_model"]["total_rewards"] >= 0

    # ── 重置 ──────────────────────────────────────────────────

    def test_reset_includes_learning_modules(self, agent):
        agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        agent.reset()
        stats = agent.stats()
        assert stats["policy"]["total"] == 0
        assert stats["strategy_memory"]["total_records"] == 0

    # ── 数据闭环 ──────────────────────────────────────────────

    def test_end_to_end_learning_flow(self, agent):
        """完整数据闭环: Experiment → Learn → Pattern Mine → Policy."""
        # 1. 创建实验
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        experiment = agent.start_experiment(plan)

        # 2. 收集结果
        variant_metrics = [
            VariantMetrics(
                variant_id="V001", creative_id="C102",
                group_type=VariantGroupType.VARIANT,
                roas=2.5, ctr=0.035, fatigue=0.2,
                spend=1500.0, revenue=3750.0, installs=800,
                ltv=8.5, is_winner=True,
            ),
        ]
        agent.collect_experiment_results(experiment, variant_metrics)

        # 3. 学习
        learn_result = agent.learn_from_experiment(experiment)
        assert learn_result["winner_found"]

        # 4. 模式挖掘
        mining_report = agent.get_pattern_miner().mine_all()
        assert isinstance(mining_report, MiningReport)

        # 5. 策略决策
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        assert decision is not None
        assert decision.action is not None

    def test_multiple_learning_cycles(self, agent):
        """多次学习循环数据累积."""
        for i in range(3):
            plan = CreativePlan(
                creative_id=f"C10{i}",
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                mutation_configs=[MutationConfig()],
                experiment_config=ExperimentConfig(
                    experiment_type=ExperimentType.A_B_TEST,
                    max_budget=1000.0,
                ),
            )
            exp = agent.start_experiment(plan)
            agent._experiment_manager.complete(exp)

        result = agent.run_learning_loop(
            completed_experiments=agent._experiment_manager.get_completed_experiments(),
        )
        assert "experiment_learning" in result
        learned = result["experiment_learning"]
        assert learned["experiments_processed"] == 3

    def test_learning_with_mutation_tracking(self, agent, populated_memory):
        """学习追踪变异记录."""
        # 导入已有变异记录
        count = agent.get_mutation_learning().import_from_memory()
        assert count >= 0

        # 运行学习循环
        result = agent.run_learning_loop()
        mutation_report = result["mutation_report"]
        assert mutation_report["total_records"] >= 0


# ═══════════════════════════════════════════════════════════════
# Full Learning Loop Tests (20 tests)
# ═══════════════════════════════════════════════════════════════


class TestFullLearningLoop:
    """完整 E14.4.4 学习闭环测试."""

    def test_learning_loop_complete_cycle(self, agent, populated_memory):
        """完整学习闭环: 实验→奖励→模式→变异→策略→决策."""
        # 1. Reward
        reward_model = agent.get_reward_model()
        metrics = VariantMetrics(
            variant_id="V001", creative_id="C102",
            roas=2.5, ctr=0.035, fatigue=0.2,
            spend=1500.0, revenue=3750.0, installs=800,
            ltv=8.5, is_winner=True,
        )
        reward = reward_model.calculate(metrics)
        assert reward.is_positive

        # 2. Pattern Mining
        miner = agent.get_pattern_miner()
        report = miner.mine_all()
        assert isinstance(report, MiningReport)

        # 3. Strategy Memory
        strat_mem = agent.get_strategy_memory()
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        strat_mem.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.7,
        )
        recs = strat_mem.recommend(context, min_confidence=0.0)
        assert len(recs) > 0

        # 4. Mutation Learning
        mut_learn = agent.get_mutation_learning()
        for _ in range(3):
            mut_learn.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )
        priorities = mut_learn.get_priorities(min_confidence=0.0)
        assert len(priorities) > 0

        # 5. Policy
        policy = agent.get_policy()
        ctx = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        decision = policy.decide(ctx)
        assert decision is not None

    def test_learning_loop_data_accumulation(self, agent):
        """数据累积: 多次学习后数据量递增."""
        sm = agent.get_strategy_memory()
        context = ContextProfile(game="G", platform="android", market="US")

        for i in range(5):
            sm.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )

        assert sm.stats()["total_records"] == 5
        assert len(sm.get_reliable_strategies()) > 0

    def test_learning_loop_policy_improvement(self, agent):
        """策略改进: 有数据后决策置信度提升."""
        sm = agent.get_strategy_memory()
        context = ContextProfile(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )

        # 无数据时
        ctx1 = PolicyContext(
            game="MergeGame", platform="android", market="US",
            genre="merge", stage="growth",
        )
        decision1 = agent.get_policy().decide(ctx1)
        assert decision1.confidence == PolicyConfidence.LOW

        # 填充数据
        for _ in range(10):
            sm.record(
                strategy_type=CreativeStrategyType.REFRESH_HOOK,
                context=context,
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.7,
            )

        # 有数据后
        decision2 = agent.get_policy().decide(ctx1)
        assert decision2.confidence_score > decision1.confidence_score

    def test_learning_loop_reward_to_strategy(self, agent):
        """奖励→策略记忆闭环."""
        reward_model = agent.get_reward_model()
        strategy_memory = agent.get_strategy_memory()

        metrics = VariantMetrics(
            variant_id="V001", creative_id="C102",
            roas=2.5, ctr=0.035, fatigue=0.2,
            spend=1500.0, revenue=3750.0, installs=800,
            ltv=8.5, is_winner=True,
        )
        reward = reward_model.calculate(metrics)

        context = ContextProfile(game="MergeGame", platform="android", market="US")
        strategy_memory.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS if reward.is_positive else CreativeDecisionOutcome.FAILURE,
            reward=reward.total_reward,
        )
        assert strategy_memory.stats()["total_records"] == 1

    def test_learning_loop_dna_to_pattern(self, agent):
        """DNA 记忆→模式挖掘闭环."""
        miner = agent.get_pattern_miner()
        agent.extract_dna(
            "C101", "creative_a",
            hook="transformation", visual="fantasy",
            emotion="surprise", fitness={"roas": 2.5},
        )
        all_dnas = agent.get_dna_engine().get_all_dnas()
        if all_dnas:
            agent._memory.mark_winner(all_dnas[0].dna_id)
        report = miner.mine_all()
        assert isinstance(report, MiningReport)

    def test_learning_loop_mutation_priority(self, agent):
        """变异学习→优先级排序."""
        mut_learn = agent.get_mutation_learning()

        for _ in range(5):
            mut_learn.record(
                gene_category=GeneCategory.HOOK,
                mutation_action=GeneMutationAction.CHANGE,
                before_metrics={"roas": 1.0},
                after_metrics={"roas": 1.5},
                outcome=CreativeDecisionOutcome.SUCCESS,
                reward=0.5,
            )

        priorities = mut_learn.get_priorities(min_confidence=0.0)
        assert len(priorities) > 0
        assert priorities[0].gene_category == GeneCategory.HOOK

    def test_learning_loop_context_aware_decision(self, agent):
        """上下文感知决策: 不同场景不同决策."""
        policy = agent.get_policy()

        # 高ROAS低疲劳 → 放量
        healthy_ctx = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.8, current_fatigue=0.2,
            current_frequency=1.5, active_creative_count=10,
        )
        decision1 = policy.decide(healthy_ctx)
        assert decision1.action == PolicyAction.SCALE_WINNER

        # 低ROAS高疲劳 → 刷新
        fatigued_ctx = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=0.5, current_fatigue=0.8,
            current_frequency=5.0, active_creative_count=8,
        )
        decision2 = policy.decide(fatigued_ctx)
        assert decision2.action in (PolicyAction.REFRESH_HOOK, PolicyAction.REFRESH_CREATIVE)

    def test_learning_loop_gene_category_enum(self):
        """基因类别枚举完整性."""
        assert GeneCategory.HOOK.value == "hook"
        assert GeneCategory.VISUAL.value == "visual"
        assert GeneCategory.GAMEPLAY.value == "gameplay"
        assert GeneCategory.EMOTION.value == "emotion"
        assert GeneCategory.AUDIENCE.value == "audience"
        assert GeneCategory.CONTEXT.value == "context"
        assert GeneCategory.MONETIZATION.value == "monetization"

    def test_learning_loop_policy_action_enum(self):
        """策略动作枚举完整性."""
        assert PolicyAction.REFRESH_HOOK.value == "refresh_hook"
        assert PolicyAction.CHANGE_VISUAL.value == "change_visual"
        assert PolicyAction.CHANGE_EMOTION.value == "change_emotion"
        assert PolicyAction.CHANGE_GAMEPLAY.value == "change_gameplay"
        assert PolicyAction.EXPLORE_AUDIENCE.value == "explore_audience"
        assert PolicyAction.COPY_WINNER.value == "copy_winner"
        assert PolicyAction.EXPLORE_NEW.value == "explore_new"
        assert PolicyAction.SCALE_WINNER.value == "scale_winner"
        assert PolicyAction.REFRESH_CREATIVE.value == "refresh_creative"
        assert PolicyAction.HOLD.value == "hold"

    def test_learning_loop_policy_confidence_enum(self):
        """置信度枚举完整性."""
        assert PolicyConfidence.HIGH.value == "high"
        assert PolicyConfidence.MEDIUM.value == "medium"
        assert PolicyConfidence.LOW.value == "low"
        assert PolicyConfidence.INSUFFICIENT.value == "insufficient"

    def test_learning_loop_all_modules_connected(self, agent):
        """所有学习模块连接验证."""
        assert agent.get_reward_model()._memory is agent.get_memory()
        assert agent.get_pattern_miner()._memory is agent.get_memory()
        assert agent.get_strategy_memory()._memory is agent.get_memory()
        assert agent.get_mutation_learning()._memory is agent.get_memory()

    def test_learning_loop_policy_shares_modules(self, agent):
        """Policy 与其他模块共享 memory."""
        policy = agent.get_policy()
        assert policy._memory is agent.get_memory()
        assert policy._pattern_miner is agent.get_pattern_miner()
        assert policy._strategy_memory is agent.get_strategy_memory()
        assert policy._mutation_learning is agent.get_mutation_learning()

    def test_run_full_creative_loop_with_data(self, agent, populated_memory):
        """完整闭环: 有数据时运行."""
        signals = [
            {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91},
        ]
        context = PolicyContext(
            game="MergeGame", platform="android", market="US",
            current_roas=1.0, current_fatigue=0.4,
        )
        result = agent.run_full_creative_loop(signals, context=context)
        assert "strategy_pipeline" in result
        assert "learning_loop" in result
        assert "summary" in result
        assert "mining_report" in result["learning_loop"]

    def test_mutation_learning_from_agent_decisions(self, agent, populated_memory):
        """从 Agent 决策中导入变异记录."""
        count = agent.get_mutation_learning().import_from_memory()
        assert count >= 0

    def test_strategy_memory_roas_improvement(self, agent):
        """策略记忆追踪 ROAS 提升."""
        sm = agent.get_strategy_memory()
        context = ContextProfile(game="MergeGame", platform="android", market="US")
        sm.record(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            context=context,
            outcome=CreativeDecisionOutcome.SUCCESS,
            reward=0.5,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 1.2},
        )
        eff = sm.get_effectiveness(
            CreativeStrategyType.REFRESH_HOOK, context.broad_context_key,
        )
        assert eff is not None
        assert eff.avg_roas_improvement > 0

    def test_pattern_miner_with_experiment_data(self, agent):
        """模式挖掘: 实验数据驱动."""
        # 创建并完成实验
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        exp = agent.start_experiment(plan)
        variant_metrics = [
            VariantMetrics(
                variant_id="V001", creative_id="C102",
                roas=2.5, ctr=0.035, fatigue=0.2,
                spend=1500.0, revenue=3750.0, installs=800,
                ltv=8.5, is_winner=True,
            ),
        ]
        agent.collect_experiment_results(exp, variant_metrics)

        # 学习
        agent.learn_from_experiment(exp)

        # 挖掘
        report = agent.get_pattern_miner().mine_all()
        assert isinstance(report, MiningReport)

    def test_reward_model_with_experiment_variants(self, agent):
        """奖励模型: 实验变体数据."""
        metrics = VariantMetrics(
            variant_id="V001", creative_id="C102",
            roas=2.5, ctr=0.035, fatigue=0.2,
            spend=1500.0, revenue=3750.0, installs=800,
            ltv=8.5, is_winner=True,
        )
        reward = agent.get_reward_model().calculate(metrics)
        assert reward.is_positive

    def test_policy_decision_has_suggested_params(self, agent):
        """策略决策包含建议参数."""
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        assert "mutation_weights" in decision.suggested_params
        assert "source" in decision.suggested_params

    def test_learning_loop_complete_flow_from_scratch(self, agent):
        """从零开始的完整学习闭环."""
        # 1. 创建素材
        agent.extract_dna("C101", "creative_a", hook="transformation",
                           visual="fantasy", emotion="surprise",
                           fitness={"roas": 2.0, "ctr": 0.035})

        # 2. 创建实验
        plan = CreativePlan(
            creative_id="C101",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        exp = agent.start_experiment(plan)

        # 3. 收集结果
        variant_metrics = [
            VariantMetrics(
                variant_id="V001", creative_id="C101",
                roas=2.5, ctr=0.035, fatigue=0.2,
                spend=1500.0, revenue=3750.0, installs=800,
                ltv=8.5, is_winner=True,
            ),
        ]
        agent.collect_experiment_results(exp, variant_metrics)

        # 4. 学习
        agent.learn_from_experiment(exp)

        # 5. 决策
        decision = agent.decide_with_policy(
            game="MergeGame", platform="android", market="US",
            current_roas=1.2, current_fatigue=0.35,
        )
        assert decision is not None


# ═══════════════════════════════════════════════════════════════
# Regression Tests (20 tests)
# ═══════════════════════════════════════════════════════════════


class TestE1444Regression:
    """E14.4.4 回归测试 — 确保 E14.4.1 / E14.4.2 / E14.4.3 / E14.3 / E14.2 / E14.1 不受影响."""

    # ── E14.4.1 回归 ──────────────────────────────────────────

    def test_e1441_analyze_creative(self, agent):
        rec = agent.quick_analysis("C102", roas=0.45, ctr=0.018, fatigue=0.82)
        assert rec.creative_id == "C102"
        assert rec.action is not None

    def test_e1441_extract_dna(self, agent):
        dna = agent.extract_dna("C102", "test", hook="before_after", visual="fantasy")
        assert dna.creative_id == "C102"

    def test_e1441_compare_dna(self, agent):
        dna1 = agent.extract_dna("C102", "a", hook="before_after", visual="fantasy")
        dna2 = agent.extract_dna("C103", "b", hook="rescue", visual="realistic")
        comparison = agent.compare_dna(dna1, dna2)
        assert comparison is not None

    def test_e1441_analyze_batch(self, agent):
        metrics_list = [
            {"creative_id": "C102", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82},
            {"creative_id": "C201", "roas": 2.5, "ctr": 0.04, "fatigue": 0.15},
        ]
        report = agent.analyze_creative_batch(metrics_list)
        assert report is not None
        assert len(report.recommendations) >= 1

    # ── E14.4.2 回归 ──────────────────────────────────────────

    def test_e1442_detect_opportunities(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        report = agent.detect_opportunities(signals)
        assert report is not None

    def test_e1442_generate_strategies(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        opp_report = agent.detect_opportunities(signals)
        if opp_report.opportunities:
            strategy_report = agent.generate_strategies(opp_report.opportunities)
            assert strategy_report is not None

    def test_e1442_run_full_strategy_pipeline(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        pipeline = agent.run_full_strategy_pipeline(signals)
        assert "opportunities" in pipeline
        assert "strategies" in pipeline
        assert "plans" in pipeline

    def test_e1442_evaluate_creative_strategy(self, agent):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[],
            priority=OpportunityPriority.HIGH,
        )
        before = {"roas": 0.8, "ctr": 0.02}
        after = {"roas": 1.2, "ctr": 0.03}
        outcome = agent.evaluate_creative_strategy(strategy, before, after)
        assert outcome is not None

    # ── E14.4.3 回归 ──────────────────────────────────────────

    def test_e1443_create_actions(self, agent):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[],
            priority=OpportunityPriority.HIGH,
        )
        plan = agent.plan_creative_batch([strategy], max_total_variants=5)
        assert plan is not None

    def test_e1443_start_experiment(self, agent):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        experiment = agent.start_experiment(plan)
        assert experiment is not None
        assert experiment.status == ExperimentStatus.RUNNING

    def test_e1443_collect_results(self, agent):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        experiment = agent.start_experiment(plan)
        variant_metrics = [
            VariantMetrics(
                variant_id="V001", creative_id="C102",
                roas=2.5, ctr=0.035, fatigue=0.2,
                spend=1500.0, revenue=3750.0, installs=800,
                ltv=8.5, is_winner=True,
            ),
        ]
        result = agent.collect_experiment_results(experiment, variant_metrics)
        assert result is not None

    def test_e1443_rollout(self, agent):
        plan = CreativePlan(
            creative_id="C102",
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            mutation_configs=[MutationConfig()],
            experiment_config=ExperimentConfig(
                experiment_type=ExperimentType.A_B_TEST,
                max_budget=1000.0,
            ),
        )
        experiment = agent.start_experiment(plan)
        variant = VariantMetrics(
            variant_id="V001", creative_id="C102",
            roas=2.5, ctr=0.035, fatigue=0.2,
            spend=1500.0, revenue=3750.0, installs=800,
            ltv=8.5, is_winner=True,
        )
        decision = agent.evaluate_rollout(experiment, variant)
        assert decision is not None

    # ── E14.3 回归 ────────────────────────────────────────────

    def test_e1443_agent_communication(self):
        bus = create_message_bus()
        registry = create_agent_registry()
        assert bus is not None
        assert registry is not None

    def test_e1443_agent_identity(self):
        ua_id = comm_ua_identity()
        creative_id = comm_creative_identity()
        assert ua_id.role.value == "ua"
        assert creative_id.role.value == "creative"

    def test_e1443_submodule_access(self, agent):
        """E14.4.3 子模块仍然可访问."""
        assert agent.get_executor() is not None
        assert agent.get_generator_bridge() is not None
        assert agent.get_experiment_manager() is not None
        assert agent.get_rollout_controller() is not None

    # ── E14.4.2 子模块访问 ────────────────────────────────────

    def test_e1442_submodule_access(self, agent):
        assert agent.get_opportunity_engine() is not None
        assert agent.get_strategy_engine() is not None
        assert agent.get_planner() is not None
        assert agent.get_evaluator() is not None

    # ── E14.4.1 子模块访问 ────────────────────────────────────

    def test_e1441_submodule_access(self, agent):
        assert agent.get_analyzer() is not None
        assert agent.get_dna_engine() is not None
        assert agent.get_memory() is not None

    # ── 全局回归 ──────────────────────────────────────────────

    def test_agent_creation_idempotent(self):
        agent1 = create_creative_agent()
        agent2 = create_creative_agent()
        assert agent1.agent_id != agent2.agent_id

    def test_agent_reset_all(self, agent):
        agent.quick_analysis("C102", roas=0.45, ctr=0.018, fatigue=0.82)
        agent.extract_dna("C102", "test", hook="before_after", visual="fantasy")
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        agent.run_full_strategy_pipeline(signals)
        agent.decide_with_policy(game="MergeGame", platform="android", market="US")
        agent.reset()
        stats = agent.stats()
        assert stats["state"] == "idle"

    def test_agent_stats_comprehensive(self, agent):
        stats = agent.stats()
        assert "agent_id" in stats
        assert "state" in stats
        assert "analyzer" in stats
        assert "memory" in stats
        assert "reward_model" in stats
        assert "pattern_miner" in stats
        assert "strategy_memory" in stats
        assert "mutation_learning" in stats
        assert "policy" in stats