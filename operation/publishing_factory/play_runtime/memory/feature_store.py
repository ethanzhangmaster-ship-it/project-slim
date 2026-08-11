"""E15.2 Play Feature Store — JSONL 持久化的历史特征库.

Lean 原则: 纯 Python + JSONL, 无外部数据库。
默认落 data/play_runtime/features.jsonl。

用途: 保存每次 PlayRealitySnapshot 的关键特征, 供 Decision Engine
做历史对比 (如 crash 环比恶化 / rollout 观察窗口)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = Path("data") / "play_runtime" / "features.jsonl"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PlayFeatureRecord:
    package_name: str
    feature_name: str
    value: Any
    version_code: Optional[int] = None
    timestamp: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "feature_name": self.feature_name,
            "value": self.value,
            "version_code": self.version_code,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PlayFeatureRecord":
        ts = raw.get("timestamp")
        timestamp = _utcnow()
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts)
            except ValueError:
                pass
        return cls(
            package_name=raw.get("package_name", ""),
            feature_name=raw.get("feature_name", ""),
            value=raw.get("value"),
            version_code=raw.get("version_code"),
            timestamp=timestamp,
        )


# Snapshot 中会被抽取为特征的字段
_SNAPSHOT_FEATURES = (
    "rollout_percentage",
    "crash_rate",
    "anr_rate",
    "d1_retention",
    "rating_average",
    "review_count",
    "negative_review_ratio",
    "installs",
)


class PlayFeatureStore:
    """append-only JSONL 特征库, package 级隔离查询."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else _DEFAULT_PATH

    # ---------- 写 ----------

    def record(self, record: PlayFeatureRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def record_snapshot(self, snapshot: Any) -> int:
        """把 PlayRealitySnapshot 的关键字段拆成特征记录, 返回写入条数."""
        count = 0
        version_code = getattr(snapshot, "version_code", None)
        package_name = getattr(snapshot, "package_name", "")
        for name in _SNAPSHOT_FEATURES:
            value = getattr(snapshot, name, None)
            if value is None:
                continue
            self.record(
                PlayFeatureRecord(
                    package_name=package_name,
                    feature_name=name,
                    value=value,
                    version_code=version_code,
                )
            )
            count += 1
        return count

    # ---------- 读 ----------

    def _iter_records(self) -> List[PlayFeatureRecord]:
        if not self.path.exists():
            return []
        records: List[PlayFeatureRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(PlayFeatureRecord.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue  # 坏行跳过, 不影响整体
        return records

    def history(
        self,
        package_name: str,
        feature_name: str,
        limit: Optional[int] = None,
    ) -> List[PlayFeatureRecord]:
        """按时间正序返回某包某特征的历史 (package 级隔离)."""
        rows = [
            r
            for r in self._iter_records()
            if r.package_name == package_name and r.feature_name == feature_name
        ]
        rows.sort(key=lambda r: r.timestamp)
        if limit is not None:
            rows = rows[-limit:]
        return rows

    def latest(
        self, package_name: str, feature_name: str
    ) -> Optional[PlayFeatureRecord]:
        rows = self.history(package_name, feature_name)
        return rows[-1] if rows else None

    def packages(self) -> List[str]:
        return sorted({r.package_name for r in self._iter_records()})
