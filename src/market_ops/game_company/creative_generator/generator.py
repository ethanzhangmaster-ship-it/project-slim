from typing import Dict, List, Optional
from datetime import datetime

from .variant_engine import VariantEngine, CreativeConfig, CreativeAsset
from .exporter import CreativeExporter


class CreativeGenerator:
    def __init__(self):
        self._variant_engine = VariantEngine()
        self._exporter = CreativeExporter()

    def generate(self, project: str = "P04 Witch", direction: str = "collection",
                 count: int = 20, hook_type: str = None) -> Dict:
        if hook_type is None:
            hook_type = direction if direction in ["collection", "reward", "curiosity", "comparison", "crisis"] else "collection"

        config = CreativeConfig(project=project, hook_type=hook_type, direction=direction)

        assets = self._variant_engine.generate_variants(config, count)
        batch_dir = self._exporter.export_batch(assets)

        return {
            "project": project,
            "direction": direction,
            "count": count,
            "batch_dir": batch_dir,
            "generated_at": datetime.now().isoformat(),
            "creatives": [
                {
                    "id": a.creative_id,
                    "title": a.title,
                    "hero": a.hero.get("name"),
                    "pet": a.hero.get("pet"),
                    "environment": a.environment.get("name"),
                    "reward": a.reward.get("name"),
                }
                for a in assets
            ],
        }

    def get_stats(self) -> Dict[str, int]:
        return {"total_dna_combinations": 6 * 8 * 8 * 7 * 6 * 7}
