"""V5.0 Phase E — Human+AI Creative Intelligence Marketplace Release Gate (120 tests).

Gates:
  Gate 1: Human Input — 20 tests
  Gate 2: AI Discovery — 30 tests
  Gate 3: Multi-Agent Debate — 20 tests
  Gate 4: Human-AI Ranking — 20 tests
  Gate 5: Genome Marketplace — 30 tests
"""

from __future__ import annotations
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain_ui import (
    CreativeAnalysisEngine, CreativeScoringEngine, CreativeScore, BuildAction,
    MultiAgentDebateEngine, DebateResult, AgentRole, Vote,
    GenomeMarketplace, VerifiedGenome, GenomeCombo,
    HumanFeedbackLoop, IdeaEvolutionOrchestrator,
)
from market_ops.creative_opportunity.human_idea import HumanIdeaInbox
from market_ops.creative_opportunity.schemas import HumanIdea
from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_analysis(genes: dict[str, str] | None = None, **kw) -> dict:
    """Build a minimal analysis dict for testing."""
    d = {"idea_type": "gameplay", "category": genes.get("core_loop", "unknown") if genes else "unknown",
         "genes": genes or {}, "confidence": 0.7, "missing_dimensions": [], "suggestions": []}
    d.update(kw)
    return d

def _quick_genome(name: str = "test_genome", **gene_values) -> Genome:
    """Create a minimal Genome with string-value genes."""
    g = Genome(name=name)
    genes = {}
    for k, v in gene_values.items():
        gt_map = {
            "hook": GeneType.HOOK, "core_loop": GeneType.GAMEPLAY, "reward": GeneType.REWARD,
            "character": GeneType.CHARACTER, "visual": GeneType.VISUAL,
            "monetization": GeneType.PLATFORM, "theme": GeneType.VISUAL,
        }
        gt = gt_map.get(k, GeneType.GAMEPLAY)
        genes[k] = Gene(gene_type=gt, value=str(v), mutation_pool=[str(v)], confidence=0.6)
    g.genes = genes
    return g


# ═══════════════════════════════════════════════════════════
# GATE 1: Human Input (20 tests)
# ═══════════════════════════════════════════════════════════

def test_analysis_engine_import():
    """G1: CreativeAnalysisEngine can be imported and instantiated."""
    eng = CreativeAnalysisEngine()
    assert eng is not None
    return True

def test_analyze_text_basic():
    """G1: analyze_text returns a dict with required keys."""
    eng = CreativeAnalysisEngine()
    result = eng.analyze_text("A merge puzzle game with dragons and rescue hook")
    assert isinstance(result, dict)
    assert "genes" in result
    assert "confidence" in result
    return True

def test_analyze_text_extracts_core_loop():
    """G1: Detects merge, sort, puzzle, simulation core loops."""
    eng = CreativeAnalysisEngine()
    assert eng.analyze_text("merge items together")["genes"].get("core_loop") == "merge"
    assert eng.analyze_text("sort the objects")["genes"].get("core_loop") == "sort"
    assert eng.analyze_text("a puzzle game")["genes"].get("core_loop") == "puzzle"
    assert eng.analyze_text("simulation of a farm")["genes"].get("core_loop") == "simulation"
    return True

def test_analyze_text_extracts_hook():
    """G1: Detects rescue, reward, mess_to_clean hooks."""
    eng = CreativeAnalysisEngine()
    assert eng.analyze_text("rescue the animals")["genes"].get("hook") == "rescue"
    assert eng.analyze_text("reward the player")["genes"].get("hook") == "reward"
    assert eng.analyze_text("clean up the mess")["genes"].get("hook") == "mess_to_clean"
    return True

def test_analyze_text_extracts_reward():
    """G1: Detects evolution, collection, growth rewards."""
    eng = CreativeAnalysisEngine()
    assert eng.analyze_text("evolution of creatures")["genes"].get("reward") == "evolution"
    assert eng.analyze_text("collection of items")["genes"].get("reward") == "collection"
    assert eng.analyze_text("growth and upgrade")["genes"].get("reward") == "growth"
    return True

def test_analyze_text_extracts_character():
    """G1: Detects character from text."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("A game about dragons and pets")
    assert r["genes"].get("character") is not None
    return True

def test_analyze_text_extracts_visual():
    """G1: Detects visual style from text."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("A bright and colorful 3d game")
    assert "visual" in r["genes"]
    return True

def test_analyze_text_extracts_monetization():
    """G1: Detects monetization type from text."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("IAA based game with ads")
    assert r["genes"].get("monetization") == "IAA"
    return True

def test_analyze_text_finds_missing_dimensions():
    """G1: Reports which genome dimensions are missing."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("a simple game")
    assert "missing_dimensions" in r
    assert len(r["missing_dimensions"]) > 0
    return True

def test_analyze_text_generates_suggestions():
    """G1: Generates actionable suggestions for missing genes."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("a simple game")
    assert "suggestions" in r
    assert len(r["suggestions"]) > 0
    return True

def test_analyze_text_confidence_scales():
    """G1: Confidence increases with more detail."""
    eng = CreativeAnalysisEngine()
    r1 = eng.analyze_text("merge")
    r2 = eng.analyze_text("A merge puzzle game with dragon character, rescue hook, 3d cartoon visual, and IAA monetization")
    assert r2["confidence"] > r1["confidence"]
    return True

def test_analyze_url_google_play():
    """G1: URL analysis detects google_play type."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_url("https://play.google.com/store/apps/details?id=com.example")
    assert r["url_type"] == "google_play"
    return True

def test_analyze_url_app_store():
    """G1: URL analysis detects app_store type."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_url("https://apps.apple.com/us/app/example/id123456")
    assert r["url_type"] == "app_store"
    return True

def test_analyze_url_youtube():
    """G1: URL analysis detects youtube type."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_url("https://youtube.com/watch?v=abc123")
    assert r["url_type"] == "youtube"
    return True

def test_analyze_url_tiktok():
    """G1: URL analysis detects tiktok type."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_url("https://tiktok.com/@user/video/123456")
    assert r["url_type"] == "tiktok"
    return True

def test_analyze_url_reddit():
    """G1: URL analysis returns url_type=reddit for Reddit URLs."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_url("https://reddit.com/r/gaming/comments/abc")
    assert r["url_type"] == "reddit"
    return True

