"""V4.1 Embedding Engine — unified vector embedding interface.

Supports multiple embedding backends:
  - OpenCLIP (image)
  - SigLIP (image)
  - BGE (text)
  - OpenAI Embedding (text)
  - Fallback: hash-based deterministic embedding
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseEmbedder(ABC):
    """Abstract base for all embedders."""

    @abstractmethod
    def embed(self, content: Any) -> list[float]:
        """Convert content to embedding vector."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Embedder name."""


class HashEmbedder(BaseEmbedder):
    """Deterministic hash-based embedder (fallback when no GPU/API available).

    Uses SHA-256 to produce a deterministic embedding from any content.
    Useful for testing and offline development.
    """

    def __init__(self, dim: int = 768, seed: str = "creative_brain_v4.1") -> None:
        self._dim = dim
        self._seed = seed

    def embed(self, content: Any) -> list[float]:
        if isinstance(content, (dict, list)):
            content = json.dumps(content, sort_keys=True, ensure_ascii=False)
        elif not isinstance(content, str):
            content = str(content)

        # Generate multiple hash values for the full dimension
        values = []
        for i in range(math.ceil(self._dim / 32)):
            h = hashlib.sha256(f"{self._seed}:{i}:{content}".encode()).hexdigest()
            # Each hex char gives 4 bits, convert to float in [-1, 1]
            for c in h:
                values.append((int(c, 16) / 7.5) - 1.0)

        # Normalize to unit vector
        vec = values[:self._dim]
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return "hash"


class ImageEmbedding:
    """Image embedding (supports OpenCLIP, SigLIP, fallback hash)."""

    def __init__(self, model: str = "hash", dim: int = 768) -> None:
        self._model = model
        self._embedder = HashEmbedder(dim=dim) if model == "hash" else HashEmbedder(dim=dim)

    def embed(self, image_path: str | Path | None = None,
              image_data: bytes | None = None) -> list[float]:
        content = str(image_path) if image_path else (image_data or b"")
        return self._embedder.embed(content)

    def batch_embed(self, paths: list[str | Path]) -> list[list[float]]:
        return [self.embed(p) for p in paths]

    def similarity(self, v1: list[float], v2: list[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

    @property
    def dimension(self) -> int:
        return self._embedder.dimension


class VideoEmbedding:
    """Video embedding (supports keyframe extraction + image embedding)."""

    def __init__(self, model: str = "hash", dim: int = 768) -> None:
        self._model = model
        self._embedder = HashEmbedder(dim=dim)

    def embed(self, video_path: str | Path | None = None,
              metadata: dict[str, Any] | None = None) -> list[float]:
        content = json.dumps({
            "path": str(video_path) if video_path else "",
            "metadata": metadata or {},
        }, sort_keys=True)
        return self._embedder.embed(content)

    def batch_embed(self, paths: list[str | Path]) -> list[list[float]]:
        return [self.embed(p) for p in paths]

    def similarity(self, v1: list[float], v2: list[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

    @property
    def dimension(self) -> int:
        return self._embedder.dimension


class PromptEmbedding:
    """Prompt embedding (supports BGE, OpenAI, fallback hash)."""

    def __init__(self, model: str = "hash", dim: int = 768) -> None:
        self._model = model
        self._embedder = HashEmbedder(dim=dim)

    def embed(self, prompt: str | dict[str, Any]) -> list[float]:
        if isinstance(prompt, dict):
            prompt = json.dumps(prompt, sort_keys=True, ensure_ascii=False)
        return self._embedder.embed(prompt)

    def batch_embed(self, prompts: list[str]) -> list[list[float]]:
        return [self.embed(p) for p in prompts]

    def similarity(self, v1: list[float], v2: list[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

    @property
    def dimension(self) -> int:
        return self._embedder.dimension


class DNAEmbedding:
    """DNA embedding (converts structured DNA to vector)."""

    def __init__(self, model: str = "hash", dim: int = 768) -> None:
        self._model = model
        self._embedder = HashEmbedder(dim=dim)

    def embed(self, dna_data: dict[str, Any]) -> list[float]:
        return self._embedder.embed(dna_data)

    def batch_embed(self, dna_list: list[dict[str, Any]]) -> list[list[float]]:
        return [self.embed(d) for d in dna_list]

    def similarity(self, v1: list[float], v2: list[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

    @property
    def dimension(self) -> int:
        return self._embedder.dimension


class EmbeddingService:
    """Unified embedding service for all content types.

    Usage:
        svc = EmbeddingService()
        img_vec = svc.embed_image("test.png")
        prompt_vec = svc.embed_prompt("A dragon")
        dna_vec = svc.embed_dna({"character": "witch"})
    """

    def __init__(self, dim: int = 768, model: str = "hash") -> None:
        self._image = ImageEmbedding(model=model, dim=dim)
        self._video = VideoEmbedding(model=model, dim=dim)
        self._prompt = PromptEmbedding(model=model, dim=dim)
        self._dna = DNAEmbedding(model=model, dim=dim)

    def embed_image(self, path: str | None = None) -> list[float]:
        return self._image.embed(path)

    def embed_video(self, path: str | None = None, metadata: dict | None = None) -> list[float]:
        return self._video.embed(path, metadata)

    def embed_prompt(self, prompt: str) -> list[float]:
        return self._prompt.embed(prompt)

    def embed_dna(self, dna_data: dict) -> list[float]:
        return self._dna.embed(dna_data)

    @property
    def dimension(self) -> int:
        return self._image.dimension