"""Screenshot DNA - 截图 DNA"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ScreenshotDNA:
    """截图 DNA"""
    screenshot_id: str = ""
    visuals: List[str] = None
    colors: List[str] = None
    text: List[str] = None
    themes: List[str] = None
    emotions: List[str] = None
    
    def __post_init__(self):
        if self.visuals is None:
            self.visuals = []
        if self.colors is None:
            self.colors = []
        if self.text is None:
            self.text = []
        if self.themes is None:
            self.themes = []
        if self.emotions is None:
            self.emotions = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "screenshot_id": self.screenshot_id,
            "visuals": self.visuals,
            "colors": self.colors,
            "text": self.text,
            "themes": self.themes,
            "emotions": self.emotions,
        }


class ScreenshotDNAAnalyzer:
    """截图 DNA 分析器"""
    
    def extract(self, screenshot_id: str, image_data: Dict[str, Any]) -> ScreenshotDNA:
        """提取截图 DNA"""
        return ScreenshotDNA(
            screenshot_id=screenshot_id,
            visuals=image_data.get("visuals", []),
            colors=image_data.get("colors", []),
            text=image_data.get("text", []),
            themes=image_data.get("themes", []),
            emotions=image_data.get("emotions", []),
        )
    
    def compare(self, dna1: ScreenshotDNA, dna2: ScreenshotDNA) -> float:
        """比较两个截图 DNA"""
        similarity = 0.0
        total_elements = 0
        
        # 视觉相似性
        common_visuals = set(dna1.visuals) & set(dna2.visuals)
        if dna1.visuals or dna2.visuals:
            similarity += len(common_visuals) / max(len(dna1.visuals), len(dna2.visuals)) * 0.3
            total_elements += 0.3
        
        # 颜色相似性
        common_colors = set(dna1.colors) & set(dna2.colors)
        if dna1.colors or dna2.colors:
            similarity += len(common_colors) / max(len(dna1.colors), len(dna2.colors)) * 0.2
            total_elements += 0.2
        
        # 主题相似性
        common_themes = set(dna1.themes) & set(dna2.themes)
        if dna1.themes or dna2.themes:
            similarity += len(common_themes) / max(len(dna1.themes), len(dna2.themes)) * 0.3
            total_elements += 0.3
        
        # 情感相似性
        common_emotions = set(dna1.emotions) & set(dna2.emotions)
        if dna1.emotions or dna2.emotions:
            similarity += len(common_emotions) / max(len(dna1.emotions), len(dna2.emotions)) * 0.2
            total_elements += 0.2
        
        return similarity / total_elements if total_elements > 0 else 0.0
    
    def extract_demo(self) -> ScreenshotDNA:
        """演示提取截图 DNA"""
        image_data = {
            "visuals": ["dragons", "magic effects", "treasure"],
            "colors": ["gold", "purple", "blue"],
            "text": ["Merge!", "Magic", "Adventure"],
            "themes": ["fantasy", "magic", "adventure"],
            "emotions": ["excitement", "wonder"],
        }
        
        return self.extract("screenshot_001", image_data)
