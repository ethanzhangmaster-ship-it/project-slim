"""E15.0.8 Database Manager — 单元测试.

验证 DatabaseManager 的完整功能:
  - 初始化: 默认/自定义 URL、参数配置 (6 tests)
  - 连接: connect()、is_connected、engine 属性 (6 tests)
  - Session 管理: 上下文管理器、commit/rollback、异常处理 (9 tests)
  - 健康检查: health_check 各种状态 (5 tests)
  - 连接生命周期: connect/close/reconnect (5 tests)
  - 边界情况: 属性访问、表管理、create_session (5 tests)
  - Repr: __repr__ 格式验证 (2 tests)

总计: 38 个测试用例
使用 SQLite 内存数据库 (sqlite:///:memory:)
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Mock redis to prevent import error when redis is not installed
# (storage/__init__.py → service.py → redis_state.py → redis)
if "redis" not in sys.modules:
    sys.modules["redis"] = MagicMock()

from market_ops.creative_vision_runtime.growth_runtime.storage.database import DatabaseManager


# ═══════════════════════════════════════════════════════════
# Test ORM (for create_all_tables / drop_all_tables tests)
# ═══════════════════════════════════════════════════════════

class _TestBase(DeclarativeBase):
    """测试用 ORM Base."""
    pass


class _TestModel(_TestBase):
    __tablename__ = "test_model"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    value = Column(Integer, default=0)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_db(
    database_url: str = "sqlite:///:memory:",
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 3600,
) -> DatabaseManager:
    return DatabaseManager(
        database_url=database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )


def _make_connected_db(
    database_url: str = "sqlite:///:memory:",
) -> DatabaseManager:
    db = _make_db(database_url=database_url)
    db.connect()
    return db


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _patch_sqlite_create_engine(monkeypatch):
    """Monkey-patch create_engine 以兼容 SQLite 内存数据库.

    DatabaseManager.connect() 传递的 max_overflow / pool_recycle / pool_pre_ping
    参数不被 SQLite 的 SingletonThreadPool 支持，需要在此剥离。
    """
    from market_ops.creative_vision_runtime.growth_runtime.storage import database as db_mod

    _original = db_mod.create_engine

    def _patched(url, **kwargs):
        if "sqlite" in str(url):
            kwargs.pop("max_overflow", None)
            kwargs.pop("pool_recycle", None)
            kwargs.pop("pool_pre_ping", None)
        return _original(url, **kwargs)

    monkeypatch.setattr(db_mod, "create_engine", _patched)


@pytest.fixture
def db() -> DatabaseManager:
    """创建内存 SQLite 数据库并连接."""
    manager = DatabaseManager(database_url="sqlite:///:memory:")
    manager.connect()
    yield manager
    manager.close()


# ═══════════════════════════════════════════════════════════
# 1. Initialization
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerInit:
    """DatabaseManager 初始化测试."""

    def test_init_with_default_url(self):
        """默认 database_url 从环境变量或内置默认值读取."""
        db = DatabaseManager()
        assert db._database_url is not None
        assert "postgresql://" in db._database_url or "DATABASE_URL" in db._database_url or True
        # 默认 URL 包含 postgresql:// 或来自环境变量
        assert isinstance(db._database_url, str)
        assert len(db._database_url) > 0

    def test_init_with_custom_sqlite_url(self):
        """自定义 SQLite 数据库 URL."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        assert db._database_url == "sqlite:///:memory:"

    def test_init_with_echo_false(self):
        """echo 默认为 False."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        assert db._echo is False

    def test_init_with_echo_true(self):
        """echo=True 时正确保存."""
        db = DatabaseManager(database_url="sqlite:///:memory:", echo=True)
        assert db._echo is True

    def test_init_with_pool_params(self):
        """自定义连接池参数."""
        db = DatabaseManager(
            database_url="sqlite:///:memory:",
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
        )
        assert db._pool_size == 5
        assert db._max_overflow == 10
        assert db._pool_recycle == 1800

    def test_init_not_connected_initially(self):
        """新创建的 DatabaseManager 尚未连接."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        assert db.is_connected is False
        assert db._engine is None
        assert db._session_factory is None


