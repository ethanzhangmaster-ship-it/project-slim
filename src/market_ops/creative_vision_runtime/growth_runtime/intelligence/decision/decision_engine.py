"""E13.5.5 / E13.6.5 / E13.7.1 / E13.7.2 / E13.7.3 Decision Engine — 自主决策编排引擎.

Day 6.5 升级:
  集成 DecisionMemoryRetriever，在决策时查询历史决策轨迹。

Day 7.1 升级:
  集成 DecisionConfidenceEngine，多维度量化决策置信度，
  从"找相似案例"升级为"预测动作价值并量化可信度"。

Day 7.2 升级:
  集成 DecisionValuePredictor，预测未来价值，
  从"我相信这个策略"升级为"这个策略未来值多少钱"。

Day 7.3 升级:
  集成 MemoryConsolidator，在决策前清理过期/低价值记忆，
  防止旧经验污染新决策。从"记住所有经验"升级为"只相信有效经验"。

核心流程:
  DecisionInput
      ↓
  MemoryConsolidator → 清理过期记忆 (Day 7.3 新增)
      ↓
  DecisionMemoryRetriever → 查询历史决策 (Day 6.5)
      ↓
  DecisionScorer.score_all() → 策略评分排序
      ↓
  DecisionConfidenceEngine → 计算置信度 (Day 7.1)
      ↓
  DecisionValuePredictor → 预测未来价值 (Day 7.2)
      ↓
  Decision Rules → 决策类型判定 (EXECUTE/TEST/HOLD/BLOCK/ESCALATE)
      ↓
  DecisionPlan → 生成执行计划
      ↓
  DecisionExplainer → 生成决策解释
      ↓
  DecisionMemory.record_decision() → 记录决策
      ↓
  DecisionOutput → 最终决策

连接:
  E13.5.2 Opportunity → E13.5.3 Strategy → E13.5.4 Risk → E13.5.5 Decision
  E13.6.5 DecisionMemoryRetriever → DecisionEngine (历史行为增强)
  E13.7.1 DecisionConfidenceEngine → DecisionEngine (置信度量化)
  E13.7.2 DecisionValuePredictor → DecisionEngine (价值预测)
  E13.7.3 MemoryConsolidator → DecisionEngine (记忆清理)
"""

from __future__ import annotations

from typing import Any

from ..intelligence_models import GrowthOpportunity, StrategyCandidate
from ..risk_models import RiskAssessment, RiskDecision, RiskLevel
from ...decision.decision_memory_retriever import DecisionContext, DecisionHistoryResult
from .confidence_engine import DecisionConfidence, DecisionConfidenceEngine
from .decision_explainer import DecisionExplainer
from .decision_memory import DecisionMemory
from .decision_scorer import DecisionScorer
from .models import (
    DecisionInput,
    DecisionOutput,
    DecisionPlan,
    DecisionScore,
    DecisionType,
)
from .memory_consolidator import ConsolidationResult, MemoryConsolidator
from .value_predictor import DecisionValuePrediction, DecisionValuePredictor


