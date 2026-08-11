"""Template Engine V2

加载 V2 模板（merge_evolution_v2, reward_unlock_v2, before_after_v2）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TemplateLayerV2:
    name: str
    position: str
    x: float
    y: float
    width: float
    height: float
    z_index: int
    content: str
    generator: str = ""
    feather_radius: int = 0
    align: str = "center"
    components: list[str] = field(default_factory=list)
    label: str = ""
    label_color: list[int] = field(default_factory=lambda: [255, 255, 255])
    label_style: str = "normal"
    text: str = ""
    style: str = ""


@dataclass(slots=True)
class TemplateV2:
    template_id: str
    template_name: str
    version: str
    description: str
    canvas: dict[str, Any]
    layers: list[TemplateLayerV2]
    config: dict[str, Any] = field(default_factory=dict)


class TemplateEngineV2:
    """V2 template engine for hybrid renderer."""

    TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "creative_templates"

    TEMPLATE_MAP = {
        "before_after_merge": "merge_evolution_ua_v4.json",
        "merge_evolution": "merge_evolution_ua_v4.json",
        "vertical_progression": "merge_evolution_ua_v4.json",
        "before_after": "merge_evolution_ua_v4.json",
        "character_driven_merge": "merge_evolution_ua_v4.json",
        "reward_unlock": "merge_evolution_ua_v4.json",
        "split_screen_compare": "merge_evolution_ua_v4.json",
        "collection": "collection_v3.json",
        "ua_fixed": "merge_evolution_ua_v4.json",
    }

    def __init__(self) -> None:
        self._cache: dict[str, TemplateV2] = {}

    def load(self, template_key: str) -> TemplateV2:
        if template_key in self._cache:
            return self._cache[template_key]

        filename = self.TEMPLATE_MAP.get(template_key, f"{template_key}.json")
        path = self.TEMPLATE_DIR / filename

        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path} (key={template_key})")

        raw = json.loads(path.read_text(encoding="utf-8"))
        template = self._parse(raw)
        self._cache[template_key] = template
        return template

    def _parse(self, raw: dict) -> TemplateV2:
        layers = []
        for layer in raw.get("layers", []):
            layers.append(TemplateLayerV2(
                name=layer["name"],
                position=layer["position"],
                x=layer["x"],
                y=layer["y"],
                width=layer["width"],
                height=layer["height"],
                z_index=layer["z_index"],
                content=layer["content"],
                generator=layer.get("generator", ""),
                feather_radius=layer.get("feather_radius", 0),
                align=layer.get("align", "center"),
                components=layer.get("components", []),
                label=layer.get("label", ""),
                label_color=layer.get("label_color", [255, 255, 255]),
                label_style=layer.get("label_style", "normal"),
                text=layer.get("text", ""),
                style=layer.get("style", ""),
            ))

        config = {}
        for key in ("gameplay_config", "character_config", "reward_config", "generation_config"):
            if key in raw:
                config[key] = raw[key]

        return TemplateV2(
            template_id=raw["template_id"],
            template_name=raw["template_name"],
            version=raw["version"],
            description=raw["description"],
            canvas=raw["canvas"],
            layers=layers,
            config=config,
        )

    def resolve_layout(self, layout_type: str) -> TemplateV2:
        return self.load(layout_type)