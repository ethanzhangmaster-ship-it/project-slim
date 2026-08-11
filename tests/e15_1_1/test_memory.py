"""E15.1.1 — Publishing Memory tests (10)."""
import os
from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)


def _mem():
    return PublishingMemory(path="data/_t_mem.jsonl")


def _clear(p):
    if os.path.exists(p):
        os.remove(p)


def test_record_and_recall():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "reject_fix", "4.3_spam", "resolved", 1.0, "distinct", "merge"))
    assert len(m.recall()) == 1


def test_recall_by_kind():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "reject_fix", "4.3_spam", "resolved"))
    assert len(m.recall(kind="reject_fix")) == 1
    assert len(m.recall(kind="screenshot_style")) == 0


def test_recall_by_genre():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "reject_fix", "x", "resolved", genre="merge"))
    m.record(PublishingMemoryEntry("g2", "reject_fix", "x", "resolved", genre="puzzle"))
    assert len(m.recall(genre="merge")) == 1


def test_best_style_returns_key():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "screenshot_style", "neon_glass", "good", 0.18, genre="merge"))
    m.record(PublishingMemoryEntry("g2", "screenshot_style", "flat", "good", 0.10, genre="merge"))
    assert m.best_style("merge") == "neon_glass"


def test_best_style_none_when_empty():
    m = _mem(); _clear(m.path)
    assert m.best_style("merge") is None


def test_best_style_averages():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "screenshot_style", "neon", "good", 0.20, genre="merge"))
    m.record(PublishingMemoryEntry("g2", "screenshot_style", "neon", "good", 0.10, genre="merge"))
    # averaged 0.15, still best
    m.record(PublishingMemoryEntry("g3", "screenshot_style", "flat", "good", 0.12, genre="merge"))
    assert m.best_style("merge") == "neon"


def test_summarize_counts():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "reject_fix", "x", "resolved"))
    m.record(PublishingMemoryEntry("g2", "screenshot_style", "y", "good", 0.1, genre="merge"))
    s = m.summarize()
    assert s["total"] == 2 and s["by_kind"].get("reject_fix") == 1


def test_entry_roundtrip_dict():
    e = PublishingMemoryEntry("g", "k", "key", "good", 0.5, "d", "merge")
    e2 = PublishingMemoryEntry.from_dict(e.to_dict())
    assert e2.game_id == e.game_id and e2.value == e.value


def test_memory_persists_multiple():
    m = _mem(); _clear(m.path)
    for i in range(3):
        m.record(PublishingMemoryEntry(f"g{i}", "reject_fix", "x", "resolved"))
    assert len(m.all()) == 3


def test_summarize_best_style_filter():
    m = _mem(); _clear(m.path)
    m.record(PublishingMemoryEntry("g1", "screenshot_style", "neon", "good", 0.2, genre="merge"))
    s = m.summarize(genre="merge")
    assert s["best_style"] == "neon"
