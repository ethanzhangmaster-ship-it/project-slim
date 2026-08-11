"""Template Engine V1

加载和管理 UA 创意模板。

模板目录: creative_templates/
  - merge_evolution.json
  - before_after.json
  - reward_unlock.json
  - collection.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TemplateLayer:
    name: str
    position: str
    x: float
    y: float
    width: float
    height: float
    z_index: int
    content: str
    align: str = "center"
    components: list[str] = field(default_factory=list)
    label: str = ""
    label_color: list[int] = field(default_factory=lambda: [255, 255, 255])
    label_style: str = "normal"
    text: str = ""
    style: str = ""
    progress_pct: float = 0.0


@dataclass(slots=True)
class Template:
    template_id: str
    template_name: str
    version: str
    description: str
    canvas: dict[str, Any]
    layers: list[TemplateLayer]
    config: dict[str, Any] = field(default_factory=dict)


class TemplateEngine:
    """加载和选择 UA 创意模板。"""

    TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "creative_templates"

    TEMPLATE_MAP = {
        "before_after_merge": "merge_evolution.json",
        "merge_evolution": "merge_evolution.json",
        "vertical_progression": "before_after.json",
        "before_after": "before_after.json",
        "character_driven_merge": "reward_unlock.json",
        "reward_unlock": "reward_unlock.json",
        "split_screen_compare": "before_after.json",
        "collection": "collection.json",
    }

    def __init__(self) -> None:
        self._cache: dict[str, Template] = {}

    def load(self, template_key: str) -> Template:
        """加载模板。支持 layout_type 名称或 template_id。"""
        if template_key in self._cache:
            return self._cache[template_key]

        filename = self.TEMPLATE_MAP.get(template_key, f"{template_key}.json")
        path = self.TEMPLATE_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Template not found: {path} (key={template_key})"
            )

        raw = json.loads(path.read_text(encoding="utf-8"))
        template = self._parse(raw)
        self._cache[template_key] = template
        return template

    def _parse(self, raw: dict) -> Template:
        layers = []
        for layer in raw.get("layers", []):
            layers.append(TemplateLayer(
                name=layer["name"],
                position=layer["position"],
                x=layer["x"],
                y=layer["y"],
                width=layer["width"],
                height=layer["height"],
                z_index=layer["z_index"],
                content=layer["content"],
                align=layer.get("align", "center"),
                components=layer.get("components", []),
                label=layer.get("label", ""),
                label_color=layer.get("label_color", [255, 255, 255]),
                label_style=layer.get("label_style", "normal"),
                text=layer.get("text", ""),
                style=layer.get("style", ""),
                progress_pct=layer.get("progress_pct", 0.0),
            ))

        config = {}
        for key in ("merge_config", "before_after_config", "reward_config", "collection_config", "ui_elements"):
            if key in raw:
                config[key] = raw[key]

        return Template(
            template_id=raw["template_id"],
            template_name=raw["template_name"],
            version=raw["version"],
            description=raw["description"],
            canvas=raw["canvas"],
            layers=layers,
            config=config,
        )

    def list_templates(self) -> list[str]:
        return sorted(self.TEMPLATE_MAP.keys())

    def resolve_layout(self, layout_type: str) -> Template:
        """根据 layout_type 返回最佳匹配模板。"""
        return self.load(layout_type)