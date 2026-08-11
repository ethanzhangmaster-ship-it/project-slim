import tempfile, os
from operation.optimizer.experiments.optimization_memory import OptimizationMemory
from operation.revenue_optimizer.memory.optimization_memory import record_outcome


def _mem(tmp_path):
    return OptimizationMemory(path=os.path.join(str(tmp_path), "m.jsonl"))


def test_record_returns_row():
    m = _mem(tempfile.mkdtemp())
    r = m.record(account="A", action="disable_network", target="CHB",
                 net_impact_pct=5.0, guardrail="pass", decision="KEEP",
                 confidence=0.9, applied_at="2026-07-10")
    assert r["decision"] == "KEEP" and r["net_impact_pct"] == 5.0


def test_record_dedup(tmp_path):
    m = _mem(tmp_path)
    m.record(account="A", action="disable_network", target="CHB",
            net_impact_pct=5.0, guardrail="pass", decision="KEEP",
            confidence=0.9, applied_at="2026-07-10")
    m.record(account="A", action="disable_network", target="CHB",
            net_impact_pct=5.0, guardrail="pass", decision="KEEP",
            confidence=0.9, applied_at="2026-07-10")
    assert len(m._load()) == 1


def test_query_by_action(tmp_path):
    m = _mem(tmp_path)
    m.record(account="A", action="disable_network", target="CHB",
            net_impact_pct=5.0, guardrail="pass", decision="KEEP",
            confidence=0.9, applied_at="2026-07-10")
    q = m.query(action="disable_network")
    assert q["prior"]["n"] == 1


def test_query_by_target(tmp_path):
    m = _mem(tmp_path)
    m.record(account="A", action="disable_network", target="CHB",
            net_impact_pct=5.0, guardrail="pass", decision="KEEP",
            confidence=0.9, applied_at="2026-07-10")
    q = m.query(target="CHB")
    assert q["prior"]["n"] == 1
    q2 = m.query(target="NOPE")
    assert q2["prior"]["n"] == 0


def test_query_no_match(tmp_path):
    m = _mem(tmp_path)
    q = m.query(action="disable_network")
    assert q["prior"]["n"] == 0


def test_prior_aggregation(tmp_path):
    m = _mem(tmp_path)
    for i, v in enumerate((5.0, 7.0)):
        m.record(account="A", action="disable_network", target="CHB",
                 net_impact_pct=v, guardrail="pass", decision="KEEP",
                 confidence=0.9, applied_at=f"2026-07-1{i}")
    p = m.query(action="disable_network")["prior"]
    assert p["mean_impact_pct"] == 6.0
    assert p["hit_rate"] == 1.0


def test_prior_note_empty(tmp_path):
    m = _mem(tmp_path)
    assert m.prior_note("disable_network", "CHB") == ""


def test_prior_note_formatted(tmp_path):
    m = _mem(tmp_path)
    m.record(account="A", action="disable_network", target="CHB",
            net_impact_pct=5.0, guardrail="pass", decision="KEEP",
            confidence=0.9, applied_at="2026-07-10")
    note = m.prior_note("disable_network", "CHB")
    assert "precedent" in note


def test_record_outcome_convenience(tmp_path):
    m = _mem(tmp_path)
    row = record_outcome(m, account="A", action="disable_network",
                         target="CHB", net_impact_pct=4.0, guardrail="pass",
                         decision="KEEP", confidence=0.9,
                         applied_at="2026-07-10")
    assert row["decision"] == "KEEP"
    assert len(m._load()) == 1


def test_memory_persists(tmp_path):
    p = str(tmp_path / "m.jsonl")
    m1 = OptimizationMemory(path=p)
    m1.record(account="A", action="disable_network", target="CHB",
              net_impact_pct=5.0, guardrail="pass", decision="KEEP",
              confidence=0.9, applied_at="2026-07-10")
    m2 = OptimizationMemory(path=p)
    assert len(m2._load()) == 1
