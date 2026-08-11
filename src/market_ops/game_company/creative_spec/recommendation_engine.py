from typing import Dict, List, Any, Optional


class RecommendationEngine:
    def __init__(self):
        self._recommendations = {
            "subject_center": {
                "condition": lambda d: d.get("subject_center", 1.0) < 0.40,
                "issues": ["Subject not centered"],
                "suggestions": ["Move subject to center 40% of frame", "Use radial gradient spotlight on subject"],
                "priority": "high",
                "impact": "ROAS +0.074 (P1 policy)",
            },
            "contrast": {
                "condition": lambda d: d.get("contrast", 1.0) < 0.15,
                "issues": ["Contrast too low"],
                "suggestions": ["Use S-curve to boost contrast", "Add pure black and white areas", "Increase shadow depth by 30%"],
                "priority": "high",
                "impact": "ROAS +0.047 (P2 policy)",
            },
            "saturation": {
                "condition": lambda d: d.get("saturation", 1.0) < 0.45,
                "issues": ["Saturation too low"],
                "suggestions": ["Increase overall saturation by 15-20%", "Boost warm tones (golden/amber)", "Use vibrant color grading"],
                "priority": "high",
                "impact": "ROAS +0.34 (causal driver)",
            },
            "text_density": {
                "condition": lambda d: d.get("text_density", 0) > 0.015,
                "issues": ["Too much text in first 3 seconds"],
                "suggestions": ["Remove all text from first 3 seconds", "Use icons instead of text labels", "Move brand logo after 3s mark"],
                "priority": "high",
                "impact": "ROAS +0.054 (P5 policy)",
            },
            "motion": {
                "condition": lambda d: d.get("motion_change", 1.0) < 0.10,
                "issues": ["No visual structure change within 3s"],
                "suggestions": ["Add scene cut at 0.8-3.0s", "Add character movement/animation", "Add UI popup element as transition"],
                "priority": "medium",
                "impact": "56% of low-ROAS videos fail here (P3)",
            },
            "reward": {
                "condition": lambda d: d.get("reward_surge", 1.0) < 0.05,
                "issues": ["No visual reward event after 6s"],
                "suggestions": ["Add bright flash/particle effect at 6s", "Show victory/evolution screen", "Increase brightness+30% and saturation+20% at reward moment"],
                "priority": "high",
                "impact": "32% of low-ROAS videos fail at reward (P4)",
            },
            "cta": {
                "condition": lambda d: not d.get("has_cta", True),
                "issues": ["Missing CTA"],
                "suggestions": ["Add CTA button in last 3 seconds", "Use pulse animation on CTA", "Add social proof near CTA"],
                "priority": "high",
                "impact": "Required conversion element",
            },
            "aspect_ratio": {
                "condition": lambda d: d.get("aspect_ratio", "9:16") != "9:16",
                "issues": ["Wrong aspect ratio"],
                "suggestions": ["Convert to 9:16 vertical format", "Top 5 videos all use 9:16"],
                "priority": "medium",
                "impact": "Most high-ROAS videos use 9:16",
            },
            "palette": {
                "condition": lambda d: d.get("palette", "warm") != "warm",
                "issues": ["Wrong color palette"],
                "suggestions": ["Shift to warm golden/amber palette", "Reduce cool/blue tones", "Use soft purples and pastels as accent"],
                "priority": "medium",
                "impact": "Warm:Cool = 1039:790 in data",
            },
            "hook_type": {
                "condition": lambda d: d.get("hook_type", "collection") != "collection",
                "issues": ["Non-optimal hook type"],
                "suggestions": ["Use collection hook (62.1% of winners)", "If using curiosity hook, ensure reward payoff is strong"],
                "priority": "medium",
                "impact": "Collection = 62.1% of all creatives",
            },
        }

    def analyze(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        issues = []
        suggestions = []
        improvements = []

        for rule_id, rule in self._recommendations.items():
            if rule["condition"](video_data):
                issues.extend(rule["issues"])
                suggestions.extend(rule["suggestions"])
                improvements.append({
                    "rule": rule_id,
                    "priority": rule["priority"],
                    "impact": rule["impact"],
                    "suggestions": rule["suggestions"],
                })

        total_improvements = len(improvements)
        estimated_roas_gain = self._estimate_gain(improvements)

        return {
            "total_issues": total_improvements,
            "high_priority_count": sum(1 for i in improvements if i["priority"] == "high"),
            "issues": issues,
            "improvements": improvements,
            "estimated_roas_gain": round(estimated_roas_gain, 3),
            "optimization_potential": self._get_potential(total_improvements),
        }

    def _estimate_gain(self, improvements: List[Dict]) -> float:
        gain_map = {
            "contrast": 0.047, "text_density": 0.054, "subject_center": 0.074,
            "reward": 0.017, "saturation": 0.05, "motion": 0.022,
            "cta": 0.03, "aspect_ratio": 0.02, "palette": 0.02, "hook_type": 0.05,
        }
        total = 0.0
        for imp in improvements:
            total += gain_map.get(imp["rule"], 0.01)
        return min(total, 0.30)

    def _get_potential(self, count: int) -> str:
        if count == 0:
            return "EXCELLENT"
        elif count <= 2:
            return "GOOD"
        elif count <= 4:
            return "MODERATE"
        else:
            return "POOR"

    def get_stats(self) -> Dict[str, Any]:
        return {"total_recommendations": len(self._recommendations)}
