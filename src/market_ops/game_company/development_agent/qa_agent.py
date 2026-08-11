from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class QAResult:
    qa_id: str
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    bugs_found: List[Dict[str, Any]] = field(default_factory=list)
    performance_score: float = 0.0
    status: str = "pending"


class QAAgent:
    def __init__(self):
        self.results: Dict[str, QAResult] = {}

    def run_tests(self, project) -> QAResult:
        if isinstance(project, dict):
            name = project.get("name", "project")
            scripts = project.get("scripts", [])
            ui_elements = project.get("ui_elements", [])
            known_issues = project.get("known_issues", [])
        else:
            name = project.name
            scripts = project.scripts
            ui_elements = project.ui_elements
            known_issues = []
        
        bugs_found = self._detect_bugs(scripts, ui_elements, known_issues)
        performance_score = self._measure_performance(len(scripts), len(ui_elements))
        tests_run = 20 + len(scripts) * 5
        tests_passed = tests_run - len(bugs_found)

        result = QAResult(
            qa_id=f"qa_{hash(name) % 10000:04d}",
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=len(bugs_found),
            bugs_found=bugs_found,
            performance_score=performance_score,
            status=self._determine_status(tests_passed, tests_run),
        )

        self.results[result.qa_id] = result
        return result

    def test(self, project) -> QAResult:
        return self.run_tests(project)

    def test_full(self, project) -> QAResult:
        return self.run_tests(project)

    def _detect_bugs(self, scripts, ui_elements, known_issues) -> List[Dict[str, Any]]:
        bugs = []
        
        if len(scripts) < 3:
            bugs.append({"severity": "critical", "description": "Missing core scripts"})
        
        if len(ui_elements) < 5:
            bugs.append({"severity": "medium", "description": "Incomplete UI"})
        
        for issue in known_issues:
            bugs.append({"severity": "medium", "description": issue})
        
        return bugs

    def _measure_performance(self, script_count: int, ui_count: int) -> float:
        base_score = 85.0
        
        if script_count > 10:
            base_score -= 5
        if ui_count > 10:
            base_score -= 3
        
        return min(base_score, 100)

    def _determine_status(self, passed: int, total: int) -> str:
        ratio = passed / total
        if ratio >= 0.95:
            return "ready"
        elif ratio >= 0.85:
            return "needs_fixes"
        else:
            return "blocked"

    def run_tests_demo(self) -> QAResult:
        project = {"name": "Cozy Witch Garden", "scripts": ["a", "b", "c", "d", "e", "f"], "ui_elements": ["x", "y", "z"]}
        return self.run_tests(project)
