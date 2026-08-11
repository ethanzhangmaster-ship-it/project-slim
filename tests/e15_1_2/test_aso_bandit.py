"""E15.1.2 — AsoBandit tests (explore-then-commit)."""
import pytest

from operation.publishing_factory.memory import PublishingMemory
from operation.factory_brain import AsoVariant
from operation.factory_brain.aso_bandit import AsoBandit


def _bandit(tmp_path, min_impressions=500):
    return AsoBandit(path=str(tmp_path / "trials.jsonl"),
                     memory=PublishingMemory(path=str(tmp_path / "m.jsonl")),
                     min_impressions=min_impressions)


def _two_variants(b, imp_a=1000, ins_a=180, imp_b=1000, ins_b=250):
    b.register(AsoVariant("va", "p1", "title", "Build Your Kingdom"))
    b.register(AsoVariant("vb", "p1", "title", "Merge Magic Castle"))
    b.observe("p1", "title", "va", imp_a, ins_a)
    b.observe("p1", "title", "vb", imp_b, ins_b)


def test_register_and_aggregate(tmp_path):
    b = _bandit(tmp_path)
    _two_variants(b)
    vs = b.variants("p1", "title")
    assert len(vs) == 2
    assert vs[1].cvr() == 0.25


def test_register_idempotent(tmp_path):
    b = _bandit(tmp_path)
    v = AsoVariant("va", "p1", "title", "X")
    b.register(v)
    b.register(v)
    assert len(b.variants("p1", "title")) == 1


def test_observe_additive(tmp_path):
    b = _bandit(tmp_path)
    b.register(AsoVariant("va", "p1", "title", "X"))
    b.observe("p1", "title", "va", 500, 50)
    b.observe("p1", "title", "va", 500, 100)
    v = b.variants("p1", "title")[0]
    assert v.impressions == 1000 and v.installs == 150


def test_observe_invalid_raises(tmp_path):
    b = _bandit(tmp_path)
    with pytest.raises(ValueError):
        b.observe("p1", "title", "va", 100, 200)


def test_winner_committed_when_evidence_sufficient(tmp_path):
    b = _bandit(tmp_path)
    _two_variants(b)
    w = b.pick_winner("p1", "title", genre="merge")
    assert w is not None and w.payload == "Merge Magic Castle"


def test_no_winner_while_exploring(tmp_path):
    b = _bandit(tmp_path)
    _two_variants(b, imp_a=100, imp_b=100, ins_a=20, ins_b=30)
    assert b.pick_winner("p1", "title") is None


def test_no_winner_single_variant(tmp_path):
    b = _bandit(tmp_path)
    b.register(AsoVariant("va", "p1", "title", "X"))
    b.observe("p1", "title", "va", 2000, 400)
    assert b.pick_winner("p1", "title") is None


def test_no_winner_too_close(tmp_path):
    b = _bandit(tmp_path)
    _two_variants(b, ins_a=250, ins_b=251)      # 0.1pt apart < 1pt edge
    assert b.pick_winner("p1", "title") is None


def test_winner_memorized(tmp_path):
    b = _bandit(tmp_path)
    _two_variants(b)
    b.pick_winner("p1", "title", genre="merge")
    got = b.memory.recall(kind="aso_variant", genre="merge")
    assert len(got) == 1
    assert "Merge Magic Castle" in got[0].key
    assert got[0].value == 0.25


def test_status_reports_exploring(tmp_path):
    b = _bandit(tmp_path)
    b.register(AsoVariant("va", "p1", "title", "X"))
    st = b.status("p1", "title")
    assert st["exploring"] is True and len(st["variants"]) == 1


def test_kinds_isolated(tmp_path):
    b = _bandit(tmp_path)
    b.register(AsoVariant("va", "p1", "title", "X"))
    b.register(AsoVariant("ic1", "p1", "icon", "bold"))
    assert len(b.variants("p1", "title")) == 1
    assert len(b.variants("p1", "icon")) == 1


def test_games_isolated(tmp_path):
    b = _bandit(tmp_path)
    b.register(AsoVariant("va", "p1", "title", "X"))
    b.register(AsoVariant("va", "p2", "title", "Y"))
    assert b.variants("p1", "title")[0].payload == "X"
    assert b.variants("p2", "title")[0].payload == "Y"
