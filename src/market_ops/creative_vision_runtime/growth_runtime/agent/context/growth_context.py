"""E13.7.2 Growth Context — 增长上下文构建器.

从多个数据源构建 LLM 推理所需的完整业务上下文:
  - 实时指标 (Metrics)
  - 素材状态 (Creative)
  - 记忆系统 (Memory)
  - 知识图谱 (Knowledge Graph)
  - 历史行动 (Past Actions)
  - 活跃目标 (Active Goals)

设计原则:
  - 上下文是 LLM 推理的"眼睛"
  - 所有数据源统一接口
  - 支持增量构建
  - 上下文大小可控

用法:
    builder = GrowthContextBuilder()
    context = builder.with_metrics(data).with_memory(data).build()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Data Sources
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetricsSnapshot:
    """指标快照."""
    spend: float = 0.0
    roas: float = 0.0
    roas_change: float = 0.0
    ctr: float = 0.0
    ctr_change: float = 0.0
    cpm: float = 0.0
    installs: int = 0
    installs_change: float = 0.0
    creative_fatigue: float = 0.0
    payer_quality: float = 0.5
    payer_rate: float = 0.0
    d30_ltv: float = 0.0
    frequency: float = 0.0
    spend_change: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend": self.spend,
            "roas": self.roas,
            "roas_change": self.roas_change,
            "ctr": self.ctr,
            "ctr_change": self.ctr_change,
            "cpm": self.cpm,
            "installs": self.installs,
            "installs_change": self.installs_change,
            "creative_fatigue": self.creative_fatigue,
            "payer_quality": self.payer_quality,
            "payer_rate": self.payer_rate,
            "d30_ltv": self.d30_ltv,
            "frequency": self.frequency,
            "spend_change": self.spend_change,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetricsSnapshot":
        known = {
            "spend", "roas", "roas_change", "ctr", "ctr_change", "cpm",
            "installs", "installs_change", "creative_fatigue", "payer_quality",
            "payer_rate", "d30_ltv", "frequency", "spend_change",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            spend=float(data.get("spend", 0)),
            roas=float(data.get("roas", 0)),
            roas_change=float(data.get("roas_change", 0)),
            ctr=float(data.get("ctr", 0)),
            ctr_change=float(data.get("ctr_change", 0)),
            cpm=float(data.get("cpm", 0)),
            installs=int(data.get("installs", 0)),
            installs_change=float(data.get("installs_change", 0)),
            creative_fatigue=float(data.get("creative_fatigue", 0)),
            payer_quality=float(data.get("payer_quality", 0.5)),
            payer_rate=float(data.get("payer_rate", 0)),
            d30_ltv=float(data.get("d30_ltv", 0)),
            frequency=float(data.get("frequency", 0)),
            spend_change=float(data.get("spend_change", 0)),
            extra=extra,
        )


@dataclass
class CreativeSnapshot:
    """素材快照."""
    total_creatives: int = 0
    active_creatives: int = 0
    fatigued_creatives: int = 0
    winner_creative: str = ""
    top_dna: str = ""
    top_ctr: float = 0.0
    avg_ctr: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_creatives": self.total_creatives,
            "active_creatives": self.active_creatives,
            "fatigued_creatives": self.fatigued_creatives,
            "winner_creative": self.winner_creative,
            "top_dna": self.top_dna,
            "top_ctr": self.top_ctr,
            "avg_ctr": self.avg_ctr,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreativeSnapshot":
        return cls(
            total_creatives=int(data.get("total_creatives", 0)),
            active_creatives=int(data.get("active_creatives", 0)),
            fatigued_creatives=int(data.get("fatigued_creatives", 0)),
            winner_creative=str(data.get("winner_creative", "")),
            top_dna=str(data.get("top_dna", "")),
            top_ctr=float(data.get("top_ctr", 0)),
            avg_ctr=float(data.get("avg_ctr", 0)),
        )


# ═══════════════════════════════════════════════════════════════
# Growth Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthContext:
    """增长上下文 — LLM 推理的完整输入.

    Attributes:
        product_name: 产品名称
        platform: 平台
        market: 市场
        metrics: 指标快照
        creative: 素材快照
        pattern_memories: 模式记忆
        strategy_memories: 策略记忆
        failure_memories: 失败记忆
        knowledge: 知识图谱
        past_actions: 历史行动
        active_goals: 活跃目标
        cycle: 当前循环
        timestamp: 时间戳
    """
    product_name: str = ""
    platform: str = ""
    market: str = ""
    metrics: MetricsSnapshot = field(default_factory=MetricsSnapshot)
    creative: CreativeSnapshot = field(default_factory=CreativeSnapshot)
    pattern_memories: list[dict[str, Any]] = field(default_factory=list)
    strategy_memories: list[dict[str, Any]] = field(default_factory=list)
    failure_memories: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    past_actions: list[dict[str, Any]] = field(default_factory=list)
    active_goals: list[dict[str, Any]] = field(default_factory=list)
    cycle: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_prompt_context(self) -> dict[str, Any]:
        """转换为 Prompt Builder 可用的格式."""
        return {
            "product_name": self.product_name,
            "platform": self.platform,
            "market": self.market,
            "metrics": self.metrics.to_dict(),
            "creative": self.creative.to_dict(),
            "pattern_memories": self.pattern_memories,
            "strategy_memories": self.strategy_memories,
            "failure_memories": self.failure_memories,
            "knowledge": self.knowledge,
            "past_actions": self.past_actions,
            "active_goals": self.active_goals,
            "cycle": self.cycle,
        }


# ═══════════════════════════════════════════════════════════════
# Growth Context Builder
# ═══════════════════════════════════════════════════════════════


class GrowthContextBuilder:
    """增长上下文构建器 — 从多个数据源组装 GrowthContext.

    用法:
        builder = GrowthContextBuilder()
        context = (
            builder
            .with_product("Witch Merge", "iOS", "US")
            .with_metrics({"roas": 0.53, "creative_fatigue": 0.81})
            .with_memory(working_memory, semantic_memory)
            .with_past_actions(recent_actions)
            .build()
        )
    """

    def __init__(self):
        self._context = GrowthContext()

    def with_product(self, name: str, platform: str = "", market: str = "") -> "GrowthContextBuilder":
        """设置产品信息."""
        self._context.product_name = name
        self._context.platform = platform
        self._context.market = market
        return self

    def with_metrics(self, metrics: dict[str, Any]) -> "GrowthContextBuilder":
        """设置指标."""
        self._context.metrics = MetricsSnapshot.from_dict(metrics)
        # 同时从 metrics 中提取素材信息
        self._context.creative.top_ctr = float(metrics.get("top_creative_ctr", 0))
        self._context.creative.avg_ctr = float(metrics.get("avg_ctr", 0))
        return self

    def with_creative(self, creative: dict[str, Any]) -> "GrowthContextBuilder":
        """设置素材状态."""
        self._context.creative = CreativeSnapshot.from_dict(creative)
        return self

    def with_memory(
        self,
        working_memory: Any = None,
        semantic_memory: Any = None,
        episodic_memory: Any = None,
        failure_memory: Any = None,
    ) -> "GrowthContextBuilder":
        """从记忆系统提取上下文."""
        # 语义记忆
        if semantic_memory:
            try:
                knowledge = semantic_memory.query("growth", n=5)
                self._context.pattern_memories = [
                    {"concept": k.concept, "description": k.description, "confidence": k.confidence}
                    for k in knowledge
                ]
            except Exception:
                pass

        # 情景记忆
        if episodic_memory:
            try:
                recent = episodic_memory.get_recent(5)
                self._context.past_actions = [
                    {"action_type": e.get("action_type", "unknown"), "result": e.get("outcome", "unknown")}
                    for e in recent
                ]
            except Exception:
                pass

        # 失败记忆
        if failure_memory:
            try:
                failures = failure_memory.get_recent(5)
                self._context.failure_memories = [
                    {"pattern": f.get("pattern", "unknown"), "lesson": f.get("lesson", "")}
                    for f in failures
                ]
            except Exception:
                pass

        return self

    def with_knowledge(self, knowledge: list[dict[str, Any]]) -> "GrowthContextBuilder":
        """设置知识图谱."""
        self._context.knowledge = knowledge
        return self

    def with_past_actions(self, actions: list[dict[str, Any]]) -> "GrowthContextBuilder":
        """设置历史行动."""
        self._context.past_actions = actions
        return self

    def with_goals(self, goals: list[dict[str, Any]]) -> "GrowthContextBuilder":
        """设置活跃目标."""
        self._context.active_goals = goals
        return self

    def with_cycle(self, cycle: int) -> "GrowthContextBuilder":
        """设置循环编号."""
        self._context.cycle = cycle
        return self

    def build(self) -> GrowthContext:
        """构建 GrowthContext."""
        return self._context

    def reset(self) -> "GrowthContextBuilder":
        """重置构建器."""
        self._context = GrowthContext()
        return self