from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from datetime import date, timedelta

from market_ops.clients.ai import AIClient
from market_ops.models import (
    ActionItem,
    AdsPerformanceRow,
    AnalysisSection,
    CreativeAssetRow,
    DecisionItem,
    RevenueRow,
)
from market_ops.prompts import (
    CREATIVE_ANALYSIS_INSTRUCTIONS,
    DECISION_GENERATION_INSTRUCTIONS,
    GROWTH_ANALYSIS_INSTRUCTIONS,
    REVENUE_ANALYSIS_INSTRUCTIONS,
)


class AnalysisService:
    def __init__(
        self,
        ai_client: AIClient,
        default_task_owner: str,
        default_task_due_days: int,
        task_owner_rules: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._default_task_owner = default_task_owner
        self._default_task_due_days = default_task_due_days
        self._task_owner_rules = task_owner_rules or {}

    def growth_analysis(
        self,
        ads_rows: list[AdsPerformanceRow],
        revenue_rows: list[RevenueRow],
    ) -> AnalysisSection:
        payload = {
            "ads_rows": [asdict(row) for row in ads_rows],
            "revenue_rows": [asdict(row) for row in revenue_rows],
        }
        result = self._ai_client.generate_json("growth_analysis", GROWTH_ANALYSIS_INSTRUCTIONS, payload)
        return AnalysisSection(
            title=result["title"],
            conclusions=result["conclusions"],
            highlights=result["highlights"],
            recommendations=result["recommendations"],
            raw_output=result,
        )

    def creative_analysis(
        self,
        creative_rows: list[CreativeAssetRow],
        ads_rows: list[AdsPerformanceRow],
    ) -> AnalysisSection:
        payload = {
            "creative_rows": [asdict(row) for row in creative_rows],
            "ads_rows": [asdict(row) for row in ads_rows],
        }
        result = self._ai_client.generate_json("creative_analysis", CREATIVE_ANALYSIS_INSTRUCTIONS, payload)
        return AnalysisSection(
            title=result["title"],
            conclusions=result["conclusions"],
            highlights=result["highlights"],
            recommendations=result["recommendations"],
            raw_output=result,
        )

    def revenue_analysis(
        self,
        revenue_rows: list[RevenueRow],
        ads_rows: list[AdsPerformanceRow],
    ) -> AnalysisSection:
        payload = {
            "revenue_rows": [asdict(row) for row in revenue_rows],
            "ads_rows": [asdict(row) for row in ads_rows],
        }
        result = self._ai_client.generate_json("revenue_analysis", REVENUE_ANALYSIS_INSTRUCTIONS, payload)
        return AnalysisSection(
            title=result["title"],
            conclusions=result["conclusions"],
            highlights=result["highlights"],
            recommendations=result["recommendations"],
            raw_output=result,
        )

    def decisions(
        self,
        growth_analysis: AnalysisSection,
        creative_analysis: AnalysisSection,
        revenue_analysis: AnalysisSection,
        creative_rows: list[CreativeAssetRow] | None = None,
    ) -> list[DecisionItem]:
        payload = {
            "growth_analysis": growth_analysis.raw_output,
            "creative_analysis": creative_analysis.raw_output,
            "revenue_analysis": revenue_analysis.raw_output,
            "default_owner": self._default_task_owner,
            "creative_asset_project_map": self._creative_asset_project_map(creative_rows or []),
        }
        result = self._ai_client.generate_json("decision_generation", DECISION_GENERATION_INSTRUCTIONS, payload)
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
        return self._enforce_creative_project_targets(items, creative_rows or [])

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

    @staticmethod
    def _build_task_id(report_date: date, action_type: str, target: str) -> str:
        identity = f"{action_type.strip()}|{target.strip()}".lower()
        digest = hashlib.md5(identity.encode("utf-8")).hexdigest()[:8]
        return f"{report_date.strftime('%Y%m%d')}-{digest}"

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
        if decision.recommendation_type in {"加码", "减量", "暂停"}:
            return "投放负责人"
        return self._default_task_owner

    @classmethod
    def _creative_asset_project_map(cls, creative_rows: list[CreativeAssetRow]) -> dict[str, str]:
        spend_by_asset_project: dict[tuple[str, str], float] = {}
        for row in creative_rows:
            asset_id = (row.asset_id or "").strip()
            game = (row.game or "").strip()
            if not asset_id or not game:
                continue
            spend_by_asset_project[(asset_id, game)] = spend_by_asset_project.get((asset_id, game), 0.0) + float(row.spend)
        asset_to_best_project: dict[str, tuple[str, float]] = {}
        for (asset_id, game), spend in spend_by_asset_project.items():
            current = asset_to_best_project.get(asset_id)
            if current is None or spend > current[1]:
                asset_to_best_project[asset_id] = (game, spend)
        return {asset_id: game for asset_id, (game, _) in asset_to_best_project.items()}

    @classmethod
    def _enforce_creative_project_targets(
        cls,
        decisions: list[DecisionItem],
        creative_rows: list[CreativeAssetRow],
    ) -> list[DecisionItem]:
        asset_project_map = cls._creative_asset_project_map(creative_rows)
        normalized: list[DecisionItem] = []
        for decision in decisions:
            if decision.recommendation_type != "复制素材":
                normalized.append(decision)
                continue
            asset_id = cls._extract_asset_id(decision.target)
            project = asset_project_map.get(asset_id or "")
            if not asset_id or not project or project in decision.target:
                normalized.append(decision)
                continue
            normalized.append(
                DecisionItem(
                    recommendation_type=decision.recommendation_type,
                    target=f"{project} / {decision.target}",
                    owner=decision.owner,
                    kpi_target=decision.kpi_target,
                    estimated_impact=decision.estimated_impact,
                    reason=decision.reason,
                )
            )
        return normalized

    @staticmethod
    def _extract_game_name(target: str) -> str:
        match = re.search(r"\bP\d{2}\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", target)
        return match.group(0).strip() if match else ""

    @staticmethod
    def _extract_asset_id(target: str) -> str:
        match = re.search(r"\bA\d+\b", target or "")
        return match.group(0).strip() if match else ""
