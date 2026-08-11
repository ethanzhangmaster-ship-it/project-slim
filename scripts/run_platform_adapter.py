"""Run Platform Adapter Pipeline"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_ops.video_generation.video_generation_api import generate, generate_all
from src.market_ops.video_generation.adapters.registry import registry


def main():
    print("=" * 60)
    print("Platform Adapter Layer V4.5.1")
    print("=" * 60)

    blueprint_dir = "output/video_blueprint/V001"
    
    print(f"\n[1/3] Available Platforms:")
    platforms = registry.list_platforms()
    for i, platform in enumerate(platforms, 1):
        print(f"  {i}. {platform}")

    print(f"\n[2/3] Generating for all platforms...")
    
    results = generate_all(blueprint_dir)
    
    for platform, package in results.items():
        status = "✓" if package.success else "✗"
        print(f"\n  {status} {platform}:")
        if package.success:
            print(f"    Prompt Files: {len(package.prompt_files)}")
            if package.workflow_file:
                print(f"    Workflow: {package.workflow_file}")
        else:
            print(f"    Failed")

    print(f"\n[3/3] Output Summary")
    print("-" * 60)
    for platform in platforms:
        output_dir = Path("output") / "platform" / platform
        if output_dir.exists():
            scene_dirs = list(output_dir.glob("S*"))
            print(f"\n  {platform}/")
            for scene_dir in scene_dirs[:3]:
                files = [f.name for f in scene_dir.iterdir()]
                print(f"    {scene_dir.name}/")
                for f in files:
                    print(f"      - {f}")
            if len(scene_dirs) > 3:
                print(f"    ... ({len(scene_dirs) - 3} more scenes)")

    print("\n" + "=" * 60)
    print("Platform Adapter Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
