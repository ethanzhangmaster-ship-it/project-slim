"""Embedding Engine — CLIP multimodal encoder with provider abstraction.

Supports:
  - transformers_clip (stable, fallback)
  - open_clip (ViT-H-14, ViT-L-14, ViT-B-32)
  - Easy to extend: SigLIP, EVA-CLIP, Qwen-VL

Usage:
    ee = EmbeddingEngine(config)
    img_vec = ee.encode_image(img_pil)
    img_mat = ee.encode_images([img1, img2, img3])
    txt_mat = ee.encode_text(["text1", "text2"])
"""
import time, warnings
from typing import Optional
import numpy as np
from PIL import Image
import torch

warnings.filterwarnings("ignore")


class EmbeddingEngine:
    """Vision-language embedding engine. Provider-agnostic."""

    def __init__(self, config):
        self.cfg = config.get("embedding", default={})
        self.provider = self.cfg.get("provider", "open_clip")
        self.model_name = self.cfg.get("model", "openai/clip-vit-base-patch32")
        self.pretrained = self.cfg.get("pretrained", "")
        self.batch_size = self.cfg.get("batch_size", 32)
        self.device = config.device
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._dim = None

    def _lazy_load(self):
        if self._model is not None:
            return
        t0 = time.time()

        if self.provider == "open_clip":
            import open_clip
            print(f"    Loading OpenCLIP {self.model_name} on {self.device}...")
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained=self.pretrained or None, device=self.device
            )
            self._model.eval()
            self._tokenizer = open_clip.get_tokenizer(self.model_name)
            self._dim = self._model.visual.output_dim
        else:
            from transformers import CLIPProcessor, CLIPModel
            hf_name = self.model_name
            print(f"    Loading transformers {hf_name} on {self.device}...")
            self._processor = CLIPProcessor.from_pretrained(hf_name)
            self._model = CLIPModel.from_pretrained(hf_name).to(self.device)
            self._model.eval()
            self._dim = self._model.config.projection_dim

        print(f"    Model loaded in {time.time()-t0:.1f}s, dim={self._dim}")

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._lazy_load()
        return self._dim

    def encode_image(self, image: Image.Image) -> np.ndarray:
        """Single PIL image → 512d/768d embedding vector."""
        self._lazy_load()
        if self.provider == "open_clip":
            img = self._preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                emb = self._model.encode_image(img)
        else:
            inputs = self._processor(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                emb = self._model.get_image_features(**inputs)
        return emb.cpu().numpy().flatten().astype(np.float32)

    def encode_images(self, images: list) -> np.ndarray:
        """Batch PIL images → (N, dim) embedding matrix."""
        self._lazy_load()
        embs = []
        for i in range(0, len(images), self.batch_size):
            batch = images[i:i + self.batch_size]
            if self.provider == "open_clip":
                imgs = torch.stack([self._preprocess(img) for img in batch]).to(self.device)
                with torch.no_grad():
                    embs.append(self._model.encode_image(imgs).cpu().numpy())
            else:
                inputs = self._processor(images=batch, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    embs.append(self._model.get_image_features(**inputs).cpu().numpy())
        return np.concatenate(embs, axis=0).astype(np.float32)

    def encode_texts(self, texts: list) -> np.ndarray:
        """Batch texts → (N, dim) embedding matrix."""
        self._lazy_load()
        embs = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            if self.provider == "open_clip":
                tokens = self._tokenizer(batch).to(self.device)
                with torch.no_grad():
                    embs.append(self._model.encode_text(tokens).cpu().numpy())
            else:
                inputs = self._processor(text=batch, return_tensors="pt",
                                         padding=True, truncation=True).to(self.device)
                with torch.no_grad():
                    embs.append(self._model.get_text_features(**inputs).cpu().numpy())
        return np.concatenate(embs, axis=0).astype(np.float32)
