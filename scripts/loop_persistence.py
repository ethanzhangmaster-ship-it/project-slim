"""Growth Loop V2 — LoopPersistence 持久化管理器。

统一管理 Orchestrator 全部持久化状态的读写和启动恢复。

文件结构:
  data/growth_loop/
  ├── loop_state.json              # LoopState (覆盖写)
  ├── pending_evaluations.jsonl    # PendingEvaluation 列表 (全量覆盖写)
  ├── cycle_history.jsonl          # CycleRecord 列表 (追加写)
  └── experience_snapshot.json     # ExperienceStore 快照 (覆盖写)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.loop_state import LoopState
from scripts.pending_evaluation import PendingEvaluation

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# CycleRecord — 单轮循环历史归档
# ──────────────────────────────────────────────


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_cycle_record(
    loop_id: str,
    cycle_number: int,
    started_at: str,
    completed_at: str | None = None,
    duration_ms: int = 0,
    signal_ids: list[str] | None = None,
    diagnosis: dict[str, Any] | None = None,
    hypothesis: dict[str, Any] | None = None,
    strategy: dict[str, Any] | None = None,
    actions: list[dict[str, Any]] | None = None,
    execution_results: list[dict[str, Any]] | None = None,
    outcomes: list[dict[str, Any]] | None = None,
    actions_planned: int = 0,
    actions_executed: int = 0,
    actions_skipped: int = 0,
    actions_rolled_back: int = 0,
    pending_evaluations_created: int = 0,
    pending_evaluations_completed: int = 0,
) -> dict[str, Any]:
    """构建单轮循环记录 dict (用于追加写入 cycle_history.jsonl)。

    使用函数而非 dataclass，因为 CycleRecord 仅追加写入、按需读取，
    不需要反序列化路径。
    """
    return {
        "loop_id": loop_id,
        "cycle_number": cycle_number,
        "started_at": started_at,
        "completed_at": completed_at or _now_utc(),
        "duration_ms": duration_ms,
        "signal_ids": signal_ids or [],
        "diagnosis": diagnosis or {},
        "hypothesis": hypothesis or {},
        "strategy": strategy or {},
        "actions": actions or [],
        "execution_results": execution_results or [],
        "outcomes": outcomes or [],
        "actions_planned": actions_planned,
        "actions_executed": actions_executed,
        "actions_skipped": actions_skipped,
        "actions_rolled_back": actions_rolled_back,
        "pending_evaluations_created": pending_evaluations_created,
        "pending_evaluations_completed": pending_evaluations_completed,
    }


# ──────────────────────────────────────────────
# LoopPersistence — 持久化管理器
# ──────────────────────────────────────────────


class LoopPersistence:
    """Orchestrator 持久化管理器。

    统一管理 4 个持久化文件的读写，提供启动恢复接口。

    Usage:
        persistence = LoopPersistence(data_dir="data/growth_loop")

        # 启动恢复
        state = persistence.load_state()
        pending = persistence.load_pending_evaluations()

        # 循环运行中
        persistence.save_state(state)
        persistence.save_pending_evaluations(pending_list)
        persistence.append_cycle_record(cycle_record_dict)
    """

    # 文件名常量
    STATE_FILENAME = "loop_state.json"
    PENDING_FILENAME = "pending_evaluations.jsonl"
    HISTORY_FILENAME = "cycle_history.jsonl"
    EXPERIENCE_FILENAME = "experience_snapshot.json"

    def __init__(self, data_dir: Path | str = "data/growth_loop") -> None:
        """初始化持久化管理器。

        Args:
            data_dir: 持久化数据目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径
        self.state_path = self.data_dir / self.STATE_FILENAME
        self.pending_path = self.data_dir / self.PENDING_FILENAME
        self.history_path = self.data_dir / self.HISTORY_FILENAME
        self.experience_path = self.data_dir / self.EXPERIENCE_FILENAME

        logger.debug("LoopPersistence initialized: %s", self.data_dir)

    # ──────────────────────────────────────
    # LoopState
    # ──────────────────────────────────────

    def load_state(self) -> LoopState:
        """加载循环状态。

        文件不存在或解析失败时返回全新的 LoopState。
        """
        state = LoopState.load(self.state_path)
        if state is None:
            logger.info("No existing LoopState, creating new one")
            state = LoopState()
        return state

    def save_state(self, state: LoopState) -> None:
        """保存循环状态 (覆盖写)。"""
        state.save(self.state_path)

    # ──────────────────────────────────────
    # PendingEvaluation
    # ──────────────────────────────────────

    def load_pending_evaluations(self) -> list[PendingEvaluation]:
        """加载全部待评估记录。"""
        return PendingEvaluation.load_batch(self.pending_path)

    def save_pending_evaluations(
        self, pending_list: list[PendingEvaluation]
    ) -> None:
        """保存全部待评估记录 (全量覆盖写)。"""
        PendingEvaluation.save_batch(pending_list, self.pending_path)

    # ──────────────────────────────────────
    # CycleRecord (历史归档)
    # ──────────────────────────────────────

    def append_cycle_record(self, record: dict[str, Any]) -> None:
        """追加单轮循环记录到历史文件。

        Args:
            record: build_cycle_record() 构建的 dict
        """
        line = json.dumps(record, ensure_ascii=False)
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.debug(
            "CycleRecord appended: cycle=%d",
            record.get("cycle_number", -1),
        )

    def load_cycle_history(
        self, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """加载循环历史记录。

        Args:
            limit: 最多读取条数 (从最新开始); None 表示全部

        Returns:
            CycleRecord dict 列表 (按时间正序)
        """
        if not self.history_path.exists():
            return []

        lines = self.history_path.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse CycleRecord: %s", exc)

        if limit is not None:
            records = records[-limit:]
        return records

    # ──────────────────────────────────────
    # ExperienceStore 快照
    # ──────────────────────────────────────

    def save_experience_snapshot(self, records: list[dict[str, Any]]) -> None:
        """保存 ExperienceStore 快照 (覆盖写)。

        Args:
            records: ExperienceStore.to_dict_list() 的输出
        """
        self.experience_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Experience snapshot saved: %d records", len(records))

    def load_experience_snapshot(self) -> list[dict[str, Any]]:
        """加载 ExperienceStore 快照。

        Returns:
            ExperienceRecord dict 列表; 文件不存在时返回空列表
        """
        if not self.experience_path.exists():
            logger.debug("Experience snapshot not found")
            return []
        try:
            return json.loads(self.experience_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Failed to load experience snapshot: %s", exc)
            return []

    # ──────────────────────────────────────
    # 全量持久化 (循环结束时调用)
    # ──────────────────────────────────────

    def save_all(
        self,
        state: LoopState,
        pending_list: list[PendingEvaluation],
        experience_records: list[dict[str, Any]] | None = None,
        cycle_record: dict[str, Any] | None = None,
    ) -> None:
        """一次性保存全部状态 (循环结束时调用)。

        Args:
            state: 循环状态
            pending_list: 待评估队列
            experience_records: ExperienceStore 快照 (None 则跳过)
            cycle_record: 本轮循环记录 (None 则不追加)
        """
        self.save_state(state)
        self.save_pending_evaluations(pending_list)
        if experience_records is not None:
            self.save_experience_snapshot(experience_records)
        if cycle_record is not None:
            self.append_cycle_record(cycle_record)
        logger.info(
            "Persistence saved: cycle=%d, pending=%d",
            state.cycle_number,
            len(pending_list),
        )

    # ──────────────────────────────────────
    # 清理
    # ──────────────────────────────────────

    def clear_all(self) -> None:
        """清空全部持久化数据 (仅用于测试和重置)。"""
        for path in [
            self.state_path,
            self.pending_path,
            self.history_path,
            self.experience_path,
        ]:
            if path.exists():
                path.unlink()
        logger.info("All persistence data cleared: %s", self.data_dir)
