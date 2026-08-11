"""E11.1 Genome Repository — Genome 持久化存储层。

支持：
  - save: 保存 Genome 到 JSON 文件
  - load: 从 JSON 文件加载 Genome
  - save_all: 批量保存
  - load_all: 批量加载
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..genome.schema import CreativeGenome
from ..genome.exceptions import GenomeRepositoryError, GenomeNotFoundError


class GenomeRepository:
    """Genome 文件存储仓库。

    Usage:
        repo = GenomeRepository(storage_dir="./data/genomes")
        repo.save(genome)
        loaded = repo.load("genome_001")
    """

    def __init__(self, storage_dir: str | Path = "./data/genomes") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # ── 单条操作 ──────────────────────────────────────

    def save(self, genome: CreativeGenome) -> str:
        """保存单个 Genome 到文件。

        Args:
            genome: CreativeGenome 实例

        Returns:
            保存的文件路径
        """
        filepath = self._get_filepath(genome.genome_id)
        try:
            data = genome.to_dict()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return str(filepath)
        except (OSError, TypeError) as e:
            raise GenomeRepositoryError(
                f"Failed to save genome {genome.genome_id!r}: {e}"
            ) from e

    def load(self, genome_id: str) -> CreativeGenome:
        """从文件加载单个 Genome。

        Args:
            genome_id: Genome ID

        Returns:
            CreativeGenome 实例

        Raises:
            GenomeNotFoundError: 文件不存在
            GenomeRepositoryError: 加载失败
        """
        filepath = self._get_filepath(genome_id)
        if not filepath.exists():
            raise GenomeNotFoundError(genome_id)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CreativeGenome.from_dict(data)
        except (json.JSONDecodeError, OSError) as e:
            raise GenomeRepositoryError(
                f"Failed to load genome {genome_id!r}: {e}"
            ) from e

    def exists(self, genome_id: str) -> bool:
        """检查 Genome 是否存在。"""
        return self._get_filepath(genome_id).exists()

    def delete(self, genome_id: str) -> None:
        """删除 Genome 文件。"""
        filepath = self._get_filepath(genome_id)
        if filepath.exists():
            filepath.unlink()

    # ── 批量操作 ──────────────────────────────────────

    def save_all(self, genomes: list[CreativeGenome]) -> list[str]:
        """批量保存 Genome。

        Returns:
            保存的文件路径列表
        """
        paths: list[str] = []
        for genome in genomes:
            path = self.save(genome)
            paths.append(path)
        return paths

    def load_all(self) -> list[CreativeGenome]:
        """加载所有存储的 Genome。

        Returns:
            CreativeGenome 列表
        """
        genomes: list[CreativeGenome] = []
        for filepath in self._storage_dir.glob("*.json"):
            genome_id = filepath.stem
            try:
                genome = self.load(genome_id)
                genomes.append(genome)
            except GenomeRepositoryError:
                continue
        return genomes

    def list_ids(self) -> list[str]:
        """列出所有已存储的 Genome ID。"""
        return [
            fp.stem
            for fp in self._storage_dir.glob("*.json")
            if fp.is_file()
        ]

    def count(self) -> int:
        """返回已存储的 Genome 数量。"""
        return len(self.list_ids())

    # ── 内部方法 ──────────────────────────────────────

    def _get_filepath(self, genome_id: str) -> Path:
        """获取 Genome 文件路径。"""
        return self._storage_dir / f"{genome_id}.json"

    @property
    def storage_dir(self) -> Path:
        """存储目录。"""
        return self._storage_dir