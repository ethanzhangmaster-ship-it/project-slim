"""E11.4.2 Evolution History — 进化历史记录器。

扩展 EvolutionHistory，提供：
  - 历史记录写入
  - 最佳代查询
  - 最新代查询
  - 序列化 / 反序列化

数据流：
  GenerationRecord → EvolutionHistory → ConvergenceDetector / Checkpoint
"""

from __future__ import annotations

from typing import Any

from .generation_schema import (
    EvolutionHistory,
    GenerationRecord,
    GenerationStatus,
)


class EvolutionHistoryRecorder:
    """进化历史记录器。

    封装 EvolutionHistory 并提供便捷的写入和查询方法。

    Usage:
        recorder = EvolutionHistoryRecorder(run_id="evo_001")
        recorder.record(gen_record)
        recorder.latest()
        recorder.best()
        recorder.to_dict()
    """

    def __init__(self, run_id: str = "") -> None:
        """初始化记录器。

        Args:
            run_id: 进化运行 ID
        """
        self._history = EvolutionHistory(run_id=run_id)

    # ── 属性 ──────────────────────────────────────────

    @property
    def history(self) -> EvolutionHistory:
        """底层 EvolutionHistory 实例。"""
        return self._history

    @property
    def run_id(self) -> str:
        return self._history.run_id

    @property
    def generation_count(self) -> int:
        return self._history.generation_count

    @property
    def score_progression(self) -> list[float]:
        return self._history.score_progression

    # ── 写入 ──────────────────────────────────────────

    def record(self, generation_record: GenerationRecord) -> None:
        """记录一代进化结果。

        Args:
            generation_record: 代记录
        """
        self._history.add_generation(generation_record)

    def record_batch(
        self,
        records: list[GenerationRecord],
    ) -> None:
        """批量记录多代结果。

        Args:
            records: 代记录列表
        """
        for record in records:
            self._history.add_generation(record)

    # ── 查询 ──────────────────────────────────────────

    def latest(self) -> GenerationRecord | None:
        """最新一代记录。"""
        return self._history.latest()

    def best(self) -> GenerationRecord | None:
        """评分最高的一代。"""
        return self._history.best()

    def highest_score(self) -> float:
        """历史最高评分。"""
        return self._history.highest_score()

    def get_generation(self, generation: int) -> GenerationRecord | None:
        """按代数查找。"""
        return self._history.get_generation(generation)

    def get_all(self) -> list[GenerationRecord]:
        """获取所有代记录。"""
        return list(self._history.generations)

    def get_completed(self) -> list[GenerationRecord]:
        """获取所有已完成的代。"""
        return [
            g for g in self._history.generations
            if g.status == GenerationStatus.COMPLETED
        ]

    def get_failed(self) -> list[GenerationRecord]:
        """获取所有失败的代。"""
        return [
            g for g in self._history.generations
            if g.status == GenerationStatus.FAILED
        ]

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return self._history.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionHistoryRecorder:
        history = EvolutionHistory.from_dict(data)
        recorder = cls(run_id=history.run_id)
        recorder._history = history
        return recorder

    def clear(self) -> None:
        """清空历史。"""
        self._history.clear()

    def __repr__(self) -> str:
        return repr(self._history)