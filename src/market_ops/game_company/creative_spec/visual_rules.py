from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


REAL_VISUAL_RULES = {
    "first_frame": {
        "contrast_min": 0.15,
        "saturation_min": 0.45,
        "subject_center_percent": 0.40,
        "subject_fill_min": 0.30,
        "text_density_max": 0.015,
    },
    "color": {
        "palette": "warm",
        "warm_count": 1039,
        "cool_count": 790,
        "entropy_min": 7.8,
        "dominant_palette": "warm golden yellows, soft purples, pastel blues",
    },
    "timeline": {
        "hook_0_0_8s": "High contrast subject in center 40%, no text, no UI",
        "motion_0_8_3s": "At least 1 visual structure change, no text overlay",
        "gameplay_3_6s": "Core gameplay loop, minimal UI (density < 0.06)",
        "reward_6_9s": "Visual reward event: brighter, more saturated, particles",
        "cta_9s_end": "CTA with consistent visual quality, pulse animation",
    },
    "causal_impact": {
        "hook_contrast": 0.3844,
        "hook_saturation": 0.3385,
        "mid_center_contrast": 0.1363,
        "hook_top_color_ratio": 0.1023,
        "mid_brightness": 0.0775,
        "hook_edge_density": -0.3144,
        "motion_edge_delta": -0.1717,
        "mid_edge_density": -0.1702,
        "hook_text_density": -0.1102,
    },
    "policy_pass_rates": {
        "P1": {"description": "Subject in center 40% within 0.8s", "high_roas_pass": 0.7308, "low_roas_block": 0.8462},
        "P2": {"description": "First frame contrast >= 0.15", "high_roas_pass": 0.9487, "low_roas_block": 0.2949},
        "P3": {"description": "Visual structure change within 3s", "high_roas_pass": 0.2949, "low_roas_block": 0.5128},
        "P4": {"description": "Reward visual surge after 6s", "high_roas_pass": 0.4872, "low_roas_block": 0.6154},
        "P5": {"description": "Min text density first 3s", "high_roas_pass": 0.8846, "low_roas_block": 0.0128},
    },
    "anti_patterns": [
        "Do NOT start with empty background/landscape",
        "Do NOT start with text-only frame",
        "Do NOT start with gameplay UI without character",
        "Do NOT use center-empty composition",
        "Do NOT use flat/soft lighting in first frame",
        "Do NOT use low-contrast gradients",
        "Do NOT keep same frame composition for >2s in first 3 seconds",
        "Do NOT end on the same visual state as middle section",
        "Do NOT use text-only CTA as the only payoff",
        "Do NOT fade between similar compositions",
    ],
}


@dataclass
class VisualSpec:
    first_frame_contrast_min: float = 0.15
    first_frame_saturation_min: float = 0.45
    subject_center_percent: float = 0.40
    subject_fill_min: float = 0.30
    text_density_max: float = 0.015
    palette: str = "warm"
    entropy_min: float = 7.8
    timeline_rules: Dict[str, str] = field(default_factory=dict)
    causal_impact: Dict[str, float] = field(default_factory=dict)
    policy_pass_rates: Dict[str, Dict[str, float]] = field(default_factory=dict)
    anti_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_frame": {
                "contrast_min": self.first_frame_contrast_min,
                "saturation_min": self.first_frame_saturation_min,
                "subject_center_percent": self.subject_center_percent,
                "subject_fill_min": self.subject_fill_min,
                "text_density_max": self.text_density_max,
            },
            "color": {"palette": self.palette, "entropy_min": self.entropy_min},
            "timeline": self.timeline_rules,
            "causal_impact": self.causal_impact,
            "policy_pass_rates": self.policy_pass_rates,
            "anti_patterns": self.anti_patterns,
        }


class VisualRules:
    def __init__(self):
        self.spec = VisualSpec(
            timeline_rules=REAL_VISUAL_RULES["timeline"],
            causal_impact=REAL_VISUAL_RULES["causal_impact"],
            policy_pass_rates=REAL_VISUAL_RULES["policy_pass_rates"],
            anti_patterns=REAL_VISUAL_RULES["anti_patterns"],
        )

    def get_rules(self) -> List[Dict[str, Any]]:
        rules = []
        rules.append({"id": "V1", "category": "first_frame", "rule": f"Contrast >= {self.spec.first_frame_contrast_min}", "priority": "high"})
        rules.append({"id": "V2", "category": "first_frame", "rule": f"Saturation >= {self.spec.first_frame_saturation_min}", "priority": "high"})
        rules.append({"id": "V3", "category": "framing", "rule": f"Subject in center {self.spec.subject_center_percent*100:.0f}% of frame", "priority": "high"})
        rules.append({"id": "V4", "category": "framing", "rule": f"Subject fills >= {self.spec.subject_fill_min*100:.0f}% of frame", "priority": "medium"})
        rules.append({"id": "V5", "category": "text", "rule": f"Text density < {self.spec.text_density_max} in first 3s", "priority": "high"})
        rules.append({"id": "V6", "category": "color", "rule": f"Use {self.spec.palette} palette (warm preferred)", "priority": "high"})
        rules.append({"id": "V7", "category": "color", "rule": f"Color entropy >= {self.spec.entropy_min}", "priority": "medium"})
        rules.append({"id": "V8", "category": "motion", "rule": "Visual structure change within 0.8-3.0s", "priority": "high"})
        rules.append({"id": "V9", "category": "reward", "rule": "Visual reward event after 6s (brighter + more saturated)", "priority": "high"})
        return rules

    def get_anti_patterns(self) -> List[str]:
        return list(self.spec.anti_patterns)

    def get_causal_impact(self) -> Dict[str, float]:
        return dict(self.spec.causal_impact)

    def get_top_drivers(self, n: int = 3) -> List[Dict[str, Any]]:
        pos = [(k, v) for k, v in self.spec.causal_impact.items() if v > 0]
        pos.sort(key=lambda x: -x[1])
        return [{"feature": k, "impact": v} for k, v in pos[:n]]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_rules": len(self.get_rules()),
            "total_anti_patterns": len(self.spec.anti_patterns),
            "top_positive_driver": self.get_top_drivers(1)[0] if self.get_top_drivers() else None,
            "contrast_min": self.spec.first_frame_contrast_min,
            "saturation_min": self.spec.first_frame_saturation_min,
        }
