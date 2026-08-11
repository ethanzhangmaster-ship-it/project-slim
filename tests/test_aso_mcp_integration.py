"""ASO MCP 集成单元测试.

测试覆盖:
  1. ASOMcpClient — MCP stdio 协议客户端 (mock 子进程)
  2. ASOKeywordResearcher — 高层关键词研究接口
  3. KeywordMetric / KeywordResearchResult 数据模型
  4. API 端点
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from fastapi.testclient import TestClient

# 确保项目根在 path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.aso_mcp_client import (
    ASOMcpClient,
    ASOMcpError,
    ASOMcpNotInstalledError,
    ASOMcpTimeoutError,
    ASOMcpToolError,
)
from src.market_ops.workspace.aso_keyword_researcher import (
    ASOKeywordResearcher,
    KeywordMetric,
    KeywordResearchResult,
    get_aso_keyword_researcher,
    reset_aso_keyword_researcher,
)


# ── 数据模型测试 ──────────────────────────────────────────────

class TestKeywordMetric:
    """KeywordMetric 数据模型."""

    def test_to_dict(self):
        m = KeywordMetric(
            keyword="meditation",
            popularity=85,
            difficulty_score=45.5,
            min_difficulty_score=30.0,
            is_brand_keyword=False,
        )
        d = m.to_dict()
        assert d["keyword"] == "meditation"
        assert d["popularity"] == 85
        assert d["difficulty_score"] == 45.5
        assert d["is_brand_keyword"] is False

    def test_defaults(self):
        m = KeywordMetric(keyword="test")
        assert m.popularity == 0
        assert m.difficulty_score == 0.0
        assert m.is_brand_keyword is False


class TestKeywordResearchResult:
    """KeywordResearchResult 数据模型."""

    def test_empty_result(self):
        r = KeywordResearchResult()
        assert r.success is True
        assert r.total_researched == 0

    def test_with_error(self):
        r = KeywordResearchResult(error="some error")
        assert r.success is False
        assert r.error == "some error"

    def test_with_items(self):
        r = KeywordResearchResult(
            items=[KeywordMetric(keyword="a"), KeywordMetric(keyword="b")],
            failed_keywords=["c"],
            filtered_out=["d"],
        )
        assert r.total_researched == 4
        assert r.success is True

    def test_to_dict(self):
        r = KeywordResearchResult(
            items=[KeywordMetric(keyword="a", popularity=50)],
            failed_keywords=["b"],
        )
        d = r.to_dict()
        assert d["success"] is True
        assert len(d["items"]) == 1
        assert d["items"][0]["keyword"] == "a"
        assert d["failed_keywords"] == ["b"]
        assert d["total_researched"] == 2


# ── ASOMcpClient 测试 ────────────────────────────────────────

class TestASOMcpClientAvailability:
    """ASOMcpClient 静态方法测试."""

    def test_is_available_returns_bool(self):
        result = ASOMcpClient.is_available()
        assert isinstance(result, bool)

    def test_is_authenticated_returns_bool(self):
        result = ASOMcpClient.is_authenticated()
        assert isinstance(result, bool)


class TestASOMcpClientProtocol:
    """ASOMcpClient MCP 协议测试 (mock 子进程)."""

    def test_not_installed_raises(self):
        """aso-mcp 未安装时应抛出 ASOMcpNotInstalledError."""
        client = ASOMcpClient(command="nonexistent-aso-mcp-12345")
        with patch("shutil.which", return_value=None):
            with pytest.raises(ASOMcpNotInstalledError, match="未找到"):
                client.start()

    def test_call_tool_without_init_raises(self):
        """未初始化时调用工具应抛出异常."""
        client = ASOMcpClient(command="aso-mcp")
        with pytest.raises(ASOMcpError, match="未初始化"):
            client.call_tool("test", {})

    def test_list_tools_without_init_raises(self):
        """未初始化时列出工具应抛出异常."""
        client = ASOMcpClient(command="aso-mcp")
        with pytest.raises(ASOMcpError, match="未初始化"):
            client.list_tools()

    def test_close_when_not_started(self):
        """未启动时 close 不应抛异常."""
        client = ASOMcpClient(command="aso-mcp")
        client.close()  # 不应抛异常

    def test_context_manager_close(self):
        """上下文管理器退出时应关闭."""
        client = ASOMcpClient(command="aso-mcp")
        # 手动标记为已启动以测试 close 路径
        mock_proc = MagicMock()
        client._process = mock_proc
        mock_proc.poll.return_value = None
        client.close()
        mock_proc.terminate.assert_called_once()


class TestASOMcpClientSendReceive:
    """ASOMcpClient 消息收发测试 (mock stdin/stdout)."""

    def _create_mock_client(self):
        """创建带 mock 进程的客户端."""
        client = ASOMcpClient(command="aso-mcp")
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.poll.return_value = None
        client._process = mock_proc
        return client, mock_proc

    def test_write_message(self):
        client, proc = self._create_mock_client()
        client._write_message({"jsonrpc": "2.0", "method": "test"})
        proc.stdin.write.assert_called_once()
        written = proc.stdin.write.call_args[0][0]
        assert '"method":"test"' in written or '"method": "test"' in written
        assert written.endswith("\n")

    def test_send_request_increments_id(self):
        client, proc = self._create_mock_client()

        # mock stdout 返回匹配的响应
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}) + "\n",
        ]
        proc.stdout.readline = MagicMock(side_effect=responses)

        result = client._send_request("test_method")
        assert result == {"ok": True}

    def test_send_request_error_response(self):
        client, proc = self._create_mock_client()

        error_response = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"}
        }) + "\n"
        proc.stdout.readline = MagicMock(return_value=error_response)

        with pytest.raises(ASOMcpToolError, match="Invalid request"):
            client._send_request("test")

    def test_send_request_timeout(self):
        client, proc = self._create_mock_client()
        client._timeout = 0.1  # 100ms 超时

        # readline 永不返回 (模拟阻塞)
        import time
        proc.stdout.readline = MagicMock(side_effect=lambda: time.sleep(1) or "")

        with pytest.raises(ASOMcpTimeoutError):
            client._send_request("test")

    def test_read_response_skips_notifications(self):
        """应跳过没有 id 的通知消息."""
        client, proc = self._create_mock_client()

        responses = [
            json.dumps({"jsonrpc": "2.0", "method": "notifications/progress"}) + "\n",
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"data": "ok"}}) + "\n",
        ]
        proc.stdout.readline = MagicMock(side_effect=responses)

        result = client._read_response(1)
        assert result == {"data": "ok"}

    def test_read_response_skips_non_json(self):
        """应跳过非 JSON 行."""
        client, proc = self._create_mock_client()

        responses = [
            "Some log message\n",
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}) + "\n",
        ]
        proc.stdout.readline = MagicMock(side_effect=responses)

        result = client._read_response(1)
        assert result == {}

    def test_send_notification(self):
        client, proc = self._create_mock_client()
        client._send_notification("notifications/initialized")
        proc.stdin.write.assert_called_once()
        written = proc.stdin.write.call_args[0][0]
        assert "notifications/initialized" in written

    def test_call_tool_extracts_text_content(self):
        """call_tool 应从 content 数组中提取文本并解析 JSON."""
        client, proc = self._create_mock_client()
        client._initialized = True

        tool_result = {
            "content": [
                {"type": "text", "text": json.dumps({"items": [{"keyword": "test", "popularity": 50}]})}
            ]
        }
        response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": tool_result}) + "\n"
        proc.stdout.readline = MagicMock(return_value=response)

        result = client.call_tool("aso_evaluate_keywords", {"keywords": "test"})
        assert isinstance(result, dict)
        assert "items" in result
        assert result["items"][0]["keyword"] == "test"

    def test_call_tool_returns_string_for_non_json(self):
        """非 JSON 文本应原样返回字符串."""
        client, proc = self._create_mock_client()
        client._initialized = True

        tool_result = {
            "content": [
                {"type": "text", "text": "plain text result"}
            ]
        }
        response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": tool_result}) + "\n"
        proc.stdout.readline = MagicMock(return_value=response)

        result = client.call_tool("test", {})
        assert result == "plain text result"


# ── ASOKeywordResearcher 测试 ────────────────────────────────

class TestASOKeywordResearcherStatus:
    """ASOKeywordResearcher 状态检查."""

    def test_check_status_returns_dict(self):
        researcher = ASOKeywordResearcher()
        with patch("src.market_ops.workspace.aso_mcp_client.ASOMcpClient.is_available", return_value=False), \
             patch("src.market_ops.workspace.aso_mcp_client.ASOMcpClient.is_authenticated", return_value=False), \
             patch("shutil.which", return_value=None):
            status = researcher.check_status()
        assert "status" in status
        assert "cli_installed" in status
        assert "setup_guide" in status

    def test_check_status_not_installed(self):
        researcher = ASOKeywordResearcher()
        with patch("shutil.which", return_value=None):
            status = researcher.check_status()
        assert status["status"] == "not_installed"
        assert "npm install" in status["setup_guide"]

    def test_check_status_ready(self):
        researcher = ASOKeywordResearcher()
        with patch("shutil.which", return_value="/usr/bin/aso"), \
             patch("src.market_ops.workspace.aso_mcp_client.ASOMcpClient.is_available", return_value=True), \
             patch("src.market_ops.workspace.aso_mcp_client.ASOMcpClient.is_authenticated", return_value=True):
            status = researcher.check_status()
        assert status["status"] == "ready"


class TestASOKeywordResearcherResearch:
    """ASOKeywordResearcher 关键词研究."""

    def test_empty_keywords(self):
        researcher = ASOKeywordResearcher()
        result = researcher.research_keywords([])
        assert result.error == "关键词列表为空"
        assert not result.success

    def test_not_installed_error(self):
        researcher = ASOKeywordResearcher()
        with patch("src.market_ops.workspace.aso_mcp_client.ASOMcpClient.is_available", return_value=False), \
             patch("shutil.which", return_value=None):
            result = researcher.research_keywords(["meditation"])
        assert not result.success
        assert "未安装" in result.error or "not" in result.error.lower()

    def test_successful_research(self):
        """mock MCP 客户端返回成功结果."""
        researcher = ASOKeywordResearcher()

        mock_mcp_result = {
            "items": [
                {"keyword": "meditation", "popularity": 85, "difficultyScore": 45.5, "isBrandKeyword": False},
                {"keyword": "sleep sounds", "popularity": 72, "difficultyScore": 38.0, "isBrandKeyword": False},
            ],
            "failedKeywords": [],
            "filteredOut": [],
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.call_tool = MagicMock(return_value=mock_mcp_result)

        with patch("src.market_ops.workspace.aso_keyword_researcher.ASOMcpClient", return_value=mock_client):
            result = researcher.research_keywords(["meditation", "sleep sounds"])

        assert result.success
        assert len(result.items) == 2
        assert result.items[0].keyword == "meditation"
        assert result.items[0].popularity == 85
        assert result.items[1].keyword == "sleep sounds"
        assert result.items[1].difficulty_score == 38.0

    def test_research_with_failed_keywords(self):
        """部分关键词失败的场景."""
        researcher = ASOKeywordResearcher()

        mock_mcp_result = {
            "items": [
                {"keyword": "meditation", "popularity": 85, "difficultyScore": 45.0},
            ],
            "failedKeywords": ["invalid!@#"],
            "filteredOut": ["low_volume_word"],
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.call_tool = MagicMock(return_value=mock_mcp_result)

        with patch("src.market_ops.workspace.aso_keyword_researcher.ASOMcpClient", return_value=mock_client):
            result = researcher.research_keywords(["meditation", "invalid!@#", "low_volume_word"])

        assert result.success
        assert len(result.items) == 1
        assert result.failed_keywords == ["invalid!@#"]
        assert result.filtered_out == ["low_volume_word"]
        assert result.total_researched == 3

    def test_research_tool_error(self):
        """工具调用返回错误."""
        researcher = ASOKeywordResearcher()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.call_tool = MagicMock(side_effect=ASOMcpToolError("API error", error_code="500"))

        with patch("src.market_ops.workspace.aso_keyword_researcher.ASOMcpClient", return_value=mock_client):
            result = researcher.research_keywords(["test"])

        assert not result.success
        assert "API error" in result.error

    def test_research_single(self):
        """单个关键词研究."""
        researcher = ASOKeywordResearcher()

        mock_mcp_result = {
            "items": [
                {"keyword": "meditation", "popularity": 85, "difficultyScore": 45.0},
            ],
            "failedKeywords": [],
            "filteredOut": [],
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.call_tool = MagicMock(return_value=mock_mcp_result)

        with patch("src.market_ops.workspace.aso_keyword_researcher.ASOMcpClient", return_value=mock_client):
            result = researcher.research_single("meditation")

        assert result.success
        assert len(result.items) == 1
        assert result.items[0].keyword == "meditation"

    def test_parse_result_string(self):
        """测试字符串结果解析."""
        json_str = json.dumps({
            "items": [{"keyword": "test", "popularity": 50}],
            "failedKeywords": [],
            "filteredOut": [],
        })
        result = ASOKeywordResearcher._parse_result(json_str)
        assert result.success
        assert len(result.items) == 1
        assert result.items[0].keyword == "test"

    def test_parse_result_with_error(self):
        """测试带错误的返回解析."""
        result = ASOKeywordResearcher._parse_result({
            "error": {"message": "Not authenticated", "code": "AUTH_001"}
        })
        assert not result.success
        assert "Not authenticated" in result.error

    def test_parse_result_invalid_type(self):
        """测试无效类型返回."""
        result = ASOKeywordResearcher._parse_result(12345)
        assert not result.success
        assert "格式异常" in result.error


# ── 单例测试 ──────────────────────────────────────────────────

class TestSingleton:
    """单例工厂测试."""

    def test_get_singleton(self):
        reset_aso_keyword_researcher()
        r1 = get_aso_keyword_researcher()
        r2 = get_aso_keyword_researcher()
        assert r1 is r2

    def test_reset(self):
        reset_aso_keyword_researcher()
        r1 = get_aso_keyword_researcher()
        reset_aso_keyword_researcher()
        r2 = get_aso_keyword_researcher()
        assert r1 is not r2


# ── API 端点测试 ──────────────────────────────────────────────

class TestAPIEndpoints:
    """ASO API 端点测试."""

    @pytest.fixture
    def client(self):
        reset_aso_keyword_researcher()
        from src.market_ops.workspace.app import app
        yield TestClient(app)
        reset_aso_keyword_researcher()

    def test_aso_status_endpoint(self, client):
        resp = client.get("/api/aso/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "cli_installed" in data
        assert "setup_guide" in data

    def test_aso_keywords_research_endpoint(self, client):
        """测试关键词研究端点 (aso-mcp 未安装时应返回错误)."""
        resp = client.post("/api/aso/keywords/research", json={
            "keywords": ["meditation", "sleep"],
        })
        assert resp.status_code == 200
        data = resp.json()
        # aso-mcp 未安装时应有 error
        assert "error" in data or "items" in data

    def test_aso_keywords_research_with_string_input(self, client):
        """测试逗号分隔字符串输入."""
        resp = client.post("/api/aso/keywords/research", json={
            "keywords": "meditation,sleep,relax",
        })
        assert resp.status_code == 200

    def test_aso_keywords_research_empty(self, client):
        """空关键词列表."""
        resp = client.post("/api/aso/keywords/research", json={
            "keywords": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "关键词列表为空"

    def test_aso_keywords_research_single_endpoint(self, client):
        resp = client.post("/api/aso/keywords/research-single", json={
            "keyword": "meditation",
        })
        assert resp.status_code == 200

    def test_aso_keywords_research_single_empty(self, client):
        resp = client.post("/api/aso/keywords/research-single", json={
            "keyword": "",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


# ── ASOKeywordAgent.collect_reality 集成测试 ──────────────────

class TestAgentCollectRealityIntegration:
    """ASO 集成点注入到 ASOKeywordAgent.collect_reality 中."""

    def _make_agent(self, researcher=None, **kwargs):
        from src.aso_intelligence.keyword.agent import ASOKeywordAgent
        agent = ASOKeywordAgent(
            keyword_researcher=researcher,
            **kwargs,
        )
        return agent

    def _make_reality(self, keyword, **overrides):
        from src.aso_intelligence.keyword.models import KeywordReality
        data = dict(
            keyword=keyword,
            country="US",
            category="",
            search_volume=0,
            competition=0.5,
            date="2026-01-01",
        )
        data.update(overrides)
        return KeywordReality(**data)

    # ------------------------------------------------------------ #
    # 1. 优雅降级: 无研究器时直通
    # ------------------------------------------------------------ #
    def test_no_researcher_passthrough(self):
        agent = self._make_agent(researcher=None)
        r1 = self._make_reality("puzzle game")
        r2 = self._make_reality("match 3")
        result = agent.collect_reality([r1, r2])
        assert [r.keyword for r in result] == ["puzzle game", "match 3"]
        # 没有 enrichment 时 search_volume 保持为 0
        assert result[0].search_volume == 0
        assert result[1].search_volume == 0

    # ------------------------------------------------------------ #
    # 2. enrich_with_asa=False 时关闭 enrichment
    # ------------------------------------------------------------ #
    def test_disable_enrichment_flag(self):
        mock_researcher = MagicMock()
        agent = self._make_agent(
            researcher=mock_researcher,
            enrich_with_asa=False,
        )
        r1 = self._make_reality("puzzle game")
        result = agent.collect_reality([r1])
        assert result[0].search_volume == 0
        mock_researcher.research_keywords.assert_not_called()

    # ------------------------------------------------------------ #
    # 3. 研究失败时直通 (不抛异常)
    # ------------------------------------------------------------ #
    def test_researcher_exception_passthrough(self):
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.side_effect = RuntimeError(
            "boom"
        )
        agent = self._make_agent(researcher=mock_researcher)
        r1 = self._make_reality("puzzle game")
        result = agent.collect_reality([r1])
        assert len(result) == 1
        assert result[0].keyword == "puzzle game"

    # ------------------------------------------------------------ #
    # 4. 研究返回 success=False 时直通
    # ------------------------------------------------------------ #
    def test_researcher_result_not_success(self):
        bad_result = KeywordResearchResult(
            error="auth failed",
            items=[],
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = bad_result
        agent = self._make_agent(researcher=mock_researcher)
        r1 = self._make_reality("puzzle game")
        result = agent.collect_reality([r1])
        assert len(result) == 1
        assert result[0].search_volume == 0

    # ------------------------------------------------------------ #
    # 5. 正常 enrichment: 更新已有关键词的 search_volume/competition
    # ------------------------------------------------------------ #
    def test_enrich_existing_keyword_fields(self):
        result_items = [
            KeywordMetric(
                keyword="puzzle game",
                popularity=70,
                difficulty_score=60.0,
                is_brand_keyword=False,
            ),
        ]
        good_result = KeywordResearchResult(
            error="",
            items=result_items,
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = good_result
        agent = self._make_agent(researcher=mock_researcher)

        r1 = self._make_reality("puzzle game")
        enriched = agent.collect_reality([r1])

        assert len(enriched) == 1
        # popularity=70 * 1000 = 70000
        assert enriched[0].search_volume == 70_000
        # difficulty=60.0 / 100 = 0.6
        assert enriched[0].competition == 0.6
        assert enriched[0].category == ""

    # ------------------------------------------------------------ #
    # 6. 品牌关键词被打上 category="brand"
    # ------------------------------------------------------------ #
    def test_brand_keyword_category(self):
        result_items = [
            KeywordMetric(
                keyword="Candy Crush",
                popularity=90,
                difficulty_score=95.0,
                is_brand_keyword=True,
            ),
        ]
        good_result = KeywordResearchResult(
            error="",
            items=result_items,
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = good_result
        agent = self._make_agent(researcher=mock_researcher)

        r1 = self._make_reality("Candy Crush")
        enriched = agent.collect_reality([r1])
        assert enriched[0].category == "brand"

    # ------------------------------------------------------------ #
    # 7. 已经有 search_volume 的不会被覆盖
    # ------------------------------------------------------------ #
    def test_existing_volume_not_overwritten(self):
        result_items = [
            KeywordMetric(
                keyword="puzzle game",
                popularity=70,
                difficulty_score=60.0,
                is_brand_keyword=False,
            ),
        ]
        good_result = KeywordResearchResult(
            error="",
            items=result_items,
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = good_result
        agent = self._make_agent(researcher=mock_researcher)

        r1 = self._make_reality("puzzle game", search_volume=12345)
        enriched = agent.collect_reality([r1])
        # 原有值保留
        assert enriched[0].search_volume == 12345

    # ------------------------------------------------------------ #
    # 8. 研究器返回的新关键词会追加到结果末尾
    # ------------------------------------------------------------ #
    def test_new_keywords_appended(self):
        researcher_items = [
            KeywordMetric(
                keyword="puzzle game",
                popularity=70,
                difficulty_score=60.0,
                is_brand_keyword=False,
            ),
            KeywordMetric(
                keyword="brain teaser",
                popularity=55,
                difficulty_score=40.0,
                is_brand_keyword=False,
            ),
        ]
        good_result = KeywordResearchResult(
            error="",
            items=researcher_items,
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = good_result
        agent = self._make_agent(researcher=mock_researcher)

        r1 = self._make_reality("puzzle game")
        enriched = agent.collect_reality([r1])

        keywords = [r.keyword for r in enriched]
        assert keywords == ["puzzle game", "brain teaser"]

        # 新的 brain teaser 字段被正确构建
        new_r = enriched[1]
        assert new_r.search_volume == 55_000
        assert new_r.competition == 0.4
        assert new_r.country == "US"
        assert new_r.date == "2026-01-01"

    # ------------------------------------------------------------ #
    # 9. 空 realities 直通
    # ------------------------------------------------------------ #
    def test_empty_realities(self):
        mock_researcher = MagicMock()
        agent = self._make_agent(researcher=mock_researcher)
        result = agent.collect_reality([])
        assert result == []
        mock_researcher.research_keywords.assert_not_called()

    # ------------------------------------------------------------ #
    # 10. 注入接口 / has_researcher 检查
    # ------------------------------------------------------------ #
    def test_set_and_has_researcher(self):
        agent = self._make_agent(researcher=None)
        assert agent.has_keyword_researcher() is False

        mock = MagicMock()
        agent.set_keyword_researcher(mock)
        assert agent.has_keyword_researcher() is True

    # ------------------------------------------------------------ #
    # 11. agent.run() 整体链路: collect_reality → score → portfolio
    # ------------------------------------------------------------ #
    def test_run_pipeline_with_researcher(self):
        researcher_items = [
            KeywordMetric(
                keyword="puzzle game",
                popularity=80,
                difficulty_score=50.0,
                is_brand_keyword=False,
            ),
            KeywordMetric(
                keyword="match 3",
                popularity=65,
                difficulty_score=70.0,
                is_brand_keyword=False,
            ),
        ]
        good_result = KeywordResearchResult(
            error="",
            items=researcher_items,
            failed_keywords=[],
            filtered_out=[],
        )
        mock_researcher = MagicMock()
        mock_researcher.research_keywords.return_value = good_result
        agent = self._make_agent(researcher=mock_researcher)

        r1 = self._make_reality("puzzle game")
        r2 = self._make_reality("match 3")

        report = agent.run(
            game_id="casual_merge_witch",
            realities=[r1, r2],
        )

        assert report.game_id == "casual_merge_witch"
        assert len(report.keyword_scores) == 2
        # enrichment 让 reality 有了 search_volume → 评分应该是非零
        vol_sum = sum(r.search_volume for r in [r1, r2])
        assert vol_sum == 80_000 + 65_000


# ── 模块级 helper 测试 ────────────────────────────────────────

class TestModuleHelpers:
    """enrich_reality / build_new_reality 单元测试."""

    def _make_reality(self, **overrides):
        from src.aso_intelligence.keyword.models import KeywordReality
        data = dict(
            keyword="game",
            country="US",
            category="",
            search_volume=0,
            competition=0.5,
            date="2026-01-01",
        )
        data.update(overrides)
        return KeywordReality(**data)

    def test_enrich_reality_updates_volume_and_competition(self):
        from src.aso_intelligence.keyword.agent import enrich_reality
        metric = KeywordMetric(
            keyword="game",
            popularity=50,
            difficulty_score=80.0,
            is_brand_keyword=False,
        )
        reality = self._make_reality()
        enrich_reality(reality, metric)
        assert reality.search_volume == 50_000
        assert reality.competition == 0.8

    def test_enrich_reality_preserves_existing_volume(self):
        from src.aso_intelligence.keyword.agent import enrich_reality
        metric = KeywordMetric(
            keyword="game",
            popularity=50,
            difficulty_score=80.0,
            is_brand_keyword=False,
        )
        reality = self._make_reality(search_volume=10_000)
        enrich_reality(reality, metric)
        assert reality.search_volume == 10_000

    def test_enrich_reality_sets_brand_category(self):
        from src.aso_intelligence.keyword.agent import enrich_reality
        metric = KeywordMetric(
            keyword="Candy Crush",
            popularity=50,
            difficulty_score=80.0,
            is_brand_keyword=True,
        )
        reality = self._make_reality(keyword="Candy Crush")
        enrich_reality(reality, metric)
        assert reality.category == "brand"

    def test_build_new_reality(self):
        from src.aso_intelligence.keyword.agent import build_new_reality
        metric = KeywordMetric(
            keyword="brain training",
            popularity=60,
            difficulty_score=55.0,
            is_brand_keyword=False,
        )
        reality = build_new_reality(metric, country="GB", date="2026-06-01")
        assert reality.keyword == "brain training"
        assert reality.country == "GB"
        assert reality.date == "2026-06-01"
        assert reality.search_volume == 60_000
        assert reality.competition == 0.55
        assert reality.category == ""

    def test_build_new_reality_brand(self):
        from src.aso_intelligence.keyword.agent import build_new_reality
        metric = KeywordMetric(
            keyword="Disney",
            popularity=100,
            difficulty_score=100.0,
            is_brand_keyword=True,
        )
        reality = build_new_reality(metric, country="US", date="2026-01-01")
        assert reality.category == "brand"
        assert reality.search_volume == 100_000
        assert reality.competition == 1.0
