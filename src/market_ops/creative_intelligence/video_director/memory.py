"""Creative Memory - 创意记忆系统

记录成功和失败的视频创意模式，用于持续优化。

文件结构：
- winner_patterns.json: 成功模式
- failed_patterns.json: 失败模式
- hook_patterns.json: Hook 效果记录
- camera_patterns.json: 运镜效果记录
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class CreativeMemory:
    """创意记忆系统"""

    def __init__(self, memory_dir: str = ""):
        if not memory_dir:
            base = os.path.dirname(os.path.abspath(__file__))
            memory_dir = os.path.join(base, "memory")
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)

        self.winner_file = os.path.join(memory_dir, "winner_patterns.json")
        self.failed_file = os.path.join(memory_dir, "failed_patterns.json")
        self.hook_file = os.path.join(memory_dir, "hook_patterns.json")
        self.camera_file = os.path.join(memory_dir, "camera_patterns.json")

    # ------------------------------------------------------------------
    # 记录成功
    # ------------------------------------------------------------------
    def record_winner(
        self,
        video_id: str,
        hook: str,
        camera: str,
        action: str,
        ctr: float = 0.0,
        cpi: float = 0.0,
        roas: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录成功创意"""
        entry = {
            "video_id": video_id,
            "hook": hook,
            "camera": camera,
            "action": action,
            "ctr": ctr,
            "cpi": cpi,
            "roas": roas,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._append_json(self.winner_file, entry)

    # ------------------------------------------------------------------
    # 记录失败
    # ------------------------------------------------------------------
    def record_failure(
        self,
        video_id: str,
        hook: str,
        reason: str,
        ctr: float = 0.0,
        retention_3s: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录失败创意"""
        entry = {
            "video_id": video_id,
            "hook": hook,
            "reason": reason,
            "ctr": ctr,
            "retention_3s": retention_3s,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._append_json(self.failed_file, entry)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def get_top_hooks(self, limit: int = 5) -> list[dict[str, Any]]:
        """获取表现最好的 Hook"""
        winners = self._load_json(self.winner_file)
        # 按 ROAS 排序
        winners.sort(key=lambda x: x.get("roas", 0), reverse=True)
        return winners[:limit]

    def get_failed_reasons(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取常见失败原因"""
        failures = self._load_json(self.failed_file)
        return failures[-limit:]

    def get_best_cameras(self, content_type: str = "", limit: int = 5) -> list[dict[str, Any]]:
        """获取最佳运镜"""
        winners = self._load_json(self.winner_file)
        if content_type:
            winners = [w for w in winners
                       if content_type in w.get("metadata", {}).get("content_type", "")]
        winners.sort(key=lambda x: x.get("roas", 0), reverse=True)
        return winners[:limit]

    # ------------------------------------------------------------------
    # 反馈学习
    # ------------------------------------------------------------------
    def learn_from_performance(
        self,
        video_id: str,
        ctr: float,
        cpi: float,
        roas: float,
        retention_3s: float = 0.0,
    ) -> dict[str, Any]:
        """根据投放数据更新记忆

        Returns:
            学习结果 {"action": "winner|failed|neutral", "insights": [...]}
        """
        insights: list[str] = []

        if roas > 2.0 or ctr > 2.0:
            action = "winner"
            insights.append(f"高 ROAS ({roas:.2f})，记录为成功模式")
        elif retention_3s < 0.3 or ctr < 0.5:
            action = "failed"
            insights.append(f"低留存 ({retention_3s:.1%}) 或低 CTR ({ctr:.2f})，记录为失败")
        else:
            action = "neutral"
            insights.append("表现中等，作为对照组")

        return {
            "action": action,
            "insights": insights,
            "video_id": video_id,
            "metrics": {"ctr": ctr, "cpi": cpi, "roas": roas, "retention_3s": retention_3s},
        }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _load_json(self, filepath: str) -> list[dict[str, Any]]:
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _append_json(self, filepath: str, entry: dict[str, Any]) -> None:
        data = self._load_json(filepath)
        data.append(entry)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
