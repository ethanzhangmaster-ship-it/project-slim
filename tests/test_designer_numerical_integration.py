"""跨 Agent 集成测试 — Game Designer → Numerical Designer 设计数值闭环.

验证 Phase 2 游戏策划 Agent 的完整集成:
  1. Product Agent PRD → GDD → Game Designer 设计产物（关卡/经济/系统/难度/文档）
  2. Game Designer EconomyBalance → Numerical Designer monitor_inflation 消费链路
  3. Game Designer MessageBus 广播（注入 message_bus 后事件真正投递）
  4. CEO Memory 多 domain 回流（design + numerical + data_numerical_bridge）
  5. DataNumericalBridge 闭环与 Game Designer 设计数值的端到端协同

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 不依赖外部模块（v9_company/EconomyManager 不可导入时降级）
  - 验证"设计阶段数值 → 运营阶段建模"的数据流转
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from src.market_ops.workspace.game_designer_agent import (
    GameDesignerAgent,
    EconomyBalance,
    DesignDocument,
)
from src.market_ops.workspace.numerical_designer_agent import (
    NumericalDesignerAgent,
    GameMetrics,
    InflationReport,
)
from src.market_ops.workspace.product_agent import (
    ProductManagerAgent,
    MarketOpportunity,
)
from src.market_ops.workspace.data_numerical_bridge import DataNumericalBridge


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """临时数据目录."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def tmp_product(tmp_data_dir: Path) -> ProductManagerAgent:
    """使用临时目录的 Product Agent."""
    return ProductManagerAgent(data_dir=str(tmp_data_dir))


@pytest.fixture
def tmp_designer(tmp_data_dir: Path) -> GameDesignerAgent:
    """使用临时目录的 Game Designer Agent（无 message_bus）."""
    return GameDesignerAgent(data_dir=str(tmp_data_dir))


@pytest.fixture
def tmp_numerical(tmp_data_dir: Path) -> NumericalDesignerAgent:
    """使用临时目录的 Numerical Designer Agent.

    注入 mock economy_manager 返回空列表，强制 monitor_inflation 降级到
    design EconomyBalance（而非懒加载 v9_company EconomyManager）。
    """
    mock_em = MagicMock()
    mock_em.analyze_economy.return_value = []  # 空列表 → 降级到 design 数据
    return NumericalDesignerAgent(
        data_dir=str(tmp_data_dir),
        profitability_engine=None,
        economy_manager=mock_em,
    )


@pytest.fixture
def sample_gdd_id(tmp_product: ProductManagerAgent) -> str:
    """生成一个 Merge 品类的 GDD."""
    opp = MarketOpportunity(genre="Merge", budget_usd=500000.0, timeline_months=6)
    prd = tmp_product.generate_prd(opp)
    gdd = tmp_product.generate_gdd(prd.prd_id)
    return gdd.gdd_id


@pytest.fixture
def sample_game_name(tmp_product: ProductManagerAgent, sample_gdd_id: str) -> str:
    """获取 GDD 关联的 game_name（作为 numerical 的 game_id 关联键）."""
    gdd_path = Path(tmp_product.data_dir) / "product" / "gdds.jsonl"
    text = gdd_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("gdd_id") == sample_gdd_id:
                return rec.get("game_name", "")
    return ""


# ═══════════════════════════════════════════════════════════════
# 1. Product → Game Designer 数据流闭环
# ═══════════════════════════════════════════════════════════════


