from __future__ import annotations

from collections import defaultdict
from statistics import mean

from market_ops.clients.ai import AIClient, MockAIClient, OpenAIAIClient
from market_ops.config import Settings
from market_ops.models import AdsPerformanceRow, CreativeAssetRow, RevenueRow


class CleanMockAIClient(MockAIClient):
    def _mock_growth(self, payload: dict) -> dict:
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
            segment = "/".join(part for part in [row.country, row.channel] if part and part != "All") or "整体"
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
                f"优先把新增预算放到 {best_channel} 中已验证回收的组合。",
                f"先收缩 {weakest_segment} 的低回收花费，再观察 3 日回收恢复情况。",
                "预算动作继续绑定回收阈值，不做情绪化放量。",
            ],
            "weakest_segment": weakest_segment,
            "best_channel": best_channel,
            "top_game": top_game,
        }

    def _mock_creatives(self, payload: dict) -> dict:
        rows = [CreativeAssetRow(**row) for row in payload["creative_rows"]]
        ranked = sorted(rows, key=lambda row: (row.roas, row.ctr, row.spend), reverse=True)
        evidence_rows = [
            row
            for row in ranked
            if (row.spend >= self._settings.creative_action_min_spend or row.installs >= 20)
            and row.roas >= self._settings.creative_action_min_roi
        ]
        observation_rows = ranked[:3]
        top_assets = evidence_rows[:3]
        if top_assets:
            top_hook = top_assets[0].hook_type or top_assets[0].creative_type or "暂无明确方向"
            conclusions = [
                "本周素材结论只采用达到最低样本门槛且回收为正的素材。",
                f"当前可进入复用观察的素材是 {top_assets[0].asset_id}，ROAS {top_assets[0].roas:.2f}，花费 {top_assets[0].spend:.0f}。",
                f"可继续验证的方向是 {top_hook}。",
            ]
            recommendations = [
                "只对达到样本门槛且回收为正的素材做变体测试。",
                "未达到门槛的素材继续作为观察样本，不进入复制任务。",
                "对已有花费但回收明显偏弱的素材先降权，等收入回流后再复核。",
            ]
        else:
            top_hook = "暂无可信复用方向"
            conclusions = [
                "本周素材层没有同时满足样本门槛和正回收的素材，不能输出优质素材强结论。",
                "当前素材数据只适合作为代理层观察，不作为预算增减的主要依据。",
                "素材方向需要等花费≥50美元或安装≥20后再判断。",
            ]
            highlights = [
                f"当前进入观察池的素材样本 {len(observation_rows)} 条，但尚无素材达到复用门槛。",
                "ROAS 为 0 的素材不进入优质素材排序，也不生成复制任务。",
            ]
            recommendations = [
                "本周不生成复制素材任务，先补齐素材归因与样本量。",
                "对 ROAS 为 0 的素材只做观察或降权，不作为复用对象。",
                "素材优化先配合项目级回收修复，不单独驱动预算动作。",
            ]
        if top_assets:
            highlights = [
                f"{row.asset_id} | hook={row.hook_type or row.creative_type} | ROAS={row.roas:.2f} | CTR={row.ctr:.3f} | 样本=有效"
                for row in top_assets
            ]
        return {
            "title": "素材分析",
            "conclusions": conclusions,
            "highlights": highlights,
            "recommendations": recommendations,
            "top_asset_id": top_assets[0].asset_id if top_assets else "",
            "top_hook": top_hook,
        }

    def _mock_revenue(self, payload: dict) -> dict:
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
                f"如果素材供给和留存稳定，{top_game} 仍可优先承接收入优化资源。",
                "放量时继续盯住收入质量，而不只看装量和点击。",
                "预算排序优先看收入效率，而不是单看买量成本。",
            ],
            "top_game": top_game,
            "blended_roi": blended_roi,
        }

    def _mock_decisions(self, payload: dict) -> dict:
        growth = payload["growth_analysis"]
        creative = payload["creative_analysis"]
        revenue = payload["revenue_analysis"]
        default_owner = payload.get("default_owner") or self._settings.default_task_owner

        weakest_segment = growth.get("weakest_segment") or "低回收段"
        top_asset_id = creative.get("top_asset_id") or "本周优胜素材"
        top_hook = creative.get("top_hook") or "当前强势方向"
        top_game = revenue.get("top_game") or growth.get("top_game") or "核心项目"

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
                    "recommendation_type": "加码",
                    "target": f"{top_game} 高回收投放",
                    "owner": default_owner,
                    "kpi_target": "放量期间收入/花费比保持在目标线以上",
                    "estimated_impact": "把预算集中到当前收入效率更高的项目",
                    "reason": f"{top_game} 当前收入贡献最高，适合在回收稳定前提下承接增量。",
                },
            ]
        }


def build_clean_ai_client(settings: Settings) -> AIClient:
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
        return OpenAIAIClient(settings)
    return CleanMockAIClient(settings)
