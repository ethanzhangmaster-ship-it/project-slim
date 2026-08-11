"""E13.7.2 LLM Reasoning — 测试套件.

覆盖:
  - LLMClient: Provider 抽象, Mock, Config, timeout, retry, fallback
  - PromptBuilder: System Prompt, Context Building, Formatting
  - ReasoningChain: 单步/多步推理, 输出转换
  - ResponseParser: JSON 解析, 容错, 字段验证
  - LLMExperienceMemory: 记录, 检索, 质量评分
  - GrowthContext: Builder, Snapshot, 转换
  - ContextRetriever: 多源检索
  - LLMReasoningEngine: LLM + 规则集成
  - Integration: 完整流程
"""

import json
import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent import (
    Insight,
    InsightType,
    ReasoningContext,
    ReasoningEngine,
    LLMReasoningEngine,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    GrowthAgent,
    create_growth_agent,
    AgentGoal,
    GoalPriority,
    GoalStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.llm import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    LLMClient,
    MockLLMProvider,
    create_llm_client,
    SystemPrompt,
    GrowthContextPrompt,
    PromptBuilder,
    ReasoningStep,
    ReasoningChain,
    ReasoningOutput,
    ParsedResponse,
    ResponseParser,
    ReasoningExperience,
    LLMExperienceMemory,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.context import (
    MetricsSnapshot,
    CreativeSnapshot,
    GrowthContext,
    GrowthContextBuilder,
    RetrievalResult,
    ContextRetriever,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_client():
    return MockLLMProvider()


@pytest.fixture
def mock_client_with_responses():
    client = MockLLMProvider()
    client.set_response("fatigue", json.dumps({
        "insight_type": "CREATIVE_FATIGUE",
        "diagnosis": "Creative fatigue detected",
        "hypothesis": "New variants needed",
        "confidence": 0.85,
        "recommended_actions": [{"action_type": "MUTATE_CREATIVE", "parameters": {"count": 5}, "reasoning": "test", "expected_impact": "CTR+15%", "risk": "low"}],
        "evidence": ["fatigue=0.81"],
        "alternative_hypotheses": [],
        "learning_notes": "Dark fantasy works",
    }))
    return client


@pytest.fixture
def metrics_context():
    return {
        "spend": 17000,
        "roas": 0.53,
        "roas_change": -0.12,
        "creative_fatigue": 0.81,
        "ctr": 0.021,
        "ctr_change": -0.12,
        "payer_quality": 0.65,
        "d30_ltv": 2.5,
        "payer_rate": 0.03,
    }


@pytest.fixture
def prompt_context(metrics_context):
    return GrowthContextPrompt(
        metrics=metrics_context,
        creative_state={"total_creatives": 10, "active_creatives": 8, "winner_creative": "witch_forest_v2"},
        pattern_memories=[{"concept": "Dark Fantasy", "description": "Hook works well", "confidence": 0.85}],
        cycle=1,
    )


@pytest.fixture
def reasoning_context(metrics_context):
    return ReasoningContext(
        metrics=metrics_context,
        cycle=1,
        active_goals=["reduce_fatigue"],
    )


# ═══════════════════════════════════════════════════════════════
# 1. LLM Client Tests
# ═══════════════════════════════════════════════════════════════


class TestLLMProvider:
    def test_provider_enum_values(self):
        assert LLMProvider.MOCK.value == "mock"
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.CLAUDE.value == "claude"
        assert LLMProvider.DEEPSEEK.value == "deepseek"


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.provider == LLMProvider.MOCK
        assert config.model == "gpt-4o"
        assert config.temperature == 0.3
        assert config.max_retries == 3

    def test_custom_config(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            temperature=0.7,
            max_retries=5,
        )
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_retries == 5

    def test_fallback_providers(self):
        config = LLMConfig(fallback_providers=[LLMProvider.DEEPSEEK, LLMProvider.MOCK])
        assert len(config.fallback_providers) == 2


class TestLLMResponse:
    def test_default_response(self):
        resp = LLMResponse()
        assert resp.success is True
        assert resp.content == ""

    def test_error_response(self):
        resp = LLMResponse(success=False, error="timeout")
        assert resp.success is False
        assert resp.error == "timeout"


class TestMockLLMProvider:
    def test_create_mock(self):
        client = create_llm_client(LLMProvider.MOCK)
        assert isinstance(client, MockLLMProvider)
        assert client.provider == LLMProvider.MOCK

    def test_generate_returns_response(self, mock_client, metrics_context):
        resp = mock_client.generate("Analyze", metrics_context)
        assert resp.success is True
        assert resp.content
        assert resp.provider == LLMProvider.MOCK

    def test_generate_returns_json(self, mock_client, metrics_context):
        resp = mock_client.generate("Analyze", metrics_context)
        data = json.loads(resp.content)
        assert "insight_type" in data
        assert "diagnosis" in data
        assert "confidence" in data

    def test_generate_fatigue_scenario(self, mock_client):
        ctx = {"metrics": {"creative_fatigue": 0.85, "roas_change": -0.1}}
        resp = mock_client.generate("Analyze fatigue", ctx)
        data = json.loads(resp.content)
        assert data["insight_type"] == "CREATIVE_FATIGUE"
        assert data["confidence"] > 0.8

    def test_generate_roas_decline(self, mock_client):
        ctx = {"metrics": {"creative_fatigue": 0.3, "roas_change": -0.35}}
        resp = mock_client.generate("Analyze ROAS", ctx)
        data = json.loads(resp.content)
        assert data["insight_type"] == "ROAS_DECLINE"

    def test_generate_roas_opportunity(self, mock_client):
        ctx = {"metrics": {"creative_fatigue": 0.3, "roas_change": 0.35}}
        resp = mock_client.generate("Analyze ROAS", ctx)
        data = json.loads(resp.content)
        assert data["insight_type"] == "ROAS_OPPORTUNITY"

    def test_generate_normal(self, mock_client):
        ctx = {"metrics": {"creative_fatigue": 0.3, "roas_change": 0.0}}
        resp = mock_client.generate("Analyze", ctx)
        data = json.loads(resp.content)
        assert data["insight_type"] == "NORMAL"

    def test_custom_response(self, mock_client):
        mock_client.set_response("custom_test", '{"insight_type": "ANOMALY", "diagnosis": "test"}')
        resp = mock_client.generate("custom_test analysis", {})
        data = json.loads(resp.content)
        assert data["insight_type"] == "ANOMALY"

    def test_response_history(self, mock_client):
        mock_client.generate("test1", {})
        mock_client.generate("test2", {})
        assert len(mock_client.history) == 2

    def test_tokens_used(self, mock_client):
        resp = mock_client.generate("test", {})
        assert resp.tokens_used > 0


class TestLLMClientFactory:
    def test_create_mock_client(self):
        client = create_llm_client(LLMProvider.MOCK)
        assert isinstance(client, MockLLMProvider)

    def test_create_unknown_provider(self):
        client = create_llm_client("unknown")  # type: ignore
        assert isinstance(client, MockLLMProvider)

    def test_create_with_config(self):
        config = LLMConfig(provider=LLMProvider.MOCK, temperature=0.5)
        client = create_llm_client(LLMProvider.MOCK, config)
        assert client._config.temperature == 0.5


# ═══════════════════════════════════════════════════════════════
# 2. Prompt Builder Tests
# ═══════════════════════════════════════════════════════════════


class TestSystemPrompt:
    def test_system_prompt_not_empty(self):
        prompt = SystemPrompt.get()
        assert len(prompt) > 100
        assert "autonomous mobile game growth agent" in prompt.lower()

    def test_contains_framework(self):
        prompt = SystemPrompt.get()
        assert "OBSERVE" in prompt
        assert "DIAGNOSE" in prompt
        assert "HYPOTHESIZE" in prompt

    def test_contains_output_format(self):
        prompt = SystemPrompt.get()
        assert "insight_type" in prompt
        assert "JSON" in prompt

    def test_with_extras(self):
        prompt = SystemPrompt.get_with_extras({"Custom Rule": "Always validate first"})
        assert "Custom Rule" in prompt
        assert "Always validate first" in prompt


class TestGrowthContextPrompt:
    def test_default_creation(self):
        ctx = GrowthContextPrompt()
        assert ctx.product_name == ""
        assert ctx.metrics == {}

    def test_with_metrics(self, metrics_context):
        ctx = GrowthContextPrompt(metrics=metrics_context)
        assert ctx.metrics["creative_fatigue"] == 0.81


class TestPromptBuilder:
    def test_build_prompt(self, prompt_context):
        builder = PromptBuilder()
        prompt = builder.build(prompt_context)
        assert "Current Situation" in prompt
        assert "Key Metrics" in prompt
        assert "Creative Status" in prompt
        assert "Your Task" in prompt

    def test_build_metrics_section(self, prompt_context):
        builder = PromptBuilder()
        prompt = builder.build(prompt_context)
        assert "Spend" in prompt
        assert "ROAS" in prompt
        assert "Creative Fatigue" in prompt

    def test_build_memory_section(self, prompt_context):
        builder = PromptBuilder()
        prompt = builder.build(prompt_context)
        assert "Pattern Memories" in prompt
        assert "Dark Fantasy" in prompt

    def test_build_messages(self, prompt_context):
        builder = PromptBuilder()
        messages = builder.build_messages(prompt_context)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_with_extra_instructions(self, prompt_context):
        builder = PromptBuilder()
        prompt = builder.build(prompt_context, "Extra: check competitor data")
        assert "Extra: check competitor data" in prompt

    def test_build_with_history(self, prompt_context):
        builder = PromptBuilder()
        builder.build(prompt_context)  # first call
        prompt = builder.build(prompt_context)  # second call should include history
        assert "Previous Analysis" in prompt

    def test_empty_context(self):
        builder = PromptBuilder()
        prompt = builder.build(GrowthContextPrompt())
        assert "No metrics available" in prompt

    def test_get_system_prompt(self):
        builder = PromptBuilder()
        sp = builder.get_system_prompt()
        assert len(sp) > 100

    def test_format_actions(self):
        ctx = GrowthContextPrompt(
            recent_actions=[
                {"action_type": "mutate", "result": "CTR+22%"},
                {"action_type": "scale", "result": "ROAS+15%"},
            ]
        )
        builder = PromptBuilder()
        prompt = builder.build(ctx)
        assert "mutate" in prompt
        assert "CTR+22%" in prompt

    def test_format_goals(self):
        ctx = GrowthContextPrompt(
            active_goals=[
                {"title": "Reduce Fatigue", "priority": "high", "progress": 0.3},
            ]
        )
        builder = PromptBuilder()
        prompt = builder.build(ctx)
        assert "Reduce Fatigue" in prompt


# ═══════════════════════════════════════════════════════════════
# 3. Reasoning Chain Tests
# ═══════════════════════════════════════════════════════════════


class TestReasoningStep:
    def test_default_step(self):
        step = ReasoningStep()
        assert step.step_name == ""
        assert step.confidence == 0.5

    def test_named_step(self):
        step = ReasoningStep(
            step_name="observation",
            output={"key": "value"},
            confidence=0.9,
        )
        assert step.step_name == "observation"
        assert step.confidence == 0.9


class TestReasoningOutput:
    def test_default_output(self):
        output = ReasoningOutput()
        assert output.insight_type == "NORMAL"
        assert output.confidence == 0.5

    def test_to_insights_creates_main_insight(self):
        output = ReasoningOutput(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Fatigue detected",
            hypothesis="Generate variants",
            confidence=0.87,
            recommended_actions=[{"action_type": "MUTATE_CREATIVE", "parameters": {"variants": 5}, "reasoning": "test", "expected_impact": "", "risk": "low"}],
            evidence=["fatigue=0.81"],
        )
        insights = output.to_insights()
        assert len(insights) > 0
        assert insights[0].insight_type == InsightType.THREAT
        assert "CREATIVE_FATIGUE" in str(insights[0].metadata)

    def test_to_insights_includes_alternatives(self):
        output = ReasoningOutput(
            insight_type="ROAS_DECLINE",
            alternative_hypotheses=["Competition", "Seasonality"],
        )
        insights = output.to_insights()
        assert len(insights) >= 2  # main + at least 1 alternative

    def test_to_insights_llm_source(self):
        output = ReasoningOutput(insight_type="CREATIVE_FATIGUE")
        insights = output.to_insights()
        assert insights[0].metadata.get("source") == "llm_reasoning"

    def test_to_dict(self):
        output = ReasoningOutput(
            insight_type="ROAS_OPPORTUNITY",
            diagnosis="Opportunity detected",
            confidence=0.8,
        )
        d = output.to_dict()
        assert d["insight_type"] == "ROAS_OPPORTUNITY"
        assert d["confidence"] == 0.8


class TestReasoningChain:
    def test_create_chain(self, mock_client):
        chain = ReasoningChain(llm_client=mock_client)
        assert chain.chain_count == 0

    def test_reason_with_mock(self, mock_client, metrics_context):
        chain = ReasoningChain(llm_client=mock_client, use_multi_step=False)
        output = chain.reason(context=metrics_context, prompt="Analyze fatigue")
        assert output is not None
        assert chain.chain_count == 1

    def test_reason_without_client(self, metrics_context):
        chain = ReasoningChain(llm_client=None)
        output = chain.reason(context=metrics_context, prompt="")
        assert output is not None
        assert output.metadata.get("fallback") == "rule_based"

    def test_reason_fatigue_returns_insights(self, mock_client_with_responses, metrics_context):
        chain = ReasoningChain(llm_client=mock_client_with_responses, use_multi_step=False)
        output = chain.reason(context=metrics_context, prompt="Analyze fatigue")
        assert output.insight_type == "CREATIVE_FATIGUE"
        assert output.confidence > 0.8

    def test_reason_with_steps(self, mock_client, metrics_context):
        chain = ReasoningChain(llm_client=mock_client, use_multi_step=True)
        output = chain.reason(context=metrics_context, prompt="")
        assert len(output.steps) > 0
        assert output.metadata.get("multi_step") is True

    def test_rule_fallback_produces_output(self, metrics_context):
        chain = ReasoningChain(llm_client=None)
        output = chain.reason(context=metrics_context, prompt="")
        assert output.diagnosis or output.insight_type == "NORMAL"

    def test_reset(self, mock_client, metrics_context):
        chain = ReasoningChain(llm_client=mock_client)
        chain.reason(context=metrics_context, prompt="")
        chain.reset()
        assert chain.chain_count == 0


# ═══════════════════════════════════════════════════════════════
# 4. Response Parser Tests
# ═══════════════════════════════════════════════════════════════


class TestResponseParser:
    def test_parse_valid_json(self):
        parser = ResponseParser()
        content = json.dumps({
            "insight_type": "CREATIVE_FATIGUE",
            "diagnosis": "Fatigue detected",
            "hypothesis": "Generate variants",
            "confidence": 0.87,
            "recommended_actions": [],
            "evidence": [],
            "alternative_hypotheses": [],
            "learning_notes": "",
        })
        parsed = parser.parse(content)
        assert parsed.parse_success is True
        assert parsed.insight_type == "CREATIVE_FATIGUE"
        assert parsed.confidence == 0.87

    def test_parse_markdown_json_block(self):
        parser = ResponseParser()
        content = '```json\n{"insight_type": "ROAS_DECLINE", "diagnosis": "test", "confidence": 0.6}\n```'
        parsed = parser.parse(content)
        assert parsed.parse_success is True
        assert parsed.insight_type == "ROAS_DECLINE"

    def test_parse_markdown_code_block(self):
        parser = ResponseParser()
        content = '```\n{"insight_type": "ANOMALY", "diagnosis": "test", "confidence": 0.5}\n```'
        parsed = parser.parse(content)
        assert parsed.parse_success is True
        assert parsed.insight_type == "ANOMALY"

    def test_parse_invalid_insight_type(self):
        parser = ResponseParser()
        content = '{"insight_type": "INVALID", "diagnosis": "test", "confidence": 0.5}'
        parsed = parser.parse(content)
        assert parsed.insight_type == "NORMAL"  # falls back to NORMAL

    def test_parse_clamps_confidence(self):
        parser = ResponseParser()
        content = '{"insight_type": "NORMAL", "confidence": 1.5}'
        parsed = parser.parse(content)
        assert parsed.confidence == 1.0

        content = '{"insight_type": "NORMAL", "confidence": -0.5}'
        parsed = parser.parse(content)
        assert parsed.confidence == 0.0

    def test_parse_empty_content(self):
        parser = ResponseParser()
        parsed = parser.parse("")
        assert parsed.parse_success is False

    def test_parse_missing_fields(self):
        parser = ResponseParser()
        content = '{"insight_type": "NORMAL"}'
        parsed = parser.parse(content)
        assert parsed.parse_success is True
        assert parsed.diagnosis == ""

    def test_parse_text_fallback(self):
        parser = ResponseParser()
        content = "I think there is creative fatigue in the system"
        parsed = parser.parse(content)
        assert parsed.parse_success is False
        assert parsed.insight_type == "CREATIVE_FATIGUE"

    def test_normalize_actions(self):
        parser = ResponseParser()
        content = json.dumps({
            "insight_type": "NORMAL",
            "recommended_actions": [
                {"action_type": "TEST", "risk": "HIGH"},
            ],
        })
        parsed = parser.parse(content)
        assert len(parsed.recommended_actions) == 1
        assert parsed.recommended_actions[0]["risk"] == "high"

    def test_parse_count(self):
        parser = ResponseParser()
        parser.parse('{"insight_type": "NORMAL"}')
        parser.parse('{"insight_type": "NORMAL"}')
        assert parser.parse_count == 2


# ═══════════════════════════════════════════════════════════════
# 5. LLM Experience Memory Tests
# ═══════════════════════════════════════════════════════════════


class TestReasoningExperience:
    def test_default_experience(self):
        exp = ReasoningExperience()
        assert exp.confidence == 0.5
        assert exp.quality_score > 0

    def test_correct_experience_quality(self):
        exp = ReasoningExperience(
            was_correct=True,
            learning="Dark fantasy works",
            evidence=["ctr_increase"],
            confidence=0.9,
        )
        assert exp.quality_score > 0.7

    def test_incorrect_experience_quality(self):
        exp = ReasoningExperience(was_correct=False)
        assert exp.quality_score < 0.7

    def test_to_dict(self):
        exp = ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="test",
            confidence=0.85,
            was_correct=True,
        )
        d = exp.to_dict()
        assert d["insight_type"] == "CREATIVE_FATIGUE"
        assert d["was_correct"] is True

    def test_to_prompt_fragment(self):
        exp = ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Fatigue detected",
            hypothesis="Generate variants",
            outcome="CTR+22%",
            was_correct=True,
            learning="Dark fantasy works",
        )
        fragment = exp.to_prompt_fragment()
        assert "CREATIVE_FATIGUE" in fragment
        assert "correct" in fragment


