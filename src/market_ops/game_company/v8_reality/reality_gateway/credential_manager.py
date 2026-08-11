from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from enum import Enum


class CredentialType(Enum):
    API_KEY = "api_key"
    OAUTH = "oauth"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    JWT = "jwt"


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "bearer"

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at

    def expires_in_seconds(self) -> Optional[int]:
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": "***REDACTED***",
            "refresh_token": "***REDACTED***" if self.refresh_token else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "token_type": self.token_type,
        }


@dataclass
class Credential:
    platform: str
    credential_type: CredentialType
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[TokenResponse] = None
    last_refreshed: Optional[datetime] = None
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "credential_type": self.credential_type.value,
            "client_id": self.client_id,
            "client_secret": "***REDACTED***" if self.client_secret else None,
            "api_key": "***REDACTED***" if self.api_key else None,
            "username": self.username,
            "password": "***REDACTED***" if self.password else None,
            "token": self.token.to_dict() if self.token else None,
            "last_refreshed": self.last_refreshed.isoformat() if self.last_refreshed else None,
            "is_valid": self.is_valid,
        }


class CredentialManager:
    def __init__(self):
        self._credentials: Dict[str, Credential] = {}
        self._refresh_callbacks: Dict[str, callable] = {}

    def add_credential(self, credential: Credential) -> Credential:
        self._credentials[credential.platform] = credential
        return credential

    def get_credential(self, platform: str) -> Optional[Credential]:
        return self._credentials.get(platform)

    def remove_credential(self, platform: str) -> bool:
        if platform in self._credentials:
            del self._credentials[platform]
            return True
        return False

    def refresh_token(self, platform: str) -> Optional[TokenResponse]:
        cred = self.get_credential(platform)
        if not cred or not cred.token or not cred.token.refresh_token:
            return None

        callback = self._refresh_callbacks.get(platform)
        if callback:
            try:
                new_token = callback(cred)
                cred.token = new_token
                cred.last_refreshed = datetime.now()
                return new_token
            except Exception:
                cred.is_valid = False
                return None
        else:
            cred.token = TokenResponse(
                access_token=f"refreshed_token_{platform}",
                refresh_token=cred.token.refresh_token,
                expires_at=datetime.now() + timedelta(hours=1),
            )
            cred.last_refreshed = datetime.now()
            return cred.token

    def register_refresh_callback(self, platform: str, callback: callable):
        self._refresh_callbacks[platform] = callback

    def check_expiration(self, platform: str) -> bool:
        cred = self.get_credential(platform)
        if not cred or not cred.token:
            return False
        return cred.token.is_expired()

    def get_expiring_credentials(self, hours_before: int = 24) -> List[Credential]:
        expiring = []
        for cred in self._credentials.values():
            if cred.token and cred.token.expires_in_seconds():
                if cred.token.expires_in_seconds() < hours_before * 3600:
                    expiring.append(cred)
        return expiring

    def get_valid_credentials(self) -> List[Credential]:
        return [c for c in self._credentials.values() if c.is_valid]

    def invalidate_credential(self, platform: str) -> bool:
        cred = self.get_credential(platform)
        if cred:
            cred.is_valid = False
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._credentials)
        valid = len(self.get_valid_credentials())
        expiring = len(self.get_expiring_credentials())
        return {
            "total_credentials": total,
            "valid_credentials": valid,
            "expiring_credentials": expiring,
            "invalid_credentials": total - valid,
        }

    def get_credentials(self) -> Dict[str, Credential]:
        return dict(self._credentials)
