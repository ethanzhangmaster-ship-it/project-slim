"""E15.2.5 — module-level generic helper ``feishu.send_markdown_card``.

The helper exists so secondary daily cards (per-app fleet verdicts, weekly
growth briefing, the unified morning digest) can push a markdown card
without the ``FeishuNotifier(None).send_markdown_card(...)`` idiom. Two
guarantees the caller batch jobs rely on:

  * success  -> returns the Feishu API response dict (caller marks
                ``notified = res is not None``).
  * no webhook configured -> returns ``None`` (no crash), so a missing
                credential degrades to "not pushed" instead of raising.
  * other errors (rate-limit exhaustion / network) still propagate and are
                caught by the caller's surrounding try/except.
"""
import pytest

from operation.optimizer.notify import feishu
from operation.optimizer.notify.feishu import (
    FeishuNotifier,
    send_markdown_card,
)


class TestGenericHelper:
    def test_success_returns_response(self, monkeypatch):
        monkeypatch.setattr(
            FeishuNotifier, "_post",
            lambda self, payload: {"code": 0, "msg": "success"})

        res = send_markdown_card(
            "标题", "**正文** markdown", color="green",
            webhook_url="https://example.com/hook")
        assert res == {"code": 0, "msg": "success"}

    def test_no_webhook_returns_none(self, monkeypatch):
        # No explicit url + store lookup empty -> graceful None, no raise.
        monkeypatch.setattr(feishu, "load_webhook", lambda *a, **k: None)
        assert send_markdown_card("t", "b") is None

    def test_routes_through_post_with_color(self, monkeypatch):
        captured = {}

        def fake_post(self, payload):
            captured["p"] = payload
            return {"code": 0}

        monkeypatch.setattr(FeishuNotifier, "_post", fake_post)
        send_markdown_card(
            "🚢 判决", "**Winner** SCALE", color="orange",
            webhook_url="https://x")
        p = captured["p"]
        assert p["msg_type"] == "interactive"
        assert p["card"]["header"]["template"] == "orange"
        assert p["card"]["header"]["title"]["content"] == "🚢 判决"
        assert p["card"]["elements"][0]["content"] == "**Winner** SCALE"

    def test_non_ratelimit_error_propagates(self, monkeypatch):
        class _Resp:
            def read(self):
                return b'{"code": 19001, "msg": "invalid webhook"}'
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *a, **k: _Resp())
        with pytest.raises(RuntimeError):
            send_markdown_card("t", "b", webhook_url="https://x")
