"""SOP (Standard Operating Procedure) 定义 — YAML 格式的 agent 编排流程.

借鉴 MetaGPT 的 SOP 理念:
  - Code = SOP(Team): 将 agent 协作流程标准化
  - 角色化 agent 按步骤编排, 输入/输出显式声明
  - YAML 定义可读、可版本控制、可热重载

SOP 结构:
  name: 市场拓展决策流程
  trigger: manual | scheduled | event
  steps:
    - agent: MarketIntelligenceAgent
      action: research_market
      input: { query: "$user_query" }
      output: research_result
    - agent: ASOKeywordAgent
      action: run
      input: { realities: "$research_result.keywords" }
      output: keyword_report
  fallback:
    on_error: skip | retry | abort

集成点:
  - GrowthLoopScheduler.load_sop() 加载 YAML 定义
  - GrowthLoopScheduler.run_sop() 按 SOP 编排 agent 调用链
  - 替代硬编码的 Python 编排逻辑

用法:
  loader = SOPLoader(sops_dir="sops")
  sop = loader.load("market_expansion")
  executor = SOPExecutor(sop, agent_registry={...})
  result = executor.execute(context={"user_query": "2026 休闲游戏趋势"})
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class SOPStep:
    """SOP 单步 — 一个 agent 调用."""

    agent: str                              # agent 名称
    action: str                             # agent 方法名
    input: Dict[str, Any] = field(default_factory=dict)  # 输入参数
    output: str = ""                        # 输出变量名
    condition: str = ""                     # 执行条件 (如 "$prev_result.success == true")
    timeout: int = 120                      # 超时 (秒)
    retry: int = 0                          # 重试次数
    on_error: str = "skip"                  # skip | retry | abort

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "action": self.action,
            "input": self.input,
            "output": self.output,
            "condition": self.condition,
            "timeout": self.timeout,
            "retry": self.retry,
            "on_error": self.on_error,
        }


@dataclass
class SOPDefinition:
    """SOP 定义 — 完整的 agent 编排流程."""

    name: str                               # SOP 名称
    trigger: str = "manual"                 # manual | scheduled | event
    description: str = ""                   # 描述
    steps: List[SOPStep] = field(default_factory=list)
    fallback_on_error: str = "skip"         # skip | abort
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "fallback_on_error": self.fallback_on_error,
            "metadata": self.metadata,
        }


@dataclass
class SOPExecutionResult:
    """SOP 执行结果."""

    sop_name: str
    success: bool
    steps_executed: int = 0
    steps_succeeded: int = 0
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sop_name": self.sop_name,
            "success": self.success,
            "steps_executed": self.steps_executed,
            "steps_succeeded": self.steps_succeeded,
            "outputs": self.outputs,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
        }


# ── SOP 加载器 ────────────────────────────────────────────────

class SOPLoader:
    """从 YAML 文件加载 SOP 定义.

    YAML 格式:
        name: market_expansion
        trigger: manual
        description: 市场拓展决策流程
        steps:
          - agent: MarketIntelligenceAgent
            action: research_market
            input:
              query: "$user_query"
            output: research_result
            timeout: 120
            on_error: skip
        fallback_on_error: skip
    """

    def __init__(self, sops_dir: str = "sops") -> None:
        self._sops_dir = Path(sops_dir)

    def list_sops(self) -> List[str]:
        """列出所有可用的 SOP 名称."""
        if not self._sops_dir.exists():
            return []
        return [
            f.stem for f in self._sops_dir.glob("*.yaml")
        ] + [
            f.stem for f in self._sops_dir.glob("*.yml")
        ]

    def load(self, name: str) -> SOPDefinition:
        """按名称加载 SOP 定义.

        Args:
            name: SOP 名称 (对应 sops/{name}.yaml)

        Returns:
            SOPDefinition 实例

        Raises:
            FileNotFoundError: SOP 文件不存在
            ValueError: YAML 格式错误
        """
        path = self._find_sop_file(name)
        if path is None:
            raise FileNotFoundError(f"SOP '{name}' 未找到在 {self._sops_dir}")

        try:
            import yaml
        except ImportError:
            raise ValueError("PyYAML 未安装, 请运行: pip install pyyaml")

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"SOP '{name}' 格式错误: 顶层应为 dict")

        return self._parse_definition(name, data)

    def load_all(self) -> Dict[str, SOPDefinition]:
        """加载所有 SOP 定义."""
        result: Dict[str, SOPDefinition] = {}
        for name in self.list_sops():
            try:
                result[name] = self.load(name)
            except Exception as exc:
                logger.warning("加载 SOP '%s' 失败: %s", name, exc)
        return result

    def _find_sop_file(self, name: str) -> Optional[Path]:
        for ext in (".yaml", ".yml"):
            path = self._sops_dir / f"{name}{ext}"
            if path.exists():
                return path
        return None

    @staticmethod
    def _parse_definition(name: str, data: Dict[str, Any]) -> SOPDefinition:
        """解析 YAML dict 为 SOPDefinition."""
        steps: List[SOPStep] = []
        for step_data in data.get("steps", []):
            steps.append(SOPStep(
                agent=step_data.get("agent", ""),
                action=step_data.get("action", ""),
                input=step_data.get("input", {}),
                output=step_data.get("output", ""),
                condition=step_data.get("condition", ""),
                timeout=step_data.get("timeout", 120),
                retry=step_data.get("retry", 0),
                on_error=step_data.get("on_error", "skip"),
            ))

        return SOPDefinition(
            name=data.get("name", name),
            trigger=data.get("trigger", "manual"),
            description=data.get("description", ""),
            steps=steps,
            fallback_on_error=data.get("fallback_on_error", "skip"),
            metadata=data.get("metadata", {}),
        )


# ── SOP 执行器 ────────────────────────────────────────────────

class SOPExecutor:
    """按 SOP 定义编排 agent 调用链.

    agent_registry 是一个 dict[str, Any], 将 agent 名称映射到实例.
    执行时按步骤顺序调用 agent.action(**resolved_input), 将结果存入 context.
    """

    def __init__(
        self,
        sop: SOPDefinition,
        agent_registry: Dict[str, Any],
    ) -> None:
        self._sop = sop
        self._agents = agent_registry

    def execute(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> SOPExecutionResult:
        """执行 SOP.

        Args:
            context: 初始上下文 (包含 SOP 输入变量)

        Returns:
            SOPExecutionResult 包含每步输出和执行状态
        """
        import time

        ctx = dict(context) if context else {}
        outputs: Dict[str, Any] = {}
        errors: List[str] = []
        steps_executed = 0
        steps_succeeded = 0
        start_time = time.time()

        for i, step in enumerate(self._sop.steps):
            # 检查条件
            if step.condition and not self._eval_condition(step.condition, ctx):
                logger.debug("SOP step %d 跳过 (条件不满足): %s", i, step.condition)
                continue

            steps_executed += 1

            # 解析输入参数 (变量引用 $var_name)
            resolved_input = self._resolve_inputs(step.input, ctx)

            # 获取 agent 实例
            agent = self._agents.get(step.agent)
            if agent is None:
                err = f"步骤 {i}: agent '{step.agent}' 未注册"
                errors.append(err)
                if step.on_error == "abort" or self._sop.fallback_on_error == "abort":
                    break
                continue

            # 获取 agent 方法
            method = getattr(agent, step.action, None)
            if method is None or not callable(method):
                err = f"步骤 {i}: agent '{step.agent}' 没有 action '{step.action}'"
                errors.append(err)
                if step.on_error == "abort" or self._sop.fallback_on_error == "abort":
                    break
                continue

            # 执行
            try:
                result = self._call_agent(method, resolved_input, step.timeout)

                if step.output:
                    outputs[step.output] = result
                    ctx[step.output] = result

                steps_succeeded += 1
                logger.info(
                    "SOP step %d/%d 完成: %s.%s → %s",
                    i + 1, len(self._sop.steps),
                    step.agent, step.action, step.output or "(unnamed)",
                )

            except Exception as exc:
                err = f"步骤 {i}: {step.agent}.{step.action} 失败: {exc}"
                errors.append(err)
                logger.error("SOP step %d 失败: %s", i, exc, exc_info=True)

                if step.on_error == "abort" or self._sop.fallback_on_error == "abort":
                    break

                # retry
                for retry_idx in range(step.retry):
                    logger.info("SOP step %d 重试 %d/%d", i, retry_idx + 1, step.retry)
                    try:
                        result = self._call_agent(method, resolved_input, step.timeout)
                        if step.output:
                            outputs[step.output] = result
                            ctx[step.output] = result
                        steps_succeeded += 1
                        break
                    except Exception as retry_exc:
                        logger.warning("SOP step %d 重试 %d 失败: %s", i, retry_idx + 1, retry_exc)

        duration = time.time() - start_time
        success = steps_succeeded == steps_executed and not errors

        return SOPExecutionResult(
            sop_name=self._sop.name,
            success=success,
            steps_executed=steps_executed,
            steps_succeeded=steps_succeeded,
            outputs=outputs,
            errors=errors,
            duration_seconds=duration,
        )

    # ── 内部方法 ──

    @staticmethod
    def _resolve_inputs(
        input_spec: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析输入参数中的变量引用 ($var_name)."""
        resolved: Dict[str, Any] = {}
        for key, value in input_spec.items():
            resolved[key] = SOPExecutor._resolve_value(value, context)
        return resolved

    @staticmethod
    def _resolve_value(value: Any, context: Dict[str, Any]) -> Any:
        """递归解析值中的变量引用."""
        if isinstance(value, str):
            return SOPExecutor._resolve_string(value, context)
        elif isinstance(value, dict):
            return {
                k: SOPExecutor._resolve_value(v, context)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [SOPExecutor._resolve_value(v, context) for v in value]
        else:
            return value

    @staticmethod
    def _resolve_string(s: str, context: Dict[str, Any]) -> Any:
        """解析字符串中的 $variable 引用.

        支持:
          - "$var" → 整体替换为 context["var"]
          - "prefix $var suffix" → 字符串插值
          - "$var.field" → context["var"]["field"] (仅 dict)
        """
        # 完全匹配 $var 或 $var.field
        full_match = re.match(r"^\$([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)$", s)
        if full_match:
            return SOPExecutor._lookup_path(full_match.group(1), context)

        # 字符串插值
        def replace_var(m):
            path = m.group(1)
            val = SOPExecutor._lookup_path(path, context)
            return str(val) if val is not None else m.group(0)

        return re.sub(
            r"\$\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}",
            replace_var,
            s,
        )

    @staticmethod
    def _lookup_path(path: str, context: Dict[str, Any]) -> Any:
        """按点分路径查找 context 值."""
        parts = path.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _eval_condition(condition: str, context: Dict[str, Any]) -> bool:
        """评估条件表达式 (简化版: 只支持 $var == value / $var != value)."""
        # 解析变量
        def resolve_var(m):
            path = m.group(1)
            val = SOPExecutor._lookup_path(path, context)
            return repr(val)

        expr = re.sub(
            r"\$([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
            resolve_var,
            condition,
        )

        try:
            # 安全评估: 只允许比较运算
            allowed = all(c in "!=<>TrueFalseNone'\"" for c in expr if not c.isalnum())
            if not allowed:
                logger.warning("条件表达式包含不允许的字符: %s", expr)
                return True  # 默认执行
            result = eval(expr, {"__builtins__": {}}, {})
            return bool(result)
        except Exception:
            logger.warning("条件评估失败: %s → %s", condition, expr)
            return True  # 默认执行

    @staticmethod
    def _call_agent(method, kwargs: Dict[str, Any], timeout: int) -> Any:
        """调用 agent 方法 (带超时)."""
        import threading

        result_holder: Dict[str, Any] = {}

        def _call():
            try:
                result_holder["result"] = method(**kwargs)
            except Exception as exc:
                result_holder["error"] = exc

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            raise TimeoutError(f"agent 调用超时 (timeout={timeout}s)")

        if "error" in result_holder:
            raise result_holder["error"]

        return result_holder.get("result")


__all__ = [
    "SOPStep",
    "SOPDefinition",
    "SOPExecutionResult",
    "SOPLoader",
    "SOPExecutor",
]
