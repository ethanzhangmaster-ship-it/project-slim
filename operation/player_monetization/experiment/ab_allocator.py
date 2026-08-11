"""E15.2.7 §7 — A/B user allocator for in-game experiments.
Hash-based deterministic allocation so the same user always gets the same bucket."""
import hashlib
from typing import Dict

class ABAllocator:
    def allocate(self, user_id: str, experiment: str,
                 control_pct: float = 0.5) -> str:
        h = int(hashlib.md5(f"{experiment}|{user_id}".encode()).hexdigest()[:8], 16)
        return "control" if (h / 0xFFFFFFFF) < control_pct else "variant"