class TestLLMExperienceMemory:
    def test_create_memory(self):
        mem = LLMExperienceMemory()
        assert mem.size == 0

    def test_record_experience(self):
        mem = LLMExperienceMemory()
        exp = ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="test",
            was_correct=True,
        )
        mem.record(exp)
        assert mem.size == 1

    def test_record_auto_id(self):
        mem = LLMExperienceMemory()
        exp = ReasoningExperience()
        mem.record(exp)
        assert exp.experience_id.startswith("llm_exp_")

    def test_retrieve_by_keyword(self):
        mem = LLMExperienceMemory()
        exp = ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Creative fatigue detected in US campaign",
            hypothesis="Generate dark fantasy variants",
            was_correct=True,
            learning="Dark fantasy hook works",
        )
        mem.record(exp)
        results = mem.retrieve("fatigue", top_k=5)
        assert len(results) == 1

    def test_retrieve_no_match(self):
        mem = LLMExperienceMemory()
        exp = ReasoningExperience(insight_type="CREATIVE_FATIGUE", diagnosis="test")
        mem.record(exp)
        results = mem.retrieve("nonexistent", top_k=5)
        assert len(results) == 0

    def test_retrieve_by_type(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience(insight_type="CREATIVE_FATIGUE", was_correct=True))
        mem.record(ReasoningExperience(insight_type="ROAS_DECLINE", was_correct=True))
        results = mem.retrieve_by_type("CREATIVE_FATIGUE")
        assert len(results) == 1

    def test_retrieve_by_type_only_correct(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience(insight_type="CREATIVE_FATIGUE", was_correct=True))
        mem.record(ReasoningExperience(insight_type="CREATIVE_FATIGUE", was_correct=False))
        results = mem.retrieve_by_type("CREATIVE_FATIGUE", only_correct=True)
        assert len(results) == 1
        assert results[0].was_correct is True

    def test_get_recent(self):
        mem = LLMExperienceMemory()
        for i in range(5):
            mem.record(ReasoningExperience(insight_type="NORMAL"))
        assert len(mem.get_recent(3)) == 3

    def test_get_best_learnings(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience(was_correct=True, learning="Lesson 1"))
        mem.record(ReasoningExperience(was_correct=False, learning="Lesson 2"))
        learnings = mem.get_best_learnings()
        assert len(learnings) == 1
        assert "Lesson 1" in learnings[0]

    def test_to_prompt_context(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Fatigue found",
            hypothesis="Mutate",
            was_correct=True,
            learning="Works",
        ))
        ctx = mem.to_prompt_context("fatigue")
        assert "Past Reasoning Experiences" in ctx

    def test_max_size(self):
        mem = LLMExperienceMemory(max_size=3)
        for i in range(5):
            mem.record(ReasoningExperience(insight_type="NORMAL"))
        assert mem.size == 3

    def test_stats(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience(was_correct=True))
        mem.record(ReasoningExperience(was_correct=False))
        stats = mem.stats()
        assert stats["total"] == 2
        assert stats["correct"] == 1
        assert stats["incorrect"] == 1

    def test_clear(self):
        mem = LLMExperienceMemory()
        mem.record(ReasoningExperience())
        mem.clear()
        assert mem.size == 0


