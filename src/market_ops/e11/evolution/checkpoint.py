"""E11.4.2 Checkpoint — 进化断点保存/恢复。

防止进化中断导致进度丢失。

保存内容：
  - run_id: 进化运行 ID
  - generation: 当前代数
  - population: 当前种群状态
  - history: 进化历史
  - config: 进化配置

支持：
  save()    — 保存断点
  load()    — 加载断点
  restore() — 恢复断点

数据流：
  Orchestrator → Checkpoint.save() → checkpoint_data
  checkpoint_data → Checkpoint.load() → restored state
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .generation_schema import EvolutionHistory, GenerationRecord
from .orchestrator_schema import EvolutionConfig, EvolutionRun
from .population_schema import GenomePopulation


# ═══════════════════════════════════════════════════════════
# CheckpointRecord — 断点记录
# ═══════════════════════════════════════════════════════════

@dataclass
class CheckpointRecord:
    """一次断点保存的完整记录。

    包含当前进化状态的所有必要信息。
    """
    checkpoint_id: str = field(default_factory=lambda: f"ckpt_{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    generation: int = 0
    population: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    saved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "run_id": self.run_id,
            "generation": self.generation,
            "population": self.population,
            "history": self.history,
            "config": self.config,
            "saved_at": self.saved_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointRecord:
        saved_at = data.get("saved_at")
        return cls(
            checkpoint_id=data.get("checkpoint_id", ""),
            run_id=data.get("run_id", ""),
            generation=data.get("generation", 0),
            population=data.get("population"),
            history=data.get("history"),
            config=data.get("config"),
            saved_at=datetime.fromisoformat(saved_at) if saved_at else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"CheckpointRecord(id={self.checkpoint_id!r}, "
            f"run={self.run_id!r}, gen={self.generation})"
        )


# ═══════════════════════════════════════════════════════════
# CheckpointManager — 断点管理器
# ═══════════════════════════════════════════════════════════

class CheckpointManager:
    """断点管理器。

    提供 save/load/restore 功能，支持内存中的断点存储。

    Usage:
        ckpt = CheckpointManager()
        ckpt.save(run, population, history, config)
        # ... 进化中断 ...
        state = ckpt.load(checkpoint_id)
        pop, history, config = ckpt.restore(checkpoint_id)
    """

    def __init__(self) -> None:
        self._checkpoints: dict[str, CheckpointRecord] = {}

    # ── 保存 ──────────────────────────────────────────

    def save(
        self,
        run: EvolutionRun,
        population: GenomePopulation,
        history: EvolutionHistory,
        config: EvolutionConfig,
        checkpoint_id: str = "",
    ) -> CheckpointRecord:
        """保存当前进化状态为断点。

        Args:
            run: 当前 EvolutionRun
            population: 当前种群
            history: 进化历史
            config: 进化配置
            checkpoint_id: 断点 ID（默认自动生成）

        Returns:
            CheckpointRecord
        """
        record = CheckpointRecord(
            run_id=run.run_id,
            generation=run.generation,
            population=population.to_dict(),
            history=history.to_dict(),
            config=config.to_dict(),
        )
        # 如果指定了 checkpoint_id，覆盖自动生成的
        if checkpoint_id:
            record.checkpoint_id = checkpoint_id
        self._checkpoints[record.checkpoint_id] = record
        return record

    # ── 加载 ──────────────────────────────────────────

    def load(self, checkpoint_id: str) -> CheckpointRecord | None:
        """加载断点。

        Args:
            checkpoint_id: 断点 ID

        Returns:
            CheckpointRecord 或 None
        """
        return self._checkpoints.get(checkpoint_id)

    def restore(
        self,
        checkpoint_id: str,
    ) -> tuple[GenomePopulation | None, EvolutionHistory | None, EvolutionConfig | None]:
        """恢复断点，返回种群、历史和配置。

        Args:
            checkpoint_id: 断点 ID

        Returns:
            (population, history, config) 三元组，未找到时返回 (None, None, None)
        """
        record = self._checkpoints.get(checkpoint_id)
        if record is None:
            return None, None, None

        population = None
        history = None
        config = None

        if record.population:
            population = GenomePopulation.from_dict(record.population)
        if record.history:
            history = EvolutionHistory.from_dict(record.history)
        if record.config:
            config = EvolutionConfig.from_dict(record.config)

        return population, history, config

    # ── 管理 ──────────────────────────────────────────

    def delete(self, checkpoint_id: str) -> bool:
        """删除断点。

        Returns:
            是否成功删除
        """
        if checkpoint_id in self._checkpoints:
            del self._checkpoints[checkpoint_id]
            return True
        return False

    def list_all(self) -> list[CheckpointRecord]:
        """列出所有断点。"""
        return list(self._checkpoints.values())

    @property
    def checkpoint_count(self) -> int:
        """断点数量。"""
        return len(self._checkpoints)

    def clear(self) -> None:
        """清空所有断点。"""
        self._checkpoints.clear()

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            cid: record.to_dict()
            for cid, record in self._checkpoints.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointManager:
        manager = cls()
        for cid, record_data in data.items():
            record = CheckpointRecord.from_dict(record_data)
            manager._checkpoints[cid] = record
        return manager