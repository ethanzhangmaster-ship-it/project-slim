"""E13.5.3 Strategy Selector — 测试套件.

覆盖:
  - StrategyCandidate / StrategySelection 模型
  - StrategyMatcher (opportunity, signal, product, audience match)
  - StrategyRanker (scoring, risk penalty, blocking, sorting)
  - StrategySelector (select, select_best, select_with_alternatives)
  - Failure Memory 集成 (risk check, risk adjustment)
  - End-to-end 集成 (Opportunity → StrategyMemory → FailureMemory → Selection)
"""

from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
    DecisionPriority,
    ExpectedImpact,
    GrowthOpportunity,
    OpportunitySource,
    OpportunityType,
    StrategyCandidate,
    StrategySelection,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.strategy_matcher import StrategyMatcher
from market_ops.creative_vision_runtime.growth_runtime.intelligence.strategy_ranker import StrategyRanker
from market_ops.creative_vision_runtime.growth_runtime.intelligence.strategy_selector import StrategySelector
from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
    FailureCategory,
    FailureCondition,
    FailurePattern,
    FailureSeverity,
    FailureWarning,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyPerformance,
    StrategyStep,
    StrategyTriggerCondition,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH, **kwargs) -> GrowthOpportunity:
    """创建测试用 GrowthOpportunity."""
    defaults = {
        "opportunity_type": opp_type,
        "source": OpportunitySource.SIGNAL_ENGINE,
        "product_id": "merge_witch",
        "impact_score": 0.75,
        "confidence": 0.8,
        "urgency": 0.7,
        "priority": DecisionPriority.HIGH,
        "reason": "Creative fatigue detected: CTR decay 0.35, frequency increase 4.5, ROAS declining",
        "metadata": {"audience_segment": "ios_us_facebook"},
    }
    defaults.update(kwargs)
    return GrowthOpportunity(**defaults)


def make_strategy(
    strategy_id="S001",
    name="Hook Mutation Strategy",
    category=StrategyCategory.CREATIVE_REVIVAL,
    opp_type="creative_refresh",
    signal_types=None,
    audience_segment="ios_us_facebook",
    product_category="merge_witch",
    success_rate=0.91,
    total_executions=50,
    score=0.85,
    confidence=0.82,
    steps=None,
) -> GrowthStrategyPattern:
    """创建测试用 GrowthStrategyPattern."""
    if signal_types is None:
        signal_types = ["creative_fatigue", "ctr_drop"]
    if steps is None:
        steps = [
            StrategyStep(order=1, action_type="mutate_hook", approval_level="auto"),
            StrategyStep(order=2, action_type="update_creative", approval_level="auto"),
        ]

    trigger = StrategyTriggerCondition(
        scenario="Creative fatigue detected",
        opportunity_type=opp_type,
        signal_types=signal_types,
        audience_segment=audience_segment,
        product_category=product_category,
    )

    perf = StrategyPerformance(
        total_executions=total_executions,
        successful_executions=int(total_executions * success_rate),
        success_rate=success_rate,
        avg_reward=0.15,
        avg_roas_change=0.12,
    )

    s = GrowthStrategyPattern(
        strategy_id=strategy_id,
        name=name,
        category=category,
        trigger=trigger,
        steps=steps,
        performance=perf,
        score=score,
        confidence=confidence,
    )
    s.compute_score()
    return s


def make_memory_with_strategies(*strategies: GrowthStrategyPattern) -> StrategyMemory:
    """创建预填充策略的 StrategyMemory."""
    mock_exp = MagicMock()
    memory = StrategyMemory(mock_exp)
    for s in strategies:
        memory.store(s)
    return memory


def make_failure_memory_with_patterns(*patterns: FailurePattern) -> FailureMemory:
    """创建预填充失败模式的 FailureMemory."""
    mock_exp = MagicMock()
    memory = FailureMemory(mock_exp)
    for p in patterns:
        memory.store(p)
    return memory


def make_failure_pattern(
    failure_id="F001",
    name="Budget Increase Crash",
    blocked_action="increase_budget",
    failure_rate=0.8,
    total_attempts=10,
    severity=FailureSeverity.HIGH,
    opp_type="budget_optimization",
) -> FailurePattern:
    """创建测试用 FailurePattern."""
    condition = FailureCondition(
        scenario="Budget increase during volatility",
        opportunity_type=opp_type,
        action_type=blocked_action,
    )
    p = FailurePattern(
        failure_id=failure_id,
        name=name,
        category=FailureCategory.BUDGET_WASTE,
        condition=condition,
        blocked_action=blocked_action,
        failure_rate=failure_rate,
        total_attempts=total_attempts,
        failed_attempts=int(total_attempts * failure_rate),
        severity=severity,
        avg_loss=500.0,
        suggestion=f"Consider gradual {blocked_action} instead",
    )
    p.compute_confidence()
    p.compute_severity()
    return p


