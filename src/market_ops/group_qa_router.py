from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_ops.config import load_settings
from market_ops.group_requirements_queue import GroupRequirementRecord, GroupRequirementsQueue


@dataclass(slots=True)
class GroupRouteDecision:
    route: str
    summary: str = ""
    scopes: list[str] | None = None
    risk_level: str = "low"
    target_request_id: str = ""
    note_text: str = ""
    target_status: str = ""


class GroupQARouter:
    def __init__(self, active_output_dir: Path) -> None:
        self._active_output_dir = active_output_dir
        self._requirements_queue = GroupRequirementsQueue(active_output_dir / "group_requirements_queue.json")
        self._settings = load_settings()
        self._help_keywords = ("帮助", "help", "可问", "怎么用", "指令")
        self._fixed_commands = {
            "简版": "market_simple",
            "市场版": "market_simple",
            "详细版": "market_detail",
            "详细": "market_detail",
            "回收版": "recovery",
            "回收": "recovery",
            "倍率版": "recovery",
            "老板版": "boss",
            "摘要": "summary",
            "总结": "summary",
            "简报": "summary",
            "执行已批准任务": "execute_approved",
            "执行批准任务": "execute_approved",
            "发送市场版": "send_market",
            "发送详细市场版": "send_market_detailed",
            "发送回收版": "send_recovery_only",
            "发送老板版": "send_boss",
            "最近发送记录": "send_log",
            "发送记录": "send_log",
        }
        self._change_prefixes = (
            "改",
            "修改",
            "调整",
            "优化",
            "新增",
            "增加",
            "删除",
            "去掉",
            "不要发",
            "以后",
            "帮我改",
            "需要",
            "想要",
            "压缩",
            "缩短",
            "精简",
            "补上",
            "修复",
            "收紧",
            "放开",
            "接入",
            "打通",
            "改成",
            "换成",
        )
        self._followup_prefixes = ("补充", "补一句", "再补充", "说明", "备注", "更新需求", "追加")
        self._status_prefix_map = {
            "确认待办": "confirmed",
            "开始处理": "in_progress",
            "标记进行中": "in_progress",
            "完成待办": "done",
            "关闭待办": "closed",
            "批准待办": "approved",
            "驳回待办": "rejected",
        }
        self._status_display = {
            "new": "新建",
            "confirmed": "已确认",
            "in_progress": "进行中",
            "approved": "已批准",
            "rejected": "已驳回",
            "done": "已完成",
            "closed": "已关闭",
        }
        self._priority_display = {
            "P0": "P0",
            "P1": "P1",
            "P2": "P2",
            "P3": "P3",
        }

    def classify(self, text: str, *, chat_id: str = "") -> GroupRouteDecision:
        normalized = self._normalize_text(text)
        if not normalized:
            return GroupRouteDecision(route="unsupported")

        status_decision = self._detect_status_update(normalized)
        if status_decision is not None:
            return status_decision

        followup_decision = self._detect_followup(normalized, chat_id=chat_id)
        if followup_decision is not None:
            return followup_decision

        if self._looks_like_change_request(normalized):
            return GroupRouteDecision(
                route="change_request",
                summary=self._summarize_request(normalized),
                scopes=self._infer_scopes(normalized),
                risk_level=self._infer_risk_level(normalized),
            )

        if self._looks_like_fixed_command(normalized):
            return GroupRouteDecision(route="fixed")

        if self._looks_like_question(normalized):
            return GroupRouteDecision(route="qa")

        return GroupRouteDecision(route="unsupported")

    def answer(self, text: str, *, chat_id: str = "") -> str | None:
        normalized = self._normalize_text(text)
        if not normalized:
            return None

        status_payload = self._read_json("market_ops_status_latest.json")
        callback_payload = self._read_json("feishu_callback_live.json")
        pre_send_payload = self._latest_pre_send_payload()
        market_detail_text = self._latest_market_detail_text()

        if any(token in normalized.lower() for token in ("callback", "回调", "地址", "公网")):
            callback_url = str((callback_payload or {}).get("callback_url") or "未生成")
            health = str((status_payload or {}).get("callback_health") or "未知")
            allowed = int((status_payload or {}).get("allowed_group_count") or 0)
            return (
                "当前回调状态：\n"
                f"- 回调地址：{callback_url}\n"
                f"- 健康状态：{health}\n"
                f"- 已放行群数：{allowed}"
            )

        if "最近发送记录" in normalized or "发送记录" in normalized:
            payload = self._read_json("group_send_log_latest.json") or {}
            items = payload.get("items") or []
            if not items:
                return "当前还没有发送记录。"
            lines = ["最近发送记录："]
            for item in items[:3]:
                sent_items = "/".join(item.get("sent_items") or []) or "无"
                lines.append(
                    f"- {item.get('created_at', '未知时间')} | {item.get('status', '未知状态')} | {item.get('route', '未知路由')} | {sent_items}"
                )
            return "\n".join(lines)

        if any(token in normalized for token in ("能发", "可发", "发送", "门禁", "自检")):
            gate_text = self._read_text("weekly_release_gate_latest.md")
            status = "PASS" if "Status: PASS" in gate_text else "BLOCKED"
            recommendation = str((pre_send_payload or {}).get("send_recommendation") or "未知")
            headline = str((pre_send_payload or {}).get("headline") or "暂无")
            return (
                "当前发送结论：\n"
                f"- 门禁状态：{status}\n"
                f"- 发送建议：{recommendation}\n"
                f"- 说明：{headline}"
            )

        if any(token in normalized for token in ("公司", "整体", "ROI", "roi", "收入", "花费")):
            metrics = self._extract_company_metrics_from_market_detail(market_detail_text)
            if not metrics:
                metrics = ((pre_send_payload or {}).get("key_metrics") or {}).get("公司") or {}
            focus = ((pre_send_payload or {}).get("executive_summary") or ["暂无"])
            return (
                "当前公司口径：\n"
                f"- 本周花费：{metrics.get('本周花费', '未知')}\n"
                f"- 整体收入：{metrics.get('整体收入', '未知')}\n"
                f"- 公司总收入ROI：{metrics.get('公司总收入ROI', '未知')}\n"
                f"- 核心结论：{focus[0] if focus else '暂无'}"
            )

        project_key = self._match_project_key(normalized)
        if project_key:
            detail_reply = self._build_project_detail_reply(project_key, market_detail_text)
            if detail_reply:
                return detail_reply

        if any(token in normalized.lower() for token in ("项目", "p02", "p04", "p07", "mermaid", "witch", "vampire")):
            if not project_key:
                return "当前可直接回答的项目有：P02 Mermaid、P04 Witch、P07 Vampire。请直接写项目名。"
            metrics = ((pre_send_payload or {}).get("key_metrics") or {}).get(project_key) or {}
            summary_lines = (pre_send_payload or {}).get("focus_points") or []
            risk_line = next((line for line in summary_lines if project_key.split()[0] in line), "暂无项目结论。")
            return (
                f"{project_key} 当前口径：\n"
                f"- 花费：{metrics.get('花费', '未知')}\n"
                f"- 总收入：{metrics.get('总收入', '未知')}\n"
                f"- 总收入ROI：{metrics.get('总收入ROI', '未知')}\n"
                f"- 付费净ROI：{metrics.get('付费净ROI', '未知')}\n"
                f"- 结论：{risk_line}"
            )

        if any(token in normalized for token in ("风险", "问题", "不可信", "可信度")):
            risks = (pre_send_payload or {}).get("risks") or []
            credibility = next(
                (line for line in ((pre_send_payload or {}).get("executive_summary") or []) if "可信度" in line),
                "数据可信度：暂无",
            )
            top_risks = "\n".join(f"- {item}" for item in risks[:3]) if risks else "- 暂无"
            return f"{credibility}\n当前主要风险：\n{top_risks}"

        if any(token in normalized for token in ("群", "机器人", "回复", "allow", "chat")):
            allowed = (status_payload or {}).get("allowed_groups") or []
            if not allowed:
                return "当前还没有已记录的允许群。"
            return "当前已接通的群：\n" + "\n".join(f"- {item}" for item in allowed)

        if "最新待办" in normalized or "待办状态" in normalized:
            return self.latest_request_summary(chat_id)
        if "最近待办" in normalized or "待办列表" in normalized:
            return self.latest_requests_list(chat_id)

        return (
            "当前我可以回答这几类问题：\n"
            "- 本周ROI多少\n"
            "- P04为什么有风险\n"
            "- 现在能发吗\n"
            "- 当前回调地址是什么\n"
            "- 最新待办 / 最近待办\n"
            "- 最近发送记录"
        )

    def queue_request(self, *, chat_id: str, text: str, decision: GroupRouteDecision) -> GroupRequirementRecord:
        return self._requirements_queue.append(
            chat_id=chat_id,
            user_text=text,
            request_summary=decision.summary or self._summarize_request(text),
            suggested_scope=decision.scopes or self._infer_scopes(text),
            risk_level=decision.risk_level or self._infer_risk_level(text),
            normalized_brief=self._build_normalized_brief(text, decision),
            suggested_action=self._build_suggested_action(text, decision),
            requires_manual_confirmation=True,
        )

    def append_followup(self, *, decision: GroupRouteDecision) -> dict[str, Any] | None:
        if not decision.target_request_id or not decision.note_text:
            return None
        return self._requirements_queue.append_note(request_id=decision.target_request_id, note=decision.note_text)

    def update_request_status(self, *, decision: GroupRouteDecision) -> dict[str, Any] | None:
        if not decision.target_request_id or not decision.target_status:
            return None
        return self._requirements_queue.update_status(
            request_id=decision.target_request_id,
            status=decision.target_status,
            note=f"状态更新为 {self._display_status(decision.target_status)}",
        )

    def build_request_reply(self, record: GroupRequirementRecord) -> str:
        scopes = " / ".join(record.suggested_scope) if record.suggested_scope else "待人工补充"
        return (
            "我已记录这条需求：\n"
            f"- 需求：{record.request_summary}\n"
            f"- 影响范围：{scopes}\n"
            f"- 待办编号：{record.id}\n"
            "- 当前只会入队，不会直接改配置或直接发群\n"
            "- 如需继续执行，请回到 Codex 会话里处理"
        )

    def build_followup_reply(self, item: dict[str, Any] | None) -> str:
        if not item:
            return "没有找到可补充的待办。"
        notes = item.get("notes") or []
        latest_note = notes[-1] if notes else "无"
        return (
            "已补充到最新待办：\n"
            f"- {item.get('id')}: {item.get('request_summary')}\n"
            f"- 当前状态：{self._display_status(str(item.get('status') or ''))}\n"
            f"- 最新补充：{latest_note}"
        )

    def build_status_update_reply(self, item: dict[str, Any] | None) -> str:
        if not item:
            return "没有找到要更新的待办。"
        return (
            "待办状态已更新：\n"
            f"- {item.get('id')}: {item.get('request_summary')}\n"
            f"- 当前状态：{self._display_status(str(item.get('status') or ''))}"
        )

    def build_request_detail_reply(self, item: dict[str, Any] | None) -> str:
        if not item:
            return "没有找到这条待办。"
        request_summary, normalized_brief, suggested_action = self._normalize_request_fields(item)
        lines = [
            f"待办详情：{item.get('id')}",
            f"- 需求：{request_summary}",
            f"- 状态：{self._display_status(str(item.get('status') or ''))}",
            f"- 风险：{item.get('risk_level')}",
        ]
        owner = self._infer_owner(item)
        if owner:
            lines.append(f"- 建议负责人：{owner}")
        if normalized_brief:
            lines.append(f"- 规范描述：{normalized_brief}")
        if suggested_action:
            lines.append(f"- 建议动作：{suggested_action}")
        notes = item.get("notes") or []
        if notes:
            lines.append(f"- 最新补充：{notes[-1]}")
        return "\n".join(lines)

    def build_help_text(self) -> str:
        return (
            "当前支持两类能力：\n"
            "1. 固定指令：简版 / 详细版 / 回收版 / 老板版 / 摘要 / 帮助\n"
            "2. 直接提问：例如“本周ROI多少”“P04为什么有风险”“现在能发吗”“当前回调地址是什么”\n\n"
            "也支持记录需求，但当前只会记为待办，不会直接改系统配置。\n"
            "你还可以这样说：\n"
            "- 最新待办\n"
            "- 最近待办\n"
            "- 最近发送记录\n"
            "- 补充：老板版再短一点\n"
            "- 待办 req_xxx\n"
            "- 确认待办 req_xxx\n"
            "- 开始处理 req_xxx\n"
            "- 批准待办 req_xxx\n"
            "- 驳回待办 req_xxx\n"
            "- 完成待办 req_xxx\n"
            "- 已确认待办\n"
            "- 进行中待办\n"
            "- 已批准任务\n"
            "- 待办统计\n"
            "- 执行清单\n"
            "- 正式任务包\n"
            "- 待审批执行单"
        )

    def latest_request_summary(self, chat_id: str) -> str:
        item = self._requirements_queue.latest_open_for_chat(chat_id)
        if not item:
            return "当前这个群还没有需求待办。"
        notes = item.get("notes") or []
        lines = [
            "当前最新待办：",
            f"- {item.get('id')}: {item.get('request_summary')}",
            f"- 状态：{self._display_status(str(item.get('status') or ''))}",
            f"- 风险：{item.get('risk_level')}",
        ]
        if notes:
            lines.append(f"- 最新补充：{notes[-1]}")
        return "\n".join(lines)

    def latest_requests_list(self, chat_id: str, limit: int = 3) -> str:
        items = self._requirements_queue.latest_open_list_for_chat(chat_id, limit=limit)
        if not items:
            return "当前这个群还没有需求待办。"
        lines = ["最近待办："]
        for item in items:
            lines.append(
                f"- {item.get('id')}: {item.get('request_summary')} | 状态={self._display_status(str(item.get('status') or ''))}"
            )
        return "\n".join(lines)

    def get_request_detail(self, request_id: str) -> str:
        return self.build_request_detail_reply(self._requirements_queue.get(request_id))

    def list_requests_by_status(self, chat_id: str, statuses: list[str], title: str) -> str:
        items = self._requirements_queue.list_by_status(chat_id=chat_id, statuses=statuses, limit=10)
        if not items:
            return f"{title}：当前没有。"
        lines = [f"{title}："]
        for item in items:
            lines.append(
                f"- {item.get('id')}: {item.get('request_summary')} | 状态={self._display_status(str(item.get('status') or ''))}"
            )
        return "\n".join(lines)

    def build_status_counts_reply(self, chat_id: str) -> str:
        counts = self._requirements_queue.status_counts(chat_id=chat_id)
        if not counts:
            return "当前这个群还没有需求待办。"
        order = ["new", "confirmed", "in_progress", "approved", "rejected", "done", "closed"]
        lines = ["待办统计："]
        for status in order:
            if status in counts:
                lines.append(f"- {self._display_status(status)}：{counts[status]}")
        for status, value in counts.items():
            if status not in order:
                lines.append(f"- {status}：{value}")
        return "\n".join(lines)

    def export_execution_checklist(self, chat_id: str) -> Path:
        items = self._requirements_queue.list_by_status(
            chat_id=chat_id,
            statuses=["confirmed", "in_progress", "approved"],
            limit=100,
        )
        path = self._active_output_dir / "group_execution_checklist_latest.md"
        lines = ["# Group Execution Checklist", ""]
        if not items:
            lines.append("当前没有已确认、进行中或已批准的待办。")
        else:
            for item in items:
                request_summary, normalized_brief, suggested_action = self._normalize_request_fields(item)
                lines.append(f"## {item.get('id')}")
                lines.append(f"- 需求：{request_summary}")
                lines.append(f"- 状态：{self._display_status(str(item.get('status') or ''))}")
                owner = self._infer_owner(item)
                if owner:
                    lines.append(f"- 建议负责人：{owner}")
                if normalized_brief:
                    lines.append(f"- 规范描述：{normalized_brief}")
                if suggested_action:
                    lines.append(f"- 建议动作：{suggested_action}")
                notes = item.get("notes") or []
                if notes:
                    lines.append(f"- 最新补充：{notes[-1]}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def export_task_packet(self, chat_id: str) -> Path:
        items = self._requirements_queue.list_by_status(
            chat_id=chat_id,
            statuses=["approved", "in_progress"],
            limit=100,
        )
        path = self._active_output_dir / "group_task_packet_latest.md"
        lines = ["# Group Task Packet", ""]
        if not items:
            lines.append("当前没有可进入执行准备的任务。")
        else:
            for index, item in enumerate(items, start=1):
                request_summary, normalized_brief, suggested_action = self._normalize_request_fields(item)
                owner = self._infer_owner(item)
                priority = self._infer_priority(item)
                lines.append(f"## Task {index}: {item.get('id')}")
                lines.append(f"- 标题：{request_summary}")
                lines.append(f"- 当前状态：{self._display_status(str(item.get('status') or ''))}")
                lines.append(f"- 优先级：{self._priority_display.get(priority, priority)}")
                if owner:
                    lines.append(f"- 建议负责人：{owner}")
                if normalized_brief:
                    lines.append(f"- 任务描述：{normalized_brief}")
                if suggested_action:
                    lines.append(f"- 建议执行：{suggested_action}")
                notes = item.get("notes") or []
                if notes:
                    lines.append(f"- 最新备注：{notes[-1]}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def export_approval_packet(self, chat_id: str) -> Path:
        items = self._requirements_queue.list_by_status(
            chat_id=chat_id,
            statuses=["confirmed", "in_progress"],
            limit=100,
        )
        path = self._active_output_dir / "group_approval_packet_latest.md"
        lines = ["# Group Approval Packet", ""]
        if not items:
            lines.append("当前没有待审批执行单。")
        else:
            for index, item in enumerate(items, start=1):
                request_summary, normalized_brief, suggested_action = self._normalize_request_fields(item)
                owner = self._infer_owner(item)
                priority = self._infer_priority(item)
                lines.append(f"## Approval Item {index}: {item.get('id')}")
                lines.append(f"- 事项：{request_summary}")
                lines.append(f"- 当前状态：{self._display_status(str(item.get('status') or ''))}")
                lines.append(f"- 优先级：{self._priority_display.get(priority, priority)}")
                if owner:
                    lines.append(f"- 建议负责人：{owner}")
                if normalized_brief:
                    lines.append(f"- 执行说明：{normalized_brief}")
                if suggested_action:
                    lines.append(f"- 批准后动作：{suggested_action}")
                lines.append("- 审批结论：待确认")
                notes = item.get("notes") or []
                if notes:
                    lines.append(f"- 最新备注：{notes[-1]}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def export_approved_tasks(self, chat_id: str) -> Path:
        items = self._requirements_queue.list_by_status(chat_id=chat_id, statuses=["approved"], limit=100)
        path = self._active_output_dir / "group_approved_tasks_latest.md"
        lines = ["# Group Approved Tasks", ""]
        if not items:
            lines.append("当前没有已批准任务。")
        else:
            for item in items:
                request_summary, normalized_brief, suggested_action = self._normalize_request_fields(item)
                owner = self._infer_owner(item)
                priority = self._infer_priority(item)
                lines.append(f"## {item.get('id')}")
                lines.append(f"- 标题：{request_summary}")
                lines.append(f"- 优先级：{self._priority_display.get(priority, priority)}")
                if owner:
                    lines.append(f"- 负责人：{owner}")
                if normalized_brief:
                    lines.append(f"- 描述：{normalized_brief}")
                if suggested_action:
                    lines.append(f"- 执行动作：{suggested_action}")
                notes = item.get("notes") or []
                if notes:
                    lines.append(f"- 最新备注：{notes[-1]}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def list_requests_by_scope(self, chat_id: str, scopes: list[str], title: str) -> str:
        items = self._requirements_queue.list_by_scope(chat_id=chat_id, scopes=scopes, limit=10)
        if not items:
            return f"{title}：当前没有。"
        lines = [f"{title}："]
        for item in items:
            lines.append(
                f"- {item.get('id')}: {item.get('request_summary')} | 状态={self._display_status(str(item.get('status') or ''))}"
            )
        return "\n".join(lines)

    def list_requests_by_risk(self, chat_id: str, risk_levels: list[str], title: str) -> str:
        items = self._requirements_queue.list_by_risk(chat_id=chat_id, risk_levels=risk_levels, limit=10)
        if not items:
            return f"{title}：当前没有。"
        lines = [f"{title}："]
        for item in items:
            lines.append(
                f"- {item.get('id')}: {item.get('request_summary')} | 风险={item.get('risk_level')} | 状态={self._display_status(str(item.get('status') or ''))}"
            )
        return "\n".join(lines)

    def list_requests_by_owner(self, chat_id: str, owner: str, title: str) -> str:
        items = self._requirements_queue.latest_for_chat(chat_id, limit=100)
        filtered = [item for item in items if self._infer_owner(item) == owner]
        if not filtered:
            return f"{title}：当前没有。"
        lines = [f"{title}："]
        for item in filtered[:10]:
            lines.append(
                f"- {item.get('id')}: {item.get('request_summary')} | 状态={self._display_status(str(item.get('status') or ''))}"
            )
        return "\n".join(lines)

    def _looks_like_change_request(self, text: str) -> bool:
        normalized = text.strip()
        if self._looks_like_question(normalized):
            return False
        if any(normalized.startswith(prefix) for prefix in self._change_prefixes):
            return True
        action_markers = ("改", "修改", "调整", "优化", "新增", "增加", "删除", "压缩", "缩短", "精简", "修复", "接入", "打通")
        return any(marker in normalized for marker in action_markers)

    def _looks_like_fixed_command(self, text: str) -> bool:
        compact = text.replace("@机器人", "").replace(" ", "").strip()
        if compact in ("帮助", "help"):
            return True
        return compact in self._fixed_commands

    def _looks_like_question(self, text: str) -> bool:
        if "?" in text or "？" in text:
            return True
        question_tokens = (
            "多少",
            "为什么",
            "能不能",
            "能否",
            "是否",
            "现在",
            "哪个",
            "哪里",
            "怎么",
            "怎么样",
            "什么",
            "请问",
            "麻烦",
            "可不可以",
            "要不要",
            "值不值得",
            "有没有",
            "最新待办",
            "最近待办",
            "待办状态",
            "待办列表",
            "待办 req_",
            "已确认待办",
            "进行中待办",
            "已批准任务",
            "待办统计",
            "执行清单",
            "老板版待办",
            "市场版待办",
            "回收版待办",
            "机器人待办",
            "高风险待办",
            "林凯待办",
            "牟耕待办",
            "姜会伟待办",
            "正式任务包",
            "待审批执行单",
            "最近发送记录",
            "发送记录",
        )
        return any(token in text for token in question_tokens)

    def _summarize_request(self, text: str) -> str:
        trimmed = " ".join((text or "").split())
        if len(trimmed) <= 42:
            return trimmed
        return f"{trimmed[:42]}..."

    def _infer_scopes(self, text: str) -> list[str]:
        scopes: list[str] = []
        lowered = text.lower()
        if any(token in text for token in ("老板", "管理层")):
            scopes.append("boss_report")
        if any(token in text for token in ("市场", "周报", "详细版", "简版")):
            scopes.append("market_report")
        if any(token in text for token in ("回收", "倍率")):
            scopes.append("recovery_report")
        if any(token in text for token in ("回调", "机器人", "群", "问答")):
            scopes.append("feishu_bot")
        if any(token in lowered for token in ("webhook", "callback")) or "发送" in text or "定时" in text:
            scopes.append("delivery_chain")
        if any(token in lowered for token in ("creative", "google", "facebook", "meta")) or "素材" in text:
            scopes.append("creative_analysis")
        return scopes or ["general_request"]

    def _infer_risk_level(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in (".env", "webhook", "callback")) or any(
            token in text for token in ("白名单", "定时", "群", "发送")
        ):
            return "high"
        if any(token in text for token in ("老板版", "管理层", "口径", "数据")):
            return "medium"
        return "low"

    def _match_project_key(self, text: str) -> str | None:
        mapping = {
            "p02": "P02 Mermaid",
            "mermaid": "P02 Mermaid",
            "p04": "P04 Witch",
            "witch": "P04 Witch",
            "p07": "P07 Vampire",
            "vampire": "P07 Vampire",
        }
        lowered = text.lower()
        for token, key in mapping.items():
            if token in lowered:
                return key
        return None

    def _normalize_text(self, text: str) -> str:
        normalized = (text or "").strip()
        normalized = normalized.replace("@机器人", " ").replace("@ bot", " ").replace("@bot", " ")
        normalized = " ".join(normalized.split())
        return normalized.strip()

    def _detect_status_update(self, text: str) -> GroupRouteDecision | None:
        request_id = self._extract_request_id(text)
        if not request_id:
            return None
        for prefix, status in self._status_prefix_map.items():
            if text.startswith(prefix):
                return GroupRouteDecision(route="status_update", target_request_id=request_id, target_status=status)
        return None

    def _detect_followup(self, text: str, *, chat_id: str) -> GroupRouteDecision | None:
        normalized = text.strip()
        if not any(normalized.startswith(prefix) for prefix in self._followup_prefixes):
            return None
        item = self._requirements_queue.latest_open_for_chat(chat_id)
        if not item:
            return None
        note_text = normalized
        for prefix in self._followup_prefixes:
            if note_text.startswith(prefix):
                note_text = note_text[len(prefix) :].lstrip("：: ")
                break
        note_text = note_text or normalized
        return GroupRouteDecision(
            route="change_followup",
            target_request_id=str(item.get("id") or ""),
            note_text=note_text,
        )

    def _extract_request_id(self, text: str) -> str:
        match = re.search(r"(req_\d{8}_\d{6}_\d{3})", text)
        return match.group(1) if match else ""

    def _build_normalized_brief(self, text: str, decision: GroupRouteDecision) -> str:
        scope = " / ".join(decision.scopes or self._infer_scopes(text))
        summary = decision.summary or self._summarize_request(text)
        return f"{summary} | 影响范围={scope}"

    def _build_suggested_action(self, text: str, decision: GroupRouteDecision) -> str:
        scope = decision.scopes or self._infer_scopes(text)
        if "boss_report" in scope:
            return "先调整老板版文案结构，再重新预览老板版输出。"
        if "market_report" in scope:
            return "先改市场版文案或模块，再重新生成预览核对。"
        if "recovery_report" in scope:
            return "先调整回收版标题或结构，再重新生成回收版预览核对。"
        if "feishu_bot" in scope:
            return "先确认是否只是回复逻辑调整，再决定是否需要改回调服务。"
        return "先在 Codex 会话里确认需求边界，再安排实现。"

    def _normalize_request_fields(self, item: dict[str, Any]) -> tuple[str, str, str]:
        request_summary = str(item.get("request_summary") or "").strip()
        scopes = [str(scope).strip() for scope in (item.get("suggested_scope") or []) if str(scope).strip()]
        normalized_brief = str(item.get("normalized_brief") or "").strip()
        if "?" in normalized_brief and request_summary:
            normalized_brief = f"{request_summary} | 影响范围={' / '.join(scopes) if scopes else 'general_request'}"
        suggested_action = str(item.get("suggested_action") or "").strip()
        if "?" in suggested_action and request_summary:
            suggested_action = self._build_suggested_action(
                request_summary,
                GroupRouteDecision(route="change_request", scopes=scopes, summary=request_summary),
            )
        return request_summary, normalized_brief, suggested_action

    def _infer_owner(self, item: dict[str, Any]) -> str:
        summary = str(item.get("request_summary") or "")
        scopes = [str(scope).strip() for scope in (item.get("suggested_scope") or []) if str(scope).strip()]
        rules = self._settings.task_owner_rules or {}

        by_game = rules.get("by_game") or {}
        for game, owner in by_game.items():
            if str(game) and str(game) in summary:
                return str(owner)

        by_action_type = rules.get("by_action_type") or {}
        for action_type, owner in by_action_type.items():
            if str(action_type) and str(action_type) in summary:
                return str(owner)

        if "boss_report" in scopes or "market_report" in scopes or "recovery_report" in scopes:
            if "素材" in summary:
                return "牟耕"
            return "林凯"
        if "feishu_bot" in scopes:
            return "姜会伟"
        return ""

    def _infer_priority(self, item: dict[str, Any]) -> str:
        risk_level = str(item.get("risk_level") or "").strip().lower()
        status = str(item.get("status") or "").strip().lower()
        scopes = [str(scope).strip() for scope in (item.get("suggested_scope") or []) if str(scope).strip()]
        if risk_level == "high":
            return "P0"
        if status in {"approved", "in_progress"}:
            return "P1"
        if "boss_report" in scopes:
            return "P1"
        if "market_report" in scopes or "recovery_report" in scopes:
            return "P2"
        return "P3"

    def _build_project_detail_reply(self, project_key: str, market_detail_text: str) -> str | None:
        if not market_detail_text:
            return None
        lines = market_detail_text.splitlines()
        header = f"**{project_key}**"
        start_index = None
        for index, line in enumerate(lines):
            if line.strip() == header:
                start_index = index + 1
                break
        if start_index is None:
            return None
        picked: list[str] = []
        for line in lines[start_index:]:
            stripped = line.strip()
            if stripped.startswith("**") and stripped.endswith("**"):
                break
            if stripped.startswith("- 回本门槛：") or stripped.startswith("- 当前主要消耗集中在") or stripped.startswith("- 风险判断：") or stripped.startswith("- 建议动作：") or stripped.startswith("- 原因=") or stripped.startswith("- 行动="):
                picked.append(stripped.removeprefix("- ").strip())
        if not picked:
            return None
        return f"{project_key} 风险解释：\n- " + "\n- ".join(picked[:6])

    @staticmethod
    def _extract_company_metrics_from_market_detail(text: str) -> dict[str, str]:
        if not text:
            return {}
        patterns = {
            "本周花费": r"\*\*本周花费\*\*\s*\n([^\n]+)",
            "整体收入": r"\*\*整体收入\*\*\s*\n([^\n]+)",
            "公司总收入ROI": r"\*\*公司总收入ROI\*\*\s*\n([^\n]+)",
            "主投渠道": r"\*\*主投渠道\*\*\s*\n([^\n]+)",
        }
        metrics: dict[str, str] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                metrics[key] = match.group(1).strip()
        return metrics

    def _read_json(self, name: str) -> dict[str, Any] | None:
        path = self._active_output_dir / name
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _read_text(self, name: str) -> str:
        path = self._active_output_dir / name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _latest_pre_send_payload(self) -> dict[str, Any] | None:
        candidates = sorted(self._active_output_dir.glob("pre_send_summary_*.json"), reverse=True)
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _latest_market_detail_text(self) -> str:
        candidates = sorted(self._active_output_dir.glob("card_preview_market_detail_*.md"), reverse=True)
        for path in candidates:
            return path.read_text(encoding="utf-8")
        return ""

    def _display_status(self, status: str) -> str:
        return self._status_display.get(status.strip().lower(), status or "未知")
