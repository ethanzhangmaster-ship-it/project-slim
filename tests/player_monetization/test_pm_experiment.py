from operation.player_monetization.experiment.ab_allocator import ABAllocator
from operation.player_monetization.experiment.result_analyzer import ResultAnalyzer

def test_ab_same_user_same_bucket():
    a = ABAllocator()
    assert a.allocate("u1","exp1") == a.allocate("u1","exp1")

def test_ab_may_differ():
    a = ABAllocator()
    b1 = a.allocate("u1","exp1")
    b2 = a.allocate("u2","exp1")
    # different users may differ (not guaranteed, but test allocation returns str)
    assert b1 in ("control","variant") and b2 in ("control","variant")

def test_ab_control_all():
    a = ABAllocator()
    assert a.allocate("u1","e", 1.0) == "control"

def test_ab_variant_all():
    a = ABAllocator()
    assert a.allocate("u1","e", 0.0) == "variant"

def test_analyzer_arpdau_delta():
    ctrl = [{"arpdau":0.1,"retention":0.7}]
    var = [{"arpdau":0.12,"retention":0.68}]
    r = ResultAnalyzer().analyze(ctrl,var)
    assert r["arpdau_delta_pct"] > 0

def test_analyzer_ret_delta_negative():
    ctrl = [{"arpdau":0.1,"retention":0.7}]
    var = [{"arpdau":0.1,"retention":0.6}]
    r = ResultAnalyzer().analyze(ctrl,var)
    assert r["retention_delta_pct"] < 0

def test_analyzer_winner():
    ctrl = [{"arpdau":0.1,"retention":0.7}]
    var = [{"arpdau":0.12,"retention":0.69}]
    r = ResultAnalyzer().analyze(ctrl,var)
    assert r["decision"] == "WINNER"

def test_analyzer_loser_arpdau_down():
    ctrl = [{"arpdau":0.1}]
    var = [{"arpdau":0.09}]
    r = ResultAnalyzer().analyze(ctrl,var)
    assert r["decision"] == "LOSER"

def test_analyzer_counts():
    ctrl = [{"arpdau":0.1},{"arpdau":0.11}]
    var = [{"arpdau":0.12}]
    r = ResultAnalyzer().analyze(ctrl,var)
    assert r["control_n"] == 2 and r["variant_n"] == 1

def test_ab_deterministic():
    a = ABAllocator()
    b1 = a.allocate("uxyz","exp_big")
    b2 = a.allocate("uxyz","exp_big")
    assert b1 == b2
