"""E14.4 Creative Agent — 创意智能 Agent (完整管道).

Creative Agent 是多 Agent 组织中的专业 Agent，负责创意素材的全链路智能:

E14.4.1 核心循环:
  1. Analyze: 分析素材表现 → 识别赢家/疲劳/潜力
  2. Extract DNA: 提取创意 DNA 画像
  3. Strategize: 生成创意策略 (变体/缩放/暂停)
  4. Learn: 记录经验 → 反馈学习

E14.4.2 策略管道:
  UA Signal → Opportunity → Strategy → Plan → Evaluate

E14.4.3 执行管道:
  Plan → Action → Generate → Experiment → Rollout → UA Agent

完整闭环:
  UA Agent → Creative Fatigue → Creative Opportunity → Creative Strategy
  → Creative Plan → Creative Execute → E11 Evolution → New Creatives
  → UA Test → Feedback Loop → Automonous Creative Growth Loop

与 Supervisor 的交互:
  Supervisor → Creative Agent: 请求创意分析 (TASK/REQUEST)
  Creative Agent → Supervisor: 返回创意推荐 (TASK_RESULT/RESPONSE)

与 UA Agent 的交互:
  UA Agent → Creative Agent: 请求创意分析/变体 (REQUEST_CREATIVE_ANALYSIS)
  Creative Agent → UA Agent: 返回创意诊断/变体 (CREATIVE_VARIANTS_READY)

设计原则:
  - 继承 E14.1 通信协议
  - 集成 E14.2 Supervisor 任务分配
  - 复用 E11 Creative Evolution Engine (Genome/Mutation/CLIP)
  - 确定性、可解释、可追溯
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import (
    AgentIdentity,
    AgentRole,
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageStatus,
    StandardMessageType,
    create_creative_agent_identity,
)
from ..communication.agent_registry import AgentRegistry, AgentStatus
from ..communication.message_bus import MessageBus
from ..communication.collaboration import CollaborationEngine

from .analyzer import (
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosis,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    CreativeAnalysisReport,
    CreativeThresholds,
    DEFAULT_CREATIVE_THRESHOLDS,
    create_creative_analyzer,
)
from .dna_engine import (
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    DNAComparisonResult,
    WinnerDNAReport,
    create_dna_engine,
)
from .memory import (
    CreativeMemory,
    CreativeDecisionRecord,
    CreativeDecisionOutcome,
    CreativeActionType,
    CreativeExperienceEntry,
    CreativeDNAMemoryEntry,
    create_creative_memory,
)
from .opportunity import (
    CreativeOpportunityEngine,
    CreativeOpportunity,
    CreativeOpportunityType,
    CreativeSignal,
    OpportunityPriority,
    OpportunityReport,
    create_opportunity_engine,
)
from .strategy import (
    CreativeStrategyEngine,
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
    StrategyReport,
    create_strategy_engine,
)
from .planner import (
    CreativePlanner,
    CreativePlan,
    MutationConfig,
    ExperimentConfig,
    ExperimentType,
    PlanStatus,
    BatchPlan,
    create_planner,
)
from .evaluator import (
    CreativeEvaluator,
    CreativeStrategyOutcome,
    CreativeMetricsSnapshot,
    StrategyEvaluation,
    StrategyOutcomeType,
    EvaluationReport,
    create_evaluator,
)
from .executor import (
    CreativeExecutor,
    CreativeExecutionAction,
    ExecutionActionType,
    ExecutionStatus,
    ExecutionParameters,
    ExecutionBatch,
    create_executor,
)
from .generator_bridge import (
    GeneratorBridge,
    CreativeVariant,
    GenerationResult,
    VariantStatus,
    GeneratorType,
    create_generator_bridge,
)
from .experiment import (
    ExperimentManager,
    CreativeExperiment,
    ExperimentStatus,
    ExperimentResult,
    VariantMetrics,
    VariantGroupType,
    ExperimentReport,
    create_experiment_manager,
)
from .rollout import (
    RolloutController,
    RolloutDecision,
    RolloutStrategy,
    RolloutStatus,
    RolloutTrigger,
    RolloutReport,
    create_rollout_controller,
)

# E14.4.4 学习模块
from .learning import (
    RewardModel,
    CreativeReward,
    DNAReward,
    MutationReward,
    RewardConfig,
    create_reward_model,
    PatternMiner,
    CreativePattern,
    DNAPattern,
    PatternCategory,
    PatternConfidence,
    MiningReport,
    create_pattern_miner,
    StrategyMemory,
    StrategyRecord,
    ContextProfile,
    StrategyEffectiveness,
    StrategyMemoryReport,
    create_strategy_memory,
    MutationLearning,
    MutationRecord,
    GeneCategory,
    MutationEffectiveness,
    MutationPriority,
    MutationLearningReport,
    create_mutation_learning,
    CreativePolicy,
    PolicyDecision,
    PolicyContext,
    PolicyConfidence,
    PolicyAction,
    PolicyReport,
    create_creative_policy,
)


# ═══════════════════════════════════════════════════════════════
# Agent State
# ═══════════════════════════════════════════════════════════════


class CreativeAgentState(str, Enum):
    """Creative Agent 状态."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    STRATEGIZING = "strategizing"
    EVOLVING = "evolving"
    EXECUTING = "executing"
    LEARNING = "learning"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeRecommendation:
    """创意推荐 — Creative Agent 的输出.

    Attributes:
        recommendation_id: 推荐 ID
        creative_id: 创意 ID
        diagnosis: 诊断结果
        dna_profile: DNA 画像 (如果已提取)
        action: 推荐动作
        priority: 优先级
        expected_impact: 预期影响
        summary: 推荐摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    diagnosis: CreativeDiagnosis | None = None
    dna_profile: CreativeDNAProfile | None = None
    action: CreativeActionType = CreativeActionType.UNKNOWN
    priority: str = "normal"
    expected_impact: str = ""
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "creative_id": self.creative_id,
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "dna_profile": self.dna_profile.to_dict() if self.dna_profile else None,
            "action": self.action.value,
            "priority": self.priority,
            "expected_impact": self.expected_impact,
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class CreativeReport:
    """创意报告 — 批量分析结果.

    Attributes:
        report_id: 报告 ID
        recommendations: 推荐列表
        analysis_report: 分析报告
        winner_dna_report: 赢家 DNA 报告
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recommendations: list[CreativeRecommendation] = field(default_factory=list)
    analysis_report: CreativeAnalysisReport | None = None
    winner_dna_report: WinnerDNAReport | None = None
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "analysis_report": self.analysis_report.to_dict() if self.analysis_report else None,
            "winner_dna_report": self.winner_dna_report.to_dict() if self.winner_dna_report else None,
            "summary": self.summary,
            "recommendation_count": len(self.recommendations),
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Creative Agent
# ═══════════════════════════════════════════════════════════════


