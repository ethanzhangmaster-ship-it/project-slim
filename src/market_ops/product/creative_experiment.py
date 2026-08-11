"""Single-variable creative experiments with an auditable attribution ledger."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CreativeVariant:
    variant_id: str
    parent_creative_id: str
    experiment_id: str
    changed_variable: str
    changed_from: str
    changed_to: str
    prompt: str
    asset_path: str = ""


class CreativeExperimentLedger:
    """The contract joining Creative Agent output to UA evidence and revenue."""

    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS creative_variants (
                    variant_id TEXT PRIMARY KEY, parent_creative_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL, changed_variable TEXT NOT NULL,
                    changed_from TEXT NOT NULL, changed_to TEXT NOT NULL,
                    prompt TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS creative_bindings (
                    variant_id TEXT PRIMARY KEY, platform TEXT NOT NULL, ad_id TEXT NOT NULL,
                    adset_id TEXT NOT NULL, campaign_id TEXT NOT NULL, bound_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS creative_outcomes (
                    variant_id TEXT PRIMARY KEY, spend REAL NOT NULL, revenue REAL NOT NULL,
                    impressions INTEGER NOT NULL, clicks INTEGER NOT NULL, installs INTEGER NOT NULL,
                    observed_at TEXT NOT NULL);
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(creative_variants)")}
            if "asset_path" not in columns:
                conn.execute("ALTER TABLE creative_variants ADD COLUMN asset_path TEXT NOT NULL DEFAULT ''")

    def create_variant(self, *, parent_creative_id: str, changed_variable: str, changed_from: str, changed_to: str, prompt: str, asset_path: str = "", experiment_id: str | None = None) -> CreativeVariant:
        if not all((parent_creative_id.strip(), changed_variable.strip(), changed_from.strip(), changed_to.strip(), prompt.strip())):
            raise ValueError("A variant requires parent, exactly one changed variable, before/after values and prompt")
        if changed_from == changed_to:
            raise ValueError("The changed variable must have a different before and after value")
        if asset_path and not Path(asset_path).exists():
            raise FileNotFoundError(f"Creative asset does not exist: {asset_path}")
        variant = CreativeVariant(str(uuid.uuid4()), parent_creative_id, experiment_id or f"creative-exp:{uuid.uuid4()}", changed_variable, changed_from, changed_to, prompt, asset_path)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO creative_variants
                (variant_id,parent_creative_id,experiment_id,changed_variable,changed_from,changed_to,prompt,asset_path,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (*asdict(variant).values(), self._now()),
            )
        return variant

    def bind_delivery(self, variant_id: str, *, platform: str, ad_id: str, adset_id: str, campaign_id: str) -> None:
        if not all((platform.strip(), ad_id.strip(), adset_id.strip(), campaign_id.strip())):
            raise ValueError("Delivery binding requires platform, ad, ad set and campaign IDs")
        self._require_variant(variant_id)
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO creative_bindings VALUES(?,?,?,?,?,?)", (variant_id, platform, ad_id, adset_id, campaign_id, self._now()))

    def attach_asset(self, variant_id: str, asset_path: str) -> None:
        """Attach or replace the materialized asset before delivery binding."""
        self._require_variant(variant_id)
        path = Path(asset_path)
        if not path.exists():
            raise FileNotFoundError(f"Creative asset does not exist: {asset_path}")
        if self._one("SELECT 1 FROM creative_bindings WHERE variant_id=?", (variant_id,)) is not None:
            raise ValueError("A delivery-bound variant asset cannot be replaced")
        with self._connect() as conn:
            conn.execute("UPDATE creative_variants SET asset_path=? WHERE variant_id=?", (str(path), variant_id))

    def record_outcome(self, variant_id: str, *, spend: float, revenue: float, impressions: int, clicks: int, installs: int) -> dict:
        self._require_variant(variant_id)
        if self._one("SELECT 1 FROM creative_bindings WHERE variant_id=?", (variant_id,)) is None:
            raise ValueError("Outcome requires a verified delivery binding")
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO creative_outcomes VALUES(?,?,?,?,?,?,?)", (variant_id, spend, revenue, impressions, clicks, installs, self._now()))
        return self.outcome(variant_id)

    def outcome(self, variant_id: str) -> dict:
        row = self._one("""SELECT v.*, b.platform,b.ad_id,b.adset_id,b.campaign_id,o.spend,o.revenue,o.impressions,o.clicks,o.installs,o.observed_at
            FROM creative_variants v LEFT JOIN creative_bindings b USING(variant_id) LEFT JOIN creative_outcomes o USING(variant_id) WHERE v.variant_id=?""", (variant_id,))
        if row is None: raise KeyError(variant_id)
        result = dict(row); spend = float(result.get("spend") or 0); result["roas"] = round(float(result.get("revenue") or 0) / spend, 4) if spend else None
        return result

    def export_experiment_packet(self, variant_id: str, path: Path) -> Path:
        path.write_text(json.dumps(self.outcome(variant_id), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _require_variant(self, variant_id: str) -> None:
        if self._one("SELECT 1 FROM creative_variants WHERE variant_id=?", (variant_id,)) is None: raise KeyError(variant_id)
    def _connect(self):
        conn = sqlite3.connect(self.database); conn.row_factory = sqlite3.Row; return conn
    def _one(self, sql: str, args: tuple):
        with self._connect() as conn: return conn.execute(sql, args).fetchone()
    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