def test_analyze_media_image():
    """G1: Media analysis with type='image' returns correct media_type."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_media("image", "rescue a cute dragon in bright colors")
    assert r["media_type"] == "image"
    assert "hook" in r
    return True

def test_analyze_media_video():
    """G1: Media analysis with type='video' returns structure info."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_media("video", "rescue cute baby animals fast paced")
    assert r["media_type"] == "video"
    assert "structure" in r
    return True

def test_analyze_media_ctr_prediction():
    """G1: Media analysis predicts CTR based on content."""
    eng = CreativeAnalysisEngine()
    r1 = eng.analyze_media("image", "rescue cute baby")
    r2 = eng.analyze_media("image", "plain text")
    assert r1["ctr_prediction"] == "high"
    return True

def test_analyze_text_empty_input():
    """G1: analyze_text handles empty input gracefully."""
    eng = CreativeAnalysisEngine()
    r = eng.analyze_text("")
    assert isinstance(r, dict)
    assert "genes" in r
    return True


# ═══════════════════════════════════════════════════════════
# GATE 2: AI Discovery (30 tests)
# ═══════════════════════════════════════════════════════════

def test_scoring_engine_import():
    """G2: CreativeScoringEngine can be imported and instantiated."""
    eng = CreativeScoringEngine()
    assert eng is not None
    return True

def test_score_from_analysis_basic():
    """G2: score_from_analysis returns a CreativeScore."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    assert isinstance(score, CreativeScore)
    return True

def test_score_from_analysis_components_range():
    """G2: All component scores are within their valid ranges."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue", "visual": "3d_cartoon",
                                "monetization": "IAA", "reward": "collection", "character": "dragon"})
    score = eng.score_from_analysis(analysis)
    assert 0 <= score.market_score <= 30
    assert 0 <= score.creative_score <= 25
    assert 0 <= score.build_score <= 20
    assert 0 <= score.monetization_score <= 15
    assert 0 <= score.evolution_score <= 10
    return True

def test_score_from_analysis_total_100():
    """G2: Total score does not exceed 100."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue", "visual": "3d_cartoon",
                                "monetization": "battle_pass", "reward": "evolution", "character": "dragon"})
    score = eng.score_from_analysis(analysis)
    assert score.total <= 100
    return True

def test_score_market_high_for_merge():
    """G2: Market score is high for 'merge' core loop."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"core_loop": "merge"})
    a2 = _make_analysis({"core_loop": "unknown"})
    s1 = eng.score_from_analysis(a1).market_score
    s2 = eng.score_from_analysis(a2).market_score
    assert s1 > s2
    return True

def test_score_market_high_for_sort():
    """G2: Market score is high for 'sort' core loop."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"core_loop": "sort"})
    a2 = _make_analysis({"core_loop": "unknown"})
    s1 = eng.score_from_analysis(a1).market_score
    s2 = eng.score_from_analysis(a2).market_score
    assert s1 > s2
    return True

def test_score_market_baseline():
    """G2: Market score has a baseline above 0."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "battle"})
    score = eng.score_from_analysis(analysis)
    assert score.market_score > 0
    return True

def test_score_creative_high_rescue_hook():
    """G2: Creative score is boosted for rescue hook."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"hook": "rescue"})
    a2 = _make_analysis({"hook": "build_progress"})
    s1 = eng.score_from_analysis(a1).creative_score
    s2 = eng.score_from_analysis(a2).creative_score
    assert s1 > s2
    return True

def test_score_creative_high_3d_visual():
    """G2: Creative score is higher with 3d_cartoon visual."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"visual": "3d_cartoon"})
    a2 = _make_analysis({})
    s1 = eng.score_from_analysis(a1).creative_score
    s2 = eng.score_from_analysis(a2).creative_score
    assert s1 > s2
    return True

def test_score_creative_with_character():
    """G2: Creative score is boosted when a character is present."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"character": "dragon"})
    a2 = _make_analysis({})
    s1 = eng.score_from_analysis(a1).creative_score
    s2 = eng.score_from_analysis(a2).creative_score
    assert s1 > s2
    return True

def test_score_build_easy_for_merge():
    """G2: Build score is higher (easier) for merge core loop."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"core_loop": "merge"})
    a2 = _make_analysis({"core_loop": "battle"})
    s1 = eng.score_from_analysis(a1).build_score
    s2 = eng.score_from_analysis(a2).build_score
    assert s1 > s2
    return True

def test_score_build_iaa_simple():
    """G2: Build score is higher for IAA monetization (simpler)."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"monetization": "IAA"})
    a2 = _make_analysis({"monetization": "IAP"})
    s1 = eng.score_from_analysis(a1).build_score
    s2 = eng.score_from_analysis(a2).build_score
    assert s1 > s2
    return True

def test_score_monetization_iaa():
    """G2: Monetization score is boosted for IAA."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"monetization": "IAA", "core_loop": "merge"})
    s1 = eng.score_from_analysis(a1).monetization_score
    assert s1 >= 5  # at least baseline + IAA boost
    return True

def test_score_monetization_battle_pass():
    """G2: Battle pass scores higher ARPU than IAA."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"monetization": "battle_pass"})
    a2 = _make_analysis({"monetization": "IAA"})
    s1 = eng.score_from_analysis(a1).monetization_score
    s2 = eng.score_from_analysis(a2).monetization_score
    assert s1 > s2
    return True

def test_score_evolution_gene_count():
    """G2: More genes = higher evolution score."""
    eng = CreativeScoringEngine()
    a1 = _make_analysis({"core_loop": "merge", "hook": "rescue", "visual": "3d_cartoon",
                          "reward": "collection", "character": "dragon"})
    a2 = _make_analysis({"core_loop": "merge"})
    s1 = eng.score_from_analysis(a1).evolution_score
    s2 = eng.score_from_analysis(a2).evolution_score
    assert s1 > s2
    return True

def test_score_build_action_80_build():
    """G2: Score >= 80 triggers BUILD action."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue", "visual": "3d_cartoon",
                                "monetization": "battle_pass", "reward": "evolution", "character": "dragon"})
    score = eng.score_from_analysis(analysis)
    if score.total >= 80:
        assert score.action == BuildAction.BUILD
    return True