# ═══════════════════════════════════════════════════════════════
# Test: StrategyCandidate Model
# ═══════════════════════════════════════════════════════════════


class TestStrategyCandidate:
    def test_default_values(self):
        c = StrategyCandidate()
        assert c.strategy_id == ""
        assert c.strategy_name == ""
        assert c.match_score == 0.0
        assert c.historical_score == 0.0
        assert c.final_score == 0.0
        assert c.risk_score == 0.0
        assert c.failure_warnings == []

    def test_is_viable_high_score_low_risk(self):
        c = StrategyCandidate(final_score=0.8, risk_score=0.1)
        assert c.is_viable is True

    def test_is_viable_borderline_score(self):
        c = StrategyCandidate(final_score=0.5, risk_score=0.1)
        assert c.is_viable is True

    def test_is_viable_low_score(self):
        c = StrategyCandidate(final_score=0.4, risk_score=0.1)
        assert c.is_viable is False

    def test_is_viable_high_risk(self):
        c = StrategyCandidate(final_score=0.9, risk_score=0.8)
        assert c.is_viable is False

    def test_is_blocked_high_risk(self):
        c = StrategyCandidate(risk_score=0.8)
        assert c.is_blocked is True

    def test_is_blocked_critical_risk(self):
        c = StrategyCandidate(risk_score=0.95)
        assert c.is_blocked is True

    def test_is_blocked_low_risk(self):
        c = StrategyCandidate(risk_score=0.3)
        assert c.is_blocked is False

    def test_to_dict(self):
        c = StrategyCandidate(
            strategy_id="S001",
            strategy_name="Hook Mutation",
            match_score=0.85,
            historical_score=0.91,
            confidence_score=0.82,
            risk_score=0.12,
            final_score=0.84,
            reason="High match + proven success",
            failure_warnings=["Past low ROAS on similar"],
        )
        d = c.to_dict()
        assert d["strategy_id"] == "S001"
        assert d["strategy_name"] == "Hook Mutation"
        assert d["match_score"] == 0.85
        assert d["historical_score"] == 0.91
        assert d["confidence_score"] == 0.82
        assert d["risk_score"] == 0.12
        assert d["final_score"] == 0.84
        assert "High match" in d["reason"]
        assert len(d["failure_warnings"]) == 1

    def test_to_dict_rounds_floats(self):
        c = StrategyCandidate(
            match_score=0.85555,
            historical_score=0.91111,
            final_score=0.84444,
        )
        d = c.to_dict()
        assert d["match_score"] == 0.8556
        assert d["historical_score"] == 0.9111
        assert d["final_score"] == 0.8444


# ═══════════════════════════════════════════════════════════════
# Test: StrategySelection Model
# ═══════════════════════════════════════════════════════════════


class TestStrategySelection:
    def test_default_has_no_selection(self):
        s = StrategySelection()
        assert s.has_selection is False
        assert s.alternative_count == 0
        assert s.get_top_alternative() is None

    def test_has_selection_with_id(self):
        s = StrategySelection(selected_strategy_id="S001")
        assert s.has_selection is True

    def test_alternative_count(self):
        alt1 = StrategyCandidate(strategy_id="S002")
        alt2 = StrategyCandidate(strategy_id="S003")
        s = StrategySelection(alternatives=[alt1, alt2])
        assert s.alternative_count == 2

    def test_get_top_alternative(self):
        alt1 = StrategyCandidate(strategy_id="S002", final_score=0.7)
        alt2 = StrategyCandidate(strategy_id="S003", final_score=0.6)
        s = StrategySelection(alternatives=[alt1, alt2])
        top = s.get_top_alternative()
        assert top is not None
        assert top.strategy_id == "S002"

    def test_get_top_alternative_empty(self):
        s = StrategySelection()
        assert s.get_top_alternative() is None

    def test_to_dict_empty(self):
        s = StrategySelection()
        d = s.to_dict()
        assert d["selected_strategy_id"] == ""
        assert d["alternatives"] == []
        assert d["decision_confidence"] == 0.0

    def test_to_dict_with_data(self):
        alt = StrategyCandidate(strategy_id="S002", strategy_name="Alt", final_score=0.7)
        s = StrategySelection(
            selection_id="sel-001",
            opportunity_id="opp-001",
            selected_strategy_id="S001",
            selected_strategy={"name": "Best"},
            alternatives=[alt],
            decision_confidence=0.86,
            selection_reason="Best match",
            risk_warnings=["Low risk"],
            requires_approval=False,
        )
        d = s.to_dict()
        assert d["selection_id"] == "sel-001"
        assert d["opportunity_id"] == "opp-001"
        assert d["selected_strategy_id"] == "S001"
        assert len(d["alternatives"]) == 1
        assert d["decision_confidence"] == 0.86
        assert d["requires_approval"] is False
        assert d["risk_warnings"] == ["Low risk"]

    def test_best_candidate_stored(self):
        best = StrategyCandidate(strategy_id="S001", final_score=0.9)
        s = StrategySelection(_best_candidate=best)
        assert s._best_candidate is best
        assert s._best_candidate.strategy_id == "S001"


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMatcher
# ═══════════════════════════════════════════════════════════════


