"""E14.4.4.3 Strategy Memory — 长期策略记忆.

Strategy Memory 是 Learning Loop 的长期记忆层，记住「什么策略在什么场景下有效」:

  输入: 策略执行历史 (strategy + context + outcome)
  输出: ContextProfile → StrategyEffectiveness (场景 → 策略有效性)

核心能力:
  - 场景记忆: 记录游戏/平台/市场/阶段等上下文
  - 策略有效性: 每个策略在特定场景下的成功率
  - 最优策略推荐: 根据当前场景推荐最有效的策略

设计原则:
  - 确定性、可解释 — 基于历史频次统计
  - 场景感知 — 不同游戏/平台/市场分别记忆
  - 时间衰减 — 最近的经验权重更高
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..memory import CreativeMemory, CreativeDecisionRecord, CreativeDecisionOutcome
from ..strategy import CreativeStrategyType


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ContextProfile:
    """场景画像 — 描述当前游戏/投放环境.

    Attributes:
        context_id: 场景 ID
        game: 游戏名称
        platform: 平台 (android/ios)
        market: 市场 (US/JP/KR/...)
        genre: 游戏类型 (merge/puzzle/rpg/...)
        stage: 投放阶段 (launch/growth/mature/decline)
        metrics: 当前指标快照
    """
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    game: str = ""
    platform: str = ""
    market: str = ""
    genre: str = ""
    stage: str = ""
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "game": self.game,
            "platform": self.platform,
            "market": self.market,
            "genre": self.genre,
            "stage": self.stage,
            "metrics": self.metrics,
        }

    @property
    def context_key(self) -> str:
        """生成场景键 (用于聚合)."""
        return f"{self.game}:{self.platform}:{self.market}:{self.genre}:{self.stage}"

    @property
    def broad_context_key(self) -> str:
        """生成宽泛场景键 (忽略 stage)."""
        return f"{self.game}:{self.platform}:{self.market}:{self.genre}"


@dataclass
class StrategyRecord:
    """策略记录 — 单次策略执行记录.

    Attributes:
        record_id: 记录 ID
        strategy_type: 策略类型
        context_key: 场景键
        context: 场景画像
        outcome: 结果 (SUCCESS/FAILURE/PARTIAL)
        reward: 奖励值
        metrics_before: 执行前指标
        metrics_after: 执行后指标
        created_at: 创建时间
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_type: CreativeStrategyType = CreativeStrategyType.REFRESH_HOOK
    context_key: str = ""
    context: ContextProfile = field(default_factory=ContextProfile)
    outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.PENDING
    reward: float = 0.0
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "strategy_type": self.strategy_type.value,
            "context_key": self.context_key,
            "context": self.context.to_dict(),
            "outcome": self.outcome.value,
            "reward": self.reward,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "created_at": self.created_at,
        }


@dataclass
class StrategyEffectiveness:
    """策略有效性 — 某个策略在某个场景下的表现.

    Attributes:
        strategy_type: 策略类型
        context_key: 场景键
        attempt_count: 尝试次数
        success_count: 成功次数
        success_rate: 成功率
        avg_reward: 平均奖励
        avg_roas_improvement: 平均 ROAS 提升
        confidence: 置信度
        last_updated: 最后更新时间
    """
    strategy_type: CreativeStrategyType = CreativeStrategyType.REFRESH_HOOK
    context_key: str = ""
    attempt_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_roas_improvement: float = 0.0
    confidence: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type.value,
            "context_key": self.context_key,
            "attempt_count": self.attempt_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_reward": round(self.avg_reward, 4),
            "avg_roas_improvement": round(self.avg_roas_improvement, 4),
            "confidence": round(self.confidence, 4),
            "last_updated": self.last_updated,
        }

    @property
    def is_reliable(self) -> bool:
        return self.attempt_count >= 5 and self.confidence >= 0.5


