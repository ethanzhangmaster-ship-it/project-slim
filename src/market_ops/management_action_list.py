from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.payback_targets import PaybackTargetsBuilder, ProjectTargets


@dataclass(slots=True)
class ManagementActionListResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ManagementActionListBuilder:
    _PROJECT_RULES: dict[str, dict[str, Any]] = {
        "P02 Mermaid": {"d7_floor": 0.35, "d30_target": 0.70},
        "P04 Witch": {"d7_floor": 0.32, "d30_target": None},
        "P07 Vampire": {"d7_floor": 0.45, "d30_target": None},
    }
    _MIN_DIMENSION_COST = 100.0
    _MIN_DIMENSION_SHARE = 0.02

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = None
        self._payback_targets_cache: dict[str, ProjectTargets] | None = None

    def build(self, report_date: date) -> ManagementActionListResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"management_action_list_{suffix}.md"
        json_path = output_dir / f"management_action_list_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ManagementActionListResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        if self._repo is None:
            from market_ops.pipeline import DataRepository

            self._repo = DataRepository(self._settings)

        window_start = report_date - timedelta(days=6)
        rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        payback_targets_map = self._load_payback_targets_map(report_date)

        by_project: dict[str, list[Any]] = {}
        for row in rows:
            project = self._project_key(str(getattr(row, "game", "") or ""))
            if project:
                by_project.setdefault(project, []).append(row)

        items: list[dict[str, Any]] = []
        for project, project_rows in sorted(by_project.items()):
            paid_cost = sum(
                float(getattr(row, "cost", 0.0) or 0.0)
                for row in project_rows
                if float(getattr(row, "cost", 0.0) or 0.0) > 0
            )
            if paid_cost <= 0:
                continue
            action_item = self._build_project_action(
                project,
                project_rows,
                report_date,
                payback_targets_map.get(self._project_code(project)),
            )
            if action_item is not None:
                items.append(action_item)

        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": True,
            "count": len(items),
            "items": items,
        }

    @staticmethod
    def to_action_lines(payload: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for item in payload.get("items", [])[:3]:
            action_type = ManagementActionListBuilder._infer_action_type(str(item.get("action") or ""))
            target = f"{item.get('project', '')} / {item.get('scope', '')}".strip(" /")
            owner = str(item.get("owner") or "待定")
            due_date = str(item.get("due_date") or "")
            verification = str(item.get("verification_metric") or "")
            lines.append(f"{action_type}：{target}。负责人：{owner}；截止时间：{due_date}；KPI：{verification}")
        return lines

    @staticmethod
    def _infer_action_type(action_text: str) -> str:
        text = str(action_text or "")
        if "暂停" in text:
            return "暂停"
        if "减量" in text or "压缩" in text:
            return "减量"
        if "加码" in text or "放量" in text:
            return "加码"
        if "维持观察" in text or "维持预算" in text or "先维持" in text:
            return "维持观察"
        if "限额验证" in text or "小规模验证" in text or "小额验证" in text:
            return "限额验证"
        if "口径复核" in text or "校对" in text or "补项目级" in text:
            return "口径复核"
        return "处理"

    def _build_project_action(
        self,
        project: str,
        rows: list[Any],
        report_date: date,
        payback_target: ProjectTargets | None,
    ) -> dict[str, Any] | None:
        if not rows:
            return None

        segment_rollup = self._aggregate_segments(rows)
        actionable_segments = {key: metrics for key, metrics in segment_rollup.items() if metrics["cost"] > 0}
        if not actionable_segments:
            return None

        top_spend_key, top_spend_metrics = max(actionable_segments.items(), key=lambda item: item[1]["cost"])
        focus_key, focus_metrics = self._pick_focus_segment(actionable_segments)
        channel_rollup = self._aggregate_dimension(rows, "partner")
        country_rollup = self._aggregate_dimension(rows, "country")
        store_rollup = self._aggregate_dimension(rows, "store")

        total_cost = sum(metrics["cost"] for metrics in actionable_segments.values())
        weak_channel = self._pick_weakest_dimension(channel_rollup, total_cost, max_roi=1.0)
        weak_country = self._pick_weakest_dimension(country_rollup, total_cost, max_roi=1.0)
        weak_store = self._pick_weakest_dimension(store_rollup, total_cost, max_roi=1.0)

        root_cause = self._root_cause_text(rows, weak_store, weak_channel, weak_country)
        problem = f"{project} 当前最需要重点关注的付费组合是 {focus_key}，本周总收入ROI 为 {focus_metrics['roi']:.2f}"
        reason = (
            f"本周主要消耗集中在 {top_spend_key}，花费 {top_spend_metrics['cost']:.0f}；"
            f"当前优先处理组合 {focus_key}，花费 {focus_metrics['cost']:.0f}，ROI {focus_metrics['roi']:.2f}。{root_cause}"
        )
        action = self._action_text(project, focus_metrics["roi"], focus_key, None, None, payback_target)
        verification = self._verification_text(project, focus_key, payback_target)

        return {
            "project": project,
            "scope": focus_key,
            "top_spend_scope": top_spend_key,
            "problem": problem,
            "reason": reason,
            "action": action,
            "owner": self._resolve_owner(action),
            "due_date": (report_date + timedelta(days=7)).isoformat(),
            "verification_metric": verification,
            "store_breakdown": self._serialize_rollup(store_rollup),
            "channel_breakdown": self._serialize_rollup(channel_rollup),
            "country_breakdown": self._serialize_rollup(country_rollup),
            "dimension_gate": {
                "min_cost": self._MIN_DIMENSION_COST,
                "min_share": self._MIN_DIMENSION_SHARE,
                "max_root_cause_roi": 1.0,
            },
        }

    def _resolve_owner(self, action_text: str) -> str:
        text = str(action_text or "")
        if "素材" in text:
            return "牟耕"
        if any(keyword in text for keyword in ("暂停", "减量", "压缩", "放量", "加码", "限额验证", "小规模验证", "小额验证", "预算", "维持观察")):
            return "林凯"
        return "姜会伟"

    @staticmethod
    def _pick_focus_segment(actionable_segments: dict[str, dict[str, float]]) -> tuple[str, dict[str, float]]:
        loss_candidates: list[tuple[str, dict[str, float], float]] = []
        for key, metrics in actionable_segments.items():
            cost = float(metrics.get("cost") or 0.0)
            roi = float(metrics.get("roi") or 0.0)
            loss = cost * max(0.0, 1.0 - roi)
            if loss > 0:
                loss_candidates.append((key, metrics, loss))
        if not loss_candidates:
            return min(actionable_segments.items(), key=lambda item: (item[1]["roi"], -item[1]["cost"]))
        key, metrics, _ = max(loss_candidates, key=lambda item: (item[2], item[1]["cost"]))
        return key, metrics

    @classmethod
    def _root_cause_text(
        cls,
        rows: list[Any],
        weak_store: tuple[str, dict[str, float]] | None,
        weak_channel: tuple[str, dict[str, float]] | None,
        weak_country: tuple[str, dict[str, float]] | None,
    ) -> str:
        parts: list[str] = []
        if weak_store is not None:
            parts.append(f"平台总收入ROI偏弱：{weak_store[0]}（ROI {weak_store[1]['roi']:.2f}）")
        if weak_channel is not None:
            note = cls._channel_anomaly_note(rows, weak_channel[0])
            suffix = f"，{note}" if note else ""
            parts.append(f"渠道总收入ROI偏弱：{weak_channel[0]}（ROI {weak_channel[1]['roi']:.2f}{suffix}）")
        if weak_country is not None:
            parts.append(f"国家总收入ROI偏弱：{weak_country[0]}（ROI {weak_country[1]['roi']:.2f}）")
        if parts:
            return "；".join(parts) + "。"
        return "未发现达到样本门槛且 ROI<1 的平台/渠道/国家单点根因，先以组合和项目级回收验证为准。"

    @classmethod
    def _channel_anomaly_note(cls, rows: list[Any], channel: str) -> str:
        zero_share, _ = cls._zero_revenue_share_after_grouping(rows, channel)
        if zero_share >= 0.20:
            return "部分 Campaign/国家聚合后仍为零收入，执行前需复核是否真实低回收"
        return ""

    @classmethod
    def _zero_revenue_share_after_grouping(cls, rows: list[Any], channel: str) -> tuple[float, float]:
        buckets: dict[tuple[str, str, str, str, str, str], dict[str, float]] = {}
        for row in rows or []:
            row_channel = cls._normalize_channel(str(getattr(row, "partner", "") or ""))
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
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            bucket["cost"] += cost
            bucket["revenue"] += revenue
        total_cost = sum(float(item["cost"] or 0.0) for item in buckets.values())
        zero_cost = sum(
            float(item["cost"] or 0.0)
            for item in buckets.values()
            if float(item["cost"] or 0.0) > 0 and float(item["revenue"] or 0.0) <= 0
        )
        return ((zero_cost / total_cost) if total_cost else 0.0, zero_cost)

    @staticmethod
    def _segment_channel(segment_key: str) -> str:
        if "/" not in segment_key:
            return segment_key.strip()
        return segment_key.rsplit("/", 1)[-1].strip()

    @classmethod
    def _action_text(
        cls,
        project: str,
        weak_roi: float,
        weak_key: str,
        weak_channel: tuple[str, dict[str, float]] | None,
        weak_country: tuple[str, dict[str, float]] | None,
        payback_target: ProjectTargets | None,
    ) -> str:
        focus_text = cls._focus_text(weak_channel, weak_country)
        d7_current = payback_target.current_recovery.get("D7") if payback_target else None
        d7_floor = payback_target.recovery_targets.get("D7").floor if payback_target and payback_target.recovery_targets.get("D7") else None

        if d7_current is not None and d7_floor is not None:
            if d7_current < d7_floor * 0.85:
                return f"先控量验证 {weak_key}，只保留小额验证预算，同时排查{focus_text}回收问题。"
            if d7_current < d7_floor:
                return f"先限额验证 {weak_key}，保留小额预算，同时排查{focus_text}回收波动。"
            return f"维持观察 {weak_key}，不新增预算，继续观察{focus_text}后续回收。"

        if weak_roi < 0.30:
            return f"先控量验证 {weak_key}，只保留小额验证预算，同时排查{focus_text}回收问题。"
        if weak_roi < 0.60:
            return f"先限额验证 {weak_key}，保留小额预算，同时排查{focus_text}回收波动。"
        return f"维持观察 {weak_key}，不新增预算，继续观察{focus_text}后续回收。"

    @staticmethod
    def _focus_text(
        weak_channel: tuple[str, dict[str, float]] | None,
        weak_country: tuple[str, dict[str, float]] | None,
    ) -> str:
        parts: list[str] = []
        if weak_channel is not None:
            parts.append(weak_channel[0])
        if weak_country is not None:
            parts.append(weak_country[0])
        return f" {' / '.join(parts)} 的" if parts else "当前组合的"

    @classmethod
    def _verification_text(
        cls,
        project: str,
        weak_key: str,
        payback_target: ProjectTargets | None,
    ) -> str:
        rule = cls._PROJECT_RULES.get(project, {})
        d7_floor = (
            payback_target.recovery_targets.get("D7").floor
            if payback_target and payback_target.recovery_targets.get("D7")
            else rule.get("d7_floor")
        )
        d30_target = (
            payback_target.recovery_targets.get("D30").floor
            if payback_target and payback_target.recovery_targets.get("D30")
            else rule.get("d30_target")
        )
        if d7_floor is not None and d30_target is not None:
            d7_current = payback_target.current_recovery.get("D7") if payback_target else None
            if d7_current is not None and d7_current >= d7_floor:
                return (
                    f"维持现有预算观察；优先看 {weak_key} 对应商店+渠道D7是否持续不低于历史保底线 {d7_floor:.2f}，"
                    f"且D30接近历史保底线 {d30_target:.2f}；D7至少满9天后再确认是否提高验证预算。"
                )
            return (
                f"先看低效组合7日累计ROI和3日ROAS是否回升；优先用 {weak_key} 对应商店+渠道D7回到历史保底线 {d7_floor:.2f}，"
                f"且D30接近历史保底线 {d30_target:.2f} 后，再讨论是否提高验证预算；D7至少满9天后再确认。"
            )
        if d7_floor is not None:
            d7_current = payback_target.current_recovery.get("D7") if payback_target else None
            if d7_current is not None and d7_current >= d7_floor:
                return (
                    "不再用短周期总收入ROI直接当回本依据；"
                    f"商店+渠道D7持续不低于历史保底线 {d7_floor:.2f} 时，才讨论是否小幅提高 {weak_key} 的验证预算。"
                )
            return (
                "不再用短周期总收入ROI直接当回本依据；"
                f"先确认商店+渠道D7回到历史保底线 {d7_floor:.2f} 后，再讨论是否提高 {weak_key} 的验证预算。"
            )
        return f"先看 {weak_key} 对应组合的 3日ROAS 和回收变化，再决定是否调整预算。"

    @staticmethod
    def _project_key(value: str) -> str:
        text = (value or "").strip()
        upper = text.upper()
        if upper.startswith("P02") or "MERMAID" in upper:
            return "P02 Mermaid"
        if upper.startswith("P04") or "WITCH" in upper:
            return "P04 Witch"
        if upper.startswith("P07") or "VAMPIRE" in upper:
            return "P07 Vampire"
        return text

    @staticmethod
    def _project_code(value: str) -> str:
        text = (value or "").strip().upper()
        if text.startswith("P02"):
            return "P02"
        if text.startswith("P04"):
            return "P04"
        if text.startswith("P07"):
            return "P07"
        return text

    @staticmethod
    def _normalize_channel(value: str) -> str:
        lowered = (value or "").strip().lower()
        if lowered in {"meta", "facebook", "fb", "instagram", "off-facebook"}:
            return "Facebook"
        if "google" in lowered:
            return "Google"
        return value.strip() or "Unknown"

    @staticmethod
    def _normalize_store(value: str) -> str:
        lowered = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(lowered, value.strip() or "Unknown")

    def _aggregate_segments(self, rows: list[Any]) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_channel(str(getattr(row, "partner", "") or ""))
            key = f"{store} / {channel}"
            bucket = buckets.setdefault(key, {"cost": 0.0, "revenue": 0.0, "roi": 0.0})
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            if cost > 0:
                bucket["cost"] += cost
        for bucket in buckets.values():
            bucket["roi"] = bucket["revenue"] / bucket["cost"] if bucket["cost"] else 0.0
        return buckets

    def _aggregate_dimension(self, rows: list[Any], dimension: str) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            raw_value = str(getattr(row, dimension, "") or "").strip()
            if dimension == "partner":
                key = self._normalize_channel(raw_value)
            elif dimension == "store":
                key = self._normalize_store(raw_value)
            else:
                key = raw_value or "Unknown"
            bucket = buckets.setdefault(key, {"cost": 0.0, "revenue": 0.0, "roi": 0.0})
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            if cost > 0:
                bucket["cost"] += cost
        for bucket in buckets.values():
            bucket["roi"] = bucket["revenue"] / bucket["cost"] if bucket["cost"] else 0.0
        return buckets

    @staticmethod
    def _pick_weakest(rollup: dict[str, dict[str, float]]) -> tuple[str, dict[str, float]] | None:
        actionable = [(key, metrics) for key, metrics in rollup.items() if metrics["cost"] > 0]
        if not actionable:
            return None
        return min(actionable, key=lambda item: (item[1]["roi"], -item[1]["cost"]))

    @classmethod
    def _pick_weakest_dimension(
        cls,
        rollup: dict[str, dict[str, float]],
        total_cost: float,
        *,
        max_roi: float | None = None,
    ) -> tuple[str, dict[str, float]] | None:
        min_cost = max(cls._MIN_DIMENSION_COST, total_cost * cls._MIN_DIMENSION_SHARE)
        actionable: list[tuple[str, dict[str, float]]] = []
        for key, metrics in rollup.items():
            cost = float(metrics.get("cost") or 0.0)
            roi = float(metrics.get("roi") or 0.0)
            if cost < min_cost:
                continue
            if max_roi is not None and roi >= max_roi:
                continue
            actionable.append((key, metrics))
        if not actionable:
            return None
        return min(actionable, key=lambda item: (item[1]["roi"], -item[1]["cost"]))

    @staticmethod
    def _serialize_rollup(rollup: dict[str, dict[str, float]]) -> list[dict[str, float | str]]:
        rows: list[dict[str, float | str]] = []
        for key, metrics in sorted(rollup.items(), key=lambda item: item[1]["cost"], reverse=True):
            rows.append(
                {
                    "key": key,
                    "cost": round(metrics["cost"], 4),
                    "revenue": round(metrics["revenue"], 4),
                    "roi": round(metrics["roi"], 4),
                }
            )
        return rows

    def _load_payback_targets_map(self, report_date: date) -> dict[str, ProjectTargets]:
        if self._payback_targets_cache is not None:
            return self._payback_targets_cache
        try:
            targets, _ = PaybackTargetsBuilder(self._settings).build_targets_data(report_date)
        except Exception:
            self._payback_targets_cache = {}
            return self._payback_targets_cache
        self._payback_targets_cache = {item.project: item for item in targets}
        return self._payback_targets_cache

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# 管理动作台账 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}",
            f"- 动作数：{payload['count']}",
            "",
        ]
        for item in payload["items"]:
            lines.extend(
                [
                    f"## {item['project']}",
                    "",
                    f"- 问题：{item['problem']}",
                    f"- 原因：{item['reason']}",
                    f"- 行动：{item['action']}",
                    f"- 负责人：{item['owner']}",
                    f"- 截止时间：{item['due_date']}",
                    f"- 验证指标：{item['verification_metric']}",
                    f"- 主耗组合：{item['top_spend_scope']}",
                    f"- 当前优先处理组合：{item['scope']}",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"
