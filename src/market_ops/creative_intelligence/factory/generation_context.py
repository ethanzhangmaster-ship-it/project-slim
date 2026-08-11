"""Phase 1 统一生成上下文。

统一在 Factory 各阶段之间传递状态，避免散落的 kwargs。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def find_project_root() -> Path:
    """从当前文件向上查找项目根（含 output/creative_analysis 或 src 的目录）。"""
    here = Path(__file__).resolve()
    candidates = [here, *here.parents]
    for p in candidates:
        if (p / "output" / "creative_analysis" / "dna_cache" / "winners_dna.json").exists():
            return p
        if (p / "src" / "market_ops").exists() or (p / ".git").exists():
            return p
    # 兜底：认为是 src 的上一级
    return here.parents[4]


@dataclass
class GenerationContext:
    """贯穿一次生成任务的上下文对象。"""

    project_id: str = "P04"
    winner_id: str = ""
    winner_code: str = ""                 # 归一化短码，如 "001"
    winner_dna: dict[str, Any] = field(default_factory=dict)
    reference_images: list[dict[str, Any]] = field(default_factory=list)
    generation_count: int = 50
    mutation_level: float = 0.0           # Phase 2 预留，Phase 1 不使用
    output_dir: Path = field(default_factory=Path)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.output_dir:
            self.output_dir = find_project_root() / "output" / "creative_factory"
