"""Segment Memory - 细分记忆"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class SegmentRecord:
    """细分记录"""
    segment_id: str = ""
    audience_id: str = ""
    creative_ids: List[str] = None
    performance: Dict[str, float] = None
    match_score: float = 0.0
    last_updated: str = ""
    
    def __post_init__(self):
        if self.creative_ids is None:
            self.creative_ids = []
        if self.performance is None:
            self.performance = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "audience_id": self.audience_id,
            "creative_count": len(self.creative_ids),
            "performance": {k: round(v, 2) for k, v in self.performance.items()},
            "match_score": round(self.match_score, 2),
            "last_updated": self.last_updated,
        }


class SegmentMemory:
    """细分记忆系统"""
    
    def __init__(self):
        self._segments: Dict[str, SegmentRecord] = {}
        self._counter = 0
    
    def add_segment(
        self,
        audience_id: str,
        creative_ids: List[str] = None,
        performance: Dict[str, float] = None,
        match_score: float = 0.0,
    ) -> SegmentRecord:
        """添加细分"""
        self._counter += 1
        segment_id = f"segment_{self._counter:04d}"
        
        record = SegmentRecord(
            segment_id=segment_id,
            audience_id=audience_id,
            creative_ids=creative_ids or [],
            performance=performance or {},
            match_score=match_score,
            last_updated="2024-01-15T10:00:00",
        )
        
        self._segments[segment_id] = record
        return record
    
    def get_segment(self, segment_id: str) -> SegmentRecord:
        """获取细分"""
        return self._segments.get(segment_id, SegmentRecord(segment_id=segment_id))
    
    def get_by_audience(self, audience_id: str) -> List[SegmentRecord]:
        """按受众获取细分"""
        return [
            s for s in self._segments.values()
            if s.audience_id == audience_id
        ]
    
    def get_top_segments(self, limit: int = 5) -> List[SegmentRecord]:
        """获取最佳细分"""
        return sorted(
            self._segments.values(),
            key=lambda s: s.match_score,
            reverse=True
        )[:limit]
    
    def update_segment(self, segment_id: str, **kwargs) -> SegmentRecord:
        """更新细分"""
        if segment_id not in self._segments:
            return None
        
        record = self._segments[segment_id]
        
        if "performance" in kwargs:
            record.performance.update(kwargs["performance"])
        if "match_score" in kwargs:
            record.match_score = kwargs["match_score"]
        if "creative_ids" in kwargs:
            record.creative_ids.extend(kwargs["creative_ids"])
        
        record.last_updated = "2024-01-15T10:00:00"
        return record
    
    def add_demo(self) -> SegmentRecord:
        """添加演示数据"""
        return self.add_segment(
            audience_id="US_Female_30-44",
            creative_ids=["creative_001", "creative_002"],
            performance={"ctr": 5.8, "cvr": 4.2, "roas": 1.8},
            match_score=0.91,
        )
