"""E9.4: Player Event Collector + Player DNA Engine.

PlayerEventCollector: loads events from CSV/API, generates sample data for testing.
PlayerDNAEngine: extracts PlayerDNA from raw events per player.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from market_ops.player_intelligence.models import (
    PlayerEvent, PlayerDNA,
    ProgressionDNA, CollectionDNA, PaymentDNA, RetentionDNA,
)


# ═══════════════════════════════════════════════════════════
# Merge Game Event Templates (for sample generation)
# ═══════════════════════════════════════════════════════════

_MERGE_EVENT_TEMPLATES = {
    # Progression events
    "level_start": {"level": lambda: random.randint(1, 50)},
    "level_complete": {"level": lambda: random.randint(1, 50), "stars": lambda: random.randint(1, 3)},
    "merge_create": {"item": lambda: random.choice(["dragon_egg", "plant_seed", "magic_gem", "mystery_box"]), "level": lambda: random.randint(1, 5)},
    "merge_upgrade": {"item": lambda: random.choice(["dragon", "flower", "crystal", "artifact"]), "from_level": lambda: random.randint(1, 4), "to_level": lambda: random.randint(2, 5)},
    "area_unlock": {"area": lambda: random.choice(["dark_forest", "crystal_cave", "dragon_peak", "enchanted_garden", "witch_tower"])},
    "building_restore": {"building": lambda: random.choice(["castle", "bridge", "fountain", "library", "greenhouse"])},

    # Collection events
    "item_collect": {"item": lambda: random.choice(["dragon_scale", "magic_herb", "star_dust", "moon_pearl"]), "rarity": lambda: random.choice(["common", "uncommon", "rare"])},
    "rare_item_get": {"item": lambda: random.choice(["golden_dragon", "phoenix_feather", "diamond_crystal", "ancient_scroll"]), "rarity": "legendary"},
    "collection_complete": {"collection": lambda: random.choice(["dragon_set", "plant_collection", "gem_collection", "artifact_collection"])},

    # Monetization events
    "shop_open": {"section": lambda: random.choice(["daily_deals", "special_offer", "gem_shop", "energy_shop"])},
    "offer_view": {"offer_id": lambda: f"offer_{random.randint(1, 20)}", "price": lambda: round(random.uniform(0.99, 49.99), 2)},
    "purchase_start": {"offer_id": lambda: f"offer_{random.randint(1, 20)}", "price": lambda: round(random.uniform(0.99, 49.99), 2)},
    "purchase_success": {"offer_id": lambda: f"offer_{random.randint(1, 20)}", "price": lambda: round(random.uniform(0.99, 49.99), 2), "currency": "USD"},

    # Pressure events
    "energy_empty": {"current": 0, "max": lambda: random.randint(20, 100)},
    "blocked_progress": {"reason": lambda: random.choice(["need_item", "level_requirement", "area_locked"])},
    "missing_item": {"item": lambda: random.choice(["dragon_scale", "magic_herb", "star_dust"]), "needed": lambda: random.randint(1, 5)},
    "waiting_timer": {"duration_seconds": lambda: random.randint(300, 3600), "action": lambda: random.choice(["merge", "build", "explore"])},

    # Engagement events
    "session_start": {},
    "daily_login": {"streak": lambda: random.randint(1, 30)},
    "event_participate": {"event_name": lambda: random.choice(["dragon_festival", "harvest_moon", "starfall", "witch_trials"])},
}


# ═══════════════════════════════════════════════════════════
# Player Event Collector
# ═══════════════════════════════════════════════════════════

class PlayerEventCollector:
    """Loads player events from CSV/API and generates sample data for testing.

    CSV format (MVP):
      player_id, creative_id, event_name, event_time, event_value_json, source

    Usage:
        collector = PlayerEventCollector()
        events = collector.load_from_csv("player_events.csv")
        # or
        events = collector.generate_sample(num_players=500, creative_ids=[...])
    """

    def __init__(self) -> None:
        self._events: list[PlayerEvent] = []

    def load_from_csv(self, path: str | Path) -> list[PlayerEvent]:
        """Load events from CSV file."""
        self._events = []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = PlayerEvent(
                    player_id=row.get("player_id", ""),
                    creative_id=row.get("creative_id", ""),
                    event_name=row.get("event_name", ""),
                    event_time=datetime.fromisoformat(row.get("event_time", datetime.now().isoformat())),
                    event_value=json.loads(row.get("event_value", "{}")),
                    source=row.get("source", "csv"),
                )
                self._events.append(event)
        return self._events

    def generate_sample(
        self,
        num_players: int = 500,
        creative_ids: list[str] | None = None,
        days: int = 30,
        payer_rate: float = 0.08,
        seed: int = 42,
    ) -> list[PlayerEvent]:
        """Generate realistic Merge Witch player events for testing.

        Simulates:
          - Players with different engagement levels (casual, regular, hardcore)
          - Progression events (merge, level, area, build)
          - Collection events (item, rare, complete)
          - Monetization events (shop, offer, purchase)
          - Pressure events (energy, blocked, missing, timer)

        Args:
            num_players: total players to generate
            creative_ids: creative IDs to assign players to
            days: simulation period in days
            payer_rate: expected payer percentage
            seed: random seed for reproducibility
        """
        random.seed(seed)
        if creative_ids is None:
            creative_ids = [f"creative_{i:03d}" for i in range(1, 21)]

        self._events = []
        now = datetime.now()

        # Player archetypes with different behavior profiles
        archetypes = {
            "hardcore": {"weight": 0.10, "daily_sessions": (3, 8), "merge_per_day": (10, 30),
                         "payer_chance": 0.25, "retention_d30": 0.80,
                         "collect_chance": 0.04, "event_chance": 0.06,
                         "progression_chance": 0.25},
            "regular": {"weight": 0.25, "daily_sessions": (1, 3), "merge_per_day": (3, 10),
                        "payer_chance": 0.08, "retention_d30": 0.50,
                        "collect_chance": 0.05, "event_chance": 0.08,
                        "progression_chance": 0.15},
            "collector": {"weight": 0.10, "daily_sessions": (1, 2), "merge_per_day": (1, 2),
                          "payer_chance": 0.12, "retention_d30": 0.60,
                          "collect_chance": 0.50, "event_chance": 0.25,
                          "progression_chance": 0.03},
            "casual": {"weight": 0.40, "daily_sessions": (0, 1), "merge_per_day": (1, 3),
                       "payer_chance": 0.02, "retention_d30": 0.20,
                       "collect_chance": 0.02, "event_chance": 0.03},
            "churned": {"weight": 0.15, "daily_sessions": (0, 1), "merge_per_day": (0, 2),
                        "payer_chance": 0.01, "retention_d30": 0.05,
                        "collect_chance": 0.01, "event_chance": 0.01},
        }

        for i in range(num_players):
            player_id = f"player_{i:04d}"
            creative_id = random.choice(creative_ids)

            # Pick archetype
            arch_name = random.choices(
                list(archetypes.keys()),
                weights=[a["weight"] for a in archetypes.values()],
            )[0]
            arch = archetypes[arch_name]

            # Determine if payer
            is_payer = random.random() < arch["payer_chance"]

            # Generate events over the simulation period
            for day in range(days):
                # Check if player churned
                if day > 1 and random.random() > arch["retention_d30"]:
                    if random.random() > 0.3:  # 70% chance to stay churned
                        continue

                event_date = now - timedelta(days=days - day)
                num_sessions = random.randint(*arch["daily_sessions"])

                for _ in range(num_sessions):
                    # Session start
                    self._add_event(player_id, creative_id, "session_start", event_date, {})

                    # Merge actions
                    num_merges = random.randint(*arch["merge_per_day"])
                    for _ in range(num_merges):
                        if random.random() < 0.3:
                            self._add_event(player_id, creative_id, "merge_upgrade", event_date,
                                            {"item": random.choice(["dragon", "flower", "crystal", "artifact"]),
                                             "from_level": random.randint(1, 4),
                                             "to_level": random.randint(2, 5)})
                        else:
                            self._add_event(player_id, creative_id, "merge_create", event_date,
                                            {"item": random.choice(["dragon_egg", "plant_seed", "magic_gem", "mystery_box"]),
                                             "level": random.randint(1, 5)})

                    # Collection (frequency driven by archetype)
                    if random.random() < arch.get("collect_chance", 0.05):
                        if random.random() < 0.1:
                            self._add_event(player_id, creative_id, "rare_item_get", event_date,
                                            {"item": random.choice(["golden_dragon", "phoenix_feather"]),
                                             "rarity": "legendary"})
                        elif random.random() < 0.05:
                            self._add_event(player_id, creative_id, "collection_complete", event_date,
                                            {"collection": random.choice(["dragon_set", "plant_collection", "gem_collection", "artifact_collection"])})
                        else:
                            self._add_event(player_id, creative_id, "item_collect", event_date,
                                            {"item": random.choice(["dragon_scale", "magic_herb", "star_dust", "moon_pearl"]),
                                             "rarity": random.choice(["common", "uncommon", "rare"])})

                    # Progression (frequency driven by archetype)
                    prog_chance = arch.get("progression_chance", 0.15)
                    if random.random() < prog_chance:
                        self._add_event(player_id, creative_id, "area_unlock", event_date,
                                        {"area": random.choice(["dark_forest", "crystal_cave", "dragon_peak", "enchanted_garden", "witch_tower"])})
                    if random.random() < prog_chance * 0.6:
                        self._add_event(player_id, creative_id, "building_restore", event_date,
                                        {"building": random.choice(["castle", "bridge", "fountain", "library", "greenhouse"])})

                    # Pressure events (occasional)
                    if random.random() < 0.2:
                        self._add_event(player_id, creative_id, "energy_empty", event_date,
                                        {"current": 0, "max": random.randint(20, 100)})
                    if random.random() < 0.1:
                        self._add_event(player_id, creative_id, "missing_item", event_date,
                                        {"item": random.choice(["dragon_scale", "magic_herb", "star_dust"]),
                                         "needed": random.randint(1, 5)})

                # Daily login
                if day > 0 and random.random() < 0.8:
                    self._add_event(player_id, creative_id, "daily_login", event_date,
                                    {"streak": min(day + 1, 30)})

                # Event participation (special events, collector drivers)
                if random.random() < arch.get("event_chance", 0.05):
                    self._add_event(player_id, creative_id, "event_participate", event_date,
                                    {"event_name": random.choice(["dragon_festival", "harvest_moon", "starfall", "witch_trials"])})

                # Monetization (for payers)
                if is_payer and random.random() < 0.15:
                    price = round(random.uniform(0.99, 49.99), 2)
                    self._add_event(player_id, creative_id, "shop_open", event_date, {"section": "special_offer"})
                    self._add_event(player_id, creative_id, "offer_view", event_date,
                                    {"offer_id": f"offer_{random.randint(1, 20)}", "price": price})
                    if random.random() < 0.4:
                        self._add_event(player_id, creative_id, "purchase_success", event_date,
                                        {"offer_id": f"offer_{random.randint(1, 20)}", "price": price, "currency": "USD"})

        return self._events

    def _add_event(self, player_id: str, creative_id: str, event_name: str,
                   event_time: datetime, event_value: dict[str, Any]) -> None:
        """Add a single event with random time offset."""
        time_offset = timedelta(
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )
        self._events.append(PlayerEvent(
            player_id=player_id,
            creative_id=creative_id,
            event_name=event_name,
            event_time=event_time + time_offset,
            event_value=event_value,
            source="sample",
        ))

    def export_csv(self, path: str | Path) -> str:
        """Export events to CSV for future use."""
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "player_id", "creative_id", "event_name", "event_time", "event_value", "source"
            ])
            writer.writeheader()
            for e in self._events:
                writer.writerow({
                    "player_id": e.player_id,
                    "creative_id": e.creative_id,
                    "event_name": e.event_name,
                    "event_time": e.event_time.isoformat(),
                    "event_value": json.dumps(e.event_value),
                    "source": e.source,
                })
        return str(path)

    @property
    def events(self) -> list[PlayerEvent]:
        return self._events


# ═══════════════════════════════════════════════════════════
# Player DNA Engine
# ═══════════════════════════════════════════════════════════

class PlayerDNAEngine:
    """Extracts PlayerDNA from raw PlayerEvent data.

    Processes events per-player to compute:
      - ProgressionDNA: merge count, speed, areas, levels
      - CollectionDNA: items, rare items, collections completed
      - PaymentDNA: payer status, purchase frequency, triggers
      - RetentionDNA: days active, sessions, retention flags
    """

    def __init__(self) -> None:
        self._player_dna: dict[str, PlayerDNA] = {}

    def extract_all(self, events: list[PlayerEvent]) -> dict[str, PlayerDNA]:
        """Extract PlayerDNA for all players from events.

        Returns: {player_id: PlayerDNA}
        """
        # Group events by player
        player_events: dict[str, list[PlayerEvent]] = defaultdict(list)
        for e in events:
            player_events[e.player_id].append(e)

        self._player_dna = {}
        for player_id, evts in player_events.items():
            self._player_dna[player_id] = self._extract_one(player_id, evts)

        return self._player_dna

    def _extract_one(self, player_id: str, events: list[PlayerEvent]) -> PlayerDNA:
        """Extract DNA for a single player."""
        # Sort events by time
        events.sort(key=lambda e: e.event_time)

        if not events:
            return PlayerDNA(player_id=player_id, creative_id="unknown")

        creative_id = events[0].creative_id
        first_event = events[0].event_time
        last_event = events[-1].event_time
        lifetime_days = max(1, (last_event - first_event).days)

        # ── Progression DNA ──
        merge_count = sum(1 for e in events if e.event_name in ("merge_create", "merge_upgrade"))
        merge_speed = merge_count / lifetime_days
        max_level = max((e.event_value.get("to_level", 0) for e in events
                         if e.event_name == "merge_upgrade"), default=0)
        areas_unlocked = sum(1 for e in events if e.event_name == "area_unlock")
        buildings_restored = sum(1 for e in events if e.event_name == "building_restore")
        progression_velocity = max_level / lifetime_days if lifetime_days > 0 else 0

        progression = ProgressionDNA(
            merge_count=merge_count,
            merge_speed=round(merge_speed, 2),
            max_level=max_level,
            areas_unlocked=areas_unlocked,
            buildings_restored=buildings_restored,
            progression_velocity=round(progression_velocity, 2),
        )

        # ── Collection DNA ──
        items_collected = sum(1 for e in events if e.event_name == "item_collect")
        rare_items = sum(1 for e in events if e.event_name == "rare_item_get")
        collections_completed = sum(1 for e in events if e.event_name == "collection_complete")
        collection_rate = (items_collected + rare_items) / lifetime_days if lifetime_days > 0 else 0
        rare_item_interest = rare_items / max(1, items_collected + rare_items)
        completion_bias = collections_completed / 5.0  # assume 5 collections available

        collection = CollectionDNA(
            items_collected=items_collected,
            rare_items=rare_items,
            collections_completed=collections_completed,
            collection_rate=round(collection_rate, 2),
            rare_item_interest=round(rare_item_interest, 2),
            completion_bias=round(completion_bias, 2),
        )

        # ── Payment DNA ──
        purchase_events = [e for e in events if e.event_name == "purchase_success"]
        is_payer = len(purchase_events) > 0
        first_purchase_day = -1
        if is_payer:
            first_purchase = purchase_events[0]
            first_purchase_day = (first_purchase.event_time - first_event).days

        total_purchases = len(purchase_events)
        total_spend = sum(e.event_value.get("price", 0) for e in purchase_events)
        purchase_frequency = total_purchases / (lifetime_days / 7) if lifetime_days >= 7 else 0
        avg_order_value = total_spend / total_purchases if total_purchases > 0 else 0.0

        # Determine purchase triggers from pressure events before purchase
        purchase_triggers: list[str] = []
        if is_payer:
            for pe in purchase_events:
                # Look at pressure events within 10 minutes before purchase
                purchase_time = pe.event_time
                for e in events:
                    if e.is_pressure:
                        time_diff = (purchase_time - e.event_time).total_seconds()
                        if 0 < time_diff < 600:  # within 10 min
                            purchase_triggers.append(e.event_name)

        # Deduplicate triggers
        purchase_triggers = list(set(purchase_triggers))[:5]

        payment = PaymentDNA(
            is_payer=is_payer,
            first_purchase_day=first_purchase_day,
            total_purchases=total_purchases,
            total_spend=round(total_spend, 2),
            purchase_frequency=round(purchase_frequency, 2),
            avg_order_value=round(avg_order_value, 2),
            purchase_triggers=purchase_triggers,
        )

        # ── Retention DNA ──
        active_days = set()
        session_count = 0
        for e in events:
            active_days.add(e.event_time.date())
            if e.event_name == "session_start":
                session_count += 1

        days_active = len(active_days)
        session_frequency = session_count / lifetime_days if lifetime_days > 0 else 0

        # Retention flags
        d1_retained = (last_event - first_event).days >= 1
        d7_retained = (last_event - first_event).days >= 7
        d30_retained = (last_event - first_event).days >= 29  # 30-day simulation = 29 days span

        # Return behavior
        if days_active >= lifetime_days * 0.8:
            return_behavior = "daily"
        elif days_active >= lifetime_days * 0.4:
            return_behavior = "weekly"
        elif days_active >= 3:
            return_behavior = "sporadic"
        else:
            return_behavior = "churned"

        event_participation = sum(1 for e in events if e.event_name == "event_participate")

        retention = RetentionDNA(
            days_active=days_active,
            total_sessions=session_count,
            session_frequency=round(session_frequency, 2),
            d1_retained=d1_retained,
            d7_retained=d7_retained,
            d30_retained=d30_retained,
            return_behavior=return_behavior,
            event_participation=event_participation,
        )

        # ── Build PlayerDNA ──
        dna = PlayerDNA(
            player_id=player_id,
            creative_id=creative_id,
            progression=progression,
            collection=collection,
            payment=payment,
            retention=retention,
            lifetime_days=lifetime_days,
        )
        dna.compute_derived()
        return dna

    def get_all(self) -> dict[str, PlayerDNA]:
        return self._player_dna

    def get_by_creative(self) -> dict[str, list[PlayerDNA]]:
        """Group player DNA by creative_id."""
        grouped: dict[str, list[PlayerDNA]] = defaultdict(list)
        for dna in self._player_dna.values():
            grouped[dna.creative_id].append(dna)
        return dict(grouped)