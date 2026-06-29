"""完整闭环系统 - Creative Factory Pipeline"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class AdvancedVisualDNA:
    hook_type: str
    reward_type: str
    emotion_type: str
    progress_depth: int
    collection_density: int
    character_count: int
    mystery_score: int
    cute_score: int
    color_theme: str
    camera_distance: str
    composition: str
    particle_strength: int
    creative_id: str = ""
    generation: int = 1
    parent_id: str = ""
    performance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in vars(self).items()}

@dataclass
class CreativePerformance:
    creative_id: str
    ctr: float = 0.0
    cpc: float = 0.0
    ipm: float = 0.0
    cvr: float = 0.0
    d1_retention: float = 0.0
    roas_d3: float = 0.0
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0

class WinnerEngine:
    def select_winners(self, performances: List[CreativePerformance], top_n: int = 20) -> List[str]:
        performances.sort(key=lambda p: (p.ctr, p.ipm, p.roas_d3), reverse=True)
        return [p.creative_id for p in performances[:top_n]]

class DNASimilarityEngine:
    def calculate_similarity(self, dna1: AdvancedVisualDNA, dna2: AdvancedVisualDNA) -> float:
        score = 0
        if dna1.hook_type == dna2.hook_type: score += 0.25
        if dna1.reward_type == dna2.reward_type: score += 0.2
        if dna1.color_theme == dna2.color_theme: score += 0.15
        score += 0.15 * (1 - abs(dna1.cute_score - dna2.cute_score) / 10)
        score += 0.15 * (1 - abs(dna1.mystery_score - dna2.mystery_score) / 10)
        score += 0.1 * (1 - abs(dna1.progress_depth - dna2.progress_depth) / 10)
        return min(score, 1.0)
    
    def filter_similar(self, dnas: List[AdvancedVisualDNA], threshold: float = 0.85) -> List[AdvancedVisualDNA]:
        unique = []
        for dna in dnas:
            is_unique = True
            for existing in unique:
                if self.calculate_similarity(dna, existing) > threshold:
                    is_unique = False
                    break
            if is_unique:
                unique.append(dna)
        return unique

class MutationEngine:
    def __init__(self):
        self.reward_pool = ["dragon", "unicorn", "fox", "owl", "phoenix", "cat", "rabbit", "bear", "treasure", "castle", "egg"]
        self.color_pool = ["purple", "dark_purple", "blue_gold", "warm_gold", "lavender", "mysterious_blue", "enchanted", "glowing_gold"]
    
    def mutate(self, dna: AdvancedVisualDNA, mutation_rate: float = 0.3) -> AdvancedVisualDNA:
        new_dna = AdvancedVisualDNA(**dna.to_dict())
        new_dna.creative_id = f"mut_{dna.creative_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        new_dna.parent_id = dna.creative_id
        new_dna.generation = dna.generation + 1
        
        if mutation_rate > 0.5:
            new_dna.reward_type = self.reward_pool[hash(dna.creative_id) % len(self.reward_pool)]
        
        if mutation_rate > 0.3:
            new_dna.color_theme = self.color_pool[hash(dna.creative_id + "color") % len(self.color_pool)]
        
        new_dna.cute_score = min(10, max(1, dna.cute_score + (1 if mutation_rate > 0.5 else -1)))
        new_dna.mystery_score = min(10, max(1, dna.mystery_score + (1 if mutation_rate < 0.3 else -1)))
        
        return new_dna

class CreativeFactory:
    def __init__(self, project_name: str = "P04_Witch"):
        self.project_name = project_name
        self.output_dir = Path(f"output/{project_name}_Factory")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.winner_engine = WinnerEngine()
        self.similarity_engine = DNASimilarityEngine()
        self.mutation_engine = MutationEngine()
        
        self.seed_dnas = [
            AdvancedVisualDNA(
                creative_id="seed_1", hook_type="collection", reward_type="dragon", emotion_type="whimsical",
                progress_depth=1, collection_density=9, character_count=12, mystery_score=6, cute_score=9,
                color_theme="purple", camera_distance="medium", composition="hero_center", particle_strength=4
            ),
            AdvancedVisualDNA(
                creative_id="seed_2", hook_type="progress", reward_type="castle", emotion_type="mysterious",
                progress_depth=4, collection_density=3, character_count=1, mystery_score=8, cute_score=6,
                color_theme="dark_purple", camera_distance="medium", composition="split", particle_strength=3
            ),
            AdvancedVisualDNA(
                creative_id="seed_3", hook_type="collection", reward_type="creature", emotion_type="enchanting",
                progress_depth=3, collection_density=7, character_count=8, mystery_score=5, cute_score=8,
                color_theme="gold_purple", camera_distance="close", composition="layered", particle_strength=4
            ),
            AdvancedVisualDNA(
                creative_id="seed_4", hook_type="curiosity", reward_type="egg", emotion_type="mysterious",
                progress_depth=2, collection_density=6, character_count=6, mystery_score=7, cute_score=9,
                color_theme="warm_gold", camera_distance="close", composition="hero_center", particle_strength=3
            ),
        ]
    
    def run_generation(self, input_dnas: List[AdvancedVisualDNA], num_variants: int = 25) -> List[AdvancedVisualDNA]:
        all_variants = []
        for dna in input_dnas:
            for i in range(num_variants):
                mutation_rate = (i / num_variants)
                variant = self.mutation_engine.mutate(dna, mutation_rate)
                variant.creative_id = f"{dna.creative_id}_mut_{i}"
                all_variants.append(variant)
        
        return self.similarity_engine.filter_similar(all_variants)
    
    def dna_to_prompt(self, dna: AdvancedVisualDNA) -> str:
        emotion_map = {
            "whimsical": "whimsical and magical",
            "mysterious": "mysterious and enchanting",
            "enchanting": "enchanting and magical",
        }
        
        reward_map = {
            "dragon": "cute baby dragon",
            "unicorn": "adorable unicorn",
            "fox": "cute fox",
            "owl": "cute owl",
            "phoenix": "colorful phoenix",
            "castle": "magical castle",
            "egg": "glowing magical egg",
            "secret_dragon": "mysterious secret dragon",
        }
        
        hook_prompts = {
            "collection": f"showing {dna.collection_density} cute magical creatures to collect",
            "progress": f"evolution progression showing {dna.progress_depth} stages",
            "curiosity": "mysterious magical surprise with question mark",
        }
        
        parts = [
            "3D cartoon style mobile game advertisement",
            f"{emotion_map.get(dna.emotion_type, dna.emotion_type)} atmosphere",
            f"{reward_map.get(dna.reward_type, dna.reward_type)} as main subject",
            hook_prompts[dna.hook_type],
            f"color theme: {dna.color_theme}",
            f"{dna.camera_distance} camera view",
            f"{dna.composition} composition",
            "professional game advertising quality",
            "mobile portrait 9:16 aspect ratio",
        ]
        
        return ", ".join(p for p in parts if p)
    
    def run_full_cycle(self, generations: int = 3):
        current_dnas = self.seed_dnas
        
        for gen in range(generations):
            print(f"\n=== Generation {gen + 1} ===")
            
            variants = self.run_generation(current_dnas, num_variants=25)
            print(f"Generated {len(variants)} variants")
            
            prompts = [{
                "creative_id": dna.creative_id,
                "hook_type": dna.hook_type,
                "reward_type": dna.reward_type,
                "prompt": self.dna_to_prompt(dna),
                "dna": dna.to_dict()
            } for dna in variants]
            
            gen_dir = self.output_dir / f"generation_{gen + 1}"
            gen_dir.mkdir(exist_ok=True)
            
            with open(gen_dir / "dnas.json", "w", encoding="utf-8") as f:
                json.dump([d.to_dict() for d in variants], f, indent=2, ensure_ascii=False)
            
            with open(gen_dir / "prompts.json", "w", encoding="utf-8") as f:
                json.dump(prompts, f, indent=2, ensure_ascii=False)
            
            print(f"Saved to {gen_dir}")
            
            current_dnas = variants[:20]

def main():
    factory = CreativeFactory()
    factory.run_full_cycle(generations=3)
    print("\n✅ Creative Factory Pipeline completed!")

if __name__ == "__main__":
    main()