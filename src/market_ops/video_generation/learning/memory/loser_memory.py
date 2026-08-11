"""Loser Memory - 失败记忆"""
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class LoserRecord:
    """失败记录"""
    loser_id: str = ""
    pattern: str = ""
    failure_reason: str = ""
    confidence: float = 0.0
    context: str = ""
    count: int = 1
    created_at: str = ""
    last_seen: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "loser_id": self.loser_id,
            "pattern": self.pattern,
            "failure": self.failure_reason,
            "confidence": round(self.confidence, 2),
            "context": self.context,
            "count": self.count,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }


class LoserMemory:
    """失败记忆系统
    
    记录失败模式，避免重复生成失败素材
    """
    
    def __init__(self):
        self._losers: Dict[str, LoserRecord] = {}
        self._counter = 0
    
    def record_failure(
        self,
        pattern: str,
        failure_reason: str,
        confidence: float = 0.0,
        context: str = "",
    ) -> LoserRecord:
        """记录失败"""
        # 检查是否已存在相同模式
        existing = self._find_by_pattern(pattern)
        
        now = datetime.now().isoformat()
        
        if existing:
            existing.count += 1
            existing.confidence = min(1.0, existing.confidence + 0.05)
            existing.last_seen = now
            return existing
        
        # 创建新记录
        self._counter += 1
        loser_id = f"loser_{self._counter:04d}"
        
        record = LoserRecord(
            loser_id=loser_id,
            pattern=pattern,
            failure_reason=failure_reason,
            confidence=confidence,
            context=context,
            count=1,
            created_at=now,
            last_seen=now,
        )
        
        self._losers[loser_id] = record
        return record
    
    def _find_by_pattern(self, pattern: str) -> LoserRecord:
        """查找失败模式"""
        for record in self._losers.values():
            if record.pattern == pattern:
                return record
        return None
    
    def is_forbidden(self, pattern: str, min_confidence: float = 0.70) -> bool:
        """检查是否禁止使用"""
        record = self._find_by_pattern(pattern)
        return record is not None and record.confidence >= min_confidence
    
    def get_forbidden_patterns(self, min_confidence: float = 0.70) -> List[str]:
        """获取禁止使用的模式"""
        return [
            record.pattern
            for record in self._losers.values()
            if record.confidence >= min_confidence
        ]
    
    def get_all_failures(self) -> List[LoserRecord]:
        """获取所有失败记录"""
        return sorted(self._losers.values(), key=lambda r: r.confidence, reverse=True)
    
    def record_demo(self) -> LoserRecord:
        """记录演示数据"""
        return self.record_failure(
            pattern="slow_intro",
            failure_reason="low CTR",
            confidence=0.88,
            context="US iOS",
        )
