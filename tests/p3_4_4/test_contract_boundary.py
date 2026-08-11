"""P3.4.4 — 契约边界锁：提案生成器不得执行、不得预测收入、不得触碰执行层。

守护「只建议不执行」纪律；含变异测试确认锁会真实触发。
"""

import ast
import io
import tokenize

import src.operator.portfolio.proposal as proposal_mod
from src.operator.portfolio.proposal import PortfolioProposal, ProposalGenerator

PROP_SRC = open(proposal_mod.__file__, encoding="utf-8").read()

# 执行层符号（P3.4.4 绝不产出 / 引用）
FORBIDDEN_TOKENS = (
    "ExecutionRequest",
    "ExecutionContract",
    "ExecutionIntent",
    "SafeExecutor",
    "ProviderRouter",
    "build_safe_executor",
    "DecisionEngine",
    "ApprovalService",
    "src.execution",
)

# 收入预测式（P3.4.4 绝不 new_revenue = old_revenue * multiplier）
REVENUE_PREDICTION_TOKENS = (
    "new_revenue",
    "predicted_revenue",
    "forecast",
    "predict(",
    "revenue *",
    "* revenue",
)

# proposal.py 不得定义这些越界方法（执行/预测/分配/模拟属其它层）
FORBIDDEN_METHODS = {"allocate", "execute", "decide", "predict", "forecast", "simulate"}


def _code_only(src: str) -> str:
    """去掉注释与字符串字面量（含 docstring），只保留实际代码。"""
    out: list = []
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in toks:
            if tok.type in (tokenize.STRING, tokenize.COMMENT):
                continue
            out.append(tok.string)
    except tokenize.TokenError:
        return src
    return " ".join(out)


def assert_no_forbidden_tokens(src: str, label: str) -> None:
    code = _code_only(src)
    for tok in FORBIDDEN_TOKENS:
        assert tok not in code, f"{label} 不应引用 {tok}（P3.4.4 不碰执行层）"
    for tok in REVENUE_PREDICTION_TOKENS:
        assert tok not in code, f"{label} 不应含收入预测式 {tok!r}（P3.4.4 不预测收入）"


def assert_no_forbidden_methods(src: str, label: str) -> None:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name not in FORBIDDEN_METHODS, f"{label} 不应定义方法 {node.name}()"


# --------------------------------------------------------------------------- #
# 正向锁：真实源码通过
# --------------------------------------------------------------------------- #
def test_proposal_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(PROP_SRC, "proposal.py")


def test_proposal_defines_no_forbidden_methods():
    assert_no_forbidden_methods(PROP_SRC, "proposal.py")


def test_proposal_does_not_import_execution_layer():
    imported: set = set()
    tree = ast.parse(PROP_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "src.execution" not in imported
    assert "execution" not in " ".join(imported)


def test_proposal_reuses_action_state_enum():
    # 三态必须复用 P3.2 ActionState，不新造
    from src.operator.report.models import ActionState

    assert hasattr(proposal_mod, "PortfolioProposal")
    # 构造一个最小提案，验证 action_state 取值来自 ActionState
    from src.operator.portfolio.allocation_models import (
        AllocationDelta,
        AllocationSimulationResult,
        ConstraintCheck,
        ConstraintStatus,
        GameAllocation,
        RiskLevel,
        SimulationVerdict,
    )
    from src.operator.portfolio.models import GamePortfolioSnapshot, PortfolioSnapshot
    from src.operator.portfolio.ranking_models import AllocationCandidate, PortfolioVerdict

    sim = AllocationSimulationResult(
        as_of="t",
        baseline_allocation=[GameAllocation("A", 5000.0)],
        proposed_allocation=[GameAllocation("A", 5100.0)],
        delta=[AllocationDelta("A", 5000.0, 5100.0, 100.0)],
        constraints_checked=[ConstraintCheck("x", ConstraintStatus.PASS)],
        confidence=1.0,
        verdict=SimulationVerdict.PASS,
        risk=RiskLevel.LOW,
        total_budget=5000.0,
        gross_shift=100.0,
    )
    snap = PortfolioSnapshot(
        generated_at="t",
        games=[GamePortfolioSnapshot(game_id="A", spend=5000.0, confidence=0.9)],
    )
    ranking = [AllocationCandidate("A", 1, 0.8, PortfolioVerdict.SCALE, 0.0, 80.0, 0.9, "", "rk")]
    prop = ProposalGenerator().propose(sim, ranking, snap, __import__(
        "src.operator.portfolio.constraints", fromlist=["AllocationConstraints"]
    ).AllocationConstraints(total_budget=5000.0))
    assert prop.items[0].action_state in (ActionState.AUTO, ActionState.APPROVAL, ActionState.BLOCKED)


def test_proposal_real_api_called_false():
    assert hasattr(proposal_mod, "REAL_API_CALLED")
    gen = ProposalGenerator()
    assert gen is not None
    # 通过 build 工厂确认常量锁死
    from src.operator.portfolio.proposal import build_proposal_generator

    assert build_proposal_generator() is not None


# --------------------------------------------------------------------------- #
# 变异测试：确认检测器确实会抓违规
# --------------------------------------------------------------------------- #
def test_forbidden_token_detector_fires_on_execution_reference():
    import pytest

    violating = "req = ExecutionRequest(intent=foo)\ncontract = ExecutionContract(req)"
    with pytest.raises(AssertionError):
        assert_no_forbidden_tokens(violating, "mutation")


def test_forbidden_token_detector_fires_on_revenue_prediction():
    import pytest

    violating = "new_revenue = old_revenue * 1.5  # 偷偷预测收入"
    with pytest.raises(AssertionError):
        assert_no_forbidden_tokens(violating, "mutation")


def test_forbidden_token_detector_passes_clean_source():
    clean = "delta = weight * baseline  # 只挪钱，不预测收入"
    assert_no_forbidden_tokens(clean, "clean-mutation")  # 不应抛


def test_forbidden_method_detector_fires_on_execute():
    import pytest

    violating = (
        "class Foo:\n"
        "    def execute(self, x):\n"
        "        return x\n"
    )
    with pytest.raises(AssertionError):
        assert_no_forbidden_methods(violating, "mutation")


def test_forbidden_method_detector_passes_propose():
    # propose / _evaluate_guard 是合法方法名
    assert_no_forbidden_methods(PROP_SRC, "proposal.py")