class TestProductToDesignerFlow:
    """验证 Product Agent PRD → GDD → Game Designer 设计产物."""

    def test_prd_to_gdd_to_design_document(
        self, tmp_product: ProductManagerAgent, tmp_designer: GameDesignerAgent,
        sample_gdd_id: str,
    ):
        """完整链路: PRD → GDD → DesignDocument."""
        doc = tmp_designer.create_design_document(sample_gdd_id)

        assert isinstance(doc, DesignDocument)
        assert doc.gdd_id == sample_gdd_id
        assert doc.ready_for_dev is True
        assert doc.level_design is not None
        assert doc.economy_balance is not None
        assert len(doc.system_specs) > 0
        assert doc.difficulty_curve is not None

    def test_design_persists_to_jsonl(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str,
        tmp_data_dir: Path,
    ):
        """设计产物持久化到 data/design/*.jsonl."""
        tmp_designer.create_design_document(sample_gdd_id)

        design_dir = tmp_data_dir / "design"
        assert (design_dir / "level_designs.jsonl").exists()
        assert (design_dir / "economy_balances.jsonl").exists()
        assert (design_dir / "system_specs.jsonl").exists()
        assert (design_dir / "difficulty_curves.jsonl").exists()
        assert (design_dir / "design_documents.jsonl").exists()

    def test_three_genres_all_produce_designs(
        self, tmp_product: ProductManagerAgent, tmp_designer: GameDesignerAgent,
    ):
        """三种品类（Merge/Match3/Simulation）均能生成设计文档."""
        for genre, budget in [("Merge", 500000), ("Match3", 300000), ("Simulation", 400000)]:
            opp = MarketOpportunity(genre=genre, budget_usd=budget, timeline_months=6)
            prd = tmp_product.generate_prd(opp)
            gdd = tmp_product.generate_gdd(prd.prd_id)
            doc = tmp_designer.create_design_document(gdd.gdd_id)
            assert doc.ready_for_dev is True
            # DesignDocument 中 economy_balance 是 dict（to_dict() 后）
            assert len(doc.economy_balance["currencies"]) > 0


# ═══════════════════════════════════════════════════════════════
# 2. Game Designer → Numerical Designer 设计数值消费闭环
# ═══════════════════════════════════════════════════════════════


class TestDesignerToNumericalFlow:
    """验证 Game Designer EconomyBalance → Numerical Designer monitor_inflation."""

    def test_monitor_inflation_uses_design_economy_balance(
        self, tmp_designer: GameDesignerAgent, tmp_numerical: NumericalDesignerAgent,
        sample_gdd_id: str, sample_game_name: str,
    ):
        """monitor_inflation 应消费 design EconomyBalance（无 EconomyManager 时）."""
        # 1. Game Designer 生成经济数值
        balance = tmp_designer.balance_economy(sample_gdd_id)
        assert isinstance(balance, EconomyBalance)
        assert len(balance.currencies) > 0

        # 2. Numerical Designer 通胀监控（无显式 economy_data，无 EconomyManager）
        #    应降级到 design/economy_balances.jsonl
        report = tmp_numerical.monitor_inflation(sample_game_name)

        assert isinstance(report, InflationReport)
        assert report.game_id == sample_game_name
        assert len(report.currencies) > 0
        # 货币名称应来自设计阶段 CurrencyConfig
        currency_names = [c["name"] for c in report.currencies]
        design_currency_names = [c.currency_name for c in balance.currencies]
        assert any(name in currency_names for name in design_currency_names)

    def test_design_economy_balance_currency_count_matches(
        self, tmp_designer: GameDesignerAgent, tmp_numerical: NumericalDesignerAgent,
        sample_gdd_id: str, sample_game_name: str,
    ):
        """通胀报告货币数 = 设计阶段 EconomyBalance 货币数."""
        balance = tmp_designer.balance_economy(sample_gdd_id)
        report = tmp_numerical.monitor_inflation(sample_game_name)

        assert len(report.currencies) == len(balance.currencies)

    def test_design_economy_balance_sink_to_faucet_propagated(
        self, tmp_designer: GameDesignerAgent, tmp_numerical: NumericalDesignerAgent,
        sample_gdd_id: str, sample_game_name: str,
    ):
        """设计阶段 sink_to_faucet_ratio 传播到通胀报告."""
        balance = tmp_designer.balance_economy(sample_gdd_id)
        report = tmp_numerical.monitor_inflation(sample_game_name)

        # 通胀报告的 avg sink_to_faucet 应反映设计阶段比值
        design_ratios = []
        for c in balance.currencies:
            if c.daily_faucet > 0:
                design_ratios.append(c.daily_sink / c.daily_faucet)
        if design_ratios:
            expected_avg = sum(design_ratios) / len(design_ratios)
            assert abs(report.sink_to_faucet_ratio - round(expected_avg, 4)) < 0.01

    def test_monitor_inflation_falls_back_to_default_without_design(
        self, tmp_numerical: NumericalDesignerAgent,
    ):
        """无 design EconomyBalance 时降级到内置默认值."""
        # game_id 不匹配任何设计记录
        report = tmp_numerical.monitor_inflation("nonexistent_game")

        assert isinstance(report, InflationReport)
        assert len(report.currencies) == 3  # 默认 Gems/Coins/Energy
        currency_names = [c["name"] for c in report.currencies]
        assert "Gems" in currency_names
        assert "Coins" in currency_names

    def test_load_design_economy_balance_returns_none_when_no_file(
        self, tmp_numerical: NumericalDesignerAgent,
    ):
        """无 design/economy_balances.jsonl 文件时返回 None."""
        result = tmp_numerical._load_design_economy_balance("any_game")
        assert result is None

    def test_load_design_economy_balance_returns_none_when_no_match(
        self, tmp_designer: GameDesignerAgent, tmp_numerical: NumericalDesignerAgent,
        sample_gdd_id: str,
    ):
        """有文件但 game_id 不匹配时返回 None."""
        tmp_designer.balance_economy(sample_gdd_id)
        result = tmp_numerical._load_design_economy_balance("wrong_game_id")
        assert result is None


