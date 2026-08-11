"""Adapter Result Schema"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any
import json


@dataclass
class AdapterResult:
    """统一适配器输出结构"""
    platform: str = ""
    status: str = "pending"
    prompt: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    cost: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def is_success(self) -> bool:
        return self.status == "success"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdapterResult":
        return cls(
            platform=data.get("platform", ""),
            status=data.get("status", "pending"),
            prompt=data.get("prompt", {}),
            validation=data.get("validation", {}),
            cost=data.get("cost", {}),
            metadata=data.get("metadata", {})
        )
