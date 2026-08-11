"""V4.0: DNA Extractor — unified DNA extraction for Image and Video.

Bridges to existing modules:
  - Image DNA: Reuses Phase 3.0 Winner DNA format
  - Video DNA: Reuses video_intelligence/creative_mapping/engine.py
"""

from __future__ import annotations

from typing import Any

from .image_dna import ImageDNA
from .video_dna import VideoDNA


class DNAExtractor:
    """Unified DNA extraction for Image and Video creatives.

    For Image: converts Winner DNA JSON to ImageDNA.
    For Video: wraps existing video_intelligence pipeline.
    """

    def extract_image_dna(self, data: dict[str, Any]) -> ImageDNA:
        """Extract Image DNA from a Winner DNA dict.

        Compatible with Phase 3.0 winner_dna JSON format.
        """
        dna = data.get("dna", data)
        return ImageDNA(
            character=dna.get("character", ""),
            reward=dna.get("reward", ""),
            gameplay=dna.get("gameplay", ""),
            composition=dna.get("composition", ""),
            camera=dna.get("camera", ""),
            lighting=dna.get("lighting", ""),
            palette=dna.get("palette", ""),
            emotion=dna.get("emotion", ""),
            hook=dna.get("hook", ""),
            style=dna.get("style", ""),
            brand=data.get("summary", ""),
            source_creative_id=data.get("winner_id", ""),
            confidence=0.8,
        )

    def extract_video_dna(self, data: dict[str, Any]) -> VideoDNA:
        """Extract Video DNA from existing video_intelligence output.

        Compatible with video_intelligence pipeline output.
        """
        return VideoDNA(
            opening_hook=data.get("opening_hook", ""),
            gameplay_start_ms=data.get("gameplay_start_ms", 0),
            gameplay_structure=data.get("gameplay_structure", ""),
            gameplay_density=data.get("gameplay_density", 0),
            reward_timing_ms=data.get("reward_timing_ms", 0),
            reward_type=data.get("reward_type", ""),
            ending_type=data.get("ending_type", ""),
            cta_text=data.get("cta_text", ""),
            cta_timing_ms=data.get("cta_timing_ms", 0),
            camera_motion=data.get("camera_motion", ""),
            camera_distance=data.get("camera_distance", ""),
            transitions=data.get("transitions", ""),
            cut_rhythm=data.get("cut_rhythm", ""),
            duration_ms=data.get("duration_ms", 0),
            music=data.get("music", ""),
            sfx=data.get("sfx", ""),
            emotion_curve=data.get("emotion_curve", ""),
            story_arc=data.get("story_arc", ""),
            hook_type=data.get("hook_type", ""),
            style=data.get("style", ""),
            source_creative_id=data.get("creative_id", ""),
            facebook_video_id=data.get("video_id", ""),
            eagle_local_path=data.get("eagle_path", ""),
            confidence=data.get("confidence", 0.0),
        )