@dataclass
class StrategyMemoryReport:
    """策略记忆报告.

    Attributes:
        report_id: 报告 ID
        total_records: 总记录数
        total_contexts: 场景数
        effectiveness: 有效性列表
        top_strategies: 最佳策略
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_contexts: int = 0
    effectiveness: list[StrategyEffectiveness] = field(default_factory=list)
    top_strategies: list[StrategyEffectiveness] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_records": self.total_records,
            "total_contexts": self.total_contexts,
            "effectiveness": [e.to_dict() for e in self.effectiveness],
            "top_strategies": [e.to_dict() for e in self.top_strategies],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Strategy Memory
# ═══════════════════════════════════════════════════════════════


class StrategyMemory:
    """长期策略记忆 — 记住「什么策略在什么场景下有效」.

    职责:
      1. 记录策略执行历史 (场景 + 策略 + 结果)
      2. 计算每个策略在特定场景下的有效性
      3. 根据当前场景推荐最优策略

    用法:
        memory = StrategyMemory()
        memory.record(strategy, context, outcome, reward)
        best = memory.recommend(current_context)  # 获取最佳策略
    """

    def __init__(self, memory: CreativeMemory | None = None):
        self._memory = memory or CreativeMemory()
        self._records: list[StrategyRecord] = []
        self._effectiveness: dict[str, StrategyEffectiveness] = {}  # key = "context_key:strategy_type"

    # ── 记录 ──────────────────────────────────────────────────

    def record(
        self,
        strategy_type: CreativeStrategyType,
        context: ContextProfile,
        outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.PENDING,
        reward: float = 0.0,
        metrics_before: dict[str, float] | None = None,
        metrics_after: dict[str, float] | None = None,
    ) -> StrategyRecord:
        """记录一次策略执行.

        Args:
            strategy_type: 策略类型
            context: 场景画像
            outcome: 结果
            reward: 奖励值
            metrics_before: 执行前指标
            metrics_after: 执行后指标

        Returns:
            StrategyRecord: 策略记录
        """
        record = StrategyRecord(
            strategy_type=strategy_type,
            context_key=context.broad_context_key,
            context=context,
            outcome=outcome,
            reward=reward,
            metrics_before=metrics_before or {},
            metrics_after=metrics_after or {},
        )
        self._records.append(record)

        # 更新有效性
        self._update_effectiveness(record)

        return record

    def record_batch(
        self,
        entries: list[dict[str, Any]],
    ) -> list[StrategyRecord]:
        """批量记录策略执行."""
        records = []
        for entry in entries:
            record = self.record(
                strategy_type=CreativeStrategyType(entry["strategy_type"]),
                context=entry["context"],
                outcome=CreativeDecisionOutcome(entry.get("outcome", "pending")),
                reward=entry.get("reward", 0.0),
                metrics_before=entry.get("metrics_before"),
                metrics_after=entry.get("metrics_after"),
            )
            records.append(record)
        return records

    def _update_effectiveness(self, record: StrategyRecord) -> None:
        """更新策略有效性."""
        key = f"{record.context_key}:{record.strategy_type.value}"
        eff = self._effectiveness.get(key)

        if not eff:
            eff = StrategyEffectiveness(
                strategy_type=record.strategy_type,
                context_key=record.context_key,
            )
            self._effectiveness[key] = eff

        eff.attempt_count += 1
        if record.outcome == CreativeDecisionOutcome.SUCCESS:
            eff.success_count += 1

        eff.success_rate = eff.success_count / max(eff.attempt_count, 1)

        # 更新平均奖励
        old_total = eff.attempt_count - 1
        eff.avg_reward = (eff.avg_reward * old_total + record.reward) / max(eff.attempt_count, 1)

        # ROAS 提升
        roas_before = record.metrics_before.get("roas", 0)
        roas_after = record.metrics_after.get("roas", 0)
        if roas_before > 0:
            improvement = (roas_after - roas_before) / roas_before
            eff.avg_roas_improvement = (eff.avg_roas_improvement * old_total + improvement) / max(eff.attempt_count, 1)

        # 置信度: 基于尝试次数和成功率
        eff.confidence = min(eff.attempt_count / 10.0, 1.0) * 0.6 + eff.success_rate * 0.4
        eff.last_updated = datetime.now(timezone.utc).isoformat()

    # ── 推荐 ──────────────────────────────────────────────────

    def recommend(
        self,
        context: ContextProfile,
        min_confidence: float = 0.3,
        top_n: int = 5,
    ) -> list[StrategyEffectiveness]:
        """根据当前场景推荐最优策略.

        匹配策略:
          1. 精确匹配 (game + platform + market + genre + stage)
          2. 宽泛匹配 (game + platform + market + genre)
          3. 全局最佳 (所有场景)

        Args:
            context: 当前场景画像
            min_confidence: 最小置信度
            top_n: 返回 Top N

        Returns:
            list[StrategyEffectiveness]: 策略有效性列表
        """
        # 精确匹配
        exact_key = context.context_key
        exact = [
            e for e in self._effectiveness.values()
            if e.context_key == exact_key and e.confidence >= min_confidence
        ]

        # 宽泛匹配
        broad_key = context.broad_context_key
        broad = [
            e for e in self._effectiveness.values()
            if e.context_key == broad_key and e.confidence >= min_confidence
        ]

        # 全局最佳
        global_best = [
            e for e in self._effectiveness.values()
            if e.confidence >= min_confidence
        ]

        # 合并去重 (精确 > 宽泛 > 全局)
        seen = set()
        results = []
        for e in exact + broad + global_best:
            if e.strategy_type.value not in seen:
                seen.add(e.strategy_type.value)
                results.append(e)

        # 按 success_rate × confidence 排序
        results.sort(key=lambda e: e.success_rate * e.confidence, reverse=True)
        return results[:top_n]

    def recommend_for_context(
        self,
        game: str = "",
        platform: str = "",
        market: str = "",
        genre: str = "",
        stage: str = "",
    ) -> list[StrategyEffectiveness]:
        """快捷推荐 — 从关键参数构建场景."""
        context = ContextProfile(
            game=game, platform=platform, market=market,
            genre=genre, stage=stage,
        )
        return self.recommend(context)

    # ── 查询 ──────────────────────────────────────────────────

    def get_effectiveness(
        self,
        strategy_type: CreativeStrategyType,
        context_key: str = "",
    ) -> StrategyEffectiveness | None:
        """获取指定策略的有效性."""
        if context_key:
            key = f"{context_key}:{strategy_type.value}"
            return self._effectiveness.get(key)
        # 聚合所有场景
        matched = [e for e in self._effectiveness.values() if e.strategy_type == strategy_type]
        if not matched:
            return None
        return StrategyEffectiveness(
            strategy_type=strategy_type,
            attempt_count=sum(e.attempt_count for e in matched),
            success_count=sum(e.success_count for e in matched),
            success_rate=sum(e.success_count for e in matched) / max(sum(e.attempt_count for e in matched), 1),
            avg_reward=sum(e.avg_reward for e in matched) / len(matched),
            avg_roas_improvement=sum(e.avg_roas_improvement for e in matched) / len(matched),
            confidence=sum(e.confidence for e in matched) / len(matched),
        )

    def get_records_by_strategy(
        self,
        strategy_type: CreativeStrategyType,
    ) -> list[StrategyRecord]:
        """获取指定策略的所有记录."""
        return [r for r in self._records if r.strategy_type == strategy_type]

    def get_records_by_context(
        self,
        context_key: str,
    ) -> list[StrategyRecord]:
        """获取指定场景的所有记录."""
        return [r for r in self._records if r.context_key == context_key]

    def get_all_effectiveness(self) -> list[StrategyEffectiveness]:
        """获取所有策略有效性."""
        return list(self._effectiveness.values())

    def get_reliable_strategies(self) -> list[StrategyEffectiveness]:
        """获取可靠策略 (attempt >= 5, confidence >= 0.5)."""
        return [e for e in self._effectiveness.values() if e.is_reliable]

    # ── 报告 ──────────────────────────────────────────────────

    def generate_report(self) -> StrategyMemoryReport:
        """生成策略记忆报告."""
        reliable = self.get_reliable_strategies()
        top = sorted(
            self._effectiveness.values(),
            key=lambda e: e.success_rate * e.confidence,
            reverse=True,
        )[:10]

        contexts = set(r.context_key for r in self._records)

        if reliable:
            best = reliable[0]
            summary = (
                f"共 {len(self._records)} 条策略记录，{len(contexts)} 个场景。"
                f"最佳策略: {best.strategy_type.value} (成功率 {best.success_rate:.0%}，"
                f"置信度 {best.confidence:.2f})"
            )
        else:
            summary = f"共 {len(self._records)} 条记录，{len(contexts)} 个场景，但无足够数据形成可靠策略"

        return StrategyMemoryReport(
            total_records=len(self._records),
            total_contexts=len(contexts),
            effectiveness=list(self._effectiveness.values()),
            top_strategies=top,
            summary=summary,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "total_records": len(self._records),
            "total_effectiveness": len(self._effectiveness),
            "reliable_strategies": len(self.get_reliable_strategies()),
        }

    def reset(self) -> None:
        self._records.clear()
        self._effectiveness.clear()


def create_strategy_memory(memory: CreativeMemory | None = None) -> StrategyMemory:
    """创建默认 StrategyMemory."""
    return StrategyMemory(memory=memory)