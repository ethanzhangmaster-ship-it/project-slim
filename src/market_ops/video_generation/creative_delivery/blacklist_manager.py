from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class BlacklistRecord:
    creative_id: str
    reason: str
    platform: str
    blacklisted_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True


class BlacklistManager:
    def __init__(self):
        self.blacklist: Dict[str, BlacklistRecord] = {}

    def add(self, creative_id: str, reason: str, platform: str, expires_at: Optional[datetime] = None) -> BlacklistRecord:
        record = BlacklistRecord(
            creative_id=creative_id,
            reason=reason,
            platform=platform,
            expires_at=expires_at,
        )
        self.blacklist[creative_id] = record
        return record

    def remove(self, creative_id: str) -> bool:
        if creative_id in self.blacklist:
            self.blacklist[creative_id].is_active = False
            return True
        return False

    def is_blacklisted(self, creative_id: str, platform: str = "") -> bool:
        record = self.blacklist.get(creative_id)
        if not record or not record.is_active:
            return False
        if platform and record.platform != platform:
            return False
        if record.expires_at and record.expires_at < datetime.now():
            record.is_active = False
            return False
        return True

    def get_blacklisted(self, platform: str = "") -> List[BlacklistRecord]:
        results = []
        for record in self.blacklist.values():
            if not record.is_active:
                continue
            if platform and record.platform != platform:
                continue
            if record.expires_at and record.expires_at < datetime.now():
                record.is_active = False
                continue
            results.append(record)
        return results

    def add_demo(self) -> BlacklistRecord:
        return self.add("creative_bad_001", "Policy violation: copyright", "meta")
