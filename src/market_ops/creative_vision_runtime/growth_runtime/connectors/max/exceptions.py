"""E13.1.4 MAX Exceptions — MAX 广告变现平台专用异常."""

from __future__ import annotations


class MAXError(Exception):
    """MAX 基础异常."""
    pass


class MAXAuthError(MAXError):
    """认证失败."""
    pass


class MAXAPIError(MAXError):
    """API 请求错误."""

    def __init__(self, message: str = "", error_code: int = 0, error_type: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type


class MAXRateLimitError(MAXError):
    """速率限制错误."""

    def __init__(self, message: str = "", retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class MAXValidationError(MAXError):
    """数据校验错误."""
    pass


class MAXDataNotFoundError(MAXError):
    """数据不存在."""
    pass


class MAXConnectionError(MAXError):
    """连接错误."""
    pass


class MAXConfigError(MAXError):
    """配置错误."""
    pass