"""E13.6.5 DecisionPatternSync — 决策→模式提取与同步.

Day 6.5 核心模块:
  从 DecisionMemory 中提取已完成的决策，转换为经验并推送到 PatternMemory，
  形成"Decision → Result → Learning → Better Decision"的完整闭环。

之前:
  PatternMemory 仅来自 ExperienceStore 的原始经验挖掘

现在:
  DecisionMemory (已完成决策) → DecisionPatternExtractor → PatternMemory
  同时保留 ExperienceStore 路径，形成双通道学习

核心流程:
  DecisionMemorySync.get_completed_decisions()
      ↓
  DecisionPatternExtractor.extract_learning_cases()
      ↓
  DecisionPatternExtractor.convert_to_experience()
      ↓
  DecisionPatternExtractor.push_to_pattern_memory()
      ↓
  PatternMemory (更新)

与现有模块的关系:
  - DecisionMemorySync: 提供已完成的决策记录
  - DecisionOutcomeBridge (memory/decision_sync.py): 转换为统一事件
  - PatternMiner: 从经验中挖掘模式
  - PatternStore: 存储和检索模式

用法:
    sync = DecisionMemorySync(decision_memory)
    extractor = DecisionPatternExtractor(sync, pattern_store, experience_store)

    # 提取已完成决策 → 学习
    result = extractor.extract_learning_cases()
    # → 10 个已完成决策被转换为经验并推送到 PatternMemory

    # 按机会类型提取
    result = extractor.extract_by_opportunity_type("creative_fatigue")
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...intelligence.decision.decision_sync import DecisionMemorySync, DecisionMemoryRecord
    from .models import GrowthExperience, PatternMemory


# ═══════════════════════════════════════════════════════════════
# 提取结果
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExtractionResult:
    """决策→模式提取结果.

    Attributes:
        extraction_id: 提取批次ID
        decisions_extracted: 提取的决策数
        experiences_created: 创建的经验数
        patterns_updated: 更新的模式数
        learning_summary: 学习摘要
        extracted_at: 提取时间
        metadata: 扩展元数据
    """
    extraction_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    decisions_extracted: int = 0
    experiences_created: int = 0
    patterns_updated: int = 0
    learning_summary: str = ""
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# DecisionPatternExtractor
# ═══════════════════════════════════════════════════════════════


class DecisionPatternExtractor:
    """E13.6.5 DecisionPatternExtractor — 决策→模式提取器.

    从 DecisionMemorySync 中提取已完成的决策记录，
    转换为 GrowthExperience 并推送到 PatternMemory。

    双通道学习:
      通道 1 (原始): ExperienceStore → PatternMiner → PatternMemory
      通道 2 (新增): DecisionMemory → DecisionPatternExtractor → PatternMemory

    提取条件:
      1. 决策已终止 (COMPLETED/FAILED/EXPIRED)
      2. 有明确结果 (success/failure)
      3. 有足够的指标数据 (至少 roas_change 或 ctr_change)
    """

    # 最小样本数: 低于此值不提取
    MIN_SAMPLES_FOR_EXTRACTION = 5

    # 最小改善阈值: 低于此值视为中性
    MIN_IMPROVEMENT_THRESHOLD = 0.02

    def __init__(
        self,
        decision_sync: Any = None,  # DecisionMemorySync
        pattern_store: Any = None,  # PatternStore
        experience_store: Any = None,  # ExperienceStore
        min_samples: int = 5,
    ):
        """初始化提取器.

        Args:
            decision_sync: DecisionMemorySync 实例
            pattern_store: PatternStore 实例
            experience_store: ExperienceStore 实例 (可选)
            min_samples: 最小提取样本数
        """
        self._decision_sync = decision_sync
        self._pattern_store = pattern_store
        self._experience_store = experience_store
        self._min_samples = min_samples

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def extract_learning_cases(
        self,
        opportunity_type: str = "",
        action_type: str = "",
    ) -> ExtractionResult:
        """提取学习案例.

        找出已完成的决策:
          1. 成功案例 → 强化正向 Pattern
          2. 失败案例 → 生成负向 Pattern (避免)

        Args:
            opportunity_type: 机会类型过滤 (可选)
            action_type: 动作类型过滤 (可选)

        Returns:
            ExtractionResult: 提取结果
        """
        result = ExtractionResult()

        if self._decision_sync is None:
            result.learning_summary = "No DecisionMemorySync configured."
            return result

        # 1. 获取已完成的决策
        completed = self._decision_sync.get_completed_decisions(
            opportunity_type=opportunity_type,
            action_type=action_type,
            min_samples=self._min_samples,
        )

        if not completed:
            result.learning_summary = (
                f"No completed decisions found (min_samples={self._min_samples})"
                + (f" for opportunity_type='{opportunity_type}'" if opportunity_type else "")
            )

            return result

        result.decisions_extracted = len(completed)

        # 2. 转换为经验
        experiences = []
        for record in completed:
            exp = self.convert_to_experience(record)
            if exp is not None:
                experiences.append(exp)

        if not experiences:
            result.learning_summary = "No valid experiences could be created from completed decisions."
            return result

        result.experiences_created = len(experiences)

        # 3. 写入 ExperienceStore
        if self._experience_store is not None:
            for exp in experiences:
                try:
                    self._experience_store.store(exp)
                except Exception:
                    pass

        # 4. 推送到 PatternMemory
        patterns_updated = self.push_to_pattern_memory(experiences, opportunity_type)
        result.patterns_updated = patterns_updated

        # 5. 生成摘要
        success_count = sum(1 for r in completed if r.success)
        failure_count = len(completed) - success_count

        result.learning_summary = (
            f"Extracted {len(completed)} completed decisions "
            f"({success_count} success, {failure_count} failure) → "
            f"{result.experiences_created} experiences, "
            f"{result.patterns_updated} patterns updated"
        )

        return result

    def extract_by_opportunity_type(
        self,
        opportunity_type: str,
    ) -> ExtractionResult:
        """按机会类型提取学习案例."""
        return self.extract_learning_cases(opportunity_type=opportunity_type)

    def extract_by_action_type(
        self,
        action_type: str,
    ) -> ExtractionResult:
        """按动作类型提取学习案例."""
        return self.extract_learning_cases(action_type=action_type)

    # ═══════════════════════════════════════════════════════════
    # 转换
    # ═══════════════════════════════════════════════════════════

    def convert_to_experience(
        self,
        record: Any,  # DecisionMemoryRecord
    ) -> Any | None:  # GrowthExperience | None
        """将 DecisionMemoryRecord 转换为 GrowthExperience.

        Args:
            record: DecisionMemoryRecord 实例

        Returns:
            GrowthExperience | None: 转换失败时返回 None
        """
        try:
            from .models import (
                ExperienceCategory,
                ExperienceContext,
                ExperienceOutcome,
                ExperienceOutcomeLevel,
                GrowthExperience,
            )

            # 确定结果等级
            outcome_level = self._determine_outcome_level(record)

            # 构建上下文
            context = ExperienceContext(
                product_id=record.decision_context.get("product_id", ""),
                date=record.created_at[:10] if record.created_at else "",
                opportunity_type=record.opportunity_type,
                opportunity_id=record.decision_context.get("opportunity_id", ""),
                action_type=record.action_type,
                entity_id=record.decision_id,
                entity_type="decision",
                market_conditions=record.outcome_detail,
                trigger_signals=record.decision_context.get("trigger_signals", []),
                audience_segment=record.decision_context.get("audience_segment", ""),
            )

            # 构建结果
            outcome = ExperienceOutcome(
                success=record.success if record.success is not None else False,
                outcome_level=outcome_level,
                metrics_before={},
                metrics_after=record.outcome_detail,
                metrics_delta={},
                actual_impact=self._generate_impact_summary(record),
                actual_reward=self._normalize_reward(record.reward),
                error="" if record.success else record.decision_context.get("error", ""),
                rolled_back=False,
                time_to_outcome_hours=0.0,
            )

            # 推断类别
            category = self._infer_category(record.action_type)

            # 生成标签
            tags = self._generate_tags(record)

            # 计算综合奖励
            reward = self._normalize_reward(record.reward)

            experience = GrowthExperience(
                context=context,
                action_type=record.action_type,
                action_params=record.decision_detail,
                outcome=outcome,
                reward=reward,
                confidence=record.confidence,
                category=category,
                tags=tags,
                metadata={
                    "source": "decision_memory",
                    "decision_id": record.decision_id,
                    "execution_id": record.execution_id,
                    "strategy_id": record.strategy_id,
                    "strategy_name": record.strategy_name,
                    "decision_status": record.status.value if hasattr(record.status, 'value') else str(record.status),
                    "lessons": record.lessons,
                },
            )

            return experience

        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════
    # 推送到 PatternMemory
    # ═══════════════════════════════════════════════════════════

    def push_to_pattern_memory(
        self,
        experiences: list[Any],  # GrowthExperience
        opportunity_type: str = "",
    ) -> int:
        """推送经验到 PatternMemory.

        触发 PatternMiner 或 PatternStore 从经验中挖掘/更新模式。

        Args:
            experiences: GrowthExperience 列表
            opportunity_type: 机会类型过滤

        Returns:
            int: 更新的模式数
        """
        if self._pattern_store is None:
            return 0

        patterns_updated = 0

        try:
            # 方式 1: 通过 PatternMiner 从经验挖掘
            if hasattr(self._pattern_store, "mine_from_experiences"):
                self._pattern_store.mine_from_experiences(experiences)
                patterns_updated = len(self._pattern_store.get_all()) if hasattr(self._pattern_store, "get_all") else len(experiences)

            # 方式 2: 通过 PatternStore 直接更新
            elif hasattr(self._pattern_store, "update"):
                self._pattern_store.update()
                patterns_updated = 1

            # 方式 3: 逐个添加经验到 PatternStore
            elif hasattr(self._pattern_store, "add_experience"):
                for exp in experiences:
                    try:
                        self._pattern_store.add_experience(exp)
                        patterns_updated += 1
                    except Exception:
                        pass

        except Exception:
            pass

        return patterns_updated

    def push_single_decision(
        self,
        record: Any,  # DecisionMemoryRecord
    ) -> ExtractionResult:
        """推送单个决策到 PatternMemory.

        Args:
            record: DecisionMemoryRecord 实例

        Returns:
            ExtractionResult: 提取结果
        """
        result = ExtractionResult()
        result.decisions_extracted = 1

        exp = self.convert_to_experience(record)
        if exp is None:
            result.learning_summary = "Failed to convert decision to experience."
            return result

        result.experiences_created = 1

        # 写入 ExperienceStore
        if self._experience_store is not None:
            try:
                self._experience_store.store(exp)
            except Exception:
                pass

        # 推送到 PatternMemory
        result.patterns_updated = self.push_to_pattern_memory([exp])

        result.learning_summary = (
            f"Decision {record.decision_id} → "
            f"{'positive' if record.success else 'negative'} pattern"
        )

        return result

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _determine_outcome_level(record: Any) -> Any:
        """确定结果等级."""
        try:
            from .models import ExperienceOutcomeLevel

            if record.reward is not None and record.reward > 0.5:
                return ExperienceOutcomeLevel.STRONG_SUCCESS
            elif record.success:
                return ExperienceOutcomeLevel.SUCCESS
            elif record.reward is not None and record.reward < -0.5:
                return ExperienceOutcomeLevel.STRONG_FAILURE
            elif record.success is False:
                return ExperienceOutcomeLevel.FAILURE
            else:
                return ExperienceOutcomeLevel.NEUTRAL
        except ImportError:
            return "neutral"

    @staticmethod
    def _infer_category(action_type: str) -> Any:
        """推断经验类别."""
        try:
            from .models import ExperienceCategory

            creative_actions = {
                "replace_creative", "mutate_creative", "creative_refresh",
                "generate_variants", "launch_ab_test",
            }
            ua_actions = {
                "scale", "pause_campaign", "increase_budget", "decrease_budget",
                "reallocate_budget", "adjust_bid", "scale_budget",
            }

            action_lower = action_type.lower()
            if action_lower in creative_actions:
                return ExperienceCategory.CREATIVE
            elif action_lower in ua_actions:
                return ExperienceCategory.UA
            else:
                return ExperienceCategory.UA
        except ImportError:
            return None

    @staticmethod
    def _generate_tags(record: Any) -> list[str]:
        """生成经验标签."""
        tags = []

        if record.opportunity_type:
            tags.append(f"opportunity:{record.opportunity_type}")
        if record.action_type:
            tags.append(f"action:{record.action_type}")
        if record.success:
            tags.append("success")
        else:
            tags.append("failure")
        if record.reward is not None and record.reward > 0.3:
            tags.append("high_reward")
        elif record.reward is not None and record.reward < -0.3:
            tags.append("low_reward")
        if record.strategy_id:
            tags.append(f"strategy:{record.strategy_id}")

        tags.append("source:decision_memory")

        return tags

    @staticmethod
    def _normalize_reward(reward: float | None) -> float:
        """将 reward 归一化到 [0, 1].

        DecisionMemoryRecord.reward 范围是 [-1, 1]，
        GrowthExperience.reward 范围是 [0, 1]。
        """
        if reward is None:
            return 0.5
        return round(max(0.0, min(1.0, (reward + 1.0) / 2.0)), 4)

    @staticmethod
    def _generate_impact_summary(record: Any) -> str:
        """生成影响摘要."""
        parts = []

        if record.action_type:
            parts.append(f"Action: {record.action_type}")

        if record.success:
            parts.append("Result: SUCCESS")
        elif record.success is False:
            parts.append("Result: FAILURE")
        else:
            parts.append("Result: UNKNOWN")

        if record.reward is not None:
            parts.append(f"Reward: {record.reward:+.2f}")

        # 指标变化
        metrics = record.outcome_detail
        if metrics:
            roas = metrics.get("roas_change", 0)
            if roas:
                parts.append(f"ROAS: {roas:+.1%}")

        return " | ".join(parts) if parts else "No impact summary available"

    # ═══════════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════════

    def get_extractable_count(
        self,
        opportunity_type: str = "",
        action_type: str = "",
    ) -> int:
        """获取可提取的决策数."""
        if self._decision_sync is None:
            return 0

        completed = self._decision_sync.get_completed_decisions(
            opportunity_type=opportunity_type,
            action_type=action_type,
        )
        return len(completed)

    def __repr__(self) -> str:
        count = self.get_extractable_count()
        return (
            f"DecisionPatternExtractor(extractable={count}, "
            f"min_samples={self._min_samples})"
        )


# ═══════════════════════════════════════════════════════════════
# DecisionPatternSync (编排层)
# ═══════════════════════════════════════════════════════════════


class DecisionPatternSync:
    """E13.6.5 DecisionPatternSync — 决策→模式同步编排器.

    编排 DecisionPatternExtractor 的完整同步流程:
      1. 从 DecisionMemorySync 获取已完成的决策
      2. 提取学习案例 (成功/失败)
      3. 转换为经验
      4. 推送到 PatternMemory
      5. 触发 PatternMiner 重新挖掘

    与 DecisionPatternSynchronizer 的区别:
      - DecisionPatternSynchronizer: 单一决策→Pattern 实时同步
      - DecisionPatternSync: 批量决策→Pattern 批量提取

    用法:
        sync = DecisionMemorySync(decision_memory)
        pattern_sync = DecisionPatternSync(sync, pattern_store, experience_store)

        # 批量提取
        result = pattern_sync.sync_all()
        # → 提取了 15 个已完成决策，更新了 3 个模式

        # 定时提取 (每天)
        result = pattern_sync.sync_recent(days=7)
    """

    def __init__(
        self,
        decision_sync: Any = None,  # DecisionMemorySync
        pattern_store: Any = None,  # PatternStore
        experience_store: Any = None,  # ExperienceStore
        min_samples: int = 5,
    ):
        self._extractor = DecisionPatternExtractor(
            decision_sync=decision_sync,
            pattern_store=pattern_store,
            experience_store=experience_store,
            min_samples=min_samples,
        )
        self._decision_sync = decision_sync

    def sync_all(
        self,
        opportunity_type: str = "",
        action_type: str = "",
    ) -> ExtractionResult:
        """同步所有已完成的决策.

        Args:
            opportunity_type: 机会类型过滤
            action_type: 动作类型过滤

        Returns:
            ExtractionResult: 提取结果
        """
        return self._extractor.extract_learning_cases(
            opportunity_type=opportunity_type,
            action_type=action_type,
        )

    def sync_by_opportunity_type(
        self,
        opportunity_type: str,
    ) -> ExtractionResult:
        """按机会类型同步."""
        return self._extractor.extract_by_opportunity_type(opportunity_type)

    def sync_by_action_type(
        self,
        action_type: str,
    ) -> ExtractionResult:
        """按动作类型同步."""
        return self._extractor.extract_by_action_type(action_type)

    def sync_single_decision(
        self,
        record: Any,  # DecisionMemoryRecord
    ) -> ExtractionResult:
        """同步单个决策."""
        return self._extractor.push_single_decision(record)

    def get_extractable_count(self) -> int:
        """获取可提取的决策数."""
        return self._extractor.get_extractable_count()

    def __repr__(self) -> str:
        return f"DecisionPatternSync(extractable={self.get_extractable_count()})"


__all__ = [
    "DecisionPatternExtractor",
    "DecisionPatternSync",
    "ExtractionResult",
]