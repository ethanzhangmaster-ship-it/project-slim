from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
import re
from typing import Any

from market_ops.clean_digest import CleanWeeklyDigestBuilder
from market_ops.digest import CampaignDigestItem, RecoveryAnalysis, RecoveryCurveRow, WeeklyDigest
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.payback_targets import PaybackTargetsBuilder, ProjectTargets


TEAM_TITLE = "\u5e02\u573a\u90e8\u5468\u62a5"
SIMPLE_TEAM_TITLE = "\u5e02\u573a\u90e8\u7b80\u62a5"
SEC_COMPANY = "1. \u516c\u53f8\u603b\u4f53\u6570\u636e\u60c5\u51b5"
SEC_PROJECT = "2. \u6bcf\u4e2a\u9879\u76ee\u7684\u6295\u653e\u6570\u636e\u60c5\u51b5\u5206\u6790"
SEC_CREATIVE = "3. \u6700\u8fd1\u7684\u7d20\u6750\u5206\u6790\u60c5\u51b5"
SEC_ACTION = "4. \u672c\u5468\u5efa\u8bae\u52a8\u4f5c"
NO_DATA = "\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u6570\u636e\u3002"
NO_FORECAST = "暂无预测回收结果"
NO_ACTUAL = "暂无实际回收数据"
INVALID_CREATIVE_SIGNAL_VALUES = {"", "-", "display", "unknown", "(not set)", "nan", "none"}
MIN_CAMPAIGN_DECISION_SPEND = 200.0
MIN_CAMPAIGN_DECISION_SHARE = 0.05
MIN_DIMENSION_DECISION_SPEND = 100.0
MIN_DIMENSION_DECISION_SHARE = 0.02
CHANNEL_REVENUE_ANOMALY_THRESHOLD = 0.20


