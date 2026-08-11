"""P3.4.1 — 契约边界锁：禁止计算 / 排序 / 决策 / 触碰 E17.3。

这些测试守护「只装配、不创造」的纪律，一旦后续有人越界即失败。
"""

import ast
import importlib

import src.operator.portfolio.assembler as asm_mod
import src.operator.portfolio.models as models_mod
from src.operator.portfolio.assembler import PortfolioAssembler
from src.operator.portfolio.models import (
    GamePortfolioSnapshot,
    PortfolioSignal,
    PortfolioSnapshot,
)
from tests.p3_4_1.helpers import make_reality

SRC_TEXT = open(asm_mod.__file__, encoding="utf-8").read()
MODELS_TEXT = open(models_mod.__file__, encoding="utf-8").read()
MODELS_TREE = ast.parse(MODELS_TEXT)

# P3.4.2+ 归属符号：一律不得出现在 P3.4.1 模型层
DOWNSTREAM_SYMBOLS = (
    "PortfolioScore",
    "PortfolioVerdict",
    "AllocationCandidate",
    "PortfolioRecommendation",
)


def test_assembler_does_not_recompute_roas():
    # revenue/spend 在，但 roas 显式 0.0（未计算）→ 必须原样 0.0，不能 100/40
    r = make_reality("g", daily_revenue=100.0, spend=40.0, roas=0.0)
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.roas == 0.0
    assert g.roas != 2.5


def test_assembler_does_not_sort():
    realities = [make_reality("zeta"), make_reality("alpha"), make_reality("mike")]
    ps = PortfolioAssembler().assemble_fleet(realities)
    assert ps.game_ids == ["zeta", "alpha", "mike"]


def test_assembler_does_not_produce_recommendation():
    r = make_reality("g", daily_revenue=10.0)
    ps = PortfolioAssembler().assemble(r)
    # 返回的是组合快照，不是推荐对象
    assert isinstance(ps, PortfolioSnapshot)
    mod = importlib.import_module("src.operator.portfolio.assembler")
    assert not hasattr(mod, "PortfolioRecommendation")
    # 也不暴露任何 recommendation 类
    assert "PortfolioRecommendation" not in SRC_TEXT


def test_assembler_no_sorted_call_in_source():
    # 静态保证：assembler 源码中不存在 sorted( 调用
    assert "sorted(" not in SRC_TEXT


def test_assembler_does_not_import_provider_or_decision_engine():
    # 装配层只消费既有数据，绝不直连 Provider / E17.3 Decision
    # 注：docstring 中「不触碰 E17.3」属边界声明，非 import，故不计入禁用 token
    forbidden = ["safe_executor", "DecisionEngine", "ProviderRouter", "build_safe_executor"]
    for token in forbidden:
        assert token not in SRC_TEXT, f"assembler 不应引用 {token}"


def test_assembler_has_no_rank_score_or_recommend_methods():
    a = PortfolioAssembler()
    for meth in ("rank", "score_game", "recommend", "allocate", "decide"):
        assert not hasattr(a, meth), f"assembler 不应有 {meth} 方法"


def test_missing_strategy_yields_unknown_not_zero():
    r = make_reality("g", daily_revenue=10.0)
    g = PortfolioAssembler().assemble(r).games[0]
    # 缺策略数据 → UNKNOWN(None)，而非伪造的 0.0
    assert g.strategy_score is None
    assert g.strategy_success_rate is None


def test_confidence_is_consumed_not_computed():
    # confidence 直接来自 reality.confidence，不触发 P1.7 重算
    r = make_reality("g", confidence=0.37)
    g = PortfolioAssembler().assemble(r).games[0]
    assert g.confidence == 0.37


