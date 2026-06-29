from __future__ import annotations

import base64
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any

from Crypto.Cipher import AES

from market_ops.clients.feishu_im import FeishuIMClient
from market_ops.clients.feishu_bot import FeishuBotClient
from market_ops.config import Settings
from market_ops.group_approved_executor import build_group_approved_execution_reply, execute_group_approved_tasks
from market_ops.group_qa_router import GroupQARouter
from market_ops.group_send_log import GroupSendLog
from market_ops.manual_broadcast import build_artifacts, send_selected_cards
from market_ops.pipeline import DataRepository
from market_ops.pre_send_summary import PreSendSummaryBuilder
from market_ops.report_audit import ReportAuditBuilder
from market_ops.self_check import CardPreviewPaths, SelfCheckIssue, SelfCheckResult, run_self_check


@dataclass(slots=True)
class ChatObservation:
    chat_id: str
    first_seen_at: str
    last_seen_at: str
    last_message_id: str
    trigger_text: str
    matched_keyword: str
    allowlist_configured: bool
    allowlisted: bool
    reply_sent: bool


def _align_weekly_report_date(report_date: date) -> date:
    wednesday = 2
    days_since_wednesday = (report_date.weekday() - wednesday) % 7
    return report_date - timedelta(days=days_since_wednesday)


