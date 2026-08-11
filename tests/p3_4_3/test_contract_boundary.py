"""P3.4.3 — 契约边界锁：模拟器不得执行、不得预测收入、不得触碰执行层。

这些测试守护「只模拟不执行」的纪律，一旦后续有人越界即失败。
含变异测试：向检测器喂入违规片段，确认锁能正确触发。
"""

import ast
import importlib
import io
import tokenize

import src.operator.portfolio.allocation_models as alloc_mod
import src.operator.portfolio.constraints as constraints_mod
import src.operator.portfolio.simulator as sim_mod
from src.operator.portfolio.allocation_models import AllocationSimulationResult
from src.operator.portfolio.simulator import AllocationSimulator

SIM_SRC = open(sim_mod.__file__, encoding="utf-8").read()
ALLOC_SRC = open(alloc_mod.__file__, encoding="utf-8").read()
CONST_SRC = open(constraints_mod.__file__, encoding="utf-8").read()

# 执行层符号（P3.4.3 绝不产出 / 引用）
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

# 收入预测式（P3.4.3 绝不 new_revenue = old_revenue * multiplier）
REVENUE_PREDICTION_TOKENS = (
    "new_revenue",
    "predicted_revenue",
    "forecast",
    "predict(",
    "revenue *",
    "* revenue",
)

# allocation_models / constraints 不得定义这些方法（分配/执行/预测属 simulator 或下游）
FORBIDDEN_METHODS = {"allocate", "execute", "decide", "predict", "forecast", "simulate"}


def _code_only(src: str) -> str:
    """去掉注释与字符串字面量（含 docstring 声明），只保留实际代码。

    边界声明（如 «不产生 ``ExecutionRequest``»）出现在 docstring 中属合法纪律说明，
    不计为「引用」；只检查真实代码中的符号。tokenize 失败时回退到原文。
    """
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
        assert tok not in code, f"{label} 不应引用 {tok}（P3.4.3 不碰执行层）"
    for tok in REVENUE_PREDICTION_TOKENS:
        assert tok not in code, f"{label} 不应含收入预测式 {tok!r}（P3.4.3 不预测收入）"


def assert_no_forbidden_methods(src: str, label: str) -> None:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name not in FORBIDDEN_METHODS, f"{label} 不应定义方法 {node.name}()"


# --------------------------------------------------------------------------- #
# 正向锁：真实源码通过
# --------------------------------------------------------------------------- #
def test_simulator_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(SIM_SRC, "simulator.py")


def test_allocation_models_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(ALLOC_SRC, "allocation_models.py")


def test_constraints_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(CONST_SRC, "constraints.py")


def test_data_modules_define_no_forbidden_methods():
    assert_no_forbidden_methods(ALLOC_SRC, "allocation_models.py")
    assert_no_forbidden_methods(CONST_SRC, "constraints.py")


def test_simulator_does_not_import_execution_layer():
    imported: set = set()
    tree = ast.parse(SIM_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "src.execution" not in imported
    assert "execution" not in " ".join(imported)


def test_simulator_exposes_real_api_called_constant():
    # 常量定义在 allocation_models.py，simulator 仅导入使用
    assert hasattr(sim_mod, "REAL_API_CALLED")
    assert sim_mod.REAL_API_CALLED is False
    assert "REAL_API_CALLED = False" in ALLOC_SRC


def test_result_never_carries_execution_request():
    res = AllocationSimulator().simulate(
        __import__("src.operator.portfolio.models", fromlist=["PortfolioSnapshot"])
        .PortfolioSnapshot(generated_at="t", games=[]),
        [],
        __import__("src.operator.portfolio.constraints", fromlist=["AllocationConstraints"])
        .AllocationConstraints(total_budget=1000.0),
    )
    assert isinstance(res, AllocationSimulationResult)
    assert not hasattr(res, "execution_request")
    assert res.real_api_called is False


# --------------------------------------------------------------------------- #
# 变异测试：确认检测器确实会抓违规（否则锁形同虚设）
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
    # 反向确认：合法源码不会被误杀
    clean = "delta = weight * baseline  # 只挪钱，不预测收入"
    assert_no_forbidden_tokens(clean, "clean-mutation")  # 不应抛


def test_forbidden_method_detector_fires_on_allocate():
    import pytest
    violating = (
        "class Foo:\n"
        "    def allocate(self, x):\n"
        "        return x\n"
    )
    with pytest.raises(AssertionError):
        assert_no_forbidden_methods(violating, "mutation")


def test_forbidden_method_detector_passes_validate():
    # constraints.validate 是合法方法名
    assert_no_forbidden_methods(CONST_SRC, "constraints.py")
