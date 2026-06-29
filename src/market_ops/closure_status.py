from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class ClosureStatusResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ClosureStatusBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ClosureStatusResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"closure_status_{suffix}.md"
        json_path = output_dir / f"closure_status_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        preview_paths = payload.get("preview_paths") or {}
        if preview_paths:
            write_preview_overview(
                report_date,
                output_dir / f"weekly_preview_overview_{suffix}.md",
                summary_markdown=Path(preview_paths["summary_markdown"]),
                summary_json=Path(preview_paths["summary_json"]),
                index_markdown=Path(preview_paths["index_markdown"]),
                boss_markdown=Path(preview_paths["boss_markdown"]),
                market_markdown=Path(preview_paths["market_markdown"]),
                market_detail_markdown=Path(preview_paths["market_detail_markdown"]),
                recovery_markdown=Path(preview_paths["recovery_markdown"]),
                self_check_markdown=output_dir / f"self_check_{suffix}.md",
                report_audit_markdown=output_dir / f"report_audit_{suffix}.md",
                pre_send_summary_markdown=output_dir / f"pre_send_summary_{suffix}.md",
                health_check_markdown=output_dir / f"weekly_health_check_{suffix}.md",
                creative_source_readiness_markdown=output_dir / f"creative_source_readiness_{suffix}.md",
                data_quality_audit_markdown=(output_dir / f"data_quality_audit_{suffix}.md") if (output_dir / f"data_quality_audit_{suffix}.md").exists() else None,
                creative_attribution_audit_markdown=output_dir / f"creative_attribution_audit_{suffix}.md",
                google_creative_repair_audit_markdown=output_dir / f"google_creative_repair_audit_{suffix}.md",
                tecdo_probe_markdown=(output_dir / f"tecdo_probe_{suffix}.md") if (output_dir / f"tecdo_probe_{suffix}.md").exists() else None,
                tecdo_account_reconciliation_markdown=(output_dir / f"tecdo_account_reconciliation_{suffix}.md") if (output_dir / f"tecdo_account_reconciliation_{suffix}.md").exists() else None,
                tecdo_sync_checklist_markdown=(output_dir / f"tecdo_sync_checklist_{suffix}.md") if (output_dir / f"tecdo_sync_checklist_{suffix}.md").exists() else None,
                closure_status_markdown=markdown_path,
                project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md") if (output_dir / f"project_detail_coverage_{suffix}.md").exists() else None,
                p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{suffix}.md") if (output_dir / f"p04_source_checklist_{suffix}.md").exists() else None,
                detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{suffix}.md") if (output_dir / f"detail_reply_checklist_{suffix}.md").exists() else None,
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md") if (output_dir / f"management_action_list_{suffix}.md").exists() else None,
            )
        return ClosureStatusResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        self_check = self._load_json(output_dir / f"self_check_{suffix}.json")
        report_audit = self._load_json(output_dir / f"report_audit_{suffix}.json")
        pre_send = self._load_json(output_dir / f"pre_send_summary_{suffix}.json")
        creative_readiness = self._load_json(output_dir / f"creative_source_readiness_{suffix}.json")
        tecdo_probe = self._load_json(output_dir / f"tecdo_probe_{suffix}.json")
        google_repair = self._load_json(output_dir / f"google_creative_repair_audit_{suffix}.json")
        project_detail_coverage = self._load_json(output_dir / f"project_detail_coverage_{suffix}.json")
        p04_source_checklist = self._load_json(output_dir / f"p04_source_checklist_{suffix}.json")
        detail_reply_checklist = self._load_json(output_dir / f"detail_reply_checklist_{suffix}.json")
        tecdo_sync_checklist = self._load_json(output_dir / f"tecdo_sync_checklist_{suffix}.json")
        management_action_list = self._load_json(output_dir / f"management_action_list_{suffix}.json")

        preview_paths = (self_check.get("preview_paths") or {}) if isinstance(self_check, dict) else {}
        observed_path = output_dir / "feishu_detail_chat_observations.json"
        observed = self._load_json(observed_path).get("items", []) if observed_path.exists() else []
        real_chat_ids = [str(item.get("chat_id") or "") for item in observed if str(item.get("chat_id") or "").startswith("oc_")]
        trusted_projects = sorted(self._settings.trusted_detail_project_keys)

        items = [
            self._build_gate_item(self_check, report_audit, pre_send),
            self._build_detail_reply_item(real_chat_ids, observed_path),
            self._build_project_detail_item(trusted_projects, project_detail_coverage),
            self._build_tecdo_item(creative_readiness, tecdo_probe, tecdo_sync_checklist),
            self._build_google_item(creative_readiness, google_repair),
            self._build_boss_send_item(),
        ]
        passed = all(bool(item.get("ready")) for item in items if item.get("category") in {"核心门禁"})
        return {
            "report_date": report_date.isoformat(),
            "passed": passed,
            "summary": {
                "ready_count": sum(1 for item in items if item.get("ready")),
                "blocked_count": sum(1 for item in items if item.get("status") == "blocked"),
                "pending_count": sum(1 for item in items if item.get("status") == "pending"),
                "trusted_detail_projects": trusted_projects,
                "real_detail_chat_ids": real_chat_ids,
            },
            "blocking_summary": self._build_blocking_summary(
                items=items,
                report_date=report_date,
                output_dir=output_dir,
                p04_source_checklist=p04_source_checklist,
                detail_reply_checklist=detail_reply_checklist,
                tecdo_sync_checklist=tecdo_sync_checklist,
            ),
            "preview_paths": preview_paths,
            "items": items,
            "management_action_list": management_action_list,
        }

    def _build_blocking_summary(
        self,
        *,
        items: list[dict[str, Any]],
        report_date: date,
        output_dir: Path,
        p04_source_checklist: dict[str, Any],
        detail_reply_checklist: dict[str, Any],
        tecdo_sync_checklist: dict[str, Any],
    ) -> list[dict[str, Any]]:
        suffix = report_date.strftime("%Y%m%d")
        checklist_map = {
            "项目级可信飞书明细": {
                "path": str(output_dir / f"p04_source_checklist_{suffix}.md"),
                "root_cause": str((p04_source_checklist.get("summary") or {}).get("root_cause") or ""),
            },
            "详细版群内回复": {
                "path": str(output_dir / f"detail_reply_checklist_{suffix}.md"),
                "root_cause": str((detail_reply_checklist.get("summary") or {}).get("root_cause") or ""),
            },
            "TecDo 代理素材源": {
                "path": str(output_dir / f"tecdo_sync_checklist_{suffix}.md"),
                "root_cause": str((tecdo_sync_checklist.get("summary") or {}).get("root_cause") or ""),
            },
        }
        summary: list[dict[str, Any]] = []
        for item in items:
            if item.get("ready"):
                continue
            extra = checklist_map.get(str(item.get("name") or ""), {})
            summary.append(
                {
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "risk_level": item.get("risk_level"),
                    "reason": item.get("reason"),
                    "next_action": item.get("next_action"),
                    "checklist_path": extra.get("path", ""),
                    "root_cause": extra.get("root_cause", ""),
                }
            )
        return summary

    def _build_gate_item(self, self_check: dict[str, Any], report_audit: dict[str, Any], pre_send: dict[str, Any]) -> dict[str, Any]:
        self_check_passed = bool(self_check.get("passed"))
        report_audit_passed = bool(report_audit.get("passed"))
        pre_send_passed = bool(pre_send.get("passed"))
        ready = self_check_passed and report_audit_passed and pre_send_passed
        reasons: list[str] = []
        if not self_check_passed:
            reasons.append("自检未通过")
        if not report_audit_passed:
            reasons.append("审计未通过")
        if not pre_send_passed:
            reasons.append("发送前结论页未通过")
        return {
            "category": "核心门禁",
            "name": "市场版发群门禁",
            "status": "ready" if ready else "blocked",
            "ready": ready,
            "risk_level": "low" if ready else "high",
            "reason": "；".join(reasons) if reasons else "自检、审计、发送前结论页均已通过",
            "next_action": "继续按当前链路预览或发群" if ready else "先修复门禁失败项，再重新生成预览",
            "owner": "系统",
            "evidence": [
                str(self_check.get("path") or self_check.get("json_path") or ""),
                str(report_audit.get("path") or ""),
                str(pre_send.get("path") or ""),
            ],
        }

    def _build_detail_reply_item(self, real_chat_ids: list[str], observed_path: Path) -> dict[str, Any]:
        allowlist = list(self._settings.feishu_detail_allowed_chat_ids or [])
        if allowlist:
            return {
                "category": "详细版回复",
                "name": "详细版群内回复",
                "status": "ready",
                "ready": True,
                "risk_level": "low",
                "reason": f"已锁定允许群：{', '.join(allowlist)}",
                "next_action": "保持当前 allowlist 配置，仅在新增群时更新",
                "owner": "系统",
                "evidence": [str(observed_path)],
            }
        if real_chat_ids:
            return {
                "category": "详细版回复",
                "name": "详细版群内回复",
                "status": "pending",
                "ready": False,
                "risk_level": "medium",
                "reason": f"已观察到真实群 chat_id，但尚未写回 allowlist：{', '.join(real_chat_ids[:3])}",
                "next_action": "把真实群 chat_id 写回 FEISHU_DETAIL_ALLOWED_CHAT_IDS 后再放开详细版",
                "owner": "你",
                "evidence": [str(observed_path)],
            }
        return {
            "category": "详细版回复",
            "name": "详细版群内回复",
            "status": "pending",
            "ready": False,
            "risk_level": "medium",
            "reason": "尚未观察到真实 oc_ 群 chat_id；当前系统已切到安全模式，未锁群时只观测、不自动回复详细版。",
            "next_action": "先在真实群触发一次 @机器人 详情，再收集真实群 chat_id 并写回 allowlist。",
            "owner": "系统",
            "evidence": [str(observed_path)],
        }

    @staticmethod
    def _build_project_detail_item(trusted_projects: list[str], project_detail_coverage: dict[str, Any]) -> dict[str, Any]:
        expected = {"P02", "P04", "P07"}
        trusted = set(trusted_projects)
        missing = sorted(expected - trusted)
        blocking_missing = [item for item in missing if item != "P04"]
        enhancement_gap = "P04" in missing and not blocking_missing
        ready = not missing
        p04_row = next(
            (row for row in (project_detail_coverage.get("rows") or []) if str(row.get("project_key") or "") == "P04"),
            {},
        )
        if not blocking_missing and p04_row and "P04" in missing:
            reason = "P02、P07 已有可信项目级明细；P04 当前仍缺独立项目级飞书映射，已降级为项目精度增强项，不再阻塞主链路。"
            next_action = str(p04_row.get("next_action") or "")
        elif not ready and p04_row:
            reason = str(p04_row.get("reason") or "")
            next_action = str(p04_row.get("next_action") or "")
        else:
            reason = (
                f"当前可信项目明细已覆盖：{', '.join(trusted_projects)}"
                if ready
                else f"当前可信项目明细仅覆盖：{', '.join(trusted_projects) or '无'}；缺少：{', '.join(missing)}"
            )
            next_action = "继续沿用当前项目明细口径" if ready else "补齐缺失项目的独立飞书明细映射，避免项目判断混入口径风险"
        return {
            "category": "项目明细",
            "name": "项目级可信飞书明细",
            "status": "enhancement_pending" if enhancement_gap else ("ready" if not blocking_missing else "pending"),
            "ready": not blocking_missing,
            "risk_level": "low" if not blocking_missing else "medium",
            "reason": reason,
            "next_action": next_action,
            "owner": "系统",
            "evidence": [],
        }

    def _build_tecdo_item(
        self,
        creative_readiness: dict[str, Any],
        tecdo_probe: dict[str, Any],
        tecdo_sync_checklist: dict[str, Any],
    ) -> dict[str, Any]:
        summary = creative_readiness.get("summary") or {}
        probe_status = str(summary.get("tecdo_probe_status") or tecdo_probe.get("status") or "")
        has_rows = summary.get("tecdo_probe_has_rows")
        business_status = str(summary.get("tecdo_business_status") or "")
        root_cause = str((tecdo_sync_checklist.get("summary") or {}).get("root_cause") or "")
        if probe_status == "ok" and has_rows is True:
            return {
                "category": "素材数据",
                "name": "TecDo 代理素材源",
                "status": "ready",
                "ready": True,
                "risk_level": "low",
                "reason": business_status or "TecDo 已授权且探针窗口有报表行，可进入代理素材分析",
                "next_action": "继续按当前接口拉取代理素材数据",
                "owner": "系统",
                "evidence": [],
            }
        if probe_status in {"ok", "sync_pending"} and has_rows is False:
            return {
                "category": "素材数据",
                "name": "TecDo 代理素材源",
                "status": "pending",
                "ready": False,
                "risk_level": "medium",
                "reason": business_status or "TecDo 已授权，但当前报表数据还未同步完成",
                "next_action": "等待 TecDo 完成数据同步后，重新跑 tecdo-probe 和 tecdo-account-reconciliation",
                "owner": "你",
                "evidence": [root_cause] if root_cause else [],
            }
        return {
            "category": "素材数据",
            "name": "TecDo 代理素材源",
            "status": "blocked",
            "ready": False,
            "risk_level": "high",
            "reason": business_status or "TecDo 当前还不具备稳定素材数据输入条件",
            "next_action": "先完成 TecDo 授权或后台报表核对，再恢复素材链路",
            "owner": "你",
            "evidence": [root_cause] if root_cause else [],
        }

    def _build_google_item(self, creative_readiness: dict[str, Any], google_repair: dict[str, Any]) -> dict[str, Any]:
        summary = creative_readiness.get("summary") or {}
        if summary.get("tecdo_is_formal_source"):
            return {
                "category": "素材数据",
                "name": "Google 素材源",
                "status": "ready",
                "ready": True,
                "risk_level": "low",
                "reason": "Google 当前已由 TecDo 代理素材源承接，可继续做广告层代理素材分析。",
                "next_action": "继续沿用 TecDo + Google 修复链路；如需原生 creative id 再补 Google 官方凭证。",
                "owner": "系统",
                "evidence": [],
            }
        if summary.get("google_can_run_now"):
            return {
                "category": "素材数据",
                "name": "Google 素材源",
                "status": "ready",
                "ready": True,
                "risk_level": "low",
                "reason": "Google Ads live 凭证已接通，可直接进入素材级分析",
                "next_action": "继续按 Google 官方素材接口 + 素材修复链路输出素材级结论",
                "owner": "系统",
                "evidence": [],
            }
        placeholder_share = float(google_repair.get("placeholder_cost_share") or 0.0)
        if summary.get("google_resolver_ready"):
            return {
                "category": "素材数据",
                "name": "Google 素材源",
                "status": "pending",
                "ready": False,
                "risk_level": "medium",
                "reason": f"Google 解析层已接入，但 Google Ads 直连接口凭证缺失，占位素材花费占比 {placeholder_share:.1%}",
                "next_action": "补齐 Google Ads 凭证后，再把解析候选还原到素材 ID 层",
                "owner": "你",
                "evidence": [],
            }
        return {
            "category": "素材数据",
            "name": "Google 素材源",
            "status": "blocked",
            "ready": False,
            "risk_level": "high",
            "reason": "Google live 素材源和解析层当前都不足以支持可信素材分析",
            "next_action": "先补 Google Ads 凭证，再验证素材解析链路",
            "owner": "你",
            "evidence": [],
        }

    def _build_boss_send_item(self) -> dict[str, Any]:
        ready = bool(self._settings.allow_boss_send and (self._settings.feishu_boss_webhook or "").strip())
        return {
            "category": "管理层发送",
            "name": "老板群发送策略",
            "status": "ready",
            "ready": True,
            "risk_level": "low",
            "reason": "老板群当前按手动发送策略运行。" if not ready else "老板群自动发送已放开",
            "next_action": "保持当前策略；如需改成自动发送，再放开老板群 webhook。" if not ready else "继续自动发送",
            "owner": "系统",
            "evidence": [],
        }

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Closure Status | {payload['report_date']}",
            "",
            f"- Overall: {'Main path closed and ready for incremental improvements' if payload.get('passed') else 'Critical gaps remain'}",
            f"- Ready: {summary.get('ready_count', 0)}",
            f"- Pending: {summary.get('pending_count', 0)}",
            f"- Blocked: {summary.get('blocked_count', 0)}",
            "",
            "## Top Priorities",
            "",
        ]
        blocking_summary = payload.get("blocking_summary") or []
        if blocking_summary:
            for item in blocking_summary[:5]:
                lines.extend(
                    [
                        f"### {item.get('name', '')}",
                        f"- Status: {item.get('status', '')}",
                        f"- Risk: {item.get('risk_level', '')}",
                        f"- Current reason: {item.get('reason', '')}",
                        f"- Root cause: {item.get('root_cause', '') or 'See current reason'}",
                        f"- Next action: {item.get('next_action', '')}",
                        f"- Checklist: {item.get('checklist_path', '') or 'none'}",
                        "",
                    ]
                )
        else:
            lines.extend(["- No open closure gaps at the moment.", ""])

        lines.extend(["## Current Status", ""])
        for item in payload.get("items") or []:
            lines.extend(
                [
                    f"### {item.get('name', '')}",
                    f"- Category: {item.get('category', '')}",
                    f"- Status: {item.get('status', '')}",
                    f"- Risk: {item.get('risk_level', '')}",
                    f"- Reason: {item.get('reason', '')}",
                    f"- Next action: {item.get('next_action', '')}",
                    f"- Owner suggestion: {item.get('owner', '')}",
                    "",
                ]
            )
        return "\n".join(lines)