class DecisionEngine:
    """决策引擎 — 将机会、策略、风险合成为最终自主决策.

    Day 6.5 升级:
      集成 DecisionMemoryRetriever，在决策时查询"我之前做过什么"。

    Day 7.1 升级:
      集成 DecisionConfidenceEngine，多维度计算"这个决定我应该有多相信"。

    Day 7.2 升级:
      集成 DecisionValuePredictor，预测"这个策略未来值多少钱"。

    Day 7.3 升级:
      集成 MemoryConsolidator，在决策前清理过期记忆，
      确保"只相信有效经验"。

    编排完整决策流程:
      0. 记忆清理: 运行 MemoryConsolidator 清理过期记忆 (Day 7.3 新增)
      1. 历史查询: 从 DecisionMemory 检索历史决策 (Day 6.5)
      2. 置信度计算: 多维度量化决策可信度 (Day 7.1)
      3. 价值预测: 预测未来收益与衰减 (Day 7.2)
      4. 评分: 对所有候选策略进行风险调整评分
      5. 判定: 根据决策规则确定决策类型
      6. 计划: 生成可执行的行动计划
      7. 解释: 生成人类可读的决策解释
      8. 记录: 写入决策记忆

    用法:
        engine = DecisionEngine(
            memory=DecisionMemory(),
            decision_retriever=None,  # 可选
            confidence_engine=None,   # 可选 (Day 7.1)
            value_predictor=None,     # 可选 (Day 7.2)
            memory_consolidator=None, # 可选 (Day 7.3)
        )
        output = engine.decide(input_data)
        if output.is_executable:
            execute(output.action_plan)
    """

    # ── 决策规则阈值 ──────────────────────────────────────────

    # 风险阈值
    block_risk_threshold: float = 0.80      # 风险 >= 此值 → BLOCK
    escalate_risk_threshold: float = 0.65   # 风险 >= 此值 → ESCALATE
    warning_risk_threshold: float = 0.50    # 风险 >= 此值 → 降级

    # 置信度阈值
    hold_confidence_threshold: float = 0.50  # 置信度 < 此值 → HOLD
    test_confidence_threshold: float = 0.70  # 置信度 < 此值 → TEST

    # 收益阈值
    execute_reward_threshold: float = 0.60  # 预期收益 >= 此值 + 低风险 → EXECUTE

    # 测试预算
    default_test_budget: float = 500.0      # 默认测试预算
    default_test_duration: int = 3          # 默认测试天数

    def __init__(
        self,
        scorer: DecisionScorer | None = None,
        explainer: DecisionExplainer | None = None,
        memory: DecisionMemory | None = None,
        decision_retriever: Any = None,  # DecisionMemoryRetriever (Day 6.5)
        confidence_engine: DecisionConfidenceEngine | None = None,  # Day 7.1
        value_predictor: DecisionValuePredictor | None = None,  # Day 7.2
        memory_consolidator: MemoryConsolidator | None = None,  # Day 7.3
        block_risk_threshold: float = 0.80,
        escalate_risk_threshold: float = 0.65,
        hold_confidence_threshold: float = 0.50,
        test_confidence_threshold: float = 0.70,
        execute_reward_threshold: float = 0.60,
        default_test_budget: float = 500.0,
        default_test_duration: int = 3,
    ):
        """初始化决策引擎.

        Args:
            scorer: 策略评分器 (默认创建)
            explainer: 决策解释器 (默认创建)
            memory: 决策记忆 (默认创建)
            decision_retriever: DecisionMemoryRetriever 实例 (Day 6.5)
            confidence_engine: DecisionConfidenceEngine 实例 (Day 7.1)
            value_predictor: DecisionValuePredictor 实例 (Day 7.2)
            memory_consolidator: MemoryConsolidator 实例 (Day 7.3 新增)
            block_risk_threshold: 阻止阈值
            escalate_risk_threshold: 升级阈值
            hold_confidence_threshold: 保持阈值
            test_confidence_threshold: 测试阈值
            execute_reward_threshold: 执行阈值
            default_test_budget: 默认测试预算
            default_test_duration: 默认测试天数
        """
        self.scorer = scorer or DecisionScorer()
        self.explainer = explainer or DecisionExplainer()
        self.memory = memory or DecisionMemory()
        self.decision_retriever = decision_retriever  # Day 6.5
        self.confidence_engine = confidence_engine  # Day 7.1
        self.value_predictor = value_predictor  # Day 7.2
        self.memory_consolidator = memory_consolidator  # Day 7.3

        # 阈值
        self.block_risk_threshold = block_risk_threshold
        self.escalate_risk_threshold = escalate_risk_threshold
        self.hold_confidence_threshold = hold_confidence_threshold
        self.test_confidence_threshold = test_confidence_threshold
        self.execute_reward_threshold = execute_reward_threshold
        self.default_test_budget = default_test_budget
        self.default_test_duration = default_test_duration

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def decide(self, input_data: DecisionInput) -> DecisionOutput:
        """执行完整决策流程.

        Day 6.5 升级:
          在评分前查询 DecisionMemoryRetriever，获取历史决策轨迹，
          将历史成功率、警告等信息注入决策输出。

        Day 7.3 升级:
          在决策前运行 MemoryConsolidator 清理过期记忆，
          确保只使用有效经验。

        Args:
            input_data: 决策输入 (机会 + 策略 + 风险)

        Returns:
            DecisionOutput: 最终决策结果
        """
        # ── 0. 空输入保护 ──
        if not input_data.has_strategies:
            return self._create_empty_decision(input_data)

        # ── 0.3. 记忆整合清理 (Day 7.3 新增) ──
        consolidation_result = self._run_memory_consolidation()

        # ── 0.5. 历史决策查询 (Day 6.5 新增) ──
        decision_history = self._query_decision_history(input_data)

        # ── 1. 策略评分排序 ──
        candidates = self._extract_candidates(input_data)
        scores = self.scorer.score_all(candidates, input_data.risks)

        if not scores:
            return self._create_empty_decision(input_data)

        best_score = scores[0]

        # ── 1.5. 基于历史调整置信度 (Day 6.5 新增) ──
        if decision_history and decision_history.has_recommendations:
            best_score = self._apply_history_confidence(best_score, decision_history)

        # ── 1.7. 置信度引擎计算 (Day 7.1 新增) ──
        decision_confidence = self._compute_decision_confidence(
            best_score=best_score,
            input_data=input_data,
        )
        if decision_confidence is not None:
            best_score = self._apply_confidence_engine(best_score, decision_confidence)

        # ── 1.8. 价值预测 (Day 7.2 新增) ──
        value_prediction = self._compute_value_prediction(
            best_score=best_score,
            input_data=input_data,
        )
        if value_prediction is not None:
            best_score = self._apply_value_prediction(best_score, value_prediction)

        # ── 2. 决策类型判定 ──
        risk = self._get_risk_for_best(best_score, input_data)
        decision_type = self._determine_decision_type(best_score, risk)

        # ── 3. 生成执行计划 ──
        action_plan = self._create_action_plan(decision_type, best_score, input_data)

        # ── 4. 构建决策输出 ──
        output = self._build_output(
            input_data=input_data,
            best_score=best_score,
            scores=scores,
            risk=risk,
            decision_type=decision_type,
            action_plan=action_plan,
        )

        # ── 5. 生成解释 ──
        opportunity = input_data.opportunity if isinstance(input_data.opportunity, GrowthOpportunity) else None
        history = self._build_history_context(best_score)
        self.explainer.explain(output, opportunity, risk, best_score, history)

        # ── 5.5. 注入决策历史到输出 (Day 6.5 新增, 必须在 explain 之后以避免被覆盖) ──
        if decision_history:
            self._inject_history_to_output(output, decision_history)

        # ── 5.7. 注入置信度到输出 (Day 7.1 新增) ──
        if decision_confidence is not None:
            self._inject_confidence_to_output(output, decision_confidence)

        # ── 5.8. 注入价值预测到输出 (Day 7.2 新增) ──
        if value_prediction is not None:
            self._inject_value_to_output(output, value_prediction)

        # ── 5.9. 注入记忆整合结果到输出 (Day 7.3 新增) ──
        if consolidation_result is not None:
            self._inject_consolidation_to_output(output, consolidation_result)

        # ── 6. 记录到决策记忆 ──
        self.memory.record_decision(output, opportunity_type=self._extract_opportunity_type(input_data))

        return output

    # ═══════════════════════════════════════════════════════════
    # 决策类型判定
    # ═══════════════════════════════════════════════════════════

    def _determine_decision_type(
        self,
        score: DecisionScore,
        risk: RiskAssessment | None,
    ) -> DecisionType:
        """根据决策规则确定决策类型.

        决策规则:
          1. risk_score >= 0.80  → BLOCK (禁止执行)
          2. risk_score >= 0.65  → ESCALATE (需要人工确认)
          3. confidence < 0.50   → HOLD (保持观察)
          4. 高置信度 + 低风险 + 高收益 → EXECUTE
          5. 其他 → TEST
        """
        risk_score = score.risk_score

        # Rule 1: 高风险 → BLOCK
        if risk_score >= self.block_risk_threshold:
            return DecisionType.BLOCK

        # Rule 2: 中高风险 → ESCALATE
        if risk_score >= self.escalate_risk_threshold:
            return DecisionType.ESCALATE

        # Rule 3: 低置信度 → HOLD
        if score.confidence < self.hold_confidence_threshold:
            return DecisionType.HOLD

        # Rule 4: 高置信度 + 低风险 + 高收益 → EXECUTE
        if (
            score.confidence >= self.test_confidence_threshold
            and risk_score < self.escalate_risk_threshold
            and score.final_score >= self.execute_reward_threshold
        ):
            return DecisionType.EXECUTE

        # Rule 5: 默认 → TEST
        return DecisionType.TEST

    # ═══════════════════════════════════════════════════════════
    # 执行计划生成
    # ═══════════════════════════════════════════════════════════

    def _create_action_plan(
        self,
        decision_type: DecisionType,
        score: DecisionScore,
        input_data: DecisionInput,
    ) -> DecisionPlan:
        """根据决策类型生成执行计划.

        Args:
            decision_type: 决策类型
            score: 最优策略评分
            input_data: 决策输入

        Returns:
            DecisionPlan: 执行计划
        """
        plan = DecisionPlan(
            action_type=decision_type.value,
            target_entity="creative",
            params={},
        )

        if decision_type == DecisionType.EXECUTE:
            # 直接执行: 分配执行预算
            plan.execute_budget = self._estimate_execute_budget(score, input_data)
            plan.duration_days = 7
            plan.expected_roas_impact = score.strategy_reward * score.confidence

        elif decision_type == DecisionType.TEST:
            # 小预算测试
            plan.test_budget = self.default_test_budget
            plan.duration_days = self.default_test_duration
            plan.expected_roas_impact = score.strategy_reward * score.confidence * 0.5
            plan.params = {
                "generate_creatives": 5,
                "test_budget": self.default_test_budget,
                "duration_days": self.default_test_duration,
            }

        elif decision_type == DecisionType.ESCALATE:
            # 需要人工确认: 准备提案但暂不执行
            plan.duration_days = 0
            plan.params = {"requires_approval": True}

        elif decision_type == DecisionType.BLOCK:
            # 阻止执行: 空计划
            plan.duration_days = 0

        elif decision_type == DecisionType.HOLD:
            # 保持观察: 记录观察参数
            plan.duration_days = 0
            plan.params = {"observation_only": True}

        return plan

    # ═══════════════════════════════════════════════════════════
    # 输出构建
    # ═══════════════════════════════════════════════════════════

    def _build_output(
        self,
        input_data: DecisionInput,
        best_score: DecisionScore,
        scores: list[DecisionScore],
        risk: RiskAssessment | None,
        decision_type: DecisionType,
        action_plan: DecisionPlan,
    ) -> DecisionOutput:
        """构建 DecisionOutput."""
        opportunity_id = ""
        if isinstance(input_data.opportunity, GrowthOpportunity):
            opportunity_id = input_data.opportunity.opportunity_id
        elif isinstance(input_data.opportunity, dict):
            opportunity_id = input_data.opportunity.get("opportunity_id", "")

        risk_level = "safe"
        risk_score = best_score.risk_score
        if risk:
            risk_level = risk.risk_level.value
            risk_score = risk.risk_score

        # 备选方案 (排除最优)
        alternatives = [s for s in scores if s.strategy_id != best_score.strategy_id]
        alternatives = alternatives[:5]  # 最多保留5个备选

        requires_approval = decision_type in {DecisionType.ESCALATE, DecisionType.BLOCK}

        return DecisionOutput(
            opportunity_id=opportunity_id,
            strategy_id=best_score.strategy_id,
            strategy_name=best_score.strategy_name,
            decision_type=decision_type,
            confidence=best_score.confidence,
            expected_reward=best_score.strategy_reward,
            risk_score=risk_score,
            risk_level=risk_level,
            final_score=best_score.final_score,
            action_plan=action_plan,
            alternatives=alternatives,
            requires_approval=requires_approval,
            metadata=input_data.metadata,
        )

    # ═══════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════

    def _extract_candidates(self, input_data: DecisionInput) -> list[StrategyCandidate]:
        """从 DecisionInput 提取 StrategyCandidate 列表."""
        candidates: list[StrategyCandidate] = []
        for s in input_data.strategies:
            if isinstance(s, StrategyCandidate):
                candidates.append(s)
            elif isinstance(s, dict):
                candidates.append(StrategyCandidate(
                    strategy_id=s.get("strategy_id", ""),
                    strategy_name=s.get("strategy_name", ""),
                    strategy=s,
                    historical_score=s.get("historical_score", 0.0),
                    confidence_score=s.get("confidence_score", 0.0),
                    risk_score=s.get("risk_score", 0.0),
                    final_score=s.get("final_score", 0.0),
                ))
        return candidates

    def _get_risk_for_best(
        self,
        best_score: DecisionScore,
        input_data: DecisionInput,
    ) -> RiskAssessment | None:
        """获取最优策略的风险评估."""
        sid = best_score.strategy_id
        risk = input_data.risks.get(sid) if input_data.risks else None
        if isinstance(risk, RiskAssessment):
            return risk
        return None

    def _extract_opportunity_type(self, input_data: DecisionInput) -> str:
        """从输入提取机会类型.

        优先使用 metadata 中的 opportunity_type (来自 DecisionEnhancer)，
        其次使用 opportunity 的 opportunity_type。
        """
        # 优先从 metadata 提取
        metadata = getattr(input_data, "metadata", {}) or {}
        if isinstance(metadata, dict):
            mt = metadata.get("opportunity_type", "")
            if mt:
                return mt

        # 备选: 从 opportunity 提取
        opp = input_data.opportunity
        if isinstance(opp, GrowthOpportunity):
            return opp.opportunity_type.value
        if isinstance(opp, dict):
            return opp.get("opportunity_type", "")
        return ""

    def _build_history_context(
        self,
        score: DecisionScore,
    ) -> dict[str, Any]:
        """构建历史上下文 (用于解释器)."""
        similar = self.memory.find_similar(
            strategy_id=score.strategy_id,
            limit=20,
        )
        resolved = [e for e in similar if e.is_resolved]

        return {
            "similar_cases": len(resolved),
            "success_rate": self.memory.get_strategy_success_rate(score.strategy_id),
            "total_experiences": self.memory.total_experiences,
        }

    def _estimate_execute_budget(
        self,
        score: DecisionScore,
        input_data: DecisionInput,
    ) -> float:
        """估算执行预算."""
        # 基于策略评分和默认预算
        return self.default_test_budget * 2.0 * score.final_score

    # ═══════════════════════════════════════════════════════════
    # Day 6.5: Decision History Integration
    # ═══════════════════════════════════════════════════════════

    def _query_decision_history(
        self,
        input_data: DecisionInput,
    ) -> DecisionHistoryResult | None:
        """查询历史决策轨迹 (Day 6.5 新增).

        从 DecisionMemory 检索与当前场景匹配的历史决策，
        让 DecisionEngine 了解"我之前做过什么"。
        """
        if self.decision_retriever is None:
            return None

        context = self._build_decision_context_from_input(input_data)
        if context is None:
            return None

        try:
            return self.decision_retriever.retrieve(context)
        except Exception:
            return None

    def _build_decision_context_from_input(
        self,
        input_data: DecisionInput,
    ) -> DecisionContext | None:
        """从 DecisionInput 构建 DecisionContext.

        优先使用 metadata 中的 opportunity_type (来自 DecisionEnhancer)，
        其次使用 opportunity 的 opportunity_type。
        """
        # 优先从 metadata 提取
        metadata = getattr(input_data, "metadata", {}) or {}
        if isinstance(metadata, dict):
            opportunity_type = metadata.get("opportunity_type", "")
        else:
            opportunity_type = ""

        # 备选: 从 opportunity 提取
        if not opportunity_type:
            opportunity_type = self._extract_opportunity_type(input_data)

        if not opportunity_type:
            return None

        # 提取 action_type (从最佳策略中)
        action_type = ""
        if input_data.strategies:
            s0 = input_data.strategies[0]
            if isinstance(s0, dict):
                inner = s0.get("strategy", {})
                if isinstance(inner, dict):
                    action_type = inner.get("action_type", "")
                if not action_type:
                    action_type = s0.get("action_type", "")
            elif hasattr(s0, "strategy"):
                # StrategyCandidate 等有 strategy 属性的对象
                strategy_attr = s0.strategy
                if isinstance(strategy_attr, dict):
                    action_type = strategy_attr.get("action_type", "")
            if not action_type and hasattr(s0, "action_type"):
                action_type = s0.action_type

        # 提取产品/平台/受众信息
        product_id = ""
        platform = ""
        audience_segment = ""
        metadata = getattr(input_data, "metadata", {}) or {}
        if isinstance(metadata, dict):
            product_id = metadata.get("product_id", "")
            platform = metadata.get("platform", "")
            audience_segment = metadata.get("audience_segment", "")

        return DecisionContext(
            opportunity_type=opportunity_type,
            action_type=action_type,
            product_id=product_id,
            platform=platform,
            audience_segment=audience_segment,
        )

    def _apply_history_confidence(
        self,
        score: DecisionScore,
        history: DecisionHistoryResult,
    ) -> DecisionScore:
        """基于历史决策调整置信度 (Day 6.5 新增).

        合并公式:
          adjusted_confidence = score.confidence × 0.7 + history.confidence × 0.3

        如果历史推荐的动作与当前策略匹配，额外提升置信度。
        """
        if history.total_matched == 0:
            return score

        # 基础合并: 历史置信度加权
        adjusted_confidence = round(
            score.confidence * 0.7 + history.confidence * 0.3,
            4,
        )

        # 如果历史推荐的动作与当前策略匹配，额外提升
        if history.recommended_action and history.recommended_action == score.strategy_name:
            adjusted_confidence = min(1.0, adjusted_confidence + 0.05)

        # 如果历史成功率很低，降低置信度
        if history.success_rate < 0.3 and history.total_matched >= 5:
            adjusted_confidence = max(0.0, adjusted_confidence - 0.10)

        score.confidence = adjusted_confidence
        # 重新计算 final_score
        score.final_score = round(
            score.strategy_reward * score.confidence * (1.0 - score.risk_score),
            4,
        )

        return score

    def _inject_history_to_output(
        self,
        output: DecisionOutput,
        history: DecisionHistoryResult,
    ) -> None:
        """将决策历史注入输出 (Day 6.5 新增).

        将历史检索结果写入 output.metadata 和 warnings，
        使下游系统可以了解决策的历史依据。
        仅在存在实际匹配时注入。
        """
        # 无匹配时不注入
        if history.total_matched == 0:
            return

        # 写入 metadata
        output.metadata["decision_history"] = {
            "total_matched": history.total_matched,
            "success_rate": history.success_rate,
            "confidence": history.confidence,
            "recommended_action": history.recommended_action,
            "match_dimensions": history.match_dimensions,
            "summary": history.summary,
        }

        # 添加历史警告
        for warning in history.warnings:
            if warning not in output.warnings:
                output.warnings.append(warning)

        # 添加历史推荐理由
        if history.recommended_action:
            output.reasons.append(
                f"Decision history: {history.total_matched} similar cases, "
                f"{history.success_rate:.0%} success rate → "
                f"recommend '{history.recommended_action}'"
            )

    # ═══════════════════════════════════════════════════════════
    # Day 7.1: Decision Confidence Engine Integration
    # ═══════════════════════════════════════════════════════════

    def _compute_decision_confidence(
        self,
        best_score: DecisionScore,
        input_data: DecisionInput,
    ) -> DecisionConfidence | None:
        """调用 DecisionConfidenceEngine 计算置信度 (Day 7.1 新增).

        从 DecisionMemorySync 和 PatternMemory 获取历史数据，
        多维度计算"这个策略我应该有多相信"。
        """
        if self.confidence_engine is None:
            return None

        opportunity_type = self._extract_opportunity_type(input_data)
        action_type = ""
        if best_score.strategy_name:
            action_type = best_score.strategy_name

        try:
            return self.confidence_engine.compute(
                strategy_id=best_score.strategy_id,
                strategy_name=best_score.strategy_name,
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
        except Exception:
            return None

    def _apply_confidence_engine(
        self,
        score: DecisionScore,
        confidence: DecisionConfidence,
    ) -> DecisionScore:
        """将置信度引擎结果应用到评分 (Day 7.1 新增).

        调整逻辑:
          - HIGH: 保持原置信度
          - MEDIUM: 置信度 × 0.85
          - LOW: 置信度 × 0.65
          - INSUFFICIENT: 置信度 × 0.40
        """
        level_multipliers = {
            "high": 1.0,
            "medium": 0.85,
            "low": 0.65,
            "insufficient": 0.40,
        }
        multiplier = level_multipliers.get(
            confidence.level.value if hasattr(confidence.level, 'value') else str(confidence.level),
            0.5,
        )

        score.confidence = round(score.confidence * multiplier, 4)
        # 重新计算 final_score
        score.final_score = round(
            score.strategy_reward * score.confidence * (1.0 - score.risk_score),
            4,
        )
        return score

    def _inject_confidence_to_output(
        self,
        output: DecisionOutput,
        confidence: DecisionConfidence,
    ) -> None:
        """将置信度评估注入输出 (Day 7.1 新增)."""
        output.metadata["decision_confidence"] = {
            "confidence_score": confidence.confidence_score,
            "level": confidence.level.value if hasattr(confidence.level, 'value') else str(confidence.level),
            "pattern_quality": confidence.pattern_quality,
            "sample_size_factor": confidence.sample_size_factor,
            "recency_factor": confidence.recency_factor,
            "reward_consistency": confidence.reward_consistency,
            "historical_success_rate": confidence.historical_success_rate,
            "total_samples": confidence.total_samples,
            "components": confidence.components,
        }

        # 添加置信度警告
        for warning in confidence.warnings:
            if warning not in output.warnings:
                output.warnings.append(warning)

        # 添加置信度理由
        level_label = (
            confidence.level.value.upper()
            if hasattr(confidence.level, 'value')
            else str(confidence.level).upper()
        )
        output.reasons.append(
            f"Decision confidence: {level_label} "
            f"({confidence.confidence_score:.2f}) "
            f"— {confidence.total_samples} historical samples, "
            f"{confidence.historical_success_rate:.0%} success rate"
        )

    # ═══════════════════════════════════════════════════════════
    # Day 7.2: Decision Value Predictor Integration
    # ═══════════════════════════════════════════════════════════

    def _compute_value_prediction(
        self,
        best_score: DecisionScore,
        input_data: DecisionInput,
    ) -> DecisionValuePrediction | None:
        """调用 DecisionValuePredictor 预测未来价值 (Day 7.2 新增).

        从 DecisionMemorySync 和 PatternStore 获取数据，
        预测"这个策略未来值多少钱"。
        """
        if self.value_predictor is None:
            return None

        opportunity_type = self._extract_opportunity_type(input_data)
        action_type = best_score.strategy_name or ""

        try:
            return self.value_predictor.predict(
                strategy_id=best_score.strategy_id,
                strategy_name=best_score.strategy_name,
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
        except Exception:
            return None

    def _apply_value_prediction(
        self,
        score: DecisionScore,
        prediction: DecisionValuePrediction,
    ) -> DecisionScore:
        """将价值预测应用到评分 (Day 7.2 新增).

        决策效用 = expected_value × prediction_confidence
        将预测价值融入 final_score:
          - 高价值 (EV >= 0.6): 提升评分
          - 中价值 (EV >= 0.3): 中性
          - 低价值 (EV < 0.3): 降低评分
          - 高衰减: 降低评分
        """
        # 决策效用权重: 0.3 (与历史评分 0.7 合并)
        utility_weight = 0.3

        # 衰减惩罚
        decay_penalty = 1.0
        if prediction.decay_risk >= 0.5:
            decay_penalty = 0.7
        elif prediction.decay_risk >= 0.3:
            decay_penalty = 0.85

        # 预测调整因子
        prediction_factor = prediction.decision_utility * decay_penalty

        # 合并: final_score = 历史评分 × 0.7 + 预测效用 × 0.3
        score.final_score = round(
            score.final_score * (1.0 - utility_weight)
            + prediction_factor * utility_weight,
            4,
        )
        return score

    def _inject_value_to_output(
        self,
        output: DecisionOutput,
        prediction: DecisionValuePrediction,
    ) -> None:
        """将价值预测注入输出 (Day 7.2 新增)."""
        output.metadata["predicted_value"] = {
            "expected_value": prediction.expected_value,
            "decision_utility": prediction.decision_utility,
            "avg_reward": prediction.avg_reward,
            "success_probability": prediction.success_probability,
            "scalability_score": prediction.scalability_score,
            "decay_risk": prediction.decay_risk,
            "sample_size": prediction.sample_size,
            "prediction_confidence": prediction.prediction_confidence,
            "horizon_days": prediction.horizon_days,
            "components": prediction.components,
        }

        # 添加价值预测警告
        for warning in prediction.warnings:
            if warning not in output.warnings:
                output.warnings.append(warning)

        # 添加价值预测理由
        if prediction.is_high_value:
            output.reasons.append(
                f"Value prediction: HIGH (EV={prediction.expected_value:.2f}, "
                f"utility={prediction.decision_utility:.2f}) "
                f"— scalable ({prediction.scalability_score:.0%}), "
                f"low decay ({prediction.decay_risk:.0%})"
            )
        elif prediction.is_high_decay:
            output.reasons.append(
                f"Value prediction: DECAYING (EV={prediction.expected_value:.2f}, "
                f"decay_risk={prediction.decay_risk:.0%}) "
                f"— strategy value is declining"
            )
        elif prediction.is_viable:
            output.reasons.append(
                f"Value prediction: VIABLE (EV={prediction.expected_value:.2f}, "
                f"utility={prediction.decision_utility:.2f}) "
                f"— {prediction.sample_size} samples, "
                f"{prediction.success_probability:.0%} success rate"
            )
        else:
            output.reasons.append(
                f"Value prediction: LOW (EV={prediction.expected_value:.2f}) "
                f"— insufficient evidence for high returns"
            )

    def _create_empty_decision(self, input_data: DecisionInput) -> DecisionOutput:
        """创建空决策 (无可用策略时)."""
        opportunity_id = ""
        if isinstance(input_data.opportunity, GrowthOpportunity):
            opportunity_id = input_data.opportunity.opportunity_id
        elif isinstance(input_data.opportunity, dict):
            opportunity_id = input_data.opportunity.get("opportunity_id", "")

        return DecisionOutput(
            opportunity_id=opportunity_id,
            decision_type=DecisionType.HOLD,
            reasons=["无可用策略"],
            warnings=["输入中无有效策略候选"],
            explanation="Decision: HOLD\nReason: No viable strategies available.",
        )

    # ═══════════════════════════════════════════════════════════
    # Day 7.3: Memory Consolidation Integration
    # ═══════════════════════════════════════════════════════════

    def _run_memory_consolidation(self) -> ConsolidationResult | None:
        """运行记忆整合清理 (Day 7.3 新增).

        在决策前调用 MemoryConsolidator 清理过期/低价值记忆，
        确保后续的历史查询只使用有效经验。

        处理逻辑:
          - 无 MemoryConsolidator → 跳过
          - 整合成功 → 返回 ConsolidationResult
          - 整合失败 → 静默返回 None (不阻塞决策流程)

        Returns:
            ConsolidationResult | None: 整合结果, 或 None (跳过/失败)
        """
        if self.memory_consolidator is None:
            return None

        try:
            result = self.memory_consolidator.consolidate()
            return result
        except Exception:
            # 记忆整合失败不应阻塞决策流程
            return None

    def _inject_consolidation_to_output(
        self,
        output: DecisionOutput,
        result: ConsolidationResult,
    ) -> None:
        """将记忆整合结果注入输出 (Day 7.3 新增).

        将 MemoryConsolidator 的整合统计写入 output.metadata，
        使下游系统可以了解记忆质量状态。

        注入内容:
          - consolidation_stats: 整合统计 (kept/archived/forgotten/分类)
          - 如果有清理动作 → 记录到 reasons
          - 如果记忆质量偏低 → 记录到 warnings
        """
        # 写入 metadata
        output.metadata["memory_consolidation"] = {
            "total_evaluated": result.total_evaluated,
            "kept": result.kept,
            "archived": result.archived,
            "forgotten": result.forgotten,
            "core_patterns": result.core_patterns,
            "temporary_patterns": result.temporary_patterns,
            "noise_count": result.noise_count,
            "failed_count": result.failed_count,
            "avg_memory_value": result.avg_memory_value,
            "retention_rate": result.retention_rate,
            "cleanup_rate": result.cleanup_rate,
            "timestamp": result.timestamp,
        }

        # 无记忆时跳过
        if result.total_evaluated == 0:
            return

        # 记录清理动作
        if result.forgotten > 0 or result.archived > 0:
            output.reasons.append(
                f"Memory consolidation: cleaned {result.forgotten + result.archived} "
                f"stale memories ({result.forgotten} forgotten, {result.archived} archived), "
                f"{result.kept} kept — retention rate {result.retention_rate:.0%}"
            )

        # 记忆质量警告
        if result.retention_rate < 0.3 and result.total_evaluated >= 10:
            output.warnings.append(
                f"Low memory retention ({result.retention_rate:.0%}): "
                f"only {result.kept}/{result.total_evaluated} memories retained. "
                f"Consider reviewing decision quality."
            )

        if result.failed_count > result.kept:
            output.warnings.append(
                f"Failed memories ({result.failed_count}) exceed "
                f"kept memories ({result.kept}). Decision quality may be declining."
            )