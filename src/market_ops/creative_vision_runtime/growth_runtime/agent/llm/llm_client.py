"""E13.7.2 LLM Client — LLM Provider 抽象层.

支持多 Provider:
  - OpenAI (GPT-4, GPT-4o)
  - Claude (Anthropic)
  - DeepSeek
  - Mock (测试用)

设计原则:
  - 不绑定单一 Provider
  - 统一接口: generate(prompt, context) → LLMResponse
  - 支持 timeout, retry, fallback
  - Mock Provider 支持确定性测试

用法:
    client = create_llm_client(LLMProvider.MOCK)
    response = client.generate("分析以下数据", {"metrics": {...}})
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════


class LLMProvider(str, Enum):
    """LLM Provider 枚举."""
    MOCK = "mock"
    OPENAI = "openai"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"


@dataclass
class LLMConfig:
    """LLM 配置.

    Attributes:
        provider: Provider 类型
        model: 模型名称
        api_key: API 密钥
        api_base: API 基础 URL
        max_tokens: 最大输出 token
        temperature: 温度 [0, 2]
        timeout_seconds: 超时时间
        max_retries: 最大重试次数
        fallback_providers: 降级 Provider 列表
        metadata: 扩展配置
    """
    provider: LLMProvider = LLMProvider.MOCK
    model: str = "gpt-4o"
    api_key: str = ""
    api_base: str = ""
    max_tokens: int = 2000
    temperature: float = 0.3
    timeout_seconds: int = 30
    max_retries: int = 3
    fallback_providers: list[LLMProvider] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 响应.

    Attributes:
        content: 响应内容 (文本)
        provider: 使用的 Provider
        model: 使用的模型
        tokens_used: token 消耗
        latency_ms: 延迟 (毫秒)
        success: 是否成功
        error: 错误信息
        metadata: 扩展元数据
    """
    content: str = ""
    provider: LLMProvider = LLMProvider.MOCK
    model: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Base LLM Client
# ═══════════════════════════════════════════════════════════════


