"""E13.7.7.4 Learning Policy Controller — 学习策略控制器.

Day 7.7.4:
  将 LearningStrategyOptimizer 和 AdaptiveConfidenceEngine 的输出
  统一为 LearningPolicyDecision，回答四个核心问题:
    1. 是否应该学习？ (should_learn)
    2. 是否应该刷新记忆？ (should_update_memory)
    3. 是否调整策略模式？ (strategy_mode)
    4. 产生的决策类型是什么？ (decision_type)

核心流程:
  LearningEffectiveness
  AdaptiveConfidenceResult
  LearningStrategyState
              |
              v
  LearningPolicyController.evaluate()
              |
              +--> _assess_should_learn()       → should_learn
              |
              +--> _assess_memory_refresh()      → should_update_memory
              |
              +--> _determine_strategy_mode()    → strategy_mode
              |
              +--> _classify_decision_type()     → decision_type
              |
              v
  LearningPolicyDecision

设计原则:
  - 不修改执行链: 只输出决策，不执行
  - 确定性: 基于明确规则，可解释
  - 可追溯: 每个决策包含 reasons 和 evidence
  - 可回滚: 所有决策默认可逆

用法:
  from growth_runtime.intelligence.learning.learning_policy_controller import (
      LearningPolicyController,
  )

  controller = LearningPolicyController()
  decision = controller.evaluate(
      effectiveness=effectiveness,
      adaptive_confidence=adaptive_result,
      current_state=state,
  )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .evaluation.models import LearningEffectiveness
from .models.adaptive_confidence_models import AdaptiveConfidenceResult
from .models.learning_strategy_models import (
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyAction,
    PolicyDecisionType,
    PolicyPriority,
)


# ═══════════════════════════════════════════════════════════════
# LearningPolicyController
# ═══════════════════════════════════════════════════════════════


class LearningPolicyController:
    """学习策略控制器 — 综合评估学习状态，输出策略决策.

    用法:
        controller = LearningPolicyController()
        decision = controller.evaluate(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_result,
            current_state=state,
        )

    Decision 包含:
        - should_learn: 是否允许学习系统更新
        - should_update_memory: 是否应刷新记忆
        - strategy_mode: 推荐的学习模式
        - decision_type: 综合决策类型
        - reasons: 决策原因列表
    """

    # ── 阈值配置 ─────────────────────────────────────────────────

    # 学习有效性: 视为"有效"的最低分数
    EFFECTIVENESS_EFFECTIVE_THRESHOLD = 0.50
    # 学习有效性: 高置信度阈值
    EFFECTIVENESS_HIGH_THRESHOLD = 0.70
    # 自适应置信度: 视为"可信"的最低分数
    ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD = 0.50
    # 自适应置信度: 高置信度阈值
    ADAPTIVE_CONFIDENCE_HIGH_THRESHOLD = 0.75
    # learning_gain: 视为"正向收益"的最小值
    LEARNING_GAIN_POSITIVE_THRESHOLD = 0.01
    # memory_decay_rate: 需要刷新的阈值
    MEMORY_DECAY_REFRESH_THRESHOLD = 0.02
    # pattern_weight: Pattern 失效阈值
    PATTERN_WEIGHT_LOW_THRESHOLD = 0.40

    def __init__(self) -> None:
        self._decision_count: int = 0
        self._decision_history: list[LearningPolicyDecision] = []

    @property
    def decision_count(self) -> int:
        return self._decision_count

    # ═══════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════

    def evaluate(
        self,
        effectiveness: LearningEffectiveness | None = None,
        adaptive_confidence: AdaptiveConfidenceResult | None = None,
        current_state: LearningStrategyState | None = None,
        triggered_by: str = "",
        context_patterns: list[Any] | None = None,
    ) -> LearningPolicyDecision:
        """综合评估学习状态，生成策略决策.

        Args:
            effectiveness: 学习有效性评估 (可选)
            adaptive_confidence: 自适应置信度结果 (可选)
            current_state: 当前学习策略状态 (可选)
            triggered_by: 触发来源标识
            context_patterns: 历史 Pattern 列表 (可选, Day 7.11 Step 1)

        Returns:
            LearningPolicyDecision: 综合策略决策
        """
        self._decision_count += 1
        state = current_state or LearningStrategyState.default()
        patterns = context_patterns or []

        # ── Pattern Context Analysis ──
        pattern_stats = self._analyze_pattern_context(patterns)

        # 1. 评估是否应该学习
        should_learn, learn_reasons = self._assess_should_learn(
            effectiveness, adaptive_confidence, state, pattern_stats,
        )

        # 2. 评估是否需要刷新记忆
        should_refresh, refresh_reasons = self._assess_memory_refresh(
            effectiveness, adaptive_confidence, state,
        )

        # 3. 确定推荐策略模式
        strategy_mode, mode_reasons = self._determine_strategy_mode(
            effectiveness, adaptive_confidence, state, pattern_stats,
        )

        # 4. 分类决策类型
        decision_type = self._classify_decision_type(
            should_learn, should_refresh, strategy_mode, state,
        )

        # 5. 汇总 reasons
        all_reasons = learn_reasons + refresh_reasons + mode_reasons
        if not all_reasons:
            all_reasons = ["All indicators nominal — maintaining current strategy"]

        # 6. 汇总 evidence
        evidence = self._build_evidence(
            should_learn, should_refresh, strategy_mode,
            effectiveness, adaptive_confidence, state, pattern_stats,
        )

        # 7. 计算决策置信度
        confidence = self._compute_decision_confidence(
            effectiveness, adaptive_confidence, state, pattern_stats,
        )

        # 8. 确定优先级
        priority = self._determine_priority(
            decision_type, should_learn, should_refresh, strategy_mode, state,
        )

        # 9. 确定推荐动作
        action = self._determine_action(
            decision_type, should_learn, should_refresh, strategy_mode,
        )

        # 10. 构建决策
        decision = LearningPolicyDecision(
            state_id=state.state_id,
            decision_type=decision_type,
            should_learn=should_learn,
            should_update_memory=should_refresh,
            strategy_mode=strategy_mode,
            action=action,
            priority=priority,
            evidence=evidence,
            reasons=all_reasons,
            confidence=confidence,
            adaptive_confidence=adaptive_confidence.adjusted_confidence if adaptive_confidence else 0.0,
            learning_effectiveness_score=effectiveness.effectiveness_score if effectiveness else 0.0,
            expected_impact=self._compute_expected_impact(decision_type),
            reversible=True,
            previous_state_snapshot=state.to_dict(),
            triggered_by=triggered_by,
        )

        self._decision_history.append(decision)
        return decision

    # ═══════════════════════════════════════════════════════════
    # Assessment 1: Should Learn
    # ═══════════════════════════════════════════════════════════

    def _assess_should_learn(
        self,
        effectiveness: LearningEffectiveness | None,
        adaptive_confidence: AdaptiveConfidenceResult | None,
        state: LearningStrategyState,
        pattern_stats: dict[str, Any] | None = None,
    ) -> tuple[bool, list[str]]:
        """评估是否应该允许学习系统更新.

        规则:
          1. 无有效性评估 → 允许学习 (默认开放)
          2. 学习有效 + 置信度足够 → 允许学习
          3. 学习无效 + 置信度不足 → 阻止学习
          4. 学习有效但置信度低 → 阻止学习 (不可靠)
          5. 学习无效但置信度高 → 阻止学习 (确定无效)
          6. [Day 7.11] 历史 Pattern 强证据覆盖: 即使当前置信度低，
             如果有足够多的高成功率历史 Pattern，允许学习
        """
        reasons: list[str] = []
        ps = pattern_stats or {}

        if effectiveness is None:
            reasons.append("No effectiveness evaluation — defaulting to allow learning")
            return True, reasons

        eff_score = effectiveness.effectiveness_score
        is_effective = effectiveness.is_effective
        learning_gain = effectiveness.learning_gain

        # 获取自适应置信度
        adaptive_conf = adaptive_confidence.adjusted_confidence if adaptive_confidence else 0.0

        # [Day 7.11] Pattern override: 低置信度但有强历史证据
        pattern_override = self._check_pattern_override(
            adaptive_conf, is_effective, ps,
        )

        # 学习有效 + 置信度足够 → 允许
        if is_effective and adaptive_conf >= self.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD:
            reasons.append(
                f"Learning effective (score={eff_score:.2f}, gain={learning_gain:+.4f}) "
                f"with sufficient confidence ({adaptive_conf:.2f}) → ALLOW_LEARNING"
            )
            return True, reasons

        # 学习有效但置信度低 → 检查 Pattern 覆盖
        if is_effective and adaptive_conf < self.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD:
            if pattern_override:
                reasons.append(
                    f"Learning effective (score={eff_score:.2f}) with low confidence "
                    f"({adaptive_conf:.2f}) BUT historical pattern evidence overrides "
                    f"→ ALLOW_LEARNING (pattern_count={ps.get('count', 0)}, "
                    f"avg_success={ps.get('avg_success_rate', 0):.2f})"
                )
                return True, reasons
            reasons.append(
                f"Learning effective (score={eff_score:.2f}) but adaptive confidence "
                f"too low ({adaptive_conf:.2f} < {self.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD}) → BLOCK_LEARNING"
            )
            return False, reasons

        # 学习无效 + 置信度高 → 阻止 (但有强 Pattern 时可能覆盖)
        if not is_effective and adaptive_conf >= self.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD:
            if pattern_override:
                reasons.append(
                    f"Learning ineffective (score={eff_score:.2f}) with high confidence "
                    f"({adaptive_conf:.2f}) BUT strong historical patterns suggest "
                    f"retrying → ALLOW_LEARNING (pattern_count={ps.get('count', 0)})"
                )
                return True, reasons
            reasons.append(
                f"Learning ineffective (score={eff_score:.2f}, gain={learning_gain:+.4f}) "
                f"with high confidence ({adaptive_conf:.2f}) → BLOCK_LEARNING"
            )
            return False, reasons

        # 学习无效 + 置信度低 → 阻止
        reasons.append(
            f"Learning ineffective (score={eff_score:.2f}) and confidence low "
            f"({adaptive_conf:.2f}) → BLOCK_LEARNING"
        )
        return False, reasons

    # ═══════════════════════════════════════════════════════════
    # Assessment 2: Should Update Memory
    # ═══════════════════════════════════════════════════════════

    def _assess_memory_refresh(
        self,
        effectiveness: LearningEffectiveness | None,
        adaptive_confidence: AdaptiveConfidenceResult | None,
        state: LearningStrategyState,
    ) -> tuple[bool, list[str]]:
        """评估是否需要刷新记忆系统.

        规则:
          1. memory_decay_rate 高于阈值 → 需要刷新
          2. pattern_weight 低于阈值 → Pattern 失效，需要刷新
          3. 学习无效 + 高置信度 → 需要刷新
          4. 保守模式 → 优先刷新
        """
        reasons: list[str] = []

        # 记忆衰减速率过高
        if state.memory_decay_rate >= self.MEMORY_DECAY_REFRESH_THRESHOLD:
            reasons.append(
                f"Memory decay rate high ({state.memory_decay_rate:.3f} >= "
                f"{self.MEMORY_DECAY_REFRESH_THRESHOLD}) → REQUEST_MEMORY_REFRESH"
            )
            return True, reasons

        # Pattern 权重过低
        if state.pattern_weight <= self.PATTERN_WEIGHT_LOW_THRESHOLD:
            reasons.append(
                f"Pattern weight critically low ({state.pattern_weight:.2f} <= "
                f"{self.PATTERN_WEIGHT_LOW_THRESHOLD}) → REQUEST_MEMORY_REFRESH"
            )
            return True, reasons

        # 学习无效 + 高置信度 → 记忆可能过时
        if effectiveness is not None and not effectiveness.is_effective:
            adaptive_conf = adaptive_confidence.adjusted_confidence if adaptive_confidence else 0.0
            if adaptive_conf >= self.ADAPTIVE_CONFIDENCE_HIGH_THRESHOLD:
                reasons.append(
                    f"Learning ineffective with high confidence "
                    f"({adaptive_conf:.2f}) → REQUEST_MEMORY_REFRESH"
                )
                return True, reasons

        # 保守模式优先刷新
        if state.is_conservative and state.memory_decay_rate >= 0.015:
            reasons.append(
                f"Conservative mode with elevated decay "
                f"({state.memory_decay_rate:.3f}) → REQUEST_MEMORY_REFRESH"
            )
            return True, reasons

        reasons.append("Memory system healthy — no refresh needed")
        return False, reasons

    # ═══════════════════════════════════════════════════════════
    # Assessment 3: Strategy Mode
    # ═══════════════════════════════════════════════════════════

    def _determine_strategy_mode(
        self,
        effectiveness: LearningEffectiveness | None,
        adaptive_confidence: AdaptiveConfidenceResult | None,
        state: LearningStrategyState,
        pattern_stats: dict[str, Any] | None = None,
        exploration_policy: Any = None,
    ) -> tuple[str, list[str]]:
        """确定推荐的学习模式.

        规则:
          - 高置信度 + 学习有效 → AGGRESSIVE (高信任、低探索)
          - 低置信度 + 学习无效 → CONSERVATIVE (低信任、高探索)
          - 其他 → BALANCED (默认)
          - [Day 7.11] 有强历史 Pattern → 倾向 AGGRESSIVE
          - [Day 7.11] 无历史 Pattern → 倾向 CONSERVATIVE
          - [Day 7.12] 探索策略集成: 当 explore=true 时 AGGRESSIVE → BALANCED
          - [Day 7.12] 高 uncertainty 强制 CONSERVATIVE
        """
        reasons: list[str] = []
        ps = pattern_stats or {}

        if effectiveness is None or adaptive_confidence is None:
            reasons.append("Insufficient data — maintaining current mode")
            return state.learning_mode, reasons

        adaptive_conf = adaptive_confidence.adjusted_confidence
        eff_score = effectiveness.effectiveness_score

        # [Day 7.11] Pattern influence on mode
        has_strong_patterns = ps.get("high_confidence_count", 0) >= 3
        has_no_patterns = ps.get("count", 0) == 0

        # [Day 7.12] Uncertainty assessment (仅在 pattern_stats 有数据时生效)
        pattern_count = ps.get("count", 0)
        avg_pattern_conf = ps.get("avg_confidence", 0.0)
        has_pattern_data = pattern_count > 0
        is_high_uncertainty = has_pattern_data and (pattern_count < 3 or avg_pattern_conf < 0.50)

        # [Day 7.12] 高 uncertainty → CONSERVATIVE
        if is_high_uncertainty:
            reasons.append(
                f"High uncertainty (patterns={pattern_count}, "
                f"avg_conf={avg_pattern_conf:.2f}) → CONSERVATIVE mode"
            )
            return LearningMode.CONSERVATIVE.value, reasons

        # AGGRESSIVE: 高置信度 + 高有效性
        if (adaptive_conf >= self.ADAPTIVE_CONFIDENCE_HIGH_THRESHOLD
                and eff_score >= self.EFFECTIVENESS_HIGH_THRESHOLD):
            # [Day 7.12] 探索策略覆盖: 需要探索时降级为 BALANCED
            if exploration_policy is not None and exploration_policy.should_explore():
                reasons.append(
                    f"High confidence ({adaptive_conf:.2f}) + high effectiveness "
                    f"({eff_score:.2f}) but exploration required → BALANCED mode"
                )
                return LearningMode.BALANCED.value, reasons
            reasons.append(
                f"High confidence ({adaptive_conf:.2f}) + high effectiveness "
                f"({eff_score:.2f}) → AGGRESSIVE mode"
            )
            return LearningMode.AGGRESSIVE.value, reasons

        # [Day 7.11] 有强 Pattern 证据 → 即使中等置信度也倾向 AGGRESSIVE
        if has_strong_patterns and eff_score >= self.EFFECTIVENESS_EFFECTIVE_THRESHOLD:
            if exploration_policy is not None and exploration_policy.should_explore():
                reasons.append(
                    f"Strong historical patterns ({ps.get('high_confidence_count', 0)} high-conf) "
                    f"but exploration required → BALANCED mode"
                )
                return LearningMode.BALANCED.value, reasons
            reasons.append(
                f"Strong historical patterns ({ps.get('high_confidence_count', 0)} high-conf) "
                f"with moderate effectiveness ({eff_score:.2f}) → AGGRESSIVE mode"
            )
            return LearningMode.AGGRESSIVE.value, reasons

        # CONSERVATIVE: 低置信度 + 低有效性
        if (adaptive_conf < self.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD
                and eff_score < self.EFFECTIVENESS_EFFECTIVE_THRESHOLD):
            reasons.append(
                f"Low confidence ({adaptive_conf:.2f}) + low effectiveness "
                f"({eff_score:.2f}) → CONSERVATIVE mode"
            )
            return LearningMode.CONSERVATIVE.value, reasons

        # CONSERVATIVE: 学习无效 + 高置信度 (确定无效)
        if (not effectiveness.is_effective
                and adaptive_conf >= self.ADAPTIVE_CONFIDENCE_HIGH_THRESHOLD):
            reasons.append(
                f"Learning confirmed ineffective with high confidence "
                f"({adaptive_conf:.2f}) → CONSERVATIVE mode"
            )
            return LearningMode.CONSERVATIVE.value, reasons

        # [Day 7.11] 无历史 Pattern → 倾向保守探索
        if has_no_patterns and eff_score < self.EFFECTIVENESS_HIGH_THRESHOLD:
            reasons.append(
                f"No historical patterns available + moderate effectiveness "
                f"({eff_score:.2f}) → CONSERVATIVE mode (safe exploration)"
            )
            return LearningMode.CONSERVATIVE.value, reasons

        reasons.append(
            f"Balanced indicators (conf={adaptive_conf:.2f}, eff={eff_score:.2f}) "
            f"→ BALANCED mode"
        )
        return LearningMode.BALANCED.value, reasons

    # ═══════════════════════════════════════════════════════════
    # Classification: Decision Type
    # ═══════════════════════════════════════════════════════════

    def _classify_decision_type(
        self,
        should_learn: bool,
        should_refresh: bool,
        strategy_mode: str,
        state: LearningStrategyState,
    ) -> str:
        """分类综合决策类型.

        优先级: BLOCK > REFRESH > ADJUST_MODE > ALLOW > MAINTAIN
        """
        # 1. 阻止学习优先级最高
        if not should_learn:
            return PolicyDecisionType.BLOCK_LEARNING.value

        # 2. 需要刷新记忆
        if should_refresh:
            return PolicyDecisionType.REQUEST_MEMORY_REFRESH.value

        # 3. 模式需要调整
        if strategy_mode != state.learning_mode:
            return PolicyDecisionType.ADJUST_MODE.value

        # 4. 允许学习
        if should_learn:
            return PolicyDecisionType.ALLOW_LEARNING.value

        # 5. 默认保持
        return PolicyDecisionType.MAINTAIN.value

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    def _build_evidence(
        self,
        should_learn: bool,
        should_refresh: bool,
        strategy_mode: str,
        effectiveness: LearningEffectiveness | None,
        adaptive_confidence: AdaptiveConfidenceResult | None,
        state: LearningStrategyState,
        pattern_stats: dict[str, Any] | None = None,
    ) -> list[str]:
        """构建支持证据列表."""
        evidence: list[str] = []
        ps = pattern_stats or {}

        if effectiveness is not None:
            evidence.append(
                f"effectiveness_score={effectiveness.effectiveness_score:.2f}"
            )
            evidence.append(
                f"learning_gain={effectiveness.learning_gain:+.4f}"
            )

        if adaptive_confidence is not None:
            evidence.append(
                f"adaptive_confidence={adaptive_confidence.adjusted_confidence:.2f}"
            )
            evidence.append(
                f"confidence_level={adaptive_confidence.confidence_level}"
            )

        # [Day 7.11] Pattern context evidence
        if ps.get("count", 0) > 0:
            evidence.append(
                f"matched_patterns={ps.get('count', 0)}"
            )
            evidence.append(
                f"pattern_avg_success={ps.get('avg_success_rate', 0):.2f}"
            )
            evidence.append(
                f"pattern_high_confidence={ps.get('high_confidence_count', 0)}"
            )

        evidence.append(f"current_mode={state.learning_mode}")
        evidence.append(f"recommended_mode={strategy_mode}")
        evidence.append(f"should_learn={should_learn}")
        evidence.append(f"should_refresh={should_refresh}")

        return evidence

    def _compute_decision_confidence(
        self,
        effectiveness: LearningEffectiveness | None,
        adaptive_confidence: AdaptiveConfidenceResult | None,
        state: LearningStrategyState,
        pattern_stats: dict[str, Any] | None = None,
    ) -> float:
        """计算决策自身的置信度.

        基于:
          - 自适应置信度 (权重 0.5)
          - 学习有效性 (权重 0.3)
          - 状态稳定性 (权重 0.2)
          - [Day 7.11] Pattern 历史证据 boost (最多 +0.15)
          - [Day 7.12] 历史决策准确率校准
        """
        components: list[float] = []
        weights: list[float] = []
        ps = pattern_stats or {}

        if adaptive_confidence is not None:
            components.append(adaptive_confidence.adjusted_confidence)
            weights.append(0.5)
        else:
            components.append(0.5)
            weights.append(0.5)

        if effectiveness is not None:
            components.append(effectiveness.effectiveness_score)
            weights.append(0.3)
        else:
            components.append(0.5)
            weights.append(0.3)

        # 状态稳定性: 模式越稳定，置信度越高
        stability = 0.50
        if state.is_balanced:
            stability = 0.70
        elif state.is_aggressive:
            stability = 0.60
        components.append(stability)
        weights.append(0.2)

        raw_conf = sum(w * c for w, c in zip(weights, components))

        # [Day 7.12] 置信度校准: 基于历史决策准确率
        historical_accuracy = self._get_historical_accuracy(
            PolicyDecisionType.ALLOW_LEARNING.value
        )
        calibrated = self._calibrate_confidence(
            raw_conf, historical_accuracy if historical_accuracy is not None else raw_conf
        )

        # [Day 7.11] Pattern boost: 历史证据增强置信度 (在校准后应用)
        pattern_boost = self._compute_pattern_boost(ps)
        total = min(1.0, calibrated + pattern_boost)

        return round(total, 4)

    def _calibrate_confidence(self, raw_conf: float, historical_accuracy: float) -> float:
        """基于历史决策准确率校准置信度.

        [Day 7.12] 校准公式:
          calibrated = raw_conf × 0.6 + historical_accuracy × 0.4

        Args:
            raw_conf: 原始置信度 [0, 1]
            historical_accuracy: 历史准确率 [0, 1]

        Returns:
            float: 校准后置信度 [0, 1]
        """
        calibrated = raw_conf * 0.6 + historical_accuracy * 0.4
        return round(max(0.0, min(1.0, calibrated)), 4)

    def _get_historical_accuracy(self, decision_type: str) -> float | None:
        """查询同类型决策的历史准确率.

        [Day 7.12] 基于最近 N 次同类型决策中正确预测的比例。

        Args:
            decision_type: 决策类型

        Returns:
            float | None: 历史准确率，无历史数据时返回 None
        """
        matching = [
            d for d in self._decision_history
            if d.decision_type == decision_type
        ]
        if not matching:
            return None

        # 准确率 = 正确预测数 / 总数
        # "正确" 定义为 should_learn=True 且 confidence >= 0.5 的决策
        correct = sum(
            1 for d in matching
            if d.should_learn and d.confidence >= 0.5
        )
        return round(correct / len(matching), 4)

    def _determine_priority(
        self,
        decision_type: str,
        should_learn: bool,
        should_refresh: bool,
        strategy_mode: str,
        state: LearningStrategyState,
    ) -> str:
        """确定决策优先级."""
        # BLOCK 总是高优先级
        if decision_type == PolicyDecisionType.BLOCK_LEARNING.value:
            return PolicyPriority.HIGH.value

        # 模式切换需要关注
        if strategy_mode != state.learning_mode:
            return PolicyPriority.HIGH.value

        # 记忆刷新中等优先级
        if should_refresh:
            return PolicyPriority.MEDIUM.value

        return PolicyPriority.LOW.value

    def _determine_action(
        self,
        decision_type: str,
        should_learn: bool,
        should_refresh: bool,
        strategy_mode: str,
    ) -> str:
        """确定推荐动作."""
        if decision_type == PolicyDecisionType.BLOCK_LEARNING.value:
            return PolicyAction.ADJUST_CONFIDENCE_THRESHOLD.value
        if decision_type == PolicyDecisionType.REQUEST_MEMORY_REFRESH.value:
            return PolicyAction.REFRESH_MEMORY.value
        if decision_type == PolicyDecisionType.ADJUST_MODE.value:
            return PolicyAction.SWITCH_LEARNING_MODE.value
        if decision_type == PolicyDecisionType.ALLOW_LEARNING.value:
            return PolicyAction.STRENGTHEN_PATTERN.value
        return PolicyAction.INCREASE_EXPLORATION.value

    def _compute_expected_impact(self, decision_type: str) -> float:
        """计算预期影响."""
        impact_map = {
            PolicyDecisionType.BLOCK_LEARNING.value: -0.10,       # 可能错过机会
            PolicyDecisionType.REQUEST_MEMORY_REFRESH.value: 0.15,  # 可能改善
            PolicyDecisionType.ADJUST_MODE.value: 0.05,            # 轻微调整
            PolicyDecisionType.ALLOW_LEARNING.value: 0.10,         # 积极影响
            PolicyDecisionType.MAINTAIN.value: 0.0,                # 无变化
        }
        return impact_map.get(decision_type, 0.0)

    # ═══════════════════════════════════════════════════════════
    # Utility
    # ═══════════════════════════════════════════════════════════

    # ── Day 7.11: Pattern Context Analysis ─────────────────────

    def _analyze_pattern_context(
        self,
        patterns: list[Any],
    ) -> dict[str, Any]:
        """分析 Pattern 上下文，提取统计信息.

        Args:
            patterns: PatternMemory 列表

        Returns:
            dict: {
                count: 匹配 Pattern 总数,
                avg_success_rate: 平均成功率,
                avg_confidence: 平均置信度,
                high_confidence_count: 高置信度 (>0.7) Pattern 数,
                total_samples: 总样本数,
            }
        """
        if not patterns:
            return {
                "count": 0,
                "avg_success_rate": 0.0,
                "avg_confidence": 0.0,
                "high_confidence_count": 0,
                "total_samples": 0,
            }

        count = len(patterns)
        success_rates: list[float] = []
        confidences: list[float] = []
        total_samples = 0
        high_conf_count = 0

        for p in patterns:
            perf = getattr(p, "performance", None)
            if perf is not None:
                sr = getattr(perf, "success_rate", 0.0)
                ac = getattr(perf, "avg_confidence", 0.0)
                samples = getattr(perf, "samples", 0)
                success_rates.append(sr)
                confidences.append(ac)
                total_samples += samples
                if ac >= 0.70:
                    high_conf_count += 1

        avg_success = (
            round(sum(success_rates) / len(success_rates), 4)
            if success_rates else 0.0
        )
        avg_confidence = (
            round(sum(confidences) / len(confidences), 4)
            if confidences else 0.0
        )

        return {
            "count": count,
            "avg_success_rate": avg_success,
            "avg_confidence": avg_confidence,
            "high_confidence_count": high_conf_count,
            "total_samples": total_samples,
        }

    def _check_pattern_override(
        self,
        adaptive_conf: float,
        is_effective: bool,
        pattern_stats: dict[str, Any],
    ) -> bool:
        """检查历史 Pattern 是否有足够证据覆盖当前判断.

        条件:
          - 至少 2 个匹配 Pattern
          - 平均成功率 >= 0.60
          - 至少 1 个高置信度 (>0.7) Pattern

        Args:
            adaptive_conf: 当前自适应置信度
            is_effective: 当前是否有效
            pattern_stats: Pattern 统计信息

        Returns:
            bool: 是否应该覆盖
        """
        count = pattern_stats.get("count", 0)
        avg_success = pattern_stats.get("avg_success_rate", 0.0)
        high_conf = pattern_stats.get("high_confidence_count", 0)

        if count < 2:
            return False
        if avg_success < 0.60:
            return False
        if high_conf < 1:
            return False

        return True

    def _compute_pattern_boost(
        self,
        pattern_stats: dict[str, Any],
    ) -> float:
        """计算 Pattern 历史证据对决策置信度的 boost.

        boost = min(0.15, count * 0.02 + avg_success * 0.10)

        最大 boost = 0.15 (限制在合理范围)

        Args:
            pattern_stats: Pattern 统计信息

        Returns:
            float: boost 值 (0.0 ~ 0.15)
        """
        count = pattern_stats.get("count", 0)
        avg_success = pattern_stats.get("avg_success_rate", 0.0)

        if count == 0:
            return 0.0

        boost = count * 0.02 + avg_success * 0.10
        return round(min(0.15, boost), 4)

    def reset(self) -> None:
        """重置控制器状态."""
        self._decision_count = 0
        self._decision_history.clear()

    def get_decision_history(self) -> list[LearningPolicyDecision]:
        """获取决策历史."""
        return list(self._decision_history)

    def __repr__(self) -> str:
        return (
            f"LearningPolicyController("
            f"decisions={self._decision_count})"
        )


__all__ = [
    "LearningPolicyController",
]