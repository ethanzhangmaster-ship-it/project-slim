"""
E15.1.2 — Portfolio Manager
============================

Manages the 10–50 game matrix as a portfolio with a lifecycle:

    IDEA -> PROTOTYPE -> SOFT_LAUNCH -> UA_TEST -> SCALE
                     (KILL reachable from anywhere)

Lifecycle state lives in its OWN store (data/portfolio_state.json) so the
frozen E15.1.1 GameProduct contract is untouched.

Daily judgement table (user-defined, deterministic):

    ROAS > 1.00        -> increase_budget
    ROAS 0.50 - 1.00   -> keep_optimizing
    ROAS < 0.30        -> stop_ua (UA_TEST) / kill candidate (SCALE)
    ad-revenue heavy   -> boost_iaa
    iap heavy          -> boost_iap

Every decision has requires_manual_apply=True. The brain NEVER spends
money, never kills a game, never touches a store.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct

from .models import (
    STAGE_ORDER, LifecycleStage, PortfolioAction, PortfolioDecision,
)

DEFAULT_STATE = "data/portfolio_state.json"

# decision thresholds (documented constants)
_ROAS_SCALE = 1.00
_ROAS_OK = 0.50
_ROAS_STOP = 0.30
_IAA_HEAVY = 0.75        # ad share of revenue >= 75% -> IAA-driven product
_IAP_HEAVY = 0.50        # iap share >= 50% -> IAP-driven product


class PortfolioManager:
    """Lifecycle state machine + daily decision engine."""

    def __init__(self, registry: GameRegistry,
                 state_path: str = DEFAULT_STATE):
        self.registry = registry
        self.state_path = state_path
        self._stages: Dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # state persistence
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as fh:
                    self._stages = dict(json.load(fh))
            except (json.JSONDecodeError, OSError):
                self._stages = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.state_path)),
                    exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(self._stages, fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def stage_of(self, game_id: str) -> str:
        """Stage from state file; sensible default from GameProduct.status."""
        if game_id in self._stages:
            return self._stages[game_id]
        g = self.registry.get(game_id)
        if g is None:
            return LifecycleStage.IDEA.value
        default = {
            "development": LifecycleStage.PROTOTYPE.value,
            "ready": LifecycleStage.PROTOTYPE.value,
            "submitted": LifecycleStage.SOFT_LAUNCH.value,
            "published": LifecycleStage.SOFT_LAUNCH.value,
            "rejected": LifecycleStage.PROTOTYPE.value,
            "archived": LifecycleStage.KILL.value,
        }.get(g.status, LifecycleStage.IDEA.value)
        return default

    def set_stage(self, game_id: str, stage: str) -> None:
        valid = {s.value for s in LifecycleStage}
        if stage not in valid:
            raise ValueError(f"invalid stage: {stage}")
        self._stages[game_id] = stage
        self._save()

    def advance(self, game_id: str) -> str:
        """Move to the next stage in order (no-op at SCALE / KILL)."""
        cur = self.stage_of(game_id)
        if cur == LifecycleStage.KILL.value:
            return cur
        try:
            idx = STAGE_ORDER.index(cur)
        except ValueError:
            return cur
        nxt = STAGE_ORDER[min(idx + 1, len(STAGE_ORDER) - 1)]
        self.set_stage(game_id, nxt)
        return nxt

    def kill(self, game_id: str) -> str:
        self.set_stage(game_id, LifecycleStage.KILL.value)
        return LifecycleStage.KILL.value

    # ------------------------------------------------------------------ #
    # daily decisions
    # ------------------------------------------------------------------ #
    def _decide_one(self, g: GameProduct) -> Optional[PortfolioDecision]:
        stage = self.stage_of(g.game_id)
        if stage == LifecycleStage.KILL.value:
            return None                       # dead games get no decisions

        m = g.metrics or {}
        roas = m.get("roas")
        ad_share = float(m.get("ad_revenue_share", 0.0))
        iap_share = float(m.get("iap_revenue_share", 0.0))
        snap = {k: float(v) for k, v in m.items()
                if isinstance(v, (int, float))}

        def mk(action: PortfolioAction, reason: str) -> PortfolioDecision:
            return PortfolioDecision(
                game_id=g.game_id, stage=stage, action=action.value,
                reason=reason, metric_snapshot=snap)

        # 1) ROAS ladder (only meaningful once UA is running)
        if roas is not None and stage in (LifecycleStage.UA_TEST.value,
                                          LifecycleStage.SCALE.value):
            roas = float(roas)
            if roas > _ROAS_SCALE:
                return mk(PortfolioAction.INCREASE_BUDGET,
                          f"ROAS {roas:.2f} > {_ROAS_SCALE:.2f}: scale up")
            if roas >= _ROAS_OK:
                return mk(PortfolioAction.KEEP_OPTIMIZING,
                          f"ROAS {roas:.2f} in [{_ROAS_OK:.2f}, "
                          f"{_ROAS_SCALE:.2f}]: keep optimizing")
            if roas < _ROAS_STOP:
                if stage == LifecycleStage.SCALE.value:
                    return mk(PortfolioAction.KILL,
                              f"ROAS {roas:.2f} < {_ROAS_STOP:.2f} at "
                              f"scale: kill candidate")
                return mk(PortfolioAction.STOP_UA,
                          f"ROAS {roas:.2f} < {_ROAS_STOP:.2f}: stop UA")
            return mk(PortfolioAction.KEEP_OPTIMIZING,
                      f"ROAS {roas:.2f} in grey zone "
                      f"[{_ROAS_STOP:.2f}, {_ROAS_OK:.2f}): watch closely")

        # 2) revenue-mix leans (published games without UA signal)
        if g.is_published():
            if ad_share >= _IAA_HEAVY:
                return mk(PortfolioAction.BOOST_IAA,
                          f"ad revenue share {ad_share:.0%}: IAA-driven, "
                          f"push rewarded placements")
            if iap_share >= _IAP_HEAVY:
                return mk(PortfolioAction.BOOST_IAP,
                          f"IAP share {iap_share:.0%}: strengthen bundles "
                          f"/ starter packs")

        # 3) pipeline progression: pre-launch games advance when ready
        if stage in (LifecycleStage.IDEA.value,
                     LifecycleStage.PROTOTYPE.value):
            if g.status in ("ready", "published", "submitted"):
                return mk(PortfolioAction.ADVANCE,
                          f"status={g.status}: ready for next stage")

        return mk(PortfolioAction.HOLD, "no strong signal today")

    def daily_decisions(self) -> List[PortfolioDecision]:
        out: List[PortfolioDecision] = []
        for g in self.registry.list_all():
            d = self._decide_one(g)
            if d is not None:
                out.append(d)
        return out

    # ------------------------------------------------------------------ #
    def portfolio_summary(self) -> dict:
        by_stage: Dict[str, int] = {}
        for g in self.registry.list_all():
            s = self.stage_of(g.game_id)
            by_stage[s] = by_stage.get(s, 0) + 1
        return {"total": self.registry.count(), "by_stage": by_stage}


__all__ = ["PortfolioManager", "DEFAULT_STATE"]
