"""E17.1 Growth Reality Hub — 特征存储。

逐游戏 JSONL 时序存储（每游戏一个 <game_id>.jsonl）。
- append(snapshot)  追加一条快照
- history(game_id)  取全部/最近 N 条
- latest(game_id)   取最新一条
- all_latest()      全舰队最新快照（用于 CompanySnapshot 构建 / 决策层 E17.3 读取）

落盘路径默认 data/growth_reality/，与既有 Intelligence 的 data/ 约定一致。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import GrowthRealitySnapshot


class GrowthFeatureStore:
    def __init__(self, root: str = "data/growth_reality"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _game_file(self, game_id: str) -> Path:
        safe = game_id.replace("/", "_").replace("\\", "_")
        return self.root / f"{safe}.jsonl"

    def append(self, snap: GrowthRealitySnapshot) -> None:
        with open(self._game_file(snap.game_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(snap.to_dict(), ensure_ascii=False) + "\n")

    def history(self, game_id: str, limit: Optional[int] = None) -> List[GrowthRealitySnapshot]:
        p = self._game_file(game_id)
        if not p.exists():
            return []
        rows: List[GrowthRealitySnapshot] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(GrowthRealitySnapshot.from_dict(json.loads(line)))
        return rows[-limit:] if limit else rows

    def latest(self, game_id: str) -> Optional[GrowthRealitySnapshot]:
        h = self.history(game_id)
        return h[-1] if h else None

    def all_latest(self) -> Dict[str, GrowthRealitySnapshot]:
        out: Dict[str, GrowthRealitySnapshot] = {}
        for f in self.root.glob("*.jsonl"):
            gid = f.stem
            latest = self.latest(gid)
            if latest:
                out[gid] = latest
        return out