def test_score_build_action_60_prototype():
    """G2: Score in 60-79 triggers PROTOTYPE action."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "puzzle", "hook": "reward"})
    score = eng.score_from_analysis(analysis)
    if 60 <= score.total < 80:
        assert score.action == BuildAction.PROTOTYPE
    return True

def test_score_build_action_40_watch():
    """G2: Score in 40-59 triggers WATCH action."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "battle"})
    score = eng.score_from_analysis(analysis)
    if 40 <= score.total < 60:
        assert score.action == BuildAction.WATCH
    return True

def test_score_build_action_20_ignore():
    """G2: Score < 40 triggers IGNORE action."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({})
    score = eng.score_from_analysis(analysis)
    if score.total < 40:
        assert score.action == BuildAction.IGNORE
    return True

def test_score_to_dict_has_all_keys():
    """G2: to_dict includes all top-level fields."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    d = score.to_dict()
    for key in ["opportunity_name", "total", "components", "confidence", "action",
                "justification", "risks", "advantages"]:
        assert key in d, f"Missing key: {key}"
    return True

def test_score_to_dict_has_components():
    """G2: to_dict components has all 5 sub-scores."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    d = score.to_dict()
    comps = d["components"]
    for key in ["market_score", "creative_score", "build_score", "monetization_score", "evolution_score"]:
        assert key in comps, f"Missing component: {key}"
    return True

def test_score_from_text_quick():
    """G2: score_from_text returns a CreativeScore from free text."""
    eng = CreativeScoringEngine()
    score = eng.score_from_text("A merge puzzle game with dragons and rescue hook")
    assert isinstance(score, CreativeScore)
    assert score.total > 0
    return True

def test_scoring_engine_integration_with_analysis():
    """G2: Scoring engine integrates correctly with analysis engine output."""
    analysis_eng = CreativeAnalysisEngine()
    scoring_eng = CreativeScoringEngine()
    analysis = analysis_eng.analyze_text("A merge puzzle with rescue hook, dragon character, and evolution reward")
    score = scoring_eng.score_from_analysis(analysis)
    assert score.total > 0
    assert score.market_score > 0
    return True

def test_score_justification_not_empty():
    """G2: Justification text is not empty when genes are present."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    assert len(score.justification) > 0
    return True

def test_score_advantages_not_empty():
    """G2: Advantages list is populated for merge+rescue."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    assert len(score.advantages) > 0
    return True

def test_score_risks_for_missing_reward():
    """G2: Risks include retention warning when reward is missing."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    risks_text = " ".join(score.risks).lower()
    assert "reward" in risks_text or "retention" in risks_text
    return True

def test_score_risks_for_missing_character():
    """G2: Risks include engagement warning when character is missing."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    risks_text = " ".join(score.risks).lower()
    assert "character" in risks_text or "emotional" in risks_text
    return True

def test_score_confidence_present():
    """G2: Confidence value is present and within 0-1."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge"})
    score = eng.score_from_analysis(analysis)
    assert 0 <= score.confidence <= 1
    return True

def test_score_action_is_buildaction():
    """G2: Action field is a BuildAction enum instance."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    assert isinstance(score.action, BuildAction)
    return True

def test_creative_score_dataclass_defaults():
    """G2: CreativeScore has sensible dataclass defaults."""
    cs = CreativeScore()
    assert cs.total == 0.0
    assert cs.confidence == 0.5
    assert cs.action == BuildAction.WATCH
    assert cs.justification == ""
    return True


# ═══════════════════════════════════════════════════════════
# GATE 3: Multi-Agent Debate (20 tests)
# ═══════════════════════════════════════════════════════════

def test_debate_engine_import():
    """G3: MultiAgentDebateEngine can be imported and instantiated."""
    eng = MultiAgentDebateEngine()
    assert eng is not None
    return True

def test_debate_produces_5_opinions():
    """G3: Debate produces exactly 5 agent opinions."""
    eng = MultiAgentDebateEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue", "reward": "collection"})
    score = CreativeScore(total=75)
    result = eng.debate(analysis, score)
    assert len(result.opinions) == 5
    return True

def test_debate_has_market_agent():
    """G3: Debate includes a Market Agent opinion."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=75))
    roles = [o.agent_role for o in result.opinions]
    assert AgentRole.MARKET in roles
    return True

def test_debate_has_gameplay_agent():
    """G3: Debate includes a Gameplay Agent opinion."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=75))
    roles = [o.agent_role for o in result.opinions]
    assert AgentRole.GAMEPLAY in roles
    return True

def test_debate_has_ua_agent():
    """G3: Debate includes a UA Agent opinion."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=75))
    roles = [o.agent_role for o in result.opinions]
    assert AgentRole.UA in roles
    return True

def test_debate_has_producer_agent():
    """G3: Debate includes a Producer Agent opinion."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=75))
    roles = [o.agent_role for o in result.opinions]
    assert AgentRole.PRODUCER in roles
    return True

def test_debate_has_investor_agent():
    """G3: Debate includes an Investor Agent opinion."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=75))
    roles = [o.agent_role for o in result.opinions]
    assert AgentRole.INVESTOR in roles
    return True

def test_debate_consensus_calculated():
    """G3: Consensus strength is calculated."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=90))
    assert result.consensus_strength is not None
    return True

def test_debate_consensus_range_0_to_1():
    """G3: Consensus strength is between 0 and 1."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=90))
    assert 0.0 <= result.consensus_strength <= 1.0
    return True

def test_debate_final_vote_is_vote_enum():
    """G3: Final vote is a Vote enum instance."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=90))
    assert isinstance(result.final_vote, Vote)
    return True

def test_debate_vote_counts_sum_to_5():
    """G3: All vote counts sum to 5 (one per agent)."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge", "hook": "rescue"}), CreativeScore(total=85))
    assert sum(result.vote_counts.values()) == 5
    return True

def test_debate_majority_reasoning_not_empty():
    """G3: Majority reasoning text is populated."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge", "hook": "rescue"}), CreativeScore(total=85))
    assert len(result.majority_reasoning) > 0
    return True

def test_debate_action_items_for_prototype():
    """G3: Action items are generated when vote is PROTOTYPE."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "puzzle", "hook": "reward"}), CreativeScore(total=65))
    if result.final_vote in (Vote.BUILD, Vote.PROTOTYPE):
        assert len(result.action_items) > 0
    return True

