"""E15.2 — Reality -> Decision -> Execution 集成测试.

覆盖:
  * ReleaseAgent.execute_decision 三映射 (INCREASE/HALT/HOLD)
  * 决策执行仍受 PlayConnector 三级门 + RELEASE unlock 约束
  * HealthAgent.evaluate_release_risk -> ReleaseRiskScore
  * 端到端: FakeClient -> RealityConnector -> DecisionEngine -> ReleaseAgent
"""
from __future__ import annotations

import pytest

from monetization.providers.models import SandboxMode
from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.decision.engine import (
    PlayDecisionEngine,
)
from operation.publishing_factory.play_runtime.decision.models import (
    PlayAction,
    PlayDecision,
)
from operation.publishing_factory.play_runtime.health_agent import (
    HealthAgent, HealthPolicy, ReleaseRiskScore,
)
from operation.publishing_factory.play_runtime.models import GateStage
from operation.publishing_factory.play_runtime.reality.connector import (
    PlayRealityConnector,
)
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent, ReleasePolicy,
)


class FakeClient:
    """In-memory Google Play client (与 e15_1_2 同款契约)."""

    def __init__(self):
        self.calls = []
        self.tracks = {}   # pkg -> {status, user_fraction}
        self.vitals = {}   # pkg -> dict
        self.reviews = {}  # pkg -> dict

    def check_status(self, pkg):
        return {"success": True, "status": "published",
                "version": "1", "play_status": "inProgress"}

    def get_track_status(self, pkg, track="production"):
        t = self.tracks.get(pkg)
        if t is None:
            return {"success": True, "track": track, "status": "empty",
                    "releases": [], "user_fraction": 0.0}
        return {"success": True, "track": track, "status": t["status"],
                "releases": [], "user_fraction": t["user_fraction"],
                "version_code": t.get("version_code")}

    def get_vitals(self, pkg, window_days=7):
        return self.vitals.get(pkg) or {}

    def get_reviews(self, pkg, max_results=50):
        return self.reviews.get(pkg) or {"reviews": [], "count": 0}

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


def _make_release_agent(tmp_path, *, unlock=True):
    fc = FakeClient()
    conn = PlayConnector(client=fc, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    if unlock:
        conn.unlock_release()
    policy = ReleasePolicy(observe_hours=0)  # 测试不等观察窗
    agent = ReleaseAgent(conn, policy=policy,
                         state_path=str(tmp_path / "release_state.json"))
    return agent, fc


def _decision(pkg, action, reason="test"):
    return PlayDecision(package_name=pkg, action=action,
                        confidence=0.9, reason=reason)


# --------------------------------------------------------------------------- #
# execute_decision 映射
# --------------------------------------------------------------------------- #
def test_execute_decision_increase_advances(tmp_path):
    agent, fc = _make_release_agent(tmp_path)
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05}
    metrics = {"crash_rate": 0.1, "anr_rate": 0.05, "d1_retention": 30.0}
    res = agent.execute_decision(
        _decision("com.game.a", PlayAction.INCREASE_ROLLOUT),
        apply=True, metrics=metrics)
    assert res.ok and res.stage == GateStage.EXECUTE
    assert ("set_rollout", "com.game.a", 0.20) in fc.calls


def test_execute_decision_halt_halts(tmp_path):
    agent, fc = _make_release_agent(tmp_path)
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.execute_decision(
        _decision("com.game.a", PlayAction.HALT_RELEASE), apply=True)
    assert res.ok and res.stage == GateStage.EXECUTE
    assert ("halt_rollout", "com.game.a") in fc.calls


def test_execute_decision_hold_is_noop(tmp_path):
    agent, fc = _make_release_agent(tmp_path)
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.execute_decision(
        _decision("com.game.a", PlayAction.HOLD_ROLLOUT), apply=True)
    assert res.ok
    assert res.real_api_called is False
    assert fc.calls == []  # 完全没有 API 调用


