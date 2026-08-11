"""E13.5 — Health Agent (Vitals Monitor) tests + real_client.get_vitals seam.

No network: the Health Agent is driven by an injected ``vitals_provider``,
and the real client's Vitals read is exercised through its ``arm_vitals`` /
``_call_reporting`` seams.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from monetization.providers.models import SandboxMode

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.health_agent import (
    HealthAgent, HealthPolicy, HealthReport,
)
from operation.publishing_factory.play_runtime.health_audit import (
    audit_path, latest_board,
)
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage,
)
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent, ReleasePolicy,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)


class FakeClient:
    """In-memory stand-in for GooglePlayRealClient (owned app)."""
    def __init__(self, owned: bool = True, vitals: dict = None):
        self.owned = owned
        self.calls = []
        self._vitals = vitals or {
            "package_name": "x", "crash_rate": 0.5, "anr_rate": 0.2,
            "d1_retention": None, "window_days": 7,
            "source": "fake", "fetched_at": "t"}

    def check_status(self, package_name: str):
        if self.owned:
            return {"success": True, "status": "draft", "play_status": "draft"}
        return {"success": False, "status_code": 404,
                "error": "package not found in account"}

    def get_vitals(self, package_name: str, window_days: int = 7):
        self.calls.append(("get_vitals", package_name, window_days))
        v = dict(self._vitals)
        v["package_name"] = package_name
        return v

    def halt_rollout(self, package_name, track="production"):
        self.calls.append(("halt_rollout", package_name, track))
        return {"success": True, "detail": "halted"}

    def get_track_status(self, package_name, track="production"):
        self.calls.append(("get_track_status", package_name, track))
        return {"success": True, "track": track, "status": "inProgress",
                "user_fraction": 0.05, "version_code": 10, "releases": [
                    {"status": "inProgress", "userFraction": 0.05,
                     "versionCode": 10}]}


PKG = "com.ofwsalary.ofwcalculator"


def _agent(vitals, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
           client=None, health_file=None):
    if health_file is not None:
        os.environ["LAUNCHFORGE_PLAY_HEALTH"] = str(health_file)
    conn = PlayConnector(
        client=client or FakeClient(),
        sandbox=sandbox, auto_pilot=auto_pilot)
    return HealthAgent(conn, policy=HealthPolicy(),
                       vitals_provider=lambda p, w: vitals)


# --------------------------------------------------------------------------- #
# scoring / evaluation
def test_evaluate_healthy():
    a = _agent({"crash_rate": 0.5, "anr_rate": 0.2, "d1_retention": None})
    r = a.evaluate(PKG)
    assert r.recommendation == "healthy"
    assert r.crash_rate == 0.5 and r.anr_rate == 0.2


def test_evaluate_watch():
    a = _agent({"crash_rate": 0.9, "anr_rate": 0.1, "d1_retention": None})
    r = a.evaluate(PKG)
    assert r.recommendation == "watch"
    assert any("near" in x for x in r.reasons)


def test_evaluate_halt_crash():
    a = _agent({"crash_rate": 2.0, "anr_rate": 0.1, "d1_retention": None})
    r = a.evaluate(PKG)
    assert r.recommendation == "halt"
    assert any("crash_rate" in x for x in r.reasons)


def test_evaluate_halt_anr():
    a = _agent({"crash_rate": 0.1, "anr_rate": 1.0, "d1_retention": None})
    r = a.evaluate(PKG)
    assert r.recommendation == "halt"
    assert any("anr_rate" in x for x in r.reasons)


def test_evaluate_no_data():
    a = _agent(None)
    r = a.evaluate(PKG)
    assert r.recommendation == "no_data"


def test_evaluate_min_d1_halt():
    pol = HealthPolicy(min_d1_retention=0.30)
    conn = PlayConnector(client=FakeClient(), sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    a = HealthAgent(conn, policy=pol,
                    vitals_provider=lambda p, w: {
                        "crash_rate": 0.1, "anr_rate": 0.1, "d1_retention": 0.20})
    r = a.evaluate(PKG)
    assert r.recommendation == "halt"
    assert any("d1_retention" in x for x in r.reasons)


# --------------------------------------------------------------------------- #
# Release Agent compatibility (the whole point of this agent)
def test_read_vitals_dict_feeds_release_agent():
    a = _agent({"crash_rate": 2.0, "anr_rate": 0.1, "d1_retention": None})
    d = a.read_vitals_dict(PKG)
    assert set(d.keys()) == {"crash_rate", "anr_rate", "d1_retention"}
    # Release Agent's gate must consume it directly:
    ra = ReleaseAgent(PlayConnector(client=FakeClient(),
                                    sandbox=SandboxMode.PRODUCTION,
                                    auto_pilot=True))
    healthy, reason = ra._healthy(d)
    assert healthy is False and "crash_rate" in reason


def test_read_vitals_dict_none_when_unreadable():
    a = _agent(None)
    assert a.read_vitals_dict(PKG) is None


# --------------------------------------------------------------------------- #
# halt action + safety gates
def test_halt_if_critical_refused_when_healthy():
    a = _agent({"crash_rate": 0.1, "anr_rate": 0.1, "d1_retention": None})
    res = a.halt_if_critical(PKG, apply=True)  # NOT a halt -> refused
    assert res.stage == GateStage.BLOCKED
    assert res.ok is False
    assert res.real_api_called is False


def test_halt_if_critical_locked_without_unlock():
    a = _agent({"crash_rate": 3.0, "anr_rate": 0.1, "d1_retention": None})
    # apply=True but connector NOT unlocked -> APPROVE (refused, no write)
    res = a.halt_if_critical(PKG, apply=True)
    assert res.stage == GateStage.APPROVE
    assert res.real_api_called is False


def test_halt_if_critical_execute_when_unlocked():
    client = FakeClient()
    conn = PlayConnector(client=client, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    conn.unlock_release()
    a = HealthAgent(conn, policy=HealthPolicy(),
                    vitals_provider=lambda p, w: {
                        "crash_rate": 3.0, "anr_rate": 0.1,
                        "d1_retention": None})
    res = a.halt_if_critical(PKG, apply=True)
    assert res.stage == GateStage.EXECUTE
    assert res.ok is True
    assert res.real_api_called is True
    assert ("halt_rollout", PKG, "production") in client.calls


# --------------------------------------------------------------------------- #
# daily sweep + persistence
def test_run_daily_persists_and_halts(tmp_path):
    hf = tmp_path / "health.jsonl"
    os.environ["LAUNCHFORGE_PLAY_HEALTH"] = str(hf)
    client = FakeClient()
    conn = PlayConnector(client=client, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    conn.unlock_release()
    a = HealthAgent(conn, policy=HealthPolicy(),
                    vitals_provider=lambda p, w: {
                        "crash_rate": 5.0, "anr_rate": 0.1,
                        "d1_retention": None})
    out = a.run_daily([PKG], apply=True, window_days=7)
    assert len(out) == 1
    assert out[0]["recommendation"] == "halt"
    assert out[0]["action_taken"] == "halted"
    # persisted to the env-overridden health.jsonl
    board = latest_board()
    assert PKG in board
    assert board[PKG]["recommendation"] == "halt"


def test_run_daily_no_write_when_healthy(tmp_path):
    hf = tmp_path / "health.jsonl"
    os.environ["LAUNCHFORGE_PLAY_HEALTH"] = str(hf)
    a = _agent({"crash_rate": 0.1, "anr_rate": 0.1, "d1_retention": None},
               health_file=hf)
    out = a.run_daily([PKG], apply=True)
    assert out[0]["recommendation"] == "healthy"
    assert out[0]["action_taken"] == "healthy"  # no halt triggered


# --------------------------------------------------------------------------- #
# connector.read_vitals gate routing
def test_read_vitals_simulation_is_safe():
    conn = PlayConnector(client=None, sandbox=SandboxMode.SIMULATION,
                         auto_pilot=False)
    res = conn.read_vitals(PKG)
    assert res.stage == GateStage.RECOMMEND
    assert res.real_api_called is False


def test_read_vitals_production_reads_client():
    client = FakeClient()
    conn = PlayConnector(client=client, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    res = conn.read_vitals(PKG)
    assert res.ok is True
    assert res.real_api_called is True
    assert res.data["crash_rate"] == 0.5
    assert ("get_vitals", PKG, 7) in client.calls


# --------------------------------------------------------------------------- #
# real_client.get_vitals seam
def test_real_client_get_vitals_seam():
    c = GooglePlayRealClient(credential={})
    captured = {}

    def transport(pkg, window):
        captured["pkg"] = pkg
        captured["window"] = window
        return {"package_name": pkg, "crash_rate": 1.5, "anr_rate": 0.3,
                "d1_retention": None, "window_days": window,
                "source": "test", "fetched_at": "t"}

    c.arm_vitals(transport)
    v = c.get_vitals(PKG, window_days=14)
    assert v["crash_rate"] == 1.5
    assert v["anr_rate"] == 0.3
    assert v["d1_retention"] is None
    assert v["window_days"] == 14
    assert captured["pkg"] == PKG and captured["window"] == 14


def test_real_client_query_metric_set_percent_and_parsing():
    c = GooglePlayRealClient(credential={})

    def fake_call(method, path, body=None):
        return {"success": True, "status_code": 200,
                "data": {"dailyMetrics": [{
                    "columns": ["ts", "crashRate"],
                    "rows": [["2026-07-20", {"decimal": "0.005"}],
                             ["2026-07-21", {"decimal": "0.02"}]]}]}}

    c._call_reporting = fake_call
    val = c._query_metric_set(PKG, "crashRateMetricSet", "crashRate")
    assert abs(val - 2.0) < 1e-6  # 0.02 fraction -> 2.0 percent


def test_real_client_query_metric_set_empty_returns_none():
    c = GooglePlayRealClient(credential={})
    c._call_reporting = lambda m, p, b=None: {
        "success": True, "status_code": 200, "data": {"dailyMetrics": []}}
    assert c._query_metric_set(PKG, "crashRateMetricSet", "crashRate") is None
