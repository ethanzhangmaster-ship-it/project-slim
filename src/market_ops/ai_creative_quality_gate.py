"""Phase 2: AI Creative Quality Gate.

Evaluates AI-generated creatives for ad monetization quality,
NOT artistic beauty. The gate answers: "Would this work as a
Facebook ad?" not "Is this a pretty picture?"

Scoring (100pts):
  DNA Matching:      40pts (does it follow the spec?)
  FB Ad Structure:   30pts (does it have ad elements?)
  CTR Factors:       20pts (subject + color + emotion)
  AI Risk Detection: 10pts (is it fantasy art instead of ad?)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .creative_blueprint_validator import CreativeGenerationSpec
from .lovart_generator_adapter import GeneratedCreative


# ═══════════════════════════════════════════════════════════
# 1. Quality Gate
# ═══════════════════════════════════════════════════════════

@dataclass
class QualityGateResult:
    """Quality assessment for a single AI-generated creative."""
    creative_id: str = ""
    dna_score: int = 0           # 0-40
    ad_structure_score: int = 0  # 0-30
    ctr_score: int = 0           # 0-20
    risk_score: int = 0          # 0-10 (lower = more risk detected)
    total: int = 0               # 0-100
    status: str = "FAIL"      # PASS / REVIEW / FAIL
    issues: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "dna_score": self.dna_score,
            "ad_structure_score": self.ad_structure_score,
            "ctr_score": self.ctr_score,
            "risk_score": self.risk_score,
            "total": self.total,
            "status": self.status,
            "issues": self.issues,
            "checks": self.checks,
        }


class AICreativeQualityGate:
    """Quality gate for AI-generated ad creatives.

    PASS:  >= 80  → ready for Facebook testing
    REVIEW: 60-79 → needs human review
    FAIL:  < 60   → discard
    """

    PASS_THRESHOLD = 80
    REVIEW_THRESHOLD = 60

    # ── DNA elements to check against ──
    DNA_ELEMENTS = {
        "hook": ["character", "witch", "dragon", "showcase"],
        "color": ["purple", "magic", "glow", "fantasy"],
        "composition": ["center", "focal", "main", "focus"],
        "reward": ["evolution", "transform", "dragon", "merge"],
    }

    # ── Ad structure elements ──
    AD_ELEMENTS = [
        "main_visual",      # strong focal point
        "reward_visible",    # reward/result shown
        "conversion_hook",   # reason to click/install
        "clear_theme",       # game genre is obvious
        "mobile_format",     # square/vertical, mobile-friendly
        "action_energy",     # dynamic, not static
    ]

    # ── AI risk patterns (things to detect and penalize) ──
    AI_RISK_PATTERNS = [
        ("fantasy_poster", ["illustration", "poster", "concept art", "painting"]),
        ("character_portrait", ["portrait", "headshot", "face only", "bust"]),
        ("no_game_feeling", ["no ui", "no game", "no gameplay", "just art"]),
        ("no_progression", ["static", "no change", "no evolution", "no merge"]),
        ("too_much_text", ["text heavy", "paragraph", "long text", "description"]),
        ("complex_scene", ["cluttered", "busy", "too many elements", "chaotic"]),
        ("wrong_style", ["realistic", "3d render", "photorealistic", "photo"]),
        ("low_contrast", ["flat", "muted", "washed out", "no contrast"]),
    ]

    def evaluate(self, creative: GeneratedCreative, spec: CreativeGenerationSpec) -> QualityGateResult:
        """Evaluate a generated creative against its source spec."""
        prompt_text = creative.prompt.prompt_text.lower()
        checks: list[str] = []
        issues: list[str] = []

        # 1. DNA Matching (40pts)
        dna = self._check_dna_match(prompt_text, checks, issues)

        # 2. FB Ad Structure (30pts)
        ad_struct = self._check_ad_structure(prompt_text, checks, issues)

        # 3. CTR Factors (20pts)
        ctr = self._check_ctr_factors(spec, checks, issues)

        # 4. AI Risk Detection (10pts)
        risk = self._check_ai_risks(prompt_text, checks, issues)

        total = dna + ad_struct + ctr + risk
        if total >= self.PASS_THRESHOLD:
            status = "PASS"
        elif total >= self.REVIEW_THRESHOLD:
            status = "REVIEW"
        else:
            status = "FAIL"

        return QualityGateResult(
            creative_id=creative.creative_id,
            dna_score=dna,
            ad_structure_score=ad_struct,
            ctr_score=ctr,
            risk_score=risk,
            total=total,
            status=status,
            issues=issues,
            checks=checks,
        )

    def evaluate_batch(
        self, creatives: list[GeneratedCreative], specs: list[CreativeGenerationSpec]
    ) -> list[QualityGateResult]:
        """Evaluate all creatives against their specs."""
        spec_map = {s.source_pattern: s for s in specs}
        results = []
        for c in creatives:
            spec = spec_map.get(c.source_blueprint)
            if spec is None:
                spec = specs[0] if specs else CreativeGenerationSpec()
            results.append(self.evaluate(c, spec))
        return results

    # ── DNA Matching (40pts) ──

    def _check_dna_match(self, prompt: str, checks: list[str], issues: list[str]) -> int:
        score = 0
        for dim, keywords in self.DNA_ELEMENTS.items():
            matches = sum(1 for kw in keywords if kw in prompt)
            if matches >= 3:
                score += 10
                checks.append(f"DNA_{dim}: {matches} keywords matched")
            elif matches >= 1:
                score += 5
                checks.append(f"DNA_{dim}: {matches} keyword(s) partial")
            else:
                issues.append(f"DNA_{dim}: no keywords found in prompt")
        return min(score, 40)

    # ── FB Ad Structure (30pts) ──

    def _check_ad_structure(self, prompt: str, checks: list[str], issues: list[str]) -> int:
        per_element = 30 // len(self.AD_ELEMENTS)
        score = 0

        element_keywords = {
            "main_visual": ["main", "center", "focal", "focus", "character"],
            "reward_visible": ["reward", "evolution", "transform", "dragon", "result"],
            "conversion_hook": ["hook", "click", "attention", "showcase"],
            "clear_theme": ["merge", "witch", "magic", "game", "puzzle"],
            "mobile_format": ["1080", "square", "mobile", "vertical"],
            "action_energy": ["action", "energy", "dynamic", "impact", "transformation"],
        }

        for elem, keywords in element_keywords.items():
            if any(kw in prompt for kw in keywords):
                score += per_element
                checks.append(f"ad_{elem}: present")
            else:
                issues.append(f"ad_{elem}: not detected")

        return min(score, 30)

    # ── AI Risk Detection (10pts) ──

    def _check_ai_risks(self, prompt: str, checks: list[str], issues: list[str]) -> int:
        score = 10
        per_risk = max(10 // len(self.AI_RISK_PATTERNS), 1)

        # Filter out negative-context keywords (e.g., "not illustration" in STYLE_GUARD)
        # Split by "not" to isolate negative instructions
        safe_prompt = prompt
        # Remove phrases that appear after "not " in the prompt (negative guard clauses)
        parts = prompt.split("not ")
        if len(parts) > 1:
            # Keep only the first part (before any "not") + check for risk
            # The negative parts after "not" are instructions to avoid, not risks
            safe_prompt = parts[0]

        for risk_name, risk_keywords in self.AI_RISK_PATTERNS:
            if any(kw in safe_prompt for kw in risk_keywords):
                score -= per_risk
                issues.append(f"AI_RISK: {risk_name} detected")
            else:
                checks.append(f"AI_RISK: {risk_name} CLEAN")

        # Only check negative signals in the main (non-guard) prompt
        negative_signals = ["illustration", "painting", "concept art", "cinematic",
                           "portrait", "realistic", "photorealistic"]
        for signal in negative_signals:
            if signal in safe_prompt:
                score -= per_risk
                issues.append(f"AI_RISK: negative_pattern '{signal}' in prompt")

        return max(score, 0)

    # ── CTR Factors (20pts) ──

    def _check_ctr_factors(self, spec: CreativeGenerationSpec, checks: list[str], issues: list[str]) -> int:
        """Evaluate CTR-driving visual factors: subject(7) + color(7) + emotion(6)."""
        s = spec.hook_scene
        v = spec.visual_constraints
        r = spec.reward_moment
        score = 0

        # Subject prominence (7pts)
        has_center = (s.position == "center")
        has_named_char = bool(s.character and s.character not in ("", "character"))
        if has_center and has_named_char:
            subj = 7
            checks.append("CTR_subject: center + named character (7)")
        elif has_center or has_named_char:
            subj = 4
            checks.append(f"CTR_subject: partial ({'center' if has_center else 'named'}) (4)")
        else:
            subj = 1
            issues.append("CTR_subject: no clear focal point (1)")
        score += subj

        # Color contrast (7pts)
        high_contrast_colors = {"purple", "purple_magic", "warm_red", "mystical_blue"}
        if v.color_palette in high_contrast_colors:
            color = 7
            checks.append(f"CTR_color: high contrast '{v.color_palette}' (7)")
        elif v.color_palette and v.color_palette not in ("", "color", "theme"):
            color = 4
            checks.append(f"CTR_color: medium '{v.color_palette}' (4)")
        else:
            color = 1
            issues.append("CTR_color: no color directive (1)")
        score += color

        # Emotion expression (6pts)
        high_emotions = {"surprise", "excitement", "wow", "awe"}
        if r.reward_emotion in high_emotions:
            emotion = 6
            checks.append(f"CTR_emotion: high impact '{r.reward_emotion}' (6)")
        elif r.reward_emotion and r.reward_emotion not in ("", "neutral"):
            emotion = 3
            checks.append(f"CTR_emotion: medium '{r.reward_emotion}' (3)")
        else:
            emotion = 1
            issues.append("CTR_emotion: weak or missing (1)")
        score += emotion

        return score


# ═══════════════════════════════════════════════════════════
# 2. Batch Quality Report
# ═══════════════════════════════════════════════════════════

@dataclass
class BatchQualityReport:
    """Quality report for a batch of generated creatives."""
    batch_id: str = ""
    total: int = 0
    passed: int = 0
    review: int = 0
    failed: int = 0
    average_score: float = 0.0
    results: list[QualityGateResult] = field(default_factory=list)

    def print_report(self) -> str:
        lines = []
        lines.append("=" * 65)
        lines.append("  AI Creative Quality Gate Report")
        lines.append("=" * 65)
        lines.append(f"  Batch: {self.batch_id}")
        lines.append(f"  Total: {self.total}")
        lines.append(f"  PASS:   {self.passed}  (>= {AICreativeQualityGate.PASS_THRESHOLD})")
        lines.append(f"  REVIEW: {self.review}  ({AICreativeQualityGate.REVIEW_THRESHOLD}-{AICreativeQualityGate.PASS_THRESHOLD-1})")
        lines.append(f"  FAIL:   {self.failed}  (< {AICreativeQualityGate.REVIEW_THRESHOLD})")
        lines.append(f"  Average Score: {self.average_score:.0f}/100")

        # Per-creative detail
        lines.append("")
        lines.append(f"  {'ID':<35} {'DNA':>4} {'Ad':>3} {'CTR':>4} {'Risk':>5} {'Total':>5} {'Status':>7}")
        lines.append(f"  {'─'*68}")
        for r in self.results:
            lines.append(f"  {r.creative_id:<35} {r.dna_score:>4} {r.ad_structure_score:>3} "
                         f"{r.ctr_score:>4} {r.risk_score:>5} {r.total:>5} {r.status:>7}")

        # Issues summary
        all_issues = [i for r in self.results for i in r.issues]
        if all_issues:
            lines.append("")
            lines.append(f"  Issues ({len(all_issues)}):")
            for issue in all_issues[:10]:
                lines.append(f"    - {issue}")
            if len(all_issues) > 10:
                lines.append(f"    ... and {len(all_issues) - 10} more")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total": self.total,
            "passed": self.passed,
            "review": self.review,
            "failed": self.failed,
            "average_score": round(self.average_score, 1),
            "results": [r.to_dict() for r in self.results],
        }