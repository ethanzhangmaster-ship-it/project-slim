from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_NEGATIVE_PROMPTS: list[str] = [
    "No watermark",
    "No logo",
    "No blur",
    "No low resolution",
    "No cropped UI",
    "No extra fingers",
    "No deformed hands",
    "No duplicated objects",
    "No unreadable text",
]


@dataclass(slots=True)
class CreativeSpec:
    creative_id: str
    template: str

    hook: str
    reward: str
    mechanic: str
    identity: str

    scene: str
    camera: str
    composition: str
    lighting: str
    emotion: str
    cta: str
    style: str

    negative: list[str] = field(default_factory=lambda: list(DEFAULT_NEGATIVE_PROMPTS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "CreativeSpec":
        negative = payload.get("negative") or []
        if not isinstance(negative, list):
            negative = []
        return CreativeSpec(
            creative_id=str(payload.get("creative_id") or ""),
            template=str(payload.get("template") or ""),
            hook=str(payload.get("hook") or ""),
            reward=str(payload.get("reward") or ""),
            mechanic=str(payload.get("mechanic") or ""),
            identity=str(payload.get("identity") or ""),
            scene=str(payload.get("scene") or ""),
            camera=str(payload.get("camera") or ""),
            composition=str(payload.get("composition") or ""),
            lighting=str(payload.get("lighting") or ""),
            emotion=str(payload.get("emotion") or ""),
            cta=str(payload.get("cta") or ""),
            style=str(payload.get("style") or ""),
            negative=[str(item) for item in negative if str(item).strip()],
        )


@dataclass(slots=True)
class CompiledPrompt:
    creative_id: str
    lovart_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dumps_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
