"""Creative Performance Builder — FB/Adjust 数据归因闭环.

核心职责：
  读取已合并的 FBcreative_id ↔ Adjust revenue 数据，
  输出统一的 CreativePerformance 记录，
  打通 Creative Factory 的最后 20%。

数据源：
  output/video_intelligence/p04/creative_mapping_adjust_merged_v2.csv
  (1315 rows, 474 with adjust_revenue > 0)

输出格式：
  {
    creative_id, spend, revenue, installs,
    roas_d1, roas_d7, roas_d30,
    ctr, cvr, cpi, platform, country, campaign,
    is_winner, is_valid_sample, confidence
  }
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
from typing import Any, Optional


MERGED_CSV_PATH = Path("output/video_intelligence/p04/creative_mapping_adjust_merged_v2.csv")
MERGED_CSV_V2B = Path("output/video_intelligence/p04/creative_mapping_v2.csv")
EFFECTIVE_SPEND = 100.0
EFFECTIVE_INSTALLS = 30
MIN_REVENUE = 0.01


@dataclass
class CreativePerformance:
    """统一格式：FBcreative_id → Adjust revenue 归因结果."""
    creative_id: str = ""
    creative_name: str = ""

    # 渠道信息
    platform: str = ""  # ios / android
    country: str = "Global"
    campaign: str = ""
    campaign_id: str = ""
    adset: str = ""
    account: str = ""

    # FB 数据
    fb_spend: float = 0.0
    fb_installs: int = 0

    # Adjust 数据（可靠）
    adjust_cost: float = 0.0
    adjust_revenue: float = 0.0
    adjust_installs: int = 0

    # 统一计算
    spend: float = 0.0       # 优先 fb_spend
    installs: int = 0       # 优先 adjust_installs
    revenue: float = 0.0    # adjust_revenue
    roas: float = 0.0

    # 衍生指标
    ctr: float = 0.0
    cvr: float = 0.0
    cpi: float = 0.0

    # 资产路径
    video_path: str = ""
    image_path: str = ""

    # 样本质量
    is_valid_sample: bool = False
    confidence: str = "low"  # high / medium / low
    is_winner: bool = False
    decision: str = "observe"  # scale / observe / stop
    suggested_action: str = ""

    # 元数据
    match_method: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("fb_spend")
        d.pop("fb_installs")
        d.pop("adjust_cost")
        return {k: v for k, v in d.items() if v != "" and v != 0.0 or k in ("installs", "revenue", "roas")}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class CreativePerformanceBuilder:
    """从 merged CSV 读取 + 标准化 + 输出 CreativePerformance 列表."""

    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path else MERGED_CSV_PATH

    def load(self) -> list[CreativePerformance]:
        if not self.csv_path.exists():
            return []
        with self.csv_path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        return [self._normalize(row) for row in rows if self._is_meaningful(row)]

    def _is_meaningful(self, row: dict[str, str]) -> bool:
        spend = float(row.get("fb_spend") or 0)
        adj_rev = float(row.get("adjust_revenue") or 0)
        adj_inst = int(float(row.get("adjust_installs") or 0))
        return spend > 0 or adj_rev > 0 or adj_inst > 0

    def _normalize(self, row: dict[str, str]) -> CreativePerformance:
        fb_spend = float(row.get("fb_spend") or 0)
        adjust_cost = float(row.get("adjust_cost") or 0)
        adjust_revenue = float(row.get("adjust_revenue") or 0)
        adjust_installs = int(float(row.get("adjust_installs") or 0))

        ad_name = row.get("ad_name", "")
        platform = self._detect_platform(ad_name)
        country = self._detect_country(ad_name)

        spend = fb_spend if fb_spend > 0 else adjust_cost
        roas = round(adjust_revenue / spend, 4) if spend > 0 else 0.0
        cpi = round(spend / adjust_installs, 4) if adjust_installs > 0 else 0.0

        is_valid = spend >= EFFECTIVE_SPEND or adjust_installs >= EFFECTIVE_INSTALLS
        is_winner = is_valid and roas >= 1.0
        confidence = self._confidence(spend, adjust_installs, adjust_revenue, is_valid)
        decision, action = self._decision_and_action(roas, spend, is_valid, is_winner, confidence)

        return CreativePerformance(
            creative_id=str(row.get("creative_id") or "").strip(),
            creative_name=str(row.get("creative_name") or "").strip(),
            platform=platform,
            country=country,
            campaign=str(row.get("campaign_name") or "").strip(),
            adset=str(row.get("adset_name") or "").strip(),
            account=str(row.get("account_name") or "").strip(),
            fb_spend=fb_spend,
            fb_installs=int(float(row.get("fb_installs") or 0)),
            adjust_cost=adjust_cost,
            adjust_revenue=adjust_revenue,
            adjust_installs=adjust_installs,
            spend=round(spend, 2),
            installs=adjust_installs,
            revenue=round(adjust_revenue, 2),
            roas=roas,
            cpi=cpi,
            video_path=row.get("eagle_filename") or "",
            match_method=row.get("match_method") or "",
            is_valid_sample=is_valid,
            confidence=confidence,
            is_winner=is_winner,
            decision=decision,
            suggested_action=action,
        )

    def _detect_platform(self, ad_name: str) -> str:
        name = ad_name.upper()
        if "IOS" in name or "IPHONE" in name:
            return "ios"
        if "AND" in name or "ANDROID" in name or "GOOGLE" in name:
            return "android"
        return "unknown"

    def _detect_country(self, ad_name: str) -> str:
        if "-TW-" in ad_name:
            return "TW"
        if "-HK-" in ad_name:
            return "HK"
        if "-JP-" in ad_name:
            return "JP"
        if "-US-" in ad_name or "-US-" in ad_name.upper():
            return "US"
        if "-GB-" in ad_name:
            return "GB"
        if "-DE-" in ad_name:
            return "DE"
        return "Global"

    def _confidence(self, spend: float, installs: int, revenue: float, is_valid: bool) -> str:
        if not is_valid:
            return "low"
        if spend >= 500 and revenue >= 100:
            return "high"
        if spend >= 200 and revenue >= 50:
            return "medium"
        return "low"

    def _decision_and_action(self, roas: float, spend: float, is_valid: bool, is_winner: bool, confidence: str) -> tuple[str, str]:
        if not is_valid:
            return "observe", "继续小额验证，积累7日累计样本"
        if confidence == "low":
            return "observe", "低可信度，继续观察"
        if is_winner and confidence == "high":
            return "scale", "有效样本+高ROAS+高可信度，建议加量"
        if roas >= 1.0:
            return "scale_candidate", "ROAS过线，建议加量候选复核"
        if roas < 0.35 and spend >= 150:
            return "stop", "持续低回收且花费较高，建议降权或关闭"
        if roas < 0.5 and spend >= 100:
            return "reduce", "低回收，建议降低预算"
        return "observe", "ROI未过线，继续观察后续回收"

    def get_winners(self) -> list[CreativePerformance]:
        return [p for p in self.load() if p.is_winner]

    def get_top_by_spend(self, limit: int = 20) -> list[CreativePerformance]:
        all_ = self.load()
        all_.sort(key=lambda p: p.spend, reverse=True)
        return all_[:limit]

    def get_by_platform(self, platform: str) -> list[CreativePerformance]:
        return [p for p in self.load() if p.platform == platform]

    def summary(self) -> dict[str, Any]:
        all_ = self.load()
        winners = [p for p in all_ if p.is_winner]
        valid = [p for p in all_ if p.is_valid_sample]
        ios = [p for p in all_ if p.platform == "ios"]
        android = [p for p in all_ if p.platform == "android"]
        total_spend = sum(p.spend for p in all_)
        total_revenue = sum(p.revenue for p in all_)
        return {
            "total_creatives": len(all_),
            "with_revenue": len([p for p in all_ if p.revenue > 0]),
            "winners": len(winners),
            "valid_samples": len(valid),
            "ios_creatives": len(ios),
            "android_creatives": len(android),
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "blend_roas": round(total_revenue / total_spend, 4) if total_spend > 0 else 0.0,
            "platform_breakdown": {
                "ios": {"creatives": len(ios), "spend": round(sum(p.spend for p in ios), 2), "revenue": round(sum(p.revenue for p in ios), 2)},
                "android": {"creatives": len(android), "spend": round(sum(p.spend for p in android), 2), "revenue": round(sum(p.revenue for p in android), 2)},
            },
        }

    def save(self, output_dir: Path | None = None) -> dict[str, Path]:
        all_ = self.load()
        if output_dir is None:
            output_dir = Path("output/creative_factory")
        output_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        suffix = today.replace("-", "")

        json_path = output_dir / f"creative_performance_{suffix}.json"
        csv_path = output_dir / f"creative_performance_{suffix}.csv"
        winners_path = output_dir / f"winners_{suffix}.json"
        summary_path = output_dir / f"summary_{suffix}.json"

        json_path.write_text(json.dumps([p.to_dict() for p in all_], ensure_ascii=False, indent=2), encoding="utf-8")

        if all_:
            fieldnames = list(all_[0].to_dict().keys())
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for p in all_:
                    writer.writerow(p.to_dict())

        winners_path.write_text(json.dumps([p.to_dict() for p in self.get_winners()], ensure_ascii=False, indent=2), encoding="utf-8")
        summary_path.write_text(json.dumps(self.summary(), ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "all_performance": json_path,
            "all_performance_csv": csv_path,
            "winners": winners_path,
            "summary": summary_path,
        }
