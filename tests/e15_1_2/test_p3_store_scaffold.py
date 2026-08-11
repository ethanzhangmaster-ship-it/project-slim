"""
P3 — Store API scaffold dry-run validation.

Guarantees the scaffold is correct WITHOUT any real credentials or network:
  * credential vault round-trips (App Store + Google Play)
  * real clients with no creds stay disabled (no network, no crash)
  * arm_real_client override routes correctly (seam works end-to-end)
  * collect_store_status is safe in dry_run / empty-vault (real_api_called=False)
  * auth JWTs are well-formed and cryptographically self-verifiable
"""
from __future__ import annotations

import base64
import json

import pytest

from operation.providers.live import auth
from operation.providers.live.store_keys import (
    get_appstore,
    get_googleplay,
    has_any,
    set_appstore,
    set_googleplay,
)
from operation.publishing.providers.app_store.real_client import (
    AppStoreRealClient,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)
from operation.publishing.store_status import collect_store_status


# --------------------------------------------------------------------------- #
# Credential vault
# --------------------------------------------------------------------------- #
@pytest.fixture
def tmp_vault(tmp_path, monkeypatch):
    p = tmp_path / "store_keys.json"
    monkeypatch.setattr(
        "operation.providers.live.store_keys._store_path", lambda: str(p))
    # also point store_status's imported getters at the same tmp path
    monkeypatch.setattr(
        "operation.publishing.store_status.get_appstore",
        lambda: get_appstore())
    monkeypatch.setattr(
        "operation.publishing.store_status.get_googleplay",
        lambda: get_googleplay())
    monkeypatch.setattr(
        "operation.publishing.store_status.has_any",
        lambda: has_any())
    return p


def test_vault_appstore_roundtrip(tmp_vault):
    set_appstore("KEYID123", "issuer-uuid", "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----")
    c = get_appstore()
    assert c["key_id"] == "KEYID123"
    assert c["issuer_id"] == "issuer-uuid"
    assert "PRIVATE KEY" in c["private_key_p8"]
    assert has_any() is True


def test_vault_googleplay_roundtrip(tmp_vault):
    set_googleplay("/secret/sa.json")
    c = get_googleplay()
    assert c["service_account_json_path"] == "/secret/sa.json"
    assert has_any() is True


def test_vault_empty_is_none(tmp_vault):
    assert get_appstore() is None
    assert get_googleplay() is None
    assert has_any() is False


# --------------------------------------------------------------------------- #
# Real clients: no creds -> disabled, no network
# --------------------------------------------------------------------------- #
def test_appstore_no_creds_disabled():
    c = AppStoreRealClient(credential={"bundle_id": "com.x.g"})
    res = c.check_status("game_x")
    assert res["status"] == "unknown"
    assert "credentials" in (res.get("error") or "")
    # _call_api itself must not reach the network
    api = c._call_api("GET", "/apps")
    assert api["success"] is False
    assert api["status_code"] == 0


def test_googleplay_no_creds_disabled():
    c = GooglePlayRealClient(credential={"package_name": "com.x.g"})
    res = c.check_status("game_y")
    assert res["status"] == "unknown"
    assert "credentials" in (res.get("error") or "")
    api = c._call_api("GET", "/applications/pkg/edits")
    assert api["success"] is False
    assert api["status_code"] == 0


# --------------------------------------------------------------------------- #
# arm_real_client override routes end-to-end (no network)
# --------------------------------------------------------------------------- #
def test_appstore_override_routes():
    def fake(method, path, body):
        if path.startswith("/apps?"):
            return {"success": True,
                    "data": {"data": [{"id": "app_abc"}]}}
        if "appStoreVersions" in path:
            return {"success": True, "data": {"data": [
                {"attributes": {"appStoreState": "READY_FOR_SALE",
                                "versionString": "1.2.0"}}]}}
        return {"success": False, "error": f"unexpected {path}"}

    c = AppStoreRealClient(credential={"key_id": "k", "issuer_id": "i",
                                       "private_key_p8": "x",
                                       "bundle_id": "com.x.g"})
    c.arm_real_client(fake)
    res = c.check_status("game_z")
    assert res["status"] == "ready_for_sale"
    assert res["version"] == "1.2.0"


def test_googleplay_override_routes():
    def fake(method, path, body):
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "data": {"id": "edit_1"}}
        if "tracks/production" in path:
            return {"success": True, "data": {"releases": [
                {"status": "completed", "versionCode": 42}]}}
        return {"success": True, "data": {}}  # DELETE cleanup

    c = GooglePlayRealClient(credential={"service_account_json_path": "/x",
                                         "package_name": "com.x.g"})
    c.arm_real_client(fake)
    res = c.check_status("game_w")
    assert res["status"] == "published"
    assert res["version"] == "42"


# --------------------------------------------------------------------------- #
# collect_store_status safety
# --------------------------------------------------------------------------- #
def test_collect_dry_run_safe():
    out = collect_store_status(
        [{"game_id": "g1", "platform": "ios", "bundle_id": "com.x.g1"},
         {"game_id": "g2", "platform": "android", "package_name": "com.x.g2"}],
        dry_run=True)
    assert out["status"] == "disabled"
    assert out["real_api_called"] is False
    assert out["reason"] == "dry_run"
    assert len(out["per_game"]) == 2


def test_collect_empty_vault_disabled(tmp_vault):
    # vault is empty -> even with dry_run=False it must not call the network
    out = collect_store_status(
        [{"game_id": "g1", "platform": "ios", "bundle_id": "com.x.g1"}],
        dry_run=False, sandbox="production")
    assert out["status"] == "disabled"
    assert out["real_api_called"] is False
    assert out["reason"] == "no_store_credentials"


# --------------------------------------------------------------------------- #
# Auth JWT self-verification (no network)
# --------------------------------------------------------------------------- #
def test_appstore_jwt_self_verify():
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    p8 = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()

    token = auth.make_appstore_jwt("KEYID", "ISSUER", p8)
    parts = token.split(".")
    assert len(parts) == 3
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    assert header["alg"] == "ES256"
    assert header["kid"] == "KEYID"

    signing_input = (parts[0] + "." + parts[1]).encode()
    sig = base64.urlsafe_b64decode(parts[2] + "==")
    # verify with the public key -> proves the signature is valid ES256
    key.public_key().verify(sig, signing_input, ec.ECDSA(hashes.SHA256()))


def test_googleplay_jwt_self_verify():
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sa = {
        "client_email": "svc@proj.iam.gserviceaccount.com",
        "private_key": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode(),
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    token = auth.make_googleplay_jwt(sa)
    parts = token.split(".")
    assert len(parts) == 3
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    assert header["alg"] == "RS256"

    signing_input = (parts[0] + "." + parts[1]).encode()
    sig = base64.urlsafe_b64decode(parts[2] + "==")
    key.public_key().verify(
        sig, signing_input, padding.PKCS1v15(), hashes.SHA256())


__all__ = [
    "test_vault_appstore_roundtrip", "test_vault_googleplay_roundtrip",
    "test_vault_empty_is_none", "test_appstore_no_creds_disabled",
    "test_googleplay_no_creds_disabled", "test_appstore_override_routes",
    "test_googleplay_override_routes", "test_collect_dry_run_safe",
    "test_collect_empty_vault_disabled", "test_appstore_jwt_self_verify",
    "test_googleplay_jwt_self_verify",
]
