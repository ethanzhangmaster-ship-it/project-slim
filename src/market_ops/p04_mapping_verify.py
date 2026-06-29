from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings


@dataclass(slots=True)
class P04MappingVerifyResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class P04MappingVerifyBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date, sync_summary: dict[str, Any], coverage_payload: dict[str, Any]) -> P04MappingVerifyResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        row = next(
            (item for item in (coverage_payload.get("rows") or []) if str(item.get("project_key") or "") == "P04"),
            {},
        )
        payload = {
            "report_date": report_date.isoformat(),
            "sync_summary": sync_summary,
            "p04": {
                "status": str(row.get("status") or "unknown"),
                "trusted": bool(row.get("trusted")),
                "detail_row_count": int(row.get("detail_row_count") or 0),
                "daily_url": str(row.get("daily_url") or ""),
                "roi_url": str(row.get("roi_url") or ""),
                "reason": str(row.get("reason") or ""),
                "next_action": str(row.get("next_action") or ""),
            },
            "passed": bool(row.get("trusted")) and int(row.get("detail_row_count") or 0) > 0,
        }
        markdown_path = output_dir / f"p04_mapping_verify_{suffix}.md"
        json_path = output_dir / f"p04_mapping_verify_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return P04MappingVerifyResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        p04 = payload.get("p04") or {}
        sync_summary = payload.get("sync_summary") or {}
        lines = [
            f"# P04 映射验证结果 | {payload['report_date']}",
            "",
            f"- 验证结论：{'通过' if payload.get('passed') else '未通过'}",
            f"- 同步后 ads_rows：{sync_summary.get('ads_rows', 0)}",
            f"- 同步后 adjust_rows：{sync_summary.get('adjust_rows', 0)}",
            f"- P04 状态：{p04.get('status', '')}",
            f"- P04 是否 trusted：{'是' if p04.get('trusted') else '否'}",
            f"- P04 明细行数：{p04.get('detail_row_count', 0)}",
            f"- P04 Daily 来源：{p04.get('daily_url', '') or '未解析到'}",
            f"- P04 ROI 来源：{p04.get('roi_url', '') or '未解析到'}",
            f"- 当前原因：{p04.get('reason', '')}",
            f"- 下一步：{p04.get('next_action', '')}",
            "",
        ]
        return "\n".join(lines)
