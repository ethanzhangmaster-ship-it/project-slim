"""
E15.2.5 — ActionValidator.

Turns a flat, priority-ordered action list into a *decision*: is each
action worth executing, and through which path (auto / experiment /
observe)? Deterministic — no LLM.

Execution value = confidence x impact x safety x reversibility, each 0-1.

Per-action-type profile (grounded in MAX operational reality):
  disable_network        impact hi, safety hi (near-zero rev at stake),
                         reversible -> SAFE
  quarantine_network     protected zombie -> watch only -> OBSERVE
  increase_bid_opportunity  impact hi, safety med (shifts exposure),
                         reversible -> EXPERIMENT
  adjust_bid_constraint  impact med, safety med (floors can cut fill) -> EXPERIMENT
  diversify              portfolio/demand, not a single API write -> OBSERVE
  monitor / handoff_ua   advisory / out-of-scope -> OBSERVE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from operation.optimizer.intel_models import ActionItem


class Layer(str, Enum):
    SAFE = "safe"             # 🔥 execute today (auto-exec candidate)
    EXPERIMENT = "experiment"  # 🧪 A/B first
    OBSERVE = "observe"        # 👀 monitor / out of scope


# impact, safety, reversibility, executable(is it a concrete MAX write?)
_PROFILE: Dict[str, Dict[str, Any]] = {
    "disable_network":        {"impact": 0.9, "safety": 0.9, "reversibility": 1.0, "executable": True},
    "quarantine_network":     {"impact": 0.4, "safety": 1.0, "reversibility": 1.0, "executable": False},
    "increase_bid_opportunity": {"impact": 0.8, "safety": 0.7, "reversibility": 0.9, "executable": True},
    "adjust_bid_constraint":  {"impact": 0.6, "safety": 0.6, "reversibility": 0.9, "executable": True},
    "diversify":              {"impact": 0.5, "safety": 1.0, "reversibility": 0.5, "executable": False},
    "monitor":                {"impact": 0.2, "safety": 1.0, "reversibility": 1.0, "executable": False},
    "handoff_ua":             {"impact": 0.3, "safety": 1.0, "reversibility": 1.0, "executable": False},
}
_DEFAULT_PROFILE = {"impact": 0.3, "safety": 0.8, "reversibility": 0.8, "executable": False}


@dataclass
class ValidatedAction:
    action: ActionItem
    layer: Layer
    value_score: float                       # 0-1 execution value
    factors: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.action.to_dict(),
            "layer": self.layer.value,
            "value_score": round(self.value_score, 3),
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "rationale": self.rationale,
        }


class ActionValidator:
    # thresholds to qualify as an auto-execute-safe action
    SAFE_MIN_CONF = 0.90
    SAFE_MIN_SAFETY = 0.85
    SAFE_MIN_REVERS = 0.85

    def classify(self, actions: List[ActionItem]) -> List[ValidatedAction]:
        out: List[ValidatedAction] = []
        for a in actions:
            p = _PROFILE.get(a.action, _DEFAULT_PROFILE)
            conf = float(a.confidence)
            impact, safety, revers = p["impact"], p["safety"], p["reversibility"]
            value = conf * impact * safety * revers
            layer, why = self._layer(a, p, conf)
            out.append(ValidatedAction(
                action=a, layer=layer, value_score=value,
                factors={"confidence": conf, "impact": impact,
                         "safety": safety, "reversibility": revers},
                rationale=why))
        out.sort(key=lambda v: (self._layer_order(v.layer), -v.value_score))
        return out

    def _layer(self, a: ActionItem, p: Dict[str, Any], conf: float) -> tuple:
        if not p["executable"]:
            return Layer.OBSERVE, "advisory / out-of-scope — watch only, never an automated write"
        if (conf >= self.SAFE_MIN_CONF and p["safety"] >= self.SAFE_MIN_SAFETY
                and p["reversibility"] >= self.SAFE_MIN_REVERS):
            return (Layer.SAFE,
                    "high-confidence, reversible, minimal downside — auto-execute candidate (Phase 3)")
        return (Layer.EXPERIMENT,
                "real revenue/fill impact — validate with a controlled A/B before rollout")

    @staticmethod
    def _layer_order(layer: Layer) -> int:
        return {Layer.SAFE: 0, Layer.EXPERIMENT: 1, Layer.OBSERVE: 2}[layer]

    @staticmethod
    def group(validated: List[ValidatedAction]) -> Dict[str, List[ValidatedAction]]:
        groups: Dict[str, List[ValidatedAction]] = {
            Layer.SAFE.value: [], Layer.EXPERIMENT.value: [], Layer.OBSERVE.value: []}
        for v in validated:
            groups[v.layer.value].append(v)
        return groups
