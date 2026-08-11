"""Creative Embedding — 创意相似度计算（占位）"""
from ..models import RemixRecipe


class CreativeEmbedding:
    """基于 CLIP 的创意嵌入计算（简化版）"""

    def embed(self, recipe: RemixRecipe) -> list:
        """生成创意嵌入向量"""
        return [0.0] * 128