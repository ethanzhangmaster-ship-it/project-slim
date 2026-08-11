"""Timeline Planner — DNA Selector + Timeline Builder stages of the merged pipeline.

DNA Selector: picks candidate source clips per DNA role (ROAS-ranked, ratio-filtered).
Timeline Builder: assembles `count` recipes. Every segment's source time is resolved
by ClipResolver (never guessed). timeline_start is the cumulative position in the NEW
video, computed from the ACTUAL resolved durations — this is what the xfade offset
relies on, so it must be exact.
"""
from typing import Dict, List

from ..config import DNA_TEMPLATES, CONTENT_ROLE_MAP
from .clip_resolver import resolve_clip


class DNASelector:
    """Lightweight, ROAS-driven selector.

    NOTE (V4 seam): this is the placeholder for real Shot Intelligence (Phase 3).
    Replace select() with CLIP/FAISS similarity ranking when that pipeline lands;
    the rest of the pipeline is agnostic to how candidates are chosen.
    """

    def __init__(self, sources: List[Dict]):
        self.sources = sources

    def select(self, role: str, ratio: str, top_n: int = 15) -> List[Dict]:
        same_ratio = [s for s in self.sources if s.get("ratio") == ratio]
        # content type that maps to this role
        matched = [
            s for s in same_ratio
            if role in CONTENT_ROLE_MAP.get(s.get("content", ""), ["hook"])
        ]
        if not matched:
            matched = same_ratio  # fallback: any same-ratio source
        matched.sort(key=lambda s: -(float(s.get("roas", 0) or 0)))
        return matched[:top_n]


class TimelineBuilder:
    def __init__(self, selector: DNASelector):
        self.selector = selector

    def build(self, template: str, ratio: str, count: int) -> List[Dict]:
        spec = DNA_TEMPLATES.get(template)
        if not spec:
            raise ValueError(f"unknown template: {template}")
        recipes = []
        for r in range(count):
            segments: List[Dict] = []
            cursor = 0.0
            for s in spec:
                role = s["role"]
                dur = float(s["duration"])
                cands = self.selector.select(role, ratio)
                if not cands:
                    # no source for this role/ratio -> skip (recipe becomes shorter)
                    continue
                src = cands[r % len(cands)]
                s_start, s_end, actual = resolve_clip(
                    src["duration"], dur, role, variant_index=r, variant_total=count
                )
                segments.append({
                    "role": role,
                    "v_num": src.get("v_num", ""),
                    "source": src["path"],
                    "source_start": s_start,
                    "source_end": s_end,
                    "duration": actual,
                    "timeline_start": round(cursor, 3),
                    "subtitle_text": "",  # Phase 4: real UA hook copy
                })
                cursor += actual
            if segments:
                recipes.append({
                    "recipe_id": f"{template}_{ratio}_{r + 1:03d}",
                    "template": template,
                    "ratio": ratio,
                    "total_duration": round(cursor, 3),
                    "segments": segments,
                })
        return recipes
