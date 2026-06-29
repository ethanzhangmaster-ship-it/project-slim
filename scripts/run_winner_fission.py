"""Probe: winner fission end-to-end (dry-run first, then real generation).

This validates the full winner-fission pipeline:
  1. Load cached winner visual DNA
  2. Forge variation prompts (anchored to real winners, with reference_image_url)
  3. Optionally generate images via Lovart img2img

Usage:
    # Dry-run: verify prompts look correct, no API calls
    set PYTHONUTF8=1
    python scripts\run_winner_fission.py --dry-run

    # Real run: generate 2 variation images (costs Lovart credits)
    python scripts\run_winner_fission.py --max-prompts 2

    # All 6 prompts, real generation
    python scripts\run_winner_fission.py --max-prompts 6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from market_ops.config import load_settings
from market_ops.creative_closed_loop import CreativeClosedLoop


def main() -> int:
    parser = argparse.ArgumentParser(description="Winner fission: real winner → variation images")
    parser.add_argument("--game", default="P04 Witch")
    parser.add_argument("--max-prompts", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true",
                        help="Only forge prompts, skip image generation")
    parser.add_argument("--score-threshold", type=float, default=6.0)
    parser.add_argument("--no-lovart", dest="lovart", action="store_false")
    parser.add_argument("--output-dir", default="output/creative_loop")
    args = parser.parse_args()

    loop = CreativeClosedLoop(
        game=args.game,
        output_dir=args.output_dir,
        use_lovart=args.lovart,
        score_threshold=args.score_threshold,
    )
    result = loop.run_winner_fission(
        max_prompts=args.max_prompts,
        dry_run=args.dry_run,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
