"""P1.7.2 — 数据新鲜度监控（Data Freshness Monitor）。

检查各数据源的最后同步时间，映射到 GREEN/YELLOW/RED：
- < 6h     → GREEN  (1.0)
- 6–24h    → YELLOW (0.5)
- > 24h    → RED    (0.0)
- 无数据   → UNKNOWN (0.5，中立)

逐游戏聚合：取所有有数据源的最差 freshness -> overall。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import FreshnessCheck, GameFreshness

AGE_GREEN = 6 * 60       # minutes
AGE_YELLOW = 24 * 60     # minutes


def _age_minutes(ts: Optional[datetime]) -> float:
    if ts is None:
        return 0.0
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60.0


def _status_by_age(age: float) -> str:
    if age < AGE_GREEN:
        return "GREEN"
    if age < AGE_YELLOW:
        return "YELLOW"
    return "RED"


def _score_by_status(s: str) -> float:
    return {"GREEN": 1.0, "YELLOW": 0.5, "RED": 0.0, "UNKNOWN": 1.0}.get(s, 1.0)


class DataFreshnessMonitor:
    """检查各真实源的时间新鲜度。

    支持三种源：
    - max:  检查 data/ACCT_*_report.json 文件修改时间
    - adjust: 检查可选的 freshness 记录文件
    - meta: 同上
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self._freshness_file = self.data_dir / "validation" / "freshness.json"

    # ------------------------------------------------------------------ #
    # 源级检查
    # ------------------------------------------------------------------ #
    def _file_mtime(self, pattern: str) -> Optional[datetime]:
        files = sorted(self.data_dir.glob(pattern))
        if not files:
            return None
        ts = max(f.stat().st_mtime for f in files)
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    def _read_record(self, source: str) -> Optional[datetime]:
        if not self._freshness_file.exists():
            return None
        try:
            data = json.loads(self._freshness_file.read_text(encoding="utf-8"))
            ts = (data or {}).get(source, {}).get("last_sync")
            return datetime.fromisoformat(ts) if ts else None
        except Exception:
            return None

    def check_max(self) -> FreshnessCheck:
        ts = self._file_mtime("ACCT_*_report.json")
        age = round(_age_minutes(ts), 1) if ts else 0.0
        if ts:
            status = _status_by_age(age)
            detail = f"MAX 报表缓存 {ts.isoformat()}"
        else:
            status = "UNKNOWN"
            detail = "未找到 MAX 报表缓存文件"
        return FreshnessCheck(source="max", last_sync=ts, age_minutes=age,
                              status=status, detail=detail)

    def check_adjust(self) -> FreshnessCheck:
        ts = self._read_record("adjust")
        age = round(_age_minutes(ts), 1) if ts else 0.0
        if ts:
            status = _status_by_age(age)
            detail = f"Adjust 最后同步 {ts.isoformat()}"
        else:
            status = "UNKNOWN"
            detail = "Adjust 未配置或无同步记录（无 token）"
        return FreshnessCheck(source="adjust", last_sync=ts, age_minutes=age,
                              status=status, detail=detail)

    def check_meta(self) -> FreshnessCheck:
        ts = self._read_record("meta")
        age = round(_age_minutes(ts), 1) if ts else 0.0
        if ts:
            status = _status_by_age(age)
            detail = f"Meta 最后同步 {ts.isoformat()}"
        else:
            status = "UNKNOWN"
            detail = "Meta 未配置或无同步记录（无 token）"
        return FreshnessCheck(source="meta", last_sync=ts, age_minutes=age,
                              status=status, detail=detail)

    def check_all(self) -> Dict[str, FreshnessCheck]:
        return {
            "max": self.check_max(),
            "adjust": self.check_adjust(),
            "meta": self.check_meta(),
        }

    # ------------------------------------------------------------------ #
    # 游戏级聚合
    # ------------------------------------------------------------------ #
    def game_freshness(
        self,
        game_id: str,
        source_freshness: Optional[Dict[str, FreshnessCheck]] = None,
        active_sources: Optional[Set[str]] = None,
    ) -> GameFreshness:
        """逐游戏新鲜度：取该游戏有数据的源的最差状态。

        active_sources: 哪些源对该游戏产生了真实数据（如 {"max_live", "registry"}）.
        """
        sf = source_freshness or self.check_all()
        active = active_sources or set()

        # 映射 source_id → freshness key
        _MAP = {"max_live": "max", "adjust_live": "adjust", "meta_live": "meta"}
        # registry 是本地源，永不过期
        relevant = [_MAP.get(s) for s in active]
        relevant = [r for r in relevant if r is not None]

        if not relevant:
            # 无真实源（纯 SIM） → UNKNOWN，不扣分
            return GameFreshness(game_id=game_id, overall="UNKNOWN",
                                 freshness_score=1.0)

        checks: List[FreshnessCheck] = []
        scored: List[float] = []
        for key in relevant:
            c = sf.get(key)
            if c:
                checks.append(c)
                scored.append(_score_by_status(c.status))

        overall = "UNKNOWN"
        if scored:
            all_unknown = all(c.status == "UNKNOWN" for c in checks)
            if all_unknown:
                overall = "UNKNOWN"
            elif all(s == 1.0 for s in scored):
                overall = "GREEN"
            elif all(s >= 0.5 for s in scored):
                overall = "YELLOW"
            else:
                overall = "RED"

        return GameFreshness(
            game_id=game_id, sources=checks,
            overall=overall,
            freshness_score=min(scored) if scored else 0.5,
        )

    def fleet_freshness(
        self,
        game_ids: List[str],
        active_sources_by_game: Optional[Dict[str, Set[str]]] = None,
    ) -> Dict[str, GameFreshness]:
        sf = self.check_all()
        as_map = active_sources_by_game or {}
        return {gid: self.game_freshness(gid, sf, as_map.get(gid))
                for gid in game_ids}

    # ------------------------------------------------------------------ #
    # 记录更新（供数据拉取完成后调用）
    # ------------------------------------------------------------------ #
    def record_sync(self, source: str, ts: Optional[datetime] = None) -> None:
        ts = ts or datetime.now(timezone.utc)
        existing = {}
        if self._freshness_file.exists():
            try:
                existing = json.loads(self._freshness_file.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing.setdefault(source, {})["last_sync"] = ts.isoformat()
        self._freshness_file.parent.mkdir(parents=True, exist_ok=True)
        self._freshness_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
