"""Phase 2.1.6 — 广告结构检查（Facebook UA 广告三段式）。

将图像按上/中/下三等分 crop，分别用 CLIP 判断：
- Top    : 是否像 Brand / Game Identity 区
- Middle : 是否像 Gameplay Mechanic 区
- Bottom : 是否像 Reward / CTA 区

ad_structure_score = 三区「正确内容」概率的均值。

这是 CLIP 区域近似，不是版面解析。用于趋势判断 + Hard Reject 的
「Fantasy Illustration / 无广告结构」辅助判定。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.ranking.clip_ranker import (  # noqa: E402
    OpenCLIPEncoder,
)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _prob(pos: float, neg: float, temperature: float = 100.0) -> float:
    """temperature-scaled softmax（同 gameplay_checker，放大 CLIP 微小差值）。"""
    m = max(pos, neg)
    ex = np.exp([(pos - m) * temperature, (neg - m) * temperature])
    return float(ex[0] / ex.sum())


_TOP_PROMPTS = (
    "top area of a mobile game ad showing brand identity: game logo, title, or game name banner",
    "top area that is empty, plain background, or has no brand identity",
)
_MID_PROMPTS = (
    "middle area showing the core merge gameplay mechanic: items merging, before and after",
    "middle area that is a static character or plain scenery with no gameplay",
)
_BOT_PROMPTS = (
    "bottom area showing the reward or call-to-action: a legendary item, character reward, or CTA tagline",
    "bottom area that is empty or just background with no reward or CTA",
)


class AdStructureChecker:
    def __init__(self, encoder: OpenCLIPEncoder) -> None:
        self.enc = encoder
        self._top = np.stack([encoder.encode_text(p) for p in _TOP_PROMPTS])
        self._mid = np.stack([encoder.encode_text(p) for p in _MID_PROMPTS])
        self._bot = np.stack([encoder.encode_text(p) for p in _BOT_PROMPTS])

    @staticmethod
    def _crop_region(path: str | Path, band: str) -> str | Path:
        """就地生成临时 crop 文件并返回路径（OpenCLIPEncoder 吃路径）。"""
        import tempfile

        img = Image.open(path).convert("RGB")
        w, h = img.size
        if band == "top":
            box = (0, 0, w, h // 3)
        elif band == "mid":
            box = (0, h // 3, w, 2 * h // 3)
        else:
            box = (0, 2 * h // 3, w, h)
        crop = img.crop(box)
        tmp = Path(tempfile.gettempdir()) / f"_adstruct_{band}.png"
        crop.save(tmp)
        return tmp

    def score(self, image_path: str | Path) -> dict[str, float]:
        res: dict[str, float] = {}
        for band, prompts, emb in (
            ("top", _TOP_PROMPTS, self._top),
            ("middle", _MID_PROMPTS, self._mid),
            ("bottom", _BOT_PROMPTS, self._bot),
        ):
            crop_path = self._crop_region(image_path, band)
            imb = self.enc.encode_image(crop_path)
            p = _cosine(imb, emb[0])
            n = _cosine(imb, emb[1])
            res[band] = round(_prob(p, n), 4)
        res["ad_structure_score"] = round(
            float(np.mean([res["top"], res["middle"], res["bottom"]])), 4
        )
        return res
