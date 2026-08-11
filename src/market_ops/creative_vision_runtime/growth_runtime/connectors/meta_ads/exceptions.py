"""E13.1.2 Meta Ads Exceptions — Meta 广告平台专用异常."""

from __future__ import annotations


class MetaAdsError(Exception):
    """Meta Ads 基础异常."""


class MetaAuthError(MetaAdsError):
    """认证失败."""
    pass


class MetaAPIError(MetaAdsError):
    """API 请求错误."""

    def __init__(self, message: str = "", error_code: int = 0, error_type: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type


class MetaRateLimitError(MetaAdsError):
    """速率限制错误."""

    def __init__(self, message: str = "", retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class MetaValidationError(MetaAdsError):
    """数据校验错误."""
    pass


class MetaDataNotFoundError(MetaAdsError):
    """数据不存在."""
    pass


class MetaConnectionError(MetaAdsError):
    """连接错误."""
    pass


class MetaConfigError(MetaAdsError):
    """配置错误."""
    pass