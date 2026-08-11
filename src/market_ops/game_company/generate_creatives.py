#!/usr/bin/env python3
"""CLI for generating creative batches."""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from game_company.creative_generator.generator import CreativeGenerator


def main():
    parser = argparse.ArgumentParser(description="Generate creative batches for mobile game ads")
    parser.add_argument("--project", default="P04 Witch", help="Project name (default: P04 Witch)")
    parser.add_argument("--direction", default="collection",
                        choices=["collection", "reward", "curiosity", "comparison", "crisis"],
                        help="Creative direction / hook type")
    parser.add_argument("--count", type=int, default=20, help="Number of creatives to generate (default: 20)")
    args = parser.parse_args()

    gen = CreativeGenerator()
    result = gen.generate(
        project=args.project,
        direction=args.direction,
        count=args.count,
    )

    print(f"\n{'='*60}")
    print(f"Creative Generator - Batch Complete")
    print(f"{'='*60}")
    print(f"Project: {result['project']}")
    print(f"Direction: {result['direction']}")
    print(f"Count: {result['count']}")
    print(f"Output: {result['batch_dir']}")
    print(f"{'='*60}\n")

    for c in result["creatives"]:
        print(f"  {c['id']}: {c['title']}")
        print(f"    Hero: {c['hero']} + {c['pet']}")
        print(f"    Environment: {c['environment']}")
        print(f"    Reward: {c['reward']}")
        print()

    print(f"Total: {len(result['creatives'])} creatives generated.")
    print(f"Export directory: {result['batch_dir']}")


if __name__ == "__main__":
    main()
