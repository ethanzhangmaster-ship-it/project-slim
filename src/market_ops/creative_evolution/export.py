"""E9.8: Export Module — Standalone export for all Evolution output files.

Exports:
  1. mutation_candidates.json  — all generated mutation candidates
  2. top_mutations.json        — top 20 ranked mutations
  3. evolution_report.json     — full evolution cycle summary
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_evolution.schemas import (
    MutationCandidate, EvolutionReport,
)


class EvolutionExporter:
    """Standalone export module for E9.8 Evolution outputs.

    Usage:
        exporter = EvolutionExporter(output_dir="output/creative_evolution")
        paths = exporter.export_all(candidates, report)
    """

    def __init__(self, output_dir: str | Path = "output/creative_evolution") -> None:
        self._output_dir = Path(output_dir)

    def ensure_output_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── File 1: mutation_candidates.json ──────────────────

    def export_candidates(
        self,
        candidates: list[MutationCandidate],
        filename: str = "mutation_candidates.json",
    ) -> Path:
        """Export all mutation candidates."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                [c.to_dict() for c in candidates],
                f, ensure_ascii=False, indent=2,
            )
        return path

    # ── File 2: top_mutations.json ────────────────────────

    def export_top_mutations(
        self,
        candidates: list[MutationCandidate],
        top_n: int = 20,
        filename: str = "top_mutations.json",
    ) -> Path:
        """Export top N ranked mutations."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        top = candidates[:top_n]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                [
                    {
                        "rank": i + 1,
                        "genome_id": c.genome.genome_id,
                        "genome": c.genome.to_dict(),
                        "mutations": [m.to_dict() for m in c.mutations],
                        "composite_score": c.composite_score,
                        "predicted_ltv": c.predicted_ltv,
                        "predicted_archetypes": c.predicted_archetypes,
                        "risk_level": c.risk_level,
                        "confidence": c.confidence,
                    }
                    for i, c in enumerate(top)
                ],
                f, ensure_ascii=False, indent=2,
            )
        return path

    # ── File 3: evolution_report.json ─────────────────────

    def export_report(
        self,
        report: EvolutionReport,
        filename: str = "evolution_report.json",
    ) -> Path:
        """Export evolution summary report."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                report.to_dict(),
                f, ensure_ascii=False, indent=2,
            )
        return path

    # ── Batch Export ───────────────────────────────────────

    def export_all(
        self,
        candidates: list[MutationCandidate],
        report: EvolutionReport,
    ) -> dict[str, str]:
        """Export all 3 output files.

        Returns:
            {file_category: full_path}
        """
        return {
            "mutation_candidates": str(self.export_candidates(candidates)),
            "top_mutations": str(self.export_top_mutations(candidates)),
            "evolution_report": str(self.export_report(report)),
        }

    # ── Summary ────────────────────────────────────────────

    def get_export_summary(self, paths: dict[str, str]) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
        summary = {}
        for category, path_str in paths.items():
            p = Path(path_str)
            if p.exists():
                summary[category] = {
                    "path": path_str,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                }
            else:
                summary[category] = {"path": path_str, "status": "missing"}
        return summary