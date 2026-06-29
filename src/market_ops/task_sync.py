from __future__ import annotations

import re
from datetime import date
from statistics import median

from market_ops.models import ActionItem, AdsPerformanceRow, CreativeAssetRow, DailySyncReport, TaskSyncUpdate


class TaskSyncService:
    DONE_STATUSES = {"完成", "Done", "Completed"}
    PENDING_STATUSES = {"待确认", "Draft"}

    def sync(
        self,
        action_items: list[ActionItem],
        ads_rows: list[AdsPerformanceRow],
        creative_rows: list[CreativeAssetRow],
        as_of_date: date,
    ) -> DailySyncReport:
        updated_tasks: list[TaskSyncUpdate] = []
        overdue_tasks: list[ActionItem] = []

        for item in action_items:
            previous_status = item.status
            previous_note = item.latest_note
            new_status, note = self._evaluate_item(item, ads_rows, creative_rows, as_of_date)
            item.status = new_status
            item.latest_note = note

            if new_status != previous_status or note != previous_note:
                updated_tasks.append(
                    TaskSyncUpdate(
                        task_id=item.task_id,
                        previous_status=previous_status,
                        new_status=new_status,
                        latest_note=note,
                    )
                )

            if item.due_date < as_of_date and new_status not in self.DONE_STATUSES:
                overdue_tasks.append(item)

        return DailySyncReport(
            as_of_date=as_of_date,
            total_tasks=len(action_items),
            updated_tasks=updated_tasks,
            overdue_tasks=overdue_tasks,
        )

    def _evaluate_item(
        self,
        item: ActionItem,
        ads_rows: list[AdsPerformanceRow],
        creative_rows: list[CreativeAssetRow],
        as_of_date: date,
    ) -> tuple[str, str]:
        if item.status in self.DONE_STATUSES:
            return "完成", item.latest_note or "任务已完成。"

        if item.status in self.PENDING_STATUSES:
            return "待确认", item.latest_note or "等待会议确认后进入执行。"

        if item.action_type in {"加码", "减量", "暂停", "Budget"}:
            return self._evaluate_budget_task(item, ads_rows, as_of_date)
        if item.action_type in {"复制素材", "Creative"}:
            return self._evaluate_creative_task(item, creative_rows, as_of_date)
        if item.action_type in {"Review"}:
            return self._evaluate_review_task(item, as_of_date)
        return self._evaluate_generic_task(item, as_of_date)

    def _evaluate_budget_task(
        self,
        item: ActionItem,
        ads_rows: list[AdsPerformanceRow],
        as_of_date: date,
    ) -> tuple[str, str]:
        match = re.search(r"ROAS\s*[>=]+\s*([0-9.]+)", item.acceptance_metric, re.IGNORECASE)
        threshold = float(match.group(1)) if match else None
        if not ads_rows:
            return "风险", "暂无投放回流数据，无法判断预算动作结果。"

        recent_rows = sorted(ads_rows, key=lambda row: row.date, reverse=True)[:3]
        avg_roas = sum(row.roas for row in recent_rows) / len(recent_rows)
        if threshold is not None and avg_roas >= threshold:
            return "完成", f"最近 3 条投放记录平均 ROAS 为 {avg_roas:.2f}，已达到目标 {threshold:.2f}。"
        if item.due_date < as_of_date:
            if threshold is None:
                return "逾期", f"最近 3 条投放记录平均 ROAS 为 {avg_roas:.2f}，任务已逾期。"
            return "风险", f"最近 3 条投放记录平均 ROAS 为 {avg_roas:.2f}，仍低于目标 {threshold:.2f}。"
        if threshold is None:
            return "执行中", f"最近 3 条投放记录平均 ROAS 为 {avg_roas:.2f}。"
        return "执行中", f"最近 3 条投放记录平均 ROAS 为 {avg_roas:.2f}，目标为 {threshold:.2f}。"

    def _evaluate_creative_task(
        self,
        item: ActionItem,
        creative_rows: list[CreativeAssetRow],
        as_of_date: date,
    ) -> tuple[str, str]:
        if not creative_rows:
            return "风险", "暂无素材回流数据，无法判断素材动作结果。"

        ctr_values = [row.ctr for row in creative_rows]
        median_ctr = median(ctr_values)
        winners = [row for row in creative_rows if row.ctr > median_ctr]
        if len(winners) >= 3:
            return "完成", f"已有 {len(winners)} 条素材 CTR 高于当前中位数 {median_ctr:.3f}。"
        if item.due_date < as_of_date:
            return "风险", f"目前仅有 {len(winners)} 条素材 CTR 高于当前中位数 {median_ctr:.3f}。"
        return "执行中", f"目前有 {len(winners)} 条素材 CTR 高于当前中位数 {median_ctr:.3f}。"

    def _evaluate_review_task(self, item: ActionItem, as_of_date: date) -> tuple[str, str]:
        if item.due_date < as_of_date:
            return "逾期", "复盘任务已逾期，仍待人工确认。"
        return "执行中", "等待人工复盘确认。"

    def _evaluate_generic_task(self, item: ActionItem, as_of_date: date) -> tuple[str, str]:
        if item.due_date < as_of_date:
            return "逾期", "任务已逾期。"
        return "执行中", "任务执行中。"
