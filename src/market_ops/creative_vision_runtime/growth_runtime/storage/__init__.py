"""E15.0.8 Persistent Storage Layer — 持久化存储层.

将 E15.0 内存态 Control Plane 升级为可长期运行、可恢复、可审计的生产状态层。

模块:
  - database.py:   DatabaseManager (SQLAlchemy + PostgreSQL 连接管理)
  - models.py:     SQLAlchemy ORM 模型
  - repositories/: Repository 模式 (audit/event/metric/execution/alert)
  - redis_state.py: Redis 运行时状态 (锁/冷却/心跳)
  - service.py:    StorageService 统一入口
  - migration.py:  数据库迁移管理
"""

from .database import DatabaseManager
from .service import StorageService

__all__ = [
    "DatabaseManager",
    "StorageService",
]