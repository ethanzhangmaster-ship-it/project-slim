from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class UploadStatus(Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Screenshot:
    screenshot_id: str
    file_path: str
    locale: str = "en-US"
    device_type: str = "iPhone"
    display_type: str = "standard"
    size_bytes: int = 0
    width: int = 0
    height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "screenshot_id": self.screenshot_id,
            "file_path": self.file_path,
            "locale": self.locale,
            "device_type": self.device_type,
            "display_type": self.display_type,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class UploadResult:
    upload_id: str
    status: UploadStatus = UploadStatus.PENDING
    total_screenshots: int = 0
    uploaded_count: int = 0
    failed_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "upload_id": self.upload_id,
            "status": self.status.value,
            "total_screenshots": self.total_screenshots,
            "uploaded_count": self.uploaded_count,
            "failed_count": self.failed_count,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": self.errors,
        }


class ScreenshotUploader:
    def __init__(self):
        self._uploads: Dict[str, UploadResult] = {}
        self._app_screenshots: Dict[str, List[Screenshot]] = {}

    def upload_screenshots(self, app_id: str, screenshots: List[Dict[str, Any]]) -> UploadResult:
        upload_id = f"upload_{int(datetime.now().timestamp())}"
        result = UploadResult(
            upload_id=upload_id,
            status=UploadStatus.UPLOADING,
            total_screenshots=len(screenshots),
        )

        uploaded_count = 0
        errors = []
        uploaded_screenshots = []

        for idx, screenshot_data in enumerate(screenshots):
            screenshot_id = f"{app_id}_ss_{idx + 1}"
            screenshot = Screenshot(
                screenshot_id=screenshot_id,
                **screenshot_data,
            )
            uploaded_screenshots.append(screenshot)
            uploaded_count += 1

        if app_id not in self._app_screenshots:
            self._app_screenshots[app_id] = []
        self._app_screenshots[app_id].extend(uploaded_screenshots)

        result.status = UploadStatus.COMPLETED
        result.uploaded_count = uploaded_count
        result.completed_at = datetime.now()
        result.errors = errors

        self._uploads[upload_id] = result
        return result

    def get_upload_status(self, upload_id: str) -> Optional[UploadResult]:
        return self._uploads.get(upload_id)

    def validate_screenshots(self, screenshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        valid_formats = ["png", "jpg", "jpeg"]
        valid_device_types = ["iPhone", "iPad", "Apple Watch", "Mac", "Apple TV"]
        valid_locales = ["en-US", "zh-CN", "ja-JP", "ko-KR", "fr-FR", "de-DE"]

        errors = []
        warnings = []

        for idx, screenshot in enumerate(screenshots):
            file_path = screenshot.get("file_path", "")
            ext = file_path.split(".")[-1].lower() if file_path else ""

            if not file_path:
                errors.append(f"Screenshot {idx + 1}: file_path is required")
            elif ext not in valid_formats:
                errors.append(f"Screenshot {idx + 1}: Invalid format '{ext}', must be one of {valid_formats}")

            if screenshot.get("device_type") and screenshot["device_type"] not in valid_device_types:
                warnings.append(f"Screenshot {idx + 1}: Unknown device type '{screenshot['device_type']}'")

            if screenshot.get("locale") and screenshot["locale"] not in valid_locales:
                warnings.append(f"Screenshot {idx + 1}: Unknown locale '{screenshot['locale']}'")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_screenshots": len(screenshots),
            "valid_count": len(screenshots) - len(errors),
        }

    def delete_screenshots(self, app_id: str, screenshot_ids: List[str]) -> Dict[str, Any]:
        if app_id not in self._app_screenshots:
            return {"deleted": 0, "failed": len(screenshot_ids), "errors": ["App not found"]}

        deleted = 0
        failed = 0

        for ss_id in screenshot_ids:
            original_count = len(self._app_screenshots[app_id])
            self._app_screenshots[app_id] = [
                s for s in self._app_screenshots[app_id] if s.screenshot_id != ss_id
            ]
            if len(self._app_screenshots[app_id]) < original_count:
                deleted += 1
            else:
                failed += 1

        return {
            "deleted": deleted,
            "failed": failed,
            "remaining_count": len(self._app_screenshots[app_id]),
        }