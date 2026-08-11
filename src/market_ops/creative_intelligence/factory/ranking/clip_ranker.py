"""CLIP Similarity Ranker — Phase 2.1 真实视觉 embedding 排序。

计算每张生成创意与 Winner 参考图的余弦相似度。

模式：
- "openclip"   : OpenCLIP ViT-B-32（laion2b 权重）—— 真实图像编码（Phase 2.1 主路径）
- "clip"       : CLIP ViT-B/32 —— 备用真实图像编码
- "heuristic"  : 无 torch/clip 依赖时的回退，基于 DNA 特征向量（Winner DNA 相似度）

OpenCLIPEncoder 负责真实图像编码；heuristic 仍由本模块的 encode_dna 提供。
所有模式统一输出 cosine similarity ∈ [0,1]。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.ranking.embedding_store import (  # noqa: E402
    EmbeddingStore,
)
from market_ops.creative_intelligence.factory.dna.dna_mutator import DNAMutator  # noqa: E402


# 核心维度（定义“像不像 Winner”）高权重；可变维度低权重
_DIM_WEIGHTS = {
    "character": 3.0,
    "color": 3.0,
    "hook": 3.0,
    "reward": 1.0,
    "background": 1.0,
    "composition": 1.0,
    "theme": 1.0,
}


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class OpenCLIPEncoder:
    """真实视觉 embedding 编码器（Phase 2.1）。

    使用 OpenCLIP ViT-B-32（laion2b_s34b_b79k 预训练权重）。
    首次编码会按需下载模型权重（需网络）；之后权重本地缓存。
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    def __init__(self, device: str = "cpu") -> None:
        import open_clip

        self._open_clip = open_clip
        self.device = device
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.MODEL_NAME, pretrained=self.PRETRAINED
        )
        self.tokenizer = open_clip.get_tokenizer(self.MODEL_NAME)
        self.model.eval().to(device)
        print(
            f"OpenCLIPEncoder initialized | model: {self.MODEL_NAME} | "
            f"pretrained: {self.PRETRAINED} | device: {device}",
            file=sys.stderr,
        )

    def encode_image(self, image_path: str | Path) -> np.ndarray:
        import torch
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        x = self.preprocess(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feat = self.model.encode_image(x)
        return feat.cpu().numpy().flatten().astype(np.float32)

    def encode_text(self, text: str) -> np.ndarray:
        """文本编码（512-d），用于 game clarity / visual quality 等文图相似度维度。"""
        import torch

        tok = self.tokenizer([text])
        with torch.no_grad():
            feat = self.model.encode_text(tok)
        return feat.cpu().numpy().flatten().astype(np.float32)


class CLIPRanker:
    def __init__(self, mode: str = "auto", embeddings_dir: str | Path | None = None) -> None:
        self.mode = self._resolve_mode(mode)
        self._encoder: OpenCLIPEncoder | None = None
        self._model = None
        self._preprocess = None
        self._device = "cpu"
        self._mutator = DNAMutator()
        self.store = EmbeddingStore(
            embeddings_dir
            or (Path(__file__).resolve().parent.parent / "embeddings")
        )
        if self.mode in ("openclip", "clip"):
            self._load_model()

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_mode(mode: str) -> str:
        if mode == "heuristic":
            return "heuristic"
        if mode in ("openclip", "clip"):
            try:
                if mode == "openclip":
                    import open_clip  # noqa: F401
                else:
                    import clip  # noqa: F401
                return mode
            except Exception:
                return "heuristic"
        # auto：探测可用真实模型
        try:
            import open_clip  # noqa: F401

            return "openclip"
        except Exception:
            pass
        try:
            import clip  # noqa: F401

            return "clip"
        except Exception:
            pass
        print("mode=heuristic | fallback heuristic (real CLIP deps unavailable)", file=sys.stderr)
        return "heuristic"

    def _load_model(self) -> None:
        if self.mode == "openclip":
            self._encoder = OpenCLIPEncoder(device=self._device)
            print(
                f"mode=openclip | CLIPRanker using OpenCLIPEncoder "
                f"({OpenCLIPEncoder.MODEL_NAME}, {OpenCLIPEncoder.PRETRAINED})",
                file=sys.stderr,
            )
        else:
            import clip

            self._model, self._preprocess = clip.load("ViT-B/32", device=self._device)
            self._model.eval()

    # ------------------------------------------------------------------
    def _build_vocab(self, base: dict[str, Any] | None = None) -> dict[str, list[str]]:
        lib = self._mutator.library
        b = base or {}
        vocab: dict[str, list[str]] = {}
        vocab["character"] = list(lib.get("character", {}).get("preserve", [])) or ["witch"]
        vocab["reward"] = [b.get("reward")] + [
            r["to"] for r in lib.get("reward", []) if isinstance(r, dict)
        ] + list(lib.get("reward_alternatives", []))
        vocab["background"] = [b.get("background")] + list(lib.get("background", []))
        vocab["composition"] = list(lib.get("composition", []))
        vocab["color"] = [b.get("color")] + [
            c["to"] for c in lib.get("color", []) if isinstance(c, dict)
        ] + list(lib.get("color_alternatives", []))
        vocab["hook"] = list(lib.get("hook", []))
        vocab["theme"] = [b.get("theme")] or ["magic garden"]
        for k, vals in vocab.items():
            seen = set()
            uniq = []
            for v in vals:
                if v and v not in seen:
                    seen.add(v)
                    uniq.append(v)
            vocab[k] = uniq
        return vocab

    # ------------------------------------------------------------------
    def encode_dna(self, dna: dict[str, Any], base: dict[str, Any] | None = None) -> np.ndarray:
        """将 DNA 编码为加权 one-hot 向量（heuristic 模式）。"""
        vocab = self._build_vocab(base)
        vec: list[float] = []
        for dim_name in ("character", "reward", "background", "composition", "color", "hook", "theme"):
            w = _DIM_WEIGHTS.get(dim_name, 1.0)
            terms = vocab.get(dim_name, [])
            val = (dna.get(dim_name) or "").strip().lower()
            for t in terms:
                vec.append(w if t.lower() == val else 0.0)
        return np.array(vec, dtype=np.float32)

    def encode_image(self, path: str | Path) -> np.ndarray:
        """图像编码：真实 CLIP（OpenCLIPEncoder 或 clip）或 heuristic 像素回退。"""
        if self.mode == "openclip" and self._encoder is not None:
            return self._encoder.encode_image(path)
        if self.mode == "clip" and self._model is not None:
            return self._clip_encode_image(path)
        return self._pixel_vec(path)

    def _clip_encode_image(self, path: str | Path) -> np.ndarray:
        import torch
        from PIL import Image

        img = Image.open(path).convert("RGB")
        x = self._preprocess(img).unsqueeze(0).to(self._device)
        with torch.no_grad():
            feat = self._model.encode_image(x)
        return feat.cpu().numpy().flatten().astype(np.float32)

    @staticmethod
    def _pixel_vec(path: str | Path) -> np.ndarray:
        from PIL import Image

        try:
            img = Image.open(path).convert("RGB").resize((32, 32))
            arr = np.asarray(img, dtype=np.float32).flatten()
            arr = (arr - arr.mean()) / (arr.std() + 1e-6)
            return arr.astype(np.float32)
        except Exception:
            return np.zeros(32 * 32 * 3, dtype=np.float32)

    # ------------------------------------------------------------------
    def rank(
        self,
        winner_dna: dict[str, Any],
        winner_ref_path: str | Path | None,
        creatives: list[dict[str, Any]],
        top_k: int | None = None,
        winner_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """返回按相似度降序的列表：[{creative_id, similarity}, ...]。

        heuristic 模式完全基于 DNA 特征向量（不加载/不写入图像 embedding 缓存），
        以保证与真实 CLIP 模式的对比是“规则 vs 视觉”的有效对照，不被缓存污染。
        """
        base = self._mutator._extract_base_dna(winner_dna)

        if self.mode == "heuristic":
            wvec = self.encode_dna(base, base)
            scored = []
            for c in creatives:
                cvec = self.encode_dna(c.get("dna", {}), base)
                sim = _cosine(wvec, cvec)
                scored.append(
                    {"creative_id": c["creative_id"], "similarity": round(float(sim), 4)}
                )
            scored.sort(key=lambda x: -x["similarity"])
            if top_k is not None:
                scored = scored[:top_k]
            return scored

        # 真实模式（openclip / clip）：基于图像 embedding，带缓存
        wname = f"winner_{winner_code or winner_dna.get('winner_code', '000')}"
        wvec = self.store.load_winner(wname)
        if wvec is None:
            if winner_ref_path and Path(winner_ref_path).exists():
                wvec = self.encode_image(winner_ref_path)
            else:
                wvec = self.encode_dna(base, base)
            self.store.save_winner(wname, wvec)

        scored = []
        for c in creatives:
            cid = c["creative_id"]
            cvec = self.store.load_creative(cid)
            if cvec is None:
                if c.get("file") and Path(c["file"]).exists():
                    cvec = self.encode_image(c["file"])
                else:
                    cvec = self.encode_dna(c.get("dna", {}), base)
                self.store.save_creative(cid, cvec)
            sim = _cosine(wvec, cvec)
            scored.append({"creative_id": cid, "similarity": round(float(sim), 4)})

        scored.sort(key=lambda x: -x["similarity"])
        if top_k is not None:
            scored = scored[:top_k]
        return scored
