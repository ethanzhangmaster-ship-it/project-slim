"""User Embedding - 用户嵌入"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class UserEmbedding:
    """用户嵌入向量"""
    user_id: str = ""
    embedding: List[float] = None
    profile: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.embedding is None:
            self.embedding = []
        if self.profile is None:
            self.profile = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "embedding_dim": len(self.embedding),
            "profile": self.profile,
        }


class UserEmbeddingEngine:
    """用户嵌入引擎"""
    
    def __init__(self):
        self._embeddings: Dict[str, UserEmbedding] = {}
    
    def embed(self, user_id: str, profile: Dict[str, Any]) -> UserEmbedding:
        """生成用户嵌入"""
        # 简单的特征编码作为嵌入
        embedding = self._encode_profile(profile)
        
        embedding_obj = UserEmbedding(
            user_id=user_id,
            embedding=embedding,
            profile=profile,
        )
        
        self._embeddings[user_id] = embedding_obj
        return embedding_obj
    
    def _encode_profile(self, profile: Dict[str, Any]) -> List[float]:
        """编码用户画像为向量"""
        embedding = []
        
        # 国家编码
        country_map = {"US": 0.8, "UK": 0.7, "CA": 0.6, "AU": 0.5, "DE": 0.4}
        embedding.append(country_map.get(profile.get("country", ""), 0.3))
        
        # OS 编码
        os_map = {"iOS": 0.7, "Android": 0.3}
        embedding.append(os_map.get(profile.get("os", ""), 0.5))
        
        # 性别编码
        gender_map = {"Female": 0.7, "Male": 0.3}
        embedding.append(gender_map.get(profile.get("gender", ""), 0.5))
        
        # 年龄编码
        age_map = {"18-24": 0.3, "25-34": 0.5, "30-44": 0.7, "35-44": 0.8, "45+": 0.6}
        embedding.append(age_map.get(profile.get("age_range", ""), 0.5))
        
        # 游戏类型编码
        genre_map = {"Puzzle": 0.8, "Action": 0.6, "RPG": 0.5, "Strategy": 0.4, "Simulation": 0.7}
        embedding.append(genre_map.get(profile.get("game_genre", ""), 0.5))
        
        return embedding
    
    def similarity(self, user_id1: str, user_id2: str) -> float:
        """计算用户相似度"""
        emb1 = self._embeddings.get(user_id1)
        emb2 = self._embeddings.get(user_id2)
        
        if not emb1 or not emb2:
            return 0.0
        
        # 余弦相似度
        return self._cosine_similarity(emb1.embedding, emb2.embedding)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)
    
    def get_similar_users(self, user_id: str, limit: int = 5) -> List[str]:
        """获取相似用户"""
        user_emb = self._embeddings.get(user_id)
        if not user_emb:
            return []
        
        similarities = []
        for other_id, other_emb in self._embeddings.items():
            if other_id != user_id:
                sim = self._cosine_similarity(user_emb.embedding, other_emb.embedding)
                similarities.append((other_id, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [uid for uid, _ in similarities[:limit]]
    
    def embed_demo(self) -> UserEmbedding:
        """演示用户嵌入"""
        profile = {
            "country": "US",
            "os": "iOS",
            "gender": "Female",
            "age_range": "30-44",
            "game_genre": "Puzzle",
        }
        return self.embed("user_001", profile)
