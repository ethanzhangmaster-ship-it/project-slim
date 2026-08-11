"""E15.3 Graduated Rollout + Deployer + Operator tests."""
import tempfile, os
from operation.revenue_optimizer.experiment.graduated_rollout import GraduatedRollout, RolloutState
from operation.remote_config.deployer import ConfigDeployer
from operation.remote_config.models import RemoteConfig
from operation.remote_config.experiment_binding import ExperimentBinder
from operation.revenue_optimizer.operator import AutonomousOperator
from tests.revenue_optimizer.ro_helpers import report, winner_sig, zombie_sig


def test_rollout_init():
    s = GraduatedRollout().init("e1")
    assert s.current_phase == 1 and s.traffic == 0.05 and s.verdict == "advancing"

def test_rollout_advance_good():
    s = GraduatedRollout().init("e2")
    # set started_at to > 24h ago so time gate passes
    from datetime import datetime, timedelta, timezone
    s.started_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    s = GraduatedRollout().evaluate(s, {"arpdau_delta_pct": 5.0, "retention_delta_pct": 0.0})
    assert s.current_phase >= 2 and s.verdict in ("advancing", "complete")

def test_rollout_rollback_arpdau():
    s = GraduatedRollout().init("e3")
    s = GraduatedRollout().evaluate(s, {"arpdau_delta_pct": -6.0, "retention_delta_pct": 0.0})
    assert s.verdict == "rollback" and s.traffic == 0.0

def test_rollout_rollback_retention():
    s = GraduatedRollout().init("e4")
    s = GraduatedRollout().evaluate(s, {"arpdau_delta_pct": 0.0, "retention_delta_pct": -3.0})
    assert s.verdict == "rollback"

def test_rollout_paused_on_neutral():
    s = GraduatedRollout().init("e5")
    s = GraduatedRollout().evaluate(s, {"arpdau_delta_pct": 1.0, "retention_delta_pct": 0.0})
    assert s.verdict in ("paused", "advancing")  # passed gate but may not advance due to time

def test_rollout_phase_spec():
    spec = GraduatedRollout().current_phase_spec(GraduatedRollout().init("e"))
    assert spec.phase == 1 and spec.traffic_pct == 0.05

def test_rollout_to_dict():
    s = GraduatedRollout().init("e6")
    d = s.to_dict()
    assert d["experiment_id"] == "e6"

def test_deployer_writes_files():
    d = tempfile.mkdtemp()
    cfg = RemoteConfig.default_for("com.gf.t")
    deployer = ConfigDeployer()
    res = deployer.deploy(cfg, cfg, "com.gf.t", "exp_x", d)
    assert os.path.exists(res["control_path"])
    assert os.path.exists(res["variant_path"])
    assert os.path.exists(res["manifest_path"])

def test_deployer_manifest_keys():
    d = tempfile.mkdtemp()
    cfg = RemoteConfig.default_for("com.gf.t2")
    res = ConfigDeployer().deploy(cfg, cfg, "com.gf.t2", "exp_m", d)
    import json
    m = json.load(open(res["manifest_path"]))
    assert m["game_id"] == "com.gf.t2" and m["experiment_id"] == "exp_m"

def test_operator_process():
    op = AutonomousOperator()
    out = op._cycle.process(report(signals=[winner_sig(), zombie_sig()]), 100000.0, "ACCT_2")
    assert out["opportunities"] > 0

def test_operator_deploy_safe():
    op = AutonomousOperator()
    summary = op._cycle.process(report(signals=[winner_sig()]), 100000.0, "ACCT_2")
    # auto_deploy=False → no deployments
    assert summary.get("deployed_experiments", 0) == 0

def test_operator_evaluate_empty():
    op = AutonomousOperator()
    result = op.evaluate_rollouts({})
    assert result["evaluated"] == 0

def test_operator_evaluate_rollback():
    op = AutonomousOperator()
    rs = op._rollout.init("exp_rollback")
    op._active_rollouts["exp_rollback"] = rs
    result = op.evaluate_rollouts({"exp_rollback": {"arpdau_delta_pct": -7.0, "retention_delta_pct": 0.0}})
    assert result["results"]["exp_rollback"]["verdict"] == "rollback"

def test_rollout_history_tracked():
    s = GraduatedRollout().init("e7")
    s = GraduatedRollout().evaluate(s, {"arpdau_delta_pct": 3.0, "retention_delta_pct": 0.0})
    assert len(s.history) == 1

def test_rollout_phase2_traffic():
    rs = GraduatedRollout()
    s = rs.init("e8")
    # manually advance to phase 2
    s.current_phase = 2; s.traffic = rs.PHASES[1].traffic_pct
    assert s.traffic == 0.25
