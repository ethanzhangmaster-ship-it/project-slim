"""Embedding Store — Phase 2.1 向量持久化（带缓存）。

目录布局：
    <base>/winner/winner_001.npy
    <base>/creative/creative_001.npy

规则：若 .npy 已存在，直接读取，避免重复编码（省 GPU/CPU 时间）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class EmbeddingStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self.winner_dir = self.base / "winner"
        self.creative_dir = self.base / "creative"
        self.winner_dir.mkdir(parents=True, exist_ok=True)
        self.creative_dir.mkdir(parents=True, exist_ok=True)

    # ---- winner ----
    def save_winner(self, name: str, vec: Any) -> str:
        path = self.winner_dir / f"{name}.npy"
        np.save(path, np.asarray(vec, dtype=np.float32))
        return str(path)

    def load_winner(self, name: str) -> Any | None:
        path = self.winner_dir / f"{name}.npy"
        return np.load(path) if path.exists() else None

    def winner_path(self, name: str) -> str:
        return str(self.winner_dir / f"{name}.npy")

    # ---- creative ----
    def save_creative(self, name: str, vec: Any) -> str:
        path = self.creative_dir / f"{name}.npy"
        np.save(path, np.asarray(vec, dtype=np.float32))
        return str(path)

    def load_creative(self, name: str) -> Any | None:
        path = self.creative_dir / f"{name}.npy"
        return np.load(path) if path.exists() else None

    def creative_path(self, name: str) -> str:
        return str(self.creative_dir / f"{name}.npy")

    # ---- 兼容通用接口 ----
    def save(self, name: str, vec: Any, kind: str = "creative") -> str:
        if kind == "winner":
            return self.save_winner(name, vec)
        return self.save_creative(name, vec)

    def load(self, name: str, kind: str = "creative") -> Any | None:
        if kind == "winner":
            return self.load_winner(name)
        return self.load_creative(name)
