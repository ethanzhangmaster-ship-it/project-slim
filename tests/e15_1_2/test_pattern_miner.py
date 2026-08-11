"""E15.1.2 — PatternMiner tests (Revenue -> Publishing feedback)."""
from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)
from operation.factory_brain.pattern_miner import PatternMiner

from tests.e15_1_2.brainhelpers import game, registry


def _miner(tmp_path, games=(), mem_entries=()):
    reg = registry(tmp_path, games)
    mem = PublishingMemory(path=str(tmp_path / "mem.jsonl"))
    for e in mem_entries:
        mem.record(e)
    return PatternMiner(reg, memory=mem)


def test_mines_genre_monetization_groups(tmp_path):
    m = _miner(tmp_path, [
        game("p1", metrics={"revenue_per_dau": 0.06}),
        game("p2", genre="word", monetization="iaa",
             metrics={"revenue_per_dau": 0.01})])
    ids = {p.pattern_id for p in m.mine()}
    assert ids == {"pat_merge_hybrid", "pat_word_iaa"}


def test_success_rate_uses_rpd_threshold(tmp_path):
    m = _miner(tmp_path, [
        game("p1", metrics={"revenue_per_dau": 0.06}),
        game("p2", metrics={"revenue_per_dau": 0.01})])
    p = m.mine()[0]
    assert p.sample == 2 and p.success_rate == 0.5


def test_unpublished_excluded(tmp_path):
    m = _miner(tmp_path, [
        game("p1", status="development",
             metrics={"revenue_per_dau": 0.9})])
    assert m.mine() == []


def test_weight_neutral_small_sample(tmp_path):
    m = _miner(tmp_path, [game("p1", metrics={"revenue_per_dau": 0.9})])
    assert m.mine()[0].weight == 1.0


def test_weight_boost_on_evidence(tmp_path):
    m = _miner(tmp_path, [
        game("p1", metrics={"revenue_per_dau": 0.06}),
        game("p2", metrics={"revenue_per_dau": 0.07})])
    assert m.mine()[0].weight == 1.5


def test_weight_penalty_on_failures(tmp_path):
    m = _miner(tmp_path, [
        game("p1", metrics={"revenue_per_dau": 0.001}),
        game("p2", metrics={"revenue_per_dau": 0.002})])
    assert m.mine()[0].weight == 0.5


def test_theme_from_publishing_memory(tmp_path):
    m = _miner(
        tmp_path,
        [game("p1", metrics={"revenue_per_dau": 0.06})],
        [PublishingMemoryEntry(game_id="p1", kind="screenshot_style",
                               key="merge_fantasy", outcome="good",
                               value=0.25, genre="merge")])
    assert m.mine()[0].theme == "fantasy"


def test_theme_empty_without_memory(tmp_path):
    m = _miner(tmp_path, [game("p1", metrics={"revenue_per_dau": 0.06})])
    assert m.mine()[0].theme == ""


def test_ranked_by_success_rate(tmp_path):
    m = _miner(tmp_path, [
        game("p1", genre="word", monetization="iaa",
             metrics={"revenue_per_dau": 0.001}),
        game("p2", metrics={"revenue_per_dau": 0.08}),
        game("p3", metrics={"revenue_per_dau": 0.09})])
    pats = m.mine()
    assert pats[0].pattern_id == "pat_merge_hybrid"


def test_summarize_shape(tmp_path):
    m = _miner(tmp_path, [
        game("p1", metrics={"revenue_per_dau": 0.06}),
        game("p2", metrics={"revenue_per_dau": 0.07})])
    s = m.summarize()
    assert s["patterns"] == 1 and s["with_evidence"] == 1
    assert s["best"]["pattern_id"] == "pat_merge_hybrid"
