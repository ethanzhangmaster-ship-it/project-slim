from __future__ import annotations

import argparse
import json
from pathlib import Path

from .control_plane import ControlPlane


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose Market Ops production readiness")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    control = ControlPlane(args.root)
    snapshot = control.snapshot()
    if args.write:
        control.write_snapshot()
    print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
    raise SystemExit(1 if snapshot.status == "blocked" else 0)


if __name__ == "__main__":
    main()