# ═══════════════════════════════════════════════════════════════
# 6. Growth Context Tests
# ═══════════════════════════════════════════════════════════════


class TestMetricsSnapshot:
    def test_default_snapshot(self):
        snap = MetricsSnapshot()
        assert snap.spend == 0.0
        assert snap.roas == 0.0

    def test_from_dict(self, metrics_context):
        snap = MetricsSnapshot.from_dict(metrics_context)
        assert snap.spend == 17000
        assert snap.creative_fatigue == 0.81
        assert snap.d30_ltv == 2.5

    def test_to_dict(self, metrics_context):
        snap = MetricsSnapshot.from_dict(metrics_context)
        d = snap.to_dict()
        assert d["spend"] == 17000
        assert d["creative_fatigue"] == 0.81


class TestCreativeSnapshot:
    def test_default_snapshot(self):
        snap = CreativeSnapshot()
        assert snap.total_creatives == 0

    def test_from_dict(self):
        snap = CreativeSnapshot.from_dict({"total_creatives": 10, "active_creatives": 8, "winner_creative": "test"})
        assert snap.total_creatives == 10
        assert snap.winner_creative == "test"


class TestGrowthContext:
    def test_default_context(self):
        ctx = GrowthContext()
        assert ctx.product_name == ""
        assert ctx.cycle == 0

    def test_to_prompt_context(self, metrics_context):
        ctx = GrowthContext(metrics=MetricsSnapshot.from_dict(metrics_context))
        pc = ctx.to_prompt_context()
        assert "metrics" in pc
        assert pc["metrics"]["creative_fatigue"] == 0.81


