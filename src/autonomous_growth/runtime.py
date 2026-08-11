"""P4 composition root connecting fleet orchestration to the real operator stack."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.execution.models import ExecutionMode
from src.operator.pipeline import DailyOperatorPipeline

from .fleet import AgentRole, FleetConfig, FleetOrchestrator, FleetRun


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str = "dry_run"
    require_memory: bool = True
    require_feedback: bool = True
    fleet: FleetConfig = FleetConfig()


class LaunchForgeRuntime:
    """Create one real DailyOperatorPipeline per isolated fleet shard."""

    def __init__(self, context_factory: Callable[..., Any], *,
                 feedback_recorder: Any = None, config: RuntimeConfig = RuntimeConfig(),
                 pipeline_class: Any = DailyOperatorPipeline):
        self.context_factory = context_factory
        self.feedback_recorder = feedback_recorder
        self.config = config
        self.pipeline_class = pipeline_class

    def validate(self) -> List[str]:
        errors = list(self.config.fleet.validate())
        if self.config.mode not in ("simulation", "dry_run", "production"):
            errors.append("invalid runtime mode")
        if self.config.require_feedback and self.feedback_recorder is None:
            errors.append("feedback recorder required")
        return errors

    def run(self, business_date: str, game_ids: List[str],
            roles: Optional[List[AgentRole]] = None) -> FleetRun:
        errors = self.validate()
        if errors: raise ValueError("; ".join(errors))
        return FleetOrchestrator(self._run_shard, self.config.fleet).run(
            business_date, game_ids, roles)

    def _run_shard(self, *, shard_id: str, business_date: str,
                   game_ids: List[str], roles: List[str]) -> Dict[str, Any]:
        mode = ExecutionMode(self.config.mode)
        context = self.context_factory(game_ids=list(game_ids), mode=mode,
                                       shard_id=shard_id, roles=list(roles))
        if self.config.require_memory and getattr(context, "memory_controller", None) is None:
            raise RuntimeError("memory controller required")
        if getattr(context, "approval_service", None) is None:
            raise RuntimeError("approval service required")
        if getattr(context, "safe_executor", None) is None:
            raise RuntimeError("safe executor required")
        pipeline = self.pipeline_class(context, feedback_recorder=self.feedback_recorder)
        stages, aggregates = pipeline.execute(business_date, run_id=shard_id)
        stage_rows = [stage.to_dict() if hasattr(stage, "to_dict") else dict(stage)
                      for stage in stages]
        real = any(bool(row.get("real_api_called", False)) for row in stage_rows)
        return {"shard_id": shard_id, "stages": stage_rows,
                "aggregates": dict(aggregates or {}), "real_api_called": real}


__all__ = ["RuntimeConfig", "LaunchForgeRuntime"]
