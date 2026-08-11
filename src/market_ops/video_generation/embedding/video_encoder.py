"""Video Encoder"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import random


@dataclass
class VideoEmbedding:
    embedding_id: str = ""
    video_path: str = ""
    embedding: List[float] = field(default_factory=list)
    thumbnail_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class VideoEncoder:
    """视频编码器 - 生成视频嵌入向量"""

    def __init__(self):
        self._dimensions = 512

    def encode(self, video_path: str, thumbnail_path: str = "") -> VideoEmbedding:
        embedding = self._generate_fake_embedding()
        return VideoEmbedding(
            embedding_id=f"emb_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            video_path=video_path,
            embedding=embedding,
            thumbnail_path=thumbnail_path,
            metadata={
                "dimensions": self._dimensions,
                "model": "clip-vit-large-patch14",
            }
        )

    def _generate_fake_embedding(self) -> List[float]:
        return [random.uniform(-1, 1) for _ in range(self._dimensions)]

    def batch_encode(self, videos: List[Dict[str, Any]]) -> List[VideoEmbedding]:
        embeddings = []
        for video in videos:
            embedding = self.encode(video.get("video_path", ""))
            embeddings.append(embedding)
        return embeddings