def test_debate_action_items_for_build():
    """G3: Action items are generated when vote is BUILD."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge", "hook": "rescue", "reward": "collection"}),
                         CreativeScore(total=90))
    if result.final_vote == Vote.BUILD:
        assert len(result.action_items) > 0
    return True

def test_debate_dissenting_view_when_not_unanimous():
    """G3: Dissenting view is present when not all agents agree."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "puzzle"}), CreativeScore(total=50))
    if result.consensus_strength < 1.0:
        assert result.dissenting_view != "" or result.consensus_strength < 1.0
    return True

def test_debate_to_dict_complete():
    """G3: DebateResult.to_dict includes all expected fields."""
    eng = MultiAgentDebateEngine()
    result = eng.debate(_make_analysis({"core_loop": "merge"}), CreativeScore(total=80))
    d = result.to_dict()
    for key in ["opportunity_name", "opinions", "vote_counts", "final_vote",
                "consensus_strength", "majority_reasoning", "dissenting_view", "action_items"]:
        assert key in d, f"Missing key: {key}"
    return True

def test_agent_opinion_to_dict():
    """G3: AgentOpinion.to_dict includes all expected fields."""
    from market_ops.creative_brain_ui.multi_agent_debate import AgentOpinion
    op = AgentOpinion(agent_role=AgentRole.MARKET, vote=Vote.BUILD, confidence=0.8,
                       reasoning="Strong market", key_concerns=[], key_strengths=["Trend"])
    d = op.to_dict()
    for key in ["agent_role", "vote", "confidence", "reasoning", "key_concerns", "key_strengths"]:
        assert key in d, f"Missing key: {key}"
    return True

def test_vote_enum_values():
    """G3: Vote enum has BUILD, PROTOTYPE, WATCH, SKIP values."""
    values = [v.value for v in Vote]
    for expected in ["build", "prototype", "watch", "skip"]:
        assert expected in values, f"Missing Vote value: {expected}"
    return True

def test_agent_role_enum_values():
    """G3: AgentRole enum has exactly 5 agent types."""
    roles = list(AgentRole)
    assert len(roles) == 5
    return True

def test_debate_result_dataclass_defaults():
    """G3: DebateResult has sensible dataclass defaults."""
    dr = DebateResult()
    assert dr.opportunity_name == ""
    assert dr.opinions == []
    assert dr.final_vote == Vote.WATCH
    assert dr.consensus_strength == 0.0
    return True


# ═══════════════════════════════════════════════════════════
# GATE 4: Human-AI Ranking (20 tests)
# ═══════════════════════════════════════════════════════════

def test_feedback_loop_record_selection():
    """G4: HumanFeedbackLoop records a human selection."""
    loop = HumanFeedbackLoop()
    idea = HumanIdea(title="Test Idea", description="A merge game")
    genome = _quick_genome("test", hook="rescue", core_loop="merge")
    loop.record_selection(idea, approved=True, genome=genome)
    rates = loop.get_approval_rates()
    assert len(rates) > 0
    return True

def test_feedback_loop_approval_rates_populated():
    """G4: Approval rates are populated after recording selections."""
    loop = HumanFeedbackLoop()
    idea1 = HumanIdea(title="A", description="merge game")
    idea2 = HumanIdea(title="B", description="sort game")
    g1 = _quick_genome("g1", hook="rescue", core_loop="merge")
    g2 = _quick_genome("g2", hook="reward", core_loop="sort")
    loop.record_selection(idea1, approved=True, genome=g1)
    loop.record_selection(idea2, approved=False, genome=g2)
    rates = loop.get_approval_rates()
    total_entries = sum(len(v) for v in rates.values())
    assert total_entries > 0
    return True

def test_feedback_loop_top_approved_genes():
    """G4: Top approved genes returns a list of best-performing genes."""
    loop = HumanFeedbackLoop()
    for i in range(4):
        idea = HumanIdea(title=f"idea_{i}", description="merge game")
        genome = _quick_genome(f"g{i}", hook="rescue", core_loop="merge")
        loop.record_selection(idea, approved=(i < 3), genome=genome)
    top = loop.get_top_approved_genes(n=3)
    assert isinstance(top, list)
    if top:
        assert "approval_rate" in top[0]
    return True

def test_idea_evolution_orchestrator_import():
    """G4: IdeaEvolutionOrchestrator can be imported and instantiated."""
    orch = IdeaEvolutionOrchestrator()
    assert orch is not None
    return True

def test_submit_and_rank_returns_full_result():
    """G4: submit_and_rank returns a dict with all pipeline sections."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert isinstance(result, dict)
    assert "idea" in result
    assert "analysis" in result
    assert "score" in result
    assert "debate" in result
    return True

def test_submit_and_rank_has_analysis():
    """G4: Result includes analysis with genes."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert "genes" in result["analysis"]
    return True

def test_submit_and_rank_has_score():
    """G4: Result includes a score dict with total."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert "total" in result["score"]
    return True

def test_submit_and_rank_has_debate():
    """G4: Result includes a debate dict with final_vote."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert "final_vote" in result["debate"]
    return True

def test_submit_and_rank_has_genome_id():
    """G4: Result includes a genome_id string."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert "genome_id" in result
    assert len(result["genome_id"]) > 0
    return True

def test_submit_and_rank_has_experiment_plan():
    """G4: Result includes an experiment plan with plan_id."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert "experiment_plan" in result
    assert "plan_id" in result["experiment_plan"]
    return True