class LLMClient:
    """LLM 客户端抽象基类.

    所有 Provider 实现必须继承此类并实现:
      - _generate_impl(prompt, context) → LLMResponse

    内置:
      - timeout 控制
      - retry 机制
      - fallback 降级
    """

    def __init__(self, config: LLMConfig | None = None):
        self._config = config or LLMConfig()
        self._request_count: int = 0
        self._total_tokens: int = 0

    @property
    def provider(self) -> LLMProvider:
        return self._config.provider

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """生成响应 — 带 timeout, retry, fallback.

        Args:
            prompt: 提示词
            context: 上下文数据

        Returns:
            LLMResponse: 响应
        """
        ctx = context or {}
        last_error = ""

        # 尝试当前 Provider
        for attempt in range(self._config.max_retries + 1):
            try:
                start = time.time()
                response = self._generate_impl(prompt, ctx)
                response.latency_ms = (time.time() - start) * 1000
                response.provider = self._config.provider
                response.model = self._config.model

                if response.success:
                    self._request_count += 1
                    self._total_tokens += response.tokens_used
                    return response

                last_error = response.error
            except Exception as e:
                last_error = str(e)

            if attempt < self._config.max_retries:
                time.sleep(min(2 ** attempt, 10))  # 指数退避

        # 尝试 fallback
        for fallback_provider in self._config.fallback_providers:
            try:
                fallback_client = create_llm_client(
                    fallback_provider,
                    LLMConfig(
                        provider=fallback_provider,
                        timeout_seconds=self._config.timeout_seconds,
                    ),
                )
                response = fallback_client.generate(prompt, ctx)
                if response.success:
                    response.metadata["fallback_from"] = self._config.provider.value
                    return response
            except Exception:
                continue

        # 全部失败
        return LLMResponse(
            content="",
            provider=self._config.provider,
            model=self._config.model,
            success=False,
            error=f"All attempts failed: {last_error}",
        )

    def _generate_impl(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> LLMResponse:
        """子类实现: 实际的 LLM 调用."""
        raise NotImplementedError("Subclasses must implement _generate_impl")


# ═══════════════════════════════════════════════════════════════
# Mock Provider (测试用)
# ═══════════════════════════════════════════════════════════════


class MockLLMProvider(LLMClient):
    """Mock LLM Provider — 用于测试.

    根据 prompt 中的关键词返回确定性响应。
    支持自定义响应映射。
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        responses: dict[str, str] | None = None,
    ):
        super().__init__(config or LLMConfig(provider=LLMProvider.MOCK, model="mock"))
        self._responses = responses or {}
        self._history: list[dict[str, Any]] = []

    @property
    def history(self) -> list[dict[str, Any]]:
        return self._history

    def set_response(self, keyword: str, response: str) -> None:
        """设置特定关键词的响应."""
        self._responses[keyword.lower()] = response

    def _generate_impl(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> LLMResponse:
        """Mock 生成 — 基于关键词匹配返回确定性响应."""
        self._history.append({
            "prompt": prompt[:200],
            "context_keys": list(context.keys()),
        })

        # 关键词匹配
        prompt_lower = prompt.lower()
        for keyword, response_text in self._responses.items():
            if keyword in prompt_lower:
                return LLMResponse(
                    content=response_text,
                    provider=LLMProvider.MOCK,
                    model="mock",
                    tokens_used=len(response_text) // 4,
                    success=True,
                )

        # 默认: 根据 context 生成合理响应
        response_data = self._build_default_response(context)
        return LLMResponse(
            content=json.dumps(response_data, ensure_ascii=False),
            provider=LLMProvider.MOCK,
            model="mock",
            tokens_used=200,
            success=True,
        )

    def _build_default_response(self, context: dict[str, Any]) -> dict[str, Any]:
        """根据 context 构建默认 mock 响应."""
        metrics = context.get("metrics", {})
        fatigue = metrics.get("creative_fatigue", 0)
        roas_change = metrics.get("roas_change", 0)

        # 疲劳度场景
        if fatigue > 0.7:
            return {
                "insight_type": "CREATIVE_FATIGUE",
                "diagnosis": "素材疲劳度超过阈值，CTR 和 ROAS 同步下降",
                "hypothesis": "当前素材已进入疲劳期，需要生成新 DNA 变体恢复表现",
                "confidence": 0.87,
                "recommended_actions": [
                    {
                        "action_type": "MUTATE_CREATIVE",
                        "parameters": {
                            "variants": 5,
                            "strategy": "hook_change",
                            "based_on_winner": True,
                        },
                        "reasoning": "基于赢家素材进行 hook 变异，保留核心机制",
                        "expected_impact": "CTR +15%, ROAS +20%",
                        "risk": "low",
                    },
                ],
                "evidence": [
                    f"creative_fatigue={fatigue:.2f}",
                    f"roas_change={roas_change:.2f}",
                ],
                "alternative_hypotheses": [
                    "受众饱和导致表现下降",
                    "竞品素材更新导致分流",
                ],
            }

        # ROAS 下降场景
        if roas_change < -0.2:
            return {
                "insight_type": "ROAS_DECLINE",
                "diagnosis": "ROAS 显著下降，需要分析根本原因",
                "hypothesis": "成本上升或素材效果下降导致 ROAS 恶化",
                "confidence": 0.75,
                "recommended_actions": [
                    {
                        "action_type": "REDUCE_BUDGET",
                        "parameters": {"scale_factor": 0.8},
                        "reasoning": "临时降低预算保护 ROI",
                        "expected_impact": "ROAS 回升至可控水平",
                        "risk": "low",
                    },
                    {
                        "action_type": "CHECK_FATIGUE",
                        "parameters": {"creative_id": "all"},
                        "reasoning": "排查素材疲劳度",
                        "expected_impact": "确定是否需要素材变异",
                        "risk": "none",
                    },
                ],
                "evidence": [f"roas_change={roas_change:.2f}"],
                "alternative_hypotheses": ["竞品加大投放", "季节性波动"],
            }

        # ROAS 上升场景
        if roas_change > 0.2:
            return {
                "insight_type": "ROAS_OPPORTUNITY",
                "diagnosis": "ROAS 显著上升，存在扩大投放机会",
                "hypothesis": "当前策略有效，可以适度扩大预算",
                "confidence": 0.80,
                "recommended_actions": [
                    {
                        "action_type": "SCALE_BUDGET",
                        "parameters": {"scale_factor": 1.2},
                        "reasoning": "在 ROAS 上升期扩大预算获取更多转化",
                        "expected_impact": "安装量 +20%, 收入 +20%",
                        "risk": "medium",
                    },
                ],
                "evidence": [f"roas_change={roas_change:.2f}"],
                "alternative_hypotheses": ["短期波动", "归因数据延迟"],
            }

        # 默认: 正常运行
        return {
            "insight_type": "NORMAL",
            "diagnosis": "当前指标在正常范围内",
            "hypothesis": "系统运行正常，无需干预",
            "confidence": 0.90,
            "recommended_actions": [
                {
                    "action_type": "MONITOR",
                    "parameters": {"duration_hours": 24},
                    "reasoning": "保持监控，等待信号变化",
                    "expected_impact": "维持当前表现",
                    "risk": "none",
                },
            ],
            "evidence": ["metrics within normal range"],
            "alternative_hypotheses": [],
        }


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_llm_client(
    provider: LLMProvider = LLMProvider.MOCK,
    config: LLMConfig | None = None,
) -> LLMClient:
    """创建 LLM 客户端.

    Args:
        provider: Provider 类型
        config: 配置 (为 None 时使用默认配置)

    Returns:
        LLMClient: 对应 Provider 的客户端
    """
    cfg = config or LLMConfig(provider=provider)

    if provider == LLMProvider.MOCK:
        return MockLLMProvider(cfg)
    elif provider == LLMProvider.OPENAI:
        return _create_openai_client(cfg)
    elif provider == LLMProvider.CLAUDE:
        return _create_claude_client(cfg)
    elif provider == LLMProvider.DEEPSEEK:
        return _create_deepseek_client(cfg)
    else:
        return MockLLMProvider(cfg)


def _create_openai_client(config: LLMConfig) -> LLMClient:
    """创建 OpenAI 客户端 (需要 openai 库)."""
    try:
        import openai  # noqa: F401

        class OpenAIClient(LLMClient):
            def _generate_impl(self, prompt, context) -> LLMResponse:
                try:
                    client = openai.OpenAI(
                        api_key=config.api_key,
                        base_url=config.api_base or None,
                        timeout=config.timeout_seconds,
                    )
                    response = client.chat.completions.create(
                        model=config.model,
                        messages=[
                            {"role": "system", "content": "You are an autonomous mobile game growth agent."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        response_format={"type": "json_object"},
                    )
                    return LLMResponse(
                        content=response.choices[0].message.content or "",
                        tokens_used=response.usage.total_tokens if response.usage else 0,
                        success=True,
                    )
                except Exception as e:
                    return LLMResponse(success=False, error=str(e))

        return OpenAIClient(config)
    except ImportError:
        return MockLLMProvider(config)


def _create_claude_client(config: LLMConfig) -> LLMClient:
    """创建 Claude 客户端 (需要 anthropic 库)."""
    try:
        import anthropic  # noqa: F401

        class ClaudeClient(LLMClient):
            def _generate_impl(self, prompt, context) -> LLMResponse:
                try:
                    client = anthropic.Anthropic(api_key=config.api_key)
                    response = client.messages.create(
                        model=config.model,
                        max_tokens=config.max_tokens,
                        system="You are an autonomous mobile game growth agent. Always respond in JSON.",
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return LLMResponse(
                        content=response.content[0].text,
                        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                        success=True,
                    )
                except Exception as e:
                    return LLMResponse(success=False, error=str(e))

        return ClaudeClient(config)
    except ImportError:
        return MockLLMProvider(config)


def _create_deepseek_client(config: LLMConfig) -> LLMClient:
    """创建 DeepSeek 客户端 (兼容 OpenAI SDK)."""
    try:
        import openai  # noqa: F401

        class DeepSeekClient(LLMClient):
            def _generate_impl(self, prompt, context) -> LLMResponse:
                try:
                    client = openai.OpenAI(
                        api_key=config.api_key,
                        base_url=config.api_base or "https://api.deepseek.com",
                        timeout=config.timeout_seconds,
                    )
                    response = client.chat.completions.create(
                        model=config.model or "deepseek-chat",
                        messages=[
                            {"role": "system", "content": "You are an autonomous mobile game growth agent."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        response_format={"type": "json_object"},
                    )
                    return LLMResponse(
                        content=response.choices[0].message.content or "",
                        tokens_used=response.usage.total_tokens if response.usage else 0,
                        success=True,
                    )
                except Exception as e:
                    return LLMResponse(success=False, error=str(e))

        return DeepSeekClient(config)
    except ImportError:
        return MockLLMProvider(config)