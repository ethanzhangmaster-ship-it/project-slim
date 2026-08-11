"""Context Memory - 上下文记忆"""
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class ContextRecord:
    """上下文记录"""
    context_id: str = ""
    country: str = ""
    os: str = ""
    placement: str = ""
    audience: str = ""
    game_genre: str = ""
    winner_dna: Dict[str, str] = None
    confidence: float = 0.0
    created_at: str = ""
    
    def __post_init__(self):
        if self.winner_dna is None:
            self.winner_dna = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "country": self.country,
            "os": self.os,
            "placement": self.placement,
            "audience": self.audience,
            "game_genre": self.game_genre,
            "winner_dna": self.winner_dna,
            "confidence": round(self.confidence, 2),
            "created_at": self.created_at,
        }


class ContextMemory:
    """上下文记忆系统
    
    保存不同环境下的赢家 DNA
    """
    
    def __init__(self):
        self._contexts: Dict[str, ContextRecord] = {}
        self._counter = 0
    
    def save_context(
        self,
        country: str,
        os: str,
        placement: str,
        audience: str,
        game_genre: str,
        winner_dna: Dict[str, str],
        confidence: float = 0.0,
    ) -> ContextRecord:
        """保存上下文"""
        self._counter += 1
        context_id = f"ctx_{self._counter:04d}"
        
        record = ContextRecord(
            context_id=context_id,
            country=country,
            os=os,
            placement=placement,
            audience=audience,
            game_genre=game_genre,
            winner_dna=winner_dna,
            confidence=confidence,
            created_at=datetime.now().isoformat(),
        )
        
        self._contexts[context_id] = record
        return record
    
    def get_context(self, context_id: str) -> ContextRecord:
        """获取上下文"""
        return self._contexts.get(context_id)
    
    def query(
        self,
        country: str = "",
        os: str = "",
        placement: str = "",
        audience: str = "",
        game_genre: str = "",
    ) -> List[ContextRecord]:
        """查询上下文"""
        results = []
        
        for record in self._contexts.values():
            match = True
            
            if country and record.country != country:
                match = False
            if os and record.os != os:
                match = False
            if placement and record.placement != placement:
                match = False
            if audience and audience.lower() not in record.audience.lower():
                match = False
            if game_genre and record.game_genre != game_genre:
                match = False
            
            if match:
                results.append(record)
        
        return sorted(results, key=lambda r: r.confidence, reverse=True)
    
    def get_winner_for_context(
        self,
        country: str,
        os: str,
        placement: str,
        audience: str = "",
        game_genre: str = "",
    ) -> Dict[str, str]:
        """获取指定上下文的赢家 DNA"""
        contexts = self.query(country, os, placement, audience, game_genre)
        
        if contexts:
            return contexts[0].winner_dna
        
        return {}
    
    def save_demo(self) -> ContextRecord:
        """保存演示数据"""
        return self.save_context(
            country="US",
            os="iOS",
            placement="Facebook Feed",
            audience="Female 25-44",
            game_genre="Puzzle",
            winner_dna={
                "hook": "reward_reveal",
                "camera": "close_up",
                "lighting": "warm",
            },
            confidence=0.92,
        )