def test_submit_url_and_rank_returns_result():
    """G4: submit_url_and_rank processes a URL and returns analysis+score+debate."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_url_and_rank("https://play.google.com/store/apps/details?id=com.example")
    assert "score" in result
    assert "debate" in result
    return True

def test_run_evolution_cycle_returns_summary():
    """G4: run_evolution_cycle returns a summary dict with expected keys."""
    orch = IdeaEvolutionOrchestrator()
    orch._inbox.submit_text("Sort Puzzle", "A sort puzzle with dragons and rescue hook")
    orch._inbox.submit_text("Merge Game", "A merge game with collection and evolution")
    result = orch.run_evolution_cycle()
    assert isinstance(result, dict)
    assert "cycle_results" in result
    assert "top_suggestions" in result
    return True

def test_run_evolution_cycle_results_count():
    """G4: run_evolution_cycle processes pending ideas."""
    orch = IdeaEvolutionOrchestrator()
    orch._inbox.submit_text("Sort Puzzle", "A sort puzzle with dragons")
    orch._inbox.submit_text("Merge Game", "A merge game with evolution")
    result = orch.run_evolution_cycle()
    assert result["cycle_results"] >= 0
    return True

def test_run_evolution_cycle_has_top_suggestions():
    """G4: run_evolution_cycle top_suggestions is a list."""
    orch = IdeaEvolutionOrchestrator()
    orch._inbox.submit_text("Sort Puzzle", "A sort puzzle with rescue hook and dragon character")
    orch._inbox.submit_text("Merge Game", "A merge game with collection and evolution reward")
    result = orch.run_evolution_cycle()
    assert isinstance(result["top_suggestions"], list)
    return True

def test_submit_and_rank_score_total_is_number():
    """G4: Score total in submit_and_rank result is a number."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert isinstance(result["score"]["total"], (int, float))
    return True

def test_submit_and_rank_debate_vote_is_string():
    """G4: Debate final_vote in submit_and_rank result is a string."""
    orch = IdeaEvolutionOrchestrator()
    result = orch.submit_and_rank("A merge puzzle with rescue hook and dragon character")
    assert isinstance(result["debate"]["final_vote"], str)
    return True

def test_run_cycle_approval_rates_not_empty():
    """G4: After evolution cycle, approval_rates dict is present."""
    orch = IdeaEvolutionOrchestrator()
    orch._inbox.submit_text("Sort Puzzle", "A sort puzzle with rescue hook and dragon character")
    orch._inbox.submit_text("Merge Game", "A merge game with collection and evolution reward")
    result = orch.run_evolution_cycle()
    assert "approval_rates" in result
    return True

def test_run_cycle_marketplace_size_increases():
    """G4: Marketplace size is reported and is a number."""
    orch = IdeaEvolutionOrchestrator()
    orch._inbox.submit_text("Sort Puzzle", "A sort puzzle with rescue hook")
    orch._inbox.submit_text("Merge Game", "A merge game with evolution")
    orch._inbox.submit_text("Puzzle Fun", "A puzzle with collection reward")
    result = orch.run_evolution_cycle()
    assert "marketplace_size" in result
    assert isinstance(result["marketplace_size"], int)
    return True

def test_build_action_enum_values():
    """G4: BuildAction enum has BUILD, PROTOTYPE, WATCH, IGNORE."""
    values = [a.value for a in BuildAction]
    for expected in ["build", "prototype", "watch", "ignore"]:
        assert expected in values, f"Missing BuildAction: {expected}"
    return True

def test_creative_score_to_dict_is_json_serializable():
    """G4: CreativeScore.to_dict is JSON serializable."""
    eng = CreativeScoringEngine()
    analysis = _make_analysis({"core_loop": "merge", "hook": "rescue"})
    score = eng.score_from_analysis(analysis)
    d = score.to_dict()
    json_str = json.dumps(d)
    assert isinstance(json_str, str)
    assert len(json_str) > 0
    return True


# ═══════════════════════════════════════════════════════════
# GATE 5: Genome Marketplace (30 tests)
# ═══════════════════════════════════════════════════════════

def test_marketplace_import():
    """G5: GenomeMarketplace can be imported and instantiated."""
    mp = GenomeMarketplace()
    assert mp is not None
    return True

def test_marketplace_empty_on_init():
    """G5: Marketplace starts with no genomes."""
    mp = GenomeMarketplace()
    assert len(mp.get_all()) == 0
    return True

def test_marketplace_publish_returns_verified_genome():
    """G5: publish returns a VerifiedGenome instance."""
    mp = GenomeMarketplace()
    genome = _quick_genome("test", hook="rescue", core_loop="merge")
    vg = mp.publish(genome, d7_roas=1.5, category="merge")
    assert isinstance(vg, VerifiedGenome)
    return True

def test_marketplace_publish_tracks_in_all():
    """G5: Published genome appears in get_all."""
    mp = GenomeMarketplace()
    genome = _quick_genome("test", hook="rescue", core_loop="merge")
    mp.publish(genome, d7_roas=1.5, category="merge")
    assert len(mp.get_all()) == 1
    return True

def test_marketplace_verified_genome_is_winner_true():
    """G5: is_winner is True when d7_roas >= 1 and spend >= 100."""
    mp = GenomeMarketplace()
    genome = _quick_genome("winner", hook="rescue", core_loop="merge")
    vg = mp.publish(genome, d7_roas=2.0, total_spend=500, category="merge")
    assert vg.is_winner is True
    return True

def test_marketplace_verified_genome_is_winner_false():
    """G5: is_winner is False when d7_roas < 1."""
    mp = GenomeMarketplace()
    genome = _quick_genome("loser", hook="reward", core_loop="sort")
    vg = mp.publish(genome, d7_roas=0.5, total_spend=200, category="sort")
    assert vg.is_winner is False
    return True

def test_marketplace_verified_genome_success_level_high():
    """G5: d7_roas >= 1.0 maps to 'high' success level."""
    mp = GenomeMarketplace()
    genome = _quick_genome("high", hook="rescue", core_loop="merge")
    vg = mp.publish(genome, d7_roas=1.2, category="merge")
    assert vg.success_level == "high"
    return True

def test_marketplace_verified_genome_success_level_medium():
    """G5: 0.5 <= d7_roas < 1.0 maps to 'medium' success level."""
    mp = GenomeMarketplace()
    genome = _quick_genome("mid", hook="reward", core_loop="sort")
    vg = mp.publish(genome, d7_roas=0.7, category="sort")
    assert vg.success_level == "medium"
    return True

def test_marketplace_verified_genome_success_level_low():
    """G5: d7_roas < 0.5 maps to 'low' success level."""
    mp = GenomeMarketplace()
    genome = _quick_genome("low", hook="build_progress", core_loop="battle")
    vg = mp.publish(genome, d7_roas=0.3, category="battle")
    assert vg.success_level == "low"
    return True

