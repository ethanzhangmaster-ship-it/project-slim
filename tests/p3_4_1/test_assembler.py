"""P3.4.1 — assembler.py 单元测试（装配 + 适配器）。"""

from unittest.mock import MagicMock

from src.operator.portfolio.assembler import (
    PortfolioAssembler,
    build_execution_source,
    build_lifecycle_source,
    build_recovery_source,
    build_strategy_source,
)
from src.operator.portfolio.models import (
    ExecutionSource,
    LifecycleSource,
    RecoverySource,
    StrategySource,
)
from tests.p3_4_1.helpers import make_reality

EPS = 1e-6


# --------------------------------------------------------------------------- #
# assemble 单游戏
# --------------------------------------------------------------------------- #
def test_assemble_maps_reality_fields():
    r = make_reality("g1", daily_revenue=120.0, spend=40.0, roas=1.5, confidence=0.8)
    ps = PortfolioAssembler().assemble(r)
    assert ps.count == 1
    g = ps.games[0]
    assert g.game_id == "g1"
    assert g.revenue == 120.0
    assert g.spend == 40.0
    assert g.roas == 1.5
    assert g.confidence == 0.8
    assert abs(g.coverage - 0.4) < EPS  # 2 domains / 5


def test_assemble_coverage_zero_domains():
    r = make_reality("g0")
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.coverage is None


def test_assemble_confidence_verbatim():
    # confidence 原样取自 reality.confidence，不重算
    r = make_reality("g", confidence=0.42)
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.confidence == 0.42


def test_assemble_with_strategy_source():
    r = make_reality("g", daily_revenue=100.0)
    strat = StrategySource(strategy_score=0.6, strategy_success_rate=0.6, active_strategy_count=4)
    g = PortfolioAssembler().assemble(r, strategy=strat).games[0]
    assert g.strategy_score == 0.6
    assert g.strategy_success_rate == 0.6
    assert g.active_strategy_count == 4


def test_assemble_missing_strategy_keeps_unknown():
    r = make_reality("g", daily_revenue=100.0)
    g = PortfolioAssembler().assemble(r).games[0]  # strategy=None
    assert g.strategy_score is None
    assert g.strategy_success_rate is None
    assert g.active_strategy_count == 0


def test_assemble_with_execution_source():
    r = make_reality("g")
    ex = ExecutionSource(execution_health=0.88, failure_rate=0.12)
    g = PortfolioAssembler().assemble(r, execution=ex).games[0]
    assert g.execution_health == 0.88
    assert g.failure_rate == 0.12


def test_assemble_with_recovery_source():
    r = make_reality("g")
    rec = RecoverySource(recovery_rate=0.9)
    g = PortfolioAssembler().assemble(r, recovery=rec).games[0]
    assert g.recovery_rate == 0.9


def test_assemble_with_lifecycle_source():
    r = make_reality("g")
    lc = LifecycleSource(lifecycle_stage="scale", data_freshness=0.95)
    g = PortfolioAssembler().assemble(r, lifecycle=lc).games[0]
    assert g.lifecycle_stage == "scale"
    assert g.data_freshness == 0.95


def test_assemble_metadata_carries_domains():
    r = make_reality("g", daily_revenue=10.0, real_domains=["revenue", "acquisition"])
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.metadata["real_domains"] == ["revenue", "acquisition"]


def test_assemble_roas_not_recomputed():
    # revenue/spend 存在但 roas=0.0（未计算）→ 必须原样 0.0，绝不能算成 100/40
    r = make_reality("g", daily_revenue=100.0, spend=40.0, roas=0.0)
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.roas == 0.0
    assert g.roas != 2.5


# --------------------------------------------------------------------------- #
# assemble_fleet 多游戏
# --------------------------------------------------------------------------- #
def test_assemble_fleet_order_preserved():
    realities = [make_reality("zeta"), make_reality("alpha"), make_reality("mike")]
    ps = PortfolioAssembler().assemble_fleet(realities)
    assert ps.game_ids == ["zeta", "alpha", "mike"]


