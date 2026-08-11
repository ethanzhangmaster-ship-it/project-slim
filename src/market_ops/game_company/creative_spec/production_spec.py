from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass
class ProductionSpec:
    project: str = "P04 Witch"
    hook: Dict[str, Any] = field(default_factory=dict)
    storyboard: List[Dict[str, Any]] = field(default_factory=list)
    visual: Dict[str, Any] = field(default_factory=dict)
    reward: Dict[str, Any] = field(default_factory=dict)
    cta: Dict[str, Any] = field(default_factory=dict)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    score: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "hook": self.hook,
            "storyboard": self.storyboard,
            "visual": self.visual,
            "reward": self.reward,
            "cta": self.cta,
            "rules": self.rules,
            "score": self.score,
            "metadata": {**self.metadata, "generated_at": datetime.now().isoformat()},
        }

    def save_json(self, filepath: str) -> str:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    @classmethod
    def load_json(cls, filepath: str) -> "ProductionSpec":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            project=data.get("project", "P04 Witch"),
            hook=data.get("hook", {}),
            storyboard=data.get("storyboard", []),
            visual=data.get("visual", {}),
            reward=data.get("reward", {}),
            cta=data.get("cta", {}),
            rules=data.get("rules", []),
            score=data.get("score", {}),
            metadata=data.get("metadata", {}),
        )

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for r in self.rules:
            if r.get("id") == rule_id:
                return r
        return None

    def add_rule(self, rule: Dict[str, Any]):
        rule_ids = {r.get("id") for r in self.rules}
        if rule.get("id") not in rule_ids:
            self.rules.append(rule)

    def update_score(self, score: Dict[str, Any]):
        self.score.update(score)
