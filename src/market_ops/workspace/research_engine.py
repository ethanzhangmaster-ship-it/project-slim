"""市场研究引擎 — 封装 gpt-researcher 的 Plan-and-Solve 研究能力.

gpt-researcher 架构:
  1. Planner: 将查询拆解为多个子问题
  2. Execution Agents: 并行抓取多来源信息
  3. Aggregator: 聚合为带引用的研究报告

集成点:
  - MarketIntelligenceAgent.research_market() 注入此引擎
  - workspace/app.py API 端点直接调用
  - 研究结果写入 experiment_memory 供下游 agent 复用

设计原则:
  - 优雅降级: gpt-researcher 未安装时返回 not_available, 不阻断主流程
  - 同步接口: 内部用 asyncio.run 包装 async 调用, 对外暴露同步 API
  - 结果结构化: 返回 ResearchReport dataclass, 不返回原始字符串

用法:
  engine = MarketResearchEngine()
  status = engine.check_status()
  if status["status"] == "ready":
      report = engine.research("2026 休闲合并类游戏市场趋势")
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_DEFAULT_REPORT_TYPE = "research_report"
_DEFAULT_MAX_SUB_QUERIES = 4
_DEFAULT_TIMEOUT = 120  # 秒


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class ResearchSource:
    """研究来源 — 单条信息来源."""

    url: str = ""
    title: str = ""
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
        }


@dataclass
class ResearchReport:
    """市场研究报告 — gpt-researcher 输出的结构化结果."""

    query: str
    report_type: str
    content: str                           # 完整报告 markdown
    sources: List[ResearchSource] = field(default_factory=list)
    sub_queries: List[str] = field(default_factory=list)
    cost: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "report_type": self.report_type,
            "content": self.content,
            "sources": [s.to_dict() for s in self.sources],
            "sub_queries": self.sub_queries,
            "cost": self.cost,
            "success": self.success,
            "error": self.error,
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }


# ── 研究引擎 ──────────────────────────────────────────────────

class MarketResearchEngine:
    """市场研究引擎 — 封装 gpt-researcher.

    线程安全: 单实例可并发调用 (内部每次创建新 GPTResearcher).
    """

    def __init__(
        self,
        report_type: str = _DEFAULT_REPORT_TYPE,
        max_sub_queries: int = _DEFAULT_MAX_SUB_QUERIES,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._report_type = report_type
        self._max_sub_queries = max_sub_queries
        self._timeout = timeout
        self._lock = threading.Lock()

    # ── 状态检查 ──

    def check_status(self) -> Dict[str, Any]:
        """检查 gpt-researcher 安装和 LLM 配置状态."""
        try:
            import gpt_researcher  # noqa: F401
            gpt_installed = True
        except ImportError:
            gpt_installed = False

        # 检查 LLM 配置 (gpt-researcher 依赖 OPENAI_API_KEY 或 Tavily API key)
        import os
        llm_configured = bool(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        retriever_configured = bool(
            os.getenv("TAVILY_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        if not gpt_installed:
            status = "not_installed"
        elif not llm_configured:
            status = "llm_not_configured"
        elif not retriever_configured:
            status = "retriever_not_configured"
        else:
            status = "ready"

        return {
            "status": status,
            "gpt_researcher_installed": gpt_installed,
            "llm_configured": llm_configured,
            "retriever_configured": retriever_configured,
            "setup_guide": self._get_setup_guide(status),
        }

    @staticmethod
    def _get_setup_guide(status: str) -> str:
        guides = {
            "not_installed": "安装: pip install gpt-researcher",
            "llm_not_configured": "配置 LLM: 设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 环境变量",
            "retriever_not_configured": "配置检索器: 设置 TAVILY_API_KEY 或 GOOGLE_API_KEY 环境变量",
            "ready": "gpt-researcher 已就绪",
        }
        return guides.get(status, "未知状态")

    # ── 研究接口 ──

    def research(
        self,
        query: str,
        report_type: Optional[str] = None,
    ) -> ResearchReport:
        """执行市场研究 — Plan-and-Solve 架构.

        Args:
            query: 研究查询 (如 "2026 休闲合并类游戏市场趋势")
            report_type: 报告类型 (research_report / summary_report / resource_report)
                         默认使用构造时的 report_type

        Returns:
            ResearchReport 包含完整报告内容、来源和子查询
        """
        if not query.strip():
            return ResearchReport(
                query=query,
                report_type=report_type or self._report_type,
                content="",
                error="查询不能为空",
            )

        try:
            import gpt_researcher
        except ImportError:
            return ResearchReport(
                query=query,
                report_type=report_type or self._report_type,
                content="",
                error="gpt-researcher 未安装. 请运行: pip install gpt-researcher",
            )

        rt = report_type or self._report_type

        try:
            return self._run_research_sync(query, rt)
        except Exception as exc:
            logger.error("市场研究失败: %s", exc, exc_info=True)
            return ResearchReport(
                query=query,
                report_type=rt,
                content="",
                error=f"研究失败: {exc}",
            )

    def research_batch(
        self,
        queries: List[str],
        report_type: Optional[str] = None,
    ) -> List[ResearchReport]:
        """批量研究多个查询."""
        return [self.research(q, report_type) for q in queries]

    # ── 内部实现 ──

    def _run_research_sync(self, query: str, report_type: str) -> ResearchReport:
        """同步执行 gpt-researcher 的 async 研究."""

        async def _conduct():
            researcher = gpt_researcher.GPTResearcher(
                query=query,
                report_type=report_type,
                max_sub_queries=self._max_sub_queries,
            )
            await researcher.conduct_research()
            report_content = researcher.write_report()

            # 提取来源和子查询
            sources = self._extract_sources(researcher)
            sub_queries = getattr(researcher, "sub_queries", [])
            cost = getattr(researcher, "costs", 0.0)

            return ResearchReport(
                query=query,
                report_type=report_type,
                content=report_content,
                sources=sources,
                sub_queries=list(sub_queries) if sub_queries else [],
                cost=float(cost) if cost else 0.0,
            )

        # 在新事件循环中运行 (避免冲突)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                asyncio.wait_for(_conduct(), timeout=self._timeout)
            )
            return result
        except asyncio.TimeoutError:
            return ResearchReport(
                query=query,
                report_type=report_type,
                content="",
                error=f"研究超时 (timeout={self._timeout}s)",
            )
        finally:
            loop.close()

    @staticmethod
    def _extract_sources(researcher: Any) -> List[ResearchSource]:
        """从 gpt-researcher 提取来源信息."""
        sources: List[ResearchSource] = []
        visited_urls = getattr(researcher, "visited_urls", [])

        if isinstance(visited_urls, list):
            for url in visited_urls:
                if isinstance(url, str):
                    sources.append(ResearchSource(url=url))
                elif isinstance(url, dict):
                    sources.append(ResearchSource(
                        url=url.get("url", ""),
                        title=url.get("title", ""),
                        snippet=url.get("snippet", "") or url.get("raw_content", "")[:200],
                    ))

        # 也尝试从 researcher.context 提取
        context = getattr(researcher, "context", [])
        if isinstance(context, list):
            for item in context[:20]:
                if isinstance(item, dict) and item.get("url"):
                    url = item["url"]
                    if not any(s.url == url for s in sources):
                        sources.append(ResearchSource(
                            url=url,
                            title=item.get("title", ""),
                            snippet=(item.get("snippet", "") or "")[:200],
                        ))

        return sources[:30]  # 限制来源数量


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[MarketResearchEngine] = None
_instance_lock = threading.Lock()


def get_market_research_engine(
    report_type: str = _DEFAULT_REPORT_TYPE,
    max_sub_queries: int = _DEFAULT_MAX_SUB_QUERIES,
) -> MarketResearchEngine:
    """获取单例实例."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MarketResearchEngine(
                    report_type=report_type,
                    max_sub_queries=max_sub_queries,
                )
    return _instance


def reset_market_research_engine() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "ResearchSource",
    "ResearchReport",
    "MarketResearchEngine",
    "get_market_research_engine",
    "reset_market_research_engine",
]
