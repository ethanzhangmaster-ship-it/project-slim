"""P0 ApprovalGate V2 — BudgetWindowTracker.

Spec: docs/p0_approval_gate_v2_spec.md §5.1, §6 (累计窗口查询), §12 (跨重启持久化)

职责：按 (game_id, action_type, day) 维度追踪 Level 0 自动批准动作的累计金额，
防止小额高频动作绕过单次阈值。Policy.evaluate() 在分级前调用 get_cumulative()
查询当日累计，action_executor 在真实执行后调用 record() 记账。

设计纪律（继承全库 + Spec §1）：
- 持久化风格对齐 src/execution/approval/store.py（append-only JSONL）
- 跨重启可重建：启动时从 JSONL 重载当日累计
- 线程不安全（与 store.py 一致，单进程使用；多进程需外部锁）
- 不抛异常中断主流程：IO 失败回退内存态
- 金额单位固定 USD，不做币种转换
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

DEFAULT_BUDGET_WINDOW_DIR = "outputs/approval_audit"
DEFAULT_BUDGET_WINDOW_FILENAME = "budget_window.jsonl"

# JSONL 记录字段名
FIELD_TS = "ts"
FIELD_GAME_ID = "game_id"
FIELD_ACTION_TYPE = "action_type"
FIELD_DAY = "day"  # YYYY-MM-DD（与 date.isoformat() 一致）
FIELD_AMOUNT_USD = "amount_usd"
FIELD_ACTION_ID = "action_id"


def _parse_float_safe(value: object, default: float = 0.0) -> float:
    """解析浮点，失败回退默认值（fail-safe，对齐 config.py::_parse_float）。"""
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


@dataclass
class BudgetWindowEntry:
    """单条预算窗口记账记录（对应 JSONL 一行）。"""

    game_id: str
    action_type: str
    day: str  # YYYY-MM-DD
    amount_usd: float
    action_id: str
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, object]:
        return {
            FIELD_TS: self.ts,
            FIELD_GAME_ID: self.game_id,
            FIELD_ACTION_TYPE: self.action_type,
            FIELD_DAY: self.day,
            FIELD_AMOUNT_USD: self.amount_usd,
            FIELD_ACTION_ID: self.action_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "BudgetWindowEntry":
        return cls(
            game_id=str(d.get(FIELD_GAME_ID, "")),
            action_type=str(d.get(FIELD_ACTION_TYPE, "")),
            day=str(d.get(FIELD_DAY, "")),
            amount_usd=_parse_float_safe(d.get(FIELD_AMOUNT_USD, 0.0)),
            action_id=str(d.get(FIELD_ACTION_ID, "")),
            ts=str(d.get(FIELD_TS, "")),
        )


# ──────────────────────────────────────────────
# 主类
# ──────────────────────────────────────────────


class BudgetWindowTracker:
    """日累计预算追踪器（按 game_id + action_type + day 聚合）。

    用法：
        tracker = BudgetWindowTracker(audit_log_dir)
        tracker.load_for_today()  # 启动时重建当日内存索引（可选）
        cumulative = tracker.get_cumulative(game_id, action_type, today)
        if cumulative + amount <= LIMIT:
            tracker.record(game_id, action_type, amount, action_id)

    持久化约定（Spec §12）：
        - 文件路径：{audit_log_dir}/budget_window.jsonl
        - append-only，每条 record() 调用写一行
        - 跨重启：启动时调用 load_for_today() 重载当日累计到内存
        - 历史日数据保留在文件中，但内存索引只保留当日（按 day 过滤）

    线程安全：与 store.py 一致，非线程安全。多进程需外部锁。
    """

    def __init__(
        self,
        audit_log_dir: str = DEFAULT_BUDGET_WINDOW_DIR,
        filename: str = DEFAULT_BUDGET_WINDOW_FILENAME,
    ) -> None:
        self._audit_log_dir = audit_log_dir
        self._path = os.path.join(audit_log_dir, filename)
        # 内存索引：(game_id, action_type, day_str) -> 累计金额
        self._cumulative: Dict[Tuple[str, str, str], float] = {}
        # 已加载的日期集合（避免重复 load）
        self._loaded_days: set[str] = set()

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def path(self) -> str:
        """JSONL 文件完整路径（供测试断言）。"""
        return self._path

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_cumulative(
        self,
        game_id: str,
        action_type: str,
        day: date,
    ) -> float:
        """查询 (game_id, action_type, day) 当日累计金额。

        若当日未 load，会惰性加载一次（Spec §12 跨重启重建）。
        返回 0.0 表示当日无记录或加载失败。

        Args:
            game_id: 游戏 ID（如 "p04_witch_merge"）
            action_type: 动作类型（如 "SCALE_BUDGET"，与 ExecutionAction.value 一致）
            day: 查询日期

        Returns:
            当日累计 USD 金额
        """
        day_str = day.isoformat()
        # 惰性加载当日（若未加载过）
        if day_str not in self._loaded_days:
            self._load_day(day_str)
        key = (game_id, action_type, day_str)
        return self._cumulative.get(key, 0.0)

    # ------------------------------------------------------------------
    # 记账
    # ------------------------------------------------------------------

    def record(
        self,
        game_id: str,
        action_type: str,
        amount_usd: float,
        action_id: str,
        day: Optional[date] = None,
    ) -> None:
        """记录一笔已执行的金额到当日窗口。

        同时更新内存索引和持久化 JSONL。IO 失败不抛异常，仅 log warning，
        内存索引仍更新（保证当次进程内 get_cumulative 正确）。

        Args:
            game_id: 游戏 ID
            action_type: 动作类型
            amount_usd: 金额（USD，正数；负数取绝对值记账）
            action_id: 关联动作 ID（供审计追溯）
            day: 可选日期，默认 today(UTC)
        """
        if day is None:
            day = datetime.now(timezone.utc).date()
        day_str = day.isoformat()
        abs_amount = abs(amount_usd)

        # 更新内存索引
        key = (game_id, action_type, day_str)
        self._cumulative[key] = self._cumulative.get(key, 0.0) + abs_amount

        # 持久化（fail-safe：IO 失败不中断主流程）
        entry = BudgetWindowEntry(
            game_id=game_id,
            action_type=action_type,
            day=day_str,
            amount_usd=abs_amount,
            action_id=action_id,
        )
        try:
            self._append(entry.to_dict())
        except OSError as e:
            logger.warning(
                "BudgetWindowTracker: persist failed (in-memory still updated): "
                "game_id=%s action=%s amount=%.2f day=%s err=%s",
                game_id,
                action_type,
                abs_amount,
                day_str,
                e,
            )

        # 标记当日已加载（record 后内存即权威，无需再 load）
        self._loaded_days.add(day_str)

    # ------------------------------------------------------------------
    # 重置（仅测试用，生产不调用）
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """清空内存索引（不影响已持久化的 JSONL 文件）。

        仅供测试在测试间隔离状态。生产代码禁止调用。
        """
        self._cumulative.clear()
        self._loaded_days.clear()

    # ------------------------------------------------------------------
    # 持久化内部实现
    # ------------------------------------------------------------------

    def _append(self, record: Dict[str, object]) -> None:
        """追加一行到 JSONL（风格对齐 store.py::_append）。"""
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_day(self, day_str: str) -> None:
        """从 JSONL 重载指定日期的累计到内存索引。

        - 文件不存在 → 静默返回（当日无记录）
        - 解析失败 → 跳过该行（与 store.py::_read_all 一致）
        - 重复加载保护：通过 _loaded_days 避免重复扫描

        Spec §12：跨重启场景，启动后首次 get_cumulative 会触发此方法。
        """
        self._loaded_days.add(day_str)  # 先标记，防止 record() 后重复 load
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    try:
                        entry = BudgetWindowEntry.from_dict(raw)
                    except (ValueError, TypeError):
                        continue
                    # 只聚合目标日
                    if entry.day != day_str:
                        continue
                    key = (entry.game_id, entry.action_type, entry.day)
                    # 注意：load 时不覆盖已 record 的内存值（record 是权威）
                    self._cumulative[key] = (
                        self._cumulative.get(key, 0.0) + entry.amount_usd
                    )
        except OSError as e:
            logger.warning(
                "BudgetWindowTracker: load_day(%s) failed: %s", day_str, e
            )


__all__ = [
    "BudgetWindowTracker",
    "BudgetWindowEntry",
    "DEFAULT_BUDGET_WINDOW_DIR",
    "DEFAULT_BUDGET_WINDOW_FILENAME",
]
