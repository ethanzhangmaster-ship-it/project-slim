"""Strategy Memory - 策略记忆"""
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class StrategyRecord:
    """策略记录"""
    strategy_id: str = ""
    context: str = ""
    winner_dna: Dict[str, str] = None
    confidence: float = 0.0
    performance: Dict[str, Any] = None
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if self.winner_dna is None:
            self.winner_dna = {}
        if self.performance is None:
            self.performance = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "context": self.context,
            "winner": self.winner_dna,
            "confidence": round(self.confidence, 2),
            "performance": self.performance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class StrategyMemory:
    """策略记忆系统
    
    升级 V4.5 winner_memory，保存成功策略
    """
    
    def __init__(self):
        self._strategies: Dict[str, StrategyRecord] = {}
        self._counter = 0
    
    def save_strategy(
        self,
        context: str,
        winner_dna: Dict[str, str],
        confidence: float = 0.0,
        performance: Dict[str, Any] = None,
    ) -> StrategyRecord:
        """保存策略"""
        self._counter += 1
        strategy_id = f"strategy_{self._counter:04d}"
        
        now = datetime.now().isoformat()
        
        record = StrategyRecord(
            strategy_id=strategy_id,
            context=context,
            winner_dna=winner_dna,
            confidence=confidence,
            performance=performance or {},
            created_at=now,
            updated_at=now,
        )
        
        self._strategies[strategy_id] = record
        return record
    
    def get_strategy(self, strategy_id: str) -> StrategyRecord:
        """获取策略"""
        return self._strategies.get(strategy_id)
    
    def get_by_context(self, context: str) -> List[StrategyRecord]:
        """按上下文获取策略"""
        return [
            s for s in self._strategies.values()
            if context.lower() in s.context.lower()
        ]
    
    def get_top_strategies(self, limit: int = 5, min_confidence: float = 0.70) -> List[StrategyRecord]:
        """获取最佳策略"""
        filtered = [
            s for s in self._strategies.values()
            if s.confidence >= min_confidence
        ]
        
        return sorted(filtered, key=lambda s: s.confidence, reverse=True)[:limit]
    
    def update_strategy(self, strategy_id: str, **kwargs) -> StrategyRecord:
        """更新策略"""
        if strategy_id not in self._strategies:
            return None
        
        record = self._strategies[strategy_id]
        
        if "confidence" in kwargs:
            record.confidence = kwargs["confidence"]
        if "performance" in kwargs:
            record.performance = kwargs["performance"]
        if "winner_dna" in kwargs:
            record.winner_dna = kwargs["winner_dna"]
        
        record.updated_at = datetime.now().isoformat()
        return record
    
    def save_demo(self) -> StrategyRecord:
        """保存演示数据"""
        return self.save_strategy(
            context="US iOS Puzzle",
            winner_dna={
                "hook": "instant_reward",
                "camera": "close_up",
                "lighting": "warm",
                "emotion": "surprise",
            },
            confidence=0.94,
            performance={"roas": 2.3, "ctr": 5.8},
        )
