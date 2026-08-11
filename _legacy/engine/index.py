"""Vector Index — unified abstraction over FAISS / sklearn NearestNeighbors.

Priority:
  1. FAISS IndexFlatIP (cosine)
  2. sklearn NearestNeighbors
  3. Pure numpy fallback

All backends share the same API: add(), search(), save(), load().
"""
from pathlib import Path
from typing import Optional
import numpy as np


class VectorIndex:
    """Unified vector search index. Add → search → save → load."""

    def __init__(self, dim: int, metric: str = "cosine"):
        self.dim = dim
        self.metric = metric
        self._index = None
        self._ids = None
        self._backend = None

    def add(self, vectors: np.ndarray, ids: Optional[list] = None) -> None:
        """Add vectors to index. vectors: (N, dim)."""
        n, d = vectors.shape
        if ids is None:
            ids = list(range(n))
        self._ids = np.array(ids)

        # Try FAISS
        try:
            import faiss
            idx = faiss.IndexFlatIP(d)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True).clip(1e-10)
            idx.add(vectors / norms)
            self._index = idx
            self._backend = "faiss"
            print(f"    VectorIndex: FAISS ({d}d, {n} vectors)")
            return
        except ImportError:
            pass

        # Fallback: sklearn
        try:
            from sklearn.neighbors import NearestNeighbors
            nn = NearestNeighbors(n_neighbors=min(20, n), metric="cosine", algorithm="brute")
            nn.fit(vectors)
            self._index = nn
            self._backend = "sklearn"
            print(f"    VectorIndex: sklearn NearestNeighbors ({n} vectors)")
            return
        except ImportError:
            pass

        # Pure numpy
        norms = np.linalg.norm(vectors, axis=1, keepdims=True).clip(1e-10)
        self._vectors = vectors / norms
        self._backend = "numpy"
        print(f"    VectorIndex: numpy brute-force ({n} vectors)")

    def search(self, query: np.ndarray, k: int, ef_search: Optional[int] = None):
        """Search top-K. query: (N, dim). Returns (scores, ids)."""
        k = min(k, len(self._ids))

        if self._backend == "faiss":
            q = query / np.linalg.norm(query, axis=1, keepdims=True).clip(1e-10)
            scores, idxs = self._index.search(q.astype(np.float32), k)
            return scores, np.array([self._ids[i] for i in idxs])

        elif self._backend == "sklearn":
            dists, idxs = self._index.kneighbors(query, n_neighbors=k)
            scores = np.clip(1 - dists, 0, 1)
            return scores, np.array([self._ids[i] for i in idxs])

        elif self._backend == "numpy":
            q_norm = query / np.linalg.norm(query, axis=1, keepdims=True).clip(1e-10)
            sim = q_norm @ self._vectors.T
            top_k = np.argsort(-sim, axis=1)[:, :k]
            scores = np.take_along_axis(sim, top_k, axis=1)
            return scores, np.array([self._ids[t] for t in top_k])

        else:
            raise RuntimeError("No index backend loaded")

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        meta = {"backend": self._backend, "dim": self.dim, "metric": self.metric}

        if self._backend == "faiss":
            import faiss
            faiss.write_index(self._index, str(path / "faiss.index"))
        elif self._backend == "sklearn":
            import joblib
            joblib.dump(self._index, path / "sklearn.joblib")
        elif self._backend == "numpy":
            np.save(path / "vectors.npy", self._vectors)

        np.save(path / "ids.npy", self._ids)
        np.save(path / "meta.npy", meta)
        print(f"    Index saved to {path}")

    def load(self, path: Path) -> bool:
        if not (path / "ids.npy").exists():
            return False

        self._ids = np.load(path / "ids.npy", allow_pickle=True)
        meta = np.load(path / "meta.npy", allow_pickle=True).item()
        self.dim = meta["dim"]
        self.metric = meta["metric"]
        self._backend = meta["backend"]

        if self._backend == "faiss":
            import faiss
            self._index = faiss.read_index(str(path / "faiss.index"))
        elif self._backend == "sklearn":
            import joblib
            self._index = joblib.load(path / "sklearn.joblib")
        elif self._backend == "numpy":
            self._vectors = np.load(path / "vectors.npy")

        print(f"    Index loaded from {path} ({self._backend})")
        return True

    @property
    def ntotal(self) -> int:
        return len(self._ids) if self._ids is not None else 0

    @property
    def backend(self) -> Optional[str]:
        return self._backend
