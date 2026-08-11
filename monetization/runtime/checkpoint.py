"""
E14.2 — Module 2: Checkpoint Manager
=====================================

The core durability primitive for 7x24 operation. After (or before) every
stage of an Agent Cycle we persist a *checkpoint* so that a crash or data
corruption can be recovered from the most recent consistent state.

Two complementary artefacts:
  1. STAGE CHECKPOINTS  — metadata-only snapshots of where the cycle was:
         before_decision -> after_decision -> during_execution -> after_execution
     Used to prove stage-level progress and to know what was in flight.
  2. STORE SNAPSHOTS    — a byte copy of the agent's DecisionStore JSONL file,
     kept as a rolling window (last N). Used to recover from a *corrupted*
     store (Case 2): copy the latest good snapshot back over the broken file
     and reload.

Pure stdlib. No DB. Every write is atomic (temp file + os.replace).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from monetization.runtime.event_logger import EVENT_CHECKPOINT_SAVED


# Cycle stages (the resume points)
STAGE_BEFORE_DECISION = "before_decision"
STAGE_AFTER_DECISION = "after_decision"
STAGE_DURING_EXECUTION = "during_execution"
STAGE_AFTER_EXECUTION = "after_execution"
CHECKPOINT_STAGES = (
    STAGE_BEFORE_DECISION, STAGE_AFTER_DECISION,
    STAGE_DURING_EXECUTION, STAGE_AFTER_EXECUTION,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointManager:
    """Per-game checkpoint store. Lives at `<root>/<game_slug>/`."""

    def __init__(self, root_dir: str, game_slug: str,
                 max_store_snapshots: int = 5):
        self.slug = game_slug
        self.dir = Path(root_dir) / game_slug
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_store_snapshots = max_store_snapshots

    # ------------------------------------------------------------------ #
    # Stage checkpoints (metadata)
    # ------------------------------------------------------------------ #
    def save_stage(self, cycle_id: str, stage: str, state_hash: str,
                   meta: Optional[dict] = None) -> dict:
        if stage not in CHECKPOINT_STAGES:
            raise ValueError(f"unknown stage: {stage}")
        ckpt = {
            "cycle_id": cycle_id,
            "game": self.slug,
            "stage": stage,
            "state_hash": state_hash,
            "timestamp": _now_iso(),
            "meta": meta or {},
        }
        path = self.dir / f"ckpt_{stage}_{cycle_id}.json"
        self._atomic_write(path, ckpt)
        # prune older stage checkpoints for the same stage
        for old in sorted(self.dir.glob(f"ckpt_{stage}_*.json"))[:-3]:
            try:
                old.unlink()
            except OSError:
                pass
        return ckpt

    def latest_stage(self, stage: str) -> Optional[dict]:
        files = sorted(self.dir.glob(f"ckpt_{stage}_*.json"))
        if not files:
            return None
        try:
            return json.loads(files[-1].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------ #
    # Store snapshots (byte copy of the DecisionStore JSONL)
    # ------------------------------------------------------------------ #
    def snapshot_store(self, store_path: str) -> Optional[Path]:
        src = Path(store_path)
        if not src.exists():
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        dst = self.dir / f"store_{ts}.jsonl"
        try:
            shutil.copyfile(src, dst)
        except OSError:
            return None
        self._prune_store_snapshots()
        return dst

    def latest_store_snapshot(self) -> Optional[Path]:
        snaps = sorted(self.dir.glob("store_*.jsonl"))
        return snaps[-1] if snaps else None

    def _prune_store_snapshots(self) -> None:
        snaps = sorted(self.dir.glob("store_*.jsonl"))
        for old in snaps[:-self.max_store_snapshots]:
            try:
                old.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Restore (Case 2: data corruption)
    # ------------------------------------------------------------------ #
    def restore_store(self, agent) -> int:
        """Copy the latest good store snapshot over the (possibly corrupted)
        live store file and reload the agent's in-memory index.

        Returns the number of records recovered (0 if nothing to restore).
        """
        snap = self.latest_store_snapshot()
        if snap is None:
            return 0
        # Copy the snapshot over the live store in place. We stage the temp file
        # inside the live store's OWN directory so the final rename stays on the
        # same volume (os.replace raises WinError 17 across drives on Windows).
        live = Path(str(agent.store.path))
        live.parent.mkdir(parents=True, exist_ok=True)
        tmp = live.parent / f".restore_tmp_{os.getpid()}.jsonl"
        shutil.copyfile(snap, tmp)
        os.replace(str(tmp), str(live))
        agent.store.load()
        return agent.store.count()

    # ------------------------------------------------------------------ #
    def _atomic_write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, str(path))
        finally:
            if Path(tmp).exists():
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


__all__ = [
    "CheckpointManager", "CHECKPOINT_STAGES",
    "STAGE_BEFORE_DECISION", "STAGE_AFTER_DECISION",
    "STAGE_DURING_EXECUTION", "STAGE_AFTER_EXECUTION",
]
