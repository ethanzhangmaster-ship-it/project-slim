"""P1.4 — 从真实 MAX 报表 + catalog 生成 data/game_registry.json。

设计纪律：
- 注册表只存「映射」与「secret 引用」，绝不内联任何密钥。
  token 以 secret_ref 字符串表示（如 "live_accounts:accounts:ACCT_2:report_key"），
  真实解析仍由各源 load_adjust_config / load_meta_config 在运行时读取 credentials。
- canonical game_id 取 MAX application 名（RealFleetBridge 直接产出的 id），
  这样 MaxRealitySource 无需 app_map 即可命中；catalog 仅补充 package/genre。
- 运行：python scripts/build_game_registry.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = sorted(ROOT.glob("data/ACCT_*_report.json"))
CATALOG = ROOT / "data/catalog.json"
OUT = ROOT / "data/game_registry.json"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s


def _load_catalog() -> dict:
    if not CATALOG.exists():
        return {}
    games = json.loads(CATALOG.read_text(encoding="utf-8"))
    games = games if isinstance(games, list) else games.get("games") or []
    by_disp = {}
    for g in games:
        disp = (g.get("display_name") or g.get("game_id") or "").strip().lower()
        by_disp[disp] = g
        by_disp[g.get("game_id", "").lower()] = g
    return by_disp


def main() -> None:
    catalog = _load_catalog()
    entries: dict = {}

    for rp in REPORTS:
        acct = rp.stem.replace("_report", "")  # ACCT_1 / ACCT_TEST ...
        data = json.loads(rp.read_text(encoding="utf-8"))
        apps = sorted({r.get("application") for r in data.get("rows", []) if r.get("application")})
        for app in apps:
            gid = app  # canonical id = MAX application 名
            cat = catalog.get(app.strip().lower()) or catalog.get(_slug(app))
            pkg = cat.get("package_name", "") if cat else ""
            genre = cat.get("genre", "") if cat else ""
            entry = entries.setdefault(
                gid,
                {
                    "game_id": gid,
                    "display_name": app,
                    "package_name": pkg,
                    "genre": genre,
                    "platform": "unknown",
                    "max_apps": [],
                    "adjust_app_token_ref": "",
                    "meta_campaign_ids": [],
                },
            )
            if acct not in entry["max_apps"]:
                entry["max_apps"].append(acct)
            if not entry["package_name"] and pkg:
                entry["package_name"] = pkg
            if not entry["genre"] and genre:
                entry["genre"] = genre

    out = {
        "_note": "P1.4 真实游戏注册表。token 仅以 secret_ref 字符串保存，绝不内联密钥；"
        "真实解析由各源运行时从 credentials/live_accounts.json 读取。",
        "games": list(entries.values()),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} with {len(out['games'])} games")


if __name__ == "__main__":
    main()
