"""Winner Engine - V15素材增长闭环"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..01_collectors.facebook_ads_collector import CreativePerformance


@dataclass
class Winner:
    creative_id: str
    image_path: str
    ctr: float
    ipm: float
    roas_d1: float
    roas_d7: float
    win_score: float
    win_reasons: List[str]
    project: str
    date: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "image_path": self.image_path,
            "ctr": self.ctr,
            "ipm": self.ipm,
            "roas_d1": self.roas_d1,
            "roas_d7": self.roas_d7,
            "win_score": self.win_score,
            "win_reasons": self.win_reasons,
            "project": self.project,
            "date": self.date,
        }


class WinnerEngine:
    CTR_TOP_PCT = 0.10
    IPM_TOP_PCT = 0.10
    ROAS_TOP_PCT = 0.20
    
    WINNER_POOL_PATH = "winner_pool"
    WINNER_MEMORY_PATH = "memory/winner_pool.json"
    
    def __init__(self, winner_pool_path: str = None):
        self.winner_pool_path = Path(winner_pool_path or self.WINNER_POOL_PATH)
        self.winner_pool_path.mkdir(parents=True, exist_ok=True)
        
        self.memory_path = Path(self.WINNER_MEMORY_PATH)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    def select_winners(self, performances: List[CreativePerformance],
                       image_dir: str = None) -> List[Winner]:
        """从表现数据中选择赢家"""
        if not performances:
            return []
        
        winners = []
        
        ctr_sorted = sorted(performances, key=lambda x: x.ctr, reverse=True)
        ctr_top = ctr_sorted[:int(len(ctr_sorted) * self.CTR_TOP_PCT)]
        
        ipm_sorted = sorted(performances, key=lambda x: x.ipm, reverse=True)
        ipm_top = ipm_sorted[:int(len(ipm_sorted) * self.IPM_TOP_PCT)]
        
        roas_sorted = sorted(performances, key=lambda x: x.roas_d1, reverse=True)
        roas_top = roas_sorted[:int(len(roas_sorted) * self.ROAS_TOP_PCT)]
        
        top_set = set()
        for perf in ctr_top + ipm_top + roas_top:
            top_set.add(perf.creative_id)
        
        for perf in performances:
            if perf.creative_id in top_set:
                win_score = self._calculate_win_score(perf)
                win_reasons = self._get_win_reasons(perf, ctr_top, ipm_top, roas_top)
                
                image_path = self._find_image(perf.creative_id, image_dir)
                
                winner = Winner(
                    creative_id=perf.creative_id,
                    image_path=image_path,
                    ctr=perf.ctr,
                    ipm=perf.ipm,
                    roas_d1=perf.roas_d1,
                    roas_d7=perf.roas_d7,
                    win_score=win_score,
                    win_reasons=win_reasons,
                    project=perf.project,
                    date=perf.date,
                )
                winners.append(winner)
        
        winners = sorted(winners, key=lambda x: x.win_score, reverse=True)
        
        self._save_winners(winners)
        self._copy_to_winner_pool(winners, image_dir)
        
        return winners
    
    def _calculate_win_score(self, perf: CreativePerformance) -> float:
        """计算赢家分数"""
        ctr_score = min(perf.ctr * 100, 10)
        ipm_score = min(perf.ipm / 10, 10)
        roas_score = min(perf.roas_d1 * 2, 10)
        
        return (ctr_score + ipm_score + roas_score) / 3
    
    def _get_win_reasons(self, perf: CreativePerformance, 
                         ctr_top: List, ipm_top: List, roas_top: List) -> List[str]:
        """获取赢家的原因"""
        reasons = []
        
        if perf in ctr_top:
            reasons.append(f"CTR Top 10%: {perf.ctr:.2%}")
        if perf in ipm_top:
            reasons.append(f"IPM Top 10%: {perf.ipm:.2f}")
        if perf in roas_top:
            reasons.append(f"ROAS Top 20%: {perf.roas_d1:.2f}")
        
        return reasons
    
    def _find_image(self, creative_id: str, image_dir: str = None) -> str:
        """查找素材图片"""
        if not image_dir:
            return ""
        
        image_dir = Path(image_dir)
        
        patterns = [
            f"{creative_id}.png",
            f"{creative_id}.jpg",
            f"*{creative_id}*",
        ]
        
        for pattern in patterns:
            matches = list(image_dir.glob(pattern))
            if matches:
                return str(matches[0])
        
        return ""
    
    def _save_winners(self, winners: List[Winner]) -> None:
        """保存赢家到记忆"""
        memory = self._load_memory()
        
        for winner in winners:
            memory[winner.creative_id] = winner.to_dict()
        
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    
    def _load_memory(self) -> Dict[str, Any]:
        """加载记忆"""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _copy_to_winner_pool(self, winners: List[Winner], image_dir: str = None) -> None:
        """复制赢家图片到winner_pool"""
        for winner in winners:
            if winner.image_path and Path(winner.image_path).exists():
                dest = self.winner_pool_path / f"{winner.creative_id}.png"
                shutil.copy(winner.image_path, str(dest))
    
    def get_top_winner(self) -> Optional[Winner]:
        """获取Top赢家"""
        memory = self._load_memory()
        
        if not memory:
            return None
        
        sorted_winners = sorted(memory.values(), key=lambda x: x["win_score"], reverse=True)
        top = sorted_winners[0]
        
        return Winner(
            creative_id=top["creative_id"],
            image_path=top["image_path"],
            ctr=top["ctr"],
            ipm=top["ipm"],
            roas_d1=top["roas_d1"],
            roas_d7=top["roas_d7"],
            win_score=top["win_score"],
            win_reasons=top["win_reasons"],
            project=top["project"],
            date=top["date"],
        )
    
    def get_winners_by_project(self, project: str) -> List[Winner]:
        """按项目获取赢家"""
        memory = self._load_memory()
        
        winners = []
        for data in memory.values():
            if data["project"] == project:
                winners.append(Winner(
                    creative_id=data["creative_id"],
                    image_path=data["image_path"],
                    ctr=data["ctr"],
                    ipm=data["ipm"],
                    roas_d1=data["roas_d1"],
                    roas_d7=data["roas_d7"],
                    win_score=data["win_score"],
                    win_reasons=data["win_reasons"],
                    project=data["project"],
                    date=data["date"],
                ))
        
        return sorted(winners, key=lambda x: x.win_score, reverse=True)