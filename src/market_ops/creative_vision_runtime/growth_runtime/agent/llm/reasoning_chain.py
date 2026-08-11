"""E13.7.2 Reasoning Chain — 多步推理链.

将 LLM 推理从单步 Prompt → Answer 升级为多步推理链:
  Observation → Diagnosis → Hypothesis → Action Recommendation → Confidence

设计原则:
  - 每步推理有明确的输入输出
  - 支持 Chain-of-Thought 推理
  - 输出结构化 ReasoningOutput
  - 与现有 Insight 模型兼容

用法:
    chain = ReasoningChain(llm_client)
    output = chain.reason(context_prompt)
    insights = output.to_insights()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..agent_models import Insight, InsightType


# ═══════════════════════════════════════════════════════════════
# Reasoning Step
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningStep:
    """推理步骤 — 推理链中的单步.

    Attributes:
        step_name: 步骤名称
        input: 输入数据
        output: 输出数据
        confidence: 该步骤的置信度
        reasoning: 推理过程
    """
    step_name: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    reasoning: str = ""


# ═══════════════════════════════════════════════════════════════
# Reasoning Output
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningOutput:
    """推理输出 — 推理链的最终产出.

    Attributes:
        insight_type: 洞察类型
        diagnosis: 诊断结论
        hypothesis: 可测试假设
        confidence: 综合置信度
        recommended_actions: 推荐行动列表
        evidence: 支撑证据
        alternative_hypotheses: 替代假设
        steps: 推理步骤 (Chain-of-Thought)
        learning_notes: 学习笔记
        raw_response: 原始 LLM 响应
        metadata: 扩展元数据
    """
    insight_type: str = "NORMAL"
    diagnosis: str = ""
    hypothesis: str = ""
    confidence: float = 0.5
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    alternative_hypotheses: list[str] = field(default_factory=list)
    steps: list[ReasoningStep] = field(default_factory=list)
    learning_notes: str = ""
    raw_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_insights(self) -> list[Insight]:
        """将推理输出转换为 Insight 列表.

        Returns:
            list[Insight]: 洞察列表
        """
        insights = []

        # 映射 insight_type 到 InsightType
        type_map = {
            "CREATIVE_FATIGUE": InsightType.THREAT,
            "ROAS_DECLINE": InsightType.THREAT,
            "ROAS_OPPORTUNITY": InsightType.OPPORTUNITY,
            "ANOMALY": InsightType.ANOMALY,
            "PATTERN": InsightType.PATTERN,
            "NORMAL": InsightType.CONFIRMATION,
        }

        insight_type = type_map.get(self.insight_type, InsightType.OPPORTUNITY)

        # 主洞察
        main_insight = Insight(
            insight_type=insight_type,
            title=self._build_title(),
            description=self.diagnosis,
            reasoning=self.hypothesis,
            confidence=self.confidence,
            evidence=self.evidence,
            suggested_action=self._build_suggested_action(),
            urgency=self._calculate_urgency(),
            metadata={
                "source": "llm_reasoning",
                "insight_type": self.insight_type,
                "alternative_hypotheses": self.alternative_hypotheses,
                "learning_notes": self.learning_notes,
                "recommended_actions": self.recommended_actions,
            },
        )
        insights.append(main_insight)

        # 替代假设作为低置信度洞察
        for alt in self.alternative_hypotheses:
            insights.append(Insight(
                insight_type=InsightType.PATTERN,
                title=f"替代假设: {alt[:50]}",
                description=alt,
                reasoning="Alternative hypothesis from LLM reasoning",
                confidence=0.3,
                evidence=[],
                suggested_action="",
                urgency=0.2,
                metadata={"source": "llm_alternative_hypothesis"},
            ))

        return insights

    def _build_title(self) -> str:
        """构建洞察标题."""
        titles = {
            "CREATIVE_FATIGUE": "LLM 分析: 素材疲劳警告",
            "ROAS_DECLINE": "LLM 分析: ROAS 下降分析",
            "ROAS_OPPORTUNITY": "LLM 分析: ROAS 上升机会",
            "ANOMALY": "LLM 分析: 异常检测",
            "PATTERN": "LLM 分析: 模式识别",
            "NORMAL": "LLM 分析: 正常运行",
        }
        return titles.get(self.insight_type, f"LLM 分析: {self.insight_type}")

    def _build_suggested_action(self) -> str:
        """构建建议行动字符串."""
        if not self.recommended_actions:
            return ""
        primary = self.recommended_actions[0]
        action_type = primary.get("action_type", "")
        params = primary.get("parameters", {})
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"{action_type}: {param_str}" if param_str else action_type

    def _calculate_urgency(self) -> float:
        """计算紧急程度."""
        urgency_map = {
            "CREATIVE_FATIGUE": 0.85,
            "ROAS_DECLINE": 0.80,
            "ANOMALY": 0.60,
            "ROAS_OPPORTUNITY": 0.50,
            "PATTERN": 0.35,
            "NORMAL": 0.10,
        }
        return urgency_map.get(self.insight_type, 0.40)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "confidence": self.confidence,
            "recommended_actions": self.recommended_actions,
            "evidence": self.evidence,
            "alternative_hypotheses": self.alternative_hypotheses,
            "steps": [s.__dict__ for s in self.steps],
            "learning_notes": self.learning_notes,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Reasoning Chain
# ═══════════════════════════════════════════════════════════════


class ReasoningChain:
    """多步推理链 — 执行结构化推理流程.

    推理链:
      1. Observation → 理解当前状态
      2. Diagnosis → 诊断根本原因
      3. Hypothesis → 生成可测试假设
      4. Action → 推荐具体行动
      5. Confidence → 评估置信度

    用法:
        chain = ReasoningChain(llm_client)
        output = chain.reason(context_prompt)
    """

    # 每步推理的 Prompt 模板
    STEP_PROMPTS = {
        "observation": "What are the key signals in the current data? Summarize the most important metrics and trends.",
        "diagnosis": "Based on the observations, what is the most likely root cause of any performance issues? Consider multiple factors.",
        "hypothesis": "What testable hypothesis would explain the observed patterns? What would improve the situation?",
        "action": "What specific actions should we take? Include action type, parameters, expected impact, and risk level.",
        "confidence": "Rate your confidence in this analysis (0.0-1.0) and explain why. What alternative hypotheses should be considered?",
    }

    def __init__(
        self,
        llm_client: Any = None,
        use_multi_step: bool = True,
    ):
        """初始化推理链.

        Args:
            llm_client: LLM 客户端
            use_multi_step: 是否使用多步推理 (False 则单步)
        """
        self._llm_client = llm_client
        self._use_multi_step = use_multi_step
        self._chain_count: int = 0

    @property
    def chain_count(self) -> int:
        return self._chain_count

    def reason(
        self,
        context: dict[str, Any],
        prompt: str = "",
    ) -> ReasoningOutput:
        """执行推理链.

        Args:
            context: 业务上下文
            prompt: 完整 Prompt (单步模式)

        Returns:
            ReasoningOutput: 推理输出
        """
        self._chain_count += 1

        if not self._llm_client:
            return self._rule_based_fallback(context)

        if self._use_multi_step:
            return self._multi_step_reason(context, prompt)
        else:
            return self._single_step_reason(context, prompt)

    def _multi_step_reason(
        self,
        context: dict[str, Any],
        prompt: str,
    ) -> ReasoningOutput:
        """多步推理 — 每步独立调用 LLM."""
        steps = []

        # Step 1: Observation
        obs_result = self._llm_step("observation", context, prompt)
        steps.append(ReasoningStep(
            step_name="observation",
            input={"context": {k: str(v)[:100] for k, v in context.items()}},
            output=obs_result,
            confidence=0.9,
        ))

        # Step 2: Diagnosis
        diag_result = self._llm_step("diagnosis", context, prompt, obs_result)
        steps.append(ReasoningStep(
            step_name="diagnosis",
            input={"observation": obs_result},
            output=diag_result,
            confidence=0.8,
        ))

        # Step 3: Hypothesis
        hyp_result = self._llm_step("hypothesis", context, prompt, diag_result)
        steps.append(ReasoningStep(
            step_name="hypothesis",
            input={"diagnosis": diag_result},
            output=hyp_result,
            confidence=0.7,
        ))

        # Step 4: Action
        action_result = self._llm_step("action", context, prompt, hyp_result)
        steps.append(ReasoningStep(
            step_name="action",
            input={"hypothesis": hyp_result},
            output=action_result,
            confidence=0.7,
        ))

        # Step 5: Confidence
        conf_result = self._llm_step("confidence", context, prompt, action_result)
        steps.append(ReasoningStep(
            step_name="confidence",
            input={"action": action_result},
            output=conf_result,
            confidence=0.9,
        ))

        return self._build_output(steps, diag_result, hyp_result, action_result, conf_result)

    def _single_step_reason(
        self,
        context: dict[str, Any],
        prompt: str,
    ) -> ReasoningOutput:
        """单步推理 — 一次 LLM 调用完成全部推理."""
        from .response_parser import ResponseParser

        response = self._llm_client.generate(prompt, context)
        if not response.success:
            return ReasoningOutput(
                diagnosis=f"LLM call failed: {response.error}",
                confidence=0.0,
                metadata={"error": response.error},
            )

        parser = ResponseParser()
        parsed = parser.parse(response.content)

        return ReasoningOutput(
            insight_type=parsed.insight_type,
            diagnosis=parsed.diagnosis,
            hypothesis=parsed.hypothesis,
            confidence=parsed.confidence,
            recommended_actions=parsed.recommended_actions,
            evidence=parsed.evidence,
            alternative_hypotheses=parsed.alternative_hypotheses,
            learning_notes=parsed.learning_notes,
            raw_response=response.content,
            steps=[ReasoningStep(
                step_name="single_step",
                input={"context_size": len(str(context))},
                output=parsed.to_dict(),
                confidence=parsed.confidence,
                reasoning="Single-step LLM reasoning",
            )],
        )

    def _llm_step(
        self,
        step_name: str,
        context: dict[str, Any],
        base_prompt: str,
        previous_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行单步 LLM 推理."""
        step_prompt = self.STEP_PROMPTS.get(step_name, "Analyze the data.")
        if previous_output:
            step_prompt = f"Previous analysis: {previous_output}\n\n{step_prompt}"

        response = self._llm_client.generate(step_prompt, context)
        if response.success:
            return {"content": response.content, "step": step_name}
        return {"error": response.error, "step": step_name}

    def _build_output(
        self,
        steps: list[ReasoningStep],
        diagnosis: dict[str, Any],
        hypothesis: dict[str, Any],
        action: dict[str, Any],
        confidence: dict[str, Any],
    ) -> ReasoningOutput:
        """从多步结果构建 ReasoningOutput."""
        return ReasoningOutput(
            insight_type="PATTERN",
            diagnosis=str(diagnosis.get("content", "")),
            hypothesis=str(hypothesis.get("content", "")),
            confidence=0.7,
            recommended_actions=[],
            evidence=[],
            steps=steps,
            learning_notes=str(confidence.get("content", "")),
            metadata={"multi_step": True},
        )

    def _rule_based_fallback(self, context: dict[str, Any]) -> ReasoningOutput:
        """规则降级 — LLM 不可用时的规则推理."""
        from ..agent_reasoning import ReasoningContext, ReasoningEngine

        engine = ReasoningEngine()
        metrics = context.get("metrics", {})

        rc = ReasoningContext(
            metrics=metrics,
            cycle=context.get("cycle", 0),
        )

        insights = engine.reason(rc)

        if insights:
            main = insights[0]
            return ReasoningOutput(
                insight_type=main.insight_type.value.upper(),
                diagnosis=main.description,
                hypothesis=main.reasoning,
                confidence=main.confidence,
                recommended_actions=[{
                    "action_type": main.suggested_action.split(":")[0].strip() if main.suggested_action else "MONITOR",
                    "parameters": {},
                    "reasoning": main.reasoning,
                    "expected_impact": main.description,
                    "risk": "low",
                }],
                evidence=main.evidence,
                metadata={"fallback": "rule_based"},
            )

        return ReasoningOutput(
            insight_type="NORMAL",
            diagnosis="No significant signals detected",
            confidence=0.5,
            metadata={"fallback": "rule_based"},
        )

    def reset(self) -> None:
        self._chain_count = 0