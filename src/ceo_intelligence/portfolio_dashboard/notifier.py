"""E17.10 Portfolio Dashboard — file notifier.

Writes the rendered dashboard to ``reports/portfolio/`` as three files:
- ``portfolio_{date}.md``    Markdown CEO view
- ``portfolio_{date}.html``  self-contained static HTML snapshot
- ``portfolio_{date}.json``  serialized PortfolioDashboard (machine-readable)

Lean discipline: plain files only, no server, no push channel.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import PortfolioDashboard
from .reporter import PortfolioReporter


class FileNotifier:
    """Persists dashboard artifacts under a reports directory."""

    def __init__(self, reports_dir: str | Path = "reports/portfolio") -> None:
        self.reports_dir = Path(reports_dir)

    def notify(self, dash: PortfolioDashboard) -> List[str]:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        reporter = PortfolioReporter()
        safe_date = dash.date.replace(":", "-").replace("/", "-")

        md_path = self.reports_dir / f"portfolio_{safe_date}.md"
        html_path = self.reports_dir / f"portfolio_{safe_date}.html"
        json_path = self.reports_dir / f"portfolio_{safe_date}.json"

        md_path.write_text(reporter.to_markdown(dash), encoding="utf-8")
        html_path.write_text(reporter.to_html(dash), encoding="utf-8")
        json_path.write_text(
            json.dumps(dash.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return [str(md_path), str(html_path), str(json_path)]


__all__ = ["FileNotifier"]
