"""E13.7.2 LLM Reasoning — 大语言模型推理层.

将 Agent 从规则驱动升级为 Reasoning Agent:
  - llm_client: LLM Provider 抽象层 (OpenAI / Claude / DeepSeek / Mock)
  - prompt_builder: Growth Context Prompt 构建器
  - reasoning_chain: 多步推理链 (Observation → Diagnosis → Hypothesis → Action)
  - response_parser: 结构化输出解析器
  - llm_memory: LLM 经验记忆

设计原则:
  - LLM 是高级推理层，不替代现有 Decision Engine
  - 所有输出必须结构化 JSON
  - Prompt Builder 是核心资产
  - 支持多 Provider，降低绑定成本
"""

from .llm_client import (
    LLMClient,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    MockLLMProvider,
    create_llm_client,
)
from .llm_memory import (
    LLMExperienceMemory,
    ReasoningExperience,
)
from .prompt_builder import (
    GrowthContextPrompt,
    PromptBuilder,
    SystemPrompt,
)
from .reasoning_chain import (
    ReasoningChain,
    ReasoningOutput,
    ReasoningStep,
)
from .response_parser import (
    ParsedResponse,
    ResponseParser,
)

__all__ = [
    # LLM Client
    "LLMProvider",
    "LLMConfig",
    "LLMResponse",
    "LLMClient",
    "MockLLMProvider",
    "create_llm_client",
    # Prompt Builder
    "SystemPrompt",
    "GrowthContextPrompt",
    "PromptBuilder",
    # Reasoning Chain
    "ReasoningStep",
    "ReasoningChain",
    "ReasoningOutput",
    # Response Parser
    "ParsedResponse",
    "ResponseParser",
    # LLM Memory
    "ReasoningExperience",
    "LLMExperienceMemory",
]