def test_module_ast_has_no_call_to_rank_or_allocate():
    tree = ast.parse(SRC_TEXT)
    calls = [
        node.func
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    names = {c.id for c in calls}
    assert "rank" not in names
    assert "allocate" not in names
    assert "decide" not in names


# --------------------------------------------------------------------------- #
# models.py 边界锁（P3.4.1 是纯快照模型层：不评分 / 不排序 / 不产生 Action）
#
# 背景：早期实现把 PortfolioScore.compute() 与 PortfolioRecommendation 混入
# models.py，越过了 P3.4.1 边界。这些锁确保同类越界不再复发——
# 评分/排序/分配/推荐类模型一律归 ranking_models.py（P3.4.2+）。
# --------------------------------------------------------------------------- #
def test_models_does_not_export_downstream_symbols():
    """P3.4.1 模型层不得暴露 P3.4.2+ 的评分 / 判决 / 推荐对象。"""
    for sym in DOWNSTREAM_SYMBOLS:
        assert not hasattr(models_mod, sym), f"models.py 不应定义/导出 {sym}（属 P3.4.2+）"


def test_models_source_has_no_downstream_class_definitions():
    """静态锁：源码中不得出现下游类定义（docstring 中的说明性引用不计）。"""
    defined = {
        node.name
        for node in ast.walk(MODELS_TREE)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    for sym in DOWNSTREAM_SYMBOLS:
        assert sym not in defined, f"models.py 不应定义 {sym}"


def test_models_has_no_enum_or_verdict_semantics():
    """P3.4.1 只有快照字段，不引入 Action / Verdict 语义枚举。"""
    class_defs = [n for n in ast.walk(MODELS_TREE) if isinstance(n, ast.ClassDef)]
    for cls in class_defs:
        base_names = {b.id for b in cls.bases if isinstance(b, ast.Name)}
        assert "Enum" not in base_names, f"{cls.name} 不应是枚举（Action 语义属下游）"


def test_models_defines_no_scoring_or_ranking_methods():
    """模型层不得出现 compute / score / rank / allocate / recommend / decide 方法。"""
    forbidden = {"compute", "score", "rank", "allocate", "recommend", "decide", "simulate"}
    for node in ast.walk(MODELS_TREE):
        if isinstance(node, ast.FunctionDef):
            assert node.name not in forbidden, f"models.py 不应定义 {node.name}()"


def test_models_public_classes_have_no_scoring_attributes():
    """运行时锁：核心模型不得挂载评分 / 排序 / 决策方法。"""
    for cls in (GamePortfolioSnapshot, PortfolioSnapshot, PortfolioSignal):
        for meth in ("compute", "score", "rank", "allocate", "recommend", "decide"):
            assert not hasattr(cls, meth), f"{cls.__name__} 不应有 {meth}"


def test_models_has_no_division_no_roas_recompute():
    """静态锁：模型层不含任何除法 —— 从根上杜绝 revenue/spend 重算 ROAS。"""
    divs = [n for n in ast.walk(MODELS_TREE) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
    assert not divs, "models.py 出现除法运算，疑似重算业务指标（ROAS 应由 Reality 层提供）"


def test_models_has_no_sorted_call():
    """静态锁：排序属 P3.4.2 ranker.py。"""
    assert "sorted(" not in MODELS_TEXT
    calls = {
        n.func.id
        for n in ast.walk(MODELS_TREE)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "sorted" not in calls


def test_models_does_not_import_downstream_or_upstream_engines():
    """模型层零依赖：不 import ranker / ranking_models / Provider / E17.3 Decision。"""
    imported: set = set()
    for node in ast.walk(MODELS_TREE):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    joined = " ".join(imported)
    for token in ("ranker", "ranking_models", "safe_executor", "decision_engine", "provider"):
        assert token not in joined, f"models.py 不应 import {token}"


def test_models_snapshot_preserves_insertion_order():
    """运行时锁：PortfolioSnapshot 不对 games 做任何重排。"""
    ids = ["zeta", "alpha", "mike", "beta"]
    ps = PortfolioSnapshot(
        generated_at="t",
        games=[GamePortfolioSnapshot(game_id=i) for i in ids],
    )
    assert ps.game_ids == ids
    assert PortfolioSnapshot.from_dict(ps.to_dict()).game_ids == ids


def test_downstream_models_live_in_ranking_models_module():
    """正向确认：下游模型确实存在，只是归属 ranking_models.py（未被误删）。"""
    rm = importlib.import_module("src.operator.portfolio.ranking_models")
    for sym in DOWNSTREAM_SYMBOLS:
        assert hasattr(rm, sym), f"{sym} 应归属 ranking_models.py"
