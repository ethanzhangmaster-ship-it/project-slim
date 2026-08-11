"""集成测试 — gpt-researcher / pandas-ai / SOP 三项集成.

覆盖:
  1. MarketResearchEngine (gpt-researcher 封装)
  2. MarketIntelligenceAgent.research_market() 注入
  3. DataQueryEngine (pandas-ai 封装)
  4. DataAnalystAgent.ask() 注入
  5. SOPLoader / SOPExecutor / GrowthLoopScheduler SOP 集成
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
# 1. MarketResearchEngine (gpt-researcher)
# ═══════════════════════════════════════════════════════════════

class TestMarketResearchEngine:
    """gpt-researcher 封装测试."""

    def _make_engine(self):
        from src.market_ops.workspace.research_engine import MarketResearchEngine
        return MarketResearchEngine()

    def test_check_status_not_installed(self):
        """gpt-researcher 未安装时返回 not_installed."""
        engine = self._make_engine()
        status = engine.check_status()
        assert status["status"] in ("not_installed", "llm_not_configured", "ready")

    def test_research_empty_query(self):
        """空查询返回错误."""
        engine = self._make_engine()
        result = engine.research("")
        assert not result.success
        assert "空" in result.error

    def test_research_not_installed(self):
        """gpt-researcher 未安装时优雅降级."""
        engine = self._make_engine()
        # 不 patch, 直接调用 — 测试环境未安装会返回 not_installed 错误
        result = engine.research("market trends")
        # 如果 gpt-researcher 安装了但没有 LLM 配置, 也会失败
        if not result.success:
            assert result.error != ""

    def test_research_report_dataclass(self):
        """ResearchReport 数据模型正确."""
        from src.market_ops.workspace.research_engine import (
            ResearchReport,
            ResearchSource,
        )
        report = ResearchReport(
            query="test",
            report_type="research_report",
            content="content here",
            sources=[ResearchSource(url="https://example.com", title="Example")],
        )
        d = report.to_dict()
        assert d["query"] == "test"
        assert d["success"] is True
        assert len(d["sources"]) == 1
        assert d["sources"][0]["url"] == "https://example.com"

    def test_singleton(self):
        """单例正常工作."""
        from src.market_ops.workspace.research_engine import (
            get_market_research_engine,
            reset_market_research_engine,
        )
        reset_market_research_engine()
        e1 = get_market_research_engine()
        e2 = get_market_research_engine()
        assert e1 is e2
        reset_market_research_engine()


# ═══════════════════════════════════════════════════════════════
# 2. MarketIntelligenceAgent 研究引擎注入
# ═══════════════════════════════════════════════════════════════

class TestMarketIntelligenceResearchIntegration:
    """MarketIntelligenceAgent + gpt-researcher 集成."""

    def _make_agent(self, engine=None):
        from src.market_ops.workspace.market_intelligence_agent import (
            MarketIntelligenceAgent,
        )
        return MarketIntelligenceAgent(
            data_dir="data/test_research",
            research_engine=engine,
        )

    def test_set_and_has_research_engine(self):
        """注入和检查研究引擎."""
        agent = self._make_agent()
        assert agent.has_research_engine() is False
        mock = MagicMock()
        agent.set_research_engine(mock)
        assert agent.has_research_engine() is True

    def test_research_market_no_engine(self):
        """无研究引擎时优雅降级."""
        agent = self._make_agent(engine=None)
        # _get_research_engine 会 lazy-load, 但测试环境没有 gpt-researcher
        result = agent.research_market("test query")
        assert result["success"] is False
        assert "不可用" in result["error"] or result["error"] != ""

    def test_research_market_with_mock_engine(self):
        """注入 mock 引擎时正常调用."""
        from src.market_ops.workspace.research_engine import ResearchReport

        mock_engine = MagicMock()
        mock_engine.research.return_value = ResearchReport(
            query="market trends",
            report_type="research_report",
            content="Market is growing 20% YoY",
        )
        agent = self._make_agent(engine=mock_engine)
        result = agent.research_market("market trends")

        assert result["success"] is True
        assert "growing" in result["content"]
        mock_engine.research.assert_called_once()

    def test_research_competitors_with_mock(self):
        """批量竞品研究."""
        from src.market_ops.workspace.research_engine import ResearchReport

        mock_engine = MagicMock()
        mock_engine.research_batch.return_value = [
            ResearchReport(query="comp1", report_type="research_report", content="comp1 report"),
            ResearchReport(query="comp2", report_type="research_report", content="comp2 report"),
        ]
        agent = self._make_agent(engine=mock_engine)
        results = agent.research_competitors(["Game A", "Game B"])

        assert len(results) == 2
        assert results[0]["competitor_name"] == "Game A"
        assert results[1]["competitor_name"] == "Game B"

    def test_list_researches_empty(self):
        """空研究历史."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._make_agent()
            agent.data_dir = tmpdir
            assert agent.list_researches() == []