def test_assemble_fleet_aggregation():
    r1 = make_reality("a", daily_revenue=100.0, spend=40.0)
    r2 = make_reality("b", daily_revenue=50.0, spend=10.0)
    ps = PortfolioAssembler().assemble_fleet([r1, r2])
    assert ps.total_revenue == 150.0
    assert ps.total_spend == 50.0
    assert abs(ps.coverage - 0.4) < EPS  # 两游戏各 2/5=0.4


def test_assemble_fleet_with_per_game_sources():
    r1 = make_reality("a", daily_revenue=100.0)
    r2 = make_reality("b", daily_revenue=200.0)
    sources = {
        "a": {"strategy": StrategySource(strategy_score=0.5, active_strategy_count=2),
              "lifecycle": LifecycleSource(lifecycle_stage="scale")},
        "b": {"recovery": RecoverySource(recovery_rate=0.8)},
    }
    ps = PortfolioAssembler().assemble_fleet([r1, r2], sources=sources)
    ga = ps.get("a")
    gb = ps.get("b")
    assert ga.strategy_score == 0.5
    assert ga.active_strategy_count == 2
    assert ga.lifecycle_stage == "scale"
    assert gb.recovery_rate == 0.8
    assert gb.strategy_score is None


# --------------------------------------------------------------------------- #
# 适配器
# --------------------------------------------------------------------------- #
class FakeGraph:
    def __init__(self, rate, types):
        self._rate = rate
        self._types = types

    def success_rate_by(self, strategy_type=None, domain=None, action_type=None, game_id=None):
        return self._rate

    def query(self, node_type):
        # 返回带 payload 的伪节点，模拟 N 个不同 strategy_type
        return [MagicMock(payload={"game_id": "g1", "strategy_type": t}) for t in self._types]


def test_build_strategy_source():
    graph = FakeGraph(rate=0.7, types=["a", "b", "c"])
    src = build_strategy_source(graph, "g1")
    assert isinstance(src, StrategySource)
    assert src.strategy_score == 0.7
    assert src.strategy_success_rate == 0.7
    assert src.active_strategy_count == 3


def test_build_strategy_source_no_samples():
    graph = FakeGraph(rate=0.0, types=[])
    src = build_strategy_source(graph, "gX")
    assert src.strategy_score == 0.0
    assert src.active_strategy_count == 0


def test_build_execution_source_filters_by_target(monkeypatch):
    fake_health = MagicMock()
    fake_health.score = 0.9
    fake_health.success_rate = 0.92

    def fake_compute(outcomes):
        # 验证只传入了 target==game_id 的 outcomes
        assert all(o.target == "g1" for o in outcomes)
        return fake_health

    monkeypatch.setattr(
        "src.execution.monitor.health.compute_health_score", fake_compute
    )
    o1 = MagicMock(target="g1")
    o2 = MagicMock(target="g2")
    src = build_execution_source([o1, o2], "g1")
    assert isinstance(src, ExecutionSource)
    assert src.execution_health == 0.9
    assert abs(src.failure_rate - 0.08) < EPS


def test_build_execution_source_empty():
    src = build_execution_source([], "g1")
    assert src.execution_health is None
    assert src.failure_rate is None


def test_build_recovery_source_passthrough():
    src = build_recovery_source(0.75)
    assert isinstance(src, RecoverySource)
    assert src.recovery_rate == 0.75
    assert build_recovery_source().recovery_rate is None


def test_build_lifecycle_source():
    manager = MagicMock()
    manager.stage_of.return_value = "soft_launch"
    src = build_lifecycle_source(manager, "g1")
    assert isinstance(src, LifecycleSource)
    assert src.lifecycle_stage == "soft_launch"
    manager.stage_of.assert_called_once_with("g1")
