"""
E14 Slice 1 — Multi-game isolation: per-game configuration contract
===================================================================

A single person operating 10–50 games needs each game to be a *fully isolated*
tenant: its own memory (DecisionStore), its own learned prior, and its own
Policy / Guardrail tuning. This module is the lean, stdlib-only data contract
for one game's configuration.

No external services, no DB, no YAML dependency — a GameConfig is plain data
that can be loaded from JSON (or a Python dict) and resolved to a namespaced
on-disk store path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class GameConfig:
    """Configuration for one isolated game tenant.

    Fields:
        slug        — filesystem/namespace-safe unique id (e.g. "word_quest").
        display_name— human label (defaults to slug).
        store_dir   — optional explicit directory for this game's JSONL; when
                      omitted it defaults to <base_dir>/<slug>.
        policy      — overrides merged onto PolicyConfig defaults.
        guardrails  — overrides merged onto GuardrailConfig defaults.
        active      — whether the OS should run this game's agent.
    """

    slug: str
    display_name: str = ""
    store_dir: Optional[str] = None
    policy: Dict[str, object] = field(default_factory=dict)
    guardrails: Dict[str, object] = field(default_factory=dict)
    active: bool = True

    def resolved_store_path(self, base_dir: str) -> Path:
        """Absolute path to this game's namespaced decisions JSONL file."""
        d = Path(self.store_dir) if self.store_dir else Path(base_dir) / self.slug
        return d / "decisions.jsonl"

    @classmethod
    def from_dict(cls, d: dict) -> "GameConfig":
        return cls(
            slug=str(d["slug"]),
            display_name=str(d.get("display_name", d["slug"])),
            store_dir=d.get("store_dir"),
            policy=dict(d.get("policy", {}) or {}),
            guardrails=dict(d.get("guardrails", {}) or {}),
            active=bool(d.get("active", True)),
        )

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "store_dir": self.store_dir,
            "policy": self.policy,
            "guardrails": self.guardrails,
            "active": self.active,
        }
