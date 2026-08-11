"""Winner DNA Loader — 读取 winners_dna.json，归一化为统一结构。

设计要点（对应需求）：
- 支持按 winner_id 取单个，也支持按多个 id 批量取。
- 缺字段自动 warning（不中断），但不允许 silent failure：
  winner 不存在 / 没有任何可用 winner 时直接抛异常。
- 归一化字段：把原始 JSON 的 creative_id / _cdn_url 等映射为
  spec 约定的 id / reference_url / theme 等，并补 winner_code 短码。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 允许通过 PYTHONPATH 直接 import（与项目其它脚本保持一致）
_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.generation_context import find_project_root  # noqa: E402


# 归一化后建议存在的字段；缺失则 warning
_EXPECTED_FIELDS = (
    "subject",
    "palette",
    "composition",
    "overlay_text",
    "reference_url",
)


class WinnerDNALoader:
    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            root = find_project_root()
            data_path = root / "output" / "creative_analysis" / "dna_cache" / "winners_dna.json"
        self.data_path = Path(data_path)
        if not self.data_path.exists():
            raise FileNotFoundError(f"winners_dna.json 不存在: {self.data_path}")

    # ------------------------------------------------------------------
    def load_all(self) -> list[dict[str, Any]]:
        """读取全部 winner，并按位置补 winner_code 短码。"""
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"winners_dna.json 内容异常（应为非空列表）: {self.data_path}")

        items: list[dict[str, Any]] = []
        for idx, entry in enumerate(raw):
            items.append(self._normalize(entry, idx))
        return items

    def load_winner(self, winner_id: str) -> dict[str, Any]:
        """按 winner_id 取单个 winner。

        winner_id 可以是原始 creative_id，也可以是归一化别名 winner_NNN。
        """
        for w in self.load_all():
            if w["id"] == winner_id or f"winner_{w['winner_code']}" == winner_id:
                return w
        available = [f"winner_{w['winner_code']}" for w in self.load_all()]
        raise KeyError(
            f"未找到 winner: '{winner_id}'。"
            f"可用别名示例: {available[:5]}{'...' if len(available) > 5 else ''}"
        )

    def load_winners(self, winner_ids: list[str]) -> list[dict[str, Any]]:
        """批量取多个 winner（保持入参顺序，缺失的会抛异常）。"""
        return [self.load_winner(wid) for wid in winner_ids]

    # ------------------------------------------------------------------
    def _normalize(self, entry: dict[str, Any], idx: int) -> dict[str, Any]:
        code = f"{idx + 1:03d}"

        subject = (entry.get("subject") or "").strip()
        palette = (entry.get("palette") or "").strip()
        composition = (entry.get("composition") or "").strip()
        overlay_text = (entry.get("overlay_text") or "").strip()
        reference_url = (entry.get("_cdn_url") or "").strip()

        # theme 在原始数据里没有独立字段：用 overall_summary 或 standout 兜底
        standout = entry.get("standout_features") or []
        theme_src = (entry.get("overall_summary") or "").strip()
        if not theme_src and standout:
            theme_src = "; ".join(str(s) for s in standout[:3])
        theme = theme_src

        normalized = {
            "id": entry.get("creative_id") or f"winner_{code}",
            "winner_code": code,
            "subject": subject,
            "theme": theme,
            "palette": palette,
            "composition": composition,
            "overlay_text": overlay_text,
            "hook_type": entry.get("hook_type") or "collection",
            "reference_url": reference_url,
            # 投放表现（供后续阶段/元数据使用）
            "iap_score": entry.get("iap_score", 0),
            "spend": entry.get("spend", 0),
            "ctr": entry.get("ctr", 0),
            "roas_d7": entry.get("roas_d7", 0),
            # 保留原始，便于扩展
            "raw": entry,
        }

        # 缺字段自动 warning（不中断）
        missing = [f for f in _EXPECTED_FIELDS if not normalized.get(f)]
        if missing:
            print(
                f"[WinnerDNALoader][WARN] winner_{code} (id={normalized['id']}) "
                f"缺失字段: {missing}",
                file=sys.stderr,
            )

        return normalized
