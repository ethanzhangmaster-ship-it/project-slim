from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from market_ops.config import Settings
from market_ops.models import CreativeAssetRow
from market_ops.pipeline import DataRepository


PAID_CHANNELS = {"Facebook", "Google", "Apple Search", "Applovin", "Unity Ads", "TikTok"}
MIN_EFFECTIVE_SPEND = 100
MIN_EFFECTIVE_INSTALLS = 30
STOP_LOSS_SPEND = 150
STOP_LOSS_ROI = 0.35
SCALE_ROI = 1.15


@dataclass(slots=True)
class CreativeAnalysisItem:
    project: str
    country: str
    channel: str
    creative_id: str
    creative_name: str
    identity_level: str
    campaign: str
    campaign_id: str
    adgroup: str
    adgroup_id: str
    source_name: str
    source_id: str
    spend: float
    installs: float
    revenue: float
    roi: float
    sample_status: str
    confidence_level: str
    decision_status: str
    risk_judgement: str
    suggested_action: str


class AdjustCreativeAnalysisBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = _align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        creative_rows = self._repo.load_adjust_creative_library(window_start, report_date)
        paid_creative_rows = [
            row for row in creative_rows
            if _normalize_channel(row.channel) in PAID_CHANNELS and row.spend > 0
        ]
        items = [self._build_item(row) for row in paid_creative_rows]
        items.sort(key=lambda item: (_sample_rank(item), item.roi, item.spend, item.revenue), reverse=True)

        payload = self._build_payload(
            report_date=report_date,
            window_start=window_start,
            raw_rows=len(rows),
            creative_rows=items,
        )

        markdown_path = output_dir / f"adjust_creative_analysis_{suffix}.md"
        json_path = output_dir / f"adjust_creative_analysis_{suffix}.json"
        csv_path = output_dir / f"adjust_creative_analysis_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, items)
        return {"summary": markdown_path, "json": json_path, "csv": csv_path}

    def _build_item(self, row: CreativeAssetRow) -> CreativeAnalysisItem:
        channel = _normalize_channel(row.channel)
        revenue = float(row.revenue_value or 0.0)
        spend = float(row.spend or 0.0)
        installs = float(row.installs or 0.0)
        roi = revenue / spend if spend else float(row.roas or 0.0)
        identity_level = _identity_level(row)
        sample_status = "有效样本" if spend >= MIN_EFFECTIVE_SPEND or installs >= MIN_EFFECTIVE_INSTALLS else "观察样本"
        confidence_level = _confidence_level(channel, identity_level, sample_status)
        decision_status, risk_judgement, suggested_action = _risk_and_action(
            roi=roi,
            spend=spend,
            sample_status=sample_status,
            confidence_level=confidence_level,
            identity_level=identity_level,
        )
        return CreativeAnalysisItem(
            project=row.game,
            country=row.country or "Global",
            channel=channel,
            creative_id=row.asset_id,
            creative_name=row.creative_name or row.asset_id,
            identity_level=identity_level,
            campaign=row.campaign,
            campaign_id=row.campaign_id,
            adgroup=row.adgroup,
            adgroup_id=row.adgroup_id,
            source_name=row.source_name,
            source_id=row.source_id,
            spend=round(spend, 2),
            installs=round(installs, 2),
            revenue=round(revenue, 2),
            roi=round(roi, 4),
            sample_status=sample_status,
            confidence_level=confidence_level,
            decision_status=decision_status,
            risk_judgement=risk_judgement,
            suggested_action=suggested_action,
        )

    def _build_payload(
        self,
        *,
        report_date: date,
        window_start: date,
        raw_rows: int,
        creative_rows: list[CreativeAnalysisItem],
    ) -> dict:
        effective = [item for item in creative_rows if item.sample_status == "有效样本"]
        observations = [item for item in creative_rows if item.sample_status == "观察样本"]
        by_project_channel = self._group_items(creative_rows, ("project", "channel"))
        by_project_channel_country = self._group_items(creative_rows, ("project", "channel", "country"))
        top_effective = sorted(
            effective,
            key=lambda item: (item.roi, item.spend, item.revenue),
            reverse=True,
        )[:20]
        high_spend_risks = sorted(
            [item for item in effective if item.roi < 0.5],
            key=lambda item: (item.spend, -item.roi),
            reverse=True,
        )[:20]
        google_proxy_spend = sum(item.spend for item in creative_rows if item.channel == "Google" and "proxy" in item.identity_level.lower())
        google_spend = sum(item.spend for item in creative_rows if item.channel == "Google")
        facebook_spend = sum(item.spend for item in creative_rows if item.channel == "Facebook")
        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "source": "Adjust API revenue breakdown",
            "rules": {
                "effective_sample": f"7日累计 spend >= {MIN_EFFECTIVE_SPEND} or installs >= {MIN_EFFECTIVE_INSTALLS}",
                "decision_rule": "加量/关闭必须基于7日累计样本，不按单日波动作强结论",
                "stop_loss_rule": f"有效样本且 spend >= {STOP_LOSS_SPEND} 且 ROI < {STOP_LOSS_ROI}",
                "scale_rule": f"有效样本且 ROI >= {SCALE_ROI}",
                "low_confidence_rule": "低可信度或观察样本不输出强复制/强停测结论",
            },
            "summary": {
                "raw_adjust_rows": raw_rows,
                "creative_rows": len(creative_rows),
                "paid_creative_rows": len(creative_rows),
                "effective_samples": len(effective),
                "observation_samples": len(observations),
                "facebook_spend": round(facebook_spend, 2),
                "google_spend": round(google_spend, 2),
                "google_proxy_spend_share": round(google_proxy_spend / google_spend, 4) if google_spend else 0.0,
            },
            "project_channel_summary": by_project_channel,
            "project_channel_country_summary": by_project_channel_country[:30],
            "top_effective_creatives": [asdict(item) for item in top_effective],
            "high_spend_risks": [asdict(item) for item in high_spend_risks],
            "observation_samples": [asdict(item) for item in sorted(observations, key=lambda item: item.spend, reverse=True)[:20]],
            "all_items": [asdict(item) for item in creative_rows],
        }

    @staticmethod
    def _group_items(items: list[CreativeAnalysisItem], fields: tuple[str, ...]) -> list[dict]:
        buckets: dict[tuple[str, ...], dict] = {}
        for item in items:
            key = tuple(str(getattr(item, field) or "") for field in fields)
            bucket = buckets.setdefault(
                key,
                {
                    **{field: key[index] for index, field in enumerate(fields)},
                    "spend": 0.0,
                    "installs": 0.0,
                    "revenue": 0.0,
                    "creative_count": 0,
                    "effective_samples": 0,
                    "proxy_samples": 0,
                },
            )
            bucket["spend"] += item.spend
            bucket["installs"] += item.installs
            bucket["revenue"] += item.revenue
            bucket["creative_count"] += 1
            if item.sample_status == "有效样本":
                bucket["effective_samples"] += 1
            if "proxy" in item.identity_level.lower():
                bucket["proxy_samples"] += 1
        rows = []
        for bucket in buckets.values():
            spend = float(bucket["spend"])
            revenue = float(bucket["revenue"])
            bucket["spend"] = round(spend, 2)
            bucket["installs"] = round(float(bucket["installs"]), 2)
            bucket["revenue"] = round(revenue, 2)
            bucket["roi"] = round(revenue / spend, 4) if spend else 0.0
            rows.append(bucket)
        return sorted(rows, key=lambda item: (item["spend"], item["revenue"]), reverse=True)

    def _render_markdown(self, payload: dict) -> str:
        summary = payload["summary"]
        lines = [
            f"# Adjust 素材分析 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}（上周四到本周三）",
            "- 数据源：Adjust API revenue breakdown，按 campaign/adgroup/creative/source 维度聚合。",
            "- 口径：只分析本周有花费的素材/代理素材；花费为 0 的历史回收行不进入素材 ROI 排名。",
            f"- 样本规则：7日累计花费 >= {MIN_EFFECTIVE_SPEND} 美元 或 安装 >= {MIN_EFFECTIVE_INSTALLS} 才算有效样本；未过门槛统一标记为观察样本。",
            "- 结论规则：Campaign/素材动作基于多日累计表现，不按单日波动直接关闭或加量。",
            f"- 止损规则：有效样本且花费 >= {STOP_LOSS_SPEND}、ROI < {STOP_LOSS_ROI} 才进入降权/停测复核；低可信度先复核归因。",
            f"- 加量规则：有效样本且 ROI >= {SCALE_ROI} 才进入加量候选，仍需看对应商店+渠道回收门槛。",
            "",
            "## 数据概览",
            "",
            f"- Adjust 原始明细行：{summary['raw_adjust_rows']}",
            f"- 本周有花费的素材/代理素材聚合行：{summary['paid_creative_rows']}",
            f"- 有效样本：{summary['effective_samples']}；观察样本：{summary['observation_samples']}",
            f"- Facebook 花费：{summary['facebook_spend']:.2f}",
            f"- Google 花费：{summary['google_spend']:.2f}",
            f"- Google 代理素材花费占比：{summary['google_proxy_spend_share']:.1%}",
            "",
            "## 项目 × 渠道汇总",
            "",
            "| 项目 | 渠道 | 花费 | 安装 | 收入 | ROI | 素材数 | 有效样本 | 代理样本 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in payload["project_channel_summary"][:20]:
            lines.append(
                f"| {item.get('project', '')} | {item.get('channel', '')} | {item['spend']:.2f} | {item['installs']:.0f} | {item['revenue']:.2f} | {item['roi']:.2f} | {item['creative_count']} | {item['effective_samples']} | {item['proxy_samples']} |"
            )
        lines.extend(["", "## 有效样本 Top 素材", ""])
        lines.extend(self._render_item_table(payload["top_effective_creatives"][:15]))
        lines.extend(["", "## 高花费低回收风险素材", ""])
        if payload["high_spend_risks"]:
            lines.extend(self._render_item_table(payload["high_spend_risks"][:15]))
        else:
            lines.append("- 当前没有达到有效样本且 ROI < 0.50 的高花费素材。")
        lines.extend(["", "## 观察样本", ""])
        lines.extend(self._render_item_table(payload["observation_samples"][:10]))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_item_table(items: list[dict]) -> list[str]:
        if not items:
            return ["- 暂无。"]
        lines = [
            "| 项目 | 渠道 | 国家 | 素材ID | 素材名 | 身份层级 | 花费 | 安装 | 收入 | ROI | 样本 | 可信度 | 决策 | 建议 |",
            "|---|---|---|---|---|---|---:|---:|---:|---:|---|---|---|---|",
        ]
        for item in items:
            lines.append(
                f"| {item['project']} | {item['channel']} | {item['country']} | `{item['creative_id']}` | {item['creative_name']} | {item['identity_level']} | {item['spend']:.2f} | {item['installs']:.0f} | {item['revenue']:.2f} | {item['roi']:.2f} | {item['sample_status']} | {item['confidence_level']} | {item['decision_status']} | {item['suggested_action']} |"
            )
        return lines

    @staticmethod
    def _write_csv(path: Path, items: list[CreativeAnalysisItem]) -> None:
        fieldnames = list(asdict(items[0]).keys()) if items else list(CreativeAnalysisItem.__dataclass_fields__.keys())
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow(asdict(item))


def _align_to_wednesday(report_date: date) -> date:
    weekday = report_date.weekday()
    target = 2
    delta = (weekday - target) % 7
    return report_date - timedelta(days=delta)


def _normalize_channel(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "google" in normalized:
        return "Google"
    if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized or "meta" in normalized:
        return "Facebook"
    if "apple" in normalized or "asa" in normalized:
        return "Apple Search"
    if "applovin" in normalized:
        return "Applovin"
    if "unity" in normalized:
        return "Unity Ads"
    if "tiktok" in normalized or "bytedance" in normalized:
        return "TikTok"
    return value or "Unknown"


def _identity_level(row: CreativeAssetRow) -> str:
    creative_type = str(row.creative_type or "").lower()
    if "source proxy" in creative_type:
        return "source_proxy"
    if "adgroup proxy" in creative_type:
        return "adgroup_proxy"
    if "campaign proxy" in creative_type:
        return "campaign_proxy"
    return "creative_id"


def _confidence_level(channel: str, identity_level: str, sample_status: str) -> str:
    if sample_status == "观察样本":
        return "低"
    if channel == "Google" and identity_level != "creative_id":
        return "中"
    return "高"


def _risk_and_action(
    *,
    roi: float,
    spend: float,
    sample_status: str,
    confidence_level: str,
    identity_level: str,
) -> tuple[str, str, str]:
    if sample_status == "观察样本":
        return "观察", "样本不足，不能直接判断优劣", "继续小额验证，先跑够7日累计样本"
    if confidence_level == "低":
        return "归因复核", "低可信度，仅观察", "先补归因字段，再进入动作判断"
    if identity_level != "creative_id":
        if roi >= 1.0:
            return "加量候选复核", "代理素材表现正向，但非原生 creative id", "保留观察，优先补素材ID映射"
        if spend >= STOP_LOSS_SPEND and roi < STOP_LOSS_ROI:
            return "降权复核", "代理素材低回收，但非原生 creative id", "先按 Campaign/Adgroup 定位问题，不直接停素材"
        return "观察", "代理素材未证明有效", "继续看多日累计回收，不按单日停素材"
    if roi >= SCALE_ROI:
        return "加量候选", "有效样本且 ROI 稳定过线", "进入复核名单，可做变体方向并小幅加量测试"
    if roi >= 0.5:
        return "观察", "有效样本但 ROI 未过线", "保留观察，继续看后续回收"
    if spend >= STOP_LOSS_SPEND and roi < STOP_LOSS_ROI:
        return "降权/停测复核", "有效样本持续低回收", "归因复核后降权或关闭，避免继续亏损"
    return "限额验证", "有效样本低回收但未达止损花费", "限额继续验证，不新增预算"


def _sample_rank(item: CreativeAnalysisItem) -> int:
    return 1 if item.sample_status == "有效样本" else 0
