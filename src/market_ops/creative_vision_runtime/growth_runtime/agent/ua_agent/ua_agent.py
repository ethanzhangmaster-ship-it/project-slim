"""E14.3.1 UA Growth Agent — 用户获取增长 Agent.

UA Agent 是多 Agent 组织中的专业 Agent，负责 UA 领域的全链路决策:

核心循环:
  1. Analyze: 分析 UA 指标 → 检测异常
  2. Diagnose: 根因诊断 → 识别问题类型
  3. Strategize: 生成策略 → 确定行动方案
  4. Select: 选择动作 → 生成执行计划
  5. Execute: 执行动作 → 连接 E13 执行层
  6. Learn: 记录经验 → 反馈学习

与 Supervisor 的交互:
  Supervisor → UA Agent: 请求 UA 分析 (TASK/REQUEST)
  UA Agent → Supervisor: 返回 GrowthRecommendation (TASK_RESULT/RESPONSE)

设计原则:
  - 继承 E14.1 通信协议
  - 集成 E14.2 Supervisor 任务分配
  - 连接 E13 GrowthDecisionExecutor
  - 确定性、可解释、可回滚
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
    create_ua_agent_identity,
)
from ..communication.agent_registry import AgentRegistry, AgentStatus
from ..communication.message_bus import MessageBus
from ..communication.collaboration import CollaborationEngine

from .analyzer import UAAnalyzer, UAMetrics, UAAnalysisResult, MetricAnomaly
from .diagnosis import UADiagnosisEngine, UADiagnosis, DiagnosisType, DiagnosisSeverity
from .strategy import UAStrategyEngine, UAStrategy, StrategyType, StrategyAction
from .action_selector import (
    UAActionSelector,
    SelectedAction,
    ActionPlan,
    ActionStatus,
    ActionRisk,
)
from .memory import UAMemory, UADecisionRecord, DecisionOutcome, ExperienceEntry
from .feedback import (
    UAActionOutcome,
    FeedbackCollector,
    FeedbackBatch,
    create_feedback_collector,
)
from .evaluation import (
    EvaluationResult,
    EvaluationBatch,
    RewardCalculator,
    OutcomeEvaluator,
    RewardConfig,
    DEFAULT_REWARD_CONFIG,
    create_reward_calculator,
    create_outcome_evaluator,
)
from .learning import (
    LearningResult,
    FeedbackLoopResult,
    FeedbackLoopBatch,
    LearningEngine,
    FeedbackLoop,
    create_feedback_loop,
)


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class UAAgentState(str, Enum):
    """UA Agent 状态."""
    IDLE = "idle"
    ANALYZING = "analyzing"        # 分析中
    DIAGNOSING = "diagnosing"      # 诊断中
    STRATEGIZING = "strategizing"  # 策略生成中
    SELECTING = "selecting"        # 动作选择中
    EXECUTING = "executing"        # 执行中
    OBSERVING = "observing"        # 观察反馈中 (E14.3.1)
    EVALUATING = "evaluating"      # 评估结果中 (E14.3.1)
    LEARNING = "learning"          # 学习中
    ERROR = "error"


@dataclass
class GrowthRecommendation:
    """增长建议 — UA Agent 的输出.

    Attributes:
        recommendation_id: 建议 ID
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        analysis: 分析结果
        diagnoses: 诊断列表
        strategies: 策略列表
        action_plan: 执行计划
        summary: 摘要
        confidence: 综合置信度
        requires_approval: 是否需要审批
        created_at: 创建时间
        metadata: 扩展元数据
    """
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    campaign_id: str = ""
    analysis: UAAnalysisResult | None = None
    diagnoses: list[UADiagnosis] = field(default_factory=list)
    strategies: list[UAStrategy] = field(default_factory=list)
    action_plan: ActionPlan | None = None
    summary: str = ""
    confidence: float = 0.0
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "strategies": [s.to_dict() for s in self.strategies],
            "action_plan": self.action_plan.to_dict() if self.action_plan else None,
            "summary": self.summary,
            "confidence": round(self.confidence, 4),
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def has_critical_issues(self) -> bool:
        return any(
            d.severity == DiagnosisSeverity.CRITICAL
            for d in self.diagnoses
        )

    @property
    def top_diagnosis(self) -> UADiagnosis | None:
        return self.diagnoses[0] if self.diagnoses else None

    @property
    def top_strategy(self) -> UAStrategy | None:
        return self.strategies[0] if self.strategies else None


# ═══════════════════════════════════════════════════════════════
# UA Growth Agent
# ═══════════════════════════════════════════════════════════════


class UAGrowthAgent:
    """UA 增长 Agent — 用户获取领域的专业决策 Agent.

    职责:
      1. 分析 UA 指标 (spend, ROAS, CPI, CTR, CVR, LTV, fatigue)
      2. 诊断异常根因 (素材疲劳、受众饱和、商店问题等)
      3. 生成增长策略 (素材生成、预算调整、受众扩展等)
      4. 选择最优动作 (优先级排序、去重、风险过滤)
      5. 执行动作 (连接 E13 GrowthDecisionExecutor)
      6. 记录经验 (记忆系统，支持未来决策)

    与 Supervisor 的交互:
      Supervisor → UA Agent: 分析请求
      UA Agent → Supervisor: GrowthRecommendation

    用法:
        agent = UAGrowthAgent()
        agent.register(bus, registry)

        # 分析 UA 指标
        rec = agent.analyze_metrics(metrics_dict)

        # 处理 Supervisor 任务
        task = agent.receive_task(message)
        result = agent.process_task(task)
        agent.respond_to_supervisor(task, result)
    """

    def __init__(
        self,
        name: str = "UA Growth Agent",
        bus: MessageBus | None = None,
        registry: AgentRegistry | None = None,
        collab: CollaborationEngine | None = None,
        thresholds: dict[str, dict[str, float]] | None = None,
    ):
        self._identity = create_ua_agent_identity(name)
        self._bus = bus or MessageBus()
        self._registry = registry or AgentRegistry()
        self._collab = collab or CollaborationEngine(bus=self._bus, registry=self._registry)

        # 子模块
        self._analyzer = UAAnalyzer(thresholds=thresholds)
        self._diagnosis = UADiagnosisEngine()
        self._strategy = UAStrategyEngine()
        self._selector = UAActionSelector()
        self._memory = UAMemory()
        self._feedback_loop = FeedbackLoop()  # E14.3.1
        self._feedback_collector = FeedbackCollector()  # E14.3.1

        # 运行时状态
        self._state = UAAgentState.IDLE
        self._cycle_count: int = 0
        self._recommendations: list[GrowthRecommendation] = []
        self._registered = False

    # ── 生命周期 ──────────────────────────────────────────────

    def register(self, bus: MessageBus | None = None, registry: AgentRegistry | None = None) -> None:
        """注册到通信层."""
        if bus:
            self._bus = bus
        if registry:
            self._registry = registry

        self._registry.register(self._identity)
        self._registered = True

    def unregister(self) -> None:
        """注销."""
        self._registry.unregister(self._identity.agent_id)
        self._registered = False

    @property
    def is_registered(self) -> bool:
        return self._registered

    # ── 核心循环: 分析 → 诊断 → 策略 → 选择 ──────────────────

    def analyze_metrics(
        self,
        metrics_data: dict[str, Any],
        previous_metrics: dict[str, Any] | None = None,
        top_n_actions: int = 10,
    ) -> GrowthRecommendation:
        """完整分析 UA 指标并生成增长建议.

        这是 UA Agent 的核心入口:
          1. 构建 UAMetrics
          2. 分析异常
          3. 根因诊断
          4. 策略生成
          5. 动作选择
          6. 记录决策

        Args:
            metrics_data: 当前指标数据
            previous_metrics: 历史指标数据 (用于趋势)
            top_n_actions: 最多选择的动作数

        Returns:
            GrowthRecommendation: 增长建议
        """
        self._cycle_count += 1
        self._state = UAAgentState.ANALYZING

        # Phase 1: 分析
        metrics = self._build_metrics(metrics_data)
        prev = self._build_metrics(previous_metrics) if previous_metrics else None
        analysis = self._analyzer.analyze(metrics, prev)

        self._state = UAAgentState.DIAGNOSING

        # Phase 2: 诊断
        diagnoses = self._diagnosis.diagnose(analysis)

        self._state = UAAgentState.STRATEGIZING

        # Phase 3: 策略
        strategies = self._strategy.generate_strategies(
            diagnoses,
            campaign_id=metrics.campaign_id,
            product_id=metrics.product_id,
        )

        # 应用历史经验提升置信度
        strategies = self._apply_experience_boost(strategies, diagnoses)

        self._state = UAAgentState.SELECTING

        # Phase 4: 动作选择
        action_plan = self._selector.select(strategies, top_n=top_n_actions)

        # Phase 5: 记录决策
        self._state = UAAgentState.LEARNING
        self._record_decisions(analysis, diagnoses, strategies, action_plan, metrics)

        # Phase 6: 生成建议
        recommendation = self._build_recommendation(
            analysis, diagnoses, strategies, action_plan,
            metrics.product_id, metrics.campaign_id,
        )
        self._recommendations.append(recommendation)

        self._state = UAAgentState.IDLE
        return recommendation

    def analyze_from_dict(
        self,
        metrics_data: dict[str, Any],
        previous_metrics: dict[str, Any] | None = None,
    ) -> GrowthRecommendation:
        """从字典数据快速分析."""
        return self.analyze_metrics(metrics_data, previous_metrics)

    def quick_analysis(
        self,
        spend: float = 0,
        revenue: float = 0,
        roas: float = 0,
        cpi: float = 0,
        ctr: float = 0,
        cvr: float = 0,
        ltv: float = 0,
        fatigue: float = 0,
        frequency: float = 0,
        campaign_id: str = "",
        product_id: str = "",
    ) -> GrowthRecommendation:
        """快速分析 — 传入关键指标即可."""
        return self.analyze_metrics({
            "spend": spend,
            "revenue": revenue,
            "roas": roas,
            "cpi": cpi,
            "ctr": ctr,
            "cvr": cvr,
            "ltv": ltv,
            "fatigue": fatigue,
            "frequency": frequency,
            "campaign_id": campaign_id,
            "product_id": product_id,
        })

    # ── 与 Supervisor 通信 ────────────────────────────────────

    def receive_task(self, message: AgentMessage) -> dict[str, Any]:
        """接收 Supervisor 分配的任务.

        Args:
            message: Supervisor 发来的任务消息

        Returns:
            任务解析结果
        """
        return {
            "task_type": message.standard_type.value if message.standard_type else "unknown",
            "subject": message.subject,
            "body": message.body,
            "priority": message.priority.value,
            "message_id": message.message_id,
        }

    def process_task(self, task: dict[str, Any]) -> GrowthRecommendation:
        """处理 Superivsor 任务.

        Args:
            task: 从 receive_task 解析的任务

        Returns:
            GrowthRecommendation
        """
        body = task.get("body", {})
        metrics_data = body.get("metrics", body)
        return self.analyze_metrics(metrics_data)

    def respond_to_supervisor(
        self,
        task: dict[str, Any],
        recommendation: GrowthRecommendation,
    ) -> AgentMessage:
        """向 Supervisor 返回分析结果.

        Args:
            task: 原始任务
            recommendation: 增长建议

        Returns:
            AgentMessage: 响应消息
        """
        sender = self._identity
        # Find supervisor by role
        supervisors = self._registry.find_by_role(AgentRole.SUPERVISOR)
        if not supervisors:
            return None
        receiver = supervisors[0].identity

        # 构建响应体
        body = recommendation.to_dict()
        body["agent_id"] = self._identity.agent_id
        body["agent_name"] = self._identity.name

        # 确定标准消息类型
        if recommendation.has_critical_issues:
            standard_type = StandardMessageType.ROAS_ALERT
            priority = MessagePriority.CRITICAL
        else:
            standard_type = StandardMessageType.PROGRESS_REPORT
            priority = MessagePriority.NORMAL

        msg = AgentMessage(
            correlation_id=task.get("message_id", ""),
            sender=sender,
            receiver=receiver,
            message_type=MessageType.TASK_RESULT,
            standard_type=standard_type,
            subject=f"UA Analysis: {recommendation.summary[:80]}",
            body=body,
            priority=priority,
            status=MessageStatus.PROCESSED,
        )

        # 通过消息总线发送
        self._bus.send(msg)
        return msg

    def request_creative_analysis(
        self,
        campaign_id: str,
        reason: str = "Creative fatigue detected",
    ) -> AgentMessage | None:
        """请求 Creative Agent 进行素材分析.

        Args:
            campaign_id: 广告系列 ID
            reason: 请求原因

        Returns:
            发送的消息
        """
        try:
            creatives = self._registry.find_by_role(AgentRole.CREATIVE)
            if not creatives:
                return None
            creative_identity = creatives[0].identity

            msg = AgentMessage.create_request(
                sender=self._identity,
                receiver=creative_identity,
                subject=f"Creative analysis request: {campaign_id}",
                body={
                    "campaign_id": campaign_id,
                    "reason": reason,
                    "requested_by": self._identity.agent_id,
                },
                standard_type=StandardMessageType.REQUEST_CREATIVE_ANALYSIS,
                priority=MessagePriority.HIGH,
            )
            self._bus.send(msg)
            return msg
        except Exception:
            return None

    def send_alert_to_supervisor(
        self,
        subject: str,
        body: dict[str, Any],
    ) -> AgentMessage | None:
        """向 Supervisor 发送告警.

        Args:
            subject: 告警主题
            body: 告警详情

        Returns:
            发送的消息
        """
        try:
            supervisors = self._registry.find_by_role(AgentRole.SUPERVISOR)
            if not supervisors:
                return None
            supervisor_identity = supervisors[0].identity

            msg = AgentMessage.create_alert(
                sender=self._identity,
                receiver=supervisor_identity,
                subject=subject,
                body=body,
                priority=MessagePriority.CRITICAL,
            )
            self._bus.send(msg)
            return msg
        except Exception:
            return None

    # ── 执行动作 ──────────────────────────────────────────────

    def execute_plan(
        self,
        plan: ActionPlan,
        executor: Any = None,
        stop_on_failure: bool = False,
    ) -> list[dict[str, Any]]:
        """执行动作计划.

        Args:
            plan: 执行计划
            executor: 外部执行器
            stop_on_failure: 失败时停止

        Returns:
            执行结果列表
        """
        self._state = UAAgentState.EXECUTING
        results = self._selector.execute_plan(plan, executor, stop_on_failure)

        # 记录执行结果
        for action, result in zip(plan.actions, results):
            if result.get("success"):
                self._record_action_result(action, success=True)
            else:
                self._record_action_result(action, success=False, error=result.get("error"))

        self._state = UAAgentState.IDLE
        return results

    def execute_action(
        self,
        action: SelectedAction,
        executor: Any = None,
    ) -> dict[str, Any]:
        """执行单个动作."""
        self._state = UAAgentState.EXECUTING
        result = self._selector.execute(action, executor)
        self._state = UAAgentState.IDLE
        return result

    def rollback_plan(
        self,
        plan: ActionPlan,
        executor: Any = None,
    ) -> list[dict[str, Any]]:
        """回滚计划."""
        return self._selector.rollback_plan(plan, executor)

    def rollback_action(
        self,
        action: SelectedAction,
        executor: Any = None,
    ) -> dict[str, Any]:
        """回滚单个动作."""
        return self._selector.rollback(action, executor)

    # ── 记忆学习 ──────────────────────────────────────────────

    def resolve_decision(
        self,
        record_id: str,
        outcome: DecisionOutcome,
        after_metrics: dict[str, Any] | None = None,
        learning: str = "",
    ) -> UADecisionRecord | None:
        """记录决策结果."""
        return self._memory.resolve(record_id, outcome, after_metrics, learning)

    # ── E14.3.1 反馈闭环 ──────────────────────────────────────

    def evaluate_outcome(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        observation_hours: int = 24,
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        record_id: str = "",
    ) -> FeedbackLoopResult:
        """评估动作执行结果 — 运行完整 Observe → Evaluate → Learn 闭环.

        这是 UA Agent 实现 Autonomous Growth 的核心入口:
          1. Observe: 采集执行后指标
          2. Evaluate: 计算奖励并评估
          3. Learn: 更新记忆
          4. Return: 返回闭环结果

        Args:
            action_id: 动作 ID
            action_type: 动作类型
            target: 目标实体
            before_metrics: 执行前指标
            after_metrics: 执行后指标
            observation_hours: 观察周期 (小时)
            diagnosis_type: 关联的诊断类型
            strategy_type: 关联的策略类型
            record_id: 关联的决策记录 ID

        Returns:
            FeedbackLoopResult: 闭环结果
        """
        self._state = UAAgentState.OBSERVING
        result = self._feedback_loop.run(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            memory=self._memory,
            diagnosis_type=diagnosis_type,
            strategy_type=strategy_type,
            observation_hours=observation_hours,
            record_id=record_id,
        )
        self._state = UAAgentState.IDLE
        return result

    def evaluate_outcome_from_records(
        self,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        record_id: str,
        observation_hours: int = 24,
    ) -> FeedbackLoopResult:
        """从已有决策记录评估结果.

        从 UAMemory 中查找决策记录，自动获取 diagnosis_type, strategy_type, action_type.

        Args:
            before_metrics: 执行前指标
            after_metrics: 执行后指标
            record_id: 决策记录 ID
            observation_hours: 观察周期

        Returns:
            FeedbackLoopResult
        """
        record = self._memory.get_record(record_id)
        if not record:
            return FeedbackLoopResult(
                action_id=record_id,
                recommendation="决策记录未找到",
            )

        return self.evaluate_outcome(
            action_id=record_id,
            action_type=record.action_type,
            target=record.action_target,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            observation_hours=observation_hours,
            diagnosis_type=record.diagnosis_type,
            strategy_type=record.strategy_type,
            record_id=record_id,
        )

    def evaluate_pending_decisions(
        self,
        after_metrics_map: dict[str, dict[str, Any]],
        observation_hours: int = 24,
    ) -> FeedbackLoopBatch:
        """评估所有待确认的决策.

        自动查找所有 PENDING 状态的决策记录，使用提供的 after_metrics 评估结果.

        Args:
            after_metrics_map: {record_id: after_metrics} 映射
            observation_hours: 观察周期

        Returns:
            FeedbackLoopBatch
        """
        self._state = UAAgentState.EVALUATING

        pending = self._memory.get_pending()
        resolutions = []
        for record in pending:
            if record.record_id in after_metrics_map:
                resolutions.append({
                    "record_id": record.record_id,
                    "action_id": record.record_id,
                    "action_type": record.action_type,
                    "action_target": record.action_target,
                    "target": record.action_target,
                    "diagnosis_type": record.diagnosis_type.value,
                    "strategy_type": record.strategy_type.value,
                    "before_metrics": record.before_metrics,
                    "after_metrics": after_metrics_map[record.record_id],
                })

        batch = self._feedback_loop.run_from_resolutions(
            resolutions=resolutions,
            memory=self._memory,
            observation_hours=observation_hours,
        )

        self._state = UAAgentState.IDLE
        return batch

    def run_feedback_loop(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        observation_hours: int = 24,
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        record_id: str = "",
    ) -> FeedbackLoopResult:
        """运行反馈闭环 (evaluate_outcome 的别名)."""
        return self.evaluate_outcome(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            observation_hours=observation_hours,
            diagnosis_type=diagnosis_type,
            strategy_type=strategy_type,
            record_id=record_id,
        )

    def collect_feedback(
        self,
        action_id: str,
        action_type: str,
        target: str,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        observation_hours: int = 24,
    ) -> UAActionOutcome:
        """仅采集反馈数据 (不评估不学习)."""
        return self._feedback_collector.collect(
            action_id=action_id,
            action_type=action_type,
            target=target,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            observation_hours=observation_hours,
        )

    def get_feedback_loop_stats(self) -> dict[str, Any]:
        """获取反馈闭环统计."""
        return self._feedback_loop.stats()

    def get_feedback_history(self, n: int = 20) -> list[FeedbackLoopResult]:
        """获取反馈闭环历史."""
        return self._feedback_loop.get_history(n)

    def get_decision_history(
        self,
        diagnosis_type: DiagnosisType | None = None,
        n: int = 20,
    ) -> list[UADecisionRecord]:
        """获取决策历史."""
        return self._memory.get_records(diagnosis_type=diagnosis_type, n=n)

    def get_experiences(
        self,
        diagnosis_type: DiagnosisType | None = None,
    ) -> list[ExperienceEntry]:
        """获取经验."""
        return self._memory.get_experiences(diagnosis_type)

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_metrics(self, data: dict[str, Any]) -> UAMetrics:
        """从字典构建 UAMetrics."""
        if isinstance(data, UAMetrics):
            return data
        return UAMetrics(
            product_id=data.get("product_id", ""),
            campaign_id=data.get("campaign_id", ""),
            spend=data.get("spend", 0.0),
            revenue=data.get("revenue", 0.0),
            roas=data.get("roas", 0.0),
            cpi=data.get("cpi", 0.0),
            ctr=data.get("ctr", 0.0),
            cvr=data.get("cvr", 0.0),
            ltv=data.get("ltv", 0.0),
            fatigue=data.get("fatigue", 0.0),
            frequency=data.get("frequency", 0.0),
            impressions=data.get("impressions", 0),
            installs=data.get("installs", 0),
            payer_rate=data.get("payer_rate", 0.0),
            arpu=data.get("arpu", 0.0),
            d7_retention=data.get("d7_retention", 0.0),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )

    def _apply_experience_boost(
        self,
        strategies: list[UAStrategy],
        diagnoses: list[UADiagnosis],
    ) -> list[UAStrategy]:
        """根据历史经验提升策略置信度."""
        for strategy in strategies:
            if not strategy.diagnosis:
                continue
            boost = self._memory.get_confidence_boost(
                diagnosis_type=strategy.diagnosis.issue_type,
                strategy_type=strategy.strategy_type,
                action_type=strategy.actions[0].action_type if strategy.actions else "",
            )
            if boost > 0:
                strategy.confidence = min(strategy.confidence + boost, 1.0)
                strategy.metadata["experience_boost"] = boost
        return strategies

    def _record_decisions(
        self,
        analysis: UAAnalysisResult,
        diagnoses: list[UADiagnosis],
        strategies: list[UAStrategy],
        action_plan: ActionPlan,
        metrics: UAMetrics,
    ) -> None:
        """记录决策链路."""
        for strategy in strategies:
            for action in strategy.actions:
                self._memory.record_decision(
                    product_id=metrics.product_id,
                    campaign_id=metrics.campaign_id,
                    analysis_id=analysis.analysis_id,
                    diagnosis_type=strategy.diagnosis.issue_type if strategy.diagnosis else DiagnosisType.HEALTHY,
                    diagnosis_severity=strategy.diagnosis.severity if strategy.diagnosis else DiagnosisSeverity.LOW,
                    strategy_type=strategy.strategy_type,
                    action_type=action.action_type,
                    action_target=action.target,
                    confidence=strategy.confidence,
                    before_metrics=metrics.to_dict(),
                    metadata={
                        "strategy_id": strategy.strategy_id,
                        "recommendation_generated": True,
                    },
                )

    def _record_action_result(
        self,
        action: SelectedAction,
        success: bool,
        error: str = "",
    ) -> None:
        """记录动作执行结果."""
        # 查找对应的决策记录并更新
        for record_id, record in self._memory._records.items():
            if (record.action_type == action.action_type
                    and record.action_target == action.target
                    and not record.is_resolved):
                outcome = DecisionOutcome.SUCCESS if success else DecisionOutcome.FAILURE
                self._memory.resolve(
                    record_id,
                    outcome,
                    learning=error if error else f"Action {action.action_type} executed successfully",
                )
                break

    def _build_recommendation(
        self,
        analysis: UAAnalysisResult,
        diagnoses: list[UADiagnosis],
        strategies: list[UAStrategy],
        action_plan: ActionPlan,
        product_id: str,
        campaign_id: str,
    ) -> GrowthRecommendation:
        """构建增长建议."""
        # 综合置信度
        confidences = [d.confidence for d in diagnoses] if diagnoses else [0.95]
        avg_confidence = sum(confidences) / len(confidences)

        # 是否需要审批
        requires_approval = any(
            a.requires_approval for a in action_plan.actions
        )

        # 摘要
        summary_parts = []
        if diagnoses:
            top_d = diagnoses[0]
            summary_parts.append(
                f"[{top_d.issue_type.value}] {top_d.root_cause[:60]}"
            )
        if strategies:
            top_s = strategies[0]
            summary_parts.append(
                f"策略: {top_s.strategy_type.value}"
            )
        summary_parts.append(
            f"置信度: {avg_confidence:.0%}"
        )
        if action_plan.action_count > 0:
            summary_parts.append(f"动作: {action_plan.action_count}个")

        return GrowthRecommendation(
            product_id=product_id,
            campaign_id=campaign_id,
            analysis=analysis,
            diagnoses=diagnoses,
            strategies=strategies,
            action_plan=action_plan,
            summary=" | ".join(summary_parts),
            confidence=avg_confidence,
            requires_approval=requires_approval,
        )

    # ── 查询 ──────────────────────────────────────────────────

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    @property
    def state(self) -> UAAgentState:
        return self._state

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def get_analyzer(self) -> UAAnalyzer:
        return self._analyzer

    def get_diagnosis_engine(self) -> UADiagnosisEngine:
        return self._diagnosis

    def get_strategy_engine(self) -> UAStrategyEngine:
        return self._strategy

    def get_action_selector(self) -> UAActionSelector:
        return self._selector

    def get_memory(self) -> UAMemory:
        return self._memory

    def get_feedback_loop(self) -> FeedbackLoop:
        """获取反馈闭环 (E14.3.1)."""
        return self._feedback_loop

    def get_feedback_collector(self) -> FeedbackCollector:
        """获取反馈采集器 (E14.3.1)."""
        return self._feedback_collector

    def get_recommendations(self, n: int = 10) -> list[GrowthRecommendation]:
        return self._recommendations[-n:]

    def get_last_recommendation(self) -> GrowthRecommendation | None:
        return self._recommendations[-1] if self._recommendations else None

    def stats(self) -> dict[str, Any]:
        return {
            "identity": self._identity.to_dict(),
            "state": self._state.value,
            "cycle_count": self._cycle_count,
            "registered": self._registered,
            "analyzer": {"history": len(self._analyzer.get_history())},
            "diagnosis": {"history": len(self._diagnosis.get_history())},
            "strategy": {"history": len(self._strategy.get_history())},
            "selector": self._selector.stats(),
            "memory": self._memory.stats(),
            "feedback_loop": self._feedback_loop.stats(),
            "recommendations": len(self._recommendations),
        }

    def reset(self) -> None:
        self._analyzer.reset()
        self._diagnosis.reset()
        self._strategy.reset()
        self._selector.reset()
        self._memory.reset()
        self._feedback_loop.reset()
        self._recommendations.clear()
        self._cycle_count = 0
        self._state = UAAgentState.IDLE


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_ua_agent(
    name: str = "UA Growth Agent",
    bus: MessageBus | None = None,
    registry: AgentRegistry | None = None,
) -> UAGrowthAgent:
    """创建默认 UA Growth Agent."""
    return UAGrowthAgent(name=name, bus=bus, registry=registry)