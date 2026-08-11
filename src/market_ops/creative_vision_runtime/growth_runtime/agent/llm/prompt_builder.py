"""E13.7.2 Prompt Builder — Growth Context Prompt 构建器.

构建 LLM 推理所需的完整 Prompt，包含:
  - System Prompt: Agent 角色定义和行为准则
  - Growth Context: 当前业务状态 (指标、素材、记忆、知识)
  - Task Prompt: 具体推理任务

设计原则:
  - Prompt 是核心资产，必须结构化
  - 所有数据注入模板化，避免硬编码
  - 支持多轮推理记忆注入
  - 强制 JSON 输出格式

用法:
    builder = PromptBuilder()
    prompt = builder.build(context_data)
    response = llm_client.generate(prompt, context_data)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════


class SystemPrompt:
    """System Prompt — Agent 角色定义和行为准则.

    定义 Agent 的身份、职责、约束和推理框架。
    """

    # 核心 System Prompt 模板
    TEMPLATE = """You are an autonomous mobile game growth agent.

## Your Role
You manage user acquisition (UA) campaigns for mobile games. Your goal is to maximize
ROI while maintaining sustainable growth. You operate autonomously within defined
safety boundaries.

## Your Responsibilities
1. Analyze UA performance metrics (ROAS, CTR, CPI, LTV, retention)
2. Identify growth opportunities and threats
3. Diagnose root causes of performance changes
4. Propose evidence-based experiments and actions
5. Protect ROI by controlling budget and risk
6. Learn from historical outcomes to improve future decisions

## Your Thinking Framework
For each analysis, follow this chain:
1. OBSERVE: What are the key metrics telling us?
2. DIAGNOSE: What is the most likely root cause?
3. HYPOTHESIZE: What would improve the situation?
4. RECOMMEND: What specific actions should be taken?
5. RISK ASSESS: What could go wrong? How to mitigate?

## Decision Principles
- Never make decisions without evidence
- Always consider alternative hypotheses
- Prefer small, reversible experiments over large bets
- Protect downside first, then optimize upside
- Document your reasoning for future learning
- When in doubt, reduce risk rather than increase exposure

## Output Format
Always respond in JSON with this structure:
{
  "insight_type": "CREATIVE_FATIGUE | ROAS_DECLINE | ROAS_OPPORTUNITY | ANOMALY | NORMAL",
  "diagnosis": "Root cause analysis with evidence",
  "hypothesis": "Testable hypothesis about what would improve the situation",
  "confidence": 0.0-1.0,
  "recommended_actions": [
    {
      "action_type": "ACTION_NAME",
      "parameters": {},
      "reasoning": "Why this action",
      "expected_impact": "What we expect to happen",
      "risk": "low | medium | high"
    }
  ],
  "evidence": ["evidence_point_1", "evidence_point_2"],
  "alternative_hypotheses": ["alternative_1", "alternative_2"],
  "learning_notes": "What we should remember from this analysis"
}

