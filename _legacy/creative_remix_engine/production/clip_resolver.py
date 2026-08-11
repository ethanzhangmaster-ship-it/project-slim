"""ClipResolver — the fix for P0-3 (extract_start source-timeline bug).

RULE (per V3.9.1 spec):
  The assembler / composer MUST NEVER compute a source timestamp itself.
  Every DNA segment carries an explicit (source_video, source_start, source_end,
  duration) resolved here, strictly inside the source video's REAL duration.

Why the old code was broken:
  extract_start = seg_duration * (i * 0.5)
  treated the NEW video's timeline position as the SOURCE clip's start offset and
  applied it to heterogeneous source clips of varying/short length -> segments
  overflowed the source -> empty / truncated clips.

This resolver guarantees 0 <= source_start and source_end <= source_duration, so a
clip can never be requested beyond the end of its source file.
"""
from typing import Tuple

# Preferred temporal position of each DNA role inside a source clip (fraction 0..1).
# hook -> early, cta -> late. Heuristic only; replaced by real shot intelligence in V4.
ROLE_POSITION = {
    "hook": 0.08,
    "problem": 0.30,
    "gameplay": 0.45,
    "merge_action": 0.45,
    "transformation": 0.60,
    "reward": 0.72,
    "cta": 0.88,
}


def resolve_clip(
    source_duration: float,
    desired_duration: float,
    role: str = "",
    variant_index: int = 0,
    variant_total: int = 1,
) -> Tuple[float, float, float]:
    """Return (source_start, source_end, actual_duration).

    Guarantees source_end <= source_duration. If the source is shorter than the
    desired duration, the whole clip is returned (actual_duration < desired).
    """
    S = float(source_duration)
    D = float(desired_duration)
    if S <= 0:
        return (0.0, 0.0, 0.0)
    if D <= 0:
        return (0.0, 0.0, 0.0)
    if S >= D:
        pref = ROLE_POSITION.get(role, 0.5)
        # Spread multiple variants across the allowed window so they don't all
        # grab the exact same frames of the same source.
        spread = 0.0
        if variant_total > 1:
            spread = (variant_index / float(variant_total)) * 0.5
        frac = min(0.95, pref + spread)
        max_start = S - D
        start = max(0.0, min(max_start, frac * max_start))
        start = round(start, 3)
        end = start + D
        if end > S:
            end = S
            start = max(0.0, round(end - D, 3))
        return (start, end, round(end - start, 3))
    else:
        # Source shorter than desired: take the entire clip.
        return (0.0, round(S, 3), round(S, 3))
