from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.signal_score import SignalScoreBuilder


@dataclass(slots=True)
class EarlyPredictionResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class EarlyPredictionBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> EarlyPredictionResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"early_prediction_{suffix}.md"
        json_path = output_dir / f"early_prediction_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return EarlyPredictionResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        signal_payload = SignalScoreBuilder(self._settings).build_payload(report_date)
        items = [self._prediction_item(item) for item in signal_payload.get("items") or []]
        return {
            "report_date": report_date.isoformat(),
            "window_start": signal_payload.get("window_start"),
            "window_end": signal_payload.get("window_end"),
            "passed": True,
            "summary": {
                "project_count": len(items),
                "high_potential": sum(1 for item in items if item["predicted_scale_potential"] >= 0.70),
            },
            "items": items,
        }

    @staticmethod
    def _prediction_item(signal: dict[str, Any]) -> dict[str, Any]:
        score = float(signal.get("signal_score") or 0.0)
        d1 = float(signal.get("d1_retention") or 0.0)
        ipm = float(signal.get("ipm_proxy") or 0.0)
        cpi = float(signal.get("cpi_proxy") or 0.0)
        confidence = str(signal.get("confidence") or "low")
        potential = score
        if d1 >= 0.30:
            potential += 0.08
        if ipm >= 2.0:
            potential += 0.05
        if cpi and cpi <= 3.0:
            potential += 0.04
        if confidence == "low":
            potential -= 0.08
        elif confidence == "blocked":
            potential -= 0.20
        potential = max(0.0, min(1.0, potential))
        if d1 >= 0.30 and score >= 0.55:
            ltv_curve = "slow_high_tail"
        elif score >= 0.60:
            ltv_curve = "fast_test_then_validate"
        else:
            ltv_curve = "unknown_need_more_signal"
        geos = list(signal.get("geos") or [])
        channels = list(signal.get("channels") or [])
        return {
            "project": signal.get("project"),
            "stage": signal.get("stage"),
            "predicted_scale_potential": round(potential, 4),
            "predicted_ltv_curve": ltv_curve,
            "predicted_best_platform": "Android" if cpi and cpi <= 3.0 else "unknown",
            "predicted_best_geo": geos[:3],
            "predicted_best_channel": channels[:2],
            "confidence": confidence,
            "drivers": [
                f"Signal Score={score:.2f}",
                f"D1留存={d1:.3f}" if d1 else "缺少D1留存",
                f"IPM代理={ipm:.2f}" if ipm else "缺少IPM",
                f"CPI代理={cpi:.2f}" if cpi else "缺少CPI",
            ],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 新品早期潜力预测 | {payload['report_date']}",
            "",
            f"- 项目数：{summary['project_count']}；高潜候选：{summary['high_potential']}。",
            "- 说明：D1-D3/D7 早期预测只用于探索排序，不作为ROI强停测依据。",
            "",
            "| 项目 | 阶段 | 潜力分 | LTV曲线 | 推荐国家 | 驱动因素 |",
            "|---|---|---:|---|---|---|",
        ]
        for item in payload["items"]:
            lines.append(
                f"| {item['project']} | {item['stage']} | {item['predicted_scale_potential']:.2f} | "
                f"{item['predicted_ltv_curve']} | {', '.join(item['predicted_best_geo']) or 'unknown'} | {'；'.join(item['drivers'][:3])} |"
            )
        if not payload["items"]:
            lines.append("| 暂无 | - | 0 | unknown | unknown | 暂无 |")
        lines.append("")
        return "\n".join(lines)
