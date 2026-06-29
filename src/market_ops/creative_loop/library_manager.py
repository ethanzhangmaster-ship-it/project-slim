"""Library Manager - 管理winners目录 (DEPRECATED)
Use market_ops.creative_growth_loop.02_performance + 11_memory instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.02_performance + 11_memory")

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from .scoring_engine import ImageScore


@dataclass
class WinnerRecord:
    image_path: str
    score: float
    generation_round: int
    parent_mutation: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_path": self.image_path,
            "score": self.score,
            "generation_round": self.generation_round,
            "parent_mutation": self.parent_mutation,
            "timestamp": self.timestamp,
        }


class LibraryManager:
    SCORE_THRESHOLD = 8.0
    
    def __init__(self, base_dir: str = "output/creative_loop_v2"):
        self.base_dir = Path(base_dir)
        self.winners_dir = self.base_dir / "winners"
        self.manifests_dir = self.base_dir / "manifests"
        self.winners_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_path = self.manifests_dir / "winner_memory.json"

    def promote_winners(self, scores: List[ImageScore], generation_round: int = 1) -> List[WinnerRecord]:
        winners: List[WinnerRecord] = []
        
        for score in scores:
            if score.final_score >= self.SCORE_THRESHOLD:
                record = self._promote_single(score, generation_round)
                if record:
                    winners.append(record)
        
        if winners:
            self._update_winner_memory(winners)
        
        return winners

    def _promote_single(self, score: ImageScore, generation_round: int) -> Optional[WinnerRecord]:
        from datetime import datetime
        
        try:
            filename = score.image_path.name
            dest_path = self.winners_dir / filename
            
            shutil.copy(str(score.image_path), str(dest_path))
            
            mutation_info = self._extract_mutation_info(str(score.image_path))
            
            return WinnerRecord(
                image_path=str(dest_path),
                score=score.final_score,
                generation_round=generation_round,
                parent_mutation=mutation_info,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"Failed to promote {score.image_path}: {e}")
            return None

    def _extract_mutation_info(self, image_path: str) -> str:
        path = Path(image_path)
        parts = path.parent.name.split("_")
        if len(parts) > 1:
            return parts[0]
        return "unknown"

    def _update_winner_memory(self, winners: List[WinnerRecord]) -> None:
        memory = self.load_winner_memory()
        
        for winner in winners:
            memory.append(winner.to_dict())
        
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)

    def load_winner_memory(self) -> List[Dict[str, Any]]:
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def get_previous_winners(self) -> List[str]:
        memory = self.load_winner_memory()
        return [record["image_path"] for record in memory]

    def get_winner_count(self) -> int:
        return len(self.load_winner_memory())

    def get_latest_winners(self, count: int = 10) -> List[Dict[str, Any]]:
        memory = self.load_winner_memory()
        sorted_memory = sorted(memory, key=lambda x: x["timestamp"], reverse=True)
        return sorted_memory[:count]

    def export_library_report(self) -> Path:
        from datetime import datetime
        
        memory = self.load_winner_memory()
        report = {
            "total_winners": len(memory),
            "generations": self._get_generation_summary(memory),
            "latest_winners": self.get_latest_winners(5),
            "exported_at": datetime.now().isoformat(),
        }
        
        report_path = self.manifests_dir / f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report_path

    def _get_generation_summary(self, memory: List[Dict[str, Any]]) -> Dict[int, int]:
        summary: Dict[int, int] = {}
        for record in memory:
            gen = record.get("generation_round", 0)
            summary[gen] = summary.get(gen, 0) + 1
        return summary

    def clear_memory(self) -> None:
        if self.memory_path.exists():
            self.memory_path.unlink()
        
        for file in self.winners_dir.iterdir():
            if file.is_file():
                file.unlink()