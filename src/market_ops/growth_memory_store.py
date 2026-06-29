from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.learning_memory import LearningMemoryBuilder


@dataclass(slots=True)
class GrowthMemoryStoreResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class GrowthMemoryStoreBuilder:
    """Builds the long-term audited growth memory ledger from weekly learning records."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> GrowthMemoryStoreResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        LearningMemoryBuilder(self._settings).build(report_date)
        payload = self.build_payload(report_date)

        markdown_path = output_dir / "growth_memory_store_latest.md"
        json_path = output_dir / "growth_memory_store_latest.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return GrowthMemoryStoreResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        records: dict[str, dict[str, Any]] = {}
        source_files: list[str] = []
        for path in sorted(self._settings.active_output_dir.glob("learning_memory_*.json")):
            payload = _load_json(path)
            if not payload:
                continue
            source_files.append(str(path))
            for record in payload.get("records") or []:
                key = str(record.get("learning_id") or record.get("action_id") or "")
                if not key:
                    continue
                records[key] = _merge_record(records.get(key), record, payload.get("report_date"))

        all_records = list(records.values())
        closed = [item for item in all_records if item.get("learning_state") == "closed"]
        pending = [item for item in all_records if item.get("learning_state") != "closed"]
        closed_discovery_patterns = [
            item
            for item in closed
            if str(item.get("source_type") or "") == "discovery_slot_result_ingestion"
            and str(item.get("pattern_memory_state") or "") == "pattern_memory_closed"
        ]
        pending_discovery_patterns = [
            item
            for item in all_records
            if str(item.get("source_type") or "") == "discovery_slot_result_ingestion"
            and str(item.get("pattern_memory_state") or "") != "pattern_memory_closed"
        ]
        tags = Counter(tag for item in all_records for tag in (item.get("growth_memory_tags") or []))
        projects = Counter(item.get("project") or "unknown" for item in all_records)

        return {
            "report_date": report_date.isoformat(),
            "mode": "long_term_growth_memory_store",
            "passed": True,
            "source_files": source_files,
            "summary": {
                "total_records": len(all_records),
                "closed_records": len(closed),
                "pending_records": len(pending),
                "closed_discovery_pattern_count": len(closed_discovery_patterns),
                "pending_discovery_pattern_count": len(pending_discovery_patterns),
                "tag_counts": dict(tags.most_common()),
                "project_counts": dict(projects.most_common()),
            },
            "closed_memory": sorted(closed, key=lambda item: item.get("last_seen_report_date") or "", reverse=True),
            "pending_memory": sorted(pending, key=lambda item: item.get("last_seen_report_date") or "", reverse=True),
            "closed_discovery_patterns": sorted(
                closed_discovery_patterns,
                key=lambda item: item.get("last_seen_report_date") or "",
                reverse=True,
            ),
            "pending_discovery_patterns": sorted(
                pending_discovery_patterns,
                key=lambda item: item.get("last_seen_report_date") or "",
                reverse=True,
            ),
            "next_learning_actions": [_next_learning_action(item) for item in pending[:30]],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            "# Growth Memory Store",
            "",
            f"- As of: {payload['report_date']}",
            "- Mode: long_term_growth_memory_store",
            f"- Total records: {summary['total_records']}",
            f"- Closed records: {summary['closed_records']}",
            f"- Pending records: {summary['pending_records']}",
            f"- Closed discovery patterns: {summary['closed_discovery_pattern_count']}",
            f"- Pending discovery patterns: {summary['pending_discovery_pattern_count']}",
            "",
            "## Tags",
            "",
        ]
        if not summary["tag_counts"]:
            lines.append("- None.")
        for tag, count in summary["tag_counts"].items():
            lines.append(f"- {tag}: {count}")

        lines.extend(["", "## Closed Memory", ""])
        if not payload["closed_memory"]:
            lines.append("- None yet.")
        for item in payload["closed_memory"][:30]:
            lines.append(
                f"- {item['learning_id']} | project={item.get('project') or 'unknown'} | "
                f"success={item.get('success')} | tags={','.join(item.get('growth_memory_tags') or [])}"
            )

        lines.extend(["", "## Closed Discovery Patterns", ""])
        if not payload["closed_discovery_patterns"]:
            lines.append("- None yet.")
        for item in payload["closed_discovery_patterns"][:30]:
            lines.append(
                f"- {item['learning_id']} | key={item.get('reusable_pattern_key') or ''} | "
                f"focus={item.get('change_focus') or ''} | success={item.get('success')}"
            )

        lines.extend(["", "## Pending Memory", ""])
        if not payload["pending_memory"]:
            lines.append("- None.")
        for item in payload["pending_memory"][:30]:
            missing = ", ".join(item.get("missing_fields") or [])
            lines.append(f"- {item['learning_id']} | {item['learning_state']} | missing={missing}")

        lines.extend(["", "## Pending Discovery Patterns", ""])
        if not payload["pending_discovery_patterns"]:
            lines.append("- None.")
        for item in payload["pending_discovery_patterns"][:30]:
            lines.append(
                f"- {item['learning_id']} | state={item.get('pattern_memory_state') or ''} | "
                f"key={item.get('reusable_pattern_key') or ''}"
            )

        lines.extend(["", "## Next Learning Actions", ""])
        if not payload["next_learning_actions"]:
            lines.append("- None.")
        for item in payload["next_learning_actions"]:
            lines.append(f"- {item['learning_id']} | {item['required_update']}")
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _merge_record(existing: dict[str, Any] | None, incoming: dict[str, Any], report_date: str | None) -> dict[str, Any]:
    if not existing:
        merged = dict(incoming)
        merged["first_seen_report_date"] = report_date or incoming.get("due_date") or ""
        merged["last_seen_report_date"] = report_date or incoming.get("due_date") or ""
        return merged
    merged = dict(existing)
    if incoming.get("learning_state") == "closed" or merged.get("learning_state") != "closed":
        merged.update(incoming)
    merged["first_seen_report_date"] = existing.get("first_seen_report_date") or report_date or ""
    merged["last_seen_report_date"] = report_date or existing.get("last_seen_report_date") or ""
    return merged


def _next_learning_action(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_id": item.get("learning_id", ""),
        "action_id": item.get("action_id", ""),
        "project": item.get("project", ""),
        "required_update": item.get("next_update_required", "Add actual result note and pass/fail status."),
        "missing_fields": item.get("missing_fields", []),
        "tags": item.get("growth_memory_tags", []),
    }
