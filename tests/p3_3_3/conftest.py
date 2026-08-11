"""P3.3.3 测试夹具 — 全部落在 tmp_path，绝不污染 data/。

提供：
- FakeProvider：可注入的 Provider 骨架（记录调用次数，DRY_RUN 永不强触网）
- build_engine：一键装配 AdaptiveStrategyController
- make_request：AdaptiveStrategyRequest 工厂
- blocking_prior / review_prior：强制 SIM 闸门结果的先验注入器
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.ceo_intelligence.simulation_engine.models import SimulationPrior
from src.execution.models import ExecutionAction
from src.execution.providers.base import BaseExecutionProvider
from src.execution.providers.result import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ExecutionResult,
)
from src.operator.adaptive_strategy import (
    AdaptiveStrategyController,
    AdaptiveStrategyRequest,
    build_adaptive_strategy_engine,
)

# ---------------------------------------------------------------------------
# 可注入的 Provider（不触真实外部系统）
# ---------------------------------------------------------------------------
MAX_ACTIONS = (ExecutionAction.DISABLE_NETWORK, ExecutionAction.UPDATE_WATERFALL)
META_ACTIONS = (ExecutionAction.PAUSE_CAMPAIGN,)


class FakeProvider(BaseExecutionProvider):
    """测试用 Provider：记录调用，支持配置返回状态与 real_api_called 纪律。"""

    def __init__(
        self,
        provider_id: str,
        supported_actions,
        *,
        real_api_called: bool = True,
        status: str = STATUS_SUCCESS,
        after_state: Optional[Dict[str, Any]] = None,
        on_real: Optional[Callable] = None,
    ) -> None:
        self.provider_id = provider_id
        self.supported_actions = tuple(supported_actions)
        self._real_api_called = real_api_called
        self._status = status
        self._after_state = after_state or {}
        self.on_real = on_real
        # 观测字段
        self.execute_calls: List[Any] = []   # 每次 execute 调用记录的 request
        self.real_invocations: int = 0
        self.dry_invocations: int = 0

    def execute(self, request):
        self.execute_calls.append(request)
        return super().execute(request)

    def _dry_run(self, request):
        self.dry_invocations += 1
        return super()._dry_run(request)

    def _do_real(self, request):
        self.real_invocations += 1
        if self.on_real is not None:
            return self.on_real(request)
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=self._status,
            real_api_called=self._real_api_called,
            before_state={},
            after_state=dict(self._after_state),
        )


def ok_providers() -> List[FakeProvider]:
    return [
        FakeProvider("max", MAX_ACTIONS),
        FakeProvider("meta", META_ACTIONS),
    ]


def blocked_providers() -> List[FakeProvider]:
    return [
        FakeProvider("max", MAX_ACTIONS, status=STATUS_BLOCKED, real_api_called=False),
        FakeProvider("meta", META_ACTIONS, status=STATUS_BLOCKED, real_api_called=False),
    ]


def failed_providers() -> List[FakeProvider]:
    return [
        FakeProvider("max", MAX_ACTIONS, status=STATUS_FAILED, real_api_called=True),
        FakeProvider("meta", META_ACTIONS, status=STATUS_FAILED, real_api_called=True),
    ]


# ---------------------------------------------------------------------------
# 引擎构建器
# ---------------------------------------------------------------------------
def build_engine(
    *,
    providers: Optional[List[FakeProvider]] = None,
    memory_path: Optional[str] = None,
    prior_provider: Optional[Callable[[str], Any]] = None,
) -> AdaptiveStrategyController:
    """一键装配（共享 approval_store 的闭环）。"""
    return build_adaptive_strategy_engine(
        providers=providers if providers is not None else ok_providers(),
        memory_path=memory_path,
        prior_provider=prior_provider,
    )


# ---------------------------------------------------------------------------
# 请求工厂
# ---------------------------------------------------------------------------
def make_request(strategy_id: str = "adaptive.network_cleanup", **kw) -> AdaptiveStrategyRequest:
    base = dict(
        proposal_id="p1",
        strategy_id=strategy_id,
        target="game_a",
        expected_change="kill zombie network",
        parameters={"network": "zombie_net_X"},
        mode="dry_run",
        approver="operator1",
        approver_role="OPERATOR",
        source="strategy_loop",
    )
    base.update(kw)
    return AdaptiveStrategyRequest(**base)


# ---------------------------------------------------------------------------
# SIM 先验注入器（强制闸门结果）
# ---------------------------------------------------------------------------
def blocking_prior(_opportunity_type: str) -> SimulationPrior:
    """负期望先验 → 基线 p50 < 0 → PreFlightStatus.BLOCK。"""
    return SimulationPrior(
        opportunity_type=_opportunity_type,
        expected_revenue_change=-0.5,
        expected_roas_change=-0.2,
        confidence=0.5,
        risk=0.5,
        source="injected-block",
    )


def review_prior(_opportunity_type: str) -> SimulationPrior:
    """高风险先验 → REVIEW（仍应继续进审批）。"""
    return SimulationPrior(
        opportunity_type=_opportunity_type,
        expected_revenue_change=0.10,
        expected_roas_change=0.10,
        confidence=0.40,   # 低于 0.50 → REVIEW
        risk=0.70,         # 高于 0.60 → REVIEW
        source="injected-review",
    )
