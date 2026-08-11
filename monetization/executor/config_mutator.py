"""
E13.3.3 — Module 3: Config Mutator  (like E12 Mutation Engine, but dry)
========================================================================

Turns a StrategyDecision's `mutation` (the E12 gene payload) into a list of
concrete, provider-tagged `Change` records. This is the *plan* of what would be
mutated. It performs NO side effects and calls NO platform API — it only
produces reversible before/after records that a Provider later applies.

Mapping is driven by `mutation_type` + `gene` (the canonical E12 gene), which
is exactly what the Strategy Engine produced in E13.3.2:

    mutation_type | gene                      | Change(s)
    ---------------+--------------------------+-------------------------------
    bid_floor_gene | {bid_floor_delta: ±0.20} | MAX bid floor old->new
    waterfall_gene | {priority_shift: 1|2}    | MAX waterfall priority reorder
    frequency_gene | {reward_interval_delta}  | RemoteConfig reward_frequency
    network_gene   | {enable_backup: True}    | MAX enable backup network
    none           | {}                       | (no changes — no_action)

Provider attribution:
    * bid_floor / waterfall / backup_network -> MAX (or LevelPlay if the
      segment network is ironSource; see `_provider_for_network`)
    * reward_frequency / frequency            -> RemoteConfig

The `target` string encodes the segment so a human can audit exactly what scope
the change touches (e.g. "US_android_reward_applovin_floor").
"""
from __future__ import annotations

from typing import Any, Dict, List

from monetization.executor.models import (
    PROVIDER_LEVELPLAY, PROVIDER_MAX, PROVIDER_REMOTE_CONFIG, Change,
)

# Sensible defaults used when the live config value is not yet known (mock v1).
DEFAULT_FLOOR = 30.0          # hypothetical current bid floor (USD cents-equivalent)
DEFAULT_REWARD_FREQ = 5       # rewarded-ad interval (RemoteConfig units)
DEFAULT_WATERFALL = ["applovin", "admob", "mintegral", "unityads"]

# Networks mediated by LevelPlay (ironSource) rather than AppLovin MAX directly.
LEVELPLAY_NETWORKS = {"ironsource", "levelplay", "supersonic"}


def _seg_target(segment: dict) -> str:
    """Build a stable, auditable target prefix from the segment."""
    parts = [str(segment[k]) for k in ("country", "platform", "ad_format", "network")
             if segment.get(k)]
    return "_".join(parts) if parts else "global"


def _provider_for_network(network: str) -> str:
    if network and network.lower() in LEVELPLAY_NETWORKS:
        return PROVIDER_LEVELPLAY
    return PROVIDER_MAX


class ConfigMutator:
    """Translates a strategy mutation into reversible Change records."""

    def generate_changes(self, strategy_type: str, mutation: dict,
                         target_segment: dict) -> List[Change]:
        mut = mutation or {}
        mut_type = mut.get("mutation_type")
        gene = mut.get("gene", {}) or {}
        params = mut.get("params", {}) or {}
        seg = target_segment or {}
        base = _seg_target(seg)
        provider = _provider_for_network(seg.get("network", ""))
        changes: List[Change] = []

        if mut_type == "bid_floor_gene":
            delta = float(gene.get("bid_floor_delta", 0.20))
            old_floor = float(params.get("old_floor", DEFAULT_FLOOR))
            new_floor = round(old_floor * (1.0 + delta), 2)
            changes.append(Change(
                target=f"{base}_floor", provider=provider,
                change_type="bid_floor", old=old_floor, new=new_floor,
                note=f"Bid floor {delta:+.0%} per {strategy_type}",
            ))
            # Realistic dual-write: the client reads the effective floor from
            # RemoteConfig to gate ad-show logic, so we mirror it there too.
            changes.append(Change(
                target=f"{base}_floor_rc_mirror", provider=PROVIDER_REMOTE_CONFIG,
                change_type="bid_floor", old=old_floor, new=new_floor,
                note="RemoteConfig mirror of the new floor (client-side gate)",
            ))

        elif mut_type == "waterfall_gene":
            shift = int(gene.get("priority_shift", 1))
            new_order = list(DEFAULT_WATERFALL)
            if new_order:
                # promote the top network by `shift` positions (mock reorder)
                promoted = new_order[0]
                new_order = new_order[1:1 + (shift - 1)] + [promoted] + new_order[1 + (shift - 1):]
            changes.append(Change(
                target=f"{base}_waterfall_priority", provider=provider,
                change_type="waterfall_priority",
                old=list(DEFAULT_WATERFALL), new=new_order,
                note=f"Promote top network by {shift} position(s)",
            ))

        elif mut_type == "frequency_gene":
            delta = int(gene.get("reward_interval_delta",
                                 gene.get("reward_cooldown_delta", 1)) or 1)
            old_freq = int(params.get("old_frequency", DEFAULT_REWARD_FREQ))
            new_freq = old_freq + delta   # larger interval == lower frequency
            changes.append(Change(
                target="reward_frequency", provider=PROVIDER_REMOTE_CONFIG,
                change_type="reward_frequency", old=old_freq, new=new_freq,
                note=f"Reward interval {old_freq}->{new_freq} (frequency down)",
            ))

        elif mut_type == "network_gene":
            enable = bool(gene.get("enable_backup", True))
            if enable:
                backup = ["mintegral"]
                changes.append(Change(
                    target=f"{base}_backup_networks", provider=provider,
                    change_type="backup_network", old=[], new=backup,
                    note="Enable backup network to recover fill",
                ))

        elif mut_type == "none":
            # no_action: deliberately produce no changes
            pass

        return changes
