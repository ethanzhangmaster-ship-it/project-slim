"""Growth Loop V2 — PendingEvaluation 待评估动作队列。

已执行但尚未到达观察期的动作，等待 OutcomeEvaluator 评估。

时间策略:
  - 不预存 due_at (避免时钟漂移导致评估被延迟或提前)
  - 运行时通过 is_due 动态判断是否到期
  - 超过 2 倍观察期仍未拉到数据 → is_expired 自动标记过期

持久化: data/growth_loop/pending_evaluations.jsonl (全量覆盖写)
序列化: to_dict() / from_dict() 双向
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 时间工具
# ──────────────────────────────────────────────


def _now_utc() -> str:
    """当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def parse_utc(iso_str: str) -> datetime:
    """安全解析 UTC ISO 字符串。

    兼容 Python 3.10+:
      - datetime.now(timezone.utc).isoformat() 输出 "2026-08-06T12:34:56.789012+00:00"
      - Python < 3.11 的 fromisoformat() 无法解析 "+00:00" 后缀
      - 此函数确保跨版本兼容

    Args:
        iso_str: UTC ISO 8601 字符串

    Returns:
        带时区的 datetime 对象 (tzinfo=timezone.utc)
    """
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        # 无时区信息 → 假定为 UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ──────────────────────────────────────────────
# PendingEvaluation
# ──────────────────────────────────────────────


