"""E15.0.8 Redis Runtime State — 单元测试.

验证 RedisStateManager 的完整功能:
  - Connection: connect / close / is_connected / health_check (7 tests)
  - Scheduler Lock: acquire / release / check / holder / extend (11 tests)
  - Cooldown: set / get / check / reset / all (8 tests)
  - Worker Heartbeat: send / get / alive check / all workers (9 tests)
  - Runtime State: set / get / delete / keys / TTL (8 tests)
  - Stats & Flush: stats / flush (6 tests)
  - Worker ID & Repr (4 tests)

总计: 53 个测试用例
"""

from __future__ import annotations

import importlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── 注入 mock redis 模块 ───────────────────────────────────────
# 关键: 由于其他测试文件 (test_e1508_wiring.py) 先导入了 redis_state,
# redis_state 模块已用真实 redis 加载。需要 reload 使其使用 mock。
_mock_redis = MagicMock(name="redis_module")
_mock_redis.Redis = MagicMock(name="redis.Redis")
sys.modules["redis"] = _mock_redis

# 重新加载 redis_state 以使用 mock redis
import market_ops.creative_vision_runtime.growth_runtime.storage.redis_state as _rs_module

importlib.reload(_rs_module)

from market_ops.creative_vision_runtime.growth_runtime.storage.redis_state import (
    RedisStateManager,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

def _make_mock_client():
    """创建配置好的 mock Redis 客户端."""
    c = MagicMock(name="redis_client")
    c.ping.return_value = True
    c.set.return_value = True
    c.get.return_value = None
    c.delete.return_value = 1
    c.exists.return_value = 0
    c.eval.return_value = 1
    c.setex.return_value = True
    c.expire.return_value = True
    c.scan_iter.return_value = iter([])
    c.info.return_value = {
        "redis_version": "7.2.0",
        "used_memory": 2097152,
        "connected_clients": 3,
    }
    c.close.return_value = None
    return c


@pytest.fixture
def mock_client():
    """返回一个配置好的 mock Redis 客户端."""
    return _make_mock_client()


@pytest.fixture
def connected_manager(mock_client):
    """已连接且 worker_id 固定的 RedisStateManager."""
    _mock_redis.Redis.from_url.return_value = mock_client
    manager = RedisStateManager(worker_id="test_worker_01")
    manager.connect()
    yield manager
    _mock_redis.Redis.from_url.reset_mock()


# ═══════════════════════════════════════════════════════════
# 1. Connection
# ═══════════════════════════════════════════════════════════

class TestConnection:
    """连接管理测试."""

    def test_connect_creates_client_and_pings(self, mock_client):
        """connect() 应创建 Redis 客户端并 ping."""
        _mock_redis.Redis.from_url.reset_mock()
        _mock_redis.Redis.from_url.return_value = mock_client
        manager = RedisStateManager(worker_id="w1")
        manager.connect()
        _mock_redis.Redis.from_url.assert_called_once()
        mock_client.ping.assert_called_once()

    def test_connect_default_url(self, mock_client):
        """connect() 默认使用 redis://localhost:6379/0."""
        _mock_redis.Redis.from_url.reset_mock()
        _mock_redis.Redis.from_url.return_value = mock_client
        manager = RedisStateManager(worker_id="w1")
        manager.connect()
        call_args = _mock_redis.Redis.from_url.call_args[0]
        assert "redis://" in call_args[0]

    def test_close_disconnects_and_nullifies_client(self, connected_manager, mock_client):
        """close() 应关闭客户端并置空."""
        connected_manager.close()
        mock_client.close.assert_called_once()
        assert not connected_manager.is_connected

    def test_is_connected_after_connect(self, connected_manager):
        """connect() 后 is_connected 应为 True."""
        assert connected_manager.is_connected

    def test_client_raises_when_not_connected(self):
        """未连接时访问 client 属性应抛出 RuntimeError."""
        manager = RedisStateManager()
        with pytest.raises(RuntimeError, match="not connected"):
            _ = manager.client


# ═══════════════════════════════════════════════════════════
# 2. Health Check
# ═══════════════════════════════════════════════════════════

class TestHealthCheck:
    """健康检查测试."""

    def test_health_check_disconnected(self):
        """未连接时 health_check 返回 disconnected."""
        manager = RedisStateManager()
        result = manager.health_check()
        assert result["status"] == "disconnected"

    def test_health_check_healthy(self, connected_manager, mock_client):
        """连接正常时 health_check 返回 healthy."""
        mock_client.ping.return_value = True
        result = connected_manager.health_check()
        assert result["status"] == "healthy"
        assert result["redis_version"] == "7.2.0"

    def test_health_check_unhealthy_on_ping_failure(self, connected_manager, mock_client):
        """ping 失败时 health_check 返回 unhealthy."""
        mock_client.ping.side_effect = Exception("connection refused")
        result = connected_manager.health_check()
        assert result["status"] == "unhealthy"
        assert "error" in result


# ═══════════════════════════════════════════════════════════
# 3. Scheduler Lock
# ═══════════════════════════════════════════════════════════

class TestSchedulerLockAcquire:
    """调度器锁获取测试."""

    def test_acquire_success(self, connected_manager, mock_client):
        """SETNX 成功时 acquire 返回 True."""
        mock_client.set.return_value = True
        result = connected_manager.acquire_scheduler_lock("growth_scheduler", ttl=3600)
        assert result is True
        mock_client.set.assert_called_with(
            "growth:scheduler:lock:growth_scheduler",
            "test_worker_01",
            nx=True,
            ex=3600,
        )

    def test_acquire_failure_already_held(self, connected_manager, mock_client):
        """SETNX 失败时 acquire 返回 False."""
        mock_client.set.return_value = None
        result = connected_manager.acquire_scheduler_lock("growth_scheduler")
        assert result is False

    def test_acquire_default_scheduler_name(self, connected_manager, mock_client):
        """默认 scheduler_name 为 'default'."""
        mock_client.set.return_value = True
        connected_manager.acquire_scheduler_lock()
        mock_client.set.assert_called_with(
            "growth:scheduler:lock:default",
            "test_worker_01",
            nx=True,
            ex=3600,
        )

    def test_acquire_custom_ttl(self, connected_manager, mock_client):
        """自定义 TTL 应正确传递."""
        mock_client.set.return_value = True
        connected_manager.acquire_scheduler_lock("s1", ttl=7200)
        call_kwargs = mock_client.set.call_args.kwargs
        assert call_kwargs["ex"] == 7200


class TestSchedulerLockRelease:
    """调度器锁释放测试."""

    def test_release_success_own_lock(self, connected_manager, mock_client):
        """释放自己的锁应成功."""
        mock_client.eval.return_value = 1
        result = connected_manager.release_scheduler_lock("growth_scheduler")
        assert result is True
        mock_client.eval.assert_called_once()

    def test_release_failure_not_owner(self, connected_manager, mock_client):
        """释放他人持有的锁应失败."""
        mock_client.eval.return_value = 0
        result = connected_manager.release_scheduler_lock("growth_scheduler")
        assert result is False


class TestSchedulerLockQuery:
    """调度器锁查询测试."""

    def test_is_scheduler_locked_true(self, connected_manager, mock_client):
        """锁存在时返回 True."""
        mock_client.exists.return_value = 1
        assert connected_manager.is_scheduler_locked("s1") is True

    def test_is_scheduler_locked_false(self, connected_manager, mock_client):
        """锁不存在时返回 False."""
        mock_client.exists.return_value = 0
        assert connected_manager.is_scheduler_locked("s1") is False

    def test_get_lock_holder(self, connected_manager, mock_client):
        """获取锁持有者."""
        mock_client.get.return_value = "worker_42"
        holder = connected_manager.get_lock_holder("s1")
        assert holder == "worker_42"

    def test_get_lock_holder_none(self, connected_manager, mock_client):
        """锁不存在时 holder 为 None."""
        mock_client.get.return_value = None
        holder = connected_manager.get_lock_holder("s1")
        assert holder is None


class TestSchedulerLockExtend:
    """调度器锁延长测试."""

    def test_extend_success_when_holder(self, connected_manager, mock_client):
        """持有者延长锁 TTL 成功."""
        mock_client.get.return_value = "test_worker_01"
        mock_client.expire.return_value = True
        result = connected_manager.extend_scheduler_lock("s1", ttl=7200)
        assert result is True
        mock_client.expire.assert_called_once_with("growth:scheduler:lock:s1", 7200)

    def test_extend_failure_not_holder(self, connected_manager, mock_client):
        """非持有者延长锁 TTL 失败."""
        mock_client.get.return_value = "other_worker"
        result = connected_manager.extend_scheduler_lock("s1")
        assert result is False

    def test_extend_failure_lock_not_exists(self, connected_manager, mock_client):
        """锁不存在时延长失败."""
        mock_client.get.return_value = None
        result = connected_manager.extend_scheduler_lock("s1")
        assert result is False


# ═══════════════════════════════════════════════════════════
# 4. Cooldown
# ═══════════════════════════════════════════════════════════

class TestCooldownSet:
    """冷却设置测试."""

    def test_set_cooldown_uses_setex(self, connected_manager, mock_client):
        """set_cooldown 应调用 setex."""
        connected_manager.set_cooldown("c1", "pause", ttl_days=7)
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "growth:cooldown:c1"
        assert call_args[1] == 7 * 86400

    def test_set_cooldown_data_contains_correct_fields(self, connected_manager, mock_client):
        """冷却数据包含正确字段."""
        connected_manager.set_cooldown("c2", "scale", ttl_days=3)
        data = json.loads(mock_client.setex.call_args[0][2])
        assert data["campaign_id"] == "c2"
        assert data["last_action"] == "scale"
        assert data["ttl_days"] == 3

    def test_set_cooldown_default_ttl(self, connected_manager, mock_client):
        """默认 TTL 为 7 天."""
        connected_manager.set_cooldown("c3", "update")
        assert mock_client.setex.call_args[0][1] == 7 * 86400


class TestCooldownGet:
    """冷却查询测试."""

    def test_get_cooldown_returns_parsed_data(self, connected_manager, mock_client):
        """get_cooldown 返回解析后的 JSON 数据."""
        mock_client.get.return_value = json.dumps({"campaign_id": "c1", "last_action": "pause"})
        result = connected_manager.get_cooldown("c1")
        assert result["campaign_id"] == "c1"
        assert result["last_action"] == "pause"

    def test_get_cooldown_not_found(self, connected_manager, mock_client):
        """冷却不存在时返回 None."""
        mock_client.get.return_value = None
        result = connected_manager.get_cooldown("nonexistent")
        assert result is None

    def test_is_in_cooldown_true(self, connected_manager, mock_client):
        """冷却期内返回 True."""
        mock_client.exists.return_value = 1
        assert connected_manager.is_in_cooldown("c1") is True

    def test_is_in_cooldown_false(self, connected_manager, mock_client):
        """不在冷却期内返回 False."""
        mock_client.exists.return_value = 0
        assert connected_manager.is_in_cooldown("c1") is False


class TestCooldownReset:
    """冷却重置测试."""

    def test_reset_cooldown_success(self, connected_manager, mock_client):
        """删除冷却成功."""
        mock_client.delete.return_value = 1
        result = connected_manager.reset_cooldown("c1")
        assert result is True
        mock_client.delete.assert_called_once_with("growth:cooldown:c1")

    def test_reset_cooldown_not_found(self, connected_manager, mock_client):
        """删除不存在的冷却返回 False."""
        mock_client.delete.return_value = 0
        result = connected_manager.reset_cooldown("c1")
        assert result is False

    def test_get_all_cooldowns(self, connected_manager, mock_client):
        """获取所有冷却状态."""
        mock_client.scan_iter.return_value = iter([
            "growth:cooldown:c1",
            "growth:cooldown:c2",
        ])
        mock_client.get.side_effect = lambda k: json.dumps({
            "campaign_id": k.split(":")[-1],
            "last_action": "pause",
        })
        result = connected_manager.get_all_cooldowns()
        assert len(result) == 2
        assert "c1" in result
        assert "c2" in result

    def test_get_all_cooldowns_empty(self, connected_manager, mock_client):
        """无冷却时返回空字典."""
        mock_client.scan_iter.return_value = iter([])
        result = connected_manager.get_all_cooldowns()
        assert result == {}

    def test_get_all_cooldowns_skips_none(self, connected_manager, mock_client):
        """跳过空数据键."""
        mock_client.scan_iter.return_value = iter(["growth:cooldown:c1"])
        mock_client.get.return_value = None
        result = connected_manager.get_all_cooldowns()
        assert result == {}


# ═══════════════════════════════════════════════════════════
# 5. Worker Heartbeat
# ═══════════════════════════════════════════════════════════

class TestHeartbeatSend:
    """心跳发送测试."""

    def test_send_heartbeat_defaults(self, connected_manager, mock_client):
        """默认心跳发送."""
        connected_manager.send_heartbeat()
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "growth:worker:heartbeat:test_worker_01"
        assert call_args[1] == 120
        data = json.loads(call_args[2])
        assert data["worker_id"] == "test_worker_01"
        assert data["status"] == "running"

    def test_send_heartbeat_custom_status(self, connected_manager, mock_client):
        """自定义状态心跳."""
        connected_manager.send_heartbeat(status="error")
        data = json.loads(mock_client.setex.call_args[0][2])
        assert data["status"] == "error"

    def test_send_heartbeat_custom_ttl(self, connected_manager, mock_client):
        """自定义 TTL 心跳."""
        connected_manager.send_heartbeat(ttl=60)
        assert mock_client.setex.call_args[0][1] == 60

    def test_send_heartbeat_error_status(self, connected_manager, mock_client):
        """错误状态心跳."""
        connected_manager.send_heartbeat(status="error", ttl=30)
        data = json.loads(mock_client.setex.call_args[0][2])
        assert data["status"] == "error"
        assert "last_tick" in data


class TestHeartbeatGet:
    """心跳查询测试."""

    def test_get_heartbeat_own_worker(self, connected_manager, mock_client):
        """获取自己的心跳."""
        mock_client.get.return_value = json.dumps({
            "worker_id": "test_worker_01",
            "status": "running",
            "last_tick": "2026-07-29T00:00:00Z",
        })
        result = connected_manager.get_heartbeat()
        assert result["worker_id"] == "test_worker_01"
        assert result["status"] == "running"

    def test_get_heartbeat_custom_worker(self, connected_manager, mock_client):
        """获取指定 worker 的心跳."""
        mock_client.get.return_value = json.dumps({
            "worker_id": "w_other",
            "status": "idle",
        })
        result = connected_manager.get_heartbeat("w_other")
        assert result["worker_id"] == "w_other"

    def test_get_heartbeat_not_found(self, connected_manager, mock_client):
        """心跳不存在时返回 None."""
        mock_client.get.return_value = None
        result = connected_manager.get_heartbeat("w_missing")
        assert result is None

    def test_is_worker_alive_true(self, connected_manager, mock_client):
        """Worker 存活时返回 True."""
        mock_client.exists.return_value = 1
        assert connected_manager.is_worker_alive("w1") is True

    def test_is_worker_alive_false(self, connected_manager, mock_client):
        """Worker 不存活时返回 False."""
        mock_client.exists.return_value = 0
        assert connected_manager.is_worker_alive("w1") is False

    def test_is_worker_alive_default_self(self, connected_manager, mock_client):
        """默认检查自己的存活状态."""
        mock_client.exists.return_value = 1
        connected_manager.is_worker_alive()
        mock_client.exists.assert_called_with(
            "growth:worker:heartbeat:test_worker_01"
        )


class TestGetAllWorkers:
    """获取所有 Worker 测试."""

    def test_get_all_workers(self, connected_manager, mock_client):
        """获取所有 Worker 状态."""
        mock_client.scan_iter.return_value = iter([
            "growth:worker:heartbeat:w1",
            "growth:worker:heartbeat:w2",
        ])
        mock_client.get.side_effect = lambda k: json.dumps({
            "worker_id": k.split(":")[-1],
            "status": "running",
        })
        workers = connected_manager.get_all_workers()
        assert len(workers) == 2
        assert all(w["alive"] for w in workers)

    def test_get_all_workers_empty(self, connected_manager, mock_client):
        """无 Worker 时返回空列表."""
        mock_client.scan_iter.return_value = iter([])
        workers = connected_manager.get_all_workers()
        assert workers == []

    def test_get_all_workers_skips_none(self, connected_manager, mock_client):
        """跳过空数据 Worker."""
        mock_client.scan_iter.return_value = iter(["growth:worker:heartbeat:w1"])
        mock_client.get.return_value = None
        workers = connected_manager.get_all_workers()
        assert workers == []


# ═══════════════════════════════════════════════════════════
# 6. Runtime State
# ═══════════════════════════════════════════════════════════

class TestRuntimeStateSet:
    """运行时状态设置测试."""

    def test_set_state_without_ttl(self, connected_manager, mock_client):
        """无 TTL 的状态设置."""
        connected_manager.set_state("key1", {"a": 1})
        mock_client.set.assert_called_with(
            "growth:runtime:state:key1",
            json.dumps({"a": 1}),
        )

    def test_set_state_with_ttl(self, connected_manager, mock_client):
        """有 TTL 的状态设置."""
        connected_manager.set_state("key2", "value", ttl=300)
        mock_client.setex.assert_called_with(
            "growth:runtime:state:key2",
            300,
            "value",
        )

    def test_set_state_string_value(self, connected_manager, mock_client):
        """字符串值不经过 json.dumps."""
        connected_manager.set_state("key3", "plain_string")
        mock_client.set.assert_called_with(
            "growth:runtime:state:key3",
            "plain_string",
        )


class TestRuntimeStateGet:
    """运行时状态获取测试."""

    def test_get_state_json(self, connected_manager, mock_client):
        """获取 JSON 状态."""
        mock_client.get.return_value = json.dumps({"a": 1, "b": [2, 3]})
        result = connected_manager.get_state("key1")
        assert result == {"a": 1, "b": [2, 3]}

    def test_get_state_plain_string(self, connected_manager, mock_client):
        """获取纯字符串状态 (非 JSON)."""
        mock_client.get.return_value = "just_a_string"
        result = connected_manager.get_state("key2")
        assert result == "just_a_string"

    def test_get_state_not_found(self, connected_manager, mock_client):
        """状态不存在时返回 None."""
        mock_client.get.return_value = None
        result = connected_manager.get_state("nonexistent")
        assert result is None


class TestRuntimeStateDelete:
    """运行时状态删除测试."""

    def test_delete_state_success(self, connected_manager, mock_client):
        """删除状态成功."""
        mock_client.delete.return_value = 1
        result = connected_manager.delete_state("key1")
        assert result is True
        mock_client.delete.assert_called_with("growth:runtime:state:key1")

    def test_delete_state_not_found(self, connected_manager, mock_client):
        """删除不存在的状态返回 False."""
        mock_client.delete.return_value = 0
        result = connected_manager.delete_state("nonexistent")
        assert result is False


class TestRuntimeStateKeys:
    """运行时状态键查询测试."""

    def test_get_state_keys_default_pattern(self, connected_manager, mock_client):
        """默认 pattern 获取所有键."""
        mock_client.scan_iter.return_value = iter([
            "growth:runtime:state:k1",
            "growth:runtime:state:k2",
        ])
        keys = connected_manager.get_state_keys()
        assert keys == ["k1", "k2"]

    def test_get_state_keys_custom_pattern(self, connected_manager, mock_client):
        """自定义 pattern."""
        mock_client.scan_iter.return_value = iter([
            "growth:runtime:state:prefix_k1",
        ])
        keys = connected_manager.get_state_keys("prefix_*")
        assert keys == ["prefix_k1"]

    def test_get_state_keys_empty(self, connected_manager, mock_client):
        """无键时返回空列表."""
        mock_client.scan_iter.return_value = iter([])
        keys = connected_manager.get_state_keys()
        assert keys == []


# ═══════════════════════════════════════════════════════════
# 7. Stats & Flush
# ═══════════════════════════════════════════════════════════

class TestStats:
    """统计信息测试."""

    def test_get_stats_disconnected(self):
        """未连接时返回 disconnected."""
        manager = RedisStateManager()
        result = manager.get_stats()
        assert result["status"] == "disconnected"

    def test_get_stats_connected(self, connected_manager, mock_client):
        """连接时返回完整统计."""
        mock_client.scan_iter.return_value = iter([])
        mock_client.info.return_value = {
            "redis_version": "7.2.0",
            "used_memory": 2097152,
            "connected_clients": 3,
        }
        result = connected_manager.get_stats()
        assert result["status"] == "connected"
        assert result["redis_version"] == "7.2.0"
        assert result["connected_clients"] == 3

    def test_get_stats_memory_rounding(self, connected_manager, mock_client):
        """内存单位转换正确."""
        mock_client.info.return_value = {
            "used_memory": 2097152,
            "redis_version": "7.0",
            "connected_clients": 1,
        }
        mock_client.scan_iter.return_value = iter([])
        result = connected_manager.get_stats()
        assert result["used_memory_mb"] == 2.0

    def test_get_stats_with_zero_keys(self, connected_manager, mock_client):
        """零键时统计."""
        mock_client.scan_iter.return_value = iter([])
        result = connected_manager.get_stats()
        assert result["keys"]["scheduler_lock"] == 0
        assert result["keys"]["cooldown"] == 0
        assert result["keys"]["heartbeat"] == 0
        assert result["keys"]["runtime_state"] == 0


class TestFlush:
    """清空测试."""

    def test_flush_all_deletes_growth_keys(self, connected_manager, mock_client):
        """flush_all 删除所有 growth:* 键."""
        mock_client.scan_iter.return_value = iter([
            "growth:key1",
            "growth:key2",
            "growth:key3",
            "growth:key4",
        ])
        connected_manager.flush_all()
        assert mock_client.delete.call_count == 4

    def test_flush_all_no_keys(self, connected_manager, mock_client):
        """无键时 flush_all 不报错."""
        mock_client.scan_iter.return_value = iter([])
        connected_manager.flush_all()
        mock_client.delete.assert_not_called()


# ═══════════════════════════════════════════════════════════
# 8. Worker ID & Repr
# ═══════════════════════════════════════════════════════════

class TestWorkerIdAndRepr:
    """Worker ID 和 Repr 测试."""

    def test_custom_worker_id(self, mock_client):
        """自定义 worker_id."""
        _mock_redis.Redis.from_url.reset_mock()
        _mock_redis.Redis.from_url.return_value = mock_client
        manager = RedisStateManager(worker_id="custom_worker")
        manager.connect()
        assert manager.worker_id == "custom_worker"

    def test_auto_generated_worker_id(self):
        """自动生成 worker_id."""
        manager = RedisStateManager()
        assert manager.worker_id.startswith("worker_")
        assert len(manager.worker_id) > 7

    def test_repr_connected(self, connected_manager):
        """已连接时 repr."""
        r = repr(connected_manager)
        assert "test_worker_01" in r
        assert "connected=True" in r

    def test_repr_disconnected(self):
        """未连接时 repr."""
        manager = RedisStateManager(worker_id="w1")
        r = repr(manager)
        assert "w1" in r
        assert "connected=False" in r