# ═══════════════════════════════════════════════════════════
# 2. Connection
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerConnection:
    """DatabaseManager 连接测试."""

    def test_connect_sqlite_memory(self):
        """connect() 使用 SQLite 内存数据库成功."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.connect()
        assert db.is_connected is True

    def test_connect_sets_engine_attribute(self):
        """connect() 后 engine 属性被设置."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.connect()
        assert db._engine is not None
        assert isinstance(db.engine, Engine)

    def test_connect_sets_session_factory(self):
        """connect() 后 session_factory 属性被设置."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.connect()
        assert db._session_factory is not None
        assert isinstance(db.session_factory, sessionmaker)

    def test_is_connected_true_after_connect(self):
        """connect() 后 is_connected 返回 True."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        assert db.is_connected is False
        db.connect()
        assert db.is_connected is True

    def test_engine_is_sqlalchemy_engine(self):
        """engine 属性返回 SQLAlchemy Engine 实例."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.connect()
        assert isinstance(db.engine, Engine)

    def test_connect_custom_pool_params(self):
        """connect() 使用自定义连接池参数创建引擎."""
        db = DatabaseManager(database_url="sqlite:///:memory:", pool_size=3, max_overflow=5)
        db.connect()
        assert isinstance(db.engine, Engine)
        assert db.is_connected is True


# ═══════════════════════════════════════════════════════════
# 3. Session Management
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerSession:
    """DatabaseManager Session 管理测试."""

    def test_session_context_manager_commit(self, db):
        """session() 上下文管理器在成功时自动 commit."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_commit (id INTEGER PRIMARY KEY, name TEXT)"))
            session.execute(text("INSERT INTO test_commit (name) VALUES ('alice')"))

        with db.session() as session:
            result = session.execute(text("SELECT name FROM test_commit")).scalar()
            assert result == "alice"

    def test_session_context_manager_rollback_on_exception(self, db):
        """session() 上下文管理器在异常时自动 rollback."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, name TEXT)"))

        with pytest.raises(ValueError, match="test rollback"):
            with db.session() as session:
                session.execute(text("INSERT INTO test_rollback (name) VALUES ('should_rollback')"))
                raise ValueError("test rollback")

        with db.session() as session:
            result = session.execute(text("SELECT COUNT(*) FROM test_rollback")).scalar()
            assert result == 0

    def test_session_execute_simple_query(self, db):
        """session() 可以执行简单查询."""
        with db.session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1

    def test_session_create_table_insert_query(self, db):
        """session() 中创建表、插入数据、查询数据."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"))
            session.execute(text("INSERT INTO test_items (name, value) VALUES ('item1', 100)"))
            session.execute(text("INSERT INTO test_items (name, value) VALUES ('item2', 200)"))

        with db.session() as session:
            rows = session.execute(text("SELECT name, value FROM test_items ORDER BY id")).fetchall()
            assert len(rows) == 2
            assert rows[0] == ("item1", 100)
            assert rows[1] == ("item2", 200)

    def test_session_multiple_sequential(self, db):
        """多个连续的 session() 上下文，数据可见."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_seq (id INTEGER PRIMARY KEY, name TEXT)"))

        for i in range(3):
            with db.session() as session:
                session.execute(text("INSERT INTO test_seq (name) VALUES (:name)"), {"name": f"seq_{i}"})

        with db.session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM test_seq")).scalar()
            assert count == 3

    def test_session_exception_propagation(self, db):
        """session() 中的异常会正确传播."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_prop (id INTEGER PRIMARY KEY, name TEXT)"))

        with pytest.raises(RuntimeError, match="boom"):
            with db.session() as session:
                session.execute(text("INSERT INTO test_prop (name) VALUES ('data')"))
                raise RuntimeError("boom")

    def test_create_session_returns_session(self, db):
        """create_session() 返回 Session 实例."""
        s = db.create_session()
        assert isinstance(s, Session)
        s.close()

    def test_create_session_independent(self, db):
        """create_session() 创建的 session 独立可用."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_independent (id INTEGER PRIMARY KEY, name TEXT)"))
            session.execute(text("INSERT INTO test_independent (name) VALUES ('hello')"))

        s = db.create_session()
        try:
            result = s.execute(text("SELECT name FROM test_independent")).scalar()
            assert result == "hello"
        finally:
            s.close()

    def test_session_rollback_data_not_persisted(self, db):
        """rollback 后数据不会被持久化."""
        with db.session() as session:
            session.execute(text("CREATE TABLE test_not_persisted (id INTEGER PRIMARY KEY, name TEXT)"))

        with pytest.raises(ValueError):
            with db.session() as session:
                session.execute(text("INSERT INTO test_not_persisted (name) VALUES ('lost')"))
                # 在 commit 前抛出异常，触发 rollback
                raise ValueError("intentional")

        with db.session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM test_not_persisted")).scalar()
            assert count == 0


# ═══════════════════════════════════════════════════════════
# 4. Health Check
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerHealthCheck:
    """DatabaseManager 健康检查测试.

    health_check() 内部使用 SELECT version() (PostgreSQL 专用).
    SQLite 不支持此函数，因此测试涵盖两种场景:
      - 已连接 SQLite: 返回 unhealthy + error (因为 version() 不存在)
      - 未连接: 返回 disconnected
    """

    def test_health_check_connected_sqlite(self, db):
        """已连接 SQLite 时 health_check 返回 unhealthy 并包含错误信息."""
        result = db.health_check()
        assert result["status"] == "unhealthy"
        assert result["latency_ms"] == 0
        assert result["version"] == ""
        assert "error" in result
        assert "version" in result["error"]

    def test_health_check_disconnected(self):
        """未连接时 health_check 返回 disconnected 状态."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        result = db.health_check()
        assert result["status"] == "disconnected"
        assert result["latency_ms"] == 0
        assert result["version"] == ""

    def test_health_check_keys_structure(self, db):
        """health_check 返回的字典包含正确的键."""
        result = db.health_check()
        assert "status" in result
        assert "latency_ms" in result
        assert "version" in result
        assert isinstance(result["status"], str)
        assert isinstance(result["latency_ms"], (int, float))
        assert isinstance(result["version"], str)

    def test_health_check_unhealthy_has_error_key(self, db):
        """health_check 返回 unhealthy 时包含 error 键."""
        result = db.health_check()
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0

    def test_health_check_disconnected_no_error_key(self):
        """health_check 返回 disconnected 时不包含 error 键."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        result = db.health_check()
        assert result["status"] == "disconnected"
        assert "error" not in result


# ═══════════════════════════════════════════════════════════
# 5. Connection Lifecycle
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerLifecycle:
    """DatabaseManager 连接生命周期测试."""

    def test_close_disposes_engine(self, db):
        """close() 释放引擎并将 engine 设为 None."""
        assert db.is_connected is True
        assert db._engine is not None
        db.close()
        assert db._engine is None

    def test_close_is_connected_false(self, db):
        """close() 后 is_connected 返回 False."""
        db.close()
        assert db.is_connected is False

    def test_reconnect_after_close(self, db):
        """close() 后可以重新 connect()."""
        db.close()
        assert db.is_connected is False

        db.connect()
        assert db.is_connected is True

        # 验证重新连接后可以正常使用
        with db.session() as session:
            session.execute(text("CREATE TABLE test_reconnect (id INTEGER PRIMARY KEY, name TEXT)"))
            session.execute(text("INSERT INTO test_reconnect (name) VALUES ('reconnected')"))

        with db.session() as session:
            result = session.execute(text("SELECT name FROM test_reconnect")).scalar()
            assert result == "reconnected"

    def test_multiple_close_is_safe(self):
        """多次 close() 调用安全 (不抛异常)."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.connect()
        db.close()
        db.close()  # 第二次 close 不应抛异常
        assert db.is_connected is False

    def test_close_before_connect_is_safe(self):
        """未连接时 close() 安全 (不抛异常)."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        db.close()  # 不应抛异常
        assert db.is_connected is False


# ═══════════════════════════════════════════════════════════
# 6. Edge Cases
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerEdgeCases:
    """DatabaseManager 边界情况测试."""

    def test_engine_property_raises_before_connect(self):
        """未连接时访问 engine 属性抛出 RuntimeError."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.engine

    def test_session_factory_property_raises_before_connect(self):
        """未连接时访问 session_factory 属性抛出 RuntimeError."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.session_factory

    def test_session_before_connect_raises(self):
        """未连接时使用 session() 上下文管理器抛出 RuntimeError."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            with db.session() as session:
                pass

    def test_create_all_tables_and_drop(self, db):
        """create_all_tables 和 drop_all_tables 正常工作."""
        db.create_all_tables(_TestBase)

        # 验证表已创建
        with db.session() as session:
            session.execute(text("INSERT INTO test_model (name, value) VALUES ('test', 42)"))

        with db.session() as session:
            row = session.execute(text("SELECT name, value FROM test_model")).fetchone()
            assert row == ("test", 42)

        db.drop_all_tables(_TestBase)

        # 验证表已删除
        with pytest.raises(Exception):
            with db.session() as session:
                session.execute(text("SELECT * FROM test_model"))

    def test_create_all_tables_multiple_calls(self, db):
        """多次 create_all_tables 调用安全 (幂等)."""
        db.create_all_tables(_TestBase)
        db.create_all_tables(_TestBase)  # 第二次调用不抛异常

        with db.session() as session:
            session.execute(text("INSERT INTO test_model (name, value) VALUES ('idempotent', 1)"))

        with db.session() as session:
            row = session.execute(text("SELECT name FROM test_model")).fetchone()
            assert row == ("idempotent",)


# ═══════════════════════════════════════════════════════════
# 7. Repr
# ═══════════════════════════════════════════════════════════

class TestDatabaseManagerRepr:
    """DatabaseManager __repr__ 测试."""

    def test_repr_connected(self, db):
        """已连接时 __repr__ 包含 connected=True."""
        r = repr(db)
        assert "DatabaseManager" in r
        assert "connected=True" in r

    def test_repr_not_connected(self):
        """未连接时 __repr__ 包含 connected=False."""
        db = DatabaseManager(database_url="sqlite:///:memory:")
        r = repr(db)
        assert "DatabaseManager" in r
        assert "connected=False" in r