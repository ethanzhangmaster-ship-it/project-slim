"""Bitable 报告数据转换核心

将 WeeklyDigest + 各分析模块 JSON payload 转换为 6 组扁平化 record dicts，
同时组装 chart_data 字典供 HTML 报告使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from market_ops.config import Settings
from market_ops.digest import (
    CampaignDigestItem,
    CreativeDigestItem,
    MetricItem,
    ProjectDigestItem,
    WeeklyDigest,
)
from market_ops.models import ActionItem


@dataclass(slots=True)
class BitableReportPayload:
    kpi_overview_records: list[dict[str, Any]]
    project_records: list[dict[str, Any]]
    campaign_records: list[dict[str, Any]]
    creative_records: list[dict[str, Any]]
    decision_records: list[dict[str, Any]]
    action_records: list[dict[str, Any]]
    chart_data: dict[str, Any]


class BitableReportBuilder:
    """将周报数据转换为飞书多维表格 record dicts + HTML 图表数据。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_payload(
        self,
        report_date: date,
        digest: WeeklyDigest,
        decision_payload: dict[str, Any],
        creative_fatigue_payload: dict[str, Any],
        lifecycle_payload: dict[str, Any],
        action_items: list[ActionItem],
        dynamic_payback_payload: dict[str, Any] | None = None,
    ) -> BitableReportPayload:
        kpi_records = self._build_kpi_overview_records(digest, report_date)
        project_records = self._build_project_records(digest, lifecycle_payload, dynamic_payback_payload or {})
        campaign_records = self._build_campaign_records(digest)
        creative_records = self._build_creative_records(
            digest, creative_fatigue_payload, lifecycle_payload
        )
        decision_records = self._build_decision_records(decision_payload)
        action_records = self._build_action_records(action_items, decision_payload)
        chart_data = self._build_chart_data(
            digest, decision_payload, creative_fatigue_payload, dynamic_payback_payload or {}
        )
        return BitableReportPayload(
            kpi_overview_records=kpi_records,
            project_records=project_records,
            campaign_records=campaign_records,
            creative_records=creative_records,
            decision_records=decision_records,
            action_records=action_records,
            chart_data=chart_data,
        )

    # ------------------------------------------------------------------
    # Table 1: 公司指标总览
    # ------------------------------------------------------------------

    def _build_kpi_overview_records(
        self, digest: WeeklyDigest, report_date: date
    ) -> list[dict[str, Any]]:
        metrics_map = {m.label.strip(): m.value for m in digest.company_metrics}
        spend_str = metrics_map.get("本周花费", "0")
        revenue_str = metrics_map.get("整体收入", "0")
        roi_str = metrics_map.get("公司总收入ROI", "")
        spend = self._parse_metric_value(spend_str)
        revenue = self._parse_metric_value(revenue_str)
        profit = revenue - spend
        return [
            {
                "报告周期": report_date.isoformat(),
                "本周花费": spend,
                "整体收入": revenue,
                "利润估算": profit,
                "公司总收入ROI": roi_str,
                "主投渠道": metrics_map.get("主投渠道", ""),
                "花费环比变化": self._extract_change_pct(spend_str),
                "收入环比变化": self._extract_change_pct(revenue_str),
                "ROI环比变化": self._extract_change_pct(roi_str),
                "重点亮点": "\n".join(digest.company_highlights[:4]),
                "下周关注": "\n".join(digest.next_actions[:3]),
            }
        ]

    # ------------------------------------------------------------------
    # Table 2: 项目分析表
    # ------------------------------------------------------------------

    def _build_project_records(
        self,
        digest: WeeklyDigest,
        lifecycle_payload: dict[str, Any],
        dynamic_payback_payload: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        lifecycle_items = lifecycle_payload.get("items", [])
        if isinstance(lifecycle_items, list):
            lifecycle_items = {it.get("project_key", it.get("project", "")): it for it in lifecycle_items if isinstance(it, dict)}
        payback_items = (dynamic_payback_payload or {}).get("items", [])
        if isinstance(payback_items, list):
            payback_items = {it.get("project", ""): it for it in payback_items if isinstance(it, dict)}
        records: list[dict[str, Any]] = []
        for item in digest.project_items:
            project_key = self._project_key(item.game)
            lc = lifecycle_items.get(project_key, {})
            pb = payback_items.get(project_key, {})
            records.append(
                {
                    "项目名称": item.game,
                    "项目Key": project_key,
                    "本周花费": item.spend,
                    "花费环比": item.spend_change,
                    "总收入": item.total_revenue,
                    "总收入ROI": item.project_roi,
                    "付费净ROI": item.paid_roi_net if item.paid_roi_net is not None else 0,
                    "平均ROAS": item.avg_roas,
                    "平均CPI": item.avg_cpi,
                    "主投渠道": item.top_channel,
                    "风险段": item.risk_segment,
                    "回本状态": item.payback_gate,
                    "生命周期阶段": lc.get("lifecycle_stage", ""),
                    "增长潜力": lc.get("predicted_growth_potential", 0),
                    "风险等级": item.risk_judgement,
                    "置信度": item.confidence_level,
                    "建议动作": item.suggested_action,
                    "预测建议": item.forecast_recommendation,
                    "利润结构": item.profit_split,
                    # Phase 3: 回本曲线 + 动态保底线
                    "静态保本D7": pb.get("static_break_even_d7", 0),
                    "静态保本D30": pb.get("static_break_even_d30", 0),
                    "动态保本D7": pb.get("dynamic_break_even_d7", 0),
                    "动态保本D30": pb.get("dynamic_break_even_d30", 0),
                    "当前D7": pb.get("current_d7", 0),
                    "当前CPI": pb.get("current_cpi", 0),
                    "D1留存": pb.get("current_retention_d1", 0),
                    "当前ARPU": pb.get("current_arpu", 0),
                    "当前ARPPU": pb.get("current_arppu", 0),
                    "回本判断": pb.get("judgement", ""),
                    "生命周期风险分": lc.get("lifecycle_risk_score", 0),
                    "回本比例": lc.get("payback_ratio", 0),
                    "质量得分": lc.get("quality_score", 0),
                    "早期放量潜力": lc.get("early_scale_potential", 0),
                    "素材集群数": lc.get("creative_cluster_count", 0),
                    "最大集群扩展性": lc.get("max_cluster_scalability", 0),
                    "疲劳信号数": lc.get("fatigue_signal_count", 0),
                }
            )
        return records

    # ------------------------------------------------------------------
    # Table 3: Campaign 明细表
    # ------------------------------------------------------------------

    def _build_campaign_records(
        self, digest: WeeklyDigest
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in digest.campaign_items:
            # Phase 4: 从 campaign 名或 segment_scope 推导商店
            store = self._extract_store(item.campaign, item.segment_scope)
            records.append(
                {
                    "项目名称": item.game,
                    "渠道": item.channel,
                    "Campaign名称": item.campaign,
                    "国家": item.country,
                    "商店": store,
                    "花费": item.spend,
                    "收入": item.revenue,
                    "ROI": item.roi,
                    "CPI": 0,  # CampaignDigestItem 无此字段，后续从原始数据补
                    "CTR": 0,
                    "安装数": 0,
                    "D1留存": 0,
                    "D7留存": 0,
                    "花费环比": "",
                    "回本门禁": item.payback_gate,
                    "置信度": item.confidence_level,
                    "风险判断": item.risk_judgement,
                    "建议动作": item.suggested_action,
                    "问题描述": item.problem,
                    "原因": item.reason,
                    "负责人": item.action_owner,
                    "截止日期": item.action_due_date,
                    "验收指标": item.verification_metric,
                }
            )
        return records

    # ------------------------------------------------------------------
    # Table 4: 素材分析表
    # ------------------------------------------------------------------

    def _build_creative_records(
        self,
        digest: WeeklyDigest,
        creative_fatigue_payload: dict[str, Any],
        lifecycle_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        # Phase 2: 直接从 creative_fatigue JSON 取数，只取 fatigue + watch 状态
        raw_fatigue = creative_fatigue_payload.get("items", [])
        if isinstance(raw_fatigue, dict):
            raw_fatigue = list(raw_fatigue.values())
        # lifecycle lookup
        raw_lc = lifecycle_payload.get("items", [])
        if isinstance(raw_lc, list):
            lifecycle_items = {it.get("project_key", it.get("project", "")): it for it in raw_lc if isinstance(it, dict)}
        else:
            lifecycle_items = raw_lc

        records: list[dict[str, Any]] = []
        for fc in raw_fatigue:
            if not isinstance(fc, dict):
                continue
            status = fc.get("status", "")
            if status not in ("fatigue", "watch"):
                continue
            project = fc.get("project", "")
            project_key = self._project_key(project)
            lc = lifecycle_items.get(project_key, {})
            # 疲劳原因和建议都是 list，转成文本
            reason_list = fc.get("reason", [])
            if isinstance(reason_list, list):
                reason_text = "; ".join(str(r) for r in reason_list)
            else:
                reason_text = str(reason_list or "")
            suggestion_list = fc.get("suggestion", [])
            if isinstance(suggestion_list, list):
                suggestion_text = "; ".join(str(s) for s in suggestion_list)
            else:
                suggestion_text = str(suggestion_list or "")

            # 风险等级从 status 推导
            if status == "fatigue":
                risk_level = "疲劳素材，需立即替换"
                sample_status = "有效样本"
                confidence = "高"
            else:
                risk_level = "观察素材，持续监控"
                sample_status = "有效样本"
                confidence = "中"

            records.append(
                {
                    "素材ID": fc.get("creative_id", ""),
                    "素材名称": fc.get("creative_name", ""),
                    "素材类型": f"{project} / {fc.get('channel', '')}",
                    "项目": project,
                    "渠道": fc.get("channel", ""),
                    "国家": fc.get("country", ""),
                    "CTR": fc.get("ctr", 0),
                    "ROAS": fc.get("roi", 0),  # fatigue JSON 用 roi 字段
                    "花费": fc.get("spend", 0),
                    "安装数": fc.get("installs", 0),
                    "收入": fc.get("revenue", 0),
                    "CPI": fc.get("cpi", 0),
                    "CPM": 0,  # fatigue JSON 无 CPM
                    "样本状态": sample_status,
                    "疲劳状态": status,
                    "CTR降幅": fc.get("ctr_drop_pct", 0),
                    "CPI涨幅": fc.get("cpi_rise_pct", 0),
                    "ROI变化": fc.get("roi_change_pct", 0),
                    "上周花费": fc.get("previous_spend", 0),
                    "上周ROI": fc.get("previous_roi", 0),
                    "上周CTR": fc.get("previous_ctr", 0),
                    "上周CPI": fc.get("previous_cpi", 0),
                    "生命周期": lc.get("lifecycle_stage", ""),
                    "Hook类型": "",
                    "风险等级": risk_level,
                    "建议动作": suggestion_text,
                    "疲劳原因": reason_text,
                    "修复建议": suggestion_text,
                    "置信度": confidence,
                }
            )
        return records

    # ------------------------------------------------------------------
    # Table 5: 决策分布表
    # ------------------------------------------------------------------

    def _build_decision_records(
        self, decision_payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        items = decision_payload.get("items", [])
        records: list[dict[str, Any]] = []
        for item in items:
            records.append(
                {
                    "实体类型": item.get("entity_type", ""),
                    "实体ID": item.get("entity_id", ""),
                    "项目": item.get("project", ""),
                    "范围": item.get("scope", ""),
                    "决策类别": item.get("decision", ""),
                    "增长得分": item.get("final_growth_score", 0),
                    "风险得分": item.get("final_risk_score", 0),
                    "花费": item.get("spend", 0),
                    "收入": item.get("revenue", 0),
                    "ROI": item.get("roi", 0),
                    "置信度": item.get("confidence", 0),
                    "增长阶段": item.get("growth_stage", ""),
                    "推荐动作": item.get("recommended_action", ""),
                    # -- Phase 1: 13维权重拆解 --
                    "原始增长优先级": item.get("growth_priority", 0),
                    "原始风险优先级": item.get("risk_priority", 0),
                    "生命周期阶段": item.get("lifecycle_stage", ""),
                    "生命周期增长潜力": item.get("lifecycle_growth_potential", 0),
                    "生命周期风险分": item.get("lifecycle_risk_score", 0),
                    "生命周期决策输入": item.get("lifecycle_decision_input", ""),
                    "战略对齐分": item.get("strategy_alignment_score", 0),
                    "战略护栏风险": item.get("strategy_guardrail_risk", 0),
                    "战略护栏阻断": "是" if item.get("strategy_blocked_by_guardrail") else "否",
                    "剧本增长偏置": item.get("playbook_growth_bias", 0),
                    "剧本风险偏置": item.get("playbook_risk_bias", 0),
                    "动作信号": item.get("recommended_action_signal", ""),
                    "预算变化信号": item.get("budget_change_signal", ""),
                    # -- 信号链 --
                    "正向信号": "; ".join(item.get("top_positive_signals", [])),
                    "负向信号": "; ".join(item.get("top_negative_signals", [])),
                    "引用子模块": "; ".join(item.get("source_modules", [])),
                }
            )
        return records

    # ------------------------------------------------------------------
    # Table 6: 行动追踪表
    # ------------------------------------------------------------------

    def _build_action_records(
        self,
        action_items: list[ActionItem],
        decision_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        decision_map = self._build_decision_lookup(decision_payload)
        records: list[dict[str, Any]] = []
        for item in action_items:
            matched = decision_map.get(item.title, {})
            records.append(
                {
                    "Task ID": item.task_id,
                    "Source Meeting": item.source_meeting,
                    "Type": item.action_type,
                    "Title": item.title,
                    "Owner": item.owner,
                    "Status": item.status,
                    "Acceptance Metric": item.acceptance_metric,
                    "Due Date": item.due_date.isoformat() if item.due_date else "",
                    "Description": item.description,
                    "Latest Note": item.latest_note,
                    "Decision Context": matched.get("decision", ""),
                    "Priority Score": matched.get("final_growth_score", 0),
                    # -- Phase 5: 闭环回填 --
                    "完成日期": "",
                    "实际结果": "",
                    "验收值": "",
                    "创建日期": item.due_date.isoformat() if item.due_date else "",
                }
            )
        return records

    # ------------------------------------------------------------------
    # Chart data for HTML report
    # ------------------------------------------------------------------

    def _build_chart_data(
        self,
        digest: WeeklyDigest,
        decision_payload: dict[str, Any],
        creative_fatigue_payload: dict[str, Any],
        dynamic_payback_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 1) 项目花费与收入对比
        project_labels = [item.game for item in digest.project_items]
        project_spend = [item.spend for item in digest.project_items]
        project_revenue = [item.total_revenue for item in digest.project_items]

        # 2) 项目 ROI 对比
        project_roi_values = [item.project_roi for item in digest.project_items]

        # 3) 决策分布
        decision_items = decision_payload.get("items", [])
        decision_counts: dict[str, int] = {}
        for di in decision_items:
            cat = di.get("decision", "unknown")
            decision_counts[cat] = decision_counts.get(cat, 0) + 1

        # 4) 渠道花费分布
        channel_spend: dict[str, float] = {}
        for item in digest.campaign_items:
            ch = item.channel or "Unknown"
            channel_spend[ch] = channel_spend.get(ch, 0) + item.spend

        # 5) 素材 ROAS Top 10 — 从 creative_fatigue 取
        raw_fatigue_chart = creative_fatigue_payload.get("items", [])
        if isinstance(raw_fatigue_chart, dict):
            fatigue_iter = list(raw_fatigue_chart.values())
        else:
            fatigue_iter = raw_fatigue_chart

        # 疲劳分布
        fatigue_counts: dict[str, int] = {"fatigue": 0, "watch": 0, "metric_missing": 0}
        for f_item in fatigue_iter:
            if not isinstance(f_item, dict):
                continue
            status = f_item.get("status", "metric_missing")
            if status in fatigue_counts:
                fatigue_counts[status] += 1

        # Top 10 疲劳素材 CTR 降幅
        fatigue_with_ctr = [
            f for f in fatigue_iter
            if isinstance(f, dict) and f.get("status") == "fatigue"
        ]
        fatigue_with_ctr.sort(key=lambda x: x.get("ctr_drop_pct", 0), reverse=True)
        top_fatigue_labels = [
            f.get("creative_name", f.get("creative_id", f"素材{i+1}"))
            for i, f in enumerate(fatigue_with_ctr[:10])
        ]
        top_fatigue_ctr_drops = [f.get("ctr_drop_pct", 0) for f in fatigue_with_ctr[:10]]

        # 6) 决策 13 维雷达 — 取第一个 project 级别 decision item 的维度
        radar_dims = [
            "growth", "roi_payback", "quality_confidence", "fatigue_risk",
            "attribution_confidence", "lifecycle_potential", "lifecycle_risk",
            "strategy_alignment", "strategy_guardrail_risk",
            "playbook_growth_bias", "playbook_risk_bias",
            "playbook_candidate_growth_bias", "playbook_candidate_risk_bias",
        ]
        radar_labels = [
            "增长", "ROI回本", "质量置信", "疲劳风险", "归因置信",
            "生命周期潜力", "生命周期风险", "战略对齐", "战略护栏风险",
            "剧本增长偏置", "剧本风险偏置",
            "候选增长偏置", "候选风险偏置",
        ]
        project_decisions = [
            d for d in decision_items if d.get("entity_type") == "project"
        ][:5]
        radar_datasets = []
        for d in project_decisions:
            values = [
                d.get("growth_priority", 0),
                d.get("final_growth_score", 0),
                d.get("confidence", 0),
                -(d.get("lifecycle_risk_score", 0)),
                0.05,  # attribution_confidence default
                d.get("lifecycle_growth_potential", 0),
                -(d.get("lifecycle_risk_score", 0)),
                d.get("strategy_alignment_score", 0),
                -(d.get("strategy_guardrail_risk", 0)),
                d.get("playbook_growth_bias", 0),
                -(d.get("playbook_risk_bias", 0)),
                d.get("playbook_candidate_growth_bias", 0),
                -(d.get("playbook_candidate_risk_bias", 0)),
            ]
            radar_datasets.append({
                "label": d.get("entity_id", ""),
                "values": values,
            })

        # 7) 动态保底线对比 — 从 dynamic_payback_payload
        payback_items = (dynamic_payback_payload or {}).get("items", [])
        if isinstance(payback_items, list):
            payback_iter = payback_items
        elif isinstance(payback_items, dict):
            payback_iter = list(payback_items.values())
        else:
            payback_iter = []
        payback_labels = [p.get("project", "") for p in payback_iter if isinstance(p, dict)]
        payback_static_d7 = [p.get("static_break_even_d7", 0) for p in payback_iter if isinstance(p, dict)]
        payback_dynamic_d7 = [p.get("dynamic_break_even_d7", 0) for p in payback_iter if isinstance(p, dict)]
        payback_current_d7 = [p.get("current_d7", 0) for p in payback_iter if isinstance(p, dict)]

        # 8) 行动追踪漏斗
        action_status_counts: dict[str, int] = {
            "待确认": 0, "执行中": 0, "已完成": 0, "已验收": 0,
        }
        for item in digest.action_items if hasattr(digest, "action_items") else []:
            status = item.status if hasattr(item, "status") else "待确认"
            if status in action_status_counts:
                action_status_counts[status] += 1

        return {
            "project_spend_revenue": {
                "labels": project_labels,
                "spend": project_spend,
                "revenue": project_revenue,
            },
            "project_roi_comparison": {
                "labels": project_labels,
                "roi_values": project_roi_values,
            },
            "decision_distribution": {
                "categories": list(decision_counts.keys()),
                "counts": list(decision_counts.values()),
            },
            "channel_spend_breakdown": {
                "labels": list(channel_spend.keys()),
                "values": list(channel_spend.values()),
            },
            "creative_roas_top10": {
                "labels": top_fatigue_labels if top_fatigue_labels else [f"素材{i+1}" for i in range(10)],
                "values": top_fatigue_ctr_drops if top_fatigue_ctr_drops else [0]*10,
            },
            "fatigue_distribution": {
                "labels": list(fatigue_counts.keys()),
                "counts": list(fatigue_counts.values()),
            },
            "kpi_summary": {
                m.label: m.value for m in digest.company_metrics
            },
            # -- Phase 6: 新图表数据 --
            "decision_radar": {
                "labels": radar_labels,
                "datasets": radar_datasets,
            },
            "fatigue_ctr_drop_top10": {
                "labels": top_fatigue_labels if top_fatigue_labels else [f"素材{i+1}" for i in range(10)],
                "values": top_fatigue_ctr_drops if top_fatigue_ctr_drops else [0]*10,
            },
            "dynamic_payback_comparison": {
                "labels": payback_labels,
                "static_d7": payback_static_d7,
                "dynamic_d7": payback_dynamic_d7,
                "current_d7": payback_current_d7,
            },
            "action_funnel": {
                "labels": list(action_status_counts.keys()),
                "counts": list(action_status_counts.values()),
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _project_key(game: str) -> str:
        text = (game or "").strip()
        if not text:
            return ""
        match = re.search(r"\bP0*([0-9]+)\b", text.upper())
        if match:
            return f"P{int(match.group(1)):02d}"
        simplified = re.sub(r"(?i)\bamazon\b", "", text)
        simplified = re.sub(r"\s+", " ", simplified).strip(" -")
        return simplified or text

    @staticmethod
    def _parse_metric_value(text: str) -> float:
        if not text:
            return 0.0
        match = re.search(r"[\d,]+\.?\d*", text)
        if not match:
            return 0.0
        try:
            return float(match.group().replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _extract_change_pct(text: str) -> str:
        """从 '17494 (-0.3%)' 这样的值里提取百分比变化部分."""
        if not text:
            return ""
        match = re.search(r"\(([^)]+)\)", text)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_store(campaign_name: str, segment_scope: str = "") -> str:
        """从 campaign 名或 segment_scope 推导商店平台."""
        text = f"{campaign_name} {segment_scope}".upper()
        if "ANDROID" in text or "GOOGLE" in text:
            return "Android"
        if "IOS" in text or "APPLE" in text:
            return "iOS"
        if "AMAZON" in text:
            return "Amazon"
        return ""

    @staticmethod
    def _build_decision_lookup(
        decision_payload: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for item in decision_payload.get("items", []):
            entity_id = item.get("entity_id", "")
            scope = item.get("scope", "")
            if entity_id:
                lookup[entity_id] = item
            if scope:
                lookup[scope] = item
        return lookup
