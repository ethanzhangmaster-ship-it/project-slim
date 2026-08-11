"""E17.3 Decision Memory 测试（Test5：历史成功 → 置信度提升）。"""
from src.ceo_intelligence.decision_engine.memory import DecisionMemory


def _seed(memory, game_id, action, pairs):
    for b, a in pairs:
        memory.record_outcome(
            game_id=game_id, action=action, reason="test",
            before_revenue=b, after_revenue=a,
            before_roas=1.0, after_roas=(a / b) if b else 1.0,
        )


def test_memory_stats_and_boost(tmp_path):
    """Test5：历史成功 → 置信度提升。"""
    m = DecisionMemory(experience_path=str(tmp_path / "exp.jsonl"))
    _seed(m, "merge_witch", "creative_refresh", [(100, 120), (100, 125), (100, 130)])
    st = m.stats("merge_witch", "creative_refresh")
    assert st.n == 3
    assert st.success_rate == 1.0
    boosted = m.confidence_adjust(0.5, "merge_witch", "creative_refresh")
    assert boosted > 0.5


def test_memory_failure_lowers_confidence(tmp_path):
    m = DecisionMemory(experience_path=str(tmp_path / "exp.jsonl"))
    _seed(m, "g", "monetization", [(100, 90), (100, 85)])
    st = m.stats("g", "monetization")
    assert st.success_rate == 0.0
    lowered = m.confidence_adjust(0.9, "g", "monetization")
    assert lowered < 0.9


def test_memory_insufficient_samples_no_boost(tmp_path):
    m = DecisionMemory(experience_path=str(tmp_path / "exp.jsonl"))
    _seed(m, "g", "creative_refresh", [(100, 110)])
    assert m.confidence_adjust(0.5, "g", "creative_refresh") == 0.5


def test_memory_records_pattern_when_provided(tmp_path):
    from src.revenue_intelligence.pattern_memory import JsonlPatternMemory

    pat = JsonlPatternMemory(str(tmp_path / "pat.jsonl"))
    m = DecisionMemory(
        experience_path=str(tmp_path / "exp.jsonl"), pattern_memory=pat
    )
    m.record_pattern(
        game_id="g", action="creative_refresh",
        description="Merge 类创意刷新 CVR 提升", confidence=0.85,
    )
    stored = pat.all()
    assert len(stored) == 1
    assert stored[0]["recommended_strategy"] == "creative_refresh"
