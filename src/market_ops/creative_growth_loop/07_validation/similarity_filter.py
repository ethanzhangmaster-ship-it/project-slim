"""Similarity Filter - V15素材增长闭环"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import imagehash
from PIL import Image


@dataclass
class FilterResult:
    image_path: Path
    is_valid: bool
    reason: str = ""
    phash: str = ""
    clip_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_path": str(self.image_path),
            "is_valid": self.is_valid,
            "reason": self.reason,
            "phash": self.phash,
            "clip_score": self.clip_score,
        }


class SimilarityFilter:
    PHASH_DISTANCE_THRESHOLD = 5
    CLIP_MIN = 0.6
    CLIP_MAX = 0.95
    CLIP_TARGET_RANGE = (0.7, 0.9)
    
    def __init__(self, original_image_path: str = None):
        self.original_image_path = Path(original_image_path) if original_image_path else None
        self.original_phash = self._compute_phash(self.original_image_path) if self.original_image_path else None
    
    def _compute_phash(self, image_path: Path) -> Optional[str]:
        """计算phash"""
        try:
            img = Image.open(image_path)
            return str(imagehash.phash(img))
        except Exception:
            return None
    
    def filter_images(self, image_paths: List[Path]) -> List[FilterResult]:
        """过滤图片"""
        results = []
        seen_hashes = {}
        
        for image_path in image_paths:
            result = self._filter_single(image_path, seen_hashes)
            results.append(result)
            
            if result.is_valid and result.phash:
                seen_hashes[result.phash] = image_path
        
        return results
    
    def _filter_single(self, image_path: Path, seen_hashes: Dict[str, Path]) -> FilterResult:
        """过滤单个图片"""
        if not image_path.exists():
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason="File not found"
            )
        
        try:
            img = Image.open(image_path)
        except Exception as e:
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason=f"Cannot open image: {str(e)}"
            )
        
        phash = str(imagehash.phash(img))
        
        if self._is_duplicate(phash, seen_hashes):
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason="Duplicate image (phash distance < 5)",
                phash=phash
            )
        
        if self.original_phash:
            clip_score = self._compute_similarity(phash, self.original_phash)
            
            if clip_score > self.CLIP_MAX:
                return FilterResult(
                    image_path=image_path,
                    is_valid=False,
                    reason=f"Too similar to original (CLIP > 0.95: {clip_score:.2f})",
                    phash=phash,
                    clip_score=clip_score
                )
            
            if clip_score < self.CLIP_MIN:
                return FilterResult(
                    image_path=image_path,
                    is_valid=False,
                    reason=f"Too different from original (CLIP < 0.6: {clip_score:.2f})",
                    phash=phash,
                    clip_score=clip_score
                )
            
            if not (self.CLIP_TARGET_RANGE[0] <= clip_score <= self.CLIP_TARGET_RANGE[1]):
                return FilterResult(
                    image_path=image_path,
                    is_valid=True,
                    reason=f"Outside target range but acceptable ({clip_score:.2f})",
                    phash=phash,
                    clip_score=clip_score
                )
        
        return FilterResult(
            image_path=image_path,
            is_valid=True,
            phash=phash
        )
    
    def _is_duplicate(self, phash: str, seen_hashes: Dict[str, Path]) -> bool:
        """检查是否重复"""
        for existing_hash in seen_hashes.keys():
            distance = self._hamming_distance(phash, existing_hash)
            if distance < self.PHASH_DISTANCE_THRESHOLD:
                return True
        return False
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """计算汉明距离"""
        if len(hash1) != len(hash2):
            return len(hash1) + len(hash2)
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    def _compute_similarity(self, phash1: str, phash2: str) -> float:
        """计算相似度"""
        distance = self._hamming_distance(phash1, phash2)
        max_distance = len(phash1) * 4
        return 1.0 - (distance / max_distance)
    
    def compute_clip_similarity(self, image_path1: Path, image_path2: Path) -> float:
        """计算CLIP相似度"""
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
            return self._compute_similarity(
                self._compute_phash(image_path1),
                self._compute_phash(image_path2)
            )


class DuplicateFilter:
    """重复图过滤器"""
    
    def __init__(self):
        self.seen_hashes = {}
    
    def filter_duplicates(self, image_paths: List[Path]) -> List[Path]:
        """过滤重复图"""
        unique_paths = []
        
        for image_path in image_paths:
            phash = self._compute_phash(image_path)
            
            if phash and phash not in self.seen_hashes:
                self.seen_hashes[phash] = image_path
                unique_paths.append(image_path)
        
        return unique_paths
    
    def _compute_phash(self, image_path: Path) -> Optional[str]:
        """计算phash"""
        try:
            img = Image.open(image_path)
            return str(imagehash.phash(img))
        except Exception:
            return None


class ImageQualityFilter:
    """图片质量过滤器"""
    
    MIN_WIDTH = 1024
    MIN_HEIGHT = 1792
    MIN_BRIGHTNESS = 10
    MAX_BRIGHTNESS = 245
    
    def filter_by_quality(self, image_paths: List[Path]) -> List[FilterResult]:
        """按质量过滤"""
        results = []
        
        for image_path in image_paths:
            result = self._check_quality(image_path)
            results.append(result)
        
        return results
    
    def _check_quality(self, image_path: Path) -> FilterResult:
        """检查质量"""
        if not image_path.exists():
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason="File not found"
            )
        
        try:
            img = Image.open(image_path)
        except Exception as e:
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason=f"Cannot open: {str(e)}"
            )
        
        width, height = img.size
        
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason=f"Size too small: {width}x{height}"
            )
        
        if self._is_blank_or_black(img):
            return FilterResult(
                image_path=image_path,
                is_valid=False,
                reason="Blank or black image"
            )
        
        return FilterResult(
            image_path=image_path,
            is_valid=True
        )
    
    def _is_blank_or_black(self, img: Image.Image) -> bool:
        """检查是否空白或黑图"""
        grayscale = img.convert("L")
        histogram = grayscale.histogram()
        
        total_pixels = sum(histogram)
        if total_pixels == 0:
            return True
        
        dark_pixels = sum(histogram[:self.MIN_BRIGHTNESS])
        light_pixels = sum(histogram[self.MAX_BRIGHTNESS:])
        
        if dark_pixels / total_pixels > 0.95:
            return True
        if light_pixels / total_pixels > 0.95:
            return True
        
        return False