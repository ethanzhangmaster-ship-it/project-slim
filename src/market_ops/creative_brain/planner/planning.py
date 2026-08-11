"""V4.1 Planning — generates creative plans from reasoning."""

from __future__ import annotations

from typing import Any


class Planner:
    """Generates creative plans (image/video) from reasoning insights."""

    def generate(self, request: str, plan_type: str,
                 retrieved: list[dict[str, Any]],
                 reasoning: str, **context) -> dict[str, Any]:
        """Generate a creative plan."""
        plan = {
            "plan_type": plan_type,
            "request": request,
            "prompt": self._build_prompt(request, plan_type, retrieved, context),
            "composition": self._build_composition(plan_type, context),
            "camera": self._build_camera(plan_type, context),
            "motion": {"type": "smooth", "speed": "medium"},
            "subtitle": {"enabled": True, "style": "bold_white"},
            "music": {"genre": "epic", "tempo": "fast"},
            "launch_ready": bool(retrieved),
            "confidence": min(0.5 + len(retrieved) * 0.1, 0.95),
        }
        return plan

    def _build_prompt(self, request: str, plan_type: str,
                  retrieved: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        positive = request
        negative = ""

        # Incorporate retrieved DNA
        for r in retrieved:
            if r.get("type") == "dna":
                dna_data = r.get("metadata", {}).get("dna_data", {})
                if dna_data.get("character"):
                    positive += f", character: {dna_data['character']}"
                if dna_data.get("reward"):
                    positive += f", reward: {dna_data['reward']}"
                if dna_data.get("hook"):
                    positive += f", hook: {dna_data['hook']}"

        return {
            "positive_prompt": positive,
            "negative_prompt": negative or "blurry, low quality, deformed",
            "model": context.get("model", "lovart"),
            "strategy": context.get("strategy", "balanced"),
        }

    def _build_composition(self, plan_type: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "layout": context.get("composition", "center"),
            "subject_position": "center",
            "background": "gameplay_scene",
            "aspect_ratio": "1:1" if plan_type == "image" else "9:16",
        }

    def _build_camera(self, plan_type: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "angle": context.get("camera", "45_degree"),
            "distance": "medium",
            "motion": "zoom" if plan_type == "video" else "static",
        }