"""Growth Loop V2 — LoopState 循环运行状态。

Orchestrator 的运行状态快照，跨重启续跑的关键。

持久化: data/growth_loop/loop_state.json (覆盖写)
序列化: to_dict() / from_dict() 双向
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    """当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LoopState:
    """Orchestrator 运行状态 — 跨重启续跑的关键。

    每轮循环结束后覆盖写入 loop_state.json。
    启动时读取此文件恢复循环上下文。
    """

    # ── 循环标识 ──
    loop_id: str = ""
    cycle_number: int = 0

    # ── 运行模式 ──
    mode: str = "manual"            # manual / autonomous
    interval_hours: float = 6.0     # autonomous 模式的轮询间隔

    # ── 时间戳 (全部 UTC ISO) ──
    started_at: str = ""
    last_cycle_at: str = ""
    next_cycle_at: str = ""

    # ── 统计 ──
    total_cycles: int = 0
    total_actions_executed: int = 0
    total_actions_skipped: int = 0
    total_outcomes_evaluated: int = 0

    # ── 经验统计快照 ──
    experience_count: int = 0
    success_rate: float = 0.5

    def __post_init__(self) -> None:
        if not self.loop_id:
            self.loop_id = f"loop_{uuid4().hex[:12]}"
        if not self.started_at:
            self.started_at = _now_utc()

    # ──────────────────────────────────────
    # 序列化 / 反序列化
    # ──────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化为 dict (JSON 可序列化)。"""
        return {
            "loop_id": self.loop_id,
            "cycle_number": self.cycle_number,
            "mode": self.mode,
            "interval_hours": self.interval_hours,
            "started_at": self.started_at,
            "last_cycle_at": self.last_cycle_at,
            "next_cycle_at": self.next_cycle_at,
            "total_cycles": self.total_cycles,
            "total_actions_executed": self.total_actions_executed,
            "total_actions_skipped": self.total_actions_skipped,
            "total_outcomes_evaluated": self.total_outcomes_evaluated,
            "experience_count": self.experience_count,
            "success_rate": round(self.success_rate, 4),
        }

    @classmethod
    def from_dict(cls, data: dict) -> LoopState:
        """从 dict 反序列化。

        忽略未知字段，缺失字段使用默认值。
        """
        known_fields = {
            "loop_id", "cycle_number", "mode", "interval_hours",
            "started_at", "last_cycle_at", "next_cycle_at",
            "total_cycles", "total_actions_executed", "total_actions_skipped",
            "total_outcomes_evaluated",
            "experience_count", "success_rate",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    # ──────────────────────────────────────
    # 文件 I/O
    # ──────────────────────────────────────

    def save(self, path: Path | str) -> None:
        """覆盖写入 JSON 文件。

        Args:
            path: loop_state.json 的路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("LoopState saved to %s (cycle=%d)", path, self.cycle_number)

    @classmethod
    def load(cls, path: Path | str) -> LoopState | None:
        """从 JSON 文件读取。

        Args:
            path: loop_state.json 的路径

        Returns:
            LoopState 实例; 文件不存在或解析失败时返回 None
        """
        path = Path(path)
        if not path.exists():
            logger.debug("LoopState file not found: %s", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to load LoopState from %s: %s", path, exc)
            return None

    # ──────────────────────────────────────
    # 便捷方法
    # ──────────────────────────────────────

    def advance_cycle(self) -> None:
        """推进到下一轮 — 更新轮次号和时间戳。"""
        self.cycle_number += 1
        self.total_cycles += 1
        self.last_cycle_at = _now_utc()
