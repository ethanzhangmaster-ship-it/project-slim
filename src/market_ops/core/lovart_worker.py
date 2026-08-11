"""Phase 2.1.1: Lovart Worker — strict state machine, observability via Event Bus.

Each worker:
  1. fetch: queue.claim() → PENDING → CLAIM
  2. start: queue.start_processing() → CLAIM → PROCESSING
  3. generate: Lovart API call
  4. download + validate
  5. finish: queue.complete() → SUCCESS or queue.fail() → RETRY/FAILED

Phase 2.2A: Publishes events to Event Bus (WorkerRegistered, WorkerHeartbeat,
TaskStarted, TaskFinished, TaskFailed). Observers subscribe independently.
Worker has NO direct dependency on any monitoring module.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .generation_store import GenerationStore
from .lovart_queue import LovartQueue
from ..lovart_adapter import LovartAPIAdapter
from ..image_validator import ImageValidator

if TYPE_CHECKING:
    from ..observability.event_bus import EventBus


class LovartWorker:
    """A single worker that processes generation tasks with strict state machine.

    Observability: publishes events to optional EventBus. Zero coupling to monitors.
    """

    def __init__(
        self,
        worker_id: str,
        queue: LovartQueue,
        adapter: LovartAPIAdapter,
        store: GenerationStore,
        validator: ImageValidator,
        output_dir: Path,
        timeout: int = 60,
        event_bus: Any = None,  # EventBus | None
    ) -> None:
        self.worker_id = worker_id
        self._queue = queue
        self._adapter = adapter
        self._store = store
        self._validator = validator
        self._output_dir = output_dir
        self._timeout = timeout
        self._running = False
        self._thread: threading.Thread | None = None
        self._bus = event_bus

        self._output_dir.mkdir(parents=True, exist_ok=True)

        if self._bus:
            from ..observability.events import WorkerRegistered
            self._bus.publish(WorkerRegistered(worker_id=self.worker_id))

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the worker in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name=self.worker_id)
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop after current task."""
        self._running = False

    def _run_loop(self) -> None:
        """Main worker loop: claim → start_processing → process → repeat."""
        while self._running:
            self._queue.re_queue_all_ready()

            task = self._queue.claim(self.worker_id)
            if task is None:
                self._publish_heartbeat(status="IDLE")
                time.sleep(1)
                continue

            task_id = task["id"]
            self._publish_heartbeat(status="RUNNING", current_task=task_id)

            if not self._queue.start_processing(task_id, self.worker_id):
                self._publish_heartbeat(
                    status="IDLE",
                    last_error=f"Failed to start processing {task_id}",
                )
                print(f"  [Worker {self.worker_id}] Failed to start processing {task_id}")
                continue

            self._process_task(task)

    def _process_task(self, task: dict[str, Any]) -> None:
        """Process a single task: generate → download → validate → complete/fail."""
        task_id = task["id"]
        creative_id = task.get("creative_id", "")
        t0 = time.time()

        if self._bus:
            from ..observability.events import TaskStarted
            self._bus.publish(TaskStarted(
                task_id=task_id, worker_id=self.worker_id, creative_id=creative_id,
            ))

        result = self._adapter.generate(
            prompt=task["prompt"],
            negative_prompt=task.get("negative_prompt", ""),
            size=task.get("format", "1080x1080"),
        )

        if not result.success:
            print(f"  [Worker {self.worker_id}] API FAIL {task_id}: {result.error}")
            final_status = self._queue.fail(task_id, result.error, retry=True)
            print(f"  [Worker {self.worker_id}] → {final_status}")
            self._publish_task_failed(task_id, creative_id, result.error, final_status)
            return

        image_path = self._download_image(result.image_url, task_id)
        if not image_path:
            final_status = self._queue.fail(task_id, "Failed to download image", retry=True)
            print(f"  [Worker {self.worker_id}] DOWNLOAD FAIL {task_id} → {final_status}")
            self._publish_task_failed(task_id, creative_id, "Failed to download image", final_status)
            return

        validation = self._validator.validate(image_path)
        if not validation.valid:
            err = f"Image validation failed: {'; '.join(validation.errors)}"
            final_status = self._queue.fail(task_id, err, retry=True)
            print(f"  [Worker {self.worker_id}] VALIDATION FAIL {task_id} → {final_status}")
            self._publish_task_failed(task_id, creative_id, err, final_status)
            return

        elapsed = time.time() - t0
        self._queue.complete(
            task_id=task_id,
            image_path=image_path,
            image_url=result.image_url,
            generation_time=elapsed,
            cost=result.cost,
            model=result.model,
            quality_score=0,
        )
        print(f"  [Worker {self.worker_id}] SUCCESS {task_id} "
              f"({elapsed:.1f}s, {result.cost:.2f} credits)")

        if self._bus:
            from ..observability.events import TaskFinished
            self._bus.publish(TaskFinished(
                task_id=task_id, worker_id=self.worker_id, creative_id=creative_id,
                generation_time=elapsed, cost=result.cost, image_path=image_path,
            ))

    def _download_image(self, url: str, task_id: str) -> str:
        """Download image from URL to output directory. Returns file path or empty string."""
        import requests as _requests

        try:
            resp = _requests.get(url, timeout=30, stream=True)
            resp.raise_for_status()

            ct = resp.headers.get("content-type", "")
            if "png" in ct:
                ext = ".png"
            elif "jpeg" in ct or "jpg" in ct:
                ext = ".jpg"
            elif "webp" in ct:
                ext = ".webp"
            else:
                ext = ".png"

            file_path = self._output_dir / f"{task_id}{ext}"
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(file_path)
        except Exception as e:
            print(f"  [Worker {self.worker_id}] Download error: {e}")
            return ""

    def _publish_heartbeat(self, status: str, current_task: str = "",
                           last_error: str = "") -> None:
        if self._bus:
            from ..observability.events import WorkerHeartbeat
            self._bus.publish(WorkerHeartbeat(
                worker_id=self.worker_id, status=status,
                current_task=current_task, last_error=last_error,
            ))

    def _publish_task_failed(self, task_id: str, creative_id: str,
                             error: str, final_status: str) -> None:
        if self._bus:
            from ..observability.events import TaskFailed
            self._bus.publish(TaskFailed(
                task_id=task_id, worker_id=self.worker_id,
                creative_id=creative_id, error=error,
                final_status=final_status,
            ))


