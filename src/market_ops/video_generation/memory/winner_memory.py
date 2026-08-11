"""Winner Memory"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class WinnerPattern:
    pattern_id: str = ""
    prompt_dna: str = ""
    platform: str = ""
    style: str = ""
    hook_type: str = ""
    camera_move: str = ""
    cta_type: str = ""
    avg_ctr: float = 0.0
    occurrences: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: str = ""

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WinnerMemory:
    """赢家记忆系统 - 记录和发现成功模式"""

    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            memory_dir = Path(__file__).resolve().parent / "winners"
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._patterns: Dict[str, WinnerPattern] = {}
        self._load_patterns()

    def _load_patterns(self):
        for pattern_file in self.memory_dir.glob("*.json"):
            with open(pattern_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            pattern = WinnerPattern(**data)
            self._patterns[pattern.pattern_id] = pattern

    def _save_pattern(self, pattern: WinnerPattern):
        pattern_path = self.memory_dir / f"{pattern.pattern_id}.json"
        with open(pattern_path, "w", encoding="utf-8") as f:
            json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)

    def learn(self, record: Dict[str, Any]):
        prompt_dna = record.get("prompt_dna", "")
        if not prompt_dna:
            return

        style = record.get("style", "")
        hook_type = record.get("hook_type", "")
        camera_move = record.get("camera_move", "")
        cta_type = record.get("cta_type", "")
        platform = record.get("platform", "")
        ctr = record.get("ctr", 0.0)

        pattern_key = f"{prompt_dna}_{platform}"

        if pattern_key in self._patterns:
            pattern = self._patterns[pattern_key]
            pattern.avg_ctr = (pattern.avg_ctr * pattern.occurrences + ctr) / (pattern.occurrences + 1)
            pattern.occurrences += 1
        else:
            pattern = WinnerPattern(
                pattern_id=f"winner_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                prompt_dna=prompt_dna,
                platform=platform,
                style=style,
                hook_type=hook_type,
                camera_move=camera_move,
                cta_type=cta_type,
                avg_ctr=ctr,
                occurrences=1,
            )
            self._patterns[pattern_key] = pattern

        self._save_pattern(pattern)

    def get_pattern(self, pattern_id: str) -> Optional[WinnerPattern]:
        return self._patterns.get(pattern_id)

    def find_matching(self, prompt_dna: str) -> List[WinnerPattern]:
        results = []
        for pattern in self._patterns.values():
            if pattern.prompt_dna == prompt_dna:
                results.append(pattern)
        return sorted(results, key=lambda p: p.avg_ctr, reverse=True)

    def suggest_best(self, style: str = "", camera_move: str = "") -> Optional[WinnerPattern]:
        candidates = []
        for pattern in self._patterns.values():
            if style and pattern.style != style:
                continue
            if camera_move and pattern.camera_move != camera_move:
                continue
            candidates.append(pattern)
        if candidates:
            return max(candidates, key=lambda p: p.avg_ctr)
        return None

    def get_top_patterns(self, limit: int = 10) -> List[WinnerPattern]:
        return sorted(self._patterns.values(), key=lambda p: p.avg_ctr, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        patterns = list(self._patterns.values())
        return {
            "total_patterns": len(patterns),
            "avg_ctr": round(sum(p.avg_ctr for p in patterns) / len(patterns), 2) if patterns else 0,
            "top_pattern": patterns[0].to_dict() if patterns else {},
        }
