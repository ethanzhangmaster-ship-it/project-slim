"""E17.11.2 Experience Write Pipeline — 经验写入路径.

Day 7.11 Step 2:
  将 ExecutionResult 自动转化为 GrowthExperience 并写入 ExperienceStore，
  包含重要性评分和自动整合触发。

核心流程:
  LearningExecutionResult
      │
      ▼
  ExperienceBuilder.build()         → GrowthExperience
      │
      ▼
  ExperienceImportanceScorer.score() → ImportanceScore
      │
      ▼
  (重要性 >= 阈值?)
      │
   YES ├──→ ExperienceStore.store()
      │         │
      │         ▼
      │    (新经验数 >= 触发阈值?)
      │         │
      │      YES ├──→ MemoryConsolidationPipeline.consolidate()
      │         │
      │         ▼
      │    ExperienceWriteResult
      │
   NO  └──→ ExperienceWriteResult (SKIPPED)

连接:
  LearningCycleOrchestrator._update_memory() → ExperienceWritePipeline
  ExperienceWritePipeline → ExperienceStore → MemoryConsolidationPipeline

设计原则:
  - 编排层，不实现具体算法
  - 每个阶段 fail-safe
  - 可审计的写入记录
  - 不修改已有模块
"""

from __future__ import annotations

import time
from typing import Any

from ...memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
)
from .models.experience_write_models import (
    ConsolidationTrigger,
    ExperienceBuildResult,
    ExperienceImportanceLevel,
    ExperienceWriteResult,
    ImportanceScore,
    WriteBatchResult,
    WriteStatus,
)


# ═══════════════════════════════════════════════════════════════
# ExperienceBuilder
# ═══════════════════════════════════════════════════════════════


