"""跨 Agent 冲突检测器 — 多 Agent 同时修改同一游戏数值时检测冲突并告警.

设计原则 (来自 PHASE3_PLAN.md):
  - 冲突检测基于 version 字段, 不引入分布式锁
  - 乐观并发控制 (Optimistic Concurrency Control)
  - 检测到冲突时告警, 由人工或编排层决定如何解决

冲突场景:
  1. 版本冲突: Agent A 基于版本 v1 修改, 但 Agent B 已经将版本推进到 v2
  2. 参数冲突: 两个 Agent 对同一指标的调优方向矛盾 (如 +50% vs -20%)
  3. 并发冲突: 时间窗口内同一 game_id + metric 被多个 Agent 同时修改

数据结构:
  游戏数值版本表: {game_id: {metric: MetricVersion}}
    MetricVersion: {version, current_value, last_modified_by, last_modified_at, source_event}

  冲突记录: JSONL 持久化到 data/collaboration/conflicts.jsonl

用法:
    from .conflict_detector import get_conflict_detector

    detector = get_conflict_detector(data_dir="data")

    # Agent 发起修改前检查冲突
    conflict = detector.check_before_modify(
        game_id="merge_game_001",
        metric="retention_d1",
        agent_id="numerical_designer",
        proposed_value=0.45,
        base_version=1,  # Agent 基于的版本
    )
    if conflict:
        # 有冲突, 告警或拒绝
        ...

    # Agent 完成修改后注册变更
    detector.register_change(
        game_id="merge_game_001",
        metric="retention_d1",
        agent_id="numerical_designer",
        new_value=0.45,
        base_version=1,
    )

    # 扫描最近的协同记录检测参数冲突
    conflicts = detector.scan_recent_conflicts(window_hours=24)
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    """解析 ISO 时间字符串 (容错)."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


@dataclass
class MetricVersion:
    """游戏数值指标的版本记录."""
    version: int = 1
    current_value: float = 0.0
    last_modified_by: str = ""
    last_modified_at: str = ""
    source_event: str = ""  # 触发修改的事件类型

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "current_value": self.current_value,
            "last_modified_by": self.last_modified_by,
            "last_modified_at": self.last_modified_at,
            "source_event": self.source_event,
        }


@dataclass
class Conflict:
    """检测到的冲突."""
    conflict_id: str = ""
    conflict_type: str = ""  # version | parameter | concurrent
    game_id: str = ""
    metric: str = ""
    severity: str = "warning"  # warning | critical
    description: str = ""
    agent_a: str = ""
    agent_b: str = ""
    value_a: float = 0.0
    value_b: float = 0.0
    version_a: int = 0
    version_b: int = 0
    detected_at: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "game_id": self.game_id,
            "metric": self.metric,
            "severity": self.severity,
            "description": self.description,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "detected_at": self.detected_at,
            "suggestion": self.suggestion,
        }


# ── 默认配置 ─────────────────────────────────────────────────

# 并发冲突时间窗口 (秒): 同一指标在此窗口内被多个 Agent 修改视为并发冲突
DEFAULT_CONCURRENT_WINDOW_SECONDS = 300  # 5 分钟

# 参数冲突阈值: 两个建议的调整方向相反且差异超过此阈值
DEFAULT_PARAMETER_CONFLICT_THRESHOLD = 0.10  # 10%


