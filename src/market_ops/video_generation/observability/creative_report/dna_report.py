"""DNA Report - 赢家 DNA 模式提取"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import Counter


@dataclass
class DNAPattern:
    """DNA 模式"""
    element: str = ""
    value: str = ""
    frequency: float = 0.0
    avg_ctr: float = 0.0
    count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "element": self.element,
            "value": self.value,
            "frequency": round(self.frequency, 1),
            "avg_ctr": round(self.avg_ctr, 2),
            "count": self.count,
        }


@dataclass
class WinnerDNA:
    """赢家 DNA 报告"""
    total_winners: int = 0
    patterns: List[DNAPattern] = field(default_factory=list)
    top_elements: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_winners": self.total_winners,
            "patterns": [p.to_dict() for p in self.patterns],
            "top_elements": self.top_elements,
        }


class DNAExtractor:
    """DNA 模式提取器"""
    
    # DNA 元素定义
    DNA_ELEMENTS = ["camera", "lighting", "hook", "cta", "mood", "pace"]
    
    def __init__(self):
        self._winners: List[Dict[str, Any]] = []
    
    def add_winner(self, winner: Dict[str, Any]):
        """添加 winner 数据"""
        self._winners.append(winner)
    
    def extract_patterns(self) -> WinnerDNA:
        """提取赢家 DNA 模式"""
        if not self._winners:
            return WinnerDNA()
        
        patterns = []
        top_elements = {}
        
        for element in self.DNA_ELEMENTS:
            element_values = []
            element_ctrs = []
            
            for winner in self._winners:
                dna = winner.get("dna", {})
                if element in dna and dna[element]:
                    element_values.append(dna[element])
                    element_ctrs.append(winner.get("ctr", 0.0))
            
            if element_values:
                # 统计最常见值
                counter = Counter(element_values)
                most_common = counter.most_common(1)[0]
                
                # 计算频率
                frequency = (most_common[1] / len(element_values)) * 100
                
                # 计算平均 CTR
                avg_ctr = sum(element_ctrs) / len(element_ctrs) if element_ctrs else 0.0
                
                patterns.append(DNAPattern(
                    element=element,
                    value=most_common[0],
                    frequency=frequency,
                    avg_ctr=avg_ctr,
                    count=most_common[1],
                ))
                
                top_elements[element] = most_common[0]
        
        return WinnerDNA(
            total_winners=len(self._winners),
            patterns=sorted(patterns, key=lambda p: p.frequency, reverse=True),
            top_elements=top_elements,
        )
    
    def generate_report_text(self, dna: WinnerDNA) -> str:
        """生成文本报告"""
        lines = [
            "=== Winner DNA Pattern ===",
            f"",
            f"Total Winners Analyzed: {dna.total_winners}",
            f"",
            f"Top Patterns:",
        ]
        
        for p in dna.patterns:
            lines.append(
                f"  {p.element.capitalize()}: {p.value} "
                f"({p.frequency:.0f}% of winners, avg CTR {p.avg_ctr:.1f}%)"
            )
        
        return "\n".join(lines)
    
    def generate_demo(self) -> WinnerDNA:
        """生成演示数据"""
        winners = [
            {"dna": {"camera": "close-up", "lighting": "warm", "hook": "action"}, "ctr": 5.8},
            {"dna": {"camera": "close-up", "lighting": "warm", "hook": "action"}, "ctr": 4.2},
            {"dna": {"camera": "close-up", "lighting": "cool", "hook": "reveal"}, "ctr": 3.9},
            {"dna": {"camera": "medium", "lighting": "warm", "hook": "action"}, "ctr": 4.5},
            {"dna": {"camera": "close-up", "lighting": "warm", "hook": "action"}, "ctr": 5.1},
        ]
        
        for w in winners:
            self.add_winner(w)
        
        return self.extract_patterns()
