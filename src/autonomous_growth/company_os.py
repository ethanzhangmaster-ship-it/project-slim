"""Unified AI Game Company OS daily-cycle entry point."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from .cycle import AutonomousCycle, CycleStage, CycleState, CycleStore, ORDER
from .fleet import AgentRole


class CompanyOS:
    """Bind resumable cognition stages to the real fleet runtime execute stage."""

    def __init__(self, runtime: Any, store: CycleStore,
                 stage_handlers: Dict[str, Callable[..., Any]]):
        self.runtime, self.store = runtime, store
        self.stage_handlers = dict(stage_handlers)

    def validate(self) -> List[str]:
        required = [stage.value for stage in ORDER[:-1]
                    if stage != CycleStage.EXECUTE]
        return [f"handler missing: {name}" for name in required
                if name not in self.stage_handlers]

    def run_daily(self, business_date: str, game_ids: Iterable[str], *,
                  roles: Optional[List[AgentRole]] = None,
                  approval_present: bool = False, cycle_id: str = "") -> CycleState:
        errors = self.validate()
        if errors: raise ValueError("; ".join(errors))
        games = sorted({str(game) for game in game_ids or [] if str(game)})
        cid = cycle_id or f"company:{business_date}"
        handlers = dict(self.stage_handlers)

        def execute_stage(**_: Any) -> Dict[str, Any]:
            result = self.runtime.run(business_date, games, roles)
            if result.failed_shards:
                raise RuntimeError("fleet shard failure")
            return {
                "total_games": result.total_games,
                "successful_shards": result.successful_shards,
                "failed_shards": result.failed_shards,
                "real_api_called": result.real_api_called,
                "shards": [
                    {"shard_id": shard.shard_id, "game_ids": list(shard.game_ids),
                     "success": shard.success, "output": dict(shard.output)}
                    for shard in result.shards
                ],
            }

        handlers[CycleStage.EXECUTE.value] = execute_stage
        production = getattr(getattr(self.runtime, "config", None), "mode", "dry_run") == "production"
        return AutonomousCycle(self.store, handlers, production=production).run(
            cid, business_date, approval_present=approval_present)


__all__ = ["CompanyOS"]
