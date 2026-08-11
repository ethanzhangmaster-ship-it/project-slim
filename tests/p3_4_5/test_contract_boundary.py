"""P3.4.5 — 契约边界锁：编排器不得重算、不得执行、不得碰执行层、不得预测收入。

守护「只编排不决策」纪律，一旦后续有人越界即失败。含变异测试。
"""

import ast
import io
import tokenize

import src.operator.portfolio.optimizer as opt_mod
import src.operator.portfolio.optimizer_models as opt_models_mod

OPT_SRC = open(opt_mod.__file__, encoding="utf-8").read()
OPT_MODELS_SRC = open(opt_models_mod.__file__, encoding="utf-8").read()

# 执行层符号（P3.4.5 绝不产出 / 引用）
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
    "Provider",
    "Meta",
    "MAX",
    "calculate_roas",
    "predict_revenue",
    "estimate_ltv",
)

# 收入预测式（P3.4.5 绝不 new_revenue = old_revenue * multiplier）
REVENUE_PREDICTION_TOKENS = (
    "new_revenue",
    "predicted_revenue",
    "forecast",
    "predict(",
    "revenue *",
    "* revenue",
)

# 禁止定义的方法（重算/执行/预测属下游，编排器不定义）
FORBIDDEN_METHODS = {
    "allocate",
    "execute",
    "decide",
    "predict",
    "forecast",
    "simulate",
    "calculate_roas",
    "predict_revenue",
    "estimate_ltv",
}


def _code_only(src: str) -> str:
    """去掉注释与字符串字面量（含 docstring 声明），只保留实际代码。

    边界声明（如 «不产生 ``ExecutionRequest``»）出现在 docstring 中属合法纪律说明，
    不计为「引用」；只检查真实代码中的符号。tokenize 失败时回退到原文。
    """
    out = []
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
        assert tok not in code, f"{label} 不应引用 {tok}（P3.4.5 不碰执行层）"
    for tok in REVENUE_PREDICTION_TOKENS:
        assert tok not in code, f"{label} 不应含收入预测式 {tok!r}（P3.4.5 不预测收入）"


def assert_no_forbidden_methods(src: str, label: str) -> None:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name not in FORBIDDEN_METHODS, f"{label} 不应定义方法 {node.name}()"


# --------------------------------------------------------------------------- #
# 正向锁：真实源码通过
# --------------------------------------------------------------------------- #
def test_optimizer_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(OPT_SRC, "optimizer.py")


def test_optimizer_models_source_has_no_forbidden_tokens():
    assert_no_forbidden_tokens(OPT_MODELS_SRC, "optimizer_models.py")


def test_optimizer_defines_no_forbidden_methods():
    assert_no_forbidden_methods(OPT_SRC, "optimizer.py")


def test_optimizer_models_defines_no_forbidden_methods():
    assert_no_forbidden_methods(OPT_MODELS_SRC, "optimizer_models.py")


def test_optimizer_does_not_import_execution_layer():
    imported = set()
    for src in (OPT_SRC, OPT_MODELS_SRC):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
    assert "src.execution" not in imported
    assert "execution" not in " ".join(imported)


def test_optimizer_exposes_real_api_called_false():
    # 常量来自 allocation_models，optimizer 链路所有结果 real_api_called 恒 False
    from src.operator.portfolio.allocation_models import REAL_API_CALLED

    assert REAL_API_CALLED is False
    assert "REAL_API_CALLED = False" in open(
        src_operator_portfolio_allocation_models_path(), encoding="utf-8"
    ).read()


def src_operator_portfolio_allocation_models_path() -> str:
    import src.operator.portfolio.allocation_models as m

    return m.__file__


def test_result_never_carries_execution_request():
    snap = __import__(
        "src.operator.portfolio.models", fromlist=["PortfolioSnapshot"]
    ).PortfolioSnapshot(generated_at="t", games=[])
    cons = __import__(
        "src.operator.portfolio.constraints", fromlist=["AllocationConstraints"]
    ).AllocationConstraints(total_budget=1000.0)
    res = opt_mod.PortfolioOptimizer().optimize(
        opt_models_mod.PortfolioOptimizationInput(snapshots=snap, constraints=cons)
    )
    # 空输入 → INSUFFICIENT_DATA，proposal/simulation 为 None，不携带执行请求
    assert not hasattr(res, "execution_request")
    assert res.real_api_called is False


# --------------------------------------------------------------------------- #
# 变异测试：确认检测器确实会抓违规（否则锁形同虚设）
# --------------------------------------------------------------------------- #
def test_forbidden_token_detector_fires_on_execution_reference():
    violating = "req = ExecutionRequest(intent=foo)\ncontract = ExecutionContract(req)"
    try:
        assert_no_forbidden_tokens(violating, "mutation")
    except AssertionError:
        return
    raise AssertionError("detector failed to fire on ExecutionRequest reference")


def test_forbidden_token_detector_fires_on_provider_router():
    violating = "router = ProviderRouter(channel='meta')"
    try:
        assert_no_forbidden_tokens(violating, "mutation")
    except AssertionError:
        return
    raise AssertionError("detector failed to fire on ProviderRouter reference")


def test_forbidden_token_detector_fires_on_revenue_prediction():
    violating = "new_revenue = old_revenue * 1.5  # 偷偷预测收入"
    try:
        assert_no_forbidden_tokens(violating, "mutation")
    except AssertionError:
        return
    raise AssertionError("detector failed to fire on revenue prediction")


def test_forbidden_token_detector_fires_on_calculate_roas():
    violating = "def calculate_roas(self):\n    return self._roas * 2"
    try:
        assert_no_forbidden_tokens(violating, "mutation")
    except AssertionError:
        return
    raise AssertionError("detector failed to fire on calculate_roas")


def test_forbidden_token_detector_passes_clean_source():
    clean = "delta = weight * baseline  # 只编排，不重算、不预测收入"
    assert_no_forbidden_tokens(clean, "clean-mutation")  # 不应抛


def test_forbidden_method_detector_fires_on_allocate():
    violating = "class Foo:\n    def allocate(self, x):\n        return x\n"
    try:
        assert_no_forbidden_methods(violating, "mutation")
    except AssertionError:
        return
    raise AssertionError("detector failed to fire on allocate()")


def test_forbidden_method_detector_passes_optimize():
    # optimize 是合法入口方法名（不在禁止集合内）
    assert_no_forbidden_methods(OPT_SRC, "optimizer.py")
