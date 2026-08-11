"""V4.4.1 Artifact Manager — AI asset lifecycle management.

Manages all AI artifacts:
  Creative videos, images, prompts, embeddings, model checkpoints, generated assets.

Lifecycle: ACTIVE → ARCHIVED → EXPIRED → DELETED
Supports: versioning, storage tracking, expiry, search by tags.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from .schemas import Artifact, ArtifactType, ArtifactStatus


class ArtifactManager:
    """AI artifact lifecycle manager."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}
        self._by_type: dict[str, set[str]] = {}      # artifact_type → {artifact_id}
        self._by_tag: dict[str, set[str]] = {}        # tag → {artifact_id}
        self._version_history: dict[str, list[str]] = {}  # name → [artifact_id versions]

    def register(self, name: str, artifact_type: ArtifactType,
                 storage_path: str = "",
                 size_bytes: int = 0,
                 version: str = "1.0.0",
                 expires_at: float = 0.0,
                 tags: list[str] | None = None,
                 data: bytes | None = None,
                 metadata: dict[str, Any] | None = None) -> Artifact:
        """Register a new artifact.

        Args:
            name: Human-readable name.
            artifact_type: Type of artifact.
            storage_path: Where it's stored.
            size_bytes: Size in bytes.
            version: Version string.
            expires_at: Expiry timestamp (0 = never).
            tags: Tags for discovery.
            data: Optional raw data for checksum.
            metadata: Additional metadata.

        Returns:
            The registered Artifact.
        """
        artifact_id = str(uuid.uuid4())[:12]
        checksum = ""
        if data:
            checksum = hashlib.sha256(data).hexdigest()[:16]
        if size_bytes == 0 and data:
            size_bytes = len(data)

        artifact = Artifact(
            artifact_id=artifact_id,
            name=name,
            artifact_type=artifact_type,
            status=ArtifactStatus.ACTIVE,
            version=version,
            storage_path=storage_path,
            size_bytes=size_bytes,
            checksum=checksum,
            created_at=time.time(),
            expires_at=expires_at,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._artifacts[artifact_id] = artifact

        # Index by type
        atype = artifact_type.value
        if atype not in self._by_type:
            self._by_type[atype] = set()
        self._by_type[atype].add(artifact_id)

        # Index by tag
        for tag in artifact.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(artifact_id)

        # Version history
        if name not in self._version_history:
            self._version_history[name] = []
        self._version_history[name].append(artifact_id)

        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        """Get an artifact by ID."""
        return self._artifacts.get(artifact_id)

    def get_latest(self, name: str) -> Artifact | None:
        """Get the latest version of an artifact by name."""
        versions = self._version_history.get(name, [])
        if not versions:
            return None
        return self._artifacts.get(versions[-1])

    def get_version(self, name: str, version: str) -> Artifact | None:
        """Get a specific version of an artifact."""
        for aid in self._version_history.get(name, []):
            artifact = self._artifacts.get(aid)
            if artifact and artifact.version == version:
                return artifact
        return None

    def find_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        """Find artifacts by type."""
        ids = self._by_type.get(artifact_type.value, set())
        return [self._artifacts[aid] for aid in ids if aid in self._artifacts]

    def find_by_tag(self, tag: str) -> list[Artifact]:
        """Find artifacts by tag."""
        ids = self._by_tag.get(tag, set())
        return [self._artifacts[aid] for aid in ids if aid in self._artifacts]

    def find_by_tags(self, tags: list[str]) -> list[Artifact]:
        """Find artifacts matching ALL given tags."""
        if not tags:
            return []
        result_ids = self._by_tag.get(tags[0], set())
        for tag in tags[1:]:
            result_ids = result_ids & self._by_tag.get(tag, set())
        return [self._artifacts[aid] for aid in result_ids if aid in self._artifacts]

    def archive(self, artifact_id: str) -> bool:
        """Archive an artifact."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return False
        artifact.status = ArtifactStatus.ARCHIVED
        artifact.archived_at = time.time()
        return True

    def expire(self, artifact_id: str) -> bool:
        """Mark an artifact as expired."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return False
        artifact.status = ArtifactStatus.EXPIRED
        return True

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact (soft delete)."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return False
        artifact.status = ArtifactStatus.DELETED
        return True

    def auto_expire(self) -> int:
        """Auto-expire artifacts past their expiry date. Returns count."""
        now = time.time()
        count = 0
        for artifact in self._artifacts.values():
            if artifact.expires_at > 0 and now > artifact.expires_at:
                if artifact.status == ArtifactStatus.ACTIVE:
                    self.expire(artifact.artifact_id)
                    count += 1
        return count

    def get_active(self) -> list[Artifact]:
        """Get all active artifacts."""
        return [a for a in self._artifacts.values() if a.status == ArtifactStatus.ACTIVE]

    def get_by_status(self, status: ArtifactStatus) -> list[Artifact]:
        """Get artifacts by status."""
        return [a for a in self._artifacts.values() if a.status == status]

    def get_stats(self) -> dict[str, Any]:
        """Get artifact statistics."""
        by_type: dict[str, dict[str, Any]] = {}
        for atype in ArtifactType:
            artifacts = self.find_by_type(atype)
            if artifacts:
                total_size = sum(a.size_bytes for a in artifacts)
                by_type[atype.value] = {
                    "count": len(artifacts),
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                }

        status_counts = {s.value: len(self.get_by_status(s)) for s in ArtifactStatus}

        return {
            "total_artifacts": len(self._artifacts),
            "by_type": by_type,
            "by_status": status_counts,
            "total_size_mb": round(
                sum(a.size_bytes for a in self._artifacts.values()) / 1024 / 1024, 2
            ),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get artifact summary."""
        return self.get_stats()

    def list_all(self) -> list[dict[str, Any]]:
        """List all artifacts as dicts."""
        return [a.to_dict() for a in self._artifacts.values()]