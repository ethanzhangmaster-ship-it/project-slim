"""Reference Image Validator.

严格校验历史赢家参考图，任何一项不达标直接抛 ReferenceError。
明确禁止 fallback 到 text2img（由调用方遵守：拿到异常即终止）。

校验项：
- URL 可访问（HTTP 200 + 图像 content-type）
- 本地文件存在且为合法图片格式（magic bytes）
- 分辨率 >= MIN_RESOLUTION
- 图片未损坏（可被解码）
"""
from __future__ import annotations

from pathlib import Path


class ReferenceError(Exception):
    """参考图校验失败异常。

    触发场景：URL 不可达 / 返回非图像 / 文件缺失 / 格式不支持 / 分辨率过低 / 图片损坏。
    设计意图：硬失败，调用方捕获后必须终止流程，禁止回退到 text2img。
    注意：此处自定义而非使用 Python 内置 ReferenceError（弱引用语义），便于显式导入与捕获。
    """


MIN_RESOLUTION = 256  # 短边最小像素；Lovart 出图通常为 1024+


def validate_url(url: str) -> None:
    """校验参考图 URL 可访问。不可访问直接抛 ReferenceError。"""
    if not url or not str(url).startswith("http"):
        raise ReferenceError(f"参考图 URL 非法或为空: '{url}'")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise ReferenceError(f"缺少 requests 依赖，无法校验 URL: {exc}")

    try:
        resp = requests.head(url, timeout=20, allow_redirects=True)
        if resp.status_code >= 400:
            # 部分 CDN 不支持 HEAD，退回 GET（只取头）
            resp = requests.get(url, timeout=20, allow_redirects=True, stream=True)
            resp.close()
        if resp.status_code >= 400:
            raise ReferenceError(f"参考图 URL 不可访问 (HTTP {resp.status_code}): {url}")
        ctype = resp.headers.get("Content-Type", "") or ""
        if ctype and "image" not in ctype.lower():
            raise ReferenceError(f"参考图 URL 返回非图像类型: {ctype} ({url})")
    except ReferenceError:
        raise
    except Exception as exc:  # 网络错误等
        raise ReferenceError(f"校验参考图 URL 失败: {exc} ({url})")


def validate_image_file(path: str | Path) -> None:
    """校验本地图片文件：格式 / 分辨率 / 是否损坏。失败抛 ReferenceError。"""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        raise ReferenceError(f"参考图文件不存在或为空: {p}")

    # 1) magic bytes 初筛
    header = p.read_bytes()[:12]
    is_png = header[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpg = header[:3] == b"\xff\xd8\xff"
    is_webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not (is_png or is_jpg or is_webp):
        raise ReferenceError(f"参考图格式不支持（非 PNG/JPG/WEBP）: {p}")

    # 2) 真正解码，检查分辨率与完整性
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ReferenceError(f"缺少 Pillow 依赖，无法校验图片内容: {exc}")

    try:
        with Image.open(p) as img:
            img.verify()  # 检测损坏
        with Image.open(p) as img:
            w, h = img.size
    except Exception as exc:
        raise ReferenceError(f"参考图损坏或无法解码: {exc} ({p})")

    if w < MIN_RESOLUTION or h < MIN_RESOLUTION:
        raise ReferenceError(
            f"参考图分辨率过低 ({w}x{h} < {MIN_RESOLUTION}): {p}"
        )


def validate_reference(url: str, path: str | Path) -> None:
    """完整校验：先 URL 再本地文件。任一失败抛 ReferenceError。"""
    validate_url(url)
    validate_image_file(path)
