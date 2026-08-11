"""Reference Manager — 管理历史赢家参考图。

流程：winner_dna -> reference_url -> 校验 URL -> 下载 -> 校验本地文件 -> 缓存。
任何校验失败直接抛 ReferenceError（禁止 fallback text2img）。

缓存位置：<factory_root>/reference_cache/winner_NNN.png
同一 winner 复用已下载的缓存，避免重复拉取。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# 复用 Lovart 的下载工具（已验证可用）
_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.clients.lovart import download_image  # noqa: E402
from market_ops.creative_intelligence.factory.reference.image_validator import (  # noqa: E402
    ReferenceError,
    validate_reference,
)


class ReferenceManager:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_reference(self, winner_dna: dict[str, Any]) -> dict[str, Any]:
        """获取一个 winner 的参考图（下载并校验后缓存）。

        Returns:
            {"path": str, "url": str, "status": "available"}
        Raises:
            ReferenceError: URL 不可达 / 文件损坏 / 缺失，且绝不回退 text2img。
        """
        code = winner_dna.get("winner_code", "000")
        url = (winner_dna.get("reference_url") or "").strip()
        if not url:
            raise ReferenceError(
                f"winner_{code} 的 DNA 中没有 reference_url，无法获取参考图（禁止 text2img 回退）"
            )

        cache_path = self.cache_dir / f"winner_{code}.png"

        # 先校验 URL（可达性 + 内容类型）
        validate_reference(url, cache_path)

        # URL 通过后才下载（若已有缓存且校验通过则跳过下载）
        if not cache_path.exists():
            download_image(url, cache_path)

        # 下载后再次校验本地文件（格式 / 分辨率 / 完整性）
        from market_ops.creative_intelligence.factory.reference.image_validator import (
            validate_image_file,
        )

        validate_image_file(cache_path)

        return {
            "path": str(cache_path),
            "url": url,
            "status": "available",
        }
