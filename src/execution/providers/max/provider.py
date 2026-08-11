"""P2.2 MAX Provider — 广告变现执行器（AppLovin MAX）。

第一阶段支持：DISABLE_NETWORK（关停某广告网络）。

设计：
- 复用 operation.providers.live.max.client.MaxClient 的传输层（不重写）
- DRY_RUN：只回显意图，real_api_called=False
- PRODUCTION：经 MaxClient 真实请求 MAX Management API，
  real_api_called=True（成败不论，平台对写动作的限制见 memory：Management API
  在扩容 targeting 瀑布流上会 403/422，这正是「人工后台落子」纪律的体现）
- 动作参数（ad_unit_id / network）从 intent.expected_impact 读取，
  缺省回退到 intent.target_id 作为 ad_unit_id
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ...models import ExecutionAction, ExecutionIntent, ExecutionRequest
from ..base import BaseExecutionProvider
from ..result import STATUS_FAILED, STATUS_SUCCESS, ExecutionResult


class MaxExecutionProvider(BaseExecutionProvider):
    provider_id = "max"
    supported_actions = (
        ExecutionAction.DISABLE_NETWORK,
        ExecutionAction.UPDATE_WATERFALL,
    )

    def __init__(self, client: Any = None, *, data_dir: str = "data") -> None:
        if client is None:
            from operation.providers.live.max.client import MaxClient

            client = MaxClient()
        self.client = client
        self.data_dir = data_dir

    # ------------------------------------------------------------------
    def can_execute(self, intent: ExecutionIntent) -> bool:
        return intent.action in self.supported_actions

    # ------------------------------------------------------------------
    # 参数解析
    # ------------------------------------------------------------------
    @staticmethod
    def _params(intent: ExecutionIntent) -> Dict[str, Any]:
        impact = intent.expected_impact or {}
        ad_unit_id = impact.get("ad_unit_id") or intent.target_id
        network = impact.get("network")
        networks = impact.get("networks")
        return {
            "ad_unit_id": ad_unit_id,
            "network": network,
            "networks": networks,
        }

    # ------------------------------------------------------------------
    # PRODUCTION 真实执行
    # ------------------------------------------------------------------
    def _do_real(self, request: ExecutionRequest) -> ExecutionResult:
        intent = request.intent
        p = self._params(intent)
        ad_unit_id = p["ad_unit_id"]

        if intent.action == ExecutionAction.DISABLE_NETWORK:
            network = p["network"] or "unknown"
            payload = {"disable_network": network}
            endpoint = f"/mediation/v1/ad_unit/{ad_unit_id}"
            resp = self.client.request("PUT", endpoint, payload)
            after_state = {"action": "disable_network", "network": network,
                          "ad_unit_id": ad_unit_id, "response": resp}
        elif intent.action == ExecutionAction.UPDATE_WATERFALL:
            networks = p["networks"] or []
            resp = self.client.update_waterfall(ad_unit_id, networks)
            after_state = {"action": "update_waterfall",
                          "ad_unit_id": ad_unit_id, "response": resp}
        else:  # pragma: no cover — guarded by can_execute
            return self._blocked(request, "unsupported max action")

        if isinstance(resp, dict) and resp.get("success"):
            return ExecutionResult(
                request_id=request.request_id,
                provider=self.provider_id,
                status=STATUS_SUCCESS,
                real_api_called=True,
                before_state={"ad_unit_id": ad_unit_id},
                after_state=after_state,
            )
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_FAILED,
            real_api_called=True,
            before_state={"ad_unit_id": ad_unit_id},
            after_state=after_state,
            error=(resp.get("error") if isinstance(resp, dict) else str(resp)),
        )


__all__ = ["MaxExecutionProvider"]