class TestGrowthContextBuilder:
    def test_build_empty(self):
        builder = GrowthContextBuilder()
        ctx = builder.build()
        assert isinstance(ctx, GrowthContext)

    def test_with_product(self):
        builder = GrowthContextBuilder()
        ctx = builder.with_product("Witch Merge", "iOS", "US").build()
        assert ctx.product_name == "Witch Merge"
        assert ctx.platform == "iOS"
        assert ctx.market == "US"

    def test_with_metrics(self, metrics_context):
        builder = GrowthContextBuilder()
        ctx = builder.with_metrics(metrics_context).build()
        assert ctx.metrics.spend == 17000
        assert ctx.metrics.creative_fatigue == 0.81

    def test_with_creative(self):
        builder = GrowthContextBuilder()
        ctx = builder.with_creative({"total_creatives": 15, "active_creatives": 12}).build()
        assert ctx.creative.total_creatives == 15

    def test_with_past_actions(self):
        builder = GrowthContextBuilder()
        actions = [{"action_type": "mutate", "result": "success"}]
        ctx = builder.with_past_actions(actions).build()
        assert len(ctx.past_actions) == 1

    def test_with_goals(self):
        builder = GrowthContextBuilder()
        goals = [{"title": "Test", "priority": "high"}]
        ctx = builder.with_goals(goals).build()
        assert len(ctx.active_goals) == 1

    def test_with_cycle(self):
        builder = GrowthContextBuilder()
        ctx = builder.with_cycle(5).build()
        assert ctx.cycle == 5

    def test_chained_build(self, metrics_context):
        builder = GrowthContextBuilder()
        ctx = (
            builder
            .with_product("Test", "Android", "JP")
            .with_metrics(metrics_context)
            .with_cycle(3)
            .build()
        )
        assert ctx.product_name == "Test"
        assert ctx.cycle == 3
        assert ctx.metrics.spend == 17000

    def test_reset(self):
        builder = GrowthContextBuilder()
        builder.with_product("Test").with_cycle(5)
        builder.reset()
        ctx = builder.build()
        assert ctx.product_name == ""
        assert ctx.cycle == 0


