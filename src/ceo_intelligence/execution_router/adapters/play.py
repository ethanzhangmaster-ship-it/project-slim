"""E17.6 — GooglePlayAdapter（ASO 域）与 PlayReleaseAdapter（RELEASE 域）。

复用（不重造）：
- ASO：E15 PlayConnector.update_listing / create_experiment（SIM 默认，门控内建）
- RELEASE：E15 ReleaseAgent.halt / advance（经 PlayConnector 门控，
  SIM 下 real_api_called=False，halt 永远允许）
"""
from __future__ import annotations

from typing import Optional

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent,
    ReleasePolicy,
)

from ..models import AdapterOutcome, ExecutionAction, ExecutionDomain
from .base import BaseSimAdapter


def _package(action: ExecutionAction) -> str:
    return action.target or action.payload.get("package_name", "") or action.game_id


class GooglePlayAdapter(BaseSimAdapter):
    """ASO 域：商店页更新 / A/B 实验，经 PlayConnector 门控。"""

    name = "google_play"
    domain = ExecutionDomain.ASO.value

    def __init__(self, connector: Optional[PlayConnector] = None):
        # 默认 SIM：never calls the API
        self.connector = connector or PlayConnector()

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="play api error (simulated)",
                detail=f"failed {action.action_type} on {_package(action)}",
            )
        pkg = _package(action)
        if action.action_type == "update_listing":
            meta = action.payload.get("meta", {"title": "optimized"})
            res = self.connector.update_listing(pkg, meta)
            return AdapterOutcome(
                ok=res.ok, real_api_called=res.real_api_called,
                detail=res.detail, error=res.error or "",
                data={"stage": res.stage.value, "op": res.op},
            )
        if action.action_type == "run_ab_experiment":
            res = self.connector.create_experiment(
                pkg, action.payload.get("experiment", {"type": "listing_ab"}))
            return AdapterOutcome(
                ok=res.ok, real_api_called=res.real_api_called,
                detail=res.detail, error=res.error or "",
                data={"stage": res.stage.value, "op": res.op},
            )
        # keyword_analysis 等只读分析：纯本地
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"simulated: {action.action_type} for {pkg}",
        )


class PlayReleaseAdapter(BaseSimAdapter):
    """RELEASE 域：委托 E15 ReleaseAgent（halt / advance）。"""

    name = "play_runtime_release"
    domain = ExecutionDomain.RELEASE.value

    def __init__(self, release_agent: Optional[ReleaseAgent] = None,
                 state_path: Optional[str] = None):
        self.release_agent = release_agent or ReleaseAgent(
            PlayConnector(),  # SIM 默认
            policy=ReleasePolicy(),
            state_path=state_path,
        )

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="release api error (simulated)",
                detail=f"failed {action.action_type} on {_package(action)}",
            )
        pkg = _package(action)
        if action.action_type == "halt_release":
            res = self.release_agent.halt(pkg, apply=bool(action.payload.get("apply", False)))
            return AdapterOutcome(
                ok=res.ok, real_api_called=res.real_api_called,
                detail=res.detail, error=res.error or "",
                data={"stage": res.stage.value, "op": res.op},
            )
        if action.action_type == "advance_rollout":
            res = self.release_agent.advance(pkg, apply=bool(action.payload.get("apply", False)))
            return AdapterOutcome(
                ok=res.ok, real_api_called=res.real_api_called,
                detail=res.detail, error=res.error or "",
                data={"stage": res.stage.value, "op": res.op},
            )
        # triage_health 等只读
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"simulated: {action.action_type} for {pkg}",
        )


__all__ = ["GooglePlayAdapter", "PlayReleaseAdapter"]
