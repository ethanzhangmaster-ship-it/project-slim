"""E15.5 Execution Result Feedback Bridge — 执行结果到经验记忆的桥接.

填充自主增长闭环的最后缺口:
  Execution Engine (E15)
      ↓
  EngineResult (立即执行结果)
      ↓
  [等待 Reality Layer 返回业务指标]
      ↓
  ExecutionResultBridge.capture()     ← 本模块
      ↓
  ExecutionResultBridge.evaluate()    ← 本模块
      ↓
  GrowthExperience
      ↓
  ExperienceStore (E13.4.1)
      ↓
  PatternMemory (E13.4.2)
      ↓
  Future Decision (E13.5)

核心职责:
  1. 捕获 E15 EngineResult + 执行前的业务指标 (metrics_before)
  2. 等待 Reality Layer 返回执行后的业务指标 (metrics_after)
  3. 评估业务结果 (ROAS delta, CTR delta, CVR delta 等)
  4. 计算综合 reward
  5. 创建 GrowthExperience 并写入 ExperienceStore
  6. 触发 PatternMemory 更新

与 FeedbackLoop 的区别:
  - FeedbackLoop (E13.6.5): 评估执行质量 (成功率、效率、安全)
  - ExecutionResultBridge (E15.5): 评估业务结果 (ROAS 变化、素材表现)

用法:
    bridge = ExecutionResultBridge(
        experience_store=experience_store,
        pattern_store=pattern_store,
    )

    # Step 1: 捕获执行结果 + 执行前指标
    entry = bridge.capture(
        engine_result=engine_result,
        context=execution_context,
        metrics_before={"roas": 0.42, "ctr": 0.021, "cvr": 0.08},
    )

    # ... 等待 7 天，Reality Layer 返回最新指标 ...

    # Step 2: 评估业务结果
    result = bridge.evaluate(
        entry=entry,
        metrics_after={"roas": 0.51, "ctr": 0.028, "cvr": 0.11},
    )
    # → ROAS +21.4%, 写入 ExperienceStore

    # 或者一步完成:
    result = bridge.bridge(
        engine_result=engine_result,
        context=execution_context,
        metrics_before={"roas": 0.42, "ctr": 0.021},
        metrics_after={"roas": 0.51, "ctr": 0.028},
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..execution_context import ExecutionContext
from ..execution_core import EngineResult

# 延迟导入避免循环依赖
_EXPERIENCE_MODELS = None


def _get_experience_models():
    global _EXPERIENCE_MODELS
    if _EXPERIENCE_MODELS is None:
        from ...memory.models import (
            ExperienceCategory,
            ExperienceContext,
            ExperienceOutcome,
            ExperienceOutcomeLevel,
            GrowthExperience,
        )
        _EXPERIENCE_MODELS = (
            ExperienceCategory,
            ExperienceContext,
            ExperienceOutcome,
            ExperienceOutcomeLevel,
            GrowthExperience,
        )
    return _EXPERIENCE_MODELS


# ═══════════════════════════════════════════════════════════════
# 业务指标权重 (与 ResultEvaluator 对齐)
# ═══════════════════════════════════════════════════════════════

BUSINESS_METRIC_WEIGHTS: dict[str, float] = {
    "roas": 0.35,
    "ctr": 0.25,
    "cvr": 0.20,
    "cpi": 0.20,
}

# 正向指标 (越高越好)
HIGHER_IS_BETTER = {"roas", "ctr", "cvr"}

# 负向指标 (越低越好)
LOWER_IS_BETTER = {"cpi", "cpa"}

# 指标显示名称
METRIC_DISPLAY_NAMES: dict[str, str] = {
    "roas": "ROAS",
    "ctr": "CTR",
    "cvr": "CVR",
    "cpi": "CPI",
    "cpa": "CPA",
    "spend": "Spend",
    "impressions": "Impressions",
    "frequency": "Frequency",
    "d7_roas": "D7 ROAS",
    "d30_roas": "D30 ROAS",
    "payer_rate": "Payer Rate",
}


# ═══════════════════════════════════════════════════════════════
# Bridge Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class BridgeEntry:
    """桥接条目 — 已捕获的执行结果，等待业务指标评估.

    Attributes:
        bridge_id:            桥接条目唯一标识
        engine_result:        E15 执行引擎结果
        context:              执行上下文
        metrics_before:       执行前业务指标
        action_type:          执行动作类型
        opportunity_id:       来源机会 ID
        decision_id:          关联决策 ID
        captured_at:          捕获时间
        metadata:             扩展元数据
    """

    bridge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    engine_result: EngineResult | None = None
    context: ExecutionContext | None = None
    metrics_before: dict[str, float] = field(default_factory=dict)
    action_type: str = ""
    opportunity_id: str = ""
    decision_id: str = ""
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_metrics_before(self) -> bool:
        """是否有执行前指标."""
        return len(self.metrics_before) > 0

    @property
    def is_ready(self) -> bool:
        """是否准备好评估 (有执行结果 + 执行前指标)."""
        return self.engine_result is not None and self.has_metrics_before

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_id": self.bridge_id,
            "action_type": self.action_type,
            "opportunity_id": self.opportunity_id,
            "decision_id": self.decision_id,
            "metrics_before": self.metrics_before,
            "captured_at": self.captured_at,
            "engine_result": self.engine_result.to_dict() if self.engine_result else None,
            "context": self.context.to_dict() if self.context else None,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"BridgeEntry(id={self.bridge_id[:8]}..., "
            f"action={self.action_type}, "
            f"ready={self.is_ready})"
        )


# ═══════════════════════════════════════════════════════════════
# Bridge Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class BridgeResult:
    """桥接结果 — 评估完成后的输出.

    Attributes:
        bridge_id:            来源桥接条目 ID
        experience:           生成的 GrowthExperience
        experience_stored:    是否已写入 ExperienceStore
        pattern_updated:      是否触发 PatternMemory 更新
        reward:               综合奖励 [0, 1]
        improvement_score:    业务改善分数
        outcome_level:        结果等级
        metrics_delta:        指标变化
        learning_summary:     学习摘要
        evaluated_at:         评估时间
        metadata:             扩展元数据
    """

    bridge_id: str = ""
    experience: Any = None  # GrowthExperience
    experience_stored: bool = False
    pattern_updated: bool = False
    reward: float = 0.0
    improvement_score: float = 0.0
    outcome_level: str = "neutral"
    metrics_delta: dict[str, float] = field(default_factory=dict)
    learning_summary: str = ""
    evaluated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """业务结果是否正向."""
        return self.improvement_score > 0.05

    @property
    def is_significant_improvement(self) -> bool:
        """是否有显著改善 (>15%)."""
        return self.improvement_score > 0.15

    @property
    def is_degradation(self) -> bool:
        """是否有退化."""
        return self.improvement_score < -0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_id": self.bridge_id,
            "experience_stored": self.experience_stored,
            "pattern_updated": self.pattern_updated,
            "reward": round(self.reward, 4),
            "improvement_score": round(self.improvement_score, 4),
            "outcome_level": self.outcome_level,
            "metrics_delta": {k: round(v, 4) for k, v in self.metrics_delta.items()},
            "learning_summary": self.learning_summary,
            "evaluated_at": self.evaluated_at,
            "is_successful": self.is_successful,
            "is_significant_improvement": self.is_significant_improvement,
            "is_degradation": self.is_degradation,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"BridgeResult(id={self.bridge_id[:8]}..., "
            f"improvement={self.improvement_score:+.1%}, "
            f"outcome={self.outcome_level})"
        )


# ═══════════════════════════════════════════════════════════════
# Execution Result Bridge
# ═══════════════════════════════════════════════════════════════


class ExecutionResultBridge:
    """E15.5 Execution Result Feedback Bridge.

    将 E15 Execution Engine 的输出与 E13 Memory Layer 连接，
    形成完整的自主增长闭环。

    Attributes:
        experience_store:    E13.4.1 ExperienceStore 实例
        pattern_store:       E13.4.2 PatternStore 实例 (可选)
        min_improvement:     最低改善阈值 (低于此值视为无影响)
        min_confidence:      最低置信度 (低于此值的 entry 不评估)
        pending_entries:     待评估的桥接条目
        bridge_history:      已完成的桥接结果
    """

    # 默认阈值
    DEFAULT_MIN_IMPROVEMENT = 0.02
    DEFAULT_MIN_CONFIDENCE = 0.0
    DEFAULT_MAX_PENDING = 1000

    def __init__(
        self,
        experience_store: Any = None,
        pattern_store: Any = None,
        decision_sync: Any = None,  # DecisionMemorySync (Day 6.5)
        min_improvement: float = 0.02,
        min_confidence: float = 0.0,
        max_pending: int = 1000,
    ):
        self._experience_store = experience_store
        self._pattern_store = pattern_store
        self._decision_sync = decision_sync  # Day 6.5
        self._min_improvement = min_improvement
        self._min_confidence = min_confidence
        self._max_pending = max_pending

        self._pending: dict[str, BridgeEntry] = {}
        self._history: list[BridgeResult] = []
        self._total_bridged: int = 0

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def experience_store(self) -> Any:
        return self._experience_store

    @property
    def pattern_store(self) -> Any:
        return self._pattern_store

    @property
    def decision_sync(self) -> Any:
        """Day 6.5: DecisionMemorySync 实例."""
        return self._decision_sync

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def total_bridged(self) -> int:
        return self._total_bridged

    # ═══════════════════════════════════════════════════════════
    # Capture: 捕获执行结果
    # ═══════════════════════════════════════════════════════════

    def capture(
        self,
        engine_result: EngineResult,
        context: ExecutionContext | None = None,
        metrics_before: dict[str, float] | None = None,
        action_type: str = "",
        opportunity_id: str = "",
        decision_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BridgeEntry:
        """捕获执行结果 + 执行前指标，创建待评估的桥接条目.

        Args:
            engine_result:   E15 执行引擎结果
            context:         执行上下文
            metrics_before:  执行前业务指标 (ROAS, CTR, CVR 等)
            action_type:     执行动作类型
            opportunity_id:  来源机会 ID
            decision_id:     关联决策 ID
            metadata:        扩展元数据

        Returns:
            BridgeEntry: 待评估条目
        """
        # 从 context 提取补充信息
        if context is not None:
            opportunity_id = opportunity_id or context.opportunity_id
            decision_id = decision_id or context.decision_id

        entry = BridgeEntry(
            engine_result=engine_result,
            context=context,
            metrics_before=metrics_before or {},
            action_type=action_type,
            opportunity_id=opportunity_id,
            decision_id=decision_id,
            metadata=metadata or {},
        )

        self._pending[entry.bridge_id] = entry

        # 容量控制
        if len(self._pending) > self._max_pending:
            oldest = sorted(self._pending.keys())[0]
            self._pending.pop(oldest, None)

        return entry

    def capture_batch(
        self,
        engine_results: list[EngineResult],
        contexts: list[ExecutionContext] | None = None,
        metrics_before_list: list[dict[str, float]] | None = None,
        action_types: list[str] | None = None,
        opportunity_ids: list[str] | None = None,
        decision_ids: list[str] | None = None,
    ) -> list[BridgeEntry]:
        """批量捕获执行结果.

        Args:
            engine_results:     E15 执行引擎结果列表
            contexts:           执行上下文列表 (与 engine_results 一一对应)
            metrics_before_list: 执行前指标列表
            action_types:       动作类型列表
            opportunity_ids:    机会 ID 列表
            decision_ids:       决策 ID 列表

        Returns:
            list[BridgeEntry]: 待评估条目列表
        """
        entries: list[BridgeEntry] = []
        n = len(engine_results)

        for i in range(n):
            entry = self.capture(
                engine_result=engine_results[i],
                context=contexts[i] if contexts and i < len(contexts) else None,
                metrics_before=metrics_before_list[i] if metrics_before_list and i < len(metrics_before_list) else None,
                action_type=action_types[i] if action_types and i < len(action_types) else "",
                opportunity_id=opportunity_ids[i] if opportunity_ids and i < len(opportunity_ids) else "",
                decision_id=decision_ids[i] if decision_ids and i < len(decision_ids) else "",
            )
            entries.append(entry)

        return entries

    # ═══════════════════════════════════════════════════════════
    # Evaluate: 评估业务结果
    # ═══════════════════════════════════════════════════════════

    def evaluate(
        self,
        entry: BridgeEntry,
        metrics_after: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> BridgeResult:
        """评估业务结果，生成 GrowthExperience 并写入 Memory.

        Args:
            entry:          桥接条目 (来自 capture())
            metrics_after:  执行后业务指标
            metadata:       扩展元数据

        Returns:
            BridgeResult: 评估结果
        """
        evaluated_at = datetime.now(timezone.utc).isoformat()

        # 1. 计算指标变化 (delta)
        metrics_delta = self._compute_metrics_delta(
            entry.metrics_before, metrics_after
        )

        # 2. 计算综合改善分数
        improvement_score = self._compute_improvement_score(metrics_delta)

        # 3. 计算 reward
        reward = self._compute_reward(
            improvement_score=improvement_score,
            engine_result=entry.engine_result,
        )

        # 4. 判定结果等级
        outcome_level = self._classify_outcome(
            improvement_score=improvement_score,
            reward=reward,
        )

        # 5. 生成学习摘要
        learning_summary = self._generate_learning_summary(
            improvement_score=improvement_score,
            metrics_delta=metrics_delta,
            metrics_before=entry.metrics_before,
            metrics_after=metrics_after,
            action_type=entry.action_type,
        )

        result = BridgeResult(
            bridge_id=entry.bridge_id,
            reward=reward,
            improvement_score=improvement_score,
            outcome_level=outcome_level,
            metrics_delta=metrics_delta,
            learning_summary=learning_summary,
            evaluated_at=evaluated_at,
            metadata={
                "action_type": entry.action_type,
                "opportunity_id": entry.opportunity_id,
                "decision_id": entry.decision_id,
                **(entry.metadata or {}),
                **(metadata or {}),
            },
        )

        # 6. 创建 GrowthExperience 并写入 ExperienceStore
        if self._experience_store is not None:
            experience = self._create_experience(entry, result, metrics_after)
            result.experience = experience
            try:
                self._experience_store.store(experience)
                result.experience_stored = True
            except Exception:
                pass

        # 7. 触发 PatternMemory 更新 (如果有足够经验)
        if self._pattern_store is not None and result.experience_stored:
            try:
                self._trigger_pattern_update(entry, result)
                result.pattern_updated = True
            except Exception:
                pass

        # 7.5. 同步到 DecisionMemorySync (Day 6.5 新增)
        if self._decision_sync is not None and entry.decision_id:
            try:
                self._sync_to_decision_memory(entry, result)
            except Exception:
                pass

        # 8. 从 pending 移除
        self._pending.pop(entry.bridge_id, None)

        # 9. 记录历史
        self._history.append(result)
        self._total_bridged += 1

        return result

    def evaluate_by_id(
        self,
        bridge_id: str,
        metrics_after: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> BridgeResult | None:
        """按 bridge_id 评估.

        Args:
            bridge_id:     桥接条目 ID
            metrics_after: 执行后业务指标
            metadata:      扩展元数据

        Returns:
            BridgeResult | None: 条目不存在时返回 None
        """
        entry = self._pending.get(bridge_id)
        if entry is None:
            return None
        return self.evaluate(entry, metrics_after, metadata=metadata)

    # ═══════════════════════════════════════════════════════════
    # Bridge: 一步桥接 (capture + evaluate)
    # ═══════════════════════════════════════════════════════════

    def bridge(
        self,
        engine_result: EngineResult,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
        context: ExecutionContext | None = None,
        action_type: str = "",
        opportunity_id: str = "",
        decision_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BridgeResult:
        """一步完成桥接: capture + evaluate.

        适用于已知执行前后指标的离线评估场景。

        Args:
            engine_result:   E15 执行引擎结果
            metrics_before:  执行前业务指标
            metrics_after:   执行后业务指标
            context:         执行上下文
            action_type:     执行动作类型
            opportunity_id:  来源机会 ID
            decision_id:     关联决策 ID
            metadata:        扩展元数据

        Returns:
            BridgeResult: 评估结果
        """
        entry = self.capture(
            engine_result=engine_result,
            context=context,
            metrics_before=metrics_before,
            action_type=action_type,
            opportunity_id=opportunity_id,
            decision_id=decision_id,
            metadata=metadata,
        )
        return self.evaluate(entry, metrics_after)

    def bridge_batch(
        self,
        engine_results: list[EngineResult],
        metrics_before_list: list[dict[str, float]],
        metrics_after_list: list[dict[str, float]],
        contexts: list[ExecutionContext] | None = None,
        action_types: list[str] | None = None,
        opportunity_ids: list[str] | None = None,
        decision_ids: list[str] | None = None,
    ) -> list[BridgeResult]:
        """批量一步桥接.

        Args:
            engine_results:     E15 执行引擎结果列表
            metrics_before_list: 执行前指标列表
            metrics_after_list:  执行后指标列表
            contexts:           执行上下文列表
            action_types:       动作类型列表
            opportunity_ids:    机会 ID 列表
            decision_ids:       决策 ID 列表

        Returns:
            list[BridgeResult]: 评估结果列表
        """
        entries = self.capture_batch(
            engine_results=engine_results,
            contexts=contexts,
            metrics_before_list=metrics_before_list,
            action_types=action_types,
            opportunity_ids=opportunity_ids,
            decision_ids=decision_ids,
        )
        results: list[BridgeResult] = []
        for i, entry in enumerate(entries):
            result = self.evaluate(entry, metrics_after_list[i])
            results.append(result)
        return results

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def get_pending(self) -> list[BridgeEntry]:
        """获取所有待评估条目."""
        return list(self._pending.values())

    def get_pending_by_action(self, action_type: str) -> list[BridgeEntry]:
        """按动作类型获取待评估条目."""
        return [e for e in self._pending.values() if e.action_type == action_type]

    def get_pending_by_opportunity(self, opportunity_id: str) -> list[BridgeEntry]:
        """按机会 ID 获取待评估条目."""
        return [e for e in self._pending.values() if e.opportunity_id == opportunity_id]

    def get_history(self, limit: int = 50) -> list[BridgeResult]:
        """获取最近的桥接历史."""
        return self._history[-limit:]

    def get_successful(self) -> list[BridgeResult]:
        """获取业务结果正向的桥接."""
        return [r for r in self._history if r.is_successful]

    def get_degradations(self) -> list[BridgeResult]:
        """获取业务结果退化的桥接."""
        return [r for r in self._history if r.is_degradation]

    def get_significant_improvements(self) -> list[BridgeResult]:
        """获取显著改善的桥接."""
        return [r for r in self._history if r.is_significant_improvement]

    def get_by_action(self, action_type: str) -> list[BridgeResult]:
        """按动作类型获取桥接历史."""
        return [r for r in self._history if r.metadata.get("action_type", "") == action_type]

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def stats(self) -> dict[str, Any]:
        """获取桥接统计."""
        total = len(self._history)
        if total == 0:
            return {
                "total_bridged": 0,
                "pending": self.pending_count,
                "success_rate": 0.0,
                "avg_improvement": 0.0,
                "avg_reward": 0.0,
                "by_outcome": {},
                "by_action": {},
            }

        successful = sum(1 for r in self._history if r.is_successful)
        degradations = sum(1 for r in self._history if r.is_degradation)
        significant = sum(1 for r in self._history if r.is_significant_improvement)
        neutral = total - successful - degradations

        avg_improvement = round(
            sum(r.improvement_score for r in self._history) / total, 4
        )
        avg_reward = round(
            sum(r.reward for r in self._history) / total, 4
        )

        by_outcome: dict[str, int] = {}
        for r in self._history:
            by_outcome[r.outcome_level] = by_outcome.get(r.outcome_level, 0) + 1

        by_action: dict[str, dict[str, float]] = {}
        action_groups: dict[str, list[BridgeResult]] = {}
        for r in self._history:
            a = r.metadata.get("action_type", "unknown")
            if a not in action_groups:
                action_groups[a] = []
            action_groups[a].append(r)
        for a, group in action_groups.items():
            s = sum(1 for r in group if r.is_successful)
            by_action[a] = {
                "count": len(group),
                "success_count": s,
                "success_rate": round(s / len(group), 4) if group else 0.0,
                "avg_improvement": round(
                    sum(r.improvement_score for r in group) / len(group), 4
                ),
                "avg_reward": round(
                    sum(r.reward for r in group) / len(group), 4
                ),
            }

        return {
            "total_bridged": self._total_bridged,
            "history_count": total,
            "pending": self.pending_count,
            "successful_count": successful,
            "degradation_count": degradations,
            "significant_count": significant,
            "neutral_count": neutral,
            "success_rate": round(successful / total, 4),
            "avg_improvement": avg_improvement,
            "avg_reward": avg_reward,
            "by_outcome": by_outcome,
            "by_action": by_action,
        }

    def get_improvement_trend(self, window: int = 10) -> list[float]:
        """获取最近 N 次桥接的改善趋势."""
        recent = self._history[-window:]
        return [r.improvement_score for r in recent]

    # ═══════════════════════════════════════════════════════════
    # Management
    # ═══════════════════════════════════════════════════════════════

    def clear_pending(self) -> None:
        """清空待评估条目."""
        self._pending.clear()

    def clear_history(self) -> None:
        """清空桥接历史."""
        self._history.clear()

    def reset(self) -> None:
        """重置桥接器."""
        self._pending.clear()
        self._history.clear()
        self._total_bridged = 0

    def expire_old_entries(self, max_age_hours: float = 168.0) -> int:
        """过期旧的待评估条目 (默认 7 天).

        Args:
            max_age_hours: 最大保留时间 (小时)

        Returns:
            int: 已过期的条目数
        """
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []
        for bid, entry in self._pending.items():
            try:
                captured = datetime.fromisoformat(entry.captured_at)
                age_hours = (now - captured).total_seconds() / 3600
                if age_hours > max_age_hours:
                    expired_ids.append(bid)
            except (ValueError, TypeError):
                expired_ids.append(bid)

        for bid in expired_ids:
            self._pending.pop(bid, None)

        return len(expired_ids)

    # ═══════════════════════════════════════════════════════════
    # Internal: Metric Computation
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _compute_metrics_delta(
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
    ) -> dict[str, float]:
        """计算指标变化 (delta).

        Args:
            metrics_before: 执行前指标
            metrics_after:  执行后指标

        Returns:
            dict[str, float]: 各指标的变化率
        """
        deltas: dict[str, float] = {}
        all_metrics = set(metrics_before.keys()) | set(metrics_after.keys())

        for metric in all_metrics:
            before = metrics_before.get(metric, 0.0)
            after = metrics_after.get(metric, 0.0)

            if before == 0.0 and after == 0.0:
                continue

            if before == 0.0:
                delta = 1.0 if after > 0 else 0.0
            else:
                delta = (after - before) / abs(before)

            deltas[metric] = delta

        return deltas

    @staticmethod
    def _compute_improvement_score(metrics_delta: dict[str, float]) -> float:
        """计算综合改善分数.

        使用加权公式: roas×0.35 + ctr×0.25 + cvr×0.20 + cpi×0.20
        仅对存在 delta 的指标进行加权平均。

        Args:
            metrics_delta: 指标变化率

        Returns:
            float: 综合改善分数 [-1, 1]
        """
        total_weight = 0.0
        weighted_score = 0.0

        for metric, weight in BUSINESS_METRIC_WEIGHTS.items():
            if metric not in metrics_delta:
                continue

            delta = metrics_delta[metric]

            # 负向指标反向
            if metric in LOWER_IS_BETTER:
                delta = -delta

            total_weight += weight
            weighted_score += delta * weight

        if total_weight == 0:
            return 0.0

        return weighted_score / total_weight

    @staticmethod
    def _compute_reward(
        improvement_score: float,
        engine_result: EngineResult | None = None,
    ) -> float:
        """计算综合 reward.

        Reward = 0.7 × improvement_score + 0.3 × execution_quality

        Args:
            improvement_score: 业务改善分数
            engine_result:     执行引擎结果

        Returns:
            float: 综合奖励 [0, 1]
        """
        # 业务结果权重 0.7
        outcome_reward = max(0.0, min(1.0, (improvement_score + 1.0) / 2.0))

        # 执行质量权重 0.3
        if engine_result is not None:
            execution_quality = engine_result.success_rate
        else:
            execution_quality = 1.0

        reward = 0.7 * outcome_reward + 0.3 * execution_quality
        return round(max(0.0, min(1.0, reward)), 4)

    @staticmethod
    def _classify_outcome(
        improvement_score: float,
        reward: float,
    ) -> str:
        """判定结果等级.

        Args:
            improvement_score: 改善分数
            reward:            综合奖励

        Returns:
            str: strong_success / success / neutral / failure / strong_failure
        """
        if improvement_score > 0.30 and reward > 0.7:
            return "strong_success"
        elif improvement_score > 0.05:
            return "success"
        elif improvement_score < -0.30 and reward < 0.3:
            return "strong_failure"
        elif improvement_score < -0.05:
            return "failure"
        else:
            return "neutral"

    @staticmethod
    def _generate_learning_summary(
        improvement_score: float,
        metrics_delta: dict[str, float],
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
        action_type: str = "",
    ) -> str:
        """生成学习摘要.

        Args:
            improvement_score: 改善分数
            metrics_delta:     指标变化
            metrics_before:    执行前指标
            metrics_after:     执行后指标
            action_type:       动作类型

        Returns:
            str: 可读的学习摘要
        """
        if not metrics_delta:
            return "No metrics delta available"

        # 找出贡献最大的指标
        best_metric = ""
        best_abs_delta = 0.0
        for metric, delta in metrics_delta.items():
            abs_delta = abs(delta)
            if abs_delta > best_abs_delta:
                best_abs_delta = abs_delta
                best_metric = metric

        if not best_metric:
            return "No significant metric change"

        display = METRIC_DISPLAY_NAMES.get(best_metric, best_metric)
        pct = abs(metrics_delta[best_metric]) * 100

        if best_metric in LOWER_IS_BETTER:
            if metrics_delta[best_metric] < 0:
                direction = "decreased"
            else:
                direction = "increased"
        else:
            if metrics_delta[best_metric] > 0:
                direction = "improved"
            else:
                direction = "declined"

        action_display = action_type or "execution"

        if improvement_score > 0.05:
            return (
                f"After {action_display}: {display} {direction} by {pct:.0f}% "
                f"(overall improvement {improvement_score:+.1%})"
            )
        elif improvement_score < -0.05:
            return (
                f"After {action_display}: {display} {direction} by {pct:.0f}% "
                f"(overall degradation {improvement_score:+.1%})"
            )
        else:
            return (
                f"After {action_display}: {display} {direction} by {pct:.0f}% "
                f"(no significant change, {improvement_score:+.1%})"
            )

    # ═══════════════════════════════════════════════════════════
    # Internal: Experience Creation
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _create_experience(
        entry: BridgeEntry,
        result: BridgeResult,
        metrics_after: dict[str, float],
    ) -> Any:
        """创建 GrowthExperience.

        Args:
            entry:          桥接条目
            result:         桥接结果
            metrics_after:  执行后指标

        Returns:
            GrowthExperience
        """
        (
            ExperienceCategory,
            ExperienceContext,
            ExperienceOutcome,
            ExperienceOutcomeLevel,
            GrowthExperience,
        ) = _get_experience_models()

        # 映射 outcome_level
        level_map = {
            "strong_success": ExperienceOutcomeLevel.STRONG_SUCCESS,
            "success": ExperienceOutcomeLevel.SUCCESS,
            "neutral": ExperienceOutcomeLevel.NEUTRAL,
            "failure": ExperienceOutcomeLevel.FAILURE,
            "strong_failure": ExperienceOutcomeLevel.STRONG_FAILURE,
        }
        outcome_level = level_map.get(result.outcome_level, ExperienceOutcomeLevel.NEUTRAL)

        # 推断类别
        creative_actions = {
            "replace_creative", "mutate_creative", "creative_refresh",
            "generate_variants", "launch_ab_test",
        }
        ua_actions = {
            "scale", "pause_campaign", "increase_budget", "decrease_budget",
            "reallocate_budget", "adjust_bid",
        }
        action_type = entry.action_type.lower()
        if action_type in creative_actions:
            category = ExperienceCategory.CREATIVE
        elif action_type in ua_actions:
            category = ExperienceCategory.UA
        else:
            category = ExperienceCategory.UA

        context = ExperienceContext(
            product_id=entry.metadata.get("product_id", ""),
            date=entry.captured_at[:10],
            opportunity_type=entry.metadata.get("opportunity_type", ""),
            opportunity_id=entry.opportunity_id,
            action_type=entry.action_type,
            entity_id=entry.metadata.get("creative_id", entry.metadata.get("campaign_id", "")),
            entity_type=entry.metadata.get("entity_type", "creative"),
            market_conditions=entry.metrics_before,
            trigger_signals=entry.metadata.get("trigger_signals", []),
            audience_segment=entry.metadata.get("audience_segment", ""),
        )

        outcome = ExperienceOutcome(
            success=result.is_successful,
            outcome_level=outcome_level,
            metrics_before=entry.metrics_before,
            metrics_after=metrics_after,
            metrics_delta=result.metrics_delta,
            actual_impact=result.learning_summary,
            actual_reward=result.reward,
            error="",
            rolled_back=False,
            time_to_outcome_hours=0.0,
        )

        experience = GrowthExperience(
            context=context,
            action_type=entry.action_type,
            action_params=entry.metadata.get("action_params", {}),
            outcome=outcome,
            reward=result.reward,
            confidence=entry.metadata.get("confidence", 0.5),
            category=category,
            tags=entry.metadata.get("tags", []),
            metadata={
                "bridge_id": entry.bridge_id,
                "improvement_score": result.improvement_score,
                **(entry.metadata.get("extra_metadata", {})),
            },
        )

        return experience

    # ═══════════════════════════════════════════════════════════
    # Internal: DecisionMemory Sync (Day 6.5)
    # ═══════════════════════════════════════════════════════════

    def _sync_to_decision_memory(
        self,
        entry: BridgeEntry,
        result: BridgeResult,
    ) -> None:
        """同步评估结果到 DecisionMemorySync (Day 6.5 新增).

        将 ExecutionResultBridge 的评估结果自动同步到 DecisionMemorySync，
        使决策记忆系统感知到执行结果。

        Args:
            entry:  桥接条目
            result: 桥接结果
        """
        if self._decision_sync is None:
            return

        # 映射 outcome_level → result status
        status_map = {
            "strong_success": "success",
            "success": "success",
            "neutral": "partial",
            "failure": "failure",
            "strong_failure": "failure",
        }
        status = status_map.get(result.outcome_level, "partial")

        # 构建指标
        metrics = dict(result.metrics_delta)
        # 添加 reward
        metrics["reward"] = result.reward
        metrics["improvement_score"] = result.improvement_score

        # 同步到 DecisionMemorySync
        self._decision_sync.sync_execution_result(
            decision_id=entry.decision_id,
            status=status,
            metrics=metrics,
            reason=result.learning_summary,
            lessons=[],
        )

    # ═══════════════════════════════════════════════════════════
    # Internal: Pattern Update
    # ═══════════════════════════════════════════════════════════

    def _trigger_pattern_update(
        self,
        entry: BridgeEntry,
        result: BridgeResult,
    ) -> None:
        """触发 PatternMemory 更新.

        当 ExperienceStore 中有足够经验时，触发 PatternMemory 重新挖掘模式。

        Args:
            entry:  桥接条目
            result: 桥接结果
        """
        if self._pattern_store is None:
            return

        # 检查是否有足够经验触发模式更新
        if self._experience_store is not None:
            exp_count = self._experience_store.count
            if exp_count < 5:
                return  # 经验不足，不触发

        # 尝试触发 PatternMemory 更新
        try:
            if hasattr(self._pattern_store, "mine_from_experiences"):
                experiences = self._experience_store.get_all()
                self._pattern_store.mine_from_experiences(experiences)
            elif hasattr(self._pattern_store, "update"):
                self._pattern_store.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════

    def __repr__(self) -> str:
        return (
            f"ExecutionResultBridge(pending={self.pending_count}, "
            f"bridged={self._total_bridged}, "
            f"history={len(self._history)})"
        )


__all__ = [
    "ExecutionResultBridge",
    "BridgeEntry",
    "BridgeResult",
    "BUSINESS_METRIC_WEIGHTS",
    "HIGHER_IS_BETTER",
    "LOWER_IS_BETTER",
]