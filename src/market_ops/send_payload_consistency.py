from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.card_preview import CardPreviewPaths
from market_ops.manual_broadcast import BroadcastArtifacts, build_artifacts


@dataclass(slots=True)
class PayloadConsistencyIssue:
    card_name: str
    path: str
    message: str
    actual: str
    expected: str


@dataclass(slots=True)
class PayloadConsistencyResult:
    passed: bool
    issues: list[PayloadConsistencyIssue]
    markdown_path: Path
    json_path: Path


class SendPayloadConsistencyBuilder:
    def build(
        self,
        *,
        report_date: date,
        meeting_name: str,
        output_dir: Path,
        artifacts: BroadcastArtifacts | None = None,
        preview_paths: CardPreviewPaths | None = None,
    ) -> PayloadConsistencyResult:
        artifacts = artifacts or build_artifacts(report_date, meeting_name)
        if preview_paths is None:
            raise ValueError("preview_paths is required for payload consistency audit.")

        suffix = report_date.strftime("%Y%m%d")
        markdown_path = output_dir / f"send_payload_consistency_{suffix}.md"
        json_path = output_dir / f"send_payload_consistency_{suffix}.json"

        card_pairs = [
            ("summary", artifacts.summary_card, preview_paths.summary_json),
            ("boss", artifacts.boss_card, preview_paths.boss_json),
            ("market_simple", artifacts.market_simple_card, preview_paths.market_json),
            ("market_detail", artifacts.market_detailed_card, preview_paths.market_detail_json),
            ("recovery", artifacts.recovery_card, preview_paths.recovery_json),
        ]

        issues: list[PayloadConsistencyIssue] = []
        checks: list[dict[str, Any]] = []
        for card_name, expected_card, preview_json_path in card_pairs:
            file_exists = preview_json_path.exists()
            actual_card = self._load_json_if_exists(preview_json_path) if file_exists else None
            passed = file_exists and actual_card is not None and self._canonicalize(actual_card) == self._canonicalize(expected_card)
            diff_path, actual_value, expected_value = self._first_diff(actual_card, expected_card) if actual_card is not None else ("<missing>", "", "")
            checks.append(
                {
                    "card_name": card_name,
                    "preview_json_path": str(preview_json_path),
                    "exists": file_exists,
                    "passed": passed,
                    "first_diff_path": diff_path,
                    "actual": actual_value,
                    "expected": expected_value,
                }
            )
            if passed:
                continue
            message = "saved preview JSON does not match the current builder payload"
            if not file_exists:
                message = "saved preview JSON is missing"
            elif actual_card is None:
                message = "saved preview JSON is unreadable"
            issues.append(
                PayloadConsistencyIssue(
                    card_name=card_name,
                    path=str(preview_json_path),
                    message=message,
                    actual=actual_value,
                    expected=expected_value,
                )
            )

        payload = {
            "report_date": report_date.isoformat(),
            "meeting_name": meeting_name,
            "passed": not issues,
            "checks": checks,
            "issues": [asdict(item) for item in issues],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        return PayloadConsistencyResult(
            passed=not issues,
            issues=issues,
            markdown_path=markdown_path,
            json_path=json_path,
        )

    @staticmethod
    def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _canonicalize(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _first_diff(self, actual: Any, expected: Any, path: str = "$") -> tuple[str, str, str]:
        if actual == expected:
            return path, self._short(actual), self._short(expected)
        if type(actual) is not type(expected):
            return path, self._short(actual), self._short(expected)
        if isinstance(actual, dict):
            keys = sorted(set(actual.keys()) | set(expected.keys()))
            for key in keys:
                if key not in actual:
                    return f"{path}.{key}", "<missing>", self._short(expected.get(key))
                if key not in expected:
                    return f"{path}.{key}", self._short(actual.get(key)), "<missing>"
                diff = self._first_diff(actual.get(key), expected.get(key), f"{path}.{key}")
                if diff[1] != diff[2]:
                    return diff
            return path, self._short(actual), self._short(expected)
        if isinstance(actual, list):
            if len(actual) != len(expected):
                return f"{path}.length", str(len(actual)), str(len(expected))
            for index, (left, right) in enumerate(zip(actual, expected)):
                diff = self._first_diff(left, right, f"{path}[{index}]")
                if diff[1] != diff[2]:
                    return diff
            return path, self._short(actual), self._short(expected)
        return path, self._short(actual), self._short(expected)

    @staticmethod
    def _short(value: Any) -> str:
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        return text if len(text) <= 180 else f"{text[:177]}..."

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        lines = [
            f"# 发送载荷一致性审计 | {payload['report_date']}",
            "",
            f"- 结果：{'通过' if payload.get('passed') else '失败'}",
            "",
            "## 检查项",
            "",
        ]
        for check in payload.get("checks") or []:
            lines.append(
                f"- {check['card_name']}：{'一致' if check.get('passed') else '不一致'} | {check['preview_json_path']}"
            )
            if not check.get("passed"):
                lines.append(f"  首个差异：{check.get('first_diff_path')}")
                if check.get("actual"):
                    lines.append(f"  当前值：{check.get('actual')}")
                if check.get("expected"):
                    lines.append(f"  预期值：{check.get('expected')}")
        if payload.get("issues"):
            lines.extend(["", "## 失败项", ""])
            for issue in payload["issues"]:
                lines.append(
                    f"- {issue['card_name']} | {issue['message']} | path={issue['path']} | 当前值={issue['actual']} | 预期值={issue['expected']}"
                )
        return "\n".join(lines) + "\n"
