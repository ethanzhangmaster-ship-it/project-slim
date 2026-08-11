"""
E13.3.2 — Module 2: Strategy Rule Engine
========================================

First version is rule-based, NOT a model. Given an Opportunity type, emit a
fixed set of candidate StrategyTemplates. No autonomy, no learning.

Rule table (matches the PRD test requirements exactly):

  ecpm_drop          -> waterfall_change, bid_floor_adjust, network_test
  fill_drop          -> backup_network, floor_down, waterfall_change
  ad_frequency_issue -> frequency_down, reward_cooldown, no_action
  revenue_drop*      -> monetization_aggressive   (* retention stable)

Each template carries enough to (a) run the E13.2.9 Simulator and (b) hand
off to an E12 Mutation Operation later:

  mutation = {
    action_type : E13.2.9 simulator action (change_waterfall|review_bidding|adjust_ad_frequency)
    params      : E13.2.9 simulator params
    description : human-readable intent
    mutation_type : E12 future gene type
    gene        : E12 future gene payload (what the Executor would mutate)
  }

E12 connection point (per PRD):
  Monetization Strategy -> Mutation Operation -> Executor
"""
from __future__ import annotations

from typing import Dict, List

# Default lever magnitudes (mirror E13.2.9 DEFAULT_PCT so simulations are sane)
_WF_PCT = 20      # waterfall rebalance magnitude
_BF_PCT = 20      # bid floor change magnitude
_FILL_PCT = 15    # fill-recovery / backup-network magnitude
_FREQ_PCT = 10    # ad-frequency change magnitude


def _t(strategy_type: str, action_type: str, params: dict,
       description: str, mutation_type: str, gene: dict) -> dict:
    return {
        "strategy_type": strategy_type,
        "mutation": {
            "action_type": action_type,
            "params": params,
            "description": description,
            "mutation_type": mutation_type,
            "gene": gene,
        },
    }


# --------------------------------------------------------------------------- #
# Rule table
# --------------------------------------------------------------------------- #
RULES: Dict[str, List[dict]] = {
    # ---- Rule 1: eCPM dropped -------------------------------------------- #
    "ecpm_drop": [
        _t("waterfall_change", "change_waterfall", {"magnitude_pct": _WF_PCT},
           "Promote a healthy network above the underperforming one in the "
           "waterfall for this segment to lift eCPM.",
           "waterfall_gene",
           {"priority_shift": 1}),
        _t("bid_floor_adjust", "review_bidding",
           {"increase_bid_floor": True, "bid_floor_pct": _BF_PCT},
           "Raise bid floor +{0}% to lift eCPM (accepts some fill loss).".format(_BF_PCT),
           "bid_floor_gene",
           {"bid_floor_delta": 0.20}),
        _t("network_test", "review_bidding",
           {"increase_bid_floor": False, "magnitude_pct": _FILL_PCT},
           "Enable / A-B test a backup network to stabilise fill and eCPM.",
           "network_gene",
           {"enable_backup": True}),
    ],

    # ---- Rule 2: fill rate dropped --------------------------------------- #
    "fill_drop": [
        _t("backup_network", "review_bidding",
           {"increase_bid_floor": False, "magnitude_pct": _FILL_PCT},
           "Enable backup networks / fix mediation timeout to recover fill.",
           "network_gene",
           {"enable_backup": True}),
        _t("floor_down", "review_bidding",
           {"increase_bid_floor": False, "bid_floor_pct": _BF_PCT},
           "Lower bid floor to widen fill for this segment.",
           "bid_floor_gene",
           {"bid_floor_delta": -0.15}),
        _t("waterfall_change", "change_waterfall", {"magnitude_pct": _WF_PCT},
           "Re-prioritise the waterfall to a higher-fill network.",
           "waterfall_gene",
           {"priority_shift": 1}),
    ],

    # ---- Rule 3: ad frequency hurting retention -------------------------- #
    "ad_frequency_issue": [
        _t("frequency_down", "adjust_ad_frequency",
           {"direction": "down", "magnitude_pct": _FREQ_PCT},
           "Reduce ad frequency (e.g. raise RemoteConfig reward interval) to "
           "recover retention.",
           "frequency_gene",
           {"reward_interval_delta": +1}),
        _t("reward_cooldown", "adjust_ad_frequency",
           {"direction": "down", "magnitude_pct": _FREQ_PCT},
           "Increase rewarded-ad cooldown to protect D1 retention.",
           "frequency_gene",
           {"reward_cooldown_delta": +1}),
        _t("no_action", "", {},
           "Accept current ad load; monitor retention for one more window "
           "before changing anything.",
           "none",
           {}),
    ],

    # ---- Rule 4: revenue dropped but retention stable -------------------- #
    # (revenue_drop with retention NOT degraded -> push monetisation harder)
    "revenue_drop": [
        _t("monetization_aggressive", "change_waterfall",
           {"magnitude_pct": _WF_PCT + 5},
           "Retention is stable, so re-prioritise the waterfall more "
           "aggressively to recover revenue.",
           "waterfall_gene",
           {"priority_shift": 2}),
    ],
}


# --------------------------------------------------------------------------- #
# Rule metadata: expected impact prior (pre-simulation), used to seed the
# candidate's `expected_impact` and `confidence`.
# --------------------------------------------------------------------------- #
EXPECTED_IMPACT: Dict[str, dict] = {
    "waterfall_change":    {"intent": "rebalance_waterfall", "expected_effect": "ecpm_up_fill_down"},
    "bid_floor_adjust":    {"intent": "raise_bid_floor", "expected_effect": "ecpm_up_fill_down"},
    "network_test":        {"intent": "test_backup_network", "expected_effect": "fill_up_ecpm_stable"},
    "backup_network":      {"intent": "enable_backup_network", "expected_effect": "fill_up"},
    "floor_down":          {"intent": "lower_bid_floor", "expected_effect": "fill_up_ecpm_down"},
    "frequency_down":      {"intent": "reduce_ad_frequency", "expected_effect": "retention_up_revenue_down"},
    "reward_cooldown":     {"intent": "increase_reward_cooldown", "expected_effect": "retention_up_revenue_down"},
    "monetization_aggressive": {"intent": "aggressive_monetization", "expected_effect": "revenue_up"},
    "no_action":           {"intent": "no_change", "expected_effect": "none"},
}

# Rule prior confidence (how well we understand the mechanics).
RULE_CONFIDENCE: Dict[str, float] = {
    "waterfall_change": 0.75,
    "bid_floor_adjust": 0.82,
    "network_test": 0.70,
    "backup_network": 0.70,
    "floor_down": 0.78,
    "frequency_down": 0.62,
    "reward_cooldown": 0.62,
    "monetization_aggressive": 0.68,
    "no_action": 0.90,   # certain that doing nothing has no mechanical effect
}


def candidate_specs(opportunity_type: str) -> List[dict]:
    """Return the rule templates for an opportunity type (may be empty)."""
    return list(RULES.get(opportunity_type, []))


def has_rule(opportunity_type: str) -> bool:
    return opportunity_type in RULES
