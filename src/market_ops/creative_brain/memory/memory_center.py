"""V4.1 Memory Center — unified memory management for Creative Brain.

Manages all long-term memory types:
  - Creative Memory
  - Prompt Memory
  - DNA Memory
  - Performance Memory
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .creative_memory import CreativeMemory, CreativeRecord
from .prompt_memory import PromptMemory, PromptRecord
from .dna_memory import DNAMemory, DNARecord
from .performance_memory import PerformanceMemory, PerformanceRecord


class MemoryCenter:
    """Unified memory center for the Creative Brain.

    Usage:
        mc = MemoryCenter()
        mc.creatives.add("c001", creative_type="image")
        mc.prompts.add("p001", positive_prompt="A dragon...")
        mc.dna.add("dna001", dna_type="image", dna_data={"character": "witch"})
        mc.performance.add("perf001", spend=100, ctr=0.85)
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        base = Path(base_dir or "output/creative_brain/memory")
        self._creatives = CreativeMemory(base / "creatives")
        self._prompts = PromptMemory(base / "prompts")
        self._dna = DNAMemory(base / "dna")
        self._performance = PerformanceMemory(base / "performance")

    @property
    def creatives(self) -> CreativeMemory:
        return self._creatives

    @property
    def prompts(self) -> PromptMemory:
        return self._prompts

    @property
    def dna(self) -> DNAMemory:
        return self._dna

    @property
    def performance(self) -> PerformanceMemory:
        return self._performance

    def search_all(self, query: str) -> dict[str, list[Any]]:
        """Search across all memory types."""
        return {
            "creatives": [r for r in self._creatives.search() if query.lower() in str(r.to_dict()).lower()],
            "prompts": [r for r in self._prompts.search() if query.lower() in str(r.to_dict()).lower()],
            "dna": [r for r in self._dna.search() if query.lower() in str(r.to_dict()).lower()],
            "performance": [r for r in self._performance.search() if query.lower() in str(r.to_dict()).lower()],
        }