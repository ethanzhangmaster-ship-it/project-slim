"""Creative Store Alignment - 创意商店对齐"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class AlignmentResult:
    """对齐结果"""
    creative_id: str = ""
    app_id: str = ""
    alignment_score: float = 0.0
    cvr_loss_estimate: float = 0.0
    mismatch_detected: bool = False
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "app_id": self.app_id,
            "alignment_score": round(self.alignment_score, 2),
            "cvr_loss_estimate": round(self.cvr_loss_estimate, 2),
            "mismatch_detected": self.mismatch_detected,
            "recommendations": self.recommendations,
        }


class CreativeStoreAligner:
    """创意商店对齐器"""
    
    def check_alignment(
        self,
        creative_dna: Dict[str, str],
        store_data: Dict[str, Any],
        creative_id: str = "",
        app_id: str = "",
    ) -> AlignmentResult:
        """检查对齐"""
        # 提取创意关键词
        creative_text = " ".join(creative_dna.values()).lower()
        
        # 提取商店关键词
        store_text = " ".join(
            [
                store_data.get("title", ""),
                store_data.get("subtitle", ""),
                store_data.get("description", ""),
                " ".join(store_data.get("keywords", [])),
            ]
        ).lower()
        
        # 计算对齐分数
        alignment_score = self._calculate_alignment(creative_text, store_text)
        
        # 检测不匹配
        mismatch_detected = alignment_score < 0.5
        
        # 估计 CVR 损失
        cvr_loss = self._estimate_cvr_loss(alignment_score)
        
        # 生成建议
        recommendations = self._generate_recommendations(creative_dna, store_data, alignment_score)
        
        return AlignmentResult(
            creative_id=creative_id,
            app_id=app_id,
            alignment_score=alignment_score,
            cvr_loss_estimate=cvr_loss,
            mismatch_detected=mismatch_detected,
            recommendations=recommendations,
        )
    
    def _calculate_alignment(self, creative_text: str, store_text: str) -> float:
        """计算对齐分数"""
        creative_words = set(creative_text.split())
        store_words = set(store_text.split())
        
        if not creative_words:
            return 0.0
        
        # 计算匹配词数
        matched = len(creative_words & store_words)
        
        return matched / len(creative_words)
    
    def _estimate_cvr_loss(self, alignment_score: float) -> float:
        """估计 CVR 损失"""
        if alignment_score >= 0.7:
            return 0.05
        
        if alignment_score >= 0.5:
            return 0.12
        
        if alignment_score >= 0.3:
            return 0.22
        
        return 0.35
    
    def _generate_recommendations(self, creative_dna: Dict[str, str], store_data: Dict[str, Any], alignment_score: float) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if alignment_score < 0.7:
            recommendations.append("Update store screenshots to match creative visuals")
        
        if alignment_score < 0.5:
            recommendations.append("Update app title/subtitle to include creative keywords")
            recommendations.append("Revise description to match creative messaging")
        
        return recommendations
    
    def check_alignment_demo(self) -> AlignmentResult:
        """演示对齐检查"""
        creative_dna = {
            "hook": "merge dragon magic adventure",
            "genre": "Puzzle",
            "emotion": "excitement",
        }
        
        store_data = {
            "title": "Puzzle Brain Relax",
            "subtitle": "Brain Training",
            "description": "Train your brain with relaxing puzzles.",
            "keywords": ["puzzle", "brain", "relax", "training"],
        }
        
        return self.check_alignment(creative_dna, store_data, "creative_001", "com.example.game")