class WorkerPool:
    """Manages a pool of concurrent LovartWorkers."""

    def __init__(
        self,
        queue: LovartQueue,
        adapter: LovartAPIAdapter,
        store: GenerationStore,
        output_dir: Path,
        num_workers: int = 3,
        timeout: int = 60,
        event_bus: Any = None,
    ) -> None:
        self.queue = queue
        self.adapter = adapter
        self.store = store
        self.output_dir = output_dir
        self.num_workers = num_workers
        self.timeout = timeout
        self.validator = ImageValidator()
        self._bus = event_bus
        self._workers: list[LovartWorker] = []

    def start(self) -> None:
        """Start all workers."""
        for i in range(self.num_workers):
            worker = LovartWorker(
                worker_id=f"worker_{i+1:02d}",
                queue=self.queue,
                adapter=self.adapter,
                store=self.store,
                validator=self.validator,
                output_dir=self.output_dir / f"w{i+1:02d}",
                timeout=self.timeout,
                event_bus=self._bus,
            )
            worker.start()
            self._workers.append(worker)
        print(f"[WorkerPool] Started {self.num_workers} workers")

    def stop(self) -> None:
        """Stop all workers."""
        for w in self._workers:
            w.stop()
        print(f"[WorkerPool] Stopped {len(self._workers)} workers")

    def wait_idle(self, poll_interval: float = 2.0, max_wait: float = 600) -> bool:
        """Wait until all tasks are done (no PENDING/CLAIM/PROCESSING/RETRY)."""
        elapsed = 0.0
        while elapsed < max_wait:
            stats = self.store.get_stats()
            active = (stats["pending_count"] + stats.get("claim_count", 0) +
                      stats["processing_count"] + stats.get("retry_count", 0))
            if active == 0:
                return True
            time.sleep(poll_interval)
            elapsed += poll_interval
        return False

    @property
    def all_idle(self) -> bool:
        stats = self.store.get_stats()
        active = (stats["pending_count"] + stats.get("claim_count", 0) +
                  stats["processing_count"] + stats.get("retry_count", 0))
        return active == 0