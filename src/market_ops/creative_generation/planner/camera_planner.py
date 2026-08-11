"""Phase 3.0: Camera Planner — lens, distance, angle, focus, DOF.

Outputs camera tokens: lens type, shot distance, angle, focus point, depth of field.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


CAMERA_TOKENS: dict[str, dict[str, str]] = {
    "45_degree": {
        "lens": "35mm lens",
        "distance": "medium shot",
        "angle": "45 degree overhead angle",
        "focus": "sharp focus on main subject",
        "dof": "shallow depth of field, bokeh background",
        "description": "45° overhead, medium shot",
    },
    "35_degree": {
        "lens": "35mm lens",
        "distance": "medium shot",
        "angle": "35 degree angle",
        "focus": "sharp focus on main subject",
        "dof": "shallow depth of field",
        "description": "35° angle, medium shot",
    },
    "55_degree": {
        "lens": "50mm lens",
        "distance": "medium shot",
        "angle": "55 degree high angle",
        "focus": "sharp focus on main subject",
        "dof": "moderate depth of field",
        "description": "55° high angle, medium shot",
    },
    "top_down": {
        "lens": "24mm wide lens",
        "distance": "full scene",
        "angle": "top down, bird's eye view",
        "focus": "sharp focus on center area",
        "dof": "deep depth of field, everything in focus",
        "description": "Top-down view, full scene",
    },
    "low_angle": {
        "lens": "24mm wide lens",
        "distance": "low angle looking up",
        "angle": "heroic low angle",
        "focus": "sharp focus on subject face",
        "dof": "shallow depth of field, dramatic",
        "description": "Heroic low angle",
    },
    "eye_level": {
        "lens": "50mm lens",
        "distance": "medium shot",
        "angle": "eye level, direct engagement",
        "focus": "sharp focus on eyes",
        "dof": "shallow depth of field",
        "description": "Eye level, direct engagement",
    },
    "close_up": {
        "lens": "85mm portrait lens",
        "distance": "close-up portrait",
        "angle": "eye level",
        "focus": "ultra sharp focus on eyes and expression",
        "dof": "very shallow depth of field, creamy bokeh",
        "description": "Close-up portrait",
    },
    "extreme_close_up": {
        "lens": "100mm macro lens",
        "distance": "extreme close-up",
        "angle": "eye level",
        "focus": "razor sharp focus on eyes and details",
        "dof": "extremely shallow depth of field",
        "description": "Extreme close-up",
    },
    "medium_shot": {
        "lens": "50mm lens",
        "distance": "medium shot, waist up",
        "angle": "eye level",
        "focus": "sharp focus on subject",
        "dof": "moderate depth of field",
        "description": "Medium shot, waist up",
    },
    "full_body": {
        "lens": "35mm lens",
        "distance": "full body shot",
        "angle": "slightly low angle",
        "focus": "sharp focus on full subject",
        "dof": "moderate depth of field",
        "description": "Full body shot",
    },
    "wide_shot": {
        "lens": "24mm wide lens",
        "distance": "wide establishing shot",
        "angle": "eye level or slightly high",
        "focus": "everything in focus",
        "dof": "deep depth of field",
        "description": "Wide establishing shot",
    },
    "dutch_angle": {
        "lens": "35mm lens",
        "distance": "medium shot",
        "angle": "dutch tilt, dynamic diagonal",
        "focus": "sharp focus on subject",
        "dof": "shallow depth of field",
        "description": "Dutch tilt, dynamic angle",
    },
    "isometric": {
        "lens": "orthographic projection",
        "distance": "full scene",
        "angle": "isometric 30° angle",
        "focus": "uniform focus across scene",
        "dof": "no depth of field, game-like perspective",
        "description": "Isometric game view",
    },
}


class CameraPlanner:
    """Plans camera setup for a prompt based on camera angle type."""

    def plan(self, camera: str, strategy: str = "balanced") -> PromptComponent:
        tokens = CAMERA_TOKENS.get(camera, CAMERA_TOKENS["45_degree"])
        return PromptComponent(
            dimension="camera",
            value=camera,
            label=tokens.get("description", camera),
            weight=1.0,
        )

    def get_tokens(self, camera: str) -> dict[str, str]:
        return CAMERA_TOKENS.get(camera, CAMERA_TOKENS["45_degree"])