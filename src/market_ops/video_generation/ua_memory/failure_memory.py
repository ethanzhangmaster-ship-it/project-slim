from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class FailureRecord:
    failure_id: str
    creative_id: str
    campaign_id: str
    platform: str
    reason: str
    failure_type: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    is_blacklisted: bool = False


class FailureMemory:
    def __init__(self):
        self.records: Dict[str, FailureRecord] = {}
        self.failure_patterns: Dict[str, int] = {}

    def add(self, record: FailureRecord) -> None:
        self.records[record.failure_id] = record
        
        pattern_key = f"{record.platform}_{record.failure_type}"
        self.failure_patterns[pattern_key] = self.failure_patterns.get(pattern_key, 0) + 1

    def get(self, failure_id: str) -> Optional[FailureRecord]:
        return self.records.get(failure_id)

    def get_failures_by_type(self, failure_type: str) -> List[FailureRecord]:
        return [r for r in self.records.values() if r.failure_type == failure_type]

    def get_patterns(self) -> Dict[str, int]:
        return dict(sorted(self.failure_patterns.items(), key=lambda x: x[1], reverse=True))

    def should_blacklist(self, creative_id: str, platform: str) -> bool:
        failures = [
            r for r in self.records.values()
            if r.creative_id == creative_id and r.platform == platform
        ]
        
        if len(failures) >= 3:
            return True
        
        critical_failures = [r for r in failures if r.failure_type == "policy_violation"]
        if critical_failures:
            return True
        
        return False

    def add_demo(self) -> FailureRecord:
        record = FailureRecord(
            failure_id="failure_0001",
            creative_id="creative_bad_001",
            campaign_id="campaign_002",
            platform="meta",
            reason="CTR -40%, spend $300 with 0 purchases",
            failure_type="performance",
            metrics={"spend": 300, "purchases": 0, "ctr": 0.01},
            is_blacklisted=True,
        )
        self.add(record)
        return record
