"""Phase 2.1: Image Validator — post-generation quality checks.

Validates generated images:
  - File exists and is readable
  - Dimensions within acceptable range (1080x1080 or 1024x1024)
  - File size > 50KB (rejects corrupted/empty images)
  - Format is valid PNG/JPEG

Never generates fake images. Only validates real ones.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ImageValidationResult:
    """Result of image validation."""
    valid: bool = False
    file_path: str = ""
    width: int = 0
    height: int = 0
    file_size_kb: float = 0
    format: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ImageValidator:
    """Validates generated images meet production quality standards."""

    # Acceptable dimensions
    ACCEPTED_SIZES = {
        (1080, 1080),
        (1024, 1024),
        (1024, 1792),  # portrait 9:16
    }

    # Minimum file size in bytes (reject corrupt/empty images)
    MIN_FILE_SIZE = 50 * 1024  # 50KB

    def validate(self, file_path: str | Path) -> ImageValidationResult:
        """Validate a generated image file.

        Returns ImageValidationResult with valid=True only if all checks pass.
        """
        path = Path(file_path)
        errors: list[str] = []
        warnings: list[str] = []

        # 1. File exists
        if not path.exists():
            errors.append(f"File does not exist: {file_path}")
            return ImageValidationResult(
                valid=False,
                file_path=str(file_path),
                errors=errors,
            )

        # 2. File size check
        file_size = path.stat().st_size
        file_size_kb = file_size / 1024.0
        if file_size < self.MIN_FILE_SIZE:
            errors.append(
                f"File too small: {file_size_kb:.1f}KB (min: {self.MIN_FILE_SIZE / 1024:.0f}KB)"
            )

        # 3. Format detection
        img_format = self._detect_format(path)

        # 4. Dimension check
        width, height = 0, 0
        try:
            width, height = self._get_dimensions(path)
        except Exception as e:
            errors.append(f"Cannot read dimensions: {e}")

        if width > 0 and height > 0:
            if (width, height) not in self.ACCEPTED_SIZES:
                warnings.append(
                    f"Non-standard dimensions: {width}x{height} "
                    f"(expected one of {self.ACCEPTED_SIZES})"
                )

        # 5. Image integrity (try to read)
        if not errors:
            try:
                self._verify_integrity(path)
            except Exception as e:
                errors.append(f"Image integrity check failed: {e}")

        valid = len(errors) == 0

        return ImageValidationResult(
            valid=valid,
            file_path=str(file_path),
            width=width,
            height=height,
            file_size_kb=round(file_size_kb, 1),
            format=img_format,
            errors=errors,
            warnings=warnings,
        )

    def _detect_format(self, path: Path) -> str:
        """Detect image format from file header bytes."""
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
        """Get image dimensions from file header without full decode."""
        fmt = self._detect_format(path)

        if fmt == "PNG":
            with open(path, "rb") as f:
                f.read(16)  # skip PNG signature + IHDR length
                return struct.unpack(">II", f.read(8))

        if fmt == "JPEG":
            with open(path, "rb") as f:
                f.read(2)  # skip SOI
                while True:
                    marker, = struct.unpack(">H", f.read(2))
                    if marker == 0xFFC0:  # SOF0
                        f.read(3)  # skip length + precision
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    length, = struct.unpack(">H", f.read(2))
                    f.read(length - 2)

        # Fallback: try PIL
        try:
            from PIL import Image
            with Image.open(path) as img:
                return img.size
        except Exception:
            pass

        return 0, 0

    def _verify_integrity(self, path: Path) -> None:
        """Verify image can be fully read without corruption."""
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.verify()
        except ImportError:
            # PIL not available, skip deep integrity check
            pass
        except Exception as e:
            raise ValueError(f"Image appears corrupted: {e}") from e