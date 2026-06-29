from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.creative_dna import CreativeDnaBuilder
from market_ops.exploration_budget import ExplorationBudgetBuilder
from market_ops.signal_score import SignalScoreBuilder
from market_ops.transfer_learning import TransferLearningBuilder


@dataclass(slots=True)
class HypothesisPlanResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class HypothesisGeneratorBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> HypothesisPlanResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"hypothesis_plan_{suffix}.md"
        json_path = output_dir / f"hypothesis_plan_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return HypothesisPlanResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        signal_payload = SignalScoreBuilder(self._settings).build_payload(report_date)
        budget_payload = ExplorationBudgetBuilder(self._settings).build_payload(report_date)
        transfer_payload = TransferLearningBuilder(self._settings).build_payload(report_date)
        creative_dna_payload = CreativeDnaBuilder(self._settings).build_payload(report_date)
        budget_index = {item["project"]: item for item in budget_payload.get("items") or []}
        transfer_index = {item["new_project"]: item for item in transfer_payload.get("items") or []}
        signal_hypotheses = [
            self._hypothesis_item(signal, budget_index.get(signal["project"], {}), transfer_index.get(signal["project"], {}), index)
            for index, signal in enumerate(signal_payload.get("items") or [], start=1)
        ]
        winner_priors = list(creative_dna_payload.get("local_winner_priors") or [])
        proactive_hypotheses = [
            self._winner_prior_hypothesis_item(item, index)
            for index, item in enumerate(winner_priors, start=1)
        ]
        hypotheses = proactive_hypotheses + signal_hypotheses
        return {
            "report_date": report_date.isoformat(),
            "window_start": signal_payload.get("window_start"),
            "window_end": signal_payload.get("window_end"),
            "passed": True,
            "summary": {
                "hypothesis_count": len(hypotheses),
                "winner_material_hypothesis_count": len(proactive_hypotheses),
                "discovery_signal_hypothesis_count": len(signal_hypotheses),
            },
            "hypotheses": hypotheses,
        }

    @staticmethod
    def _hypothesis_item(
        signal: dict[str, Any],
        budget: dict[str, Any],
        transfer: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        project = str(signal.get("project") or "")
        stage = str(signal.get("stage") or "Unknown")
        score = float(signal.get("signal_score") or 0.0)
        missing = set(signal.get("missing_signals") or [])
        patterns = list(transfer.get("recommended_creative_patterns") or [])
        base_pattern = patterns[0] if patterns else "危机Hook"
        if "CTR" in missing:
            test_type = "hook_test"
            hypothesis = f"{base_pattern} 开场可能提升 CTR 和首屏兴趣。"
            variant_a = "平稳开场"
            variant_b = f"{base_pattern} 强刺激开场"
            expected_impact = {"ctr": "+10%"}
        elif "D1留存" in missing:
            test_type = "quality_signal_test"
            hypothesis = "需要补齐 D1 留存，验证点击用户是否能被产品承接。"
            variant_a = "当前投放组合"
            variant_b = "保留高信号国家并补充留存回传"
            expected_impact = {"retention_signal": "complete"}
        elif score >= 0.60:
            test_type = "geo_or_audience_test"
            hypothesis = "当前信号已可继续探索，优先拆分国家/人群验证可复制性。"
            variant_a = "当前最佳国家组合"
            variant_b = "新增1-2个相似高潜国家"
            expected_impact = {"signal_score": "+0.05"}
        else:
            test_type = "message_test"
            hypothesis = "当前信号不足，优先更换前3秒卖点和 CTA。"
            variant_a = "当前素材节奏"
            variant_b = "强化前3秒冲突和结尾CTA"
            expected_impact = {"ctr": "+8%"}
        return {
            "hypothesis_id": f"hyp_{index:03d}",
            "project": project,
            "stage": stage,
            "source": "discovery_signal",
            "test_type": test_type,
            "hypothesis": hypothesis,
            "test_plan": {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "duration": "3d",
                "suggested_daily_budget": budget.get("suggested_daily_budget", 0),
            },
            "expected_impact": expected_impact,
            "success_metrics": [
                "Signal Score 不低于当前分",
                "CTR 或 IPM 出现正向变化",
                "形成下一轮明确学习结论",
            ],
            "rollback_metrics": [
                "连续2日 CTR/IPM 同时下滑",
                "探索预算消耗后没有新增有效信号",
            ],
            "source_signals": {
                "signal_score": signal.get("signal_score"),
                "signal_level": signal.get("signal_level"),
                "missing_signals": signal.get("missing_signals"),
                "transfer_patterns": patterns,
            },
        }

    @staticmethod
    def _winner_prior_hypothesis_item(item: dict[str, Any], index: int) -> dict[str, Any]:
        creative_id = str(item.get("creative_id") or "").strip()
        creative_name = str(item.get("creative_name") or creative_id).strip()
        project = str(item.get("project") or "Unknown")
        channel = str(item.get("channel") or "Unknown")
        country = str(item.get("country") or "Global")
        video_structure = str(item.get("video_structure") or "unknown")
        asset_orientation = str(item.get("asset_orientation") or "unknown")
        asset_aspect_ratio = str(item.get("asset_aspect_ratio") or "unknown")
        asset_duration_bucket = str(item.get("asset_duration_bucket") or "unknown")
        if video_structure == "image":
            test_type = "winner_image_to_motion_test"
            variant_a = f"{creative_name} 原图方向"
            variant_b = f"{creative_name} 动效化/轻动画版本"
            hypothesis = f"{project} 的本地赢家图片素材 {creative_name} 可能具备可复制性，动效化后有机会提升 CTR 并维持用户质量。"
            expected_impact = {"ctr": "+8%", "learning_goal": "validate image-to-motion scalability"}
        else:
            test_type = "winner_hook_clone_test"
            variant_a = f"{creative_name} 原赢家方向"
            variant_b = f"{creative_name} 前3秒/字幕/CTA 变体"
            hypothesis = f"{project} 的本地赢家视频素材 {creative_name} 可能包含可复制 Hook，控制变量改前3秒或 CTA 可以验证增长驱动。"
            expected_impact = {"ctr": "+10%", "learning_goal": "validate reusable winner hook"}
        return {
            "hypothesis_id": f"hyp_local_{index:03d}",
            "project": project,
            "stage": "Validation",
            "source": "local_winner_prior",
            "test_type": test_type,
            "creative_id": creative_id,
            "creative_name": creative_name,
            "hypothesis": hypothesis,
            "test_plan": {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "duration": "3d",
                "suggested_daily_budget": 0,
                "channel": channel,
                "country": country,
            },
            "expected_impact": expected_impact,
            "success_metrics": [
                "CTR improves versus the current winner baseline or variant control",
                "CPI does not materially deteriorate after the creative swap",
                "a reusable winner pattern is captured for the next round",
            ],
            "rollback_metrics": [
                "CTR drops more than 15% versus the active winner direction",
                "CPI rises more than 20% after the variant test",
                "the variant fails to produce a reusable learning signal",
            ],
            "source_signals": {
                "label_source": item.get("label_source"),
                "predicted_scalability": item.get("predicted_scalability"),
                "label_confidence": item.get("label_confidence"),
                "video_structure": video_structure,
                "ui_type": item.get("ui_type"),
                "asset_orientation": asset_orientation,
                "asset_aspect_ratio": asset_aspect_ratio,
                "asset_duration_bucket": asset_duration_bucket,
                "structural_profile": {
                    "asset_type": item.get("asset_type"),
                    "asset_orientation": asset_orientation,
                    "asset_aspect_ratio": asset_aspect_ratio,
                    "asset_duration_bucket": asset_duration_bucket,
                },
            },
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        lines = [
            f"# 新品下一轮测试假设 | {payload['report_date']}",
            "",
            f"- 窗口：{payload.get('window_start')} 至 {payload.get('window_end')}",
            "- 说明：假设计划只用于探索排期，不自动创建广告组、不改预算。",
            "",
        ]
        for item in payload["hypotheses"]:
            lines.extend(
                [
                    f"## {item['hypothesis_id']} | {item['project']} | {item['test_type']}",
                    f"- 假设：{item['hypothesis']}",
                    f"- A：{item['test_plan']['variant_a']}",
                    f"- B：{item['test_plan']['variant_b']}",
                    f"- 建议日预算：{item['test_plan']['suggested_daily_budget']}",
                    f"- 成功指标：{'；'.join(item['success_metrics'])}",
                    f"- 回撤指标：{'；'.join(item['rollback_metrics'])}",
                    "",
                ]
            )
        if not payload["hypotheses"]:
            lines.append("- 暂无可生成的测试假设。")
        return "\n".join(lines)
