"""Loser Engine - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from ..01_collectors.facebook_ads_collector import CreativePerformance


@dataclass
class Loser:
    creative_id: str
    image_path: str
    ctr: float
    ipm: float
    roas_d1: float
    lose_score: float
    lose_reasons: List[str]
    project: str
    date: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "image_path": self.image_path,
            "ctr": self.ctr,
            "ipm": self.ipm,
            "roas_d1": self.roas_d1,
            "lose_score": self.lose_score,
            "lose_reasons": self.lose_reasons,
            "project": self.project,
            "date": self.date,
        }


class LoserEngine:
    LOSER_POOL_PATH = "loser_pool"
    LOSER_MEMORY_PATH = "memory/loser_pool.json"
    
    CTR_BOTTOM_PCT = 0.20
    IPM_BOTTOM_PCT = 0.20
    ROAS_BOTTOM_PCT = 0.30
    
    def __init__(self, loser_pool_path: str = None):
        self.loser_pool_path = Path(loser_pool_path or self.LOSER_POOL_PATH)
        self.loser_pool_path.mkdir(parents=True, exist_ok=True)
        
        self.memory_path = Path(self.LOSER_MEMORY_PATH)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    def select_losers(self, performances: List[CreativePerformance]) -> List[Loser]:
        """选择失败素材"""
        if not performances:
            return []
        
        losers = []
        
        ctr_sorted = sorted(performances, key=lambda x: x.ctr)
        ctr_bottom = ctr_sorted[:int(len(ctr_sorted) * self.CTR_BOTTOM_PCT)]
        
        ipm_sorted = sorted(performances, key=lambda x: x.ipm)
        ipm_bottom = ipm_sorted[:int(len(ipm_sorted) * self.IPM_BOTTOM_PCT)]
        
        roas_sorted = sorted(performances, key=lambda x: x.roas_d1)
        roas_bottom = roas_sorted[:int(len(roas_sorted) * self.ROAS_BOTTOM_PCT)]
        
        bottom_set = set()
        for perf in ctr_bottom + ipm_bottom + roas_bottom:
            bottom_set.add(perf.creative_id)
        
        for perf in performances:
            if perf.creative_id in bottom_set:
                lose_score = self._calculate_lose_score(perf)
                lose_reasons = self._get_lose_reasons(perf, ctr_bottom, ipm_bottom, roas_bottom)
                
                loser = Loser(
                    creative_id=perf.creative_id,
                    image_path="",
                    ctr=perf.ctr,
                    ipm=perf.ipm,
                    roas_d1=perf.roas_d1,
                    lose_score=lose_score,
                    lose_reasons=lose_reasons,
                    project=perf.project,
                    date=perf.date,
                )
                losers.append(loser)
        
        self._save_losers(losers)
        return losers
    
    def _calculate_lose_score(self, perf: CreativePerformance) -> float:
        """计算失败分数"""
        ctr_penalty = max(0, 5 - perf.ctr * 100)
        ipm_penalty = max(0, 5 - perf.ipm / 10)
        roas_penalty = max(0, 5 - perf.roas_d1 * 2)
        
        return (ctr_penalty + ipm_penalty + roas_penalty) / 3
    
    def _get_lose_reasons(self, perf: CreativePerformance,
                          ctr_bottom: List, ipm_bottom: List, roas_bottom: List) -> List[str]:
        """获取失败原因"""
        reasons = []
        
        if perf in ctr_bottom:
            reasons.append(f"CTR Bottom 20%: {perf.ctr:.2%}")
        if perf in ipm_bottom:
            reasons.append(f"IPM Bottom 20%: {perf.ipm:.2f}")
        if perf in roas_bottom:
            reasons.append(f"ROAS Bottom 30%: {perf.roas_d1:.2f}")
        
        return reasons
    
    def _save_losers(self, losers: List[Loser]) -> None:
        """保存失败素材到记忆"""
        memory = self._load_memory()
        
        for loser in losers:
            memory[loser.creative_id] = loser.to_dict()
        
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    
    def _load_memory(self) -> Dict[str, Any]:
        """加载记忆"""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def is_known_loser(self, creative_id: str) -> bool:
        """检查是否已知失败素材"""
        memory = self._load_memory()
        return creative_id in memory
    
    def get_loser_patterns(self) -> Dict[str, int]:
        """获取失败模式统计"""
        memory = self._load_memory()
        
        patterns = {}
        for loser_data in memory.values():
            for reason in loser_data.get("lose_reasons", []):
                key = reason.split(":")[0]
                patterns[key] = patterns.get(key, 0) + 1
        
        return patterns