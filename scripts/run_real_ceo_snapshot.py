"""P1.5 — 首个真实经营闭环快照生成器。

把四个真实源（MAX 报表 / Meta 买量 / Adjust KPI / Game Registry）接入
GrowthRealityHub，跑首个真·CEO 经营快照，落盘到 data/reality/<as_of>_snapshot.jsonl
（每行一个 GrowthRealitySnapshot.to_dict()），并输出中文 CEO 摘要。

纪律：
- 各源 production 模式；MAX 读本地真实报表（零凭据），Meta/Adjust 缺凭证时
  优雅降级（返回 {}，不报错），real_api_called 仅在有真实数据的源置 True。
- 不臆造：ROAS 仅在收入与花费均真实时由 normalizer 计算（见 RealityNormalizer）。
- 纯 Python + JSONL，Lean 无框架。

用法：
    python scripts/run_real_ceo_snapshot.py [--as-of 2026-07-29] [--out-dir data/reality]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.production_sources.adjust_source import AdjustRealitySource
from src.growth_reality.production_sources.max_source import MaxRealitySource
from src.growth_reality.production_sources.meta_source import MetaRealitySource
from src.growth_reality.registry import GameRegistry, RegistryRealitySource


def _discover_accounts() -> List[str]:
    """发现所有真实 MAX 报表账户（与注册表生成口径一致）。"""
    return sorted(
        p.stem.replace("_report", "")
        for p in Path("data").glob("ACCT_*_report.json")
    )


def build_sources(registry: GameRegistry, as_of: str) -> List:
    """构建四个真实源（production 模式，缺凭证优雅降级）。"""
    sources = []
    # 1) MAX：真实本地报表（零凭据，必然有数据）
    accounts = _discover_accounts()
    sources.append(MaxRealitySource(accounts=accounts, mode="production", registry=registry, as_of=as_of))
    # 2) Registry：真实产品元数据（替代假 catalog）
    sources.append(RegistryRealitySource(registry=registry))
    # 3) Meta：买量花费（缺 token 时返回 {}，不阻断）
    try:
        from operation.providers.live.meta.meta_client import load_meta_config
        mc = load_meta_config() or {}
        meta = MetaRealitySource(
            access_token=mc.get("access_token", ""),
            ad_account_id=mc.get("ad_account_id", ""),
            mode="production", registry=registry, as_of=as_of,
        )
    except Exception:
        meta = MetaRealitySource(mode="production", registry=registry, as_of=as_of)
    sources.append(meta)
    # 4) Adjust：KPI（缺 token 时返回 {}，不阻断）
    sources.append(AdjustRealitySource(mode="production", registry=registry, as_of=as_of))
    return sources


def write_snapshot_jsonl(company, out_dir: str, as_of: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{as_of}_snapshot.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for gid, snap in company.per_game.items():
            f.write(json.dumps(snap.to_dict(), ensure_ascii=False) + "\n")
    return path


def ceo_summary(company) -> str:
    lines = [f"# CEO 真实经营快照 — {company.as_of}", ""]
    lines.append(f"- 覆盖游戏数：{len(company.per_game)}")
    lines.append(f"- 平均数据置信度：{company.avg_confidence:.0%}")
    lines.append("")
    lines.append("| 游戏 | 日收入 | 买量花费 | ROAS | 真实置信 | 建议 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for gid, snap in company.per_game.items():
        rev = snap.revenue.daily_revenue if snap.revenue else 0.0
        spend = snap.acquisition.spend if snap.acquisition else 0.0
        roas = snap.acquisition.roas if (snap.acquisition and snap.attribution) else 0.0
        advice = _advice(roas, snap.real_confidence)
        lines.append(
            f"| {gid} | {rev:,.0f} | {spend:,.0f} | {roas:.2f} | {snap.real_confidence:.0%} | {advice} |"
        )
    return "\n".join(lines)


def _advice(roas: float, real_conf: float) -> str:
    if real_conf < 0.4:
        return "数据不足→观察"
    if roas >= 1.2:
        return "INCREASE_BUDGET"
    if roas < 0.8:
        return "STOP_LOSS"
    return "HOLD"


def run(as_of: Optional[str] = None, out_dir: str = "data/reality") -> Path:
    as_of = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    registry = GameRegistry()
    sources = build_sources(registry, as_of)
    hub = GrowthRealityHub(sources=sources)
    games = registry.all_game_ids()
    company = hub.refresh(games, as_of, persist=False)
    path = write_snapshot_jsonl(company, out_dir, as_of)
    print(ceo_summary(company))
    print(f"\n快照已写入：{path}  ({len(company.per_game)} 行)")
    print(f"real_api_called={hub.last_real_api_called}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--out-dir", default="data/reality")
    args = ap.parse_args()
    run(args.as_of, args.out_dir)


if __name__ == "__main__":
    main()
