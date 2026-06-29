from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict
from statistics import mean
from typing import Any

from openai import OpenAI

from market_ops.config import Settings
from market_ops.models import AdsPerformanceRow, CreativeAssetRow, RevenueRow
from market_ops.prompts import COMMON_RULES


class AIClient(ABC):
    @abstractmethod
    def generate_json(self, task_name: str, instructions: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIAIClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self._client = OpenAI(**client_kwargs)
        self._model = settings.openai_model

    def generate_json(self, task_name: str, instructions: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": COMMON_RULES},
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"{task_name} returned empty content.")
        return json.loads(content)


class MockAIClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_json(self, task_name: str, instructions: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task_name == "growth_analysis":
            return self._mock_growth(payload)
        if task_name == "creative_analysis":
            return self._mock_creatives(payload)
        if task_name == "revenue_analysis":
            return self._mock_revenue(payload)
        if task_name == "decision_generation":
            return self._mock_decisions(payload)
        raise ValueError(f"Unsupported mock task: {task_name}")

    def _mock_growth(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = [AdsPerformanceRow(**row) for row in payload["ads_rows"]]
        if not rows:
            return {
                "title": "增长分析",
                "conclusions": ["本周没有可用投放数据。"],
                "highlights": [],
                "recommendations": ["先检查飞书投放表同步是否正常。"],
                "weakest_segment": "",
                "best_channel": "",
                "top_game": "",
            }

        spend_by_game: dict[str, float] = defaultdict(float)
        roas_by_channel: dict[str, list[float]] = defaultdict(list)
        roas_by_segment: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            spend_by_game[row.game] += row.spend
            roas_by_channel[row.channel].append(row.roas)
            segment = "/".join(part for part in [row.country, row.channel] if part and part != "All") or "总体"
            roas_by_segment[segment].append(row.roas)

        top_game = max(spend_by_game, key=spend_by_game.get)
        best_channel = max(roas_by_channel, key=lambda key: mean(roas_by_channel[key]))
        weakest_segment = min(roas_by_segment, key=lambda key: mean(roas_by_segment[key]))
        avg_roas = mean(row.roas for row in rows)
        total_spend = sum(row.spend for row in rows)

        return {
            "title": "增长分析",
            "conclusions": [
                f"本周投放花费 {total_spend:.0f}，整体平均 ROAS 为 {avg_roas:.2f}。",
                f"{top_game} 仍是当前主要投放项目。",
                f"{best_channel} 是当前回收表现相对更稳的渠道。",
            ],
            "highlights": [
                f"主投项目：{top_game}",
                f"最佳渠道：{best_channel}",
                f"最弱回收段：{weakest_segment}",
            ],
            "recommendations": [
                f"优先把新增预算放到 {best_channel} 中已验证回收的组。",
                f"先收紧 {weakest_segment} 的低回收花费，再观察 3 日回收恢复情况。",
                "预算动作继续绑定回收阈值，不做情绪化放量。",
            ],
            "weakest_segment": weakest_segment,
            "best_channel": best_channel,
            "top_game": top_game,
        }

    def _mock_creatives(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = [CreativeAssetRow(**row) for row in payload["creative_rows"]]
        ranked = sorted(rows, key=lambda row: (row.roas, row.ctr, row.spend), reverse=True)
        top_assets = ranked[:3]
        top_hook = top_assets[0].hook_type if top_assets else "暂无明确方向"
        return {
            "title": "素材分析",
            "conclusions": [
                "本周高表现素材仍然依赖前 3 秒快速给出核心冲突或结果预期。",
                f"表现最强素材是 {top_assets[0].asset_id}，ROAS {top_assets[0].roas:.2f}，CTR {top_assets[0].ctr:.3f}。" if top_assets else "本周没有素材表现数据。",
                f"当前最值得复用的方向是 {top_hook}。" if top_assets else "当前还没有形成稳定的素材方向。",
            ],
            "highlights": [
                f"{row.asset_id} | hook={row.hook_type or row.creative_type} | ROAS={row.roas:.2f} | CTR={row.ctr:.3f}"
                for row in top_assets
            ],
            "recommendations": [
                "新素材继续保证前 0 到 3 秒直接给出信息点，不做慢热开场。",
                "把本周最强 hook 至少复制成 3 个变体，分别加强冲突、对比和结尾行动指令。",
                "对已有花费但没有付费验证的素材尽快降权或停投。",
            ],
            "top_asset_id": top_assets[0].asset_id if top_assets else "",
            "top_hook": top_hook,
        }

    def _mock_revenue(self, payload: dict[str, Any]) -> dict[str, Any]:
        revenue_rows = [RevenueRow(**row) for row in payload["revenue_rows"]]
        ads_rows = [AdsPerformanceRow(**row) for row in payload["ads_rows"]]
        if not revenue_rows:
            ad_spend = sum(row.spend for row in ads_rows)
            return {
                "title": "收入归因分析",
                "conclusions": [
                    "当前还没有接入可用的收入归因数据。",
                    f"报告窗口内已确认投放花费 {ad_spend:.0f}。",
                ],
                "highlights": ["先补齐 Adjust 数据后，再依据收入质量做预算判断。"],
                "recommendations": ["未接入收入数据前，只能先按投放回收和素材表现做保守调整。"],
                "top_game": "",
                "blended_roi": 0.0,
            }

        revenue_by_game: dict[str, list[float]] = defaultdict(list)
        for row in revenue_rows:
            revenue_by_game[row.game].append(row.total_revenue)
        top_game = max(revenue_by_game, key=lambda key: sum(revenue_by_game[key]))
        avg_ltv = mean(row.ltv for row in revenue_rows if row.ltv)
        avg_arpu = mean(row.arpu for row in revenue_rows if row.arpu)
        total_revenue = sum(row.total_revenue for row in revenue_rows)
        total_spend = sum(row.total_cost for row in revenue_rows)
        if total_spend <= 0:
            total_spend = sum(row.spend for row in ads_rows)
        blended_roi = total_revenue / total_spend if total_spend else 0.0
        return {
            "title": "收入归因分析",
            "conclusions": [
                f"当前收入贡献最高的项目是 {top_game}。",
                f"本周收入/花费比为 {blended_roi:.2f}。",
                f"平均变现质量为 LTV {avg_ltv:.2f}、ARPU {avg_arpu:.2f}。",
            ],
            "highlights": [
                f"窗口总收入：{total_revenue:.0f}",
                f"收入主力项目：{top_game}",
            ],
            "recommendations": [
                f"只要素材供给和留存稳定，{top_game} 仍可优先承接增量预算。",
                "放量时继续盯住收入质量，不只看装量和点击。",
                "预算排序优先用收入效率，而不是单看买量成本。",
            ],
            "top_game": top_game,
            "blended_roi": blended_roi,
        }

    def _mock_decisions(self, payload: dict[str, Any]) -> dict[str, Any]:
        growth = payload["growth_analysis"]
        creative = payload["creative_analysis"]
        revenue = payload["revenue_analysis"]
        default_owner = payload.get("default_owner") or self._settings.default_task_owner
        creative_asset_project_map = payload.get("creative_asset_project_map") or {}

        weakest_segment = growth.get("weakest_segment") or "低回收段"
        top_asset_id = creative.get("top_asset_id") or "本周优胜素材"
        top_hook = creative.get("top_hook") or "当前强势方向"
        top_game = revenue.get("top_game") or growth.get("top_game") or "核心项目"
        top_asset_project = str(creative_asset_project_map.get(top_asset_id) or "").strip()
        creative_target = f"{top_asset_project} / {top_asset_id} {top_hook}方向素材" if top_asset_project else f"{top_asset_id} {top_hook}方向素材"

        return {
            "items": [
                {
                    "recommendation_type": "减量",
                    "target": f"{weakest_segment} 低回收预算",
                    "owner": default_owner,
                    "kpi_target": "先看3日ROAS与项目级回收是否改善，再决定是否提高验证预算",
                    "estimated_impact": "先减少低效花费，控制预算浪费",
                    "reason": f"{weakest_segment} 当前回收最弱，先压缩低效段预算更稳妥。",
                },
                {
                    "recommendation_type": "复制素材",
                    "target": creative_target,
                    "owner": default_owner,
                    "kpi_target": "新出 3 个变体，CTR 高于账户中位数",
                    "estimated_impact": "补充可放量的高质量素材供给",
                    "reason": f"{top_asset_id} 已验证效果，优先复用 {top_hook} 方向更有效率。",
                },
                {
                    "recommendation_type": "加码",
                    "target": f"{top_game} 高回收投放",
                    "owner": default_owner,
                    "kpi_target": "放量期间收入/花费比保持在目标线以上",
                    "estimated_impact": "把预算集中到当前收入效率更高的项目",
                    "reason": f"{top_game} 当前收入贡献最高，适合在回收稳定前提下承接增量。",
                },
            ]
        }


def build_ai_client(settings: Settings) -> AIClient:
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
        return OpenAIAIClient(settings)
    return MockAIClient(settings)
