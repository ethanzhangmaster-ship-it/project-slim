"""Prompt Compiler Runner - V4.5.0"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_ops.video_generation.compiler.prompt_compiler import PromptCompiler


def main():
    blueprint_dir = Path(__file__).resolve().parents[1] / "output" / "video_blueprint" / "V001"
    output_dir = Path(__file__).resolve().parents[1] / "output" / "prompt_compiler"

    print("=" * 60)
    print("Prompt Compiler V4.5.0 - Core")
    print("=" * 60)

    print("\n[1/5] Blueprint Parser...")
    compiler = PromptCompiler(str(blueprint_dir))

    print("\n[2/5] Building AST...")
    master = compiler.compile()

    print(f"  Scenes: {len(master.scenes)}")

    print("\n[3/5] Validating...")
    validation = compiler.validate(master)
    print(f"  Passed: {validation.passed}")
    print(f"  Errors: {len(validation.errors)}")
    print(f"  Warnings: {len(validation.warnings)}")

    print("\n[4/5] Rendering & Saving...")
    result = compiler.compile_and_save(str(output_dir))

    print(f"  Total Tokens: {result['statistics']['total_tokens']}")
    print(f"  Total Prompts: {result['statistics']['total_prompts']}")
    print(f"  Avg Length: {result['statistics']['avg_length']}")
    print(f"  Duplicate Rate: {result['statistics']['duplicate_rate']:.2%}")
    print(f"  Compression Rate: {result['statistics']['compression_rate']:.2%}")

    print("\n[5/5] Output Files:")
    for fpath in result['output_files']:
        print(f"  ✓ {Path(fpath).name}")

    print("\n" + "=" * 60)
    print("Prompt Compiler Complete!")
    print("=" * 60)

    print(f"\nOutput Directory: {output_dir}")


if __name__ == "__main__":
    main()