"""
P3.5.2 — 契约边界锁（AST 静态检查，P3.5.2 契约冻结点 1/5/6/7）。

锁死「Graph Writer 唯一入口 = KnowledgeFeedbackRecorder.record()」：

1. feedback.py（writer）：
   - ✅ 正向：必须含 ``def record`` 与 ``add_node``（写 Graph 的唯一合法入口）；
   - ❌ 禁 5 源写回：record_outcome / consolidate( / strategy_memory /
     execution_memory / recovery_store；
   - ❌ 禁执行链：src.execution / SafeExecutor / Provider / DecisionEngine。
2. advisor.py + signals.py（消费端）：
   - ❌ 禁 add_node( / add_edge(（P3.5.1 只读纪律保持）;
   - ❌ 禁 import feedback（不得自行写）。
3. optimizer.py + loop.py（业务计算层）：
   - ❌ 禁 add_node( / add_edge( / growth_memory_graph.feedback /
     KnowledgeFeedbackRecorder（不感知 Knowledge storage）。
4. operator/feedback.py（Operator Layer 适配器）：
   - ✅ 正向：必须含 DecisionKnowledgeRecord（经 recorder 写）；
   - ❌ 禁 add_node( / add_edge(（只调 recorder，不直接写）；
   - ❌ 禁 5 源写回 / 执行链。

全部剥 docstring/注释后扫描（注释/字符串里的说明不算引用）。
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

WRITER = REPO / "src/ceo_intelligence/growth_memory_graph/feedback.py"
READERS = [
    REPO / "src/ceo_intelligence/growth_memory_graph/advisor.py",
    REPO / "src/ceo_intelligence/growth_memory_graph/signals.py",
]
BUSINESS = [
    REPO / "src/operator/portfolio/optimizer.py",
    REPO / "src/operator/strategy/loop.py",
]
ADAPTER = REPO / "src/operator/feedback.py"

SOURCE_WRITE_TOKENS = [
    "record_outcome",
    "consolidate(",
    "strategy_memory",
    "execution_memory",
    "recovery_store",
]
EXECUTION_TOKENS = [
    "src.execution",
    "SafeExecutor",
    "Provider",
    "DecisionEngine",
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


def _all_code(files) -> str:
    return "\n".join(_code_only(p.read_text(encoding="utf-8")) for p in files)


# ---------------------------------------------------------------------- #
# 基础
# ---------------------------------------------------------------------- #
def test_files_exist():
    for p in [WRITER, *READERS, *BUSINESS, ADAPTER]:
        assert p.exists(), f"missing {p}"


# ---------------------------------------------------------------------- #
# 1. Writer（feedback.py）：唯一写入口 + 禁源写回 + 禁执行链
# ---------------------------------------------------------------------- #
def test_writer_has_record_and_add_node():
    code = _code_only(WRITER.read_text(encoding="utf-8"))
    assert "def record" in code
    assert "add_node" in code


def test_writer_no_source_write_back():
    code = _code_only(WRITER.read_text(encoding="utf-8"))
    for bad in SOURCE_WRITE_TOKENS:
        assert bad not in code, f"forbidden source-write token in feedback.py: {bad}"


def test_writer_no_execution_layer():
    code = _code_only(WRITER.read_text(encoding="utf-8"))
    for bad in EXECUTION_TOKENS:
        assert bad not in code, f"forbidden execution token in feedback.py: {bad}"


# ---------------------------------------------------------------------- #
# 2. 消费端（advisor.py + signals.py）：保持只读，不得自行写
# ---------------------------------------------------------------------- #
def test_readers_stay_read_only():
    code = _all_code(READERS)
    assert "add_node(" not in code
    assert "add_edge(" not in code
    # 不得 import feedback（不得绕过 recorder 自己写）
    for p in READERS:
        assert "feedback" not in _code_only(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- #
# 3. 业务计算层（optimizer.py + loop.py）：不感知 Knowledge storage
# ---------------------------------------------------------------------- #
def test_business_layer_no_graph_writes():
    for p in BUSINESS:
        code = _code_only(p.read_text(encoding="utf-8"))
        assert "add_node(" not in code, f"{p.name} writes graph nodes"
        assert "add_edge(" not in code, f"{p.name} writes graph edges"
        assert "growth_memory_graph.feedback" not in code, f"{p.name} imports feedback"
        assert "KnowledgeFeedbackRecorder" not in code, f"{p.name} uses recorder"


# ---------------------------------------------------------------------- #
# 4. Operator Layer 适配器（operator/feedback.py）：只调 recorder
# ---------------------------------------------------------------------- #
def test_adapter_delegates_to_recorder_only():
    code = _code_only(ADAPTER.read_text(encoding="utf-8"))
    assert "DecisionKnowledgeRecord" in code
    assert "def record_portfolio_feedback" in code
    assert "def record_strategy_feedback" in code
    # 只调 recorder.record()，绝不直接写 Graph
    assert "add_node(" not in code
    assert "add_edge(" not in code


def test_adapter_no_source_write_back_or_execution():
    code = _code_only(ADAPTER.read_text(encoding="utf-8"))
    for bad in SOURCE_WRITE_TOKENS + EXECUTION_TOKENS:
        assert bad not in code, f"forbidden token in operator/feedback.py: {bad}"