# ═══════════════════════════════════════════════════════════════
# 3. DataQueryEngine (pandas-ai)
# ═══════════════════════════════════════════════════════════════

class TestDataQueryEngine:
    """pandas-ai 封装测试."""

    def _make_engine(self):
        from src.market_ops.workspace.data_query_engine import DataQueryEngine
        return DataQueryEngine()

    def test_check_status(self):
        """状态检查返回正确字段."""
        engine = self._make_engine()
        status = engine.check_status()
        assert "status" in status
        assert "pandasai_installed" in status
        assert "llm_configured" in status
        assert "setup_guide" in status

    def test_ask_empty_question(self):
        """空问题返回错误."""
        engine = self._make_engine()
        result = engine.ask("", {})
        assert not result.success
        assert "空" in result.error

    def test_ask_no_dataframes(self):
        """无 DataFrame 返回错误."""
        engine = self._make_engine()
        result = engine.ask("what is the revenue?", None)
        # pandas-ai 未安装时会返回 not_installed 错误
        # 如果安装了但没有 LLM 配置, 也会返回错误
        assert not result.success

    def test_query_result_dataclass(self):
        """QueryResult 数据模型正确."""
        from src.market_ops.workspace.data_query_engine import QueryResult
        result = QueryResult(
            question="test",
            answer="42",
            code="df.sum()",
            dataframes_used=["revenue"],
        )
        d = result.to_dict()
        assert d["question"] == "test"
        assert d["answer"] == "42"
        assert d["success"] is True
        assert d["dataframes_used"] == ["revenue"]

    def test_singleton(self):
        """单例正常工作."""
        from src.market_ops.workspace.data_query_engine import (
            get_data_query_engine,
            reset_data_query_engine,
        )
        reset_data_query_engine()
        e1 = get_data_query_engine()
        e2 = get_data_query_engine()
        assert e1 is e2
        reset_data_query_engine()


# ═══════════════════════════════════════════════════════════════
# 4. DataAnalystAgent.ask() 注入
# ═══════════════════════════════════════════════════════════════

class TestDataAnalystAskIntegration:
    """DataAnalystAgent + pandas-ai 集成."""

    def _make_agent(self, engine=None):
        from src.market_ops.workspace.data_analyst_agent import DataAnalystAgent
        return DataAnalystAgent(
            data_dir="data/test_query",
            query_engine=engine,
        )

    def test_set_and_has_query_engine(self):
        """注入和检查查询引擎."""
        agent = self._make_agent()
        assert agent.has_query_engine() is False
        mock = MagicMock()
        agent.set_query_engine(mock)
        assert agent.has_query_engine() is True

    def test_ask_no_engine(self):
        """无查询引擎时优雅降级."""
        agent = self._make_agent(engine=None)
        result = agent.ask("what is DAU?")
        assert result["success"] is False
        assert "不可用" in result["error"] or result["error"] != ""

    def test_ask_with_mock_engine(self):
        """注入 mock 引擎时正常调用."""
        from src.market_ops.workspace.data_query_engine import QueryResult

        mock_engine = MagicMock()
        mock_engine.ask.return_value = QueryResult(
            question="what is DAU?",
            answer="DAU is 10000",
            dataframes_used=["behavior"],
        )
        agent = self._make_agent(engine=mock_engine)

        from src.market_ops.workspace.data_analyst_agent import BehaviorData
        data = BehaviorData(game_id="test")
        result = agent.ask("what is DAU?", data=data)

        assert result["success"] is True
        assert "10000" in result["answer"]
        mock_engine.ask.assert_called_once()

    def test_ask_no_data(self):
        """无数据时返回错误."""
        mock_engine = MagicMock()
        agent = self._make_agent(engine=mock_engine)
        result = agent.ask("question", data=None, extra_dataframes=None)
        assert result["success"] is False
        assert "没有提供数据" in result["error"]


# ═══════════════════════════════════════════════════════════════
# 5. SOP 引擎
# ═══════════════════════════════════════════════════════════════