# ═══════════════════════════════════════════════════════════════
# 3. Game Designer MessageBus 广播验证
# ═══════════════════════════════════════════════════════════════


class TestDesignerMessageBusBroadcast:
    """验证 Game Designer 注入 message_bus 后真正广播事件."""

    def test_broadcast_economy_balanced_event(
        self, tmp_data_dir: Path, sample_gdd_id: str,
    ):
        """balance_economy 广播 design:economy_balanced 事件."""
        mock_bus = MagicMock()
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            AgentIdentity, AgentRole, create_game_designer_agent_identity,
        )
        identity = create_game_designer_agent_identity()

        designer = GameDesignerAgent(
            data_dir=str(tmp_data_dir),
            message_bus=mock_bus,
            agent_identity=identity,
        )
        designer.balance_economy(sample_gdd_id)

        # 验证 message_bus.send 被调用
        assert mock_bus.send.called
        sent_msg = mock_bus.send.call_args[0][0]
        assert sent_msg.subject == "design:economy_balanced"
        assert sent_msg.body["balance_id"]
        assert sent_msg.body["gdd_id"] == sample_gdd_id

    def test_broadcast_levels_designed_event(
        self, tmp_data_dir: Path, sample_gdd_id: str,
    ):
        """design_levels 广播 design:levels_designed 事件."""
        mock_bus = MagicMock()
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            create_game_designer_agent_identity,
        )
        identity = create_game_designer_agent_identity()

        designer = GameDesignerAgent(
            data_dir=str(tmp_data_dir),
            message_bus=mock_bus,
            agent_identity=identity,
        )
        designer.design_levels(sample_gdd_id)

        assert mock_bus.send.called
        sent_msg = mock_bus.send.call_args[0][0]
        assert sent_msg.subject == "design:levels_designed"

    def test_no_broadcast_without_message_bus(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str,
    ):
        """无 message_bus 时不广播（静默 no-op，不报错）."""
        # 不应抛异常
        result = tmp_designer.balance_economy(sample_gdd_id)
        assert isinstance(result, EconomyBalance)


# ═══════════════════════════════════════════════════════════════
# 4. CEO Memory 多 domain 回流
# ═══════════════════════════════════════════════════════════════


