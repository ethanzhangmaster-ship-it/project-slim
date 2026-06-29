"""Image Validator - pHash查重/黑白图检测/相似度过滤 (DEPRECATED)
Use market_ops.creative_growth_loop.07_validation instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.07_validation")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import imagehash
except ImportError:
    imagehash = None
from PIL import Image


@dataclass
class ValidationResult:
    image_path: Path
    is_valid: bool
    reason: str = ""
    phash: str = ""
    similarity_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_path": str(self.image_path),
            "is_valid": self.is_valid,
            "reason": self.reason,
            "phash": self.phash,
            "similarity_score": self.similarity_score,
        }


class ImageValidator:
    PHASH_DISTANCE_THRESHOLD = 5
    SIMILARITY_THRESHOLD = 0.95
    MIN_BRIGHTNESS = 10
    MAX_BRIGHTNESS = 245

    def __init__(self, original_image_path: Optional[str] = None):
        self.original_image_path = Path(original_image_path) if original_image_path else None
        self.original_phash = self._compute_phash(self.original_image_path) if self.original_image_path else None

    def _compute_phash(self, image_path: Path) -> Optional[str]:
        try:
            img = Image.open(image_path)
            phash = imagehash.phash(img)
            return str(phash)
        except Exception:
            return None

    def validate_images(self, image_paths: List[Path]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        seen_hashes: Dict[str, Path] = {}
        
        for image_path in image_paths:
            result = self._validate_single(image_path, seen_hashes)
            results.append(result)
            
            if result.is_valid and result.phash:
                seen_hashes[result.phash] = image_path
        
        return results

    def _validate_single(self, image_path: Path, seen_hashes: Dict[str, Path]) -> ValidationResult:
        if not image_path.exists():
            return ValidationResult(
                image_path=image_path,
                is_valid=False,
                reason="File not found"
            )
        
        try:
            img = Image.open(image_path)
        except Exception as e:
            return ValidationResult(
                image_path=image_path,
                is_valid=False,
                reason=f"Failed to open image: {str(e)}"
            )
        
        phash = str(imagehash.phash(img))
        
        if self._is_duplicate(phash, seen_hashes):
            return ValidationResult(
                image_path=image_path,
                is_valid=False,
                reason="Duplicate image detected",
                phash=phash
            )
        
        if self._is_blank_or_black(img):
            return ValidationResult(
                image_path=image_path,
                is_valid=False,
                reason="Blank or black image",
                phash=phash
            )
        
        if self.original_phash:
            similarity = self._compute_similarity(phash, self.original_phash)
            if similarity > self.SIMILARITY_THRESHOLD:
                return ValidationResult(
                    image_path=image_path,
                    is_valid=False,
                    reason=f"Too similar to original (similarity={similarity:.2f})",
                    phash=phash,
                    similarity_score=similarity
                )
        
        return ValidationResult(
            image_path=image_path,
            is_valid=True,
            phash=phash
        )

    def _is_duplicate(self, phash: str, seen_hashes: Dict[str, Path]) -> bool:
        for existing_hash, existing_path in seen_hashes.items():
            distance = self._hamming_distance(phash, existing_hash)
            if distance < self.PHASH_DISTANCE_THRESHOLD:
                return True
        return False

    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        if len(hash1) != len(hash2):
            return len(hash1) + len(hash2)
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    def _is_blank_or_black(self, img: Image.Image) -> bool:
        grayscale = img.convert("L")
        histogram = grayscale.histogram()
        
        total_pixels = sum(histogram)
        if total_pixels == 0:
            return True
        
        dark_pixels = sum(histogram[:self.MIN_BRIGHTNESS])
        light_pixels = sum(histogram[self.MAX_BRIGHTNESS:])
        
        dark_ratio = dark_pixels / total_pixels
        light_ratio = light_pixels / total_pixels
        
        if dark_ratio > 0.95:
            return True
        if light_ratio > 0.95:
            return True
        
        return False

    def _compute_similarity(self, phash1: str, phash2: str) -> float:
        distance = self._hamming_distance(phash1, phash2)
        max_distance = len(phash1) * 4
        return 1.0 - (distance / max_distance)

    def compute_clip_similarity(self, image_path1: Path, image_path2: Path) -> float:
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch
            
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            img1 = Image.open(image_path1).convert("RGB")
            img2 = Image.open(image_path2).convert("RGB")
            
            inputs = processor(images=[img1, img2], return_tensors="pt")
            outputs = model.get_image_features(**inputs)
            
            similarity = torch.nn.functional.cosine_similarity(outputs[0], outputs[1], dim=0).item()
            return similarity
        except Exception:
            return 0.0

    def validate_clip_similarity(self, generated_path: Path, expected_range: Tuple[float, float] = (0.6, 0.85)) -> bool:
        if not self.original_image_path:
            return True
        
        similarity = self.compute_clip_similarity(self.original_image_path, generated_path)
        return expected_range[0] <= similarity <= expected_range[1]