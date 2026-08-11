"""Platform Capability Manager"""
import json
from typing import Dict, Any
from pathlib import Path


class CapabilityManager:
    _instance = None
    _capabilities: Dict[str, Dict[str, Any]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self):
        config_path = Path(__file__).resolve().parent / "platform_capability.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._capabilities = json.load(f)

    def get_capability(self, platform: str) -> Dict[str, Any]:
        return self._capabilities.get(platform, {})

    def has_capability(self, platform: str, capability: str) -> bool:
        platform_cap = self.get_capability(platform)
        return platform_cap.get(capability, False)

    def list_platforms(self) -> list:
        return list(self._capabilities.keys())

    def get_supported_fields(self, platform: str) -> list:
        return self.get_capability(platform).get("supported_fields", [])

    def get_required_fields(self, platform: str) -> list:
        return self.get_capability(platform).get("required_fields", [])

    def get_max_token_length(self, platform: str) -> int:
        return self.get_capability(platform).get("max_token_length", 0)


capability_manager = CapabilityManager()
