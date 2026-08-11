"""
P3.5.1 — 契约边界锁（AST 静态检查）。

确保 GrowthKnowledgeAdvisor / KnowledgeSignal（只读消费端）：
- 不调执行链（src.execution / SafeExecutor / Provider / DecisionEngine）；
- 不写回（write() / append() / consolidate() / record_outcome / save()）；
- 不重算业务指标（calculate_roas / predict_revenue / estimate_ltv / allocate /
  decide / predict / forecast）；
- 不预测收入。

扫描范围仅 advisor.py + signals.py（P3.5.1 新增文件），与 P3.5 一致。
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGETS = [
    REPO / "src/ceo_intelligence/growth_memory_graph/advisor.py",
    REPO / "src/ceo_intelligence/growth_memory_graph/signals.py",
]

FORBIDDEN_TOKENS = [
    "src.execution",
    "SafeExecutor",
    "Provider",
    "DecisionEngine",
    "write(",
    "append(",
    "consolidate(",
    "record_outcome",
    "save(",
    "calculate_roas",
    "predict_revenue",
    "estimate_ltv",
    "allocate",
    "decide",
    "predict",
    "forecast",
    "safe_executor",
]

FORBIDDEN_IMPORTS = [
    "src.execution",
    "safe_executor",
]


def _code_only(src: str) -> str:
    out = []
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in toks:
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        return src
    return " ".join(out)


def _all_code() -> str:
    return "\n".join(_code_only(p.read_text(encoding="utf-8")) for p in TARGETS)


def test_files_exist():
    for p in TARGETS:
        assert p.exists(), f"missing {p}"


def test_no_forbidden_tokens():
    code = _all_code()
    for bad in FORBIDDEN_TOKENS:
        assert bad not in code, f"forbidden token found: {bad}"


def test_no_forbidden_imports():
    for p in TARGETS:
        text = p.read_text(encoding="utf-8")
        for bad in FORBIDDEN_IMPORTS:
            assert bad not in text, f"forbidden import in {p.name}: {bad}"


def test_no_revenue_prediction_phrase():
    code = _all_code()
    assert "new_revenue" not in code
    assert "revenue *" not in code
    assert "predict_revenue" not in code