class ExperienceBuilder:
    """ExecutionResult → GrowthExperience 转换器.

    将 LearningExecutionResult 转化为 GrowthExperience，
    提取执行前后的指标变化，构建完整经验对象。

    用法:
        builder = ExperienceBuilder()
        result = builder.build(execution_result)
    """

    # ── 阈值配置 ─────────────────────────────────────────────────

    # 结果等级判定阈值
    STRONG_SUCCESS_THRESHOLD = 0.30  # 指标改善 > 30%
    SUCCESS_THRESHOLD = 0.05         # 指标改善 > 5%
    FAILURE_THRESHOLD = -0.05        # 指标恶化 < -5%
    STRONG_FAILURE_THRESHOLD = -0.30 # 指标恶化 < -30%

    def __init__(self) -> None:
        self._build_count: int = 0

    def build(self, execution_result: Any) -> ExperienceBuildResult:
        """将执行结果转化为经验.

        Args:
            execution_result: LearningExecutionResult 实例

        Returns:
            ExperienceBuildResult
        """
        start = time.perf_counter()
        self._build_count += 1

        try:
            if execution_result is None:
                raise ValueError("execution_result is None")

            # 提取关键字段
            success = getattr(execution_result, "success", False)
            action = getattr(execution_result, "action", "")
            prev_state = getattr(execution_result, "previous_state", None) or {}
            new_state = getattr(execution_result, "new_state", None) or {}
            metadata = getattr(execution_result, "metadata", None) or {}
            reasons = getattr(execution_result, "reasons", None) or []
            policy_type = getattr(execution_result, "policy_decision_type", "")

            # 提取指标
            metrics_before = self._extract_metrics(prev_state)
            metrics_after = self._extract_metrics(new_state)
            metrics_delta = self._compute_delta(metrics_before, metrics_after)

            # 构建 outcome
            outcome = self._build_outcome(
                success, metrics_before, metrics_after, metrics_delta,
            )

            # 计算 reward
            reward = self._compute_reward(success, metrics_delta, outcome)

            # 推断类别
            category = self._infer_category(action, metadata)

            # 构建 context
            context = self._build_context(execution_result, metadata)

            # 构建 GrowthExperience
            experience = GrowthExperience(
                context=context,
                action_type=action,
                action_params={
                    "policy_decision_type": policy_type,
                    "reasons": reasons,
                },
                outcome=outcome,
                reward=reward,
                confidence=self._extract_confidence(execution_result),
                category=category,
                tags=self._generate_tags(action, success, outcome),
                metadata={
                    "source": "execution_result",
                    "build_count": self._build_count,
                    "policy_decision_type": policy_type,
                },
            )

            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return ExperienceBuildResult(
                success=True,
                experience=experience,
                build_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return ExperienceBuildResult(
                success=False,
                error=str(e),
                build_time_ms=duration_ms,
            )

    def _extract_metrics(self, state: dict[str, Any]) -> dict[str, float]:
        """从状态中提取数值指标."""
        metrics: dict[str, float] = {}
        if not state:
            return metrics

        # 尝试从 state["metrics"] 提取
        inner = state.get("metrics", {})
        if isinstance(inner, dict):
            for k, v in inner.items():
                if isinstance(v, (int, float)):
                    metrics[k] = float(v)

        # 直接从 state 提取数值字段
        for k, v in state.items():
            if k == "metrics":
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                metrics[k] = float(v)

        return metrics

    def _compute_delta(
        self,
        before: dict[str, float],
        after: dict[str, float],
    ) -> dict[str, float]:
        """计算指标变化."""
        delta: dict[str, float] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            v_before = before.get(key, 0.0)
            v_after = after.get(key, 0.0)
            delta[key] = round(v_after - v_before, 4)
        return delta

    def _build_outcome(
        self,
        success: bool,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
        metrics_delta: dict[str, float],
    ) -> ExperienceOutcome:
        """构建 ExperienceOutcome."""
        # 计算总体变化率
        total_delta = sum(metrics_delta.values()) if metrics_delta else 0.0
        total_before = sum(abs(v) for v in metrics_before.values()) if metrics_before else 0.0
        change_rate = total_delta / total_before if total_before > 0 else 0.0

        # 判定结果等级
        if change_rate >= self.STRONG_SUCCESS_THRESHOLD:
            level = ExperienceOutcomeLevel.STRONG_SUCCESS
        elif change_rate >= self.SUCCESS_THRESHOLD:
            level = ExperienceOutcomeLevel.SUCCESS
        elif change_rate >= self.FAILURE_THRESHOLD:
            level = ExperienceOutcomeLevel.NEUTRAL
        elif change_rate >= self.STRONG_FAILURE_THRESHOLD:
            level = ExperienceOutcomeLevel.FAILURE
        else:
            level = ExperienceOutcomeLevel.STRONG_FAILURE

        # 实际奖励: 基于变化率的归一化
        actual_reward = round(max(0.0, min(1.0, 0.5 + change_rate * 1.5)), 4)

        # 影响描述
        impact = self._describe_impact(change_rate, metrics_delta)

        return ExperienceOutcome(
            success=success,
            outcome_level=level,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            metrics_delta=metrics_delta,
            actual_impact=impact,
            actual_reward=actual_reward,
        )

    def _compute_reward(
        self,
        success: bool,
        metrics_delta: dict[str, float],
        outcome: ExperienceOutcome,
    ) -> float:
        """计算综合奖励."""
        # 基础奖励: 基于结果等级
        level_reward = {
            ExperienceOutcomeLevel.STRONG_SUCCESS: 0.95,
            ExperienceOutcomeLevel.SUCCESS: 0.75,
            ExperienceOutcomeLevel.NEUTRAL: 0.50,
            ExperienceOutcomeLevel.FAILURE: 0.25,
            ExperienceOutcomeLevel.STRONG_FAILURE: 0.05,
        }
        base = level_reward.get(outcome.outcome_level, 0.50)

        # 如果执行失败，reward 降低
        if not success:
            base = max(0.0, base - 0.30)

        return round(base, 4)

    def _infer_category(
        self,
        action: str,
        metadata: dict[str, Any],
    ) -> ExperienceCategory:
        """从 action 推断经验类别."""
        creative_actions = {
            "clone_dna", "generate_variants", "mutate_hook", "mutate_visual",
            "create_population", "launch_ab_test", "replace_creative",
        }
        ua_actions = {
            "increase_budget", "reduce_budget", "duplicate_campaign",
            "pause_campaign", "expand_targeting", "reallocate_budget", "adjust_bid",
            "execute_learning", "block_learning", "refresh_memory",
            "update_strategy", "no_action",
        }
        revenue_actions = {
            "optimize_pricing", "optimize_ad_placement", "increase_retention",
            "create_high_value_audience",
        }

        if action in creative_actions:
            return ExperienceCategory.CREATIVE
        elif action in ua_actions:
            return ExperienceCategory.UA
        elif action in revenue_actions:
            return ExperienceCategory.REVENUE

        # 从 metadata 推断
        cat = metadata.get("category", "")
        if cat in ("creative", "ua", "revenue", "monetization"):
            return ExperienceCategory(cat)

        return ExperienceCategory.UA

    def _build_context(
        self,
        execution_result: Any,
        metadata: dict[str, Any],
    ) -> ExperienceContext:
        """构建 ExperienceContext."""
        action = getattr(execution_result, "action", "")
        return ExperienceContext(
            opportunity_type=metadata.get("opportunity_type", action),
            action_type=action,
            entity_type=metadata.get("entity_type", "learning"),
            entity_id=metadata.get("entity_id", ""),
            trigger_signals=metadata.get("trigger_signals", []),
            market_conditions=metadata.get("market_conditions", {}),
        )

    def _extract_confidence(self, execution_result: Any) -> float:
        """从执行结果中提取置信度."""
        meta = getattr(execution_result, "metadata", None) or {}
        conf = meta.get("confidence", 0.0)
        if isinstance(conf, (int, float)):
            return float(conf)
        return 0.5

    def _generate_tags(
        self,
        action: str,
        success: bool,
        outcome: ExperienceOutcome,
    ) -> list[str]:
        """生成经验标签."""
        tags = [action]
        if success:
            tags.append("success")
        else:
            tags.append("failure")
        level = outcome.outcome_level
        if level in (ExperienceOutcomeLevel.STRONG_SUCCESS, ExperienceOutcomeLevel.SUCCESS):
            tags.append("positive")
        elif level in (ExperienceOutcomeLevel.FAILURE, ExperienceOutcomeLevel.STRONG_FAILURE):
            tags.append("negative")
        else:
            tags.append("neutral")
        return tags

    def _describe_impact(
        self,
        change_rate: float,
        metrics_delta: dict[str, float],
    ) -> str:
        """描述影响."""
        if not metrics_delta:
            return "No measurable impact"
        top_deltas = sorted(
            metrics_delta.items(), key=lambda x: abs(x[1]), reverse=True,
        )[:3]
        parts = [f"{k}: {v:+.4f}" for k, v in top_deltas]
        direction = "improved" if change_rate > 0 else "declined"
        return f"Metrics {direction}: {', '.join(parts)}"

    @property
    def build_count(self) -> int:
        return self._build_count


# ═══════════════════════════════════════════════════════════════
# ExperienceImportanceScorer
# ═══════════════════════════════════════════════════════════════


class ExperienceImportanceScorer:
    """经验重要性评分器.

    评分公式:
      importance = impact × 0.4 + confidence × 0.3 + novelty × 0.2 + repeatability × 0.1

    等级划分:
      >= 0.80 → CRITICAL
      >= 0.60 → HIGH
      >= 0.40 → MEDIUM
      >= 0.20 → LOW
      < 0.20  → NEGLIGIBLE

    用法:
        scorer = ExperienceImportanceScorer()
        score = scorer.score(experience, existing_experiences)
    """

    # ── 权重配置 ─────────────────────────────────────────────────

    IMPACT_WEIGHT = 0.40
    CONFIDENCE_WEIGHT = 0.30
    NOVELTY_WEIGHT = 0.20
    REPEATABILITY_WEIGHT = 0.10

    # ── 等级阈值 ─────────────────────────────────────────────────

    CRITICAL_THRESHOLD = 0.80
    HIGH_THRESHOLD = 0.60
    MEDIUM_THRESHOLD = 0.40
    LOW_THRESHOLD = 0.20

    # ── 最低写入阈值 ──────────────────────────────────────────────

    MIN_WRITE_THRESHOLD = 0.20

    def __init__(self) -> None:
        self._score_count: int = 0

    def score(
        self,
        experience: GrowthExperience,
        existing_experiences: list[GrowthExperience] | None = None,
    ) -> ImportanceScore:
        """评估经验重要性.

        Args:
            experience: GrowthExperience 实例
            existing_experiences: 已存在的经验列表 (用于计算 novelty/repeatability)

        Returns:
            ImportanceScore
        """
        self._score_count += 1
        existing = existing_experiences or []
        reasons: list[str] = []

        if experience is None:
            return ImportanceScore(
                total_score=0.0,
                level=ExperienceImportanceLevel.NEGLIGIBLE,
                reasons=["experience is None"],
            )

        # 1. Impact: 基于实际奖励
        impact = self._calc_impact(experience)
        reasons.append(f"impact={impact:.2f} (reward={experience.reward:.2f})")

        # 2. Confidence: 基于经验置信度
        confidence = self._calc_confidence(experience)
        reasons.append(f"confidence={confidence:.2f}")

        # 3. Novelty: 是否是新动作类型
        novelty = self._calc_novelty(experience, existing)
        if novelty > 0.5:
            reasons.append(f"novelty={novelty:.2f} (new action type)")
        else:
            reasons.append(f"novelty={novelty:.2f} (known action)")

        # 4. Repeatability: 同类动作历史成功率
        repeatability = self._calc_repeatability(experience, existing)
        reasons.append(f"repeatability={repeatability:.2f}")

        # 加权计算
        total = round(
            impact * self.IMPACT_WEIGHT
            + confidence * self.CONFIDENCE_WEIGHT
            + novelty * self.NOVELTY_WEIGHT
            + repeatability * self.REPEATABILITY_WEIGHT,
            4,
        )

        # 等级判定
        level = self._classify_level(total)

        return ImportanceScore(
            total_score=total,
            impact=impact,
            confidence=confidence,
            novelty=novelty,
            repeatability=repeatability,
            level=level,
            reasons=reasons,
        )

    def _calc_impact(self, experience: GrowthExperience) -> float:
        """计算影响因子: 基于 reward."""
        return experience.reward

    def _calc_confidence(self, experience: GrowthExperience) -> float:
        """计算置信度因子."""
        return experience.confidence

    def _calc_novelty(
        self,
        experience: GrowthExperience,
        existing: list[GrowthExperience],
    ) -> float:
        """计算新颖性: 1.0 = 全新, 0.0 = 很常见."""
        if not existing:
            return 1.0

        action = experience.action_type
        same_action = [e for e in existing if e.action_type == action]
        count = len(same_action)

        # 完全没见过: 1.0, 见过很多: 趋近 0
        if count == 0:
            return 1.0
        # 指数衰减: 见过 1 次 = 0.5, 见过 5 次 = 0.03
        novelty = round(1.0 / (1.0 + count), 4)
        return novelty

    def _calc_repeatability(
        self,
        experience: GrowthExperience,
        existing: list[GrowthExperience],
    ) -> float:
        """计算可重复性: 同类动作历史成功率."""
        if not existing:
            return 0.5  # 没有历史数据，中性

        action = experience.action_type
        same_action = [e for e in existing if e.action_type == action]

        if not same_action:
            return 0.5

        successes = sum(1 for e in same_action if e.is_successful())
        return round(successes / len(same_action), 4)

    def _classify_level(self, total: float) -> ExperienceImportanceLevel:
        """判定重要性等级."""
        if total >= self.CRITICAL_THRESHOLD:
            return ExperienceImportanceLevel.CRITICAL
        elif total >= self.HIGH_THRESHOLD:
            return ExperienceImportanceLevel.HIGH
        elif total >= self.MEDIUM_THRESHOLD:
            return ExperienceImportanceLevel.MEDIUM
        elif total >= self.LOW_THRESHOLD:
            return ExperienceImportanceLevel.LOW
        else:
            return ExperienceImportanceLevel.NEGLIGIBLE

    def should_write(self, score: ImportanceScore) -> bool:
        """判断是否应该写入."""
        return score.total_score >= self.MIN_WRITE_THRESHOLD

    @property
    def score_count(self) -> int:
        return self._score_count


# ═══════════════════════════════════════════════════════════════
# ExperienceWritePipeline
# ═══════════════════════════════════════════════════════════════


class ExperienceWritePipeline:
    """经验写入流水线 — 编排 Build → Score → Store → Consolidate.

    用法:
        pipeline = ExperienceWritePipeline(
            experience_store=store,
            consolidation_pipeline=consolidation,
        )
        result = pipeline.write(execution_result)
        batch_result = pipeline.write_batch(execution_results)
    """

    def __init__(
        self,
        experience_store: Any = None,  # ExperienceStore
        consolidation_pipeline: Any = None,  # MemoryConsolidationPipeline
        trigger: ConsolidationTrigger | None = None,
    ) -> None:
        """初始化写入流水线.

        Args:
            experience_store: ExperienceStore 实例
            consolidation_pipeline: MemoryConsolidationPipeline 实例
            trigger: 整合触发配置
        """
        self._builder = ExperienceBuilder()
        self._scorer = ExperienceImportanceScorer()
        self._experience_store = experience_store
        self._consolidation_pipeline = consolidation_pipeline
        self._trigger = trigger or ConsolidationTrigger.default()
        self._write_count: int = 0
        self._consolidation_count: int = 0
        self._last_consolidation_at: int = 0  # 上次整合时的写入计数

    # ── Properties ──────────────────────────────────────────────

    @property
    def write_count(self) -> int:
        return self._write_count

    @property
    def consolidation_count(self) -> int:
        return self._consolidation_count

    @property
    def builder(self) -> ExperienceBuilder:
        return self._builder

    @property
    def scorer(self) -> ExperienceImportanceScorer:
        return self._scorer

    # ── Public API ──────────────────────────────────────────────

    def write(self, execution_result: Any) -> ExperienceWriteResult:
        """写入单条经验.

        Args:
            execution_result: LearningExecutionResult 实例

        Returns:
            ExperienceWriteResult
        """
        self._write_count += 1

        # ── Step 1: Build ──
        build_result = self._builder.build(execution_result)
        if not build_result.success:
            return ExperienceWriteResult(
                status=WriteStatus.FAILED,
                build_result=build_result,
                error=build_result.error,
            )

        experience = build_result.experience

        # ── Step 2: Score ──
        try:
            existing = self._get_existing_experiences()
        except Exception:
            existing = []
        importance = self._scorer.score(experience, existing)

        # ── Step 3: Quality Gate ──
        if not self._scorer.should_write(importance):
            return ExperienceWriteResult(
                status=WriteStatus.SKIPPED_LOW_IMPORTANCE,
                experience_id=experience.experience_id,
                importance=importance,
                build_result=build_result,
            )

        # ── Step 4: Store ──
        stored = False
        try:
            if self._experience_store is not None:
                self._experience_store.store(experience)
                stored = True
        except Exception as e:
            return ExperienceWriteResult(
                status=WriteStatus.FAILED,
                experience_id=experience.experience_id,
                importance=importance,
                build_result=build_result,
                error=f"Store failed: {e}",
            )

        # ── Step 5: Consolidation Trigger ──
        consolidation_triggered = False
        consolidation_report = None
        if self._should_trigger_consolidation():
            try:
                consolidation_report = self._trigger_consolidation()
                consolidation_triggered = True
            except Exception:
                pass

        return ExperienceWriteResult(
            status=WriteStatus.WRITTEN,
            experience_id=experience.experience_id,
            importance=importance,
            build_result=build_result,
            stored=stored,
            consolidation_triggered=consolidation_triggered,
            consolidation_report=consolidation_report,
        )

    def write_batch(self, execution_results: list[Any]) -> WriteBatchResult:
        """批量写入经验.

        Args:
            execution_results: LearningExecutionResult 列表

        Returns:
            WriteBatchResult
        """
        results: list[ExperienceWriteResult] = []
        written = 0
        skipped = 0
        failed = 0
        consolidation_triggered = False
        consolidation_report = None

        for er in execution_results:
            result = self.write(er)
            results.append(result)

            if result.is_written:
                written += 1
            elif result.is_skipped:
                skipped += 1
            else:
                failed += 1

            if result.consolidation_triggered:
                consolidation_triggered = True
                consolidation_report = result.consolidation_report

        return WriteBatchResult(
            total=len(execution_results),
            written=written,
            skipped=skipped,
            failed=failed,
            consolidation_triggered=consolidation_triggered,
            consolidation_report=consolidation_report,
            results=results,
        )

    # ── Internal ────────────────────────────────────────────────

    def _get_existing_experiences(self) -> list[GrowthExperience]:
        """获取已有经验列表."""
        if self._experience_store is None:
            return []
        try:
            return self._experience_store.get_all()
        except Exception:
            return []

    def _should_trigger_consolidation(self) -> bool:
        """检查是否应该触发整合."""
        if not self._trigger.enabled:
            return False
        if not self._trigger.auto_trigger:
            return False
        if self._consolidation_pipeline is None:
            return False
        if self._experience_store is None:
            return False

        # 检查经验数量
        try:
            count = self._experience_store.count
        except Exception:
            return False

        if count < self._trigger.min_experience_count:
            return False

        # 检查冷却周期
        since_last = self._write_count - self._last_consolidation_at
        if since_last < self._trigger.cooldown_cycles:
            return False

        return True

    def _trigger_consolidation(self) -> Any:
        """触发整合."""
        self._consolidation_count += 1
        self._last_consolidation_at = self._write_count

        if self._consolidation_pipeline is None:
            return None

        return self._consolidation_pipeline.consolidate(None)

    # ── Management ──────────────────────────────────────────────

    def reset(self) -> None:
        """重置流水线状态."""
        self._write_count = 0
        self._consolidation_count = 0
        self._last_consolidation_at = 0
        self._builder = ExperienceBuilder()
        self._scorer = ExperienceImportanceScorer()

    def set_trigger(self, trigger: ConsolidationTrigger) -> None:
        """设置整合触发配置."""
        self._trigger = trigger


__all__ = [
    "ExperienceBuilder",
    "ExperienceImportanceScorer",
    "ExperienceWritePipeline",
]