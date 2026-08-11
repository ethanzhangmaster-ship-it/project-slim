"""Creative Mapping Engine — 持久化层。

管理 records.jsonl 和 review_queue.jsonl 的读写。
采用 append-only JSONL 格式，按 mapping_id/task_id 去重 (保留最新)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CreativeMappingRecord, MappingDeliveryStatus, ReviewTask, now_iso


class MappingStore:
    """映射记录持久化层。"""

    def __init__(self, data_dir: str = "data/creative_mapping"):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._records_path = self._dir / "records.jsonl"
        self._review_path = self._dir / "review_queue.jsonl"
        self._stats_path = self._dir / "stats.json"

    # ── 映射记录 ──────────────────────────────────────────────

    def save_record(self, record: CreativeMappingRecord) -> None:
        """保存映射记录 (append-only)。"""
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def get_record(self, mapping_id: str) -> CreativeMappingRecord | None:
        """按 mapping_id 查询 (返回最新一条)。"""
        latest: dict[str, Any] | None = None
        if not self._records_path.exists():
            return None
        for line in self._records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("mapping_id") == mapping_id:
                latest = data
        return CreativeMappingRecord.from_dict(latest) if latest else None

    def get_by_facebook_id(self, fb_creative_id: str) -> CreativeMappingRecord | None:
        """按 Facebook creative_id 查询 (返回最新一条)。"""
        latest: dict[str, Any] | None = None
        if not self._records_path.exists():
            return None
        for line in self._records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("facebook_creative_id") == fb_creative_id:
                latest = data
        return CreativeMappingRecord.from_dict(latest) if latest else None

    def list_records(
        self, status: str = "", limit: int = 50
    ) -> list[CreativeMappingRecord]:
        """列出映射记录 (按时间倒序，可按 status 筛选)。"""
        if not self._records_path.exists():
            return []
        records: list[CreativeMappingRecord] = []
        seen: set[str] = set()
        lines = self._records_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = data.get("mapping_id", "")
            if mid in seen:
                continue
            seen.add(mid)
            if status and data.get("status") != status:
                continue
            records.append(CreativeMappingRecord.from_dict(data))
            if len(records) >= limit:
                break
        return records

    def list_all_records(self, limit: int = 10000) -> list[CreativeMappingRecord]:
        """列出全部映射记录 (按 mapping_id 去重，保留最新)。

        用于需要遍历全量记录做筛选的场景 (如 v1.5 DeliveryBridge 查询可投递记录)。
        """
        if not self._records_path.exists():
            return []
        records: list[CreativeMappingRecord] = []
        seen: set[str] = set()
        lines = self._records_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = data.get("mapping_id", "")
            if mid in seen:
                continue
            seen.add(mid)
            records.append(CreativeMappingRecord.from_dict(data))
            if len(records) >= limit:
                break
        return records

    def update_delivery_status(
        self,
        mapping_id: str,
        delivery_status: MappingDeliveryStatus,
        publish_id: str = "",
        ad_id: str = "",
        ad_creative_id: str = "",
        delivery_error: str = "",
        increment_attempts: bool = False,
    ) -> bool:
        """更新映射记录的投递状态 (append-only 新行, v1.5)。

        Args:
            mapping_id: 映射记录 ID
            delivery_status: 新投递状态
            publish_id: AdPublishRecord.publish_id (DISPATCHED 时填充)
            ad_id: Facebook ad_id (PUBLISHED 时填充)
            ad_creative_id: Facebook ad_creative_id
            delivery_error: 失败原因 (FAILED 时填充)
            increment_attempts: True 则 delivery_attempts += 1

        Returns:
            True=更新成功，False=记录不存在
        """
        record = self.get_record(mapping_id)
        if record is None:
            return False

        record.delivery_status = delivery_status
        if publish_id:
            record.publish_id = publish_id
        if ad_id:
            record.ad_id = ad_id
        if ad_creative_id:
            record.ad_creative_id = ad_creative_id
        if delivery_error:
            record.delivery_error = delivery_error
        elif delivery_status != MappingDeliveryStatus.FAILED:
            # 非 FAILED 状态清除错误信息
            record.delivery_error = ""
        if increment_attempts:
            record.delivery_attempts += 1
        record.updated_at = now_iso()
        if delivery_status == MappingDeliveryStatus.PUBLISHED:
            record.delivered_at = now_iso()

        # append-only 写入新行
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return True

    def update_auto_structure(
        self,
        mapping_id: str,
        auto_campaign_id: str = "",
        auto_adset_id: str = "",
        auto_strategy: str = "",
    ) -> bool:
        """更新映射记录的 v1.6 自动投放结构字段 (append-only 新行)。

        Args:
            mapping_id: 映射记录 ID
            auto_campaign_id: 自动创建的 Campaign ID
            auto_adset_id: 自动创建的 AdSet ID
            auto_strategy: 使用的策略 (ABO/CBO/ASC)

        Returns:
            True=更新成功，False=记录不存在
        """
        record = self.get_record(mapping_id)
        if record is None:
            return False

        if auto_campaign_id:
            record.auto_campaign_id = auto_campaign_id
        if auto_adset_id:
            record.auto_adset_id = auto_adset_id
        if auto_strategy:
            record.auto_strategy = auto_strategy
        record.updated_at = now_iso()

        # append-only 写入新行
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return True

    def update_performance(
        self,
        mapping_id: str,
        performance: Any,
    ) -> bool:
        """更新映射记录的 v1.7 成效数据 (append-only 新行)。

        Args:
            mapping_id: 映射记录 ID
            performance: CreativePerformance 实例

        Returns:
            True=更新成功，False=记录不存在
        """
        record = self.get_record(mapping_id)
        if record is None:
            return False

        record.performance = performance
        record.updated_at = now_iso()

        # append-only 写入新行
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return True

    def update_strategy_fields(
        self,
        mapping_id: str,
        performance_score: float | None = None,
        delivery_priority: float | None = None,
        auto_archived: bool | None = None,
        auto_archived_reason: str = "",
    ) -> bool:
        """更新映射记录的 v1.8 策略字段 (append-only 新行)。

        Args:
            mapping_id: 映射记录 ID
            performance_score: 归一化成效得分 [0, 1]
            delivery_priority: 联合排序优先级
            auto_archived: 是否自动归档
            auto_archived_reason: 归档原因

        Returns:
            True=更新成功，False=记录不存在
        """
        record = self.get_record(mapping_id)
        if record is None:
            return False

        if performance_score is not None:
            record.performance_score = performance_score
        if delivery_priority is not None:
            record.delivery_priority = delivery_priority
        if auto_archived is not None:
            record.auto_archived = auto_archived
        if auto_archived_reason:
            record.auto_archived_reason = auto_archived_reason
        record.updated_at = now_iso()

        # append-only 写入新行
        with open(self._records_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return True

    # ── 审核任务 ──────────────────────────────────────────────

    def save_review_task(self, task: ReviewTask) -> None:
        """保存审核任务 (append-only)。"""
        with open(self._review_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    def get_review_task(self, task_id: str) -> ReviewTask | None:
        """按 task_id 查询审核任务 (返回最新一条)。"""
        latest: dict[str, Any] | None = None
        if not self._review_path.exists():
            return None
        for line in self._review_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("task_id") == task_id:
                latest = data
        return ReviewTask.from_dict(latest) if latest else None

    def list_open_review_tasks(self, limit: int = 50) -> list[ReviewTask]:
        """列出待审核任务 (open 状态，按时间倒序)。"""
        if not self._review_path.exists():
            return []
        tasks: list[ReviewTask] = []
        seen: set[str] = set()
        lines = self._review_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = data.get("task_id", "")
            if tid in seen:
                continue
            seen.add(tid)
            if data.get("status") != "open":
                continue
            tasks.append(ReviewTask.from_dict(data))
            if len(tasks) >= limit:
                break
        return tasks

    # ── 统计 ──────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取映射统计。"""
        records = self.list_records(limit=10000)
        status_dist: dict[str, int] = {}
        confidence_sum = 0.0
        for r in records:
            s = r.status.value
            status_dist[s] = status_dist.get(s, 0) + 1
            confidence_sum += r.confidence
        total = len(records)
        stats = {
            "total_records": total,
            "status_distribution": status_dist,
            "average_confidence": round(confidence_sum / total, 4) if total > 0 else 0.0,
            "generated_at": now_iso(),
        }
        # 覆盖写入 stats.json
        with open(self._stats_path, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, ensure_ascii=False, indent=2)
        return stats


__all__ = ["MappingStore"]
