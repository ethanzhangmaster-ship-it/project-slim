from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.new_product_stage import NewProductStageBuilder, project_label
from market_ops.pipeline import DataRepository


FEATURE_KEYWORDS = {
    "女性向": ("witch", "vampire", "mermaid", "queen", "princess", "girl", "female", "女", "美人鱼", "女巫"),
    "危机Hook": ("crisis", "danger", "rescue", "save", "broken", "collapse", "危机", "拯救", "破损", "崩塌"),
    "Merge玩法": ("merge", "合成"),
    "Survival": ("survival", "survive", "生存"),
    "Drama": ("drama", "story", "romance", "剧情"),
    "Build": ("build", "home", "house", "room", "building", "建造", "房屋"),
}


@dataclass(slots=True)
class TransferLearningResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class TransferLearningBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> TransferLearningResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"transfer_learning_{suffix}.md"
        json_path = output_dir / f"transfer_learning_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return TransferLearningResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        stage_payload = NewProductStageBuilder(self._settings).build_payload(report_date)
        profiles = self._project_profiles_from_cache(report_date)
        if not profiles:
            rows = self._repo.load_adjust_revenue_breakdown(report_date - timedelta(days=70), report_date)
            profiles = self._project_profiles(rows)
        new_projects = [
            item["project"]
            for item in stage_payload.get("items") or []
            if item.get("stage") in {"Discovery", "Validation"}
        ]
        items = [self._transfer_item(project, profiles, stage_payload) for project in new_projects]
        return {
            "report_date": report_date.isoformat(),
            "passed": True,
            "summary": {"new_project_count": len(items)},
            "items": items,
        }

    def _project_profiles_from_cache(self, report_date: date) -> dict[str, dict[str, Any]]:
        path = self._settings.active_output_dir / f"adjust_creative_analysis_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        rows = payload.get("all_items") or payload.get("top_effective_creatives") or []
        profiles: dict[str, dict[str, Any]] = {}
        for row in rows:
            project = project_label(str(row.get("project") or ""))
            if not project:
                continue
            text = " ".join(
                str(row.get(key) or "")
                for key in ("project", "campaign", "adgroup", "creative_name", "source_name")
            ).lower()
            profile = profiles.setdefault(project, {"features": set(), "spend": 0.0, "revenue": 0.0})
            profile["spend"] += float(row.get("spend") or 0.0)
            profile["revenue"] += float(row.get("revenue") or 0.0)
            for feature, keywords in FEATURE_KEYWORDS.items():
                if any(keyword.lower() in text for keyword in keywords):
                    profile["features"].add(feature)
        for project, profile in profiles.items():
            profile["features"].update(infer_features_from_name(project))
        return profiles

    @staticmethod
    def _project_profiles(rows: list[Any]) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}
        for row in rows:
            project = project_label(row.game)
            if not project:
                continue
            text = " ".join(
                str(getattr(row, attr, "") or "")
                for attr in ("game", "campaign", "adgroup", "creative_name", "source_name")
            ).lower()
            profile = profiles.setdefault(project, {"features": set(), "spend": 0.0, "revenue": 0.0})
            profile["spend"] += float(getattr(row, "cost", 0.0) or 0.0)
            profile["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            for feature, keywords in FEATURE_KEYWORDS.items():
                if any(keyword.lower() in text for keyword in keywords):
                    profile["features"].add(feature)
        for project, profile in profiles.items():
            fallback = infer_features_from_name(project)
            profile["features"].update(fallback)
        return profiles

    @staticmethod
    def _transfer_item(project: str, profiles: dict[str, dict[str, Any]], stage_payload: dict[str, Any]) -> dict[str, Any]:
        project_features = set(profiles.get(project, {}).get("features") or infer_features_from_name(project))
        scored: list[dict[str, Any]] = []
        for candidate, profile in profiles.items():
            if candidate == project:
                continue
            features = set(profile.get("features") or [])
            shared = sorted(project_features & features)
            if not shared:
                continue
            spend = float(profile.get("spend") or 0.0)
            revenue = float(profile.get("revenue") or 0.0)
            score = len(shared) + min(spend / 10000.0, 1.0) + (0.5 if spend and revenue / spend >= 1.0 else 0.0)
            scored.append(
                {
                    "project": candidate,
                    "similarity_score": round(score, 4),
                    "shared_features": shared,
                    "historical_roi": round(revenue / spend, 4) if spend else 0.0,
                    "historical_spend": round(spend, 2),
                }
            )
        scored.sort(key=lambda item: (item["similarity_score"], item["historical_spend"]), reverse=True)
        patterns = recommended_patterns(project_features)
        return {
            "new_project": project,
            "stage": next((item.get("stage") for item in stage_payload.get("items") or [] if item.get("project") == project), "Unknown"),
            "similar_projects": scored[:5],
            "shared_features": sorted(project_features),
            "recommended_creative_patterns": patterns,
            "rule": "迁移学习只提供探索方向，不用老项目ROI直接否决新品。",
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        lines = [
            f"# 新品迁移学习建议 | {payload['report_date']}",
            "",
            "- 说明：用老项目帮助新品找方向，但不让老品 ROI 直接压制新品。",
            "",
        ]
        for item in payload["items"]:
            similar = "；".join(
                f"{candidate['project']}({','.join(candidate['shared_features'])})"
                for candidate in item["similar_projects"][:3]
            ) or "暂无"
            lines.extend(
                [
                    f"## {item['new_project']} | {item['stage']}",
                    f"- 共享特征：{'、'.join(item['shared_features']) or '待识别'}",
                    f"- 相似项目：{similar}",
                    f"- 推荐模式：{'、'.join(item['recommended_creative_patterns']) or '先做Hook探索'}",
                    "",
                ]
            )
        if not payload["items"]:
            lines.append("- 暂无 Discovery / Validation 项目。")
        return "\n".join(lines)


def infer_features_from_name(value: str) -> set[str]:
    text = str(value or "").lower()
    features: set[str] = set()
    for feature, keywords in FEATURE_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            features.add(feature)
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if match and not features:
        features.add("待识别品类")
    return features


def recommended_patterns(features: set[str]) -> list[str]:
    patterns: list[str] = []
    if "危机Hook" in features or "女性向" in features:
        patterns.extend(["资源不足", "房屋破损", "女主危机"])
    if "Merge玩法" in features:
        patterns.extend(["合成失败惩罚", "目标物展示", "资源卡点"])
    if "Survival" in features:
        patterns.extend(["倒计时压力", "资源短缺", "环境威胁"])
    if "Drama" in features:
        patterns.extend(["反转开场", "强情绪字幕", "选择冲突"])
    return list(dict.fromkeys(patterns))