class FeishuEventServer:
    def __init__(
        self,
        settings: Settings,
        *,
        meeting_name: str,
        report_date: date | None = None,
    ) -> None:
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET are required for the Feishu event server.")

        self._settings = settings
        self._meeting_name = meeting_name
        self._report_date_override = report_date
        self._event_path = self._normalize_path(settings.feishu_event_path)
        self._trigger_keywords = tuple(settings.feishu_detail_trigger_keywords or ["详细"])
        self._allowed_chat_ids = set(settings.feishu_detail_allowed_chat_ids)
        self._im_client = FeishuIMClient(settings.feishu_app_id, settings.feishu_app_secret)
        self._seen_message_ids: deque[str] = deque(maxlen=512)
        self._seen_lookup: set[str] = set()
        self._lock = Lock()
        self._chat_observation_path = settings.active_output_dir / "feishu_detail_chat_observations.json"
        self._qa_router = GroupQARouter(settings.active_output_dir)
        self._send_log = GroupSendLog(settings.active_output_dir)
        self._help_keywords = ("帮助", "help", "可问", "怎么用", "指令")

    @property
    def event_path(self) -> str:
        return self._event_path

    def serve(self, host: str, port: int) -> None:
        handler_cls = self._build_handler()
        server = ThreadingHTTPServer((host, port), handler_cls)
        print(f"Feishu event server listening on http://{host}:{port}{self._event_path}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Feishu event server stopped.")
        finally:
            server.server_close()

    def handle_request(self, raw_body: bytes) -> tuple[int, dict[str, Any]]:
        payload = json.loads(raw_body.decode("utf-8"))
        if "encrypt" in payload:
            payload = self._decrypt_payload(str(payload.get("encrypt") or ""))

        self._verify_token(payload)

        if payload.get("type") == "url_verification":
            return HTTPStatus.OK, {"challenge": payload.get("challenge", "")}

        event_type = str(payload.get("header", {}).get("event_type") or "")
        if event_type == "im.message.receive_v1":
            self._handle_message_event(payload.get("event") or {})
            return HTTPStatus.OK, {"code": 0, "msg": "ok"}

        return HTTPStatus.OK, {"code": 0, "msg": f"ignored: {event_type or 'unknown'}"}

    def _decrypt_payload(self, encrypted_text: str) -> dict[str, Any]:
        encrypt_key = self._settings.feishu_event_encrypt_key
        if not encrypt_key:
            raise ValueError("Encrypted Feishu callback received, but FEISHU_EVENT_ENCRYPT_KEY is missing.")

        encrypted_bytes = base64.b64decode(encrypted_text)
        if len(encrypted_bytes) < AES.block_size:
            raise ValueError("Encrypted Feishu payload is too short.")

        iv = encrypted_bytes[: AES.block_size]
        cipher = AES.new(hashlib.sha256(encrypt_key.encode("utf-8")).digest(), AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_bytes[AES.block_size :])
        unpadded = self._unpad_pkcs7(decrypted)
        return json.loads(unpadded.decode("utf-8"))

    @staticmethod
    def _unpad_pkcs7(payload: bytes) -> bytes:
        if not payload:
            return payload
        pad_length = payload[-1]
        if pad_length < 1 or pad_length > AES.block_size:
            return payload.rstrip(b"\x00")
        return payload[:-pad_length]

    def _verify_token(self, payload: dict[str, Any]) -> None:
        expected = self._settings.feishu_event_verification_token
        if not expected:
            return
        actual = payload.get("token") or payload.get("header", {}).get("token")
        if actual and actual != expected:
            raise ValueError("Invalid Feishu event token.")

    def _handle_message_event(self, event: dict[str, Any]) -> None:
        message = event.get("message") or {}
        message_id = str(message.get("message_id") or "")
        if not message_id:
            return
        print(
            "Received Feishu message event: "
            f"message_id={message_id} chat_id={message.get('chat_id')} "
            f"chat_type={message.get('chat_type')} message_type={message.get('message_type')} "
            f"content={message.get('content')} mentions={message.get('mentions') or event.get('mentions')}"
        )
        if not self._remember_message(message_id):
            return

        if str(message.get("message_type") or "") != "text":
            return

        chat_type = str(message.get("chat_type") or "")
        if chat_type and chat_type != "group":
            return

        chat_id = str(message.get("chat_id") or "")
        if self._allowed_chat_ids and chat_id not in self._allowed_chat_ids:
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=self._extract_text(message.get("content")),
                matched_keyword=self._matched_keyword(self._extract_text(message.get("content"))),
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=False,
                reply_sent=False,
            )
            print(f"Detailed reply ignored for non-allowed chat: chat_id={chat_id} message_id={message_id}")
            return

        text = self._extract_text(message.get("content"))
        route = self._resolve_route(text, chat_id=chat_id)
        if not self._should_reply(text=text, event=event, message=message, route=route):
            return

        self._record_chat_observation(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            matched_keyword=self._matched_keyword(text),
            allowlist_configured=bool(self._allowed_chat_ids),
            allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
            reply_sent=False,
        )

        if not self._allowed_chat_ids:
            print(
                "Detailed reply trigger observed with no chat allowlist; safe mode skips reply: "
                f"chat_id={chat_id} message_id={message_id}"
            )
            return

        if route == "qa":
            if "最新待办" in text or "待办状态" in text:
                answer = self._qa_router.latest_request_summary(chat_id)
            elif "最近待办" in text or "待办列表" in text:
                answer = self._qa_router.latest_requests_list(chat_id)
            elif "已确认待办" in text:
                answer = self._qa_router.list_requests_by_status(chat_id, ["confirmed"], "已确认待办")
            elif "进行中待办" in text:
                answer = self._qa_router.list_requests_by_status(chat_id, ["in_progress"], "进行中待办")
            elif "已批准任务" in text:
                answer = self._qa_router.list_requests_by_status(chat_id, ["approved"], "已批准任务")
            elif "老板版待办" in text:
                answer = self._qa_router.list_requests_by_scope(chat_id, ["boss_report"], "老板版待办")
            elif "市场版待办" in text:
                answer = self._qa_router.list_requests_by_scope(chat_id, ["market_report"], "市场版待办")
            elif "回收版待办" in text:
                answer = self._qa_router.list_requests_by_scope(chat_id, ["recovery_report"], "回收版待办")
            elif "机器人待办" in text:
                answer = self._qa_router.list_requests_by_scope(chat_id, ["feishu_bot"], "机器人待办")
            elif "高风险待办" in text:
                answer = self._qa_router.list_requests_by_risk(chat_id, ["high"], "高风险待办")
            elif "林凯待办" in text:
                answer = self._qa_router.list_requests_by_owner(chat_id, "林凯", "林凯待办")
            elif "牟耕待办" in text:
                answer = self._qa_router.list_requests_by_owner(chat_id, "牟耕", "牟耕待办")
            elif "姜会伟待办" in text:
                answer = self._qa_router.list_requests_by_owner(chat_id, "姜会伟", "姜会伟待办")
            elif "待办统计" in text:
                answer = self._qa_router.build_status_counts_reply(chat_id)
            elif "执行清单" in text:
                path = self._qa_router.export_execution_checklist(chat_id)
                answer = f"执行清单已生成：\n- {path}"
            elif "正式任务包" in text:
                path = self._qa_router.export_task_packet(chat_id)
                answer = f"正式任务包已生成：\n- {path}"
            elif "待审批执行单" in text:
                path = self._qa_router.export_approval_packet(chat_id)
                answer = f"待审批执行单已生成：\n- {path}"
            elif "已批准任务包" in text or "已批准任务清单" in text:
                path = self._qa_router.export_approved_tasks(chat_id)
                answer = f"已批准任务清单已生成：\n- {path}"
            elif "最近发送记录" in text or "发送记录" in text:
                answer = self._send_log.build_latest_reply(chat_id=chat_id)
            elif "执行已批准任务" in text or "执行批准任务" in text:
                report_date = self._resolve_report_date()
                result_payload, output_paths = execute_group_approved_tasks(
                    self._settings,
                    report_date=report_date,
                    meeting_name=self._meeting_name,
                    chat_id=chat_id,
                    request_ids=[],
                )
                answer = build_group_approved_execution_reply(result_payload, output_paths)
            elif "req_" in text:
                import re

                match = re.search(r"(req_\d{8}_\d{6}_\d{3})", text)
                answer = self._qa_router.get_request_detail(match.group(1)) if match else self._qa_router.build_help_text()
            else:
                answer = self._qa_router.answer(text) or self._qa_router.build_help_text()
            self._im_client.reply_text(message_id, answer)
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                matched_keyword="qa",
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
                reply_sent=True,
            )
            print(f"Feishu QA reply sent: message_id={message_id}")
            return

        if route == "change_followup":
            decision = self._qa_router.classify(text, chat_id=chat_id)
            updated_item = self._qa_router.append_followup(decision=decision)
            self._im_client.reply_text(message_id, self._qa_router.build_followup_reply(updated_item))
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                matched_keyword="change_followup",
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
                reply_sent=True,
            )
            print(f"Feishu change request followup saved: message_id={message_id}")
            return

        if route == "status_update":
            decision = self._qa_router.classify(text, chat_id=chat_id)
            updated_item = self._qa_router.update_request_status(decision=decision)
            self._im_client.reply_text(message_id, self._qa_router.build_status_update_reply(updated_item))
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                matched_keyword="status_update",
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
                reply_sent=True,
            )
            print(f"Feishu change request status updated: message_id={message_id}")
            return

        if route == "change_request":
            decision = self._qa_router.classify(text, chat_id=chat_id)
            record = self._qa_router.queue_request(chat_id=chat_id, text=text, decision=decision)
            self._im_client.reply_text(message_id, self._qa_router.build_request_reply(record))
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                matched_keyword="change_request",
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
                reply_sent=True,
            )
            print(f"Feishu change request queued: message_id={message_id} request_id={record.id}")
            return

        report_date = self._resolve_report_date()
        gate_result, audit_payload, pre_send_result, pre_send_payload = self._resolve_send_gate_bundle(report_date)

        if not (gate_result.passed and audit_payload.get("passed") and pre_send_payload.get("passed")):
            self._send_log.append(
                chat_id=chat_id,
                message_id=message_id,
                route=route,
                report_date=report_date.isoformat(),
                meeting_name=self._meeting_name,
                gate_passed=False,
                status="blocked",
                sent_items=[],
                overview_path=str(gate_result.preview_paths.overview_markdown),
                detail="发送前自检或门禁未通过，已拦截正式发送。",
            )
            self._record_chat_observation(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                matched_keyword=self._matched_keyword(text),
                allowlist_configured=bool(self._allowed_chat_ids),
                allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
                reply_sent=False,
            )
            print(
                "Detailed reply intercepted by send gate: "
                f"message_id={message_id} report={report_date.isoformat()} "
                f"self_check={gate_result.markdown_path} pre_send={pre_send_result.markdown_path}"
            )
            return

        if route in {"send_market", "send_market_detailed", "send_recovery_only", "send_boss"}:
            try:
                if route == "send_recovery_only":
                    artifacts = build_artifacts(report_date, self._meeting_name)
                    webhook = (self._settings.feishu_market_webhook or self._settings.feishu_bot_webhook or "").strip()
                    if not webhook:
                        raise ValueError("Market webhook is missing.")
                    FeishuBotClient(webhook).send_card(artifacts.recovery_card)
                    sent_items = "market_recovery"
                    self._send_log.append(
                        chat_id=chat_id,
                        message_id=message_id,
                        route=route,
                        report_date=report_date.isoformat(),
                        meeting_name=self._meeting_name,
                        gate_passed=True,
                        status="sent",
                        sent_items=[sent_items],
                        overview_path=str(gate_result.preview_paths.overview_markdown),
                        detail="已发送回收版卡片。",
                    )
                    self._im_client.reply_text(
                        message_id,
                        f"已通过门禁并完成发送：\n- 发送项目：{sent_items}\n- 先看总览页：{gate_result.preview_paths.overview_markdown}",
                    )
                else:
                    send_market = route in {"send_market", "send_market_detailed"}
                    send_boss = route == "send_boss"
                    include_recovery = route in {"send_market_detailed", "send_boss"}
                    market_detailed = route == "send_market_detailed"
                    send_result = send_selected_cards(
                        report_date=report_date,
                        meeting_name=self._meeting_name,
                        send_boss=send_boss,
                        send_market=send_market,
                        include_recovery=include_recovery,
                        market_detailed=market_detailed,
                    )
                    sent_items = " / ".join(sorted(send_result.keys())) if send_result else "无"
                    self._send_log.append(
                        chat_id=chat_id,
                        message_id=message_id,
                        route=route,
                        report_date=report_date.isoformat(),
                        meeting_name=self._meeting_name,
                        gate_passed=True,
                        status="sent",
                        sent_items=sorted(send_result.keys()),
                        overview_path=str(gate_result.preview_paths.overview_markdown),
                        detail="已通过门禁并完成正式发送。",
                    )
                    self._im_client.reply_text(
                        message_id,
                        f"已通过门禁并完成发送：\n- 发送项目：{sent_items}\n- 先看总览页：{gate_result.preview_paths.overview_markdown}",
                    )
            except ValueError as exc:
                self._send_log.append(
                    chat_id=chat_id,
                    message_id=message_id,
                    route=route,
                    report_date=report_date.isoformat(),
                    meeting_name=self._meeting_name,
                    gate_passed=True,
                    status="blocked",
                    sent_items=[],
                    overview_path=str(gate_result.preview_paths.overview_markdown),
                    detail=str(exc),
                )
                self._im_client.reply_text(message_id, f"当前不能发送：\n- {exc}")
        elif route == "execute_approved":
            report_date = self._resolve_report_date()
            result_payload, output_paths = execute_group_approved_tasks(
                self._settings,
                report_date=report_date,
                meeting_name=self._meeting_name,
                chat_id=chat_id,
                request_ids=[],
            )
            self._im_client.reply_text(message_id, build_group_approved_execution_reply(result_payload, output_paths))
        elif route == "help":
            self._im_client.reply_text(message_id, self._build_help_text())
        elif route == "summary":
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.summary_json))
        elif route == "boss":
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.summary_json))
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.boss_json))
        elif route == "market_simple":
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.summary_json))
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.market_json))
        elif route == "recovery":
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.recovery_json))
        else:
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.summary_json))
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.market_detail_json))
            self._im_client.reply_card(message_id, self._load_card(gate_result.preview_paths.recovery_json))
        self._record_chat_observation(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            matched_keyword=self._matched_keyword(text),
            allowlist_configured=bool(self._allowed_chat_ids),
            allowlisted=(not self._allowed_chat_ids) or (chat_id in self._allowed_chat_ids),
            reply_sent=True,
        )
        print(
            "Feishu reply sent: "
            f"message_id={message_id} report={report_date.isoformat()} route={route}"
        )

    def _should_reply(
        self,
        *,
        text: str,
        event: dict[str, Any],
        message: dict[str, Any],
        route: str,
    ) -> bool:
        if not text:
            return False
        if route == "unsupported":
            return False
        mentions = message.get("mentions") or event.get("mentions") or []
        if mentions:
            return True
        return "@_user_" in text or "<at " in text

    def _resolve_route(self, text: str, *, chat_id: str = "") -> str:
        normalized = str(text or "").strip().lower()
        decision = self._qa_router.classify(str(text or "").strip(), chat_id=chat_id)
        if decision.route == "status_update":
            return "status_update"
        if decision.route == "change_followup":
            return "change_followup"
        if decision.route == "fixed":
            compact = str(text or "").replace("@机器人", "").replace(" ", "").strip()
            if compact in {"执行已批准任务", "执行批准任务"}:
                return "execute_approved"
            if compact == "发送市场版":
                return "send_market"
            if compact == "发送详细市场版":
                return "send_market_detailed"
            if compact == "发送回收版":
                return "send_recovery_only"
            if compact == "发送老板版":
                return "send_boss"
            if compact in {"最近发送记录", "发送记录"}:
                return "qa"
            if compact in {"帮助", "help"}:
                return "help"
        if decision.route == "qa":
            return "qa"
        if decision.route == "change_request":
            return "change_request"
        if any(keyword in normalized for keyword in self._help_keywords):
            return "help"
        if "老板版" in normalized or ("老板" in normalized and "周报" in normalized):
            return "boss"
        if "回收版" in normalized or "回收" in normalized or "倍率" in normalized:
            return "recovery"
        if "简版" in normalized or "市场版" in normalized or "简报" in normalized:
            return "market_simple"
        if "摘要" in normalized or "结论" in normalized or "总结" in normalized:
            return "summary"
        if "详细" in normalized:
            return "market_detail"
        return "unsupported"

    def _build_help_text(self) -> str:
        return self._qa_router.build_help_text()

    @staticmethod
    def _extract_text(content: Any) -> str:
        if not content:
            return ""
        if isinstance(content, dict):
            return str(content.get("text") or "")
        try:
            parsed = json.loads(str(content))
        except json.JSONDecodeError:
            return str(content)
        return str(parsed.get("text") or "")

    def _resolve_report_date(self) -> date:
        if self._report_date_override is not None:
            return _align_weekly_report_date(self._report_date_override)
        try:
            rows = DataRepository(self._settings).load_ads_performance()
            if rows:
                return _align_weekly_report_date(max(row.date for row in rows))
        except Exception as exc:
            print(f"Failed to resolve latest report date from ads source, fallback to calendar week: {exc}")
        return _align_weekly_report_date(datetime.now().date())

    def _remember_message(self, message_id: str) -> bool:
        with self._lock:
            if message_id in self._seen_lookup:
                return False
            if len(self._seen_message_ids) == self._seen_message_ids.maxlen:
                expired = self._seen_message_ids.popleft()
                self._seen_lookup.discard(expired)
            self._seen_message_ids.append(message_id)
            self._seen_lookup.add(message_id)
        return True

    def _record_chat_observation(
        self,
        *,
        chat_id: str,
        message_id: str,
        text: str,
        matched_keyword: str,
        allowlist_configured: bool,
        allowlisted: bool,
        reply_sent: bool,
    ) -> None:
        if not chat_id:
            return
        now = datetime.now().isoformat(timespec="seconds")
        self._chat_observation_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = self._load_chat_observations()
            items = payload.get("items") or []
            found = None
            for item in items:
                if str(item.get("chat_id") or "") == chat_id:
                    found = item
                    break
            if found is None:
                found = {
                    "chat_id": chat_id,
                    "first_seen_at": now,
                }
                items.append(found)
            found["last_seen_at"] = now
            found["last_message_id"] = message_id
            found["trigger_text"] = text
            found["matched_keyword"] = matched_keyword
            found["allowlist_configured"] = allowlist_configured
            found["allowlisted"] = allowlisted
            found["reply_sent"] = reply_sent
            payload["items"] = sorted(items, key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)
            payload["updated_at"] = now
            self._chat_observation_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_chat_observations(self) -> dict[str, Any]:
        if not self._chat_observation_path.exists():
            return {"items": [], "updated_at": ""}
        try:
            payload = json.loads(self._chat_observation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": [], "updated_at": ""}
        if not isinstance(payload, dict):
            return {"items": [], "updated_at": ""}
        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        return payload

    def _matched_keyword(self, text: str) -> str:
        for keyword in self._trigger_keywords:
            if keyword in text:
                return keyword
        return ""

    @staticmethod
    def _load_card(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _resolve_send_gate_bundle(
        self,
        report_date: date,
    ) -> tuple[SelfCheckResult, dict[str, Any], Any, dict[str, Any]]:
        output_dir = self._settings.active_output_dir
        suffix = report_date.strftime("%Y%m%d")
        self_check_json = output_dir / f"self_check_{suffix}.json"
        report_audit_json = output_dir / f"report_audit_{suffix}.json"
        pre_send_json = output_dir / f"pre_send_summary_{suffix}.json"

        gate_result = self._load_self_check_result(self_check_json)
        if gate_result is None:
            gate_result = run_self_check(
                report_date=report_date,
                meeting_name=self._meeting_name,
                output_dir=output_dir,
            )

        if report_audit_json.exists():
            audit_payload = json.loads(report_audit_json.read_text(encoding="utf-8"))
        else:
            audit_payload = ReportAuditBuilder(self._settings).audit_payload(
                report_date=report_date,
                meeting_name=self._meeting_name,
                self_check_result=gate_result,
            )

        pre_send_result = PreSendSummaryBuilder(self._settings).build(report_date=report_date)
        pre_send_payload = json.loads(pre_send_result.json_path.read_text(encoding="utf-8"))
        return gate_result, audit_payload, pre_send_result, pre_send_payload

    def _load_self_check_result(self, path: Path) -> SelfCheckResult | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        preview_payload = payload.get("preview_paths") or {}
        suffix = path.stem.replace("self_check_", "")
        inferred_preview_payload = {
            "overview_markdown": preview_payload.get("overview_markdown") or str(self._settings.active_output_dir / f"weekly_preview_overview_{suffix}.md"),
            "summary_markdown": preview_payload.get("summary_markdown") or str(self._settings.active_output_dir / f"card_preview_summary_{suffix}.md"),
            "summary_json": preview_payload.get("summary_json") or str(self._settings.active_output_dir / f"card_preview_summary_{suffix}.json"),
            "boss_markdown": preview_payload.get("boss_markdown") or str(self._settings.active_output_dir / f"card_preview_boss_{suffix}.md"),
            "boss_json": preview_payload.get("boss_json") or str(self._settings.active_output_dir / f"card_preview_boss_{suffix}.json"),
            "market_markdown": preview_payload.get("market_markdown") or str(self._settings.active_output_dir / f"card_preview_market_{suffix}.md"),
            "market_json": preview_payload.get("market_json") or str(self._settings.active_output_dir / f"card_preview_market_{suffix}.json"),
            "market_detail_markdown": preview_payload.get("market_detail_markdown") or str(self._settings.active_output_dir / f"card_preview_market_detail_{suffix}.md"),
            "market_detail_json": preview_payload.get("market_detail_json") or str(self._settings.active_output_dir / f"card_preview_market_detail_{suffix}.json"),
            "recovery_markdown": preview_payload.get("recovery_markdown") or str(self._settings.active_output_dir / f"card_preview_recovery_{suffix}.md"),
            "recovery_json": preview_payload.get("recovery_json") or str(self._settings.active_output_dir / f"card_preview_recovery_{suffix}.json"),
            "index_markdown": preview_payload.get("index_markdown") or str(self._settings.active_output_dir / f"card_preview_index_{suffix}.md"),
        }
        required_keys = list(inferred_preview_payload.keys())
        if not all(Path(inferred_preview_payload[key]).exists() for key in required_keys):
            return None
        preview_paths = CardPreviewPaths(
            overview_markdown=Path(inferred_preview_payload["overview_markdown"]),
            summary_markdown=Path(inferred_preview_payload["summary_markdown"]),
            summary_json=Path(inferred_preview_payload["summary_json"]),
            boss_markdown=Path(inferred_preview_payload["boss_markdown"]),
            boss_json=Path(inferred_preview_payload["boss_json"]),
            market_markdown=Path(inferred_preview_payload["market_markdown"]),
            market_json=Path(inferred_preview_payload["market_json"]),
            market_detail_markdown=Path(inferred_preview_payload["market_detail_markdown"]),
            market_detail_json=Path(inferred_preview_payload["market_detail_json"]),
            recovery_markdown=Path(inferred_preview_payload["recovery_markdown"]),
            recovery_json=Path(inferred_preview_payload["recovery_json"]),
            index_markdown=Path(inferred_preview_payload["index_markdown"]),
        )
        issues = [
            SelfCheckIssue(
                code=str(item.get("code") or ""),
                source=str(item.get("source") or ""),
                message=str(item.get("message") or ""),
                actual=str(item.get("actual") or ""),
                expected=str(item.get("expected") or ""),
            )
            for item in (payload.get("issues") or [])
            if isinstance(item, dict)
        ]
        markdown_path = self._settings.active_output_dir / f"self_check_{payload.get('report_date', '').replace('-', '')}.md"
        return SelfCheckResult(
            passed=bool(payload.get("passed")),
            issues=issues,
            warnings=[str(item) for item in (payload.get("warnings") or [])],
            preview_paths=preview_paths,
            markdown_path=markdown_path,
            json_path=path,
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        stripped = (path or "/").strip()
        if not stripped.startswith("/"):
            stripped = f"/{stripped}"
        return stripped

    def _build_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != server.event_path:
                    self._write_json(HTTPStatus.NOT_FOUND, {"code": 404, "msg": "not found"})
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(length)
                    status, payload = server.handle_request(raw_body)
                    self._write_json(status, payload)
                except Exception as exc:
                    print(f"Feishu event server error: {exc}")
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"code": 500, "msg": str(exc)})

            def do_GET(self) -> None:  # noqa: N802
                if self.path == server.event_path:
                    self._write_json(HTTPStatus.OK, {"code": 0, "msg": "ok"})
                    return
                self._write_json(HTTPStatus.NOT_FOUND, {"code": 404, "msg": "not found"})

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _write_json(self, status: int, payload: dict[str, Any]) -> None:
                encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler
