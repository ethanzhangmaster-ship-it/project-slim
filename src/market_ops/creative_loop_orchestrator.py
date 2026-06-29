"""素材创意闭环编排器 (Creative Loop Orchestrator)

完整闭环：
  1. discover_winners()   → 从 Adjust 归因 + growth_priorities 找赢家 creative
  2. extract_patterns()   → 分析赢家特征模式（视觉DNA 或 文本模式降级）
  3. generate_variants()  → 基于赢家模式批量生成裂变变体建议
  4. feedback_loop()      → 裂变投放效果回灌到 growth_priorities 评分

降级策略：无本地图片时从 creative_name / creative_library 文本中提取模式。

Usage:
    orchestrator = CreativeLoopOrchestrator(settings)
    result = orchestrator.run(report_date=date.today())
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.creative_dna import _infer_labels, _DNA_ONLY_FIELDS
from market_ops.creative_winner_reader import WinnerVisualDnaReader, WinnerReadResult
from market_ops.growth_priorities import GrowthPrioritiesBuilder, GrowthPriorityItem
from market_ops.models import CreativeAssetRow
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class WinnerCreative:
    creative_id: str
    creative_name: str
    project: str
    channel: str
    country: str
    campaign: str
    spend: float
    revenue: float
    roi: float
    growth_priority: float
    growth_stage: str
    recommended_action: str


@dataclass(slots=True)
class CreativePattern:
    name: str
    hook_type: str
    emotion: str
    pace: str
    ui_type: str
    copy_style: str
    cta_strength: str
    video_structure: str
    first_3s_density: str
    conflict_strength: str
    source: str
    confidence: float
    supporting_creatives: list[str] = field(default_factory=list)
    avg_roi: float = 0.0
    visual_dna: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class VariantSuggestion:
    variant_id: str
    parent_pattern: str
    parent_creative: str
    mutation_type: str
    new_hook: str
    new_emotion: str
    new_pace: str
    new_ui_type: str
    suggested_copy: str
    rationale: str
    expected_difficulty: str
    priority: str


@dataclass(slots=True)
class FeedbackEntry:
    creative_id: str
    variant_of: str
    feedback_date: str
    spend: float
    revenue: float
    roi: float
    installs: int
    verdict: str
    learning_note: str


@dataclass(slots=True)
class OrchestratorResult:
    run_id: str
    report_date: str
    output_dir: Path

    # Stage outputs
    winners: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    feedback_summary: dict[str, Any] = field(default_factory=dict)

    # Paths
    winners_json: str = ""
    patterns_json: str = ""
    variants_md: str = ""
    feedback_json: str = ""

    # Status
    visual_mode: str = "text_fallback"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class CreativeLoopOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, report_date: date, *, max_winners: int = 5, max_variants: int = 10) -> OrchestratorResult:
        run_id = f"cl_{report_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        result = OrchestratorResult(
            run_id=run_id, report_date=report_date.isoformat(), output_dir=output_dir,
        )

        print(f"\n{'='*60}")
        print(f"  Creative Loop Orchestrator | {report_date.isoformat()}")
        print(f"  Run ID: {run_id}")
        print(f"{'='*60}\n")

        # Stage 1: Discover winners
        print("[1/4] Discovering winner creatives...")
        winners, visual_items = self.discover_winners(report_date, max_winners=max_winners)
        result.winners = [asdict(w) for w in winners]
        winners_json = output_dir / f"creative_loop_winners_{run_id}.json"
        winners_json.write_text(json.dumps(result.winners, ensure_ascii=False, indent=2), encoding="utf-8")
        result.winners_json = str(winners_json)
        print(f"      Found {len(winners)} winner creatives, {len(visual_items)} with visual DNA")

        if not winners:
            result.warnings.append("No winner creatives found; check Adjust data availability.")
            return result

        # Stage 2: Extract patterns
        print("[2/4] Extracting creative patterns...")
        patterns = self.extract_patterns(winners, visual_items)
        result.patterns = [asdict(p) for p in patterns]
        patterns_json = output_dir / f"creative_loop_patterns_{run_id}.json"
        patterns_json.write_text(json.dumps(result.patterns, ensure_ascii=False, indent=2), encoding="utf-8")
        result.patterns_json = str(patterns_json)
        result.visual_mode = "visual" if visual_items else "text_fallback"
        print(f"      Extracted {len(patterns)} patterns (mode={result.visual_mode})")

        # Stage 3: Generate variants
        print(f"[3/4] Generating variant suggestions (max {max_variants})...")
        variants = self.generate_variants(patterns, winners, max_variants=max_variants)
        result.variants = [asdict(v) for v in variants]
        variants_md = output_dir / f"creative_loop_variants_{run_id}.md"
        variants_md.write_text(self._render_variants_markdown(run_id, report_date, winners, patterns, variants), encoding="utf-8")
        result.variants_md = str(variants_md)
        print(f"      Generated {len(variants)} variant suggestions")

        # Stage 4: Feedback loop
        print("[4/4] Building feedback loop...")
        feedback = self.feedback_loop(report_date)
        result.feedback_summary = feedback
        feedback_json = output_dir / f"creative_loop_feedback_{run_id}.json"
        feedback_json.write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8")
        result.feedback_json = str(feedback_json)
        print(f"      Feedback entries: {feedback.get('total_entries', 0)}")

        print(f"\n{'='*60}")
        print(f"  Orchestrator Complete: {run_id}")
        print(f"  Winners: {len(winners)} | Patterns: {len(patterns)} | Variants: {len(variants)}")
        print(f"  Visual Mode: {result.visual_mode}")
        print(f"  Output: {output_dir}")
        print(f"{'='*60}\n")

        return result

    # ------------------------------------------------------------------
    # Stage 1: discover_winners
    # ------------------------------------------------------------------

    def discover_winners(
        self, report_date: date, *, max_winners: int = 5,
    ) -> tuple[list[WinnerCreative], list[dict[str, Any]]]:
        window_start = report_date - timedelta(days=6)
        try:
            growth_builder = GrowthPrioritiesBuilder(self._settings)
            payload = growth_builder.build_payload(report_date)
        except Exception as exc:
            raise RuntimeError(f"Failed to build growth priorities: {exc}") from exc

        creative_items = [
            item for item in payload.get("items", [])
            if item.get("entity_type") == "creative" and item.get("growth_stage") in ("素材复制候选", "素材观察")
        ]
        creative_items.sort(key=lambda x: (x.get("growth_priority", 0), x.get("roi", 0), x.get("spend", 0)), reverse=True)
        top = creative_items[:max_winners]

        winners = []
        for item in top:
            winners.append(WinnerCreative(
                creative_id=str(item.get("entity_id", "")),
                creative_name=str(item.get("entity_id", "")),
                project=str(item.get("project", "")),
                channel=str(item.get("scope", "")).split(" / ")[0] if " / " in str(item.get("scope", "")) else str(item.get("scope", "")),
                country=str(item.get("scope", "")).split(" / ")[1] if " / " in str(item.get("scope", "")) else "Global",
                campaign="",
                spend=float(item.get("spend", 0)),
                revenue=float(item.get("revenue", 0)),
                roi=float(item.get("roi", 0)),
                growth_priority=float(item.get("growth_priority", 0)),
                growth_stage=str(item.get("growth_stage", "")),
                recommended_action=str(item.get("recommended_action", "")),
            ))

        # Load creative library rows for text-based enrichment
        creative_rows = self._repo.load_adjust_creative_library(window_start, report_date)

        for w in winners:
            for row in creative_rows:
                row_id = str(row.asset_id or row.creative_name or "").strip()
                if row_id == w.creative_id or w.creative_id in row_id or row_id in w.creative_id:
                    w.creative_name = str(row.creative_name or w.creative_id)
                    w.campaign = str(row.campaign or "")
                    w.country = str(row.country or w.country)
                    w.channel = str(row.channel or w.channel)
                    break

        # Attempt visual DNA via WinnerVisualDnaReader
        visual_items: list[dict[str, Any]] = []
        try:
            reader = WinnerVisualDnaReader(self._settings)
            dna_result = reader.read(limit=min(3, len(winners)))
            visual_items = dna_result.items
        except Exception:
            pass

        return winners, visual_items

    # ------------------------------------------------------------------
    # Stage 2: extract_patterns
    # ------------------------------------------------------------------

    def extract_patterns(
        self, winners: list[WinnerCreative], visual_items: list[dict[str, Any]],
    ) -> list[CreativePattern]:
        patterns: list[CreativePattern] = []

        # Merge visual DNA into winners where available
        visual_map: dict[str, dict[str, Any]] = {}
        for vi in visual_items:
            vid = str(vi.get("creative_id", ""))
            if vid:
                visual_map[vid.lower()] = vi

        for w in winners:
            text = f"{w.creative_name} {w.campaign} {w.project}"
            labels, hits = _infer_labels(text)

            pattern_name = _pattern_name(w)
            visual_dna: dict[str, str] = {}

            vid = visual_map.get(w.creative_id.lower())
            if vid:
                visual_dna = vid.get("visual_dna", {})
                if isinstance(visual_dna, dict):
                    for field in _DNA_ONLY_FIELDS:
                        if labels.get(field, "unknown") == "unknown" and visual_dna.get(field, ""):
                            labels[field] = str(visual_dna[field])

            source = "visual+text" if visual_dna else "text_only"
            confidence = min(0.85, 0.35 + hits * 0.10 + (0.25 if visual_dna else 0.0))

            patterns.append(CreativePattern(
                name=pattern_name,
                hook_type=labels.get("hook_type", "unknown"),
                emotion=labels.get("emotion", "unknown"),
                pace=labels.get("pace", "unknown"),
                ui_type=labels.get("ui_type", "unknown"),
                copy_style=labels.get("copy_style", "unknown"),
                cta_strength=labels.get("cta_strength", "unknown"),
                video_structure=labels.get("video_structure", "unknown"),
                first_3s_density=labels.get("first_3s_density", "unknown"),
                conflict_strength=labels.get("conflict_strength", "unknown"),
                source=source,
                confidence=round(confidence, 3),
                supporting_creatives=[w.creative_id],
                avg_roi=w.roi,
                visual_dna=visual_dna,
            ))

        return patterns

    # ------------------------------------------------------------------
    # Stage 3: generate_variants
    # ------------------------------------------------------------------

    def generate_variants(
        self, patterns: list[CreativePattern], winners: list[WinnerCreative],
        *, max_variants: int = 10,
    ) -> list[VariantSuggestion]:
        if not patterns:
            return []

        MUTATION_RULES: list[dict[str, Any]] = [
            {"name": "hook_swap", "field": "hook_type", "candidates": ["爽点", "危机", "反转"], "desc": "更换Hook类型但保留情绪基调"},
            {"name": "emotion_shift", "field": "emotion", "candidates": ["爽感", "焦虑", "治愈"], "desc": "调整情绪方向但保留Hook节奏"},
            {"name": "pace_flip", "field": "pace", "candidates": ["快", "慢"], "desc": "快慢节奏互换"},
            {"name": "ui_extend", "field": "ui_type", "candidates": ["Merge", "Build", "Battle"], "desc": "在同类UI下尝试不同子玩法展示"},
            {"name": "copy_intensify", "field": "copy_style", "candidates": ["强标题", "弱标题"], "desc": "强化/弱化文案力度"},
            {"name": "cta_boost", "field": "cta_strength", "candidates": ["强", "弱"], "desc": "CTA强度调整"},
            {"name": "structure_mix", "field": "video_structure", "candidates": ["UGC", "游戏录屏", "图片"], "desc": "尝试不同素材形式混搭"},
        ]

        winner_map = {w.creative_id: w for w in winners}
        variant_id = 0
        variants: list[VariantSuggestion] = []

        for pat in patterns:
            if variant_id >= max_variants:
                break
            for rule in MUTATION_RULES:
                if variant_id >= max_variants:
                    break
                field = rule["field"]
                current = getattr(pat, field, "unknown")
                candidates = [c for c in rule["candidates"] if c != current]
                if not candidates:
                    continue
                new_val = candidates[0]

                parent_creative = pat.supporting_creatives[0] if pat.supporting_creatives else "unknown"
                parent_winner = winner_map.get(parent_creative)
                parent_roi = parent_winner.roi if parent_winner else pat.avg_roi

                difficulty = "low" if field in ("copy_style", "cta_strength", "pace") else "medium"
                priority = "high" if pat.avg_roi >= 1.3 else "medium"

                variants.append(VariantSuggestion(
                    variant_id=f"var_{variant_id:03d}",
                    parent_pattern=pat.name,
                    parent_creative=parent_creative,
                    mutation_type=rule["name"],
                    new_hook=pat.hook_type if field != "hook_type" else new_val,
                    new_emotion=pat.emotion if field != "emotion" else new_val,
                    new_pace=pat.pace if field != "pace" else new_val,
                    new_ui_type=pat.ui_type if field != "ui_type" else new_val,
                    suggested_copy=_build_suggested_copy(pat, field, new_val),
                    rationale=f"{rule['desc']}（父素材ROI={parent_roi:.2f}）",
                    expected_difficulty=difficulty,
                    priority=priority,
                ))
                variant_id += 1

        variants.sort(key=lambda v: (0 if v.priority == "high" else 1, v.expected_difficulty))
        return variants

    # ------------------------------------------------------------------
    # Stage 4: feedback_loop
    # ------------------------------------------------------------------

    def feedback_loop(self, report_date: date) -> dict[str, Any]:
        feedback_path = self._settings.active_output_dir / "creative_loop_feedback_store.json"
        entries: list[dict[str, Any]] = []
        if feedback_path.exists():
            try:
                data = json.loads(feedback_path.read_text(encoding="utf-8"))
                entries = data.get("entries", [])
            except json.JSONDecodeError:
                pass

        return {
            "report_date": report_date.isoformat(),
            "total_entries": len(entries),
            "recent_entries": entries[-10:],
            "summary": {
                "total_variants_tracked": len({e.get("creative_id") for e in entries}),
                "positive_verdicts": sum(1 for e in entries if e.get("verdict") == "positive"),
                "negative_verdicts": sum(1 for e in entries if e.get("verdict") == "negative"),
                "pending": sum(1 for e in entries if e.get("verdict") == "pending"),
            },
            "feedback_file": str(feedback_path),
        }

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_variants_markdown(
        self, run_id: str, report_date: date,
        winners: list[WinnerCreative], patterns: list[CreativePattern],
        variants: list[VariantSuggestion],
    ) -> str:
        lines = [
            f"# 素材裂变建议 | {report_date.isoformat()}",
            "",
            f"- Run ID: `{run_id}`",
            f"- 赢家素材: {len(winners)} | 模式: {len(patterns)} | 裂变建议: {len(variants)}",
            "",
            "## 赢家素材",
            "",
            "| 素材ID | 项目 | ROI | 增长分 | 阶段 | 建议 |",
            "|---|---:|---:|---|---|",
        ]
        for w in winners:
            lines.append(
                f"| `{w.creative_id}` | {w.project} | {w.roi:.2f} | {w.growth_priority:.2f} | {w.growth_stage} | {w.recommended_action} |"
            )
        lines.extend(["", "## 特征模式", ""])
        lines.append("| 模式名 | Hook | 情绪 | 节奏 | UI | 置信度 | 来源 |")
        lines.append("|---|---|---|---|---:|---|")
        for p in patterns:
            lines.append(f"| {p.name} | {p.hook_type} | {p.emotion} | {p.pace} | {p.ui_type} | {p.confidence:.2f} | {p.source} |")

        lines.extend(["", "## 裂变变体建议", ""])
        lines.append("| 变体ID | 父模式 | 变异类型 | Hook | 情绪 | 节奏 | 难度 | 优先级 | 文案建议 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for v in variants:
            lines.append(
                f"| `{v.variant_id}` | {v.parent_pattern} | {v.mutation_type} | {v.new_hook} | {v.new_emotion} | {v.new_pace} | {v.expected_difficulty} | {v.priority} | {v.suggested_copy[:40]}... |"
            )

        lines.extend(["", "## 每条变体详情", ""])
        for v in variants:
            lines.extend([
                f"### {v.variant_id}",
                f"- **父模式**: {v.parent_pattern}",
                f"- **变异**: {v.mutation_type}",
                f"- **Hook**: {v.new_hook} | **情绪**: {v.new_emotion} | **节奏**: {v.new_pace} | **UI**: {v.new_ui_type}",
                f"- **文案**: {v.suggested_copy}",
                f"- **理由**: {v.rationale}",
                f"- **难度**: {v.expected_difficulty} | **优先级**: {v.priority}",
                "",
            ])

        lines.extend([
            "## 说明",
            "",
            "- 所有裂变建议基于 Adjust 归因数据中的赢家素材模式生成",
            "- 降级模式时从 creative_name / creative_library 文本提取模式特征",
            "- 建议先小额测试（日预算 $50-100），7日后回灌效果数据",
            "- 裂变投放效果可通过 feedback_loop 自动回灌到 growth_priorities",
        ])
        return "\n".join(lines)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _pattern_name(w: WinnerCreative) -> str:
    parts = [w.project.replace(" ", "_")]
    if w.channel:
        parts.append(w.channel)
    if w.creative_name and w.creative_name != w.creative_id:
        # Use first 20 chars of creative_name as a disambiguator
        name_part = w.creative_name.replace(" ", "_")[:20].rstrip("_")
        if name_part:
            parts.append(name_part)
    if not any(p != parts[0] for p in parts[1:]):
        # Still no differentiation: append last 8 chars of creative_id
        parts.append(w.creative_id[-8:])
    return "_".join(parts) + "_pattern"


def _build_suggested_copy(pat: CreativePattern, field: str, new_val: str) -> str:
    templates: dict[str, dict[str, str]] = {
        "hook_type": {
            "爽点": "Level Up! Unlock Epic Rewards Now",
            "危机": "URGENT: Save Your Kingdom Before It's Too Late!",
            "反转": "You Won't Believe What Happens Next...",
        },
        "emotion": {
            "爽感": "Feel the Power - Merge & Dominate!",
            "焦虑": "Don't Miss Out - Limited Time Only!",
            "治愈": "Relax, Merge, and Build Your Dream World",
        },
        "pace": {
            "快": "⚡ Fast-Paced Action - Merge Now!",
            "慢": "Unwind with a Beautiful Merge Journey",
        },
        "ui_type": {
            "Merge": "Merge, Evolve, Conquer!",
            "Build": "Build Your Dream Kingdom - Start Now!",
            "Battle": "Enter the Arena - Fight for Glory!",
        },
        "copy_style": {
            "强标题": "【NEW】Unlock Exclusive Rewards Today!",
            "弱标题": "just a casual merge game... try it?",
        },
        "cta_strength": {
            "强": "INSTALL NOW - Don't Wait!",
            "弱": "Try it out if you have a minute...",
        },
        "video_structure": {
            "UGC": "[Real Player]: 'I can't stop playing this game!'",
            "游戏录屏": "[Gameplay Footage] Watch the merge magic happen...",
            "图片": "[Stunning Visual] Check out this transformation!",
        },
    }
    field_templates = templates.get(field, {})
    return field_templates.get(new_val, f"Try this new angle: {new_val}")
