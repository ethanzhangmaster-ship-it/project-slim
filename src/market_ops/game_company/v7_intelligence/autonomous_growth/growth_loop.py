from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class GrowthIssue:
    issue_id: str
    category: str
    severity: str
    description: str
    affected_metrics: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class GrowthExperiment:
    experiment_id: str
    issue_id: str
    hypothesis: str
    action: str
    expected_outcome: str
    status: str = "proposed"


@dataclass
class GrowthLearning:
    learning_id: str
    experiment_id: str
    insight: str
    applicability: List[str] = field(default_factory=list)
    confidence: float = 0.0
    recorded_at: datetime = field(default_factory=datetime.now)


class GrowthLoop:
    """增长闭环，负责检测问题、提出实验、执行并学习。"""

    def __init__(self):
        self.issues: List[GrowthIssue] = []
        self.experiments: List[GrowthExperiment] = []
        self.learnings: List[GrowthLearning] = []
        self._issue_counter = 0
        self._exp_counter = 0
        self._learning_counter = 0

    def _next_issue_id(self) -> str:
        self._issue_counter += 1
        return f"issue_{datetime.now().strftime('%Y%m%d')}_{self._issue_counter:04d}"

    def _next_exp_id(self) -> str:
        self._exp_counter += 1
        return f"gexp_{datetime.now().strftime('%Y%m%d')}_{self._exp_counter:04d}"

    def _next_learning_id(self) -> str:
        self._learning_counter += 1
        return f"learn_{datetime.now().strftime('%Y%m%d')}_{self._learning_counter:04d}"

    def detect_issues(self, metrics: Dict[str, Any]) -> List[GrowthIssue]:
        """基于指标检测增长问题。"""
        issues = []
        if metrics.get("dau", 0) < metrics.get("dau_last_week", 0) * 0.9:
            issues.append(
                GrowthIssue(
                    issue_id=self._next_issue_id(),
                    category="retention",
                    severity="high",
                    description="DAU 环比下降超过 10%",
                    affected_metrics=["dau", "retention_d1", "retention_d7"],
                )
            )
        if metrics.get("cpi", 0) > metrics.get("cpi_target", 2.0):
            issues.append(
                GrowthIssue(
                    issue_id=self._next_issue_id(),
                    category="acquisition",
                    severity="medium",
                    description="CPI 超出目标值",
                    affected_metrics=["cpi", "roas"],
                )
            )
        if metrics.get("arpu", 0) < metrics.get("arpu_target", 0.5):
            issues.append(
                GrowthIssue(
                    issue_id=self._next_issue_id(),
                    category="monetization",
                    severity="medium",
                    description="ARPU 低于预期",
                    affected_metrics=["arpu", "ltv"],
                )
            )
        self.issues.extend(issues)
        return issues

    def propose_experiments(self, issues: List[GrowthIssue]) -> List[GrowthExperiment]:
        """针对检测出的问题提出实验方案。"""
        experiments = []
        for issue in issues:
            if issue.category == "retention":
                exp = GrowthExperiment(
                    experiment_id=self._next_exp_id(),
                    issue_id=issue.issue_id,
                    hypothesis="改进新手引导可提升次日留存",
                    action="简化前 3 关流程并增加奖励",
                    expected_outcome="retention_d1 +5%",
                )
            elif issue.category == "acquisition":
                exp = GrowthExperiment(
                    experiment_id=self._next_exp_id(),
                    issue_id=issue.issue_id,
                    hypothesis="更换创意素材可降低 CPI",
                    action="上线 3 组新的视频创意",
                    expected_outcome="cpi -15%",
                )
            elif issue.category == "monetization":
                exp = GrowthExperiment(
                    experiment_id=self._next_exp_id(),
                    issue_id=issue.issue_id,
                    hypothesis="限时礼包可提高付费转化",
                    action="在 Level 5 推出限时 50% 折扣礼包",
                    expected_outcome="conversion +3%, arpu +10%",
                )
            else:
                exp = GrowthExperiment(
                    experiment_id=self._next_exp_id(),
                    issue_id=issue.issue_id,
                    hypothesis="通用优化实验",
                    action="监控并微调",
                    expected_outcome="总体指标持平或微升",
                )
            experiments.append(exp)
        self.experiments.extend(experiments)
        return experiments

    def execute_experiments(self, experiments: List[GrowthExperiment]) -> List[Dict[str, Any]]:
        """执行实验并返回状态更新。"""
        results = []
        for exp in experiments:
            exp.status = "running"
            results.append({
                "experiment_id": exp.experiment_id,
                "status": "running",
                "started_at": datetime.now().isoformat(),
            })
        return results

    def learn_and_update(self, experiment_results: List[Dict[str, Any]]) -> List[GrowthLearning]:
        """从实验结果中提取学习并更新知识库。"""
        learnings = []
        for result in experiment_results:
            success = result.get("is_winner", False)
            insight = (
                f"实验 {result['experiment_id']} 成功：{result.get('hypothesis', '')}"
                if success
                else f"实验 {result['experiment_id']} 未达预期，需调整假设"
            )
            learning = GrowthLearning(
                learning_id=self._next_learning_id(),
                experiment_id=result["experiment_id"],
                insight=insight,
                applicability=[result.get("category", "general")],
                confidence=round(result.get("confidence", 0.8), 2),
            )
            learnings.append(learning)
        self.learnings.extend(learnings)
        return learnings
