"""Asset Cluster — DBSCAN 视觉聚类

用 CLIP embedding 的余弦距离做 DBSCAN 聚类,
将视觉相同/相近的素材归为同一 visual_asset_id。
"""
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict

try:
    from sklearn.cluster import DBSCAN
    from sklearn.metrics.pairwise import cosine_distances
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ..config import CLUSTER_EPS, CLUSTER_MIN_SAMPLES


class AssetCluster:
    """视觉素材聚类器"""

    def __init__(self, eps: float = CLUSTER_EPS,
                 min_samples: int = CLUSTER_MIN_SAMPLES):
        self.eps = eps
        self.min_samples = min_samples

    def cluster(self, embeddings: Dict[str, np.ndarray]) -> Dict[str, int]:
        """对 embedding 进行聚类

        Args:
            embeddings: {ad_id: 512-dim vector}

        Returns:
            {ad_id: cluster_label}  (label=-1 表示噪声/独立素材)
        """
        if not embeddings:
            return {}

        if not HAS_SKLEARN:
            # 降级: 用 thumbnail_url 分组代替 (每个 ad 自成一组)
            print("[AssetCluster] WARNING: sklearn 未安装, 每个 ad 独立分组")
            return {ad_id: i for i, ad_id in enumerate(embeddings)}

        ad_ids = list(embeddings.keys())
        vectors = np.array([embeddings[aid] for aid in ad_ids])

        print(f"[AssetCluster] 输入 {len(ad_ids)} 个 embedding, eps={self.eps}")

        # 计算余弦距离矩阵
        dist_matrix = cosine_distances(vectors)

        # DBSCAN 聚类
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="precomputed"
        ).fit(dist_matrix)

        labels = clustering.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = (labels == -1).sum()

        # 将噪声点各自成一组 (给它们分配新的 cluster id)
        next_label = max(labels) + 1 if len(labels) > 0 else 0
        final_labels = {}
        for ad_id, label in zip(ad_ids, labels):
            if label == -1:
                final_labels[ad_id] = next_label
                next_label += 1
            else:
                final_labels[ad_id] = int(label)

        total_groups = len(set(final_labels.values()))
        print(f"[AssetCluster] 聚类结果: {n_clusters} 核心簇, "
              f"{n_noise} 独立点, 总共 {total_groups} 组")

        return final_labels

    def get_cluster_groups(self, labels: Dict[str, int]) -> Dict[int, List[str]]:
        """从 labels 反转得到 {cluster_id: [ad_ids]}"""
        groups = defaultdict(list)
        for ad_id, label in labels.items():
            groups[label].append(ad_id)
        return dict(groups)

    def get_cluster_centroids(self, embeddings: Dict[str, np.ndarray],
                              labels: Dict[str, int]) -> Dict[int, np.ndarray]:
        """计算每个 cluster 的中心向量"""
        groups = self.get_cluster_groups(labels)
        centroids = {}
        for cluster_id, ad_ids in groups.items():
            vectors = [embeddings[aid] for aid in ad_ids if aid in embeddings]
            if vectors:
                centroid = np.mean(vectors, axis=0)
                centroid = centroid / np.linalg.norm(centroid)  # normalize
                centroids[cluster_id] = centroid
        return centroids
