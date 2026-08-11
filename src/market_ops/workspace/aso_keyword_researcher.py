"""ASO 关键词研究器 — 高层接口, 供 ASO Agent 和 API 端点调用.

封装 aso-mcp 的 MCP 工具调用, 提供简洁的关键词研究接口:
  - research_keywords(): 关键词热度/难度/品牌词分析
  - check_status(): 检查 aso-mcp 安装和认证状态
  - get_keyword_suggestions(): 基于种子词的关键词扩展

集成点:
  - ASOKeywordAgent.collect_reality() 可注入此研究器获取真实数据
  - workspace/app.py API 端点直接调用
  - ASORealityConnector 可作为 ASODataProvider 使用

用法:
  researcher = ASOKeywordResearcher()
  status = researcher.check_status()
  if status["available"]:
      result = researcher.research_keywords(["meditation", "sleep sounds"])
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .aso_mcp_client import (
    ASOMcpClient,
    ASOMcpError,
    ASOMcpNotInstalledError,
    ASOMcpToolError,
)

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_TOOL_EVALUATE_KEYWORDS = "aso_evaluate_keywords"

# MCP 默认过滤参数 (与 aso-mcp 一致)
_DEFAULT_MIN_POPULARITY = 6
_DEFAULT_MAX_DIFFICULTY = 70


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class KeywordMetric:
    """单个关键词的 ASO 指标."""

    keyword: str
    popularity: int = 0
    difficulty_score: float = 0.0
    min_difficulty_score: float = 0.0
    is_brand_keyword: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "popularity": self.popularity,
            "difficulty_score": self.difficulty_score,
            "min_difficulty_score": self.min_difficulty_score,
            "is_brand_keyword": self.is_brand_keyword,
        }


@dataclass
class KeywordResearchResult:
    """关键词研究结果."""

    items: List[KeywordMetric] = field(default_factory=list)
    failed_keywords: List[str] = field(default_factory=list)
    filtered_out: List[str] = field(default_factory=list)
    raw: Optional[Dict] = None
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error

    @property
    def total_researched(self) -> int:
        return len(self.items) + len(self.failed_keywords) + len(self.filtered_out)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "failed_keywords": self.failed_keywords,
            "filtered_out": self.filtered_out,
            "total_researched": self.total_researched,
            "success": self.success,
            "error": self.error,
        }


# ── 研究器 ────────────────────────────────────────────────────

class ASOKeywordResearcher:
    """ASO 关键词研究器 — 封装 aso-mcp 工具调用.

    每次调用创建新的 MCP 连接 (避免长连接管理复杂性).
    对于批量场景, 可使用 with 语法保持连接.
    """

    def __init__(
        self,
        command: str = "aso-mcp",
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout = timeout
        self._lock = threading.Lock()

    # ── 状态检查 ──

    def check_status(self) -> Dict[str, Any]:
        """检查 aso-mcp 和 aso CLI 的安装/认证状态."""
        mcp_available = ASOMcpClient.is_available()
        cli_authenticated = ASOMcpClient.is_authenticated()

        # 检查 aso CLI 是否安装
        import shutil
        cli_installed = shutil.which("aso") is not None

        status = "ready"
        if not cli_installed:
            status = "not_installed"
        elif not cli_authenticated:
            status = "not_authenticated"
        elif not mcp_available:
            status = "mcp_unavailable"

        return {
            "status": status,
            "cli_installed": cli_installed,
            "mcp_available": mcp_available,
            "authenticated": cli_authenticated,
            "setup_guide": self._get_setup_guide(status),
        }

    @staticmethod
    def _get_setup_guide(status: str) -> str:
        guides = {
            "not_installed": "安装: npm install -g aso-cli",
            "not_authenticated": "认证: 在终端运行 'aso auth' 完成 Apple Search Ads 登录",
            "mcp_unavailable": "aso-mcp 不可用, 尝试重新安装: npm install -g aso-cli",
            "ready": "aso-mcp 已就绪",
        }
        return guides.get(status, "未知状态")

    # ── 关键词研究 ──

    def research_keywords(
        self,
        keywords: List[str],
        min_popularity: int = _DEFAULT_MIN_POPULARITY,
        max_difficulty: int = _DEFAULT_MAX_DIFFICULTY,
    ) -> KeywordResearchResult:
        """研究关键词的 ASO 指标 (热度/难度/品牌词).

        Args:
            keywords: 关键词列表 (如 ["meditation", "sleep sounds"])
            min_popularity: 最小热度过滤 (默认 6)
            max_difficulty: 最大难度过滤 (默认 70)

        Returns:
            KeywordResearchResult 包含通过过滤的关键词指标
        """
        if not keywords:
            return KeywordResearchResult(error="关键词列表为空")

        # 将关键词列表转为逗号分隔字符串 (aso-mcp 的输入格式)
        keywords_str = ",".join(keywords)

        try:
            with ASOMcpClient(
                command=self._command,
                cwd=self._cwd,
                timeout=self._timeout,
            ) as client:
                result = client.call_tool(
                    _TOOL_EVALUATE_KEYWORDS,
                    {
                        "keywords": keywords_str,
                        "minPopularity": min_popularity,
                        "maxDifficulty": max_difficulty,
                    },
                )

                return self._parse_result(result)

        except ASOMcpNotInstalledError as exc:
            logger.error("aso-mcp 未安装: %s", exc)
            return KeywordResearchResult(
                error=f"aso-mcp 未安装: {exc}. 请运行: npm install -g aso-cli"
            )
        except ASOMcpToolError as exc:
            logger.error("aso-mcp 工具调用失败: %s", exc)
            return KeywordResearchResult(
                error=f"工具调用失败: {exc} (code={exc.error_code})"
            )
        except ASOMcpError as exc:
            logger.error("aso-mcp 通信错误: %s", exc)
            return KeywordResearchResult(error=f"MCP 通信错误: {exc}")
        except Exception as exc:
            logger.error("关键词研究异常: %s", exc, exc_info=True)
            return KeywordResearchResult(error=f"未知错误: {exc}")

    def research_single(self, keyword: str, **kwargs) -> KeywordResearchResult:
        """研究单个关键词 (便捷方法)."""
        return self.research_keywords([keyword], **kwargs)

    # ── 结果解析 ──

    @staticmethod
    def _parse_result(result: Any) -> KeywordResearchResult:
        """解析 aso-mcp 返回的结果为 KeywordResearchResult."""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return KeywordResearchResult(
                    error=f"无法解析返回结果: {result[:200]}"
                )

        if not isinstance(result, dict):
            return KeywordResearchResult(
                error=f"返回结果格式异常: {type(result).__name__}"
            )

        # 检查错误格式
        if "error" in result and isinstance(result["error"], dict):
            err = result["error"]
            return KeywordResearchResult(
                error=f"{err.get('message', '未知错误')} (code={err.get('code', '')})"
            )

        items: List[KeywordMetric] = []
        for item in result.get("items", []):
            items.append(KeywordMetric(
                keyword=item.get("keyword", ""),
                popularity=item.get("popularity", 0),
                difficulty_score=item.get("difficultyScore", 0.0),
                min_difficulty_score=item.get("minDifficultyScore", 0.0),
                is_brand_keyword=item.get("isBrandKeyword", False),
            ))

        return KeywordResearchResult(
            items=items,
            failed_keywords=result.get("failedKeywords", []),
            filtered_out=result.get("filteredOut", []),
            raw=result if isinstance(result, dict) else None,
        )


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[ASOKeywordResearcher] = None
_instance_lock = threading.Lock()


def get_aso_keyword_researcher(
    command: str = "aso-mcp",
    cwd: Optional[str] = None,
) -> ASOKeywordResearcher:
    """获取单例实例."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ASOKeywordResearcher(command=command, cwd=cwd)
    return _instance


def reset_aso_keyword_researcher() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "KeywordMetric",
    "KeywordResearchResult",
    "ASOKeywordResearcher",
    "get_aso_keyword_researcher",
    "reset_aso_keyword_researcher",
]
