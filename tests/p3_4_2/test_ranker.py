"""P3.4.2 — PortfolioRanker 单元测试。

覆盖契约 Case1（多游戏排序）、生命周期因子、边界条件（空列表 / 全 None / tie-break）。
"""

import pytest

from src.operator.portfolio.models import GamePortfolioSnapshot
from src.operator.portfolio.ranker import PortfolioRanker, build_portfolio_ranker
from src.operator.portfolio.ranking_models import PortfolioScore, PortfolioVerdict

EPS = 1e-6


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def ranker() -> PortfolioRanker:
    return build_portfolio_ranker()


def _g(
    game_id: str,
    revenue: float = 0.0,
    spend: float = 0.0,
    roas: float = 0.0,
    confidence: float = 0.0,
    strategy_score: float = 0.0,
    execution_health: float = 0.0,
    lifecycle_stage: str = "soft_launch",
) -> GamePortfolioSnapshot:
    return GamePortfolioSnapshot(
        game_id=game_id,
        revenue=revenue,
        spend=spend,
        roas=roas,
        confidence=confidence,
        strategy_score=strategy_score,
        execution_health=execution_health,
        lifecycle_stage=lifecycle_stage,
    )


# ====================== basic behavior ====================== #


class TestBasicRanking:
    def test_empty_list_returns_empty(self, ranker):
        assert ranker.rank([]) == []

    def test_single_game_rank_1(self, ranker):
        g = _g("game_a", revenue=100, roas=1.2, confidence=0.8, execution_health=0.9)
        candidates = ranker.rank([g])
        assert len(candidates) == 1
        assert candidates[0].game_id == "game_a"
        assert candidates[0].rank == 1

    def test_score_formula_product(self, ranker):
        """score = revenue_quality * growth_potential * confidence * execution_health"""
        g = _g("g", revenue=100, spend=50, roas=1.5, confidence=0.8,
               execution_health=0.9, lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        # revenue_quality = clamp(1.5/1.5, 0, 1) = 1.0
        # lifecycle_factor = scale = 1.0
        # growth_potential = 1.0
        # expected = 1.0 * 1.0 * 0.8 * 0.9 = 0.72
        assert abs(c.portfolio_score - 0.72) < EPS

    def test_sort_by_score_descending(self, ranker):
        g1 = _g("high", roas=1.5, confidence=0.9, execution_health=0.9,
                 lifecycle_stage="scale")
        g2 = _g("low", roas=0.2, confidence=0.3, execution_health=0.3,
                 lifecycle_stage="prototype")
        c = ranker.rank([g2, g1])  # 故意反向
        assert c[0].game_id == "high"
        assert c[1].game_id == "low"
        assert c[0].portfolio_score > c[1].portfolio_score

    def test_tie_break_by_revenue_desc(self, ranker):
        """同分 → revenue 高的在前"""
        g1 = _g("a", revenue=200, roas=1.0, confidence=0.6, execution_health=0.6)
        g2 = _g("b", revenue=100, roas=1.0, confidence=0.6, execution_health=0.6)
        # 两种都是 roas/1.5=0.667, lifecycle=0.7 (soft_launch)
        # revenue_quality=0.667, growth=0.7, conf=0.6, exec=0.6
        # score=0.667*0.7*0.6*0.6=0.168... 同分
        c = ranker.rank([g2, g1])
        assert c[0].game_id == "a"   # revenue 200 > 100
        assert c[1].game_id == "b"

    def test_tie_break_by_game_id_asc(self, ranker):
        """同分 + 同 revenue → game_id 升序"""
        g1 = _g("early", revenue=100, roas=1.0, confidence=0.6, execution_health=0.6)
        g2 = _g("zebra", revenue=100, roas=1.0, confidence=0.6, execution_health=0.6)
        c = ranker.rank([g2, g1])
        assert c[0].game_id == "early"
        assert c[1].game_id == "zebra"


# ====================== verdict logic ====================== #


class TestInitialVerdict:
    def test_scale_when_high_score_and_growth_stage(self, ranker):
        g = _g("g", roas=2.0, confidence=0.9, execution_health=0.9,
               lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        assert c.recommended_action == PortfolioVerdict.SCALE

    def test_scale_when_ua_test_stage(self, ranker):
        g = _g("g", roas=2.0, confidence=0.9, execution_health=0.9,
               lifecycle_stage="ua_test")
        c = ranker.rank([g])[0]
        assert c.recommended_action == PortfolioVerdict.SCALE

    def test_maintain_verdict(self, ranker):
        """score >= 0.4 → MAINTAIN"""
        g = _g("g", roas=1.2, confidence=0.8, execution_health=0.9,
               lifecycle_stage="soft_launch")
        c = ranker.rank([g])[0]
        # rq=0.8, life=0.7, conf=0.8, exec=0.9 → score=0.8*0.7*0.8*0.9=0.4032
        assert c.portfolio_score >= 0.4
        assert c.recommended_action == PortfolioVerdict.MAINTAIN

    def test_reduce_when_score_below_025(self, ranker):
        g = _g("g", roas=0.1, confidence=0.2, execution_health=0.2,
               lifecycle_stage="prototype")
        c = ranker.rank([g])[0]
        assert c.recommended_action == PortfolioVerdict.REDUCE

    def test_sunset_when_kill_lifecycle(self, ranker):
        g = _g("g", roas=2.0, confidence=0.9, execution_health=0.9,
               lifecycle_stage="kill")
        c = ranker.rank([g])[0]
        assert c.recommended_action == PortfolioVerdict.SUNSET

    def test_default_for_unknown_lifecycle(self, ranker):
        """未知生命周期 → lifecycle_factor=0.0 → score=0 → REDUCE"""
        g = _g("g", roas=1.5, confidence=0.7, execution_health=0.7,
               lifecycle_stage="unknown")
        c = ranker.rank([g])[0]
        assert c.recommended_action == PortfolioVerdict.REDUCE


# ====================== lifecycle factor ====================== #


class TestLifecycleFactor:
    def test_scale_higher_than_prototype(self, ranker):
        scale = _g("s", roas=1.0, confidence=0.5, execution_health=0.5,
                   lifecycle_stage="scale")
        proto = _g("p", roas=1.0, confidence=0.5, execution_health=0.5,
                   lifecycle_stage="prototype")
        c = ranker.rank([proto, scale])
        # scale 1.0 vs prototype 0.45
        assert c[0].game_id == "s"
        assert c[1].game_id == "p"

    def test_lifecycle_weights_mapping(self):
        scale = PortfolioScore.compute(_g("g", lifecycle_stage="scale"))
        ua_test = PortfolioScore.compute(_g("g", lifecycle_stage="ua_test"))
        soft_launch = PortfolioScore.compute(_g("g", lifecycle_stage="soft_launch"))
        prototype = PortfolioScore.compute(_g("g", lifecycle_stage="prototype"))
        idea = PortfolioScore.compute(_g("g", lifecycle_stage="idea"))
        kill = PortfolioScore.compute(_g("g", lifecycle_stage="kill"))
        unknown = PortfolioScore.compute(_g("g", lifecycle_stage="unknown"))
        none_val = PortfolioScore.compute(_g("g", lifecycle_stage=None))

        assert scale.growth_potential == 1.0
        assert ua_test.growth_potential == 0.85
        assert soft_launch.growth_potential == 0.70
        assert prototype.growth_potential == 0.45
        assert idea.growth_potential == 0.25
        assert kill.growth_potential == 0.0
        assert unknown.growth_potential == 0.0
        assert none_val.growth_potential == 0.0


# ====================== PortfolioScore.compute ====================== #


class TestPortfolioScoreCompute:
    def test_revenue_quality_clamp(self):
        """clamp(roas/1.5, 0, 1)"""
        assert PortfolioScore.compute(_g("g", roas=3.0)).revenue_quality == 1.0
        assert abs(PortfolioScore.compute(_g("g", roas=0.75)).revenue_quality - 0.5) < EPS
        assert PortfolioScore.compute(_g("g", roas=0.0)).revenue_quality == 0.0

    def test_none_roas_treated_as_zero(self):
        s = GamePortfolioSnapshot(game_id="g", roas=None)
        score = PortfolioScore.compute(s)
        assert score.revenue_quality == 0.0

    def test_none_confidence_treated_as_zero(self):
        s = GamePortfolioSnapshot(game_id="g", confidence=None)
        score = PortfolioScore.compute(s)
        assert score.confidence == 0.0

    def test_none_execution_health_treated_as_zero(self):
        s = GamePortfolioSnapshot(game_id="g", execution_health=None)
        score = PortfolioScore.compute(s)
        assert score.execution_health == 0.0

    def test_score_zero_when_any_factor_zero(self):
        """score = product; 任一为零则整体为零"""
        g = _g("g", roas=1.5, confidence=0.8, execution_health=0.0,
               lifecycle_stage="scale")
        score = PortfolioScore.compute(g)
        assert score.score == 0.0

    def test_strategy_score_passthrough(self):
        s = GamePortfolioSnapshot(game_id="g", strategy_score=0.75)
        score = PortfolioScore.compute(s)
        assert score.strategy_score == 0.75

    def test_to_dict_roundtrip(self):
        score = PortfolioScore.compute(
            _g("g", roas=1.2, confidence=0.8, execution_health=0.85,
               strategy_score=0.7, lifecycle_stage="scale")
        )
        d = score.to_dict()
        s2 = PortfolioScore.from_dict(d)
        assert abs(s2.score - score.score) < EPS
        assert s2.game_id == "g"
        assert abs(s2.revenue_quality - 0.8) < EPS  # 1.2/1.5


# ====================== ranker output integrity ====================== #


class TestRankerOutput:
    def test_rank_is_1_based_continuous(self, ranker):
        games = [_g(f"g{i}") for i in range(5)]
        c = ranker.rank(games)
        ranks = [x.rank for x in c]
        assert ranks == [1, 2, 3, 4, 5]

    def test_priority_is_score_times_100(self, ranker):
        g = _g("g", roas=1.5, confidence=0.8, execution_health=0.9,
               lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        assert abs(c.priority - c.portfolio_score * 100) < EPS
        # 2 位小数
        assert c.priority == round(c.priority, 2)

    def test_action_state_left_empty(self, ranker):
        g = _g("g", roas=1.0, confidence=0.5, execution_health=0.5)
        c = ranker.rank([g])[0]
        assert c.action_state == ""  # guard 填

    def test_reason_contains_score_evidence(self, ranker):
        g = _g("g", roas=0.1, confidence=0.2, execution_health=0.2)
        c = ranker.rank([g])[0]
        assert "score=" in c.reason

    def test_reason_for_scale_highlights_high_potential(self, ranker):
        g = _g("g", roas=2.0, confidence=0.9, execution_health=0.9,
               lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        assert "high_potential" in c.reason

    def test_reason_for_sunset(self, ranker):
        g = _g("g", roas=2.0, confidence=0.9, execution_health=0.9,
               lifecycle_stage="kill")
        c = ranker.rank([g])[0]
        assert "lifecycle_end" in c.reason

    def test_reason_for_reduce(self, ranker):
        g = _g("g", roas=0.1, confidence=0.2, execution_health=0.2)
        c = ranker.rank([g])[0]
        assert "low_score" in c.reason


# ====================== boundary contract ====================== #


class TestContractBoundary:
    """确保 ranker：
    - 不 import Provider / SafeExecutor / E17.3
    - 不重算 ROAS（roas 原样来自 snapshot）
    """
    def test_no_forbidden_imports(self):
        import src.operator.portfolio.ranker as mod
        src = open(mod.__file__).read()
        for token in ["safe_executor", "ProviderRouter", "build_safe_executor",
                       "DecisionEngine", "ApprovalService", "ExecutionContract"]:
            assert token not in src, f"ranker 不应引用 {token}"

    def test_rank_does_not_recalculate_roas(self, ranker):
        """ranker 只读 snpashot.roas，绝不 revenue/spend 反推"""
        # 设 roas=0.0（已知）, revenue=100, spend=100
        # 如果 ranker 反推 roas=revenue/spend=1.0，则 revenue_quality=0.667
        g = _g("g", revenue=100, spend=100, roas=0.0, confidence=0.5,
               execution_health=0.5)
        c = ranker.rank([g])[0]
        # roas=0.0 → revenue_quality=0.0 → score=0.0
        assert c.portfolio_score == 0.0


# ====================== serialization ====================== #


class TestAllocationCandidateSerialization:
    def test_roundtrip(self, ranker):
        g = _g("g", roas=1.5, confidence=0.8, execution_health=0.9,
               lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        d = c.to_dict()
        c2 = type(c).from_dict(d)
        assert c2.game_id == c.game_id
        assert c2.rank == c.rank
        assert abs(c2.portfolio_score - c.portfolio_score) < EPS
        assert c2.recommended_action == c.recommended_action
        assert c2.action_state == c.action_state

    def test_json_roundtrip(self, ranker):
        import json
        g = _g("g", roas=1.5, confidence=0.8, execution_health=0.9,
               lifecycle_stage="scale")
        c = ranker.rank([g])[0]
        text = json.dumps(c.to_dict())
        c2 = type(c).from_dict(json.loads(text))
        assert c2.game_id == "g"
        assert c2.recommended_action == PortfolioVerdict.SCALE