class TestCEOMemoryMultiDomain:
    """验证 design + numerical + data_numerical_bridge 多 domain CEO Memory."""

    def test_design_domain_records(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str,
        tmp_data_dir: Path,
    ):
        """Game Designer 写入 domain='design' 的 CEO Memory."""
        tmp_designer.create_design_document(sample_gdd_id)

        ceo_path = tmp_data_dir / "ceo" / "execution_memory.jsonl"
        assert ceo_path.exists()
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        records = [json.loads(l) for l in lines]

        design_records = [r for r in records if r.get("domain") == "design"]
        assert len(design_records) >= 5  # 5 个核心方法各 1 条
        action_types = {r["action_type"] for r in design_records}
        assert "level_design" in action_types
        assert "economy_balance" in action_types
        assert "design_document" in action_types

    def test_numerical_domain_records(
        self, tmp_numerical: NumericalDesignerAgent,
        tmp_designer: GameDesignerAgent, sample_gdd_id: str, sample_game_name: str,
    ):
        """Numerical Designer 写入 domain='numerical' 的 CEO Memory."""
        tmp_designer.balance_economy(sample_gdd_id)
        tmp_numerical.monitor_inflation(sample_game_name)

        ceo_path = Path(tmp_numerical.data_dir) / "ceo" / "execution_memory.jsonl"
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        records = [json.loads(l) for l in lines]

        numerical_records = [r for r in records if r.get("domain") == "numerical"]
        assert len(numerical_records) >= 1
        assert any(r["action_type"] == "inflation_monitoring" for r in numerical_records)

    def test_bridge_domain_records(
        self, tmp_data_dir: Path, tmp_designer: GameDesignerAgent,
        tmp_numerical: NumericalDesignerAgent, sample_gdd_id: str, sample_game_name: str,
    ):
        """DataNumericalBridge 写入 domain='data_numerical_bridge' 的 CEO Memory."""
        bridge = DataNumericalBridge(
            data_dir=str(tmp_data_dir),
            numerical_agent=tmp_numerical,
        )
        # 触发一次协同
        bridge.process_behavior_analysis({
            "game_id": sample_game_name or "test_game",
            "dau": 10000,
            "revenue_total": 5000.0,
            "payer_count": 600,
        })

        ceo_path = tmp_data_dir / "ceo" / "execution_memory.jsonl"
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        records = [json.loads(l) for l in lines]

        bridge_records = [r for r in records if r.get("domain") == "data_numerical_bridge"]
        assert len(bridge_records) >= 1
        assert all(r["strategy_type"] == "cross_agent_collaboration" for r in bridge_records)

    def test_multi_domain_coexist(
        self, tmp_data_dir: Path, tmp_designer: GameDesignerAgent,
        tmp_numerical: NumericalDesignerAgent, sample_gdd_id: str, sample_game_name: str,
    ):
        """design + numerical + data_numerical_bridge 三 domain 共存于 CEO Memory."""
        # 1. Designer 生成设计（写 design domain）
        tmp_designer.balance_economy(sample_gdd_id)

        # 2. Numerical 通胀监控（写 numerical domain，消费 design 数据）
        tmp_numerical.monitor_inflation(sample_game_name)

        # 3. Bridge 协同（写 data_numerical_bridge domain）
        bridge = DataNumericalBridge(
            data_dir=str(tmp_data_dir),
            numerical_agent=tmp_numerical,
        )
        bridge.process_behavior_analysis({
            "game_id": sample_game_name or "test_game",
            "dau": 10000,
        })

        ceo_path = tmp_data_dir / "ceo" / "execution_memory.jsonl"
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        records = [json.loads(l) for l in lines]
        domains = {r.get("domain") for r in records}

        assert "design" in domains
        assert "numerical" in domains
        assert "data_numerical_bridge" in domains


# ═══════════════════════════════════════════════════════════════
# 5. 端到端协同闭环: Design + Data Analysis + Numerical
# ═══════════════════════════════════════════════════════════════