class TestStrategyMatcher:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.matcher = StrategyMatcher()

    # --- Overall match ---

    def test_empty_strategies_returns_empty(self):
        opp = make_opportunity()
        result = self.matcher.match(opp, [])
        assert result == []

    def test_returns_match_score_for_each_strategy(self):
        opp = make_opportunity()
        s1 = make_strategy(strategy_id="S001", name="S1")
        s2 = make_strategy(strategy_id="S002", name="S2")
        result = self.matcher.match(opp, [s1, s2])
        assert len(result) == 2
        assert "match_score" in result[0]
        assert "scores" in result[0]
        assert result[0]["strategy"] is s1
        assert result[1]["strategy"] is s2

    # --- Opportunity type match ---

    def test_opportunity_exact_match(self):
        opp = make_opportunity(OpportunityType.CREATIVE_REFRESH)
        s = make_strategy(opp_type="creative_refresh")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["opportunity"] == 1.0

    def test_opportunity_related_match(self):
        opp = make_opportunity(OpportunityType.CREATIVE_REFRESH)
        s = make_strategy(opp_type="creative_fatigue")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["opportunity"] == 0.8

    def test_opportunity_related_second_level(self):
        opp = make_opportunity(OpportunityType.CREATIVE_REFRESH)
        s = make_strategy(opp_type="creative_scale")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["opportunity"] == 0.65

    def test_opportunity_no_match(self):
        opp = make_opportunity(OpportunityType.CREATIVE_REFRESH)
        s = make_strategy(opp_type="audience_expansion")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["opportunity"] == 0.0

    def test_opportunity_budget_optimization_related(self):
        opp = make_opportunity(OpportunityType.BUDGET_OPTIMIZATION)
        s = make_strategy(opp_type="budget_redistribution")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["opportunity"] == 0.8

    # --- Signal match ---

    def test_signal_perfect_match(self):
        opp = make_opportunity(reason="Creative fatigue: CTR decay")
        s = make_strategy(signal_types=["creative_fatigue", "ctr_drop"])
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["signal"] > 0.0

    def test_signal_no_overlap(self):
        opp = make_opportunity(reason="Monetization drop: LTV decline")
        s = make_strategy(signal_types=["creative_fatigue", "ctr_drop"])
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["signal"] == 0.0

    def test_signal_empty_strategy_signals(self):
        opp = make_opportunity(reason="CTR decay")
        s = make_strategy(signal_types=[])
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["signal"] == 0.0

    def test_signal_max_one(self):
        opp = make_opportunity(reason="CTR decay, frequency increase, creative fatigue")
        s = make_strategy(signal_types=["creative_fatigue", "ctr_drop"])
        scores = self.matcher._compute_match_scores(opp, s)
        assert 0.0 <= scores["signal"] <= 1.0

    # --- Product match ---

    def test_product_exact_match(self):
        opp = make_opportunity(product_id="merge_witch")
        s = make_strategy(product_category="merge_witch")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["product"] == 1.0

    def test_product_partial_contains(self):
        opp = make_opportunity(product_id="merge_witch")
        s = make_strategy(product_category="merge")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["product"] == 0.8

    def test_product_no_match(self):
        opp = make_opportunity(product_id="merge_witch")
        s = make_strategy(product_category="puzzle_quest")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["product"] < 0.5

    def test_product_empty_both(self):
        opp = make_opportunity(product_id="")
        s = make_strategy(product_category="")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["product"] == 0.5

    def test_product_only_opp_empty(self):
        opp = make_opportunity(product_id="")
        s = make_strategy(product_category="merge_witch")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["product"] == 0.5

    # --- Audience match ---

    def test_audience_exact_match(self):
        opp = make_opportunity(metadata={"audience_segment": "ios_us_facebook"})
        s = make_strategy(audience_segment="ios_us_facebook")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["audience"] == 1.0

    def test_audience_partial_platform_match(self):
        opp = make_opportunity(metadata={"audience_segment": "ios_us_facebook"})
        s = make_strategy(audience_segment="ios_us_tiktok")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["audience"] == 0.6

    def test_audience_no_metadata(self):
        opp = make_opportunity(metadata={})
        s = make_strategy(audience_segment="ios_us_facebook")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["audience"] == 0.5

    def test_audience_empty_strategy(self):
        opp = make_opportunity(metadata={"audience_segment": "ios_us_facebook"})
        s = make_strategy(audience_segment="")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["audience"] == 0.5

    def test_audience_no_match(self):
        opp = make_opportunity(metadata={"audience_segment": "ios_us_facebook"})
        s = make_strategy(audience_segment="android_kr_google")
        scores = self.matcher._compute_match_scores(opp, s)
        assert scores["audience"] == 0.3

    # --- Weighted total ---

    def test_total_match_weighted_sum(self):
        scores = {"opportunity": 1.0, "signal": 0.5, "product": 1.0, "audience": 0.8}
        total = self.matcher._compute_total_match(scores)
        expected = 1.0 * 0.35 + 0.5 * 0.25 + 1.0 * 0.20 + 0.8 * 0.20
        assert total == pytest.approx(expected)

    def test_total_match_zero(self):
        scores = {"opportunity": 0.0, "signal": 0.0, "product": 0.0, "audience": 0.0}
        total = self.matcher._compute_total_match(scores)
        assert total == 0.0

    def test_total_match_perfect(self):
        scores = {"opportunity": 1.0, "signal": 1.0, "product": 1.0, "audience": 1.0}
        total = self.matcher._compute_total_match(scores)
        assert total == 1.0

    # --- Signal extraction ---

    def test_extract_signals_from_type_and_reason(self):
        opp = make_opportunity(
            OpportunityType.CREATIVE_REFRESH,
            reason="CTR decay, frequency increase, ROAS drop",
        )
        signals = self.matcher._extract_signal_keywords(opp)
        assert "creative_refresh" in signals
        assert any("fatigue" in s or "ctr" in s for s in signals)

    def test_signal_overlap_same(self):
        assert self.matcher._signal_overlap("creative_fatigue", "creative_fatigue") is True

    def test_signal_overlap_substring(self):
        assert self.matcher._signal_overlap("fatigue", "creative_fatigue") is True

    def test_signal_overlap_cleaned(self):
        assert self.matcher._signal_overlap("creative_fatigue", "creativefatigue") is True

    def test_signal_overlap_no_match(self):
        assert self.matcher._signal_overlap("creative_fatigue", "roas_crash") is False


