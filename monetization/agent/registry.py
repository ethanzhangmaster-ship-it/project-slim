"""
E14 Slice 1 — Multi-game isolation: registry + fleet coordinator
===============================================================

GameRegistry holds the catalogue of game tenants. GameFactoryOS is the
operating-system layer: it instantiates ONE fully-isolated MonetizationAgent per
active game and runs them as a fleet.

Isolation is enforced at construction time in `build_game_agent`:
  * each game gets its OWN DecisionStore (a namespaced JSONL path);
  * each game's Bayesian prior is learned ONLY from that store;
  * each game gets its OWN PolicyConfig / GuardrailConfig objects (no shared
    mutable config, so a tuning change for game A can never leak into game B).

Pure-Python, stdlib only. No LLM, no external API, no shared global state.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from monetization.agent.controller import MonetizationAgent
from monetization.agent.game_config import GameConfig
from monetization.agent.guardrails import Guardrails
from monetization.agent.models import AgentReport, GuardrailConfig, PolicyConfig
from monetization.agent.policy import Policy
from monetization.intelligence.strategy_prior import StrategyPriorEngine
from monetization.learning.decision_store import DecisionStore


def build_game_agent(
    cfg: GameConfig,
    base_store_dir: str,
    seed_memory_fn: Optional[Callable[[], list]] = None,
) -> MonetizationAgent:
    """Build a fully isolated MonetizationAgent for a single game.

    Args:
        cfg:             the game's configuration.
        base_store_dir:  root directory under which per-game stores live.
        seed_memory_fn:  optional callable returning DecisionRecords to
                         pre-populate the game's store (e.g. shared synthetic
                         history). Each game receives its OWN copy.
    """
    store = DecisionStore(str(cfg.resolved_store_path(base_store_dir)))
    if seed_memory_fn is not None:
        for rec in seed_memory_fn():
            store.append(rec)

    prior = StrategyPriorEngine()
    prior.learn_from_store(store)
    baseline = set(prior.prior_map().keys())

    policy = Policy(PolicyConfig(**cfg.policy), baseline_strategies=baseline)
    guardrails = Guardrails(GuardrailConfig(**cfg.guardrails))
    return MonetizationAgent(
        store=store, prior_engine=prior, policy=policy, guardrails=guardrails
    )


class GameRegistry:
    """Catalogue of game tenants (in-memory; loadable from a JSON dir)."""

    def __init__(self):
        self._games: Dict[str, GameConfig] = {}

    def register(self, cfg: GameConfig) -> None:
        self._games[cfg.slug] = cfg

    def get(self, slug: str) -> Optional[GameConfig]:
        return self._games.get(slug)

    @property
    def games(self) -> List[GameConfig]:
        return list(self._games.values())

    def active_games(self) -> List[GameConfig]:
        return [g for g in self._games.values() if g.active]

    def load_from_dir(self, games_dir: str) -> int:
        """Load every *.json game config in a directory (Lean: plain JSON)."""
        p = Path(games_dir)
        if not p.is_dir():
            return 0
        n = 0
        for f in sorted(p.glob("*.json")):
            try:
                cfg = GameConfig.from_dict(
                    json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
            self.register(cfg)
            n += 1
        return n


class MultiGameReport:
    """Aggregate report across the fleet."""

    def __init__(self):
        self.per_game: Dict[str, AgentReport] = {}
        self.cycles = 0
        self.opportunities = 0
        self.experiments = 0
        self.executions = 0
        self.executed_actually = 0
        self.rollbacks = 0
        self.blocks = 0
        self.observes = 0

    def add_report(self, slug: str, rep: AgentReport) -> None:
        self.per_game[slug] = rep
        self.cycles += rep.cycles
        self.opportunities += rep.opportunities
        self.experiments += rep.experiments
        self.executions += rep.executions
        self.executed_actually += rep.executed_actually
        self.rollbacks += rep.rollbacks
        self.blocks += rep.blocks
        self.observes += rep.observes

    def to_dict(self) -> dict:
        return {
            "games": sorted(self.per_game.keys()),
            "cycles": self.cycles,
            "opportunities": self.opportunities,
            "experiments": self.experiments,
            "executions": self.executions,
            "executed_actually": self.executed_actually,
            "rollbacks": self.rollbacks,
            "blocks": self.blocks,
            "observes": self.observes,
            "per_game": {s: r.to_dict() for s, r in self.per_game.items()},
        }


class GameFactoryOS:
    """Operating-system layer: one isolated agent per game, run as a fleet."""

    def __init__(self, registry: GameRegistry, base_store_dir: str,
                 seed_memory_fn: Optional[Callable[[], list]] = None):
        self.registry = registry
        self.base_store_dir = Path(base_store_dir)
        self.seed_memory_fn = seed_memory_fn
        self.agents: Dict[str, MonetizationAgent] = {}
        for g in registry.active_games():
            self.agents[g.slug] = build_game_agent(
                g, str(self.base_store_dir), seed_memory_fn)

    def run_simulation(
        self, per_game_schedule: Dict[str, List[List["Opportunity"]]]
    ) -> MultiGameReport:
        report = MultiGameReport()
        for slug, sched in per_game_schedule.items():
            if slug not in self.agents:
                continue
            report.add_report(slug, self.agents[slug].run_simulation(sched))
        return report

    def isolation_manifest(self) -> dict:
        """Snapshot proving per-game memory separation (paths + id sets)."""
        out = {}
        for slug, agent in self.agents.items():
            recs = agent.store.all()
            out[slug] = {
                "store_path": str(agent.store.path),
                "record_count": len(recs),
                "decision_ids": sorted(r.decision_id for r in recs),
                "strategies": sorted(set(r.strategy_type for r in recs)),
            }
        return out
