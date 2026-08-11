"""E15.2 — Play Decision Engine 测试.

需求文档指定用例:
  Test1: crash=0.1% anr=0.05% rollout=5%  -> INCREASE_ROLLOUT
  Test2: crash=1.0%                        -> HALT_RELEASE
  Test3: com.game.a / com.game.b 决策互相隔离
"""

import json

from operation.publishing_factory.play_runtime.decision.engine import (
    PlayDecisionEngine,
)
from operation.publishing_factory.play_runtime.decision.models import (
    PlayAction,
    PlayDecision,
)
from operation.publishing_factory.play_runtime.reality.models import (
    PlayRealitySnapshot,
)


def snap(package="com.game.a", crash=None, anr=None, rollout=None) -> PlayRealitySnapshot:
    return PlayRealitySnapshot(
        package_name=package,
        crash_rate=crash,
        anr_rate=anr,
        rollout_percentage=rollout,
    )


def test_1_healthy_low_rollout_increases():
    engine = PlayDecisionEngine()
    decision = engine.decide(snap(crash=0.1, anr=0.05, rollout=5.0))
    assert isinstance(decision, PlayDecision)
    assert decision.action == PlayAction.INCREASE_ROLLOUT
    assert decision.package_name == "com.game.a"
    assert decision.confidence >= 0.8
    assert "healthy" in decision.reason


def test_2_high_crash_halts():
    engine = PlayDecisionEngine()
    decision = engine.decide(snap(crash=1.0, anr=0.05, rollout=5.0))
    assert decision.action == PlayAction.HALT_RELEASE
    assert "crash_rate" in decision.reason
    assert decision.confidence >= 0.9


def test_high_anr_halts():
    engine = PlayDecisionEngine()
    decision = engine.decide(snap(crash=0.1, anr=0.5, rollout=5.0))
    assert decision.action == PlayAction.HALT_RELEASE
    assert "anr_rate" in decision.reason


def test_3_package_isolation():
    engine = PlayDecisionEngine()
    a = engine.decide(snap(package="com.game.a", crash=0.1, anr=0.05, rollout=5.0))
    b = engine.decide(snap(package="com.game.b", crash=2.0, anr=0.05, rollout=50.0))
    # a 健康 -> 扩大; b 崩溃 -> 暂停; 互不影响
    assert a.action == PlayAction.INCREASE_ROLLOUT
    assert b.action == PlayAction.HALT_RELEASE
    assert a.package_name == "com.game.a"
    assert b.package_name == "com.game.b"

    many = engine.decide_many([
        snap(package="com.game.a", crash=0.1, anr=0.05, rollout=5.0),
        snap(package="com.game.b", crash=2.0, anr=0.05, rollout=50.0),
    ])
    assert many["com.game.a"].action == PlayAction.INCREASE_ROLLOUT
    assert many["com.game.b"].action == PlayAction.HALT_RELEASE


def test_full_rollout_holds():
    engine = PlayDecisionEngine()
    decision = engine.decide(snap(crash=0.1, anr=0.05, rollout=100.0))
    assert decision.action == PlayAction.HOLD_ROLLOUT


def test_missing_data_holds_with_low_confidence():
    engine = PlayDecisionEngine()
    decision = engine.decide(snap())  # 全 None
    assert decision.action == PlayAction.HOLD_ROLLOUT
    assert decision.confidence <= 0.5
    assert "unavailable" in decision.reason


def test_decision_persisted_to_log(tmp_path):
    log = tmp_path / "decisions.jsonl"
    engine = PlayDecisionEngine(decision_log=log, persist=True)
    engine.decide(snap(crash=0.1, anr=0.05, rollout=5.0))
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "increase_rollout"
    assert entry["package_name"] == "com.game.a"


def test_decision_to_dict_roundtrip():
    engine = PlayDecisionEngine()
    d = engine.decide(snap(crash=1.5, anr=0.05, rollout=20.0)).to_dict()
    assert d["action"] == "halt_release"
    assert d["rule_name"] == "auto_halt"
    assert d["created_at"]  # ISO string