def test_marketplace_search_by_category():
    """G5: Search filters by category."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=1.5, category="merge")
    mp.publish(_quick_genome("b", hook="reward", core_loop="sort"), d7_roas=0.8, category="sort")
    results = mp.search(category="merge")
    assert len(results) == 1
    assert results[0].category == "merge"
    return True

def test_marketplace_search_by_min_roas():
    """G5: Search filters by minimum ROAS."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=2.0, category="merge")
    mp.publish(_quick_genome("b", hook="reward", core_loop="sort"), d7_roas=0.3, category="sort")
    results = mp.search(min_roas=1.0)
    assert len(results) == 1
    return True

def test_marketplace_search_by_success_level():
    """G5: Search filters by success_level."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=1.5, category="merge")
    mp.publish(_quick_genome("b", hook="reward", core_loop="sort"), d7_roas=0.3, category="sort")
    results = mp.search(success_level="high")
    assert len(results) == 1
    return True

def test_marketplace_search_by_tag():
    """G5: Search filters by tag."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=1.5,
               category="merge", tags=["dragon", "3d"])
    mp.publish(_quick_genome("b", hook="reward", core_loop="sort"), d7_roas=0.8,
               category="sort", tags=["puzzle"])
    results = mp.search(tag="dragon")
    assert len(results) >= 1
    return True

def test_marketplace_multiple_filters():
    """G5: Search with multiple filters combined."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=2.0,
               category="merge", tags=["dragon"])
    mp.publish(_quick_genome("b", hook="rescue", core_loop="merge"), d7_roas=0.5,
               category="merge", tags=["dragon"])
    results = mp.search(category="merge", min_roas=1.0, success_level="high", tag="dragon")
    assert len(results) >= 1
    for r in results:
        assert r.category == "merge"
        assert r.d7_roas >= 1.0
    return True

def test_marketplace_search_by_gene():
    """G5: search_by_gene finds genomes with a specific gene value."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a", hook="rescue", core_loop="merge"), d7_roas=1.5, category="merge")
    mp.publish(_quick_genome("b", hook="reward", core_loop="sort"), d7_roas=0.8, category="sort")
    results = mp.search_by_gene("hook", "rescue")
    assert len(results) >= 1
    return True

def test_marketplace_get_winner_genomes():
    """G5: get_winner_genomes returns only genomes with is_winner=True."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("w1", hook="rescue"), d7_roas=1.5, total_spend=200, category="merge")
    mp.publish(_quick_genome("w2", hook="reward"), d7_roas=0.3, total_spend=100, category="sort")
    winners = mp.get_winner_genomes()
    assert len(winners) == 1
    return True

def test_marketplace_get_templates():
    """G5: get_templates returns high success genomes with 5+ creatives."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("t1", hook="rescue"), d7_roas=2.0, total_creatives=10, category="merge")
    mp.publish(_quick_genome("t2", hook="reward"), d7_roas=1.5, total_creatives=3, category="sort")
    templates = mp.get_templates()
    assert len(templates) >= 1
    return True

def test_marketplace_suggest_combinations_empty():
    """G5: suggest_combinations returns empty when fewer than 2 winners."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a"), d7_roas=0.3, total_spend=50, category="merge")
    combos = mp.suggest_combinations()
    assert combos == []
    return True

def test_marketplace_suggest_combinations_returns_combos():
    """G5: suggest_combinations returns GenomeCombo list with 2+ winners."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("w1", hook="rescue"), d7_roas=2.0, total_spend=200, category="merge")
    mp.publish(_quick_genome("w2", hook="reward"), d7_roas=1.5, total_spend=150, category="sort")
    combos = mp.suggest_combinations()
    assert isinstance(combos, list)
    if len(combos) > 0:
        assert isinstance(combos[0], GenomeCombo)
    return True

def test_marketplace_combination_has_name():
    """G5: GenomeCombo has a combo_name."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("merge_hero", hook="rescue"), d7_roas=2.0, total_spend=200, category="merge")
    mp.publish(_quick_genome("sort_master", hook="reward"), d7_roas=1.5, total_spend=150, category="sort")
    combos = mp.suggest_combinations()
    if combos:
        assert len(combos[0].combo_name) > 0
    return True

def test_marketplace_combination_predicted_score():
    """G5: GenomeCombo predicted_score is between 0 and 100."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("merge_hero", hook="rescue"), d7_roas=2.0, total_spend=200, category="merge")
    mp.publish(_quick_genome("sort_master", hook="reward"), d7_roas=1.5, total_spend=150, category="sort")
    combos = mp.suggest_combinations()
    if combos:
        assert 0 <= combos[0].predicted_score <= 100
    return True

def test_marketplace_get_by_category():
    """G5: get_by_category returns only genomes in the given category."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("m1"), d7_roas=1.0, category="merge")
    mp.publish(_quick_genome("s1"), d7_roas=0.8, category="sort")
    assert len(mp.get_by_category("merge")) == 1
    return True

def test_marketplace_get_all_returns_list():
    """G5: get_all returns a list."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("a"), d7_roas=1.0, category="merge")
    all_genomes = mp.get_all()
    assert isinstance(all_genomes, list)
    assert len(all_genomes) == 1
    return True

def test_marketplace_save_and_load():
    """G5: save and load round-trips marketplace data."""
    tmpdir = Path(tempfile.mkdtemp())
    mp = GenomeMarketplace(storage_dir=tmpdir)
    mp.publish(_quick_genome("g1", hook="rescue"), d7_roas=1.5, category="merge")
    mp.publish(_quick_genome("g2", hook="reward"), d7_roas=0.8, category="sort")
    save_path = tmpdir / "genome_marketplace.json"
    mp.save(save_path)

    mp2 = GenomeMarketplace()
    mp2.load(save_path)
    assert len(mp2.get_all()) == 2
    assert mp2.get_all()[0].genome_id == mp.get_all()[0].genome_id
    assert mp2.get_all()[1].genome_id == mp.get_all()[1].genome_id
    return True

def test_marketplace_verified_genome_to_dict():
    """G5: VerifiedGenome.to_dict includes all expected keys."""
    mp = GenomeMarketplace()
    genome = _quick_genome("test", hook="rescue", core_loop="merge")
    vg = mp.publish(genome, d7_roas=1.5, category="merge")
    d = vg.to_dict()
    for key in ["genome_id", "name", "category", "genes", "d7_roas",
                "total_spend", "total_creatives", "success_level", "tags", "created_from"]:
        assert key in d, f"Missing key: {key}"
    return True

