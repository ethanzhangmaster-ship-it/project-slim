"""Retry Manager - 重试管理器"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class RetryResult:
    """重试结果"""
    success: bool = False
    attempts: int = 0
    last_error: str = ""
    output: Any = None


class RetryManager:
    """重试管理器"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def execute(self, func: Callable, *args, **kwargs) -> RetryResult:
        """执行带重试的函数"""
        result = RetryResult()

        for attempt in range(1, self.max_retries + 1):
            result.attempts = attempt
            try:
                output = func(*args, **kwargs)
                result.success = True
                result.output = output
                return result
            except Exception as e:
                result.last_error = str(e)
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                    time.sleep(delay)

        return result

    def should_retry(self, attempt: int, error_code: str = "") -> bool:
        """判断是否应该重试"""
        if attempt >= self.max_retries:
            return False
        retryable_errors = ["timeout", "rate_limit", "server_error", "500", "502", "503"]
        return any(err in error_code.lower() for err in retryable_errors)