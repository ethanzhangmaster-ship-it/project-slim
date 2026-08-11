"""
E16.6.4 — ASO Experiment Memory: data models & revenue-linked scoring.

The long-term learning layer of the ASO Agent. It records which store changes
were actually tried (``ASOExperiment``), what happened (``ASOExperimentResult``),
and — crucially — *extracts reusable strategy knowledge* (``ASOPattern``) instead
of just archiving experiments.

This module is the contract layer (pure data, no I/O, no side effects):

* ``ASOExperiment``       — one store experiment (what was changed)
* ``ASOExperimentResult`` — before/after reality + **revenue-linked** uplift
* ``ASOPattern``          — "what strategy works, under what condition"

Revenue linkage (the key difference vs a naive CVR logger):
    revenue_uplift ≈ (cvr_after / cvr_before) × (ltv_after / ltv_before) − 1
    is_revenue_success ⇔ revenue_uplift > 0 AND ltv did not drop
  → a change that lifts CVR but *harms LTV* is NOT a success and gets
    down-weighted when patterns are mined / scored. Final goal is revenue,
    not downloads.

E16.6.4 depends ONE-WAY on:
  - ``src.aso_intelligence.models`` (``ASOAction``) and
    ``src.revenue_intelligence.models`` (``GrowthAction``) — for emitting
    validated patterns back into the shared Growth Decision Layer (E16.1 /
    E13.3) via the retriever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 1. Experiment action type
# --------------------------------------------------------------------------- #
class ASOExperimentAction(str, Enum):
    """The kind of store change an ASO experiment tests."""

    UPDATE_ICON = "UPDATE_ICON"
    UPDATE_SCREENSHOT = "UPDATE_SCREENSHOT"
    UPDATE_TITLE = "UPDATE_TITLE"
    ADD_KEYWORD = "ADD_KEYWORD"


class ASOExperimentStatus(str, Enum):
    """Lifecycle state of an experiment."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --------------------------------------------------------------------------- #
# 2. One experiment (what was changed)
# --------------------------------------------------------------------------- #
@dataclass
class ASOExperiment:
    """Records one store experiment for a game.

    ``category`` scopes the pattern (e.g. "merge_game"); ``condition`` is the
    triggering situation/insight that motivated the change (e.g.
    "SCREENSHOT_WEAK"); ``action_type`` is the move that was applied.
    """

    experiment_id: str
    game_id: str
    platform: str
    category: str
    condition: str
    action_type: ASOExperimentAction
    before_asset: str
    after_asset: str
    start_date: str  # ISO date or datetime string
    end_date: Optional[str] = None
    status: ASOExperimentStatus = ASOExperimentStatus.RUNNING
    created_at: str = field(default_factory=lambda: _now().isoformat())

    def is_completed(self) -> bool:
        return self.status == ASOExperimentStatus.COMPLETED

    def is_failed(self) -> bool:
        return self.status == ASOExperimentStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "game_id": self.game_id,
            "platform": self.platform,
            "category": self.category,
            "condition": self.condition,
            "action_type": self.action_type.value,
            "before_asset": self.before_asset,
            "after_asset": self.after_asset,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOExperiment":
        try:
            at = ASOExperimentAction(d.get("action_type", "UPDATE_SCREENSHOT"))
        except ValueError:
            at = ASOExperimentAction.UPDATE_SCREENSHOT
        try:
            st = ASOExperimentStatus(d.get("status", "RUNNING"))
        except ValueError:
            st = ASOExperimentStatus.RUNNING
        return cls(
            experiment_id=d.get("experiment_id", ""),
            game_id=d.get("game_id", ""),
            platform=d.get("platform", ""),
            category=d.get("category", "unknown"),
            condition=d.get("condition", ""),
            action_type=at,
            before_asset=d.get("before_asset", ""),
            after_asset=d.get("after_asset", ""),
            start_date=d.get("start_date", ""),
            end_date=d.get("end_date"),
            status=st,
            created_at=d.get("created_at") or _now().isoformat(),
        )


