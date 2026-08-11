"""Ranking Database — JSON / DuckDB 存储评分数据"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class RankingDatabase:
    """排名数据库"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """加载已有数据"""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._data = {item["video_name"]: item for item in data.get("shots", [])}
            except Exception:
                self._data = {}

    def save(self):
        """保存数据"""
        payload = {
            "updated_at": datetime.now().isoformat(),
            "total": len(self._data),
            "shots": list(self._data.values()),
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    def get(self, video_name: str) -> Optional[dict]:
        """获取单个视频的评分"""
        return self._data.get(video_name)

    def exists(self, video_name: str) -> bool:
        """检查是否已分析"""
        return video_name in self._data

    def upsert(self, video_name: str, scores: dict):
        """插入或更新评分"""
        existing = self._data.get(video_name, {})
        existing.update(scores)
        existing["video_name"] = video_name
        existing["updated_at"] = datetime.now().isoformat()
        self._data[video_name] = existing

    def get_all(self) -> List[dict]:
        """获取全部数据"""
        return list(self._data.values())

    def get_unprocessed(self, video_paths: List[Path]) -> List[Path]:
        """获取尚未处理的视频列表"""
        return [p for p in video_paths if not self.exists(p.stem)]