class ConflictDetector:
    """跨 Agent 冲突检测器 — 基于版本号的乐观并发控制.

    线程安全: 内部锁保护版本表.
    """

    def __init__(
        self,
        data_dir: str = "data",
        concurrent_window_seconds: int = DEFAULT_CONCURRENT_WINDOW_SECONDS,
        parameter_conflict_threshold: float = DEFAULT_PARAMETER_CONFLICT_THRESHOLD,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._version_table: dict[str, dict[str, MetricVersion]] = {}
        self._conflicts_path = self.data_dir / "collaboration" / "conflicts.jsonl"
        self._concurrent_window = concurrent_window_seconds
        self._param_threshold = parameter_conflict_threshold
        self._lock = threading.Lock()

    # ── 版本管理 ─────────────────────────────────────────────

    def _get_metric_version(self, game_id: str, metric: str) -> MetricVersion:
        """获取指标的当前版本 (不存在则返回默认 v1)."""
        return self._version_table.get(game_id, {}).get(metric, MetricVersion())

    def _set_metric_version(self, game_id: str, metric: str, version: MetricVersion) -> None:
        """设置指标版本."""
        if game_id not in self._version_table:
            self._version_table[game_id] = {}
        self._version_table[game_id][metric] = version

    def get_version(self, game_id: str, metric: str) -> dict[str, Any]:
        """查询指标的当前版本 (公开接口)."""
        with self._lock:
            return self._get_metric_version(game_id, metric).to_dict()

    def get_all_versions(self, game_id: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
        """查询所有游戏的版本表 (用于调试/API)."""
        with self._lock:
            if game_id:
                return {
                    game_id: {
                        m: v.to_dict()
                        for m, v in self._version_table.get(game_id, {}).items()
                    }
                }
            return {
                g: {m: v.to_dict() for m, v in metrics.items()}
                for g, metrics in self._version_table.items()
            }

    # ── 冲突检测 ─────────────────────────────────────────────

    def check_before_modify(
        self,
        game_id: str,
        metric: str,
        agent_id: str,
        proposed_value: float,
        base_version: int,
        source_event: str = "",
    ) -> Conflict | None:
        """Agent 发起修改前检查冲突.

        乐观并发控制: Agent 持有 base_version, 与当前版本对比.

        Args:
            game_id: 游戏 ID
            metric: 目标指标 (如 retention_d1, arpu)
            agent_id: 发起修改的 Agent ID
            proposed_value: 建议的新值
            base_version: Agent 基于的版本号
            source_event: 触发修改的事件类型

        Returns:
            Conflict 对象 (有冲突) 或 None (无冲突)
        """
        with self._lock:
            current = self._get_metric_version(game_id, metric)

            # 场景 1: 版本冲突 — Agent 基于的版本落后于当前版本
            if base_version < current.version:
                conflict = Conflict(
                    conflict_id=f"conflict-{uuid.uuid4().hex[:12]}",
                    conflict_type="version",
                    game_id=game_id,
                    metric=metric,
                    severity="critical",
                    description=(
                        f"版本冲突: {agent_id} 基于版本 v{base_version} 修改, "
                        f"但当前版本已为 v{current.version} (由 {current.last_modified_by} 修改)"
                    ),
                    agent_a=agent_id,
                    agent_b=current.last_modified_by,
                    value_a=proposed_value,
                    value_b=current.current_value,
                    version_a=base_version,
                    version_b=current.version,
                    detected_at=_now_iso(),
                    suggestion=(
                        f"基于最新版本 v{current.version} 重新计算调优建议 "
                        f"(当前值: {current.current_value})"
                    ),
                )
                self._persist_conflict(conflict)
                logger.warning("ConflictDetector: %s", conflict.description)
                return conflict

            # 场景 2: 并发冲突 — 时间窗口内同一指标被多个 Agent 修改
            if current.last_modified_by and current.last_modified_by != agent_id:
                last_modified_at = _parse_iso(current.last_modified_at)
                now = datetime.now(timezone.utc)
                if (now - last_modified_at).total_seconds() < self._concurrent_window:
                    conflict = Conflict(
                        conflict_id=f"conflict-{uuid.uuid4().hex[:12]}",
                        conflict_type="concurrent",
                        game_id=game_id,
                        metric=metric,
                        severity="warning",
                        description=(
                            f"并发冲突: {agent_id} 修改 {metric}, "
                            f"但 {current.last_modified_by} 在 "
                            f"{self._concurrent_window}秒内已修改此指标"
                        ),
                        agent_a=agent_id,
                        agent_b=current.last_modified_by,
                        value_a=proposed_value,
                        value_b=current.current_value,
                        version_a=base_version,
                        version_b=current.version,
                        detected_at=_now_iso(),
                        suggestion="建议串行化修改或协调 Agent 间的调优策略",
                    )
                    self._persist_conflict(conflict)
                    logger.warning("ConflictDetector: %s", conflict.description)
                    return conflict

            return None

    def register_change(
        self,
        game_id: str,
        metric: str,
        agent_id: str,
        new_value: float,
        base_version: int,
        source_event: str = "",
    ) -> MetricVersion:
        """Agent 完成修改后注册变更 (推进版本号).

        Args:
            game_id: 游戏 ID
            metric: 目标指标
            agent_id: 完成修改的 Agent ID
            new_value: 修改后的新值
            base_version: Agent 基于的版本号 (新版本 = base_version + 1)
            source_event: 触发修改的事件类型

        Returns:
            更新后的 MetricVersion
        """
        with self._lock:
            new_version = MetricVersion(
                version=base_version + 1,
                current_value=new_value,
                last_modified_by=agent_id,
                last_modified_at=_now_iso(),
                source_event=source_event,
            )
            self._set_metric_version(game_id, metric, new_version)
            logger.info(
                "ConflictDetector: registered change game=%s metric=%s v%d by %s",
                game_id, metric, new_version.version, agent_id,
            )
            return new_version

    def detect_parameter_conflict(
        self,
        game_id: str,
        metric: str,
        recommendations: list[dict[str, Any]],
    ) -> list[Conflict]:
        """检测多个调优建议间的参数冲突.

        场景: 两个 Agent 对同一指标给出方向相反的调优建议
              (如 A 建议 +50%, B 建议 -20%)

        Args:
            game_id: 游戏 ID
            metric: 目标指标
            recommendations: 调优建议列表 (含 agent_id, suggested_param, current_param, adjustment_pct)

        Returns:
            冲突列表 (可能多条)
        """
        conflicts: list[Conflict] = []
        if len(recommendations) < 2:
            return conflicts

        with self._lock:
            # 两两对比调优建议
            for i in range(len(recommendations)):
                for j in range(i + 1, len(recommendations)):
                    rec_a = recommendations[i]
                    rec_b = recommendations[j]
                    adj_a = rec_a.get("adjustment_pct", 0.0)
                    adj_b = rec_b.get("adjustment_pct", 0.0)

                    # 方向相反且差异超过阈值
                    if (adj_a * adj_b < 0) and abs(adj_a - adj_b) > self._param_threshold * 100:
                        conflict = Conflict(
                            conflict_id=f"conflict-{uuid.uuid4().hex[:12]}",
                            conflict_type="parameter",
                            game_id=game_id,
                            metric=metric,
                            severity="warning",
                            description=(
                                f"参数冲突: {rec_a.get('agent_id', 'A')} 建议 {adj_a:+.1f}%, "
                                f"{rec_b.get('agent_id', 'B')} 建议 {adj_b:+.1f}% "
                                f"(方向相反)"
                            ),
                            agent_a=rec_a.get("agent_id", "agent_a"),
                            agent_b=rec_b.get("agent_id", "agent_b"),
                            value_a=rec_a.get("suggested_param", 0.0),
                            value_b=rec_b.get("suggested_param", 0.0),
                            version_a=0,
                            version_b=0,
                            detected_at=_now_iso(),
                            suggestion="人工审核: 两个 Agent 对同一指标的调优方向矛盾",
                        )
                        conflicts.append(conflict)
                        self._persist_conflict(conflict)
                        logger.warning("ConflictDetector: %s", conflict.description)

        return conflicts

    def scan_recent_conflicts(self, window_hours: int = 24) -> list[dict[str, Any]]:
        """扫描最近时间窗口内的冲突记录.

        Args:
            window_hours: 时间窗口 (小时)

        Returns:
            冲突记录列表
        """
        if not self._conflicts_path.exists():
            return []
        try:
            text = self._conflicts_path.read_text(encoding="utf-8")
        except OSError:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                detected_at = _parse_iso(rec.get("detected_at", ""))
                if detected_at >= cutoff:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
        return records

    # ── 持久化 ───────────────────────────────────────────────

    def _persist_conflict(self, conflict: Conflict) -> None:
        """持久化冲突记录到 JSONL."""
        self._conflicts_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conflicts_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(conflict.to_dict(), ensure_ascii=False) + "\n")

    # ── 查询 API ─────────────────────────────────────────────

    def list_conflicts(
        self,
        game_id: str | None = None,
        conflict_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询冲突记录列表."""
        if not self._conflicts_path.exists():
            return []
        try:
            text = self._conflicts_path.read_text(encoding="utf-8")
        except OSError:
            return []
        lines = [l for l in text.splitlines() if l.strip()]
        records: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                rec = json.loads(line)
                if game_id and rec.get("game_id") != game_id:
                    continue
                if conflict_type and rec.get("conflict_type") != conflict_type:
                    continue
                records.append(rec)
            except json.JSONDecodeError:
                continue
        return records

    def get_conflict(self, conflict_id: str) -> dict[str, Any] | None:
        """查询单条冲突记录."""
        if not self._conflicts_path.exists():
            return None
        try:
            text = self._conflicts_path.read_text(encoding="utf-8")
        except OSError:
            return None
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if rec.get("conflict_id") == conflict_id:
                    return rec
            except json.JSONDecodeError:
                continue
        return None

    def get_stats(self) -> dict[str, Any]:
        """冲突统计."""
        all_conflicts = self.list_conflicts(limit=10000)
        type_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        game_counts: dict[str, int] = {}
        for c in all_conflicts:
            ct = c.get("conflict_type", "unknown")
            sv = c.get("severity", "unknown")
            gid = c.get("game_id", "unknown")
            type_counts[ct] = type_counts.get(ct, 0) + 1
            severity_counts[sv] = severity_counts.get(sv, 0) + 1
            game_counts[gid] = game_counts.get(gid, 0) + 1

        # 统计版本表中的监控指标数
        total_metrics = sum(len(metrics) for metrics in self._version_table.values())

        return {
            "total_conflicts": len(all_conflicts),
            "type_counts": type_counts,
            "severity_counts": severity_counts,
            "game_counts": game_counts,
            "tracked_games": len(self._version_table),
            "tracked_metrics": total_metrics,
            "concurrent_window_seconds": self._concurrent_window,
            "parameter_conflict_threshold": self._param_threshold,
            "last_conflict_at": all_conflicts[-1]["detected_at"] if all_conflicts else None,
        }

    def reset(self) -> None:
        """重置版本表 (不删除历史冲突记录)."""
        with self._lock:
            self._version_table.clear()


# ── 模块级单例 ──────────────────────────────────────────────

_default_detector: ConflictDetector | None = None
_default_detector_lock = threading.Lock()


def get_conflict_detector(
    data_dir: str | None = None,
    force: bool = False,
) -> ConflictDetector:
    """获取默认的 ConflictDetector 单例.

    Args:
        data_dir: 数据目录 (仅首次调用有效)
        force: True 则重新初始化 (用于测试)
    """
    global _default_detector
    with _default_detector_lock:
        if _default_detector is None or force:
            if data_dir is None:
                # 推断项目根目录
                cwd = Path.cwd()
                root = cwd
                for parent in [cwd] + list(cwd.parents):
                    if (parent / "src" / "market_ops").exists():
                        root = parent
                        break
                data_dir = str(root / "data")
            _default_detector = ConflictDetector(data_dir=data_dir)
        return _default_detector


def reset_conflict_detector() -> None:
    """重置单例 (用于测试)."""
    global _default_detector
    with _default_detector_lock:
        _default_detector = None
