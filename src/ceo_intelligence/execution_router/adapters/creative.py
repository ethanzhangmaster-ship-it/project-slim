"""E17.6 — CreativeAdapter：CREATIVE 域执行（委托 E11 Creative Evolution）。

SIM seam：确定性模拟 DNA 分析 / 素材生成 / CLIP 筛选，不深入 E11 内部实现，
不触发任何真实生成 API（real_api_called=False）。
接真实链路时在此接 E11 的 dna_builder / optimizer 管线。
"""
from __future__ import annotations

from ..models import AdapterOutcome, ExecutionAction, ExecutionDomain
from .base import BaseSimAdapter


class CreativeAdapter(BaseSimAdapter):
    name = "creative_agent"
    domain = ExecutionDomain.CREATIVE.value

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="creative pipeline error (simulated)",
                detail=f"failed {action.action_type} for {action.game_id}",
            )
        if action.action_type == "analyze_dna":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: analyzed winning creative DNA for {action.game_id}",
                data={"winner_dna": "hyper_casual_v1"},
            )
        if action.action_type == "generate_creatives":
            count = int(action.payload.get("count", 30))
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would generate {count} creatives for {action.game_id}",
                data={"candidate_count": count},
            )
        if action.action_type == "clip_screen":
            top = int(action.payload.get("top", 10))
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: CLIP screened top {top} variants for {action.game_id}",
                data={"shortlist_count": top},
            )
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"simulated: {action.action_type} for {action.game_id}",
        )


__all__ = ["CreativeAdapter"]
