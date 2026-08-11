from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult


class UnityConnector(BaseConnector):
    def __init__(self, api_key: str = None, project_id: str = None):
        super().__init__(api_key, project_id)
        self.platform = "unity"
        self.project_id = project_id
        self._mock_project = {
            "project_id": "unity_proj_001",
            "name": "Merge Cozy",
            "version": "1.5.2",
            "platforms": ["Android", "iOS"],
            "scenes": ["Main", "Game", "Menu", "Shop"],
            "scripts": 45,
        }

    def get_project_info(self, project_id: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, self._mock_project)

    def get_builds(self, project_id: str = None, platform: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        builds = [
            {"build_id": "build_001", "version": "1.5.2", "platform": "Android", "status": "success", "size_mb": 156, "created_at": "2026-07-05"},
            {"build_id": "build_002", "version": "1.5.2", "platform": "iOS", "status": "success", "size_mb": 210, "created_at": "2026-07-05"},
            {"build_id": "build_003", "version": "1.5.3b1", "platform": "Android", "status": "building", "size_mb": 0, "created_at": "2026-07-08"},
        ]
        if platform:
            builds = [b for b in builds if b["platform"].lower() == platform.lower()]
        return self._make_result(True, {"builds": builds})

    def trigger_build(self, project_id: str = None, platform: str = "Android", branch: str = "main") -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        build_id = f"build_{hash(platform + branch + str(datetime.now())) % 10000:04d}"
        return self._make_result(True, {
            "build_id": build_id,
            "platform": platform,
            "branch": branch,
            "status": "queued",
            "estimated_time_minutes": 15,
        })

    def get_build_status(self, build_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {
            "build_id": build_id,
            "status": "success",
            "progress": 100,
            "download_url": f"https://unity-builds.example.com/{build_id}.apk",
        })


class GitHubConnector(BaseConnector):
    def __init__(self, token: str = None, repo: str = None):
        super().__init__(token, repo)
        self.platform = "github"
        self.repo = repo
        self._mock_repo = {
            "repo": "game-studio/merge-cozy",
            "default_branch": "main",
            "stars": 125,
            "language": "C#",
        }

    def get_repo_info(self, repo: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, self._mock_repo)

    def get_branches(self, repo: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        branches = [
            {"name": "main", "last_commit": "abc123", "updated_at": "2026-07-08"},
            {"name": "develop", "last_commit": "def456", "updated_at": "2026-07-07"},
            {"name": "feature/new-economy", "last_commit": "ghi789", "updated_at": "2026-07-06"},
        ]
        return self._make_result(True, {"branches": branches})

    def get_pull_requests(self, state: str = "open", repo: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        prs = [
            {"number": 42, "title": "Add battle pass system", "state": "open", "author": "dev-1", "created_at": "2026-07-07"},
            {"number": 41, "title": "Fix economy balance", "state": "open", "author": "dev-2", "created_at": "2026-07-06"},
        ]
        return self._make_result(True, {"pull_requests": prs})

    def create_issue(self, title: str, body: str = "", repo: str = None, labels: List[str] = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        issue_number = hash(title + str(datetime.now())) % 1000
        return self._make_result(True, {
            "issue_number": issue_number,
            "title": title,
            "body": body,
            "state": "open",
            "labels": labels or [],
        })

    def trigger_workflow(self, workflow_id: str, branch: str = "main", repo: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        run_id = f"run_{hash(workflow_id + str(datetime.now())) % 10000:04d}"
        return self._make_result(True, {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "branch": branch,
            "status": "queued",
        })
