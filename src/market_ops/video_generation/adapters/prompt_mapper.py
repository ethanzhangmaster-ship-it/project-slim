"""Prompt Field Mapper"""
import json
from typing import Dict, Any
from pathlib import Path


class PromptMapper:
    _instance = None
    _mappings: Dict[str, Dict[str, str]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_mappings()
        return cls._instance

    def _load_mappings(self):
        config_path = Path(__file__).resolve().parent / "prompt_mapping.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._mappings = json.load(f)

    def get_mapping(self, platform: str) -> Dict[str, str]:
        return self._mappings.get(platform, {})

    def map_field(self, platform: str, master_field: str) -> str:
        mapping = self.get_mapping(platform)
        return mapping.get(master_field, master_field)

    def reverse_map_field(self, platform: str, platform_field: str) -> str:
        mapping = self.get_mapping(platform)
        for master_field, pf in mapping.items():
            if pf == platform_field:
                return master_field
        return platform_field

    def transform(self, master_prompt: Dict[str, Any], platform: str) -> Dict[str, Any]:
        mapping = self.get_mapping(platform)
        result = {}

        for master_field, value in master_prompt.items():
            if master_field == "metadata" and isinstance(value, dict):
                continue

            platform_field = mapping.get(master_field, master_field)
            if value or isinstance(value, bool):
                result[platform_field] = value

        metadata = master_prompt.get("metadata", {})
        if metadata:
            camera = metadata.get("camera", {})
            for cam_key, cam_value in camera.items():
                master_cam_field = f"camera.{cam_key}"
                platform_field = mapping.get(master_cam_field, cam_key)
                if cam_value:
                    result[platform_field] = cam_value

        return result

    def list_platforms(self) -> list:
        return list(self._mappings.keys())


prompt_mapper = PromptMapper()
