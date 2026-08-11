"""P2.4.2 Idempotency Layer — 幂等键与重复执行防护。

真实执行环境的第一工程风险：同一个动作被执行两次
（重试 / 崩溃恢复 / 并发调度都会造成）。

幂等键：
    key = sha256(action | target | canonical(parameters) | date_window)

状态行为（用户契约）：
    不存在        -> ALLOW           允许执行
    RUNNING       -> REJECT_RUNNING  拒绝重复执行（Rule 2 -> BLOCK）
    SUCCESS       -> RETURN_EXISTING 返回历史结果，不再触碰外部系统
    FAILED        -> ALLOW_RETRY     允许重试
    ROLLED_BACK   -> BLOCK_ROLLED_BACK 禁止自动重试（需人工确认）
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

# 幂等记录状态
IDEM_RUNNING = "RUNNING"
IDEM_SUCCESS = "SUCCESS"
IDEM_FAILED = "FAILED"
IDEM_ROLLED_BACK = "ROLLED_BACK"

VALID_IDEM_STATUSES = (IDEM_RUNNING, IDEM_SUCCESS, IDEM_FAILED, IDEM_ROLLED_BACK)

# 幂等裁决
VERDICT_ALLOW = "ALLOW"
VERDICT_REJECT_RUNNING = "REJECT_RUNNING"
VERDICT_RETURN_EXISTING = "RETURN_EXISTING"
VERDICT_ALLOW_RETRY = "ALLOW_RETRY"
VERDICT_BLOCK_ROLLED_BACK = "BLOCK_ROLLED_BACK"

# 裁决 -> 是否允许执行
_ALLOWING_VERDICTS = (VERDICT_ALLOW, VERDICT_ALLOW_RETRY)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_str(value: Any) -> str:
    return str(getattr(value, "value", value))


def _canonical(parameters: Optional[Dict[str, Any]]) -> str:
    """参数字典 -> 稳定 JSON（键排序，str-Enum 归一化）。"""
    if not parameters:
        return "{}"

    def normalize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): normalize(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [normalize(v) for v in obj]
        if hasattr(obj, "value"):
            return obj.value
        return obj

    return json.dumps(normalize(parameters), sort_keys=True, ensure_ascii=False)


def make_idempotency_key(
    action: Any,
    target: str,
    parameters: Optional[Dict[str, Any]] = None,
    date_window: str = "",
) -> str:
    """构造幂等键：hash(action, target, parameters, date_window)。

    date_window 默认取当天 UTC 日期 —— 同一天内同 action+target+params
    视为同一次执行；跨天允许重新执行。
    """
    window = date_window or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = "|".join([_as_str(action), str(target), _canonical(parameters), window])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# IdempotencyRecord
# ---------------------------------------------------------------------------


@dataclass
class IdempotencyRecord:
    """一条幂等记录：key -> 最近一次执行的状态与结果。"""

    key: str
    execution_id: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at
        if self.status not in VALID_IDEM_STATUSES:
            raise ValueError(f"invalid idempotency status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "execution_id": self.execution_id,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdempotencyRecord":
        return cls(
            key=str(data.get("key", "")),
            execution_id=str(data.get("execution_id", "")),
            status=str(data.get("status", IDEM_RUNNING)),
            result=data.get("result") or {},
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


# ---------------------------------------------------------------------------
# Store Protocol + 实现
# ---------------------------------------------------------------------------


@runtime_checkable
class ExecutionIdempotencyStore(Protocol):
    """幂等存储契约。"""

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        ...

    def put(self, record: IdempotencyRecord) -> None:
        ...


class InMemoryIdempotencyStore:
    """进程内幂等存储（测试 / SIM 默认）。"""

    def __init__(self) -> None:
        self._records: Dict[str, IdempotencyRecord] = {}

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        return self._records.get(key)

    def put(self, record: IdempotencyRecord) -> None:
        record.updated_at = _now_iso()
        self._records[record.key] = record


class JsonlIdempotencyStore:
    """EP0 风格：append-only JSONL，读取时 last-wins。"""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        latest: Optional[IdempotencyRecord] = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("key") == key:
                latest = IdempotencyRecord.from_dict(data)
        return latest

    def put(self, record: IdempotencyRecord) -> None:
        record.updated_at = _now_iso()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 幂等裁决
# ---------------------------------------------------------------------------


def check_idempotency(
    store: ExecutionIdempotencyStore, key: str
) -> Tuple[str, Optional[IdempotencyRecord]]:
    """按状态行为表裁决：返回 (verdict, existing_record)。"""
    record = store.get(key)
    if record is None:
        return VERDICT_ALLOW, None
    if record.status == IDEM_RUNNING:
        return VERDICT_REJECT_RUNNING, record
    if record.status == IDEM_SUCCESS:
        return VERDICT_RETURN_EXISTING, record
    if record.status == IDEM_FAILED:
        return VERDICT_ALLOW_RETRY, record
    # ROLLED_BACK：禁止自动重试
    return VERDICT_BLOCK_ROLLED_BACK, record


def verdict_allows_execution(verdict: str) -> bool:
    return verdict in _ALLOWING_VERDICTS


__all__ = [
    "IDEM_RUNNING",
    "IDEM_SUCCESS",
    "IDEM_FAILED",
    "IDEM_ROLLED_BACK",
    "VALID_IDEM_STATUSES",
    "VERDICT_ALLOW",
    "VERDICT_REJECT_RUNNING",
    "VERDICT_RETURN_EXISTING",
    "VERDICT_ALLOW_RETRY",
    "VERDICT_BLOCK_ROLLED_BACK",
    "make_idempotency_key",
    "IdempotencyRecord",
    "ExecutionIdempotencyStore",
    "InMemoryIdempotencyStore",
    "JsonlIdempotencyStore",
    "check_idempotency",
    "verdict_allows_execution",
]