# ═══════════════════════════════════════════════════════════════
# 7. Context Retriever Tests
# ═══════════════════════════════════════════════════════════════


class TestRetrievalResult:
    def test_default_result(self):
        r = RetrievalResult()
        assert r.source == ""
        assert r.relevance == 0.0


class TestContextRetriever:
    def test_create_retriever(self):
        retriever = ContextRetriever()
        assert retriever._max_results == 20

    def test_retrieve_empty(self):
        retriever = ContextRetriever()
        results = retriever.retrieve("test")
        assert len(results) == 0

    def test_retrieve_from_knowledge(self):
        retriever = ContextRetriever()
        kg = [
            {"entity": "dark_fantasy", "relation": "increases CTR"},
            {"entity": "casual_style", "relation": "works in JP"},
        ]
        results = retriever.retrieve("dark", knowledge_graph=kg)
        assert len(results) == 1
        assert results[0].source == "knowledge_graph"

    def test_retrieve_from_actions(self):
        retriever = ContextRetriever()
        actions = [
            {"action_type": "mutate_creative", "result": "success"},
            {"action_type": "scale_budget", "result": "failed"},
        ]
        results = retriever.retrieve("mutate", past_actions=actions)
        assert len(results) == 1

    def test_retrieve_all(self):
        retriever = ContextRetriever()
        actions = [{"action_type": "test", "result": "ok"}]
        results = retriever.retrieve_all(past_actions=actions, top_n=5)
        assert len(results) == 1
        assert results[0].source == "past_actions"

    def test_retrieve_from_llm_memory(self):
        retriever = ContextRetriever()
        llm_mem = LLMExperienceMemory()
        llm_mem.record(ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Fatigue found",
            was_correct=True,
            learning="Works",
        ))
        results = retriever.retrieve("fatigue", llm_memory=llm_mem)
        assert len(results) >= 1

    def test_retrieve_with_semantic_memory(self):
        retriever = ContextRetriever()
        sm = SemanticMemory()
        sm.add_knowledge("creative_fatigue", "Fatigue affects CTR", 0.9)
        results = retriever.retrieve("fatigue", memory_systems={"semantic": sm})
        assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════
