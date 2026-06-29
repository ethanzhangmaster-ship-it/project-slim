from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from market_ops.config import Settings
from market_ops.pipeline import DataRepository


PAID_CHANNELS = {"Facebook", "Google", "Apple Search", "Applovin", "Unity Ads"}
INVALID_CREATIVE_SIGNAL_VALUES = {"", "-", "display", "unknown", "(not set)", "nan", "none"}
PRESETS = [
    ("保守", 50.0, 1.00),
    ("平衡", 30.0, 0.90),
    ("激进", 20.0, 0.80),
]


@dataclass(slots=True)
class CreativeCandidate:
    project: str
    channel: str
    creative_id: str
    creative_name: str
    spend: float
    revenue: float

    @property
    def roi(self) -> float:
        return self.revenue / self.spend if self.spend else 0.0

    @property
    def score(self) -> float:
        return self.spend * self.roi

    @property
    def valid_identity(self) -> bool:
        creative_id = (self.creative_id or "").strip().lower()
        creative_name = (self.creative_name or "").strip().lower()
        return creative_id not in INVALID_CREATIVE_SIGNAL_VALUES and creative_name not in INVALID_CREATIVE_SIGNAL_VALUES


class CreativeActionThresholdsBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = _align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        candidates = self._build_candidates(rows, window_start, report_date)
        payload = self._build_payload(report_date, window_start, candidates)

        markdown_path = output_dir / f"creative_action_thresholds_{suffix}.md"
        json_path = output_dir / f"creative_action_thresholds_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "summary": markdown_path,
            "json": json_path,
        }

    def _build_candidates(self, rows, window_start: date, report_date: date) -> list[CreativeCandidate]:
        buckets: dict[tuple[str, str, str, str], CreativeCandidate] = {}
        for row in rows:
            if not (window_start <= row.date <= report_date):
                continue
            if row.cost <= 0:
                continue
            channel = _normalize_channel(row.partner)
            if channel not in PAID_CHANNELS:
                continue
            project = _project_key(row.game)
            creative_id = (getattr(row, "creative_id", "") or "").strip()
            creative_name = (getattr(row, "creative_name", "") or "").strip()
            if not project or not (creative_id or creative_name):
                continue
            key = (project, channel, creative_id or creative_name, creative_name or creative_id)
            if key not in buckets:
                buckets[key] = CreativeCandidate(
                    project=project,
                    channel=channel,
                    creative_id=creative_id or "-",
                    creative_name=creative_name or creative_id or "-",
                    spend=0.0,
                    revenue=0.0,
                )
            item = buckets[key]
            item.spend += float(row.cost)
            item.revenue += float(row.total_revenue_gross)
        return sorted(
            buckets.values(),
            key=lambda item: (item.score, item.spend, item.roi),
            reverse=True,
        )

    def _build_payload(self, report_date: date, window_start: date, candidates: list[CreativeCandidate]) -> dict:
        current_spend = float(getattr(self._settings, "creative_action_min_spend", 50.0))
        current_roi = float(getattr(self._settings, "creative_action_min_roi", 1.0))
        current_pass = self._filter_candidates(candidates, current_spend, current_roi)
        current_near_miss = self._nearest_candidates(candidates, current_spend, current_roi)
        presets = []
        for name, min_spend, min_roi in PRESETS:
            preset_candidates = self._filter_candidates(candidates, min_spend, min_roi)
            presets.append(
                {
                    "name": name,
                    "min_spend": min_spend,
                    "min_roi": min_roi,
                    "count": len(preset_candidates),
                    "projects": sorted({item.project for item in preset_candidates}),
                    "top_candidates": [self._candidate_dict(item) for item in preset_candidates[:10]],
                }
            )
        recommendation = self._recommend_preset(presets)
        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "recommended_profile": recommendation,
            "current_thresholds": {
                "min_spend": current_spend,
                "min_roi": current_roi,
                "pass_count": len(current_pass),
                "projects": sorted({item.project for item in current_pass}),
            },
            "current_top_candidates": [self._candidate_dict(item) for item in current_pass[:10]],
            "current_near_miss_candidates": [
                {
                    **self._candidate_dict(item),
                    "rejection_reason": self._rejection_reason(item, current_spend, current_roi),
                }
                for item in current_near_miss[:10]
            ],
            "preset_results": presets,
            "all_top_candidates": [self._candidate_dict(item) for item in candidates[:20]],
        }

    @staticmethod
    def _recommend_preset(presets: list[dict]) -> dict:
        conservative = next((item for item in presets if item["name"] == "保守"), None)
        balanced = next((item for item in presets if item["name"] == "平衡"), None)
        aggressive = next((item for item in presets if item["name"] == "激进"), None)
        if conservative and balanced and conservative["top_candidates"] == balanced["top_candidates"]:
            reason = "保守版和平衡版选出的素材完全一致，说明当前没有必要为了多拿候选而放松ROI门槛。"
            if aggressive and aggressive["count"] > balanced["count"]:
                reason += " 激进版虽然多出候选，但会放进 ROI 低于 1 的素材，当前不适合自动进入复制动作。"
            return {
                "name": conservative["name"],
                "min_spend": conservative["min_spend"],
                "min_roi": conservative["min_roi"],
                "reason": reason,
            }
        best = max(presets, key=lambda item: (item["count"], item["min_roi"], item["min_spend"]))
        return {
            "name": best["name"],
            "min_spend": best["min_spend"],
            "min_roi": best["min_roi"],
            "reason": "当前按覆盖数量和质量综合取最优档位。",
        }

    @staticmethod
    def _candidate_dict(item: CreativeCandidate) -> dict:
        return {
            "project": item.project,
            "channel": item.channel,
            "creative_id": item.creative_id,
            "creative_name": item.creative_name,
            "spend": round(item.spend, 2),
            "revenue": round(item.revenue, 2),
            "roi": round(item.roi, 2),
        }

    @staticmethod
    def _filter_candidates(candidates: list[CreativeCandidate], min_spend: float, min_roi: float) -> list[CreativeCandidate]:
        result = []
        for item in candidates:
            if item.spend < min_spend:
                continue
            if item.roi < min_roi:
                continue
            if not item.valid_identity:
                continue
            result.append(item)
        return result

    def _nearest_candidates(self, candidates: list[CreativeCandidate], min_spend: float, min_roi: float) -> list[CreativeCandidate]:
        filtered = [item for item in candidates if item.valid_identity]
        return sorted(
            filtered,
            key=lambda item: (
                abs(item.spend - min_spend) + abs(item.roi - min_roi) * 20,
                -item.score,
            ),
        )

    @staticmethod
    def _rejection_reason(item: CreativeCandidate, min_spend: float, min_roi: float) -> str:
        reasons: list[str] = []
        if item.spend < min_spend:
            reasons.append(f"花费 {item.spend:.0f} 低于门槛 {min_spend:.0f}")
        if item.roi < min_roi:
            reasons.append(f"总收入ROI {item.roi:.2f} 低于门槛 {min_roi:.2f}")
        if not item.valid_identity:
            reasons.append("素材ID或名称是占位值")
        return "；".join(reasons) if reasons else "已过门槛"

    def _render_markdown(self, payload: dict) -> str:
        lines = [
            f"# 素材动作阈值建议 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}（上周四到本周三）",
            (
                f"- 推荐阈值：{payload['recommended_profile']['name']} "
                f"（花费 >= {payload['recommended_profile']['min_spend']:.0f}；"
                f"总收入ROI >= {payload['recommended_profile']['min_roi']:.2f}）"
            ),
            f"- 推荐理由：{payload['recommended_profile']['reason']}",
            f"- 当前阈值：花费 >= {payload['current_thresholds']['min_spend']:.0f}；总收入ROI >= {payload['current_thresholds']['min_roi']:.2f}",
            f"- 当前通过数量：{payload['current_thresholds']['pass_count']}",
            "",
            "## 当前阈值结果",
            "",
        ]
        if payload["current_top_candidates"]:
            lines.extend(self._render_candidates(payload["current_top_candidates"]))
        else:
            lines.append("- 当前阈值下没有素材通过。")
        if payload["current_near_miss_candidates"]:
            lines.extend(["", "## 最接近通过的候选", ""])
            for item in payload["current_near_miss_candidates"][:5]:
                lines.append(
                    f"- {item['project']} | {item['channel']} | 素材ID `{item['creative_id']}` | 花费 `{item['spend']:.2f}` | ROI `{item['roi']:.2f}` | 未通过原因：{item['rejection_reason']}"
                )
        lines.extend(["", "## 三档预设对比", ""])
        for preset in payload["preset_results"]:
            lines.append(
                f"- {preset['name']}：花费 >= {preset['min_spend']:.0f}，总收入ROI >= {preset['min_roi']:.2f}；通过 {preset['count']} 条；覆盖项目：{('、'.join(preset['projects']) if preset['projects'] else '无')}"
            )
            top_candidates = preset["top_candidates"][:5]
            if top_candidates:
                for item in top_candidates:
                    lines.append(
                        f"  - {item['project']} | {item['channel']} | 素材ID `{item['creative_id']}` | 花费 `{item['spend']:.2f}` | ROI `{item['roi']:.2f}`"
                    )
        lines.extend(["", "## 全量高分候选", ""])
        lines.extend(self._render_candidates(payload["all_top_candidates"][:10]))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_candidates(items: list[dict]) -> list[str]:
        lines: list[str] = []
        for item in items:
            lines.append(
                f"- {item['project']} | {item['channel']} | 素材ID `{item['creative_id']}` | 名称 `{item['creative_name']}` | 花费 `{item['spend']:.2f}` | 收入 `{item['revenue']:.2f}` | ROI `{item['roi']:.2f}`"
            )
        return lines


def _align_to_wednesday(report_date: date) -> date:
    weekday = report_date.weekday()
    target = 2
    delta = (weekday - target) % 7
    return report_date - timedelta(days=delta)


def _project_key(value: str) -> str:
    import re

    text = (value or "").strip()
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    return text


def _normalize_channel(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "google" in normalized:
        return "Google"
    if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized or "meta" in normalized:
        return "Facebook"
    return value or "未知渠道"
