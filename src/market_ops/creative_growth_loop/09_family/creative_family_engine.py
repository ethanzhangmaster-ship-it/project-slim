"""Creative Family Engine - V15素材增长闭环"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from ..08_scoring.creative_score_engine import CreativeScore


@dataclass
class CreativeFamily:
    family_id: str
    parent_winner: str
    generation: int
    variants: List[str]
    top_scores: List[float]
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_id": self.family_id,
            "parent_winner": self.parent_winner,
            "generation": self.generation,
            "variants": self.variants,
            "top_scores": self.top_scores,
            "created_at": self.created_at,
        }


class CreativeFamilyEngine:
    VARIANTS_PER_FAMILY = 20
    TOP_N_PER_FAMILY = 3
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/families"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_family(self, winner_id: str, variant_images: List[Path],
                      scores: List[CreativeScore], generation: int = 1) -> CreativeFamily:
        """创建素材家族"""
        from datetime import datetime
        
        family_id = f"family_{winner_id}_gen{generation}"
        family_dir = self.output_dir / family_id
        family_dir.mkdir(parents=True, exist_ok=True)
        
        sorted_scores = sorted(scores, key=lambda x: x.final_score, reverse=True)
        top_scores = sorted_scores[:self.TOP_N_PER_FAMILY]
        
        variants = []
        for i, score in enumerate(top_scores):
            if score.image_path.exists():
                dest_name = f"variant_{i:02d}_score{score.final_score:.1f}.png"
                dest_path = family_dir / dest_name
                shutil.copy(str(score.image_path), str(dest_path))
                variants.append(str(dest_path))
        
        for i, img_path in enumerate(variant_images[:self.VARIANTS_PER_FAMILY - len(variants)]):
            if img_path.exists() and img_path not in [s.image_path for s in top_scores]:
                dest_name = f"variant_{len(variants):02d}.png"
                dest_path = family_dir / dest_name
                shutil.copy(str(img_path), str(dest_path))
                variants.append(str(dest_path))
        
        family = CreativeFamily(
            family_id=family_id,
            parent_winner=winner_id,
            generation=generation,
            variants=variants,
            top_scores=[s.final_score for s in top_scores],
            created_at=datetime.now().isoformat(),
        )
        
        self._save_family(family)
        return family
    
    def _save_family(self, family: CreativeFamily) -> Path:
        """保存家族"""
        family_path = self.output_dir / f"{family.family_id}.json"
        
        with open(family_path, "w", encoding="utf-8") as f:
            json.dump(family.to_dict(), f, indent=2, ensure_ascii=False)
        
        return family_path
    
    def load_family(self, family_id: str) -> CreativeFamily:
        """加载家族"""
        family_path = self.output_dir / f"{family_id}.json"
        
        if family_path.exists():
            with open(family_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return CreativeFamily(
                    family_id=data["family_id"],
                    parent_winner=data["parent_winner"],
                    generation=data["generation"],
                    variants=data["variants"],
                    top_scores=data["top_scores"],
                    created_at=data["created_at"],
                )
        
        return None
    
    def get_family_variants(self, family_id: str) -> List[Path]:
        """获取家族变体"""
        family = self.load_family(family_id)
        
        if family:
            return [Path(v) for v in family.variants if Path(v).exists()]
        
        return []
    
    def get_top_family_variant(self, family_id: str) -> Path:
        """获取家族Top变体"""
        family = self.load_family(family_id)
        
        if family and family.variants:
            return Path(family.variants[0])
        
        return None
    
    def list_all_families(self) -> List[CreativeFamily]:
        """列出所有家族"""
        families = []
        
        for json_file in self.output_dir.glob("family_*.json"):
            family = self.load_family(json_file.stem)
            if family:
                families.append(family)
        
        return sorted(families, key=lambda x: x.created_at, reverse=True)