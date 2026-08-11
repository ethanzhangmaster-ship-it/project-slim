"""P2.2 Meta Provider — 买量执行器（Meta / Facebook Ads）。

第一阶段仅支持：PAUSE_CAMPAIGN（暂停广告系列）。
扩量（SCALE_BUDGET）风险高，本期不做（防止失控烧钱）。

设计：
- 复用 operation.providers.live.meta.meta_client.update_campaign_status（真实写）
- DRY_RUN：只回显意图，real_api_called=False
- PRODUCTION：经 meta_client 真实 POST Graph API campaign/update，
  real_api_called=True（成败不论）
- transport 可注入（测试用 fake），默认直连真实 Meta 客户端
- campaign_id 从 intent.expected_impact["campaign_id"] 读取，缺省回退 target_id
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ...models import ExecutionAction, ExecutionIntent, ExecutionRequest
from ..base import BaseExecutionProvider
from ..result import STATUS_FAILED, STATUS_SUCCESS, ExecutionResult


# transport 契约：(campaign_id, status) -> Dict{"success", ...}
Transport = Callable[[str, str], Dict[str, Any]]


class MetaExecutionProvider(BaseExecutionProvider):
    provider_id = "meta"
    supported_actions = (ExecutionAction.PAUSE_CAMPAIGN,)

    def __init__(
        self,
        *,
        access_token: str = "",
        ad_account_id: str = "",
        proxy: Optional[str] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.proxy = proxy
        self._transport = transport

    # ------------------------------------------------------------------
    def can_execute(self, intent: ExecutionIntent) -> bool:
        return intent.action in self.supported_actions

    # ------------------------------------------------------------------
    def _resolve_transport(self) -> Transport:
        if self._transport is not None:
            return self._transport

        def _real(campaign_id: str, status: str) -> Dict[str, Any]:
            from operation.providers.live.meta.meta_client import (
                update_campaign_status,
            )

            return update_campaign_status(
                self.access_token,
                campaign_id,
                status,
                proxy=self.proxy,
            )

        return _real

    # ------------------------------------------------------------------
    def _do_real(self, request: ExecutionRequest) -> ExecutionResult:
        intent = request.intent
        impact = intent.expected_impact or {}
        campaign_id = impact.get("campaign_id") or intent.target_id
        transport = self._resolve_transport()
        try:
            resp = transport(campaign_id, "PAUSED")
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                request_id=request.request_id,
                provider=self.provider_id,
                status=STATUS_FAILED,
                real_api_called=True,
                before_state={"campaign_id": campaign_id},
                after_state={},
                error=f"{type(exc).__name__}: {exc}",
            )
        if isinstance(resp, dict) and resp.get("success"):
            return ExecutionResult(
                request_id=request.request_id,
                provider=self.provider_id,
                status=STATUS_SUCCESS,
                real_api_called=True,
                before_state={"campaign_id": campaign_id},
                after_state={"campaign_id": campaign_id, "status": "PAUSED",
                             "response": resp},
            )
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_FAILED,
            real_api_called=True,
            before_state={"campaign_id": campaign_id},
            after_state={"response": resp},
            error=(resp.get("error") if isinstance(resp, dict) else str(resp)),
        )


__all__ = ["MetaExecutionProvider"]
