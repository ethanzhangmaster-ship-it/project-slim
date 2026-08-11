"""
EP0.8 — Backup & Recovery: snapshot / restore Memory, Patterns, Decision history.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List


class BackupManager:
    """Snapshot and restore project data.

    Usage::

        bm = BackupManager(backup_dir="data/backups")
        bm.backup(["data/play_runtime", "data/aso", "data/demo_memory"])
        bm.list_snapshots()
        bm.restore("backup_2026-08-01_090000.tar.gz", target="data/restore_test")
    """

    def __init__(self, backup_dir: str = "data/backups"):
        self.dir = Path(backup_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def backup(self, paths: List[str], label: str = "") -> str:
        """Create a timestamped .tar.gz snapshot of given paths."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        name = f"backup_{ts}" + (f"_{label}" if label else "")
        archive_path = self.dir / f"{name}.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            for p in paths:
                path = Path(p)
                if not path.exists():
                    continue
                tar.add(path, arcname=path.name)

        # Write metadata
        meta = {
            "created": ts,
            "label": label,
            "paths": paths,
            "size_bytes": archive_path.stat().st_size,
        }
        meta_path = self.dir / f"{name}.meta.json"
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)

        return str(archive_path)

    def list_snapshots(self) -> List[dict]:
        """List all snapshots with metadata."""
        snapshots = []
        for meta_file in sorted(self.dir.glob("*.meta.json"), reverse=True):
            with open(meta_file) as fh:
                meta = json.load(fh)
            archive = self.dir / meta_file.name.replace(".meta.json", ".tar.gz")
            meta["archive"] = str(archive)
            meta["exists"] = archive.exists()
            snapshots.append(meta)
        return snapshots

    def restore(self, archive_name: str, target: str = "data") -> str:
        """Restore a snapshot to target directory."""
        archive_path = self.dir / archive_name
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        target_dir = Path(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(archive_path, "r:gz") as tar:
            # EP0.11.5: "data" filter blocks path traversal / absolute paths
            # (and silences the Python 3.14 unfiltered-extract deprecation).
            tar.extractall(path=target_dir, filter="data")

        return str(target_dir)
