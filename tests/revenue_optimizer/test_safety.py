import tempfile, os
from tests.revenue_optimizer.ro_helpers import report, winner_sig
from operation.revenue_optimizer.models import (
    RevenueOpportunity, PredictionResult, ChangeAction, ChangePackage,
)
from operation.revenue_optimizer.executor.approval_gate import ApprovalGate
from operation.revenue_optimizer.executor.change_package import ChangePackageBuilder
from operation.revenue_optimizer.executor.rollback import RollbackPlanner


def _opp(action="increase_bid_opportunity", target="M", lift=0.1, conf=0.9,
         risk=0.1, metrics=None):
    return RevenueOpportunity(id="e1", app_id="ACCT_2", dimension="network",
                               rule="hidden_winner", action=action, target=target,
                               current_value=0, target_value=0,
                               expected_lift=lift, confidence=conf, risk=risk,
                               metrics=metrics or {})


def _pred(lift_pct=10.0, conf=0.9, risk=0.1):
    return PredictionResult(change="x", before_revenue=1000,
                            after_revenue=1000 * (1 + lift_pct / 100.0),
                            lift_percent=lift_pct, confidence=conf, risk=risk)


def test_gate_auto():
    g = ApprovalGate().check(_opp(), _pred())
    assert g["tier"] == "AUTO"


def test_gate_reject_revenue_loss():
    g = ApprovalGate().check(_opp(), _pred(lift_pct=-6.0))
    assert g["tier"] == "REJECT"


def test_gate_reject_retention():
    g = ApprovalGate().check(_opp(), _pred(), retention_delta_pct=-4.0)
    assert g["tier"] == "REJECT"


def test_gate_approval_low_conf():
    g = ApprovalGate().check(_opp(conf=0.7), _pred(conf=0.7))
    assert g["tier"] == "APPROVAL"


def test_gate_approval_diversify():
    g = ApprovalGate().check(_opp(action="diversify"), _pred(conf=0.95))
    assert g["tier"] == "APPROVAL"


def test_gate_reasons_nonempty():
    g = ApprovalGate().check(_opp(), _pred())
    assert g["reasons"]


def test_gate_reject_precedence():
    g = ApprovalGate().check(_opp(conf=0.95), _pred(lift_pct=-6.0))
    assert g["tier"] == "REJECT"


def test_package_disable():
    pkg = ChangePackageBuilder().build(_opp(action="disable_network",
                                            target="CHARTBOOST"), "e1")
    assert pkg.actions[0].type == "disable_network"


def test_package_floor_value():
    pkg = ChangePackageBuilder().build(
        _opp(action="adjust_bid_constraint",
             metrics={"recommended_floor_range": [3.5, 5.0]}), "e1")
    assert pkg.actions[0].type == "change_floor"
    assert pkg.actions[0].value == 3.5


def test_package_increase_bid():
    pkg = ChangePackageBuilder().build(
        _opp(action="increase_bid_opportunity", target="MINT"), "e1")
    assert pkg.actions[0].type == "increase_bid_opportunity"


def test_package_write(tmp_path):
    pkg = ChangePackageBuilder().build(_opp(action="disable_network",
                                            target="CHARTBOOST"), "e1")
    path = pkg.write(str(tmp_path))
    assert os.path.exists(path)
    assert pkg.to_dict()["actions"][0]["type"] == "disable_network"


def test_rollback_disable():
    pkg = ChangePackageBuilder().build(_opp(action="disable_network",
                                            target="CHARTBOOST"), "e1")
    rb = RollbackPlanner().plan(pkg)
    assert rb.actions[0].type == "enable_network"


def test_rollback_floor():
    pkg = ChangePackageBuilder().build(
        _opp(action="adjust_bid_constraint",
             metrics={"recommended_floor_range": [3.5, 5.0]}), "e1")
    rb = RollbackPlanner().plan(pkg)
    assert rb.actions[0].type == "remove_floor"
    assert rb.actions[0].value is None


def test_rollback_increase_bid():
    pkg = ChangePackageBuilder().build(
        _opp(action="increase_bid_opportunity", target="MINT"), "e1")
    rb = RollbackPlanner().plan(pkg)
    assert rb.actions[0].type == "revert_bid_opportunity"


def test_gate_constants():
    assert ApprovalGate.REVENUE_LOSS_LIMIT_PCT == -5.0
    assert ApprovalGate.RETENTION_DROP_LIMIT_PCT == -3.0
    assert ApprovalGate.CONFIDENCE_MIN == 0.8
