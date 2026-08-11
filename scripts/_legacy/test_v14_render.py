"""Quick test for Hybrid Renderer V1.4 — Real Asset Foundation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_intelligence.hybrid_renderer.hybrid_creative_renderer_v14 import (
    HybridCreativeRendererV14,
)

print("=" * 60)
print("Hybrid Renderer V1.4 — Real Asset Foundation Test")
print("=" * 60)

renderer = HybridCreativeRendererV14(
    project="P04 Evolution Merge",
    output_dir="output/creative_intelligence/runs/hybrid_v14",
)

result = renderer.render()

print(f"\n{'=' * 60}")
print(f"Result:")
print(f"  Final: {result.final_image}")
print(f"  Base: {result.real_base_source}")
print(f"  Layers: {len(result.layers)}")
print(f"{'=' * 60}")