"""E13.7.4.4 Report Store — 报告存储.

报告存储提供:
  - 内存存储 (InMemoryReportStore)
  - 文件存储 (FileReportStore)
  - 查询接口 (query, get_latest, get_history)
  - 统计接口 (stats, timeline)

存储策略:
  - 内存: 快速访问最近报告 (默认保留最近 1000 条)
  - 文件: JSON 持久化，支持审计和回溯
  - 未来: Postgres / Redis
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report_models import (
    AgentReport,
    ReportQuery,
    ReportStatus,
    ReportType,
)


# ═══════════════════════════════════════════════════════════════
# Abstract Report Store
# ═══════════════════════════════════════════════════════════════


class ReportStore(ABC):
    """报告存储抽象基类."""

    @abstractmethod
    def save(self, report: AgentReport) -> None:
        """保存报告."""
        ...

    @abstractmethod
    def get(self, report_id: str) -> AgentReport | None:
        """获取报告."""
        ...

    @abstractmethod
    def query(self, query: ReportQuery) -> list[AgentReport]:
        """查询报告."""
        ...

    @abstractmethod
    def get_latest(self, agent_id: str = "") -> AgentReport | None:
        """获取最新报告."""
        ...

    @abstractmethod
    def get_history(
        self,
        agent_id: str = "",
        limit: int = 50,
    ) -> list[AgentReport]:
        """获取历史报告."""
        ...

    @abstractmethod
    def count(self) -> int:
        """报告总数."""
        ...

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """存储统计."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空."""
        ...


# ═══════════════════════════════════════════════════════════════
# In-Memory Report Store
# ═══════════════════════════════════════════════════════════════


class InMemoryReportStore(ReportStore):
    """内存报告存储.

    使用方式:
        store = InMemoryReportStore(max_reports=1000)
        store.save(report)
        latest = store.get_latest("ua_agent_01")
        history = store.get_history("ua_agent_01", limit=10)
    """

    def __init__(self, max_reports: int = 1000):
        self._reports: dict[str, AgentReport] = {}
        self._max_reports = max_reports
        self._order: list[str] = []  # 按插入顺序

    def save(self, report: AgentReport) -> None:
        # 容量控制
        if len(self._reports) >= self._max_reports:
            oldest = self._order[0]
            self._reports.pop(oldest, None)
            self._order = self._order[1:]
        self._reports[report.report_id] = report
        self._order.append(report.report_id)

    def get(self, report_id: str) -> AgentReport | None:
        return self._reports.get(report_id)

    def query(self, query: ReportQuery) -> list[AgentReport]:
        results = []
        for report_id in reversed(self._order):  # 倒序 (最新在前)
            report = self._reports[report_id]
            if query.match(report):
                results.append(report)
                if len(results) >= query.limit:
                    break
        return results

    def get_latest(self, agent_id: str = "") -> AgentReport | None:
        if not self._order:
            return None
        # 从后往前找匹配的
        for report_id in reversed(self._order):
            report = self._reports[report_id]
            if not agent_id or report.agent_id == agent_id:
                return report
        return None

    def get_history(
        self,
        agent_id: str = "",
        limit: int = 50,
    ) -> list[AgentReport]:
        results = []
        for report_id in reversed(self._order):
            report = self._reports[report_id]
            if not agent_id or report.agent_id == agent_id:
                results.append(report)
                if len(results) >= limit:
                    break
        return results

    def count(self) -> int:
        return len(self._reports)

    def stats(self) -> dict[str, Any]:
        reports = list(self._reports.values())
        if not reports:
            return {"total_reports": 0, "statuses": {}, "types": {}}

        statuses: dict[str, int] = {}
        types: dict[str, int] = {}
        for r in reports:
            statuses[r.status.value] = statuses.get(r.status.value, 0) + 1
            for s in r.sections:
                types[s.type.value] = types.get(s.type.value, 0) + 1

        return {
            "total_reports": len(reports),
            "statuses": statuses,
            "types": types,
            "oldest": reports[0].timestamp if reports else "",
            "newest": reports[-1].timestamp if reports else "",
        }

    def clear(self) -> None:
        self._reports.clear()
        self._order.clear()


# ═══════════════════════════════════════════════════════════════
# File Report Store
# ═══════════════════════════════════════════════════════════════


class FileReportStore(ReportStore):
    """文件报告存储 (JSON 持久化).

    使用方式:
        store = FileReportStore("data/reports/")
        store.save(report)
        latest = store.get_latest("ua_agent_01")
    """

    def __init__(self, base_dir: str = "data/reports/"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._base_dir / "index.json"
        self._index: dict[str, str] = self._load_index()

    def _load_index(self) -> dict[str, str]:
        """加载索引."""
        if self._index_file.exists():
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self) -> None:
        """保存索引."""
        try:
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _report_path(self, report_id: str) -> Path:
        return self._base_dir / f"{report_id}.json"

    def save(self, report: AgentReport) -> None:
        path = self._report_path(report.report_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        self._index[report.report_id] = report.timestamp
        self._save_index()

    def get(self, report_id: str) -> AgentReport | None:
        path = self._report_path(report_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AgentReport.from_dict(data)
        except Exception:
            return None

    def query(self, query: ReportQuery) -> list[AgentReport]:
        results = []
        # 按时间倒序
        sorted_ids = sorted(self._index.keys(), key=lambda k: self._index.get(k, ""), reverse=True)
        for report_id in sorted_ids:
            report = self.get(report_id)
            if report and query.match(report):
                results.append(report)
                if len(results) >= query.limit:
                    break
        return results

    def get_latest(self, agent_id: str = "") -> AgentReport | None:
        if not self._index:
            return None
        sorted_ids = sorted(self._index.keys(), key=lambda k: self._index.get(k, ""), reverse=True)
        for report_id in sorted_ids:
            report = self.get(report_id)
            if report and (not agent_id or report.agent_id == agent_id):
                return report
        return None

    def get_history(
        self,
        agent_id: str = "",
        limit: int = 50,
    ) -> list[AgentReport]:
        results = []
        sorted_ids = sorted(self._index.keys(), key=lambda k: self._index.get(k, ""), reverse=True)
        for report_id in sorted_ids:
            report = self.get(report_id)
            if report and (not agent_id or report.agent_id == agent_id):
                results.append(report)
                if len(results) >= limit:
                    break
        return results

    def count(self) -> int:
        return len(self._index)

    def stats(self) -> dict[str, Any]:
        total = len(self._index)
        if total == 0:
            return {"total_reports": 0, "statuses": {}, "types": {}}

        indexes = sorted(self._index.values())
        return {
            "total_reports": total,
            "oldest": indexes[0] if indexes else "",
            "newest": indexes[-1] if indexes else "",
            "storage_path": str(self._base_dir),
        }

    def clear(self) -> None:
        for report_id in list(self._index.keys()):
            path = self._report_path(report_id)
            if path.exists():
                path.unlink()
        self._index.clear()
        self._save_index()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_report_store(
    store_type: str = "memory",
    **kwargs,
) -> ReportStore:
    """创建报告存储.

    Args:
        store_type: "memory" | "file"
        **kwargs: 传递给存储构造函数

    Returns:
        ReportStore: 报告存储实例
    """
    if store_type == "file":
        return FileReportStore(**kwargs)
    return InMemoryReportStore(**kwargs)