class TestEndToEndCollaboration:
    """端到端: 设计数值 + 行为数据 → 数值建模闭环."""

    def test_full_pipeline_design_data_numerical(
        self, tmp_data_dir: Path, tmp_product: ProductManagerAgent,
        tmp_designer: GameDesignerAgent, tmp_numerical: NumericalDesignerAgent,
        sample_gdd_id: str, sample_game_name: str,
    ):
        """完整管线: 设计 EconomyBalance → 行为分析 → 数值建模闭环."""
        # 1. 设计阶段: 生成 EconomyBalance
        balance = tmp_designer.balance_economy(sample_gdd_id)
        assert len(balance.currencies) > 0

        # 2. 运营阶段: DataNumericalBridge 触发分析闭环
        bridge = DataNumericalBridge(
            data_dir=str(tmp_data_dir),
            numerical_agent=tmp_numerical,
        )
        behavior_data = {
            "game_id": sample_game_name or "merge_game_001",
            "genre": "Merge",
            "dau": 12000,
            "mau": 96000,
            "revenue_total": 6000.0,
            "payer_count": 720,
            "retention_d1": 0.45,
            "retention_d7": 0.20,
            "retention_d30": 0.12,
            "anomalies": [
                {"metric_name": "retention_d7", "severity": "critical"},
            ],
        }
        loop_result = bridge.run_analysis_closed_loop(
            behavior_data["game_id"], behavior_data,
        )

        # 3. 验证闭环完成
        assert loop_result["collaboration_count"] == 4
        for step in loop_result["steps"]:
            assert step["status"] == "success"

        # 4. 通胀监控消费设计阶段 EconomyBalance
        inflation = tmp_numerical.monitor_inflation(behavior_data["game_id"])
        assert len(inflation.currencies) == len(balance.currencies)

    def test_design_and_numerical_share_data_dir(
        self, tmp_data_dir: Path, tmp_designer: GameDesignerAgent,
        tmp_numerical: NumericalDesignerAgent, sample_gdd_id: str,
        sample_game_name: str,
    ):
        """Designer 和 Numerical 共享 data_dir 时数据流转正确."""
        # 验证两者 data_dir 一致
        assert Path(tmp_designer.data_dir) == Path(tmp_numerical.data_dir)

        # Designer 写入 design/economy_balances.jsonl
        tmp_designer.balance_economy(sample_gdd_id)
        design_path = tmp_data_dir / "design" / "economy_balances.jsonl"
        assert design_path.exists()

        # Numerical 能读取该文件
        loaded = tmp_numerical._load_design_economy_balance(sample_game_name)
        assert loaded is not None
        assert loaded["source"] == "design_economy_balance"
        assert len(loaded["currencies"]) > 0

    def test_collaboration_audit_trail(
        self, tmp_data_dir: Path, tmp_designer: GameDesignerAgent,
        tmp_numerical: NumericalDesignerAgent, sample_gdd_id: str,
        sample_game_name: str,
    ):
        """协同审计轨迹: design JSONL + collaboration JSONL + CEO Memory JSONL."""
        # 1. 设计产物
        tmp_designer.balance_economy(sample_gdd_id)

        # 2. Bridge 协同
        bridge = DataNumericalBridge(
            data_dir=str(tmp_data_dir),
            numerical_agent=tmp_numerical,
        )
        bridge.process_behavior_analysis({
            "game_id": sample_game_name or "test_game",
            "dau": 10000,
        })

        # 3. 验证审计文件
        assert (tmp_data_dir / "design" / "economy_balances.jsonl").exists()
        assert (tmp_data_dir / "collaboration" / "data_numerical.jsonl").exists()
        assert (tmp_data_dir / "ceo" / "execution_memory.jsonl").exists()

        # 4. 协同记录可查询
        records = bridge.list_collaborations()
        assert len(records) >= 1