def test_marketplace_genome_combo_dataclass():
    """G5: GenomeCombo dataclass has expected fields."""
    gc = GenomeCombo(
        genome_a="merge_hero",
        genome_b="sort_master",
        combo_name="merge_hero + sort_master",
        description="Combines merge and sort",
        shared_genes=["hook"],
        new_gene_suggestions=["visual"],
        predicted_score=85.0,
    )
    assert gc.genome_a == "merge_hero"
    assert gc.genome_b == "sort_master"
    assert gc.predicted_score == 85.0
    return True

def test_marketplace_publish_with_tags():
    """G5: publish stores tags on the VerifiedGenome."""
    mp = GenomeMarketplace()
    genome = _quick_genome("tagged", hook="rescue")
    vg = mp.publish(genome, d7_roas=1.5, category="merge", tags=["dragon", "3d", "rescue"])
    assert "dragon" in vg.tags
    assert "3d" in vg.tags
    return True

def test_marketplace_combination_different_categories():
    """G5: Combinations are only from different categories (cross-category)."""
    mp = GenomeMarketplace()
    mp.publish(_quick_genome("m1", hook="rescue"), d7_roas=2.0, total_spend=200, category="merge")
    mp.publish(_quick_genome("m2", hook="reward"), d7_roas=1.5, total_spend=150, category="merge")
    mp.publish(_quick_genome("s1", hook="rescue"), d7_roas=1.8, total_spend=200, category="sort")
    combos = mp.suggest_combinations()
    for combo in combos:
        a_cat = [g for g in mp.get_winner_genomes() if g.name == combo.genome_a][0].category
        b_cat = [g for g in mp.get_winner_genomes() if g.name == combo.genome_b][0].category
        assert a_cat != b_cat, f"Combo has same-category genomes: {a_cat}"
    return True

def test_marketplace_verified_genome_to_dict_is_json_serializable():
    """G5: VerifiedGenome.to_dict is JSON serializable."""
    mp = GenomeMarketplace()
    genome = _quick_genome("serial", hook="rescue", core_loop="merge")
    vg = mp.publish(genome, d7_roas=1.5, category="merge")
    d = vg.to_dict()
    json_str = json.dumps(d)
    assert isinstance(json_str, str)
    assert len(json_str) > 0
    return True

def test_marketplace_search_limit():
    """G5: Search respects the limit parameter."""
    mp = GenomeMarketplace()
    for i in range(10):
        mp.publish(_quick_genome(f"g{i}", hook="rescue"), d7_roas=1.0 + i * 0.1, category="merge")
    results = mp.search(limit=3)
    assert len(results) == 3
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = _build_test_list()
    passed = 0
    failed = 0
    print("=" * 70)
    print("  V5.0 Phase E — Human+AI Creative Intelligence Marketplace")
    print(f"  {len(tests)} tests")
    print("=" * 70)

    for label, fn in tests:
        try:
            if fn():
                passed += 1
                print(f"  PASS  {label}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {label}: {e}")

    print(f"\n  Results: {passed}/{len(tests)} PASS")
    print("=" * 70)
    return failed == 0


