"""跨机器/跨账号解耦架构单元测试.

覆盖:
  1. state_store: LocalFS 后端读写 (json / jsonl / healthcheck / 原子性)
  2. portable_config: 4 层优先级 + get_secret 安全边界 + dump_safe_snapshot 脱敏
  3. cloud_runner: CLI 参数解析 + healthcheck 路径 + startup_recovery 断点续跑 +
     无参数时的 help 退出码 1
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


# ────────────────────────────────────────────────────────────────
# 1. LocalFS StateStore
# ────────────────────────────────────────────────────────────────

def test_localfs_state_store_roundtrip_json(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    payload = {"a": 1, "b": ["x", "y"], "nested": {"k": "v"}}
    store.write_json("config.json", payload)
    got = store.read_json("config.json")
    assert got == payload


def test_localfs_state_store_read_json_default(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    assert store.read_json("nope.json", default={"foo": "bar"}) == {"foo": "bar"}
    assert store.read_json("nope.json") is None


def test_localfs_state_store_corrupt_file_returns_default(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    (tmp_path / "bad.json").write_text("not { valid } json !!", encoding="utf-8")
    assert store.read_json("bad.json", default=42) == 42


def test_localfs_state_store_jsonl_append_and_read(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    records = [{"i": i, "ts": f"t{i}"} for i in range(5)]
    for r in records:
        store.append_jsonl("hist.jsonl", r)
    all_got = store.read_jsonl("hist.jsonl")
    assert all_got == records
    last_two = store.read_jsonl("hist.jsonl", limit=2)
    assert last_two == records[-2:]
    assert store.read_jsonl("missing.jsonl") == []


def test_localfs_state_store_jsonl_bad_line_skipped(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    # 手搓坏行
    with (tmp_path / "mixed.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"ok":true}\n')
        f.write("this is not json at all\n")
        f.write('{"ok":2}\n')
    got = store.read_jsonl("mixed.jsonl")
    assert len(got) == 2
    assert got[0] == {"ok": True}
    assert got[1] == {"ok": 2}


def test_localfs_state_store_atomic_write_creates_parent_dirs(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    store.write_json("a/b/c/deep.json", {"nested": True})
    assert (tmp_path / "a" / "b" / "c" / "deep.json").is_file()
    assert store.read_json("a/b/c/deep.json") == {"nested": True}


def test_localfs_state_store_exists_and_list_keys(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    store.write_json("a.json", {})
    store.write_json("sub/b.json", {})
    store.append_jsonl("logs/l.jsonl", {"r": 1})
    assert store.exists("a.json")
    assert store.exists("sub/b.json")
    assert store.exists("logs/l.jsonl")
    assert not store.exists("nope.json")
    keys = store.list_keys()
    assert "a.json" in keys
    assert "sub/b.json" in keys
    sub_keys = store.list_keys("sub/")
    assert sub_keys == ["sub/b.json"]


def test_localfs_state_store_directory_traversal_blocked(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    with pytest.raises(ValueError, match="非法 key"):
        store.write_json("../escape.json", {})


def test_localfs_state_store_healthcheck(tmp_path):
    from market_ops.workspace.state_store import LocalFSStateStore
    store = LocalFSStateStore(root_dir=str(tmp_path))
    r = store.health_check()
    assert r["backend"] == "local"
    assert r["ok"] is True
    # probe 文件应该在 .probe/ 目录下并成功写入过
    assert ".probe/" in r["probe"]


def test_state_store_factory_defaults_to_local(monkeypatch, tmp_path):
    # 当 STATE_STORE_BACKEND 未设置时, 工厂返回 LocalFS
    monkeypatch.delenv("STATE_STORE_BACKEND", raising=False)
    monkeypatch.setenv("STATE_STORE_ROOT", str(tmp_path))
    from market_ops.workspace.state_store import get_state_store
    store = get_state_store()
    assert store.backend == "local"


def test_state_store_factory_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("STATE_STORE_BACKEND", "bogus-backend")
    from market_ops.workspace.state_store import get_state_store
    with pytest.raises(ValueError, match="bogus-backend"):
        get_state_store()


# ────────────────────────────────────────────────────────────────
# 2. Portable Config
# ────────────────────────────────────────────────────────────────

@pytest.fixture()
def fresh_config_state(monkeypatch):
    """重置 portable_config 懒加载状态, 每个测试隔离环境."""
    import market_ops.workspace.portable_config as pc
    monkeypatch.setattr(pc, "_INITIALIZED", False)
    # 清空冲突的 env 变量
    for k in list(os.environ.keys()):
        if k.startswith("TESTCFG_"):
            monkeypatch.delenv(k, raising=False)
    yield
    monkeypatch.setattr(pc, "_INITIALIZED", False)


def test_portable_config_env_is_highest_priority(fresh_config_state, monkeypatch, tmp_path):
    """即使有 .env / .env.local 文件, env 变量优先级最高."""
    # 先伪造 .env 文件 (低优先级)
    dotenv = tmp_path / ".env"
    dotenv.write_text("TESTCFG_FOO=from_dotenv\n", encoding="utf-8")
    # mock project_root 返回 tmp_path
    import market_ops.workspace.portable_config as pc
    monkeypatch.setattr(pc, "_project_root", lambda: tmp_path)
    # 再设 env (高优先级)
    monkeypatch.setenv("TESTCFG_FOO", "from_env")
    assert pc.get("TESTCFG_FOO") == "from_env"


def test_portable_config_int_bool_parsing(fresh_config_state, monkeypatch):
    import market_ops.workspace.portable_config as pc
    monkeypatch.setenv("TESTCFG_N", "42")
    monkeypatch.setenv("TESTCFG_B_YES", "yes")
    monkeypatch.setenv("TESTCFG_B_NO", "0")
    monkeypatch.setenv("TESTCFG_B_EMPTY", "")
    assert pc.get_int("TESTCFG_N") == 42
    assert pc.get_int("TESTCFG_MISSING", 7) == 7
    assert pc.get_bool("TESTCFG_B_YES") is True
    assert pc.get_bool("TESTCFG_B_NO") is False
    # 空字符串走 default
    assert pc.get_bool("TESTCFG_B_EMPTY", default=True) is True


def test_portable_config_get_secret_only_from_env_not_dotenv(
    fresh_config_state, monkeypatch, tmp_path
):
    """get_secret 不会从 .env 里读密钥 (避免误提交)."""
    (tmp_path / ".env").write_text(
        "TESTCFG_MY_SECRET=accidentally_checked_in_value\n",
        encoding="utf-8",
    )
    import market_ops.workspace.portable_config as pc
    monkeypatch.setattr(pc, "_project_root", lambda: tmp_path)
    # 环境变量里没有该 key
    assert pc.get_secret("TESTCFG_MY_SECRET") is None
    # 但 get() 能从 .env 读到 (因为 .env 可以放非敏感默认值)
    assert pc.get("TESTCFG_MY_SECRET") == "accidentally_checked_in_value"
    # 当 env 里设了, get_secret 就能拿到
    monkeypatch.setenv("TESTCFG_MY_SECRET", "real_secret_from_env")
    assert pc.get_secret("TESTCFG_MY_SECRET") == "real_secret_from_env"


def test_portable_config_dump_safe_snapshot_redacts_secrets(
    fresh_config_state, monkeypatch
):
    import market_ops.workspace.portable_config as pc
    monkeypatch.setenv("MARKET_OPS_MY_OPENAI_KEY", "sk-abcdef12345")
    monkeypatch.setenv("STATE_STORE_BACKEND", "gist")
    snap = pc.dump_safe_snapshot()
    # 含 KEY → 脱敏
    assert snap["MARKET_OPS_MY_OPENAI_KEY"] == "<REDACTED>"
    # 非敏感 → 原值
    assert snap["STATE_STORE_BACKEND"] == "gist"


# ────────────────────────────────────────────────────────────────
# 3. Cloud Runner
# ────────────────────────────────────────────────────────────────

def test_cloud_runner_no_args_prints_help_and_exits_1(monkeypatch, tmp_path):
    import market_ops.workspace.cloud_runner as cr
    monkeypatch.setenv("STATE_STORE_ROOT", str(tmp_path))
    monkeypatch.setattr(cr, "_load_dotenv_if_available", lambda: None)
    rc = cr.main(argv=[])
    assert rc == 1


def test_cloud_runner_healthcheck_localfs_ok(monkeypatch, tmp_path, capsys):
    import market_ops.workspace.cloud_runner as cr
    monkeypatch.delenv("STATE_STORE_BACKEND", raising=False)
    monkeypatch.setenv("STATE_STORE_ROOT", str(tmp_path))
    monkeypatch.setattr(cr, "_load_dotenv_if_available", lambda: None)
    rc = cr.main(argv=["--healthcheck", "--no-dotenv"])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["backend"] == "local"
    assert data["ok"] is True


def test_cloud_runner_startup_recovery_resets_stale_lock(monkeypatch, tmp_path):
    import time
    import market_ops.workspace.cloud_runner as cr
    monkeypatch.delenv("STATE_STORE_BACKEND", raising=False)
    monkeypatch.setenv("STATE_STORE_ROOT", str(tmp_path))
    monkeypatch.setattr(cr, "_load_dotenv_if_available", lambda: None)
    # 写一个超过 1 小时的 in_progress 锁
    (tmp_path / ".locks").mkdir(exist_ok=True)
    stale = {
        "status": "in_progress",
        "started_ts": time.time() - 7200,  # 2 小时前
        "game_id": "com.born2play.biblequiz",
        "retry_count": 0,
    }
    (tmp_path / ".locks" / "abc.lock.json").write_text(
        json.dumps(stale), encoding="utf-8"
    )
    # 先执行 healthcheck 触发 startup_recovery 路径
    cr.main(argv=["--healthcheck", "--no-dotenv"])
    # 锁文件里的状态应该变了
    updated = json.loads((tmp_path / ".locks" / "abc.lock.json").read_text(encoding="utf-8"))
    assert updated["status"] == "recovered_pending"
    assert updated["retry_count"] == 1
    assert "recovered_at" in updated
    # 应该有 recovery_log.jsonl
    rl = tmp_path / "aso_deploy" / "recovery_log.jsonl"
    assert rl.is_file()
    lines = rl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["interrupted_tasks_recovered"] == 1


def test_cloud_runner_argparse_game_and_multichannel(monkeypatch, tmp_path):
    """参数组合应解析成功, 即使依赖跑不动, 也不会解析崩."""
    from market_ops.workspace.cloud_runner import _build_arg_parser
    p = _build_arg_parser()
    ns = p.parse_args([
        "--game", "com.foo.bar",
        "--multichannel-plan", "com.foo.bar",
        "--force-new-variant",
        "--dashboard",
        "--no-dotenv",
    ])
    assert ns.game == "com.foo.bar"
    assert ns.multichannel_plan == "com.foo.bar"
    assert ns.force_new_variant is True
    assert ns.dashboard is True


# ────────────────────────────────────────────────────────────────
# 4. 状态存储工厂在 gist/s3 环境变量缺失时应给出明确错误
# ────────────────────────────────────────────────────────────────

def test_gist_backend_without_token_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GIST_TOKEN", raising=False)
    from market_ops.workspace.state_store import GistStateStore
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN 或 GIST_TOKEN"):
        GistStateStore(gist_id="fake-id")
