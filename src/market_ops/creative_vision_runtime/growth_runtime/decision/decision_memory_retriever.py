"""E13.6.5 DecisionMemoryRetriever — 决策历史检索器.

Day 6.5 核心模块:
  从 DecisionMemory 中检索与当前场景匹配的历史决策，
  让 DecisionEngine 不只是参考 PatternMemory 的经验，
  还能读取自己过去做过什么决策、结果如何。

与 PatternRetriever 的区别:
  - PatternRetriever: 查询"历史上类似情况最佳动作是什么" (经验模式)
  - DecisionMemoryRetriever: 查询"我之前实际做过什么决定" (行为轨迹)

两者合并后形成完整的决策上下文:
  Pattern Memory (What should I do) + Decision Memory (What did I do) → Better Decision

核心流程:
  DecisionContext → DecisionMemoryRetriever → DecisionHistoryResult
       ↓
  PatternRetrieval + DecisionHistory → DecisionEnhancer → DecisionEngine

模块:
  - DecisionContext: 检索输入 (当前场景描述)
  - DecisionRecord: 扩展的决策记录 (含 context + decision + outcome)
  - DecisionHistoryResult: 检索输出 (历史决策 + 统计 + 推荐)
  - DecisionMemoryRetriever: 检索器本体
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionContext:
    """决策检索上下文 — 描述当前需要匹配的场景.

    这是 DecisionMemoryRetriever 的输入，描述当前发生了什么，
    需要从历史决策中查找类似场景的决策记录。

    Attributes:
        opportunity_type: 机会类型 (e.g., "creative_fatigue", "roas_drop")
        action_type: 当前候选动作类型 (e.g., "replace_creative")
        product_id: 产品 ID (e.g., "P04")
        audience_segment: 受众分群 (e.g., "iOS_FB", "Android_GG")
        platform: 投放平台 (e.g., "Facebook", "Google")
        signal_types: 当前触发的信号 (e.g., ["roas_decay", "frequency_high"])
        metrics: 当前指标快照 (e.g., {"roas": 0.32, "ctr": 0.021})
    """
    opportunity_type: str = ""
    action_type: str = ""
    product_id: str = ""
    audience_segment: str = ""
    platform: str = ""
    signal_types: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "product_id": self.product_id,
            "audience_segment": self.audience_segment,
            "platform": self.platform,
            "signal_types": self.signal_types,
            "metrics": self.metrics,
        }


@dataclass
class DecisionRecord:
    """扩展的决策记录 — 从 DecisionExperience 展开为结构化记录.

    比 DecisionExperience 更丰富的上下文:
      - context: 决策时的场景信息
      - decision: 决策内容 (动作、预算、目标)
      - outcome: 执行结果 (奖励、指标变化)

    Attributes:
        decision_id: 决策 ID
        opportunity_type: 机会类型
        action_type: 动作类型
        context: 决策场景 (product, platform, country, metrics)
        decision: 决策内容 (action, budget_change, target)
        outcome: 执行结果 (reward, roas_change, revenue_change)
        success: 是否成功
        timestamp: 决策时间
        confidence: 决策时置信度
        lessons: 经验教训
    """
    decision_id: str = ""
    opportunity_type: str = ""
    action_type: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    timestamp: str = ""
    confidence: float = 0.0
    lessons: list[str] = field(default_factory=list)

    @classmethod
    def from_decision_experience(cls, exp: Any) -> DecisionRecord:
        """从 DecisionExperience 构建 DecisionRecord."""
        action_type = ""
        if hasattr(exp, "action_plan") and isinstance(exp.action_plan, dict):
            action_type = exp.action_plan.get("action_type", "")
        if not action_type and hasattr(exp, "strategy_name"):
            action_type = exp.strategy_name

        metrics = {}
        if hasattr(exp, "result_metrics") and isinstance(exp.result_metrics, dict):
            metrics = exp.result_metrics

        return cls(
            decision_id=exp.decision_id if hasattr(exp, "decision_id") else "",
            opportunity_type=exp.opportunity_type if hasattr(exp, "opportunity_type") else "",
            action_type=action_type,
            context={
                "product_id": "",
                "platform": "",
                "country": "",
                "metrics": {},
            },
            decision={
                "action": action_type,
                "budget_change": 0.0,
                "target": "",
            },
            outcome={
                "reward": cls._compute_reward(exp),
                "roas_change": metrics.get("roas_change", 0.0),
                "revenue_change": metrics.get("revenue_change", 0.0),
            },
            success=exp.is_success if hasattr(exp, "is_success") else False,
            timestamp=exp.resolved_at if hasattr(exp, "resolved_at") and exp.resolved_at
                else exp.created_at if hasattr(exp, "created_at")
                else datetime.now(timezone.utc).isoformat(),
            confidence=exp.confidence if hasattr(exp, "confidence") else 0.0,
            lessons=exp.lessons_learned if hasattr(exp, "lessons_learned") else [],
        )

    @staticmethod
    def _compute_reward(exp: Any) -> float:
        """从决策经验计算奖励."""
        metrics = {}
        if hasattr(exp, "result_metrics") and isinstance(exp.result_metrics, dict):
            metrics = exp.result_metrics

        if hasattr(exp, "result") and exp.result == "failure":
            return -1.0

        reward = 0.0
        count = 0
        roas = metrics.get("roas_change", 0.0)
        if isinstance(roas, (int, float)) and roas != 0:
            reward += 1.0 if roas > 0 else -0.5
            count += 1
        ctr = metrics.get("ctr_change", 0.0)
        if isinstance(ctr, (int, float)) and ctr != 0:
            reward += 0.5 if ctr > 0 else -0.3
            count += 1
        return round(reward / max(count, 1), 4) if count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "context": self.context,
            "decision": self.decision,
            "outcome": self.outcome,
            "success": self.success,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "lessons": self.lessons,
        }


@dataclass
class DecisionHistoryResult:
    """决策历史检索结果 — DecisionMemoryRetriever 的完整输出.

    Attributes:
        similar_decisions: 排序后的历史决策记录
        success_rate: 历史成功率
        confidence: 基于历史的置信度
        recommended_action: 推荐动作
        warnings: 基于历史失败的警告
        total_matched: 匹配总数
        match_dimensions: 匹配维度详情
        summary: 检索摘要
    """
    similar_decisions: list[DecisionRecord] = field(default_factory=list)
    success_rate: float = 0.0
    confidence: float = 0.0
    recommended_action: str = ""
    warnings: list[str] = field(default_factory=list)
    total_matched: int = 0
    match_dimensions: dict[str, int] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_matched": self.total_matched,
            "success_rate": round(self.success_rate, 4),
            "confidence": round(self.confidence, 4),
            "recommended_action": self.recommended_action,
            "warnings": self.warnings,
            "similar_decisions": [d.to_dict() for d in self.similar_decisions[:10]],
            "match_dimensions": self.match_dimensions,
            "summary": self.summary,
        }

    @property
    def has_recommendations(self) -> bool:
        return len(self.similar_decisions) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


# ═══════════════════════════════════════════════════════════════
# DecisionMemoryRetriever
# ═══════════════════════════════════════════════════════════════


class DecisionMemoryRetriever:
    """决策记忆检索器 — 从 DecisionMemory 中查找历史决策.

    核心流程:
      1. 根据 DecisionContext 从 DecisionMemory 中检索类似决策
      2. 将 DecisionExperience 展开为 DecisionRecord
      3. 按相似度排序
      4. 计算成功率、置信度、推荐动作
      5. 生成警告 (基于历史失败)

    用法:
        memory = DecisionMemory()
        retriever = DecisionMemoryRetriever(memory)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            product_id="P04",
            platform="Facebook",
        ))

        print(f"Success rate: {result.success_rate}")
        print(f"Recommendation: {result.recommended_action}")
    """

    # ── 检索参数 ──────────────────────────────────────────────

    DEFAULT_MAX_RESULTS = 50
    DEFAULT_MIN_RESOLVED = 5  # 最少已决样本才给出推荐

    # ── 推荐阈值 ──────────────────────────────────────────────

    STRONG_RECOMMEND_THRESHOLD = 0.70
    RECOMMEND_THRESHOLD = 0.50
    CAUTION_THRESHOLD = 0.30

    # ── 样本可信度 ────────────────────────────────────────────

    MIN_SAMPLES_FOR_CONFIDENCE = 10

    def __init__(
        self,
        decision_memory: Any,  # DecisionMemory
        max_results: int = 50,
        min_resolved: int = 5,
    ):
        self._memory = decision_memory
        self._max_results = max_results
        self._min_resolved = min_resolved

    # ═══════════════════════════════════════════════════════════
    # Main API
    # ═══════════════════════════════════════════════════════════

    def retrieve(self, context: DecisionContext) -> DecisionHistoryResult:
        """检索与当前场景匹配的历史决策.

        Args:
            context: 检索上下文

        Returns:
            DecisionHistoryResult: 历史决策结果
        """
        # Step 1: 从 DecisionMemory 查找类似决策
        similar = self._find_similar_decisions(context)

        if not similar:
            return DecisionHistoryResult(
                summary=f"No historical decisions found for "
                        f"opportunity_type='{context.opportunity_type}'.",
            )

        # Step 2: 展开为 DecisionRecord
        records = [DecisionRecord.from_decision_experience(e) for e in similar]

        # Step 3: 计算统计
        resolved = [r for r in records if r.success or not r.success]
        if not resolved:
            resolved = records

        total = len(resolved)
        success_count = sum(1 for r in resolved if r.success)
        success_rate = success_count / total if total > 0 else 0.0

        # Step 4: 计算置信度
        confidence = self._compute_confidence(success_rate, total)

        # Step 5: 按动作类型分组统计
        action_stats = self._group_by_action(resolved)

        # Step 6: 生成推荐
        recommended_action = self._determine_recommendation(
            action_stats, success_rate, total,
        )

        # Step 7: 生成警告
        warnings = self._generate_warnings(action_stats, total)

        # Step 8: 计算匹配维度
        match_dimensions = self._compute_match_dimensions(records, context)

        summary = self._generate_summary(
            total, success_rate, recommended_action, warnings,
        )

        return DecisionHistoryResult(
            similar_decisions=records[:self._max_results],
            success_rate=round(success_rate, 4),
            confidence=round(confidence, 4),
            recommended_action=recommended_action,
            warnings=warnings,
            total_matched=total,
            match_dimensions=match_dimensions,
            summary=summary,
        )

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def _find_similar_decisions(self, context: DecisionContext) -> list[Any]:
        """从 DecisionMemory 查找类似决策.

        多维度匹配:
          1. 精确匹配: opportunity_type
          2. 动作匹配: action_type
          3. 放宽匹配: 仅 opportunity_type (如果精确匹配太少)
        """
        # 精确匹配: opportunity_type + action_type
        if context.action_type and context.opportunity_type:
            results = self._memory.find_similar(
                opportunity_type=context.opportunity_type,
                limit=self._max_results,
            )
            # 按 action_type 过滤
            action_filtered = self._filter_by_action(results, context.action_type)
            if len(action_filtered) >= self._min_resolved:
                return action_filtered[:self._max_results]

        # 放宽匹配: 仅 opportunity_type
        if context.opportunity_type:
            results = self._memory.find_similar(
                opportunity_type=context.opportunity_type,
                limit=self._max_results,
            )
            if results:
                return results

        # 最宽匹配: 仅 action_type
        if context.action_type:
            results = self._memory.find_similar(
                limit=self._max_results,
            )
            return self._filter_by_action(results, context.action_type)

        # 无匹配: 返回空列表 (不返回最近记录，避免不相关结果)
        return []

    def _filter_by_action(
        self,
        experiences: list[Any],
        action_type: str,
    ) -> list[Any]:
        """按 action_type 过滤."""
        filtered = []
        for exp in experiences:
            exp_action = ""
            if hasattr(exp, "action_plan") and isinstance(exp.action_plan, dict):
                exp_action = exp.action_plan.get("action_type", "")
            if not exp_action and hasattr(exp, "strategy_name"):
                exp_action = exp.strategy_name
            if exp_action == action_type:
                filtered.append(exp)
        return filtered

    # ═══════════════════════════════════════════════════════════
    # Confidence
    # ═══════════════════════════════════════════════════════════

    def _compute_confidence(self, success_rate: float, total: int) -> float:
        """计算基于历史的置信度.

        公式:
          sample_factor × success_rate

        样本因子: 对数平滑，避免小样本过度主导
        """
        if total == 0:
            return 0.0
        sample_factor = min(1.0, math.log(total + 1) / math.log(100))
        return round(sample_factor * success_rate, 4)

    # ═══════════════════════════════════════════════════════════
    # Recommendation
    # ═══════════════════════════════════════════════════════════

    def _group_by_action(
        self,
        records: list[DecisionRecord],
    ) -> dict[str, dict[str, Any]]:
        """按动作类型分组统计."""
        groups: dict[str, dict[str, Any]] = {}
        for r in records:
            action = r.action_type or "unknown"
            if action not in groups:
                groups[action] = {"total": 0, "success": 0, "records": []}
            groups[action]["total"] += 1
            if r.success:
                groups[action]["success"] += 1
            groups[action]["records"].append(r)

        # 计算每个动作的成功率
        for action, stats in groups.items():
            stats["success_rate"] = (
                stats["success"] / stats["total"]
                if stats["total"] > 0
                else 0.0
            )
        return groups

    def _determine_recommendation(
        self,
        action_stats: dict[str, dict[str, Any]],
        overall_success_rate: float,
        total: int,
    ) -> str:
        """确定推荐动作.

        规则:
          - 样本不足 → 不推荐
          - 高成功率动作 → 推荐
          - 整体成功率低 → 不推荐
        """
        if total < self._min_resolved:
            return ""

        # 找成功率最高的动作
        best_action = ""
        best_rate = 0.0
        best_total = 0

        for action, stats in action_stats.items():
            if stats["total"] >= 3 and stats["success_rate"] > best_rate:
                best_rate = stats["success_rate"]
                best_action = action
                best_total = stats["total"]

        if best_rate >= self.STRONG_RECOMMEND_THRESHOLD and best_total >= 5:
            return best_action
        if best_rate >= self.RECOMMEND_THRESHOLD and best_total >= 3:
            return best_action

        return ""

    # ═══════════════════════════════════════════════════════════
    # Warnings
    # ═══════════════════════════════════════════════════════════

    def _generate_warnings(
        self,
        action_stats: dict[str, dict[str, Any]],
        total: int,
    ) -> list[str]:
        """生成基于历史失败的警告."""
        warnings: list[str] = []

        for action, stats in action_stats.items():
            if stats["total"] < 3:
                continue

            failure_rate = 1.0 - stats["success_rate"]

            # 高失败率动作
            if failure_rate >= 0.70 and stats["total"] >= 5:
                warnings.append(
                    f"AVOID '{action}': {failure_rate:.0%} failure rate "
                    f"({stats['success']}/{stats['total']} successes)"
                )

            # 样本不足的动作
            elif stats["total"] < 5:
                warnings.append(
                    f"LOW CONFIDENCE: '{action}' has only {stats['total']} samples, "
                    f"insufficient data for reliable recommendation"
                )

        return warnings

    # ═══════════════════════════════════════════════════════════
    # Match Dimensions
    # ═══════════════════════════════════════════════════════════

    def _compute_match_dimensions(
        self,
        records: list[DecisionRecord],
        context: DecisionContext,
    ) -> dict[str, int]:
        """计算匹配维度统计."""
        dims: dict[str, int] = {
            "total": len(records),
            "exact_opportunity_match": 0,
            "exact_action_match": 0,
            "success": 0,
            "failure": 0,
        }
        for r in records:
            if r.opportunity_type == context.opportunity_type:
                dims["exact_opportunity_match"] += 1
            if r.action_type == context.action_type:
                dims["exact_action_match"] += 1
            if r.success:
                dims["success"] += 1
            else:
                dims["failure"] += 1
        return dims

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════

    def _generate_summary(
        self,
        total: int,
        success_rate: float,
        recommended_action: str,
        warnings: list[str],
    ) -> str:
        """生成检索摘要."""
        parts = [
            f"Found {total} historical decisions",
            f"with {success_rate:.0%} success rate",
        ]
        if recommended_action:
            parts.append(f"→ recommend '{recommended_action}'")
        if warnings:
            parts.append(f"({len(warnings)} warnings)")
        return " | ".join(parts)