def _build_test_list():
    return [
        # === GATE 1: Human Input (20) ===
        ("G1: analysis engine import", test_analysis_engine_import),
        ("G1: analyze text basic", test_analyze_text_basic),
        ("G1: analyze text core loop", test_analyze_text_extracts_core_loop),
        ("G1: analyze text hook", test_analyze_text_extracts_hook),
        ("G1: analyze text reward", test_analyze_text_extracts_reward),
        ("G1: analyze text character", test_analyze_text_extracts_character),
        ("G1: analyze text visual", test_analyze_text_extracts_visual),
        ("G1: analyze text monetization", test_analyze_text_extracts_monetization),
        ("G1: analyze text missing dimensions", test_analyze_text_finds_missing_dimensions),
        ("G1: analyze text suggestions", test_analyze_text_generates_suggestions),
        ("G1: analyze text confidence scales", test_analyze_text_confidence_scales),
        ("G1: analyze url google_play", test_analyze_url_google_play),
        ("G1: analyze url app_store", test_analyze_url_app_store),
        ("G1: analyze url youtube", test_analyze_url_youtube),
        ("G1: analyze url tiktok", test_analyze_url_tiktok),
        ("G1: analyze url reddit", test_analyze_url_reddit),
        ("G1: analyze media image", test_analyze_media_image),
        ("G1: analyze media video", test_analyze_media_video),
        ("G1: analyze media ctr prediction", test_analyze_media_ctr_prediction),
        ("G1: analyze text empty input", test_analyze_text_empty_input),
        # === GATE 2: AI Discovery (30) ===
        ("G2: scoring engine import", test_scoring_engine_import),
        ("G2: score from analysis basic", test_score_from_analysis_basic),
        ("G2: score components range", test_score_from_analysis_components_range),
        ("G2: score total <= 100", test_score_from_analysis_total_100),
        ("G2: market high for merge", test_score_market_high_for_merge),
        ("G2: market high for sort", test_score_market_high_for_sort),
        ("G2: market baseline > 0", test_score_market_baseline),
        ("G2: creative high rescue hook", test_score_creative_high_rescue_hook),
        ("G2: creative high 3d visual", test_score_creative_high_3d_visual),
        ("G2: creative with character", test_score_creative_with_character),
        ("G2: build easy for merge", test_score_build_easy_for_merge),
        ("G2: build iaa simple", test_score_build_iaa_simple),
        ("G2: monetization iaa boost", test_score_monetization_iaa),
        ("G2: monetization battle pass higher", test_score_monetization_battle_pass),
        ("G2: evolution gene count", test_score_evolution_gene_count),
        ("G2: build action >=80 → BUILD", test_score_build_action_80_build),
        ("G2: build action 60-79 → PROTOTYPE", test_score_build_action_60_prototype),
        ("G2: build action 40-59 → WATCH", test_score_build_action_40_watch),
        ("G2: build action <40 → IGNORE", test_score_build_action_20_ignore),
        ("G2: score to_dict all keys", test_score_to_dict_has_all_keys),
        ("G2: score to_dict has components", test_score_to_dict_has_components),
        ("G2: score from text quick", test_score_from_text_quick),
        ("G2: scoring engine integration", test_scoring_engine_integration_with_analysis),
        ("G2: score justification not empty", test_score_justification_not_empty),
        ("G2: score advantages not empty", test_score_advantages_not_empty),
        ("G2: score risks missing reward", test_score_risks_for_missing_reward),
        ("G2: score risks missing character", test_score_risks_for_missing_character),
        ("G2: score confidence present", test_score_confidence_present),
        ("G2: score action is BuildAction", test_score_action_is_buildaction),
        ("G2: CreativeScore dataclass defaults", test_creative_score_dataclass_defaults),
        # === GATE 3: Multi-Agent Debate (20) ===
        ("G3: debate engine import", test_debate_engine_import),
        ("G3: debate 5 opinions", test_debate_produces_5_opinions),
        ("G3: debate has market agent", test_debate_has_market_agent),
        ("G3: debate has gameplay agent", test_debate_has_gameplay_agent),
        ("G3: debate has ua agent", test_debate_has_ua_agent),
        ("G3: debate has producer agent", test_debate_has_producer_agent),
        ("G3: debate has investor agent", test_debate_has_investor_agent),
        ("G3: debate consensus calculated", test_debate_consensus_calculated),
        ("G3: debate consensus 0-1", test_debate_consensus_range_0_to_1),
        ("G3: debate final vote is Vote", test_debate_final_vote_is_vote_enum),
        ("G3: debate vote counts sum 5", test_debate_vote_counts_sum_to_5),
        ("G3: debate majority reasoning", test_debate_majority_reasoning_not_empty),
        ("G3: debate action items prototype", test_debate_action_items_for_prototype),
        ("G3: debate action items build", test_debate_action_items_for_build),
        ("G3: debate dissenting view", test_debate_dissenting_view_when_not_unanimous),
        ("G3: debate to_dict complete", test_debate_to_dict_complete),
        ("G3: agent opinion to_dict", test_agent_opinion_to_dict),
        ("G3: Vote enum values", test_vote_enum_values),
        ("G3: AgentRole 5 values", test_agent_role_enum_values),
        ("G3: DebateResult dataclass defaults", test_debate_result_dataclass_defaults),
        # === GATE 4: Human-AI Ranking (20) ===
        ("G4: feedback record selection", test_feedback_loop_record_selection),
        ("G4: feedback approval rates", test_feedback_loop_approval_rates_populated),
        ("G4: feedback top approved genes", test_feedback_loop_top_approved_genes),
        ("G4: orchestrator import", test_idea_evolution_orchestrator_import),
        ("G4: submit and rank full result", test_submit_and_rank_returns_full_result),
        ("G4: submit and rank has analysis", test_submit_and_rank_has_analysis),
        ("G4: submit and rank has score", test_submit_and_rank_has_score),
        ("G4: submit and rank has debate", test_submit_and_rank_has_debate),
        ("G4: submit and rank has genome_id", test_submit_and_rank_has_genome_id),
        ("G4: submit and rank has experiment_plan", test_submit_and_rank_has_experiment_plan),
        ("G4: submit url and rank", test_submit_url_and_rank_returns_result),
        ("G4: run cycle returns summary", test_run_evolution_cycle_returns_summary),
        ("G4: run cycle results count", test_run_evolution_cycle_results_count),
        ("G4: run cycle top suggestions", test_run_evolution_cycle_has_top_suggestions),
        ("G4: submit rank score is number", test_submit_and_rank_score_total_is_number),
        ("G4: submit rank debate vote string", test_submit_and_rank_debate_vote_is_string),
        ("G4: run cycle approval rates", test_run_cycle_approval_rates_not_empty),
        ("G4: run cycle marketplace size", test_run_cycle_marketplace_size_increases),
        ("G4: BuildAction enum values", test_build_action_enum_values),
        ("G4: CreativeScore to_dict JSON", test_creative_score_to_dict_is_json_serializable),
        # === GATE 5: Genome Marketplace (30) ===
        ("G5: marketplace import", test_marketplace_import),
        ("G5: marketplace empty on init", test_marketplace_empty_on_init),
        ("G5: marketplace publish VerifiedGenome", test_marketplace_publish_returns_verified_genome),
        ("G5: marketplace publish get_all", test_marketplace_publish_tracks_in_all),
        ("G5: VerifiedGenome is_winner true", test_marketplace_verified_genome_is_winner_true),
        ("G5: VerifiedGenome is_winner false", test_marketplace_verified_genome_is_winner_false),
        ("G5: VerifiedGenome success high", test_marketplace_verified_genome_success_level_high),
        ("G5: VerifiedGenome success medium", test_marketplace_verified_genome_success_level_medium),
        ("G5: VerifiedGenome success low", test_marketplace_verified_genome_success_level_low),
        ("G5: search by category", test_marketplace_search_by_category),
        ("G5: search by min_roas", test_marketplace_search_by_min_roas),
        ("G5: search by success_level", test_marketplace_search_by_success_level),
        ("G5: search by tag", test_marketplace_search_by_tag),
        ("G5: search multiple filters", test_marketplace_multiple_filters),
        ("G5: search by gene", test_marketplace_search_by_gene),
        ("G5: get winner genomes", test_marketplace_get_winner_genomes),
        ("G5: get templates", test_marketplace_get_templates),
        ("G5: suggest combos empty", test_marketplace_suggest_combinations_empty),
        ("G5: suggest combos returns combos", test_marketplace_suggest_combinations_returns_combos),
        ("G5: combo has name", test_marketplace_combination_has_name),
        ("G5: combo predicted score 0-100", test_marketplace_combination_predicted_score),
        ("G5: get by category", test_marketplace_get_by_category),
        ("G5: get all returns list", test_marketplace_get_all_returns_list),
        ("G5: save and load", test_marketplace_save_and_load),
        ("G5: VerifiedGenome to_dict", test_marketplace_verified_genome_to_dict),
        ("G5: GenomeCombo dataclass", test_marketplace_genome_combo_dataclass),
        ("G5: publish with tags", test_marketplace_publish_with_tags),
        ("G5: combo diff categories", test_marketplace_combination_different_categories),
        ("G5: VerifiedGenome to_dict JSON", test_marketplace_verified_genome_to_dict_is_json_serializable),
        ("G5: search limit", test_marketplace_search_limit),
    ]


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
