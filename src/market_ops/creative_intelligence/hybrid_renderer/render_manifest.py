"""Render Manifest V1

记录渲染过程的完整元数据。

输出：render_manifest.json
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LayerRecord:
    name: str
    path: str
    generator: str
    prompt_used: str = ""
    model: str = ""


@dataclass(slots=True)
class ValidationRecord:
    gameplay_score: float = 0.0
    board_visible: bool = False
    merge_action_visible: bool = False
    progression_visible: bool = False


@dataclass(slots=True)
class RenderManifest:
    creative_id: str = ""
    template: str = ""
    template_name: str = ""
    project: str = ""
    generation_mode: str = "hybrid_renderer_v1"
    generated_at: str = ""
    layers: list[LayerRecord] = field(default_factory=list)
    validation: ValidationRecord | None = None
    final_image: str = ""
    winner_dna_summary: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ManifestBuilder:
    """Build and save render manifest."""

    def __init__(self) -> None:
        self._manifest = RenderManifest(
            generated_at=datetime.now().isoformat(),
        )

    def set_creative_id(self, cid: str) -> "ManifestBuilder":
        self._manifest.creative_id = cid
        return self

    def set_template(self, template_id: str, template_name: str) -> "ManifestBuilder":
        self._manifest.template = template_id
        self._manifest.template_name = template_name
        return self

    def set_project(self, project: str) -> "ManifestBuilder":
        self._manifest.project = project
        return self

    def add_layer(self, name: str, path: str, generator: str = "",
                  prompt: str = "", model: str = "") -> "ManifestBuilder":
        self._manifest.layers.append(LayerRecord(
            name=name, path=path, generator=generator,
            prompt_used=prompt, model=model,
        ))
        return self

    def set_validation(self, gameplay_score: float, board: bool,
                       merge: bool, progression: bool) -> "ManifestBuilder":
        self._manifest.validation = ValidationRecord(
            gameplay_score=gameplay_score,
            board_visible=board,
            merge_action_visible=merge,
            progression_visible=progression,
        )
        return self

    def set_final_image(self, path: str) -> "ManifestBuilder":
        self._manifest.final_image = path
        return self

    def set_winner_dna(self, dna: dict[str, Any]) -> "ManifestBuilder":
        self._manifest.winner_dna_summary = {
            "subject": dna.get("subject", ""),
            "palette": dna.get("palette", ""),
            "overlay_text": dna.get("overlay_text", ""),
        }
        return self

    def set_metadata(self, key: str, value: Any) -> "ManifestBuilder":
        self._manifest.metadata[key] = value
        return self

    def build(self) -> RenderManifest:
        return self._manifest

    def save(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "creative_id": self._manifest.creative_id,
            "template": self._manifest.template,
            "template_name": self._manifest.template_name,
            "project": self._manifest.project,
            "generation_mode": self._manifest.generation_mode,
            "generated_at": self._manifest.generated_at,
            "layers": [
                {"name": l.name, "path": l.path, "generator": l.generator,
                 "prompt": l.prompt_used[:200] if l.prompt_used else "", "model": l.model}
                for l in self._manifest.layers
            ],
            "validation": {
                "gameplay_score": self._manifest.validation.gameplay_score if self._manifest.validation else 0,
                "board_visible": self._manifest.validation.board_visible if self._manifest.validation else False,
                "merge_action_visible": self._manifest.validation.merge_action_visible if self._manifest.validation else False,
                "progression_visible": self._manifest.validation.progression_visible if self._manifest.validation else False,
            },
            "final_image": self._manifest.final_image,
            "winner_dna_summary": self._manifest.winner_dna_summary,
            "metadata": self._manifest.metadata,
        }
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out