@dataclass
class PendingEvaluation:
    """已执行但尚未到达观察期的动作 — 等待 OutcomeEvaluator 评估。

    时间策略:
      - 不预存 due_at (避免时钟漂移导致评估被延迟或提前)
      - 运行时通过 is_due 动态判断是否到期
      - 超过 2 倍观察期仍未拉到数据 → is_expired 自动标记过期

    使用方式:
        # 动作执行成功后创建
        pending = PendingEvaluation.from_action(action, exec_result, pre_metrics)

        # 运行时检查
        if pending.is_due:
            # 拉取 post_metrics → OutcomeEvaluator.evaluate()
            ...
        elif pending.is_expired:
            # 标记过期，移除
            ...
    """

    # ── 全链路追溯 ID ──
    signal_id: str = ""
    diagnosis_id: str = ""
    hypothesis_id: str = ""
    strategy_id: str = ""
    action_id: str = ""

    # ── 执行信息 ──
    creative_id: str = ""
    adset_id: str = ""
    action_type: str = ""               # update_budget / pause_campaign / resume_campaign
    parameters: dict[str, Any] = field(default_factory=dict)

    # ── 执行前指标快照 ──
    pre_metrics: dict[str, float] = field(default_factory=dict)

    # ── 时间窗口 ──
    executed_at: str = ""               # 执行时间 (UTC ISO 字符串)
    observation_window_hours: int = 168 # 观察周期 (7天=168小时)

    # ── 执行结果 ──
    execution_success: bool = True
    actual_budget: float | None = None
    dry_run: bool = False

    # ── 状态 ──
    status: str = "waiting"             # waiting / evaluating / completed / expired

    # ──────────────────────────────────────
    # 运行时计算属性
    # ──────────────────────────────────────

    @property
    def is_due(self) -> bool:
        """运行时动态判断是否到达观察期。

        从 executed_at 计算已过时长，与 observation_window_hours 比较。
        不依赖预计算的绝对时间点，免疫时钟漂移。
        """
        if not self.executed_at:
            return False
        executed = parse_utc(self.executed_at)
        elapsed = datetime.now(timezone.utc) - executed
        return elapsed >= timedelta(hours=self.observation_window_hours)

    @property
    def is_expired(self) -> bool:
        """超过 2 倍观察期仍未拉到数据 → 标记过期。

        防止僵尸记录永久滞留在队列中。
        """
        if not self.executed_at:
            return False
        executed = parse_utc(self.executed_at)
        elapsed = datetime.now(timezone.utc) - executed
        return elapsed >= timedelta(hours=self.observation_window_hours * 2)

    @property
    def elapsed_hours(self) -> float:
        """已过去的小时数 (用于日志和调试)。"""
        if not self.executed_at:
            return 0.0
        executed = parse_utc(self.executed_at)
        elapsed = datetime.now(timezone.utc) - executed
        return round(elapsed.total_seconds() / 3600.0, 2)

    # ──────────────────────────────────────
    # 工厂方法
    # ──────────────────────────────────────

    @classmethod
    def from_action(
        cls,
        action: Any,               # ExecutionAction (避免循环导入用 Any)
        execution_result: Any,     # ExecutionResult (避免循环导入用 Any)
        pre_metrics: dict[str, float],
        observation_window_hours: int = 168,
    ) -> PendingEvaluation:
        """从 ExecutionAction + ExecutionResult 创建待评估记录。

        Args:
            action: ActionPlanner 生成的 ExecutionAction
            execution_result: ActionExecutor 执行后的 ExecutionResult
            pre_metrics: 执行前指标快照 (ROAS, CPI, CTR 等)
            observation_window_hours: 观察周期 (默认 168 小时 = 7 天)

        Returns:
            PendingEvaluation 实例
        """
        return cls(
            signal_id=action.signal_id,
            diagnosis_id=action.diagnosis_id,
            hypothesis_id=action.hypothesis_id,
            strategy_id=action.strategy_id,
            action_id=action.action_id,
            creative_id=action.creative_id,
            adset_id=action.adset_id,
            action_type=action.action_type.value if hasattr(action.action_type, "value") else str(action.action_type),
            parameters=dict(action.parameters),
            pre_metrics=dict(pre_metrics),
            executed_at=execution_result.executed_at or _now_utc(),
            observation_window_hours=observation_window_hours,
            execution_success=execution_result.success,
            actual_budget=execution_result.actual_budget,
            dry_run=execution_result.dry_run,
            status="waiting",
        )

    # ──────────────────────────────────────
    # 序列化 / 反序列化
    # ──────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict (JSON 可序列化)。"""
        return {
            "signal_id": self.signal_id,
            "diagnosis_id": self.diagnosis_id,
            "hypothesis_id": self.hypothesis_id,
            "strategy_id": self.strategy_id,
            "action_id": self.action_id,
            "creative_id": self.creative_id,
            "adset_id": self.adset_id,
            "action_type": self.action_type,
            "parameters": dict(self.parameters),
            "pre_metrics": dict(self.pre_metrics),
            "executed_at": self.executed_at,
            "observation_window_hours": self.observation_window_hours,
            "execution_success": self.execution_success,
            "actual_budget": self.actual_budget,
            "dry_run": self.dry_run,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingEvaluation:
        """从 dict 反序列化。

        忽略未知字段，缺失字段使用默认值。
        """
        known_fields = {
            "signal_id", "diagnosis_id", "hypothesis_id", "strategy_id",
            "action_id", "creative_id", "adset_id", "action_type",
            "parameters", "pre_metrics", "executed_at",
            "observation_window_hours", "execution_success",
            "actual_budget", "dry_run", "status",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    # ──────────────────────────────────────
    # 批量文件 I/O (JSONL)
    # ──────────────────────────────────────

    @staticmethod
    def save_batch(
        pending_list: list[PendingEvaluation],
        path: Path | str,
    ) -> None:
        """全量覆盖写入 JSONL 文件。

        每行一个 JSON 对象，对应一个 PendingEvaluation。

        Args:
            pending_list: 全部待评估记录
            path: pending_evaluations.jsonl 的路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(p.to_dict(), ensure_ascii=False)
            for p in pending_list
        ]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        logger.debug(
            "PendingEvaluation batch saved: %d records to %s",
            len(pending_list), path,
        )

    @staticmethod
    def load_batch(path: Path | str) -> list[PendingEvaluation]:
        """从 JSONL 文件读取全部记录。

        Args:
            path: pending_evaluations.jsonl 的路径

        Returns:
            PendingEvaluation 列表; 文件不存在时返回空列表
        """
        path = Path(path)
        if not path.exists():
            logger.debug("PendingEvaluation file not found: %s", path)
            return []

        results: list[PendingEvaluation] = []
        for line_num, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                results.append(PendingEvaluation.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.error(
                    "Failed to parse PendingEvaluation at %s:%d: %s",
                    path, line_num, exc,
                )
        logger.debug(
            "PendingEvaluation batch loaded: %d records from %s",
            len(results), path,
        )
        return results
