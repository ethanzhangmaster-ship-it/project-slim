"""V4.4 Production Runtime — 24/7 execution layer.

This layer does NOT enhance AI capabilities. It makes the entire Creative Brain
run as a stable, production-grade system.

Modules (26 total):
  Core Runtime:
  - RuntimeEngine: Unified orchestrator
  - RuntimeAPI: Unified control API (Run/Pause/Resume/Cancel/Status)
  - Scheduler: Cron/Interval/Event scheduling
  - WorkflowEngine: DAG-based workflow execution (supports OnErrorPolicy)
  - TaskQueue: Priority-based task queue
  - WorkerPool: CPU/GPU/IO worker management
  - ResourceManager: CPU/GPU/Memory/Disk allocation
  - CacheManager: LRU cache with TTL
  - DependencyGraph: Auto-dependency resolution

  Reliability:
  - RetryManager: Exponential backoff retry
  - RollbackManager: Automatic rollback on failure
  - CheckpointManager: Save/resume execution state

  State & Events:
  - StateManager: Workflow/Task state machine
  - EventBus: Decoupled publish/subscribe

  Coordination:
  - LockManager: Distributed lock (prevent concurrent conflicts)
  - RateLimiter: API rate limiting (Facebook, Google, OpenAI)

  Observability:
  - HealthMonitor: Real-time service health
  - MetricsCollector: Performance metrics (latency/TPS/queue)
  - AlertManager: Multi-channel alerting (Slack/Email/企业微信)

  Infrastructure:
  - ServiceRegistry: Service registration and discovery
  - PluginManager: Hot-swappable plugin system
  - ConfigManager: Unified configuration (YAML/JSON/ENV)
  - Logger: Structured logging

  AI Asset Management:
  - ArtifactManager: AI asset lifecycle (creative, prompt, embedding, model)
  - SecretManager: Secure credential management (FB Token, OpenAI Key)
"""

from .schemas import (
    # Enums
    TaskStatus,
    TaskPriority,
    WorkerType,
    WorkerStatus,
    ResourceType,
    HealthStatus,
    AlertLevel,
    ScheduleType,
    WorkflowState,
    OnErrorPolicy,
    ArtifactType,
    ArtifactStatus,
    SecretLevel,
    # Schemas
    RuntimeTask,
    Worker,
    ResourceState,
    HealthReport,
    RuntimeMetrics,
    Alert,
    Checkpoint,
    WorkflowNode,
    WorkflowDAG,
    RuntimeReport,
    WorkflowStateData,
    RuntimeEvent,
    DistributedLock,
    Artifact,
    Secret,
)

from .config_manager import ConfigManager
from .logger import Logger
from .task_queue import TaskQueue
from .worker_pool import WorkerPool
from .cache_manager import CacheManager
from .dependency_graph import DependencyGraph
from .retry_manager import RetryManager
from .rollback_manager import RollbackManager
from .checkpoint_manager import CheckpointManager
from .resource_manager import ResourceManager
from .health_monitor import HealthMonitor
from .metrics_collector import MetricsCollector
from .alert_manager import AlertManager
from .service_registry import ServiceRegistry
from .plugin_manager import PluginManager
from .scheduler import Scheduler
from .workflow_engine import WorkflowEngine
from .runtime_api import RuntimeAPI
from .runtime_engine import RuntimeEngine
from .state_manager import StateManager
from .event_bus import EventBus
from .lock_manager import LockManager
from .rate_limiter import RateLimiter
from .artifact_manager import ArtifactManager
from .secret_manager import SecretManager

__all__ = [
    # Enums
    "TaskStatus",
    "TaskPriority",
    "WorkerType",
    "WorkerStatus",
    "ResourceType",
    "HealthStatus",
    "AlertLevel",
    "ScheduleType",
    "WorkflowState",
    "OnErrorPolicy",
    "ArtifactType",
    "ArtifactStatus",
    "SecretLevel",
    # Schemas
    "RuntimeTask",
    "Worker",
    "ResourceState",
    "HealthReport",
    "RuntimeMetrics",
    "Alert",
    "Checkpoint",
    "WorkflowNode",
    "WorkflowDAG",
    "RuntimeReport",
    "WorkflowStateData",
    "RuntimeEvent",
    "DistributedLock",
    "Artifact",
    "Secret",
    # Core Runtime
    "ConfigManager",
    "Logger",
    "TaskQueue",
    "WorkerPool",
    "CacheManager",
    "DependencyGraph",
    "ResourceManager",
    "Scheduler",
    "WorkflowEngine",
    "RuntimeAPI",
    "RuntimeEngine",
    # Reliability
    "RetryManager",
    "RollbackManager",
    "CheckpointManager",
    # State & Events
    "StateManager",
    "EventBus",
    # Coordination
    "LockManager",
    "RateLimiter",
    # Observability
    "HealthMonitor",
    "MetricsCollector",
    "AlertManager",
    # Infrastructure
    "ServiceRegistry",
    "PluginManager",
    # AI Asset Management
    "ArtifactManager",
    "SecretManager",
]