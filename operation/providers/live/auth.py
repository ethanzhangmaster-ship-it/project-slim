"""
P3 — Store API auth helpers.

* App Store Connect: ES256 JWT signed with the .p8 Auth Key (ECDSA P-256).
* Google Play:       RS256 JWT signed with the service-account key, then
                     exchanged for an OAuth2 access token at the token URI.

Both use the managed runtime's `cryptography` package (already installed).
Network is only touched by make_googleplay_token (the token exchange);
make_appstore_jwt / make_googleplay_jwt are pure signing (no network).
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict

from operation.providers.live.http_util import http_json


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# --------------------------------------------------------------------------- #
# App Store Connect — ES256
# --------------------------------------------------------------------------- #
def make_appstore_jwt(key_id: str, issuer_id: str,
                      private_key_p8: str) -> str:
    """Build a signed ES256 JWT for App Store Connect."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
    )

    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + 600,
        "aud": "appstoreconnect-v1",
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    key = load_pem_private_key(private_key_p8.encode("utf-8"), password=None)
    signature = key.sign(signing_input.encode("utf-8"),
                         ec.ECDSA(hashes.SHA256()))
    return signing_input + "." + _b64url(signature)


# --------------------------------------------------------------------------- #
# Google Play — RS256 service-account JWT (then token exchange)
# --------------------------------------------------------------------------- #
def make_googleplay_jwt(service_account: Dict[str, Any]) -> str:
    """Build a signed RS256 JWT assertion for Google Play OAuth2."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
    )

    header = {"alg": "RS256", "typ": "JWT"}
    token_uri = service_account.get(
        "token_uri", "https://oauth2.googleapis.com/token")
    now = int(time.time())
    payload = {
        "iss": service_account["client_email"],
        "scope": "https://www.googleapis.com/auth/androidpublisher",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    key = load_pem_private_key(
        service_account["private_key"].encode("utf-8"), password=None)
    signature = key.sign(signing_input.encode("utf-8"),
                         padding.PKCS1v15(), hashes.SHA256())
    return signing_input + "." + _b64url(signature)


def make_googleplay_token(service_account: Dict[str, Any]) -> str:
    """Exchange the RS256 JWT for an OAuth2 access token (network call)."""
    token_uri = service_account.get(
        "token_uri", "https://oauth2.googleapis.com/token")
    assertion = make_googleplay_jwt(service_account)
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }).encode("utf-8")
    req = urllib.request.Request(
        token_uri, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("access_token", "")


__all__ = [
    "make_appstore_jwt",
    "make_googleplay_jwt",
    "make_googleplay_token",
]
