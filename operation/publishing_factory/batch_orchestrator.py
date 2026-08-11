"""
E15.1.1 — Batch Publishing Orchestrator
========================================

The AI scheduler that runs the WHOLE fleet every cycle:

    scan fleet -> for each game build a PublishingPlan (SIM)
              -> collect queue + human-approval list
              -> (optional) rejection feedback loop: a store rejection
                 is classified, a fix plan is generated, a resubmit
                 plan is produced.

Respects the three-tier gate: in SIMULATION/SHADOW it only produces
plans + recommendations. Real store submission is delegated to the
existing E15.1 ``PublishingAgent`` and only fires in PRODUCTION after
human approval + unlock (mirrors the MAX monetization pattern — the
system proposes, the human executes).

Rejection loop classification (deterministic):
    policy/similarity -> 4.3 spam  -> regenerate distinct icon/screenshots
    privacy            -> privacy  -> add policy url / age gate
    metadata           -> metadata -> rewrite title/keywords
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from monetization.providers.models import SandboxMode

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import (
    FleetManager, FleetScanReport,
)
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.publishing_factory import (
    PublishingFactory, PublishingPlan,
)
from operation.publishing_factory.memory import PublishingMemory
from operation.publishing_factory.auto_pilot import auto_pilot_enabled


def _diagnose_ownership(status_code: Optional[int],
                        error_text: str) -> str:
    """Translate a failed ownership READ (real Edits API) into the
    concrete next action for the human operator."""
    err = (error_text or "").lower()
    if status_code == 401:
        return ("Token 失效/签名无权限：service account JSON 可能过期，或根本不是 "
                "该 Play Console 账号的凭证。检查 store_keys 指向的 JSON 是否当前有效。")
    if status_code == 403:
        # The most common first-time mistake: the Android Publisher API
        # is disabled in the GCP project. The JSON error carries explicit
        # fields ("SERVICE_DISABLED", "androidpublisher.googleapis.com",
        # activationUrl). Detect this BEFORE the generic "project" /
        # "not linked" heuristics (which also match but give a less
        # accurate diagnosis).
        if ("SERVICE_DISABLED" in error_text or
                "androidpublisher" in err or
                "api has not been used" in err):
            # Try to extract the activation URL from the Google JSON error.
            activation_url = ""
            import re
            m = re.search(
                r'https://console\.developers\.google\.com/apis/api/'
                r'androidpublisher\.googleapis\.com/overview\?project=\d+',
                error_text)
            if m:
                activation_url = m.group(0) + " "
            return (
                f"Google Play Android Developer API 在 GCP 项目中未启用！"
                f"{activation_url}去这个链接点 Enable，等 1-2 分钟传播后重跑 "
                "push_ofw_calculator.bat。不需要改 Play Console 权限。")
        if "not linked" in err or "project" in err:
            return ("GCP 项目未关联到该 Play Console 账号：去 Settings → "
                    "Developer account → API access → Link project，"
                    "把 born2play 这个 GCP 项目关联上。仅邀请邮箱不够。")
        if "does not have permission" in err or "forbidden" in err:
            return ("服务账号没有该 App 的权限：去 Users & permissions → 选中 "
                    "com.ofwsalary.ofwcalculator → 给 born2play@... 至少 "
                    "Release manager 角色，等 1-2 分钟生效。")
        return ("403 禁止访问：通常是 GCP API 未启用／服务账号未授权到该 App／"
                "GCP 项目未关联到该 Play Console 账号。查上方 HTTP 响应详情。")
    if status_code == 404:
        return ("404 找不到 App：包名 com.ofwsalary.ofwcalculator 不在你当前登录的 "
                "Play Console 账号下（或在别的账号），或拼写不一致。确认 App 所在 "
                "账号与凭证对应。")
    if status_code == 0:
        return ("网络层失败（status 0）：本机连不上 Google。确认代理可用 "
                "(HTTPS_PROXY) 且能出网；沙箱环境本就走不通。")
    return f"未知错误码 {status_code}：{error_text}"


class RejectClass(str, Enum):
    SPAM_43 = "4.3_spam"
    PRIVACY = "privacy"
    METADATA = "metadata"
    OTHER = "other"


@dataclass
class BatchGameResult:
    game_id: str
    task_type: str
    plan: dict
    recommended: bool
    requires_approval: bool

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "task_type": self.task_type,
                "recommended": self.recommended,
                "requires_approval": self.requires_approval,
                "plan": self.plan}


@dataclass
class BatchReport:
    sandbox: str
    scanned: int
    plans: List[BatchGameResult] = field(default_factory=list)
    recommended_count: int = 0
    approval_required: int = 0
    queue: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    executed: int = 0          # auto-pilot: plans actually executed
    auto_pilot: bool = False   # auto-pilot mode flag

    def to_dict(self) -> dict:
        return {"sandbox": self.sandbox, "scanned": self.scanned,
                "recommended_count": self.recommended_count,
                "approval_required": self.approval_required,
                "executed": self.executed, "auto_pilot": self.auto_pilot,
                "plans": [p.to_dict() for p in self.plans],
                "queue": list(self.queue), "notes": list(self.notes)}


class BatchOrchestrator:
    """Runs the factory across the whole fleet on a schedule."""

    def __init__(self, registry: GameRegistry,
                 factory: PublishingFactory = None,
                 sandbox: SandboxMode = SandboxMode.SIMULATION,
                 auto_pilot: bool = None, dry_run: bool = False):
        self.registry = registry
        self.fleet_manager = FleetManager(registry)
        self.sandbox = sandbox
        self.factory = factory or PublishingFactory(sandbox=sandbox)
        # auto_pilot: None = read from env var; explicit True/False overrides
        self.auto_pilot = (auto_pilot if auto_pilot is not None
                           else auto_pilot_enabled())
        # dry_run: perform ownership verification (READ) but skip the WRITE
        self.dry_run = dry_run

    # ------------------------------------------------------------------ #
    def run_daily(self) -> BatchReport:
        scan: FleetScanReport = self.fleet_manager.scan()
        fleet = self.registry.list_all()
        report = BatchReport(sandbox=self.sandbox.value,
                             scanned=scan.scanned,
                             auto_pilot=self.auto_pilot)
        report.queue = [t.to_dict() for t in scan.tasks]

        for task in scan.tasks:
            game = self.registry.get(task.game_id)
            if game is None:
                continue
            plan = self.factory.build_plan(game, fleet)

            # ---- auto-pilot: auto-approve passing plans ----
            if self.auto_pilot and plan.recommended:
                plan.requires_approval = False
                plan.approval_status = "approved"
                plan.notes.append("auto-pilot: auto-approved")

            result = BatchGameResult(
                game_id=game.game_id, task_type=task.task_type,
                plan=plan.to_dict(), recommended=plan.recommended,
                requires_approval=plan.requires_approval)
            report.plans.append(result)
            if plan.recommended:
                report.recommended_count += 1
            if plan.requires_approval:
                report.approval_required += 1

        # ---- auto-pilot: auto-execute approved plans ----
        if self.auto_pilot:
            report.executed = self._auto_execute(report, dry_run=self.dry_run)
            verb = ("would-be auto-executed (dry-run)"
                    if self.dry_run else "auto-executed")
            report.notes.append(
                f"auto-pilot: {report.executed}/{report.recommended_count} "
                f"plans {verb}")
        else:
            report.notes.append(
                f"{report.recommended_count}/{report.scanned} games recommended; "
                f"{report.approval_required} need human approval (no real API called)")
        return report

    # ------------------------------------------------------------------ #
    # auto-pilot: real closed-loop execution for approved plans
    def _auto_execute(self, report: BatchReport, dry_run: bool = False) -> int:
        """Push auto-approved plans to the REAL Google Play console.

        Safety envelope (intentional, non-bypassable):
          * Only games with a VERIFIED package_name are touched. Empty or
            fake package names are skipped — we never blind-create apps.
          * Before any write we call check_status (a real READ) to confirm
            the package is owned by THIS service account; if not, skip.
          * Only metadata (listing title/description) is written — the
            lowest-blast-radius change. No app creation, no build upload,
            no production release.
          * dry_run=True performs the ownership READ but skips the WRITE.

        Returns the number of games whose metadata was actually pushed.
        """
        from operation.providers.live.store_keys import get_googleplay
        from operation.publishing.providers.google_play.real_client import (
            GooglePlayRealClient,
        )
        from operation.publishing.google_play.provider import GooglePlayProvider
        from monetization.providers.models import SandboxMode
        from operation.publishing.providers.models import (
            OP_CHECK_STATUS, OP_UPDATE_METADATA, PublishingChange,
        )

        gp_cred = get_googleplay()
        if gp_cred is None:
            report.notes.append(
                "auto-pilot: no Google Play credentials — execution skipped")
            return 0

        # Real client + production provider, unlocked only because the
        # operator explicitly opted in via LAUNCHFORGE_AUTO_PUBLISH.
        real_client = GooglePlayRealClient(gp_cred)
        provider = GooglePlayProvider(
            sandbox=SandboxMode.PRODUCTION, client=real_client)
        if self.auto_pilot:
            provider.unlock()

        executed = 0
        for result in report.plans:
            if not result.recommended or result.requires_approval:
                continue
            game = self.registry.get(result.game_id)
            if game is None:
                continue
            pkg = getattr(game, "package_name", "") or ""
            if not pkg or "fake" in pkg or pkg.count(".") < 2:
                report.notes.append(
                    f"auto-pilot: {result.game_id} has no verified "
                    f"package_name — skipped (no blind app creation)")
                continue
            # register the package so the client can resolve it for the
            # Edits API calls below
            real_client.set_package(result.game_id, pkg)

            # 1) verify ownership (real READ via Edits API)
            verify = provider.apply_change(PublishingChange(
                target=f"{result.game_id}/google_play/check_status",
                operation=OP_CHECK_STATUS, provider="google_play",
                game_id=result.game_id, new={},
                sandbox=SandboxMode.PRODUCTION))
            if not verify.success or not verify.real_api_called:
                report.notes.append(
                    f"auto-pilot: {result.game_id} ({pkg}) not accessible by "
                    f"this service account — skipped")
                continue

            # 2) build metadata payload from the generated ASO pack
            aso = (result.plan.get("aso") or {})
            meta = {
                "title": aso.get("title", ""),
                "short_description": aso.get("short_description", ""),
                "full_description": aso.get("full_description", ""),
            }
            if not any(meta.values()):
                report.notes.append(
                    f"auto-pilot: {result.game_id} has no ASO metadata to "
                    f"push — skipped")
                continue

            if dry_run:
                report.notes.append(
                    f"auto-pilot[DRY-RUN]: {result.game_id} ({pkg}) would "
                    f"update listing title/description on Play Console")
                continue

            # 3) real WRITE (listing text only)
            upd = provider.apply_change(PublishingChange(
                target=f"{result.game_id}/google_play/update_metadata",
                operation=OP_UPDATE_METADATA, provider="google_play",
                game_id=result.game_id, new=meta,
                sandbox=SandboxMode.PRODUCTION))
            if upd.success and upd.real_api_called:
                executed += 1
                report.notes.append(
                    f"auto-pilot: {result.game_id} ({pkg}) listing updated "
                    f"on Play Console")
            else:
                report.notes.append(
                    f"auto-pilot: {result.game_id} update failed: "
                    f"{upd.error}")
        return executed

    # ------------------------------------------------------------------ #
    # operator-directed single-app push (bypasses the fleet recommendation
    # gate but keeps every safety lock: ownership READ -> listing WRITE,
    # dry-run by default). Used by `run_auto_pilot --game <pkg> [--apply]`.
    def push_single(self, game_id: str, meta: Dict[str, str],
                    dry_run: bool = True, locale: str = "en-US") -> dict:
        """Push listing metadata to ONE explicitly-named app.

        Steps (each is a hard gate):
          1. game must exist in registry with a VERIFIED package_name.
          2. ownership READ (real Edits API): package must belong to THIS
             service account, else refuse.
          3. dry_run -> report what WOULD be written; --apply -> real WRITE
             of listing title/short/full description only. ``locale`` is a
             BCP-47 code (en-US, fil, ar, ...).

        Returns a small status dict ( safe to print ).
        """
        from operation.providers.live.store_keys import get_googleplay
        from operation.publishing.providers.google_play.real_client import (
            GooglePlayRealClient,
        )
        from operation.publishing.google_play.provider import GooglePlayProvider
        from monetization.providers.models import SandboxMode
        from operation.publishing.providers.models import (
            OP_CHECK_STATUS, OP_UPDATE_METADATA, PublishingChange,
        )

        game = self.registry.get(game_id)
        if game is None:
            return {"ok": False, "stage": "lookup",
                    "error": f"game '{game_id}' not in registry"}
        pkg = getattr(game, "package_name", "") or ""
        if not pkg or "fake" in pkg or pkg.count(".") < 2:
            return {"ok": False, "stage": "package",
                    "error": f"no verified package_name for {game_id} "
                             f"(found: '{pkg}') — refusing to blind-create"}

        gp_cred = get_googleplay()
        if gp_cred is None:
            return {"ok": False, "stage": "credentials",
                    "error": "no Google Play credentials configured"}

        real_client = GooglePlayRealClient(gp_cred)
        provider = GooglePlayProvider(
            sandbox=SandboxMode.PRODUCTION, client=real_client)
        if self.auto_pilot:
            provider.unlock()
        real_client.set_package(game_id, pkg)

        # 1) ownership READ
        verify = provider.apply_change(PublishingChange(
            target=f"{game_id}/google_play/check_status",
            operation=OP_CHECK_STATUS, provider="google_play",
            game_id=game_id, new={},
            sandbox=SandboxMode.PRODUCTION))
        if not verify.success or not verify.real_api_called:
            extra = verify.extra or {}
            sc = extra.get("status_code")
            err = verify.error or ""
            return {"ok": False, "stage": "ownership",
                    "http_status": sc,
                    "error": err or f"{pkg} not accessible by this "
                                    f"service account",
                    "diagnosis": _diagnose_ownership(sc, err)}
        status = (verify.extra or {}).get("status", "unknown")

        # normalize metadata payload
        payload = {
            "title": (meta.get("title") or "").strip(),
            "short_description": (meta.get("short_description") or "").strip(),
            "full_description": (meta.get("full_description") or "").strip(),
        }
        if not any(payload.values()):
            return {"ok": True, "stage": "verify-only",
                    "owned": True, "play_status": status,
                    "note": "ownership verified; no metadata supplied "
                            "so nothing would be written"}

        if dry_run:
            return {"ok": True, "stage": "dry-run", "owned": True,
                    "play_status": status, "would_write": payload}

        # 2) real WRITE (listing text only, for the requested locale)
        write_payload = dict(payload)
        write_payload["locale"] = locale
        upd = provider.apply_change(PublishingChange(
            target=f"{game_id}/google_play/update_metadata",
            operation=OP_UPDATE_METADATA, provider="google_play",
            game_id=game_id, new=write_payload,
            sandbox=SandboxMode.PRODUCTION))
        if upd.success and upd.real_api_called:
            return {"ok": True, "stage": "written", "owned": True,
                    "play_status": status, "written": payload}
        return {"ok": False, "stage": "write",
                "error": upd.error or "update failed"}

    # ------------------------------------------------------------------ #
    # rejection feedback loop (deterministic classifier + fix generator)
    def handle_rejection(self, game_id: str,
                         rejection: Dict[str, str]) -> PublishingPlan:
        game = self.registry.get(game_id)
        if game is None:
            raise KeyError(f"unknown game {game_id}")
        store = rejection.get("store", "apple")
        code = (rejection.get("code", "") or "").lower()
        reason = (rejection.get("reason", "") or "").lower()

        cls = self._classify(code, reason)
        # produce a fresh plan, then tag the fix
        fleet = self.registry.list_all()
        plan = self.factory.build_plan(game, fleet)
        plan.notes.append(f"rejection classified as {cls.value} ({store})")
        if cls == RejectClass.SPAM_43:
            plan.notes.append("FIX: regenerate distinct icon + screenshots "
                              "(reduce fleet similarity)")
            # record learning
            self._learn(game, "reject_fix", cls.value, "resolved",
                        "distinct creative")
        elif cls == RejectClass.PRIVACY:
            plan.notes.append("FIX: add privacy_policy_url / age gate")
            self._learn(game, "reject_fix", cls.value, "resolved",
                        "privacy posture")
        else:
            plan.notes.append("FIX: rewrite title/keywords/metadata")
            self._learn(game, "reject_fix", cls.value, "resolved",
                        "metadata refresh")
        # a rejected game must be re-approved before any real resubmit
        plan.requires_approval = True
        plan.approval_status = "pending"
        return plan

    # ------------------------------------------------------------------ #
    @staticmethod
    def _classify(code: str, reason: str) -> RejectClass:
        blob = f"{code} {reason}".lower()
        if any(k in blob for k in ("4.3", "spam", "clone", "similar", "copy")):
            return RejectClass.SPAM_43
        if any(k in blob for k in ("privacy", "coppa", "data collection",
                                   "personal data", "gdpr")):
            return RejectClass.PRIVACY
        if any(k in blob for k in ("metadata", "keyword", "title",
                                   "description", "screenshot")):
            return RejectClass.METADATA
        return RejectClass.OTHER

    def _learn(self, game: GameProduct, kind: str, key: str,
               outcome: str, detail: str) -> None:
        # best-effort: only if factory exposes a memory
        mem = getattr(self.factory, "memory", None)
        if isinstance(mem, PublishingMemory):
            from operation.publishing_factory.memory import (
                PublishingMemoryEntry,
            )
            mem.record(PublishingMemoryEntry(
                game_id=game.game_id, kind=kind, key=key,
                outcome=outcome, value=1.0, detail=detail,
                genre=game.genre))


__all__ = ["BatchOrchestrator", "BatchReport", "BatchGameResult",
           "RejectClass", "auto_pilot_enabled"]
