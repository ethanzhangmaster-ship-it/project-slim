"""Shot Embedding — Shot 向量嵌入与相似性搜索

功能：
- 将 Shot DNA 编码为向量
- 支持相似性搜索
- 支持聚类分析
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .shot_analyzer import ShotDNA, SUBJECT_TYPES, ACTION_TYPES, EMOTION_TYPES, CAMERA_TYPES


class ShotEmbedding:
    """Shot 向量嵌入"""

    ROLE_DIM = 5       # hook, gameplay, reward, story, ending
    SUBJECT_DIM = 6    # character, monster, building, item, landscape, ui
    ACTION_DIM = 8     # merge, upgrade, attack, rescue, open, transform, collect, explore
    EMOTION_DIM = 6    # surprise, curiosity, satisfaction, excitement, tension, relief
    CAMERA_DIM = 7     # zoom_in, zoom_out, closeup, pan, static, tracking, tilt

    TOTAL_DIM = ROLE_DIM + SUBJECT_DIM + ACTION_DIM + EMOTION_DIM + CAMERA_DIM + 3  # + scores + duration

    def __init__(self):
        self.embeddings: Dict[str, np.ndarray] = {}
        self._build_encoders()

    def _build_encoders(self):
        """构建编码器"""
        self.role_encoder = {
            "hook": 0, "gameplay": 1, "reward": 2, "story": 3, "ending": 4
        }
        self.subject_encoder = {s: i for i, s in enumerate(SUBJECT_TYPES)}
        self.action_encoder = {a: i for i, a in enumerate(ACTION_TYPES)}
        self.emotion_encoder = {e: i for i, e in enumerate(EMOTION_TYPES)}
        self.camera_encoder = {c: i for i, c in enumerate(CAMERA_TYPES)}

    def encode(self, shot: ShotDNA) -> np.ndarray:
        """将 Shot DNA 编码为向量"""
        features = []

        # Role (One-Hot)
        role_vec = np.zeros(self.ROLE_DIM)
        if shot.role in self.role_encoder:
            role_vec[self.role_encoder[shot.role]] = 1
        features.extend(role_vec)

        # Subject (One-Hot)
        sub_vec = np.zeros(self.SUBJECT_DIM)
        if shot.subject in self.subject_encoder:
            sub_vec[self.subject_encoder[shot.subject]] = 1
        features.extend(sub_vec)

        # Action (One-Hot)
        act_vec = np.zeros(self.ACTION_DIM)
        if shot.action in self.action_encoder:
            act_vec[self.action_encoder[shot.action]] = 1
        features.extend(act_vec)

        # Emotion (One-Hot)
        emo_vec = np.zeros(self.EMOTION_DIM)
        if shot.emotion in self.emotion_encoder:
            emo_vec[self.emotion_encoder[shot.emotion]] = 1
        features.extend(emo_vec)

        # Camera (One-Hot)
        cam_vec = np.zeros(self.CAMERA_DIM)
        if shot.camera in self.camera_encoder:
            cam_vec[self.camera_encoder[shot.camera]] = 1
        features.extend(cam_vec)

        # Numeric features (normalized)
        features.append(shot.visual_score / 100)
        features.append(shot.performance_score / 100)
        features.append(min(shot.duration / 15.0, 1.0))

        return np.array(features, dtype=np.float32)

    def batch_encode(self, shots: List[ShotDNA]) -> np.ndarray:
        """批量编码"""
        embeddings = [self.encode(s) for s in shots]
        return np.array(embeddings, dtype=np.float32)

    def cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    def find_similar(self, query_shot: ShotDNA,
                     candidates: List[ShotDNA],
                     top_k: int = 5) -> List[Tuple[ShotDNA, float]]:
        """查找相似 shot"""
        query_emb = self.encode(query_shot)

        similarities = []
        for candidate in candidates:
            if candidate.shot_id == query_shot.shot_id:
                continue
            cand_emb = self.encode(candidate)
            sim = self.cosine_similarity(query_emb, cand_emb)
            similarities.append((candidate, sim))

        similarities.sort(key=lambda x: -x[1])
        return similarities[:top_k]

    def find_diverse(self, query_shot: ShotDNA,
                     candidates: List[ShotDNA],
                     top_k: int = 5) -> List[Tuple[ShotDNA, float]]:
        """查找多样化 shot（与 query 不同但质量高）"""
        query_emb = self.encode(query_shot)

        results = []
        for candidate in candidates:
            if candidate.shot_id == query_shot.shot_id:
                continue
            # 确保不同主体或不同动作
            if candidate.subject == query_shot.subject and candidate.action == query_shot.action:
                continue
            cand_emb = self.encode(candidate)
            sim = self.cosine_similarity(query_emb, cand_emb)
            # 使用距离而非相似度（越远越 diverse）
            distance = 1 - sim
            results.append((candidate, distance))

        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def cluster_shots(self, shots: List[ShotDNA], n_clusters: int = 5) -> Dict[int, List[ShotDNA]]:
        """对 shots 进行聚类"""
        if len(shots) < n_clusters:
            return {i: [s] for i, s in enumerate(shots)}

        embeddings = self.batch_encode(shots)

        # 使用 K-Means 聚类（简化版）
        # 实际部署可使用 sklearn.cluster.KMeans
        np.random.seed(42)
        centers = embeddings[np.random.choice(len(embeddings), n_clusters, replace=False)]

        for _ in range(20):  # 迭代
            # 分配
            distances = np.array([[np.linalg.norm(e - c) for c in centers] for e in embeddings])
            labels = np.argmin(distances, axis=1)

            # 更新中心
            for i in range(n_clusters):
                mask = labels == i
                if np.any(mask):
                    centers[i] = embeddings[mask].mean(axis=0)

        clusters = {i: [] for i in range(n_clusters)}
        for shot, label in zip(shots, labels):
            clusters[int(label)].append(shot)

        return clusters