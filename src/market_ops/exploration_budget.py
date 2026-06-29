from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.signal_score import SignalScoreBuilder


@dataclass(slots=True)
class ExplorationBudgetResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ExplorationBudgetBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ExplorationBudgetResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"exploration_budget_{suffix}.md"
        json_path = output_dir / f"exploration_budget_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ExplorationBudgetResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        signal_payload = SignalScoreBuilder(self._settings).build_payload(report_date)
        items = [self._budget_item(item) for item in signal_payload.get("items") or []]
        total_recent_spend = sum(float(item.get("recent_spend") or 0.0) for item in signal_payload.get("items") or [])
        return {
            "report_date": report_date.isoformat(),
            "window_start": signal_payload.get("window_start"),
            "window_end": signal_payload.get("window_end"),
            "passed": True,
            "budget_pool_policy": {
                "exploration": 0.20,
                "scaling": 0.60,
                "repair": 0.20,
                "note": "当前仅生成建议，不直接改预算。",
            },
            "summary": {
                "project_count": len(items),
                "total_recent_spend": round(total_recent_spend, 2),
                "suggested_exploration_budget": round(total_recent_spend * 0.20, 2),
            },
            "items": items,
        }

    @staticmethod
    def _budget_item(signal: dict[str, Any]) -> dict[str, Any]:
        spend = float(signal.get("recent_spend") or 0.0)
        score = float(signal.get("signal_score") or 0.0)
        stage = str(signal.get("stage") or "")
        if stage == "Discovery":
            rate = 0.30 if score >= 0.60 else 0.20
            target = "new_hooks_test"
            learning_goal = "验证最强Hook和首批国家方向"
        elif stage == "Validation":
            rate = 0.20 if score >= 0.45 else 0.12
            target = "pattern_validation"
            learning_goal = "验证国家、素材、人群和平台组合是否可复制"
        else:
            rate = 0.05
            target = "scaling_guarded_test"
            learning_goal = "保留少量探索，不干扰成熟项目ROI优化"
        daily_budget = max(0.0, spend * rate / 7.0)
        return {
            "project": signal.get("project"),
            "stage": stage,
            "budget_type": "exploration" if stage in {"Discovery", "Validation"} else "scaling_reserve",
            "suggested_daily_budget": round(daily_budget, 2),
            "suggested_weekly_budget": round(daily_budget * 7.0, 2),
            "target": target,
            "expected_learning_goal": learning_goal,
            "reason": [
                f"阶段={stage or 'Unknown'}",
                f"Signal Score={score:.2f}",
                "新品阶段预算建议只用于探索，不自动执行。",
            ],
            "guardrails": [
                "不因低ROI直接强停测",
                "连续两天信号分恶化且无新增学习结论时回收探索预算",
                "进入Scaling后再接入常规ROI扩量规则",
            ],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 新品探索预算建议 | {payload['report_date']}",
            "",
            f"- 窗口：{payload.get('window_start')} 至 {payload.get('window_end')}",
            f"- 近7日总花费：{summary['total_recent_spend']:.0f}；建议探索池：{summary['suggested_exploration_budget']:.0f}。",
            "- 说明：仅生成预算建议，不改广告平台预算，不发送飞书。",
            "",
            "| 项目 | 阶段 | 类型 | 建议日预算 | 学习目标 | 护栏 |",
            "|---|---|---|---:|---|---|",
        ]
        for item in payload["items"]:
            lines.append(
                f"| {item['project']} | {item['stage']} | {item['budget_type']} | {item['suggested_daily_budget']:.0f} | "
                f"{item['expected_learning_goal']} | {'；'.join(item['guardrails'][:2])} |"
            )
        if not payload["items"]:
            lines.append("| 暂无 | - | - | 0 | 暂无 | 暂无 |")
        lines.append("")
        return "\n".join(lines)
