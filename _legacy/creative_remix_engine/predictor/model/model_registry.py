"""Model Registry — 模型版本管理"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from ...config import MEMORY_DIR


class ModelRegistry:
    """管理模型版本和元数据"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.registry_file = MEMORY_DIR / "models" / "registry.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save(self):
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def register(self, model_name: str, metrics: Dict, path: str):
        """注册新模型版本"""
        entry = {
            "game": self.game_code,
            "model": model_name,
            "path": path,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
            "active": True,
        }
        # 标记旧版本为非活跃
        for e in self.entries:
            if e["model"] == model_name:
                e["active"] = False
        self.entries.append(entry)
        self.save()

    def get_active(self, model_name: str) -> Dict:
        """获取当前活跃版本"""
        for e in reversed(self.entries):
            if e["model"] == model_name and e.get("active", False):
                return e
        return {}

    def list_versions(self, model_name: str = None) -> List[Dict]:
        """列出所有版本"""
        if model_name:
            return [e for e in self.entries if e["model"] == model_name]
        return self.entries