## Safety Rules
- Never propose actions that could cause >20% budget increase without approval
- Never recommend pausing all campaigns simultaneously
- Always include rollback considerations
- Flag any action with risk="high" for human review
"""

    @staticmethod
    def get() -> str:
        return SystemPrompt.TEMPLATE

    @staticmethod
    def get_with_extras(extras: dict[str, str] | None = None) -> str:
        """获取带额外指令的 System Prompt."""
        prompt = SystemPrompt.TEMPLATE
        if extras:
            for section, content in extras.items():
                prompt += f"\n\n## {section}\n{content}"
        return prompt


# ═══════════════════════════════════════════════════════════════
# Growth Context Prompt
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthContextPrompt:
    """Growth Context Prompt 数据容器.

    包含构建 Prompt 所需的所有业务上下文数据。
    """

    # 产品信息
    product_name: str = ""
    platform: str = ""
    market: str = ""

    # 指标快照
    metrics: dict[str, Any] = field(default_factory=dict)

    # 素材状态
    creative_state: dict[str, Any] = field(default_factory=dict)

    # 记忆
    pattern_memories: list[dict[str, Any]] = field(default_factory=list)
    strategy_memories: list[dict[str, Any]] = field(default_factory=list)
    failure_memories: list[dict[str, Any]] = field(default_factory=list)

    # 历史行动
    recent_actions: list[dict[str, Any]] = field(default_factory=list)

    # 知识图谱
    knowledge: list[dict[str, Any]] = field(default_factory=list)

    # 活跃目标
    active_goals: list[dict[str, Any]] = field(default_factory=list)

    # 当前循环
    cycle: int = 0


# ═══════════════════════════════════════════════════════════════
# Prompt Builder
# ═══════════════════════════════════════════════════════════════


class PromptBuilder:
    """Prompt Builder — 构建完整的 LLM 推理 Prompt.

    从多个数据源组装 Prompt:
      - System Prompt (角色定义)
      - Business Context (当前状态)
      - Memory Context (历史经验)
      - Task Instruction (推理任务)

    用法:
        builder = PromptBuilder()
        prompt = builder.build(context)
    """

    # 任务 Prompt 前缀
    TASK_PREFIX = """## Current Situation

You are managing {product_name} on {platform} in {market}.

### Key Metrics
{metrics_summary}

### Creative Status
{creative_summary}

### Recent Actions
{recent_actions_summary}

### Relevant Memories
{memory_summary}

### Active Goals
{goals_summary}

## Your Task

Analyze the current situation and provide your reasoning. Follow the thinking framework:
1. What is the most significant signal in the data?
2. What is the most likely root cause?
3. What hypothesis should we test?
4. What specific actions should we take?
5. What risks should we be aware of?

