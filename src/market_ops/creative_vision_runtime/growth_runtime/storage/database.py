"""E15.0.8 Database Manager — SQLAlchemy + PostgreSQL 连接管理.

负责:
  - 引擎创建与连接池管理
  - Session 工厂
  - 健康检查
  - 优雅关闭

用法:
    db = DatabaseManager(database_url="postgresql://growth:growth@localhost:5432/growth_db")
    db.connect()
    with db.session() as session:
        session.add(audit_record)
        session.commit()
    health = db.health_check()
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseManager:
    """数据库管理器 — SQLAlchemy 2.0 + PostgreSQL.

    属性:
        engine:          SQLAlchemy Engine
        session_factory: Session 工厂
        _database_url:   数据库连接 URL
    """

    def __init__(
        self,
        database_url: str | None = None,
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_recycle: int = 3600,
    ):
        self._database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://growth:growth@localhost:5432/growth_db",
        )
        self._echo = echo
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_recycle = pool_recycle
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    # ── Properties ───────────────────────────────────────────

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        if self._session_factory is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._session_factory

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    # ── Connection ───────────────────────────────────────────

    def connect(self) -> None:
        """建立数据库连接."""
        self._engine = create_engine(
            self._database_url,
            echo=self._echo,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            pool_recycle=self._pool_recycle,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    def close(self) -> None:
        """关闭连接."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # ── Session ──────────────────────────────────────────────

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """获取数据库会话 (上下文管理器).

        用法:
            with db.session() as session:
                record = session.get(AuditRecord, id)
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_session(self) -> Session:
        """创建独立会话 (调用者负责关闭)."""
        return self.session_factory()

    # ── Health Check ─────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """数据库健康检查.

        Returns:
            {"status": "healthy", "latency_ms": 1.5, "version": "PostgreSQL 16.x"}
        """
        if not self.is_connected:
            return {"status": "disconnected", "latency_ms": 0, "version": ""}

        import time
        try:
            start = time.monotonic()
            with self.session() as session:
                result = session.execute(text("SELECT version()")).scalar()
            latency = (time.monotonic() - start) * 1000
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "version": str(result) if result else "",
            }
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "version": "", "error": str(e)}

    # ── Table Management ─────────────────────────────────────

    def create_all_tables(self, base: Any) -> None:
        """创建所有 ORM 表."""
        base.metadata.create_all(self.engine)

    def drop_all_tables(self, base: Any) -> None:
        """删除所有 ORM 表."""
        base.metadata.drop_all(self.engine)

    def __repr__(self) -> str:
        db_name = self._database_url.split("/")[-1] if self._database_url else "unknown"
        return f"DatabaseManager(db={db_name}, connected={self.is_connected})"


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

_db_instance: DatabaseManager | None = None


def get_db() -> DatabaseManager:
    """获取全局 DatabaseManager 单例."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
        _db_instance.connect()
    return _db_instance


def set_db(db: DatabaseManager) -> None:
    """设置全局 DatabaseManager."""
    global _db_instance
    _db_instance = db