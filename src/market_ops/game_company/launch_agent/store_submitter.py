from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class SubmitResult:
    submit_id: str
    store: str
    status: str = "pending"
    version: str = ""
    review_days: float = 0.0
    feedback: List[str] = field(default_factory=list)


class StoreSubmitter:
    def __init__(self):
        self.submissions: Dict[str, SubmitResult] = {}

    def submit(self, app_data, store: str = "app_store") -> SubmitResult:
        status = "approved"
        feedback = []
        
        if not app_data.get("icon"):
            status = "rejected"
            feedback.append("Missing icon")
        
        if not app_data.get("screenshots"):
            status = "rejected"
            feedback.append("Missing screenshots")

        result = SubmitResult(
            submit_id=f"submit_{hash(str(app_data)) % 10000:04d}",
            store=store,
            status=status,
            version="1.0.0",
            review_days=self._get_review_days(store),
            feedback=feedback,
        )

        self.submissions[result.submit_id] = result
        return result

    def submit_all(self, app_data) -> List[SubmitResult]:
        results = []
        for store in ["app_store", "google_play"]:
            results.append(self.submit(app_data, store))
        return results

    def _get_review_days(self, store: str) -> float:
        if store == "app_store":
            return 2.0
        return 1.0

    def submit_demo(self) -> SubmitResult:
        app_data = {
            "name": "Cozy Witch Garden",
            "icon": "icon.png",
            "screenshots": ["s1.png", "s2.png", "s3.png"],
        }
        return self.submit(app_data, "app_store")