# --------------------------------------------------------------------------- #
# 3. Experiment result (what happened) — revenue-linked
# --------------------------------------------------------------------------- #
@dataclass
class ASOExperimentResult:
    """Before/after reality of one experiment, with **revenue** uplift.

    The ``before`` / ``after`` dicts carry:
      * ``store_cvr``   — store listing conversion rate (visitor → install)
      * ``installs``    — absolute installs in the window
      * ``ranking``     — store category rank (lower = better)
      * ``ltv``         — per-acquired-user revenue (e.g. D30 LTV); 0 = unknown

    ``revenue_uplift`` combines conversion and monetization, so a CVR win that
    hurts LTV is correctly penalised (see ``is_revenue_success``).
    """

    experiment_id: str
    before: Dict[str, float] = field(default_factory=dict)
    after: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: _now().isoformat())

    # --- raw getters ------------------------------------------------------- #
    @property
    def before_cvr(self) -> float:
        return float((self.before or {}).get("store_cvr", 0.0))

    @property
    def after_cvr(self) -> float:
        return float((self.after or {}).get("store_cvr", 0.0))

    @property
    def before_installs(self) -> float:
        return float((self.before or {}).get("installs", 0.0))

    @property
    def after_installs(self) -> float:
        return float((self.after or {}).get("installs", 0.0))

    @property
    def before_ltv(self) -> float:
        return float((self.before or {}).get("ltv", 0.0))

    @property
    def after_ltv(self) -> float:
        return float((self.after or {}).get("ltv", 0.0))

    @property
    def before_ranking(self) -> float:
        return float((self.before or {}).get("ranking", 0.0))

    @property
    def after_ranking(self) -> float:
        return float((self.after or {}).get("ranking", 0.0))

    # --- derived changes (relative) --------------------------------------- #
    def cvr_change(self) -> float:
        b = self.before_cvr
        return (self.after_cvr - b) / b if b > 0 else 0.0

    def install_change(self) -> float:
        b = self.before_installs
        return (self.after_installs - b) / b if b > 0 else 0.0

    def ltv_change(self) -> float:
        b = self.before_ltv
        return (self.after_ltv - b) / b if b > 0 else 0.0

    def revenue_uplift(self) -> float:
        """Relative revenue per acquisition: (cvr ratio) × (ltv ratio) − 1.

        If LTV is unknown (before_ltv == 0) it is treated as neutral (×1),
        so the uplift reduces to the CVR ratio — never crashes.
        """
        cvr_ratio = (
            self.after_cvr / self.before_cvr if self.before_cvr > 0 else 1.0
        )
        ltv_ratio = (
            self.after_ltv / self.before_ltv if self.before_ltv > 0 else 1.0
        )
        return round(cvr_ratio * ltv_ratio - 1.0, 6)

    def is_revenue_success(self, allow_ltv_drop: float = 0.0) -> bool:
        """True only if revenue went up AND LTV did not drop beyond tolerance.

        ``allow_ltv_drop`` is a tolerance (e.g. 0.05 = LTV may fall ≤5%).
        Default 0.0 ⇒ LTV must not decrease at all for an experiment to count
        as a genuine success. A CVR+ / LTV− change therefore fails here and
        is down-weighted when patterns are mined / scored.
        """
        if self.revenue_uplift() <= 0:
            return False
        return self.ltv_change() >= -abs(allow_ltv_drop)

    def uplift(self) -> Dict[str, float]:
        """Convenience view of all relative changes."""
        return {
            "cvr_change": round(self.cvr_change(), 6),
            "install_change": round(self.install_change(), 6),
            "ltv_change": round(self.ltv_change(), 6),
            "revenue_uplift": self.revenue_uplift(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "before": {k: round(float(v), 6) for k, v in (self.before or {}).items()},
            "after": {k: round(float(v), 6) for k, v in (self.after or {}).items()},
            "confidence": round(self.confidence, 4),
            "uplift": self.uplift(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOExperimentResult":
        return cls(
            experiment_id=d.get("experiment_id", ""),
            before=d.get("before") or {},
            after=d.get("after") or {},
            confidence=float(d.get("confidence", 0.0)),
            created_at=d.get("created_at") or _now().isoformat(),
        )


# --------------------------------------------------------------------------- #
# 4. ASO Pattern (extracted strategy knowledge)
# --------------------------------------------------------------------------- #
@dataclass
class ASOPattern:
    """A reusable ASO strategy learned from experiments.

    Not "experiment #42 worked" but "in ``category`` games, when ``condition``
    holds, applying ``action`` yields ``reward`` revenue uplift on average,
    validated by ``sample_size`` experiments at ``success_rate`` confidence."

    ``pattern_id`` is deterministic: ``"<category>:<condition>:<action>"``.
    """

    category: str
    condition: str
    action: str  # ASOExperimentAction value
    result: str  # human-readable summary, e.g. "+18% revenue"
    confidence: float
    sample_size: int
    success_rate: float = 0.0
    reward: float = 0.0  # mean revenue uplift across the group
    pattern_id: str = ""
    created_at: str = field(default_factory=lambda: _now().isoformat())

    def computed_id(self) -> str:
        return self.pattern_id or f"{self.category}:{self.condition}:{self.action}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "condition": self.condition,
            "action": self.action,
            "result": self.result,
            "confidence": round(self.confidence, 4),
            "sample_size": self.sample_size,
            "success_rate": round(self.success_rate, 4),
            "reward": round(self.reward, 6),
            "pattern_id": self.computed_id(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOPattern":
        return cls(
            category=d.get("category", ""),
            condition=d.get("condition", ""),
            action=d.get("action", ""),
            result=d.get("result", ""),
            confidence=float(d.get("confidence", 0.0)),
            sample_size=int(d.get("sample_size", 0)),
            success_rate=float(d.get("success_rate", 0.0)),
            reward=float(d.get("reward", 0.0)),
            pattern_id=d.get("pattern_id") or "",
            created_at=d.get("created_at") or _now().isoformat(),
        )


__all__ = [
    "ASOExperimentAction",
    "ASOExperimentStatus",
    "ASOExperiment",
    "ASOExperimentResult",
    "ASOPattern",
]
