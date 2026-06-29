"""P04 Witch Creative Factory - 升级版视觉DNA系统"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class AdvancedVisualDNA:
    hook_type: str  # collection, progress, curiosity
    reward_type: str  # dragon, castle, treasure, phoenix, etc.
    emotion_type: str  # whimsical, mysterious, enchanting, etc.
    
    progress_depth: int  # 1-10, 成长链长度
    collection_density: int  # 1-10, 收集物密度
    character_count: int  # 角色数量
    mystery_score: int  # 1-10, 神秘感
    cute_score: int  # 1-10, 可爱度
    
    color_theme: str  # purple, blue, gold, warm, etc.
    camera_distance: str  # close, medium, wide
    composition: str  # hero_center, split, layered, etc.
    particle_strength: int  # 1-5, 粒子效果强度
    
    # 附加信息
    creative_id: str = ""
    generation: int = 1
    parent_id: str = ""
    performance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "hook_type": self.hook_type,
            "reward_type": self.reward_type,
            "emotion_type": self.emotion_type,
            "progress_depth": self.progress_depth,
            "collection_density": self.collection_density,
            "character_count": self.character_count,
            "mystery_score": self.mystery_score,
            "cute_score": self.cute_score,
            "color_theme": self.color_theme,
            "camera_distance": self.camera_distance,
            "composition": self.composition,
            "particle_strength": self.particle_strength,
            "performance_score": self.performance_score,
        }

class CreativeFactory:
    """真正的创意工厂 - 支持遗传算法进化"""
    
    def __init__(self, project_name: str = "P04_Witch"):
        self.project_name = project_name
        self.output_dir = Path(f"output/{project_name}_Factory")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 种子赢家DNA
        self.seed_dnas = [
            AdvancedVisualDNA(
                creative_id="seed_1",
                hook_type="collection",
                reward_type="dragon",
                emotion_type="whimsical",
                progress_depth=1,
                collection_density=9,
                character_count=12,
                mystery_score=6,
                cute_score=9,
                color_theme="purple",
                camera_distance="medium",
                composition="hero_center",
                particle_strength=4,
                performance_score=8.5,
            ),
            AdvancedVisualDNA(
                creative_id="seed_2",
                hook_type="progress",
                reward_type="castle",
                emotion_type="mysterious",
                progress_depth=4,
                collection_density=3,
                character_count=1,
                mystery_score=8,
                cute_score=6,
                color_theme="dark_purple",
                camera_distance="medium",
                composition="split",
                particle_strength=3,
                performance_score=7.8,
            ),
            AdvancedVisualDNA(
                creative_id="seed_3",
                hook_type="collection",
                reward_type="creature",
                emotion_type="enchanting",
                progress_depth=3,
                collection_density=7,
                character_count=8,
                mystery_score=5,
                cute_score=8,
                color_theme="gold_purple",
                camera_distance="close",
                composition="layered",
                particle_strength=4,
                performance_score=8.2,
            ),
            AdvancedVisualDNA(
                creative_id="seed_4",
                hook_type="collection",
                reward_type="egg",
                emotion_type="whimsical",
                progress_depth=2,
                collection_density=6,
                character_count=6,
                mystery_score=7,
                cute_score=9,
                color_theme="warm_gold",
                camera_distance="close",
                composition="hero_center",
                particle_strength=3,
                performance_score=8.0,
            ),
        ]
    
    def generate_first_batch(self) -> List[AdvancedVisualDNA]:
        """生成第一批24张素材的DNA"""
        print("\n=== 生成第一批24张素材 ===")
        
        dnas = []
        
        # Collection: 8张
        print("\n[Collection 8张]")
        collection_dnas = self._generate_collection_mutations(8)
        dnas.extend(collection_dnas)
        
        # Progress: 8张
        print("\n[Progress 8张]")
        progress_dnas = self._generate_progress_mutations(8)
        dnas.extend(progress_dnas)
        
        # Mystery: 8张
        print("\n[Mystery 8张]")
        mystery_dnas = self._generate_mystery_mutations(8)
        dnas.extend(mystery_dnas)
        
        self._save_dnas(dnas, "batch_001")
        print(f"\n✅ 第一批24张素材DNA已生成")
        
        return dnas
    
    def _generate_collection_mutations(self, count: int) -> List[AdvancedVisualDNA]:
        """生成收集类变体"""
        rewards = ["dragon", "unicorn", "fox", "owl", "phoenix", "cat", "rabbit", "bear"]
        dnas = []
        
        for i, reward in enumerate(rewards[:count]):
            dna = AdvancedVisualDNA(
                creative_id=f"coll_{i+1:02d}",
                generation=1,
                parent_id="seed_1",
                hook_type="collection",
                reward_type=reward,
                emotion_type="whimsical",
                progress_depth=1,
                collection_density=random.randint(7, 10),
                character_count=random.randint(8, 15),
                mystery_score=random.randint(4, 7),
                cute_score=random.randint(7, 10),
                color_theme=random.choice(["purple", "gold_purple", "warm_gold", "lavender"]),
                camera_distance="medium",
                composition="hero_center",
                particle_strength=random.randint(3, 5),
            )
            dnas.append(dna)
            print(f"  coll_{i+1:02d}: {reward} - 密度:{dna.collection_density} 可爱:{dna.cute_score}")
        
        return dnas
    
    def _generate_progress_mutations(self, count: int) -> List[AdvancedVisualDNA]:
        """生成成长类变体"""
        chains = [
            {"name": "dragon_chain", "reward": "dragon", "depth": 4},
            {"name": "flower_chain", "reward": "tree", "depth": 4},
            {"name": "witch_chain", "reward": "queen", "depth": 4},
            {"name": "castle_chain", "reward": "castle", "depth": 4},
            {"name": "phoenix_chain", "reward": "phoenix", "depth": 4},
            {"name": "egg_chain", "reward": "egg", "depth": 3},
            {"name": "treasure_chain", "reward": "treasure", "depth": 4},
            {"name": "magic_chain", "reward": "magic", "depth": 3},
        ]
        dnas = []
        
        for i, chain in enumerate(chains[:count]):
            dna = AdvancedVisualDNA(
                creative_id=f"prog_{i+1:02d}",
                generation=1,
                parent_id="seed_2",
                hook_type="progress",
                reward_type=chain["reward"],
                emotion_type="mysterious",
                progress_depth=chain["depth"],
                collection_density=random.randint(2, 5),
                character_count=random.randint(1, 3),
                mystery_score=random.randint(6, 9),
                cute_score=random.randint(4, 7),
                color_theme=random.choice(["dark_purple", "blue_gold", "purple_magenta", "dark_blue"]),
                camera_distance="medium",
                composition="split",
                particle_strength=random.randint(2, 4),
            )
            dnas.append(dna)
            print(f"  prog_{i+1:02d}: {chain['name']} - 深度:{dna.progress_depth} 神秘:{dna.mystery_score}")
        
        return dnas
    
    def _generate_mystery_mutations(self, count: int) -> List[AdvancedVisualDNA]:
        """生成好奇类变体"""
        mysteries = [
            {"name": "mystery_egg", "reward": "egg"},
            {"name": "mystery_dragon", "reward": "secret_dragon"},
            {"name": "mystery_witch", "reward": "secret_witch"},
            {"name": "mystery_castle", "reward": "secret_castle"},
            {"name": "mystery_box", "reward": "mystery_box"},
            {"name": "mystery_potion", "reward": "potion"},
            {"name": "mystery_rune", "reward": "rune"},
            {"name": "mystery_forest", "reward": "forest"},
        ]
        dnas = []
        
        for i, mystery in enumerate(mysteries[:count]):
            dna = AdvancedVisualDNA(
                creative_id=f"myst_{i+1:02d}",
                generation=1,
                parent_id="seed_4",
                hook_type="curiosity",
                reward_type=mystery["reward"],
                emotion_type="mysterious",
                progress_depth=random.randint(1, 2),
                collection_density=random.randint(1, 4),
                character_count=random.randint(1, 4),
                mystery_score=random.randint(8, 10),
                cute_score=random.randint(5, 8),
                color_theme=random.choice(["dark_purple", "mysterious_blue", "glowing_gold", "enchanted"]),
                camera_distance="close",
                composition="hero_center",
                particle_strength=random.randint(3, 5),
            )
            dnas.append(dna)
            print(f"  myst_{i+1:02d}: {mystery['name']} - 神秘:{dna.mystery_score}")
        
        return dnas
    
    def dna_to_prompt(self, dna: AdvancedVisualDNA) -> str:
        """将DNA转换为提示词"""
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
            "tree": "magical tree",
            "queen": "witch queen",
            "secret_dragon": "mysterious secret dragon",
            "secret_witch": "mysterious secret witch",
            "mystery_box": "mysterious box with question mark",
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
            "sparkling magical particles" if dna.particle_strength >= 3 else "",
            "professional game advertising quality",
            "mobile portrait 9:16 aspect ratio",
        ]
        
        return ", ".join(p for p in parts if p)
    
    def generate_prompts(self, dnas: List[AdvancedVisualDNA]) -> List[Dict[str, str]]:
        """生成所有提示词"""
        prompts = []
        for dna in dnas:
            prompts.append({
                "creative_id": dna.creative_id,
                "hook_type": dna.hook_type,
                "reward_type": dna.reward_type,
                "prompt": self.dna_to_prompt(dna),
                "dna": dna.to_dict(),
            })
        
        return prompts
    
    def _save_dnas(self, dnas: List[AdvancedVisualDNA], batch_name: str) -> Path:
        """保存DNA到文件"""
        data = [dna.to_dict() for dna in dnas]
        path = self.output_dir / f"{batch_name}_dnas.json"
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return path

import random

def main():
    factory = CreativeFactory()
    
    # 生成第一批24张素材DNA
    dnas = factory.generate_first_batch()
    
    # 生成提示词
    prompts = factory.generate_prompts(dnas)
    
    # 保存提示词
    with open(factory.output_dir / "batch_001_prompts.json", "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 输出目录: {factory.output_dir}")
    print(f"📄 DNA文件: batch_001_dnas.json")
    print(f"📄 提示词文件: batch_001_prompts.json")
    print(f"📊 素材分布: Collection(8) + Progress(8) + Mystery(8) = 24张")
    
    # 显示部分提示词示例
    print("\n🎯 提示词示例:")
    for p in prompts[:3]:
        print(f"\n{p['creative_id']} ({p['hook_type']}):")
        print(f"  {p['prompt'][:100]}...")

if __name__ == "__main__":
    main()