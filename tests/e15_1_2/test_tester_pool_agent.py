"""Tests for the E13.5 Tester Pool Agent.

Covers: pool CRUD, invite diff/union (preserves manually-added testers),
run_daily idempotency, and a CLI smoke. Uses a stateful fake connector so
re-runs prove the UNION strategy never clobbers or duplicates.
"""
import os
import sys

import pytest

# Ensure project root importable when run under -m pytest from launchforge/.
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from operation.publishing_factory.play_runtime.tester_pool_agent import (  # noqa: E402
    TesterPoolAgent, MIN_POOL, pool_path, audit_path, summary,
)
from operation.publishing_factory.play_runtime.tester_pool_cli import main as cli_main  # noqa: E402


class FakeResult:
    def __init__(self, ok=True, data=None, detail="", error="", stage="EXECUTE"):
        self.ok = ok
        self.data = data or {}
        self.detail = detail
        self.error = error
        self.stage = stage


class StatefulFakeConnector:
    """Mimics PlayConnector: remembers invited testers per package so a
    second read reports them as already-present (proving idempotency)."""

    def __init__(self):
        self.track = {}          # pkg -> set(emails)
        self.invite_calls = []

    def read_testers(self, package_name, track="closed"):
        return FakeResult(
            ok=True,
            data={"tester_emails": list(self.track.get(package_name, set())),
                  "groups": []})

    def invite_testers(self, package_name, tester_emails=None,
                       tester_groups=None, apply=False):
        self.invite_calls.append(
            (package_name, sorted(tester_emails or []), apply))
        self.track.setdefault(package_name, set()).update(tester_emails or [])
        return FakeResult(ok=True,
                          data={"tester_emails": list(tester_emails or [])})


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    pool = tmp_path / "tester_pool.json"
    audit = tmp_path / "tester_pool_audit.jsonl"
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL", str(pool))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_AUDIT", str(audit))
    # fresh agents
    return TesterPoolAgent()


def test_add_invalid_email(isolated):
    res = isolated.add_tester("not-an-email")
    assert res["ok"] is False
    assert "invalid" in res["error"]


def test_add_and_dedupe(isolated):
    r1 = isolated.add_tester("a@x.com")
    assert r1["ok"] and not r1.get("already")
    r2 = isolated.add_tester("A@X.COM")  # case-insensitive dedupe
    assert r2["ok"] and r2.get("already")
    assert isolated.pool_size() == 1


def test_remove(isolated):
    isolated.add_tester("a@x.com")
    assert isolated.remove_tester("a@x.com")["ok"]
    assert isolated.pool_size() == 0
    assert isolated.remove_tester("a@x.com")["ok"] is False


def test_meets_minimum(isolated):
    for i in range(MIN_POOL):
        isolated.add_tester(f"u{i}@x.com")
    assert isolated.meets_minimum() is True
    assert isolated.pool_size() == MIN_POOL


def test_propose_diff_and_union(isolated):
    isolated.add_tester("a@x.com")
    isolated.add_tester("b@x.com")
    fc = StatefulFakeConnector()
    # pre-seed a manual tester NOT in the pool — must be preserved in union
    fc.track["com.pkg"] = {"manual@x.com"}
    ag = TesterPoolAgent(fc)
    prop = ag.propose_invite("com.pkg")
    assert set(prop["missing"]) == {"a@x.com", "b@x.com"}
    assert set(prop["union_to_put"]) == {"a@x.com", "b@x.com", "manual@x.com"}
    assert prop["short_by"] == max(0, MIN_POOL - 3)


def test_run_daily_idempotent(isolated):
    isolated.add_tester("a@x.com")
    isolated.add_tester("b@x.com")
    fc = StatefulFakeConnector()
    ag = TesterPoolAgent(fc)

    out1 = ag.run_daily(["com.pkg"], apply=True)
    assert out1["total_invited"] == 2
    assert out1["per_package"]["com.pkg"]["invited"] == ["a@x.com", "b@x.com"]
    assert len(fc.invite_calls) == 1
    # union PUT contained exactly the two pool members (track was empty)
    assert fc.invite_calls[0][1] == ["a@x.com", "b@x.com"]

    # second run: track now reports a@x.com,b@x.com present -> nothing missing
    out2 = ag.run_daily(["com.pkg"], apply=True)
    assert out2["total_invited"] == 0
    assert out2["per_package"]["com.pkg"]["invited"] == []
    assert len(fc.invite_calls) == 1  # unchanged — idempotent


def test_run_daily_preserves_manual(isolated):
    isolated.add_tester("a@x.com")
    fc = StatefulFakeConnector()
    fc.track["com.pkg"] = {"manual@x.com"}   # manual tester already there
    ag = TesterPoolAgent(fc)
    ag.run_daily(["com.pkg"], apply=True)
    # the PUT must include the manual tester so it isn't clobbered
    assert "manual@x.com" in fc.invite_calls[0][1]
    assert set(fc.invite_calls[0][1]) == {"a@x.com", "manual@x.com"}


def test_summary_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL",
                       str(tmp_path / "p.json"))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_AUDIT",
                       str(tmp_path / "a.jsonl"))
    s = summary()
    assert s["pool_size"] == 0
    assert s["meets_minimum"] is False
    assert s["short_by"] == MIN_POOL


def test_cli_add_list_summary(tmp_path, monkeypatch):
    pool = tmp_path / "p.json"
    audit = tmp_path / "a.jsonl"
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL", str(pool))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_AUDIT", str(audit))

    assert cli_main(["add", "z@y.com"]) == 0
    assert cli_main(["add", "z@y.com"]) == 0   # dedup, still 0
    assert cli_main(["list"]) == 0
    assert cli_main(["summary"]) == 0
    # invalid email -> non-zero
    assert cli_main(["add", "bad"]) == 1
    # remove
    assert cli_main(["remove", "z@y.com"]) == 0
    assert cli_main(["remove", "z@y.com"]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
