"""Phase 2.2A: Generation Dashboard CLI.

Usage:
    python generation_dashboard.py          # Single render
    python generation_dashboard.py --watch 5  # Refresh every 5s
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.observability.dashboard import GenerationDashboard


def main(watch: int = 0):
    dashboard = GenerationDashboard()

    if watch > 0:
        try:
            while True:
                print("\033[2J\033[H")  # Clear screen
                print(dashboard.render())
                time.sleep(watch)
        except KeyboardInterrupt:
            print("\nExiting...")
    else:
        print(dashboard.render())


if __name__ == "__main__":
    watch = 0
    if "--watch" in sys.argv:
        try:
            idx = sys.argv.index("--watch")
            watch = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            watch = 5
    main(watch=watch)