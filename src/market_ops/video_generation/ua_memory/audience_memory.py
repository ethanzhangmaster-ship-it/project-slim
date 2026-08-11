from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AudienceRecord:
    segment_id: str
    country: str
    gender: str
    age_range: str
    os: str = ""
    game_genre: str = ""
    match_score: float = 0.0
    historical_success: float = 0.0
    best_creatives: List[str] = field(default_factory=list)
    last_used: Optional[datetime] = None


class AudienceMemory:
    def __init__(self):
        self.records: Dict[str, AudienceRecord] = {}

    def add(self, record: AudienceRecord) -> None:
        self.records[record.segment_id] = record

    def get(self, segment_id: str) -> Optional[AudienceRecord]:
        return self.records.get(segment_id)

    def get_matching_segments(self, creative_dna: Dict[str, str]) -> List[AudienceRecord]:
        weights = {
            "cute": 0.9,
            "creature": 0.85,
            "merge": 0.9,
            "surprise": 0.8,
            "reward": 0.75,
            "magic": 0.8,
            "adventure": 0.7,
            "fast_action": 0.85,
            "close_up": 0.7,
        }
        
        results = []
        for record in self.records.values():
            score = 0.0
            for dna_key, dna_value in creative_dna.items():
                score += weights.get(dna_value, 0.3) * 0.25
            record.match_score = round(score, 2)
            results.append(record)
        
        return sorted(results, key=lambda r: r.match_score, reverse=True)

    def get_best_segments(self, platform: str) -> List[AudienceRecord]:
        platform_segments = {
            "meta": ["US_Female_25-34", "US_Female_35-44", "DE_Female_25-34"],
            "google": ["US_Male_18-24", "US_Female_18-34"],
            "tiktok": ["US_Female_18-24", "JP_Female_18-24"],
            "asa": ["US_Female_25-34", "US_Male_25-34"],
        }
        
        segments = platform_segments.get(platform, [])
        return [r for r in self.records.values() if r.segment_id in segments]

    def add_demo(self) -> AudienceRecord:
        record = AudienceRecord(
            segment_id="US_Female_25-34",
            country="US",
            gender="female",
            age_range="25-34",
            os="iOS",
            game_genre="casual",
            match_score=0.91,
            historical_success=0.73,
            best_creatives=["creative_A", "creative_C"],
        )
        self.add(record)
        return record
