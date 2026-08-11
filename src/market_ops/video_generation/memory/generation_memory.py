"""Generation Memory"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class GenerationRecord:
    record_id: str = ""
    blueprint_id: str = ""
    scene_id: str = ""
    prompt: Dict[str, Any] = field(default_factory=dict)
    prompt_dna: str = ""
    platform: str = ""
    video_url: str = ""
    quality_score: float = 0.0
    ctr: float = 0.0
    conversions: int = 0
    views: int = 0
    is_winner: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GenerationMemory:
    """生成记忆系统"""

    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            memory_dir = Path(__file__).resolve().parent / "records"
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, GenerationRecord] = {}
        self._load_records()

    def _load_records(self):
        for record_file in self.memory_dir.glob("*.json"):
            with open(record_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            record = GenerationRecord(**data)
            self._records[record.record_id] = record

    def _save_record(self, record: GenerationRecord):
        record_path = self.memory_dir / f"{record.record_id}.json"
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)

    def add_record(self, record: GenerationRecord):
        if not record.record_id:
            record.record_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if record.ctr >= 3.0:
            record.is_winner = True
        self._records[record.record_id] = record
        self._save_record(record)

    def get_record(self, record_id: str) -> Optional[GenerationRecord]:
        return self._records.get(record_id)

    def search_by_dna(self, prompt_dna: str) -> List[GenerationRecord]:
        results = []
        for record in self._records.values():
            if record.prompt_dna == prompt_dna:
                results.append(record)
        return sorted(results, key=lambda r: r.ctr, reverse=True)

    def get_winners(self, limit: int = 10) -> List[GenerationRecord]:
        winners = [r for r in self._records.values() if r.is_winner]
        return sorted(winners, key=lambda r: r.ctr, reverse=True)[:limit]

    def get_best_by_platform(self, platform: str, limit: int = 5) -> List[GenerationRecord]:
        records = [r for r in self._records.values() if r.platform == platform]
        return sorted(records, key=lambda r: r.ctr, reverse=True)[:limit]

    def update_performance(self, record_id: str, ctr: float, views: int = 0, conversions: int = 0):
        if record_id in self._records:
            record = self._records[record_id]
            record.ctr = ctr
            record.views = views
            record.conversions = conversions
            if ctr >= 3.0:
                record.is_winner = True
            self._save_record(record)

    def get_stats(self) -> Dict[str, Any]:
        records = list(self._records.values())
        if not records:
            return {"total_records": 0}

        platform_stats = {}
        for record in records:
            if record.platform not in platform_stats:
                platform_stats[record.platform] = {"count": 0, "avg_ctr": 0}
            platform_stats[record.platform]["count"] += 1
            platform_stats[record.platform]["avg_ctr"] += record.ctr

        for p in platform_stats:
            platform_stats[p]["avg_ctr"] = round(
                platform_stats[p]["avg_ctr"] / platform_stats[p]["count"], 2
            )

        return {
            "total_records": len(records),
            "winners": sum(1 for r in records if r.is_winner),
            "avg_ctr": round(sum(r.ctr for r in records) / len(records), 2),
            "platform_stats": platform_stats,
        }
