"""Clustering Engine — HDBSCAN → Agglomerative → KMeans fallback chain.

All methods share the same output signature: (labels: np.ndarray, n_clusters: int)
Noise points are labeled -1 (HDBSCAN). All sklearn imports are deferred to
allow graceful fallback when sklearn is not installed.
"""
import numpy as np


def cluster_embeddings(vectors: np.ndarray, config) -> tuple:
    """Cluster embeddings with automatic method selection.

    Priority:
      1. HDBSCAN (auto cluster count, noise detection)
      2. Agglomerative Clustering (cosine linkage)
      3. KMeans + StandardScaler (final fallback)

    Returns:
        labels: np.ndarray of cluster IDs (-1 for noise)
        n_clusters: int (excluding noise)
    """
    cfg = config.get("clustering", default={})
    method = cfg.get("method", "hdbscan")
    n = len(vectors)

    # ── 1. HDBSCAN ──
    if method == "hdbscan" and n >= 5:
        try:
            import hdbscan
            min_size = max(2, min(cfg.get("min_cluster_size", 5), n // 10))
            min_samp = cfg.get("min_samples", 3)
            eps = cfg.get("cluster_selection_epsilon", 0.0)
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_size,
                min_samples=min_samp,
                metric=cfg.get("metric", "euclidean"),
                cluster_selection_epsilon=eps,
                core_dist_n_jobs=1,
            )
            labels = clusterer.fit_predict(vectors)
            n_real = len(set(l for l in labels if l >= 0))
            n_noise = int((labels == -1).sum())
            print(f"    HDBSCAN: {n_real} clusters, {n_noise} noise, min_size={min_size}")
            return labels.astype(np.int32), n_real
        except Exception as e:
            print(f"    HDBSCAN failed ({e}), falling back...")

    # ── 2. Agglomerative Clustering ──
    if method in ("agglomerative", "hdbscan"):
        try:
            from sklearn.cluster import AgglomerativeClustering
            n_c = max(2, min(50, n // 8))
            ac = AgglomerativeClustering(n_clusters=n_c, metric="cosine", linkage="average")
            labels = ac.fit_predict(vectors)
            print(f"    Agglomerative: {n_c} clusters")
            return labels.astype(np.int32), n_c
        except Exception as e:
            print(f"    Agglomerative failed ({e})")

    # ── 3. KMeans (final fallback) ──
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        n_c = max(3, min(50, n // 8))
        scaler = StandardScaler()
        X = scaler.fit_transform(vectors)
        km = KMeans(n_clusters=n_c, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        print(f"    KMeans: {n_c} clusters (fallback)")
        return labels.astype(np.int32), n_c
    except Exception as e:
        print(f"    KMeans also failed ({e}) — returning single cluster")
        return np.zeros(n, dtype=np.int32), 1
