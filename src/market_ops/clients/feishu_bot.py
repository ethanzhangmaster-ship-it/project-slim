from __future__ import annotations

from typing import Any

import requests


class FeishuBotClient:
    def __init__(self, webhook: str) -> None:
        self._webhook = webhook

    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            self._webhook,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"msg_type": "interactive", "card": card},
            timeout=30,
        )
        response.encoding = "utf-8"
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (0, None):
            raise RuntimeError(f"Feishu bot webhook error: {payload}")
        return payload