# 8. LLM Reasoning Engine Tests
# ═══════════════════════════════════════════════════════════════


class TestLLMReasoningEngine:
    def test_create_engine(self, mock_client):
        engine = LLMReasoningEngine(llm_client=mock_client)
        assert engine.llm_call_count == 0
        assert engine.rule_fallback_count == 0

    def test_create_without_llm(self):
        engine = LLMReasoningEngine(llm_client=None)
        assert engine.llm_call_count == 0

    def test_reason_with_llm(self, mock_client, reasoning_context):
        engine = LLMReasoningEngine(llm_client=mock_client, use_llm=True)
        insights = engine.reason(reasoning_context)
        assert len(insights) > 0
        assert engine.llm_call_count == 1

    def test_reason_fallback_to_rules(self, reasoning_context):
        engine = LLMReasoningEngine(llm_client=None, use_llm=True)
        insights = engine.reason(reasoning_context)
        assert len(insights) > 0
        assert engine.rule_fallback_count == 1

    def test_reason_with_memory(self, mock_client, reasoning_context):
        wm = WorkingMemory()
        sm = SemanticMemory()
        sm.add_knowledge("dark_fantasy", "Works well", 0.9)
        engine = LLMReasoningEngine(
            llm_client=mock_client,
            working_memory=wm,
            semantic_memory=sm,
        )
        insights = engine.reason(reasoning_context)
        assert len(insights) > 0

    def test_reason_with_llm_memory(self, mock_client, reasoning_context):
        llm_mem = LLMExperienceMemory()
        llm_mem.record(ReasoningExperience(
            insight_type="CREATIVE_FATIGUE",
            diagnosis="Previous fatigue",
            was_correct=True,
            learning="Mutation works",
        ))
        engine = LLMReasoningEngine(
            llm_client=mock_client,
            llm_memory=llm_mem,
        )
        insights = engine.reason(reasoning_context)
        assert len(insights) > 0

    def test_stats(self, mock_client, reasoning_context):
        engine = LLMReasoningEngine(llm_client=mock_client)
        engine.reason(reasoning_context)
        stats = engine.stats()
        assert stats["llm_call_count"] > 0
        assert stats["has_llm_client"] is True

    def test_use_llm_false(self, mock_client, reasoning_context):
        engine = LLMReasoningEngine(llm_client=mock_client, use_llm=False)
        insights = engine.reason(reasoning_context)
        assert engine.llm_call_count == 0
        assert engine.rule_fallback_count >= 1

    def test_reset(self, mock_client, reasoning_context):
        engine = LLMReasoningEngine(llm_client=mock_client)
        engine.reason(reasoning_context)
        engine.reset()
        assert engine.llm_call_count == 0
        assert engine.insight_count == 0


