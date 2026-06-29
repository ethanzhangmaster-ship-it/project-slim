from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.models import CreativeAssetRow, RevenueBreakdownRow
from market_ops.payback_targets import PaybackTargetsBuilder, ProjectTargets
from market_ops.pipeline import DataRepository


MIN_CAMPAIGN_SPEND = 100.0
MIN_CREATIVE_SPEND = 100.0
MIN_CREATIVE_INSTALLS = 30.0
LOCAL_BREAKTHROUGH_ROI = 1.20
CREATIVE_SCALE_ROI = 1.15
PROJECT_SCALE_ROI = 1.05


@dataclass(slots=True)
class GrowthPriorityItem:
    entity_type: str
    entity_id: str
    project: str
    scope: str
    growth_stage: str
    growth_priority: float
    risk_priority: float
    spend: float
    revenue: float
    roi: float
    recommended_action: str
    budget_change: str
    confidence: str
    reason: list[str]
    guardrails: list[str]


@dataclass(slots=True)
class GrowthPrioritiesResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class GrowthPrioritiesBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> GrowthPrioritiesResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"growth_priorities_{suffix}.md"
        json_path = output_dir / f"growth_priorities_{suffix}.json"
        csv_path = output_dir / f"growth_priorities_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return GrowthPrioritiesResult(
            markdown_path=markdown_path,
            json_path=json_path,
            csv_path=csv_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        window_start = report_date - timedelta(days=6)
        breakdown_rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        creative_rows = self._repo.load_adjust_creative_library(window_start, report_date)
        payback_targets = self._load_payback_targets_map(report_date)

        project_spend = self._project_spend_map(breakdown_rows)
        project_roi = self._project_roi_map(breakdown_rows)
        project_items = self._build_project_items(breakdown_rows, payback_targets)
        campaign_items = self._build_campaign_items(breakdown_rows, project_spend, project_roi)
        creative_items = self._build_creative_items(creative_rows, project_roi)
        items = project_items + campaign_items + creative_items
        items.sort(key=lambda item: (item.growth_priority, item.roi, item.spend), reverse=True)

        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": True,
            "rules": {
                "campaign_local_breakthrough": {
                    "min_spend": MIN_CAMPAIGN_SPEND,
                    "min_roi": LOCAL_BREAKTHROUGH_ROI,
                    "purpose": "项目整体偏弱时，允许已过样本门槛的局部赢家做小额扩量验证。",
                },
                "creative_scale_candidate": {
                    "min_spend": MIN_CREATIVE_SPEND,
                    "min_installs": MIN_CREATIVE_INSTALLS,
                    "min_roi": CREATIVE_SCALE_ROI,
                    "purpose": "素材候选先进入复制和小额测试，不直接作为无护栏放量依据。",
                },
            },
            "summary": self._build_summary(items),
            "top_growth_candidates": [asdict(item) for item in items if item.growth_priority >= 0.65][:20],
            "repair_or_downweight": [asdict(item) for item in sorted(items, key=lambda item: (item.risk_priority, item.spend), reverse=True) if item.risk_priority >= 0.65][:20],
            "items": [asdict(item) for item in items],
        }

    def _build_project_items(
        self,
        rows: list[RevenueBreakdownRow],
        payback_targets: dict[str, ProjectTargets],
    ) -> list[GrowthPriorityItem]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            project = _project_label(row.game)
            if not project:
                continue
            bucket = buckets.setdefault(project, {"spend": 0.0, "revenue": 0.0})
            bucket["spend"] += _cost(row)
            bucket["revenue"] += _revenue(row)

        items: list[GrowthPriorityItem] = []
        for project, metrics in buckets.items():
            spend = metrics["spend"]
            revenue = metrics["revenue"]
            if spend <= 0:
                continue
            roi = revenue / spend
            project_code = _project_code(project)
            payback_target = payback_targets.get(project_code)
            current_d7, d7_floor = self._payback_d7(payback_target)
            reasons = [f"7日总收入ROI={roi:.2f}", f"7日花费={spend:.0f}"]
            if d7_floor is not None and current_d7 is not None:
                reasons.append(f"项目D7={current_d7:.2f}，历史保底线={d7_floor:.2f}")

            if roi >= PROJECT_SCALE_ROI and (d7_floor is None or current_d7 is None or current_d7 >= d7_floor):
                stage = "成长期"
                growth_priority = min(0.95, 0.62 + (roi - 1.0) * 0.25 + min(spend / 5000.0, 0.12))
                risk_priority = max(0.05, 0.35 - (roi - 1.0) * 0.2)
                action = "优先保留预算，并从下层Campaign/素材里挑局部扩量对象"
                budget_change = "+0%到+10%"
            elif roi >= 1.0:
                stage = "稳定验证期"
                growth_priority = min(0.78, 0.55 + (roi - 1.0) * 0.2)
                risk_priority = 0.35
                action = "维持预算，等待局部赢家小额突破"
                budget_change = "+0%"
            else:
                stage = "修复期"
                growth_priority = max(0.25, min(0.58, roi * 0.45))
                risk_priority = min(0.95, 0.55 + (1.0 - roi) * 0.35)
                action = "不做项目级加预算，优先修复低效组合；允许下层局部赢家单独小额验证"
                budget_change = "+0%"

            items.append(
                GrowthPriorityItem(
                    entity_type="project",
                    entity_id=project_code or project,
                    project=project,
                    scope="project",
                    growth_stage=stage,
                    growth_priority=round(growth_priority, 4),
                    risk_priority=round(risk_priority, 4),
                    spend=round(spend, 2),
                    revenue=round(revenue, 2),
                    roi=round(roi, 4),
                    recommended_action=action,
                    budget_change=budget_change,
                    confidence="medium" if payback_target else "low",
                    reason=reasons,
                    guardrails=[
                        "项目级动作不得覆盖Campaign/素材级局部突破判断",
                        "如D3/D7连续恶化，先回撤新增预算",
                        "增长动作必须保留7日累计样本复核",
                    ],
                )
            )
        return items

    def _build_campaign_items(
        self,
        rows: list[RevenueBreakdownRow],
        project_spend: dict[str, float],
        project_roi: dict[str, float],
    ) -> list[GrowthPriorityItem]:
        buckets: dict[tuple[str, str, str, str], dict[str, float]] = {}
        for row in rows:
            project = _project_label(row.game)
            channel = _normalize_channel(row.partner)
            campaign = str(row.campaign or row.campaign_id or "").strip()
            country = str(row.country or "Global").strip() or "Global"
            if not project or not channel or not campaign:
                continue
            key = (project, channel, campaign, country)
            bucket = buckets.setdefault(key, {"spend": 0.0, "revenue": 0.0, "installs": 0.0})
            bucket["spend"] += _cost(row)
            bucket["revenue"] += _revenue(row)
            bucket["installs"] += float(getattr(row, "installs", 0.0) or 0.0)

        items: list[GrowthPriorityItem] = []
        for (project, channel, campaign, country), metrics in buckets.items():
            spend = metrics["spend"]
            revenue = metrics["revenue"]
            if spend < MIN_CAMPAIGN_SPEND:
                continue
            roi = revenue / spend if spend else 0.0
            total_project_spend = project_spend.get(project, 0.0)
            spend_share = spend / total_project_spend if total_project_spend else 0.0
            parent_roi = project_roi.get(project, 0.0)
            is_local_breakthrough = roi >= LOCAL_BREAKTHROUGH_ROI and spend >= MIN_CAMPAIGN_SPEND
            reasons = [
                f"Campaign 7日ROI={roi:.2f}",
                f"花费={spend:.0f}，占项目花费={spend_share:.1%}",
                f"项目整体ROI={parent_roi:.2f}",
            ]
            if is_local_breakthrough:
                stage = "局部突破"
                growth_priority = min(0.98, 0.70 + (roi - LOCAL_BREAKTHROUGH_ROI) * 0.18 + min(spend_share, 0.12))
                risk_priority = 0.25 if parent_roi >= 1.0 else 0.42
                action = "允许小额扩量验证"
                budget_change = "+10%"
                if parent_roi < 1.0:
                    reasons.append("项目整体偏弱，但该Campaign已形成局部ROI优势")
            elif roi >= 1.0:
                stage = "候选观察"
                growth_priority = min(0.68, 0.52 + (roi - 1.0) * 0.15 + min(spend_share, 0.06))
                risk_priority = 0.35
                action = "保留预算，继续观察是否跨过局部突破线"
                budget_change = "+0%"
            else:
                stage = "低效修复"
                growth_priority = max(0.10, roi * 0.35)
                risk_priority = min(0.95, 0.55 + (1.0 - roi) * 0.35 + min(spend_share, 0.12))
                action = "降权或修复成本、国家和素材结构"
                budget_change = "-10%到+0%"

            items.append(
                GrowthPriorityItem(
                    entity_type="campaign",
                    entity_id=campaign,
                    project=project,
                    scope=f"{channel} / {country}",
                    growth_stage=stage,
                    growth_priority=round(growth_priority, 4),
                    risk_priority=round(risk_priority, 4),
                    spend=round(spend, 2),
                    revenue=round(revenue, 2),
                    roi=round(roi, 4),
                    recommended_action=action,
                    budget_change=budget_change,
                    confidence="high" if spend >= 300 else "medium",
                    reason=reasons,
                    guardrails=[
                        "单次预算增幅不超过10%",
                        "连续2日D3代理ROI恶化超过15%则回撤",
                        "若同Campaign下素材疲劳为high，则暂停扩量只保留复制测试",
                    ],
                )
            )
        return items

    def _build_creative_items(
        self,
        rows: list[CreativeAssetRow],
        project_roi: dict[str, float],
    ) -> list[GrowthPriorityItem]:
        items: list[GrowthPriorityItem] = []
        for row in rows:
            project = _project_label(row.game)
            channel = _normalize_channel(row.channel)
            creative_id = str(row.asset_id or row.creative_name or "").strip()
            if not project or not channel or not creative_id:
                continue
            spend = float(row.spend or 0.0)
            installs = float(row.installs or 0.0)
            revenue = float(row.revenue_value or 0.0)
            roi = revenue / spend if spend else float(row.roas or 0.0)
            if spend <= 0:
                continue
            effective = spend >= MIN_CREATIVE_SPEND or installs >= MIN_CREATIVE_INSTALLS
            if not effective and not (roi < 0.35 and spend >= 150):
                continue
            parent_roi = project_roi.get(project, 0.0)
            reasons = [
                f"素材7日ROI={roi:.2f}",
                f"花费={spend:.0f}，安装={installs:.0f}",
                f"项目整体ROI={parent_roi:.2f}",
            ]
            if effective and roi >= CREATIVE_SCALE_ROI:
                stage = "素材复制候选"
                growth_priority = min(0.92, 0.66 + (roi - CREATIVE_SCALE_ROI) * 0.10 + min(spend / 3000.0, 0.10))
                risk_priority = 0.30 if "proxy" not in (row.creative_type or "").lower() else 0.42
                action = "生成变体验证计划，小额进入测试组"
                budget_change = "+0%到+10%"
            elif roi < 0.35 and spend >= 150:
                stage = "素材降权"
                growth_priority = 0.12
                risk_priority = min(0.95, 0.70 + min(spend / 3000.0, 0.15))
                action = "归因复核后降权或停测"
                budget_change = "-10%到-30%"
            else:
                stage = "素材观察"
                growth_priority = 0.35 if effective else 0.22
                risk_priority = 0.45 if effective else 0.30
                action = "继续跑够样本，不进入强复制或强停测"
                budget_change = "+0%"

            items.append(
                GrowthPriorityItem(
                    entity_type="creative",
                    entity_id=creative_id,
                    project=project,
                    scope=f"{channel} / {row.country or 'Global'}",
                    growth_stage=stage,
                    growth_priority=round(growth_priority, 4),
                    risk_priority=round(risk_priority, 4),
                    spend=round(spend, 2),
                    revenue=round(revenue, 2),
                    roi=round(roi, 4),
                    recommended_action=action,
                    budget_change=budget_change,
                    confidence="medium" if effective else "low",
                    reason=reasons,
                    guardrails=[
                        "素材动作先复制模式，不直接替代Campaign预算判断",
                        "代理素材只做方向判断，原生creative id归因不足时不做强结论",
                        "新增变体必须保留原Hook假设和7日样本复核",
                    ],
                )
            )
        return items

    def _load_payback_targets_map(self, report_date: date) -> dict[str, ProjectTargets]:
        try:
            targets, _ = PaybackTargetsBuilder(self._settings).build_targets_data(report_date)
        except Exception:
            return {}
        return {item.project: item for item in targets}

    @staticmethod
    def _payback_d7(payback_target: ProjectTargets | None) -> tuple[float | None, float | None]:
        if not payback_target:
            return None, None
        current_d7 = payback_target.current_recovery.get("D7")
        target = payback_target.recovery_targets.get("D7")
        return current_d7, target.floor if target else None

    @staticmethod
    def _project_spend_map(rows: list[RevenueBreakdownRow]) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in rows:
            project = _project_label(row.game)
            if project:
                result[project] = result.get(project, 0.0) + _cost(row)
        return result

    @staticmethod
    def _project_roi_map(rows: list[RevenueBreakdownRow]) -> dict[str, float]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            project = _project_label(row.game)
            if not project:
                continue
            bucket = buckets.setdefault(project, {"spend": 0.0, "revenue": 0.0})
            bucket["spend"] += _cost(row)
            bucket["revenue"] += _revenue(row)
        return {
            project: (metrics["revenue"] / metrics["spend"] if metrics["spend"] else 0.0)
            for project, metrics in buckets.items()
        }

    @staticmethod
    def _build_summary(items: list[GrowthPriorityItem]) -> dict[str, Any]:
        return {
            "total_items": len(items),
            "scale_candidates": sum(1 for item in items if item.growth_stage in {"成长期", "局部突破", "素材复制候选"}),
            "local_breakthroughs": sum(1 for item in items if item.growth_stage == "局部突破"),
            "repair_or_downweight": sum(1 for item in items if item.risk_priority >= 0.65),
            "top_growth": asdict(items[0]) if items else None,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 增长优先级与局部突破 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}",
            "- 定位：Phase 1 增长策略引擎；输出独立行动建议，不直接执行预算动作。",
            f"- 识别对象：{summary['total_items']} 个；可增长候选：{summary['scale_candidates']} 个；局部突破：{summary['local_breakthroughs']} 个；需修复/降权：{summary['repair_or_downweight']} 个。",
            "",
            "## 最值得加钱或复制",
            "",
        ]
        lines.extend(_render_table(payload["top_growth_candidates"][:15]))
        lines.extend(["", "## 需修复或降权", ""])
        lines.extend(_render_table(payload["repair_or_downweight"][:15]))
        lines.extend(
            [
                "",
                "## 口径说明",
                "",
                f"- Campaign 局部突破：7日花费 >= {MIN_CAMPAIGN_SPEND:.0f} 且 ROI >= {LOCAL_BREAKTHROUGH_ROI:.2f}。",
                f"- 素材复制候选：7日花费 >= {MIN_CREATIVE_SPEND:.0f} 或安装 >= {MIN_CREATIVE_INSTALLS:.0f}，且 ROI >= {CREATIVE_SCALE_ROI:.2f}。",
                "- 项目整体偏弱不再一票否决下层赢家；下层赢家只能进入小额扩量验证，并带回撤护栏。",
                "- 该文件只生成建议，不发送飞书，不改预算。",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fields = [
            "entity_type",
            "entity_id",
            "project",
            "scope",
            "growth_stage",
            "growth_priority",
            "risk_priority",
            "spend",
            "revenue",
            "roi",
            "recommended_action",
            "budget_change",
            "confidence",
            "reason",
            "guardrails",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item in items:
                row = dict(item)
                row["reason"] = " | ".join(str(part) for part in row.get("reason") or [])
                row["guardrails"] = " | ".join(str(part) for part in row.get("guardrails") or [])
                writer.writerow({field: row.get(field, "") for field in fields})


def _render_table(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- 暂无。"]
    lines = [
        "| 对象 | 项目 | 范围 | 阶段 | 增长分 | 风险分 | 花费 | ROI | 建议 | 护栏 |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for item in items:
        guardrail = "；".join((item.get("guardrails") or [])[:2])
        lines.append(
            "| {entity_type}:{entity_id} | {project} | {scope} | {growth_stage} | {growth_priority:.2f} | {risk_priority:.2f} | {spend:.0f} | {roi:.2f} | {recommended_action}（{budget_change}） | {guardrail} |".format(
                guardrail=guardrail,
                **item,
            )
        )
    return lines


def _project_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if not match:
        return text
    code = f"P{int(match.group(1)):02d}"
    suffix = re.sub(r"(?i)^.*?\bP0*[0-9]+\b", "", text).strip(" -_/")
    return f"{code} {suffix}".strip()


def _project_code(value: str) -> str:
    match = re.search(r"\bP0*([0-9]+)\b", str(value or "").upper())
    return f"P{int(match.group(1)):02d}" if match else str(value or "").strip()


def _normalize_channel(value: str) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if "facebook" in lowered or "meta" in lowered or "instagram" in lowered:
        return "Facebook"
    if "google" in lowered or "adwords" in lowered:
        return "Google"
    if "apple" in lowered or "search ads" in lowered:
        return "Apple Search"
    if "applovin" in lowered:
        return "Applovin"
    if "unity" in lowered:
        return "Unity Ads"
    if "tiktok" in lowered or "tik tok" in lowered:
        return "TikTok"
    return text or "Unknown"


def _cost(row: RevenueBreakdownRow) -> float:
    return float(getattr(row, "cost", 0.0) or 0.0)


def _revenue(row: RevenueBreakdownRow) -> float:
    return float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
