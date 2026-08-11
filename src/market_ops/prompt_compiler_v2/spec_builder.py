from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.prompt_compiler_v2.schemas import CreativeSpec, DEFAULT_NEGATIVE_PROMPTS
from market_ops.prompt_compiler_v2.template_library import pick_presets


def load_winner_features(directives_path: Path) -> dict[str, Any]:
    """Load winner features from output/pipeline_directives.json.

    We intentionally do NOT parse pipeline_prompts.md as final input.
    """
    payload = json.loads(directives_path.read_text(encoding="utf-8"))
    directives = payload.get("directives") or {}
    result: dict[str, Any] = {}
    for key, item in directives.items():
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or "").strip()
        if target:
            result[key] = target
    result["_raw"] = payload
    return result


def build_creative_specs(
    *,
    project: str,
    count: int,
    winner_features: dict[str, Any],
) -> list[CreativeSpec]:
    presets = pick_presets(project, count=count)
    specs: list[CreativeSpec] = []

    for idx, preset in enumerate(presets, start=1):
        # V1 requirement: creative_id must be short and human-checkable
        creative_id = f"{idx:03d}"
        specs.append(
            CreativeSpec(
                creative_id=creative_id,
                template=preset.template,
                hook=preset.hook,
                reward=preset.reward,
                mechanic=preset.mechanic,
                identity=preset.identity,
                scene=preset.scene,
                camera=preset.camera,
                composition=preset.composition,
                lighting=preset.lighting,
                emotion=preset.emotion,
                cta=preset.cta,
                style=preset.style,
                negative=list(DEFAULT_NEGATIVE_PROMPTS),
            )
        )
    return specs


def write_creative_specs(path: Path, specs: list[CreativeSpec]) -> None:
    # V1 requirement: pure ad strategy, no natural language descriptions, no negative field in spec file
    creative_specs_fields = {
        "creative_id", "template",
        "hook", "reward", "mechanic", "identity",
        "scene", "camera", "composition", "lighting", "emotion", "cta", "style",
    }
    payload = [{k: v for k, v in item.to_dict().items() if k in creative_specs_fields} for item in specs]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_creative_specs(path: Path) -> list[CreativeSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [CreativeSpec.from_dict(item) for item in payload if isinstance(item, dict)]