def test_execute_decision_respects_release_gate(tmp_path):
    # 未 unlock -> 即使 apply=True 也被门挡住
    agent, fc = _make_release_agent(tmp_path, unlock=False)
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05}
    res = agent.execute_decision(
        _decision("com.game.a", PlayAction.HALT_RELEASE), apply=True)
    assert res.real_api_called is False
    assert fc.calls == []


def test_execute_decision_uses_snapshot_as_metrics(tmp_path):
    agent, fc = _make_release_agent(tmp_path)
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05}

    class Snap:
        crash_rate = 0.1
        anr_rate = 0.05
        d1_retention = 30.0

    res = agent.execute_decision(
        _decision("com.game.a", PlayAction.INCREASE_ROLLOUT),
        apply=True, snapshot=Snap())
    assert res.ok and res.stage == GateStage.EXECUTE


# --------------------------------------------------------------------------- #
# HealthAgent.evaluate_release_risk
# --------------------------------------------------------------------------- #
def _health_agent(vitals):
    fc = FakeClient()
    conn = PlayConnector(client=fc, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    return HealthAgent(conn, policy=HealthPolicy(),
                       vitals_provider=lambda pkg, w: vitals.get(pkg))


def test_release_risk_low_when_healthy():
    agent = _health_agent({"com.game.a": {"crash_rate": 0.1, "anr_rate": 0.05}})
    risk = agent.evaluate_release_risk("com.game.a")
    assert isinstance(risk, ReleaseRiskScore)
    assert risk.level == "low"
    assert risk.score < 25


def test_release_risk_critical_when_crashing():
    agent = _health_agent({"com.game.a": {"crash_rate": 2.5, "anr_rate": 1.5}})
    risk = agent.evaluate_release_risk("com.game.a")
    assert risk.level == "critical"
    assert risk.score >= 75
    assert any("crash_rate" in r for r in risk.reasons)


def test_release_risk_missing_data():
    agent = _health_agent({})
    risk = agent.evaluate_release_risk("com.game.a")
    assert "missing_data" in risk.factors
    assert risk.score >= 20


def test_release_risk_from_snapshot():
    agent = _health_agent({})

    class Snap:
        crash_rate = 0.9
        anr_rate = 0.4

    risk = agent.evaluate_release_risk("com.game.a", snapshot=Snap())
    # 0.9/1.0*25 + 0.4/0.5*15 = 22.5 + 12 = 34.5 -> medium
    assert risk.level == "medium"
    assert risk.score == pytest.approx(34.5)


# --------------------------------------------------------------------------- #
# 端到端: Reality -> Decision -> Execution
# --------------------------------------------------------------------------- #
def test_end_to_end_reality_to_execution(tmp_path):
    fc = FakeClient()
    fc.tracks["com.game.a"] = {"status": "inProgress", "user_fraction": 0.05,
                               "version_code": 42}
    fc.vitals["com.game.a"] = {"crash_rate": 0.1, "anr_rate": 0.05,
                               "d1_retention": 30.0}
    fc.reviews["com.game.a"] = {"reviews": [{"star_rating": 5}], "count": 1}

    # Reality
    reality = PlayRealityConnector(fc)
    snapshot = reality.collect("com.game.a", persist=False)
    assert snapshot.rollout_percentage == pytest.approx(5.0)

    # Decision
    engine = PlayDecisionEngine()
    decision = engine.decide(snapshot)
    assert decision.action == PlayAction.INCREASE_ROLLOUT

    # Execution (通过 Play 门控)
    conn = PlayConnector(client=fc, sandbox=SandboxMode.PRODUCTION,
                         auto_pilot=True)
    conn.unlock_release()
    agent = ReleaseAgent(conn, policy=ReleasePolicy(observe_hours=0),
                         state_path=str(tmp_path / "release_state.json"))
    res = agent.execute_decision(decision, apply=True, snapshot=snapshot)
    assert res.ok and res.stage == GateStage.EXECUTE
    assert ("set_rollout", "com.game.a", 0.20) in fc.calls
