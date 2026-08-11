"""Config loader — yaml-based with env override support."""
from pathlib import Path
from typing import Any, Optional
import yaml


class Config:
    """Configuration loaded from yaml file.

    Supports:
    - Nested key access via get() with defaults
    - Auto device detection
    - Dict-like attribute access
    """

    def __init__(self, path: Optional[Path] = None):
        if path is None:
            path = Path(__file__).resolve().parent.parent / "output" / "video_intelligence" / "p04" / "v3_5" / "config.yaml"
        self._path = path
        self._data = yaml.safe_load(path.read_text(encoding="utf-8"))

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get nested config value. e.g. config.get('embedding', 'model', default='vit')."""
        d = self._data
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d if d is not None else default

    def set(self, *keys: str, value: Any) -> None:
        """Set nested config value at runtime (not persisted)."""
        d = self._data
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    @property
    def device(self) -> str:
        d = self.get("embedding", "device", default="auto")
        if d == "auto":
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        return d

    @property
    def data_root(self) -> Path:
        return Path(__file__).resolve().parent.parent / "output" / "video_intelligence" / "p04"

    @property
    def output_root(self) -> Path:
        return self.data_root / "v3_5"

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        return self._data.get(key, {})
