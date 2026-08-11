"""E13.5 — Promotion-readiness tests.

Verifies the closed loop between the persistent tester pool
(TesterPoolAgent) and the per-app 14-day closed-testing clock
(tester_community.eligibility), surfaced as "can_promote"
(pool >= 12 AND 14-day clock done).

Isolated via the same env vars the production code honours:
  LAUNCHFORGE_PLAY_TESTER_POOL      -> tester_pool.json
  LAUNCHFORGE_PLAY_TESTER_AUDIT    -> tester_pool_audit.jsonl
  LAUNCHFORGE_TESTER_PROGRESS      -> tester_progress.json
"""
import json

import pytest

from operation.publishing_factory.play_runtime.tester_pool_agent import (
    TesterPoolAgent, MIN_POOL, promotion_readiness, render_promotion_markdown,
)
from operation.publishing_factory.tester_community import (
    eligibility as tc_elig)

POOL_ENV = "LAUNCHFORGE_PLAY_TESTER_POOL"
AUDIT_ENV = "LAUNCHFORGE_PLAY_TESTER_AUDIT"
PROG_ENV = "LAUNCHFORGE_TESTER_PROGRESS"


def _seed_pool(path, n: int):
    data = {"testers": [
        {"email": f"t{i}@example.com", "groups": [], "name": "",
         "note": "", "added_at": "2026-01-01T00:00:00+00:00"}
        for i in range(n)]}
    path.write_text(json.dumps(data), encoding="utf-8")


def _seed_progress(path, state: dict):
    path.write_text(json.dumps(state), encoding="utf-8")


class _FakeRes:
    def __init__(self, ok=True, data=None, stage="EXECUTE", detail=""):
        self.ok = ok
        self.data = data or {}
        self.stage = stage
        self.detail = detail
        self.error = ""


class _FakeConnector:
    def __init__(self, current_emails=None):
        self.current_emails = current_emails or []
        self.invited = []

    def read_testers(self, package_name, track="closed"):
        return _FakeRes(ok=True,
                        data={"tester_emails": list(self.current_emails)})

    def invite_testers(self, package_name, tester_emails=None, apply=False):
        self.invited.append((package_name, list(tester_emails or []), apply))
        return _FakeRes(ok=True)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    pool = tmp_path / "pool.json"
    audit = tmp_path / "audit.jsonl"
    prog = tmp_path / "progress.json"
    monkeypatch.setenv(POOL_ENV, str(pool))
    monkeypatch.setenv(AUDIT_ENV, str(audit))
    monkeypatch.setenv(PROG_ENV, str(prog))
    return pool, audit, prog


def test_empty_pool_no_promotion(isolated):
    rep = promotion_readiness()
    assert rep["pool_size"] == 0
    assert rep["pool_ok"] is False
    assert rep["promote_count"] == 0


def test_promote_when_pool_ok_and_clock_done(isolated):
    pool, _, prog = isolated
    _seed_pool(pool, 12)
    _seed_progress(prog, {"com.ready": {"invited_at": "2026-01-01",
                                        "tester_count": 12}})
    rep = promotion_readiness()
    assert rep["pool_ok"] is True
    apps = {a["package_name"]: a for a in rep["apps"]}
    assert apps["com.ready"]["can_promote"] is True
    assert "com.ready" in rep["promote_ready"]


def test_no_promote_when_pool_short(isolated):
    pool, _, prog = isolated
    _seed_pool(pool, 5)  # below MIN_POOL
    _seed_progress(prog, {"com.ready": {"invited_at": "2026-01-01",
                                        "tester_count": 12}})
    rep = promotion_readiness()
    assert rep["pool_ok"] is False
    apps = {a["package_name"]: a for a in rep["apps"]}
    assert apps["com.ready"]["can_promote"] is False
    assert rep["promote_count"] == 0


def test_run_daily_starts_clock_when_union_ge_12(isolated):
    pool, _, prog = isolated
    _seed_pool(pool, 12)
    fc = _FakeConnector(current_emails=[])
    ag = TesterPoolAgent(fc)
    out = ag.run_daily(["com.new"], apply=True)
    assert out["total_invited"] == 12
    # the 14-day clock must auto-start in tester_community eligibility
    st = tc_elig.get("com.new")
    assert st["invited_at"] is not None
    assert st["tester_count"] >= MIN_POOL
    # and the audit records it
    assert out["per_package"]["com.new"].get("clock_started") is True


def test_run_daily_no_clock_when_short(isolated):
    pool, _, prog = isolated
    _seed_pool(pool, 5)  # cannot satisfy the 12-tester gate
    fc = _FakeConnector(current_emails=[])
    ag = TesterPoolAgent(fc)
    ag.run_daily(["com.new"], apply=True)
    st = tc_elig.get("com.new")
    assert st["invited_at"] is None  # clock must NOT start


def test_render_markdown(isolated):
    pool, _, prog = isolated
    _seed_pool(pool, 12)
    _seed_progress(prog, {"com.ready": {"invited_at": "2026-01-01",
                                        "tester_count": 12}})
    rep = promotion_readiness()
    md = render_promotion_markdown(rep)
    assert "可晋升" in md
    assert "com.ready" in md
    # empty case -> "暂无"
    md2 = render_promotion_markdown(promotion_readiness([]))
    assert "暂无" in md2
