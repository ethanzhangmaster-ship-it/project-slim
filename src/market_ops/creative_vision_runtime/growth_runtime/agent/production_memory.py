"""E13.7.4 Production Memory — 生产长期记忆.

Production Memory 记录 Agent 每次循环的完整决策过程:
  - 观察了什么 (observation)
  - 推理了什么 (reasoning)
  - 决定了什么 (decision)
  - 结果是什么 (result)
  - 学到了什么 (learning)

形成可追溯的 Agent Long Term Memory, 支持:
  - 按时间范围查询
  - 按成功/失败过滤
  - 按动作类型搜索
  - 模式提取和趋势分析
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CycleRecord:
    """单次循环记录 — 完整的决策过程快照.

    Attributes:
        record_id: 记录 ID
        cycle_id: 循环 ID (如 "20260727_001")
        timestamp: 记录时间
        observation: 观察数据 (指标快照)
        reasoning: 推理结果 (诊断、原因)
        decision: 决策结果 (动作)
        plan: 执行计划
        result: 执行结果 (ROAS 变化等)
        learning: 经验教训 (模式、规律)
        success: 循环是否成功
        duration_seconds: 循环耗时
        tags: 标签
        metadata: 扩展元数据
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    observation: dict[str, Any] = field(default_factory=dict)
    reasoning: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    duration_seconds: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "observation": self.observation,
            "reasoning": self.reasoning,
            "decision": self.decision,
            "plan": self.plan,
            "result": self.result,
            "learning": self.learning,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class ProductionMemory:
    """生产记忆 — Agent 的长期记忆存储.

    存储每次循环的完整记录, 支持查询和分析。
    """

    # 最大记录数
    MAX_RECORDS: int = 10000

    def __init__(self, max_records: int = 10000):
        self._records: list[CycleRecord] = []
        self._max_records = max_records

    # ── Properties ────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._records)

    # ── 记录操作 ──────────────────────────────────────────────

    def record(self, record: CycleRecord) -> None:
        """记录一次循环."""
        self._records.append(record)

        # 限制最大记录数
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    def create_record(
        self,
        cycle_id: str,
        observation: dict[str, Any] | None = None,
        reasoning: dict[str, Any] | None = None,
        decision: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        learning: dict[str, Any] | None = None,
        success: bool = True,
        duration_seconds: float = 0.0,
        tags: list[str] | None = None,
    ) -> CycleRecord:
        """创建并存储一条循环记录."""
        record = CycleRecord(
            cycle_id=cycle_id,
            observation=observation or {},
            reasoning=reasoning or {},
            decision=decision or {},
            plan=plan or {},
            result=result or {},
            learning=learning or {},
            success=success,
            duration_seconds=duration_seconds,
            tags=tags or [],
        )
        self.record(record)
        return record

    # ── 查询 ──────────────────────────────────────────────────

    def get_recent(self, n: int = 20) -> list[CycleRecord]:
        """获取最近 N 条记录."""
        return self._records[-n:]

    def get_by_date(self, date_str: str) -> list[CycleRecord]:
        """按日期查询 (格式: 20260727)."""
        return [r for r in self._records if r.cycle_id.startswith(date_str)]

    def get_successful(self) -> list[CycleRecord]:
        """获取所有成功记录."""
        return [r for r in self._records if r.success]

    def get_failures(self) -> list[CycleRecord]:
        """获取所有失败记录."""
        return [r for r in self._records if not r.success]

    def get_by_tag(self, tag: str) -> list[CycleRecord]:
        """按标签查询."""
        return [r for r in self._records if tag in r.tags]

    def get_by_action(self, action_type: str) -> list[CycleRecord]:
        """按动作类型查询."""
        return [
            r for r in self._records
            if action_type in r.decision.get("action", "")
            or action_type in str(r.plan.get("actions", ""))
        ]

    # ── 分析 ──────────────────────────────────────────────────

    def get_patterns(self) -> list[dict[str, Any]]:
        """提取重复出现的成功模式."""
        patterns = []
        seen = set()

        for r in self.get_successful():
            learning = r.learning.get("pattern", "")
            if learning and learning not in seen:
                seen.add(learning)
                patterns.append({
                    "pattern": learning,
                    "count": sum(
                        1 for r2 in self._records
                        if r2.learning.get("pattern") == learning
                    ),
                    "last_seen": r.timestamp,
                })

        return sorted(patterns, key=lambda p: p["count"], reverse=True)

    def get_learning_summary(self) -> dict[str, Any]:
        """获取学习摘要."""
        total = len(self._records)
        if total == 0:
            return {"total_records": 0}

        successful = len(self.get_successful())
        failures = len(self.get_failures())

        patterns = self.get_patterns()

        return {
            "total_records": total,
            "successful": successful,
            "failures": failures,
            "success_rate": successful / total if total > 0 else 0,
            "top_patterns": patterns[:5],
            "avg_duration": (
                sum(r.duration_seconds for r in self._records) / total
                if total > 0 else 0
            ),
            "date_range": {
                "first": self._records[0].timestamp if self._records else "",
                "last": self._records[-1].timestamp if self._records else "",
            },
        }

    def get_trend(self, metric: str, n: int = 10) -> list[dict[str, Any]]:
        """获取指标趋势.

        Args:
            metric: 指标路径 (如 "observation.roas", "result.roas_after")
            n: 最近 N 条

        Returns:
            趋势数据列表
        """
        trend = []
        for r in self._records[-n:]:
            value = None
            parts = metric.split(".")
            data = r.to_dict()
            for part in parts:
                data = data.get(part, {}) if isinstance(data, dict) else None
            if data is not None:
                value = data

            trend.append({
                "cycle_id": r.cycle_id,
                "timestamp": r.timestamp,
                "value": value,
                "success": r.success,
            })
        return trend

    def stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return {
            "size": self.size,
            "max_records": self._max_records,
            **self.get_learning_summary(),
        }

    def clear(self) -> None:
        """清空记忆."""
        self._records.clear()


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_production_memory(max_records: int = 10000) -> ProductionMemory:
    """创建默认生产记忆."""
    return ProductionMemory(max_records=max_records)