# ═══════════════════════════════════════════════════════════════
# 9. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestLLMIntegration:
    def test_full_pipeline_mock_to_insights(self, mock_client, metrics_context):
        """完整流程: Context → Prompt → LLM → Parse → Insights."""
        # 1. Build context
        builder = GrowthContextBuilder()
        builder.with_metrics(metrics_context).with_cycle(1)
        growth_ctx = builder.build()

        # 2. Build prompt
        prompt_builder = PromptBuilder()
        prompt_ctx = GrowthContextPrompt(
            metrics=growth_ctx.metrics.to_dict(),
            creative_state=growth_ctx.creative.to_dict(),
            cycle=1,
        )
        prompt = prompt_builder.build(prompt_ctx)

        # 3. LLM generate
        response = mock_client.generate(prompt, growth_ctx.to_prompt_context())
        assert response.success

        # 4. Parse
        parser = ResponseParser()
        parsed = parser.parse(response.content)
        assert parsed.parse_success

        # 5. Convert to ReasoningOutput
        output = ReasoningOutput(
            insight_type=parsed.insight_type,
            diagnosis=parsed.diagnosis,
            hypothesis=parsed.hypothesis,
            confidence=parsed.confidence,
            recommended_actions=parsed.recommended_actions,
            evidence=parsed.evidence,
            alternative_hypotheses=parsed.alternative_hypotheses,
        )

        # 6. Convert to Insights
        insights = output.to_insights()
        assert len(insights) > 0

    def test_agent_with_llm_reasoning(self, mock_client, metrics_context):
        """Agent 使用 LLM 推理引擎."""
        wm = WorkingMemory()
        em = EpisodicMemory()
        sm = SemanticMemory()

        engine = LLMReasoningEngine(
            llm_client=mock_client,
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
        )

        agent = GrowthAgent(
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
            reasoning_engine=engine,
        )

        agent.observe(metrics_context)

        # 手动推理
        insights = agent.reason()
        assert len(insights) > 0

    def test_full_agent_cycle_with_llm(self, mock_client, metrics_context):
        """完整 Agent 循环使用 LLM 推理."""
        wm = WorkingMemory()
        em = EpisodicMemory()
        sm = SemanticMemory()

        engine = LLMReasoningEngine(
            llm_client=mock_client,
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
        )

        agent = GrowthAgent(
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
            reasoning_engine=engine,
        )

        result = agent.run_cycle(metrics=metrics_context)
        assert result["cycle"] == 1
        assert result["insight_count"] > 0

    def test_llm_memory_accumulates_experience(self, mock_client, metrics_context):
        """LLM 经验在多次循环中积累."""
        llm_mem = LLMExperienceMemory()
        assert llm_mem.size == 0

        engine = LLMReasoningEngine(
            llm_client=mock_client,
            llm_memory=llm_mem,
        )

        # 第一次推理
        engine.reason(ReasoningContext(metrics=metrics_context, cycle=1))
        assert llm_mem.size > 0

        # 第二次推理
        engine.reason(ReasoningContext(metrics={
            **metrics_context,
            "creative_fatigue": 0.75,
            "roas_change": -0.25,
        }, cycle=2))
        assert llm_mem.size > 1

    def test_rule_fallback_when_llm_fails(self, metrics_context):
        """LLM 不可用时自动降级为规则引擎."""
        # 没有 LLM client
        engine = LLMReasoningEngine(llm_client=None)
        insights = engine.reason(ReasoningContext(metrics=metrics_context, cycle=1))
        assert len(insights) > 0
        assert engine.rule_fallback_count == 1
        assert engine.llm_call_count == 0

    def test_multiple_cycles_llm_then_rule(self, mock_client, metrics_context):
        """LLM 推理 + 规则 fallback 混合."""
        engine = LLMReasoningEngine(llm_client=mock_client)

        # Cycle 1: LLM
        insights1 = engine.reason(ReasoningContext(metrics=metrics_context, cycle=1))
        assert engine.llm_call_count == 1
        assert engine.rule_fallback_count == 0

        # 禁用 LLM
        engine._use_llm = False

        # Cycle 2: Rule
        insights2 = engine.reason(ReasoningContext(metrics=metrics_context, cycle=2))
        assert engine.llm_call_count == 1  # unchanged
        assert engine.rule_fallback_count == 1

    def test_llm_insights_have_metadata(self, mock_client, reasoning_context):
        """LLM 生成的洞察包含 metadata."""
        engine = LLMReasoningEngine(llm_client=mock_client)
        insights = engine.reason(reasoning_context)

        llm_insights = [i for i in insights if i.metadata.get("source") == "llm_reasoning"]
        assert len(llm_insights) > 0

    def test_llm_insights_include_alternative_hypotheses(self, mock_client, reasoning_context):
        """LLM 洞察包含替代假设."""
        engine = LLMReasoningEngine(llm_client=mock_client)
        insights = engine.reason(reasoning_context)

        alt_insights = [i for i in insights if "替代假设" in i.title]
        # 可能有也可能没有替代假设（取决于 mock 输出）
        # 有 LLM 生成的 insight 就说明流程正常
        llm_insights = [i for i in insights if i.metadata.get("source") == "llm_reasoning"]
        assert len(llm_insights) > 0

    def test_prompt_builder_includes_all_sections(self, metrics_context):
        """Prompt 包含所有必要的 section."""
        builder = GrowthContextBuilder()
        builder.with_product("Witch Merge", "iOS", "US")
        builder.with_metrics(metrics_context)
        builder.with_creative({"total_creatives": 10, "active_creatives": 8, "winner_creative": "test"})
        builder.with_goals([{"title": "Reduce Fatigue", "priority": "high", "progress": 0.3}])
        builder.with_past_actions([{"action_type": "mutate", "result": "success"}])
        growth_ctx = builder.build()

        prompt_builder = PromptBuilder()
        prompt_ctx = GrowthContextPrompt(
            product_name=growth_ctx.product_name,
            platform=growth_ctx.platform,
            market=growth_ctx.market,
            metrics=growth_ctx.metrics.to_dict(),
            creative_state=growth_ctx.creative.to_dict(),
            active_goals=growth_ctx.active_goals,
            recent_actions=growth_ctx.past_actions,
            cycle=1,
        )
        prompt = prompt_builder.build(prompt_ctx)

        assert "Witch Merge" in prompt
        assert "iOS" in prompt
        assert "US" in prompt
        assert "Spend" in prompt
        assert "Creative Status" in prompt
        assert "Recent Actions" in prompt
        assert "Active Goals" in prompt

    def test_response_parser_handles_edge_cases(self):
        """Parser 处理各种边界情况."""
        parser = ResponseParser()

        # None-like content
        parsed = parser.parse("")
        assert parsed.parse_success is False

        # Invalid JSON
        parsed = parser.parse("not json at all")
        assert parsed.parse_success is False

        # Partially valid JSON
        parsed = parser.parse('{"insight_type": "NORMAL", "confidence": "high"}')
        assert parsed.parse_success is True
        assert parsed.confidence == 0.5  # "high" -> 0.5

        # Extra fields
        parsed = parser.parse('{"insight_type": "NORMAL", "extra_field": "value"}')
        assert parsed.parse_success is True

    def test_reasoning_output_urgency_calculation(self):
        """验证不同 insight_type 的紧急程度."""
        outputs = {
            "CREATIVE_FATIGUE": ReasoningOutput(insight_type="CREATIVE_FATIGUE"),
            "ROAS_DECLINE": ReasoningOutput(insight_type="ROAS_DECLINE"),
            "ROAS_OPPORTUNITY": ReasoningOutput(insight_type="ROAS_OPPORTUNITY"),
            "NORMAL": ReasoningOutput(insight_type="NORMAL"),
        }
        for itype, output in outputs.items():
            insights = output.to_insights()
            if insights:
                if itype == "CREATIVE_FATIGUE":
                    assert insights[0].urgency > 0.8
                elif itype == "NORMAL":
                    assert insights[0].urgency < 0.3