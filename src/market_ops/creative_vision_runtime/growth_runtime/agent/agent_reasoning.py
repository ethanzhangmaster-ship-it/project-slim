"""E13.7.2 Agent Reasoning — 推理引擎 (规则 + LLM).

Agent 的核心推理能力:
  - ReasoningEngine: 规则驱动的推理引擎 (确定性, 快速)
  - LLMReasoningEngine: LLM 增强的推理引擎 (高级, 理解力强)

推理流程:
  Observation[] + Memory → ReasoningEngine → Insight[]
  Observation[] + Memory → LLMReasoningEngine → Insight[] (LLM enhanced)

设计原则:
  - LLM 是高级推理层，不替代现有 Decision Engine
  - 规则引擎作为 fallback，确保 LLM 不可用时系统仍正常运行
  - LLM 推理结果通过 Insight 模型与现有系统对接

连接:
  Agent Reasoning → Agent Core → Agent Planner
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_memory import (
    EpisodicMemory,
    SemanticMemory,
    WorkingMemory,
)
from .agent_models import (
    Insight,
    InsightType,
    Observation,
)


# ═══════════════════════════════════════════════════════════════
# Reasoning Context
# ═══════════════════════════════════════════════════════════════


class ReasoningContext:
    """推理上下文 — 聚合推理所需的所有信息.

    Attributes:
        observations: 当前观察
        working_memory: 工作记忆
        episodic_memory: 情景记忆
        semantic_memory: 语义记忆
        metrics: 当前指标
        active_goals: 当前目标
        cycle: 当前循环
    """

    def __init__(
        self,
        observations: list[Observation] | None = None,
        working_memory: WorkingMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
        metrics: dict[str, Any] | None = None,
        active_goals: list[str] | None = None,
        cycle: int = 0,
    ):
        self.observations = observations or []
        self.working_memory = working_memory
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.metrics = metrics or {}
        self.active_goals = active_goals or []
        self.cycle = cycle


# ═══════════════════════════════════════════════════════════════
# Reasoning Engine
# ═══════════════════════════════════════════════════════════════


class ReasoningEngine:
    """推理引擎 — 从观察和记忆中生成洞察.

    推理步骤:
      1. 模式识别: 从观察中识别信号
      2. 记忆检索: 从记忆中检索相关经验
      3. 因果推理: 连接信号和结果
      4. 洞察生成: 输出可执行的洞察

    用法:
        engine = ReasoningEngine(
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
        )
        insights = engine.reason(context)
        for insight in insights:
            print(f"{insight.title}: {insight.description}")
    """

    # 信号检测阈值
    FATIGUE_THRESHOLD = 0.7          # 素材疲劳阈值
    ROAS_DECLINE_THRESHOLD = 0.3     # ROAS 下降阈值
    SPEND_ANOMALY_THRESHOLD = 0.5    # 花费异常阈值
    CTR_DECLINE_THRESHOLD = 0.15     # CTR 下降阈值

    def __init__(
        self,
        working_memory: WorkingMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
    ):
        self._working_memory = working_memory
        self._episodic_memory = episodic_memory
        self._semantic_memory = semantic_memory
        self._insight_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def reason(self, context: ReasoningContext) -> list[Insight]:
        """执行推理，生成洞察列表.

        Args:
            context: 推理上下文

        Returns:
            list[Insight]: 洞察列表
        """
        insights: list[Insight] = []

        # 1. 模式识别
        insights.extend(self._detect_patterns(context))

        # 2. 异常检测
        insights.extend(self._detect_anomalies(context))

        # 3. 记忆检索
        insights.extend(self._retrieve_memories(context))

        # 4. 因果推理
        insights.extend(self._causal_reasoning(context))

        self._insight_count += len(insights)
        return insights

    # ── 模式识别 ──────────────────────────────────────────────

    def _detect_patterns(self, context: ReasoningContext) -> list[Insight]:
        """从观察中识别模式."""
        insights = []

        # 素材疲劳检测
        fatigue = self._check_creative_fatigue(context)
        if fatigue:
            insights.append(fatigue)

        # ROAS 趋势检测
        roas_trend = self._check_roas_trend(context)
        if roas_trend:
            insights.append(roas_trend)

        # 赢家素材检测
        winner = self._check_winner_creative(context)
        if winner:
            insights.append(winner)

        return insights

    def _check_creative_fatigue(self, context: ReasoningContext) -> Insight | None:
        """检测素材疲劳."""
        fatigue = context.metrics.get("creative_fatigue", 0)
        ctr_change = context.metrics.get("ctr_change", 0)

        if fatigue >= self.FATIGUE_THRESHOLD:
            return Insight(
                insight_type=InsightType.THREAT,
                title="素材疲劳警告",
                description=f"素材疲劳度 {fatigue:.0%}，CTR 变化 {ctr_change:+.0%}",
                reasoning=f"Creative fatigue at {fatigue:.0%} exceeds threshold {self.FATIGUE_THRESHOLD:.0%}",
                confidence=min(0.95, fatigue),
                evidence=[f"fatigue={fatigue:.2f}", f"ctr_change={ctr_change:.2f}"],
                suggested_action="MUTATE_CREATIVE: 生成新 DNA 变体",
                urgency=fatigue,
            )

        return None

    def _check_roas_trend(self, context: ReasoningContext) -> Insight | None:
        """检测 ROAS 趋势."""
        roas = context.metrics.get("roas", 1.0)
        roas_change = context.metrics.get("roas_change", 0)

        if roas_change < -self.ROAS_DECLINE_THRESHOLD:
            return Insight(
                insight_type=InsightType.THREAT,
                title="ROAS 下降警告",
                description=f"ROAS {roas:.2f}，变化 {roas_change:+.0%}",
                reasoning=f"ROAS declined by {roas_change:+.0%}, exceeds threshold",
                confidence=min(0.9, abs(roas_change)),
                evidence=[f"roas={roas:.2f}", f"roas_change={roas_change:.2f}"],
                suggested_action="REDUCE_BUDGET: 降低预算 20%",
                urgency=abs(roas_change),
            )

        if roas_change > 0.3:
            return Insight(
                insight_type=InsightType.OPPORTUNITY,
                title="ROAS 上升机会",
                description=f"ROAS {roas:.2f}，变化 {roas_change:+.0%}",
                reasoning=f"ROAS improved by {roas_change:+.0%}, opportunity to scale",
                confidence=min(0.85, roas_change),
                evidence=[f"roas={roas:.2f}", f"roas_change={roas_change:.2f}"],
                suggested_action="SCALE_BUDGET: 增加预算 20%",
                urgency=0.6,
            )

        return None

    def _check_winner_creative(self, context: ReasoningContext) -> Insight | None:
        """检测赢家素材."""
        top_ctr = context.metrics.get("top_creative_ctr", 0)
        avg_ctr = context.metrics.get("avg_ctr", 0.02)

        if avg_ctr > 0 and top_ctr > avg_ctr * 2:
            return Insight(
                insight_type=InsightType.OPPORTUNITY,
                title="赢家素材发现",
                description=f"顶部素材 CTR {top_ctr:.1%}，远超平均 {avg_ctr:.1%}",
                reasoning=f"Top creative CTR ({top_ctr:.1%}) is {top_ctr/avg_ctr:.1f}x average",
                confidence=0.8,
                evidence=[f"top_ctr={top_ctr:.4f}", f"avg_ctr={avg_ctr:.4f}"],
                suggested_action="MUTATE_CREATIVE: 基于赢家生成变体",
                urgency=0.7,
            )

        return None

    # ── 异常检测 ──────────────────────────────────────────────

    def _detect_anomalies(self, context: ReasoningContext) -> list[Insight]:
        """检测异常."""
        insights = []

        # 花费异常
        spend = context.metrics.get("spend", 0)
        spend_change = context.metrics.get("spend_change", 0)
        if abs(spend_change) > self.SPEND_ANOMALY_THRESHOLD:
            insights.append(Insight(
                insight_type=InsightType.ANOMALY,
                title="花费异常",
                description=f"花费变化 {spend_change:+.0%}，当前 ${spend:.0f}",
                reasoning=f"Spend changed by {spend_change:+.0%}, may indicate issue",
                confidence=0.7,
                evidence=[f"spend={spend:.0f}", f"spend_change={spend_change:.2f}"],
                suggested_action="MONITOR: 监控花费趋势",
                urgency=0.5,
            ))

        # 安装异常
        installs_change = context.metrics.get("installs_change", 0)
        if abs(installs_change) > 0.5:
            insights.append(Insight(
                insight_type=InsightType.ANOMALY,
                title="安装量异常",
                description=f"安装量变化 {installs_change:+.0%}",
                reasoning=f"Installs changed by {installs_change:+.0%}, investigation needed",
                confidence=0.65,
                evidence=[f"installs_change={installs_change:.2f}"],
                suggested_action="MONITOR: 检查归因数据",
                urgency=0.6,
            ))

        return insights

    # ── 记忆检索 ──────────────────────────────────────────────

    def _retrieve_memories(self, context: ReasoningContext) -> list[Insight]:
        """从记忆系统中检索相关经验."""
        insights = []

        # 工作记忆: 最近的观察
        if self._working_memory:
            recent = self._working_memory.get_recent(5)
            if recent:
                summary = " | ".join(e.content[:50] for e in recent)
                insights.append(Insight(
                    insight_type=InsightType.CONFIRMATION,
                    title="近期观察回顾",
                    description=f"近期记忆: {summary}",
                    reasoning="Reviewing recent working memory",
                    confidence=0.6,
                    evidence=[e.content[:50] for e in recent],
                    suggested_action="",
                    urgency=0.3,
                ))

        # 语义记忆: 相关持久知识
        if self._semantic_memory:
            # 查找与当前指标相关的知识
            for key in ["fatigue", "roas", "ctr"]:
                if key in str(context.metrics).lower():
                    knowledge = self._semantic_memory.query(key, n=3)
                    for k in knowledge:
                        insights.append(Insight(
                            insight_type=InsightType.PATTERN,
                            title=f"相关知识: {k.concept}",
                            description=k.description,
                            reasoning=f"Semantic memory: {k.concept} (confidence: {k.confidence:.0%})",
                            confidence=k.confidence,
                            evidence=[f"evidence_count={k.evidence_count}"],
                            suggested_action="",
                            urgency=0.4,
                        ))

        return insights

    # ── 因果推理 ──────────────────────────────────────────────

    def _causal_reasoning(self, context: ReasoningContext) -> list[Insight]:
        """因果推理 — 连接信号和结果."""
        insights = []

        # 检查: 疲劳 + ROAS 下降 → 素材问题
        fatigue = context.metrics.get("creative_fatigue", 0)
        roas_change = context.metrics.get("roas_change", 0)
        payer_quality = context.metrics.get("payer_quality", 0.5)

        if fatigue > 0.6 and roas_change < 0 and payer_quality > 0.5:
            insights.append(Insight(
                insight_type=InsightType.PATTERN,
                title="因果分析: 素材疲劳导致 ROAS 下降",
                description="素材已疲劳，但付费用户质量仍好，问题在素材而非产品",
                reasoning=(
                    f"Creative fatigue ({fatigue:.0%}) + ROAS decline ({roas_change:+.0%}) "
                    f"+ stable payer quality ({payer_quality:.0%}) → Creative issue, not product"
                ),
                confidence=0.85,
                evidence=[
                    f"fatigue={fatigue:.2f}",
                    f"roas_change={roas_change:.2f}",
                    f"payer_quality={payer_quality:.2f}",
                ],
                suggested_action="MUTATE_CREATIVE: 生成素材变体，保持产品定位",
                urgency=0.75,
            ))

        # 检查: 赢家素材 + 历史记忆 → 放大策略
        if self._episodic_memory:
            top_ctr = context.metrics.get("top_creative_ctr", 0)
            if top_ctr > 0.05:
                similar = self._episodic_memory.find_similar("creative winner scale")
                if similar:
                    insights.append(Insight(
                        insight_type=InsightType.CONFIRMATION,
                        title="历史验证: 赢家素材放大策略有效",
                        description=f"历史上 {len(similar)} 次类似情况，放大策略均有效",
                        reasoning="Historical episodes confirm winner scaling strategy",
                        confidence=0.75,
                        evidence=[f"similar_episodes={len(similar)}"],
                        suggested_action="SCALE_BUDGET: 基于赢家素材增加预算",
                        urgency=0.6,
                    ))

        return insights

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def insight_count(self) -> int:
        return self._insight_count

    def reset(self) -> None:
        self._insight_count = 0


# ═══════════════════════════════════════════════════════════════
# LLM Reasoning Engine
# ═══════════════════════════════════════════════════════════════


class LLMReasoningEngine:
    """LLM 增强推理引擎 — 高级推理层.

    在规则引擎之上增加 LLM 推理能力:
      - 理解复杂增长问题 (跨平台、跨市场)
      - 综合多个 Memory / Knowledge / Reality Signal
      - 生成新的策略假设
      - 自主拆解目标

    架构:
      Reality Data → Context Builder → LLM Reasoner → Reasoning Output → Agent Planner

    如果 LLM 不可用，自动降级为规则引擎。

    用法:
        engine = LLMReasoningEngine(
            llm_client=create_llm_client(LLMProvider.MOCK),
            working_memory=wm,
            episodic_memory=em,
            semantic_memory=sm,
        )
        insights = engine.reason(context)
    """

    def __init__(
        self,
        llm_client: Any = None,
        working_memory: WorkingMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
        llm_memory: Any = None,
        use_llm: bool = True,
    ):
        # LLM 组件
        self._llm_client = llm_client
        self._llm_memory = llm_memory
        self._use_llm = use_llm

        # 规则引擎 (fallback)
        self._rule_engine = ReasoningEngine(
            working_memory=working_memory,
            episodic_memory=episodic_memory,
            semantic_memory=semantic_memory,
        )

        # 记忆引用
        self._working_memory = working_memory
        self._episodic_memory = episodic_memory
        self._semantic_memory = semantic_memory

        # 统计
        self._llm_call_count: int = 0
        self._rule_fallback_count: int = 0
        self._insight_count: int = 0

    # ── Properties ────────────────────────────────────────────

    @property
    def insight_count(self) -> int:
        return self._insight_count

    @property
    def llm_call_count(self) -> int:
        return self._llm_call_count

    @property
    def rule_fallback_count(self) -> int:
        return self._rule_fallback_count

    # ── 主入口 ────────────────────────────────────────────────

    def reason(self, context: ReasoningContext) -> list[Insight]:
        """执行推理 - LLM 增强 + 规则 fallback.

        Args:
            context: 推理上下文

        Returns:
            list[Insight]: 洞察列表
        """
        insights: list[Insight] = []

        # 尝试 LLM 推理
        if self._use_llm and self._llm_client:
            llm_insights = self._reason_with_llm(context)
            if llm_insights:
                insights.extend(llm_insights)
                self._llm_call_count += 1
                self._insight_count += len(insights)
                return insights

        # Fallback: 规则引擎
        self._rule_fallback_count += 1
        rule_insights = self._rule_engine.reason(context)
        insights.extend(rule_insights)
        self._insight_count += len(insights)
        return insights

    def _reason_with_llm(self, context: ReasoningContext) -> list[Insight]:
        """使用 LLM 进行推理."""
        try:
            from .context.growth_context import GrowthContextBuilder
            from .context.context_retriever import ContextRetriever
            from .llm.prompt_builder import PromptBuilder, GrowthContextPrompt
            from .llm.reasoning_chain import ReasoningChain
            from .llm.response_parser import ResponseParser

            # 1. 构建 Growth Context
            builder = GrowthContextBuilder()
            builder.with_cycle(context.cycle)

            if context.metrics:
                builder.with_metrics(context.metrics)

            if self._semantic_memory or self._episodic_memory:
                builder.with_memory(
                    semantic_memory=self._semantic_memory,
                    episodic_memory=self._episodic_memory,
                )

            if context.active_goals:
                builder.with_goals([
                    {"title": g, "priority": "medium", "progress": 0}
                    for g in context.active_goals
                ])

            growth_ctx = builder.build()

            # 2. 构建 Prompt
            prompt_builder = PromptBuilder()
            prompt_ctx = GrowthContextPrompt(
                metrics=growth_ctx.metrics.to_dict(),
                creative_state=growth_ctx.creative.to_dict(),
                pattern_memories=growth_ctx.pattern_memories,
                strategy_memories=growth_ctx.strategy_memories,
                failure_memories=growth_ctx.failure_memories,
                knowledge=growth_ctx.knowledge,
                recent_actions=growth_ctx.past_actions,
                active_goals=growth_ctx.active_goals,
                cycle=context.cycle,
            )

            # 注入 LLM 经验
            if self._llm_memory:
                try:
                    exp_context = self._llm_memory.to_prompt_context(
                        query=str(context.metrics),
                        top_k=3,
                    )
                    prompt_ctx.pattern_memories.append({
                        "concept": "LLM Experience",
                        "description": exp_context,
                        "confidence": 0.8,
                    })
                except Exception:
                    pass

            prompt = prompt_builder.build(prompt_ctx)

            # 3. 执行推理链
            chain = ReasoningChain(llm_client=self._llm_client, use_multi_step=False)
            reasoning_output = chain.reason(
                context=growth_ctx.to_prompt_context(),
                prompt=prompt,
            )

            # 4. 转换为 Insights
            insights = reasoning_output.to_insights()

            # 5. 记录 LLM 经验
            if self._llm_memory:
                try:
                    from .llm.llm_memory import ReasoningExperience
                    experience = ReasoningExperience(
                        insight_type=reasoning_output.insight_type,
                        diagnosis=reasoning_output.diagnosis,
                        hypothesis=reasoning_output.hypothesis,
                        confidence=reasoning_output.confidence,
                        actions_taken=[a.get("action_type", "") for a in reasoning_output.recommended_actions],
                        evidence=reasoning_output.evidence,
                        learning=reasoning_output.learning_notes,
                    )
                    self._llm_memory.record(experience)
                except Exception:
                    pass

            return insights

        except Exception:
            # LLM 推理失败，降级
            return []

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "llm_call_count": self._llm_call_count,
            "rule_fallback_count": self._rule_fallback_count,
            "insight_count": self._insight_count,
            "rule_engine_insight_count": self._rule_engine.insight_count,
            "use_llm": self._use_llm,
            "has_llm_client": self._llm_client is not None,
            "has_llm_memory": self._llm_memory is not None,
        }

    def reset(self) -> None:
        self._rule_engine.reset()
        self._llm_call_count = 0
        self._rule_fallback_count = 0
        self._insight_count = 0