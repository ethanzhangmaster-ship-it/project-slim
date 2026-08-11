"""Winner Report - 创意赢家报告"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class WinnerEntry:
    """单个 Winner 记录"""
    rank: int = 0
    creative_id: str = ""
    dna: str = ""
    prompt: str = ""
    hook: str = ""
    camera: str = ""
    platform: str = ""
    ctr: float = 0.0
    purchase_rate: float = 0.0
    qa_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "creative_id": self.creative_id,
            "dna": self.dna,
            "prompt": self.prompt,
            "hook": self.hook,
            "camera": self.camera,
            "platform": self.platform,
            "ctr": round(self.ctr, 2),
            "purchase_rate": round(self.purchase_rate, 2),
            "qa_score": round(self.qa_score, 1),
        }


class WinnerReporter:
    """赢家报告生成器"""
    
    def __init__(self):
        self._winners: List[WinnerEntry] = []
    
    def add_winner(self, entry: WinnerEntry):
        """添加 winner"""
        self._winners.append(entry)
    
    def generate_report(self, limit: int = 10) -> List[WinnerEntry]:
        """生成赢家报告"""
        sorted_winners = sorted(
            self._winners,
            key=lambda w: w.ctr * 0.5 + w.purchase_rate * 0.3 + w.qa_score * 0.02,
            reverse=True,
        )
        
        for i, w in enumerate(sorted_winners[:limit]):
            w.rank = i + 1
        
        return sorted_winners[:limit]
    
    def generate_text_report(self, limit: int = 10) -> str:
        """生成文本报告"""
        winners = self.generate_report(limit)
        
        lines = [
            "=== TOP Creative DNA ===",
            "",
        ]
        
        for w in winners:
            lines.extend([
                f"Rank {w.rank}",
                f"",
                f"  Prompt: {w.prompt}",
                f"  Hook: {w.hook}",
                f"  Camera: {w.camera}",
                f"  Platform: {w.platform}",
                f"  CTR: {w.ctr}%",
                f"  Purchase: {w.purchase_rate}%",
                f"  QA: {w.qa_score}",
                f"",
            ])
        
        return "\n".join(lines)
    
    def generate_demo(self) -> List[WinnerEntry]:
        """生成演示数据"""
        entries = [
            WinnerEntry(
                creative_id="video_001",
                dna="witch treasure opening",
                prompt="witch treasure opening",
                hook="Fast Zoom",
                camera="Close Up",
                platform="Kling",
                ctr=5.8,
                purchase_rate=4.1,
                qa_score=92,
            ),
            WinnerEntry(
                creative_id="video_002",
                dna="battle scene epic",
                prompt="epic battle scene",
                hook="Slow Motion",
                camera="Wide Shot",
                platform="Veo",
                ctr=4.2,
                purchase_rate=2.8,
                qa_score=88,
            ),
            WinnerEntry(
                creative_id="video_003",
                dna="character reveal surprise",
                prompt="surprise character reveal",
                hook="Reveal",
                camera="Medium Shot",
                platform="Kling",
                ctr=3.9,
                purchase_rate=2.5,
                qa_score=85,
            ),
        ]
        
        for e in entries:
            self.add_winner(e)
        
        return self.generate_report()
