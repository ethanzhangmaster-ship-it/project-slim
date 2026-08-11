"""E11.2.3 — Asset Event Bus。

轻量级事件总线，专为 Asset Binding Pipeline 设计。
遵循 observability/event_bus.py 模式，但更简洁：
  - 字符串 key 订阅（非 Type-based）
  - 同步 publish + 异步 publish_async
  - JSONL 持久化（支持回放）
  - 失败事件重试队列
  - 最大重试次数限制

Usage:
    bus = AssetEventBus(replay_log="data/runtime/asset_events.jsonl")
    bus.subscribe("eagle_asset_discovered", handler)
    bus.publish(event)
    bus.replay()  # 回放失败事件
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from .asset_events import AssetEvent, AssetEventType

# 事件处理器: (event) -> None
EventHandler = Callable[[AssetEvent], None]


class AssetEventBus:
    """资产事件总线。

    支持：
      - 发布/订阅（同步 + 异步）
      - 通配符订阅 "*"
      - JSONL 事件日志持久化
      - 失败事件重试（最多 3 次）
      - 线程安全
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        replay_log: str | Path | None = None,
        failed_log: str | Path | None = None,
        max_workers: int = 4,
    ) -> None:
        # 订阅者: {event_type: [handler]}
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

        # 持久化
        self._replay_log = Path(replay_log) if replay_log else None
        self._failed_log = Path(failed_log) if failed_log else None

        # 异步（懒加载，避免 pytest 收集时创建线程池）
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None

        # 统计
        self._event_counts: dict[str, int] = defaultdict(int)

    # ── Subscribe ─────────────────────────────────────────

    def subscribe(
        self,
        event_type: str | AssetEventType,
        handler: EventHandler,
    ) -> None:
        """订阅事件类型。支持通配符 "*" 订阅所有事件。

        Args:
            event_type: 事件类型 或 "*" (通配符)
            handler:    事件处理器 callable(AssetEvent) -> None
        """
        if isinstance(event_type, AssetEventType):
            event_type = event_type.value

        with self._lock:
            self._subscribers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: str | AssetEventType,
        handler: EventHandler,
    ) -> bool:
        """取消订阅。"""
        if isinstance(event_type, AssetEventType):
            event_type = event_type.value

        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
                return True
        return False

    # ── Publish ───────────────────────────────────────────

    def publish(self, event: AssetEvent) -> None:
        """同步发布事件。

        通知所有订阅者 + 通配符订阅者。
        写入 replay log。
        更新统计。
        """
        self._publish_internal(event, skip_replay_log=False)

    def _publish_internal(self, event: AssetEvent, skip_replay_log: bool = False) -> None:
        """内部发布逻辑。

        Args:
            event:           事件
            skip_replay_log: 是否跳过 replay log 写入（回放时使用）
        """
        event_type = event.event_type.value

        with self._lock:
            exact_handlers = list(self._subscribers.get(event_type, []))
            wildcard_handlers = list(self._subscribers.get("*", []))
            all_handlers = exact_handlers + wildcard_handlers

        # 分发事件
        for handler in all_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[AssetEventBus] Handler error for {event_type}: {e}")

        # 更新统计
        self._event_counts[event_type] += 1

        # 持久化（回放时跳过）
        if not skip_replay_log:
            self._append_replay(event)

    def publish_async(self, event: AssetEvent) -> None:
        """异步发布事件（fire-and-forget）。"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix="asset_evt"
            )
        self._executor.submit(self._publish_safe, event)

    def _publish_safe(self, event: AssetEvent) -> None:
        try:
            self.publish(event)
        except Exception as e:
            print(f"[AssetEventBus] Async publish error: {e}")

    def publish_chain(
        self,
        events: list[AssetEvent],
    ) -> None:
        """按顺序发布事件链（同步）。"""
        for event in events:
            self.publish(event)

    # ── Retry / Failed Events ─────────────────────────────

    def publish_with_retry(self, event: AssetEvent) -> bool:
        """发布事件并处理失败重试。

        如果处理器抛出异常，将事件写入 failed_log 供后续重试。
        超过 MAX_RETRIES 次后放弃。

        Returns:
            True if all handlers succeeded
        """
        event_type = event.event_type.value

        with self._lock:
            exact_handlers = list(self._subscribers.get(event_type, []))
            wildcard_handlers = list(self._subscribers.get("*", []))
            all_handlers = exact_handlers + wildcard_handlers

        all_succeeded = True
        for handler in all_handlers:
            try:
                handler(event)
            except Exception as e:
                all_succeeded = False
                error_msg = f"{type(e).__name__}: {e}"
                failed_event = event.with_error(error_msg)
                self._append_failed(failed_event)
                print(f"[AssetEventBus] Handler failed for {event_type}: {error_msg}")

        if all_succeeded:
            self._event_counts[event_type] += 1
            self._append_replay(event)

        return all_succeeded

    def retry_failed(self) -> int:
        """重试失败事件队列。

        Returns:
            重试成功数量
        """
        if not self._failed_log or not self._failed_log.exists():
            return 0

        retried = 0
        remaining: list[dict[str, Any]] = []

        with open(self._failed_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event = AssetEvent.from_dict(data)

                    if event.retry_count >= self.MAX_RETRIES:
                        # 放弃重试
                        remaining.append(data)
                        continue

                    # 重试
                    retry_event = event.with_retry()
                    if self.publish_with_retry(retry_event):
                        retried += 1
                    else:
                        remaining.append(retry_event.to_dict())

                except Exception as e:
                    print(f"[AssetEventBus] Retry parse error: {e}")
                    remaining.append(data)

        # 重写失败队列
        with open(self._failed_log, "w", encoding="utf-8") as f:
            for entry in remaining:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return retried

    def get_failed_count(self) -> int:
        """获取失败事件数量。"""
        if not self._failed_log or not self._failed_log.exists():
            return 0
        return sum(1 for _ in open(self._failed_log, "r", encoding="utf-8"))

    # ── Replay ────────────────────────────────────────────

    def replay(self, file_path: str | Path | None = None) -> int:
        """回放事件日志。

        注意：回放时不会重新写入 replay log，避免递归。

        Args:
            file_path: 日志文件路径，默认使用 replay_log

        Returns:
            回放的事件数量
        """
        path = Path(file_path) if file_path else self._replay_log
        if path is None or not path.exists():
            return 0

        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event = AssetEvent.from_dict(data)
                    self._publish_internal(event, skip_replay_log=True)
                    count += 1
                except Exception as e:
                    print(f"[AssetEventBus] Replay error: {e}")

        return count

    # ── Query ─────────────────────────────────────────────

    def subscriber_count(self, event_type: str | None = None) -> int:
        with self._lock:
            if event_type is not None:
                return len(self._subscribers.get(event_type, []))
            return sum(len(v) for v in self._subscribers.values())

    def get_stats(self) -> dict[str, Any]:
        """获取事件总线统计。"""
        with self._lock:
            return {
                "total_events": sum(self._event_counts.values()),
                "subscriber_count": sum(len(v) for v in self._subscribers.values()),
                "subscribed_types": len(self._subscribers),
                "events_by_type": dict(self._event_counts),
                "failed_events": self.get_failed_count(),
            }

    def shutdown(self) -> None:
        """关闭事件总线。"""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    # ── Internal ──────────────────────────────────────────

    def _append_replay(self, event: AssetEvent) -> None:
        if self._replay_log is None:
            return
        try:
            self._replay_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._replay_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[AssetEventBus] Replay log error: {e}")

    def _append_failed(self, event: AssetEvent) -> None:
        if self._failed_log is None:
            return
        try:
            self._failed_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._failed_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[AssetEventBus] Failed log error: {e}")

    def __repr__(self) -> str:
        return (
            f"AssetEventBus(subscribers={self.subscriber_count()}, "
            f"events={sum(self._event_counts.values())})"
        )