class FinalWeeklyDigestBuilder(CleanWeeklyDigestBuilder):
    def build(
        self,
        report,
        ads_rows,
        creative_rows,
        revenue_rows,
        revenue_breakdown_rows=None,
    ):
        digest = super().build(report, ads_rows, creative_rows, revenue_rows, revenue_breakdown_rows)
        self._latest_project_entity_signals = {}
        self._latest_creative_context = self._build_creative_context_map(creative_rows)
        digest.title = f"{TEAM_TITLE} | {digest.report_date.isoformat()}"
        digest.creative_notes = self._prepend_creative_confidence_note(digest.creative_notes, revenue_breakdown_rows or [])
        for metric, label in zip(digest.company_metrics, ["本周花费", "整体收入", "公司总收入ROI", "主投渠道"]):
            metric.label = label

        active_project_keys = {self._project_key(item.game) for item in digest.project_items if item.game}
        covered_recovery_keys = sorted(
            self._project_key(item.game)
            for item in digest.project_items
            if item.game and item.actual_recovery
        )
        missing_recovery_keys = sorted(key for key in active_project_keys if key and key not in covered_recovery_keys)

        if covered_recovery_keys or missing_recovery_keys:
            covered_text = "、".join(covered_recovery_keys) if covered_recovery_keys else "无"
            missing_text = "、".join(missing_recovery_keys) if missing_recovery_keys else "无"

        if not digest.creative_notes:
            digest.creative_notes = self._build_clean_creative_notes(creative_rows)
        recovery_map = getattr(self, "_latest_recovery_map", {})
        digest.forecast_bias_lines = []
        digest.forecast_accuracy_lines = []
        segment_map = self._build_project_segment_diagnostics(revenue_breakdown_rows or [], report.report_date)
        confidence_map = self._build_market_confidence_map(report.report_date, revenue_rows, revenue_breakdown_rows or [], creative_rows)
        digest.company_highlights = self._build_clean_company_highlights(
            report.report_date,
            ads_rows,
            revenue_rows,
            revenue_breakdown_rows or [],
            confidence_map,
        )
        if covered_recovery_keys or missing_recovery_keys:
            covered_text = "、".join(covered_recovery_keys) if covered_recovery_keys else "无"
            missing_text = "、".join(missing_recovery_keys) if missing_recovery_keys else "无"
            digest.company_highlights.append(f"回收曲线接入情况：已接入={covered_text}；未接入={missing_text}。")
        payback_targets_map = self._load_payback_targets_map(report.report_date)
        digest.company_confidence_lines = self._build_market_confidence_lines(confidence_map)
        digest.anomaly_lines = self._build_market_anomaly_lines(revenue_breakdown_rows or [], creative_rows, ads_rows, confidence_map)
        digest.campaign_items = self._build_campaign_digest_items(revenue_breakdown_rows or [], report.report_date, confidence_map)

        for item in digest.project_items:
            recovery = recovery_map.get(item.game) or recovery_map.get(self._project_key(item.game))
            if recovery:
                item.cohort_age_summary = self._format_cohort_age_summary(recovery)
                item.forecast_confidence = recovery.forecast_confidence or "暂无"
                item.pending_validation = recovery.pending_validation
                item.needs_validation = recovery.needs_validation
                item.forecast_analysis = self._build_market_forecast_analysis(recovery)
                item.payback_forecast = self._format_payback_summary(recovery.payback_day, recovery.forecast_curve, item.spend)
                item.forecast_recommendation = self._build_market_recommendation(recovery, item.spend)
                digest.forecast_accuracy_lines.append(
                    self._format_market_accuracy_line(item.game, recovery)
                )
            item.segment_diagnostics = segment_map.get(item.game) or segment_map.get(self._project_key(item.game)) or []
            if item.actual_recovery:
                pass
            else:
                item.actual_recovery = NO_ACTUAL
                item.forecast_recovery = NO_FORECAST
                item.payback_forecast = "回本预估：暂无可用结果"
                item.forecast_analysis = "暂无可比结果"
                item.forecast_recommendation = "在接入可信回收来源之前，先维持预算不动。"
            self._populate_project_decision_fields(item, confidence_map, report.report_date, payback_targets_map.get(self._project_key(item.game)))
            structure_note = str(getattr(item, "structure_confidence_note", "") or "")
            if structure_note:
                item.profit_split = structure_note
            else:
                rebuilt_profit_split = self._rebuild_project_profit_split(
                    revenue_breakdown_rows or [],
                    report.report_date,
                    item.game,
                )
                item.profit_split = self._apply_project_structure_gate(
                    rebuilt_profit_split or item.profit_split,
                    item.segment_diagnostics,
                )
        management_action_payload = ManagementActionListBuilder(self._settings).build_payload(report.report_date)
        digest.next_actions = self._build_clean_next_actions(
            report.draft_actions[:3],
            digest.project_items,
            management_action_payload,
        )
        digest.action_refinement_notes = self._build_action_refinement_notes(
            report.draft_actions[:3],
            digest.project_items,
            management_action_payload,
        )
        digest.forecast_bias_lines = self._build_market_bias_lines()
        self._populate_creative_decision_fields(digest.creative_items, confidence_map, report.report_date)
        return digest

    @staticmethod
    def _prepend_creative_confidence_note(notes: list[str], revenue_breakdown_rows) -> list[str]:
        paid_cost = sum(
            float(row.cost or 0.0)
            for row in revenue_breakdown_rows
            if float(row.cost or 0.0) > 0
        )
        if paid_cost <= 0:
            return notes
        google_cost = sum(
            float(row.cost or 0.0)
            for row in revenue_breakdown_rows
            if "google" in str(getattr(row, "partner", "") or "").lower() and float(row.cost or 0.0) > 0
        )
        if google_cost > 0:
            prefix = "素材可信度提示：当前素材层优先使用 Adjust API 的 campaign/adgroup/creative/source 明细；Facebook 可按 creative 维度判断，Google 若 creative 为占位值则按 source/adgroup/campaign 代理层观察，不等同于原生素材ID。"
        else:
            prefix = "素材可信度提示：当前素材层优先使用 Adjust API 的 campaign/adgroup/creative/source 明细；未过样本门槛的素材只作观察，不输出强结论。"
        if notes and notes[0] == prefix:
            return notes
        return [prefix, *notes]

    def _build_market_summary_lines(self, digest: WeeklyDigest) -> list[str]:
        metric_map = {metric.label: metric.value for metric in digest.company_metrics}
        spend_value = metric_map.get("本周花费", "暂无")
        revenue_value = metric_map.get("整体收入", "暂无")
        roi_value = metric_map.get("公司总收入ROI", "暂无")
        top_channel = metric_map.get("主投渠道", "暂无")
        lines = [
            f"本周公司花费 {spend_value}；整体收入 {revenue_value}；公司总收入ROI {roi_value}；主投渠道 {top_channel}。"
        ]

        risk_item = self._select_market_risk_project(digest.project_items)
        if risk_item:
            lines.append(f"最大风险项目：{risk_item}")

        risk_game = self._extract_summary_game_name(risk_item)
        watch_item = self._select_market_watch_project(digest.project_items, exclude_game=risk_game)
        if watch_item:
            lines.append(f"当前可保留观察项目：{watch_item}")

        if digest.campaign_items:
            campaign = self._select_summary_campaign(digest.campaign_items, digest.next_actions)
            reason = self._summary_campaign_reason(campaign)
            lines.append(
                f"重点Campaign：{campaign.game} / {campaign.channel} / {campaign.campaign}，ROI {campaign.roi:.2f}，当前动作：{campaign.suggested_action}；原因：{reason}。"
            )

        action_candidates = self._select_market_summary_actions(digest)
        action_summary = "；".join(self._summarize_market_action_line(action) for action in action_candidates[:2] if action)
        if action_summary:
            lines.append(f"本周执行优先级：{action_summary}")

        confidence_summary = self._build_market_confidence_summary(digest.company_confidence_lines)
        if confidence_summary:
            lines.append(f"数据可信度：{confidence_summary}")
        return lines[:6]

    @staticmethod
    def _build_market_confidence_summary(confidence_lines: list[str]) -> str:
        parts: list[str] = []
        for line in confidence_lines or []:
            text = str(line or "").strip()
            if "：" not in text:
                continue
            module, remainder = text.split("：", 1)
            level = remainder.split("；", 1)[0].strip()
            if not module or not level:
                continue
            if module in {"花费", "收入", "ROI"}:
                mapped = "可直接决策" if level == "高" else ("仅方向判断" if level == "中" else "先补数据")
            elif module == "公司盈利结构":
                mapped = "可下结构结论" if level == "高" else ("仅保守判断" if level == "中" else "先补结构数据")
            else:
                mapped = "可用" if level == "高" else ("仅方向判断" if level == "中" else "先补素材数据")
            parts.append(f"{module}={mapped}")
        return "；".join(parts[:5])

    def _select_market_risk_project(self, project_items) -> str:
        ranked = sorted(
            [item for item in project_items or [] if getattr(item, "game", "")],
            key=lambda item: self._market_risk_score(
                item,
                getattr(item, "risk_judgement", "") or getattr(item, "judgement", ""),
                getattr(item, "suggested_action", "") or "",
            ),
            reverse=True,
        )
        if not ranked:
            return ""
        item = ranked[0]
        risk_text = getattr(item, "risk_judgement", "") or getattr(item, "judgement", "")
        action_text = getattr(item, "suggested_action", "") or ""
        suffix = self._market_risk_reason_suffix(risk_text, action_text)
        return f"{item.game}：{risk_text}{suffix}"

    def _select_market_watch_project(self, project_items, exclude_game: str = "") -> str:
        candidates = [item for item in project_items or [] if getattr(item, "game", "")]
        if exclude_game:
            filtered = [item for item in candidates if self._project_key(getattr(item, "game", "")) != self._project_key(exclude_game)]
            if filtered:
                candidates = filtered
        if not candidates:
            return ""
        best = max(
            candidates,
            key=lambda item: (
                getattr(item, "paid_roi_net", None) if getattr(item, "paid_roi_net", None) is not None else getattr(item, "project_roi", 0.0),
                getattr(item, "project_roi", 0.0),
            ),
        )
        actual_d7 = self._extract_curve_value(getattr(best, "actual_recovery", ""), 7) or self._extract_curve_value(getattr(best, "actual_recovery", ""), 3)
        gate_floor = self._extract_first_number(getattr(best, "payback_gate", ""))
        if actual_d7 is not None:
            if gate_floor is not None and actual_d7 >= gate_floor:
                return f"{best.game}：实际D7 {actual_d7:.2f}，已高于当前历史保底线，先维持预算观察。"
            return f"{best.game}：实际D7 {actual_d7:.2f}，先继续观察后续成熟回收。"
        return f"{best.game}：先继续观察后续成熟回收。"

    @staticmethod
    def _extract_summary_game_name(summary_text: str) -> str:
        text = str(summary_text or "").strip()
        if not text:
            return ""
        for marker in ("：", ":"):
            if marker in text:
                return text.split(marker, 1)[0].strip()
        return text

    @classmethod
    def _market_risk_score(cls, item, text: str, action_text: str = "") -> float:
        base = cls._market_risk_rank(text, action_text)
        spend = float(getattr(item, "spend", 0.0) or 0.0)
        revenue = float(getattr(item, "total_revenue", 0.0) or 0.0)
        return base * 1_000_000.0 + max(spend, revenue)

    @staticmethod
    def _market_risk_rank(text: str, action_text: str = "") -> int:
        normalized = f"{text or ''} {action_text or ''}"
        if "项目级明细未接入" in normalized or "回收来源未接入" in normalized:
            return 4
        if "低可信度" in normalized or "低可信" in normalized:
            return 1
        if "未达回本门槛" in normalized or "未达历史保底线" in normalized or "低于保底线" in normalized:
            return 5
        if "亏损" in normalized:
            return 4
        if "回收偏弱" in normalized:
            return 3
        if "收入走弱" in normalized:
            return 2
        content = f"{text or ''} {action_text or ''}"
        if "低可信度" in content:
            return 1
        if "未达回本门槛" in content or "未达历史保底线" in content or "低于保底线" in content:
            return 5
        if "亏损" in content:
            return 4
        if "回收偏弱" in content:
            return 3
        if "收入走弱" in content:
            return 2
        return 0

    @staticmethod
    def _market_risk_reason_suffix(risk_text: str, action_text: str) -> str:
        if not action_text:
            return ""
        if "低可信度" in (risk_text or ""):
            return "；当前先校对数据口径，不直接据此做强动作。"
        if any(flag in (risk_text or "") for flag in ("未达回本门槛", "未达历史保底线", "低于保底线", "亏损", "回收偏弱")):
            return f"；当前动作：{action_text}"
        return ""

    @staticmethod
    def _normalize_action_line(action: str) -> str:
        text = str(action or "").strip()
        if not text:
            return ""
        return text.rstrip("。")

    def _summarize_market_action_line(self, action: str) -> str:
        text = self._normalize_action_line(action)
        if not text:
            return ""
        action_type, _, remainder = text.partition("：")
        owner = self._extract_action_field(text, "负责人")
        target = remainder.split("。", 1)[0].strip() if remainder else text
        if "；" in target:
            target = target.split("；", 1)[0].strip()
        kpi = self._extract_action_field(text, "KPI")

        verb_map = {
            "减量": "压缩",
            "暂停": "暂停",
            "加码": "加码",
            "限额验证": "限额验证",
            "口径复核": "复核",
            "复制素材": "复制",
        }
        verb = verb_map.get(action_type.strip(), action_type.strip() or "处理")
        summary = f"{owner or '待定负责人'}：{verb} {target}".strip()
        if kpi:
            summary += f"（目标：{self._shorten_kpi(kpi)}）"
        return summary

    @staticmethod
    def _extract_action_field(text: str, field_name: str) -> str:
        match = re.search(rf"{re.escape(field_name)}：([^；]+)", text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _shorten_kpi(kpi: str) -> str:
        text = str(kpi or "").strip().rstrip("。")
        replacements = [
            ("以上后再考虑补量", "后再补量"),
            ("以上，再决定是否恢复测试", "后再复核"),
            ("以上，再讨论是否放量", "后再复核是否提高验证预算"),
            ("尽快接近", "接近"),
        ]
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    def _select_market_summary_actions(self, digest: WeeklyDigest) -> list[str]:
        actions = [str(action or "").strip() for action in digest.next_actions if str(action or "").strip()]
        if not actions:
            return []
        creative_low = self._is_low_confidence_module(digest.company_confidence_lines, "Facebook素材") and self._is_low_confidence_module(digest.company_confidence_lines, "Google素材")
        if creative_low:
            filtered = [action for action in actions if not action.startswith("复制素材")]
            if filtered:
                return filtered
        return actions

    @classmethod
    def _select_summary_campaign(cls, campaign_items, next_actions=None):
        focus_segments = cls._action_focus_segments(next_actions or [])

        def priority(item) -> int:
            note = str(getattr(item, "scope_note", "") or "")
            segment_scope = cls._normalize_segment_text(str(getattr(item, "segment_scope", "") or ""))
            if segment_scope and segment_scope in focus_segments:
                return 3
            if "正常对比定位" in note:
                return 2
            if "唯一可用定位层" in note:
                return 1
            return 0

        return sorted(
            campaign_items,
            key=lambda item: (-priority(item), -(getattr(item, "spend", 0.0) or 0.0), -(getattr(item, "roi", 0.0) or 0.0)),
        )[0]

    @classmethod
    def _action_focus_segments(cls, next_actions) -> set[str]:
        result: set[str] = set()
        for action in next_actions or []:
            text = str(action or "")
            match = re.search(
                r"：[^。；]*?/\s*([^/。；]+?)\s*/\s*([^/。；]+?)(?:。|；|$)",
                text,
            )
            if not match:
                continue
            segment = f"{match.group(1).strip()} / {match.group(2).strip()}"
            result.add(cls._normalize_segment_text(segment))
        return result

    @staticmethod
    def _summary_campaign_reason(item) -> str:
        note = str(getattr(item, "scope_note", "") or "").strip()
        if note:
            return note
        return "当前在可用 Campaign 中具备更高的定位优先级"

    @staticmethod
    def _is_low_confidence_module(confidence_lines: list[str], module_name: str) -> bool:
        for line in confidence_lines or []:
            text = str(line or "")
            if not text.startswith(f"{module_name}："):
                continue
            return "：低；" in text or text.endswith("：低")
        return False

    @staticmethod
    def _extract_first_number(text: str) -> float | None:
        match = re.search(r"(\d+\.\d+|\d+)", str(text or ""))
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def render_markdown(self, digest: WeeklyDigest) -> str:
        lines = [f"# {digest.title}", ""]

        summary_lines = self._build_market_summary_lines(digest)
        if summary_lines:
            lines.extend(["## 市场负责人摘要", ""])
            lines.extend(f"- {item}" for item in summary_lines)
            lines.append("")

        lines.extend([f"## {SEC_COMPANY}", ""])
        lines.extend(f"- {metric.label} {metric.value}" for metric in digest.company_metrics)
        lines.extend(f"- {item}" for item in digest.company_highlights)
        if digest.company_confidence_lines:
            lines.append("- 数据可信度：")
            lines.extend(f"- {item}" for item in digest.company_confidence_lines)
        if digest.anomaly_lines:
            lines.append("- 风险清单：")
            lines.extend(f"- {item}" for item in digest.anomaly_lines)

        lines.extend(["", f"## {SEC_PROJECT}", ""])
        if digest.project_items:
            for item in digest.project_items:
                lines.append(f"- {item.game}")
                if item.detail_ready:
                    lines.append(
                        f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`，总收入ROI `{item.project_roi:.2f}`，"
                        f"付费净ROI `{self._fmt_optional_ratio(item.paid_roi_net)}`，平均广告ROAS `{item.avg_roas:.2f}`，平均 CPI `{item.avg_cpi:.2f}`，总收入 `{item.total_revenue:.0f}`。"
                    )
                    lines.append(
                        f"- 主投渠道 `{item.top_channel}`，风险组合 `{item.risk_segment}`，最佳单日 `{item.best_day}`，优先素材 `{item.top_creative}`。"
                    )
                else:
                    lines.append(
                        f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`，总收入ROI `{item.project_roi:.2f}`，付费净ROI `{self._fmt_optional_ratio(item.paid_roi_net)}`，总收入 `{item.total_revenue:.0f}`。"
                    )
                lines.append(f"- 实际回收倍率：{item.actual_recovery}")
                lines.append(f"- 预测回收倍率：{item.forecast_recovery or NO_FORECAST}")
                if item.cohort_age_summary:
                    lines.append(f"- 样本成熟度：{item.cohort_age_summary}")
                if item.forecast_confidence:
                    lines.append(f"- 预测可信度：{item.forecast_confidence}")
                if item.pending_validation:
                    lines.append(f"- {item.pending_validation}")
                if item.payback_gate:
                    lines.append(f"- 回本门槛：{item.payback_gate}")
                lines.append(f"- {item.payback_forecast}")
                lines.append(f"- 实际与预测：{item.forecast_analysis}")
                if getattr(item, "profit_split", ""):
                    lines.append(f"- 盈亏拆分：{item.profit_split}")
                lines.extend(f"- {line}" for line in item.segment_diagnostics)
                if item.recovery_change:
                    lines.append(f"- 回收变化：{item.recovery_change}")
                lines.append(f"- 风险判断：{item.risk_judgement or item.judgement}")
                lines.append(f"- 建议动作：{item.suggested_action or item.forecast_recommendation or item.judgement}")
                lines.append(
                    f"- 闭环：问题={item.problem}；原因={item.reason}；行动={item.suggested_action or item.forecast_recommendation or item.judgement}；负责人={item.action_owner}；截止时间={item.action_due_date}；验证指标={item.verification_metric}"
                )
        else:
            lines.append(f"- {NO_DATA}")

        lines.extend(["", "## 3. Campaign 投放分析", ""])
        if digest.campaign_items:
            for item in digest.campaign_items:
                lines.extend(
                    [
                        f"- {item.game} / {item.channel} / {item.campaign}",
                        f"- 国家 `{item.country}`；花费 `{item.spend:.0f}`；收入 `{item.revenue:.0f}`；ROI `{item.roi:.2f}`",
                        f"- 回本门槛：{item.payback_gate}",
                        f"- 定位层说明：{item.scope_note}" if getattr(item, "scope_note", "") else None,
                        f"- 风险判断：{item.risk_judgement}",
                        f"- 建议动作：{item.suggested_action}",
                        f"- 闭环：问题={item.problem}；原因={item.reason}；行动={item.suggested_action}；负责人={item.action_owner}；截止时间={item.action_due_date}；验证指标={item.verification_metric}",
                    ]
                )
        else:
            lines.append("- 当前没有可用 Campaign 数据。")

        lines.extend(["", "## 4. 回收倍率校验", ""])
        if digest.forecast_accuracy_lines:
            lines.extend(f"- {item}" for item in digest.forecast_accuracy_lines)
        else:
            lines.append("- 预测准确度暂无结果。")

        lines.extend(["", "## 预测偏差", ""])
        if digest.forecast_bias_lines:
            lines.extend(f"- {item}" for item in digest.forecast_bias_lines)
        else:
            lines.append("- 预测偏差报告暂未生成。")

        lines.extend(["", f"## {SEC_CREATIVE}", ""])
        if digest.creative_items:
            for item in digest.creative_items:
                lines.extend(
                    [
                        f"- {item.game or '未知项目'} / {item.channel or '未知渠道'} / {item.asset_id}",
                        f"- 类型 `{item.creative_type}`；花费 `{item.spend:.0f}`；安装 `{item.installs:.0f}`；ROAS `{item.roas:.2f}`；CTR `{item.ctr:.3f}`；状态 `{item.status}`",
                        f"- 样本状态：{item.sample_status or '观察样本'}；可信度：{item.confidence_level or '低'}",
                        f"- 风险判断：{item.risk_judgement or '仅观察'}",
                        f"- 建议动作：{item.suggested_action or '继续观察'}",
                        f"- 闭环：问题={item.problem}；原因={item.reason}；行动={item.suggested_action or '继续观察'}；负责人={item.action_owner}；截止时间={item.action_due_date}；验证指标={item.verification_metric}",
                    ]
                )
            lines.extend(f"- {item}" for item in digest.creative_notes)
        else:
            lines.append(f"- {NO_DATA}")

        lines.extend(["", f"## {SEC_ACTION}", ""])
        if digest.next_actions:
            lines.extend(f"- {item}" for item in digest.next_actions)
        else:
            lines.append("- 本周暂无新动作。")
        lines.append("")
        return "\n".join(lines)

    def build_card(self, digest: WeeklyDigest) -> dict[str, Any]:
        elements: list[dict[str, Any]] = []
        summary_lines = self._build_market_summary_lines(digest)
        if summary_lines:
            elements.append(self._section_title("市场负责人摘要"))
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in summary_lines)))
            elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_COMPANY))
        elements.append(self._metric_fields(digest.company_metrics[:4]))
        if digest.company_highlights:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.company_highlights)))
        if digest.company_confidence_lines:
            elements.append(self._markdown_block("**数据可信度**\n" + "\n".join(f"- {item}" for item in digest.company_confidence_lines)))
        if digest.anomaly_lines:
            elements.append(self._markdown_block("**风险清单**\n" + "\n".join(f"- {item}" for item in digest.anomaly_lines)))

        elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_PROJECT))
        if digest.project_items:
            for item in digest.project_items:
                lines = [f"**{item.game}**"]
                if item.detail_ready:
                    lines.extend(
                        [
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`",
                            f"- 总收入ROI `{item.project_roi:.2f}`，付费净ROI `{self._fmt_optional_ratio(item.paid_roi_net)}`，平均广告ROAS `{item.avg_roas:.2f}`，平均 CPI `{item.avg_cpi:.2f}`，总收入 `{item.total_revenue:.0f}`",
                            f"- 主投渠道 `{item.top_channel}`，风险组合 `{item.risk_segment}`，最佳单日 `{item.best_day}`",
                            f"- 优先素材 `{item.top_creative}`",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`",
                            f"- 总收入ROI `{item.project_roi:.2f}`，付费净ROI `{self._fmt_optional_ratio(item.paid_roi_net)}`，总收入 `{item.total_revenue:.0f}`",
                        ]
                    )
                lines.extend(
                    [
                        f"- 实际回收倍率：{item.actual_recovery}",
                        f"- 预测回收倍率：{item.forecast_recovery or NO_FORECAST}",
                        "- 口径提示：该回收倍率为项目总回收口径，包含自然量，不直接作为 Campaign/素材预算动作依据。",
                        f"- 样本成熟度：{item.cohort_age_summary or '暂无'}",
                        f"- 预测可信度：{item.forecast_confidence or '暂无'}",
                        f"- {item.pending_validation}" if item.pending_validation else None,
                        f"- 回本门槛：{item.payback_gate}" if item.payback_gate else None,
                        f"- {item.payback_forecast}",
                        f"- 实际与预测：{item.forecast_analysis}",
                    ]
                )
                lines = [line for line in lines if line]
                if getattr(item, "profit_split", ""):
                    lines.append(f"- 盈亏拆分：{item.profit_split}")
                lines.extend(f"- {line}" for line in item.segment_diagnostics)
                if item.recovery_change:
                    lines.append(f"- 回收变化：{item.recovery_change}")
                lines.append(f"- 风险判断：{item.risk_judgement or item.judgement}")
                lines.append(f"- 建议动作：{item.suggested_action or item.forecast_recommendation or item.judgement}")
                lines.append(f"- 问题={item.problem}")
                lines.append(f"- 原因={item.reason}")
                lines.append(f"- 行动={item.suggested_action or item.forecast_recommendation or item.judgement}")
                lines.append(f"- 负责人={item.action_owner}")
                lines.append(f"- 截止时间={item.action_due_date}")
                lines.append(f"- 验证指标={item.verification_metric}")
                elements.append(self._markdown_block("\n".join(lines)))
        else:
            elements.append(self._markdown_block(f"- {NO_DATA}"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("3. Campaign 投放分析"))
        if digest.campaign_items:
            for item in digest.campaign_items:
                lines = [
                    f"**{item.game} / {item.channel} / {item.campaign}**",
                    f"- 国家 `{item.country}`；花费 `{item.spend:.0f}`；收入 `{item.revenue:.0f}`；ROI `{item.roi:.2f}`",
                    f"- 回本门槛：{item.payback_gate}",
                    f"- 风险判断：{item.risk_judgement}",
                    f"- 建议动作：{item.suggested_action}",
                    f"- 问题={item.problem}",
                    f"- 原因={item.reason}",
                    f"- 行动={item.suggested_action}",
                    f"- 负责人={item.action_owner}",
                    f"- 截止时间={item.action_due_date}",
                    f"- 验证指标={item.verification_metric}",
                ]
                elements.append(self._markdown_block("\n".join(lines)))
        else:
            elements.append(self._markdown_block("- 当前没有可用 Campaign 数据。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("4. 回收倍率校验"))
        if digest.forecast_accuracy_lines:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.forecast_accuracy_lines)))
        else:
            elements.append(self._markdown_block("- 预测准确度暂无结果。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("预测偏差"))
        if digest.forecast_bias_lines:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.forecast_bias_lines)))
        else:
            elements.append(self._markdown_block("- 预测偏差报告暂未生成。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_CREATIVE))
        if digest.creative_items:
            for item in digest.creative_items:
                lines = [
                    f"**{item.game or '未知项目'} / {item.channel or '未知渠道'} / {item.asset_id}**",
                    f"- 类型 `{item.creative_type}`；花费 `{item.spend:.0f}`；安装 `{item.installs:.0f}`；ROAS `{item.roas:.2f}`；CTR `{item.ctr:.3f}`；状态 `{item.status}`",
                    f"- 样本状态：{item.sample_status or '观察样本'}；可信度：{item.confidence_level or '低'}",
                    f"- 风险判断：{item.risk_judgement or '仅观察'}",
                    f"- 建议动作：{item.suggested_action or '继续观察'}",
                    f"- 问题={item.problem}",
                    f"- 原因={item.reason}",
                    f"- 行动={item.suggested_action or '继续观察'}",
                    f"- 负责人={item.action_owner}",
                    f"- 截止时间={item.action_due_date}",
                    f"- 验证指标={item.verification_metric}",
                ]
                elements.append(self._markdown_block("\n".join(lines)))
            if digest.creative_notes:
                elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.creative_notes)))
        else:
            elements.append(self._markdown_block(f"- {NO_DATA}"))
        media_buyer_lines = self._build_media_buyer_top_lines(digest.report_date)
        if media_buyer_lines:
            elements.append(self._markdown_block("**AI Media Buyer Top 3**\n" + "\n".join(f"- {line}" for line in media_buyer_lines)))

        elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_ACTION))
        if digest.next_actions:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.next_actions)))
        else:
            elements.append(self._markdown_block("- 本周暂无新动作。"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "turquoise",
                "title": {"tag": "plain_text", "content": digest.title},
            },
            "elements": elements,
        }

    def build_simple_card(self, digest: WeeklyDigest) -> dict[str, Any]:
        elements: list[dict[str, Any]] = []
        summary_lines = self._build_market_summary_lines(digest)
        if summary_lines:
            elements.append(self._section_title("市场负责人摘要"))
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in summary_lines)))
            elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_COMPANY))
        elements.append(self._metric_fields(digest.company_metrics[:4]))
        highlights = digest.company_highlights[:4]
        if highlights:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in highlights)))
        if digest.company_confidence_lines:
            elements.append(self._markdown_block("**数据可信度**\n" + "\n".join(f"- {item}" for item in digest.company_confidence_lines[:3])))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("2. 重点项目判断"))
        if digest.project_items:
            for item in digest.project_items:
                elements.append(self._markdown_block("\n".join(self._build_simple_project_lines(item))))
        else:
            elements.append(self._markdown_block(f"- {NO_DATA}"))

        simple_creative_lines = self._build_simple_creative_lines(digest)
        if simple_creative_lines:
            elements.append({"tag": "hr"})
            elements.append(self._section_title("3. 素材方向"))
            elements.append(self._markdown_block("\n".join(f"- {line}" for line in simple_creative_lines)))
            media_buyer_lines = self._build_media_buyer_top_lines(digest.report_date)
            if media_buyer_lines:
                elements.append(self._markdown_block("**AI Media Buyer Top 3**\n" + "\n".join(f"- {line}" for line in media_buyer_lines)))

        if digest.campaign_items:
            elements.append({"tag": "hr"})
            top_campaign = self._select_summary_campaign(digest.campaign_items, digest.next_actions)
            elements.append(
                self._markdown_block(
                    "**4. 重点 Campaign**\n"
                    + f"- {top_campaign.game} / {top_campaign.channel} / {top_campaign.campaign}\n"
                    + f"- ROI `{top_campaign.roi:.2f}` | 回本门槛：{top_campaign.payback_gate} | 风险：{top_campaign.risk_judgement} | 动作：{top_campaign.suggested_action}"
                    + (f"\n- 定位层说明：{top_campaign.scope_note}" if getattr(top_campaign, "scope_note", "") else "")
                )
            )

        elements.append({"tag": "hr"})
        elements.append(self._section_title(SEC_ACTION))
        if digest.next_actions:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.next_actions[:3])))
        else:
            elements.append(self._markdown_block("- 本周暂无新动作。"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green",
                "title": {"tag": "plain_text", "content": f"{SIMPLE_TEAM_TITLE} | {digest.report_date.isoformat()}"},
            },
            "elements": elements,
        }

    def render_recovery_markdown(self, digest: WeeklyDigest) -> str:
        lines = [f"# 回收倍率增长周报 | {digest.report_date.isoformat()}", ""]
        lines.extend(
            [
                "## 项目总回收（含自然量）/ 预测 / 回本预估",
                "",
                f"- 周窗口：{(digest.report_date - timedelta(days=6)).isoformat()} 至 {digest.report_date.isoformat()}（上周四到本周三）",
                "- 口径说明：本卡使用项目 cohort 总回收口径，包含自然量与自然变现，不是纯付费回收。",
                "- 使用边界：可用于判断项目整体回收趋势和回本节奏，不直接作为 Campaign、素材、渠道的加量或停投依据。",
            ]
        )
        for item in digest.project_items:
            lines.append(f"- {item.game}")
            lines.extend(self._build_recovery_project_lines(item))
        lines.append("")
        return "\n".join(lines)

    def build_recovery_card(self, digest: WeeklyDigest) -> dict[str, Any]:
        lines = [
            f"- 周窗口：{(digest.report_date - timedelta(days=6)).isoformat()} 至 {digest.report_date.isoformat()}（上周四到本周三）",
            "- 口径说明：本卡使用项目 cohort 总回收口径，包含自然量与自然变现，不是纯付费回收。",
            "- 使用边界：可用于判断项目整体回收趋势和回本节奏，不直接作为 Campaign、素材、渠道的加量或停投依据。",
        ]
        for item in digest.project_items:
            lines.append(f"- {item.game}")
            lines.extend(self._build_recovery_project_lines(item))
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": f"回收倍率增长周报 | {digest.report_date.isoformat()}"},
            },
            "elements": [self._markdown_block("**项目总回收（含自然量）/ 预测 / 回本预估**\n" + "\n".join(lines))],
        }

    def _build_media_buyer_top_lines(self, report_date: date) -> list[str]:
        suffix = report_date.strftime("%Y%m%d")
        active = self._settings.active_output_dir
        lines: list[str] = []

        cluster_payload = _read_json(active / f"creative_clusters_{suffix}.json")
        for item in (cluster_payload.get("clusters") or [])[:1]:
            if item.get("confidence") != "low":
                lines.append(
                    f"素材模式：{item.get('cluster_name')}，ROI {float(item.get('avg_roi') or 0):.2f}，建议：{item.get('variant_direction')}"
                )

        fatigue_payload = _read_json(active / f"creative_fatigue_{suffix}.json")
        fatigue_items = [item for item in (fatigue_payload.get("items") or []) if item.get("status") == "fatigue"]
        if fatigue_items:
            top = fatigue_items[0]
            lines.append(f"疲劳复核：{top.get('project')} / {top.get('creative_id')}，原因：{'；'.join(top.get('reason') or [])}")

        plan_payload = _read_json(active / f"ai_media_buyer_plan_{suffix}.json")
        for item in (plan_payload.get("actions") or [])[: max(0, 3 - len(lines))]:
            lines.append(f"动作建议：{item.get('action_type')} / {item.get('target')}，需审批={item.get('approval_required')}")
        return lines[:3]

    @staticmethod
    def _build_recovery_project_lines(item) -> list[str]:
        lines = [
            f"- 花费 `{item.spend:.0f}`",
            f"- 实际回收倍率：{item.actual_recovery or NO_ACTUAL}",
            f"- 预测回收倍率：{item.forecast_recovery or NO_FORECAST}",
        ]
        if item.cohort_age_summary:
            lines.append(f"- 样本成熟度：{item.cohort_age_summary}")
        if item.forecast_confidence:
            lines.append(f"- 预测可信度：{item.forecast_confidence}")
        if item.pending_validation:
            lines.append(f"- {item.pending_validation}")
        lines.append(f"- {item.payback_forecast or '回本预估：暂无可用结果'}")
        lines.append(f"- 实际与预测：{item.forecast_analysis or '暂无可比结果'}")
        if item.recovery_change:
            lines.append(f"- 回收变化：{item.recovery_change}")
        suggestion = item.forecast_recommendation or item.judgement
        lines.append(f"- 建议：{suggestion}")
        lines.append("- 说明：这里看的是项目总回收趋势，包含自然量；预算动作仍以纯付费回收、商店+渠道门槛和多日累计样本为准。")
        return lines

    def _build_simple_project_lines(self, item) -> list[str]:
        actual_d7 = self._extract_curve_value(item.actual_recovery, 7) or self._extract_curve_value(item.actual_recovery, 3)
        forecast_d180 = self._extract_curve_value(item.forecast_recovery, 180) or self._extract_curve_value(item.forecast_recovery, 90)
        payback_text = (item.payback_forecast or "回本预估：暂无可用结果").replace("回本预估：", "")
        lines = [f"**{item.game}**"]
        lines.append(
            f"- 花费 `{item.spend:.0f}` | 总收入ROI `{item.project_roi:.2f}` | 付费净ROI `{self._fmt_optional_ratio(item.paid_roi_net)}`"
        )
        snapshot_parts: list[str] = []
        if actual_d7 is not None:
            snapshot_parts.append(f"实际D7 `{actual_d7:.2f}`")
        if forecast_d180 is not None:
            snapshot_parts.append(f"预测D180 `{forecast_d180:.2f}`")
        snapshot_parts.append(payback_text)
        lines.append("- " + " | ".join(snapshot_parts))
        if item.payback_gate:
            lines.append(f"- 回本门槛：{item.payback_gate}")
        if getattr(item, "profit_split", ""):
            lines.append(f"- 盈亏拆分：{item.profit_split}")
        lines.append(f"- 风险：{item.risk_judgement or item.judgement}")
        lines.append(f"- 动作：{item.suggested_action or item.forecast_recommendation or item.judgement}")
        lines.append(f"- 负责人：{item.action_owner} | 截止：{item.action_due_date}")
        return lines

    @staticmethod
    def _build_simple_creative_lines(digest: WeeklyDigest) -> list[str]:
        lines: list[str] = []
        if digest.creative_notes:
            confidence_line = next((line for line in digest.creative_notes if str(line).startswith("素材可信度提示：")), "")
            if confidence_line:
                lines.append(confidence_line)
        if digest.creative_items:
            lines.append("素材段当前仅作代理层观察，不作为本周预算增减的主要依据。")
        if digest.creative_notes:
            first_note = digest.creative_notes[0]
            if first_note not in lines:
                lines.append(first_note)
        return lines[:2]

    def _build_clean_company_highlights(self, report_date: date, ads_rows, revenue_rows, revenue_breakdown_rows, confidence_map) -> list[str]:
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)
        current_total_ads, current_detail_ads = self._split_window_ads(ads_rows, window_start, report_date)
        previous_total_ads, previous_detail_ads = self._split_window_ads(ads_rows, previous_start, previous_end)
        current_revenue = [row for row in revenue_rows if window_start <= row.date <= report_date]
        previous_revenue = [row for row in revenue_rows if previous_start <= row.date <= previous_end]
        signal_rows = self._trusted_detail_rows(current_detail_ads) or current_detail_ads
        weakest_segment = self._weakest_segment(signal_rows) if signal_rows else "n/a"
        current_spend = sum(row.total_cost for row in current_revenue)
        current_revenue_total = sum(row.total_revenue for row in current_revenue)
        current_roi = current_revenue_total / current_spend if current_spend else 0.0
        top_growth_game = self._top_growth_game(
            current_revenue,
            previous_revenue,
            current_total_ads or current_detail_ads,
            previous_total_ads or previous_detail_ads,
        )
        trusted_detail_projects = {self._project_key(row.game) for row in signal_rows if row.game}
        active_revenue_projects = {
            self._project_key(row.game)
            for row in current_revenue
            if row.total_cost > 0 or self._project_key(row.game) in trusted_detail_projects
        }

        highlights: list[str] = []
        if trusted_detail_projects and active_revenue_projects and trusted_detail_projects != active_revenue_projects:
            revenue_list = "、".join(sorted(active_revenue_projects))
            detail_list = "、".join(sorted(trusted_detail_projects))
            highlights.append(f"项目段已按 Adjust 项目口径覆盖 {revenue_list}；其中仅 {detail_list} 已接入可信飞书明细。")
        elif active_revenue_projects:
            revenue_list = "、".join(sorted(active_revenue_projects))
            highlights.append(f"项目段已按 Adjust 项目口径覆盖 {revenue_list}。")

        highlights.append(f"主要增长来自 {top_growth_game}。")
        highlights.append(f"当前最需要控量验证的低效段是 {weakest_segment}。")
        current_breakdown_rows = [
            row
            for row in (revenue_breakdown_rows or [])
            if window_start <= row.date <= report_date
        ]
        structure_level, structure_reason = confidence_map.get("公司盈利结构", ("低", "缺少盈利结构可信度说明"))
        structure_line = self._build_company_profit_structure_line(current_breakdown_rows)
        if structure_line and structure_level != "低":
            highlights.append(structure_line)
        else:
            highlights.append(f"公司盈利结构当前可信度不足：{structure_reason}。")
        if current_roi >= 1:
            highlights.append(f"下周重点关注：先控量验证 {weakest_segment}，素材段仅保留观察候选。")
        else:
            highlights.append(f"下周重点关注：先稳回收，再控量验证 {weakest_segment}。")
        return highlights

    def _build_company_profit_structure_line(self, revenue_breakdown_rows) -> str:
        if not revenue_breakdown_rows:
            return ""
        segment_buckets = self._aggregate_breakdown_profit_structure(revenue_breakdown_rows)
        best_store = None
        if segment_buckets["store"]:
            best_store = max(
                segment_buckets["store"].items(),
                key=lambda pair: ((pair[1]["revenue"] / pair[1]["cost"]) if pair[1]["cost"] else -1.0, pair[1]["cost"]),
            )
        weak_channel = None
        if segment_buckets["channel"]:
            weak_channel = min(
                segment_buckets["channel"].items(),
                key=lambda pair: ((pair[1]["revenue"] / pair[1]["cost"]) if pair[1]["cost"] else 999.0, -pair[1]["cost"]),
            )
        parts: list[str] = []
        if best_store:
            roi = best_store[1]["revenue"] / best_store[1]["cost"] if best_store[1]["cost"] else 0.0
            if roi >= 1.0:
                parts.append(f"赚钱主要来自 {best_store[0]}（总收入ROI {roi:.2f}）")
            else:
                parts.append(f"当前相对较优的商店是 {best_store[0]}（总收入ROI {roi:.2f}）")
        if weak_channel:
            roi = weak_channel[1]["revenue"] / weak_channel[1]["cost"] if weak_channel[1]["cost"] else 0.0
            anomaly_note = self._channel_anomaly_note(revenue_breakdown_rows, weak_channel[0])
            if anomaly_note:
                parts.append(f"当前需优先复核的渠道是 {weak_channel[0]}（总收入ROI {roi:.2f}，{anomaly_note}）")
            else:
                parts.append(f"当前相对偏弱渠道是 {weak_channel[0]}（总收入ROI {roi:.2f}）")
        return "；".join(parts) + "。" if parts else ""

    @classmethod
    def _channel_anomaly_note(cls, rows, channel: str) -> str:
        zero_share, _ = cls._zero_revenue_share_after_grouping(rows, channel)
        if zero_share >= CHANNEL_REVENUE_ANOMALY_THRESHOLD:
            return "存在较高占比有花费无收入明细，先复核归因再下强结论"
        return ""

    @classmethod
    def _zero_revenue_share_after_grouping(cls, rows, channel: str) -> tuple[float, float]:
        buckets: dict[tuple[str, str, str, str, str, str], dict[str, float]] = {}
        for row in rows or []:
            row_channel = cls._normalize_partner(str(getattr(row, "partner", "") or ""))
            if row_channel != channel:
                continue
            key = (
                str(getattr(row, "game", "") or ""),
                cls._normalize_store(str(getattr(row, "store", "") or "")),
                str(getattr(row, "country", "") or "Global"),
                str(getattr(row, "campaign", "") or getattr(row, "campaign_id", "") or ""),
                str(getattr(row, "adgroup", "") or getattr(row, "adgroup_id", "") or ""),
                str(getattr(row, "creative_name", "") or getattr(row, "creative_id", "") or ""),
            )
            bucket = buckets.setdefault(key, {"cost": 0.0, "revenue": 0.0})
            bucket["cost"] += float(getattr(row, "cost", 0.0) or 0.0)
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
        total_cost = sum(float(item["cost"] or 0.0) for item in buckets.values())
        zero_cost = sum(
            float(item["cost"] or 0.0)
            for item in buckets.values()
            if float(item["cost"] or 0.0) > 0 and float(item["revenue"] or 0.0) <= 0
        )
        return ((zero_cost / total_cost) if total_cost else 0.0, zero_cost)

    def _aggregate_breakdown_profit_structure(self, revenue_breakdown_rows) -> dict[str, dict[str, dict[str, float]]]:
        store_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        channel_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        for row in revenue_breakdown_rows or []:
            spend = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_partner(str(getattr(row, "partner", "") or ""))
            store_buckets[store]["revenue"] += revenue
            channel_buckets[channel]["revenue"] += revenue
            if spend > 0:
                store_buckets[store]["cost"] += spend
                channel_buckets[channel]["cost"] += spend
        return {"store": dict(store_buckets), "channel": dict(channel_buckets)}

    def _rebuild_project_profit_split(self, revenue_breakdown_rows, report_date: date, project_name: str) -> str:
        if not revenue_breakdown_rows or not project_name:
            return ""
        window_start = report_date - timedelta(days=6)
        project_key = self._project_key(project_name)
        by_store: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        paid_store_count: set[str] = set()
        paid_channel_count: set[str] = set()
        for row in revenue_breakdown_rows:
            if not (window_start <= row.date <= report_date):
                continue
            if self._project_key(getattr(row, "game", "") or "") != project_key:
                continue
            spend = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_partner(str(getattr(row, "partner", "") or ""))
            by_store[store]["revenue"] += revenue
            by_channel[channel]["revenue"] += revenue
            if spend > 0:
                by_store[store]["cost"] += spend
                by_channel[channel]["cost"] += spend
                paid_store_count.add(store)
                paid_channel_count.add(channel)
        if not any(metrics["cost"] > 0 for metrics in by_store.values()):
            return ""
        if len(paid_store_count) < 2 and len(paid_channel_count) < 2:
            return "项目盈利结构当前可信度有限：当前只有单商店单渠道结构，暂不输出商店/渠道强结论"
        if len(paid_store_count) < 2:
            return "项目盈利结构当前可信度有限：当前只有单商店多渠道结构，无法判断商店差异"
        if len(paid_channel_count) < 2:
            return "项目盈利结构当前可信度有限：当前只有多商店单渠道结构，无法判断渠道差异"

        def _classify(buckets: dict[str, dict[str, float]]) -> tuple[list[str], list[str]]:
            good: list[str] = []
            weak: list[str] = []
            for name, metrics in buckets.items():
                if metrics["cost"] <= 0:
                    continue
                roi = metrics["revenue"] / metrics["cost"] if metrics["cost"] else 0.0
                (good if roi >= 1 else weak).append(f"{name} {roi:.2f}")
            return good, weak

        good_stores, weak_stores = _classify(by_store)
        good_channels, weak_channels = _classify(by_channel)
        return (
            f"商店总收入ROI≥1={', '.join(good_stores) or '无'}；商店总收入ROI<1={', '.join(weak_stores) or '无'}；"
            f"渠道总收入ROI≥1={', '.join(good_channels) or '无'}；渠道总收入ROI<1={', '.join(weak_channels) or '无'}"
        )

    @staticmethod
    def _project_structure_confidence_from_rows(rows) -> tuple[str, str]:
        paid_rows = [row for row in (rows or []) if float(getattr(row, "cost", 0.0) or 0.0) > 0]
        if not paid_rows:
            return ("低", "缺少项目级 breakdown 结构明细")
        stores = {
            FinalWeeklyDigestBuilder._normalize_store(str(getattr(row, "store", "") or ""))
            for row in paid_rows
        }
        channels = {
            FinalWeeklyDigestBuilder._normalize_partner(str(getattr(row, "partner", "") or ""))
            for row in paid_rows
        }
        if not stores or not channels:
            return ("低", "缺少项目级商店或渠道字段")
        if len(stores) < 2 and len(channels) < 2:
            return ("中", "当前只有单商店单渠道结构")
        if len(stores) < 2:
            return ("中", "当前只有单商店多渠道结构，无法判断商店差异")
        if len(channels) < 2:
            return ("中", "当前只有多商店单渠道结构，无法判断渠道差异")
        return ("高", "项目级商店和渠道结构完整")

    def _apply_project_structure_gate(self, profit_split: str, diagnostics: list[str]) -> str:
        joined = " ".join(str(line or "") for line in (diagnostics or []))
        if "当前只有一个主投组合" in joined:
            return "项目盈利结构当前可信度有限：当前只有单商店单渠道结构，且只有一个主投组合，暂不输出商店/渠道强结论"
        return profit_split

    def _build_project_segment_diagnostics(self, revenue_breakdown_rows, report_date: date) -> dict[str, list[str]]:
        if not revenue_breakdown_rows:
            return {}
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)
        current_rows = [row for row in revenue_breakdown_rows if window_start <= row.date <= report_date]
        previous_rows = [row for row in revenue_breakdown_rows if previous_start <= row.date <= previous_end]
        result: dict[str, list[str]] = {}
        project_keys = {self._project_key(row.game) for row in current_rows if row.game}
        for project_key in project_keys:
            project_current = [row for row in current_rows if self._project_key(row.game) == project_key]
            if not project_current:
                continue
            project_previous = [row for row in previous_rows if self._project_key(row.game) == project_key]
            current_segments = self._aggregate_breakdown_segments(project_current)
            previous_segments = self._aggregate_breakdown_segments(project_previous)
            ranked = sorted(current_segments.items(), key=lambda pair: pair[1]["spend"], reverse=True)
            if not ranked:
                continue
            actionable_ranked = self._actionable_segment_ranked(ranked)
            segment_ranked = actionable_ranked or ranked
            strongest = max(segment_ranked, key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else -1.0, pair[1]["spend"]))
            weakest = min(segment_ranked, key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else 999.0, -pair[1]["spend"]))
            focus = self._focus_segment_by_loss_pressure(segment_ranked)
            strongest_roi = strongest[1]["revenue"] / strongest[1]["spend"] if strongest[1]["spend"] else 0.0
            weakest_roi = weakest[1]["revenue"] / weakest[1]["spend"] if weakest[1]["spend"] else 0.0
            focus_roi = focus[1]["revenue"] / focus[1]["spend"] if focus[1]["spend"] else 0.0
            top_spend_segment, top_spend_metrics = ranked[0]
            top_spend_roi = top_spend_metrics["revenue"] / top_spend_metrics["spend"] if top_spend_metrics["spend"] else 0.0
            top_spend_prev = previous_segments.get(top_spend_segment)
            top_spend_prev_roi = (
                top_spend_prev["revenue"] / top_spend_prev["spend"]
                if top_spend_prev and top_spend_prev["spend"]
                else None
            )
            top_spend_wow = (
                f"{top_spend_roi - top_spend_prev_roi:+.2f}"
                if top_spend_prev_roi is not None
                else "暂无"
            )
            lines = [
                f"当前主要消耗集中在 `{top_spend_segment}`：花费 `{top_spend_metrics['spend']:.0f}`，总收入ROI `{top_spend_roi:.2f}`，环比 `{top_spend_wow}`。"
            ]
            campaign_best = self._top_breakdown_entity(project_current, "campaign")
            campaign_weak = self._bottom_breakdown_entity(project_current, "campaign")
            creative_best = self._top_breakdown_entity(project_current, "creative")
            creative_weak = self._bottom_breakdown_entity(project_current, "creative")
            trusted_creative_best = self._top_trusted_breakdown_entity(project_current, "creative")
            creative_has_sample = bool(
                creative_best
                and float(creative_best.get("spend") or 0.0) >= 50.0
            )
            creative_ready = trusted_creative_best is not None
            if not creative_ready or not creative_has_sample:
                creative_best = None
                creative_weak = None
            self._latest_project_entity_signals[project_key] = {
                "project_name": project_current[0].game or project_key,
                "top_spend_segment": top_spend_segment,
                "focus_segment": focus[0],
                "strongest_segment": strongest[0],
                "weakest_segment": weakest[0],
                "best_campaign": campaign_best,
                "weak_campaign": campaign_weak,
                "best_creative": creative_best,
                "weak_creative": creative_weak,
                "best_trusted_creative": trusted_creative_best,
            }
            if len(ranked) == 1 or strongest[0] == weakest[0]:
                lines.append(f"当前只有一个主投组合 `{top_spend_segment}`，先看这个组合能否把总收入ROI继续拉高。")
            elif not actionable_ranked:
                lines.append("当前各组合样本未达到强结论门槛，只输出观察，不直接指定控量对象。")
            else:
                lines.append(f"当前优先处理组合是 `{focus[0]}`，当前总收入ROI `{focus_roi:.2f}`，按亏损压力优先排查成本、国家和素材结构。")
                lines.append(f"当前相对更稳的组合是 `{strongest[0]}`，总收入ROI `{strongest_roi:.2f}`，先保留观察。")
            if campaign_best:
                if float(campaign_best.get("spend") or 0.0) >= 200:
                    lines.append(
                        f"当前高ROI Campaign 候选是 `{campaign_best['name']}`（ID `{campaign_best['id']}`），花费 `{campaign_best['spend']:.0f}`，总收入ROI `{campaign_best['roi']:.2f}`，需继续看样本稳定性。"
                    )
                else:
                    lines.append(
                        f"当前有小样本高ROI Campaign `{campaign_best['name']}`（ID `{campaign_best['id']}`），花费仅 `{campaign_best['spend']:.0f}`，只作观察不作放量依据。"
                    )
            if campaign_weak and (not campaign_best or campaign_weak["key"] != campaign_best["key"]):
                if float(campaign_weak.get("spend") or 0.0) >= 200:
                    lines.append(
                        f"当前需要优先排查的 Campaign 是 `{campaign_weak['name']}`（ID `{campaign_weak['id']}`），花费 `{campaign_weak['spend']:.0f}`，总收入ROI `{campaign_weak['roi']:.2f}`。"
                    )
                else:
                    lines.append(
                        f"当前低ROI Campaign `{campaign_weak['name']}`（ID `{campaign_weak['id']}`）样本较小，花费 `{campaign_weak['spend']:.0f}`，先观察不下强结论。"
                    )
            if not creative_ready:
                lines.append("当前素材明细可信度偏低，素材层只保留观察提示，暂不输出最佳/最弱素材结论。")
            elif not creative_has_sample:
                lines.append("当前素材样本量还不够，素材层先只观察，不输出最佳/最弱素材结论。")
            elif creative_best:
                lines.append(
                    f"当前表现最好的素材ID是 `{creative_best['id']}`，名称 `{creative_best['name']}`，花费 `{creative_best['spend']:.0f}`，总收入ROI `{creative_best['roi']:.2f}`。"
                )
            if creative_weak and (not creative_best or creative_weak["key"] != creative_best["key"]):
                lines.append(
                    f"当前最弱的素材ID是 `{creative_weak['id']}`，名称 `{creative_weak['name']}`，花费 `{creative_weak['spend']:.0f}`，总收入ROI `{creative_weak['roi']:.2f}`。"
                )
            result[project_key] = lines
        return result

    @staticmethod
    def _aggregate_breakdown_segments(rows) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"spend": 0.0, "revenue": 0.0})
        for row in rows:
            segment = f"{FinalWeeklyDigestBuilder._normalize_store(row.store)} / {FinalWeeklyDigestBuilder._normalize_partner(row.partner)}"
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            if cost > 0:
                buckets[segment]["spend"] += cost
            buckets[segment]["revenue"] += row.total_revenue_gross
        return dict(buckets)

    @classmethod
    def _top_breakdown_entity(cls, rows, entity: str) -> dict[str, float | str] | None:
        ranked = cls._aggregate_breakdown_entities(rows, entity)
        if not ranked:
            return None
        key, metrics = max(
            ranked.items(),
            key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else -1.0, pair[1]["spend"]),
        )
        return {
            "key": key,
            "name": metrics["name"],
            "id": metrics["id"],
            "spend": metrics["spend"],
            "roi": (metrics["revenue"] / metrics["spend"]) if metrics["spend"] else 0.0,
        }

    @classmethod
    def _bottom_breakdown_entity(cls, rows, entity: str) -> dict[str, float | str] | None:
        ranked = cls._aggregate_breakdown_entities(rows, entity)
        if not ranked:
            return None
        key, metrics = min(
            ranked.items(),
            key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else 999.0, -pair[1]["spend"]),
        )
        return {
            "key": key,
            "name": metrics["name"],
            "id": metrics["id"],
            "spend": metrics["spend"],
            "roi": (metrics["revenue"] / metrics["spend"]) if metrics["spend"] else 0.0,
        }

    def _top_trusted_breakdown_entity(self, rows, entity: str) -> dict[str, float | str] | None:
        ranked = self._aggregate_breakdown_entities(rows, entity)
        if not ranked:
            return None
        candidates: list[tuple[str, dict[str, float | str]]] = []
        for key, metrics in ranked.items():
            spend = float(metrics["spend"])
            roi = (float(metrics["revenue"]) / spend) if spend else 0.0
            signal = {
                "key": key,
                "name": metrics["name"],
                "id": metrics["id"],
                "spend": spend,
                "roi": roi,
            }
            if self._is_trusted_creative_signal(signal):
                candidates.append((key, signal))
        if not candidates:
            return None
        _, best = max(
            candidates,
            key=lambda pair: (
                float(pair[1]["spend"]) * float(pair[1]["roi"]),
                float(pair[1]["spend"]),
                float(pair[1]["roi"]),
            ),
        )
        return best

    @staticmethod
    def _aggregate_breakdown_entities(rows, entity: str) -> dict[str, dict[str, float | str]]:
        buckets: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {"name": "", "id": "", "spend": 0.0, "revenue": 0.0}
        )
        for row in rows:
            if entity == "campaign":
                name = (getattr(row, "campaign", "") or "").strip()
                entity_id = (getattr(row, "campaign_id", "") or "").strip()
                key = name or entity_id
            elif entity == "creative":
                name = (getattr(row, "creative_name", "") or "").strip()
                entity_id = (getattr(row, "creative_id", "") or "").strip()
                key = entity_id or name
            else:
                continue
            if not key:
                continue
            buckets[key]["name"] = name or entity_id or "-"
            buckets[key]["id"] = entity_id or "-"
            buckets[key]["spend"] += row.cost
            buckets[key]["revenue"] += row.total_revenue_gross
        return dict(buckets)

    @staticmethod
    def _normalize_store(value: str) -> str:
        normalized = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(normalized, value or "未知商店")

    @staticmethod
    def _normalize_partner(value: str) -> str:
        normalized = (value or "").strip().lower()
        if "google" in normalized:
            return "Google"
        if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized:
            return "Facebook"
        return value or "未知渠道"

    @staticmethod
    def _build_clean_creative_notes(creative_rows) -> list[str]:
        if not creative_rows:
            return []
        hook_counts: dict[str, int] = defaultdict(int)
        low_quality_count = 0
        paid_test_count = 0
        for row in creative_rows:
            hook_key = row.hook_type or row.creative_type or "Unknown"
            hook_counts[hook_key] += 1
            if row.spend > 0 and row.roas == 0:
                low_quality_count += 1
            if row.roas > 0 or "Roas>30%" in row.status or "paid" in row.status.lower():
                paid_test_count += 1
        dominant_hook = max(hook_counts, key=hook_counts.get)
        return [
            f"本周最值得继续放大的素材方向是 `{dominant_hook}`。",
            f"本周共监测到 {len(creative_rows)} 条素材，其中已有正向付费验证的素材 {paid_test_count} 条。",
            f"当前有 {low_quality_count} 条素材已有花费但尚未跑出回收，建议先复核归因并降低优先级，不直接作为停测结论。",
        ]

    def _build_creative_context_map(self, creative_rows) -> dict[str, dict[str, float | str]]:
        context: dict[str, dict[str, float | str]] = {}
        for row in creative_rows or []:
            asset_id = str(row.asset_id or "").strip()
            if not asset_id:
                continue
            revenue = float(getattr(row, "revenue_value", 0.0) or 0.0)
            if revenue <= 0 and float(row.spend or 0.0) > 0 and float(row.roas or 0.0) > 0:
                revenue = float(row.spend) * float(row.roas)
            spend = float(row.spend or 0.0)
            installs = float(getattr(row, "installs", 0.0) or 0.0)
            candidate = {
                "game": str(row.game or "").strip(),
                "channel": self._normalize_partner(str(row.channel or "").strip()),
                "spend": spend,
                "installs": installs,
                "revenue": revenue,
            }
            current = context.get(asset_id)
            if current is None:
                context[asset_id] = candidate
            else:
                current["spend"] = float(current.get("spend") or 0.0) + spend
                current["installs"] = float(current.get("installs") or 0.0) + installs
                current["revenue"] = float(current.get("revenue") or 0.0) + revenue
                if spend > 0 and not str(current.get("game") or "").strip():
                    current["game"] = candidate["game"]
                if spend > 0 and not str(current.get("channel") or "").strip():
                    current["channel"] = candidate["channel"]
        return context

    def _build_market_confidence_map(self, report_date: date, revenue_rows, breakdown_rows, creative_rows) -> dict[str, tuple[str, str]]:
        current_start = report_date - timedelta(days=6)
        scoped_revenue_rows = [row for row in revenue_rows or [] if current_start <= row.date <= report_date]
        scoped_breakdown_rows = [row for row in breakdown_rows or [] if current_start <= row.date <= report_date]
        current_revenue = sum(float(getattr(row, "total_revenue", 0.0) or 0.0) for row in scoped_revenue_rows)
        current_cost = sum(float(getattr(row, "total_cost", 0.0) or 0.0) for row in scoped_revenue_rows)
        breakdown_revenue = sum(float(getattr(row, "total_revenue_gross", 0.0) or 0.0) for row in scoped_breakdown_rows)
        breakdown_cost = sum(float(getattr(row, "cost", 0.0) or 0.0) for row in scoped_breakdown_rows)
        result: dict[str, tuple[str, str]] = {}
        result["花费"] = self._confidence_from_gap(current_cost, breakdown_cost, "缺少 breakdown 花费校验")
        result["收入"] = self._confidence_from_gap(current_revenue, breakdown_revenue, "缺少 breakdown 收入校验")
        if result["花费"][0] == "低" or result["收入"][0] == "低":
            result["ROI"] = ("低", "收入或花费可信度不足，ROI 只可观察")
        elif result["花费"][0] == "中" or result["收入"][0] == "中":
            result["ROI"] = ("中", "ROI 可用于方向判断，但不宜下强结论")
        else:
            result["ROI"] = ("高", "ROI 口径一致，可用于判断")
        result["公司盈利结构"] = self._company_structure_confidence(
            scoped_breakdown_rows,
            result["花费"],
            result["收入"],
        )
        fb_rows = [row for row in creative_rows or [] if self._normalize_partner(str(getattr(row, "channel", "") or "")) == "Facebook"]
        google_rows = [row for row in creative_rows or [] if self._normalize_partner(str(getattr(row, "channel", "") or "")) == "Google"]
        result["Facebook素材"] = self._creative_confidence_label(
            "Facebook",
            fb_rows,
            bool(getattr(self._settings, "using_meta_creative_source", False)),
        )
        result["Google素材"] = self._creative_confidence_label(
            "Google",
            google_rows,
            bool(getattr(self._settings, "using_google_creative_source", False)),
        )
        return result

    @staticmethod
    def _actionable_segment_ranked(ranked: list[tuple[str, dict[str, float]]]) -> list[tuple[str, dict[str, float]]]:
        total_spend = sum(float(metrics.get("spend") or 0.0) for _, metrics in ranked)
        min_spend = max(MIN_DIMENSION_DECISION_SPEND, total_spend * MIN_DIMENSION_DECISION_SHARE)
        return [(key, metrics) for key, metrics in ranked if float(metrics.get("spend") or 0.0) >= min_spend]

    @staticmethod
    def _focus_segment_by_loss_pressure(
        ranked: list[tuple[str, dict[str, float]]],
    ) -> tuple[str, dict[str, float]]:
        loss_candidates: list[tuple[str, dict[str, float], float]] = []
        for key, metrics in ranked:
            spend = float(metrics.get("spend") or 0.0)
            revenue = float(metrics.get("revenue") or 0.0)
            roi = revenue / spend if spend else 0.0
            loss = spend * max(0.0, 1.0 - roi)
            if loss > 0:
                loss_candidates.append((key, metrics, loss))
        if not loss_candidates:
            return min(ranked, key=lambda pair: ((pair[1]["revenue"] / pair[1]["spend"]) if pair[1]["spend"] else 999.0, -pair[1]["spend"]))
        key, metrics, _ = max(loss_candidates, key=lambda item: (item[2], item[1]["spend"]))
        return key, metrics

    def _company_structure_confidence(
        self,
        breakdown_rows,
        spend_confidence: tuple[str, str],
        revenue_confidence: tuple[str, str],
    ) -> tuple[str, str]:
        if not breakdown_rows:
            return ("低", "缺少 Adjust breakdown 结构明细")
        if spend_confidence[0] == "低" or revenue_confidence[0] == "低":
            return ("低", "花费或收入校验未通过，不能直接判断商店和渠道结构")
        stores = {
            self._normalize_store(str(getattr(row, "store", "") or ""))
            for row in breakdown_rows
            if float(getattr(row, "cost", 0.0) or 0.0) > 0
        }
        channels = {
            self._normalize_partner(str(getattr(row, "partner", "") or ""))
            for row in breakdown_rows
            if float(getattr(row, "cost", 0.0) or 0.0) > 0
        }
        if not stores or not channels:
            return ("低", "缺少可用的商店或渠道结构字段")
        if len(stores) < 2 and len(channels) < 2:
            return ("中", "当前只有单一商店和单一渠道结构，只能做有限判断")
        if len(stores) < 2:
            return ("中", "当前只有单一商店结构，最赚钱商店判断有限")
        if len(channels) < 2:
            return ("中", "当前只有单一渠道结构，最弱渠道判断有限")
        return ("高", "商店和渠道结构完整，可输出结构结论")

    @staticmethod
    def _confidence_from_gap(left: float, right: float, empty_reason: str) -> tuple[str, str]:
        if left <= 0 or right <= 0:
            return "低", empty_reason
        gap = abs(left - right) / max(left, right)
        if gap <= 0.05:
            return "高", "跨源偏差在5%以内"
        if gap <= 0.15:
            return "中", f"跨源偏差约{gap:.1%}"
        return "低", f"跨源偏差约{gap:.1%}"

    @staticmethod
    def _creative_confidence_label(channel: str, rows, source_ready: bool) -> tuple[str, str]:
        if not rows:
            return "低", f"{channel} 当前没有素材明细"
        identified = sum(1 for row in rows if str(getattr(row, "asset_id", "") or "").strip())
        adjust_rows = [
            row for row in rows
            if str(getattr(row, "creative_type", "") or "").lower().startswith("adjust")
        ]
        if adjust_rows:
            proxy_rows = [
                row for row in adjust_rows
                if "proxy" in str(getattr(row, "creative_type", "") or "").lower()
            ]
            effective_rows = [
                row for row in adjust_rows
                if float(getattr(row, "spend", 0.0) or 0.0) >= 50
                or float(getattr(row, "installs", 0.0) or 0.0) >= 20
            ]
            if channel == "Google" and proxy_rows:
                return "中", "Adjust 已接入 Google source/adgroup/campaign 代理素材层，可用于方向判断，但不等同于原生 creative id"
            if effective_rows and identified == len(rows):
                return "高", "Adjust creative 明细已接入，且存在达到样本门槛的素材"
            return "中", "Adjust creative 明细已接入，但部分素材仍处于观察样本"
        if not source_ready:
            return "低", f"{channel} 当前未接 live 凭证"
        if identified == len(rows):
            return "高", "素材标识完整"
        return "中", "部分素材缺少完整标识"

    def _build_market_confidence_lines(self, confidence_map: dict[str, tuple[str, str]]) -> list[str]:
        return [f"{module}：{level}；{reason}" for module, (level, reason) in confidence_map.items()]

    def _build_market_anomaly_lines(self, breakdown_rows, creative_rows, ads_rows, confidence_map: dict[str, tuple[str, str]]) -> list[str]:
        lines: list[str] = []
        for module in ("花费", "收入", "ROI"):
            level, reason = confidence_map.get(module, ("中", ""))
            if level == "低":
                lines.append(f"[高] {module}可信度不足：{reason}")
        for row in creative_rows or []:
            if float(getattr(row, "spend", 0.0) or 0.0) > 0 and float(getattr(row, "ctr", 0.0) or 0.0) <= 0:
                lines.append(f"[中] CTR为0：{row.game}/{self._normalize_partner(row.channel)}/{row.asset_id or row.creative_name}")
                break
        for item in self._group_breakdown_for_revenue_anomaly(breakdown_rows or []):
            if item["cost"] > 0 and item["revenue"] <= 0:
                lines.append(f"[高] 收入缺失：{item['scope']}")
                break
        for row in ads_rows or []:
            if float(getattr(row, "spend", 0.0) or 0.0) > 0 and float(getattr(row, "roas", 0.0) or 0.0) <= 0 and int(getattr(row, "clicks", 0) or 0) > 0:
                lines.append(f"[中] ROI异常：{row.game}/{self._normalize_partner(row.channel)}/{row.country}")
                break
        return lines[:8]

    @classmethod
    def _group_breakdown_for_revenue_anomaly(cls, rows) -> list[dict[str, Any]]:
        buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in rows or []:
            channel = cls._normalize_partner(str(getattr(row, "partner", "") or ""))
            key = (
                str(getattr(row, "game", "") or ""),
                channel,
                str(getattr(row, "country", "") or "Global"),
                str(getattr(row, "campaign", "") or getattr(row, "campaign_id", "") or ""),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "scope": "/".join(part for part in key if part),
                    "cost": 0.0,
                    "revenue": 0.0,
                },
            )
            bucket["cost"] += float(getattr(row, "cost", 0.0) or 0.0)
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
        return list(buckets.values())

    def _build_campaign_digest_items(self, breakdown_rows, report_date: date, confidence_map: dict[str, tuple[str, str]]) -> list[CampaignDigestItem]:
        current_start = report_date - timedelta(days=6)
        rows = [row for row in breakdown_rows or [] if current_start <= row.date <= report_date]
        payback_targets_map = self._load_payback_targets_map(report_date)
        buckets: dict[tuple[str, str, str, str], dict[str, float | str]] = defaultdict(lambda: {"spend": 0.0, "revenue": 0.0, "country": ""})
        project_segments: dict[str, set[str]] = defaultdict(set)
        project_spend: dict[str, float] = defaultdict(float)
        for row in rows:
            campaign = str(getattr(row, "campaign", "") or getattr(row, "campaign_id", "") or "").strip()
            if not campaign:
                continue
            segment_scope = f"{self._normalize_store(str(getattr(row, 'store', '') or ''))} / {self._normalize_partner(str(getattr(row, 'partner', '') or ''))}"
            key = (str(row.game or "").strip(), self._normalize_partner(str(row.partner or "")), segment_scope, campaign)
            project_segments[str(row.game or "").strip()].add(segment_scope)
            cost = float(row.cost or 0.0)
            buckets[key]["spend"] += cost
            buckets[key]["revenue"] += float(row.total_revenue_gross or 0.0)
            project_spend[str(row.game or "").strip()] += cost
            if not buckets[key]["country"]:
                buckets[key]["country"] = str(getattr(row, "country", "") or "All")
        roi_level = confidence_map.get("ROI", ("中", ""))[0]
        items: list[CampaignDigestItem] = []
        for (game, channel, segment_scope, campaign), metrics in sorted(buckets.items(), key=lambda item: item[1]["spend"], reverse=True)[:6]:
            roi = metrics["revenue"] / metrics["spend"] if metrics["spend"] else 0.0
            payback_target = payback_targets_map.get(self._project_key(game))
            store = segment_scope.split("/", 1)[0].strip() if "/" in segment_scope else ""
            segment_target = self._segment_payback_target(payback_target, store, channel)
            payback_gate = self._format_payback_gate(payback_target, segment_target)
            campaign_spend = float(metrics["spend"] or 0.0)
            min_campaign_spend = max(MIN_CAMPAIGN_DECISION_SPEND, project_spend.get(game, 0.0) * MIN_CAMPAIGN_DECISION_SHARE)
            sample_ready = campaign_spend >= min_campaign_spend
            if roi_level == "低":
                risk = "低可信度，仅观察"
                action = "先校对归因，不直接动预算"
            elif not sample_ready:
                risk = f"Campaign样本未达强结论门槛，花费 {campaign_spend:.0f} < {min_campaign_spend:.0f}"
                action = "继续观察，不作为预算增减依据"
            elif segment_target and self._segment_current_below_floor(segment_target):
                if roi >= 1.0:
                    risk = "Campaign短期ROI可保留，但商店+渠道D7低于历史回本保底线"
                    action = "保留观察，不新增预算，等待该组合D7修复"
                else:
                    risk = "商店+渠道D7低于历史可回本保底线，该Campaign暂不承接新增预算"
                    action = "限额验证并排查成本、国家和素材结构"
            elif payback_target and (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None) and (payback_target.current_recovery.get("D7") or 0.0) < payback_target.recovery_targets["D7"].floor:
                if roi >= 1.0:
                    risk = "Campaign短期ROI可保留，但项目D7低于历史回本保底线"
                    action = "保留观察，不新增预算，等待项目D7修复"
                else:
                    risk = "项目D7低于历史可回本保底线，该 Campaign 暂不承接新增预算"
                    action = "限额验证并排查成本、国家和素材结构"
            elif roi < 1.0:
                risk = "短期总收入ROI低于1，需结合项目历史保底线和成熟回收验证"
                action = "控量验证，不直接按短期ROI一刀切停投"
            else:
                risk = "可保留"
                action = "保留并继续观察"
            owner = self._clean_action_owner("减量" if roi < 1.0 else "加码", f"{game} {campaign}")
            items.append(
                CampaignDigestItem(
                    game=game,
                    channel=channel,
                    campaign=campaign,
                    country=str(metrics["country"] or "All"),
                    spend=metrics["spend"],
                    revenue=metrics["revenue"],
                    roi=roi,
                    payback_gate=payback_gate,
                    confidence_level=roi_level,
                    risk_judgement=risk,
                    suggested_action=action,
                    scope_note=(
                        "当前项目只有单一主投组合，Campaign层是唯一可用定位层"
                        if len(project_segments.get(game, set())) <= 1
                        else "当前项目存在多个主投组合，Campaign层可用于正常对比定位"
                    )
                    + (f"；Campaign判断门槛：花费≥{min_campaign_spend:.0f}" if min_campaign_spend else ""),
                    problem=f"{game}/{channel}/{campaign} ROI={roi:.2f}",
                    reason=self._campaign_reason(payback_target, segment_target),
                    action_owner=owner,
                    action_due_date=(report_date + timedelta(days=self._settings.default_task_due_days)).isoformat(),
                    verification_metric=self._campaign_verification_metric(payback_target, segment_target),
                    segment_scope=segment_scope,
                )
            )
        return items

    def _populate_project_decision_fields(self, item, confidence_map: dict[str, tuple[str, str]], report_date: date, payback_target: ProjectTargets | None) -> None:
        roi_value = item.paid_roi_net if item.paid_roi_net is not None else item.project_roi
        confidence_level = confidence_map.get("ROI", ("中", ""))[0]
        action_target = self._project_action_target(item)
        if confidence_level == "低":
            if not getattr(item, "detail_ready", False):
                risk = "项目总收入口径可看，但项目级明细未接入"
                action = "先补项目级投放明细来源，再判断具体该压哪一段预算"
            elif not getattr(item, "actual_recovery", "") or getattr(item, "actual_recovery", "") == NO_ACTUAL:
                risk = "项目总收入口径可看，但回收曲线未接入"
                action = "先补项目级回收来源，再判断是否放量或缩量"
            else:
                risk = "跨源口径仍需复核，当前仅保留观察"
                action = "先校对收入与花费口径，再决定是否调整预算"
        elif payback_target and (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None) and (payback_target.current_recovery.get("D7") or 0.0) < payback_target.recovery_targets["D7"].floor:
            risk = f"回收未达历史保底线，D7 {(payback_target.current_recovery.get('D7') or 0.0):.2f} 低于历史保底线 {payback_target.recovery_targets['D7'].floor:.2f}"
            action = f"限额验证并修复低效组合，先把 D7 回收拉回历史保底线 {payback_target.recovery_targets['D7'].floor:.2f}，再复核是否提高验证预算"
        elif payback_target and (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None) and (payback_target.current_recovery.get("D7") or 0.0) >= payback_target.recovery_targets["D7"].floor:
            risk = "D7 高于历史保底线，但预测可信度仍低，继续观察后续成熟回收"
            action = "维持观察，不新增预算，等 D30/更成熟回收确认后再讨论验证预算"
        elif roi_value < 1.0:
            risk = "短期付费净ROI未过线，仅作为预警，不能单独作为停投或加量依据"
            action = f"控量验证{action_target}并排查付费回收"
        elif roi_value < 1.3:
            risk = "短期付费净ROI偏弱，需先看历史保底线和成熟回收"
            action = f"先控量观察{action_target}，整体预算以稳为主"
        else:
            risk = "当前可保留，但不代表可直接放量"
            action = "维持预算，先看是否还能稳定放量"
        item.confidence_level = confidence_level
        item.risk_judgement = risk
        item.suggested_action = action
        problem_metric_label = "付费净ROI" if item.paid_roi_net is not None else "总收入ROI"
        item.problem = f"{item.game} 当前{problem_metric_label}={roi_value:.2f}"
        item.reason = payback_target.findings[0] if payback_target and payback_target.findings else f"{item.game} 当前判断基于总收入ROI/付费净ROI与回收表现，需要先处理 {action_target} 这一段。"
        item.action_owner = self._clean_action_owner("减量" if roi_value < 1.0 else "加码", item.game)
        item.action_due_date = (report_date + timedelta(days=self._settings.default_task_due_days)).isoformat()
        if payback_target and payback_target.recovery_targets.get("D7") and payback_target.recovery_targets.get("D30"):
            d7_floor = payback_target.recovery_targets["D7"].floor
            d30_floor = payback_target.recovery_targets["D30"].floor
            d7_current = payback_target.current_recovery.get("D7")
            if d7_current is not None and d7_current >= d7_floor:
                item.verification_metric = f"维持现有预算观察；D7 持续不低于历史保底线 {d7_floor:.2f}，且 D30 接近历史保底线 {d30_floor:.2f} 后，再讨论是否小幅提高验证预算"
            else:
                item.verification_metric = f"D7 回到历史保底线 {d7_floor:.2f}，且 D30 接近历史保底线 {d30_floor:.2f}"
        else:
            item.verification_metric = "先看3日ROAS和后续成熟回收是否改善，再考虑是否调整预算" if roi_value < 1.0 else "放量期 ROI 不低于当前基线"
        segment_target = self._project_focus_segment_target(item, payback_target)
        item.payback_gate = self._format_payback_gate(payback_target, segment_target)

    def _project_action_target(self, item) -> str:
        candidates = [
            str(getattr(item, "risk_segment", "") or "").strip(),
            str(getattr(item, "top_channel", "") or "").strip(),
        ]
        for candidate in candidates:
            if candidate and "待补可信项目明细" not in candidate:
                return candidate
        signal = self._latest_project_entity_signals.get(self._project_key(getattr(item, "game", "")), {})
        for key in ("focus_segment", "top_spend_segment", "weakest_segment", "strongest_segment"):
            value = str(signal.get(key) or "").strip()
            if value:
                return value
        return "低效段"

    def _populate_creative_decision_fields(self, creative_items, confidence_map: dict[str, tuple[str, str]], report_date: date) -> None:
        for item in creative_items or []:
            context = self._latest_creative_context.get(item.asset_id, {})
            item.game = str(context.get("game") or item.game or "")
            item.channel = str(context.get("channel") or item.channel or "")
            item.spend = float(context.get("spend") or item.spend or 0.0)
            item.installs = float(context.get("installs") or item.installs or 0.0)
            item.revenue = float(context.get("revenue") or item.revenue or 0.0)
            item.sample_status = "有效样本" if item.spend >= 50 or item.installs >= 20 else "观察样本"
            confidence_level = confidence_map.get(f"{item.channel}素材", ("低", ""))[0] if item.channel else "低"
            item.confidence_level = confidence_level
            if confidence_level == "低":
                item.risk_judgement = "低可信度，仅观察"
                item.suggested_action = "先补齐归因或源字段，再决定是否复制"
            elif item.sample_status == "观察样本":
                item.risk_judgement = "样本不足，不能直接认定为优质素材"
                item.suggested_action = "继续小额验证，先把样本跑够"
            elif item.roas >= 1.0:
                item.risk_judgement = "已形成正向素材候选信号"
                item.suggested_action = "保留观察，待素材归因复核后再决定是否复制"
            else:
                item.risk_judgement = "当前未证明有效"
                item.suggested_action = "归因复核后再决定是否降权"
            item.problem = f"{item.game or '未知项目'}/{item.channel or '未知渠道'}/{item.asset_id} 当前素材代理ROI={item.roas:.2f}"
            item.reason = "素材结论必须建立在样本门槛和素材渠道可信度之上，当前代理素材归因不作为强停测依据。"
            action_type = "复制素材" if item.roas >= 1.0 else "素材观察"
            creative_target = f"{item.game or '未知项目'} / {item.channel or '未知渠道'} / 素材ID `{item.asset_id}`"
            item.action_owner = self._clean_action_owner(action_type, creative_target)
            item.action_due_date = (report_date + timedelta(days=self._settings.default_task_due_days)).isoformat()
            item.verification_metric = "素材花费≥50或安装≥20后，先复核归因，再判断是否进入复制或降权名单"

    def _load_payback_targets_map(self, report_date: date) -> dict[str, ProjectTargets]:
        try:
            targets, _ = PaybackTargetsBuilder(self._settings).build_targets_data(report_date)
        except Exception:
            return {}
        return {item.project: item for item in targets}

    @staticmethod
    def _segment_payback_target(payback_target: ProjectTargets | None, store: str, channel: str):
        if not payback_target:
            return None
        key = f"{FinalWeeklyDigestBuilder._normalize_store(store)} / {FinalWeeklyDigestBuilder._normalize_partner(channel)}"
        return payback_target.segment_targets.get(key)

    @staticmethod
    def _segment_sample_ready(segment_target) -> bool:
        return bool(segment_target and getattr(segment_target, "profitable_samples", 0) >= 3)

    @staticmethod
    def _segment_current_below_floor(segment_target) -> bool:
        if not FinalWeeklyDigestBuilder._segment_sample_ready(segment_target):
            return False
        d7_target = segment_target.recovery_targets.get("D7") if segment_target else None
        d7_current = (segment_target.current_recovery or {}).get("D7") if segment_target else None
        return bool(d7_target and d7_target.floor is not None and d7_current is not None and d7_current < d7_target.floor)

    def _project_focus_segment_target(self, item, payback_target: ProjectTargets | None):
        if not payback_target:
            return None
        candidates = [
            str(getattr(item, "risk_segment", "") or "").strip(),
            str(getattr(item, "top_channel", "") or "").strip(),
        ]
        signal = self._latest_project_entity_signals.get(self._project_key(getattr(item, "game", "")), {})
        for key in ("focus_segment", "top_spend_segment", "weakest_segment", "strongest_segment"):
            value = str(signal.get(key) or "").strip()
            if value:
                candidates.append(value)
        for candidate in candidates:
            if "/" not in candidate:
                continue
            store, channel = [part.strip() for part in candidate.split("/", 1)]
            segment_target = self._segment_payback_target(payback_target, store, channel)
            if segment_target:
                return segment_target
        return None

    def _campaign_reason(self, payback_target: ProjectTargets | None, segment_target=None) -> str:
        if segment_target and self._segment_current_below_floor(segment_target):
            d7_current = (segment_target.current_recovery or {}).get("D7")
            d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
            if d7_current is not None and d7_floor is not None:
                return f"{segment_target.store} / {segment_target.channel} 当前D7 {d7_current:.2f}，低于历史保底线 {d7_floor:.2f}，先按组合修复。"
        if payback_target and payback_target.findings:
            return payback_target.findings[0]
        return "该Campaign已形成主要消耗，需要先判断是否在回本线之上。"

    def _campaign_verification_metric(self, payback_target: ProjectTargets | None, segment_target=None) -> str:
        if self._segment_sample_ready(segment_target) and segment_target.recovery_targets.get("D7") and segment_target.recovery_targets.get("D30"):
            d7_floor = segment_target.recovery_targets["D7"].floor
            d30_floor = segment_target.recovery_targets["D30"].floor
            if d7_floor is not None and d30_floor is not None:
                return f"{segment_target.store} / {segment_target.channel} 的D7回到历史保底线 {d7_floor:.2f}，且D30接近历史保底线 {d30_floor:.2f}"
        if payback_target and payback_target.recovery_targets.get("D7") and payback_target.recovery_targets.get("D30"):
            return f"D7 回到历史保底线 {payback_target.recovery_targets['D7'].floor:.2f}，且 D30 接近历史保底线 {payback_target.recovery_targets['D30'].floor:.2f}"
        return "先看3日ROAS和后续成熟回收是否改善，再决定是否提高验证预算"

    @staticmethod
    def _format_payback_gate(payback_target: ProjectTargets | None, segment_target=None) -> str:
        if not payback_target:
            return "暂无项目回本门槛"
        parts: list[str] = []
        if segment_target:
            d7_current = segment_target.current_recovery.get("D7")
            d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
            d30_floor = segment_target.recovery_targets.get("D30").floor if segment_target.recovery_targets.get("D30") else None
            sample_ready = FinalWeeklyDigestBuilder._segment_sample_ready(segment_target)
            if sample_ready and d7_current is not None and d7_floor is not None:
                parts.append(f"{segment_target.store} / {segment_target.channel} D7 `{d7_current:.2f}` / 历史保底线 `{d7_floor:.2f}`")
            elif not sample_ready:
                parts.append(f"{segment_target.store} / {segment_target.channel} 样本不足，先回看项目级参考线")
            if sample_ready and d30_floor is not None:
                parts.append(f"{segment_target.store} / {segment_target.channel} D30历史保底线 `{d30_floor:.2f}`")
        d7_current = payback_target.current_recovery.get("D7")
        d7_floor = payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None
        d30_floor = payback_target.recovery_targets.get("D30").floor if payback_target.recovery_targets.get("D30") else None
        if not parts and d7_current is not None and d7_floor is not None:
            parts.append(f"项目级参考D7 `{d7_current:.2f}` / 历史保底线 `{d7_floor:.2f}`")
        if not parts and d30_floor is not None:
            parts.append(f"项目级D30历史保底线 `{d30_floor:.2f}`")
        if payback_target.cpi_guardrail.ceiling is not None:
            parts.append(f"CPI上限 `{payback_target.cpi_guardrail.ceiling:.2f}`")
        if payback_target.retention_guardrail.floor is not None:
            parts.append(f"D1留存底线 `{payback_target.retention_guardrail.floor:.2f}`")
        if parts:
            parts.append("D7按延迟缓冲取数：cohort至少满9天后才做强判断")
        return " | ".join(parts) if parts else "暂无可用门槛"

    def _build_clean_next_actions(self, draft_actions, project_items, management_action_payload=None) -> list[str]:
        if management_action_payload and management_action_payload.get("items"):
            return ManagementActionListBuilder.to_action_lines(management_action_payload)
        fallback_lines = self._build_conservative_project_actions(project_items)
        if fallback_lines:
            return fallback_lines
        lines: list[str] = []
        for action in draft_actions:
            action_type = self._clean_action_type(action.action_type)
            target = self._clean_action_title(action.title, action_type)
            target, _ = self._resolve_refined_action_target(action_type, target, project_items)
            owner = self._clean_action_owner(action_type, target)
            lines.append(
                f"{action_type}：{target}。负责人：{owner}；截止时间：{action.due_date.isoformat()}；KPI：{action.acceptance_metric}"
            )
        return lines

    def _build_conservative_project_actions(self, project_items) -> list[str]:
        lines: list[str] = []
        for item in project_items or []:
            game = str(getattr(item, "game", "") or "").strip()
            risk_segment = str(getattr(item, "risk_segment", "") or "").strip()
            risk_text = str(getattr(item, "risk_judgement", "") or getattr(item, "judgement", "") or "")
            if not game:
                continue
            if "低可信度" in risk_text:
                continue
            if risk_segment and any(flag in risk_text for flag in ("回收偏弱", "未达回本门槛", "未达历史保底线", "亏损")):
                owner = self._clean_action_owner("减量", game)
                lines.append(f"减量：{game} / {risk_segment}。负责人：{owner}；截止时间：{item.action_due_date}；KPI：先看3日ROAS与项目级回收是否改善，再决定是否调整预算")
            elif risk_segment and any(flag in risk_text for flag in ("观察", "继续观察")):
                action_type = "限额验证" if self._is_paid_delivery_scope(risk_segment) else "口径复核"
                owner = self._clean_action_owner(action_type, f"{game} / {risk_segment}")
                kpi = "保持限额验证预算，先看3日ROAS和项目级回收是否继续改善" if action_type == "限额验证" else "先完成口径复核，再决定是否做预算动作"
                lines.append(f"{action_type}：{game} / {risk_segment}。负责人：{owner}；截止时间：{item.action_due_date}；KPI：{kpi}")
            if len(lines) >= 3:
                break
        if not lines:
            lines.append("处理：先完成本周收入、花费、回收口径复核。负责人：林凯；截止时间：2026-06-17；KPI：关键项目口径复核通过后，再决定是否调整预算")
        return lines

    def _build_action_refinement_notes(self, draft_actions, project_items, management_action_payload=None) -> list[str]:
        if management_action_payload and management_action_payload.get("items"):
            return ["本周执行动作已优先切换为管理动作台账同源结果，草稿动作仅作为回退来源。"]
        notes: list[str] = []
        for action in draft_actions:
            action_type = self._clean_action_type(action.action_type)
            target = self._clean_action_title(action.title, action_type)
            _, note = self._resolve_refined_action_target(action_type, target, project_items)
            if note and note not in notes:
                notes.append(note)
        return notes

    @staticmethod
    def _clean_action_type(value: str) -> str:
        mapping = {
            "??": "??",
            "??": "??",
            "??": "??",
            "????": "????",
            "????": "??",
            "????": "??",
            "????": "??",
            "?????????": "????",
        }
        normalized = (value or "").replace("?", "").replace(":", "").strip()
        return mapping.get(normalized, value)

    def _clean_action_title(self, title: str, action_type: str) -> str:
        cleaned = title or ""
        replacements = {
            "????": "??",
            "????": "??",
            "????": "??",
            "?????????": "????",
        }
        for raw, normalized in replacements.items():
            cleaned = cleaned.replace(raw, normalized)
        generic_creative_targets = {
            "本周优胜素材",
            "暂无明确优胜素材",
            "暂无明确方向素材",
            "本周优胜素材 暂无明确方向方向素材",
            "本周优胜素材 暂无明确方向素材",
        }
        for prefix in (f"{action_type}?", f"{action_type}:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        cleaned = cleaned.strip()
        if action_type == "复制素材":
            for generic in generic_creative_targets:
                if cleaned == generic or generic in cleaned:
                    return "人工确认素材方向"
        return cleaned


    def _resolve_refined_action_target(self, action_type: str, target: str, project_items) -> tuple[str, str | None]:
        matched_project = self._match_action_project(target, project_items)
        if not matched_project:
            if action_type != "复制素材":
                return target, None
            best_global = self._best_global_creative_signal(allow_multi_project_fallback=False)
            if best_global:
                project_name = str(best_global["project_name"])
                creative = best_global["creative"]
                return (
                    self._format_creative_target(project_name, creative),
                    f"复制素材动作已回退到全局可信素材：{project_name} / 素材ID `{creative.get('id')}`。",
                )
            trusted_projects = self._trusted_creative_project_candidates()
            if len(trusted_projects) > 1:
                project_text = "、".join(trusted_projects)
                return target, f"复制素材动作保留人工标签：当前同时有多个项目存在可信素材候选（{project_text}），不自动做全局指派。"
            return target, "复制素材动作保留人工标签：当前没有达到门槛的可信素材候选，不自动替换为素材ID。"
        signal = self._latest_project_entity_signals.get(self._project_key(matched_project.game), {})
        if action_type in {"减量", "暂停"}:
            weak_campaign = signal.get("weak_campaign") if isinstance(signal, dict) else None
            if weak_campaign:
                return self._format_campaign_target(matched_project.game, weak_campaign), None
        if action_type == "加码":
            best_campaign = signal.get("best_campaign") if isinstance(signal, dict) else None
            if best_campaign:
                return self._format_campaign_target(matched_project.game, best_campaign), None
        if action_type == "复制素材":
            if self._target_mentions_project(target, matched_project.game):
                best_creative = signal.get("best_trusted_creative") if isinstance(signal, dict) else None
                if self._is_trusted_creative_signal(best_creative):
                    return (
                        self._format_creative_target(matched_project.game, best_creative),
                        f"复制素材动作已绑定到项目内可信素材：{matched_project.game} / 素材ID `{best_creative.get('id')}`。",
                    )
                fallback_creative = signal.get("best_creative") if isinstance(signal, dict) else None
                rejection_reason = self._creative_signal_rejection_reason(fallback_creative)
                return target, f"复制素材动作保留人工标签：{matched_project.game} 的最佳素材候选未过门槛，原因：{rejection_reason}。"
            best_global = self._best_global_creative_signal(allow_multi_project_fallback=False)
            if best_global:
                project_name = str(best_global["project_name"])
                creative = best_global["creative"]
                return (
                    self._format_creative_target(project_name, creative),
                    f"复制素材动作已回退到全局可信素材：{project_name} / 素材ID `{creative.get('id')}`。",
                )
            return target, "复制素材动作保留人工标签：草案没有明确项目，且当前没有可用的全局可信素材候选。"
        return target, None

    def _match_action_project(self, target: str, project_items):
        normalized_target = self._normalize_segment_text(target)
        for item in project_items or []:
            if self._target_mentions_project(target, item.game):
                return item
        segment_matches = []
        for item in project_items or []:
            if not item.game or not item.risk_segment:
                continue
            risk_segment = self._normalize_segment_text(item.risk_segment)
            if risk_segment and risk_segment in normalized_target:
                segment_matches.append(item)
        if len(segment_matches) == 1:
            return segment_matches[0]
        return None

    @staticmethod
    def _target_mentions_project(target: str, project_name: str) -> bool:
        if not project_name:
            return False
        project_key = FinalWeeklyDigestBuilder._project_key(project_name)
        lowered = target.lower()
        return project_name.lower() in lowered or (project_key and project_key.lower() in lowered)

    @staticmethod
    def _normalize_segment_text(value: str) -> str:
        cleaned = (value or "").replace(" ", "").replace("／", "/")
        cleaned = cleaned.replace("Meta", "Facebook").replace("meta", "facebook")
        cleaned = cleaned.replace("Facebook", "facebook")
        return cleaned.lower()

    @staticmethod
    def _format_campaign_target(project_name: str, campaign_signal: dict[str, float | str]) -> str:
        campaign_name = str(campaign_signal.get("name") or "-")
        campaign_id = str(campaign_signal.get("id") or "-")
        return f"{project_name} / Campaign `{campaign_name}`（ID `{campaign_id}`）"

    @staticmethod
    def _format_creative_target(project_name: str, creative_signal: dict[str, float | str]) -> str:
        creative_id = str(creative_signal.get("id") or "-")
        creative_name = str(creative_signal.get("name") or "-")
        return f"{project_name} / 素材ID `{creative_id}`（名称 `{creative_name}`）"

    def _creative_action_thresholds(self) -> tuple[float, float]:
        return (
            float(getattr(self._settings, "creative_action_min_spend", 50.0)),
            float(getattr(self._settings, "creative_action_min_roi", 1.0)),
        )

    def _is_trusted_creative_signal(self, creative_signal: dict[str, float | str] | None) -> bool:
        if not creative_signal:
            return False
        min_spend, min_roi = self._creative_action_thresholds()
        spend = float(creative_signal.get("spend") or 0.0)
        roi = float(creative_signal.get("roi") or 0.0)
        creative_id = str(creative_signal.get("id") or "").strip().lower()
        creative_name = str(creative_signal.get("name") or "").strip().lower()
        if spend < min_spend or roi < min_roi:
            return False
        if creative_id in INVALID_CREATIVE_SIGNAL_VALUES:
            return False
        if creative_name in INVALID_CREATIVE_SIGNAL_VALUES:
            return False
        return True

    def _creative_signal_rejection_reason(self, creative_signal: dict[str, float | str] | None) -> str:
        if not creative_signal:
            return "没有拿到素材级候选"
        min_spend, min_roi = self._creative_action_thresholds()
        spend = float(creative_signal.get("spend") or 0.0)
        roi = float(creative_signal.get("roi") or 0.0)
        creative_id = str(creative_signal.get("id") or "").strip().lower()
        creative_name = str(creative_signal.get("name") or "").strip().lower()
        reasons: list[str] = []
        if spend < min_spend:
            reasons.append(f"花费 {spend:.0f} 低于门槛 {min_spend:.0f}")
        if roi < min_roi:
            reasons.append(f"总收入ROI {roi:.2f} 低于门槛 {min_roi:.2f}")
        if creative_id in INVALID_CREATIVE_SIGNAL_VALUES:
            reasons.append("素材ID是占位值")
        if creative_name in INVALID_CREATIVE_SIGNAL_VALUES:
            reasons.append("素材名称是占位值")
        return "；".join(reasons) if reasons else "未通过可信度校验"

    def _trusted_creative_project_candidates(self) -> list[str]:
        projects: list[str] = []
        for signal in getattr(self, "_latest_project_entity_signals", {}).values():
            if not isinstance(signal, dict):
                continue
            creative = signal.get("best_trusted_creative") or signal.get("best_creative")
            if not self._is_trusted_creative_signal(creative):
                continue
            project_name = str(signal.get("project_name") or "").strip()
            if project_name and project_name not in projects:
                projects.append(project_name)
        return projects

    def _best_global_creative_signal(self, allow_multi_project_fallback: bool = True) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for signal in getattr(self, "_latest_project_entity_signals", {}).values():
            if not isinstance(signal, dict):
                continue
            creative = signal.get("best_trusted_creative") or signal.get("best_creative")
            if not self._is_trusted_creative_signal(creative):
                continue
            candidates.append(
                {
                    "project_name": signal.get("project_name") or "",
                    "creative": creative,
                }
            )
        if not candidates:
            return None
        if not allow_multi_project_fallback:
            project_names = sorted({str(item["project_name"]) for item in candidates if str(item["project_name"]).strip()})
            if len(project_names) > 1:
                return None
        return max(
            candidates,
            key=lambda item: (
                float(item["creative"].get("spend") or 0.0) * float(item["creative"].get("roi") or 0.0),
                float(item["creative"].get("spend") or 0.0),
            ),
        )

    @staticmethod
    def _clean_action_owner(action_type: str, target: str) -> str:
        if action_type == "\u590d\u5236\u7d20\u6750":
            return "\u725f\u8015"
        if action_type in {"\u51cf\u91cf", "\u52a0\u7801", "限额验证"}:
            return "\u6797\u51ef"
        if action_type == "\u6682\u505c" and ("Campaign" in target or "\u7d20\u6750ID" in target or "/" in target):
            return "\u6797\u51ef"
        if FinalWeeklyDigestBuilder._is_paid_delivery_scope(target):
            return "\u6797\u51ef"
        if action_type == "口径复核":
            return "\u59dc\u4f1a\u4f1f"
        if "P0" in target:
            return "\u59dc\u4f1a\u4f1f"
        return "\u6797\u51ef"

    @staticmethod
    def _is_paid_delivery_scope(text: str) -> bool:
        normalized = str(text or "")
        return "/" in normalized and any(
            keyword in normalized
            for keyword in ("Facebook", "Google", "iOS", "Android", "Amazon", "Campaign", "素材ID")
        )

    def _load_adjust_project_recovery_map(self, report_date: date) -> dict[str, RecoveryAnalysis]:
        self._latest_recovery_map = {}
        self._latest_global_bias_lines = []
        self._latest_bias_correction_factor = 1.0
        self._latest_global_bias_summary = {}
        self._multiplier_cache = {}
        if not self._adjust_client:
            return {}

        current_start = report_date - timedelta(days=6)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        history_start = previous_start - timedelta(days=210)
        try:
            actual_raw_rows = self._adjust_client.fetch_recovery_cohort_rows(
                start_date=current_start.isoformat(),
                end_date=report_date.isoformat(),
                dimensions="app,app_token",
            )
            raw_rows = self._adjust_client.fetch_recovery_cohort_rows(
                start_date=history_start.isoformat(),
                end_date=report_date.isoformat(),
                dimensions="app,app_token,day",
            )
            segmented_raw_rows = self._adjust_client.fetch_recovery_cohort_rows(
                start_date=history_start.isoformat(),
                end_date=report_date.isoformat(),
                dimensions="app,app_token,store_type,network,day",
            )
        except Exception:
            return {}

        actual_curve_by_game = self._build_adjust_actual_curve_by_game(actual_raw_rows)
        app_rows_by_game = self._build_adjust_rows_by_game(raw_rows)
        segmented_rows_by_game = self._build_adjust_rows_by_game(segmented_raw_rows)

        app_bias_lines, app_bias_correction_factor, app_bias_summary = self._build_global_bias_report(app_rows_by_game, date.today())
        segmented_bias_lines, segmented_bias_correction_factor, segmented_bias_summary = self._build_global_bias_report(segmented_rows_by_game, date.today())

        app_mape = app_bias_summary.get("weighted_mape")
        segmented_mape = segmented_bias_summary.get("weighted_mape")
        use_segmented_model = bool(
            segmented_mape is not None
            and app_mape is not None
            and segmented_mape + 0.02 < app_mape
        )
        rows_by_game = segmented_rows_by_game if use_segmented_model else app_rows_by_game
        chosen_bias_lines = segmented_bias_lines if use_segmented_model else app_bias_lines
        chosen_bias_correction_factor = segmented_bias_correction_factor if use_segmented_model else app_bias_correction_factor
        chosen_bias_summary = segmented_bias_summary if use_segmented_model else app_bias_summary
        chosen_model = "分层模型" if use_segmented_model else "项目级模型"

        comparison_lines = [
            f"当前采用的回收预测模型：{chosen_model}。",
            (
                f"模型对比：项目级模型 MAPE {app_mape:.1%}；分层模型 MAPE {segmented_mape:.1%}。"
                if app_mape is not None and segmented_mape is not None
                else "模型对比：当前成熟样本不足，暂时无法比较项目级模型和分层模型。"
            ),
        ]
        if not use_segmented_model and segmented_mape is not None and app_mape is not None:
            comparison_lines.append("本期未采用分层校准方案，因为成熟样本回测结果明显弱于项目级模型。")

        self._latest_global_bias_lines = comparison_lines + chosen_bias_lines
        self._latest_bias_correction_factor = chosen_bias_correction_factor
        chosen_bias_summary = dict(chosen_bias_summary)
        chosen_bias_summary["selected_model"] = chosen_model
        chosen_bias_summary["app_level_mape"] = app_mape
        chosen_bias_summary["segmented_mape"] = segmented_mape
        self._latest_global_bias_summary = chosen_bias_summary

        result: dict[str, RecoveryAnalysis] = {}
        for game, rows in rows_by_game.items():
            current_rows = [row for row in rows if current_start <= row.date <= report_date]
            previous_rows = [row for row in rows if previous_start <= row.date <= previous_end]
            history_rows = [row for row in rows if row.date < previous_start]
            project_key = self._project_key(game)
            analysis = self._build_recovery_analysis(
                current_rows,
                previous_rows,
                history_rows,
                date.today(),
                actual_curve_override=actual_curve_by_game.get(game) or actual_curve_by_game.get(project_key),
            )
            if not analysis:
                continue
            result[project_key] = analysis
            result[game] = analysis
        self._latest_recovery_map = result
        return result

    def _build_adjust_actual_curve_by_game(self, raw_rows: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
        result: dict[str, dict[int, float]] = {}
        for raw_row in raw_rows:
            game = str(raw_row.get("app") or "").strip()
            if not game or self._is_blacklisted_adjust_app(game):
                continue
            spend = self._parse_numeric(raw_row.get("cost"))
            if spend <= 0:
                continue
            curve: dict[int, float] = {}
            for display_day, metric_suffix in self._adjust_recovery_day_mapping().items():
                value = self._parse_numeric(raw_row.get(f"roas_d{metric_suffix}"))
                if value > 0:
                    curve[display_day] = value
            if not curve:
                continue
            project_key = self._project_key(game)
            result[game] = curve
            result[project_key] = curve
        return result

    def _build_adjust_rows_by_game(self, raw_rows: list[dict[str, Any]]) -> dict[str, list[RecoveryCurveRow]]:
        rows_by_game: dict[str, list[RecoveryCurveRow]] = defaultdict(list)
        for raw_row in raw_rows:
            game = str(raw_row.get("app") or "").strip()
            if not game or self._is_blacklisted_adjust_app(game):
                continue
            row_date = self._parse_recovery_date([raw_row.get("day")])
            if row_date is None:
                continue
            spend = self._parse_numeric(raw_row.get("cost"))
            if spend <= 0:
                continue

            roi_by_day: dict[int, float] = {}
            for display_day, metric_suffix in self._adjust_recovery_day_mapping().items():
                roi_by_day[display_day] = self._extract_adjust_roi(raw_row, spend, metric_suffix)

            rows_by_game[game].append(
                RecoveryCurveRow(
                    date=row_date,
                    spend=spend,
                    roi_by_day=roi_by_day,
                    ratio_by_key=self._build_adjust_ratio_map(roi_by_day),
                    store_type=str(raw_row.get("store_type") or "").strip(),
                    network=str(raw_row.get("network") or "").strip(),
                )
            )
        return rows_by_game

    def _build_recovery_analysis(
        self,
        current_rows: list[RecoveryCurveRow],
        previous_rows: list[RecoveryCurveRow],
        history_rows: list[RecoveryCurveRow] | None = None,
        as_of_date: date | None = None,
        actual_curve_override: dict[int, float] | None = None,
    ) -> RecoveryAnalysis | None:
        if not current_rows:
            return None
        history_rows = history_rows or []
        as_of_date = as_of_date or date.today()

        observed_curve = self._weighted_observed_roi_curve(current_rows, as_of_date)
        if not observed_curve:
            return None
        forecast_base_curve = self._smooth_roi_curve(observed_curve)
        current_curve = dict(sorted((actual_curve_override or observed_curve).items()))
        previous_curve = self._smooth_roi_curve(self._weighted_observed_roi_curve(previous_rows, as_of_date))
        current_ratios = self._ratio_curve_from_weighted_curve(current_curve)
        previous_ratios = self._ratio_curve_from_weighted_curve(previous_curve)
        current_spend = sum(row.spend for row in current_rows)
        cohort_oldest_age_days, cohort_newest_age_days = self._cohort_age_bounds(current_rows, as_of_date)
        forecast_confidence = self._forecast_confidence_from_age(cohort_newest_age_days)

        actual_days = [day for day in (0, 1, 3, 7, 14, 30, 60) if day in current_curve]
        actual_summary = " / ".join(f"{day}D {current_curve[day]:.2f}" for day in actual_days) or NO_ACTUAL

        forecast_curve, source_day_by_target = self._build_forecast_curve(current_rows, forecast_base_curve, history_rows, as_of_date)
        forecast_days = [day for day in (30, 60, 90, 180) if day in forecast_curve]
        forecast_summary = " / ".join(f"预测 D{day} {forecast_curve[day]:.2f}" for day in forecast_days) or NO_FORECAST

        payback_day = self._estimate_payback_day_number(self._build_payback_curve(current_curve, forecast_curve))
        payback_summary = self._format_payback_summary(payback_day, forecast_curve, current_spend)

        d30_source = source_day_by_target.get(30)
        d60_source = source_day_by_target.get(60)
        d90_source = source_day_by_target.get(90)
        correction_factor = getattr(self, "_latest_bias_correction_factor", 1.0)
        d30_stats = self._forecast_backtest_stats(history_rows, d30_source, 30, as_of_date, correction_factor) if d30_source else None
        d60_stats = self._forecast_backtest_stats(history_rows, d60_source, 60, as_of_date, correction_factor) if d60_source else None
        d90_stats = self._forecast_backtest_stats(history_rows, d90_source, 90, as_of_date, correction_factor) if d90_source else None
        forecast_error = (
            f"历史 D30 回测 MAPE {d30_stats['mape']:.1%}（锚点 D{d30_source}）"
            if d30_stats
            else "历史 D30 回测暂无可用样本"
        )
        forecast_accuracy = (
            f"预测准确度 {d30_stats['accuracy']:.1%}（D{d30_source}->D30，n={d30_stats['samples']:.0f}）"
            if d30_stats
            else "预测准确度暂无可用样本"
        )
        history_validation_rows = self._format_history_validation_rows(
            d30_source=d30_source,
            d30_stats=d30_stats,
            d60_source=d60_source,
            d60_stats=d60_stats,
            d90_source=d90_source,
            d90_stats=d90_stats,
        )
        validated_targets = [
            day
            for day in (30, 60, 90)
            if day in forecast_curve and day in current_curve and cohort_newest_age_days is not None and cohort_newest_age_days >= day
        ]
        validation_reason = (
            f"最老样本 {cohort_oldest_age_days} 天；最新样本 {cohort_newest_age_days} 天。"
            if cohort_oldest_age_days is not None and cohort_newest_age_days is not None
            else "样本成熟度暂无可用数据。"
        )
        pending_validation = ""
        needs_validation = False
        drift_parts: list[str] = []
        forecast_accuracy_rows: list[str] = []
        if validated_targets:
            for day in validated_targets:
                actual_value = current_curve.get(day)
                forecast_value = forecast_curve.get(day)
                if not actual_value or not forecast_value:
                    continue
                error = (actual_value - forecast_value) / forecast_value if forecast_value else 0.0
                forecast_accuracy_rows.append(
                    f"D{day}：预测 {forecast_value:.2f}，实际 {actual_value:.2f}，误差 {error:+.1%}"
                )
                if abs(error) > 0.2:
                    drift_parts.append(f"D{day} 验证误差 {error:+.1%}")
        else:
            pending_validation = (
                f"预测待验证：最新样本只有 {cohort_newest_age_days or 0} 天，当前窗口还不能验证 D30+ 预测。"
            )
            needs_validation = True
            forecast_accuracy_rows.append(
                f"待验证：最新样本只有 {cohort_newest_age_days or 0} 天，整个安装窗口的 D30+ 实际回收还未成熟。"
            )
        drift_alert = f"预测漂移预警：{'; '.join(drift_parts)}" if drift_parts else ""
        if drift_alert:
            payback_summary = "回本预估：已验证窗口出现超过 20% 的偏差，模型重校前不要把回本预测作为放量依据"

        overview = f"{actual_summary}; {payback_summary}"
        change = ""
        if previous_curve:
            compare_days = [day for day in (3, 7, 14, 30, 60) if day in current_curve and day in previous_curve]
            compare_parts = [f"D{day} {current_curve[day]:.2f}({current_curve[day] - previous_curve[day]:+.2f})" for day in compare_days[:3]]
            for ratio_key in ("3/2", "7/2", "14/7", "30/7", "60/30", "90/60"):
                if ratio_key in current_ratios and ratio_key in previous_ratios:
                    compare_parts.append(f"{ratio_key} {current_ratios[ratio_key]:.2f}({current_ratios[ratio_key] - previous_ratios[ratio_key]:+.2f})")
                    if len(compare_parts) >= 5:
                        break
            reason = self._infer_market_recovery_change_reason(
                current_curve=current_curve,
                previous_curve=previous_curve,
                current_ratios=current_ratios,
                previous_ratios=previous_ratios,
            )
            change = " / ".join(compare_parts)
            if reason:
                change = f"{change}; {reason}" if change else reason

        history_parts = [
            (
                "预测锚点 "
                + "、".join(f"D{source}->D{target}" for target, source in sorted(source_day_by_target.items()) if source)
                if source_day_by_target
                else "暂无预测锚点"
            ),
            forecast_error,
            forecast_accuracy,
            (
                "历史准确度 "
                + "；".join(
                    part
                    for part in (
                        f"D30 {d30_stats['accuracy']:.1%}" if d30_stats else "",
                        f"D60 {d60_stats['accuracy']:.1%}" if d60_stats else "",
                        f"D90 {d90_stats['accuracy']:.1%}" if d90_stats else "",
                    )
                    if part
                )
            )
            if any((d30_stats, d60_stats, d90_stats))
            else "",
        ]
        current_validation_parts = [
            f"预测可信度 {forecast_confidence}",
            validation_reason,
            pending_validation,
            drift_alert,
            "。".join(forecast_accuracy_rows) if forecast_accuracy_rows else "",
        ]
        analysis_summary = " | ".join(
            part
            for part in history_parts + current_validation_parts
            if part
        )
        recommendation = self._build_forecast_recommendation(
            current_curve=current_curve,
            forecast_curve=forecast_curve,
            payback_day=payback_day,
            current_spend=current_spend,
            drift_alert=drift_alert,
            forecast_confidence=forecast_confidence,
            needs_validation=needs_validation,
            validation_reason=validation_reason,
        )
        return RecoveryAnalysis(
            overview=overview,
            change=change,
            actual_summary=actual_summary,
            forecast_summary=forecast_summary,
            payback_summary=payback_summary,
            analysis_summary=analysis_summary,
            recommendation=recommendation,
            forecast_error=forecast_error,
            forecast_accuracy=forecast_accuracy,
            drift_alert=drift_alert,
            cohort_oldest_age_days=cohort_oldest_age_days,
            cohort_newest_age_days=cohort_newest_age_days,
            forecast_confidence=forecast_confidence,
            pending_validation=pending_validation,
            needs_validation=needs_validation,
            validation_reason=validation_reason,
            forecast_accuracy_rows=forecast_accuracy_rows,
            history_validation_rows=history_validation_rows,
            bias_summary="; ".join(getattr(self, "_latest_global_bias_lines", [])),
            bias_correction_factor=correction_factor,
            actual_curve=current_curve,
            forecast_curve=forecast_curve,
            payback_day=payback_day,
        )

    @staticmethod
    def _smooth_roi_curve(curve: dict[int, float]) -> dict[int, float]:
        smoothed: dict[int, float] = {}
        running_max = 0.0
        for day in sorted(curve):
            running_max = max(running_max, curve[day])
            smoothed[day] = running_max
        return smoothed

    def _weighted_observed_roi_curve(
        self,
        rows: list[RecoveryCurveRow],
        as_of_date: date,
    ) -> dict[int, float]:
        values: dict[int, float] = {}
        all_days = sorted({day for row in rows for day in row.roi_by_day})
        for day in all_days:
            valid_rows = [row for row in rows if self._observed_age(row, as_of_date) >= day]
            total_spend = sum(row.spend for row in valid_rows)
            if total_spend <= 0:
                continue
            values[day] = sum(row.spend * row.roi_by_day.get(day, 0.0) for row in valid_rows) / total_spend
        return values

    def _ratio_curve_from_weighted_curve(self, curve: dict[int, float]) -> dict[str, float]:
        return self._build_adjust_ratio_map(curve)

    @staticmethod
    def _observed_age(row: RecoveryCurveRow, as_of_date: date) -> int:
        return max(0, (as_of_date - row.date).days)

    def _build_forecast_curve(
        self,
        current_rows: list[RecoveryCurveRow],
        current_curve: dict[int, float],
        history_rows: list[RecoveryCurveRow],
        as_of_date: date,
    ) -> tuple[dict[int, float], dict[int, int]]:
        forecast: dict[int, float] = {}
        source_day_by_target: dict[int, int] = {}

        for target_day in (30, 60, 90):
            source_day = self._choose_forecast_anchor_day(current_rows, current_curve, history_rows, target_day, as_of_date)
            if source_day is None:
                continue
            source_day_by_target[target_day] = source_day
            anchor_actual = current_curve.get(source_day, 0.0)
            if target_day <= source_day:
                forecast[target_day] = current_curve.get(target_day, anchor_actual)
                continue
            predicted_value = self._segmented_forecast_value(
                current_rows=current_rows,
                history_rows=history_rows,
                source_day=source_day,
                target_day=target_day,
                as_of_date=as_of_date,
                correction_factor=getattr(self, "_latest_bias_correction_factor", 1.0),
            )
            if predicted_value is None:
                forecast[target_day] = max(current_curve.get(target_day, 0.0), anchor_actual)
                continue
            forecast[target_day] = max(current_curve.get(target_day, 0.0), predicted_value)

        anchor_actual = current_curve.get(source_day_by_target.get(90, 0), 0.0) or current_curve.get(max(current_curve), 0.0)
        d90 = forecast.get(90) or forecast.get(60) or anchor_actual
        bias_factor = getattr(self, "_latest_bias_correction_factor", 1.0)
        mult_60_90 = self._segmented_multiplier(current_rows, history_rows, 60, 90, as_of_date) or 1.0
        mult_30_60 = self._segmented_multiplier(current_rows, history_rows, 30, 60, as_of_date) or 1.0
        mult_60_90 *= bias_factor
        mult_30_60 *= bias_factor
        tail_extension = max(0.0, mult_60_90 - 1.0)
        if tail_extension <= 0:
            tail_extension = max(0.0, mult_30_60 - 1.0) * 0.75
        forecast[180] = max(d90, d90 * (1.0 + tail_extension * 0.7))
        if 90 in source_day_by_target:
            source_day_by_target[180] = source_day_by_target[90]
        return forecast, source_day_by_target

    def _choose_forecast_anchor_day(
        self,
        current_rows: list[RecoveryCurveRow],
        current_curve: dict[int, float],
        history_rows: list[RecoveryCurveRow],
        target_day: int,
        as_of_date: date,
    ) -> int | None:
        candidates: list[tuple[float, int]] = []
        total_spend = sum(row.spend for row in current_rows)
        for source_day in (7, 3, 14, 30, 60):
            if source_day >= target_day or source_day not in current_curve:
                continue
            if total_spend > 0:
                covered_spend = sum(row.spend for row in current_rows if self._observed_age(row, as_of_date) >= source_day)
                if covered_spend / total_spend < 0.25:
                    continue
            stats = self._forecast_backtest_stats(history_rows, source_day, target_day, as_of_date)
            if not stats:
                continue
            candidates.append((stats["accuracy"], source_day))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        fallback_days = []
        for day in (7, 3, 14, 30, 60):
            if day >= target_day or day not in current_curve:
                continue
            if total_spend > 0:
                covered_spend = sum(row.spend for row in current_rows if self._observed_age(row, as_of_date) >= day)
                if covered_spend / total_spend < 0.25:
                    continue
            fallback_days.append(day)
        return fallback_days[0] if fallback_days else None

    def _historical_multiplier(
        self,
        rows: list[RecoveryCurveRow],
        source_day: int,
        target_day: int,
        as_of_date: date,
        store_type: str = "",
        network: str = "",
    ) -> float | None:
        cache_key = (
            id(rows),
            source_day,
            target_day,
            as_of_date.isoformat(),
            store_type or "*",
            network or "*",
        )
        cached = getattr(self, "_multiplier_cache", {}).get(cache_key)
        if cached is not None:
            return cached
        candidates: list[float] = []
        for row in rows:
            if self._observed_age(row, as_of_date) < target_day:
                continue
            if store_type and row.store_type != store_type:
                continue
            if network and row.network != network:
                continue
            source_value = row.roi_by_day.get(source_day)
            target_value = row.roi_by_day.get(target_day)
            if not source_value or source_value <= 0 or not target_value or target_value <= 0:
                continue
            candidates.append(min(max(0.6, target_value / source_value), 5.0))
        if len(candidates) < 3:
            self._multiplier_cache[cache_key] = None
            return None
        candidates.sort()
        result = candidates[len(candidates) // 2]
        self._multiplier_cache[cache_key] = result
        return result

    def _forecast_backtest_stats(
        self,
        rows: list[RecoveryCurveRow],
        anchor_day: int | None,
        target_day: int,
        as_of_date: date,
        correction_factor: float = 1.0,
    ) -> dict[str, float] | None:
        if anchor_day is None:
            return None
        weighted_error = 0.0
        weighted_signed_error = 0.0
        total_weight = 0.0
        sample_count = 0
        for row in rows:
            if self._observed_age(row, as_of_date) < target_day:
                continue
            source_value = row.roi_by_day.get(anchor_day)
            actual_value = row.roi_by_day.get(target_day)
            if not source_value or source_value <= 0 or not actual_value or actual_value <= 0:
                continue
            multiplier = self._multiplier_for_row(row, rows, anchor_day, target_day, as_of_date)
            if multiplier is None:
                continue
            predicted_value = source_value * multiplier * correction_factor
            if predicted_value <= 0:
                continue
            error = (actual_value - predicted_value) / predicted_value
            weighted_error += row.spend * abs(error)
            weighted_signed_error += row.spend * error
            total_weight += row.spend
            sample_count += 1
        if sample_count < 3 or total_weight <= 0:
            return None
        mape = weighted_error / total_weight
        bias = weighted_signed_error / total_weight
        return {"accuracy": max(0.0, 1.0 - mape), "mape": mape, "bias": bias, "samples": float(sample_count)}

    def _multiplier_for_row(
        self,
        row: RecoveryCurveRow,
        history_rows: list[RecoveryCurveRow],
        source_day: int,
        target_day: int,
        as_of_date: date,
    ) -> float | None:
        for store_type, network in (
            (row.store_type, row.network),
            (row.store_type, ""),
            ("", row.network),
            ("", ""),
        ):
            multiplier = self._historical_multiplier(
                history_rows,
                source_day,
                target_day,
                as_of_date,
                store_type=store_type,
                network=network,
            )
            if multiplier is not None:
                return multiplier
        return None

    def _segmented_forecast_value(
        self,
        current_rows: list[RecoveryCurveRow],
        history_rows: list[RecoveryCurveRow],
        source_day: int,
        target_day: int,
        as_of_date: date,
        correction_factor: float,
    ) -> float | None:
        weighted_prediction = 0.0
        covered_spend = 0.0
        for row in current_rows:
            if self._observed_age(row, as_of_date) < source_day:
                continue
            source_value = row.roi_by_day.get(source_day)
            if not source_value or source_value <= 0:
                continue
            multiplier = self._multiplier_for_row(row, history_rows, source_day, target_day, as_of_date)
            if multiplier is None:
                continue
            weighted_prediction += row.spend * source_value * multiplier * correction_factor
            covered_spend += row.spend
        if covered_spend <= 0:
            return None
        return weighted_prediction / covered_spend

    def _segmented_multiplier(
        self,
        current_rows: list[RecoveryCurveRow],
        history_rows: list[RecoveryCurveRow],
        source_day: int,
        target_day: int,
        as_of_date: date,
    ) -> float | None:
        weighted_multiplier = 0.0
        covered_spend = 0.0
        for row in current_rows:
            if self._observed_age(row, as_of_date) < source_day:
                continue
            source_value = row.roi_by_day.get(source_day)
            if not source_value or source_value <= 0:
                continue
            multiplier = self._multiplier_for_row(row, history_rows, source_day, target_day, as_of_date)
            if multiplier is None:
                continue
            weighted_multiplier += row.spend * multiplier
            covered_spend += row.spend
        if covered_spend <= 0:
            return None
        return weighted_multiplier / covered_spend

    @staticmethod
    def _build_payback_curve(
        actual_curve: dict[int, float],
        forecast_curve: dict[int, float],
    ) -> dict[int, float]:
        curve: dict[int, float] = {}
        for day, value in actual_curve.items():
            curve[day] = value
        for day, value in forecast_curve.items():
            curve[day] = max(curve.get(day, 0.0), value)
        return curve

    @staticmethod
    def _estimate_payback_day_number(curve: dict[int, float]) -> float | None:
        points = sorted((day, value) for day, value in curve.items() if value > 0)
        if not points:
            return None
        for index, (day, value) in enumerate(points):
            if value < 1:
                continue
            if index == 0:
                return float(day)
            prev_day, prev_value = points[index - 1]
            if value == prev_value:
                return float(day)
            return prev_day + (1 - prev_value) * (day - prev_day) / (value - prev_value)
        return None

    @staticmethod
    def _format_payback_summary(
        payback_day: float | None,
        forecast_curve: dict[int, float],
        spend: float,
    ) -> str:
        forecast_180 = forecast_curve.get(180) or forecast_curve.get(90) or 0.0
        forecast_180_display = FinalWeeklyDigestBuilder._display_forecast_value(forecast_180)
        spend_display = round(spend)
        if payback_day is None:
            gap = spend_display * max(0.0, 1.0 - forecast_180_display)
            return f"回本预估：180 天内预计仍无法回本；按预测 ROI {forecast_180_display:.2f} 计算，距离回本还差 {round(gap):.0f}"
        if forecast_180_display >= 1:
            profit = spend_display * max(0.0, forecast_180_display - 1.0)
            return f"回本预估：预计约 {payback_day:.1f} 天回本；D180 利润空间约 {round(profit):.0f}"
        return f"回本预估：预计约 {payback_day:.1f} 天回本"

    @staticmethod
    def _build_forecast_recommendation(
        current_curve: dict[int, float],
        forecast_curve: dict[int, float],
        payback_day: float | None,
        current_spend: float,
        drift_alert: str,
        forecast_confidence: str,
        needs_validation: bool,
        validation_reason: str,
    ) -> str:
        actual_d7 = current_curve.get(7) or current_curve.get(3) or 0.0
        forecast_d90 = FinalWeeklyDigestBuilder._display_forecast_value(forecast_curve.get(90) or forecast_curve.get(60) or actual_d7)
        forecast_d180 = FinalWeeklyDigestBuilder._display_forecast_value(forecast_curve.get(180) or forecast_d90)
        spend_display = round(current_spend)
        if needs_validation:
            if forecast_d180 >= 1.0 and payback_day is not None:
                return (
                    f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，"
                    f"预测可信度 {forecast_confidence}。{validation_reason}维持观察，不新增预算，等 D30/更成熟回收确认后再讨论验证预算。"
                )
            if forecast_d180 >= 0.8:
                gap = spend_display * max(0.0, 1.0 - forecast_d180)
                return (
                    f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，"
                    f"预测可信度 {forecast_confidence}。现阶段不能单独依赖这条预测做放量或停投决策，先补回收，距离回本还差约 {gap:.0f}。"
                )
            return (
                f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，"
                f"预测可信度 {forecast_confidence}。暂不建议扩量，等样本更成熟后再验证，同时先处理低效组合。"
            )
        if drift_alert:
            return "先稳住预算，在重新校准预测模型前，不做放量决策。"
        if forecast_d90 >= 1.2 and payback_day is not None and payback_day <= 60:
            return f"当前实际 D7={actual_d7:.2f}；预计 D90={forecast_d90:.2f}；可维持预算，但只对已验证的组合谨慎放量。"
        if forecast_d90 >= 1.0 and payback_day is not None and payback_day <= 90:
            return f"当前实际 D7={actual_d7:.2f}；预计 D90={forecast_d90:.2f}；建议维持预算观察。"
        if forecast_d90 >= 0.8:
            gap = spend_display * max(0.0, 1.0 - forecast_d90)
            return f"当前实际 D7={actual_d7:.2f}；预计 D90={forecast_d90:.2f}；先优化回收，距离回本还差约 {gap:.0f}。"
        return f"当前实际 D7={actual_d7:.2f}；预计 D90={forecast_d90:.2f}；建议暂停或大幅收缩低效花费。"

    @staticmethod
    def _merge_project_judgement(judgement: str, recovery: RecoveryAnalysis) -> str:
        parts = [recovery.recommendation or judgement]
        if recovery.actual_summary:
            parts.append(f"实际回收：{recovery.actual_summary}")
        if recovery.forecast_summary:
            parts.append(f"预测回收：{recovery.forecast_summary}")
        if recovery.payback_summary:
            parts.append(recovery.payback_summary)
        return " | ".join(part for part in parts if part)

    @staticmethod
    def _adjust_recovery_day_mapping() -> dict[int, int]:
        return {
            1: 0,
            2: 1,
            3: 2,
            4: 3,
            5: 4,
            6: 5,
            7: 6,
            14: 13,
            21: 20,
            30: 29,
            60: 59,
            90: 89,
            100: 99,
        }

    @staticmethod
    def _cohort_age_bounds(rows: list[RecoveryCurveRow], as_of_date: date) -> tuple[int | None, int | None]:
        if not rows:
            return None, None
        ages = [max(0, (as_of_date - row.date).days) for row in rows]
        return max(ages), min(ages)

    @staticmethod
    def _forecast_confidence_from_age(newest_age_days: int | None) -> str:
        if newest_age_days is None:
            return "暂无"
        if newest_age_days < 7:
            return "低"
        if newest_age_days <= 30:
            return "中"
        if newest_age_days <= 90:
            return "高"
        return "很高"

    @staticmethod
    def _format_cohort_age_summary(recovery: RecoveryAnalysis) -> str:
        oldest = recovery.cohort_oldest_age_days
        newest = recovery.cohort_newest_age_days
        if oldest is None or newest is None:
            return "暂无"
        return f"最老 {oldest} 天 / 最新 {newest} 天"

    @staticmethod
    def _format_accuracy_line(game: str, recovery: RecoveryAnalysis) -> str:
        if recovery.pending_validation:
            return f"{game}: {recovery.pending_validation}"
        if recovery.forecast_accuracy_rows:
            return f"{game}: " + "; ".join(recovery.forecast_accuracy_rows)
        return f"{game}: 预测准确度暂无结果。"

    @staticmethod
    def _extract_curve_value(summary: str, day: int) -> float | None:
        match = re.search(rf"(?:D{day}|{day}D)\s+([0-9.]+)", summary or "")
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _build_market_forecast_analysis(self, recovery: RecoveryAnalysis) -> str:
        actual_d7 = recovery.actual_curve.get(7) or recovery.actual_curve.get(3)
        actual_label = "D7" if recovery.actual_curve.get(7) is not None else ("D3" if recovery.actual_curve.get(3) is not None else "")
        forecast_day = 180 if recovery.forecast_curve.get(180) is not None else (90 if recovery.forecast_curve.get(90) is not None else 60)
        forecast_value_raw = recovery.forecast_curve.get(forecast_day)
        forecast_value = self._display_forecast_value(forecast_value_raw) if forecast_value_raw is not None else None

        head_parts: list[str] = []
        if actual_d7 is not None and actual_label:
            head_parts.append(f"当前实际 {actual_label}={actual_d7:.2f}")
        if forecast_value is not None:
            head_parts.append(f"预计 D{forecast_day}={forecast_value:.2f}")
        if recovery.forecast_confidence:
            head_parts.append(f"预测可信度 {recovery.forecast_confidence}")

        if recovery.pending_validation:
            newest = recovery.cohort_newest_age_days or 0
            tail = f"最新样本仅 {newest} 天，当前先看趋势，不把这条预测直接当成放量依据。"
        elif recovery.drift_alert:
            tail = "已进入验证窗口，但当前偏差偏大，先校准模型，再决定是否放量。"
        elif forecast_value is not None and forecast_value >= 1 and recovery.payback_day is not None:
            tail = f"按当前预测，预计约 {recovery.payback_day:.1f} 天回本，可继续观察已验证组合。"
        elif forecast_value is not None and forecast_value >= 0.8:
            tail = "按当前预测，回本空间仍偏紧，优先修复回收而不是直接扩量。"
        else:
            tail = "按当前预测，回本把握仍弱，先压低效段。"

        lead = "；".join(head_parts)
        return f"{lead}；{tail}" if lead else tail

    def _build_market_recommendation(self, recovery: RecoveryAnalysis, spend: float) -> str:
        actual_d7 = recovery.actual_curve.get(7) or recovery.actual_curve.get(3) or 0.0
        forecast_d180 = self._display_forecast_value(
            recovery.forecast_curve.get(180) or recovery.forecast_curve.get(90) or recovery.forecast_curve.get(60) or actual_d7
        )
        if recovery.pending_validation:
            if forecast_d180 >= 1.0 and recovery.payback_day is not None:
                return (
                    f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，预测可信度 {recovery.forecast_confidence}。"
                    f"维持观察，不新增预算，等 D30/更成熟回收确认后再讨论验证预算。"
                )
            gap = spend * max(0.0, 1.0 - forecast_d180)
            if forecast_d180 >= 0.8:
                return (
                    f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，预测可信度 {recovery.forecast_confidence}。"
                    f"现阶段不能单独依赖这条预测做放量或停投决策，先补回收，按本周花费口径距离回本还差约 {gap:.0f}。"
                )
            return (
                f"需先验证：当前实际 D7={actual_d7:.2f}，预计 D180={forecast_d180:.2f}，预测可信度 {recovery.forecast_confidence}。"
                f"暂不建议扩量，等样本更成熟后再验证，同时先处理低效组合。"
            )
        return recovery.recommendation or "先稳住预算，继续观察回收。"

    def _format_market_accuracy_line(self, game: str, recovery: RecoveryAnalysis) -> str:
        newest = recovery.cohort_newest_age_days or 0
        if recovery.pending_validation:
            return f"{game}：最新样本 {newest} 天，D30+ 预测仍待验证。"
        if recovery.drift_alert:
            return f"{game}：已进入验证窗口，但当前预测偏差较大，先不要按预测直接放量。"
        if recovery.forecast_accuracy_rows:
            return f"{game}：已进入验证窗口，当前预测可作为观察参考。"
        return f"{game}：预测准确度暂无结果。"

    def _build_market_bias_lines(self) -> list[str]:
        summary = getattr(self, "_latest_global_bias_summary", {}) or {}
        selected_model = summary.get("selected_model")
        weighted_mape = summary.get("weighted_mape")
        average_bias = summary.get("average_bias")
        app_level_mape = summary.get("app_level_mape")
        segmented_mape = summary.get("segmented_mape")

        lines: list[str] = []
        if selected_model:
            model_text = str(selected_model)
            model_name = "项目级模型" if ("app-level" in model_text or "项目级" in model_text) else "分层模型"
            lines.append(f"当前采用的回收预测模型：{model_name}。")
        if weighted_mape is not None:
            lines.append(f"过去 12 个月成熟样本的平均预测误差约 {weighted_mape:.1%}。")
        if average_bias is not None:
            direction = "偏保守，平均低估" if average_bias > 0 else "偏乐观，平均高估"
            lines.append(f"模型整体{direction} {abs(average_bias):.1%}。")
        if app_level_mape is not None and segmented_mape is not None and segmented_mape >= app_level_mape:
            lines.append("分层模型回测更差，本期不采用。")
        return lines or ["预测偏差报告暂未生成。"]

    @staticmethod
    def _fmt_optional_ratio(value: float | None) -> str:
        if value is None:
            return "暂无"
        return f"{value:.2f}"

    @staticmethod
    def _display_forecast_value(value: float | None) -> float:
        if value is None:
            return 0.0
        return round(float(value), 2)

    @staticmethod
    def _infer_market_recovery_change_reason(
        current_curve: dict[int, float],
        previous_curve: dict[int, float],
        current_ratios: dict[str, float],
        previous_ratios: dict[str, float],
    ) -> str:
        d7_delta = (current_curve.get(7) or current_curve.get(3) or 0.0) - (previous_curve.get(7) or previous_curve.get(3) or 0.0)
        d3_delta = (current_curve.get(3) or 0.0) - (previous_curve.get(3) or 0.0)
        ratio_72_delta = (current_ratios.get("7/2") or 0.0) - (previous_ratios.get("7/2") or 0.0)
        ratio_32_delta = (current_ratios.get("3/2") or 0.0) - (previous_ratios.get("3/2") or 0.0)

        if d7_delta >= 0.20 or ratio_72_delta >= 0.30:
            return "短期回收明显改善，优先确认是投放组合优化、素材改善还是版本回收释放带动。"
        if d7_delta <= -0.10 or ratio_72_delta <= -0.20:
            return "短期回收明显走弱，优先排查成本抬升、素材疲劳和流量结构变化。"
        if abs(d3_delta) >= 0.08 or abs(ratio_32_delta) >= 0.15:
            return "整体回收变化不大，继续观察近 3 天渠道结构和素材表现。"
        return "整体回收变化不大，继续观察。"

    def _build_global_bias_report(
        self,
        rows_by_game: dict[str, list[RecoveryCurveRow]],
        as_of_date: date,
    ) -> tuple[list[str], float, dict[str, Any]]:
        total_weight = 0.0
        weighted_abs_error = 0.0
        weighted_bias = 0.0
        sample_pairs = 0
        validation_pairs: list[dict[str, Any]] = []
        pair_summaries: list[str] = []
        for source_day, target_day in ((7, 30), (30, 60), (60, 90)):
            pair_weight = 0.0
            pair_abs_error = 0.0
            pair_bias = 0.0
            pair_samples = 0
            for rows in rows_by_game.values():
                stats = self._forecast_backtest_stats(rows, source_day, target_day, as_of_date, 1.0)
                if not stats:
                    continue
                weight = stats["samples"]
                pair_weight += weight
                pair_abs_error += stats["mape"] * weight
                pair_bias += stats["bias"] * weight
                pair_samples += int(stats["samples"])
            if pair_weight <= 0:
                continue
            pair_mape = pair_abs_error / pair_weight
            pair_bias_avg = pair_bias / pair_weight
            pair_summaries.append(
                f"D{source_day}->D{target_day}: MAPE {pair_mape:.1%}，偏差 {pair_bias_avg:+.1%}，样本 {pair_samples}"
            )
            validation_pairs.append(
                {
                    "source_day": source_day,
                    "target_day": target_day,
                    "mape": pair_mape,
                    "bias": pair_bias_avg,
                    "samples": pair_samples,
                }
            )
            total_weight += pair_weight
            weighted_abs_error += pair_abs_error
            weighted_bias += pair_bias
            sample_pairs += pair_samples

        if total_weight <= 0:
            return (
                ["预测偏差报告暂未生成：成熟历史样本不足。"],
                1.0,
                {
                    "weighted_mape": None,
                    "average_bias": None,
                    "correction_factor": 1.0,
                    "validation_pairs": [],
                    "boss_autosend_ready": False,
                },
            )

        average_mape = weighted_abs_error / total_weight
        average_bias = weighted_bias / total_weight
        correction_factor = min(max(0.7, 1.0 + average_bias), 1.3)
        bias_direction = "低估" if average_bias > 0 else "高估"
        summary = {
            "weighted_mape": average_mape,
            "average_bias": average_bias,
            "correction_factor": correction_factor,
            "validation_pairs": validation_pairs,
            "boss_autosend_ready": average_mape < 0.10,
        }
        return (
            [
                f"过去 12 个月成熟样本：加权 MAPE {average_mape:.1%}；预测平均{bias_direction} {abs(average_bias):.1%}。",
                f"偏差校正系数：{correction_factor:.2f}。",
                "验证对：" + "；".join(pair_summaries),
            ],
            correction_factor,
            summary,
        )

    @staticmethod
    def _format_history_validation_rows(
        d30_source: int | None,
        d30_stats: dict[str, float] | None,
        d60_source: int | None,
        d60_stats: dict[str, float] | None,
        d90_source: int | None,
        d90_stats: dict[str, float] | None,
    ) -> list[str]:
        rows: list[str] = []
        for source_day, target_day, stats in (
            (d30_source, 30, d30_stats),
            (d60_source, 60, d60_stats),
            (d90_source, 90, d90_stats),
        ):
            if not source_day or not stats:
                continue
            rows.append(
                f"D{source_day}->D{target_day}: 准确度 {stats['accuracy']:.1%}，MAPE {stats['mape']:.1%}，偏差 {stats['bias']:+.1%}，样本 {int(stats['samples'])}"
            )
        return rows


def _read_json(path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
