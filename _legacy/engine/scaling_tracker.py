"""Scaling Tracker — 扩量验证追踪器。

追踪 Character Reveal 变体的投放表现，判断可扩展性。

核心问题：
  能否把 Character Reveal 稳定复制成 ROAS > 0.8 的视频系列？

判定规则：
  Valid:   ROAS ≥ 0.8
  Scale:   ROAS ≥ 1.0
  Reject:  ROAS < 0.5 && spent > \$100
  Pending: 数据不足 (< 24h 或 < \$50 spend)
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict


VARIANTS = ["v1_dark_fantasy", "v2_anime", "v3_sci_fi",
            "v4_hyper_realistic", "v5_minimalist"]


class ScalingTracker:
    """Track variant performance and determine scalability."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._log = self._load()

    def _load(self) -> dict:
        if self.log_path.exists():
            return json.loads(self.log_path.read_text(encoding="utf-8"))

        return {
            "experiment": {
                "name": "Character Reveal Scalability Test",
                "started_at": datetime.now().isoformat(),
                "variants": VARIANTS,
                "total_budget": 0,
                "total_spend": 0,
                "total_revenue": 0,
            },
            "variants": {
                v: {
                    "variant": v,
                    "status": "pending",
                    "spend": 0,
                    "revenue": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "installs": 0,
                    "roas": 0,
                    "ctr": 0,
                    "cvr": 0,
                    "started_at": None,
                    "last_updated": None,
                    "verdict": None,
                    "notes": "",
                }
                for v in VARIANTS
            },
            "timeline": [],
        }

    def _save(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(
            json.dumps(self._log, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_variant(self, variant: str, spend: float = 0,
                       revenue: float = 0, impressions: int = 0,
                       clicks: int = 0, installs: int = 0,
                       notes: str = "") -> dict:
        """Update a single variant's performance data.

        Returns:
            {'status', 'verdict', 'roas', 'message'}
        """
        v = self._log["variants"].get(variant)
        if not v:
            raise ValueError(f"Unknown variant: {variant}")

        v["spend"] += spend
        v["revenue"] += revenue
        v["impressions"] += impressions
        v["clicks"] += clicks
        v["installs"] += installs
        v["roas"] = round(v["revenue"] / max(v["spend"], 1), 4)
        v["ctr"] = round(v["clicks"] / max(v["impressions"], 1) * 100, 4)
        v["cvr"] = round(v["installs"] / max(v["clicks"], 1) * 100, 4)
        v["last_updated"] = datetime.now().isoformat()
        if not v["started_at"]:
            v["started_at"] = datetime.now().isoformat()
        if notes:
            v["notes"] = notes

        # Determine verdict
        v["verdict"] = self._judge_variant(v)

        # Update experiment totals
        ex = self._log["experiment"]
        ex["total_spend"] = sum(
            x["spend"] for x in self._log["variants"].values())
        ex["total_revenue"] = sum(
            x["revenue"] for x in self._log["variants"].values())

        # Log timeline entry
        self._log["timeline"].append({
            "timestamp": datetime.now().isoformat(),
            "variant": variant,
            "spend": spend,
            "revenue": revenue,
            "roas": v["roas"],
            "verdict": v["verdict"],
        })

        self._save()
        return self.get_status(variant)

    def get_status(self, variant: str) -> dict:
        """Get current status and verdict for a variant."""
        v = self._log["variants"].get(variant)
        if not v:
            return {"status": "unknown", "variant": variant}

        verdict = v["verdict"]
        status = v.get("status", "running")

        message_map = {
            "scale": f"✅ ROAS {v['roas']:.2f} — SCALE! Increase budget 2x",
            "valid": f"✅ ROAS {v['roas']:.2f} — Valid, maintain budget",
            "reject": f"❌ ROAS {v['roas']:.2f} — REJECT, pause this variant",
            "pending": f"⏳ ROAS {v['roas']:.2f} — Insufficient data, wait 24h",
        }

        return {
            "variant": variant,
            "status": verdict or "pending",
            "roas": v["roas"],
            "spend": v["spend"],
            "revenue": v["revenue"],
            "impressions": v["impressions"],
            "clicks": v["clicks"],
            "installs": v["installs"],
            "ctr": v["ctr"],
            "cvr": v["cvr"],
            "verdict": verdict,
            "message": message_map.get(verdict, "⏳ Pending"),
        }

    def summary(self) -> dict:
        """Get full experiment summary."""
        ex = self._log["experiment"]
        variants_status = [self.get_status(v) for v in VARIANTS]
        valid_count = sum(1 for v in variants_status
                          if v["verdict"] in ("valid", "scale"))
        total_roas = ex["total_revenue"] / max(ex["total_spend"], 1)

        return {
            "experiment": ex["name"],
            "elapsed_hours": self._elapsed_hours(),
            "variants_tested": len(VARIANTS),
            "valid_variants": valid_count,
            "total_spend": round(ex["total_spend"], 2),
            "total_revenue": round(ex["total_revenue"], 2),
            "overall_roas": round(total_roas, 4),
            "verdict": (
                "SCALE" if valid_count >= 3 and total_roas >= 0.8
                else "VALID" if valid_count >= 2
                else "REJECT" if valid_count == 0
                else "PENDING"
            ),
            "variants": variants_status,
        }

    def export_report(self) -> str:
        """Generate human-readable scaling report."""
        s = self.summary()
        lines = [
            f"📊 Character Reveal Scalability Report",
            f"",
            f"  Status: {s['verdict']}",
            f"  Total: ${s['total_spend']:,.0f} spend, ${s['total_revenue']:,.0f} rev, ROAS {s['overall_roas']:.2f}",
            f"  Valid variants: {s['valid_variants']}/{s['variants_tested']}",
            f"  Elapsed: {s['elapsed_hours']:.0f}h",
            f"",
            f"  Variants:",
        ]
        for v in s["variants"]:
            icon = {"scale": "🟢", "valid": "🔵", "reject": "🔴",
                    "pending": "🟡"}.get(v["verdict"] or "pending", "🟡")
            lines.append(
                f"  {icon} {v['variant']}: ROAS {v['roas']:.2f} "
                f"| ${v['spend']:,.0f} spend | {v['message']}"
            )
        return "\n".join(lines)

    # ── Internal ──

    def _judge_variant(self, v: dict) -> Optional[str]:
        """Judge a variant's viability based on data."""
        if v["spend"] < 50 or not v["started_at"]:
            return None  # pending

        # Check if enough time has passed
        started = datetime.fromisoformat(v["started_at"])
        hours_running = (datetime.now() - started).total_seconds() / 3600
        if hours_running < 24 and v["spend"] < 200:
            return None  # pending

        if v["roas"] >= 1.0:
            return "scale"
        elif v["roas"] >= 0.8:
            return "valid"
        elif v["roas"] < 0.5 and v["spend"] > 100:
            return "reject"
        else:
            return None  # pending

    def _elapsed_hours(self) -> float:
        ex = self._log["experiment"]
        if "started_at" not in ex:
            return 0
        try:
            start = datetime.fromisoformat(ex["started_at"])
            return (datetime.now() - start).total_seconds() / 3600
        except Exception:
            return 0
