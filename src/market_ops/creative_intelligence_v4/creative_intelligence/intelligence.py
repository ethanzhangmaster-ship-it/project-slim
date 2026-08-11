"""V4.0: Creative Intelligence — unified generation orchestration.

Bridges Phase 3.0 Prompt Planner for Image planning and
provides Video planning with hybrid AI + Eagle gameplay.
"""

from __future__ import annotations

from typing import Any

from ..dna.image_dna import ImageDNA
from ..dna.video_dna import VideoDNA

from ..creative_repository.repository import CreativeRepository
from ..creative_repository.metadata import CreativeMetadata, CreativeType


class CreativeIntelligence:
    """V4.0 Creative Intelligence Engine.

    Unified orchestration for Image and Video creative generation.
    Bridges Phase 3.0 Prompt Planner and Phase 3.0A Image Pipeline.
    """

    def __init__(self, repository: CreativeRepository | None = None) -> None:
        self._repo = repository or CreativeRepository()

    def plan_image_from_dna(
        self, dna: ImageDNA, strategy: str = "aggressive", model: str = "lovart",
    ) -> dict[str, Any]:
        """Generate a Prompt Plan from Image DNA.

        Bridges to Phase 3.0 CreativePromptPlanner.
        """
        from market_ops.creative_generation.planner import CreativePromptPlanner

        planner = CreativePromptPlanner(strategy=strategy, model=model)
        plan = planner.generate_plan(dna.to_planner_input())
        renderer = planner.render(plan)

        return {
            "plan": plan.to_dict(),
            "prompt": renderer.to_dict(),
            "dna_source": dna.to_dict(),
        }

    def plan_image_batch(
        self, dna: ImageDNA, count: int = 20, strategy: str = "aggressive",
    ) -> list[dict[str, Any]]:
        """Generate multiple prompt plans from Image DNA."""
        from market_ops.creative_generation.planner import CreativePromptPlanner

        planner = CreativePromptPlanner(strategy=strategy)
        prompts = planner.generate(dna.to_planner_input(), count=count)
        top = planner.top_n(prompts, n=min(count, 20))

        return [{"prompt": p.to_dict(), "dna_source": dna.to_dict()} for p in top]

    def plan_video_from_dna(
        self, dna: VideoDNA, strategy: str = "balanced",
    ) -> dict[str, Any]:
        """Generate a Video Plan from Video DNA.

        Hybrid mode: AI Opening + Eagle Gameplay + Reward + Ending + CTA.
        """
        return {
            "dna_source": dna.to_dict(),
            "plan": {
                "plan_type": "video",
                "strategy": strategy,
                "segments": [
                    {
                        "segment": "opening",
                        "type": "ai_generated",
                        "duration_ms": 3000,
                        "hook": dna.opening_hook,
                        "description": f"AI-generated opening hook: {dna.opening_hook}",
                    },
                    {
                        "segment": "gameplay",
                        "type": "eagle_real",
                        "duration_ms": dna.duration_ms - 6000 if dna.duration_ms > 6000 else 5000,
                        "structure": dna.gameplay_structure,
                        "eagle_path": dna.eagle_local_path,
                        "description": "Real Eagle gameplay footage",
                    },
                    {
                        "segment": "reward",
                        "type": "eagle_real",
                        "duration_ms": 2000,
                        "reward_type": dna.reward_type,
                        "description": f"Reward moment: {dna.reward_type}",
                    },
                    {
                        "segment": "ending",
                        "type": "ai_generated",
                        "duration_ms": 2000,
                        "cta": dna.cta_text,
                        "description": "AI-generated ending with CTA",
                    },
                ],
            },
        }

    def register_winning_dna(
        self, dna_data: dict[str, Any], creative_type: str = "image",
    ) -> CreativeMetadata:
        """Register a winning creative DNA into the repository."""
        meta = self._repo.register(
            creative_type=creative_type,
            facebook_data=dna_data.get("performance", {}),
            adjust_data=dna_data.get("adjust", {}),
        )
        self._repo.save_dna(meta.creative_id, dna_data)
        return meta

    @property
    def repository(self) -> CreativeRepository:
        return self._repo