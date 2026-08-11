"""Retry Policy"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout",
        "rate_limit",
        "server_error",
        "network_error",
        "500",
        "502",
        "503",
        "504",
    ])
    fallback_platforms: List[str] = field(default_factory=list)

    def should_retry(self, error: str, retry_count: int) -> bool:
        if retry_count >= self.max_retries:
            return False
        error_lower = error.lower()
        return any(retryable in error_lower for retryable in self.retryable_errors)

    def get_delay(self, retry_count: int) -> float:
        delay = self.initial_delay * (self.backoff_factor ** retry_count)
        return min(delay, self.max_delay)

    def get_fallback_platform(self, current_platform: str) -> str:
        for platform in self.fallback_platforms:
            if platform != current_platform:
                return platform
        return ""
