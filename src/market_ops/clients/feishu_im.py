from __future__ import annotations

import json
from typing import Any

import requests


class FeishuIMClient:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._token: str | None = None
        self._base_url = "https://open.feishu.cn/open-apis"

    def reply_card(self, message_id: str, card: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json={
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
        ).json()

    def send_card_to_chat(self, chat_id: str, card: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
        ).json()

    def reply_text(self, message_id: str, text: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json={
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
        ).json()

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if not self._token:
            self._token = self._fetch_tenant_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json; charset=utf-8"
        response = requests.request(method, f"{self._base_url}{path}", headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (0, None):
            raise RuntimeError(f"Feishu IM API error: {payload}")
        return response

    def _fetch_tenant_token(self) -> str:
        response = requests.post(
            f"{self._base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Failed to get Feishu token: {payload}")
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("Feishu token response did not include tenant_access_token.")
        return token
