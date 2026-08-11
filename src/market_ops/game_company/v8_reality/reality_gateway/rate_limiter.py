from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime
from enum import Enum
import time


class RateLimitStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"
    BLOCKED = "blocked"


@dataclass
class RateLimitConfig:
    max_requests: int = 1000
    time_window_seconds: int = 3600
    burst_limit: int = 100
    cooldown_seconds: int = 60
    backoff_multiplier: float = 1.5


@dataclass
class RateLimitState:
    config: RateLimitConfig
    requests_made: int = 0
    burst_requests_made: int = 0
    window_start: float = 0
    burst_window_start: float = 0
    blocked_until: float = 0
    remaining: int = 1000

    def reset_window(self):
        now = time.time()
        if now - self.window_start > self.config.time_window_seconds:
            self.requests_made = 0
            self.window_start = now

    def reset_burst(self):
        now = time.time()
        if now - self.burst_window_start > 60:
            self.burst_requests_made = 0
            self.burst_window_start = now

    def can_make_request(self) -> bool:
        now = time.time()
        if now < self.blocked_until:
            return False

        self.reset_window()
        self.reset_burst()

        if self.requests_made >= self.config.max_requests:
            return False

        if self.burst_requests_made >= self.config.burst_limit:
            return False

        return True

    def record_request(self):
        now = time.time()
        self.requests_made += 1
        self.burst_requests_made += 1
        self.remaining = max(0, self.config.max_requests - self.requests_made)

    def get_wait_time(self) -> float:
        now = time.time()
        if now < self.blocked_until:
            return self.blocked_until - now

        self.reset_window()
        if self.requests_made >= self.config.max_requests:
            return self.config.time_window_seconds - (now - self.window_start)

        return 0.0


class RateLimiter:
    def __init__(self):
        self._limits: Dict[str, RateLimitState] = {}
        self._default_config = RateLimitConfig()

    def register_platform(self, platform: str, config: Optional[RateLimitConfig] = None):
        self._limits[platform] = RateLimitState(
            config=config or self._default_config,
            window_start=time.time(),
            burst_window_start=time.time(),
        )

    def check(self, platform: str) -> RateLimitStatus:
        state = self._limits.get(platform)
        if not state:
            return RateLimitStatus.OK

        now = time.time()
        if now < state.blocked_until:
            return RateLimitStatus.BLOCKED

        state.reset_window()
        state.reset_burst()

        usage_ratio = state.requests_made / state.config.max_requests

        if usage_ratio >= 1.0:
            return RateLimitStatus.EXCEEDED
        elif usage_ratio >= 0.8:
            return RateLimitStatus.WARNING
        else:
            return RateLimitStatus.OK

    def acquire(self, platform: str) -> bool:
        state = self._limits.get(platform)
        if not state:
            return True

        if not state.can_make_request():
            return False

        state.record_request()
        return True

    def wait_for_available(self, platform: str, timeout: float = 60.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire(platform):
                return True
            wait_time = self.get_wait_time(platform)
            time.sleep(min(wait_time, 1.0))
        return False

    def get_wait_time(self, platform: str) -> float:
        state = self._limits.get(platform)
        if not state:
            return 0.0
        return state.get_wait_time()

    def get_state(self, platform: str) -> Optional[RateLimitState]:
        return self._limits.get(platform)

    def get_stats(self, platform: str) -> Dict[str, Any]:
        state = self._limits.get(platform)
        if not state:
            return {"platform": platform, "configured": False}

        now = time.time()
        state.reset_window()
        usage_ratio = state.requests_made / state.config.max_requests

        return {
            "platform": platform,
            "requests_made": state.requests_made,
            "max_requests": state.config.max_requests,
            "remaining": state.remaining,
            "usage_ratio": usage_ratio,
            "window_remaining": max(0, state.config.time_window_seconds - (now - state.window_start)),
            "status": self.check(platform).value,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        return {platform: self.get_stats(platform) for platform in self._limits}

    def reset_limit(self, platform: str):
        if platform in self._limits:
            state = self._limits[platform]
            state.requests_made = 0
            state.burst_requests_made = 0
            state.window_start = time.time()
            state.burst_window_start = time.time()
            state.blocked_until = 0
            state.remaining = state.config.max_requests

    def block_platform(self, platform: str, duration_seconds: float):
        if platform in self._limits:
            self._limits[platform].blocked_until = time.time() + duration_seconds
