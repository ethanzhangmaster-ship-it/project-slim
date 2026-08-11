"""Tests for E13.5 Release Agent (staged rollout controller).

Uses a stateful fake GooglePlayRealClient so the full 5%->20%->50%->100%
ladder can be exercised without touching the network. Gate routing is
verified against SIMULATION / SHADOW / PRODUCTION + unlock.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent, ReleasePolicy,
)
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage,
)
from monetization.providers.models import SandboxMode


class FakeClient:
    """In-memory Google Play client with a mutable track store."""
    def __init__(self, owned=True):
        self.calls = []
        self.tracks: dict = {}          # pkg -> {status, user_fraction}
        self.owned = owned

    def check_status(self, pkg):
        return {"success": self.owned, "status": "published",
                "version": "1", "play_status": "inProgress"}

    def get_track_status(self, pkg, track="production"):
        t = self.tracks.get(pkg)
        if t is None:
            return {"success": True, "track": track, "status": "empty",
                    "releases": [], "user_fraction": 0.0}
        return {"success": True, "track": track, "status": t["status"],
                "releases": [{"status": t["status"],
                              "userFraction": t["user_fraction"]}],
                "user_fraction": t["user_fraction"]}

    def set_rollout(self, pkg, track="production", user_fraction=0.05, **kw):
        self.calls.append(("set_rollout", pkg, user_fraction))
        self.tracks[pkg] = {"status": "inProgress",
                            "user_fraction": float(user_fraction)}
        return {"success": True, "package_name": pkg, "track": track,
                "user_fraction": float(user_fraction), "detail": "ok"}

    def halt_rollout(self, pkg, track="production"):
        self.calls.append(("halt_rollout", pkg))
        cur = self.tracks.get(pkg, {}).get("user_fraction", 0.0)
        self.tracks[pkg] = {"status": "halted", "user_fraction": cur}
        return {"success": True, "package_name": pkg, "track": track,
                "detail": "halted"}


def _healthy_metrics():
    return {"crash_rate": 0.3, "anr_rate": 0.2, "d1_retention": 0.42}


def _make_agent(sandbox, auto_pilot=True, unlock=True, policy=None,
                state_dir=None, metrics_provider=None):
    fc = FakeClient()
    conn = PlayConnector(client=fc, sandbox=sandbox, auto_pilot=auto_pilot)
    if unlock:
        conn.unlock_release()
    agent = ReleaseAgent(conn, policy=policy or ReleasePolicy(),
                         state_path=str(state_dir / "release_state.json")
                         if state_dir else None,
                         metrics_provider=metrics_provider)
    return agent, fc


# --------------------------------------------------------------------------- #
# decision logic (no write)
# --------------------------------------------------------------------------- #
def test_not_in_rollout_when_empty():
    agent, fc = _make_agent(SandboxMode.PRODUCTION)
    d = agent.evaluate("com.x.empty", metrics=_healthy_metrics())
    assert d["recommendation"] == "not_in_rollout"


def test_released_when_at_100():
    agent, fc = _make_agent(SandboxMode.PRODUCTION)
    fc.tracks["com.x.full"] = {"status": "completed", "user_fraction": 1.0}
    d = agent.evaluate("com.x.full", metrics=_healthy_metrics())
    assert d["recommendation"] == "released"


def test_halt_recommendation_on_bad_metrics():
    agent, fc = _make_agent(SandboxMode.PRODUCTION)
    fc.tracks["com.x.bad"] = {"status": "inProgress", "user_fraction": 0.05}
    bad = {"crash_rate": 5.0, "anr_rate": 0.2}  # crash gate violated
    d = agent.evaluate("com.x.bad", metrics=bad)
    assert d["recommendation"] == "halt"
    assert "crash" in d["reason"].lower()


def test_hold_when_window_not_elapsed():
    agent, fc = _make_agent(SandboxMode.PRODUCTION)
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime.now(timezone.utc)
    # last advance 1h ago, observe 48h -> window not elapsed
    agent._record("com.x.5", stage_index=0,
                  last_advance_at=(now - timedelta(hours=1)).isoformat(),
                  status="rolling")
    d = agent.evaluate("com.x.5", metrics=_healthy_metrics(), now=now)
    assert d["recommendation"] == "hold"
    assert d["window_elapsed"] is False


def test_hold_when_metrics_missing_and_required():
    agent, fc = _make_agent(SandboxMode.PRODUCTION,
                            policy=ReleasePolicy(require_metrics=True))
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    d = agent.evaluate("com.x.5", metrics=None)
    assert d["recommendation"] == "hold"
    assert "metric" in d["reason"].lower()


def test_advance_recommended_when_healthy_and_window():
    agent, fc = _make_agent(SandboxMode.PRODUCTION)
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime.now(timezone.utc)
    agent._record("com.x.5", stage_index=0,
                  last_advance_at=(now - timedelta(days=3)).isoformat(),
                  status="rolling")
    d = agent.evaluate("com.x.5", metrics=_healthy_metrics(), now=now)
    assert d["recommendation"] == "advance"
    assert d["next_fraction"] == 0.20


# --------------------------------------------------------------------------- #
# gate routing
# --------------------------------------------------------------------------- #
def test_simulation_never_calls_api():
    agent, fc = _make_agent(SandboxMode.SIMULATION, unlock=False)
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.advance("com.x.5", apply=True, metrics=_healthy_metrics())
    # SIM mode must never touch the real API, regardless of recommendation.
    assert res.real_api_called is False
    assert res.stage in (GateStage.RECOMMEND, GateStage.BLOCKED)
    assert len(fc.calls) == 0  # nothing written


def test_production_blocked_without_unlock():
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=False)
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.advance("com.x.5", apply=True, metrics=_healthy_metrics())
    assert res.stage in (GateStage.BLOCKED, GateStage.APPROVE)
    assert len(fc.calls) == 0


def test_production_advance_executes_and_records(tmp_path):
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=True,
                            state_dir=tmp_path)
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime.now(timezone.utc)
    agent._record("com.x.5", stage_index=0,
                  last_advance_at=(now - timedelta(days=3)).isoformat(),
                  status="rolling")
    res = agent.advance("com.x.5", apply=True,
                         metrics=_healthy_metrics(), now=now)
    assert res.stage == GateStage.EXECUTE
    assert res.ok is True
    assert res.real_api_called is True
    assert fc.tracks["com.x.5"]["user_fraction"] == 0.20
    # state persisted so next evaluate sees 20%
    d = agent.evaluate("com.x.5", metrics=_healthy_metrics(), now=now)
    assert d["track_fraction"] == 0.20
    assert d["stage_index"] == 1


def test_halt_executes_in_production(tmp_path):
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=True,
                            state_dir=tmp_path)
    fc.tracks["com.x.bad"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.halt("com.x.bad", apply=True)
    assert res.stage == GateStage.EXECUTE
    assert fc.tracks["com.x.bad"]["status"] == "halted"


# --------------------------------------------------------------------------- #
# full ladder 5 -> 20 -> 50 -> 100
# --------------------------------------------------------------------------- #
def test_full_ladder(tmp_path):
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=True,
                            state_dir=tmp_path)
    pkg = "com.x.ladder"
    fc.tracks[pkg] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    # first advance needs a prior observation window recorded
    agent._record(pkg, stage_index=0,
                  last_advance_at=(now - timedelta(days=3)).isoformat(),
                  status="rolling")
    fractions = [0.05, 0.20, 0.50, 1.00]
    for i in range(1, 4):
        # advance the observation window forward each iteration
        cur = agent._state_for(pkg)
        agent._record(pkg, stage_index=cur["stage_index"],
                      last_advance_at=(now - timedelta(days=3)).isoformat())
        res = agent.advance(pkg, apply=True, metrics=_healthy_metrics(), now=now)
        assert res.ok, res.detail
        assert fc.tracks[pkg]["user_fraction"] == fractions[i]
        # bump window again for next loop
        agent._record(pkg, stage_index=i,
                      last_advance_at=(now - timedelta(days=3)).isoformat())
    d = agent.evaluate(pkg, metrics=_healthy_metrics(), now=now)
    assert d["recommendation"] == "released"
    assert fc.tracks[pkg]["user_fraction"] == 1.00


def test_run_daily_only_recommends_without_apply():
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=True,
                            metrics_provider=lambda p: _healthy_metrics())
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime.now(timezone.utc)
    agent._record("com.x.5", stage_index=0,
                  last_advance_at=(now - timedelta(days=3)).isoformat())
    out = agent.run_daily(["com.x.5"], apply=False, now=now)
    assert out[0]["recommendation"] == "advance"
    assert out[0]["action_taken"] == "advance"  # proposed, not executed
    assert out[0]["executed"] is None
    assert len(fc.calls) == 0


def test_run_daily_executes_with_apply():
    agent, fc = _make_agent(SandboxMode.PRODUCTION, unlock=True,
                            metrics_provider=lambda p: _healthy_metrics())
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    now = datetime.now(timezone.utc)
    agent._record("com.x.5", stage_index=0,
                  last_advance_at=(now - timedelta(days=3)).isoformat())
    out = agent.run_daily(["com.x.5"], apply=True, now=now)
    assert out[0]["action_taken"] == "advanced"
    assert fc.tracks["com.x.5"]["user_fraction"] == 0.20
