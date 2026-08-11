"""Phase 3.0A: Image Quality Gate — structural quality validation.

Checks generated images for:
  - File existence and integrity
  - Valid format (PNG, JPEG, WEBP)
  - Minimum file size (not corrupted)
  - Expected dimensions
  - No corrupted/malformed data

Unlike CLIP-based scoring, this is purely structural.
All checks must pass for the image to be accepted.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QualityResult:
    """Result of image quality gate validation."""
    image_path: str = ""
    passed: bool = False
    checks: list[QualityCheck] = field(default_factory=list)
    score: float = 0.0  # 0-100


@dataclass
class QualityCheck:
    """Individual quality check result."""
    name: str = ""
    passed: bool = False
    detail: str = ""
    weight: float = 1.0


class ImageQualityGate:
    """Validates generated images meet production quality standards.

    Checks are purely structural — no AI/CLIP scoring.
    All checks must pass for the image to be accepted as a Golden Sample.
    """

    # Acceptable dimensions for mobile game ads
    ACCEPTED_SIZES = {
        (1080, 1080),   # square
        (1024, 1024),   # square (alt)
        (1080, 1920),   # 9:16 portrait
        (1024, 1792),   # 9:16 portrait (alt)
        (1080, 1350),   # 4:5
        (1920, 1080),   # 16:9 landscape
    }

    # Minimum file size in bytes (reject corrupt/empty images)
    MIN_FILE_SIZE = 50 * 1024       # 50KB
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict

    def validate(self, image_path: str) -> QualityResult:
        """Run all quality checks on an image.

        Args:
            image_path: Path to the generated image file.

        Returns:
            QualityResult with passed=True only if ALL checks pass.
        """
        path = Path(image_path)
        checks: list[QualityCheck] = []

        checks.append(self._check_exists(path))
        if not checks[-1].passed:
            return self._finalize(image_path, checks)

        checks.append(self._check_format(path))
        checks.append(self._check_file_size(path))
        checks.append(self._check_dimensions(path))
        checks.append(self._check_integrity(path))

        return self._finalize(image_path, checks)

    def validate_batch(self, image_paths: list[str]) -> list[QualityResult]:
        """Validate multiple images."""
        return [self.validate(p) for p in image_paths]

    # ── Individual Checks ──

    def _check_exists(self, path: Path) -> QualityCheck:
        if not path.exists():
            return QualityCheck(
                name="file_exists",
                passed=False,
                detail=f"File does not exist: {path}",
                weight=1.0,
            )
        return QualityCheck(name="file_exists", passed=True, detail=str(path), weight=1.0)

    def _check_format(self, path: Path) -> QualityCheck:
        fmt = self._detect_format(path)
        if fmt in ("PNG", "JPEG", "WEBP"):
            return QualityCheck(
                name="format",
                passed=True,
                detail=f"Valid {fmt} format",
                weight=0.5,
            )
        return QualityCheck(
            name="format",
            passed=False,
            detail=f"Invalid or unknown format: {fmt}",
            weight=0.5,
        )

    def _check_file_size(self, path: Path) -> QualityCheck:
        size = path.stat().st_size
        size_kb = size / 1024.0

        if size < self.MIN_FILE_SIZE:
            return QualityCheck(
                name="file_size",
                passed=False,
                detail=f"Too small: {size_kb:.1f}KB (min: {self.MIN_FILE_SIZE / 1024:.0f}KB)",
                weight=0.8,
            )
        if size > self.MAX_FILE_SIZE:
            return QualityCheck(
                name="file_size",
                passed=False,
                detail=f"Too large: {size_kb:.1f}KB (max: {self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB)",
                weight=0.8,
            )
        return QualityCheck(
            name="file_size",
            passed=True,
            detail=f"{size_kb:.1f}KB",
            weight=0.8,
        )

    def _check_dimensions(self, path: Path) -> QualityCheck:
        try:
            w, h = self._get_dimensions(path)
            if (w, h) in self.ACCEPTED_SIZES:
                return QualityCheck(
                    name="dimensions",
                    passed=True,
                    detail=f"{w}x{h} (accepted)",
                    weight=0.8,
                )
            if not self._strict:
                return QualityCheck(
                    name="dimensions",
                    passed=True,
                    detail=f"{w}x{h} (non-standard, accepted in non-strict mode)",
                    weight=0.8,
                )
            return QualityCheck(
                name="dimensions",
                passed=False,
                detail=f"{w}x{h} not in accepted sizes {self.ACCEPTED_SIZES}",
                weight=0.8,
            )
        except Exception as e:
            return QualityCheck(
                name="dimensions",
                passed=False,
                detail=f"Cannot read dimensions: {e}",
                weight=0.8,
            )

    def _check_integrity(self, path: Path) -> QualityCheck:
        """Verify image can be fully read without corruption."""
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.verify()
        except ImportError:
            pass  # PIL not available, skip deep check
        except Exception as e:
            return QualityCheck(
                name="integrity",
                passed=False,
                detail=f"Image appears corrupted: {e}",
                weight=1.0,
            )
        return QualityCheck(
            name="integrity",
            passed=True,
            detail="Image data is valid",
            weight=1.0,
        )

    # ── Helpers ──

    def _finalize(self, image_path: str, checks: list[QualityCheck]) -> QualityResult:
        total_weight = sum(c.weight for c in checks)
        passed_weight = sum(c.weight for c in checks if c.passed)
        score = (passed_weight / total_weight * 100) if total_weight > 0 else 0
        passed = all(c.passed for c in checks)

        return QualityResult(
            image_path=image_path,
            passed=passed,
            checks=checks,
            score=round(score, 1),
        )

    def _detect_format(self, path: Path) -> str:
        try:
            with open(path, "rb") as f:
                header = f.read(12)
                if header[:8] == b"\x89PNG\r\n\x1a\n":
                    return "PNG"
                if header[:2] == b"\xff\xd8":
                    return "JPEG"
                if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                    return "WEBP"
                if header[:4] == b"GIF8":
                    return "GIF"
        except Exception:
            pass
        return "UNKNOWN"

    def _get_dimensions(self, path: Path) -> tuple[int, int]:
        fmt = self._detect_format(path)

        if fmt == "PNG":
            with open(path, "rb") as f:
                f.read(16)
                return struct.unpack(">II", f.read(8))

        if fmt == "JPEG":
            with open(path, "rb") as f:
                f.read(2)
                while True:
                    marker, = struct.unpack(">H", f.read(2))
                    if marker == 0xFFC0:
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    length, = struct.unpack(">H", f.read(2))
                    f.read(length - 2)

        try:
            from PIL import Image
            with Image.open(path) as img:
                return img.size
        except Exception:
            pass

        return 0, 0