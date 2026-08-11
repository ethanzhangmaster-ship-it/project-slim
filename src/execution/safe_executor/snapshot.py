"""P2.4.3 Snapshot Layer — 执行前状态快照。

Execution Policy Rule 3：Snapshot 失败 -> BLOCK。
没有「执行前的世界长什么样」，就没有资格改变世界 —— 否则无法回滚。

存储契约：
    JsonlSnapshotStore -> snapshots/{execution_id}.json（每次执行一个文件）
    InMemorySnapshotStore -> 测试 / SIM 默认

Snapshotter：
    调 provider.snapshot_state(request) 获取执行前状态；
    Provider 未实现 / 抛异常 -> SnapshotError（由 executor 转成 BLOCK）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class SnapshotError(RuntimeError):
    """快照获取或落盘失败（Rule 3 -> BLOCK）。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Store Protocol + 实现
# ---------------------------------------------------------------------------


@runtime_checkable
class SnapshotStore(Protocol):
    """快照存储契约。"""

    def save(self, execution_id: str, snapshot: Dict[str, Any]) -> None:
        ...

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        ...


class InMemorySnapshotStore:
    """进程内快照存储。"""

    def __init__(self) -> None:
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def save(self, execution_id: str, snapshot: Dict[str, Any]) -> None:
        self._snapshots[execution_id] = dict(snapshot)

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        snap = self._snapshots.get(execution_id)
        return dict(snap) if snap is not None else None


class JsonlSnapshotStore:
    """每次执行一个 JSON 文件：{snapshot_dir}/{execution_id}.json。"""

    def __init__(self, snapshot_dir: str = "data/execution/snapshots") -> None:
        self.dir = Path(snapshot_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, execution_id: str) -> Path:
        # execution_id 由我们生成（exe_hex），不含路径分隔符；防御性过滤
        safe = "".join(c for c in execution_id if c.isalnum() or c in "_-")
        if not safe:
            raise SnapshotError(f"invalid execution_id for snapshot: {execution_id!r}")
        return self.dir / f"{safe}.json"

    def save(self, execution_id: str, snapshot: Dict[str, Any]) -> None:
        payload = {
            "execution_id": execution_id,
            "captured_at": _now_iso(),
            "snapshot": snapshot,
        }
        try:
            self._path(execution_id).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            raise SnapshotError(f"snapshot save failed: {exc}") from exc

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(execution_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"snapshot load failed: {exc}") from exc
        return payload.get("snapshot")


# ---------------------------------------------------------------------------
# Snapshotter
# ---------------------------------------------------------------------------


class Snapshotter:
    """执行前快照采集器。

    优先调 provider.snapshot_state(request)；Provider 未提供该方法时
    降级为「意图回显快照」（记录目标与动作，供 DRY_RUN / 低风险动作使用）。
    strict=True 时 Provider 缺失 snapshot_state 直接 SnapshotError。
    """

    def __init__(self, store: Optional[SnapshotStore] = None, strict: bool = False):
        self.store = store or InMemorySnapshotStore()
        self.strict = strict

    def take(self, provider: Any, request: Any, execution_id: str) -> Dict[str, Any]:
        """采集并落盘快照；任何失败抛 SnapshotError（Rule 3）。"""
        snapshot = self._capture(provider, request)
        try:
            self.store.save(execution_id, snapshot)
        except SnapshotError:
            raise
        except Exception as exc:  # noqa: BLE001 — 落盘失败必须 BLOCK
            raise SnapshotError(f"snapshot persist failed: {exc}") from exc
        return snapshot

    # ------------------------------------------------------------------

    def _capture(self, provider: Any, request: Any) -> Dict[str, Any]:
        fn = getattr(provider, "snapshot_state", None)
        if callable(fn):
            try:
                snapshot = fn(request)
            except Exception as exc:  # noqa: BLE001 — 采集失败必须 BLOCK
                raise SnapshotError(
                    f"provider.snapshot_state failed: {type(exc).__name__}: {exc}"
                ) from exc
            if not isinstance(snapshot, dict):
                raise SnapshotError(
                    f"provider.snapshot_state returned non-dict: {type(snapshot).__name__}"
                )
            return snapshot

        if self.strict:
            raise SnapshotError(
                f"provider {getattr(provider, 'provider_id', '?')} "
                "does not implement snapshot_state (strict mode)"
            )

        # 降级：意图回显快照
        intent = getattr(request, "intent", None)
        return {
            "fallback": True,
            "provider": getattr(provider, "provider_id", ""),
            "target_id": getattr(intent, "target_id", ""),
            "action": str(getattr(getattr(intent, "action", ""), "value",
                              getattr(intent, "action", ""))),
            "captured_at": _now_iso(),
        }


__all__ = [
    "SnapshotError",
    "SnapshotStore",
    "InMemorySnapshotStore",
    "JsonlSnapshotStore",
    "Snapshotter",
]
