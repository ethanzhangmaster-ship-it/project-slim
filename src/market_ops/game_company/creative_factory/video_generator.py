from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedVideo:
    video_id: str
    title: str
    duration: int = 0
    hooks: List[str] = field(default_factory=list)
    scenes: List[str] = field(default_factory=list)
    cta: str = ""
    quality_score: float = 0.0


class VideoGenerator:
    def __init__(self):
        self.videos: Dict[str, GeneratedVideo] = {}

    def generate(self, game_concept, count: int = 5) -> List[GeneratedVideo]:
        videos = []
        
        if isinstance(game_concept, dict):
            name = game_concept.get("name", "Game")
            genre = game_concept.get("genre", "")
            core_loop = game_concept.get("core_loop", [])
        else:
            name = game_concept.name
            genre = game_concept.genre
            core_loop = game_concept.core_loop

        hooks = self._generate_hooks(genre)
        scenes = self._generate_scenes(core_loop)

        for i in range(count):
            video = GeneratedVideo(
                video_id=f"video_{hash(name + str(i)) % 10000:04d}",
                title=f"{name} - Video {i+1}",
                duration=15 + i * 5,
                hooks=hooks[i % len(hooks)],
                scenes=scenes,
                cta="Download Now!",
                quality_score=self._calculate_quality(genre),
            )
            videos.append(video)
            self.videos[video.video_id] = video
        
        return videos

    def _generate_hooks(self, genre: str) -> List[str]:
        hooks_map = {
            "Merge + Decoration": [
                "Watch this magical merge!",
                "Create your dream garden!",
                "Can you merge to level 10?",
                "Surprising merge results!",
                "Cozy gameplay awaits!",
            ],
            "Cozy Games": [
                "Relaxing gameplay",
                "Discover hidden secrets",
                "Build your sanctuary",
            ],
        }
        return hooks_map.get(genre, ["Play now!"])

    def _generate_scenes(self, core_loop: List[str]) -> List[str]:
        scenes = []
        if "Merge" in core_loop:
            scenes.append("Merge Animation")
        if "Reward" in core_loop:
            scenes.append("Reward Reveal")
        if "Decoration" in core_loop:
            scenes.append("Decoration Showcase")
        if "Retention" in core_loop:
            scenes.append("Progression")
        return scenes

    def _calculate_quality(self, genre: str) -> float:
        base = 0.85
        if "Cozy" in genre or "Witch" in genre:
            base += 0.05
        return min(base, 0.95)

    def generate_demo(self) -> List[GeneratedVideo]:
        concept = {"name": "Cozy Witch Garden", "genre": "Merge + Decoration", "core_loop": ["Merge", "Reward", "Decoration", "Retention"]}
        return self.generate(concept, 3)
