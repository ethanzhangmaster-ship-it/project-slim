"""Phase 2: Lovart Video Content Analysis.

For each video, use Lovart AI + structured AI parsing to extract:
  - Hook (type, first 3 seconds content)
  - Story (structure, plot)
  - Reward (type, tags)
  - Character (age/gender/clothing/hair/profession/action/expression)
  - Environment (scene, tags)
  - Camera (shot type, movement, tags)
  - Motion (pace, cut speed, action speed, rhythm)
  - Emotion (emotions, intensity)
  - CTA (type, timing, style)
  - Video Style (real/3D/2D/CG/AI/hand-drawn)
  - Color (tone, saturation)
  - Audio (narration/sfx/bgm, tempo)

Output: video_analysis.json per video
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from market_ops.clients.lovart import LovartClient
from market_ops.clients.ai import AIClient, OpenAIAIClient
from market_ops.config import Settings
from market_ops.video_intelligence.models import (
    VideoAnalysis, HookAnalysis, StoryAnalysis, RewardAnalysis,
    CharacterAnalysis, EnvironmentAnalysis, CameraAnalysis,
    MotionAnalysis, EmotionAnalysis, CTAAnalysis, StyleAnalysis, AudioAnalysis,
)


VIDEO_ANALYSIS_PROMPT = """You are a video ad analyst for mobile games. Analyze the thumbnail image from a Facebook video ad creative and infer what the full video likely contains based on the visual cues.

The ad is for a mobile game. Based on the thumbnail, describe the video's content in the following structured JSON format. Respond ONLY with valid JSON, no markdown fences, no commentary.

