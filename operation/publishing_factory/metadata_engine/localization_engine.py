"""
E15.1.1 — Localization Engine
==============================

Deterministic localization of an AsoPack into target locales.

No LLM: a curated phrase table maps the small set of template tokens
(brand stays, genre keywords translated) into each locale. Falls back
to the English token if a translation is missing, so output is always
well-formed and testable.

Supported locales: en-US, de-DE, fr-FR, ja-JP, ko-KR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from operation.publishing_factory.metadata_engine.aso_generator import AsoPack

# Curated keyword translations per locale. Brand name passes through.
_LOC_KW: Dict[str, Dict[str, str]] = {
    "de-DE": {"merge": "merge", "magic": "magie", "dragon": "drache",
              "puzzle": "puzzle", "castle": "schloss", "combine": "kombiniere",
              "brain": "hirn", "relax": "entspannen", "idle": "idle",
              "tycoon": "tycoon", "word": "wort", "casual": "casual"},
    "fr-FR": {"merge": "fusion", "magic": "magie", "dragon": "dragon",
              "puzzle": "puzzle", "castle": "chateau", "combine": "combine",
              "brain": "cerveau", "relax": "detente", "idle": "idle",
              "tycoon": "magnat", "word": "mot", "casual": "casual"},
    "ja-JP": {"merge": "マージ", "magic": "魔法", "dragon": "ドラゴン",
              "puzzle": "パズル", "castle": "城", "combine": "合成",
              "brain": "脳", "relax": "リラックス", "idle": "アイドル",
              "tycoon": "大富豪", "word": "ワード", "casual": "カジュアル"},
    "ko-KR": {"merge": "합체", "magic": "마법", "dragon": "드래곤",
              "puzzle": "퍼즐", "castle": "성", "combine": "조합",
              "brain": "두뇌", "relax": "휴식", "idle": "아이들",
              "tycoon": "재벌", "word": "워드", "casual": "캐주얼"},
}

# Title/subtitle connective words per locale (used to rebuild phrases).
_LOC_CONNECTOR: Dict[str, str] = {
    "de-DE": "und", "fr-FR": "et", "ja-JP": "の", "ko-KR": "의", "en-US": "",
}


@dataclass
class LocalizedMetadata:
    locale: str
    title: str
    subtitle: str
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"locale": self.locale, "title": self.title,
                "subtitle": self.subtitle, "keywords": list(self.keywords)}


class LocalizationEngine:
    """Localizes an AsoPack into the requested locales."""

    def __init__(self, locales: List[str] = None):
        self.locales = locales or ["en-US", "de-DE", "fr-FR", "ja-JP", "ko-KR"]

    def localize(self, pack: AsoPack) -> Dict[str, LocalizedMetadata]:
        out: Dict[str, LocalizedMetadata] = {}
        for loc in self.locales:
            out[loc] = self._one(pack, loc)
        return out

    def _one(self, pack: AsoPack, loc: str) -> LocalizedMetadata:
        table = _LOC_KW.get(loc, {})
        # title: keep brand, translate the trailing keyword after ": "
        title = pack.title
        if ": " in pack.title:
            brand, kw = pack.title.split(": ", 1)
            title = f"{brand}: {table.get(kw.lower(), kw)}"
        # subtitle: translate each token
        sub_tokens = pack.subtitle.split()
        sub = " ".join(table.get(t.lower(), t) for t in sub_tokens)
        # keywords: translate known, keep unknown
        kws = [table.get(k.lower(), k) for k in pack.keywords]
        return LocalizedMetadata(locale=loc, title=title,
                                 subtitle=sub, keywords=kws)


__all__ = ["LocalizationEngine", "LocalizedMetadata", "_LOC_KW"]
