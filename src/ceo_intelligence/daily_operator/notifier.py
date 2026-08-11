"""E17.9 — Notification（第一阶段：文件落盘；第二阶段留 seam）。

- Notifier Protocol：notify(date, audience, markdown) → 送达标识（路径/消息 id）
- FileNotifier：CEO 版写 reports/daily/YYYY-MM-DD.md（spec 主文件），
  其余受众写 reports/daily/YYYY-MM-DD.{audience}.md
- 未来接 Slack/Discord/Telegram/Email：实现同一 Protocol 即可，
  agent 不需要改一行代码。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Protocol, runtime_checkable

DEFAULT_REPORT_DIR = "reports/daily"


@runtime_checkable
class Notifier(Protocol):
    def notify(self, date: str, audience: str, markdown: str) -> str:
        """投递一份晨报，返回送达标识（文件路径 / 消息 id）。"""
        ...


class FileNotifier:
    """第一阶段：写本地 Markdown 文件。"""

    def __init__(self, report_dir: str = DEFAULT_REPORT_DIR):
        self.report_dir = Path(report_dir)

    def notify(self, date: str, audience: str, markdown: str) -> str:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        name = f"{date}.md" if audience == "ceo" else f"{date}.{audience}.md"
        path = self.report_dir / name
        path.write_text(markdown, encoding="utf-8")
        return str(path)


class NullNotifier:
    """测试/静默模式：不落盘，只回显标识。"""

    def __init__(self):
        self.sent: List[tuple] = []

    def notify(self, date: str, audience: str, markdown: str) -> str:
        self.sent.append((date, audience, len(markdown)))
        return f"null://{date}/{audience}"


__all__ = ["Notifier", "FileNotifier", "NullNotifier", "DEFAULT_REPORT_DIR"]
