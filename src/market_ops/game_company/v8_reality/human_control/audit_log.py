from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class AuditAction(Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    IMPORT = "import"
    ACCESS = "access"


@dataclass
class AuditEntry:
    entry_id: str
    action: AuditAction
    user: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    resource: Optional[str] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "action": self.action.value,
            "user": self.user,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "resource": self.resource,
            "success": self.success,
        }


class AuditLog:
    def __init__(self):
        self._logs: List[AuditEntry] = []

    def log(self, action: AuditAction, user: str, details: Dict[str, Any] = None) -> AuditEntry:
        entry = AuditEntry(
            entry_id=f"audit_{datetime.now().timestamp()}",
            action=action,
            user=user,
            details=details or {},
        )
        self._logs.append(entry)
        return entry

    def get_logs(self, filter: Dict[str, Any] = None) -> List[AuditEntry]:
        filtered = self._logs
        if filter:
            if "action" in filter:
                filtered = [e for e in filtered if e.action == filter["action"]]
            if "user" in filter:
                filtered = [e for e in filtered if e.user == filter["user"]]
            if "start_time" in filter:
                filtered = [e for e in filtered if e.timestamp >= filter["start_time"]]
            if "end_time" in filter:
                filtered = [e for e in filtered if e.timestamp <= filter["end_time"]]
            if "success" in filter:
                filtered = [e for e in filtered if e.success == filter["success"]]
        return sorted(filtered, key=lambda e: e.timestamp, reverse=True)

    def search_logs(self, query: str) -> List[AuditEntry]:
        query_lower = query.lower()
        return sorted(
            [
                e for e in self._logs
                if query_lower in e.user.lower()
                or query_lower in e.action.value.lower()
                or any(query_lower in str(v).lower() for v in e.details.values())
            ],
            key=lambda e: e.timestamp,
            reverse=True
        )

    def get_access_logs(self) -> List[AuditEntry]:
        return self.get_logs({"action": AuditAction.ACCESS})

    def export_logs(self, format: str = "json") -> str:
        logs = self.get_logs()
        if format == "json":
            import json
            return json.dumps([e.to_dict() for e in logs], indent=2, default=str)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["entry_id", "action", "user", "timestamp", "ip_address", "resource", "success"])
            for entry in logs:
                writer.writerow([
                    entry.entry_id,
                    entry.action.value,
                    entry.user,
                    entry.timestamp.isoformat(),
                    entry.ip_address,
                    entry.resource,
                    entry.success,
                ])
            return output.getvalue()
        return str([e.to_dict() for e in logs])

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._logs)
        by_action = {}
        for action in AuditAction:
            count = sum(1 for e in self._logs if e.action == action)
            if count > 0:
                by_action[action.value] = count
        success_count = sum(1 for e in self._logs if e.success)
        return {
            "total_entries": total,
            "entries_by_action": by_action,
            "success_rate": success_count / total if total > 0 else 0,
        }