"""P4.1 deterministic fleet sharding and failure-isolated orchestration."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional


class AgentRole(str, Enum):
    STRATEGY = "strategy"
    GROWTH = "growth"
    PRODUCT = "product"
    UA = "ua"
    ASO = "aso"
    MONETIZATION = "monetization"
    CREATIVE = "creative"
    DATA_ANALYST = "data_analyst"
    PLAYER_SUPPORT = "player_support"
    MARKET_INTELLIGENCE = "market_intelligence"


@dataclass(frozen=True)
class FleetConfig:
    max_games: int = 200
    shard_size: int = 12
    max_workers: int = 8

    def validate(self) -> List[str]:
        errors = []
        if not 1 <= self.max_games <= 200:
            errors.append("max_games must be within [1, 200]")
        if self.shard_size < 1:
            errors.append("shard_size must be positive")
        if not 1 <= self.max_workers <= 32:
            errors.append("max_workers must be within [1, 32]")
        return errors


@dataclass
class ShardResult:
    shard_id: str
    game_ids: List[str]
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error_type: str = ""
    real_api_called: bool = False


@dataclass
class FleetRun:
    business_date: str
    roles: List[str]
    total_games: int
    successful_shards: int
    failed_shards: int
    shards: List[ShardResult]
    real_api_called: bool = False

    @property
    def completed(self) -> bool:
        return self.failed_shards == 0


class FleetOrchestrator:
    def __init__(self, runner: Callable[..., Any], config: Optional[FleetConfig] = None):
        self.runner = runner
        self.config = config or FleetConfig()

    def shard(self, game_ids: Iterable[str]) -> List[List[str]]:
        games = sorted({str(game).strip() for game in game_ids or [] if str(game).strip()})
        if len(games) > self.config.max_games:
            raise ValueError("fleet game limit exceeded")
        return [games[i:i + self.config.shard_size]
                for i in range(0, len(games), self.config.shard_size)]

    def run(self, business_date: str, game_ids: Iterable[str],
            roles: Optional[Iterable[AgentRole]] = None) -> FleetRun:
        errors = self.config.validate()
        if errors:
            raise ValueError("; ".join(errors))
        role_values = sorted({(role.value if isinstance(role, AgentRole) else str(role))
                              for role in (roles or list(AgentRole))})
        shards = self.shard(game_ids)
        results: List[ShardResult] = []
        with ThreadPoolExecutor(max_workers=min(self.config.max_workers, max(1, len(shards)))) as pool:
            future_map = {}
            for index, games in enumerate(shards):
                shard_id = f"{business_date}:shard-{index:03d}"
                future = pool.submit(self._run_one, shard_id, business_date, games, role_values)
                future_map[future] = shard_id
            for future in as_completed(future_map):
                results.append(future.result())
        results.sort(key=lambda item: item.shard_id)
        return FleetRun(
            business_date=business_date, roles=role_values,
            total_games=sum(len(item.game_ids) for item in results),
            successful_shards=sum(1 for item in results if item.success),
            failed_shards=sum(1 for item in results if not item.success),
            shards=results,
            real_api_called=any(item.real_api_called for item in results),
        )

    def _run_one(self, shard_id, business_date, games, roles):
        try:
            output = self.runner(shard_id=shard_id, business_date=business_date,
                                 game_ids=list(games), roles=list(roles))
            data = dict(output or {}) if isinstance(output, dict) else {}
            return ShardResult(shard_id, list(games), True, data,
                               real_api_called=bool(data.get("real_api_called", False)))
        except Exception as exc:
            return ShardResult(shard_id, list(games), False,
                               error_type=type(exc).__name__, real_api_called=False)


__all__ = ["AgentRole", "FleetConfig", "ShardResult", "FleetRun", "FleetOrchestrator"]
