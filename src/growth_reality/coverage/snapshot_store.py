"""P1.6.4 — 真实经营快照库（Daily Reality Store）。

把 E17.1 产出的逐游戏 GrowthRealitySnapshot 按「游戏 / 日期」落盘为
`data/reality/<game_id>/<date>.json`，形成可回放、可对比的真实经营数据库。

与 feature_store 的 JSONL（时序特征流）并存：feature_store 面向指标时间序列，
本 store 面向「每日完整快照」的逐日归档与区间回放。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..models import GrowthRealitySnapshot
from ..snapshot import CompanySnapshot


_INVALID_FS = {ord(c): "_" for c in '<>:"/\\|?*\x00\x01\x02\x03\x04\x05\x06\x07\x08'
                         '\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15'
                         '\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'}

def _safe_dir(game_id: str) -> str:
    """把 game_id 中非法文件名字符替换为 _，确保跨平台目录兼容。"""
    return game_id.translate(_INVALID_FS).strip()


class DailyRealityStore:
    def __init__(self, root: str = "data/reality"):
        self.root = Path(root)

    # -- 写入 --
    def save(self, snap: GrowthRealitySnapshot, as_of: Optional[str] = None) -> Path:
        as_of = as_of or snap.as_of
        date = as_of[:10]
        d = self.root / _safe_dir(snap.game_id)
        d.mkdir(parents=True, exist_ok=True)
        gid = snap.game_id
        payload = {
            "game_id": gid,
            "as_of": as_of,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": snap.to_dict(),
        }
        path = d / f"{date}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._save_index(gid)
        return path

    def save_company(self, company: CompanySnapshot, as_of: Optional[str] = None) -> List[Path]:
        as_of = as_of or company.as_of
        return [self.save(s, as_of) for s in company.per_game.values()]

    # -- 读取 --
    def _index_path(self) -> Path:
        return self.root / "_index.json"

    def _load_index(self) -> Dict[str, str]:
        """{safe_dir: original_game_id}"""
        p = self._index_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self, orig: str) -> None:
        idx = self._load_index()
        idx[_safe_dir(orig)] = orig
        self._index_path().write_text(
            json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    def dates(self, game_id: str) -> List[str]:
        d = self.root / _safe_dir(game_id)
        if not d.exists():
            return []
        return sorted(p.name[:10] for p in d.glob("*.json"))

    def load(self, game_id: str, date: str) -> Optional[GrowthRealitySnapshot]:
        path = self.root / _safe_dir(game_id) / f"{date[:10]}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return GrowthRealitySnapshot.from_dict(data.get("snapshot", {}))

    def load_latest(self, game_id: str) -> Optional[GrowthRealitySnapshot]:
        dates = self.dates(game_id)
        if not dates:
            return None
        return self.load(game_id, dates[-1])

    def load_range(self, game_id: str, start: str, end: str) -> List[GrowthRealitySnapshot]:
        out: List[GrowthRealitySnapshot] = []
        for dt in self.dates(game_id):
            if start <= dt <= end:
                snap = self.load(game_id, dt)
                if snap:
                    out.append(snap)
        return out

    def all_game_ids(self) -> List[str]:
        return sorted(self._load_index().values())


def build_store_from_company(
    company: CompanySnapshot, root: str = "data/reality"
) -> DailyRealityStore:
    """便捷函数：把一次 CompanySnapshot 落盘并返回 store。"""
    store = DailyRealityStore(root)
    store.save_company(company)
    return store