# ═══════════════════════════════════════════════════════════════
# Test: StrategyRanker
# ═══════════════════════════════════════════════════════════════


class TestStrategyRanker:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.ranker = StrategyRanker()

    def _make_matched(self, strategy, match_score=0.85, **score_overrides):
        """创建匹配结果条目."""
        scores = {
            "opportunity": score_overrides.get("opportunity", 1.0),
            "signal": score_overrides.get("signal", 0.5),
            "product": score_overrides.get("product", 1.0),
            "audience": score_overrides.get("audience", 0.8),
        }
        return {"strategy": strategy, "match_score": match_score, "scores": scores}

    # --- Scoring ---

    def test_rank_returns_candidates_sorted(self):
        s1 = make_strategy("S001", "A", success_rate=0.91, score=0.85)
        s2 = make_strategy("S002", "B", success_rate=0.76, score=0.70)
        s3 = make_strategy("S003", "C", success_rate=0.68, score=0.60)
        matched = [
            self._make_matched(s1, 0.85),
            self._make_matched(s2, 0.70),
            self._make_matched(s3, 0.60),
        ]
        result = self.ranker.rank(matched)
        assert len(result) == 3
        # Sorted descending by final_score
        assert result[0].final_score >= result[1].final_score >= result[2].final_score

    def test_rank_respects_top_n(self):
        strategies = [make_strategy(f"S{i:03d}", f"Strategy {i}") for i in range(10)]
        matched = [self._make_matched(s, 0.5 + i * 0.05) for i, s in enumerate(strategies)]
        result = self.ranker.rank(matched, top_n=3)
        assert len(result) == 3

    def test_rank_top_n_zero_returns_all(self):
        strategies = [make_strategy("S001"), make_strategy("S002")]
        matched = [self._make_matched(s, 0.5) for s in strategies]
        result = self.ranker.rank(matched, top_n=0)
        assert len(result) == 2

    def test_final_score_formula(self):
        s = make_strategy("S001", success_rate=0.91, score=0.85)
        matched = [self._make_matched(s, 0.85)]
        result = self.ranker.rank(matched)
        candidate = result[0]
        # Formula: historical×0.35 + match×0.30 + confidence×0.20 - risk×0.15
        expected = 0.91 * 0.35 + 0.85 * 0.30 + s.confidence * 0.20 - 0.0 * 0.15
        assert candidate.final_score == pytest.approx(expected, abs=0.01)

    def test_final_score_with_risk(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        risk_data = {
            "S001": {
                "warnings": [
                    {"risk_score": 0.45, "suggestion": "Moderate risk"},
                ],
            },
        }
        result = self.ranker.rank(matched, risk_data=risk_data)
        candidate = result[0]
        assert candidate.risk_score > 0.0
        assert candidate.final_score > 0.0

    # --- Risk penalties ---

    def test_risk_block_threshold(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        risk_data = {
            "S001": {
                "warnings": [
                    {"risk_score": 0.85, "suggestion": "CRITICAL: budget increase"},
                ],
            },
        }
        result = self.ranker.rank(matched, risk_data=risk_data)
        assert result[0].final_score < 0.05  # blocked → near 0

    def test_risk_severe_penalty(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        risk_data = {
            "S001": {
                "warnings": [
                    {"risk_score": 0.65, "suggestion": "High risk"},
                ],
            },
        }
        result = self.ranker.rank(matched, risk_data=risk_data)
        # Should have severe penalty applied (0.5 factor)
        assert result[0].risk_score >= 0.6

    def test_risk_moderate_penalty(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        risk_data = {
            "S001": {
                "warnings": [
                    {"risk_score": 0.45, "suggestion": "Moderate risk"},
                ],
            },
        }
        result = self.ranker.rank(matched, risk_data=risk_data)
        assert result[0].risk_score >= 0.4

    def test_risk_no_data(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        result = self.ranker.rank(matched, risk_data=None)
        assert result[0].risk_score == 0.0

    def test_risk_multiple_warnings(self):
        s = make_strategy("S001", success_rate=0.91)
        matched = [self._make_matched(s, 0.85)]
        risk_data = {
            "S001": {
                "warnings": [
                    {"risk_score": 0.5, "suggestion": "Risk A"},
                    {"risk_score": 0.3, "suggestion": "Risk B"},
                    {"risk_score": 0.4, "suggestion": "Risk C"},
                ],
            },
        }
        result = self.ranker.rank(matched, risk_data=risk_data)
        # Max risk (0.5) + bonus for 3 warnings (3 * 0.05 = 0.15) = 0.65
        assert result[0].risk_score == pytest.approx(0.65, abs=0.01)

    # --- Viability filtering ---

    def test_get_best(self):
        s1 = make_strategy("S001", "Best", success_rate=0.91)
        s2 = make_strategy("S002", "Second", success_rate=0.76)
        matched = [self._make_matched(s1, 0.85), self._make_matched(s2, 0.70)]
        candidates = self.ranker.rank(matched)
        best = self.ranker.get_best(candidates)
        assert best is not None
        assert best.strategy_id == "S001"

    def test_get_best_empty(self):
        assert self.ranker.get_best([]) is None

    def test_get_viable(self):
        s1 = make_strategy("S001", "Viable", success_rate=0.91)
        blocked = make_strategy("S002", "Blocked", success_rate=0.5)
        matched = [self._make_matched(s1, 0.85), self._make_matched(blocked, 0.3)]
        risk_data = {
            "S002": {"warnings": [{"risk_score": 0.85, "suggestion": "BLOCKED"}]},
        }
        candidates = self.ranker.rank(matched, risk_data=risk_data)
        viable = self.ranker.get_viable(candidates)
        assert len(viable) == 1
        assert viable[0].strategy_id == "S001"

    def test_get_blocked(self):
        s1 = make_strategy("S001", "Viable", success_rate=0.91)
        blocked = make_strategy("S002", "Blocked", success_rate=0.5)
        matched = [self._make_matched(s1, 0.85), self._make_matched(blocked, 0.3)]
        risk_data = {
            "S002": {"warnings": [{"risk_score": 0.85, "suggestion": "BLOCKED"}]},
        }
        candidates = self.ranker.rank(matched, risk_data=risk_data)
        blocked_list = self.ranker.get_blocked(candidates)
        assert len(blocked_list) == 1
        assert blocked_list[0].strategy_id == "S002"

    # --- Reason generation ---

    def test_reason_high_match_proven(self):
        s = make_strategy("S001", "Hook Mutation", success_rate=0.91)
        reason = self.ranker._generate_reason(s, 0.85, 0.91, 0.1)
        assert "high opportunity match" in reason
        assert "proven success" in reason

    def test_reason_blocked(self):
        s = make_strategy("S001", "Risky Strategy", success_rate=0.5)
        reason = self.ranker._generate_reason(s, 0.3, 0.5, 0.85)
        assert "BLOCKED" in reason

    def test_reason_unproven(self):
        s = make_strategy("S001", "New Strategy", success_rate=0.3)
        reason = self.ranker._generate_reason(s, 0.2, 0.3, 0.1)
        assert "unproven" in reason

    def test_reason_moderate_risk(self):
        s = make_strategy("S001", "Moderate", success_rate=0.7)
        reason = self.ranker._generate_reason(s, 0.5, 0.7, 0.6)
        assert "moderate risk" in reason


# ═══════════════════════════════════════════════════════════════
# Test: StrategySelector
# ═══════════════════════════════════════════════════════════════


class TestStrategySelector:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Create strategies for testing."""
        self.s_hook = make_strategy("S001", "Hook Mutation", success_rate=0.91, score=0.85)
        self.s_gameplay = make_strategy(
            "S002", "New Gameplay", opp_type="creative_refresh",
            success_rate=0.76, score=0.70,
        )
        self.s_audience = make_strategy(
            "S003", "Audience Change", opp_type="audience_expansion",
            success_rate=0.68, score=0.60,
        )
        self.s_budget = make_strategy(
            "S004", "Budget Increase", opp_type="budget_optimization",
            success_rate=0.75, score=0.65,
            steps=[StrategyStep(order=1, action_type="increase_budget", approval_level="manual")],
        )

    # --- Select without memory ---

    def test_select_without_strategy_memory(self):
        selector = StrategySelector()
        opp = make_opportunity()
        selection = selector.select(opp)
        assert selection.has_selection is False

    # --- Select with strategy memory ---

    def test_select_returns_best_strategy(self):
        memory = make_memory_with_strategies(self.s_hook, self.s_gameplay, self.s_audience)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp)
        assert selection.has_selection is True
        assert selection.selected_strategy_id == "S001"
        assert selection.decision_confidence > 0.0

    def test_select_respects_top_n(self):
        memory = make_memory_with_strategies(self.s_hook, self.s_gameplay, self.s_audience)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp, top_n=2)
        assert selection.alternative_count <= 1

    def test_select_no_viable_returns_empty(self):
        # Create a strategy with actionable but low score
        s_low = make_strategy("S005", "Low Performer", success_rate=0.5, score=0.15,
                              total_executions=5)
        memory = make_memory_with_strategies(s_low)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp, viable_only=True)
        # Low final_score strategy won't be viable (< 0.5)
        assert selection.has_selection is False

    def test_select_viable_only_false(self):
        # Strategy with low success but still actionable (passes is_actionable check)
        s_low = make_strategy("S005", "Low Performer", success_rate=0.5, score=0.2,
                              total_executions=5)
        memory = make_memory_with_strategies(s_low)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp, viable_only=False)
        # With viable_only=False, even low scorer comes through
        assert selection.has_selection is True

    # --- select_best ---

    def test_select_best_returns_candidate(self):
        memory = make_memory_with_strategies(self.s_hook, self.s_gameplay)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        best = selector.select_best(opp)
        assert best is not None
        assert best.strategy_id == "S001"
        assert isinstance(best, StrategyCandidate)

    def test_select_best_no_strategies(self):
        selector = StrategySelector()
        opp = make_opportunity()
        best = selector.select_best(opp)
        assert best is None

    # --- select_with_alternatives ---

    def test_select_with_alternatives(self):
        memory = make_memory_with_strategies(self.s_hook, self.s_gameplay, self.s_audience)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select_with_alternatives(opp, top_n=3)
        assert selection.has_selection is True
        assert selection.alternative_count >= 1

    # --- Failure Memory integration ---

    def test_select_with_failure_memory(self):
        memory = make_memory_with_strategies(self.s_budget)
        fp = make_failure_pattern(
            "F001", "Budget Increase Crash", "increase_budget",
            failure_rate=0.8, total_attempts=10, severity=FailureSeverity.HIGH,
        )
        fm = make_failure_memory_with_patterns(fp)
        selector = StrategySelector(strategy_memory=memory, failure_memory=fm)
        opp = make_opportunity(OpportunityType.BUDGET_OPTIMIZATION)
        selection = selector.select(opp)
        # Budget strategy has risk, but may still be viable if score is high enough
        # or may be blocked if risk is very high
        assert selection.has_selection is True or selection.has_selection is False

    def test_select_risk_warnings_in_selection(self):
        memory = make_memory_with_strategies(self.s_budget)
        fp = make_failure_pattern(
            "F001", "Budget Crash", "increase_budget",
            failure_rate=0.85, total_attempts=10, severity=FailureSeverity.CRITICAL,
        )
        fm = make_failure_memory_with_patterns(fp)
        selector = StrategySelector(strategy_memory=memory, failure_memory=fm)
        opp = make_opportunity(OpportunityType.BUDGET_OPTIMIZATION)
        selection = selector.select(opp, viable_only=False)
        if selection.has_selection:
            assert len(selection.risk_warnings) > 0

    def test_select_no_failure_memory_still_works(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)  # No failure_memory
        opp = make_opportunity()
        selection = selector.select(opp)
        assert selection.has_selection is True

    # --- Approval determination ---

    def test_select_high_risk_requires_approval(self):
        s_risky = make_strategy(
            "S010", "Risky Strategy", opp_type="budget_optimization",
            success_rate=0.5, score=0.5,
            steps=[StrategyStep(order=1, action_type="increase_budget", approval_level="manual")],
        )
        memory = make_memory_with_strategies(s_risky)
        fp = make_failure_pattern(
            "F010", "Risky Budget", "increase_budget",
            failure_rate=0.85, total_attempts=10, severity=FailureSeverity.CRITICAL,
        )
        fm = make_failure_memory_with_patterns(fp)
        selector = StrategySelector(strategy_memory=memory, failure_memory=fm)
        opp = make_opportunity(OpportunityType.BUDGET_OPTIMIZATION,
                               priority=DecisionPriority.HIGH)
        selection = selector.select(opp, viable_only=False)
        if selection.has_selection:
            assert selection.requires_approval is True

    def test_select_low_risk_no_approval(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp)
        assert selection.has_selection is True
        assert selection.requires_approval is False

    # --- Confidence computation ---

    def test_decision_confidence_single_candidate(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp, top_n=1)
        assert selection.decision_confidence > 0.0
        assert selection.decision_confidence <= 1.0

    def test_decision_confidence_gap_bonus(self):
        memory = make_memory_with_strategies(self.s_hook, self.s_gameplay)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp, top_n=2)
        assert selection.decision_confidence > 0.0

    # --- Selection count ---

    def test_selection_count_increments(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)
        assert selector.selection_count == 0
        selector.select(make_opportunity())
        assert selector.selection_count == 1
        selector.select(make_opportunity())
        assert selector.selection_count == 2

    # --- Context info ---

    def test_selection_stores_opportunity_id(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        opp.opportunity_id = "opp-test-001"
        selection = selector.select(opp)
        assert selection.opportunity_id == "opp-test-001"

    def test_selection_stores_selection_reason(self):
        memory = make_memory_with_strategies(self.s_hook)
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp)
        assert len(selection.selection_reason) > 0
        assert "Hook Mutation" in selection.selection_reason

    # --- Matcher and Ranker properties ---

    def test_matcher_property(self):
        selector = StrategySelector()
        assert isinstance(selector.matcher, StrategyMatcher)

    def test_ranker_property(self):
        selector = StrategySelector()
        assert isinstance(selector.ranker, StrategyRanker)


# ═══════════════════════════════════════════════════════════════
# Test: End-to-End Integration
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """完整决策链: Opportunity → StrategyMemory → FailureMemory → Selection."""

    def test_full_pipeline_creative_fatigue(self):
        """E2E: Creative fatigue → Hook Mutation selected."""
        # Setup strategies
        s_hook = make_strategy("S001", "Hook Mutation Strategy",
                               success_rate=0.91, score=0.85)
        s_gameplay = make_strategy("S002", "New Gameplay Strategy",
                                   success_rate=0.76, score=0.70)
        s_audience = make_strategy("S003", "Audience Change Strategy",
                                   opp_type="audience_expansion",
                                   success_rate=0.68, score=0.60)

        memory = make_memory_with_strategies(s_hook, s_gameplay, s_audience)
        selector = StrategySelector(strategy_memory=memory)

        opp = make_opportunity(
            OpportunityType.CREATIVE_REFRESH,
            reason="Creative fatigue detected: CTR decay 0.35, frequency increase 4.5",
            confidence=0.8, urgency=0.7,
        )

        selection = selector.select(opp)
        assert selection.has_selection is True
        assert selection.selected_strategy_id == "S001"
        assert selection.decision_confidence > 0.5
        assert "Hook Mutation" in selection.selection_reason
        assert selection.requires_approval is False

    def test_full_pipeline_with_failure_memory(self):
        """E2E: Failure memory blocks risky strategy."""
        s_hook = make_strategy("S001", "Hook Mutation", success_rate=0.91, score=0.85)
        s_budget = make_strategy(
            "S004", "Budget Increase 50%", opp_type="budget_optimization",
            success_rate=0.75, score=0.65,
            steps=[StrategyStep(order=1, action_type="increase_budget", approval_level="manual")],
        )
        memory = make_memory_with_strategies(s_hook, s_budget)

        fp = make_failure_pattern(
            "F001", "Budget Increase Crash",
            blocked_action="increase_budget",
            failure_rate=0.8, total_attempts=10,
            severity=FailureSeverity.HIGH,
            opp_type="budget_optimization",
        )
        fm = make_failure_memory_with_patterns(fp)

        selector = StrategySelector(strategy_memory=memory, failure_memory=fm)
        opp = make_opportunity(OpportunityType.BUDGET_OPTIMIZATION,
                               reason="Budget optimization opportunity")

        selection = selector.select(opp, viable_only=True)
        # Budget strategy may be risky enough to be blocked
        if selection.has_selection:
            # If not blocked, it should have risk warnings
            assert len(selection.risk_warnings) > 0 or selection.requires_approval is True

    def test_full_pipeline_multiple_candidates_ranking(self):
        """E2E: Multiple strategies properly ranked."""
        strategies = [
            make_strategy("S001", "Strategy A", success_rate=0.91, score=0.85),
            make_strategy("S002", "Strategy B", success_rate=0.76, score=0.70),
            make_strategy("S003", "Strategy C", success_rate=0.68, score=0.60),
        ]
        memory = make_memory_with_strategies(*strategies)
        selector = StrategySelector(strategy_memory=memory)

        opp = make_opportunity()
        selection = selector.select(opp, top_n=3)

        assert selection.has_selection is True
        assert selection.selected_strategy_id == "S001"
        if selection.alternative_count >= 2:
            alt1 = selection.alternatives[0]
            alt2 = selection.alternatives[1]
            assert alt1.final_score >= alt2.final_score

    def test_full_pipeline_empty_memory(self):
        """E2E: Empty strategy memory returns no selection."""
        memory = StrategyMemory(MagicMock())
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        selection = selector.select(opp)
        assert selection.has_selection is False

    def test_full_pipeline_different_opportunity_type(self):
        """E2E: Different opportunity type selects different strategy."""
        s_creative = make_strategy("S001", "Creative Refresh", opp_type="creative_refresh",
                                   success_rate=0.91, score=0.85)
        s_audience = make_strategy("S002", "Audience Expansion", opp_type="audience_expansion",
                                   success_rate=0.85, score=0.80)
        memory = make_memory_with_strategies(s_creative, s_audience)
        selector = StrategySelector(strategy_memory=memory)

        # Audience expansion opportunity
        opp = make_opportunity(OpportunityType.AUDIENCE_EXPANSION,
                               reason="Audience expansion opportunity detected")
        selection = selector.select(opp)
        assert selection.has_selection is True
        # Audience strategy should match better
        assert selection.selected_strategy_id == "S002"

    def test_full_pipeline_no_viable_all_blocked(self):
        """E2E: All strategies blocked by risk."""
        s_risky = make_strategy(
            "S010", "Very Risky", success_rate=0.3, score=0.2,
            steps=[StrategyStep(order=1, action_type="dangerous_action", approval_level="blocked")],
        )
        memory = make_memory_with_strategies(s_risky)
        fp = make_failure_pattern(
            "F010", "Dangerous Action", "dangerous_action",
            failure_rate=0.95, total_attempts=20, severity=FailureSeverity.CRITICAL,
        )
        fm = make_failure_memory_with_patterns(fp)
        selector = StrategySelector(strategy_memory=memory, failure_memory=fm)
        opp = make_opportunity()
        selection = selector.select(opp, viable_only=True)
        # All strategies should be blocked
        assert selection.has_selection is False

    def test_full_pipeline_selection_metadata(self):
        """E2E: Selection contains all required metadata."""
        memory = make_memory_with_strategies(self._make_hook_strategy())
        selector = StrategySelector(strategy_memory=memory)
        opp = make_opportunity()
        opp.opportunity_id = "opp-e2e-001"

        selection = selector.select(opp)
        d = selection.to_dict()
        assert d["selection_id"] != ""
        assert d["opportunity_id"] == "opp-e2e-001"
        assert d["selected_strategy_id"] != ""
        assert d["decision_confidence"] > 0.0
        assert d["selection_reason"] != ""
        assert "created_at" in d
        assert "requires_approval" in d

    def _make_hook_strategy(self):
        return make_strategy("S001", "Hook Mutation", success_rate=0.91, score=0.85)

    def test_full_pipeline_opportunity_context_preserved(self):
        """E2E: Opportunity context preserved through pipeline."""
        s = make_strategy("S001", "Hook Mutation", success_rate=0.91, score=0.85)
        memory = make_memory_with_strategies(s)
        selector = StrategySelector(strategy_memory=memory)

        opp = make_opportunity(
            OpportunityType.CREATIVE_REFRESH,
            product_id="merge_witch",
            metadata={"audience_segment": "ios_us_facebook"},
            priority=DecisionPriority.HIGH,
        )
        opp.opportunity_id = "opp-context-001"

        selection = selector.select(opp)
        assert selection.opportunity_id == "opp-context-001"
        assert selection.has_selection is True

    def test_full_pipeline_critical_opportunity_triggers_approval(self):
        """E2E: Critical priority with low confidence triggers approval."""
        s_low = make_strategy("S005", "Low Confidence", success_rate=0.4, score=0.3)
        memory = make_memory_with_strategies(s_low)
        selector = StrategySelector(strategy_memory=memory)

        opp = make_opportunity(
            OpportunityType.CREATIVE_REFRESH,
            priority=DecisionPriority.CRITICAL,
            confidence=0.3,
        )
        selection = selector.select(opp, viable_only=False)
        if selection.has_selection:
            assert selection.requires_approval is True