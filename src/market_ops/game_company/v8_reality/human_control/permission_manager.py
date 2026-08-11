from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class PermissionGroup(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    DEVELOPER = "developer"


@dataclass
class Permission:
    name: str
    description: str = ""
    group: Optional[PermissionGroup] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "group": self.group.value if self.group else None,
        }


@dataclass
class UserPermission:
    user_id: str
    permissions: List[str] = field(default_factory=list)
    groups: List[PermissionGroup] = field(default_factory=list)
    granted_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "permissions": self.permissions,
            "groups": [g.value for g in self.groups],
            "granted_at": self.granted_at,
        }


class PermissionManager:
    def __init__(self):
        self._user_permissions: Dict[str, UserPermission] = {}
        self._permission_definitions: Dict[str, Permission] = {}
        self._group_permissions: Dict[PermissionGroup, Set[str]] = {
            PermissionGroup.ADMIN: {"*"},
            PermissionGroup.OPERATOR: {"approval_request", "emergency_trigger", "decision_review"},
            PermissionGroup.VIEWER: {"view_dashboard", "view_reports", "view_logs"},
            PermissionGroup.AUDITOR: {"view_logs", "export_logs", "audit_access"},
            PermissionGroup.DEVELOPER: {"api_access", "config_edit", "system_monitor"},
        }

    def grant_permission(self, user: str, permission: str) -> bool:
        if user not in self._user_permissions:
            self._user_permissions[user] = UserPermission(user_id=user)
        if permission not in self._user_permissions[user].permissions:
            self._user_permissions[user].permissions.append(permission)
            return True
        return False

    def revoke_permission(self, user: str, permission: str) -> bool:
        if user not in self._user_permissions:
            return False
        if permission in self._user_permissions[user].permissions:
            self._user_permissions[user].permissions.remove(permission)
            return True
        return False

    def check_permission(self, user: str, permission: str) -> bool:
        if user not in self._user_permissions:
            return False
        user_perm = self._user_permissions[user]
        if "*" in user_perm.permissions:
            return True
        if permission in user_perm.permissions:
            return True
        for group in user_perm.groups:
            group_perms = self._group_permissions.get(group, set())
            if "*" in group_perms or permission in group_perms:
                return True
        return False

    def get_user_permissions(self, user: str) -> Optional[UserPermission]:
        return self._user_permissions.get(user)

    def get_permission_groups(self) -> Dict[PermissionGroup, List[str]]:
        return {
            group: list(perms)
            for group, perms in self._group_permissions.items()
        }

    def add_permission_definition(self, permission: Permission) -> Permission:
        self._permission_definitions[permission.name] = permission
        return permission

    def get_permission_definition(self, name: str) -> Optional[Permission]:
        return self._permission_definitions.get(name)

    def grant_group(self, user: str, group: PermissionGroup) -> bool:
        if user not in self._user_permissions:
            self._user_permissions[user] = UserPermission(user_id=user)
        if group not in self._user_permissions[user].groups:
            self._user_permissions[user].groups.append(group)
            return True
        return False

    def revoke_group(self, user: str, group: PermissionGroup) -> bool:
        if user not in self._user_permissions:
            return False
        if group in self._user_permissions[user].groups:
            self._user_permissions[user].groups.remove(group)
            return True
        return False

    def get_users(self) -> List[str]:
        return list(self._user_permissions.keys())

    def get_stats(self) -> Dict[str, Any]:
        total_users = len(self._user_permissions)
        total_permissions = len(self._permission_definitions)
        group_counts = {
            group.value: sum(1 for up in self._user_permissions.values() if group in up.groups)
            for group in PermissionGroup
        }
        return {
            "total_users": total_users,
            "total_permission_definitions": total_permissions,
            "users_by_group": group_counts,
        }