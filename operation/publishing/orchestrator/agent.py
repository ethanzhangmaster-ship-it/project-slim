"""
E15.1.7 — Publishing Orchestrator

The full release lifecycle: validate build → generate metadata →
upload → submit review → monitor → handle rejection → release.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from monetization.providers.models import SandboxMode
from operation.publishing.build.agent import BuildAgent, BuildArtifact
from operation.publishing.metadata.agent import MetadataAgent
from operation.publishing.providers.models import (
    GP_APPROVED, GP_REJECTED, AS_READY, AS_REJECTED,
    OP_CREATE_APP, OP_CREATE_RELEASE, OP_RELEASE,
    OP_SUBMIT_REVIEW, OP_UPLOAD_BUILD,
    PublishingChange, PublishingStatus,
)
from operation.publishing.review.agent import ReviewAgent
from operation.publishing.review.models import ReviewRejectEvent


@dataclass
class PublishingTask:
    task_id: str
    task_type: str
    status: str = "pending"        # pending | running | success | failed
    result: dict = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id, "task_type": self.task_type,
            "status": self.status, "result": self.result,
            "reason": self.reason,
        }


@dataclass
class PublishingReport:
    game_id: str
    store: str
    tasks: List[PublishingTask] = field(default_factory=list)
    final_status: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "store": self.store,
            "tasks": [t.to_dict() for t in self.tasks],
            "final_status": self.final_status, "error": self.error,
        }


class PublishingAgent:
    """Orchestrates the full release pipeline for one game on one store."""

    def __init__(self, provider,  # GooglePlayProvider | AppStoreProvider
                 build_agent: BuildAgent = None,
                 metadata_agent: MetadataAgent = None,
                 review_agent: ReviewAgent = None):
        self.provider = provider
        self.build_agent = build_agent or BuildAgent()
        self.metadata_agent = metadata_agent or MetadataAgent()
        self.review_agent = review_agent or ReviewAgent()
        self._tasks: List[PublishingTask] = []

    # ------------------------------------------------------------------ #
    def run(self, game_id: str, platform: str,  # "android" | "ios"
            build_artifact: BuildArtifact,
            game_config: dict) -> PublishingReport:
        self._tasks = []
        store = self.provider.name
        report = PublishingReport(game_id=game_id, store=store)

        # 1. validate build
        self._task("validate_build")
        validation = self.build_agent.validate(build_artifact)
        if not validation.valid:
            return self._fail(report, f"build invalid: {validation.issues}")
        self._tasks[-1].status = "success"

        # 2. generate metadata
        self._task("generate_metadata")
        build_info = {"version": build_artifact.version,
                      "build_number": build_artifact.build_number}
        metadata = self.metadata_agent.build(game_config, build_info)
        self._tasks[-1].status = "success"

        # 3. create app
        self._task(OP_CREATE_APP)
        listing = metadata.platforms.get(platform)
        payload = {"title": listing.title if listing else game_id}
        if store == "google_play":
            payload["package_name"] = game_config.get("package_name",
                                                       f"com.fake.{game_id}")
        else:
            payload["bundle_id"] = game_config.get("bundle_id",
                                                    f"com.fake.{game_id}")
        ch = self._change(OP_CREATE_APP, game_id, payload)
        r = self.provider.apply_change(ch)
        if not r.success:
            return self._fail(report, f"create_app failed: {r.error}")
        self._tasks[-1].status = "success"

        # 4. upload build
        self._task(OP_UPLOAD_BUILD)
        bp = {"file_path": build_artifact.file_path,
              "version": build_artifact.version,
              "build_number": build_artifact.build_number}
        ch = self._change(OP_UPLOAD_BUILD, game_id, bp)
        r = self.provider.apply_change(ch)
        if not r.success:
            return self._fail(report, f"upload_build failed: {r.error}")
        self._tasks[-1].status = "success"

        # 5. create release
        self._task(OP_CREATE_RELEASE)
        ch = self._change(OP_CREATE_RELEASE, game_id,
                          {"track": "internal"})
        r = self.provider.apply_change(ch)
        if not r.success:
            return self._fail(report, f"create_release failed: {r.error}")
        self._tasks[-1].status = "success"

        # 6. submit review
        self._task(OP_SUBMIT_REVIEW)
        ch = self._change(OP_SUBMIT_REVIEW, game_id, {})
        r = self.provider.apply_change(ch)
        if not r.success:
            return self._fail(report, f"submit_review failed: {r.error}")
        self._tasks[-1].status = "success"

        # 7. monitor review status
        self._task("monitor_review")
        hc = self.provider.health_check()
        status_ch = self._change("check_status", game_id, {})
        sr = self.provider.apply_change(status_ch)
        extra = sr.extra if sr.extra else {}
        review_status = extra.get("status", "")

        # handle rejection
        if (store == "google_play" and review_status == GP_REJECTED) or \
           (store == "app_store" and review_status == AS_REJECTED):
            rejection = extra.get("rejection", {})
            rev_event = ReviewRejectEvent(
                store=store, game_id=game_id,
                rejection_code=rejection.get("code", "Unknown"),
                reason=rejection.get("reason", ""))
            fix = self.review_agent.analyze(rev_event)
            self._task("fix_rejection", reason=str(fix.to_dict()))
            self._tasks[-1].status = "fix_required"
            report.final_status = "rejected"
            report.error = fix.issue
            report.tasks = list(self._tasks)
            return report

        # 8. release to production
        self._tasks[-1].status = "success"  # monitor_review passed
        self._task(OP_RELEASE)
        ch = self._change(OP_RELEASE, game_id, {})
        r = self.provider.apply_change(ch)
        if not r.success:
            return self._fail(report, f"release failed: {r.error}")
        self._tasks[-1].status = "success"

        report.final_status = "published"
        report.tasks = list(self._tasks)
        return report

    # ------------------------------------------------------------------ #
    def _change(self, op: str, game_id: str, payload: dict) -> PublishingChange:
        return PublishingChange(
            target=f"{game_id}/{self.provider.name}/{op}",
            operation=op, provider=self.provider.name,
            game_id=game_id, new=payload,
            sandbox=self.provider.sandbox,
        )

    def _task(self, task_type: str, reason: str = "") -> None:
        tid = f"t{len(self._tasks):03d}"
        self._tasks.append(PublishingTask(
            task_id=tid, task_type=task_type,
            status="running", reason=reason))

    def _fail(self, report: PublishingReport, error: str) -> PublishingReport:
        if self._tasks:
            self._tasks[-1].status = "failed"
            self._tasks[-1].reason = error
        report.tasks = list(self._tasks)
        report.final_status = "failed"
        report.error = error
        return report


__all__ = ["PublishingAgent", "PublishingTask", "PublishingReport"]