class TestSOPEngine:
    """SOP 加载器和执行器测试."""

    def _make_sop_yaml(self, tmpdir: Path) -> Path:
        """创建测试用 SOP YAML 文件."""
        yaml_content = """\
name: test_sop
trigger: manual
description: 测试 SOP
steps:
  - agent: MockAgent
    action: step_one
    input:
      query: "$user_query"
    output: step1_result
    timeout: 10
    on_error: skip
  - agent: MockAgent
    action: step_two
    input:
      data: "$step1_result"
    output: final_result
    on_error: abort
fallback_on_error: skip
"""
        sops_dir = tmpdir / "sops"
        sops_dir.mkdir()
        sop_file = sops_dir / "test_sop.yaml"
        sop_file.write_text(yaml_content, encoding="utf-8")
        return sops_dir

    def test_list_sops(self, tmp_path):
        """列出可用 SOP."""
        from src.market_ops.workspace.sop_engine import SOPLoader
        sops_dir = self._make_sop_yaml(tmp_path)
        loader = SOPLoader(sops_dir=str(sops_dir))
        sops = loader.list_sops()
        assert "test_sop" in sops

    def test_load_sop(self, tmp_path):
        """加载 SOP 定义."""
        from src.market_ops.workspace.sop_engine import SOPLoader
        sops_dir = self._make_sop_yaml(tmp_path)
        loader = SOPLoader(sops_dir=str(sops_dir))
        sop = loader.load("test_sop")

        assert sop.name == "test_sop"
        assert sop.trigger == "manual"
        assert len(sop.steps) == 2
        assert sop.steps[0].agent == "MockAgent"
        assert sop.steps[0].action == "step_one"
        assert sop.steps[0].output == "step1_result"
        assert sop.steps[1].on_error == "abort"

    def test_load_not_found(self, tmp_path):
        """加载不存在的 SOP 抛出 FileNotFoundError."""
        from src.market_ops.workspace.sop_engine import SOPLoader
        loader = SOPLoader(sops_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_executor_single_step(self, tmp_path):
        """执行器单步成功."""
        from src.market_ops.workspace.sop_engine import (
            SOPDefinition, SOPStep, SOPExecutor,
        )

        mock_agent = MagicMock()
        mock_agent.step_one.return_value = {"result": "success"}

        sop = SOPDefinition(
            name="test",
            steps=[SOPStep(
                agent="MockAgent",
                action="step_one",
                input={"query": "$user_query"},
                output="result",
            )],
        )
        executor = SOPExecutor(sop, {"MockAgent": mock_agent})
        result = executor.execute(context={"user_query": "hello"})

        assert result.success is True
        assert result.steps_executed == 1
        assert result.steps_succeeded == 1
        assert "result" in result.outputs
        mock_agent.step_one.assert_called_once_with(query="hello")

    def test_executor_multi_step_chain(self, tmp_path):
        """多步骤链式执行 (上一步输出作为下一步输入)."""
        from src.market_ops.workspace.sop_engine import (
            SOPDefinition, SOPStep, SOPExecutor,
        )

        mock_agent = MagicMock()
        mock_agent.step_one.return_value = {"keywords": ["puzzle", "match3"]}
        mock_agent.step_two.return_value = {"report": "done"}

        sop = SOPDefinition(
            name="chain",
            steps=[
                SOPStep(
                    agent="MockAgent",
                    action="step_one",
                    input={"query": "$user_query"},
                    output="step1",
                ),
                SOPStep(
                    agent="MockAgent",
                    action="step_two",
                    input={"data": "$step1"},
                    output="step2",
                ),
            ],
        )
        executor = SOPExecutor(sop, {"MockAgent": mock_agent})
        result = executor.execute(context={"user_query": "trends"})

        assert result.success is True
        assert result.steps_succeeded == 2
        # 第二步接收第一步的输出
        mock_agent.step_two.assert_called_once_with(
            data={"keywords": ["puzzle", "match3"]}
        )

    def test_executor_agent_not_registered(self):
        """agent 未注册时跳过."""
        from src.market_ops.workspace.sop_engine import (
            SOPDefinition, SOPStep, SOPExecutor,
        )

        sop = SOPDefinition(
            name="test",
            steps=[SOPStep(agent="MissingAgent", action="do")],
        )
        executor = SOPExecutor(sop, {})
        result = executor.execute()

        assert result.success is False
        assert len(result.errors) == 1
        assert "未注册" in result.errors[0]

    def test_executor_on_error_abort(self):
        """on_error=abort 时后续步骤不执行."""
        from src.market_ops.workspace.sop_engine import (
            SOPDefinition, SOPStep, SOPExecutor,
        )

        mock_agent = MagicMock()
        mock_agent.failing_step.side_effect = RuntimeError("boom")

        sop = SOPDefinition(
            name="test",
            steps=[
                SOPStep(agent="A", action="failing_step", on_error="abort"),
                SOPStep(agent="A", action="next_step"),
            ],
            fallback_on_error="skip",
        )
        executor = SOPExecutor(sop, {"A": mock_agent})
        result = executor.execute()

        assert result.steps_executed == 1  # 只执行了第一步
        assert result.steps_succeeded == 0
        mock_agent.next_step.assert_not_called()

    def test_executor_with_retry(self):
        """retry 后成功."""
        from src.market_ops.workspace.sop_engine import (
            SOPDefinition, SOPStep, SOPExecutor,
        )

        mock_agent = MagicMock()
        mock_agent.flaky.side_effect = [
            RuntimeError("fail 1"),
            RuntimeError("fail 2"),
            "success",
        ]

        sop = SOPDefinition(
            name="test",
            steps=[SOPStep(
                agent="A", action="flaky",
                retry=3, on_error="skip",
            )],
        )
        executor = SOPExecutor(sop, {"A": mock_agent})
        result = executor.execute()

        assert result.steps_succeeded == 1
        assert mock_agent.flaky.call_count == 3

    def test_variable_resolution_nested(self):
        """嵌套变量解析 $var.field."""
        from src.market_ops.workspace.sop_engine import SOPExecutor

        resolved = SOPExecutor._resolve_value(
            "$data.keywords",
            {"data": {"keywords": ["a", "b"]}},
        )
        assert resolved == ["a", "b"]

    def test_variable_resolution_string_interpolation(self):
        """字符串插值 ${var}."""
        from src.market_ops.workspace.sop_engine import SOPExecutor

        resolved = SOPExecutor._resolve_string(
            "query: ${user_query} in ${region}",
            {"user_query": "trends", "region": "US"},
        )
        assert resolved == "query: trends in US"


# ═══════════════════════════════════════════════════════════════
# 6. GrowthLoopScheduler SOP 集成
# ═══════════════════════════════════════════════════════════════

class TestGrowthLoopSchedulerSOP:
    """GrowthLoopScheduler SOP 方法测试."""

    def _make_scheduler(self, tmp_path):
        from src.market_ops.workspace.growth_loop_scheduler import (
            GrowthLoopScheduler,
        )
        return GrowthLoopScheduler(
            data_dir=str(tmp_path / "growth_loop"),
            project_root=str(tmp_path),
        )

    def test_list_sops_empty(self, tmp_path):
        """空 SOP 目录返回空列表."""
        scheduler = self._make_scheduler(tmp_path)
        assert scheduler.list_sops() == []

    def test_list_sops_with_file(self, tmp_path):
        """有 SOP 文件时返回名称列表."""
        sops_dir = tmp_path / "sops"
        sops_dir.mkdir()
        (sops_dir / "my_sop.yaml").write_text(
            "name: my_sop\nsteps: []\n", encoding="utf-8"
        )
        scheduler = self._make_scheduler(tmp_path)
        sops = scheduler.list_sops()
        assert "my_sop" in sops

    def test_load_sop(self, tmp_path):
        """加载 SOP 定义."""
        sops_dir = tmp_path / "sops"
        sops_dir.mkdir()
        (sops_dir / "test.yaml").write_text(
            "name: test\ndescription: test sop\nsteps:\n"
            "  - agent: A\n    action: do\n    output: result\n",
            encoding="utf-8",
        )
        scheduler = self._make_scheduler(tmp_path)
        sop = scheduler.load_sop("test")
        assert sop["name"] == "test"
        assert len(sop["steps"]) == 1
        assert sop["steps"][0]["agent"] == "A"

    def test_run_sop_with_mock_agents(self, tmp_path):
        """用 mock agent 执行 SOP."""
        sops_dir = tmp_path / "sops"
        sops_dir.mkdir()
        (sops_dir / "test_flow.yaml").write_text(
            "name: test_flow\nsteps:\n"
            "  - agent: MockAgent\n    action: do_something\n"
            "    input:\n      q: \"$query\"\n    output: result\n",
            encoding="utf-8",
        )

        mock_agent = MagicMock()
        mock_agent.do_something.return_value = {"done": True}

        scheduler = self._make_scheduler(tmp_path)
        result = scheduler.run_sop(
            "test_flow",
            context={"query": "hello"},
            agent_registry={"MockAgent": mock_agent},
        )

        assert result["success"] is True
        assert result["steps_succeeded"] == 1
        assert "result" in result["outputs"]
        mock_agent.do_something.assert_called_once_with(q="hello")
