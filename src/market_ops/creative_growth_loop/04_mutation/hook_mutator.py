"""Hook Mutator - V15素材增长闭环"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class HookMutation:
    hook_type: str
    hook_text: str
    weight: float = 0.4
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_type": self.hook_type,
            "hook_text": self.hook_text,
            "weight": self.weight,
        }


class HookMutator:
    HOOK_WEIGHT = 0.40
    
    HOOK_TEMPLATES = {
        "secret": [
            "Secret Dragon Inside",
            "Only 1% Know This Secret",
            "Hidden Treasure Revealed",
            "Secret Level Discovered",
            "The Secret to Winning",
            "Unlock Secret Character",
            "Secret Evolution Path",
            "What's The Secret?",
        ],
        "challenge": [
            "Can You Reach Lv100?",
            "Only 1% Can Beat This",
            "Challenge Accepted?",
            "Impossible Level?",
            "Can You Survive?",
            "Beat This Challenge",
            "Pro Challenge Mode",
            "Ultimate Challenge",
        ],
        "wrong_choice": [
            "Don't Merge Them!",
            "Wrong Choice!",
            "Don't Click This",
            "Stop! Wrong Way",
            "Don't Do This",
            "Warning: Wrong Move",
            "Think Before You Click",
            "This Choice Will Fail",
        ],
        "before_after": [
            "Broken Farm → Castle",
            "Lv1 → Lv100",
            "Before vs After",
            "From Zero to Hero",
            "Evolution in 3 Steps",
            "Small → Legendary",
            "Transform Your Game",
            "Level Up Fast",
        ],
        "reward": [
            "Get Golden Dragon",
            "Claim Your Reward",
            "Free Treasure Inside",
            "Unlock Legendary",
            "Reward Waiting",
            "Collect Your Prize",
            "Exclusive Reward",
            "Bonus Unlocked",
        ],
        "curiosity": [
            "What Happens Next?",
            "Why Is Everyone Stuck?",
            "What's Inside?",
            "Guess The Result",
            "Find Out Now",
            "Discover The Truth",
            "Mystery Revealed",
            "The Answer Is...",
        ],
        "urgency": [
            "Last Chance!",
            "Limited Time Only",
            "Act Now!",
            "Time Running Out",
            "Don't Miss This",
            "Hurry! Ends Soon",
            "Final Warning",
            "Only Today",
        ],
        "level": [
            "Wait For Lv100",
            "Level 100 Evolution",
            "Max Level Reached",
            "Ultimate Level",
            "Level Up Fast",
            "Reach Max Level",
            "Level 100 Secret",
            "Final Level Boss",
        ],
    }
    
    def __init__(self):
        pass
    
    def generate_mutations(self, count: int = 10) -> List[HookMutation]:
        """生成Hook变体"""
        mutations = []
        
        hook_types = list(self.HOOK_TEMPLATES.keys())
        
        for i in range(count):
            hook_type = random.choice(hook_types)
            templates = self.HOOK_TEMPLATES[hook_type]
            hook_text = random.choice(templates)
            
            mutation = HookMutation(
                hook_type=hook_type,
                hook_text=hook_text,
                weight=self.HOOK_WEIGHT,
            )
            mutations.append(mutation)
        
        return mutations
    
    def generate_from_winner(self, winner_hook: str, count: int = 10) -> List[HookMutation]:
        """从赢家Hook生成变体"""
        mutations = []
        
        if winner_hook in self.HOOK_TEMPLATES:
            templates = self.HOOK_TEMPLATES[winner_hook]
            selected = random.sample(templates, min(count, len(templates)))
            
            for hook_text in selected:
                mutation = HookMutation(
                    hook_type=winner_hook,
                    hook_text=hook_text,
                    weight=self.HOOK_WEIGHT,
                )
                mutations.append(mutation)
        
        other_types = [t for t in self.HOOK_TEMPLATES.keys() if t != winner_hook]
        remaining = count - len(mutations)
        
        for i in range(remaining):
            hook_type = random.choice(other_types)
            hook_text = random.choice(self.HOOK_TEMPLATES[hook_type])
            
            mutation = HookMutation(
                hook_type=hook_type,
                hook_text=hook_text,
                weight=self.HOOK_WEIGHT * 0.5,
            )
            mutations.append(mutation)
        
        return mutations


class RewardMutator:
    REWARD_WEIGHT = 0.20
    
    REWARD_TYPES = [
        "Dragon", "Golden Dragon", "Phoenix", "Treasure",
        "Castle", "Diamond Tree", "Unicorn", "Magic Item",
        "Legendary Creature", "Rare Egg", "Golden Egg",
        "Crystal Dragon", "Rainbow Phoenix", "Secret Pet",
    ]
    
    def generate_mutations(self, count: int = 5) -> List[Dict[str, Any]]:
        """生成Reward变体"""
        mutations = []
        
        for i in range(count):
            reward = random.choice(self.REWARD_TYPES)
            
            mutations.append({
                "reward_type": "reward",
                "reward_value": reward,
                "weight": self.REWARD_WEIGHT,
            })
        
        return mutations


class EmotionMutator:
    EMOTION_WEIGHT = 0.15
    
    EMOTION_TYPES = [
        "surprise", "panic", "happy", "wow", "cry",
        "angry", "excited", "curious", "proud", "mysterious",
        "shocked", "amazed", "thrilled", "nervous", "confident",
    ]
    
    def generate_mutations(self, count: int = 5) -> List[Dict[str, Any]]:
        """生成Emotion变体"""
        mutations = []
        
        for i in range(count):
            emotion = random.choice(self.EMOTION_TYPES)
            
            mutations.append({
                "emotion_type": "emotion",
                "emotion_value": emotion,
                "weight": self.EMOTION_WEIGHT,
            })
        
        return mutations


class ProgressMutator:
    PROGRESS_WEIGHT = 0.10
    
    PROGRESS_TYPES = [
        "Lv10", "Lv50", "Lv100", "Ultimate", "Secret",
        "Final", "Evolution", "Max", "Legendary", "Complete",
        "Level 1", "Level 50", "Level 100", "Max Level",
    ]
    
    def generate_mutations(self, count: int = 5) -> List[Dict[str, Any]]:
        """生成Progress变体"""
        mutations = []
        
        for i in range(count):
            progress = random.choice(self.PROGRESS_TYPES)
            
            mutations.append({
                "progress_type": "progress",
                "progress_value": progress,
                "weight": self.PROGRESS_WEIGHT,
            })
        
        return mutations


class OverlayMutator:
    OVERLAY_WEIGHT = 0.10
    
    OVERLAY_TYPES = [
        "Arrow", "Circle", "Glow", "Text", "+999",
        "NEW", "SECRET", "LEVEL100", "Question Mark",
        "Exclamation", "Star", "Badge", "Banner",
    ]
    
    def generate_mutations(self, count: int = 5) -> List[Dict[str, Any]]:
        """生成Overlay变体"""
        mutations = []
        
        for i in range(count):
            overlay = random.choice(self.OVERLAY_TYPES)
            
            mutations.append({
                "overlay_type": "overlay",
                "overlay_value": overlay,
                "weight": self.OVERLAY_WEIGHT,
            })
        
        return mutations


class SubjectMutator:
    SUBJECT_WEIGHT = 0.05
    
    SUBJECT_TYPES = [
        "Dragon", "Phoenix", "Unicorn", "Wolf",
        "Cat", "Fox", "Bear", "Rabbit",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        """生成Subject变体"""
        mutations = []
        
        for i in range(count):
            subject = random.choice(self.SUBJECT_TYPES)
            
            mutations.append({
                "subject_type": "subject",
                "subject_value": subject,
                "weight": self.SUBJECT_WEIGHT,
            })
        
        return mutations


class CompositionMutator:
    COMPOSITION_WEIGHT = 0.05
    
    COMPOSITION_TYPES = [
        "Split Screen", "Before After", "Vertical Stack",
        "Horizontal Split", "Center Focus", "Side Comparison",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        """生成Composition变体"""
        mutations = []
        
        for i in range(count):
            composition = random.choice(self.COMPOSITION_TYPES)
            
            mutations.append({
                "composition_type": "composition",
                "composition_value": composition,
                "weight": self.COMPOSITION_WEIGHT,
            })
        
        return mutations


class CostumeMutator:
    """服装变异器 (Port from old creative_loop mutation_engine)"""
    COSTUME_WEIGHT = 0.03
    
    COSTUME_OPTIONS = [
        "wizard", "superhero", "princess", "pirate", "knight", "ninja", "chef", "doctor",
        "detective", "cowboy", "viking", "samurai", "angel", "devil", "robot", "magician",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        mutations = []
        for i in range(count):
            costume = random.choice(self.COSTUME_OPTIONS)
            mutations.append({
                "costume_type": "costume",
                "costume_value": costume,
                "weight": self.COSTUME_WEIGHT,
            })
        return mutations


class PoseMutator:
    """姿势变异器 (Port from old creative_loop mutation_engine)"""
    POSE_WEIGHT = 0.03
    
    POSE_OPTIONS = [
        "running", "flying", "jumping", "standing", "sitting", "fighting",
        "casting spell", "dancing", "meditating", "waving", "pointing",
        "holding object", "levitating", "crouching", "laughing", "thinking",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        mutations = []
        for i in range(count):
            pose = random.choice(self.POSE_OPTIONS)
            mutations.append({
                "pose_type": "pose",
                "pose_value": pose,
                "weight": self.POSE_WEIGHT,
            })
        return mutations


class CameraMutator:
    """镜头变异器 (Port from old creative_loop mutation_engine)"""
    CAMERA_WEIGHT = 0.03
    
    CAMERA_OPTIONS = [
        "close up", "top view", "fisheye", "wide shot", "low angle", "high angle",
        "side view", "action shot", "portrait", "landscape", "macro", "panoramic",
        "dutch angle", "tracking shot", "zoom in", "bird eye",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        mutations = []
        for i in range(count):
            camera = random.choice(self.CAMERA_OPTIONS)
            mutations.append({
                "camera_type": "camera",
                "camera_value": camera,
                "weight": self.CAMERA_WEIGHT,
            })
        return mutations


class LightingMutator:
    """光照变异器 (Port from old creative_loop mutation_engine)"""
    LIGHTING_WEIGHT = 0.03
    
    LIGHTING_OPTIONS = [
        "sunset", "neon", "cinematic", "soft", "dramatic", "natural", "studio",
        "candlelight", "neon glow", "moonlight", "spotlight", "ambient", "harsh",
        "golden hour", "blue hour", "fluorescent",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        mutations = []
        for i in range(count):
            lighting = random.choice(self.LIGHTING_OPTIONS)
            mutations.append({
                "lighting_type": "lighting",
                "lighting_value": lighting,
                "weight": self.LIGHTING_WEIGHT,
            })
        return mutations


class ColorMutator:
    """颜色变异器 (Port from old creative_loop mutation_engine)"""
    COLOR_WEIGHT = 0.03
    
    COLOR_OPTIONS = [
        "purple", "blue", "rainbow", "gold", "silver", "neon green", "cyan", "coral",
        "pink", "magenta", "lavender", "platinum", "teal", "burgundy", "turquoise",
        "navy", "electric blue", "sky", "ocean",
    ]
    
    def generate_mutations(self, count: int = 3) -> List[Dict[str, Any]]:
        mutations = []
        for i in range(count):
            color = random.choice(self.COLOR_OPTIONS)
            mutations.append({
                "color_type": "color",
                "color_value": color,
                "weight": self.COLOR_WEIGHT,
            })
        return mutations