"""
E15.1.1 — Publishing Provider Contract
=========================================

Frozen contract for all store adapters (Google Play, App Store).
Consumed by the Publishing Orchestrator and the Acceptance Gate.
"""
from operation.publishing.providers.models import (
    CredentialRef, PublishingChange, PublishingResult,
    PublishingStatus, SandboxMode,
    GP_DRAFT, GP_IN_REVIEW, GP_REJECTED, GP_APPROVED, GP_PUBLISHED,
    AS_PREPARE, AS_WAITING, AS_IN_REVIEW, AS_REJECTED, AS_READY,
    OP_CREATE_APP, OP_UPLOAD_BUILD, OP_CREATE_RELEASE,
    OP_SUBMIT_REVIEW, OP_CHECK_STATUS, OP_ROLLBACK,
    OP_UPDATE_METADATA, OP_RELEASE,
)
from operation.publishing.providers.base import PublishingProvider

__all__ = [
    "PublishingChange", "PublishingResult", "PublishingStatus",
    "PublishingProvider",
    "SandboxMode", "CredentialRef",
    "GP_DRAFT", "GP_IN_REVIEW", "GP_REJECTED", "GP_APPROVED", "GP_PUBLISHED",
    "AS_PREPARE", "AS_WAITING", "AS_IN_REVIEW", "AS_REJECTED", "AS_READY",
    "OP_CREATE_APP", "OP_UPLOAD_BUILD", "OP_CREATE_RELEASE",
    "OP_SUBMIT_REVIEW", "OP_CHECK_STATUS", "OP_ROLLBACK",
    "OP_UPDATE_METADATA", "OP_RELEASE",
]
