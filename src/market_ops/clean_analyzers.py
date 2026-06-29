from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta

from market_ops.analyzers import AnalysisService
from market_ops.models import ActionItem, AnalysisSection, DecisionItem, RevenueBreakdownRow
from market_ops.prompts import DECISION_GENERATION_INSTRUCTIONS


class CleanAnalysisService(AnalysisService):
    def apply_paid_roi_guardrails_to_sections(
        self,
        growth_analysis: AnalysisSection,
        revenue_analysis: AnalysisSection,
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
    ) -> None:
        paid_roi_by_game = self._paid_roi_net_by_game(revenue_breakdown_rows or [])
        risky_games = {game: roi for game, roi in paid_roi_by_game.items() if roi < 1.0}
        if not risky_games:
            return

        revenue_analysis.recommendations = [
            self._rewrite_scale_line(line, risky_games) for line in revenue_analysis.recommendations
        ]
        revenue_analysis.conclusions = [
            self._rewrite_scale_line(line, risky_games) for line in revenue_analysis.conclusions
        ]
        growth_analysis.recommendations = [
            self._rewrite_scale_line(line, risky_games, generic_only=True) for line in growth_analysis.recommendations
        ]

    def decisions(
        self,
        growth_analysis: AnalysisSection,
        creative_analysis: AnalysisSection,
        revenue_analysis: AnalysisSection,
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
        creative_rows=None,
    ) -> list[DecisionItem]:
        paid_roi_by_game = self._paid_roi_net_by_game(revenue_breakdown_rows or [])
        payload = {
            "growth_analysis": growth_analysis.raw_output,
            "creative_analysis": creative_analysis.raw_output,
            "revenue_analysis": revenue_analysis.raw_output,
            "default_owner": self._default_task_owner,
            "creative_asset_project_map": self._creative_asset_project_map(creative_rows or []),
            "paid_roi_guardrails": {
                "rule": "If paid net ROI is below 1.00, do not recommend 加码. Prefer conservative 减量 / 限额验证 / 回本修复. Do not use hard pause unless explicitly confirmed outside the model.",
                "projects": [
                    {
                        "game": game,
                        "paid_roi_net": round(value, 4),
                        "breakeven_ready": value >= 1.0,
                    }
                    for game, value in sorted(paid_roi_by_game.items())
                ],
            },
        }
        instructions = (
            DECISION_GENERATION_INSTRUCTIONS
            + "\n\nExtra rules:\n"
            + "- If a project's paid net ROI is below 1.00, do not output 加码 for that project.\n"
            + "- Do not output 暂停 only because paid net ROI is below 1.00; use 减量 or 限额验证 unless a human-confirmed hard stop exists.\n"
            + "- Do not use fixed 0.60 / 0.80 / 1.00 KPI thresholds as recovery conditions unless they come from the payback target module.\n"
            + "- For creative actions, only output 复制素材 when the creative sample has enough spend/install evidence and positive payback. Otherwise do not create a task.\n"
            + "- Only recommend 加码 after payback is verified on paid net ROI."
        )
        result = self._ai_client.generate_json("decision_generation", instructions, payload)
        items: list[DecisionItem] = []
        for item in result["items"]:
            items.append(
                DecisionItem(
                    recommendation_type=item["recommendation_type"],
                    target=item["target"],
                    owner=item.get("owner") or self._default_task_owner,
                    kpi_target=item["kpi_target"],
                    estimated_impact=item["estimated_impact"],
                    reason=item["reason"],
                )
            )
        return self._enforce_operational_targets(
            self._filter_unsupported_creative_actions(
                self._enforce_creative_project_targets(
                    self._apply_paid_roi_guardrails(items, paid_roi_by_game),
                    creative_rows or [],
                ),
                creative_rows or [],
            ),
            revenue_breakdown_rows or [],
        )

    def draft_actions(self, meeting_name: str, report_date: date, decisions: list[DecisionItem]) -> list[ActionItem]:
        due_date = report_date + timedelta(days=self._default_task_due_days)
        items: list[ActionItem] = []
        for decision in decisions:
            owner = self._resolve_owner(decision)
            items.append(
                ActionItem(
                    task_id=self._build_task_id(report_date, decision.recommendation_type, decision.target),
                    source_meeting=meeting_name,
                    action_type=decision.recommendation_type,
                    title=f"{decision.recommendation_type}：{decision.target}",
                    owner=owner,
                    status="待确认",
                    acceptance_metric=decision.kpi_target,
                    due_date=due_date,
                    description=f"{decision.reason} 预计影响：{decision.estimated_impact}",
                )
            )
        return items

    def _resolve_owner(self, decision: DecisionItem) -> str:
        explicit_owner = (decision.owner or "").strip()
        if explicit_owner and explicit_owner != self._default_task_owner:
            return explicit_owner

        action_rules = self._task_owner_rules.get("by_action_type", {})
        if decision.recommendation_type in action_rules:
            return action_rules[decision.recommendation_type]

        game = self._extract_game_name(decision.target)
        game_rules = self._task_owner_rules.get("by_game", {})
        if game and game in game_rules:
            return game_rules[game]

        keyword_rules = self._task_owner_rules.get("by_target_keyword", {})
        target_lower = decision.target.lower()
        for keyword, owner in keyword_rules.items():
            if keyword.lower() in target_lower:
                return owner

        if decision.recommendation_type == "复制素材":
            return "素材负责人"
        if decision.recommendation_type in {"加码", "减量", "暂停", "限额验证"}:
            return "投放负责人"
        if decision.recommendation_type == "口径复核":
            return "项目负责人"
        return self._default_task_owner

    def _apply_paid_roi_guardrails(
        self,
        decisions: list[DecisionItem],
        paid_roi_by_game: dict[str, float],
    ) -> list[DecisionItem]:
        normalized: list[DecisionItem] = []
        for decision in decisions:
            if decision.recommendation_type != "加码":
                normalized.append(decision)
                continue

            game = self._extract_game_name(decision.target)
            paid_roi_net = paid_roi_by_game.get(game)
            if paid_roi_net is None or paid_roi_net >= 1.0:
                normalized.append(decision)
                continue

            normalized.append(
                DecisionItem(
                    recommendation_type="减量",
                    target=f"{game} 低效付费预算",
                    owner=decision.owner,
                    kpi_target="先看3日ROAS与项目级回收是否改善，再决定是否提高验证预算",
                    estimated_impact="先压缩低效花费，把预算保留给已验证回收组合",
                    reason=(
                        f"AI 原建议加码，但 {game} 当前付费净 ROI 为 {paid_roi_net:.2f}，"
                        "仍不能作为加量依据，应先控量并优化回本效率。"
                    ),
                )
            )
        return normalized

    def _filter_unsupported_creative_actions(
        self,
        decisions: list[DecisionItem],
        creative_rows,
    ) -> list[DecisionItem]:
        supported_assets = self._supported_creative_assets(creative_rows)
        filtered: list[DecisionItem] = []
        for decision in decisions:
            if decision.recommendation_type != "复制素材":
                filtered.append(decision)
                continue
            asset_id = self._extract_asset_id(decision.target)
            if asset_id and asset_id in supported_assets:
                filtered.append(decision)
        return filtered

    @staticmethod
    def _supported_creative_assets(creative_rows) -> set[str]:
        grouped: dict[str, dict[str, float]] = {}
        for row in creative_rows or []:
            asset_id = str(getattr(row, "asset_id", "") or "").strip()
            if not asset_id:
                continue
            bucket = grouped.setdefault(asset_id, {"spend": 0.0, "installs": 0.0, "roas": 0.0})
            bucket["spend"] += float(getattr(row, "spend", 0.0) or 0.0)
            bucket["installs"] += float(getattr(row, "installs", 0.0) or 0.0)
            bucket["roas"] = max(bucket["roas"], float(getattr(row, "roas", 0.0) or 0.0))
        return {
            asset_id
            for asset_id, values in grouped.items()
            if (values["spend"] >= 50.0 or values["installs"] >= 20.0) and values["roas"] >= 1.0
        }

    def _enforce_operational_targets(
        self,
        decisions: list[DecisionItem],
        revenue_breakdown_rows: list[RevenueBreakdownRow],
    ) -> list[DecisionItem]:
        segment_signals = self._project_segment_signals(revenue_breakdown_rows)
        normalized: list[DecisionItem] = []
        for decision in decisions:
            if decision.recommendation_type not in {"减量", "暂停"}:
                normalized.append(decision)
                continue
            target = decision.target
            project = self._extract_game_name(target)
            segment = self._extract_store_channel_segment(target)
            if project:
                weak_segment = segment_signals.get(project, {}).get("weakest_segment", "")
                if weak_segment and "/" not in target:
                    target = f"{project} / {weak_segment} {self._strip_project_prefix(target, project)}".strip()
            else:
                project = self._infer_project_for_segment(segment, segment_signals) if segment else ""
                if project:
                    suffix = target
                    target = f"{project} / {suffix}"
            normalized.append(
                DecisionItem(
                    recommendation_type=decision.recommendation_type,
                    target=target,
                    owner=decision.owner,
                    kpi_target=decision.kpi_target,
                    estimated_impact=decision.estimated_impact,
                    reason=decision.reason,
                )
            )
        return normalized

    @classmethod
    def _project_segment_signals(cls, rows: list[RevenueBreakdownRow]) -> dict[str, dict[str, str | float]]:
        buckets: dict[tuple[str, str], dict[str, float]] = {}
        for row in rows:
            if row.cost <= 0:
                continue
            project = cls._extract_game_name(row.game) or row.game
            if not project:
                continue
            segment = f"{cls._normalize_store(row.store)}/{cls._normalize_channel(row.partner)}"
            key = (project, segment)
            bucket = buckets.setdefault(key, {"cost": 0.0, "revenue": 0.0})
            bucket["cost"] += row.cost
            bucket["revenue"] += row.total_revenue_gross
        project_signals: dict[str, dict[str, str | float]] = {}
        by_project: dict[str, list[tuple[str, float, float]]] = {}
        for (project, segment), values in buckets.items():
            roi = values["revenue"] / values["cost"] if values["cost"] else 0.0
            by_project.setdefault(project, []).append((segment, roi, values["cost"]))
        for project, items in by_project.items():
            weakest = min(items, key=lambda item: (item[1], -item[2]))
            project_signals[project] = {
                "weakest_segment": weakest[0],
                "weakest_roi": weakest[1],
            }
        return project_signals

    @classmethod
    def _infer_project_for_segment(
        cls,
        segment: str,
        segment_signals: dict[str, dict[str, str | float]],
    ) -> str:
        if not segment:
            return ""
        exact_matches: list[tuple[str, float]] = []
        for project, signal in segment_signals.items():
            weakest_segment = str(signal.get("weakest_segment") or "")
            if weakest_segment == segment:
                exact_matches.append((project, float(signal.get("weakest_roi") or 0.0)))
        if exact_matches:
            exact_matches.sort(key=lambda item: (item[1], item[0]))
            return exact_matches[0][0]
        return ""

    @staticmethod
    def _extract_store_channel_segment(target: str) -> str:
        match = re.search(r"\b(iOS|Android|Amazon)/(Facebook|Google|ASA|Unity|Applovin|Mintegral)\b", target or "", re.IGNORECASE)
        if not match:
            return ""
        store = match.group(1)
        channel = match.group(2)
        return f"{store}/{channel}"

    @staticmethod
    def _strip_project_prefix(target: str, project: str) -> str:
        cleaned = (target or "").strip()
        if cleaned.startswith(project):
            cleaned = cleaned[len(project):].strip(" /")
        return cleaned

    @staticmethod
    def _normalize_store(value: str) -> str:
        normalized = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(normalized, value or "Unknown")

    @staticmethod
    def _normalize_channel(value: str) -> str:
        normalized = (value or "").strip().lower()
        if "google" in normalized:
            return "Google"
        if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized or "meta" in normalized:
            return "Facebook"
        if "apple search" in normalized or normalized == "asa":
            return "ASA"
        if "unity" in normalized:
            return "Unity"
        if "applovin" in normalized:
            return "Applovin"
        if "mintegral" in normalized:
            return "Mintegral"
        return value or "Unknown"

    @staticmethod
    def _rewrite_scale_line(
        line: str,
        risky_games: dict[str, float],
        generic_only: bool = False,
    ) -> str:
        scale_signals = ("加码", "补量", "放量", "新增预算", "增量预算", "扩大预算", "承接新增预算", "承接增量预算", "scale")
        if not any(signal in line for signal in scale_signals):
            return line

        for game, roi in risky_games.items():
            if game and game in line:
                return f"{game} 当前付费净 ROI 仅 {roi:.2f}，现阶段不建议承接新增预算，先优化回本效率。"

        if generic_only:
            return "当前未回本项目不应承接新增预算，预算动作继续以付费净 ROI 是否过线为前提。"
        return "当前未回本项目不应承接新增预算，预算动作继续以付费净 ROI 是否过线为前提。"

    @classmethod
    def _paid_roi_net_by_game(cls, rows: list[RevenueBreakdownRow]) -> dict[str, float]:
        grouped_cost: dict[str, float] = {}
        grouped_revenue: dict[str, float] = {}
        for row in rows:
            if row.cost <= 0:
                continue
            game = cls._extract_game_name(row.game) or row.game
            grouped_cost[game] = grouped_cost.get(game, 0.0) + row.cost
            grouped_revenue[game] = grouped_revenue.get(game, 0.0) + cls._net_total_revenue(row)
        result: dict[str, float] = {}
        for game, total_cost in grouped_cost.items():
            if total_cost > 0:
                result[game] = grouped_revenue.get(game, 0.0) / total_cost
        return result

    @classmethod
    def _net_total_revenue(cls, row: RevenueBreakdownRow) -> float:
        return row.iap_revenue_gross * cls._net_iap_rate(row.store) + row.ad_revenue

    @staticmethod
    def _net_iap_rate(store: str) -> float:
        store_key = (store or "").strip().lower()
        if "amazon" in store_key:
            return 0.8
        if any(keyword in store_key for keyword in ("google", "android", "play")):
            return 0.85
        if any(keyword in store_key for keyword in ("ios", "apple", "itunes", "app_store")):
            return 0.7
        return 0.7

    @staticmethod
    def _extract_game_name(target: str) -> str:
        match = re.search(r"\bP\d{2}\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", target or "")
        return match.group(0).strip() if match else ""

    @staticmethod
    def _extract_asset_id(target: str) -> str:
        match = re.search(r"\bA\d+\b|\b\d{12,}\b", target or "")
        return match.group(0).strip() if match else ""

    @staticmethod
    def build_task_id(report_date: date, action_type: str, target: str) -> str:
        identity = f"{action_type.strip()}|{target.strip()}".lower()
        digest = hashlib.md5(identity.encode("utf-8")).hexdigest()[:8]
        return f"{report_date.strftime('%Y%m%d')}-{digest}"
