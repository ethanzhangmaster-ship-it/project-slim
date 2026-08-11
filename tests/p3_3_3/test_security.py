"""P3.3.3 — 安全边界测试（契约 §5 / §8 Case 7）。

Controller / Planner / Simulator / Feedback 四件套**绝不**直连任何具体 Provider
（Max / Meta / Play）。唯一出口是注入的 ApprovalService + SafeExecutor。
"""
from __future__ import annotations

import ast
import os

from src.operator.adaptive_strategy import controller as controller_mod
from src.operator.adaptive_strategy import planner as planner_mod
from src.operator.adaptive_strategy import simulator as simulator_mod
from src.operator.adaptive_strategy import feedback as feedback_mod
from src.operator.adaptive_strategy import build_adaptive_strategy_engine

_ROOT = os.path.dirname(os.path.dirname(controller_mod.__file__))

_FORBIDDEN_NAMES = {
    "MaxExecutionProvider",
    "MetaExecutionProvider",
    "PlayExecutionProvider",
}
_FORBIDDEN_MODULES = {
    "src.execution.providers.max",
    "src.execution.providers.meta",
    "src.execution.providers.play",
    "execution.providers.max",
    "execution.providers.meta",
    "execution.providers.play",
}


def _source(module) -> str:
    with open(module.__file__, "r", encoding="utf-8") as fh:
        return fh.read()


def _imports_of(src: str):
    tree = ast.parse(src)
    mods = []
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.Import):
            for n in node.names:
                mods.append(n.name)
                names.add(n.name)
    return mods, names


def test_controller_no_provider_import():
    mods, names = _imports_of(_source(controller_mod))
    assert not (_FORBIDDEN_NAMES & names), names & _FORBIDDEN_NAMES
    assert not any(m in _FORBIDDEN_MODULES or m.endswith(".max") or
                   m.endswith(".meta") or m.endswith(".play")
                   for m in mods), mods


def test_planner_no_provider_import():
    mods, names = _imports_of(_source(planner_mod))
    assert not (_FORBIDDEN_NAMES & names)
    assert not any(m.endswith((".max", ".meta", ".play")) for m in mods)


def test_simulator_no_provider_import():
    mods, names = _imports_of(_source(simulator_mod))
    assert not (_FORBIDDEN_NAMES & names)
    assert not any(m.endswith((".max", ".meta", ".play")) for m in mods)


def test_feedback_no_provider_import():
    mods, names = _imports_of(_source(feedback_mod))
    assert not (_FORBIDDEN_NAMES & names)
    assert not any(m.endswith((".max", ".meta", ".play")) for m in mods)


def test_controller_module_runtime_has_no_provider_attr():
    # 运行时：controller 模块命名空间不应出现具体 Provider 类
    for name in _FORBIDDEN_NAMES:
        assert not hasattr(controller_mod, name)
    # 控制器实例也不持有 provider 属性
    ctrl = build_adaptive_strategy_engine()
    assert not hasattr(ctrl, "provider")
    assert not hasattr(ctrl, "max_provider")
    assert not hasattr(ctrl, "meta_provider")


def test_controller_only_holds_approval_and_executor():
    ctrl = build_adaptive_strategy_engine()
    # 唯一出口：审批服务 + 安全执行器（内部挂 router）
    assert hasattr(ctrl, "approval")
    assert hasattr(ctrl, "safe_executor")
    assert hasattr(ctrl, "planner")
    assert hasattr(ctrl, "simulator")
    assert hasattr(ctrl, "feedback")
