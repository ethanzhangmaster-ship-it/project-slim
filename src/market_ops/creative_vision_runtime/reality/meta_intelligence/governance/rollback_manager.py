"""E12.6.3 — Rollback Manager。

回滚管理器。

负责将系统恢复到安全状态，支持三种回滚:
  - Creative Rollback:  恢复 previous winner genome
  - Budget Rollback:    恢复 previous budget level
  - Strategy Rollback:  恢复 previous strategy version
"""

from __future__ import annotations

from typing import Any

from .models import (
    RollbackRecord,
    SafetyContext,
    SafetyDecision,
)


class RollbackManager:
    """回滚管理器。

    维护历史状态快照，支持安全回滚。
    """

    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self._history: list[RollbackRecord] = []
        self._creative_snapshots: dict[str, list[dict[str, Any]]] = {}
        self._budget_snapshots: dict[str, list[dict[str, Any]]] = {}
        self._strategy_snapshots: dict[str, list[dict[str, Any]]] = {}

    # ── Creative Rollback ──

    def save_creative_state(
        self,
        product_id: str,
        genome_id: str,
        state: dict[str, Any],
    ) -> None:
        """保存创意状态快照。"""
        if self.max_history <= 0:
            return
        key = f"{product_id}:{genome_id}"
        if key not in self._creative_snapshots:
            self._creative_snapshots[key] = []
        self._creative_snapshots[key].append(dict(state))

        # 限制历史数量
        if len(self._creative_snapshots[key]) > self.max_history:
            self._creative_snapshots[key] = self._creative_snapshots[key][-self.max_history:]

    def get_creative_state(
        self,
        product_id: str,
        genome_id: str,
    ) -> dict[str, Any] | None:
        """获取最近的创意状态快照。"""
        key = f"{product_id}:{genome_id}"
        snapshots = self._creative_snapshots.get(key, [])
        if not snapshots:
            return None
        return dict(snapshots[-1])

    def rollback_creative(
        self,
        product_id: str,
        genome_id: str,
        reason: str,
    ) -> RollbackRecord | None:
        """回滚创意到上一个安全状态。

        Args:
            product_id: 产品 ID
            genome_id:  Genome ID
            reason:     回滚原因

        Returns:
            RollbackRecord 或 None（无历史状态）
        """
        key = f"{product_id}:{genome_id}"
        snapshots = self._creative_snapshots.get(key, [])

        if len(snapshots) < 2:
            return None

        current = snapshots[-1]
        previous = snapshots[-2]

        record = RollbackRecord(
            product_id=product_id,
            target_type="creative",
            target_id=genome_id,
            before_state=dict(current),
            after_state=dict(previous),
            reason=reason,
        )
        self._history.append(record)

        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

        return record

    # ── Budget Rollback ──

    def save_budget_state(
        self,
        product_id: str,
        state: dict[str, Any],
    ) -> None:
        """保存预算状态快照。"""
        if self.max_history <= 0:
            return
        if product_id not in self._budget_snapshots:
            self._budget_snapshots[product_id] = []
        self._budget_snapshots[product_id].append(dict(state))

        if len(self._budget_snapshots[product_id]) > self.max_history:
            self._budget_snapshots[product_id] = self._budget_snapshots[product_id][-self.max_history:]

    def get_budget_state(
        self,
        product_id: str,
    ) -> dict[str, Any] | None:
        """获取最近的预算状态快照。"""
        snapshots = self._budget_snapshots.get(product_id, [])
        if not snapshots:
            return None
        return dict(snapshots[-1])

    def rollback_budget(
        self,
        product_id: str,
        reason: str,
        target_budget: float | None = None,
    ) -> RollbackRecord | None:
        """回滚预算到上一个安全状态。

        Args:
            product_id:    产品 ID
            reason:        回滚原因
            target_budget: 目标预算（不传则使用上一个快照）

        Returns:
            RollbackRecord 或 None
        """
        snapshots = self._budget_snapshots.get(product_id, [])

        if len(snapshots) < 2:
            return None

        current = snapshots[-1]
        previous = snapshots[-2]

        after_state = dict(previous)
        if target_budget is not None:
            after_state["budget"] = target_budget

        record = RollbackRecord(
            product_id=product_id,
            target_type="budget",
            target_id=product_id,
            before_state=dict(current),
            after_state=after_state,
            reason=reason,
        )
        self._history.append(record)

        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

        return record

    # ── Strategy Rollback ──

    def save_strategy_state(
        self,
        product_id: str,
        strategy_id: str,
        state: dict[str, Any],
    ) -> None:
        """保存策略状态快照。"""
        if self.max_history <= 0:
            return
        key = f"{product_id}:{strategy_id}"
        if key not in self._strategy_snapshots:
            self._strategy_snapshots[key] = []
        self._strategy_snapshots[key].append(dict(state))

        if len(self._strategy_snapshots[key]) > self.max_history:
            self._strategy_snapshots[key] = self._strategy_snapshots[key][-self.max_history:]

    def get_strategy_state(
        self,
        product_id: str,
        strategy_id: str,
    ) -> dict[str, Any] | None:
        """获取最近的策略状态快照。"""
        key = f"{product_id}:{strategy_id}"
        snapshots = self._strategy_snapshots.get(key, [])
        if not snapshots:
            return None
        return dict(snapshots[-1])

    def rollback_strategy(
        self,
        product_id: str,
        strategy_id: str,
        reason: str,
    ) -> RollbackRecord | None:
        """回滚策略到上一个安全状态。"""
        key = f"{product_id}:{strategy_id}"
        snapshots = self._strategy_snapshots.get(key, [])

        if len(snapshots) < 2:
            return None

        current = snapshots[-1]
        previous = snapshots[-2]

        record = RollbackRecord(
            product_id=product_id,
            target_type="strategy",
            target_id=strategy_id,
            before_state=dict(current),
            after_state=dict(previous),
            reason=reason,
        )
        self._history.append(record)

        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

        return record

    # ── General ──

    def get_history(
        self,
        product_id: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
    ) -> list[RollbackRecord]:
        """获取回滚历史记录。

        Args:
            product_id:  按产品过滤
            target_type: 按类型过滤
            limit:       最大返回数量

        Returns:
            RollbackRecord 列表
        """
        records = self._history

        if product_id:
            records = [r for r in records if r.product_id == product_id]
        if target_type:
            records = [r for r in records if r.target_type == target_type]

        return records[-limit:]

    def get_history_count(self) -> int:
        """获取回滚历史总数。"""
        return len(self._history)

    def get_snapshot_count(
        self,
        snapshot_type: str = "creative",
    ) -> dict[str, int]:
        """获取各产品的快照数量。"""
        if snapshot_type == "creative":
            source = self._creative_snapshots
        elif snapshot_type == "budget":
            source = self._budget_snapshots
        elif snapshot_type == "strategy":
            source = self._strategy_snapshots
        else:
            return {}

        return {k: len(v) for k, v in source.items()}

    def clear_history(self) -> None:
        """清空所有回滚历史和快照。"""
        self._history.clear()
        self._creative_snapshots.clear()
        self._budget_snapshots.clear()
        self._strategy_snapshots.clear()

    def __repr__(self) -> str:
        return (
            f"RollbackManager(history={len(self._history)}, "
            f"max={self.max_history})"
        )