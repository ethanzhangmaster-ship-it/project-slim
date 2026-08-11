import sys, traceback, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from market_ops.core.generation_store import GenerationStore
from market_ops.observability.observability_store import ObservabilityStore
from market_ops.observability.event_bus import EventBus
from market_ops.observability.events import WorkerRegistered, WorkerHeartbeat, TaskFinished, TaskFailed
from market_ops.observability.observers.worker_observer import WorkerObserver
from market_ops.observability.observers.latency_observer import LatencyObserver
from market_ops.observability.observers.queue_observer import QueueObserver
from market_ops.observability.observers.snapshot_observer import SnapshotObserver
from market_ops.observability.registry import ObserverRegistry
import tempfile, uuid, time, os

def _make_core_db():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="core_")
    os.close(fd)
    return GenerationStore(db_path=path)

def _make_obs_db():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="obs_")
    os.close(fd)
    return ObservabilityStore(db_path=path)

def _insert(core, creative_id, prompt="test prompt"):
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    core.insert({"id": task_id, "creative_id": creative_id, "prompt": prompt, "priority": "normal", "format": "1080x1080", "dna_source": "test", "batch_id": "batch_001"})
    return task_id

def _complete_task(core, task_id, generation_time=3.5, worker_id="test_worker"):
    core.claim_task(task_id, worker_id)
    core.start_processing(task_id, worker_id)
    core.update_status(task_id, "SUCCESS", generation_time=generation_time, cost=0.05)

core, obs = _make_core_db(), _make_obs_db()
bus = EventBus()

# Manual subscribe (no registry)
wo = WorkerObserver(store=obs, bus=bus)
lo = LatencyObserver(core_store=core, obs_store=obs, bus=bus)

task_ids = [_insert(core, f"c_int_{i}", f"integration {i}") for i in range(3)]

bus.publish(WorkerRegistered(worker_id="worker_01"))
print("After register:", wo.get_all())

bus.publish(WorkerHeartbeat(worker_id="worker_01", status="RUNNING", current_task=task_ids[0]))
print("After heartbeat:", wo.get_all())

_complete_task(core, task_ids[0], generation_time=4.2)
bus.publish(TaskFinished(task_id=task_ids[0], worker_id="worker_01", creative_id="c_int_0", generation_time=4.2, cost=0.05))
print("After TaskFinished:", wo.get_all())

bus.publish(TaskFailed(task_id=task_ids[1], worker_id="worker_01", creative_id="c_int_1", error="timeout", final_status="RETRY"))
print("After TaskFailed:", wo.get_all())

print("Tasks completed:", wo.get_all()[0]["tasks_completed"])
print("Tasks failed:", wo.get_all()[0]["tasks_failed"])