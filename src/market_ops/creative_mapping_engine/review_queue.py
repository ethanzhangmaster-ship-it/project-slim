"""Creative Mapping Engine — 人工审核队列管理。"""

from __future__ import annotations

import hashlib
from typing import Any

from .models import ReviewTask, now_iso
from .store import MappingStore


class ReviewQueue:
    """人工审核队列管理。"""

    def __init__(self, store: MappingStore):
        self._store = store

    def enqueue(
        self, mapping_id: str, facebook_creative_id: str, candidates: list[dict]
    ) -> ReviewTask:
        """创建审核任务并入队。"""
        task_id = self._gen_task_id(mapping_id)
        task = ReviewTask(
            task_id=task_id,
            mapping_id=mapping_id,
            facebook_creative_id=facebook_creative_id,
            candidates=list(candidates),
            created_at=now_iso(),
            status="open",
        )
        self._store.save_review_task(task)
        return task

    def dequeue(self, limit: int = 10) -> list[ReviewTask]:
        """获取待审核任务。"""
        return self._store.list_open_review_tasks(limit=limit)

    def approve(
        self,
        task_id: str,
        eagle_filename: str,
        eagle_path: str = "",
        reviewer: str = "",
        note: str = "",
    ) -> ReviewTask:
        """审核通过。"""
        task = self._store.get_review_task(task_id)
        if task is None:
            raise ValueError(f"Review task not found: {task_id}")
        if task.status != "open":
            raise ValueError(f"Task already resolved: {task_id} (status={task.status})")

        task.status = "approved"
        task.resolution = eagle_filename
        task.resolved_at = now_iso()
        task.resolved_by = reviewer
        task.review_note = note
        self._store.save_review_task(task)

        # 更新映射记录状态
        record = self._store.get_record(task.mapping_id)
        if record:
            record.status = record.status.REVIEW_APPROVED
            record.eagle_filename = eagle_filename
            record.eagle_path = eagle_path
            record.reviewed_by = reviewer
            record.review_note = note
            record.updated_at = now_iso()
            self._store.save_record(record)

        return task

    def reject(
        self, task_id: str, reason: str, reviewer: str = ""
    ) -> ReviewTask:
        """审核驳回。"""
        task = self._store.get_review_task(task_id)
        if task is None:
            raise ValueError(f"Review task not found: {task_id}")
        if task.status != "open":
            raise ValueError(f"Task already resolved: {task_id} (status={task.status})")

        task.status = "rejected"
        task.resolution = reason
        task.resolved_at = now_iso()
        task.resolved_by = reviewer
        task.review_note = reason
        self._store.save_review_task(task)

        # 更新映射记录状态
        record = self._store.get_record(task.mapping_id)
        if record:
            record.status = record.status.REVIEW_REJECTED
            record.reviewed_by = reviewer
            record.review_note = reason
            record.updated_at = now_iso()
            self._store.save_record(record)

        return task

    def list_open(self, limit: int = 50) -> list[ReviewTask]:
        """列出待审核任务。"""
        return self._store.list_open_review_tasks(limit=limit)

    @staticmethod
    def _gen_task_id(mapping_id: str) -> str:
        """生成审核任务 ID。"""
        h = hashlib.sha256(f"review:{mapping_id}".encode("utf-8")).hexdigest()[:12]
        return f"rv_{h}"


__all__ = ["ReviewQueue"]
