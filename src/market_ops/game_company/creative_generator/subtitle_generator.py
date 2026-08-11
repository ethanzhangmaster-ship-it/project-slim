from typing import Dict, List, Any, Optional


SUBTITLE_TEMPLATES = {
    "collection": [
        {"time": "00:03", "text": "Collect them all!", "style": "fade in"},
        {"time": "00:06", "text": "200+ Magical Creatures", "style": "zoom in"},
        {"time": "00:09", "text": "LEGENDARY UNLOCKED!", "style": "scale up, glow"},
        {"time": "00:12", "text": "Merge to Evolve!", "style": "slide up"},
        {"time": "00:15", "text": "500,000+ Players", "style": "fade in"},
        {"time": "00:18", "text": "Download Free Now!", "style": "pulse"},
    ],
    "reward": [
        {"time": "00:03", "text": "What will you get?", "style": "typewriter"},
        {"time": "00:06", "text": "The moment of truth...", "style": "slow fade"},
        {"time": "00:09", "text": "MYTHIC REWARD!", "style": "explosion, gold"},
        {"time": "00:12", "text": "Keep merging for more!", "style": "slide left"},
        {"time": "00:15", "text": "Top Rated Game 2026", "style": "fade in"},
        {"time": "00:18", "text": "Claim Your Reward!", "style": "pulse, glow"},
    ],
    "curiosity": [
        {"time": "00:03", "text": "What's inside?", "style": "question mark animation"},
        {"time": "00:06", "text": "Only 1% can find this...", "style": "mystery glow"},
        {"time": "00:09", "text": "SECRET REVEALED!", "style": "flash, stars"},
        {"time": "00:12", "text": "Discover more secrets!", "style": "swipe in"},
        {"time": "00:15", "text": "Join the Mystery", "style": "fog reveal"},
        {"time": "00:18", "text": "Download to Find Out!", "style": "shake pulse"},
    ],
    "comparison": [
        {"time": "00:03", "text": "Day 1 vs Day 30", "style": "split screen"},
        {"time": "00:06", "text": "From nothing to HERO", "style": "morph transition"},
        {"time": "00:09", "text": "MAX LEVEL ACHIEVED", "style": "epic glow"},
        {"time": "00:12", "text": "Your journey starts now", "style": "fade in"},
        {"time": "00:15", "text": "4.8★ Rating", "style": "star pop"},
        {"time": "00:18", "text": "Start Your Transformation!", "style": "morph button"},
    ],
    "crisis": [
        {"time": "00:03", "text": "The Darkness is Coming", "style": "shake, dark"},
        {"time": "00:06", "text": "Only YOU can save us!", "style": "hero glow"},
        {"time": "00:09", "text": "VICTORY!", "style": "sunburst"},
        {"time": "00:12", "text": "Build your defense", "style": "slide up"},
        {"time": "00:15", "text": "1M+ Heroes Standing", "style": "counter"},
        {"time": "00:18", "text": "Join the Fight!", "style": "battle pulse"},
    ],
}


class SubtitleGenerator:
    def __init__(self):
        self._templates = SUBTITLE_TEMPLATES

    def generate(self, asset_hook_type: str = "collection", durations: List[int] = None) -> Dict[str, Any]:
        if durations is None:
            durations = [3, 6, 12, 15]
        templates = self._templates.get(asset_hook_type, self._templates["collection"])

        result = {"hook_type": asset_hook_type, "timestamps": []}

        for i, tmpl in enumerate(templates):
            entry = dict(tmpl)
            result["timestamps"].append(entry)

        return result

    def generate_srt(self, asset_hook_type: str = "collection") -> str:
        templates = self._templates.get(asset_hook_type, self._templates["collection"])
        lines = []
        for i, tmpl in enumerate(templates):
            t = tmpl["time"]
            h, m = t.split(":")
            ts_sec = int(h) * 60 + int(m)
            next_ts = ts_sec + 2
            next_h = next_ts // 60
            next_m = next_ts % 60

            lines.append(str(i + 1))
            lines.append(f"00:00:{tmpl['time']},000 --> 00:00:{next_h:02d}:{next_m:02d},000")
            lines.append(tmpl["text"])
            lines.append("")
        return "\n".join(lines)

    def get_animation_suggestions(self, asset_hook_type: str = "collection") -> List[Dict[str, str]]:
        templates = self._templates.get(asset_hook_type, self._templates["collection"])
        return [{"time": t["time"], "text": t["text"], "animation": t["style"]} for t in templates]

    def get_stats(self) -> Dict[str, Any]:
        return {"total_hook_types": len(self._templates)}
