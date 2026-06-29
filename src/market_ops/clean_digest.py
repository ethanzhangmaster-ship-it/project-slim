from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Any

from market_ops.digest import (
    CreativeDigestItem,
    MetricItem,
    RecoveryAnalysis,
    RecoveryCurveRow,
    WeeklyDigest,
    WeeklyDigestBuilder,
)
from market_ops.google_creative_resolver import GoogleCreativeResolver
from market_ops.models import ActionItem, AdsPerformanceRow, CreativeAssetRow, RevenueRow


class CleanWeeklyDigestBuilder(WeeklyDigestBuilder):
    def build(
        self,
        report,
        ads_rows,
        creative_rows,
        revenue_rows,
        revenue_breakdown_rows=None,
    ):
        digest = super().build(report, ads_rows, creative_rows, revenue_rows, revenue_breakdown_rows)
        active_project_keys = {self._project_key(item.game) for item in digest.project_items if item.game}
        covered_recovery_keys = sorted(
            self._project_key(item.game)
            for item in digest.project_items
            if item.game and item.recovery_overview and "未接入" not in item.recovery_overview
        )
        missing_recovery_keys = sorted(key for key in active_project_keys if key and key not in covered_recovery_keys)

        if covered_recovery_keys or missing_recovery_keys:
            covered_text = "、".join(covered_recovery_keys) if covered_recovery_keys else "无"
            missing_text = "、".join(missing_recovery_keys) if missing_recovery_keys else "无"
            digest.company_highlights.append(
                f"回收曲线接入情况：已接入 {covered_text}；未接入 {missing_text}。"
            )

        for item in digest.project_items:
            project_key = self._project_key(item.game)
            if project_key in missing_recovery_keys and not item.recovery_overview:
                item.recovery_overview = "未接入项目级 ROI 来源，暂不能判断回本天数和利润空间。"
                item.recovery_change = "待接入项目级 ROI 表后，再做本期与上期的回收增长对比。"

        return digest

    def _iter_recovery_sources(self) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        for item in self._settings.project_sheet_sources:
            game = str(item.get("game") or "").strip()
            roi_url = str(item.get("roi_url") or item.get("daily_url") or "").strip()
            if not game or not roi_url:
                continue
            sources.append({"game": game, "roi_url": roi_url})
        if not sources and self._settings.feishu_roi_url and self._settings.default_game_name:
            sources.append({"game": self._settings.default_game_name, "roi_url": self._settings.feishu_roi_url})
        deduped: dict[tuple[str, str], dict[str, str]] = {}
        for item in sources:
            deduped[(item["game"], item["roi_url"])] = item
        return list(deduped.values())

    def _top_creative(
        self,
        rows: list[CreativeAssetRow],
        revenue_breakdown_rows=None,
        *,
        project_key: str = "",
        project_name: str = "",
        google_resolver: GoogleCreativeResolver | None = None,
    ) -> str:
        return super()._top_creative(
            rows,
            revenue_breakdown_rows,
            project_key=project_key,
            project_name=project_name,
            google_resolver=google_resolver,
        )

    def render_markdown(self, digest: WeeklyDigest) -> str:
        lines = [f"# {digest.title}", "", "## 1. 公司总体数据情况", ""]
        lines.extend(f"- {metric.label} {metric.value}" for metric in digest.company_metrics)
        lines.extend(f"- {item}" for item in digest.company_highlights)

        lines.extend(["", "## 2. 每个项目的投放数据情况分析", ""])
        if digest.project_items:
            for item in digest.project_items:
                lines.append(f"- {item.game}")
                if item.detail_ready:
                    lines.append(
                        f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`；7天 ROI `{item.project_roi:.2f}`，"
                        f"平均 ROAS `{item.avg_roas:.2f}`，平均 CPI `{item.avg_cpi:.2f}`，总收入 `{item.total_revenue:.0f}`"
                    )
                    lines.append(
                        f"- 主投渠道 `{item.top_channel}`，风险段 `{item.risk_segment}`，最佳单日 `{item.best_day}`，"
                        f"优先素材 `{item.top_creative}`"
                    )
                else:
                    lines.append(
                        f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`；7天 ROI `{item.project_roi:.2f}`，"
                        f"总收入 `{item.total_revenue:.0f}`"
                    )
                    lines.append("- 当前已接入 Adjust 项目总览，渠道/平台/素材明细待补飞书接入")
                if item.recovery_overview:
                    lines.append(f"- 回收横向：{item.recovery_overview}")
                if item.recovery_change:
                    lines.append(f"- 回收纵向：{item.recovery_change}")
                lines.append(f"- 判断：{item.judgement}")
        else:
            lines.append("- 当前周窗内没有可用投放数据。")

        lines.extend(["", "## 3. 最近的素材分析情况", ""])
        if digest.creative_items:
            for item in digest.creative_items:
                lines.append(
                    f"- {item.asset_id}：类型={item.creative_type}，ROAS={item.roas:.2f}，CTR={item.ctr:.3f}，状态={item.status}"
                )
            lines.extend(f"- {item}" for item in digest.creative_notes)
        else:
            lines.append("- 当前没有可用素材数据。")

        lines.extend(["", "## 本周建议动作", ""])
        if digest.next_actions:
            lines.extend(f"- {item}" for item in digest.next_actions)
        else:
            lines.append("- 本周没有新增建议动作。")
        lines.append("")
        return "\n".join(lines)

    def build_card(self, digest: WeeklyDigest) -> dict[str, Any]:
        elements: list[dict[str, Any]] = []
        elements.append(self._section_title("1. 公司总体数据情况"))
        elements.append(self._metric_fields(digest.company_metrics[:4]))
        if digest.company_highlights:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.company_highlights)))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("2. 每个项目的投放数据情况分析"))
        if digest.project_items:
            for item in digest.project_items:
                project_lines = [f"**{item.game}**"]
                if item.detail_ready:
                    project_lines.extend(
                        [
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`",
                            f"- 7天 ROI `{item.project_roi:.2f}`，平均 ROAS `{item.avg_roas:.2f}`，平均 CPI `{item.avg_cpi:.2f}`，总收入 `{item.total_revenue:.0f}`",
                            f"- 主投渠道 `{item.top_channel}`，风险段 `{item.risk_segment}`",
                            f"- 最佳单日 `{item.best_day}`",
                            f"- 优先素材 `{item.top_creative}`",
                        ]
                    )
                else:
                    project_lines.extend(
                        [
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`",
                            f"- 7天 ROI `{item.project_roi:.2f}`，总收入 `{item.total_revenue:.0f}`",
                            "- 当前已接入 Adjust 项目总览，渠道/平台/素材明细待补飞书接入",
                        ]
                    )
                if item.recovery_overview:
                    project_lines.append(f"- 回收横向：{item.recovery_overview}")
                if item.recovery_change:
                    project_lines.append(f"- 回收纵向：{item.recovery_change}")
                project_lines.append(f"- 判断：{item.judgement}")
                elements.append(self._markdown_block("\n".join(project_lines)))
        else:
            elements.append(self._markdown_block("- 当前周窗内没有可用投放数据。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("3. 最近的素材分析情况"))
        if digest.creative_items:
            creative_fields: list[dict[str, Any]] = []
            for item in digest.creative_items:
                creative_fields.append(
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**{item.asset_id}**\n"
                                f"类型：{item.creative_type}\n"
                                f"ROAS：`{item.roas:.2f}`\n"
                                f"CTR：`{item.ctr:.3f}`\n"
                                f"状态：{item.status}"
                            ),
                        },
                    }
                )
            elements.append({"tag": "div", "fields": creative_fields})
            if digest.creative_notes:
                elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.creative_notes)))
        else:
            elements.append(self._markdown_block("- 当前没有可用素材数据。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("本周建议动作"))
        if digest.next_actions:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.next_actions)))
        else:
            elements.append(self._markdown_block("- 本周没有新增建议动作。"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "turquoise",
                "title": {"tag": "plain_text", "content": digest.title},
            },
            "elements": elements,
        }

    def _build_company_summary(
        self,
        report_date: date,
        ads_rows: list[AdsPerformanceRow],
        revenue_rows: list[RevenueRow],
    ) -> tuple[list[MetricItem], list[str]]:
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)

        current_total_ads, current_detail_ads = self._split_window_ads(ads_rows, window_start, report_date)
        previous_total_ads, previous_detail_ads = self._split_window_ads(ads_rows, previous_start, previous_end)
        active_games = {row.game for row in current_total_ads + current_detail_ads if row.game}
        trusted_detail_rows = self._trusted_detail_rows(current_detail_ads)
        trusted_detail_projects = {self._project_key(row.game) for row in trusted_detail_rows if row.game}

        current_summary_rows = current_total_ads or current_detail_ads
        previous_summary_rows = previous_total_ads or previous_detail_ads
        current_detail_rows = current_detail_ads or current_summary_rows

        company_sheet_summary = self._load_company_sheet_summary(report_date)
        current_revenue = [row for row in revenue_rows if window_start <= row.date <= report_date]
        previous_revenue = [row for row in revenue_rows if previous_start <= row.date <= previous_end]
        current_adjust_spend = sum(row.total_cost for row in current_revenue)
        previous_adjust_spend = sum(row.total_cost for row in previous_revenue)

        if current_adjust_spend or previous_adjust_spend:
            current_spend = current_adjust_spend
            previous_spend = previous_adjust_spend
            signal_rows = trusted_detail_rows or current_detail_ads
            top_channel = (
                self._top_channel(signal_rows)
                if signal_rows
                else company_sheet_summary["top_channel"]
                if company_sheet_summary is not None
                else "n/a"
            )
            weakest_segment = (
                self._weakest_segment(signal_rows)
                if signal_rows
                else company_sheet_summary["weakest_segment"]
                if company_sheet_summary is not None
                else "暂无可判定风险段"
            )
            company_scope = "company"
        elif company_sheet_summary is not None:
            current_spend = company_sheet_summary["current_spend"]
            previous_spend = company_sheet_summary["previous_spend"]
            top_channel = company_sheet_summary["top_channel"]
            weakest_segment = company_sheet_summary["weakest_segment"]
            company_scope = "company"
        else:
            current_revenue = self._aligned_revenue_rows(revenue_rows, window_start, report_date, active_games)
            previous_revenue = self._aligned_revenue_rows(revenue_rows, previous_start, previous_end, active_games)
            current_spend = sum(row.spend for row in current_summary_rows)
            previous_spend = sum(row.spend for row in previous_summary_rows)
            signal_rows = trusted_detail_rows or current_detail_rows
            top_channel = self._top_channel(signal_rows)
            weakest_segment = self._weakest_segment(signal_rows)
            company_scope = "active_projects"

        current_revenue_total = sum(row.total_revenue for row in current_revenue)
        previous_revenue_total = sum(row.total_revenue for row in previous_revenue)
        current_roi = current_revenue_total / current_spend if current_spend else 0.0
        previous_roi = previous_revenue_total / previous_spend if previous_spend else 0.0

        spend_change = self._pct_change(current_spend, previous_spend)
        revenue_change = self._pct_change(current_revenue_total, previous_revenue_total)
        roi_change = self._pct_change(current_roi, previous_roi)

        top_growth_game = self._top_growth_game(current_revenue, previous_revenue, current_summary_rows, previous_summary_rows)
        focus_line = self._focus_line(current_roi, weakest_segment)

        metrics = [
            MetricItem("本周花费", f"{current_spend:.0f} ({spend_change})"),
            MetricItem("整体收入", f"{current_revenue_total:.0f} ({revenue_change})"),
            MetricItem("公司总收入ROI", f"{current_roi:.2f} ({roi_change})"),
            MetricItem("主投渠道", top_channel),
        ]

        highlights: list[str] = []
        active_revenue_projects = {
            self._project_key(row.game)
            for row in current_revenue
            if row.total_cost > 0 or self._project_key(row.game) in trusted_detail_projects
        }
        coverage_note = self._coverage_note(trusted_detail_projects, active_revenue_projects, company_scope)
        if coverage_note:
            highlights.append(coverage_note)
        highlights.extend(
            [
                f"主要增长来自 {top_growth_game}。",
                f"当前最需要压缩的低效段是 {weakest_segment}。",
                f"下周重点关注：{focus_line}",
            ]
        )
        return metrics, highlights

    def _build_recovery_analysis(
        self,
        current_rows: list[RecoveryCurveRow],
        previous_rows: list[RecoveryCurveRow],
    ) -> RecoveryAnalysis | None:
        if not current_rows:
            return None
        current_curve = self._weighted_roi_curve(current_rows)
        if not current_curve:
            return None

        previous_curve = self._weighted_roi_curve(previous_rows)
        current_ratios = self._weighted_ratio_curve(current_rows)
        previous_ratios = self._weighted_ratio_curve(previous_rows)
        current_spend = sum(row.spend for row in current_rows)

        key_days = [day for day in (3, 7, 14, 30, 60) if day in current_curve]
        curve_text = " / ".join(f"D{day} {current_curve[day]:.2f}" for day in key_days) or "暂无可用回收曲线"
        payback_text = self._estimate_payback_day(current_curve)
        long_day = max(current_curve)
        long_roi = current_curve[long_day]
        if long_roi >= 1:
            headroom = current_spend * (long_roi - 1)
            headroom_text = f"按 D{long_day} ROI {long_roi:.2f} 看，已超过回本线，利润空间约 {headroom:.0f}"
        else:
            gap = current_spend * (1 - long_roi)
            headroom_text = f"按 D{long_day} ROI {long_roi:.2f} 看，距回本还差约 {gap:.0f}"
        overview = f"{curve_text}；{payback_text}；{headroom_text}"

        change = ""
        if previous_curve:
            compare_parts: list[str] = []
            for day in (3, 7, 14, 30, 60):
                if day in current_curve and day in previous_curve:
                    delta = current_curve[day] - previous_curve[day]
                    compare_parts.append(f"D{day} {current_curve[day]:.2f}（较上期 {delta:+.2f}）")
                if len(compare_parts) >= 3:
                    break
            for ratio_key in ("3/2", "7/2", "14/7", "14/30", "21/30"):
                if ratio_key in current_ratios and ratio_key in previous_ratios:
                    delta = current_ratios[ratio_key] - previous_ratios[ratio_key]
                    compare_parts.append(f"{ratio_key} {current_ratios[ratio_key]:.2f}（较上期 {delta:+.2f}）")
                if len(compare_parts) >= 5:
                    break
            reason = self._infer_recovery_change_reason(
                current_curve,
                previous_curve,
                current_ratios,
                previous_ratios,
                current_rows,
                previous_rows,
            )
            change = " / ".join(compare_parts)
            if reason:
                change = f"{change}；原因判断：{reason}" if change else f"原因判断：{reason}"

        return RecoveryAnalysis(overview=overview, change=change)

    @staticmethod
    def _weighted_roi_curve(rows: list[RecoveryCurveRow]) -> dict[int, float]:
        values: dict[int, float] = {}
        all_days = sorted({day for row in rows for day in row.roi_by_day})
        for day in all_days:
            valid_rows = [row for row in rows if day in row.roi_by_day]
            total_spend = sum(row.spend for row in valid_rows)
            if total_spend <= 0:
                continue
            values[day] = sum(row.spend * row.roi_by_day[day] for row in valid_rows) / total_spend

        smoothed: dict[int, float] = {}
        running_max = 0.0
        for day in sorted(values):
            running_max = max(running_max, values[day])
            smoothed[day] = running_max
        return smoothed

    @staticmethod
    def _estimate_payback_day(curve: dict[int, float]) -> str:
        points = sorted((day, value) for day, value in curve.items() if value > 0)
        if not points:
            return "暂无可用回本曲线"
        for index, (day, value) in enumerate(points):
            if value < 1:
                continue
            if index == 0:
                return f"预计 {day} 天内回本"
            prev_day, prev_value = points[index - 1]
            if value == prev_value:
                return f"预计约 {day:.1f} 天回本"
            day_estimate = prev_day + (1 - prev_value) * (day - prev_day) / (value - prev_value)
            return f"预计约 {day_estimate:.1f} 天回本"
        return f"截至 D{points[-1][0]} 仍未回本"

    @staticmethod
    def _infer_recovery_change_reason(
        current_curve: dict[int, float],
        previous_curve: dict[int, float],
        current_ratios: dict[str, float],
        previous_ratios: dict[str, float],
        current_rows: list[RecoveryCurveRow],
        previous_rows: list[RecoveryCurveRow],
    ) -> str:
        early_days = [day for day in (2, 3, 7) if day in current_curve and day in previous_curve]
        late_days = [day for day in (14, 21, 30, 60) if day in current_curve and day in previous_curve]
        early_delta = mean(current_curve[day] - previous_curve[day] for day in early_days) if early_days else 0.0
        late_delta = mean(current_curve[day] - previous_curve[day] for day in late_days) if late_days else 0.0
        current_spend = sum(row.spend for row in current_rows)
        previous_spend = sum(row.spend for row in previous_rows)
        spend_delta = ((current_spend - previous_spend) / previous_spend) if previous_spend else 0.0

        if early_delta <= -0.05 and late_delta <= -0.05:
            reason = "前中段回收同步走弱，优先排查流量质量、素材承接和后端变现深度。"
        elif early_delta <= -0.05 and late_delta > -0.02:
            reason = "前段回收变弱但长尾相对稳定，更像前端流量质量或点击后转化下滑。"
        elif early_delta > 0.03 and late_delta <= -0.03:
            reason = "短期回收更快，但中后段变弱，说明前端被拉高而长尾价值释放不足。"
        elif early_delta > 0.03 and late_delta > 0.03:
            reason = "前中段回收同步改善，说明本周买量质量和后续变现承接都在提升。"
        else:
            reason = "整体回收变化不大，更像正常波动，继续观察版本、渠道和素材贡献。"

        if spend_delta > 0.15 and early_delta < 0:
            reason += " 同期有明显放量，存在放量稀释回收质量的可能。"
        if "14/7" in current_ratios and "14/7" in previous_ratios and current_ratios["14/7"] < previous_ratios["14/7"] - 0.1:
            reason += " 7日后的长尾释放也在变弱。"
        return reason

    @staticmethod
    def _merge_project_judgement(judgement: str, recovery: RecoveryAnalysis) -> str:
        return judgement

    def _build_creative_digest(
        self,
        creative_rows,
        revenue_breakdown_rows=None,
        report_date=None,
        google_resolver: GoogleCreativeResolver | None = None,
    ):
        return super()._build_creative_digest(
            creative_rows,
            revenue_breakdown_rows or [],
            report_date,
            google_resolver or GoogleCreativeResolver(creative_rows),
        )

    def _format_action_line(self, action: ActionItem) -> str:
        owner = action.owner or self._settings.default_task_owner
        prefix = f"{action.action_type}："
        title = action.title[len(prefix) :] if action.title.startswith(prefix) else action.title
        return f"{action.action_type}：{title}。负责人：{owner}；截止时间：{action.due_date.isoformat()}；KPI：{action.acceptance_metric}"

    def _build_next_actions(self, draft_actions: list[ActionItem], project_items: list[Any]) -> list[str]:
        lines: list[str] = []
        for action in draft_actions:
            matched_project = next((item for item in project_items if item.game and item.game in action.title), None)
            if matched_project and action.action_type == "加码" and "付费净 ROI" in matched_project.judgement:
                owner = action.owner or self._settings.default_task_owner
                lines.append(
                    f"优化回本：{matched_project.game}。负责人：{owner}；截止时间：{action.due_date.isoformat()}；"
                    "KPI：先把付费净 ROI 拉到 1.00 以上，再评估是否补量"
                )
                continue
            lines.append(self._format_action_line(action))
        return lines

    def _coverage_note(
        self,
        trusted_detail_projects: set[str],
        active_revenue_projects: set[str],
        company_scope: str,
    ) -> str:
        if company_scope == "company":
            if trusted_detail_projects and active_revenue_projects and trusted_detail_projects != active_revenue_projects:
                revenue_list = "、".join(sorted(active_revenue_projects)[:6])
                revenue_suffix = " 等项目" if len(active_revenue_projects) > 6 else ""
                detail_list = "、".join(sorted(trusted_detail_projects)[:4])
                detail_suffix = " 等项目" if len(trusted_detail_projects) > 4 else ""
                return f"项目段已按 Adjust 项目口径覆盖 {revenue_list}{revenue_suffix}；其中仅 {detail_list}{detail_suffix} 已接入可信飞书明细。"
            if active_revenue_projects:
                revenue_list = "、".join(sorted(active_revenue_projects)[:6])
                revenue_suffix = " 等项目" if len(active_revenue_projects) > 6 else ""
                return f"项目段已按 Adjust 项目口径覆盖 {revenue_list}{revenue_suffix}。"
            return "公司段按 Adjust 公司整体口径统计。"
        if trusted_detail_projects and active_revenue_projects and trusted_detail_projects != active_revenue_projects:
            game_list = "、".join(sorted(trusted_detail_projects)[:4])
            suffix = " 等项目" if len(trusted_detail_projects) > 4 else ""
            return f"当前公司段按已接入投放项目口径统计，当前覆盖 {game_list}{suffix}。"
        return ""

    @staticmethod
    def _pct_change(current: float, previous: float) -> str:
        if previous == 0:
            return "无上周可比基数"
        delta = (current - previous) / previous
        return f"{delta:+.1%}"

    @staticmethod
    def _parse_numeric(value: Any) -> float:
        text = str(value or "").replace("$", "").replace(",", "").replace("%", "").strip()
        if not text or text.lower() == "none":
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _best_day(rows: list[AdsPerformanceRow]) -> str:
        if not rows:
            return "暂无最佳单日"
        best_row = max(rows, key=lambda row: row.roas)
        return f"{best_row.date.isoformat()}（ROAS {best_row.roas:.2f}）"

    def _top_creative(
        self,
        rows: list[CreativeAssetRow],
        revenue_breakdown_rows=None,
        *,
        project_key: str = "",
        project_name: str = "",
        google_resolver: GoogleCreativeResolver | None = None,
    ) -> str:
        return super()._top_creative(
            rows,
            revenue_breakdown_rows,
            project_key=project_key,
            project_name=project_name,
            google_resolver=google_resolver,
        )

    @staticmethod
    def _focus_line(current_roi: float, risk_segment: str) -> str:
        if current_roi >= 1:
            return f"继续复制高回收素材，同时压缩 {risk_segment} 的低效预算。"
        return f"先控制 {risk_segment} 的低回收花费，再补充可复制的高回收素材测试。"

    @staticmethod
    def _project_action_judgement(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        if not detail_ready:
            if avg_roas >= 1:
                return "当前项目总回收已过线，可以继续观察量级，但渠道与素材细分仍待补接。"
            if avg_roas >= 0.3:
                return "当前项目总回收尚可，先保持观察，待补齐渠道细分后再做加减量决策。"
            return "当前项目总回收偏弱，建议先控量，并尽快补齐飞书渠道明细。"
        if avg_roas >= 0.3:
            return f"可以谨慎小额测试，但只放在已验证回收的组合，同时继续复制 {top_creative}。"
        if avg_roas >= 0.1:
            return f"暂时不宜激进放量，先稳住预算，并优先处理 {risk_segment}。"
        return f"应先收缩预算，再补素材测试，尤其优先处理 {risk_segment}。"

    @staticmethod
    def _project_action_judgement_paid(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        return CleanWeeklyDigestBuilder._project_action_judgement_paid_v2(
            avg_roas=avg_roas,
            risk_segment=risk_segment,
            top_creative=top_creative,
            detail_ready=detail_ready,
            paid_roi_net=paid_roi_net,
        )

    @staticmethod
    def _project_action_judgement_paid_v2(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        if paid_roi_net is not None and paid_roi_net < 1:
            if paid_roi_net >= 0.8:
                return (
                    f"按付费净 ROI 口径看仍未回本（{paid_roi_net:.2f}），暂不建议直接放量，"
                    f"先在小预算下继续验证 {top_creative}。"
                )
            if paid_roi_net >= 0.6:
                return (
                    f"按付费净 ROI 口径看仍未回本（{paid_roi_net:.2f}），先控量，优先优化 {risk_segment}，"
                    "只保留已验证组合。"
                )
            return f"按付费净 ROI 口径看回本偏弱（{paid_roi_net:.2f}），当前不适合加投，先收缩低效预算并排查 {risk_segment}。"
        if not detail_ready:
            if avg_roas >= 1:
                return "当前项目总回收已过线，可以继续观察量级，但渠道与素材细分仍待补接。"
            if avg_roas >= 0.3:
                return "当前项目总回收尚可，先保持观察，待补齐渠道细分后再做加减量决策。"
            return "当前项目总回收偏弱，建议先控量，并尽快补齐飞书渠道明细。"
        if avg_roas >= 1:
            return f"可以只在已验证回收的组合上小步补量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.3:
            return f"可以只在已验证回收的组合上小额测试，但暂不建议直接放量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.1:
            return f"暂时不宜激进放量，先稳住预算，并优先处理 {risk_segment}。"
        return f"应先收缩预算，再补素材测试，尤其优先处理 {risk_segment}。"
