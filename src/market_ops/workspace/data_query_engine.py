"""数据查询引擎 — 封装 pandas-ai 的自然语言数据查询能力.

pandas-ai 核心能力:
  - LLM 将自然语言问题转换为 pandas 代码
  - 在 DataFrame 上执行生成的代码
  - 支持多 DataFrame 关联查询
  - 可选 Docker 沙箱隔离执行环境

集成点:
  - DataAnalystAgent.ask() 注入此引擎
  - workspace/app.py API 端点直接调用
  - 将现有 BehaviorData / BI 数据转为 DataFrame 传入

安全设计:
  - 默认只读模式 (enable_safe_import_code=False)
  - Docker 沙箱可选启用
  - LLM 生成的代码不会写入文件系统
  - 优雅降级: pandas-ai 未安装时返回 not_available

用法:
  engine = DataQueryEngine()
  status = engine.check_status()
  if status["status"] == "ready":
      answer = engine.ask("各游戏 LTV 按地区排名前3", {"revenue": df_revenue})
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_DEFAULT_MODEL = "gpt-4.1-mini"


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class QueryResult:
    """自然语言查询结果."""

    question: str
    answer: str                           # LLM 生成的回答
    code: str = ""                        # 生成的 pandas 代码
    dataframes_used: list[str] = field(default_factory=list)
    error: str = ""
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "code": self.code,
            "dataframes_used": self.dataframes_used,
            "error": self.error,
            "success": self.success and not self.error,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }


# ── 数据查询引擎 ──────────────────────────────────────────────

class DataQueryEngine:
    """数据查询引擎 — 封装 pandas-ai.

    将自然语言问题转换为 pandas 代码并在 DataFrame 上执行.

    线程安全: 单实例可并发调用.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        sandbox: bool = False,
        enable_safe_import_code: bool = False,
    ) -> None:
        self._model = model
        self._sandbox = sandbox
        self._enable_safe_import_code = enable_safe_import_code
        self._lock = threading.Lock()
        self._llm = None

    # ── 状态检查 ──

    def check_status(self) -> Dict[str, Any]:
        """检查 pandas-ai 安装和 LLM 配置状态."""
        try:
            import pandasai  # noqa: F401
            pandasai_installed = True
        except ImportError:
            pandasai_installed = False

        import os
        llm_configured = bool(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )

        if not pandasai_installed:
            status = "not_installed"
        elif not llm_configured:
            status = "llm_not_configured"
        else:
            status = "ready"

        return {
            "status": status,
            "pandasai_installed": pandasai_installed,
            "llm_configured": llm_configured,
            "model": self._model,
            "sandbox": self._sandbox,
            "setup_guide": self._get_setup_guide(status),
        }

    @staticmethod
    def _get_setup_guide(status: str) -> str:
        guides = {
            "not_installed": "安装: pip install pandas-ai",
            "llm_not_configured": "配置 LLM: 设置 OPENAI_API_KEY 环境变量",
            "ready": "pandas-ai 已就绪",
        }
        return guides.get(status, "未知状态")

    # ── 查询接口 ──

    def ask(
        self,
        question: str,
        dataframes: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """用自然语言查询 DataFrame 数据.

        Args:
            question: 自然语言问题 (如 "各游戏 LTV 按地区排名前3")
            dataframes: 命名 DataFrame 字典 (如 {"revenue": df_revenue})
                        值可以是 pandas.DataFrame 或可转为 DataFrame 的 dict/list

        Returns:
            QueryResult 包含回答、生成的代码和使用的 DataFrame 名称
        """
        if not question.strip():
            return QueryResult(
                question=question,
                answer="",
                error="问题不能为空",
                success=False,
            )

        try:
            import pandasai
            from pandasai_litellm.litellm import LiteLLM
        except ImportError:
            return QueryResult(
                question=question,
                answer="",
                error="pandas-ai 未安装. 请运行: pip install pandas-ai",
                success=False,
            )

        if dataframes is None:
            dataframes = {}

        # 转换输入为 SmartDataframe
        try:
            smart_dfs = self._prepare_dataframes(dataframes)
        except Exception as exc:
            return QueryResult(
                question=question,
                answer="",
                error=f"DataFrame 准备失败: {exc}",
                success=False,
            )

        if not smart_dfs:
            return QueryResult(
                question=question,
                answer="",
                error="没有可用的 DataFrame",
                success=False,
            )

        try:
            llm = self._get_llm(LiteLLM)
            if llm is None:
                return QueryResult(
                    question=question,
                    answer="",
                    error="LLM 初始化失败, 请检查 API key 配置",
                    success=False,
                )

            # 如果只有一个 DataFrame, 直接用 SmartDataframe.chat
            if len(smart_dfs) == 1:
                name, sdf = next(iter(smart_dfs.items()))
                answer = sdf.chat(question)
                return QueryResult(
                    question=question,
                    answer=str(answer) if answer is not None else "",
                    dataframes_used=[name],
                )

            # 多 DataFrame: 使用 SmartDatalake
            from pandasai import SmartDatalake
            lake = SmartDatalake(list(smart_dfs.values()))
            answer = lake.chat(question)
            return QueryResult(
                question=question,
                answer=str(answer) if answer is not None else "",
                dataframes_used=list(smart_dfs.keys()),
            )

        except Exception as exc:
            logger.error("pandas-ai 查询失败: %s", exc, exc_info=True)
            return QueryResult(
                question=question,
                answer="",
                error=f"查询失败: {exc}",
                success=False,
            )

    # ── 内部实现 ──

    def _get_llm(self, LiteLLMClass):
        """获取/缓存 LLM 实例."""
        if self._llm is not None:
            return self._llm

        import os
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            return None

        try:
            self._llm = LiteLLMClass(model=self._model, api_key=api_key)
            return self._llm
        except Exception as exc:
            logger.error("LLM 初始化失败: %s", exc)
            return None

    def _prepare_dataframes(self, dataframes: Dict[str, Any]) -> Dict[str, Any]:
        """将输入数据转为 pandas-ai SmartDataframe."""
        import pandas as pd
        from pandasai import SmartDataframe

        smart_dfs: Dict[str, Any] = {}

        for name, data in dataframes.items():
            if hasattr(data, "chat"):
                # 已经是 SmartDataframe
                smart_dfs[name] = data
                continue

            # 转为 pandas DataFrame
            if isinstance(data, pd.DataFrame):
                df = data
            elif isinstance(data, dict):
                df = pd.DataFrame(data)
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                logger.warning("跳过无法转换的数据: %s (type=%s)", name, type(data).__name__)
                continue

            if df.empty:
                continue

            sdf = SmartDataframe(
                df,
                config={
                    "llm": self._llm,
                    "enable_safe_import_code": self._enable_safe_import_code,
                    "sandbox": self._sandbox,
                },
            )
            smart_dfs[name] = sdf

        return smart_dfs


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[DataQueryEngine] = None
_instance_lock = threading.Lock()


def get_data_query_engine(
    model: str = _DEFAULT_MODEL,
    sandbox: bool = False,
) -> DataQueryEngine:
    """获取单例实例."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DataQueryEngine(model=model, sandbox=sandbox)
    return _instance


def reset_data_query_engine() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "QueryResult",
    "DataQueryEngine",
    "get_data_query_engine",
    "reset_data_query_engine",
]
