"""Probe: describe ONE real winner image via Lovart to validate the look-at-winner path.

Purpose:
  Before rewiring PromptForge and the closed loop around real winner visual DNA,
  we need to confirm Lovart's multimodal /chat endpoint can actually look at a
  real Facebook ad image and return a structured visual description. This script
  runs that probe on a single image and prints the result.

Usage (run from project root):
    set PYTHONUTF8=1
    python scripts\\probe_winner_description.py
    python scripts\\probe_winner_description.py --limit 4   # all images

Exit code 0 = at least one image described successfully; non-zero = all failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `market_ops` importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from market_ops.config import load_settings
from market_ops.creative_winner_reader import WinnerVisualDnaReader


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Lovart winner-image description.")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="How many NEW images to describe this run (default 1, for probing).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache and re-describe.",
    )
    args = parser.parse_args()

    settings = load_settings()
    reader = WinnerVisualDnaReader(settings)
    result = reader.read(limit=args.limit, force_refresh=args.force_refresh)

    print("=" * 70)
    print("Winner Visual DNA Probe")
    print("=" * 70)
    print(f"source folder : {result.source_path}")
    print(f"cache file    : {result.cache_path}")
    print(f"newly described: {result.newly_described}")
    print(f"reused cache  : {result.cached}")
    print(f"skipped videos: {result.skipped_videos}")
    print(f"errors        : {len(result.errors)}")
    print()

    if result.errors:
        print("--- errors ---")
        for err in result.errors:
            print(f"  - {err}")
        print()

    if not result.items:
        print("No items produced. See errors above.")
        return 1

    print("--- described items ---")
    for item in result.items:
        print(f"\n[{item['creative_name']}]  ({item['image_path']})")
        dna = item.get("visual_dna") or {}
        if "error" in dna:
            print(f"  ERROR: {dna['error']}")
            if dna.get("raw_text"):
                print(f"  raw : {dna['raw_text']}")
            continue
        print(json.dumps(dna, ensure_ascii=False, indent=2))

    # Success if at least one item has a real visual_dna (no error key).
    ok = any("error" not in (item.get("visual_dna") or {}) for item in result.items)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
