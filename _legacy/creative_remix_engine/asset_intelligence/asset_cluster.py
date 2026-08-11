"""Asset Cluster — CLIP Embedding + 聚类发现 Winner Archetype

使用 CLIP 对视频帧提取 embedding，然后聚类发现隐藏模式。
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict


class AssetCluster:
    """资产聚类器 — 发现 Creative Archetype"""

    def __init__(self, ranking_db_path: Optional[Path] = None):
        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_data = {}
        self._load_ranking(ranking_db_path)
        self._clip_available = False
        self._try_load_clip()

    def _try_load_clip(self):
        """尝试加载 CLIP，失败则使用 fallback"""
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self._clip_available = True
            print("[AssetCluster] CLIP loaded successfully")
        except Exception as e:
            print(f"[AssetCluster] CLIP not available ({e}), using fallback embedding")
            self._clip_available = False

    def _load_ranking(self, path: Path):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self.ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

    def _fallback_embedding(self, name: str, rank: dict) -> np.ndarray:
        """轻量级 fallback embedding：基于分数 + 文件名关键词"""
        # 12维向量：motion, impact, hook, gameplay, reward, clarity + 6个主题one-hot
        vec = np.zeros(12)
        vec[0] = rank.get("motion_score", 0) / 100
        vec[1] = rank.get("impact_score", 0) / 100
        vec[2] = rank.get("hook_score_v2", 0) / 100
        vec[3] = rank.get("gameplay_clarity", 0) / 100
        vec[4] = rank.get("reward_score", 0) / 100
        vec[5] = rank.get("ad_value_score", 0) / 100

        # 主题 one-hot
        s = name.lower()
        themes = [
            "dragon" in s or "龙" in s or "egg" in s,
            "witch" in s or "女巫" in s or "magic" in s,
            "castle" in s or "城堡" in s,
            "merge" in s or "hecheng" in s or "wanfa" in s,
            "battle" in s or "boss" in s or "fight" in s,
            "kaitou" in s or "hook" in s or "start" in s,
        ]
        for i, t in enumerate(themes):
            vec[6 + i] = 1.0 if t else 0.0
        return vec

    def _get_embedding(self, video_name: str, frame_path: Optional[Path] = None) -> np.ndarray:
        """获取视频embedding"""
        rank = self.ranking_data.get(video_name, {})
        if self._clip_available and frame_path and frame_path.exists():
            try:
                from PIL import Image
                image = Image.open(str(frame_path)).convert("RGB")
                inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    vec = self.clip_model.get_image_features(**inputs).cpu().numpy()[0]
                # 拼接 Ranking 分数
                rank_vec = np.array([
                    rank.get("motion_score", 0) / 100,
                    rank.get("impact_score", 0) / 100,
                    rank.get("hook_score_v2", 0) / 100,
                ])
                return np.concatenate([vec, rank_vec])
            except Exception:
                pass
        return self._fallback_embedding(video_name, rank)

    def cluster(self, video_names: List[str], frame_dir: Optional[Path] = None,
                n_clusters: int = 8) -> List[dict]:
        """
        聚类并返回 Creative Archetype。
        返回: [{cluster_id, size, avg_scores, dominant_dna, videos}, ...]
        """
        # 获取 embeddings
        embeddings = []
        valid_names = []
        for name in video_names:
            fp = None
            if frame_dir:
                fd = frame_dir / name[:50]
                if fd.exists():
                    frames = sorted(fd.glob("*.jpg"))
                    if frames:
                        fp = frames[len(frames) // 2]  # 取中间帧
            emb = self._get_embedding(name, fp)
            embeddings.append(emb)
            valid_names.append(name)

        X = np.array(embeddings)

        # 使用 K-Means 聚类（fallback）或 HDBSCAN
        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=min(n_clusters, len(X)), random_state=42, n_init=10)
            labels = kmeans.fit_predict(X)
        except Exception:
            # 简单贪婪聚类 fallback
            labels = self._greedy_cluster(X, n_clusters)

        # 构建 cluster 结果
        clusters = defaultdict(list)
        for name, label in zip(valid_names, labels):
            clusters[int(label)].append(name)

        archetypes = []
        for cid, members in sorted(clusters.items()):
            if len(members) < 3:
                continue

            # 聚合 DNA
            all_dnas = [self._get_dna(name) for name in members]
            dominant_dna = self._aggregate_dna(all_dnas)

            # 平均分数
            scores = [self.ranking_data.get(name, {}) for name in members]
            avg_scores = {
                "ad_value": round(np.mean([s.get("ad_value_score", 0) for s in scores]), 1),
                "hook": round(np.mean([s.get("hook_score_v2", 0) for s in scores]), 1),
                "gameplay": round(np.mean([s.get("gameplay_clarity", 0) for s in scores]), 1),
                "reward": round(np.mean([s.get("reward_score", 0) for s in scores]), 1),
                "motion": round(np.mean([s.get("motion_score", 0) for s in scores]), 1),
                "impact": round(np.mean([s.get("impact_score", 0) for s in scores]), 1),
            }

            archetypes.append({
                "cluster_id": cid,
                "size": len(members),
                "avg_scores": avg_scores,
                "dominant_dna": dominant_dna,
                "top_videos": members[:5],
                "performance_tier": "HIGH" if avg_scores["ad_value"] > 50 else "MEDIUM" if avg_scores["ad_value"] > 35 else "LOW",
            })

        # 按 ad_value 排序
        archetypes.sort(key=lambda x: -x["avg_scores"]["ad_value"])
        return archetypes

    def _get_dna(self, name: str) -> dict:
        """从 ranking 获取 DNA 信息"""
        rank = self.ranking_data.get(name, {})
        s = name.lower()
        return {
            "subjects": self._extract_from_name(s, ["dragon", "witch", "castle", "hero"]),
            "actions": self._extract_from_name(s, ["merge", "upgrade", "battle", "unlock"]),
            "emotions": self._extract_from_name(s, ["surprise", "excitement", "achievement"]),
        }

    def _extract_from_name(self, name: str, keywords: List[str]) -> List[str]:
        return [k for k in keywords if k in name]

    def _aggregate_dna(self, dnas: List[dict]) -> dict:
        """聚合 DNA 得到主导特征"""
        subjects = Counter()
        actions = Counter()
        emotions = Counter()
        for d in dnas:
            for s in d.get("subjects", []):
                subjects[s] += 1
            for a in d.get("actions", []):
                actions[a] += 1
            for e in d.get("emotions", []):
                emotions[e] += 1
        return {
            "dominant_subjects": [s for s, _ in subjects.most_common(3)],
            "dominant_actions": [a for a, _ in actions.most_common(3)],
            "dominant_emotions": [e for e, _ in emotions.most_common(3)],
        }

    def _greedy_cluster(self, X: np.ndarray, n_clusters: int) -> np.ndarray:
        """简单贪婪聚类"""
        n = len(X)
        labels = np.zeros(n, dtype=int)
        centers = [X[0]]
        for i in range(1, n):
            dists = [np.linalg.norm(X[i] - c) for c in centers]
            if min(dists) > 0.5 and len(centers) < n_clusters:
                centers.append(X[i])
                labels[i] = len(centers) - 1
            else:
                labels[i] = np.argmin(dists)
        return labels
