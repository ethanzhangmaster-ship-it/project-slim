"""
P3.5 — 契约边界锁（AST 静态检查）。

确保 GrowthKnowledgeGraph（只读底座）：
- 不调执行链（src.execution.providers / safe_executor / contracts / Provider /
  ExecutionContract）；
- 不重算业务指标（calculate_roas / predict_revenue / estimate_ltv / predict / forecast）；
- 不写回 E17.7 结果节点（record_outcome）、不产生执行请求（allocate / decide）；
- 不预测收入。

与 P3.4 边界纪律一致，且更严——consolidate 只「读」5 源、往 E17.7 图「加」高层节点。
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGETS = [
    REPO / "src/ceo_intelligence/growth_memory_graph/knowledge.py",
    REPO / "src/ceo_intelligence/growth_memory_graph/knowledge_models.py",
]

FORBIDDEN_TOKENS = [
    "src.execution.providers",
    "src.execution.safe_executor",
    "src.execution.contracts",
    "ExecutionContract",
    "Provider",
    "calculate_roas",
    "predict_revenue",
    "estimate_ltv",
    "record_outcome",
    "safe_executor",
    "allocate",
    "decide",
    "predict",
    "forecast",
]

FORBIDDEN_IMPORTS = [
    "src.execution.providers",
    "src.execution.safe_executor",
    "src.execution.contracts",
]


def _code_only(src: str) -> str:
    """剥离 docstring / 注释后的代码文本（tokenize 方式）。"""
    out = []
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in toks:
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        # 退化：万一 tokenize 失败，退回原始文本（仍可被禁止串扫描）
        return src
    return " ".join(out)


def _all_code() -> str:
    parts = []
    for p in TARGETS:
        parts.append(_code_only(p.read_text(encoding="utf-8")))
    return "\n".join(parts)


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
    # 明确不预测收入：禁止 new_revenue / *_revenue 重算类短语
    code = _all_code()
    assert "new_revenue" not in code
    assert "predict_revenue" not in code
