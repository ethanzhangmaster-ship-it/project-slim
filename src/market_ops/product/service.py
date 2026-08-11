"""Long-running, safe service roles for the Market Ops production surface."""

from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

from .control_plane import ControlPlane


_running = True


def _stop(_: int, __: object) -> None:
    global _running
    _running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a safe Market Ops service role")
    parser.add_argument("role", choices=("worker", "scheduler"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.interval_seconds < 10:
        raise SystemExit("--interval-seconds must be at least 10")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    control = ControlPlane(args.root)
    print(f"Market Ops {args.role} started; platform writes remain gated.", flush=True)
    while _running:
        try:
            if args.role == "scheduler":
                # This sync only reads configured sources and writes local reports.
                code = control.run_safe_command("sync")
                if code:
                    print(f"source sync exited with code {code}", flush=True)
            control.write_snapshot()
        except Exception as exc:  # keep a production service observable after transient failures
            print(f"{args.role} iteration failed: {exc}", flush=True)
        for _ in range(args.interval_seconds):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
