"""Cache system — MD5-based embedding + frame cache with TTL."""
import hashlib, pickle, shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import numpy as np


class EmbeddingCache:
    """Persistent embedding cache with MD5 key and configurable TTL.

    Cache structure:
        cache_dir/
            {hash[0:2]}/
                {hash[2:]}.pkl   ← pickle'd numpy array
    """

    def __init__(self, base_dir: Path, ttl_days: int = 30, enabled: bool = True):
        self.base = base_dir / "cache"
        self.base.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(days=ttl_days)
        self.enabled = enabled

    def _key(self, source_id: str) -> str:
        return hashlib.md5(source_id.encode()).hexdigest()

    def _path(self, source_id: str) -> Path:
        k = self._key(source_id)
        return self.base / k[:2] / f"{k[2:]}.pkl"

    def get(self, source_id: str) -> Optional[np.ndarray]:
        if not self.enabled:
            return None
        p = self._path(source_id)
        if p.exists():
            age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
            if age < self.ttl:
                return pickle.loads(p.read_bytes())
        return None

    def put(self, source_id: str, embedding: np.ndarray) -> None:
        if not self.enabled:
            return
        p = self._path(source_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pickle.dumps(embedding))

    def has(self, source_id: str) -> bool:
        return self._path(source_id).exists() if self.enabled else False

    def invalidate(self, source_id: Optional[str] = None) -> None:
        if source_id:
            p = self._path(source_id)
            if p.exists():
                p.unlink()
        else:
            shutil.rmtree(self.base)
            self.base.mkdir()

    def hit_rate(self) -> float:
        """Stub: override with real stats tracking."""
        return 0.0
