from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from market_ops.config import Settings
from market_ops.executive_report import ExecutiveReportBuilder
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class DataQualityAuditResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DataQualityAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)
        self._executive = ExecutiveReportBuilder(settings)

    def build(self, report_date: date) -> DataQualityAuditResult:
        report_date = self._align_to_weekly(report_date)
        window_start = report_date - timedelta(days=6)
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        ads_rows = self._repo.load_ads_performance()
        creative_rows = self._repo.load_creative_library()
        revenue_rows = self._repo.load_adjust_revenue()
        breakdown_rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        confidence = self._executive._build_confidence_scores(  # noqa: SLF001
            [row for row in revenue_rows if window_start <= row.date <= report_date],
            [row for row in breakdown_rows if window_start <= row.date <= report_date],
            [row for row in creative_rows if row.spend > 0 or row.installs > 0 or row.revenue_value > 0 or row.roas > 0],
        )
        confidence_map = {item.module: item for item in confidence}
        anomalies = self._executive._build_anomalies(  # noqa: SLF001
            current_revenue_rows=[row for row in revenue_rows if window_start <= row.date <= report_date],
            current_breakdown_rows=[row for row in breakdown_rows if window_start <= row.date <= report_date],
            current_creative_rows=[row for row in creative_rows if row.spend > 0 or row.installs > 0 or row.revenue_value > 0 or row.roas > 0],
            current_ads_rows=[row for row in ads_rows if window_start <= row.date <= report_date],
            confidence_scores=confidence,
        )

        payload = self._build_payload(report_date, window_start, confidence_map, anomalies, breakdown_rows, creative_rows)
        markdown_path = output_dir / f"data_quality_audit_{suffix}.md"
        json_path = output_dir / f"data_quality_audit_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DataQualityAuditResult(markdown_path=markdown_path, json_path=json_path, passed=payload["passed"])

    @staticmethod
    def _align_to_weekly(report_date: date) -> date:
        weekday = report_date.weekday()
        if weekday == 2:
            return report_date
        offset = (weekday - 2) % 7
        return report_date - timedelta(days=offset)

    def _build_payload(self, report_date: date, window_start: date, confidence_map, anomalies, breakdown_rows, creative_rows) -> dict:
        fb_conf = confidence_map.get("Facebook素材")
        google_conf = confidence_map.get("Google素材")
        spend_conf = confidence_map.get("花费")
        revenue_conf = confidence_map.get("收入")
        roi_conf = confidence_map.get("ROI")
        structure_conf = confidence_map.get("公司盈利结构")

        paid_breakdown_rows = [row for row in breakdown_rows if getattr(row, "cost", 0) > 0]
        breakdown_with_creative = [
            row for row in paid_breakdown_rows
            if str(getattr(row, "creative_id", "") or "").strip() or str(getattr(row, "creative_name", "") or "").strip()
        ]
        creative_coverage = (len(breakdown_with_creative) / len(paid_breakdown_rows)) if paid_breakdown_rows else 0.0
        usable_creative_rows = [row for row in creative_rows if row.spend > 0 or row.installs > 0 or row.revenue_value > 0 or row.roas > 0]
        effective_samples = [row for row in usable_creative_rows if row.spend >= 50 or row.installs >= 20]

        modules = [
            self._module_payload("花费", spend_conf, "可直接用于经营花费决策" if spend_conf and spend_conf.level == "高" else "先校对跨源花费"),
            self._module_payload("收入", revenue_conf, "可直接用于经营收入决策" if revenue_conf and revenue_conf.level == "高" else "先校对收入归因"),
            self._module_payload("ROI", roi_conf, "可直接用于ROI判断" if roi_conf and roi_conf.level == "高" else "先校对 ROI 口径"),
            self._module_payload("公司盈利结构", structure_conf, "可直接用于商店/渠道结构判断" if structure_conf and structure_conf.level == "高" else "结构结论仅作观察或暂缓输出"),
            self._module_payload("Facebook素材", fb_conf, "可做方向判断" if fb_conf and fb_conf.level != "低" else "仅观察，不下强素材结论"),
            self._module_payload("Google素材", google_conf, "可做代理层方向判断" if google_conf and google_conf.level != "低" else "仅观察，不下强素材结论"),
        ]

        passed = all((item.get("level") != "低" for item in modules[:3]))
        top_risks = self._aggregate_anomalies(anomalies)
        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": passed,
            "modules": modules,
            "summary": {
                "paid_breakdown_rows": len(paid_breakdown_rows),
                "creative_signal_coverage": creative_coverage,
                "creative_rows_loaded": len(usable_creative_rows),
                "effective_creative_samples": len(effective_samples),
                "anomaly_count": len(anomalies),
                "unique_anomaly_count": len(top_risks),
            },
            "top_risks": top_risks[:12],
        }

    @staticmethod
    def _aggregate_anomalies(anomalies) -> list[dict]:
        severity_rank = {"高": 3, "中": 2, "低": 1}
        grouped: dict[tuple[str, str], dict] = {}
        for item in anomalies or []:
            key = (str(item.anomaly_type), str(item.scope))
            current = grouped.setdefault(
                key,
                {
                    "type": item.anomaly_type,
                    "scope": item.scope,
                    "severity": item.severity,
                    "message": item.message,
                    "count": 0,
                    "examples": [],
                },
            )
            current["count"] += 1
            if len(current["examples"]) < 3:
                current["examples"].append(item.message)
            if severity_rank.get(str(item.severity), 0) > severity_rank.get(str(current["severity"]), 0):
                current["severity"] = item.severity
                current["message"] = item.message
        return sorted(
            grouped.values(),
            key=lambda item: (-severity_rank.get(str(item.get("severity")), 0), -int(item.get("count") or 0), str(item.get("scope") or "")),
        )

    @staticmethod
    def _module_payload(name: str, score_obj, recommendation: str) -> dict:
        if score_obj is None:
            return {"module": name, "score": 0, "level": "低", "risk": "高", "status": "缺失", "reasons": ["当前无数据"], "recommendation": recommendation}
        return {
            "module": name,
            "score": score_obj.score,
            "level": score_obj.level,
            "risk": score_obj.risk_level,
            "status": score_obj.status,
            "reasons": score_obj.reasons,
            "recommendation": recommendation,
        }

    def _render_markdown(self, payload: dict) -> str:
        lines = [
            f"# 数据质量审计 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}",
            f"- 总状态：{'通过' if payload['passed'] else '未通过'}",
            "",
            "## 模块可信度",
            "",
        ]
        for item in payload["modules"]:
            reasons = "；".join(item["reasons"]) if item["reasons"] else "当前无明显缺口"
            lines.append(
                f"- {item['module']}：{item['score']}分 | {item['level']} | 风险={item['risk']} | {item['status']} | {reasons} | 建议：{item['recommendation']}"
            )
        summary = payload["summary"]
        lines.extend(
            [
                "",
                "## 素材数据覆盖",
                "",
                f"- Adjust paid breakdown 行数：{summary['paid_breakdown_rows']}",
                f"- breakdown 素材信号覆盖率：{summary['creative_signal_coverage']:.1%}",
                f"- 已加载素材行数：{summary['creative_rows_loaded']}",
                f"- 达样本门槛素材数：{summary['effective_creative_samples']}",
                f"- 异常数：{summary['anomaly_count']}（聚合后 {summary.get('unique_anomaly_count', 0)} 类）",
            ]
        )
        lines.extend(["", "## 主要风险", ""])
        if payload["top_risks"]:
            for item in payload["top_risks"]:
                count_text = f" | 出现 {item.get('count')} 次" if int(item.get("count") or 0) > 1 else ""
                lines.append(f"- [{item['severity']}] {item['type']} | {item['scope']}{count_text} | {item['message']}")
        else:
            lines.append("- 当前没有检测到异常。")
        lines.append("")
        return "\n".join(lines)
