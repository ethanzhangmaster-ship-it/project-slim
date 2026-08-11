"""End-to-end RevenueIntelligenceAgent tests + sink integration."""
import tempfile
from pathlib import Path

from src.revenue_intelligence.agent import RevenueIntelligenceAgent
from src.revenue_intelligence.executor import (
    InMemoryGrowthActionSink,
    JsonlGrowthActionSink,
    NullGrowthActionSink,
)
from src.revenue_intelligence.models import PatternMatch, RevenueAction
from src.revenue_intelligence.pattern_memory import JsonlPatternMemory
from tests.e16_1.fixtures import growth_pair, decline_pair, ua_pair, high_roas_pair


def test_end_to_end_reports_all_sections():
    prev, cur = growth_pair()
    agent = RevenueIntelligenceAgent()
    report = agent.analyze(cur, prev)
    assert report.delta is not None
    assert report.attribution is not None
    assert report.insights
    assert report.summary
    assert any(i.insight_type.value == "revenue_growth" for i in report.insights)
    # default: no sink, nothing executed
    assert isinstance(agent.action_sink, NullGrowthActionSink)


def test_auto_execute_submits_to_sink():
    prev, cur = high_roas_pair()
    sink = InMemoryGrowthActionSink()
    agent = RevenueIntelligenceAgent(action_sink=sink)
    report = agent.analyze(cur, prev, auto_execute=True)
    assert len(sink.submitted) == len(report.actions)
    assert all(a.source == "revenue_intelligence" for a in sink.submitted)


def test_analyze_from_source():
    from src.revenue_intelligence.models import RevenueDataSource

    prev, cur = ua_pair()

    class DictSource(RevenueDataSource):
        def __init__(self, mapping):
            self.mapping = mapping

        def load_snapshot(self, game_id, period):
            return self.mapping[period]

    src = DictSource({prev.date: prev, cur.date: cur})
    agent = RevenueIntelligenceAgent()
    report = agent.analyze_from_source(src, cur.game_id, cur.date, prev.date)
    assert report.delta.revenue_total_pct == 80.0
    assert report.attribution.dominant().name == "ua"


def test_agent_uses_pattern_memory():
    path = Path(tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name)
    try:
        mem = JsonlPatternMemory(str(path))
        mem.add(
            PatternMatch(
                pattern_id="pat_x",
                description="High ROAS + growth historically scaled well",
                confidence=0.85,
                similar_case="case_hist",
                recommended_action=RevenueAction.INCREASE_UA_BUDGET,
            ),
            game_id="game_x",
        )
        prev, cur = high_roas_pair()
        agent = RevenueIntelligenceAgent(pattern_memory=mem)
        report = agent.analyze(cur, prev)
        assert report.patterns, "agent should surface historical patterns"
        assert report.patterns[0].confidence == 0.85
    finally:
        path.unlink(missing_ok=True)


def test_report_markdown_renders():
    prev, cur = decline_pair()
    agent = RevenueIntelligenceAgent()
    md = agent.analyze(cur, prev).to_markdown()
    assert "Revenue Intelligence" in md
    assert "RETENTION_CHANGE" in md or "retention_change" in md
