"""Pattern Memory tests — covers the doc's Test4 (similar_pattern + confidence).

Test4: Pattern Memory call returns a similar_pattern with confidence.
"""
import json
import tempfile
from pathlib import Path

from src.revenue_intelligence.models import PatternMatch, RevenueAction
from src.revenue_intelligence.pattern_memory import JsonlPatternMemory


def _tmp_path():
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    f.close()
    return Path(f.name)


def test4_pattern_memory_returns_match():
    path = _tmp_path()
    try:
        mem = JsonlPatternMemory(str(path))
        mem.add(
            PatternMatch(
                pattern_id="pat_growth_ua",
                description="Scaling UA on high-ROAS game lifted revenue +X%",
                confidence=0.82,
                similar_case="case_2026_q1_witch_merge",
                recommended_action=RevenueAction.INCREASE_UA_BUDGET,
                recommended_strategy="Raise budget 20% on top geo",
                source="growth_memory",
            ),
            game_id="game_x",
        )
        results = mem.search_similar(
            "game_x",
            {"revenue_total_pct": 20.0, "roas": 1.5, "insight_types": ["revenue_growth"]},
            limit=3,
        )
        assert results, "expected at least one pattern match"
        top = results[0]
        assert isinstance(top, PatternMatch)
        assert top.confidence == 0.82
        assert top.similar_case == "case_2026_q1_witch_merge"
        assert top.recommended_action == RevenueAction.INCREASE_UA_BUDGET
    finally:
        path.unlink(missing_ok=True)


def test_pattern_memory_persists_and_roundtrips():
    path = _tmp_path()
    try:
        mem = JsonlPatternMemory(str(path))
        mem.add(
            PatternMatch(
                pattern_id="p2",
                description="Retention drop after version bump",
                confidence=0.6,
                similar_case="case_v2_regression",
                recommended_action=RevenueAction.ROLLBACK_VERSION,
            ),
            game_id="game_y",
        )
        raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert raw["pattern_id"] == "p2"
        assert raw["recommended_action"] == "rollback_version"
    finally:
        path.unlink(missing_ok=True)