class CreativeAgent:
    """Creative Agent — 创意智能 Agent.

    职责:
      1. 分析创意素材表现
      2. 提取创意 DNA 画像
      3. 识别赢家、疲劳、潜力素材
      4. 生成创意策略推荐
      5. 与 UA Agent 协作 (接收分析请求、返回变体)

    用法:
        agent = create_creative_agent()
        rec = agent.analyze_creative({
            "creative_id": "C102", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82,
        })
        dna = agent.extract_dna(creative_id="C102", hook="before_after", visual="fantasy")
    """

    def __init__(
        self,
        identity: AgentIdentity | None = None,
        thresholds: CreativeThresholds | None = None,
        gene_weights: dict[str, float] | None = None,
        generator_type: GeneratorType = GeneratorType.MOCK,
    ):
        self._identity = identity or create_creative_agent_identity()
        self._state = CreativeAgentState.IDLE

        # E14.4.1 核心模块
        self._analyzer = CreativeAnalyzer(thresholds)
        self._dna_engine = DNAEngine(gene_weights)
        self._memory = CreativeMemory()

        # E14.4.2 策略模块
        self._opportunity_engine = CreativeOpportunityEngine(
            memory=self._memory, dna_engine=self._dna_engine,
        )
        self._strategy_engine = CreativeStrategyEngine(
            memory=self._memory, dna_engine=self._dna_engine,
        )
        self._planner = CreativePlanner()
        self._evaluator = CreativeEvaluator(memory=self._memory)

        # E14.4.3 执行模块
        self._executor = CreativeExecutor()
        self._generator_bridge = GeneratorBridge(generator_type=generator_type)
        self._experiment_manager = ExperimentManager()
        self._rollout_controller = RolloutController()

        # E14.4.4 学习模块
        self._reward_model = RewardModel(memory=self._memory)
        self._pattern_miner = PatternMiner(memory=self._memory)
        self._strategy_memory = StrategyMemory(memory=self._memory)
        self._mutation_learning = MutationLearning(memory=self._memory)
        self._policy = CreativePolicy(
            memory=self._memory,
            pattern_miner=self._pattern_miner,
            strategy_memory=self._strategy_memory,
            mutation_learning=self._mutation_learning,
        )

        # 通信组件 (延迟初始化)
        self._bus: MessageBus | None = None
        self._registry: AgentRegistry | None = None
        self._collaboration: CollaborationEngine | None = None

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    @property
    def state(self) -> CreativeAgentState:
        return self._state

    @property
    def agent_id(self) -> str:
        return self._identity.agent_id

    # ── 核心分析 ──────────────────────────────────────────────

    def analyze_creative(
        self,
        metrics: dict[str, Any] | CreativeMetrics,
    ) -> CreativeRecommendation:
        """分析单个创意素材.

        Args:
            metrics: 创意指标 (dict 或 CreativeMetrics)

        Returns:
            CreativeRecommendation: 创意推荐
        """
        self._state = CreativeAgentState.ANALYZING

        if isinstance(metrics, dict):
            metrics = CreativeMetrics.from_dict(metrics)

        # 1. 分析
        diagnosis = self._analyzer.analyze(metrics)

        # 2. 确定推荐动作
        action = self._diagnosis_to_action(diagnosis.diagnosis_type)

        # 3. 记录决策
        self._memory.record_decision(
            creative_id=metrics.creative_id,
            diagnosis_type=diagnosis.diagnosis_type,
            diagnosis_severity=diagnosis.severity,
            action_type=action,
            confidence=diagnosis.confidence,
            before_metrics=metrics.to_dict(),
        )

        rec = CreativeRecommendation(
            creative_id=metrics.creative_id,
            diagnosis=diagnosis,
            action=action,
            priority=self._severity_to_priority(diagnosis.severity),
            expected_impact=diagnosis.expected_impact,
            summary=diagnosis.summary,
        )

        self._state = CreativeAgentState.IDLE
        return rec

    def analyze_creative_batch(
        self,
        metrics_list: list[dict[str, Any] | CreativeMetrics],
    ) -> CreativeReport:
        """批量分析创意素材.

        Args:
            metrics_list: 创意指标列表

        Returns:
            CreativeReport: 创意报告
        """
        self._state = CreativeAgentState.ANALYZING

        parsed = [
            CreativeMetrics.from_dict(m) if isinstance(m, dict) else m
            for m in metrics_list
        ]

        # 批量分析
        analysis_report = self._analyzer.analyze_batch(parsed)

        # 生成推荐
        recommendations = []
        for diagnosis in analysis_report.diagnoses:
            action = self._diagnosis_to_action(diagnosis.diagnosis_type)
            recommendations.append(CreativeRecommendation(
                creative_id=diagnosis.creative_id,
                diagnosis=diagnosis,
                action=action,
                priority=self._severity_to_priority(diagnosis.severity),
                expected_impact=diagnosis.expected_impact,
                summary=diagnosis.summary,
            ))

        # 赢家 DNA 分析
        winner_dna_report = None
        winner_dnas = [
            entry.dna for entry in self._memory.get_winner_dnas()
            if entry.dna is not None
        ]
        if winner_dnas:
            winner_dna_report = self._dna_engine.extract_winner_dna(winner_dnas)

        report = CreativeReport(
            recommendations=recommendations,
            analysis_report=analysis_report,
            winner_dna_report=winner_dna_report,
            summary=analysis_report.summary,
        )

        self._state = CreativeAgentState.IDLE
        return report

    def quick_analysis(
        self,
        creative_id: str,
        roas: float = 0.0,
        ctr: float = 0.0,
        fatigue: float = 0.0,
        frequency: float = 0.0,
        spend: float = 0.0,
        impressions: int = 0,
        days_running: int = 0,
        **kwargs: Any,
    ) -> CreativeRecommendation:
        """快捷分析 — 从关键指标直接诊断.

        Args:
            creative_id: 创意 ID
            roas: ROAS
            ctr: 点击率
            fatigue: 疲劳度
            frequency: 频次
            spend: 花费
            impressions: 展示量
            days_running: 运行天数
            **kwargs: 其他指标

        Returns:
            CreativeRecommendation
        """
        metrics = CreativeMetrics(
            creative_id=creative_id,
            roas=roas,
            ctr=ctr,
            fatigue=fatigue,
            frequency=frequency,
            spend=spend,
            impressions=impressions,
            days_running=days_running,
            **kwargs,
        )
        return self.analyze_creative(metrics)

    # ── DNA 操作 ──────────────────────────────────────────────

    def extract_dna(
        self,
        creative_id: str,
        creative_name: str = "",
        hook: str = "",
        visual: str = "",
        gameplay: str = "",
        monetization: str = "",
        emotion: str = "",
        audience: str = "",
        context: str = "",
        fitness: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> CreativeDNAProfile:
        """提取创意 DNA 画像.

        Args:
            creative_id: 创意 ID
            creative_name: 创意名称
            hook: Hook 类型
            visual: 视觉风格
            gameplay: 玩法焦点
            monetization: 变现方式
            emotion: 情绪驱动
            audience: 目标受众
            context: 投放场景
            fitness: 表现指标
            **kwargs: 其他参数

        Returns:
            CreativeDNAProfile
        """
        self._state = CreativeAgentState.EXTRACTING

        dna = self._dna_engine.extract_dna(
            creative_id=creative_id,
            creative_name=creative_name,
            hook=hook,
            visual=visual,
            gameplay=gameplay,
            monetization=monetization,
            emotion=emotion,
            audience=audience,
            context=context,
            fitness=fitness,
            **kwargs,
        )

        # 存储到记忆
        is_winner = fitness and fitness.get("roas", 0) >= 1.5
        self._memory.store_dna(dna, is_winner=is_winner)

        # 记录决策
        self._memory.record_decision(
            creative_id=creative_id,
            action_type=CreativeActionType.EXTRACT_DNA,
            dna_id=dna.dna_id,
        )

        self._state = CreativeAgentState.IDLE
        return dna

    def compare_dna(
        self,
        dna_a: CreativeDNAProfile,
        dna_b: CreativeDNAProfile,
    ) -> DNAComparisonResult:
        """比较两个 DNA 画像."""
        return self._dna_engine.compare_dna(dna_a, dna_b)

    def extract_winner_dna(self) -> WinnerDNAReport:
        """提取赢家 DNA 的共同特征."""
        winner_dnas = [
            entry.dna for entry in self._memory.get_winner_dnas()
            if entry.dna is not None
        ]
        return self._dna_engine.extract_winner_dna(winner_dnas)

    def find_similar_dnas(
        self,
        target: CreativeDNAProfile,
        min_similarity: float = 0.5,
    ) -> list[tuple[CreativeDNAProfile, float]]:
        """查找相似的 DNA."""
        return self._dna_engine.find_similar_dnas(target, min_similarity)

    # ── 策略生成 ──────────────────────────────────────────────

    def generate_strategy(
        self,
        creative_id: str,
        diagnosis_type: CreativeDiagnosisType,
    ) -> CreativeRecommendation:
        """根据诊断生成创意策略.

        Args:
            creative_id: 创意 ID
            diagnosis_type: 诊断类型

        Returns:
            CreativeRecommendation
        """
        self._state = CreativeAgentState.STRATEGIZING

        action = self._diagnosis_to_action(diagnosis_type)
        expected_impact = self._estimate_action_impact(action, diagnosis_type)

        rec = CreativeRecommendation(
            creative_id=creative_id,
            action=action,
            priority="high" if diagnosis_type in (
                CreativeDiagnosisType.CREATIVE_FATIGUE,
                CreativeDiagnosisType.UNDERPERFORMER,
            ) else "normal",
            expected_impact=expected_impact,
            summary=f"{diagnosis_type.value} → {action.value}",
        )

        self._state = CreativeAgentState.IDLE
        return rec

    # ── Agent 间通信 ──────────────────────────────────────────

    def handle_ua_request(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """处理来自 UA Agent 的请求.

        Args:
            message: UA Agent 发送的消息

        Returns:
            AgentMessage | None: 响应消息
        """
        if message.standard_type == StandardMessageType.REQUEST_CREATIVE_ANALYSIS:
            return self._handle_creative_analysis_request(message)
        elif message.standard_type == StandardMessageType.REQUEST_CREATIVE_VARIANTS:
            return self._handle_creative_variants_request(message)
        return None

    def _handle_creative_analysis_request(self, message: AgentMessage) -> AgentMessage:
        """处理创意分析请求."""
        body = message.body
        creative_id = body.get("creative_id", "")
        metrics_data = body.get("metrics", {})

        if metrics_data:
            rec = self.analyze_creative(metrics_data)
        elif creative_id:
            # 过滤 creative_id 避免重复传参
            filtered = {k: v for k, v in body.items() if k != "creative_id"}
            rec = self.quick_analysis(creative_id=creative_id, **filtered)
        else:
            rec = CreativeRecommendation(summary="缺少必要参数")

        return AgentMessage.create_response(
            original=message,
            body=rec.to_dict(),
        )

    def _handle_creative_variants_request(self, message: AgentMessage) -> AgentMessage:
        """处理创意变体请求."""
        body = message.body
        creative_id = body.get("creative_id", "")

        # 提取赢家 DNA
        winner_report = self.extract_winner_dna()

        response_body = {
            "creative_id": creative_id,
            "winner_dna_report": winner_report.to_dict(),
            "recommendation": winner_report.recommendation,
        }

        return AgentMessage.create_response(
            original=message,
            body=response_body,
        )

    # ── E14.4.2 策略管道 ──────────────────────────────────────

    def detect_opportunities(
        self,
        signals: list[CreativeSignal | dict[str, Any]],
    ) -> OpportunityReport:
        """检测创意机会 — 从 UA 信号到创意机会.

        Args:
            signals: 创意信号列表

        Returns:
            OpportunityReport: 机会报告
        """
        self._state = CreativeAgentState.STRATEGIZING
        report = self._opportunity_engine.detect_batch(signals)
        self._state = CreativeAgentState.IDLE
        return report

    def generate_strategies(
        self,
        opportunities: list[CreativeOpportunity],
        current_dna_map: dict[str, CreativeDNAProfile] | None = None,
    ) -> StrategyReport:
        """生成创意策略 — 从机会到策略.

        Args:
            opportunities: 创意机会列表
            current_dna_map: creative_id → DNA 映射

        Returns:
            StrategyReport: 策略报告
        """
        self._state = CreativeAgentState.STRATEGIZING
        report = self._strategy_engine.generate_from_opportunities(
            opportunities, current_dna_map,
        )
        self._state = CreativeAgentState.IDLE
        return report

    def plan_creative_batch(
        self,
        strategies: list[CreativeStrategy],
        max_total_variants: int = 50,
    ) -> BatchPlan:
        """规划创意执行 — 从策略到执行计划.

        Args:
            strategies: 策略列表
            max_total_variants: 最大总变体数

        Returns:
            BatchPlan: 批量计划
        """
        self._state = CreativeAgentState.EVOLVING
        batch = self._planner.plan_batch(strategies, max_total_variants)
        self._state = CreativeAgentState.IDLE
        return batch

    def evaluate_creative_strategy(
        self,
        strategy: CreativeStrategy,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
    ) -> CreativeStrategyOutcome:
        """评估创意策略 — 反馈学习.

        Args:
            strategy: 创意策略
            before_metrics: 执行前指标
            after_metrics: 执行后指标

        Returns:
            CreativeStrategyOutcome: 策略结果
        """
        self._state = CreativeAgentState.LEARNING
        outcome = self._evaluator.evaluate(strategy, before_metrics, after_metrics)
        self._state = CreativeAgentState.IDLE
        return outcome

    def run_full_strategy_pipeline(
        self,
        signals: list[dict[str, Any]],
        current_dna_map: dict[str, CreativeDNAProfile] | None = None,
    ) -> dict[str, Any]:
        """运行完整的创意策略管道.

        UA Signal → Opportunity → Strategy → Plan → (等待执行) → Evaluate

        Args:
            signals: 信号字典列表
            current_dna_map: creative_id → DNA 映射

        Returns:
            dict: 管道结果 (opportunities, strategies, plans)
        """
        self._state = CreativeAgentState.STRATEGIZING

        # 1. 检测机会
        opportunity_report = self._opportunity_engine.detect_batch(signals)

        # 2. 生成策略
        strategy_report = self._strategy_engine.generate_from_opportunities(
            opportunity_report.opportunities, current_dna_map,
        )

        # 3. 生成执行计划
        batch_plan = self._planner.plan_batch(strategy_report.strategies)

        self._state = CreativeAgentState.IDLE

        return {
            "opportunities": opportunity_report.to_dict(),
            "strategies": strategy_report.to_dict(),
            "plans": batch_plan.to_dict(),
        }

    # ── E14.4.3 执行管道 ──────────────────────────────────────

    def create_actions_from_batch(
        self,
        plans: list[CreativePlan],
    ) -> ExecutionBatch:
        """从批量计划创建执行动作 — Plan → Action.

        Args:
            plans: 计划列表

        Returns:
            ExecutionBatch: 批量执行结果
        """
        self._state = CreativeAgentState.EXECUTING
        batch = self._executor.create_actions_from_batch(plans)
        self._state = CreativeAgentState.IDLE
        return batch

    def generate_variants(
        self,
        plan: CreativePlan,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile | None = None,
    ) -> GenerationResult:
        """生成创意变体 — 通过 Generator Bridge 调用 E11.

        Args:
            plan: 执行计划
            strategy: 创意策略
            dna: 素材 DNA 画像

        Returns:
            GenerationResult: 生成结果
        """
        self._state = CreativeAgentState.EXECUTING
        result = self._generator_bridge.generate_variants(plan, strategy, dna)
        self._state = CreativeAgentState.IDLE
        return result

    def start_experiment(
        self,
        plan: CreativePlan,
        variant_ids: list[str] | None = None,
        control_creative_id: str | None = None,
    ) -> CreativeExperiment:
        """启动创意实验.

        Args:
            plan: 执行计划
            variant_ids: 变体 ID 列表
            control_creative_id: 对照组素材 ID

        Returns:
            CreativeExperiment: 实验
        """
        self._state = CreativeAgentState.EXECUTING
        experiment = self._experiment_manager.create_experiment(
            plan, variant_ids, control_creative_id,
        )
        self._experiment_manager.start(experiment)
        self._state = CreativeAgentState.IDLE
        return experiment

    def collect_experiment_results(
        self,
        experiment: CreativeExperiment,
        variant_metrics: list[VariantMetrics],
        control_metrics: VariantMetrics | None = None,
    ) -> ExperimentResult:
        """收集实验结果并判定赢家.

        Args:
            experiment: 实验
            variant_metrics: 变体组指标
            control_metrics: 对照组指标

        Returns:
            ExperimentResult: 实验结果
        """
        self._state = CreativeAgentState.LEARNING
        self._experiment_manager.collect_results(experiment, variant_metrics, control_metrics)
        result = self._experiment_manager.determine_winner(experiment)
        self._state = CreativeAgentState.IDLE
        return result

    def evaluate_rollout(
        self,
        experiment: CreativeExperiment,
        variant: VariantMetrics,
        trigger: RolloutTrigger = RolloutTrigger.EXPERIMENT_WINNER,
    ) -> RolloutDecision | None:
        """评估赢家放量 — Winner → Scale.

        Args:
            experiment: 实验
            variant: 变体指标
            trigger: 触发条件

        Returns:
            RolloutDecision | None: 放量决策
        """
        self._state = CreativeAgentState.EXECUTING
        decision = self._rollout_controller.evaluate_winner(experiment, variant, trigger)
        self._state = CreativeAgentState.IDLE
        return decision

    def execute_rollout(self, decision: RolloutDecision) -> bool:
        """执行放量决策."""
        self._state = CreativeAgentState.EXECUTING
        success = self._rollout_controller.execute(decision)
        self._state = CreativeAgentState.IDLE
        return success

    def rollback_rollout(self, decision: RolloutDecision) -> bool:
        """回滚放量."""
        return self._rollout_controller.rollback(decision)

    def run_full_execution_pipeline(
        self,
        plans: list[CreativePlan],
        strategy_map: dict[str, CreativeStrategy] | None = None,
        dna_map: dict[str, CreativeDNAProfile] | None = None,
    ) -> dict[str, Any]:
        """运行完整的创意执行管道.

        Plan → Action → Generate → Experiment → Rollout → UA Action

        Args:
            plans: 执行计划列表
            strategy_map: plan_id → Strategy 映射
            dna_map: creative_id → DNA 映射

        Returns:
            dict: 管道结果 (batch, generation_results, experiments, rollout_decisions)
        """
        self._state = CreativeAgentState.EXECUTING

        # 1. Plan → Action
        batch = self._executor.create_actions_from_batch(plans)

        # 2. Action → Generate (对每个计划)
        generation_results = []
        for plan in plans:
            strategy = strategy_map.get(plan.plan_id) if strategy_map else None
            dna = dna_map.get(plan.creative_id) if dna_map else None
            if strategy:
                result = self._generator_bridge.generate_variants(plan, strategy, dna)
                generation_results.append(result)

        # 3. Generate → Experiment
        experiments = []
        for plan in plans:
            variant_ids = [
                v.variant_id
                for result in generation_results
                for v in result.variants
                if result.plan_id == plan.plan_id
            ]
            experiment = self._experiment_manager.create_experiment(
                plan, variant_ids,
            )
            self._experiment_manager.start(experiment)
            experiments.append(experiment)

        self._state = CreativeAgentState.IDLE

        return {
            "batch": batch.to_dict(),
            "generation_results": [r.to_dict() for r in generation_results],
            "experiments": [e.to_dict() for e in experiments],
            "total_plans": len(plans),
            "total_variants": sum(r.total_generated for r in generation_results),
            "total_experiments": len(experiments),
        }

    # ── 子模块访问 ────────────────────────────────────────────

    def get_analyzer(self) -> CreativeAnalyzer:
        return self._analyzer

    def get_dna_engine(self) -> DNAEngine:
        return self._dna_engine

    def get_memory(self) -> CreativeMemory:
        return self._memory

    def get_opportunity_engine(self) -> CreativeOpportunityEngine:
        return self._opportunity_engine

    def get_strategy_engine(self) -> CreativeStrategyEngine:
        return self._strategy_engine

    def get_planner(self) -> CreativePlanner:
        return self._planner

    def get_evaluator(self) -> CreativeEvaluator:
        return self._evaluator

    def get_executor(self) -> CreativeExecutor:
        return self._executor

    def get_generator_bridge(self) -> GeneratorBridge:
        return self._generator_bridge

    def get_experiment_manager(self) -> ExperimentManager:
        return self._experiment_manager

    def get_rollout_controller(self) -> RolloutController:
        return self._rollout_controller

    # ── E14.4.4 学习模块访问 ──────────────────────────────────

    def get_reward_model(self) -> RewardModel:
        return self._reward_model

    def get_pattern_miner(self) -> PatternMiner:
        return self._pattern_miner

    def get_strategy_memory(self) -> StrategyMemory:
        return self._strategy_memory

    def get_mutation_learning(self) -> MutationLearning:
        return self._mutation_learning

    def get_policy(self) -> CreativePolicy:
        return self._policy

    # ── E14.4.4 学习管道 ──────────────────────────────────────

    def learn_from_experiment(
        self,
        experiment: CreativeExperiment,
        baseline_roas: float | None = None,
    ) -> dict[str, Any]:
        """从实验结果中学习 — 实验完成后的学习闭环.

        流程:
          VariantMetrics → RewardModel → Pattern Mining → Strategy Memory → Policy Update

        Args:
            experiment: 已完成的实验
            baseline_roas: ROAS 基准线

        Returns:
            dict: 学习结果摘要
        """
        self._state = CreativeAgentState.LEARNING

        rewards = []
        # 1. 计算每个变体的奖励
        for vg in experiment.variant_groups:
            if vg.installs > 0:
                reward = self._reward_model.calculate(vg, baseline_roas)
                rewards.append(reward)

        # 2. 记录控制组
        if experiment.control_group and experiment.control_group.installs > 0:
            control_reward = self._reward_model.calculate(experiment.control_group, baseline_roas)
            rewards.append(control_reward)

        # 3. 记录策略执行
        if experiment.plan_id:
            self._strategy_memory.record(
                strategy_type=CreativeStrategyType.REFRESH_CREATIVE,
                context=ContextProfile(),
                outcome=CreativeDecisionOutcome.SUCCESS if experiment.has_winner else CreativeDecisionOutcome.FAILURE,
                reward=sum(r.total_reward for r in rewards) / max(len(rewards), 1),
            )

        # 4. 记录变异学习
        mutation_records = self._mutation_learning.import_from_memory()

        # 5. 生成学习摘要
        avg_reward = sum(r.total_reward for r in rewards) / max(len(rewards), 1)
        mining_report = self._pattern_miner.mine_all()

        self._state = CreativeAgentState.IDLE

        return {
            "experiment_id": experiment.experiment_id,
            "variants_analyzed": len(rewards),
            "avg_reward": round(avg_reward, 4),
            "winner_found": experiment.has_winner,
            "winner_variant_id": experiment.winner_variant_id,
            "mining_report": mining_report.to_dict(),
            "mutation_records_imported": mutation_records,
        }

    def learn_from_batch_experiments(
        self,
        experiments: list[CreativeExperiment],
        baseline_roas: float | None = None,
    ) -> dict[str, Any]:
        """从批量实验结果中学习.

        Args:
            experiments: 已完成实验列表
            baseline_roas: ROAS 基准线

        Returns:
            dict: 批量学习结果
        """
        results = []
        for exp in experiments:
            if exp.is_completed:
                result = self.learn_from_experiment(exp, baseline_roas)
                results.append(result)

        # 生成综合报告
        mining_report = self._pattern_miner.mine_all()
        mutation_report = self._mutation_learning.generate_report()
        strategy_report = self._strategy_memory.generate_report()

        return {
            "experiments_processed": len(results),
            "results": results,
            "mining_report": mining_report.to_dict(),
            "mutation_learning_report": mutation_report.to_dict(),
            "strategy_memory_report": strategy_report.to_dict(),
        }

    def decide_with_policy(
        self,
        game: str = "",
        platform: str = "",
        market: str = "",
        genre: str = "",
        stage: str = "",
        current_roas: float = 0.0,
        current_ctr: float = 0.0,
        current_fatigue: float = 0.0,
        current_frequency: float = 0.0,
        current_ltv: float = 0.0,
        active_creative_count: int = 0,
        creative_id: str = "",
    ) -> PolicyDecision:
        """基于学习结果生成策略决策.

        整合 Pattern Miner + Strategy Memory + Mutation Learning 的
        三层决策结果，输出最优策略动作.

        Args:
            game: 游戏名称
            platform: 平台
            market: 市场
            genre: 游戏类型
            stage: 投放阶段
            current_roas: 当前 ROAS
            current_ctr: 当前 CTR
            current_fatigue: 当前疲劳度
            current_frequency: 当前频次
            current_ltv: 当前 LTV
            active_creative_count: 活跃素材数
            creative_id: 目标素材 ID

        Returns:
            PolicyDecision: 策略决策
        """
        self._state = CreativeAgentState.LEARNING

        context = PolicyContext(
            game=game,
            platform=platform,
            market=market,
            genre=genre,
            stage=stage,
            current_roas=current_roas,
            current_ctr=current_ctr,
            current_fatigue=current_fatigue,
            current_frequency=current_frequency,
            current_ltv=current_ltv,
            active_creative_count=active_creative_count,
            creative_id=creative_id,
        )

        decision = self._policy.decide(context)

        self._state = CreativeAgentState.IDLE
        return decision

    def run_learning_loop(
        self,
        completed_experiments: list[CreativeExperiment] | None = None,
        context: PolicyContext | None = None,
        baseline_roas: float | None = None,
    ) -> dict[str, Any]:
        """运行完整的 E14.4.4 Creative Self-Learning Loop.

        完整闭环:
          1. Learn from Experiments: 从实验结果中计算奖励
          2. Pattern Mining: 从历史赢家中挖掘 DNA 模式
          3. Strategy Memory: 更新策略有效性
          4. Mutation Learning: 更新变异有效性
          5. Policy Decision: 基于学习结果生成决策

        Args:
            completed_experiments: 已完成的实验列表
            context: 当前上下文 (用于生成决策)
            baseline_roas: ROAS 基准线

        Returns:
            dict: 学习循环结果 (rewards, mining, strategies, mutations, decision)
        """
        self._state = CreativeAgentState.LEARNING

        result: dict[str, Any] = {}

        # 1. 从实验学习
        if completed_experiments:
            batch_result = self.learn_from_batch_experiments(completed_experiments, baseline_roas)
            result["experiment_learning"] = batch_result

        # 2. DNA 模式挖掘
        mining_report = self._pattern_miner.mine_all()
        result["mining_report"] = mining_report.to_dict()

        # 3. DNA 级别奖励
        dna_rewards = self._reward_model.calculate_dna_rewards()
        result["dna_rewards"] = [r.to_dict() for r in dna_rewards]

        # 4. Mutation 学习
        mutation_report = self._mutation_learning.generate_report()
        result["mutation_report"] = mutation_report.to_dict()

        # 5. Strategy Memory
        strategy_report = self._strategy_memory.generate_report()
        result["strategy_report"] = strategy_report.to_dict()

        # 6. Policy Decision
        if context:
            decision = self._policy.decide(context)
            result["policy_decision"] = decision.to_dict()
        else:
            result["policy_decision"] = None

        result["summary"] = (
            f"Learning Loop完成: "
            f"挖掘 {mining_report.total_patterns} 个模式, "
            f"DNA奖励 {len(dna_rewards)} 个, "
            f"变异学习 {mutation_report.total_records} 条记录, "
            f"策略记忆 {strategy_report.total_records} 条记录"
        )

        self._state = CreativeAgentState.IDLE
        return result

    def run_full_creative_loop(
        self,
        signals: list[dict[str, Any]],
        context: PolicyContext | None = None,
        current_dna_map: dict[str, CreativeDNAProfile] | None = None,
        baseline_roas: float | None = None,
    ) -> dict[str, Any]:
        """运行完整的 E14.4 Creative Autonomous Growth Loop.

        完整闭环:
          Signal → Opportunity → Strategy → Plan → Execute → Learn → Policy → Better Decisions

        Args:
            signals: 创意信号列表
            context: 策略上下文
            current_dna_map: creative_id → DNA 映射
            baseline_roas: ROAS 基准线

        Returns:
            dict: 完整闭环结果
        """
        self._state = CreativeAgentState.EVOLVING

        # Phase 1: Strategy Pipeline (E14.4.2)
        pipeline_result = self.run_full_strategy_pipeline(signals, current_dna_map)

        # Phase 2: Execution Pipeline (E14.4.3)
        plans = self._planner.get_history()
        if plans:
            strategy_map = {
                s.strategy_id: s for s in self._strategy_engine.get_history()
            }
            execution_result = self.run_full_execution_pipeline(plans, strategy_map, current_dna_map)
        else:
            execution_result = {"total_plans": 0, "total_variants": 0, "total_experiments": 0}

        # Phase 3: Learning Loop (E14.4.4)
        completed = self._experiment_manager.get_completed_experiments()
        learning_result = self.run_learning_loop(
            completed_experiments=completed,
            context=context,
            baseline_roas=baseline_roas,
        )

        self._state = CreativeAgentState.IDLE

        return {
            "strategy_pipeline": pipeline_result,
            "execution_pipeline": execution_result,
            "learning_loop": learning_result,
            "summary": (
                f"完整闭环完成: "
                f"策略 {pipeline_result.get('strategies', {}).get('total_strategies', 0)} 个, "
                f"变体 {execution_result.get('total_variants', 0)} 个, "
                f"实验 {execution_result.get('total_experiments', 0)} 个"
            ),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _diagnosis_to_action(
        self,
        diagnosis_type: CreativeDiagnosisType,
    ) -> CreativeActionType:
        """诊断类型 → 动作类型映射."""
        mapping = {
            CreativeDiagnosisType.CREATIVE_FATIGUE: CreativeActionType.GENERATE_VARIANTS,
            CreativeDiagnosisType.WINNER: CreativeActionType.SCALE_CREATIVE,
            CreativeDiagnosisType.UNDERPERFORMER: CreativeActionType.PAUSE_CREATIVE,
            CreativeDiagnosisType.HIGH_POTENTIAL: CreativeActionType.ANALYZE_PERFORMANCE,
            CreativeDiagnosisType.SATURATED: CreativeActionType.GENERATE_VARIANTS,
            CreativeDiagnosisType.NEW_CREATIVE: CreativeActionType.ANALYZE_PERFORMANCE,
            CreativeDiagnosisType.STABLE: CreativeActionType.ANALYZE_PERFORMANCE,
            CreativeDiagnosisType.UNKNOWN: CreativeActionType.ANALYZE_PERFORMANCE,
        }
        return mapping.get(diagnosis_type, CreativeActionType.UNKNOWN)

    def _severity_to_priority(self, severity: CreativeDiagnosisSeverity) -> str:
        """严重度 → 优先级映射."""
        mapping = {
            CreativeDiagnosisSeverity.CRITICAL: "critical",
            CreativeDiagnosisSeverity.WARNING: "high",
            CreativeDiagnosisSeverity.INFO: "normal",
            CreativeDiagnosisSeverity.POSITIVE: "normal",
        }
        return mapping.get(severity, "normal")

    def _estimate_action_impact(
        self,
        action: CreativeActionType,
        diagnosis_type: CreativeDiagnosisType,
    ) -> str:
        """预估动作影响."""
        if action == CreativeActionType.GENERATE_VARIANTS:
            return "生成变体后预计CTR提升15-25%"
        elif action == CreativeActionType.SCALE_CREATIVE:
            return "扩大投放预计ROAS保持在1.5+"
        elif action == CreativeActionType.PAUSE_CREATIVE:
            return "暂停后预计节省低效花费"
        elif action == CreativeActionType.ANALYZE_PERFORMANCE:
            return "继续观察积累数据"
        return ""

    # ── 状态与统计 ────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state": self._state.value,
            "analyzer": self._analyzer.stats(),
            "dna_engine": {
                "extracted_count": self._dna_engine.get_dna_count(),
            },
            "memory": self._memory.stats(),
            "opportunity_engine": self._opportunity_engine.stats(),
            "strategy_engine": self._strategy_engine.stats(),
            "planner": self._planner.stats(),
            "evaluator": self._evaluator.stats(),
            "executor": self._executor.stats(),
            "generator_bridge": self._generator_bridge.stats(),
            "experiment_manager": self._experiment_manager.stats(),
            "rollout_controller": self._rollout_controller.stats(),
            "reward_model": self._reward_model.stats(),
            "pattern_miner": self._pattern_miner.stats(),
            "strategy_memory": self._strategy_memory.stats(),
            "mutation_learning": self._mutation_learning.stats(),
            "policy": self._policy.stats(),
        }

    def reset(self) -> None:
        self._state = CreativeAgentState.IDLE
        self._analyzer.reset()
        self._dna_engine.reset()
        self._memory.reset()
        self._opportunity_engine.reset()
        self._strategy_engine.reset()
        self._planner.reset()
        self._evaluator.reset()
        self._executor.reset()
        self._generator_bridge.reset()
        self._experiment_manager.reset()
        self._rollout_controller.reset()
        self._reward_model.reset()
        self._pattern_miner.reset()
        self._strategy_memory.reset()
        self._mutation_learning.reset()
        self._policy.reset()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_creative_agent(
    name: str = "Creative Agent",
    fatigue_threshold: float = 0.6,
    roas_winner_threshold: float = 1.5,
) -> CreativeAgent:
    """创建默认 Creative Agent.

    Args:
        name: Agent 名称
        fatigue_threshold: 疲劳阈值
        roas_winner_threshold: 赢家ROAS阈值

    Returns:
        CreativeAgent
    """
    identity = create_creative_agent_identity(name=name)
    thresholds = CreativeThresholds(
        fatigue_threshold=fatigue_threshold,
        roas_winner_threshold=roas_winner_threshold,
    )
    return CreativeAgent(identity=identity, thresholds=thresholds)