Respond with a JSON object following the exact format specified in the system prompt."""

    def __init__(self, system_extras: dict[str, str] | None = None):
        self._system_prompt = SystemPrompt.get_with_extras(system_extras)
        self._history: list[str] = []

    def build(
        self,
        context: GrowthContextPrompt,
        extra_instructions: str = "",
    ) -> str:
        """构建完整 Prompt.

        Args:
            context: 业务上下文数据
            extra_instructions: 额外指令

        Returns:
            str: 完整 Prompt
        """
        prompt = self._build_task_prompt(context)

        if extra_instructions:
            prompt += f"\n\n## Additional Instructions\n{extra_instructions}"

        if self._history:
            prompt += "\n\n## Previous Analysis\n"
            prompt += "\n---\n".join(self._history[-3:])

        self._history.append(prompt)
        return prompt

    def build_messages(
        self,
        context: GrowthContextPrompt,
        extra_instructions: str = "",
    ) -> list[dict[str, str]]:
        """构建消息格式 (用于 chat API).

        Args:
            context: 业务上下文
            extra_instructions: 额外指令

        Returns:
            list[dict]: [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": self.build(context, extra_instructions)},
        ]

    def get_system_prompt(self) -> str:
        """获取 System Prompt."""
        return self._system_prompt

    def _build_task_prompt(self, context: GrowthContextPrompt) -> str:
        """构建任务 Prompt."""
        return self.TASK_PREFIX.format(
            product_name=context.product_name or "Unknown Product",
            platform=context.platform or "Unknown",
            market=context.market or "Global",
            metrics_summary=self._format_metrics(context),
            creative_summary=self._format_creative(context),
            recent_actions_summary=self._format_actions(context),
            memory_summary=self._format_memories(context),
            goals_summary=self._format_goals(context),
        )

    def _format_metrics(self, context: GrowthContextPrompt) -> str:
        """格式化指标摘要."""
        m = context.metrics
        if not m:
            return "No metrics available."

        lines = []
        if "spend" in m:
            lines.append(f"- Spend: ${m['spend']:,.0f}")
        if "roas" in m:
            lines.append(f"- ROAS: {m['roas']:.2f}")
        if "roas_change" in m:
            lines.append(f"- ROAS Change: {m['roas_change']:+.0%}")
        if "ctr" in m:
            lines.append(f"- CTR: {m['ctr']:.1%}")
        if "ctr_change" in m:
            lines.append(f"- CTR Change: {m['ctr_change']:+.0%}")
        if "cpm" in m:
            lines.append(f"- CPM: ${m['cpm']:.2f}")
        if "installs" in m:
            lines.append(f"- Installs: {m['installs']:,}")
        if "creative_fatigue" in m:
            lines.append(f"- Creative Fatigue: {m['creative_fatigue']:.0%}")
        if "payer_quality" in m:
            lines.append(f"- Payer Quality: {m['payer_quality']:.0%}")
        if "frequency" in m:
            lines.append(f"- Frequency: {m['frequency']:.1f}")
        if "d30_ltv" in m:
            lines.append(f"- D30 LTV: ${m['d30_ltv']:.2f}")
        if "payer_rate" in m:
            lines.append(f"- Payer Rate: {m['payer_rate']:.1%}")

        return "\n".join(lines) if lines else "No metrics available."

    def _format_creative(self, context: GrowthContextPrompt) -> str:
        """格式化素材状态."""
        c = context.creative_state
        if not c:
            return "No creative data available."

        lines = []
        if "total_creatives" in c:
            lines.append(f"- Total Creatives: {c['total_creatives']}")
        if "active_creatives" in c:
            lines.append(f"- Active: {c['active_creatives']}")
        if "fatigued_creatives" in c:
            lines.append(f"- Fatigued: {c['fatigued_creatives']}")
        if "winner_creative" in c:
            lines.append(f"- Winner: {c['winner_creative']}")
        if "top_dna" in c:
            lines.append(f"- Top DNA: {c['top_dna']}")

        return "\n".join(lines) if lines else "No creative data available."

    def _format_actions(self, context: GrowthContextPrompt) -> str:
        """格式化历史行动."""
        actions = context.recent_actions
        if not actions:
            return "No recent actions."

        lines = []
        for a in actions[-5:]:
            action_type = a.get("action_type", "unknown")
            result = a.get("result", "unknown")
            lines.append(f"- {action_type}: {result}")

        return "\n".join(lines)

    def _format_memories(self, context: GrowthContextPrompt) -> str:
        """格式化记忆."""
        parts = []

        if context.pattern_memories:
            lines = ["### Pattern Memories"]
            for m in context.pattern_memories[:3]:
                concept = m.get("concept", "unknown")
                desc = m.get("description", "")
                confidence = m.get("confidence", 0)
                lines.append(f"- {concept}: {desc} (confidence: {confidence:.0%})")
            parts.append("\n".join(lines))

        if context.strategy_memories:
            lines = ["### Strategy Memories"]
            for m in context.strategy_memories[:3]:
                name = m.get("name", "unknown")
                effectiveness = m.get("effectiveness", 0)
                lines.append(f"- {name} (effectiveness: {effectiveness:.0%})")
            parts.append("\n".join(lines))

        if context.failure_memories:
            lines = ["### Failure Memories"]
            for m in context.failure_memories[:3]:
                pattern = m.get("pattern", "unknown")
                lesson = m.get("lesson", "")
                lines.append(f"- {pattern}: {lesson}")
            parts.append("\n".join(lines))

        if context.knowledge:
            lines = ["### Knowledge Graph"]
            for k in context.knowledge[:3]:
                entity = k.get("entity", "unknown")
                relation = k.get("relation", "")
                lines.append(f"- {entity}: {relation}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else "No relevant memories."

    def _format_goals(self, context: GrowthContextPrompt) -> str:
        """格式化目标."""
        goals = context.active_goals
        if not goals:
            return "No active goals."

        lines = []
        for g in goals:
            title = g.get("title", "unknown")
            priority = g.get("priority", "medium")
            progress = g.get("progress", 0)
            lines.append(f"- [{priority}] {title} (progress: {progress:.0%})")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_prompt_builder() -> PromptBuilder:
    """创建默认 Prompt Builder."""
    return PromptBuilder()