from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum


class APIStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    AUTH_EXPIRED = "auth_expired"


@dataclass
class APIConnection:
    platform: str
    status: APIStatus = APIStatus.DISCONNECTED
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    sync_count: int = 0
    success_rate: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status.value,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
            "sync_count": self.sync_count,
            "success_rate": self.success_rate,
        }


@dataclass
class APICallResult:
    success: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "status_code": self.status_code,
            "headers": self.headers,
        }


class APIManager:
    def __init__(self):
        self._connections: Dict[str, APIConnection] = {}
        self._call_history: List[Dict[str, Any]] = []
        self._request_handlers: Dict[str, Callable] = {}

    def register_connection(self, platform: str, initial_status: APIStatus = APIStatus.DISCONNECTED) -> APIConnection:
        conn = APIConnection(platform=platform, status=initial_status)
        self._connections[platform] = conn
        return conn

    def get_connection(self, platform: str) -> Optional[APIConnection]:
        return self._connections.get(platform)

    def update_connection_status(self, platform: str, status: APIStatus) -> bool:
        if platform in self._connections:
            self._connections[platform].status = status
            if status == APIStatus.CONNECTED:
                self._connections[platform].last_sync = datetime.now()
            return True
        return False

    def execute_request(self, platform: str, endpoint: str, method: str = "GET", **kwargs) -> APICallResult:
        conn = self.get_connection(platform)
        if not conn or conn.status != APIStatus.CONNECTED:
            return APICallResult(
                success=False,
                error=f"Platform {platform} not connected",
                status_code=503,
            )

        start_time = datetime.now()
        try:
            handler = self._request_handlers.get(f"{platform}_{method}", None)
            if handler:
                result = handler(endpoint, **kwargs)
            else:
                result = self._mock_request(platform, endpoint, method, kwargs)

            conn.sync_count += 1
            conn.last_sync = datetime.now()
            conn.success_rate = min(1.0, conn.success_rate + 0.05)

            self._record_call(platform, endpoint, method, True, start_time)
            return result
        except Exception as e:
            conn.success_rate = max(0.0, conn.success_rate - 0.1)
            conn.last_error = str(e)
            conn.status = APIStatus.ERROR

            self._record_call(platform, endpoint, method, False, start_time)
            return APICallResult(
                success=False,
                error=str(e),
                status_code=500,
            )

    def _mock_request(self, platform: str, endpoint: str, method: str, kwargs: Dict[str, Any]) -> APICallResult:
        return APICallResult(
            success=True,
            data={"platform": platform, "endpoint": endpoint, "method": method, **kwargs},
            status_code=200,
        )

    def _record_call(self, platform: str, endpoint: str, method: str, success: bool, start_time: datetime):
        duration = (datetime.now() - start_time).total_seconds()
        self._call_history.append({
            "platform": platform,
            "endpoint": endpoint,
            "method": method,
            "success": success,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
        })

    def register_handler(self, platform: str, method: str, handler: Callable):
        self._request_handlers[f"{platform}_{method}"] = handler

    def get_connections(self) -> List[APIConnection]:
        return list(self._connections.values())

    def get_call_history(self, platform: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        if platform:
            history = [c for c in self._call_history if c.get("platform") == platform]
        else:
            history = self._call_history
        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total_calls = len(self._call_history)
        success_calls = sum(1 for c in self._call_history if c["success"])
        avg_duration = sum(c["duration"] for c in self._call_history) / total_calls if total_calls > 0 else 0
        return {
            "total_connections": len(self._connections),
            "connected_connections": sum(1 for c in self._connections.values() if c.status == APIStatus.CONNECTED),
            "total_calls": total_calls,
            "success_rate": success_calls / total_calls if total_calls > 0 else 0,
            "avg_call_duration": avg_duration,
        }