{
  "hook": {
    "hook_type": "one of: chest / number / beauty / boss / gold_coin / giant_reward / danger / countdown / failure / mystery / comparison / collection / other",
    "description": "what happens in the first 3 seconds",
    "tags": ["list of specific visual elements seen"]
  },
  "story": {
    "structure": "one of: failure_growth / level_up / comeback / twist / rescue / merge / exploration / showcase / tutorial / other",
    "description": "brief narrative arc of the video"
  },
  "reward": {
    "reward_type": "one of: gold_coin / diamond / epic_chest / skin / weapon / character / none",
    "tags": ["specific reward items shown"]
  },
  "character": {
    "age": "young / adult / elder / none",
    "gender": "female / male / none / unclear",
    "clothing": "description of outfit",
    "hairstyle": "description of hair",
    "profession": "mage / warrior / archer / rogue / civilian / none",
    "action": "what the character is doing",
    "expression": "facial expression"
  },
  "environment": {
    "scene": "forest / cave / snow / dungeon / castle / village / battlefield / void / other",
    "tags": ["environmental elements seen"]
  },
  "camera": {
    "shot_type": "close_up / medium / wide / extreme_close_up",
    "movement": "zoom / rotate / shake / slow_motion / static / pan / dolly",
    "tags": ["camera techniques likely used"]
  },
  "motion": {
    "pace": "fast / medium / slow",
    "cut_speed": "rapid / moderate / slow",
    "action_speed": "fast / normal / slow",
    "rhythm_changes": ["e.g. 'start fast, end slow'"]
  },
  "emotion": {
    "emotions": ["tension / surprise / satisfaction / failure / anger / excitement / curiosity / relief / fear"],
    "intensity": "high / medium / low"
  },
  "cta": {
    "cta_type": "play_now / install / download / get_started / try_now / none_visible",
    "timing": "end / middle / beginning / throughout",
    "display_style": "button / text_overlay / voice / none_visible"
  },
  "style": {
    "video_style": "real_screen_recording / 3d / 2d / cg / ai_generated / hand_drawn / mixed",
    "color_tone": "warm / cool / neutral",
    "saturation": "high / medium / low"
  },
  "audio": {
    "has_narration": true/false,
    "has_sfx": true/false,
    "has_bgm": true/false,
    "tempo": "fast / medium / slow / uncertain",
    "tags": ["audio elements likely present"]
  }
}
"""


class LovartVideoAnalyzer:
    """Analyze each video via Lovart AI + structured parsing."""

    def __init__(
        self,
        lovart_client: LovartClient | None = None,
        ai_client: AIClient | None = None,
        settings: Settings | None = None,
        output_dir: str | Path | None = None,
        skip_existing: bool = True,
    ) -> None:
        self._settings = settings or Settings.from_env()
        self._lovart = lovart_client or LovartClient()
        self._ai = ai_client or OpenAIAIClient(self._settings)

        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._analysis_dir = self._output_dir / "analysis"
        self._analysis_dir.mkdir(parents=True, exist_ok=True)
        self._skip_existing = skip_existing

    def run(self, video_records: list[dict], video_metrics: list[dict] | None = None) -> list[dict]:
        print(f"[Phase 2] LovartVideoAnalyzer: Analyzing {len(video_records)} videos...")

        metrics_map: dict[str, dict] = {}
        if video_metrics:
            for m in video_metrics:
                metrics_map[m.get("video_id", "")] = m

        results: list[dict] = []
        for i, rec in enumerate(video_records):
            video_id = rec.get("video_id", f"video_{rec.get('creative_id', 'unknown')}")
            analysis_file = self._analysis_dir / f"{video_id}.json"

            if self._skip_existing and analysis_file.exists():
                try:
                    existing = json.loads(analysis_file.read_text(encoding="utf-8"))
                    results.append(existing)
                    print(f"  [{i+1}/{len(video_records)}] {video_id} (cached)")
                    continue
                except Exception:
                    pass

            print(f"  [{i+1}/{len(video_records)}] {video_id} analyzing...")

            local_path = rec.get("local_path", "")
            thumbnail_url = rec.get("thumbnail_url", "")
            creative_name = rec.get("creative_name", "")
            creative_id = rec.get("creative_id", "")

            try:
                analysis = self._analyze_video(
                    video_id=video_id,
                    creative_id=creative_id,
                    local_path=local_path,
                    thumbnail_url=thumbnail_url,
                    creative_name=creative_name,
                )
                analysis_dict = self._analysis_to_dict(analysis)

                analysis_file.write_text(
                    json.dumps(analysis_dict, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                results.append(analysis_dict)
            except Exception as exc:
                print(f"  [{i+1}/{len(video_records)}] {video_id} FAILED: {exc}")
                fallback = self._fallback_analysis(video_id, creative_id)
                results.append(self._analysis_to_dict(fallback))

        all_file = self._analysis_dir / "all_video_analysis.json"
        all_file.write_text(
            json.dumps(results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"[Phase 2] Done. {len(results)} analyses saved to {self._analysis_dir}")
        return results

    def _analyze_video(
        self,
        video_id: str,
        creative_id: str,
        local_path: str,
        thumbnail_url: str,
        creative_name: str,
    ) -> VideoAnalysis:
        image_path = local_path if local_path and Path(local_path).exists() else None

        metadata_context = f"Creative name: {creative_name}"

        if image_path:
            try:
                lovart_desc = self._lovart.describe_image(image_path, project="video_intel")
                metadata_context += f"\nThumbnail visual description: {json.dumps(lovart_desc, ensure_ascii=False)}"
            except Exception as exc:
                print(f"    Lovart describe failed, using OpenAI fallback: {exc}")

        parsed = self._parse_with_ai(video_id, metadata_context)

        return VideoAnalysis(
            video_id=video_id,
            creative_id=creative_id,
            hook=HookAnalysis(**parsed.get("hook", {})),
            story=StoryAnalysis(**parsed.get("story", {})),
            reward=RewardAnalysis(**parsed.get("reward", {})),
            character=CharacterAnalysis(**parsed.get("character", {})),
            environment=EnvironmentAnalysis(**parsed.get("environment", {})),
            camera=CameraAnalysis(**parsed.get("camera", {})),
            motion=MotionAnalysis(**parsed.get("motion", {})),
            emotion=EmotionAnalysis(**parsed.get("emotion", {})),
            cta=CTAAnalysis(**parsed.get("cta", {})),
            style=StyleAnalysis(**parsed.get("style", {})),
            color=StyleAnalysis(**parsed.get("color", {})),
            audio=AudioAnalysis(**parsed.get("audio", {})),
            raw_response=json.dumps(parsed, ensure_ascii=False),
        )

    def _parse_with_ai(self, video_id: str, context: str) -> dict[str, Any]:
        payload = {
            "video_id": video_id,
            "context": context,
            "task": "Analyze this video ad creative's thumbnail and infer full video content features.",
        }
        try:
            result = self._ai.generate_json(
                task_name="video_analysis",
                instructions=VIDEO_ANALYSIS_PROMPT,
                payload=payload,
            )
            return result
        except Exception as exc:
            print(f"    AI parse failed: {exc}, using fallback")
            return self._build_fallback_parsed()

    @staticmethod
    def _build_fallback_parsed() -> dict[str, Any]:
        return {
            "hook": {"hook_type": "other", "description": "unable to analyze", "tags": []},
            "story": {"structure": "other", "description": "unable to analyze"},
            "reward": {"reward_type": "none", "tags": []},
            "character": {
                "age": "none", "gender": "none", "clothing": "", "hairstyle": "",
                "profession": "none", "action": "", "expression": "",
            },
            "environment": {"scene": "other", "tags": []},
            "camera": {"shot_type": "medium", "movement": "static", "tags": []},
            "motion": {"pace": "medium", "cut_speed": "moderate", "action_speed": "normal", "rhythm_changes": []},
            "emotion": {"emotions": [], "intensity": "medium"},
            "cta": {"cta_type": "none_visible", "timing": "end", "display_style": "none_visible"},
            "style": {"video_style": "2d", "color_tone": "neutral", "saturation": "medium"},
            "audio": {"has_narration": False, "has_sfx": False, "has_bgm": False, "tempo": "uncertain", "tags": []},
        }

    @staticmethod
    def _fallback_analysis(video_id: str, creative_id: str) -> VideoAnalysis:
        return VideoAnalysis(
            video_id=video_id,
            creative_id=creative_id,
            hook=HookAnalysis(hook_type="other", description="analysis failed", tags=[]),
            story=StoryAnalysis(structure="other", description="analysis failed"),
            reward=RewardAnalysis(reward_type="none", tags=[]),
            character=CharacterAnalysis(),
            environment=EnvironmentAnalysis(scene="other", tags=[]),
            camera=CameraAnalysis(shot_type="medium", movement="static", tags=[]),
            motion=MotionAnalysis(pace="medium", cut_speed="moderate", action_speed="normal", rhythm_changes=[]),
            emotion=EmotionAnalysis(emotions=[], intensity="medium"),
            cta=CTAAnalysis(cta_type="none_visible", timing="end", display_style="none_visible"),
            style=StyleAnalysis(video_style="2d", color_tone="neutral", saturation="medium"),
            color=StyleAnalysis(video_style="2d", color_tone="neutral", saturation="medium"),
            audio=AudioAnalysis(),
        )

    def _analysis_to_dict(self, analysis: VideoAnalysis) -> dict[str, Any]:
        return analysis.to_flattened_dict()
